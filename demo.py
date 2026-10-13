# -*- coding: utf-8 -*-
"""命令行示例：构建示例网络并运行潮流。"""
from engine import Network, Substation, Section, Train, run_power_flow, feeder_chain

net = Network(
    substations=[Substation("SS1", 27.5, 500, 7.0, 20, 10.5)],
    sections=[Section("SEC0", "SS1", "B1", 5.0)] +
             [Section(f"SEC{i}", f"B{i}", f"B{i+1}", 5.0) for i in range(1, 6)],
    trains=[Train("T1", "B2", 8.0), Train("T2", "B5", 10.0)],
)
res = run_power_flow(net)
print(f"收敛: {res['converged']}  迭代: {res['iterations']}  网损: {res['losses_kW']:.1f} kW\n")
print(f"{'母线':<6}{'距离km':>8}{'电压kV':>10}{'标幺值':>9}")
for b, d in feeder_chain(net):
    print(f"{b:<6}{d:>8.1f}{res['buses'][b]['U_kV']:>10.3f}{res['buses'][b]['U_pu']:>9.4f}")
