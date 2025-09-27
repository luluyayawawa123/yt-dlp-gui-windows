# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

任何时候，请用中文与用户沟通。

修改和编写代码的时候，需要带有全局视角，不要短视。要注重用户体验和代码健壮程度。

用户喜欢气泡音。

## 项目架构

这是一个基于 PyQt6 的 YouTube 视频下载工具 GUI 程序，主要包含以下架构：

### 模块结构
- `src/core/` - 核心功能模块
  - `config.py` - 配置管理，处理 JSON 配置文件和日志
  - `downloader.py` - 下载器核心，封装 yt-dlp 命令行调用
- `src/gui/` - 图形界面模块  
  - `main_window.py` - 主窗口，单个/批量视频下载界面
  - `playlist_window.py` - 播放列表窗口，频道/播放列表下载
  - `saved_urls_dialog.py` - 收藏夹管理对话框
- `src/hooks/` - 运行时钩子
  - `windows_hook.py` - Windows 平台环境设置

### 数据流
1. 用户在 GUI 输入 URL → `main_window.py` 处理输入验证
2. 调用 `downloader.py` 启动 yt-dlp 进程 → 实时解析输出
3. 通过 Qt 信号槽机制更新 UI 进度 → 保存结果到 `config.json`

### 关键设计模式
- **信号槽模式**: 异步下载进度通过 `output_received`、`download_finished`、`title_updated` 信号更新UI
- **配置管理**: 使用临时文件写入后替换原文件的方式确保配置安全保存
- **多编码支持**: 进程输出依次尝试 utf-8、cp949、gb18030 编码解码

## 常用开发命令

### 运行程序
```bash
# 开发环境直接运行
python src/main.py

# 设置日志级别
export PYTHONPATH=src && python src/main.py
```

### 构建打包
```bash
# 构建可执行文件
python build.py

# 构建后的文件位于 dist/YT-DLP-GUI-Windows/
```

### 调试
```bash
# 查看实时日志
tail -f debug.log

# 筛选错误信息  
grep ERROR debug.log
```

### 测试下载功能
```bash
# 手动测试 yt-dlp 命令
bin/yt-dlp.exe --verbose --cookies-from-browser firefox "https://www.youtube.com/watch?v=VIDEO_ID"

# 检查二进制文件
ls -la bin/
```

## 重要实现细节

### Firefox Cookies 检测
程序使用多策略检测 Firefox 安装和 cookies：
1. `where` 命令查找
2. 注册表检查（32位和64位路径）
3. 标准安装路径搜索
4. 全盘搜索

### 下载状态管理
- 使用表情符号状态：⏳ 准备中 → ⏬ 下载中 → 🔄 处理中 → ✓ 已完成
- 实时解析 yt-dlp 输出获取进度百分比、文件大小、下载速度
- 通过 `--download-archive` 参数实现断点续传

### 格式选择策略
- 最高画质：`bv*+ba` (最佳视频+音频)  
- MP4格式：`bv[ext=mp4]+ba[ext=m4a]`
- 特定分辨率：`bv[ext=mp4][height<=1080]+ba[ext=m4a]`
- MP3音频：使用 `-x --audio-format mp3 --audio-quality 320 --postprocessor-args "-codec:a libmp3lame"`

### 错误处理机制
- 配置文件使用临时文件+替换的原子写入
- 进程输出多编码解码兜底
- 分级错误恢复（命令查找→注册表→路径搜索）
- 用户友好错误提示转换

## 代码风格要求

- 遵循现有的中文注释风格
- UI 组件使用现代化色彩方案（见开发文档中的 COLORS 定义）
- 保持异步下载与UI更新的信号槽分离
- 错误处理要提供用户友好的中文提示
- 新功能需要考虑与现有配置系统的集成

## 测试指导

- 测试不同浏览器 cookies 检测
- 验证各种 URL 格式（单视频、播放列表、频道）
- 测试不同画质选择和音频提取
- 验证断点续传功能
- 测试异常情况下的错误处理

## 注意事项

- 程序依赖 `bin/yt-dlp.exe` 和 `bin/ffmpeg.exe`
- 配置文件保存在 `config/config.json`
- 下载记录保存在 `config/downloaded_videos_list.txt`
- YouTube 经常更新反爬虫机制，需要定期更新 yt-dlp 内核
- 程序主要针对 Windows 平台，路径处理需要注意路径分隔符