DiskExplorer – 磁盘空间分析工具

一款轻量级、高性能的本地磁盘空间分析工具，以分层树状视图可视化磁盘使用情况，帮助您快速识别和管理存储空间。

功能特性

• 树状目录视图 – 分层显示文件夹和文件，包含大小、占比、修改时间和文件数量

• 饼图与柱状图 – 为任何选定目录可视化展示大小分布

• 快速多线程扫描 – 使用线程池处理大型目录

• 结果缓存 – 持久化扫描结果，使重新打开时立即可用

• 导出报告 – 支持 CSV、JSON 和独立 HTML 输出

• 右键上下文菜单 – 在文件管理器中打开、复制路径

• 零云端依赖 – 所有数据保留在您的本地机器

系统要求

组件 最低版本

Python 3.9+

PyQt6 6.4.0+

psutil 5.9.0+

操作系统 Windows 10 / macOS 10.15 / Linux

快速开始

# 1. 克隆仓库
git clone https://github.com/DARK20050101/Folder.git
cd Folder

# 2. 创建并激活虚拟环境
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动应用程序
python main.py


项目结构


DiskExplorer/
├── main.py              # 应用程序入口点
├── requirements.txt     # 运行时依赖
├── setup.py            # 打包配置
├── src/
│   ├── models.py       # FileNode 和 DiskDataModel 数据结构
│   ├── scanner.py      # FileSystemScanner (多线程)
│   ├── cache.py        # ScanCache (pickle 序列化)
│   ├── export.py       # ExportHandler (CSV / JSON / HTML)
│   └── ui/
│       ├── main_window.py   # MainWindow (PyQt6)
│       ├── tree_view.py     # FileSystemTreeView 和 FileNodeModel
│       └── chart_widget.py  # PieChartWidget, BarChartWidget, SizeChartWidget
└── tests/
    ├── test_models.py
    ├── test_scanner.py
    ├── test_cache.py
    └── test_export.py


运行测试

pip install pytest
pytest tests/ -v


打包 (Windows)

pip install pyinstaller
pyinstaller --onefile --windowed --name DiskExplorer main.py


生成的 dist/DiskExplorer.exe 是一个独立的便携式可执行文件。

架构


┌─────────────────────────────────┐
│  UI 层 (PyQt6)                  │
│  MainWindow → TreeView + Charts │
├─────────────────────────────────┤
│  逻辑层                          │
│  ScanManager · CacheManager     │
│  ExportHandler                  │
├─────────────────────────────────┤
│  数据层                          │
│  FileSystemScanner (psutil/os)  │
│  FileNode · DiskDataModel       │
└─────────────────────────────────┘


路线图

版本 计划功能

V1.1 重复文件检测，网络驱动器支持，多语言

V2.0 实时监控，高级搜索，批量操作

V3.0 多机器管理，计划报告，API

许可证

MIT
