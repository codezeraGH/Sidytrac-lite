# Sidytrac Lite

用 Python 开源组件实现的 **交流牵引供电稳态潮流仿真** 桌面软件（教学演示级，灵感来自 Siemens SITRAS Sidytrac）。

## 功能
- 图形化编辑：牵引变电所（含变压器阻抗）、接触网供电臂区段、列车负荷
- 前推回代法潮流计算（辐射状网络）
- 结果展示：节点电压表、支路电流/损耗表、供电臂电压曲线
- 工程保存/加载（JSON）

## 安装与运行
```bash
pip install -r requirements.txt
python gui.py        # 桌面界面
python demo.py       # 命令行示例
```

## 模型与限制（重要）
- 单相 27.5 kV 等值、恒功率负荷、稳态相量潮流
- **仅支持辐射状供电臂**，不支持环网/双边供电、AT 供电方式
- 不支持直流馈线保护整定与电磁暂态仿真
- **不能用于工程设计**，仅供学习交流牵引供电基本原理

## 许可建议
代码可自由使用（建议 MIT）；PySide6 为 LGPL/GPL，商用注意合规。


## 打包为 Windows EXE

### 方法一：GitHub Actions 在线打包（推荐，无需安装任何东西）
1. 把 `sidytrac_lite` 文件夹推送到你的 GitHub 仓库（Workflow 权限需为可读）
2. 打开仓库 → **Actions** → 左侧 **Build Windows EXE** → **Run workflow**
3. 约 5 分钟后，在运行记录的 **Artifacts** 中下载 `SidytracLite-Windows`
4. 解压后运行其中的 `SidytracLite.exe` 即可，可拷到任何 Windows 电脑

### 方法二：本地打包（需要 Windows + Python）
```bat
build.bat
```
产物在 `dist\SidytracLite\`，整个文件夹即为绿色免安装版。
