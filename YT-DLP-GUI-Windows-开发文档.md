# YT-DLP GUI for Windows 项目开发文档

## 1. 项目概述

YT-DLP GUI for Windows 是一个 Windows 平台下的 YouTube 视频下载工具，为开源命令行工具 yt-dlp 提供了图形用户界面。该应用程序允许用户轻松下载单个视频、播放列表和频道，并支持多种下载格式和质量选项。

### 1.1 主要功能
- 支持单个视频和批量下载（每行一个URL）
- 支持播放列表和频道下载
- 多种视频质量选择：
  - 最高画质（bv*+ba）
  - 最高画质MP4（bv[ext=mp4]+ba[ext=m4a]）
  - 4K MP4（bv[ext=mp4][height<=2160]+ba[ext=m4a]）
  - 1080P MP4（bv[ext=mp4][height<=1080]+ba[ext=m4a]）
  - 480P MP4（bv[ext=mp4][height<=480]+ba[ext=m4a]）
- MP3 音频提取（使用libmp3lame编码器，320kbps高质量输出）
- 字幕下载（支持多语言，自动转换为.srt格式）
- 自动使用 Firefox 浏览器 Cookies 实现登录下载（支持各种Firefox安装路径检测）
- 收藏夹和历史记录功能
- 断点续传和下载记录保存（使用--download-archive参数跳过已下载视频）
- 并行多任务下载
- 实时下载进度、速度和剩余时间显示
- 支持下载完成后直接打开视频或文件夹

### 1.2 技术栈
- 编程语言：Python 3
- GUI 框架：PyQt6（现代化界面组件和布局）
- 视频下载工具：yt-dlp（功能强大的YouTube下载命令行工具）
- 媒体处理工具：ffmpeg（用于视频转换和音频提取）
- 打包工具：PyInstaller（用于生成独立可执行程序）
- 其他库：
  - requests（用于HTTP请求）
  - beautifulsoup4（用于HTML解析）
  - logging（用于日志记录）

## 2. 项目结构

```
yt-dlp-gui-windows/
├── bin/                    # 依赖的二进制文件目录
│   ├── ffmpeg.exe          # 音视频处理工具
│   └── yt-dlp.exe          # YouTube 下载器核心程序
├── build/                  # 构建生成的临时文件
├── config/                 # 配置文件目录
│   ├── config.json         # 用户配置文件
│   ├── debug.log           # 程序日志文件
│   └── downloaded_videos_list.txt # 已下载视频记录
├── dist/                   # 打包发布目录
├── screenshots/            # 界面截图
├── src/                    # 源代码目录
│   ├── core/               # 核心功能模块
│   │   ├── __init__.py
│   │   ├── config.py       # 配置管理
│   │   └── downloader.py   # 下载器实现
│   ├── gui/                # 图形界面模块
│   │   ├── __init__.py
│   │   ├── main_window.py  # 主窗口
│   │   ├── playlist_window.py # 播放列表窗口
│   │   └── saved_urls_dialog.py # 收藏管理对话框
│   ├── hooks/              # 运行时钩子
│   │   └── windows_hook.py # Windows 平台特定钩子
│   └── main.py             # 程序入口
├── .gitignore              # Git 忽略规则
├── build.py                # 打包构建脚本
├── README.md               # 项目说明文档
├── version.txt             # 版本信息文件
└── YT-DLP-GUI-Windows.spec # PyInstaller 规范文件
```

## 3. 核心模块详解

### 3.1 入口文件 (main.py)

程序入口点，负责初始化应用程序：
- 配置环境变量，确保 bin 目录下的可执行文件可被访问：
  ```python
  bin_dir = Path(__file__).parent.parent / "bin"
  os.environ['PATH'] = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"
  ```
- 初始化日志系统，配置详细的日志格式：
  ```python
  logging.basicConfig(
      level=logging.DEBUG,
      format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
      datefmt='%Y-%m-%d %H:%M:%S',
      handlers=[
          logging.FileHandler("debug.log", encoding='utf-8'),
          logging.StreamHandler()
      ]
  )
  ```
- 创建 PyQt 应用实例和设置应用信息：
  ```python
  app = QApplication(sys.argv)
  app.setApplicationName("YT-DLP GUI for Windows")
  app.setApplicationVersion("1.0.2")
  ```
- 创建并显示主窗口

### 3.2 配置管理 (config.py)

配置管理器负责：
- 处理程序配置的加载和保存，使用JSON格式存储配置
- 设置日志系统，支持同时输出到控制台和文件
- 管理下载历史记录
- 提供辅助函数记录日志

技术实现细节:
- 配置文件自动检测：检测是否为PyInstaller打包环境，适配不同运行环境：
  ```python
  if getattr(sys, 'frozen', False):
      # PyInstaller打包后的运行目录
      base_dir = Path(sys._MEIPASS).parent
  else:
      # 开发环境运行目录
      base_dir = Path(__file__).parent.parent.parent
  ```
- 配置文件路径设计：将配置文件放置在程序根目录的config文件夹中，便于管理
- 安全的配置文件保存机制：使用临时文件写入后替换的方式避免写入失败导致配置丢失：
  ```python
  # 创建临时文件
  temp_file = self.config_file.with_suffix('.tmp')
  with open(temp_file, 'w') as f:
      json.dump(self.config, f, indent=4)
  # 成功写入后才替换原文件
  temp_file.replace(self.config_file)
  ```
- 确保配置目录和下载记录文件存在：
  ```python
  self.config_dir.mkdir(parents=True, exist_ok=True)
  if not self.archive_file.exists():
      self.archive_file.touch()
  ```

配置文件格式为 JSON，包含以下设置：
```json
{
  "last_download_path": "C:\\Users\\Username\\Downloads",
  "browser": "firefox",
  "format_settings": {
    "mode": "best",
    "custom_format": ""
  },
  "saved_playlists": [
    {
      "title": "我的收藏",
      "url": "https://www.youtube.com/playlist?list=ABCDEFG"
    }
  ],
  "download_history": [
    {
      "title": "视频标题",
      "path": "C:\\Downloads\\视频标题.mp4",
      "timestamp": "2023-08-15T12:34:56",
      "status": "完成"
    }
  ]
}
```

### 3.3 下载器 (downloader.py)

下载功能的核心实现：
- 封装 yt-dlp 和 ffmpeg 命令行调用，处理参数构建和格式处理
- 处理下载进度和状态，通过解析输出流获取实时信息
- 管理多下载任务，支持并行处理多个URL
- 浏览器 cookies 检测和使用，支持多种浏览器路径检测策略
- 提供格式分析功能

主要类 `Downloader` 继承自 `QObject`，实现了以下信号：
- `output_received`：输出消息信号 (task_id, message)
- `download_finished`：下载完成信号 (success, message, title, task_id)
- `title_updated`：视频标题更新信号 (task_id, title)

技术实现细节:
- Firefox浏览器检测的多策略实现：
  1. 使用 where 命令查找
  2. 检查注册表的多个可能位置（包括32位和64位路径）
  3. 搜索所有可能的安装位置（包括所有盘符搜索）
  ```python
  registry_paths = [
      (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Mozilla\Mozilla Firefox'),
      (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Mozilla\Mozilla Firefox ESR'),
      (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Wow6432Node\Mozilla\Mozilla Firefox'),
      # ...更多路径检查
  ]
  ```

- Firefox Cookies文件查找的多策略实现：
  1. 检查标准安装版的所有配置文件路径
  2. 检查便携版的多种可能路径
  3. 从当前目录向上搜索5层目录结构
  ```python
  # 检查所有可能的配置文件
  profile_patterns = [
      '*.default-release',  # 最常见
      '*.default',          # 老版本
      '*.default-*',        # 其他变体
  ]
  # ...便携版搜索
  portable_patterns = [
      os.path.join('Data', 'profile', 'cookies.sqlite'),
      # ...更多路径模式
  ]
  ```

- 进程输出处理的鲁棒性设计：
  1. 多编码支持: 依次尝试utf-8、cp949、gb18030编码解码
  2. 优雅的错误处理: 使用replace错误处理模式兜底
  ```python
  try:
      # 首先尝试 UTF-8 解码
      text = data.data().decode('utf-8')
  except UnicodeDecodeError:
      try:
          # 如果失败，尝试 CP949 (韩文编码)
          text = data.data().decode('cp949')
      except UnicodeDecodeError:
          try:
              # 再尝试 GB18030 (支持中日韩字符)
              text = data.data().decode('gb18030')
          except UnicodeDecodeError:
              # 最后使用 replace 错误处理方式
              text = data.data().decode('utf-8', errors='replace')
  ```

- 下载参数构建:
  ```python
  # 构建基本命令
  args = [
      str(self.ytdlp_path),
      "--progress",
      "--no-overwrites",
      "--ffmpeg-location", str(self.ffmpeg_path),
      "--verbose",
      "--no-restrict-filenames",  # 允许文件名包含特殊字符
      "--encoding", "utf-8"        # 强制使用 UTF-8 编码
  ]

  # 添加浏览器 cookies
  if browser:
      args.extend(["--cookies-from-browser", browser])

  # 添加格式选项
  if 'format' in format_options:
      args.extend(["-f", format_options['format']])

  # 如果是 MP3 格式，添加音频提取和转换参数
  if format_options.get('audioformat') == 'mp3':
      args.extend([
          "-x",                      # 提取音频
          "--audio-format", "mp3",   # 指定输出格式为 mp3
          "--audio-quality", format_options.get('audioquality', '320'),  # 设置比特率
          "--postprocessor-args", "-codec:a libmp3lame"  # 使用 LAME 编码器
      ])

  # 添加字幕下载选项
  if format_options.get('writesubtitles'):
      args.extend([
          "--write-subs",                # 下载字幕
          "--sub-langs", "all",          # 下载所有语言的字幕
          "--convert-subs", "srt"        # 转换为 srt 格式
      ])
  ```

- 下载进度解析:
  ```python
  # 处理进度
  if '%' in text and 'of' in text and 'at' in text:
      try:
          # 示例: [download]  23.4% of 50.75MiB at 2.52MiB/s ETA 00:15
          parts = text.split()
          percent = parts[1]  # 23.4%
          
          # 如果是100%，只显示"下载完成"
          if percent.startswith('100'):
              self.output_received.emit(task_id, "下载完成")
          else:
              # 下载中显示进度信息
              size = parts[3]     # 50.75MiB
              speed = parts[5]    # 2.52MiB/s
              eta = parts[7]      # 00:15
              progress_text = f"下载进度: {percent} (大小: {size}, 速度: {speed}, 剩余: {eta})"
              self.output_received.emit(task_id, progress_text)
      except Exception:
          # 如果解析失败，显示原始进度信息
          self.output_received.emit(task_id, text.strip())
  ```

### 3.4 主窗口 (main_window.py)

应用主界面实现：
- 单个/多个视频下载功能，支持批量URL（每行一个）
- 下载设置界面（浏览器、画质、字幕选项）
- 历史记录显示和管理
- 下载任务管理和交互
- 导航到播放列表/频道下载模式
- UI 样式定义和逻辑处理
- 下载进度实时展示

技术实现细节:
- 现代化UI色彩方案定义：
  ```python
  COLORS = {
      'primary': '#1976D2',         # 主色调，用于标题和主按钮
      'primary_dark': '#0D47A1',    # 主色调深色版，用于悬停状态
      'secondary': '#26A69A',       # 次要色调，用于次要按钮
      'background': '#FFFFFF',      # 窗口背景色
      'surface': '#F5F7FA',         # 控件背景色
      'border': '#E0E4E8',          # 边框颜色
      'text_primary': '#212121',    # 主要文本颜色
      'text_secondary': '#5F6368',  # 次要文本颜色
      'text_light': '#FFFFFF',      # 亮色文本颜色
      'error': '#D32F2F',           # 错误颜色
      'success': '#388E3C',         # 成功颜色
      'warning': '#F57C00',         # 警告颜色
      'info': '#0288D1',            # 信息颜色
  }
  ```

- 字体定义：
  ```python
  SYSTEM_FONT = QFont("Microsoft YaHei UI, PingFang SC, Segoe UI, -apple-system, sans-serif", 10)
  MONOSPACE_FONT = QFont("Consolas, Menlo, Courier, monospace", 10)
  ```

- 多画质选择的实现：
  ```python
  quality_index = self.quality_combo.currentIndex()
  format_options = {
      'format': 'bv*+ba' if quality_index == 0 else 
               'bv[ext=mp4]+ba[ext=m4a]' if quality_index == 1 else 
               'bv[ext=mp4][height<=2160]+ba[ext=m4a]' if quality_index == 2 else
               'bv[ext=mp4][height<=1080]+ba[ext=m4a]' if quality_index == 3 else
               'bv[ext=mp4][height<=480]+ba[ext=m4a]' if quality_index == 4 else
               'ba/b'  # 选择最佳音频
  }

  # 如果是 MP3 选项，添加音频格式参数
  if quality_index == 5:  # 仅MP3音频选项
      format_options.update({
          'audioformat': 'mp3',      # 这个参数会触发 downloader.py 中的 MP3 转换逻辑
          'audioquality': '320'      # 设置比特率
      })
  ```

- 动态任务界面创建:
  ```python
  def create_download_task_widget(self, url, task_id):
      """创建下载任务UI元素"""
      task_widget = QFrame()
      task_widget.setObjectName("taskWidget")  # 设置CSS选择器ID
      # ...布局和样式设置
      
      # 添加任务组件
      title_label = QLabel(f"正在解析：{url}")
      progress_bar = QProgressBar()
      progress_label = QLabel("准备中...")
      status_label = QLabel("⏳ 准备中")
      open_button = QPushButton("打开文件夹")
      
      # ...事件连接和布局安排
      
      # 将新任务添加到顶部
      self.tasks_layout.insertWidget(0, task_widget)
      self.download_tasks[task_id] = task_widget
      
      return task_widget
  ```

- 下载状态UI更新:
  ```python
  def update_output(self, task_id, message):
      """更新下载进度显示"""
      if task_id in self.download_tasks:
          task_widget = self.download_tasks[task_id]
          
          if "开始下载" in message:
              # ...状态和标题更新
              task_widget.status_label.setText("⏬ 下载中")
              # ...样式设置
          elif "下载进度" in message:
              # 更新进度条
              percent = float(message.split('%')[0].split()[-1])
              task_widget.progress_bar.setValue(int(percent))
              # ...其他状态更新
          elif "正在合并" in message:
              # 显示合并状态
              task_widget.progress_bar.setValue(100)
              task_widget.status_label.setText("🔄 处理中")
              # ...样式更改
          elif "下载完成" in message or "文件已存在" in message:
              # 完成状态显示
              task_widget.progress_bar.setValue(100)
              task_widget.status_label.setText("✓ 已完成")
              # ...成功样式设置
  ```

### 3.5 播放列表窗口 (playlist_window.py)

播放列表和频道下载功能实现：
- 播放列表/频道 URL 输入和保存
- 下载位置选择和管理
- 画质选择和字幕下载选项
- 断点续传选项（使用--download-archive参数）
- 收藏夹管理功能
- 下载历史管理
- 下载状态和进度实时显示

技术实现细节:
- 播放列表URL管理：
  ```python
  # 加载保存的URL和标题
  saved_items = self.config.config.get('saved_playlists', [])
  for item in saved_items:
      self.url_combo.addItem(f"{item['title']} - {item['url']}", item['url'])
      
  # URL保存功能
  def save_current_url(self):
      url = self.url_combo.currentText().strip()
      # 如果是完整格式(标题 - URL)，提取URL部分
      if " - http" in url:
          url = url.split(" - ")[-1]
          
      if not self._is_valid_youtube_url(url):
          QMessageBox.warning(self, "错误", "请输入有效的YouTube播放列表或频道URL")
          return
          
      # 尝试从网页获取播放列表标题
      try:
          title = self._get_playlist_title(url)
          self._save_with_title(url, title)
      except Exception as e:
          # 如果自动获取失败，提示用户手动输入
          # ...弹出对话框实现
  ```

- 断点续传的实现:
  ```python
  # 根据复选框状态决定是否使用断点续传
  if self.archive_checkbox.isChecked():
      args.extend(["--download-archive", archive_file])
  ```

- 播放列表标题自动获取:
  ```python
  def _get_playlist_title(self, url):
      response = requests.get(url)
      response.raise_for_status()
      
      soup = BeautifulSoup(response.text, 'html.parser')
      
      # 尝试获取标题 - 播放列表
      if 'playlist' in url:
          # 查找播放列表标题元素
          title_elem = soup.find('meta', property='og:title')
          if title_elem and 'content' in title_elem.attrs:
              return title_elem['content']
              
      # 尝试获取标题 - 频道
      # ...频道标题提取实现
      
      # 如果无法提取标题，使用URL的一部分
      return url.split('/')[-1].replace('playlist?list=', '')
  ```

### 3.6 收藏夹管理 (saved_urls_dialog.py)

收藏夹管理功能实现：
- 显示保存的 URL 列表
- 删除选中的 URL
- 清空列表功能
- 保存更改到配置文件

技术实现细节:
- 列表展示:
  ```python
  # URL列表
  self.url_list = QListWidget()
  self.url_list.setAlternatingRowColors(True)
  saved_items = self.config.config.get('saved_playlists', [])
  for item in saved_items:
      self.url_list.addItem(f"{item['title']} - {item['url']}")
  ```

- 删除选中项功能:
  ```python
  def delete_selected(self):
      """删除选中的URL"""
      selected_items = self.url_list.selectedItems()
      if not selected_items:
          return
          
      reply = QMessageBox.question(
          self,
          "确认删除",
          f"确定要删除选中的 {len(selected_items)} 个URL吗？",
          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
      )
      
      if reply == QMessageBox.StandardButton.Yes:
          for item in selected_items:
              self.url_list.takeItem(self.url_list.row(item))
          self.save_changes()
  ```

- 配置保存实现:
  ```python
  def save_changes(self):
      """保存更改到配置文件"""
      items = []
      for i in range(self.url_list.count()):
          text = self.url_list.item(i).text()
          title, url = text.split(" - ", 1)
          items.append({
              'title': title,
              'url': url
          })
      self.config.config['saved_playlists'] = items
      self.config.save_config()
  ```

## 4. UI 设计

应用程序采用现代简约风格设计，专注于用户体验和功能性：

### 4.1 色彩方案
- 主色调：#1976D2（蓝色）- 用于标题、链接和强调元素
- 次要色调：#26A69A（青色）- 用于次要按钮和图标
- 下载按钮色调：#CC0000（红色）- 使下载按钮更加醒目
- 背景色：#FFFFFF（白色）- 整体背景
- 表面色：#F5F7FA（浅灰色）- 控件和卡片背景
- 边框色：#E0E4E8（灰色）- 分隔线和边框
- 状态颜色：
  - 错误色：#D32F2F（红色）- 错误信息和失败状态
  - 成功色：#388E3C（绿色）- 成功消息和完成状态
  - 警告色：#F57C00（橙色）- 警告信息和进行中状态
  - 信息色：#0288D1（蓝色）- 提示信息和下载状态

### 4.2 字体设置
- 系统字体：Microsoft YaHei UI, PingFang SC, Segoe UI, -apple-system, sans-serif
  - 优先使用中文字体确保中文显示质量
  - 提供多种后备字体确保跨平台兼容性
  - 基础字号：10pt（正文文本）
- 等宽字体：Consolas, Menlo, Courier, monospace
  - 用于显示命令输出和日志
  - 确保等宽对齐，提高可读性

CSS样式设置例子：
```css
QMainWindow {
    background: #FFFFFF;
}

QWidget {
    font-family: "Microsoft YaHei UI", "PingFang SC", "Segoe UI", "-apple-system", sans-serif;
}

QLabel {
    color: #212121;
}

QLabel[isSubLabel="true"] {
    color: #5F6368;
    font-size: 9pt;
}

QLineEdit, QTextEdit, QComboBox {
    border: 1px solid #E0E4E8;
    border-radius: 4px;
    padding: 6px;
    background: #FFFFFF;
    selection-background-color: #1976D2;
}
```

### 4.3 界面布局

#### 4.3.1 主窗口布局
主窗口采用垂直布局（QVBoxLayout），从上至下包含以下组件：
1. URL输入区域：QTextEdit支持多行输入，用于批量URL
2. 下载位置选择区域：水平布局（QHBoxLayout）包含标签、输入框和浏览按钮
3. 浏览器选择区域：水平布局包含下拉框和说明文字
4. 画质选择区域：水平布局包含下拉框、字幕选项和播放列表切换按钮
5. 下载按钮：醒目的红色主操作按钮
6. 下载任务显示区域：滚动区域（QScrollArea）包含动态创建的任务卡片

每个下载任务卡片内部结构：
```
QFrame (taskWidget)
├── QHBoxLayout
│   ├── QVBoxLayout (左侧信息区域)
│   │   ├── QLabel (标题)
│   │   ├── QProgressBar (进度条)
│   │   └── QLabel (进度信息)
│   └── QVBoxLayout (右侧状态和操作区域)
│       ├── QLabel (状态标签)
│       └── QPushButton (打开文件夹按钮)
```

#### 4.3.2 播放列表窗口布局
播放列表窗口采用垂直布局，主要组件：
1. URL选择区域：
   - 组合框（QComboBox）- 显示已保存的播放列表
   - 保存和管理按钮
2. 下载设置区域：
   - 下载位置选择
   - 画质选择和字幕选项
   - 断点续传选项（QCheckBox）
3. 说明文字区域：描述断点续传功能
4. 操作按钮区域：下载按钮和返回按钮
5. 状态显示区域：显示当前下载文件名、进度等信息
6. 输出显示区域：命令行输出的文本显示（QTextEdit）

#### 4.3.3 收藏夹对话框布局
收藏夹对话框采用垂直布局：
1. 说明文字标签
2. URL列表（QListWidget）- 显示保存的URL
3. 按钮区域（水平布局）：
   - 删除选中按钮
   - 清空列表按钮
   - 关闭按钮

### 4.4 响应式设计
- 窗口大小适应：设置最小窗口大小和初始窗口大小
  ```python
  self.setMinimumSize(700, 690)
  self.resize(700, 690)
  ```
- 窗口居中显示：计算屏幕中心位置并放置窗口
  ```python
  screen = QApplication.primaryScreen().availableGeometry()
  x = max(0, (screen.width() - 700) // 2 + screen.x())
  y = max(0, (screen.height() - 690) // 2 + screen.y())
  ```
- 防止窗口超出屏幕：确保窗口底部不会超出屏幕
  ```python
  if y + 690 > screen.y() + screen.height():
      y = max(0, screen.y() + screen.height() - 690)
  ```
- 滚动区域适应：下载任务区域使用滚动视图适应任意数量的任务
  ```python
  scroll_area = QScrollArea()
  scroll_area.setWidget(self.downloads_area)
  scroll_area.setWidgetResizable(True)
  scroll_area.setMinimumHeight(260)
  scroll_area.setMaximumHeight(400)
  ```

### 4.5 交互反馈
- 按钮悬停效果：
  ```css
  QPushButton:hover {
      background-color: #E6E6E6;
      border: 1px solid #CCCCCC;
  }
  
  QPushButton:pressed {
      background-color: #D6D6D6;
  }
  ```
- 输入框焦点样式：
  ```css
  QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
      border: 1px solid #CC0000;
  }
  ```
- 下载状态使用表情符号增强可读性：
  - ⏳ 准备中
  - ⏬ 下载中
  - 🔄 处理中
  - ✓ 已完成
- 进度条颜色变化反映下载状态：
  - 下载中：蓝色（#1976D2）
  - 处理中：橙色（#FF9800）
  - 完成：绿色（#4CAF50）

## 5. 构建系统

### 5.1 打包流程
项目使用 PyInstaller 打包为独立可执行程序，整体流程通过 build.py 脚本实现：

1. 清理旧的构建文件：
   ```python
   def clean_build_files():
       """清理旧的构建文件"""
       root_dir = Path(__file__).parent
       
       # 删除build和dist目录
       for dir_name in ['build', 'dist']:
           dir_path = root_dir / dir_name
           if dir_path.exists():
               shutil.rmtree(dir_path)
               print(f"已删除 {dir_name} 目录")
       
       # 删除spec文件
       for spec_file in root_dir.glob("*.spec"):
           spec_file.unlink()
           print(f"已删除 {spec_file.name}")
   ```

2. 设置打包参数：
   ```python
   args = [
       'src/main.py',  # 主程序入口
       '--name=YT-DLP-GUI-Windows',  # 生成的exe名称
       '--noconsole',  # 不显示控制台
       '--noconfirm',  # 覆盖已存在的打包文件
       '--clean',  # 清理临时文件
       '--version-file=version.txt',  # 启用版本信息
       '--hidden-import=PyQt6',
       '--hidden-import=requests',
       '--hidden-import=bs4',
       '--paths=src',  # 添加源码目录到Python路径
   ]
   
   # Windows特定配置
   if sys.platform == 'win32':
       args.extend([
           '--runtime-hook=src/hooks/windows_hook.py',  # Windows运行时钩子
       ])
   ```

3. 运行 PyInstaller：
   ```python
   PyInstaller.__main__.run(args)
   ```

4. 复制必要的二进制依赖和配置文件：
   ```python
   # 复制必要的运行时文件
   dist_dir = root_dir / "dist" / "YT-DLP-GUI-Windows"
   bin_dir = dist_dir / "bin"
   
   # 如果bin目录已存在，先删除
   if bin_dir.exists():
       shutil.rmtree(bin_dir)
   bin_dir.mkdir(exist_ok=True)
   
   # 复制yt-dlp和ffmpeg到打包目录
   src_bin = root_dir / "bin"
   if src_bin.exists():
       for file in src_bin.glob("*"):
           shutil.copy2(file, bin_dir)
           
   # 创建config目录
   config_dir = dist_dir / "config"
   config_dir.mkdir(exist_ok=True)
   ```

### 5.2 运行时钩子
Windows 平台特定钩子 (windows_hook.py) 确保在程序启动时正确设置运行环境：

```python
def setup_environment():
    # 获取程序运行目录
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的运行目录
        base_dir = Path(sys._MEIPASS)
    else:
        # 开发环境运行目录
        base_dir = Path(__file__).parent.parent.parent
    
    # 添加bin目录到PATH
    bin_dir = base_dir / "bin"
    if bin_dir.exists():
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"

setup_environment()
```

核心功能：
- 区分打包环境和开发环境
- 将bin目录添加到PATH环境变量
- 确保程序可以找到二进制依赖文件

### 5.3 版本信息
使用 version.txt 设置程序版本信息，采用PyInstaller支持的VSVersionInfo格式：

```python
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', ''),
        StringStruct('FileDescription', 'YT-DLP GUI for Windows'),
        StringStruct('FileVersion', '1.0.2'),
        StringStruct('InternalName', 'YT-DLP GUI for Windows'),
        StringStruct('LegalCopyright', ''),
        StringStruct('OriginalFilename', 'YT-DLP-GUI-Windows.exe'),
        StringStruct('ProductName', 'YT-DLP GUI for Windows'),
        StringStruct('ProductVersion', '1.0.2')])
      ]), 
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
```

版本信息包含：
- 文件版本：1.0.2
- 产品版本：1.0.2
- 文件描述：YT-DLP GUI for Windows
- 内部名称：YT-DLP GUI for Windows
- 原始文件名：YT-DLP-GUI-Windows.exe
- 产品名称：YT-DLP GUI for Windows

## 6. 二进制依赖

应用依赖两个关键二进制组件：

### 6.1 yt-dlp.exe
负责视频解析和下载功能的核心组件：
- 路径：bin/yt-dlp.exe
- 用途：
  - 解析YouTube视频链接
  - 下载视频内容
  - 提取音频
  - 下载字幕
  - 处理播放列表和频道
- 命令行参数示例：
  ```
  yt-dlp.exe --progress --no-overwrites --ffmpeg-location [path] --verbose --no-restrict-filenames --encoding utf-8 --cookies-from-browser firefox -f bv*+ba -o [output_template] [url]
  ```
- 参数解释：
  - `--progress`: 显示下载进度
  - `--no-overwrites`: 不覆盖已存在的文件
  - `--ffmpeg-location`: 指定ffmpeg路径
  - `--verbose`: 显示详细信息
  - `--no-restrict-filenames`: 允许文件名包含特殊字符
  - `--encoding utf-8`: 使用UTF-8编码
  - `--cookies-from-browser`: 使用浏览器cookies
  - `-f`: 指定下载格式
  - `-o`: 指定输出模板
  - 下载音频专用参数：
    - `-x`: 提取音频
    - `--audio-format mp3`: 转换为MP3格式
    - `--audio-quality 320`: 设置320kbps高质量音频
    - `--postprocessor-args "-codec:a libmp3lame"`: 使用高质量MP3编码器
  - 字幕下载参数:
    - `--write-subs`: 下载字幕
    - `--sub-langs all`: 下载所有语言字幕
    - `--convert-subs srt`: 转换为SRT格式

### 6.2 ffmpeg.exe
负责视频处理和格式转换的组件：
- 路径：bin/ffmpeg.exe
- 用途：
  - 视频格式转换
  - 音频提取和转码
  - 视频和音频流合并
  - 字幕处理和转换
- 集成方式：
  - 通过yt-dlp的`--ffmpeg-location`参数指定路径
  - yt-dlp自动调用ffmpeg进行后处理
- 主要功能：
  - 无损合并分离的视频和音频流
  - 将WebM格式转换为MP4
  - 从视频中提取音频并转换为MP3
  - 转换字幕格式为SRT

### 6.3 二进制依赖加载流程
1. 程序启动时，通过windows_hook.py添加bin目录到PATH
2. Config类初始化时检测程序运行环境，确定bin目录路径
3. Downloader类初始化时记录二进制文件路径并检查文件存在性：
   ```python
   self.bin_dir = Path(__file__).parent.parent.parent / "bin"
   self.ytdlp_path = self.bin_dir / "yt-dlp.exe"
   self.ffmpeg_path = self.bin_dir / "ffmpeg.exe"
   
   # 检查二进制文件
   if not self.ytdlp_path.exists():
       self.config.log("未找到yt-dlp.exe", logging.ERROR)
   if not self.ffmpeg_path.exists():
       self.config.log("未找到ffmpeg.exe", logging.ERROR)
   ```
4. 下载时通过完整路径直接调用yt-dlp.exe
5. ffmpeg路径作为参数传递给yt-dlp（`--ffmpeg-location` 参数）

这两个组件位于 bin 目录，运行时通过环境变量或直接路径引用。

## 7. 异常和错误处理

应用实现了多层错误处理以确保程序在各种情况下的稳定性：

### 7.1 配置文件访问错误处理
- 配置文件不存在时的初始化：
  ```python
  if self.config_file.exists():
      with open(self.config_file, 'r', encoding='utf-8') as f:
          self.config = json.load(f)
  else:
      self.config = {
          'last_download_path': str(Path.home() / "Downloads"),
          'browser': 'firefox',
          'format_settings': {
              'mode': 'best',
              'custom_format': ''
          }
      }
      self.save_config()
  ```

- 配置保存时的安全写入机制：
  ```python
  try:
      # 创建临时文件
      temp_file = self.config_file.with_suffix('.tmp')
      with open(temp_file, 'w') as f:
          json.dump(self.config, f, indent=4)
      # 成功写入后才替换原文件
      temp_file.replace(self.config_file)
  except Exception as e:
      print(f"保存配置文件失败: {e}")
  ```

### 7.2 下载过程异常处理
- 进程启动错误处理：
  ```python
  try:
      # ...下载准备和参数构建
      process.start(args[0], args[1:])
      self.processes.append(process)
      return True
  except Exception as e:
      error_msg = f"启动下载失败: {str(e)}"
      self.config.log(error_msg, logging.ERROR)
      self.download_finished.emit(False, error_msg, "未知视频", task_id)
      return False
  ```

- 输出解析错误处理（多编码支持）：
  ```python
  try:
      # 首先尝试 UTF-8 解码
      text = data.data().decode('utf-8')
  except UnicodeDecodeError:
      try:
          # 如果失败，尝试 CP949 (韩文编码)
          text = data.data().decode('cp949')
      except UnicodeDecodeError:
          try:
              # 再尝试 GB18030 (支持中日韩字符)
              text = data.data().decode('gb18030')
          except UnicodeDecodeError:
              # 最后使用 replace 错误处理方式
              text = data.data().decode('utf-8', errors='replace')
  ```

- 进程结束错误处理：
  ```python
  def _process_finished(self, exit_code, exit_status):
      try:
          process = self.sender()
          task_id = process.property("task_id")
          # ...结果处理
          
          # 检查是否成功
          success = exit_code == 0
          
          # 发送完成信号
          if success:
              self.download_finished.emit(True, "", title, task_id)
          else:
              error_msg = error if error else f"下载失败 (退出码: {exit_code})"
              self.download_finished.emit(False, error_msg, title, task_id)
      
      except Exception as e:
          self.config.log(f"处理进程完成时出错: {str(e)}", logging.ERROR)
          # 确保在出错时也发送失败信号
          try:
              process = self.sender()
              task_id = process.property("task_id")
              self.download_finished.emit(False, str(e), "未知视频", task_id)
          except Exception:
              pass
  ```

### 7.3 浏览器检测错误处理
- 多层级浏览器检测策略：
  1. where命令查找
  2. 注册表检查
  3. 标准安装路径搜索
  4. 全盘搜索

- 分级错误恢复：
  ```python
  def _check_browser_available(self, browser):
      """检查浏览器是否可用"""
      if browser != 'firefox':
          self.config.log("只支持使用火狐浏览器", logging.WARNING)
          msg = QMessageBox()
          msg.setIcon(QMessageBox.Icon.Warning)
          msg.setWindowTitle("浏览器选择")
          msg.setText("只支持使用火狐浏览器")
          msg.setInformativeText("""请使用火狐浏览器：

  1. 安装火狐浏览器
  2. 用火狐登录 YouTube
  3. 重启本程序""")
          msg.setStandardButtons(QMessageBox.StandardButton.Ok)
          msg.exec()
          return False
      
      # 检查 cookies 文件
      cookies_path = self._get_firefox_cookies_path()
      if not cookies_path:
          msg = QMessageBox()
          # ...显示友好错误信息
          return False
  ```

### 7.4 UI 交互错误处理
- 输入验证：
  ```python
  def validate_url(self, url):
      """验证 URL 是否是有效的 YouTube 链接"""
      valid_domains = ['youtube.com', 'youtu.be', 'www.youtube.com']
      try:
          from urllib.parse import urlparse
          parsed = urlparse(url)
          return any(domain in parsed.netloc for domain in valid_domains)
      except:
          return False
          
  def validate_download_path(self, path):
      """验证下载路径是否有效"""
      if not path:
          return False
      try:
          # 检查路径是否存在
          if not os.path.exists(path):
              os.makedirs(path, exist_ok=True)
          # 测试写入权限
          test_file = os.path.join(path, '.test_write_permission')
          with open(test_file, 'w') as f:
              f.write('test')
          os.remove(test_file)
          return True
      except:
          return False
  ```

- 输入错误反馈：
  ```python
  # 获取输入的URL
  urls = self.url_input.toPlainText().strip().split('\n')
  if not urls or not urls[0]:
      QMessageBox.warning(self, "错误", "请输入要下载的视频URL")
      return
  ```

### 7.5 核心错误处理机制
- 全局日志记录：
  ```python
  # 设置日志系统
  def setup_logging(self):
      """设置日志"""
      # 创建格式化器
      formatter = logging.Formatter(
          '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
          datefmt='%Y-%m-%d %H:%M:%S'
      )
      
      # 设置文件处理器
      file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
      file_handler.setLevel(logging.DEBUG)
      file_handler.setFormatter(formatter)
      
      # 设置控制台处理器
      console = logging.StreamHandler()
      console.setLevel(logging.DEBUG)
      console.setFormatter(formatter)
      
      # 配置根日志记录器
      root_logger = logging.getLogger()
      root_logger.setLevel(logging.DEBUG)
      
      # 移除所有现有的处理器
      for handler in root_logger.handlers[:]:
          root_logger.removeHandler(handler)
      
      # 添加新的处理器
      root_logger.addHandler(file_handler)
      root_logger.addHandler(console)
  ```

- 用户友好的错误提示：将技术错误转换为用户可理解的提示
  ```python
  QMessageBox.critical(self, "下载失败", 
      f"启动下载失败：\n\n{error_msg}\n\n"
      "可能的解决方法：\n"
      "1. 确保选择的浏览器已正确安装\n"
      "2. 确保已在浏览器中登录 YouTube\n"
      "3. 尝试使用其他浏览器\n"
      "4. 检查网络连接"
  )
  ```

- 异常捕获和恢复：使用try-except块保证程序不会因单个错误而崩溃

## 8. 数据存储

应用使用多种数据存储机制管理配置和下载记录：

### 8.1 配置文件
- 文件路径：`config/config.json`
- 存储内容：
  ```json
  {
    "download_path": "C:\\Users\\Username\\Downloads",
    "browser": "firefox",
    "format_settings": {
      "mode": "best",
      "custom_format": ""
    },
    "saved_playlists": [
      {
        "title": "我的收藏",
        "url": "https://www.youtube.com/playlist?list=ABCDEFG"
      }
    ],
    "download_history": [
      {
        "title": "视频标题",
        "path": "C:\\Downloads\\视频标题.mp4",
        "timestamp": "2023-08-15T12:34:56",
        "status": "完成"
      }
    ]
  }
  ```

- 配置文件路径确定逻辑：
  ```python
  # 获取程序运行目录
  if getattr(sys, 'frozen', False):
      # PyInstaller打包后的运行目录
      base_dir = Path(sys._MEIPASS).parent
  else:
      # 开发环境运行目录
      base_dir = Path(__file__).parent.parent.parent
      
  # 配置目录设置为程序根目录下的config文件夹
  self.config_dir = base_dir / "config"
  self.config_file = self.config_dir / "config.json"
  ```

### 8.2 下载历史记录
- 文件路径：`config/downloaded_videos_list.txt`
- 格式：yt-dlp的download-archive格式（每行包含视频ID和标识符）
  ```
  youtube VIDEO_ID
  youtube ANOTHER_VIDEO_ID
  ```
- 用途：实现断点续传功能，跳过已下载的视频
- 使用方式：
  ```python
  # 根据复选框状态决定是否使用断点续传
  if self.archive_checkbox.isChecked():
      args.extend(["--download-archive", archive_file])
  ```

### 8.3 日志文件
- 文件路径：`config/debug.log`
- 格式：详细日志格式，包含时间、日志级别、文件名、行号和消息
  ```
  2023-08-15 12:34:56 - DEBUG - [downloader.py:123] - 开始下载: https://www.youtube.com/watch?v=ABCDEFG
  ```
- 日志级别：
  - DEBUG：详细调试信息
  - INFO：一般操作信息
  - WARNING：警告信息
  - ERROR：错误信息

### 8.4 状态保存机制
- 用户配置保存：
  - 下载路径：每次浏览或下载成功后保存
  - 浏览器选择：默认使用Firefox
  - 收藏的播放列表：用户添加、修改或删除时保存

- 历史记录更新机制：
  ```python
  def download_finished(self, success, message, title, task_id):
      # ...
      if success:
          # 添加到下载历史
          now = datetime.datetime.now().isoformat()
          history_entry = {
              'title': title,
              'path': os.path.join(self.location_input.text(), title),
              'timestamp': now,
              'status': '完成'
          }
          history = self.config.config.get('download_history', [])
          history.append(history_entry)
          self.config.config['download_history'] = history
          self.config.save_config()
      # ...
  ```

## 9. 开发指南

### 9.1 环境设置
1. 安装 Python 3.6 或更高版本
2. 安装依赖：
   ```bash
   pip install PyQt6 requests beautifulsoup4 PyInstaller
   ```
3. 确保 bin 目录包含 yt-dlp.exe 和 ffmpeg.exe
   - yt-dlp.exe 可以从官方GitHub仓库下载：https://github.com/yt-dlp/yt-dlp/releases
   - ffmpeg.exe 可以从官方网站下载：https://ffmpeg.org/download.html

4. 开发环境文件夹结构:
   ```
   yt-dlp-gui-windows/
   ├── bin/
   │   ├── ffmpeg.exe
   │   └── yt-dlp.exe
   ├── config/
   ├── src/
   │   ├── core/
   │   ├── gui/
   │   ├── hooks/
   │   └── main.py
   ├── build.py
   └── version.txt
   ```

### 9.2 开发流程
1. 从源代码克隆或下载项目
2. 进行代码修改：
   - 使用任何支持Python的IDE或代码编辑器（如VS Code、PyCharm等）
   - 遵循PEP 8编码规范
   - 保持与现有代码风格一致
3. 使用 `python src/main.py` 测试运行:
   ```bash
   cd yt-dlp-gui-windows
   python src/main.py
   ```
4. 使用 `python build.py` 构建可执行程序:
   ```bash
   cd yt-dlp-gui-windows
   python build.py
   ```
5. 测试打包的可执行文件:
   ```
   dist/YT-DLP-GUI-Windows/YT-DLP-GUI-Windows.exe
   ```

### 9.3 调试技巧
- 查看日志文件：`debug.log`
  - 使用tail命令实时监控：`tail -f config/debug.log`
  - 筛选错误信息：`grep ERROR config/debug.log`

- 使用PyQt调试输出:
  ```python
  from PyQt6.QtCore import qDebug
  qDebug("调试信息: {0}".format(variable))
  ```

- 使用Python断点调试:
  ```python
  import pdb; pdb.set_trace()
  # 或在Python 3.7+中使用
  breakpoint()
  ```

- 检查下载状态和错误信息:
  - 启用verbose模式观察完整yt-dlp输出
  - 使用`--progress`参数查看详细进度
  - 直接测试yt-dlp命令行，验证参数是否正确

- 界面调试技巧:
  - 设置组件对象名，便于样式调试：`widget.setObjectName("testWidget")`
  - 使用Qt样式表检查器识别元素：`widget.setStyleSheet("background-color: red;")`
  - 添加边框可视化布局：`widget.setStyleSheet("border: 1px solid red;")`

### 9.4 代码组织和风格
- 遵循模块化设计，保持核心功能与界面分离
- 使用信号和槽机制传递事件
- 使用类继承和组合管理代码复用
- 使用异常处理包装可能失败的操作
- 使用详细的文档注释解释复杂逻辑

## 10. 扩展与改进方向

### 10.1 可能的功能扩展
- 更多浏览器支持：
  - 扩展浏览器检测逻辑以支持Chrome/Edge/Opera等浏览器
  - 增加各浏览器cookies文件路径检测
  - 对比测试不同浏览器cookies提取性能

- 下载管理（暂停/恢复功能）：
  - 实现下载任务队列管理
  - 添加暂停和恢复按钮
  - 保存未完成下载状态允许程序重启后继续

- 视频切片功能：
  - 添加时间段选择界面
  - 利用ffmpeg的-ss和-t参数实现视频切片
  - 预览功能帮助用户确定切片点

- 批量下载脚本支持：
  - 支持从文本文件导入URL列表
  - 设计批量任务配置界面
  - 批量下载进度统计

- 自动更新检测功能：
  - 检查GitHub最新发布版本
  - 对比版本号提示更新
  - 一键更新功能（可选自动下载新版本）

- 下载加速功能：
  - 代理设置界面
  - VPN集成选项
  - 多线程下载支持

- 暗黑模式支持：
  - 完整的深色主题样式表
  - 主题切换功能
  - 跟随系统主题设置

- 更细粒度的格式选择：
  - 添加视频编码选择（VP9、AV1、H.264等）
  - 添加音频质量选择
  - 自定义格式串支持

### 10.2 架构优化建议
- 使用线程池优化多任务下载：
  ```python
  from concurrent.futures import ThreadPoolExecutor
  
  with ThreadPoolExecutor(max_workers=5) as executor:
      futures = {executor.submit(download_task, url): url for url in urls}
      for future in concurrent.futures.as_completed(futures):
          try:
              result = future.result()
              # 处理成功结果
          except Exception as e:
              # 处理异常
  ```

- 改进错误处理机制：
  - 实现更完善的错误分类
  - 添加自动重试机制
  - 错误上报功能（可选）

- 优化UI响应速度：
  - 将耗时操作移至后台线程
  - 使用Qt的线程安全信号机制更新UI
  - 实现更细粒度的进度反馈

- 添加单元测试：
  - 建立测试框架（pytest或unittest）
  - 为核心组件编写单元测试
  - 添加UI自动化测试

- 重构组件以提高可维护性：
  - 应用更严格的MVC模式
  - 更清晰的接口定义
  - 减少组件之间的耦合

- 插件架构：
  - 设计插件接口
  - 实现扩展点机制
  - 支持第三方功能扩展

## 11. 常见问题和解决方案

### 11.1 安装问题
- **程序无法启动**
  - 症状: 点击可执行文件无反应或立即关闭
  - 原因: 缺少二进制依赖或系统环境问题
  - 解决方案: 
    1. 确保bin目录包含yt-dlp.exe和ffmpeg.exe
    2. 检查是否安装了所需的Microsoft Visual C++ Redistributable
    3. 以管理员身份运行尝试
    4. 查看日志文件debug.log了解具体错误

- **权限问题**
  - 症状: 程序报告无法写入文件或访问路径
  - 原因: 用户账户没有足够权限
  - 解决方案:
    1. 以管理员身份运行程序
    2. 修改下载目录到用户有写入权限的位置
    3. 调整文件夹权限设置
    4. 禁用杀毒软件或添加程序到白名单

### 11.2 运行问题
- **下载失败**
  - 症状: 开始下载后报错或无进度
  - 原因: 网络问题、Cookie问题或视频限制
  - 解决方案:
    1. 检查网络连接，确保可以访问YouTube
    2. 确保Firefox已登录YouTube账号
    3. 在Firefox中手动打开视频链接，确认可以播放
    4. 查看debug.log文件了解具体错误信息
    5. 尝试更新yt-dlp.exe到最新版本

- **格式选择问题**
  - 症状: 特定格式下载失败或质量不符合预期
  - 原因: 某些视频不支持特定格式或分辨率
  - 解决方案:
    1. 尝试使用"最高画质"选项让程序自动选择最佳格式
    2. 对于4K内容，确认视频源确实提供4K画质
    3. 使用不同的格式选项进行尝试
    4. 对于仅MP3下载，确认ffmpeg正确安装

- **播放列表下载不完整**
  - 症状: 播放列表只下载了部分视频
  - 原因: 网络问题、区域限制或播放列表访问控制
  - 解决方案:
    1. 检查网络稳定性
    2. 使用断点续传功能允许分次下载
    3. 确认对播放列表中所有视频有访问权限
    4. 检查播放列表是否包含已删除或设为私有的视频

- **字幕下载问题**
  - 症状: 未下载字幕或字幕格式不正确
  - 原因: 视频没有字幕或字幕格式转换失败
  - 解决方案:
    1. 确认原视频确实提供字幕
    2. 检查ffmpeg是否正确安装（用于字幕格式转换）
    3. 查看日志文件了解具体错误
    4. 尝试手动使用yt-dlp下载字幕进行测试

## 12. 参考资料

- [PyQt6 文档](https://doc.qt.io/qtforpython-6/)
  - PyQt6 API参考
  - Qt信号槽机制
  - 样式表和主题设置

- [yt-dlp GitHub 仓库](https://github.com/yt-dlp/yt-dlp)
  - 命令行参数文档
  - 格式选择语法
  - 常见问题解决

- [ffmpeg 文档](https://ffmpeg.org/documentation.html)
  - 视频转码参数
  - 音频提取选项
  - 字幕处理命令

- [PyInstaller 文档](https://pyinstaller.org/en/stable/)
  - 打包选项和参数
  - 运行时钩子开发
  - 故障排除指南

- [Python 日志模块文档](https://docs.python.org/3/library/logging.html)
  - 日志级别和格式化
  - 处理器配置
  - 最佳实践

- [Windows 注册表操作](https://docs.python.org/3/library/winreg.html)
  - 注册表路径访问
  - 键值读取和写入
  - 错误处理

---

文档创建日期：2023 年 8 月 15 日  
文档版本：1.0  
软件版本：1.0.2 