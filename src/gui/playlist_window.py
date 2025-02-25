from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                           QPushButton, QLineEdit, QLabel, QMessageBox, QTextEdit, QHBoxLayout, QFileDialog, QComboBox, QCheckBox, QDialog,
                           QStyle, QSizePolicy)
from PyQt6.QtCore import Qt, QProcess, QProcessEnvironment
from PyQt6.QtGui import QTextCursor
from .saved_urls_dialog import SavedURLsDialog
import os
import logging
import re
import requests
from bs4 import BeautifulSoup

class PlaylistWindow(QMainWindow):
    def __init__(self, config, parent=None):
        super().__init__()
        self.config = config
        self.parent_window = parent
        self.process = None
        self.setup_ui()
        
    def setup_ui(self):
        """设置界面"""
        self.setWindowTitle("播放列表/频道下载模式")
        self.setMinimumSize(700, 500)
        self.setMaximumWidth(800)  # 限制最大宽度
        self.resize(700, 500)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)  # 设置边距
        
        # URL输入区域改为组合布局
        url_layout = QHBoxLayout()
        
        # URL输入框左侧添加下拉按钮
        self.url_combo = QComboBox()
        self.url_combo.setEditable(True)
        self.url_combo.setMaximumWidth(600)  # 限制下拉框最大宽度
        self.url_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.url_combo.setPlaceholderText("请输入播放列表或频道URL")
        
        # 加载保存的URL和标题
        saved_items = self.config.config.get('saved_playlists', [])
        for item in saved_items:
            self.url_combo.addItem(f"{item['title']} - {item['url']}", item['url'])
        
        # 添加收藏按钮
        self.save_url_button = QPushButton()
        self.save_url_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.save_url_button.setToolTip("保存当前URL到收藏夹")
        self.save_url_button.clicked.connect(self.save_current_url)
        
        # 添加管理按钮
        self.manage_urls_button = QPushButton()
        self.manage_urls_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.manage_urls_button.setToolTip("管理收藏的URL")
        self.manage_urls_button.clicked.connect(self.manage_saved_urls)
        
        url_layout.addWidget(self.url_combo)
        url_layout.addWidget(self.save_url_button)
        url_layout.addWidget(self.manage_urls_button)
        layout.addLayout(url_layout)
        
        # 下载路径选择区域
        path_layout = QHBoxLayout()
        path_label = QLabel("下载位置:")
        self.path_input = QLineEdit()
        # Windows下使用正确的默认下载路径
        default_downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        self.path_input.setText(os.path.normpath(default_downloads))  # 规范化路径
        self.browse_button = QPushButton("浏览...")
        self.browse_button.clicked.connect(self.browse_directory)
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_button)
        layout.addLayout(path_layout)  # 添加路径选择布局
        
        # 画质选择区域 (独立的布局)
        quality_layout = QHBoxLayout()
        quality_label = QLabel("画质选择:")
        self.quality_combo = QComboBox()
        self.quality_combo.addItems([
            "最高画质",
            "最高画质MP4",
            "仅MP3音频"  # 新增选项
        ])
        self.quality_combo.setCurrentIndex(0)  # 默认选择最佳画质
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality_combo)

        # 添加字幕下载选项
        self.subtitle_checkbox = QCheckBox("下载字幕(.srt格式)")
        self.subtitle_checkbox.setChecked(False)  # 默认不勾选
        self.subtitle_checkbox.setToolTip("下载视频的所有可用字幕并转换为srt格式")
        quality_layout.addWidget(self.subtitle_checkbox)

        quality_layout.addStretch()  # 添加弹性空间
        layout.addLayout(quality_layout)  # 添加画质选择布局
        
        # 断点续传选项
        archive_layout = QHBoxLayout()
        self.archive_checkbox = QCheckBox("跳过曾经下载过的视频")
        self.archive_checkbox.setChecked(True)  # 默认勾选
        archive_layout.addWidget(self.archive_checkbox)
        archive_layout.addStretch()
        layout.addLayout(archive_layout)
        
        # 添加说明文字
        archive_tip = QLabel(
            "说明：勾选此选项后，程序会记住已经下载过的视频，下次下载相同的播放列表时会自动跳过这些视频。\n"
            "适用于订阅更新的播放列表。若取消勾选，软件将尝试重新下载所有视频。\n"
            "下载记录保存在程序目录下的 downloaded_videos_list.txt 文件中，如需清空下载记录可以手动删除该文件"
        )
        archive_tip.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 12px;
                padding: 5px;
                background: #F8F8F8;
                border-radius: 4px;
            }
        """)
        archive_tip.setWordWrap(True)  # 允许文字换行
        layout.addWidget(archive_tip)
        
        # 下载按钮
        self.download_button = QPushButton("开始下载")
        self.download_button.clicked.connect(self.start_download)
        layout.addWidget(self.download_button)
        
        # 返回按钮
        self.back_button = QPushButton("返回普通下载")
        self.back_button.clicked.connect(self.back_to_main)
        layout.addWidget(self.back_button)
        
        # 状态显示区域
        status_layout = QVBoxLayout()  # 垂直布局
        status_layout.setSpacing(1)  # 减小垂直间距
        
        # 统一的标签样式 - 减小行高和内边距
        label_style = """
            QLabel {
                font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "Segoe UI";
                font-size: 12px;
                padding: 1px 0;  /* 减小上下内边距 */
                color: #333333;
                line-height: 1.0;  /* 减小行高 */
                margin: 0px;  /* 移除外边距 */
            }
        """
        
        # 第一行：显示当前文件名
        self.filename_label = QLabel()
        self.filename_label.setStyleSheet(label_style)
        status_layout.addWidget(self.filename_label)
        
        # 第二行：显示当前下载第几个
        self.total_progress_label = QLabel()
        self.total_progress_label.setStyleSheet(label_style)
        status_layout.addWidget(self.total_progress_label)
        
        # 第三行：显示下载进度和速度
        self.status_label = QLabel()
        self.status_label.setStyleSheet(label_style)
        status_layout.addWidget(self.status_label)
        
        layout.addLayout(status_layout)
        
        # 输出显示区域 - 调整行高和内边距
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #33FF33;
                font-family: "Cascadia Code", "JetBrains Mono", "Microsoft YaHei", monospace;
                font-size: 11px;
                line-height: 1.0;  /* 减小行高 */
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 4px;  /* 减小内边距 */
            }
            QTextEdit:focus {
                border: 1px solid #444444;
            }
            /* 自定义滚动条样式 */
            QScrollBar:vertical {
                background: #1E1E1E;
                width: 10px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: #404040;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #505050;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        layout.addWidget(self.output_text)
        
        # 修改其他标签和按钮的字体样式
        self.setStyleSheet("""
            QLabel {
                font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "Segoe UI";
                color: #333333;
            }
            QPushButton {
                font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "Segoe UI";
            }
            QComboBox {
                font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "Segoe UI";
            }
            QCheckBox {
                font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "Segoe UI";
            }
        """)
        
    def browse_directory(self):
        """选择下载目录"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择下载目录",
            self.path_input.text(),
            QFileDialog.Option.ShowDirsOnly
        )
        if directory:
            self.path_input.setText(directory)
    
    def start_download(self):
        """开始下载播放列表"""
        url = self.url_combo.currentText().strip()
        # 如果是完整格式(标题 - URL)，提取URL部分
        if " - http" in url:
            url = url.split(" - ")[-1]
        
        if not url:
            QMessageBox.warning(self, "错误", "请输入播放列表或频道URL")
            return
            
        try:
            # 获取下载路径并规范化
            output_path = os.path.normpath(self.path_input.text())
            if not output_path:
                QMessageBox.warning(self, "错误", "请选择下载位置")
                return
            
            # 确保下载目录存在
            os.makedirs(output_path, exist_ok=True)
            
            # 设置下载记录文件路径 (在项目根目录)
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            archive_file = os.path.normpath(os.path.join(root_dir, "downloaded_videos_list.txt"))
            
            # 创建进程
            self.process = QProcess()
            
            # 设置环境变量，强制使用 UTF-8
            env = QProcess.systemEnvironment()
            env.append("PYTHONIOENCODING=utf-8")
            env.append("PYTHONUTF8=1")
            env.append("LANG=zh_CN.UTF-8")  # 添加语言环境设置
            
            # 创建 QProcessEnvironment
            process_env = QProcessEnvironment()
            for env_str in env:
                if '=' in env_str:
                    key, value = env_str.split('=', 1)
                    process_env.insert(key, value)
            self.process.setProcessEnvironment(process_env)
            
            self.process.readyReadStandardOutput.connect(self.handle_output)
            self.process.readyReadStandardError.connect(self.handle_error)
            self.process.finished.connect(self.download_finished)
            
            # 构建命令
            program = os.path.normpath(os.path.join(root_dir, "bin", "yt-dlp.exe"))
            output_template = os.path.normpath(os.path.join(output_path, "%(title)s.%(ext)s"))
            
            # 根据画质选择设置下载参数
            quality_index = self.quality_combo.currentIndex()
            format_option = ('bv*+ba' if quality_index == 0 else 
                            'bv[ext=mp4]+ba[ext=m4a]' if quality_index == 1 else 
                            'ba/b')  # 选择最佳音频
            
            args = [
                url,
                "--no-restrict-filenames",  # 允许文件名包含特殊字符
                "--encoding", "utf-8",      # 强制使用 UTF-8 编码
                "-f", format_option,        # 使用选择的画质/格式
            ]
            
            # 如果勾选了字幕下载，添加字幕相关参数
            if self.subtitle_checkbox.isChecked():
                args.extend([
                    "--write-subs",      # 下载字幕
                    "--sub-langs", "all", # 下载所有语言的字幕  
                    "--convert-subs", "srt" # 转换为 srt 格式
                ])
            
            # 根据复选框状态决定是否使用断点续传
            if self.archive_checkbox.isChecked():
                args.extend(["--download-archive", archive_file])
            
            # 添加其他参数
            args.extend([
                "--cookies-from-browser", "firefox",
                "--verbose",
                "-o", output_template
            ])
            
            # 如果选择了 MP3 格式，添加音频提取和转换参数
            if quality_index == 2:  # MP3 选项
                args.extend([
                    "-x",                      # 提取音频
                    "--audio-format", "mp3",   # 指定输出格式为 mp3
                    "--audio-quality", "320",  # 设置比特率 320kbps
                    "--postprocessor-args", "-codec:a libmp3lame"  # 使用 LAME 编码器
                ])
            
            logging.debug(f"启动下载进程: {program}")
            logging.debug(f"下载参数: {args}")
            logging.debug(f"下载目录: {output_path}")
            logging.debug(f"下载记录文件: {archive_file}")
            
            # 开始下载
            self.process.start(program, args)
            self.download_button.setEnabled(False)
            self.status_label.setText("下载中...")
            logging.info(f"开始下载播放列表: {url}")
            
        except Exception as e:
            logging.error(f"下载出错: {str(e)}", exc_info=True)
            self.status_label.setText(f"下载出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"下载失败：{str(e)}")
    
    def handle_output(self):
        """处理输出"""
        try:
            data = self.process.readAllStandardOutput().data()
            try:
                text = data.decode('utf-8')
            except UnicodeDecodeError:
                text = data.decode('utf-8', errors='replace')
            
            # 记录调试信息
            logging.debug(f"Raw output: {text}")
            
            # 处理输出文本
            self.output_text.append(text)
            self.output_text.moveCursor(QTextCursor.MoveOperation.End)
            
            # 更新进度信息
            if '[download]' in text:
                # 检查是否包含文件名信息 - 使用更严格的匹配
                if '[download] Destination: ' in text:
                    # 只处理真正的目标文件名行
                    lines = text.split('\n')
                    for line in lines:
                        if '[download] Destination: ' in line:
                            # 确保这是一个视频文件
                            filename = line.split('[download] Destination: ')[-1].strip()
                            if any(filename.endswith(ext) for ext in ['.mp4', '.webm', '.mkv']):
                                self.filename_label.setText(f"正在下载: {filename}")
                                break
                # 处理播放列表进度信息
                elif 'Downloading item' in text:
                    match = re.search(r'\[download\] Downloading item (\d+) of (\d+)', text)
                    if match:
                        current, total = match.groups()
                        self.total_progress_label.setText(f"正在下载第 {current} 个视频，共 {total} 个")
                # 处理单个视频的下载进度
                elif '%' in text and 'of' in text:
                    try:
                        parts = text.split()
                        percent = parts[1]  # 30.3%
                        size = parts[3]     # 95.44MiB
                        
                        # 提取速度信息
                        speed = "0 B/s"  # 默认值
                        for i, part in enumerate(parts):
                            if part == "at" and i + 1 < len(parts):
                                next_part = parts[i + 1]
                                if next_part.endswith(('B/s', 'iB/s')):  # 确保是速度而不是时间
                                    speed = next_part
                                    break
                        
                        # 更新状态显示
                        progress_text = f"单个视频下载进度: {percent}  大小: {size}  速度: {speed}"
                        self.status_label.setText(progress_text)
                    except (IndexError, ValueError) as e:
                        logging.error(f"解析进度信息出错: {str(e)}")
                    
        except Exception as e:
            logging.error(f"处理输出时出错: {str(e)}", exc_info=True)
    
    def handle_error(self):
        """处理错误输出"""
        try:
            data = self.process.readAllStandardError().data().decode('utf-8', errors='ignore')
            # 错误信息记录到日志
            logging.error(f"下载错误: {data}")
            
            # 对用户显示更友好的错误信息
            if "Unable to download" in data:
                self.output_text.append("⚠️ 无法下载此视频，已跳过")
            elif "Video unavailable" in data:
                self.output_text.append("⚠️ 视频不可用，已跳过")
            # 其他错误信息不显示给用户
            
            self.output_text.moveCursor(QTextCursor.MoveOperation.End)
        except Exception as e:
            # 错误只记录到日志，不显示给用户
            logging.error(f"处理错误输出时出错: {str(e)}", exc_info=True)
    
    def download_finished(self, exit_code, exit_status):
        """下载完成处理"""
        logging.info(f"下载进程结束 - 退出码: {exit_code}, 状态: {exit_status}")
        self.download_button.setEnabled(True)
        if exit_code == 0:
            self.status_label.setText("下载完成")
            logging.info("下载成功完成")
        else:
            self.status_label.setText(f"下载失败 (退出码: {exit_code})")
            logging.error(f"下载失败 - 退出码: {exit_code}")
    
    def back_to_main(self):
        """返回主窗口"""
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            reply = QMessageBox.question(
                self,
                "确认返回",
                "下载正在进行中，确定要返回吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
            self.process.kill()
        
        # 直接显示主窗口并关闭当前窗口，不触发closeEvent
        self.parent_window.show()
        self.hide()  # 改用hide而不是close
    
    def closeEvent(self, event):
        """关闭窗口事件"""
        if self.process and self.process.state() == QProcess.ProcessState.Running:
            reply = QMessageBox.question(
                self,
                "确认关闭",
                "下载正在进行中，确定要关闭吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            
            self.process.kill()
        
        # 如果用户确认关闭或没有正在进行的下载，则关闭窗口
        if self.parent_window:
            self.parent_window.show()
        event.accept()

    def save_current_url(self):
        """保存当前URL到收藏夹"""
        current_url = self.url_combo.currentText().strip()
        if not current_url:
            return
        
        # 如果输入的是完整格式(标题 - URL)，提取URL部分
        if " - http" in current_url:
            current_url = current_url.split(" - ")[-1]
        
        saved_items = self.config.config.get('saved_playlists', [])
        # 检查URL是否已保存
        if any(item['url'] == current_url for item in saved_items):
            QMessageBox.information(self, "提示", "此URL已经保存在收藏夹中")
            return
        
        # 检查是否是特殊的系统播放列表
        if "list=LL" in current_url:
            title = "我喜欢的视频"
            self._save_with_title(current_url, title)
            return
        elif "list=WL" in current_url:
            title = "稍后观看"
            self._save_with_title(current_url, title)
            return
        
        try:
            # 显示正在获取标题的提示
            self.status_label.setText("正在获取播放列表信息，请耐心等待...")
            self.save_url_button.setEnabled(False)
            self.url_combo.setEnabled(False)
            
            # 设置请求头和超时
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            # 发起请求获取标题
            response = requests.get(current_url, timeout=10, headers=headers)
            response.raise_for_status()
            
            # 解析页面获取标题
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.string
            
            if not title:
                raise ValueError("无法获取标题")
            
            title = title.strip()
            if "- YouTube" in title:
                title = title.replace("- YouTube", "").strip()
            
            # 保存到配置
            saved_items.append({
                'url': current_url,
                'title': title
            })
            self.config.config['saved_playlists'] = saved_items
            self.config.save_config()
            
            # 更新下拉列表
            self.url_combo.addItem(f"{title} - {current_url}")
            QMessageBox.information(self, "成功", "播放列表已保存到收藏夹")
            
        except requests.Timeout:
            # 超时处理
            reply = QMessageBox.question(
                self,
                "获取标题超时",
                """获取播放列表标题超时，是否重试？

点击"是"重新尝试获取，点击"否"使用URL作为标题保存。""",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.save_current_url()  # 重试
                return
            else:
                self._save_with_title(current_url, title)
                
        except requests.RequestException as e:
            # 网络请求错误
            QMessageBox.warning(
                self,
                "网络错误",
                f"无法连接到YouTube，请检查网络连接。\n错误信息：{str(e)}\n\n"
                "已使用URL作为标题保存。"
            )
            self._save_with_title(current_url, title)
            
        except Exception as e:
            # 其他错误
            QMessageBox.warning(
                self,
                "错误",
                f"获取标题失败：{str(e)}\n\n"
                "可能的原因：\n"
                "1. 网络连接不稳定\n"
                "2. URL格式不正确\n"
                "3. 播放列表不存在或已被删除\n"
                "4. 需要登录才能访问此内容\n\n"
                "已使用URL作为标题保存。"
            )
            self._save_with_title(current_url, title)
            
        finally:
            # 恢复界面状态
            self.status_label.setText("")
            self.save_url_button.setEnabled(True)
            self.url_combo.setEnabled(True)

    def _save_with_title(self, url, title):
        """使用指定标题保存URL"""
        saved_items = self.config.config.get('saved_playlists', [])
        saved_items.append({
            'url': url,
            'title': title
        })
        self.config.config['saved_playlists'] = saved_items
        self.config.save_config()
        self.url_combo.addItem(f"{title} - {url}")
        QMessageBox.information(self, "成功", "播放列表已保存到收藏夹")

    def manage_saved_urls(self):
        """管理已保存的URL"""
        dialog = SavedURLsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 重新加载URL列表
            self.url_combo.clear()
            saved_items = self.config.config.get('saved_playlists', [])
            for item in saved_items:
                self.url_combo.addItem(f"{item['title']} - {item['url']}", item['url'])

    def on_url_changed(self, text):
        """URL改变时更新保存按钮状态"""
        # 如果URL已经保存，改变保存按钮的图标
        saved_items = self.config.config.get('saved_playlists', [])
        is_saved = text.strip() in [item['url'] for item in saved_items]
        self.save_url_button.setIcon(
            self.style().standardIcon(
                QStyle.StandardPixmap.SP_DialogSaveButton if not is_saved
                else QStyle.StandardPixmap.SP_DialogApplyButton
            )
        )

    def _is_valid_youtube_url(self, url):
        """验证是否是有效的YouTube URL"""
        url = url.lower()  # 转换为小写进行比较
        return ('youtube.com' in url or 'youtu.be' in url) and url.startswith('http') 