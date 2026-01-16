# YT-DLP GUI for Windows 开发文档

> 本文面向希望参与维护与扩展的开发者，涵盖架构、目录、开发命令、测试以及发布注意事项。阅读完毕后，你应当能够在本地搭建环境、理解主要模块的职责，并安全地交付新功能。

## 1. 项目概述与技术栈
YT-DLP GUI for Windows 旨在为 yt-dlp 命令行工具提供一套原生 Windows 图形界面。核心目标是让用户通过图形配置即可完成视频/音频下载、字幕抓取、批量任务调度以及日志追踪。软件支持单/多 URL、播放列表、频道下载，集成 Firefox Cookie 免登录下载、常用格式模板、任务收藏、断点续传与下载记录过滤等功能。

主要技术栈：
- **语言与运行时**：Python 3.11+，内置 `.venv` 提供隔离环境。
- **GUI**：PyQt6 Widgets，配合自定义窗口、对话框与日志面板。
- **下载/媒体**：yt-dlp（核心 downloader）、ffmpeg（转码、音频提取、字幕转换）。
- **打包**：PyInstaller + `YT-DLP-GUI-Windows.spec`，并通过 `src/hooks/windows_hook.py` 注入额外资源。
- **辅助库**：requests、BeautifulSoup、logging、concurrent.futures 等。

## 2. 环境准备与基础命令
1. **激活虚拟环境（必须）**
   ```powershell
   .\.venv\Scripts\activate
   ```
2. **安装依赖（首次或 requirements 更新后）**
   ```powershell
   pip install -r requirements.txt
   ```
3. **运行 GUI 进行功能调试**
   ```powershell
   python src/main.py
   ```
4. **运行现有集成测试**
   ```powershell
   python test_title_extraction.py
   python test_log_feature.py
   ```
5. **构建分发包**
   ```powershell
   python build.py
   ```
   构建会利用 PyInstaller，产物位于 `dist/`，并自动将 `bin/` 中需要的可执行文件打包。
6. **常用辅助脚本**
   - `bin/更新内核.bat`：更新 yt-dlp 可执行文件，解决多数下载失败问题。
   - `clear_icon_cache.py` / `create_icons.py` / `check_exe_icon.py`：维护图标缓存与打包图标。

## 3. 目录结构
```
yt-dlp-gui-windows/
├─ bin/                 # yt-dlp、ffmpeg、更新脚本等运行时依赖
├─ config/              # 用户配置、日志（debug.log）、下载记录
├─ icons/ screenshots/  # UI 资源与示例截图
├─ src/
│  ├─ main.py           # 程序入口，初始化路径、日志与主窗口
│  ├─ core/
│  │  ├─ config.py      # 配置与日志管理、断点续传记录
│  │  └─ downloader.py  # 任务封装、并发调度、yt-dlp 调用
│  ├─ gui/
│  │  ├─ main_window.py # 主窗口：URL 列表、任务面板、任务选项
│  │  ├─ playlist_window.py # 播放列表与批量任务管理
│  │  ├─ log_window.py       # 实时日志窗口
│  │  └─ saved_urls_dialog.py# 收藏/历史对话框
│  └─ hooks/windows_hook.py  # PyInstaller hook
├─ dist/ build/         # 打包产物与中间文件
├─ tests                # 集成回归脚本（根目录下 test_*.py）
├─ build.py / build.bat # 构建脚本
├─ version.txt          # 版本号
├─ README.md            # 面向用户的快速说明
└─ YT-DLP-GUI-Windows-开发文档.md # 本文
```

## 4. 核心架构与模块职责
### 4.1 入口（`src/main.py`）
- 将 `bin/` 添加到 `PATH`，确保打包与开发模式均可直接调用 yt-dlp、ffmpeg。
- 初始化 logging（输出到控制台与 `config/debug.log`），记录带时间戳和模块名的调试信息。
- 创建 `QApplication` 与主窗口实例，注册全局异常钩子，保持 UI 响应。

### 4.2 GUI 层（`src/gui`）
- **MainWindow**：负责 URL 输入、格式选择、字幕选项、任务队列展示、进度条、右键操作等；通过信号槽与 `core.downloader` 交互。
- **PlaylistWindow**：提供播放列表/批量 URL 管理、批量参数同步。
- **LogWindow**：独立显示实时日志，便于排障；可过滤级别。
- **SavedUrlsDialog**：收藏夹与历史记录管理，支持导入/导出与快速选中。

UI 中所有长耗时任务（下载、分析）都会交给后台线程，主线程只负责状态展示，避免冻结。

### 4.3 核心逻辑（`src/core`）
- **config.py**
  - 管理 `config/` 下的 JSON 配置、历史记录、下载档案。
  - 在 PyInstaller 环境中根据 `_MEIPASS` 定位资源。
  - 提供包装后的日志记录与线程安全写入。
- **downloader.py**
  - 将用户输入转换为结构化任务，支持单 URL、批量、播放列表。
  - 基于 `ThreadPoolExecutor` 进行并发下载，限制最大并行数并支持暂停/取消。
  - 拼装 yt-dlp 命令行选项（格式、字幕、Cookies、输出模板等），统一处理输出。
  - 处理 `--download-archive` 跳过已下载记录、断点续传、失败重试以及任务统计。

### 4.4 运行时资源（`bin/`）
- `yt-dlp.exe`、`ffmpeg.exe` 必须随发布包分发。
- `更新内核.bat`：调用 pip/网络更新 yt-dlp。
- 其他批处理脚本用于检测 Firefox、复制依赖等。

## 5. 下载与任务流程
1. 用户在主窗口粘贴 URL（支持多行），并选择输出目录、格式模板、字幕策略。
2. GUI 将输入打包为 `DownloadTask`（自定义 dataclass），并推入队列。
3. `downloader.py` 根据任务：
   - 解析是否为播放列表/频道，必要时使用 yt-dlp 的批量参数。
   - 构造命令，例如：`yt-dlp "URL" -P "<保存路径>" -f "bv*+ba/b" --write-auto-sub --sub-langs "zh-Hans,en"`.
   - 若启用了 Firefox Cookie，会调用辅助函数定位 `cookies.sqlite`，并添加 `--cookies-from-browser`.
4. 任务由线程池执行，实时将 stdout/stderr 解析为进度信息，通过信号发送给 GUI 更新状态。
5. 任务结束后：
   - 成功：更新下载档案、历史记录，可选打开文件或目录。
   - 失败：记录错误、展示通知，并保留失败任务供重试。

## 6. 配置、日志与数据持久化
- **配置存储**：`config/config.json` 默认包含下载目录、并行线程数、格式、字幕偏好等；修改后立刻写入，避免软件异常退出造成配置丢失。
- **日志**：`config/debug.log`。调试新功能时建议在 GUI 中打开日志窗口，同时 tail 该文件以捕捉后台异常。
- **下载记录**：`config/downloaded_videos_list.txt` 与 `--download-archive` 一致，用于跳过重复下载。
- **历史/收藏**：保存在 config 下各自文件，当用户清理历史时也会同步删除。

## 7. 开发流程建议
1. **拉取最新代码并确认版本**：`git pull` 后对照 `version.txt`，必要时同步 `src/main.py` 中的版本字符串。
2. **激活虚拟环境**：参见第 2 节。
3. **运行 `python src/main.py`**，在 UI 中复现需要修改的场景，方便定位。
4. **修改代码**：遵循 Python 4 空格缩进、snake_case 命名、GUI 类以 `_window.py` 结尾。尽量保持中文本地化字符串集中管理。
5. **编写/更新测试**：若涉及下载逻辑或日志格式，更新 `test_title_extraction.py`、`test_log_feature.py`，或者新增 `test_xxx.py`。
6. **自检**：
   - 运行核心测试脚本。
   - 手动验证字幕、播放列表、Cookie 登录、断点续传等关键路径。
7. **提交前检查**：确保 `config/` 下未包含用户隐私文件，`bin/` 仍含必要的可执行文件，禁止提交 Cookies。

## 8. 测试策略
- **集成脚本**：仓库根目录下的 `test_title_extraction.py`、`test_log_feature.py` 是最小化的回归脚本，直接 `python test_xxx.py` 运行即可。
- **新增测试**：使用 `test_*.py` 命名，保持可独立运行；需要外部资源时提供可替代的 mock 数据或说明。
- **手动测试清单**：
  1. 单视频下载（含音频提取）。
  2. 播放列表/频道下载（检测断点续传）。
  3. 字幕下载与转换。
  4. Firefox Cookies 登录下载。
  5. 下载完成后自动打开文件/文件夹。
  6. 并行任务 + 暂停/取消。
  7. 日志窗口实时刷新、筛选。

## 9. 打包与发布
1. **版本同步**：更新 `version.txt` 与 `src/main.py` 中的版本字符串。
2. **清理旧产物**：可运行 `python clear_icon_cache.py` 确保图标干净，必要时删除 `dist/`。
3. **刷新 yt-dlp**：执行 `bin/更新内核.bat`，避免发布时内核过旧。
4. **执行 `python build.py`**：脚本会读取 `YT-DLP-GUI-Windows.spec`，生成 `dist/YT-DLP-GUI-Windows/`。
5. **验证可执行文件**：启动产物，检查是否能正确加载资源、日志、下载器。
6. **发布清单**：包含可执行程序、`bin/` 依赖、配置模板、README、此开发文档；不要包含 `.venv` 或个性化配置。

## 10. 常见问题（FAQ）
- **下载突然失败**：先运行 `bin/更新内核.bat` 将 yt-dlp 更新至最新，再次尝试；若仍失败，检查 `debug.log` 与日志窗口输出。
- **Firefox Cookies 读取失败**：确保 Firefox 关闭，路径设置正确；若为便携版，需在设置中手动指定 Cookies 路径。
- **字幕没有生成**：确认视频确实提供字幕或自动字幕，且设置了正确语言（例如 `zh-Hans,en`）；同时确认 ffmpeg 存在于 `bin/`。
- **GUI 假死**：确认耗时操作均已移入后台线程；调试时可关注控制台/日志，查找阻塞调用。
- **打包后执行报错**：检查 `PATH` 是否包含 `bin/`，确保 hooks 正常复制；若图标空白，请重新运行 `create_icons.py` 并再打包。
- **配置/历史丢失**：通常由异常退出引发，检查 `config/` 是否可写；Windows 权限不足时，可将应用放置在非系统盘并以管理员身份运行。

## 11. 协作与 PR 要求
- **提交信息**：使用简洁中文、祈使句，描述意图（如“优化下载进度刷新”）。
- **拉取请求**：附加修改动机、用户可见变化、关键截图（GUI 改动）、相关 issue 链接与测试说明。
- **代码风格**：Python 4 空格缩进、明确类型提示、保持模块职责单一；GUI 交互逻辑不要直接嵌入下载核心，优先调用 `core` 中的封装。
- **文档同步**：若调整开发流程或目录结构，请同时更新本文件与 `README.md`，确保对外信息一致。

---

如需进一步了解具体模块，可直接阅读 `src/core/downloader.py` 与 `src/gui/main_window.py` 内的注释；编写新功能时，优先考虑复用现有信号槽、配置读写与日志机制，并确保所有命令在虚拟环境中执行。祝开发顺利！泡泡音挥手~ 
