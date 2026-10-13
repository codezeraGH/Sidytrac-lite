# -*- coding: utf-8 -*-
"""
sidytrac_lite.engine
====================
交流牵引供电系统稳态潮流计算引擎（教学演示级）。

模型假设（简化）：
- 单相 27.5 kV 等值网络，相量潮流计算，仅支持辐射状（radial）供电臂
- 牵引变电所 = 平衡节点(slack)，可选系统等值阻抗与变压器阻抗
- 接触网供电臂 = 串联阻抗 z = (r0 + j x0) * L
- 列车 = 恒功率负荷 P + jQ
- 求解方法：前推回代法 (Backward/Forward Sweep)

注意：仅用于教学/原理演示，不能用于工程设计与保护整定。
"""
from __future__ import annotations

import json
import math
import cmath
from dataclasses import dataclass, field, asdict


@dataclass
class Substation:
    name: str                      # 兼作 slack 母线名
    voltage_kv: float = 27.5
    short_circuit_mva: float = 500.0   # 系统等值短路容量
    x_r_ratio: float = 7.0
    transformer_mva: float = 0.0       # 0 = 忽略变压器阻抗
    uk_percent: float = 10.5


@dataclass
class Section:
    name: str
    from_bus: str
    to_bus: str
    length_km: float
    r0: float = 0.15    # Ω/km
    x0: float = 0.35    # Ω/km


@dataclass
class Train:
    name: str
    bus: str
    p_mw: float
    q_mvar: float = 0.0


@dataclass
class Network:
    substations: list = field(default_factory=list)
    sections: list = field(default_factory=list)
    trains: list = field(default_factory=list)

    # ---------- 序列化 ----------
    def to_dict(self):
        return {"substations": [asdict(s) for s in self.substations],
                "sections": [asdict(s) for s in self.sections],
                "trains": [asdict(t) for t in self.trains]}

    @classmethod
    def from_dict(cls, d):
        return cls([Substation(**s) for s in d.get("substations", [])],
                   [Section(**s) for s in d.get("sections", [])],
                   [Train(**t) for t in d.get("trains", [])])

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    # ---------- 拓扑 ----------
    def buses(self):
        bs = set()
        for s in self.sections:
            bs.add(s.from_bus); bs.add(s.to_bus)
        for t in self.trains:
            bs.add(t.bus)
        for s in self.substations:
            bs.add(s.name)
        return bs

    def radial_order(self, root):
        """DFS 生成访问顺序；返回 (order, parent_bus, parent_z, parent_sec)。"""
        adj = {}
        for sec in self.sections:
            z = complex(sec.r0 * sec.length_km, sec.x0 * sec.length_km)
            adj.setdefault(sec.from_bus, []).append((sec.to_bus, z, sec))
            adj.setdefault(sec.to_bus, []).append((sec.from_bus, z, sec))
        order, parent_bus, parent_z, parent_sec = [root], {root: None}, {root: 0j}, {root: None}
        seen = {root}
        stack = [root]
        while stack:
            u = stack.pop()
            for v, z, sec in adj.get(u, []):
                if v not in seen:
                    seen.add(v)
                    parent_bus[v] = u
                    parent_z[v] = z
                    parent_sec[v] = sec
                    order.append(v)
                    stack.append(v)
        if len(seen) != len(self.buses()):
            raise ValueError("网络非辐射状或存在孤立节点：本引擎仅支持辐射状供电臂")
        return order, parent_bus, parent_z, parent_sec


def run_power_flow(net: Network, max_iter: int = 100, tol: float = 1e-9):
    """前推回代潮流。返回结果 dict。"""
    if not net.substations:
        raise ValueError("至少需要一个牵引变电所")
    sub = net.substations[0]
    root, V_base = sub.name, sub.voltage_kv

    # 电源等值阻抗（Ω）
    Zsrc = 0j
    if sub.short_circuit_mva > 0:
        Zs = V_base ** 2 / sub.short_circuit_mva
        Zsrc += cmath.rect(Zs, math.atan(sub.x_r_ratio))
    if sub.transformer_mva > 0:
        Ztr = sub.uk_percent / 100 * V_base ** 2 / sub.transformer_mva
        Zsrc += 1j * Ztr  # 近似纯电抗

    order, pbus, pz, psec = net.radial_order(root)

    S = {b: 0j for b in net.buses()}
    for tr in net.trains:
        S[tr.bus] = S.get(tr.bus, 0j) + complex(tr.p_mw, tr.q_mvar)

    V = {b: complex(V_base, 0) for b in order}
    converged, it = False, 0
    I_branch = {}
    for it in range(1, max_iter + 1):
        # ---- 回代：支路电流（kA = MVA/kV）----
        I_inj = {b: (S[b] / V[b]).conjugate() if V[b] != 0 else 0j
                 for b in order}
        children = {b: [] for b in order}
        for b in order[1:]:
            children[pbus[b]].append(b)
        for b in reversed(order[1:]):
            p = pbus[b]
            I_branch[(p, b)] = I_inj[b] + sum(I_branch[(b, c)] for c in children[b])
        I_root = sum(I_branch[(root, c)] for c in children[root])
        # ---- 前推：节点电压 ----
        err = 0.0
        V_new = {}
        V_new[root] = V_base - Zsrc * I_root
        for b in order[1:]:
            p = pbus[b]
            V_new[b] = V_new[p] - pz[b] * I_branch[(p, b)]
            err = max(err, abs(V_new[b] - V[b]))
        V = V_new
        if err < tol:
            converged = True
            break

    # ---- 结果整理 ----
    buses_out = {b: {"U_kV": abs(v), "U_pu": abs(v) / V_base,
                     "delta_deg": math.degrees(cmath.phase(v))}
                 for b, v in V.items()}
    branches, total_loss = [], 0.0
    for b in order[1:]:
        z, i = pz[b], I_branch[(pbus[b], b)]
        loss = abs(i) ** 2 * z.real * 1000  # kW
        total_loss += loss
        branches.append({"section": psec[b].name, "from": pbus[b], "to": b,
                         "I_A": abs(i) * 1000, "P_loss_kW": loss})
    if Zsrc:
        total_loss += abs(I_root) ** 2 * Zsrc.real * 1000
    return {"buses": buses_out, "branches": branches, "converged": converged,
            "iterations": it, "losses_kW": total_loss, "V_base_kV": V_base,
            "root": root}


def feeder_chain(net: Network):
    """返回供电臂的 (bus, 距变电所 km) 列表，用于绘制电压曲线。"""
    if not net.substations:
        return []
    order, pbus, pz, psec = net.radial_order(net.substations[0].name)
    dist = {order[0]: 0.0}
    for b in order[1:]:
        dist[b] = dist[pbus[b]] + psec[b].length_km
    return [(b, dist[b]) for b in order]
