from PyQt6.QtCore import QObject, QProcess, pyqtSignal, QProcessEnvironment
import shlex
import sys
import os
import logging
from .config import Config
from pathlib import Path
import winreg  # 添加这行到文件顶部
import glob
from PyQt6.QtWidgets import QMessageBox

class Downloader(QObject):
    # 修改信号，添加任务ID
    output_received = pyqtSignal(str, str)  # task_id, message
    download_finished = pyqtSignal(bool, str, str, str)  # success, message, title, task_id
    title_updated = pyqtSignal(str, str)  # task_id, title
    
    def __init__(self):
        super().__init__()
        self.processes = []
        self.task_count = 0
        
        # 获取二进制文件路径
        self.bin_dir = Path(__file__).parent.parent.parent / "bin"
        self.ytdlp_path = self.bin_dir / "yt-dlp.exe"
        self.ffmpeg_path = self.bin_dir / "ffmpeg.exe"
        
        # 记录启动日志
        self.config = Config()
        self.config.log(f"二进制文件目录: {self.bin_dir}", logging.DEBUG)
        self.config.log(f"yt-dlp路径: {self.ytdlp_path}", logging.DEBUG)
        self.config.log(f"ffmpeg路径: {self.ffmpeg_path}", logging.DEBUG)
        
        # 检查二进制文件
        if not self.ytdlp_path.exists():
            self.config.log("未找到yt-dlp.exe", logging.ERROR)
        if not self.ffmpeg_path.exists():
            self.config.log("未找到ffmpeg.exe", logging.ERROR)
        
        # 设置环境变量
        self.env = QProcessEnvironment.systemEnvironment()
        self.env.insert("PATH", str(self.bin_dir) + os.pathsep + os.environ.get("PATH", ""))
        
        # 定义支持的视频平台配置
        self.platform_configs = {
            'youtube': {
                'domains': ['youtube.com', 'youtu.be', 'm.youtube.com'],
                'require_cookies': True,
                'default_browser': 'firefox',
                'special_args': [],
                'default_format': None  # 使用用户选择的格式
            },
            'xiaohongshu': {
                'domains': ['xiaohongshu.com', 'xhslink.com'],
                'require_cookies': False,
                'default_browser': None,
                'special_args': [
                    '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                ],
                'default_format': 'best[ext=mp4]/best',  # 优先选择mp4格式，否则选择最好的
                'user_profile_support': False,  # 当前版本不支持用户主页批量下载
                'supported_patterns': [
                    '/explore/',           # 标准视频链接
                    '/discovery/item/',    # 发现页面视频
                    '/user/profile/.+/.+', # 用户的具体视频
                ]
            },
            'bilibili': {
                'domains': ['bilibili.com', 'b23.tv'],
                'require_cookies': False,
                'default_browser': None,
                'special_args': [],
                'default_format': 'best[ext=mp4]/best'  # B站也优先mp4
            },
            'douyin': {
                'domains': ['douyin.com', 'iesdouyin.com'],
                'require_cookies': False,
                'default_browser': None,
                'special_args': [
                    '--user-agent', 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'
                ],
                'default_format': 'best[ext=mp4]/best'  # 抖音也优先mp4
            }
        }
        
    def reset_state(self):
        """重置下载器状态"""
        self.task_count = 0
        # 取消所有正在进行的下载
        self.cancel_download()
        # 清理进程列表
        self.processes.clear()
        
    def detect_platform(self, url):
        """检测URL所属的视频平台"""
        import urllib.parse as urlparse
        
        try:
            parsed_url = urlparse.urlparse(url.lower())
            domain = parsed_url.netloc.replace('www.', '').replace('m.', '')
            
            # 检查每个平台的域名
            for platform, config in self.platform_configs.items():
                for platform_domain in config['domains']:
                    if platform_domain in domain:
                        self.config.log(f"检测到平台: {platform} (URL: {url})", logging.DEBUG)
                        return platform
            
            # 如果没有匹配到已知平台，默认使用通用配置
            self.config.log(f"未识别的平台，使用通用配置 (URL: {url})", logging.DEBUG)
            return 'generic'
            
        except Exception as e:
            self.config.log(f"URL解析错误: {str(e)}", logging.ERROR)
            return 'generic'
    
    def normalize_xiaohongshu_url(self, url):
        """将小红书用户视频URL规范化为标准格式"""
        try:
            import re
            import urllib.parse as urlparse
            
            # 检查是否为用户视频URL格式: /user/profile/{user_id}/{video_id}
            user_video_pattern = r'/user/profile/[a-fA-F0-9]+/([a-fA-F0-9]+)'
            match = re.search(user_video_pattern, url)
            
            if match:
                video_id = match.group(1)
                parsed_url = urlparse.urlparse(url)
                
                # 构建标准的explore格式URL
                standard_url = f"{parsed_url.scheme}://{parsed_url.netloc}/explore/{video_id}"
                
                # 保留查询参数
                if parsed_url.query:
                    standard_url += f"?{parsed_url.query}"
                
                self.config.log(f"URL格式转换: {url} -> {standard_url}", logging.DEBUG)
                return standard_url
            
            # 如果不是用户视频格式，返回原URL
            return url
            
        except Exception as e:
            self.config.log(f"URL格式化错误: {str(e)}", logging.ERROR)
            return url
    
    def is_user_profile_url(self, url, platform):
        """检测是否为用户主页/个人资料URL（不是具体视频）"""
        try:
            if platform == 'xiaohongshu':
                import re
                # 匹配用户主页格式：/user/profile/{user_id} (结尾没有视频ID)
                # 具体视频格式：/user/profile/{user_id}/{video_id} (有视频ID，应该支持下载)
                pattern = r'/user/profile/[a-fA-F0-9]+/?(\?|$)'
                if re.search(pattern, url):
                    # 是纯用户主页，没有具体视频ID
                    return True
                else:
                    # 包含视频ID或其他路径，不是纯用户主页
                    return False
            elif platform == 'bilibili':
                return '/space.bilibili.com/' in url.lower() or '/space/' in url.lower()
            elif platform == 'douyin':
                return '/user/' in url.lower()
            return False
        except Exception:
            return False
    
    def get_platform_config(self, platform):
        """获取平台特定配置"""
        if platform in self.platform_configs:
            return self.platform_configs[platform]
        else:
            # 返回通用配置
            return {
                'domains': [],
                'require_cookies': False,
                'default_browser': None,
                'special_args': [],
                'default_format': 'best'  # 通用平台使用best格式
            }
        
    def _get_firefox_path_from_registry(self):
        """查找火狐浏览器的安装路径"""
        try:
            # 1. 使用 where 命令查找
            try:
                import subprocess
                result = subprocess.run(['where', 'firefox'], capture_output=True, text=True)
                if result.returncode == 0:
                    firefox_path = result.stdout.strip().split('\n')[0]
                    if os.path.exists(firefox_path):
                        self.config.log(f"通过 where 命令找到火狐: {firefox_path}", logging.DEBUG)
                        return firefox_path
            except Exception as e:
                self.config.log(f"where 命令查找失败: {str(e)}", logging.DEBUG)

            # 2. 检查注册表的所有可能位置
            registry_paths = [
                (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Mozilla\Mozilla Firefox'),
                (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Mozilla\Mozilla Firefox ESR'),
                (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Wow6432Node\Mozilla\Mozilla Firefox'),
                (winreg.HKEY_CURRENT_USER, r'SOFTWARE\Mozilla\Mozilla Firefox'),
                (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\firefox.exe'),
                (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Mozilla Firefox')
            ]
            
            for root_key, sub_key in registry_paths:
                try:
                    with winreg.OpenKey(root_key, sub_key) as key:
                        try:
                            path = winreg.QueryValue(key, None)
                            if path and os.path.exists(path):
                                if os.path.isfile(path):
                                    self.config.log(f"从注册表找到火狐: {path}", logging.DEBUG)
                                    return path
                                elif os.path.isdir(path) and os.path.exists(os.path.join(path, 'firefox.exe')):
                                    firefox_path = os.path.join(path, 'firefox.exe')
                                    self.config.log(f"从注册表找到火狐: {firefox_path}", logging.DEBUG)
                                    return firefox_path
                        except:
                            # 尝试读取 PathToExe 或 InstallLocation
                            try:
                                path = winreg.QueryValueEx(key, 'PathToExe')[0]
                                if os.path.exists(path):
                                    self.config.log(f"从注册表 PathToExe 找到火狐: {path}", logging.DEBUG)
                                    return path
                            except:
                                try:
                                    install_dir = winreg.QueryValueEx(key, 'InstallLocation')[0]
                                    firefox_path = os.path.join(install_dir, 'firefox.exe')
                                    if os.path.exists(firefox_path):
                                        self.config.log(f"从注册表 InstallLocation 找到火狐: {firefox_path}", logging.DEBUG)
                                        return firefox_path
                                except:
                                    pass
                except WindowsError:
                    continue

            # 3. 搜索所有可能的安装位置
            search_paths = [
                os.path.expandvars(r'%ProgramFiles%\Mozilla Firefox\firefox.exe'),
                os.path.expandvars(r'%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe'),
                os.path.expandvars(r'%LocalAppData%\Mozilla Firefox\firefox.exe'),
                os.path.expandvars(r'%ProgramFiles%\Firefox\firefox.exe'),
                os.path.expandvars(r'%ProgramFiles(x86)%\Firefox\firefox.exe'),
                r'C:\Program Files\Mozilla Firefox\firefox.exe',
                r'C:\Program Files (x86)\Mozilla Firefox\firefox.exe'
            ]
            
            # 添加所有盘符的搜索
            import string
            drives = [f'{d}:' for d in string.ascii_uppercase if os.path.exists(f'{d}:')]
            for drive in drives:
                search_paths.extend([
                    f'{drive}\\Program Files\\Mozilla Firefox\\firefox.exe',
                    f'{drive}\\Program Files (x86)\\Mozilla Firefox\\firefox.exe',
                    f'{drive}\\Firefox\\firefox.exe'
                ])

            for path in search_paths:
                if os.path.exists(path):
                    self.config.log(f"在路径中找到火狐: {path}", logging.DEBUG)
                    return path

            # 4. 如果还是找不到，记录错误并返回
            self.config.log("未能找到火狐浏览器，但系统可能已安装", logging.ERROR)
            return None

        except Exception as e:
            self.config.log(f"查找火狐浏览器时出错: {str(e)}", logging.ERROR)
            return None

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
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("需要登录")
            msg.setText("请先用火狐浏览器登录 YouTube")
            msg.setInformativeText("""请按以下步骤操作：

1. 打开火狐浏览器
2. 登录 YouTube 账号
3. 重启本程序""")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()
            return False
        
        return True

    def set_environment(self, env):
        """设置进程环境变量"""
        # 将列表转换为 QProcessEnvironment
        new_env = QProcessEnvironment()
        for env_str in env:
            if '=' in env_str:
                key, value = env_str.split('=', 1)
                new_env.insert(key, value)
        
        # 保持原有的 PATH 设置
        new_env.insert("PATH", str(self.bin_dir) + os.pathsep + os.environ.get("PATH", ""))
        self.env = new_env

    def start_download(self, url, output_path, format_options, browser):
        """开始下载"""
        try:
            # 检测平台并获取配置
            platform = self.detect_platform(url)
            platform_config = self.get_platform_config(platform)
            
            # 对小红书URL进行格式规范化
            if platform == 'xiaohongshu':
                url = self.normalize_xiaohongshu_url(url)
            
            # 检查是否为用户主页链接
            if self.is_user_profile_url(url, platform):
                if platform == 'xiaohongshu' and not platform_config.get('user_profile_support', True):
                    error_msg = """小红书用户主页批量下载功能暂时不可用。

当前解决方案：
1. 手动复制用户主页中的单个视频链接进行下载
2. 等待 yt-dlp 未来版本支持小红书用户主页
3. 使用播放列表窗口尝试其他方式

建议：点击用户主页中的具体视频，复制单个视频链接来下载。"""
                    self.config.log("小红书用户主页批量下载暂不支持", logging.WARNING)
                    raise Exception(error_msg)
            
            # 对于需要cookies的平台，检查浏览器是否可用
            if platform_config['require_cookies']:
                if not self._check_browser_available(browser):
                    browser_names = {
                        'firefox': 'Firefox 火狐浏览器',
                        'chrome': 'Chrome 谷歌浏览器',
                        'opera': 'Opera 浏览器',
                        'brave': 'Brave 浏览器'
                    }
                    browser_name = browser_names.get(browser, browser)
                    error_msg = f"未检测到 {browser_name}，请先安装浏览器或选择其他已安装的浏览器。"
                    self.config.log(error_msg, logging.ERROR)
                    raise Exception(error_msg)
            else:
                # 对于不需要cookies的平台，记录信息
                self.config.log(f"平台 {platform} 无需浏览器cookies，直接下载", logging.INFO)

            # 记录系统环境信息
            self.config.log(f"系统环境 PATH: {os.environ.get('PATH', '')}", logging.DEBUG)
            self.config.log(f"当前工作目录: {os.getcwd()}", logging.DEBUG)
            self.config.log(f"下载目录: {output_path}", logging.DEBUG)
            
            # 生成任务ID
            task_id = f"Task-{self.task_count + 1}"
            self.task_count += 1
            
            # 检查 yt-dlp 是否可用
            if not self._check_yt_dlp_available():
                error_msg = "未找到 yt-dlp 命令或无法执行"
                self.config.log(error_msg, logging.ERROR)
                self.download_finished.emit(False, error_msg, "未知视频", task_id)
                return False
            
            # 构建基本命令
            args = [
                str(self.ytdlp_path),
                "--progress",
                "--no-overwrites",
                "--ffmpeg-location", str(self.ffmpeg_path),
                "--verbose",
                "--no-restrict-filenames",  # 添加这个参数,允许文件名包含特殊字符
                "--encoding", "utf-8"        # 强制使用 UTF-8 编码
            ]

            # 添加平台特殊参数
            if platform_config['special_args']:
                args.extend(platform_config['special_args'])
                self.config.log(f"添加平台 {platform} 特殊参数: {platform_config['special_args']}", logging.DEBUG)

            # 添加浏览器 cookies（仅对需要的平台）
            if platform_config['require_cookies'] and browser:
                args.extend(["--cookies-from-browser", browser])
                self.config.log(f"使用浏览器 {browser} 的cookies", logging.DEBUG)

            # 添加格式选项 - 根据平台智能选择
            if 'format' in format_options and format_options['format']:
                user_format = format_options['format']
                
                # 检查用户选择的格式是否适用于当前平台
                if platform != 'youtube' and user_format in ['bv*+ba', 'bv[ext=mp4]+ba[ext=m4a]', 'bv*[height<=1080]+ba']:
                    # 非YouTube平台但用户选择了YouTube特定格式，使用平台默认格式
                    if platform_config.get('default_format'):
                        args.extend(["-f", platform_config['default_format']])
                        self.config.log(f"平台 {platform} 不支持格式 {user_format}，使用平台默认格式: {platform_config['default_format']}", logging.DEBUG)
                    else:
                        self.config.log(f"平台 {platform} 不支持格式 {user_format}，使用自动选择", logging.DEBUG)
                else:
                    # 用户指定的格式适用，直接使用
                    args.extend(["-f", user_format])
                    self.config.log(f"使用用户指定格式: {user_format}", logging.DEBUG)
            elif platform_config.get('default_format'):
                # 使用平台特定的默认格式
                args.extend(["-f", platform_config['default_format']])
                self.config.log(f"使用平台 {platform} 默认格式: {platform_config['default_format']}", logging.DEBUG)
            # 如果都没有，yt-dlp会自动选择最好的格式

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

            # 添加输出模板
            output_template = os.path.join(output_path, "%(title)s.%(ext)s")
            args.extend(["-o", output_template])

            # 添加URL
            args.append(url)
            
            # 记录完整命令（用于调试）
            self.config.log(f"执行命令: {' '.join(args)}", logging.DEBUG)
            
            # 创建新进程
            process = QProcess()
            process.setProcessEnvironment(self.env)
            process.setWorkingDirectory(output_path)
            
            # 设置进程属性
            process.setProperty("url", url)
            process.setProperty("task_id", task_id)
            process.setProperty("title", "未知视频")
            process.setProperty("title_set", False)  # 初始化标题设置状态
            
            # 修改这里：使用 finished 信号来处理下载完成
            process.finished.connect(
                lambda exit_code, exit_status: self._process_finished(exit_code, exit_status)
            )
            
            # 修改输出处理的连接方式
            def handle_stdout():
                data = process.readAllStandardOutput()
                self._handle_process_output(process, data)
                
            def handle_stderr():
                data = process.readAllStandardError()
                self._handle_process_output(process, data)
                
            process.readyReadStandardOutput.connect(handle_stdout)
            process.readyReadStandardError.connect(handle_stderr)
            
            # 启动进程
            process.start(args[0], args[1:])
            self.processes.append(process)
            return True
            
        except Exception as e:
            error_msg = f"启动下载失败: {str(e)}"
            self.config.log(error_msg, logging.ERROR)
            self.download_finished.emit(False, error_msg, "未知视频", task_id)
            return False
        
    def cancel_download(self):
        """取消所有正在进行的下载"""
        for process in self.processes:
            if process.state() == QProcess.ProcessState.Running:
                process.kill()  # 强制结束进程
        self.processes.clear()  # 清空进程列表
        
    def _handle_process_output(self, process, data):
        """处理下载进程的输出"""
        try:
            # 改进编码处理逻辑
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
        
            if not text:
                return
            
            task_id = process.property("task_id")
            
            # 发送原生日志到日志窗口（在处理之前发送，确保完整性）
            # 这样高级用户可以看到完整的yt-dlp和ffmpeg输出
            self.output_received.emit(task_id, f"[RAW_LOG]{text.rstrip()}")
            
            # 处理下载信息
            if '[download]' in text:
                # 处理标题 - 更精确地识别真正的文件名
                if 'Destination:' in text and not process.property("title_set"):
                    # 只有当标题尚未设置时才处理，避免被后续的临时文件信息覆盖
                    # 检查是否是真正的视频文件路径（不是临时文件或部分下载文件）
                    destination_line = text.strip()
                    if 'Destination:' in destination_line:
                        # 提取文件名并保持原始编码
                        # 先找到"Destination:"的确切位置
                        dest_index = destination_line.find('Destination:')
                        if dest_index != -1:
                            # 从"Destination:"之后提取内容
                            title_part = destination_line[dest_index + len('Destination:'):].strip()
                            # 移除可能的额外信息（如进度信息）
                            # 按顺序处理各种可能的进度信息分隔符
                            progress_separators = [' [download]', ' ETA ', ' at ', ' of ']
                            for separator in progress_separators:
                                if separator in title_part:
                                    title_part = title_part.split(separator)[0]
                            
                            # 进一步清理可能的数字和百分比信息
                            import re
                            # 移除类似 "0.0%" 的百分比信息
                            title_part = re.sub(r'\s*\d+\.\d+%\s*.*$', '', title_part)
                            # 移除类似 ".f123" 的临时文件扩展名
                            title_part = re.sub(r'\.f\d+', '', title_part)
                            
                            title = os.path.splitext(os.path.basename(title_part))[0]
                            
                            # 检查是否是字幕文件，如果是则跳过（我们只关心视频文件的标题）
                            subtitle_extensions = ['.vtt', '.srt', '.ass', '.lrc', '.sbv', '.sub', '.txt']
                            is_subtitle_file = any(ext in title_part for ext in subtitle_extensions)
                            if is_subtitle_file:
                                self.config.log(f"跳过字幕文件标题: '{title}'", logging.DEBUG)
                                title = ""
                        else:
                            title = ""
                        
                        # 添加调试信息
                        self.config.log(f"提取到标题: '{title}'", logging.DEBUG)
                        
                        # 过滤掉明显不是视频标题的信息
                        if title and len(title) > 1:
                            # 检查是否包含明显的进度信息关键词
                            progress_keywords = ['ETA', 'at', 'of', '%', 'MiB', 'KiB', 'GiB']
                            is_progress_info = any(keyword in title for keyword in progress_keywords)
                            
                            # 添加调试信息
                            self.config.log(f"是否为进度信息: {is_progress_info}", logging.DEBUG)
                            
                            # 如果标题有效且尚未设置，更新标题
                            # 即使看起来像进度信息，也可能是真实的短标题
                            if not process.property("title_set"):
                                # 对于非常短的标题（如"s"），需要额外验证
                                if len(title) <= 3:
                                    # 检查是否是合理的标题（不是纯数字或特殊字符）
                                    is_valid_title = not title.replace('.', '').replace('_', '').replace('-', '').isdigit()
                                    # 如果是单个字母，很可能是错误的标题
                                    if len(title) == 1 and title.isalpha():
                                        is_valid_title = False
                                    
                                    if not is_valid_title:
                                        self.config.log(f"标题被过滤（不合理）: '{title}'", logging.DEBUG)
                                        title = None
                                
                                if title:
                                    # 标题长度限制和截断处理
                                    max_length = 50  # 设置最大长度
                                    if len(title) > max_length:
                                        # 保留前后部分，中间用省略号，注意处理多字节字符
                                        title = title[:max_length//2-2] + "..." + title[-max_length//2+1:]
                                    
                                    process.setProperty("title", title)
                                    process.setProperty("title_set", True)  # 标记标题已设置
                                    self.output_received.emit(task_id, f"开始下载: {title}")
                                    self.title_updated.emit(task_id, title)
                                    self.config.log(f"成功设置标题: '{title}'", logging.DEBUG)
                            else:
                                self.config.log(f"标题已设置，跳过更新", logging.DEBUG)
                        else:
                            self.config.log(f"标题被过滤（长度不足或为空）: '{title}'", logging.DEBUG)
                # 处理进度
                elif '%' in text and 'of' in text and 'at' in text:
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
                # 处理合并信息
                elif 'Merging formats into' in text:
                    self.output_received.emit(task_id, "正在合并视频和音频...")
                # 处理已存在文件
                elif 'has already been downloaded' in text:
                    self.output_received.emit(task_id, "文件已存在")
                # 处理完成信息
                elif 'has already been downloaded and merged' in text:
                    self.output_received.emit(task_id, "下载完成")
                
        except Exception as e:
            self.config.log(f"处理输出时出错: {str(e)}", logging.ERROR)
            
    def analyze_formats(self, url):
        """分析视频可用格式"""
        process = QProcess()
        args = ["--cookies-from-browser", "safari", "-F", url]
        process.start("yt-dlp", args)
        process.waitForFinished()
        
        # 获取输出
        stdout = process.readAllStandardOutput().data().decode()
        stderr = process.readAllStandardError().data().decode()
        
        # 返回完整输出
        return stdout + stderr
        
    def _parse_format_list(self, output):
        """解析yt-dlp -F的输出"""
        formats = []
        for line in output.split('\n'):
            if line.startswith('format code') or not line.strip():
                continue
            try:
                parts = line.split()
                if len(parts) < 3:
                    continue
                    
                code = parts[0]
                ext = parts[1] if len(parts) > 1 else ""
                desc = line  # 保存完整的格式描述
                
                # 分类格式
                is_video = "video only" in line or ("p," in line and "audio only" not in line)
                is_audio = "audio only" in line
                
                formats.append({
                    'code': code,
                    'ext': ext,
                    'description': desc,
                    'is_video': is_video,
                    'is_audio': is_audio
                })
            except:
                continue
        return formats 

    def _check_yt_dlp_available(self):
        """检查 yt-dlp 是否可用"""
        try:
            process = QProcess()
            process.setProcessEnvironment(self.env)
            process.start(str(self.ytdlp_path), ["--version"])
            process.waitForFinished()
            success = process.exitCode() == 0
            if not success:
                self.config.log(f"yt-dlp 检查失败，退出码: {process.exitCode()}", logging.ERROR)
                self.config.log(f"错误输出: {process.readAllStandardError().data().decode()}", logging.ERROR)
            return success
        except Exception as e:
            self.config.log(f"检查 yt-dlp 时出错: {str(e)}", logging.ERROR)
            return False

    def _format_progress(self, data):
        """格式化进度信息"""
        # 示例输入: [download]  23.4% of 50.75MiB at 2.52MiB/s ETA 00:15
        try:
            parts = data.split()
            progress = parts[1]  # 23.4%
            size = parts[3]      # 50.75MiB
            speed = parts[5]     # 2.52MiB/s
            eta = parts[7]       # 00:15
            
            return f"下载进度: {progress} (大小: {size}, 速度: {speed}, 剩余时间: {eta})"
        except:
            return data.strip() 

    def _get_firefox_cookies_path(self):
        """查找 Firefox cookies 文件路径"""
        try:
            # 1. 检查标准安装版的所有可能路径
            appdata = os.getenv('APPDATA')
            if appdata:
                standard_path = os.path.join(appdata, 'Mozilla', 'Firefox', 'Profiles')
                if os.path.exists(standard_path):
                    # 检查所有可能的配置文件
                    profile_patterns = [
                        '*.default-release',  # 最常见
                        '*.default',          # 老版本
                        '*.default-*',        # 其他变体
                    ]
                    for pattern in profile_patterns:
                        profiles = glob.glob(os.path.join(standard_path, pattern))
                        for profile in profiles:
                            cookies_path = os.path.join(profile, 'cookies.sqlite')
                            if os.path.exists(cookies_path):
                                self.config.log(f"找到Firefox cookies: {cookies_path}", logging.DEBUG)
                                return cookies_path

            # 2. 检查便携版的可能路径
            portable_patterns = [
                # 标准便携版路径
                os.path.join('Data', 'profile', 'cookies.sqlite'),
                # 某些便携版的变体
                os.path.join('Data', 'Browser', 'profile', 'cookies.sqlite'),
                os.path.join('FirefoxPortable', 'Data', 'profile', 'cookies.sqlite'),
                # 用户自定义配置文件夹
                os.path.join('Data', 'Profiles', '*', 'cookies.sqlite')
            ]

            # 从当前目录开始向上查找5层
            current = os.getcwd()
            for _ in range(5):
                for pattern in portable_patterns:
                    full_pattern = os.path.join(current, pattern)
                    matches = glob.glob(full_pattern)
                    for match in matches:
                        if os.path.exists(match):
                            self.config.log(f"找到便携版Firefox cookies: {match}", logging.DEBUG)
                            return match
                current = os.path.dirname(current)

            # 3. 如果找不到，给出明确的错误提示
            self.config.log("""未找到Firefox cookies文件。可能的原因：
1. Firefox未安装或未运行过
2. 未使用Firefox登录过YouTube
3. 使用了非标准的Firefox安装方式
4. Firefox配置文件位置不标准""", logging.WARNING)
            return None

        except Exception as e:
            self.config.log(f"查找Firefox cookies时出错: {str(e)}", logging.ERROR)
            return None 

    def _process_finished(self, exit_code, exit_status):
        """处理进程完成事件"""
        try:
            process = self.sender()
            task_id = process.property("task_id")
            url = process.property("url")
            
            # 获取输出内容
            output = process.readAllStandardOutput().data().decode('utf-8', errors='ignore')
            error = process.readAllStandardError().data().decode('utf-8', errors='ignore')
            
            # 获取视频标题
            title = process.property("title") or url
            # 如果标题仍然是默认值"未知视频"或明显不合理的标题，尝试从URL中提取信息
            if (title == "未知视频" or (isinstance(title, str) and len(title) <= 3 and (title.replace('.', '').replace('_', '').replace('-', '').isdigit() or (len(title) == 1 and title.isalpha())))) and url:
                # 尝试从URL中提取视频ID作为标题
                try:
                    import urllib.parse as urlparse
                    parsed_url = urlparse.urlparse(url)
                    # 对于YouTube链接
                    if 'youtube.com' in parsed_url.netloc or 'youtu.be' in parsed_url.netloc:
                        if 'v=' in parsed_url.query:
                            video_id = urlparse.parse_qs(parsed_url.query)['v'][0]
                            title = f"YouTube视频_{video_id}"
                        elif 'youtu.be' in parsed_url.netloc:
                            video_id = parsed_url.path.lstrip('/')
                            title = f"YouTube视频_{video_id}"
                    # 对于小红书链接
                    elif 'xiaohongshu.com' in parsed_url.netloc:
                        # 提取视频ID
                        path_parts = parsed_url.path.strip('/').split('/')
                        if path_parts and path_parts[-1]:
                            title = f"小红书视频_{path_parts[-1][:10]}"  # 取前10个字符
                        else:
                            title = "小红书视频"
                    # 对于其他平台，使用域名和路径信息
                    else:
                        path_parts = parsed_url.path.strip('/').split('/')
                        if path_parts and path_parts[-1]:
                            # 限制标题长度
                            domain_part = parsed_url.netloc.split('.')[0]  # 取域名的主要部分
                            path_part = path_parts[-1][:20]  # 限制路径部分长度
                            title = f"{domain_part}_{path_part}"
                        else:
                            title = parsed_url.netloc
                except Exception as e:
                    self.config.log(f"从URL提取标题时出错: {str(e)}", logging.DEBUG)
                    title = url
            
            # 检测平台以提供针对性错误提示
            platform = self.detect_platform(url)
            
            # 检查是否成功
            success = exit_code == 0
            
            # 发送完成信号
            if success:
                self.download_finished.emit(True, "", title, task_id)
            else:
                error_msg = self._format_platform_error(error, platform, url, exit_code)
                self.download_finished.emit(False, error_msg, title, task_id)
            
            # 从进程列表中移除
            if process in self.processes:
                self.processes.remove(process)
            
        except Exception as e:
            self.config.log(f"处理进程完成时出错: {str(e)}", logging.ERROR)
            # 确保在出错时也发送失败信号
            try:
                process = self.sender()
                task_id = process.property("task_id")
                self.download_finished.emit(False, str(e), "未知视频", task_id)
            except Exception:
                pass
    
    def _format_platform_error(self, error, platform, url, exit_code):
        """根据平台类型格式化错误信息，提供用户友好的提示"""
        
        # 通用错误模式匹配
        if "No video formats found" in error:
            if platform == 'xiaohongshu':
                return "小红书链接解析失败，可能原因：\n1. 链接已失效或被删除\n2. 内容需要登录查看\n3. 地区限制\n建议：检查链接是否正确，或尝试其他链接"
            elif platform == 'bilibili':
                return "B站视频解析失败，可能原因：\n1. 视频已被删除或设为私密\n2. 需要大会员权限\n3. 地区限制\n建议：检查视频权限设置"
            elif platform == 'douyin':
                return "抖音视频解析失败，可能原因：\n1. 视频已被删除\n2. 账号设为私密\n3. 链接已过期\n建议：确认链接有效性"
            else:
                return "视频格式解析失败，可能链接已失效或平台限制访问"
        
        elif "Unable to extract" in error or "Unsupported URL" in error:
            if platform == 'xiaohongshu':
                # 检查是否为用户主页链接
                if '/user/profile/' in url:
                    return """小红书用户主页批量下载暂不支持。

解决方案：
1. 进入用户主页，点击具体的视频
2. 复制单个视频的链接（形如 xiaohongshu.com/explore/xxxxx）
3. 使用单个视频链接进行下载

提示：当前只支持单个视频下载，不支持批量下载用户所有视频。"""
                else:
                    return "小红书内容提取失败，建议：\n1. 确认链接格式正确\n2. 检查网络连接\n3. 稍后重试"
            else:
                return "内容提取失败，请检查链接是否正确"
        
        elif "HTTP Error 403" in error or "Forbidden" in error:
            return f"{platform.upper()} 平台拒绝访问，可能需要：\n1. 等待一段时间后重试\n2. 更换网络环境\n3. 检查是否需要登录"
        
        elif "HTTP Error 404" in error or "Not Found" in error:
            return "链接不存在或已被删除，请检查URL是否正确"
        
        elif "network" in error.lower() or "connection" in error.lower():
            return "网络连接错误，请检查：\n1. 网络连接状态\n2. 防火墙设置\n3. 稍后重试"
        
        elif "timeout" in error.lower():
            return "请求超时，可能原因：\n1. 网络速度较慢\n2. 服务器响应慢\n建议稍后重试"
        
        # 如果没有匹配的错误模式，返回原始错误信息（简化版）
        else:
            # 提取关键错误信息，过滤掉技术细节
            error_lines = error.strip().split('\n')
            key_error = None
            for line in error_lines:
                if "ERROR:" in line:
                    key_error = line.replace("ERROR:", "").strip()
                    break
            
            if key_error:
                return f"下载失败：{key_error}"
            else:
                return f"下载失败 (退出码: {exit_code})\n建议检查链接或稍后重试"

    def _get_safari_cookies(self):
        """获取Safari浏览器的cookies"""
        try:
            if sys.platform == 'darwin':  # macOS
                cookies_path = os.path.expanduser("~/Library/Containers/com.apple.Safari/Data/Library/Cookies/Cookies.binarycookies")
                if os.path.exists(cookies_path):
                    return cookies_path
            return None
        except Exception as e:
            self.config.log(f"获取Safari cookies时出错: {str(e)}", logging.ERROR)
            return None 