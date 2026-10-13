# -*- coding: utf-8 -*-
"""
sidytrac_lite.gui
=================
基于 PySide6 (Qt) + Matplotlib 的桌面界面。

运行:  python gui.py
依赖:  PySide6, matplotlib  (pip install -r requirements.txt)
"""
import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QSplitter,
                               QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
                               QTableWidgetItem, QLabel, QMessageBox, QFileDialog,
                               QTabWidget, QHeaderView)
from PySide6.QtCore import Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from engine import Network, Substation, Section, Train, run_power_flow, feeder_chain


SUB_COLS = ["名称", "电压kV", "短路容量MVA", "X/R", "变压器MVA", "uk%"]
SEC_COLS = ["名称", "首端母线", "末端母线", "长度km", "r0 Ω/km", "x0 Ω/km"]
TRAIN_COLS = ["名称", "所在母线", "P MW", "Q Mvar"]


class MplCanvas(FigureCanvas):
    def __init__(self):
        self.fig = Figure(figsize=(6, 4), tight_layout=True)
        super().__init__(self.fig)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sidytrac Lite — 交流牵引供电潮流仿真（教学演示版）")
        self.resize(1200, 700)
        self.net = Network()
        self.last_result = None

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_left())
        splitter.addWidget(self._build_right())
        splitter.setSizes([520, 680])
        self.setCentralWidget(splitter)
        self._build_menu()
        self.load_demo(silent=True)

    # ---------------- 左侧面板 ----------------
    def _build_left(self):
        w = QWidget(); layout = QVBoxLayout(w)

        layout.addWidget(QLabel("<b>牵引变电所</b>"))
        self.t_sub = self._make_table(SUB_COLS)
        layout.addWidget(self.t_sub)
        layout.addLayout(self._btn_row("添加变电所", self.add_sub, "删除所选", self.del_sub(self.t_sub)))

        layout.addWidget(QLabel("<b>接触网供电臂 (区段)</b>"))
        self.t_sec = self._make_table(SEC_COLS)
        layout.addWidget(self.t_sec)
        layout.addLayout(self._btn_row("添加区段", self.add_sec, "删除所选", self.del_sec))

        layout.addWidget(QLabel("<b>列车负荷</b>"))
        self.t_tr = self._make_table(TRAIN_COLS)
        layout.addWidget(self.t_tr)
        layout.addLayout(self._btn_row("添加列车", self.add_train, "删除所选", self.del_train))

        run = QPushButton("▶ 运行潮流计算 (F5)")
        run.setStyleSheet("font-weight:bold; padding:8px;")
        run.clicked.connect(self.run_pf)
        layout.addWidget(run)
        return w

    def _make_table(self, cols):
        t = QTableWidget(0, len(cols))
        t.setHorizontalHeaderLabels(cols)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        return t

    def _btn_row(self, l1, f1, l2, f2):
        h = QHBoxLayout()
        b1, b2 = QPushButton(l1), QPushButton(l2)
        b1.clicked.connect(f1); b2.clicked.connect(f2)
        h.addWidget(b1); h.addWidget(b2)
        return h

    def _fill(self, table, rows):
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, v in enumerate(row):
                item = QTableWidgetItem(str(v))
                table.setItem(i, j, item)

    def _read(self, table, ncols, cast):
        out = []
        for i in range(table.rowCount()):
            row = []
            for j in range(ncols):
                it = table.item(i, j)
                txt = it.text().strip() if it else ""
                row.append(cast[j](txt) if txt else cast[j](0))
            out.append(row)
        return out

    # ---------------- 右侧面板 ----------------
    def _build_right(self):
        tabs = QTabWidget()
        self.canvas = MplCanvas()
        tabs.addTab(self.canvas, "电压曲线")

        self.t_res_bus = self._make_table(["母线", "电压kV", "标幺值", "相角°"])
        tabs.addTab(self.t_res_bus, "节点电压")

        self.t_res_br = self._make_table(["区段", "首端", "末端", "电流A", "损耗kW"])
        tabs.addTab(self.t_res_br, "支路结果")

        self.status = QLabel("就绪 | 提示：F5 运行，Ctrl+S 保存工程")
        right = QWidget(); rl = QVBoxLayout(right)
        rl.addWidget(tabs); rl.addWidget(self.status)
        return right

    # ---------------- 菜单 ----------------
    def _build_menu(self):
        from PySide6.QtGui import QAction, QKeySequence
        m = self.menuBar().addMenu("文件(&F)")
        for text, trig, sc in [("打开工程…", self.open_net, "Ctrl+O"),
                               ("保存工程…", self.save_net, "Ctrl+S")]:
            a = QAction(text, self); a.triggered.connect(trig)
            a.setShortcut(QKeySequence(sc)); m.addAction(a)
        m.addSeparator()
        a = QAction("载入示例", self); a.triggered.connect(self.load_demo); m.addAction(a)
        m2 = self.menuBar().addMenu("计算(&C)")
        a = QAction("运行潮流", self); a.triggered.connect(self.run_pf)
        a.setShortcut(QKeySequence("F5")); m2.addAction(a)

    # ---------------- 数据同步 ----------------
    def net_from_tables(self):
        subs, secs, trs = [], [], []
        for r in self._read(self.t_sub, 6, [str, float, float, float, float, float]):
            if not r[0]:
                continue
            subs.append(Substation(r[0], r[1] or 27.5, r[2] or 500,
                                   r[3] or 7.0, r[4] or 0.0, r[5] or 10.5))
        for r in self._read(self.t_sec, 6, [str, str, str, float, float, float]):
            if not r[0]:
                continue
            secs.append(Section(r[0], r[1], r[2], r[3] or 1.0, r[4] or 0.15, r[5] or 0.35))
        for r in self._read(self.t_tr, 4, [str, str, float, float]):
            if not r[0]:
                continue
            trs.append(Train(r[0], r[1], r[2] or 1.0, r[3] or 0.0))
        return Network(subs, secs, trs)

    def tables_from_net(self, net):
        self._fill(self.t_sub, [[s.name, s.voltage_kv, s.short_circuit_mva,
                                 s.x_r_ratio, s.transformer_mva, s.uk_percent]
                                for s in net.substations])
        self._fill(self.t_sec, [[s.name, s.from_bus, s.to_bus, s.length_km, s.r0, s.x0]
                                for s in net.sections])
        self._fill(self.t_tr, [[t.name, t.bus, t.p_mw, t.q_mvar] for t in net.trains])

    # ---------------- 槽函数 ----------------
    def add_sub(self):
        self.t_sub.insertRow(self.t_sub.rowCount())
        defaults = [f"SS{self.t_sub.rowCount()}", "27.5", "500", "7", "20", "10.5"]
        for j, v in enumerate(defaults):
            self.t_sub.setItem(self.t_sub.rowCount() - 1, j, QTableWidgetItem(v))

    def add_sec(self):
        n = self.t_sec.rowCount()
        self.t_sec.insertRow(n)
        for j, v in enumerate([f"SEC{n}", f"B{n}", f"B{n+1}", "5", "0.15", "0.35"]):
            self.t_sec.setItem(n, j, QTableWidgetItem(v))

    def add_train(self):
        n = self.t_tr.rowCount()
        self.t_tr.insertRow(n)
        for j, v in enumerate([f"T{n+1}", "B2", "8", "0"]):
            self.t_tr.setItem(n, j, QTableWidgetItem(v))

    def _del_selected(self, table):
        rows = sorted({i.row() for i in table.selectedIndexes()}, reverse=True)
        for r in rows:
            table.removeRow(r)

    def del_sub(self, table):
        return lambda: self._del_selected(table)

    def del_sec(self):
        self._del_selected(self.t_sec)

    def del_train(self):
        self._del_selected(self.t_tr)

    def run_pf(self):
        try:
            self.net = self.net_from_tables()
            res = run_power_flow(self.net)
        except Exception as e:
            QMessageBox.critical(self, "计算失败", str(e))
            return
        self.last_result = res
        bus_rows = [[b, f"{v['U_kV']:.3f}", f"{v['U_pu']:.4f}", f"{v['delta_deg']:.2f}"]
                    for b, v in res["buses"].items()]
        br_rows = [[b["section"], b["from"], b["to"], f"{b['I_A']:.1f}", f"{b['P_loss_kW']:.2f}"]
                   for b in res["branches"]]
        self._fill(self.t_res_bus, bus_rows)
        self._fill(self.t_res_br, br_rows)
        self._plot(res)
        state = "收敛" if res["converged"] else "未收敛!"
        self.status.setText(f"{state} | 迭代 {res['iterations']} 次 | 总网损 {res['losses_kW']:.1f} kW")

    def _plot(self, res):
        chain = feeder_chain(self.net)
        self.canvas.fig.clear()
        ax = self.canvas.fig.add_subplot(111)
        xs = [d for _, d in chain]
        ys = [res["buses"][b]["U_kV"] for b, _ in chain]
        ax.plot(xs, ys, "o-", color="#1f77b4", lw=2)
        for (b, d), u in zip(chain, ys):
            trs = [t.name for t in self.net.trains if t.bus == b]
            if trs:
                ax.annotate("🚆" + ",".join(trs), (d, u), textcoords="offset points",
                            xytext=(0, 10), ha="center", fontsize=9)
        ax.set_xlabel("距变电所距离 (km)")
        ax.set_ylabel("电压 (kV)")
        ax.set_title("供电臂电压分布")
        ax.grid(alpha=0.3)
        self.canvas.draw_idle()

    def open_net(self):
        p, _ = QFileDialog.getOpenFileName(self, "打开工程", "", "JSON (*.json)")
        if p:
            try:
                self.tables_from_net(Network.load(p))
                self.status.setText(f"已打开: {p}")
            except Exception as e:
                QMessageBox.critical(self, "打开失败", str(e))

    def save_net(self):
        p, _ = QFileDialog.getSaveFileName(self, "保存工程", "project.json", "JSON (*.json)")
        if p:
            self.net_from_tables().save(p)
            self.status.setText(f"已保存: {p}")

    def load_demo(self, silent=False):
        demo = Network(
            substations=[Substation("SS1", 27.5, 500, 7.0, 20, 10.5)],
            sections=[Section("SEC0", "SS1", "B1", 5.0)] +
                     [Section(f"SEC{i}", f"B{i}", f"B{i+1}", 5.0) for i in range(1, 6)],
            trains=[Train("T1", "B2", 8.0), Train("T2", "B5", 10.0)],
        )
        self.tables_from_net(demo)
        if not silent:
            self.status.setText("已载入示例：1 座变电所 + 6 个区段 + 2 列车，按 F5 运行")
        self.run_pf()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
