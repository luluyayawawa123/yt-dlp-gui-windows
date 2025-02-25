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
        
    def reset_state(self):
        """重置下载器状态"""
        self.task_count = 0
        # 取消所有正在进行的下载
        self.cancel_download()
        # 清理进程列表
        self.processes.clear()
        
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
            # 检查浏览器是否可用
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
            
            # 处理下载信息
            if '[download]' in text:
                # 处理标题
                if 'Destination:' in text:
                    # 提取文件名并保持原始编码
                    title = text.split('Destination:')[-1].strip()
                    title = os.path.splitext(os.path.basename(title))[0]
                    
                    # 标题长度限制和截断处理
                    max_length = 50  # 设置最大长度
                    if len(title) > max_length:
                        # 保留前后部分，中间用省略号，注意处理多字节字符
                        title = title[:max_length//2-2] + "..." + title[-max_length//2+1:]
                    
                    process.setProperty("title", title)
                    self.output_received.emit(task_id, f"开始下载: {title}")
                    self.title_updated.emit(task_id, title)
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
            
            # 检查是否成功 - 修改判断逻辑
            success = exit_code == 0  # 只要退出码是0就认为成功
            
            # 发送完成信号
            if success:
                self.download_finished.emit(True, "", title, task_id)
            else:
                error_msg = error if error else f"下载失败 (退出码: {exit_code})"
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