from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLineEdit, QPushButton, 
                            QTextEdit, QFileDialog, QLabel, QComboBox,
                            QProgressBar, QSizePolicy, QFrame, QMessageBox,
                            QScrollArea, QMenu, QGroupBox, QCheckBox)
from PyQt6.QtCore import Qt, QProcess, QEvent
from PyQt6.QtGui import QTextCursor, QFont
import os
import datetime
from core.downloader import Downloader
from core.config import Config
import sys
from PyQt6.QtWidgets import QApplication
import re
import logging

class MainWindow(QMainWindow):
    # 定义一个更优雅的字体方案
    MONOSPACE_FONT = QFont("Microsoft YaHei, PingFang SC, Noto Sans CJK SC, Segoe UI", 10)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YT-DLP GUI for Windows")
        
        # 设置最小窗口大小
        self.setMinimumSize(700, 800)  # 修改最小宽度为700
        
        # 设置初始窗口大小
        self.resize(700, 800)
        
        # 获取屏幕几何信息并居中显示
        screen = QApplication.primaryScreen().geometry()
        # 计算窗口位置，确保完全居中且不会超出屏幕
        x = max(0, (screen.width() - 700) // 2)
        y = max(0, (screen.height() - 800) // 2 - 40)  # 向上移动40像素
        self.move(x, y)
        
        # 创建主窗口部件
        self.main_container = QWidget()
        self.setCentralWidget(self.main_container)
        
        # 添加配置和下载器
        self.config = Config()
        self.downloader = Downloader()
        
        # 连接下载器信号
        self.downloader.output_received.connect(self.update_output)
        self.downloader.download_finished.connect(self.download_finished)
        self.downloader.title_updated.connect(self.update_task_title)
        
        # 初始化变量
        self.total_urls = 0
        self.completed_urls = 0
        self.download_tasks = {}
        
        # 初始化 UI
        self.init_ui()
        
        # 从配置加载上次的下载路径
        if 'last_download_path' in self.config.config:
            self.path_input.setText(self.config.config['last_download_path'])
        else:
            # 如果没有保存的路径，使用默认下载目录
            self.path_input.setText(os.path.expanduser("~/Downloads"))
        
        # 检查完全磁盘访问权限
        self.check_full_disk_access()
        
    def init_ui(self):
        """初始化用户界面"""
        # 创建主布局
        layout = QVBoxLayout(self.main_container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # 设置窗口整体样式 - YouTube风格
        self.setStyleSheet("""
            QMainWindow {
                background: #FFFFFF;
            }
            QLabel {
                color: #0F0F0F;
                font-size: 13px;
            }
            QTextEdit, QLineEdit {
                border: 1px solid #E5E5E5;
                border-radius: 6px;
                padding: 8px;
                background: #FFFFFF;
                color: #0F0F0F;
                selection-background-color: #F1F1F1;
            }
            QTextEdit:focus, QLineEdit:focus {
                border: 1px solid #CC0000;
            }
            QPushButton {
                background: #F1F1F1;
                color: #0F0F0F;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #E5E5E5;
            }
            QPushButton:pressed {
                background: #A00000;
            }
            QPushButton[text="取消下载"] {
                background: #909090;
            }
            QPushButton[text="取消下载"]:hover {
                background: #808080;
            }
            QComboBox {
                border: 1px solid #E5E5E5;
                border-radius: 6px;
                padding: 8px;
                background: #FFFFFF;
                color: #0F0F0F;
            }
            QComboBox:focus {
                border: 1px solid #CC0000;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border: none;
            }
            QScrollArea {
                border: 1px solid #E5E5E5;
                border-radius: 6px;
                background: #FFFFFF;
            }
            QProgressBar {
                border: none;
                background: #F1F1F1;
                border-radius: 3px;
                text-align: center;
                height: 6px;
            }
            QProgressBar::chunk {
                background: #CC0000;
                border-radius: 3px;
            }
        """)

        # URL输入区域
        url_layout = QVBoxLayout()
        url_label = QLabel("视频URLs (每行一个):")
        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText("在此输入一个或多个YouTube视频链接，每行一个")
        self.url_input.setMinimumHeight(100)
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        layout.addLayout(url_layout)
        
        # 下载路径选择区域
        path_layout = QHBoxLayout()
        path_label = QLabel("下载位置:")
        self.path_input = QLineEdit()
        self.browse_button = QPushButton("浏览...")  # 先创建按钮
        self.browse_button.clicked.connect(self.browse_directory)
        
        # 现在可以设置浏览按钮样式了
        self.browse_button.setStyleSheet("""
            QPushButton {
                background: #F1F1F1;
                color: #0F0F0F;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: #E5E5E5;
            }
        """)
        
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_button)
        layout.addLayout(path_layout)
        
        # 添加浏览器选择
        browser_layout = QHBoxLayout()
        browser_label = QLabel("使用浏览器 Cookies:")
        self.browser_combo = QComboBox()
        # Windows 支持的浏览器
        browsers = [
            ('Firefox 火狐浏览器', 'firefox'),
            ('Chrome 谷歌浏览器 (不支持)', 'chrome'),  # 修改描述更简洁
        ]
        for browser_name, browser_id in browsers:
            self.browser_combo.addItem(browser_name, browser_id)
        
        browser_layout.addWidget(browser_label)
        browser_layout.addWidget(self.browser_combo)
        layout.addLayout(browser_layout)
        
        # 画质选择和播放列表下载按钮放在同一行
        quality_layout = QHBoxLayout()
        quality_label = QLabel("画质选择:")
        self.quality_combo = QComboBox()
        self.quality_combo.addItems([
            "最高画质",
            "最高画质MP4",
            "仅MP3音频"
        ])
        self.quality_combo.setCurrentIndex(0)  # 默认选择最佳画质

        # 添加字幕下载选项
        self.subtitle_checkbox = QCheckBox("下载字幕（.srt格式）")
        self.subtitle_checkbox.setChecked(False)  # 默认不勾选
        self.subtitle_checkbox.setToolTip("下载视频的所有可用字幕(srt格式)")

        # 添加播放列表下载按钮
        self.playlist_button = QPushButton("切换到播放列表/频道下载模式")
        self.playlist_button.clicked.connect(self.open_playlist_window)
        
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality_combo)
        quality_layout.addWidget(self.subtitle_checkbox)
        quality_layout.addStretch()  # 添加弹性空间
        quality_layout.addWidget(self.playlist_button)  # 放在最右边
        layout.addLayout(quality_layout)
        
        # 添加浏览器提示（简化并优化样式）
        browser_tip = QLabel(
            "提示：YouTube 现在要求登录才能观看视频，请使用 Firefox 火狐浏览器（安装版，不要使用便携版）。\n"
            "使用前请确保已在 Firefox 中登录 YouTube/Google 账号。"
        )
        browser_tip.setStyleSheet("""
            color: #606060;
            font-size: 12px;
            padding: 8px;
            background: #F8F8F8;
            border-radius: 6px;
            margin: 8px 0;
        """)
        browser_tip.setWordWrap(True)
        layout.addWidget(browser_tip)
        
        # 控制按钮区域
        button_layout = QHBoxLayout()
        self.download_button = QPushButton("开始下载")
        self.download_button.clicked.connect(self.start_download)
        button_layout.addWidget(self.download_button)
        layout.addLayout(button_layout)
        
        # 添加下载任务显示区域
        downloads_label = QLabel("下载任务:")
        layout.addWidget(downloads_label)
        
        # 创建下载任务容器
        self.downloads_area = QWidget()
        self.tasks_layout = QVBoxLayout(self.downloads_area)
        self.tasks_layout.setSpacing(0)
        self.tasks_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.downloads_area)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(260)
        scroll_area.setMaximumHeight(400)
        layout.addWidget(scroll_area)
        
        # 修改下载按钮样式，使用与墨绿色协调的灰色系
        self.download_button.setStyleSheet("""
            QPushButton {
                background: #CC0000;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 32px;
                font-size: 14px;
                font-weight: 500;
                min-width: 140px;
            }
            QPushButton:hover {
                background: #B00000;
            }
            QPushButton:pressed {
                background: #A00000;
            }
            QPushButton[text="取消下载"] {
                background: #909090;
            }
            QPushButton[text="取消下载"]:hover {
                background: #808080;
            }
        """)
        
        # 在所有现有控件之后,添加一个分隔空间
        layout.addStretch()
        
    def update_history_display(self):
        """更新下载历史显示"""
        # 清理旧的历史显示
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 获取最近的下载历史（最多显示10条）
        history = self.config.config.get('download_history', [])[-10:]
        
        for entry in reversed(history):
            item = QWidget()
            layout = QHBoxLayout(item)
            layout.setContentsMargins(5, 2, 5, 2)
            
            title = entry['title']
            path = entry['path']
            time = datetime.datetime.fromisoformat(entry['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            status = entry.get('status', '完成')  # 添加状态信息
            
            # 设置小字体
            font = self.font()
            font.setPointSize(11)  # 设置字体大小
            
            title_label = QLabel(f"{title}")
            title_label.setFont(font)
            
            status_label = QLabel(f"[{status}]")
            status_label.setFont(font)
            status_label.setFixedWidth(60)  # 只固定状态标签宽度
            
            time_label = QLabel(time)
            time_label.setFont(font)
            time_label.setFixedWidth(140)  # 固定时间标签宽度
            time_label.setAlignment(Qt.AlignmentFlag.AlignRight)  # 时间右对齐
            
            # 设置状态标签的颜色
            if status == '完成':
                status_label.setStyleSheet("color: #32CD32;")
            elif status == '失败':
                status_label.setStyleSheet("color: #FF0000;")
            elif status == '已存在':
                status_label.setStyleSheet("color: #FFA500;")
            
            layout.addWidget(title_label)
            layout.addWidget(status_label)
            layout.addWidget(time_label)
            
            self.history_layout.addWidget(item)
        
        self.history_layout.addStretch()

    def browse_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "选择下载目录",
            self.path_input.text(),
            QFileDialog.Option.ShowDirsOnly
        )
        if directory:
            self.path_input.setText(directory)
            
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
        """验证下载目录是否有效且可写"""
        try:
            if not os.path.exists(path):
                os.makedirs(path)
            # 测试是否可写
            test_file = os.path.join(path, '.write_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return True
        except:
            return False

    def create_download_task_widget(self, url, task_id):
        """创建下载任务控件"""
        # 创建任务容器
        task_widget = QWidget()
        task_widget.setFixedHeight(80)  # 从85改为80，稍微压缩一下每个任务的高度
        layout = QVBoxLayout(task_widget)
        layout.setContentsMargins(10, 3, 10, 3)
        layout.setSpacing(2)
        
        # 创建内容区域
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(1)  # 减小元素间距
        content_layout.setContentsMargins(0, 2, 0, 2)
        
        # 视频标题
        title_label = QLabel("正在获取视频信息...")
        title_label.setStyleSheet("""
            font-weight: bold; 
            color: #333;
            font-size: 13px;
            line-height: 1.1;  /* 减小行高 */
        """)
        title_label.setWordWrap(True)
        title_label.setFixedHeight(32)  # 设置标题固定高度，约两行文字
        content_layout.addWidget(title_label)
        
        # URL
        url_label = QLabel(f"URL: {url}")
        url_label.setStyleSheet("""
            color: #666; 
            font-size: 10px;
            line-height: 1;  /* 减小行高 */
        """)
        url_label.setWordWrap(True)
        url_label.setFixedHeight(15)  # 设置URL固定高度
        content_layout.addWidget(url_label)
        
        # URL 标签后面添加进度条
        progress_bar = QProgressBar()
        progress_bar.setMaximum(100)
        progress_bar.setValue(0)
        progress_bar.setFixedHeight(2)  # 设置进度条高度为2像素
        progress_bar.setTextVisible(False)  # 不显示进度文字
        progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background: #f0f0f0;
                margin: 0;
                padding: 0;
            }
            QProgressBar::chunk {
                background: #2196F3;
            }
        """)
        content_layout.addWidget(progress_bar)
        
        # 状态行（水平布局）
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(0, 2, 0, 2)
        
        # 修改进度标签的字体和样式
        progress_label = QLabel()
        progress_label.setFont(self.MONOSPACE_FONT)
        progress_label.setStyleSheet("""
            color: #444;
            line-height: 1.1;
            font-size: 11px;  /* 添加字体大小控制 */
            padding: 2px 0;   /* 添加一些内边距 */
        """)
        status_layout.addWidget(progress_label)
        
        status_layout.addStretch()
        
        # 打开文件夹按钮（初始隐藏）
        open_button = QPushButton("📂 打开文件夹")
        open_button.setCursor(Qt.CursorShape.PointingHandCursor)
        open_button.setStyleSheet("""
            QPushButton {
                border: none;
                color: #2196F3;
                font-size: 11px;
                padding: 2px 8px;
                background: transparent;
            }
            QPushButton:hover {
                color: #1976D2;
                text-decoration: underline;
            }
        """)
        open_button.hide()
        status_layout.addWidget(open_button)
        
        # 状态标签
        status_label = QLabel("⏳ 准备中")
        status_label.setStyleSheet("""
            color: #666;
            font-size: 11px;
            line-height: 1.1;
            padding: 2px 8px;
        """)
        status_layout.addWidget(status_label)
        
        content_layout.addLayout(status_layout)
        
        # 添加内容区域到主布局
        layout.addWidget(content_widget)
        
        # 添加分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("""
            background-color: #ddd;
            margin: 0;
            padding: 0;
        """)
        separator.setFixedHeight(1)  # 设置分隔线高度为1像素
        layout.addWidget(separator)
        
        # 保存引用
        task_widget.title_label = title_label
        task_widget.progress_label = progress_label
        task_widget.status_label = status_label
        task_widget.open_button = open_button
        task_widget.video_path = None  # 用于保存视频路径
        task_widget.progress_bar = progress_bar
        
        # 将新任务添加到顶部
        self.tasks_layout.insertWidget(0, task_widget)
        self.download_tasks[task_id] = task_widget
        
        return task_widget
        
    def get_format_options(self):
        """获取格式设置选项"""
        return {
            'mode': 'best',  # 默认使用最佳质量
            'format': None
        }
        
    def start_download(self):
        """开始下载"""
        if self.download_button.text() == "取消下载":
            self.cancel_download()
            return
        
        # 获取输入的URL
        urls = self.url_input.toPlainText().strip().split('\n')
        if not urls or not urls[0]:
            QMessageBox.warning(self, "错误", "请输入要下载的视频URL")
            return
        
        # 获取下载路径
        output_path = self.path_input.text()
        if not output_path:
            QMessageBox.warning(self, "错误", "请选择下载位置")
            return
        
        # 创建输出目录
        try:
            os.makedirs(output_path, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"创建下载目录失败：{str(e)}")
            return
            
        # 获取选择的浏览器
        browser = self.browser_combo.currentData()
        
        # 检查浏览器是否已安装
        try:
            if not self.downloader._check_browser_available(browser):
                browser_names = {
                    'firefox': 'Firefox 火狐浏览器',
                    'chrome': 'Chrome 谷歌浏览器',
                    'opera': 'Opera 浏览器',
                    'brave': 'Brave 浏览器'
                }
                browser_name = browser_names.get(browser, browser)
                QMessageBox.critical(self, "错误", 
                    f"未检测到 {browser_name}！\n\n"
                    "请先安装浏览器或选择其他已安装的浏览器。\n\n"
                    "推荐使用 Firefox 火狐浏览器（必须使用安装版，不要使用便携版），\n"
                    "它对 YouTube 视频下载支持最好。"
                )
                return
        except Exception as e:
            QMessageBox.critical(self, "错误", f"检查浏览器时出错：{str(e)}")
            return
            
        # 获取画质选择
        quality_index = self.quality_combo.currentIndex()
        format_options = {
            'format': 'bv*+ba' if quality_index == 0 else 
                     'bv[ext=mp4]+ba[ext=m4a]' if quality_index == 1 else 
                     'ba/b'  # 选择最佳音频
        }

        # 如果是 MP3 选项，添加音频格式参数
        if quality_index == 2:
            format_options.update({
                'audioformat': 'mp3',      # 这个参数会触发 downloader.py 中的 MP3 转换逻辑
                'audioquality': '320'      # 设置比特率
            })

        # 如果勾选了下载字幕，添加字幕相关参数
        if self.subtitle_checkbox.isChecked():
            format_options.update({
                'writesubtitles': True,
                'subtitlesformat': 'srt'
            })
        
        # 设置总任务数
        self.total_urls = len([url for url in urls if url.strip()])
        self.completed_urls = 0  # 重置完成计数
        
        # 禁用控件
        self._disable_controls()
        
        # 设置环境变量，强制使用 UTF-8
        env = QProcess.systemEnvironment()
        env.append("PYTHONIOENCODING=utf-8")
        env.append("PYTHONUTF8=1")
        env.append("LANG=zh_CN.UTF-8")  # 添加语言环境设置
        self.downloader.set_environment(env)
        
        # 开始下载
        success = True
        for url in urls:
            url = url.strip()
            if url:
                try:
                    # 创建下载进度显示
                    task_id = f"Task-{len(self.download_tasks)+1}"
                    task_widget = self.create_download_task_widget(url, task_id)
                    
                    if not self.downloader.start_download(url, output_path, format_options, browser):
                        success = False
                        break
                except Exception as e:
                    success = False
                    error_msg = str(e)
                    QMessageBox.critical(self, "下载失败", 
                        f"启动下载失败：\n\n{error_msg}\n\n"
                        "可能的解决方法：\n"
                        "1. 确保选择的浏览器已正确安装\n"
                        "2. 确保已在浏览器中登录 YouTube\n"
                        "3. 尝试使用其他浏览器\n"
                        "4. 检查网络连接"
                    )
                    self._enable_controls()
                    return False
        
        if not success:
            self._enable_controls()
        
    def cancel_download(self):
        """取消下载"""
        try:
            # 取消所有正在进行的下载
            self.downloader.cancel_download()
            
            # 更新所有未完成任务的状态
            for task_widget in self.download_tasks.values():
                if task_widget.status_label.text() in ["⏬ 下载中", "🔄 处理中", "⏳ 准备中"]:
                    task_widget.status_label.setText("已取消")
                    task_widget.status_label.setStyleSheet("color: #FF9800;")
                    task_widget.progress_label.setText("下载已取消")
                    task_widget.progress_bar.setValue(0)
            
            # 重置界面
            self._enable_controls()
            self.url_input.clear()
            
            # 重置下载计数
            self.completed_urls = 0
            self.total_urls = 0
            
        except Exception as e:  # 修复这里的语法错误
            QMessageBox.warning(self, "取消失败", f"取消下载时出错：{str(e)}")
        
    def update_output(self, task_id, message):
        """更新下载进度显示"""
        if task_id in self.download_tasks:
            task_widget = self.download_tasks[task_id]
            
            if "开始下载" in message:
                # 简化标题处理
                title = message.replace("开始下载: ", "").strip()
                task_widget.title_label.setText(title)
                task_widget.video_path = os.path.join(self.path_input.text(), title)
                
                # 更新状态
                task_widget.status_label.setText("⏬ 下载中")
                task_widget.status_label.setStyleSheet("color: #2196F3;")
                task_widget.progress_label.setText("准备下载...")
                task_widget.progress_bar.setValue(0)
                
                # 设置打开文件夹按钮点击事件
                task_widget.open_button.clicked.connect(
                    lambda: self.open_download_folder(self.path_input.text())
                )
            elif "下载进度" in message:
                # 解析进度信息
                try:
                    # 示例: [download]  23.4% of 50.75MiB at 2.52MiB/s ETA 00:15
                    percent = float(message.split('%')[0].split()[-1])
                    task_widget.progress_bar.setValue(int(percent))
                except Exception:
                    pass
                task_widget.progress_label.setText(message)
                task_widget.status_label.setText("⏬ 下载中")
                task_widget.status_label.setStyleSheet("color: #2196F3;")
            elif "正在合并" in message:
                task_widget.progress_bar.setValue(100)
                task_widget.progress_bar.setStyleSheet("""
                    QProgressBar {
                        border: none;
                        background: #f0f0f0;
                    }
                    QProgressBar::chunk {
                        background: #FF9800;
                    }
                """)
                task_widget.progress_label.setText(message)
                task_widget.status_label.setText("🔄 处理中")
                task_widget.status_label.setStyleSheet("color: #FF9800;")
            elif "下载完成" in message or "文件已存在" in message:
                task_widget.progress_bar.setValue(100)
                task_widget.progress_bar.setStyleSheet("""
                    QProgressBar {
                        border: none;
                        background: #f0f0f0;
                    }
                    QProgressBar::chunk {
                        background: #4CAF50;
                    }
                """)
                task_widget.progress_label.setText(message)
                task_widget.status_label.setText("✓ 已完成")
                task_widget.status_label.setStyleSheet("color: #4CAF50;")

    def download_finished(self, success, message, title, task_id):
        """处理下载完成事件"""
        if task_id not in self.download_tasks:
            return
            
        task_widget = self.download_tasks[task_id]
        
        if success:
            task_widget.status_label.setText("✓ 已完成")
            task_widget.status_label.setStyleSheet("color: #4CAF50")
            task_widget.open_button.show()  # 确保显示打开文件夹按钮
            task_widget.open_button.setStyleSheet("""
                QPushButton {
                    border: none;
                    color: #2196F3;
                    font-size: 11px;
                    padding: 2px 8px;
                    background: transparent;
                }
                QPushButton:hover {
                    color: #1976D2;
                    text-decoration: underline;
                }
            """)
        else:
            task_widget.status_label.setText("❌ 下载失败")
            task_widget.status_label.setStyleSheet("color: #F44336")
            task_widget.progress_label.setText("下载失败")
            task_widget.progress_label.setStyleSheet("color: #F44336")
            task_widget.open_button.hide()  # 失败时隐藏按钮
        
        self.completed_urls += 1
        
        # 检查是否所有下载都完成了
        if self.completed_urls >= self.total_urls:
            # 重置界面
            self._enable_controls()
            self.url_input.clear()
            # 重置下载计数
            self.completed_urls = 0
            self.total_urls = 0
        
    def _enable_controls(self):
        """重新启用控件"""
        try:
            self.download_button.clicked.disconnect()
        except Exception:  # 修复这里的语法错误
            pass
        
        self.download_button.clicked.connect(self.start_download)
        self.download_button.setText("开始下载")
        
        # 重新启用所有控件
        self.url_input.setEnabled(True)
        self.path_input.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.browser_combo.setEnabled(True)

    def _disable_controls(self):
        """禁用控件"""
        self.url_input.setEnabled(False)
        self.path_input.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.browser_combo.setEnabled(False)
        self.download_button.setText("取消下载")
        self.download_button.clicked.disconnect()
        self.download_button.clicked.connect(self.cancel_download)

    def clear_download_history(self):
        """清空下载历史"""
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有下载历史记录吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.config.config['download_history'] = []
            self.config.save_config()
            self.update_history_display()

    def show_history_context_menu(self, position):
        """显示历史记录的右键菜单"""
        menu = QMenu(self)
        clear_action = menu.addAction("清空历史记录")
        clear_action.triggered.connect(self.clear_download_history)
        menu.exec(self.history_area.mapToGlobal(position))

    def check_full_disk_access(self):
        """检查完全磁盘访问权限"""
        if sys.platform == 'darwin':
            cookies_path = os.path.expanduser("~/Library/Containers/com.apple.Safari/Data/Library/Cookies/Cookies.binarycookies")
            if os.path.exists(cookies_path):
                return cookies_path
        return None

    def eventFilter(self, obj, event):
        """处理事件过滤器"""
        if isinstance(obj, QWidget) and obj.parent() in self.download_tasks.values():
            task_widget = obj.parent()
            if event.type() == QEvent.Type.MouseButtonPress:  # 鼠标点击
                if (hasattr(task_widget, 'video_path') and 
                    task_widget.video_path and 
                    os.path.exists(task_widget.video_path) and
                    task_widget.status_label.text() in ["✓ 已完成", "✓ 已存在"]):
                    self.open_video(task_widget.video_path)
            elif event.type() == QEvent.Type.Enter:  # 鼠标进入
                if (hasattr(task_widget, 'video_path') and 
                    task_widget.video_path and 
                    os.path.exists(task_widget.video_path) and
                    task_widget.status_label.text() in ["✓ 已完成", "✓ 已存在"]):
                    task_widget.status_label.setText("🎬 打开视频")
                    task_widget.status_label.setStyleSheet("""
                        color: #2196F3;
                        font-size: 11px;
                        line-height: 1.1;
                        padding: 2px 8px;
                    """)
            elif event.type() == QEvent.Type.Leave:  # 鼠标离开
                if task_widget.status_label.text() == "🎬 打开视频":
                    task_widget.status_label.setText("✓ 已完成")
                    task_widget.status_label.setStyleSheet("""
                        color: #4CAF50;
                        font-size: 11px;
                        line-height: 1.1;
                        padding: 2px 8px;
                    """)
        return super().eventFilter(obj, event)

    def open_video(self, path):
        """打开视频文件"""
        # 检查不同可能的文件扩展名
        possible_extensions = ['.mp4', '.mkv', '.webm']
        video_file = None
        
        # 先检查原始路径
        if os.path.exists(path):
            video_file = path
        else:
            # 检查所有可能的扩展名
            for ext in possible_extensions:
                test_path = path + ext
                if os.path.exists(test_path):
                    video_file = test_path
                    break
        
        if video_file:
            try:
                import platform
                if platform.system() == 'Windows':
                    os.startfile(video_file)
                elif platform.system() == 'Darwin':  # macOS
                    import subprocess
                    subprocess.run(['open', video_file])
                else:  # Linux
                    import subprocess
                    subprocess.run(['xdg-open', video_file])
            except Exception as e:
                QMessageBox.warning(self, "打开失败", f"无法打开视频文件：{str(e)}")
        else:
            QMessageBox.warning(self, "文件不存在", 
                "视频文件不存在或已被移动/删除\n"
                f"尝试查找的路径：{path}"
            ) 

    def open_download_folder(self, path):
        """打开下载文件夹"""
        try:
            import platform
            if platform.system() == 'Windows':
                os.startfile(path)
            elif platform.system() == 'Darwin':  # macOS
                import subprocess
                subprocess.run(['open', path])
            else:  # Linux
                import subprocess
                subprocess.run(['xdg-open', path])
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开下载文件夹：{str(e)}") 

    def _check_all_downloads_finished(self):
        """检查是否所有下载都已完成"""
        # 检查是否还有正在进行的下载进程
        if self.downloader.processes:
            return False
        
        # 检查所有任务的状态
        for task_widget in self.download_tasks.values():
            if task_widget.status_label.text() in ["⏬ 下载中", "🔄 处理中", "⏳ 准备中"]:
                return False
        
        # 如果没有正在进行的下载，则重置界面
        try:
            self.download_button.clicked.disconnect()
        except Exception:  # 修复这里的语法错误
            pass
        
        self.download_button.clicked.connect(self.start_download)
        self.download_button.setText("开始下载")
        
        # 重新启用所有控件
        self.url_input.setEnabled(True)
        self.url_input.clear()  # 清空 URL 输入框
        self.path_input.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.browser_combo.setEnabled(True)
        
        # 重置下载计数
        self.completed_urls = 0
        self.total_urls = 0
        
        return True 

    def closeEvent(self, event):
        """处理窗口关闭事件"""
        # 取消所有正在进行的下载
        self.downloader.cancel_download()
        # 等待下载器清理完成
        event.accept() 

    def open_playlist_window(self):
        """打开播放列表下载模式"""
        from gui.playlist_window import PlaylistWindow
        self.playlist_window = PlaylistWindow(self.config, self)  # 传入 self 作为父窗口
        self.playlist_window.show()
        self.hide() 

    def update_task_title(self, task_id, title):
        """更新任务标题"""
        if task_id in self.download_tasks:
            task_widget = self.download_tasks[task_id]
            if title:
                task_widget.title_label.setText(title)
                # 更新工具提示
                task_widget.title_label.setToolTip(title)
    
    def create_download_task(self, url, task_id):
        """创建下载任务"""
        # 创建任务组件
        task_widget = QFrame()
        task_widget.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        task_widget.setStyleSheet("""
            QFrame {
                background: #F8F9FA;
                border: 1px solid #E9ECEF;
                border-radius: 8px;
                margin: 4px;
            }
        """)
        
        # 使用临时标题
        temp_title = f"正在获取标题..."
        title_label = QLabel(temp_title)
        title_label.setStyleSheet("""
            QLabel {
                color: #202124;
                font-size: 13px;
                font-weight: 500;
            }
        """)
        
        # ... 保持其他创建任务的代码不变 ... 