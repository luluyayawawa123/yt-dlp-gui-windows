# YT-DLP GUI for Windows 开发文档

> 本文面向希望参与维护与扩展的开发者，涵盖架构、目录、开发命令、测试以及发布注意事项。阅读完毕后，你应当能够在本地搭建环境、理解主要模块的职责，并安全地交付新功能。对于复杂排障和打包流程也有详尽补充。

## 1. 项目概述与技术栈
YT-DLP GUI for Windows 旨在为 yt-dlp 命令行工具提供一套原生 Windows 图形界面。核心目标是让用户通过图形配置即可实现视频/音频下载、多平台（YouTube、B站、小红书、抖音等）解析、批量任务调度以及深度的日志追踪。

软件亮点包括：单/多 URL 支持、播放列表订阅（含断点续传/跳过已下载特性）、集成 Firefox 等浏览器 Cookie 免登录下载、画质格式细粒度控制、任务收藏以及独立极客风实时监控日志。

**主要技术栈：**
- **语言与运行时**：Python 3.11+，内置 `.venv` 提供完全隔离依赖环境。
- **GUI 框架**：PyQt6 Widgets，配合自定义无边框窗口、独立进程对话框与平滑圆角日志面板。
- **下载核心与媒体处理**：yt-dlp（核心 downloader）、ffmpeg（转码、音频合并、外挂字幕内嵌/转换）。
- **签名与反爬依赖**：Deno 及 `bgutil-ytdlp-pot-provider`。用于为 YouTube 最新 SABR 协议生成 PO Token（Proof of Origin），突破高分辨率下载和 403 封锁。
- **打包分发**：PyInstaller + `build.py` 自动化脚本，通过自定义 PyInstaller hooks (`src/hooks/windows_hook.py`) 注入资源与依赖环境拷贝。
- **辅助库**：requests、BeautifulSoup4、logging。

## 2. 环境准备与基础命令
1. **激活虚拟环境（必须）**
   为避免污染全局环境和保证打包一致性，**必须**使用项目自带或自己创建的隔离虚拟环境。
   ```powershell
   .\.venv\Scripts\activate
   ```
2. **安装核心依赖（首次或 requirements 更新后）**
   ```powershell
   pip install -r requirements.txt
   ```
3. **运行 GUI 进行功能验证**
   ```powershell
   python src/main.py
   ```
4. **运行现有集成与回归测试**
   ```powershell
   python test_title_extraction.py
   python test_log_feature.py
   ```
5. **构建 Windows 分发包**
   使用自定义封装的脚本：
   ```powershell
   python build.py
   ```
   构建会利用 PyInstaller，产物位于 `dist/`，同时会自动使用 `robocopy` 搬移 `bin/` 目录中的第三方二进制依赖文件，并在 `dist` 后处理阶段通过 `deno install` 安装服务端依赖。
6. **常用辅助机制**
   - `bin/更新内核.bat`：用于用户和开发者一键更新 yt-dlp 自身可执行文件。
   - `clear_icon_cache.py` / `create_icons.py` / `check_exe_icon.py`：处理 PyQt 的缓存系统与图标打包问题。

## 3. 目录结构
```
yt-dlp-gui-windows/
├─ bin/                 # 放置 yt-dlp.exe、ffmpeg.exe、deno.exe 及其它二进制运行时依赖
│  ├─ bgutil-ytdlp-pot-provider/ # PO Token 服务端签名组件（突破 YouTube 限制要素）
│  └─ 更新内核.bat      # 针对普通用户设计的内核更新程序
├─ config/              # 开发/运行时的用户配置、日志（debug.log）、下载记录
├─ icons/ screenshots/  # UI 图像资源与示例截图
├─ src/
│  ├─ main.py           # 程序入口点，处理环境变量（如 UTF-8 与 PATH 初始化）及全局异常拦截
│  ├─ core/
│  │  ├─ config.py      # 配置中心、跨平台/打包路径解析（_MEIPASS 支持）及集中式文件/流式日志处理
│  │  └─ downloader.py  # 核心桥接器。执行平台解析、Cookie提取、进程启动和输出日志解析/状态投递
│  ├─ gui/
│  │  ├─ main_window.py # 主面板：常规 URL 输入、选项、并发可视化任务流列表及基础状态机
│  │  ├─ playlist_window.py  # 高级列表/频道界面：稳健重试逻辑(Retry Policy)、断点续传档案及合并监控
│  │  ├─ log_window.py       # 实时独立的极客风日志观测器，直接监控后台线程原生打印 (RAW_LOG)
│  │  └─ saved_urls_dialog.py# 用于管理收藏的订阅源和频繁访问的频道记录
│  └─ hooks/
│     └─ windows_hook.py     # 针对 Windows 下的 PyInstaller 的额外 hook
├─ dist/ build/         # PyInstaller 打包产物与中间文件缓存
├─ tests                # 各类集成回归探针（存放在根目录下的 test_*.py 等）
├─ build.py             # 核心打包构建脚本（包含二次安装依赖的后处理）
├─ build.bat            # 包装了构建流程的快速脚本
├─ version.txt          # 工程版本号锚定文件
├─ README.md            # 面向终端用户的快速操作说明
└─ YT-DLP-GUI-Windows-开发文档.md # 目前您正在阅读的内容
```

## 4. 核心架构与模块联动剖析

### 4.1 运行时环境挂载（`src/main.py`）
- `main.py` 第一步就是挂载 `bin/` 至当前进程的系统 `PATH` 树中，确保打包后的环境中 `yt-dlp` 和 `ffmpeg` `deno` 随叫随到，而不需要用户额外配置系统环境变量。
- 强制使用 UTF-8 编码，彻底解决 Windows 下由于默认的 `GBK/GB18030` 引发的外文（日、韩、特殊符号）下载乱码。

### 4.2 UI 层职责（`src/gui/`）
- **MainWindow**：通过 `Downloader` 实例创建长生命周期的 `QProcess`。界面上采用高度定制的 CSS 样式，包含进度条、状态提示（例如：“⏬ 下载中”、“🔄 处理中”、“✓ 已完成”）、动态推送到界面的日志组件（调用 `log_window.py`）。
- **PlaylistWindow**：不仅复用主体逻辑，还在日志抽取正则上下足了功夫。特别设计了 **“网络稳健重试”**（--retries 10 / --fragment-retries 10 / 退避算法）参数，保证在下载数十个切片时就算偶发断连也能坚持下载。内置 `_append_download_summary` 方法最终输出合并统计给用户。
- **LogWindow**：独立浮动窗口。针对遇到 403 / 拒绝访问错误的高级用户，提供实时 `[RAW_LOG]` 数据流以精确找到失败源头。

### 4.3 下载管控器（`src/core/downloader.py`）
整个应用的“大脑”。将单纯的终端命令转化为了精细的结构化异步流：
- **平台感知智能分发**：依靠传入的 URL 的 `domain` 探测平台属性。
  - **YouTube**: 强制调起 PO Token 算法 (`bgutil-ytdlp-pot-provider`)。
  - **小红书**: 处理用户页面拒绝批量下载错误并给出友好提示，自动拦截并整理含有特定特征路由。
  - **B站 / 抖音**: 自动切换 User-Agent，推荐默认 `MP4` 格式处理。
- **Cookie 嗅探提取**：自动检索用户环境（或便携版）中主流浏览器（如 Firefox 的 `cookies.sqlite`、Safari 等），以支持用户级别的私密视频查阅。
- **解析器**：捕获 QProcess 的 StdOut/StdErr，通过一套严密的正则表达式解析进度。识别 `0.0% of 100MiB at 2MB/s ETA 00:00` 流并发送 Qt 信号将格式化结果刷新给界面。

### 4.4 打包与依赖装配层（`build.py`）
- 与标准的 PyInstaller 规范不同，本项目存在 Node/Deno 后端级依赖。
- 在 `build.py` 运行时：
  1. 通过正则表达式提取 `version.txt` 或 `main.py` 中记录的版本号供构建用。
  2. 触发 PyInstaller。
  3. 执行由 `robocopy` 驱动的纯净二进制目录 `bin/` 的传输。特意抛弃打包前的开发用 `node_modules` 关联。
  4. 进程呼叫目标目录里的 `deno.exe`，对 `bin/bgutil-ytdlp-pot-provider/server` 进行二次冻结与补齐操作（`--allow-scripts=npm:canvas --frozen`），保证在目标用户的干净机器上签名组件立即可用。

## 5. 异常体系与排障指南 (FAQ & Troubleshooting)

开发过程中不可避免会遇到一些下载失败情况，软件的日志体系与判断逻辑会将许多模糊的 `yt-dlp` 报错翻译为友好的故障排除提示：

- **报错：“小红书内容提取失败 / B站视频解析失败”**
  - **原因**：这类错误多因“无痕 / 未登录拦截”或“视频本身需要大会员或下架”。目前小红书不开放纯主页批量提取。
  - **建议**：引导改用单 URL 并在 `main_window` 执行。
- **报错：“请求超时 / 连接错误”或出现 "Retrying (10/10)"**
  - **定位**：通常发生在多片段切片获取阶段（Fragmentation）。程序已应用了退避重试（Backoff algorithm）。
  - **日志窗口表现**：在 `PlaylistWindow` 中如果完全达到 10 次上限，逻辑会截断当前条目并将目标标记进入 `failed` 摘要列表且不中断整个循环队列。
- **报错：“合并失败” (`[Merger] error`)**
  - **原因**：在合并分离的音视频轨道（通常是 YouTube 高于 1080P 或高品质音乐时）失败。往往是目标系统的防病毒或缺失 ffmpeg 引起。
- **报错：“未找到 Firefox cookies” 或 403 封锁**
  - **排查**：需确认 Firefox 是否被正确安装在系统 `App Paths`、是否用其正常完整登陆了目标网站一次。

## 6. 开发工作流建议
1. **启动测试环境**：
   务必运行 `.\.venv\Scripts\activate` 激活环境后执行 `python src/main.py` 测试基本运行状态。
2. **遵守规范与编码格式**：
   提交任何影响命令行组装的代码时（例如 `downloader.py` 中的 `args.extend(...)` ），必须要特别注意参数之间空格的连接，并通过 GUI 中的日志窗口验证组装后实际执行的拼接串是否越界或格式错乱。
   注意中文字符处理和控制字符编码，保持 `utf-8` 基准。
3. **增加特定网域支持**：
   在 `src/core/downloader.py` 的 `self.platform_configs` 字典中注册对应的域名、必要的 Cookies 限定布尔值、特定 `--extractor-args` 及回滚推荐格式（`default_format`）。
4. **提交代码前**：
   使用独立的探针文件跑一次简单的单元确认：
   ```powershell
   python test_title_extraction.py
   python test_log_feature.py
   ```
5. **版本释出准备**：
   在推向主分支打包前，必须：
   - 更新 `version.txt` 与 `src/main.py` 内部的变量。
   - 打开脚本运行 `bin/更新内核.bat` 获取最新的上游提取规则（防 403 改版）。
   - 最后执行 `python build.py` 打包产出绿色的发行版（存于 `dist/` 中）。

## 7. 协作与 PR 守则
- **Commit 及 PR 语言**：必须使用**中文描述**，采用现在时简单句或者祈使句（例：“修复小红书解析规则崩溃问题”）。
- **影响评估**：任何有关 `yt-dlp` 与 `ffmpeg` 系统调用参数级别的修改，请务必详细附带本地成功验证此平台及另一平台的无退化报告结果。对图形 UI 改动请提供相关的界面截图以便高效 review。
- 此项目所有图形模块和组件都是在隔离的信号上下文中异步执行，避免向主 PyQt 事件循环添加密集型的长耗时 CPU 操作阻塞线程。任何读取大文件或进行远端 Socket 重连一定要放置在新开启的 QThread 或利用 QProcess 的后台流完成回调操作。

---
阅读完以上内容并熟悉了系统逻辑后，如果有关于组件更细节的设计疑惑，可以直接查阅 `src/core/downloader.py` 的正则分析机制代码或 `src/gui/playlist_window.py` 极完善的状态图控制。祝您顺利起飞！泡泡音挥手~ 🫧
