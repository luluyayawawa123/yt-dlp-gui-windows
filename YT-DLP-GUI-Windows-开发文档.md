# YT-DLP GUI for Windows 开发文档

> 本文面向希望参与维护与扩展的开发者，重点说明当前实现、打包链路、YouTube 组件机制和发布注意事项。阅读后应能在本地完成开发、排障和打包，不被历史方案误导。

## 1. 项目概述与技术栈
YT-DLP GUI for Windows 为 `yt-dlp` 提供原生 Windows 图形界面，目标是让用户在不接触命令行的前提下完成高画质视频下载、播放列表下载、Cookie 读取、日志排障和多平台解析。

软件亮点包括：单/多 URL 支持、播放列表/频道下载、Firefox Cookie 免手填、画质格式细粒度控制、下载任务可视化和独立实时日志窗口。

**主要技术栈：**
- **语言与运行时**：Python 3.10+，使用项目内 `.venv` 作为唯一开发环境。
- **GUI 框架**：PyQt6 Widgets。
- **下载核心与媒体处理**：`yt-dlp` + `ffmpeg`。
- **YouTube 相关运行时**：`deno.exe` + `bgutil-ytdlp-pot-provider`。
  - 项目默认启用 `PO Token provider` 支持。
  - 是否实际生成/使用 `PO Token`，由 `yt-dlp` 当前内核、视频场景和所选 client 决定。
  - 保留这套能力的目的，是提高 YouTube 高画质尤其是 4K 场景的成功率。
- **打包分发**：PyInstaller + `build.py` 自动化脚本。
- **辅助库**：requests、BeautifulSoup4、logging。

## 2. 环境准备与基础命令
1. **激活虚拟环境（必须）**
   ```powershell
   .\.venv\Scripts\activate
   ```
2. **安装 Python 依赖**
   ```powershell
   pip install -r requirements.txt
   ```
3. **运行 GUI**
   ```powershell
   python src/main.py
   ```
4. **运行现有回归探针**
   ```powershell
   python test_title_extraction.py
   python test_log_feature.py
   ```
5. **构建 Windows 发行包**
   ```powershell
   python build.py
   ```
   构建产物位于 `dist/`。当前打包流程会：
   - 调用 PyInstaller 生成主体程序
   - 复制 `bin/` 运行时目录
   - 在打包产物里的 `bin/bgutil-ytdlp-pot-provider/server` 下执行  
     `npm.cmd ci --omit=dev --no-fund --no-audit`
   - 生成可迁移的 `node_modules`

   注意：
   - **打包机需要可用的 `npm.cmd`**
   - **终端用户不需要安装 Node.js 或 Deno**

6. **常用辅助文件**
   - `bin/更新内核.bat`：更新 `yt-dlp.exe`
   - `bin/项目目录更换后，需要重新deno install.txt`：旧方案说明 + 当前推荐的开发目录重建方案
   - `bin/bgutil-ytdlp-pot-provider 维护说明.txt`：后续升级 provider/plugin 时的维护入口
   - `clear_icon_cache.py` / `create_icons.py` / `check_exe_icon.py`：图标与缓存处理

## 3. 目录结构
```text
yt-dlp-gui-windows/
├─ bin/
│  ├─ bgutil-ytdlp-pot-provider/      # YouTube PO Token provider 服务端脚本目录
│  ├─ yt-dlp-plugins/                 # 对应的 yt-dlp plugin zip
│  ├─ 更新内核.bat
│  ├─ 项目目录更换后，需要重新deno install.txt
│  └─ bgutil-ytdlp-pot-provider 维护说明.txt
├─ config/                            # 运行配置、日志、下载记录
├─ icons/ screenshots/                # UI 资源
├─ src/
│  ├─ main.py                         # 程序入口、PATH/编码初始化
│  ├─ core/
│  │  ├─ config.py                    # 配置中心与路径解析
│  │  ├─ downloader.py                # 下载命令组装、QProcess 管理、日志解析
│  │  └─ youtube_pot.py               # YouTube 组件预热逻辑
│  ├─ gui/
│  │  ├─ main_window.py               # 普通下载窗口
│  │  ├─ playlist_window.py           # 播放列表/频道窗口
│  │  ├─ log_window.py                # 实时日志窗口
│  │  └─ saved_urls_dialog.py         # 收藏管理
│  └─ hooks/
│     └─ windows_hook.py              # PyInstaller Windows hook
├─ dist/ build/                       # 打包产物与中间目录
├─ test_*.py                          # 根目录下的回归探针
├─ build.py                           # 打包脚本
├─ version.txt                        # 版本号与 Windows 文件版本信息
├─ README.md                          # 用户文档
└─ YT-DLP-GUI-Windows-开发文档.md
```

## 4. 核心架构与模块联动

### 4.1 运行时环境挂载（`src/main.py`）
- 启动时会将 `bin/` 加入进程级 `PATH`，确保运行时能找到：
  - `yt-dlp.exe`
  - `ffmpeg.exe`
  - `deno.exe`
- 强制使用 UTF-8 相关设置，降低 Windows 默认编码导致的标题、日志、文件名乱码问题。
- 绿色版仍然**自带** `deno.exe`，但用户不需要自行安装 Deno。

### 4.2 UI 层职责（`src/gui/`）
- **MainWindow**
  - 处理普通视频下载。
  - 在真正启动 YouTube 下载前，异步预热 `YouTube` 组件。
  - 预热期间在窗口顶部右侧显示状态提示，不侵入主布局高度。
- **PlaylistWindow**
  - 处理播放列表/频道下载。
  - 同样在正式下载前做异步预热。
  - 主按钮会在 `开始下载 / 取消下载` 之间切换，用户可直接终止当前任务后再次点击开始下载。
  - 预热提示直接写入播放列表窗口日志区，避免额外占用顶部布局。
  - 保留播放列表场景下的摘要输出和批量任务控制。
- **LogWindow**
  - 展示底层原始日志，适合排查 `yt-dlp`、PO Token、网络波动和 `ffmpeg` 合并问题。
  - 普通下载模式下会缓存每个任务的完整日志历史；即使日志窗口点开较晚，也能先回填本任务之前的日志。
  - 日志窗口和播放列表日志区都支持“智能自动滚动”：位于底部时自动跟随，用户滚离底部时暂停，回到底部后恢复。

### 4.3 下载管控器（`src/core/downloader.py`）
`downloader.py` 负责把 GUI 选项转成结构化的 `yt-dlp` 参数与进程控制。

核心职责：
- **平台感知分发**
  - 根据 URL 判断平台，分别组装参数。
  - YouTube 场景下，默认启用 `PO Token provider` 支持：
    - 代码会传入 `--extractor-args youtubepot-bgutilscript:server_home=...`
    - 这表示项目**默认挂上 provider 能力**
    - 但是否实际生成/使用 token，仍由 `yt-dlp` 内核决定
- **Cookie 提取**
  - 支持从 Firefox 等浏览器读取 Cookie，兼顾登录态视频与更稳的 YouTube 下载。
- **日志解析**
  - 解析 `yt-dlp` 输出，提取进度、速度、剩余时间、标题和完成状态，并刷新到界面。

### 4.4 YouTube 预热机制（`src/core/youtube_pot.py`）
这个模块是当前 YouTube 稳定性的重要组成部分。

背景：
- `yt-dlp` 在检查 `bgutil-ytdlp-pot-provider` 可用性时，内部只给大约 15 秒超时。
- Deno 脚本在首次运行、目录刚变更或系统冷启动时，可能会慢于这个时间。
- 结果就是典型现象：**第一次失败，第二次成功**。

当前方案：
- 在 GUI 层发起 YouTube 下载前，先异步执行一次轻量预热。
- 预热本质是调用 `generate_once.ts --version`，把 Deno、模块解析和当前路径预先热起来。
- Windows 下预热子进程会隐藏黑色控制台窗口，减少对用户的打扰。
- 预热结果不是永久有效；超过一段时间后再次下载 YouTube，会重新预热，避免隔很久后的首次下载重新踩中冷启动超时。

这样做的目的不是“提前下载视频”，而是规避首次冷启动撞上 `yt-dlp` 的内部超时。

### 4.5 YouTube 失败补救重试
当前项目在 YouTube 场景下，还额外补了一层**任务级的一次性自动重试**。

适用条件：
- 仅限 YouTube
- 仅限首轮失败
- 仅限还没有进入实际下载进度时
- 最多自动补两次（总共最多 3 次尝试）

主要针对这类场景：
- `PO Token` 首次生成失败
- `bgutil` 脚本首次调用失败
- 首次格式获取失败，但第二次通常恢复

这层逻辑**不替代** `yt-dlp` 自己的下载中重试：
- `yt-dlp` 内核重试：处理分片、网络抖动、HTTP 失败
- 本项目补救重试：处理整次任务已经失败退出后的首次恢复

普通下载模式还提供失败后的**手动“下载重试”按钮**：
- 按钮直接放在任务卡片原有状态行中
- 不增加任务卡片高度
- 失败时才显示

播放列表模式则保持更简单的交互：
- 不单独维护失败项重试按钮
- 用户取消或失败后，直接再次点击 `开始下载` 即可重新下载整个列表
- 已下载内容继续由现有跳过/续传机制处理

### 4.6 打包与依赖装配层（`build.py`）
当前打包逻辑已经和旧版不同，维护时要特别注意。

**旧方案问题：**
- 过去依赖 `deno install`
- 生成的 `node_modules` 在 Windows 下可能带绝对路径 `junction`
- 一旦绿色版改名或移动目录，依赖可能失效

**当前方案：**
1. 读取版本号
2. 运行 PyInstaller
3. 复制 `bin/` 到发行目录，同时排除开发期的 `node_modules`
4. 在发行目录的 `bin/bgutil-ytdlp-pot-provider/server` 下执行：
   ```powershell
   npm.cmd ci --omit=dev --no-fund --no-audit
   ```
5. 生成真实、可迁移的 `node_modules`

这意味着：
- 绿色版改名或移动目录后，`bgutil` 依赖不再因为绝对路径 `junction` 而失效
- 绿色版仍然携带 `deno.exe`
- 但不再依赖用户手动执行 `deno install`

## 5. FAQ 与排障指南

### 5.1 第一次 YouTube 下载失败，第二次成功
常见原因分两类：
- **旧问题**：Deno 脚本冷启动太慢，撞上 `yt-dlp` 内部约 15 秒检查超时
- **新问题**：真实下载阶段的网络波动、YouTube 挑战变化或 token 重新生成失败

当前项目已通过异步预热解决第一类问题。如果还有“第一次失败，第二次成功”，优先看实时日志里是否发生在：
- 组件检查阶段
- 真实 token 生成阶段
- 实际流下载阶段

另外，当前代码已经增加了自动补救重试：
- 普通下载模式和播放列表模式都支持
- 只对 YouTube 首轮初始化类失败触发
- 成功进入真实下载进度后，不会再额外补重试
- 最多自动补两次（总共最多 3 次尝试）
- 不影响 `yt-dlp` 自己的下载中重试

如果普通下载模式中用户手动点开“实时下载日志”较晚：
- 当前实现已经会回填该任务此前产生的完整日志
- 不再只能看到点开窗口后的实时片段

### 5.2 开发目录改路径后，provider 失效
对开发版来说，这仍然可能发生。

原因：
- 开发目录下的 `server/node_modules` 可能来自旧的 `deno install` 或历史路径
- 改项目目录后，旧依赖解析可能失效

当前推荐重建方式：
```powershell
cd .\bin\bgutil-ytdlp-pot-provider\server
Remove-Item -Recurse -Force .\node_modules
npm.cmd ci --omit=dev --no-fund --no-audit
```

不要再把 `deno install` 作为当前首选重建方式。

### 5.3 绿色版改名或移动目录后不能下载
当前打包方案已经针对这个问题做了修复：
- 打包时改用 `npm.cmd ci`
- 不再依赖路径绑定的 `junction`

如果以后又出现回归，优先检查：
- `build.py` 是否被改回旧方案
- `dist/.../server/node_modules` 是否真的来自 `npm ci`

### 5.4 日志里看到视频音频分离下载，再合并，是否正常
正常。

对于 YouTube 高画质（尤其高于 1080P）：
- 常见情况就是视频流和音频流分离
- `yt-dlp` 会分别下载
- 最后交给 `ffmpeg` 合并

即便这次前面实际用了 `PO Token`，后面仍然可能表现为传统的“视频 + 音频 + 合并”流程，这不冲突。

### 5.5 什么时候需要怀疑内核问题
如果 YouTube 4K 突然大面积失效，建议按这个顺序检查：
1. 当前是否已是官方最新稳定版 `yt-dlp`
2. `deno.exe` 是否仍存在且可正常运行
3. 同视频是否能在命令行直接复现
4. 若稳定版仍异常，再用官方 `nightly` 做验证

当前建议：
- **默认发布**：官方稳定版
- **异常验证**：官方 `nightly`

## 6. 开发工作流建议
1. **始终先激活虚拟环境**
   ```powershell
   .\.venv\Scripts\activate
   ```
2. **先跑 GUI，再看日志**
   任何影响下载命令组装、YouTube 流程或日志解析的修改，都应先用 `python src/main.py` 做界面回归，再看实时日志验证实际命令。
3. **修改 YouTube 流程时要有全局视角**
   优先考虑：
   - 普通下载模式与播放列表模式是否都受影响
   - 绿色版目录迁移是否会回归
   - 是否会让用户再次看到黑色控制台窗口
   - 是否会让界面出现“未响应”
4. **提交前至少执行**
   ```powershell
   python test_title_extraction.py
   python test_log_feature.py
   ```
5. **发布前检查**
   - 同步 `version.txt` 与 `src/main.py`
   - 运行 `bin/更新内核.bat`
   - 执行 `python build.py`
   - 至少验证一次：
     - 正常目录下载
     - 改名后下载
     - 移动目录后下载

## 7. 协作与 PR 守则
- Commit 与 PR 说明统一使用中文。
- 涉及 `yt-dlp`、`ffmpeg`、`deno`、`bgutil-ytdlp-pot-provider` 的修改，必须附带本地验证结论。
- UI 修改应说明是否影响布局高度、状态提示位置和用户可感知的交互。
- 不要把开发目录里的个人 Cookie、缓存和用户路径写死到仓库。
- 若需升级 `bgutil-ytdlp-pot-provider`，先看：
  - `bin/bgutil-ytdlp-pot-provider 维护说明.txt`

---
若要继续深入排查，请优先阅读：
- `src/core/downloader.py`
- `src/core/youtube_pot.py`
- `src/gui/main_window.py`
- `src/gui/playlist_window.py`
