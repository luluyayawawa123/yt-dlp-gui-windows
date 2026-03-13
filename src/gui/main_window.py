from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLineEdit, QPushButton, 
                            QTextEdit, QFileDialog, QLabel, QComboBox,
                            QProgressBar, QSizePolicy, QFrame, QMessageBox,
                            QScrollArea, QMenu, QGroupBox, QCheckBox)
from PyQt6.QtCore import Qt, QProcess, QEvent, pyqtSignal
from PyQt6.QtGui import QTextCursor, QFont, QIcon
import os
import datetime
from core.downloader import Downloader
from core.config import Config
from core.youtube_pot import prewarm_youtube_pot
from gui.log_window import LogWindow
import sys
from PyQt6.QtWidgets import QApplication
import re
import logging
import threading
from pathlib import Path

class MainWindow(QMainWindow):
    youtube_prewarm_finished = pyqtSignal(bool, str)

    # 定义一个更有兼容性的字体方案，优先使用现代系统字体
    SYSTEM_FONT = QFont("Microsoft YaHei UI, PingFang SC, Segoe UI, -apple-system, sans-serif", 10)
    MONOSPACE_FONT = QFont("Consolas, Menlo, Courier, monospace", 10)
    
    # 色彩方案（统一的色彩变量便于管理）
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
    
    def __init__(self):
        super().__init__()
        
        # 获取应用程序实例和版本号
        app = QApplication.instance()
        version = app.applicationVersion()
        self.setWindowTitle(f"YT-DLP GUI for Windows v{version}")
        
        # 设置最小窗口大小
        self.setMinimumSize(700, 600)  # 从640减小到600
        
        # 设置初始窗口大小
        self.resize(700, 600)  # 从640减小到600
        
        # 获取应用程序实例和主屏幕
        app = QApplication.instance()
        
        # 获取屏幕的实际可用区域（考虑任务栏和系统UI）
        screen = QApplication.primaryScreen().availableGeometry()  # 使用可用区域而非总区域
        x = max(0, (screen.width() - 700) // 2 + screen.x())  # 考虑屏幕起始位置
        y = max(0, (screen.height() - 600) // 2 + screen.y())  # 考虑屏幕起始位置
        
        # 确保窗口完全可见（即底部不会超出屏幕）
        if y + 600 > screen.y() + screen.height():
            y = max(0, screen.y() + screen.height() - 600)
        
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
        self.log_windows = {}  # 存储每个任务的日志窗口
        self._pending_download_request = None
        self._prewarm_in_progress = False
        self.youtube_prewarm_finished.connect(self._handle_youtube_prewarm_finished)
        
        # 设置窗口图标
        self.set_window_icon()
        
        # 初始化 UI
        self.init_ui()
        
        # 检查完全磁盘访问权限
        self.check_full_disk_access()
        
    def set_window_icon(self):
        """设置窗口图标"""
        try:
            # 获取图标文件路径
            from pathlib import Path
            icon_paths = [
                Path(__file__).parent.parent.parent / "icons" / "app_icon.ico",
                Path(__file__).parent.parent.parent / "icons" / "app_icon.png",
                Path(__file__).parent.parent.parent / "icons" / "icon_256x256.png"
            ]
            
            for icon_path in icon_paths:
                if icon_path.exists():
                    icon = QIcon(str(icon_path))
                    self.setWindowIcon(icon)
                    # 也设置应用程序图标
                    QApplication.instance().setWindowIcon(icon)
                    logging.debug(f"已设置窗口图标: {icon_path}")
                    return
            
            logging.warning("未找到图标文件")
        except Exception as e:
            logging.error(f"设置窗口图标失败: {e}")
        
    def init_ui(self):
        """初始化用户界面"""
        # 创建主布局
        layout = QVBoxLayout(self.main_container)
        layout.setContentsMargins(15, 10, 15, 10)  # 减小边距
        layout.setSpacing(8)  # 减小整体间距
        
        # 设置字体
        app = QApplication.instance()
        app.setFont(self.SYSTEM_FONT)
        
        # 设置窗口整体样式 - 现代简约风格
        self.setStyleSheet(f"""
            QMainWindow {{
                background: {self.COLORS['background']};
            }}
            
            QWidget {{
                font-family: "Microsoft YaHei UI", "PingFang SC", "Segoe UI", "-apple-system", sans-serif;
            }}
            
            QLabel {{
                color: {self.COLORS['text_primary']};
            }}
            
            QLabel[isSubLabel="true"] {{
                color: {self.COLORS['text_secondary']};
                font-size: 9pt;
            }}
            
            QLineEdit, QTextEdit, QComboBox {{
                border: 1px solid {self.COLORS['border']};
                border-radius: 4px;
                padding: 6px;
                background: {self.COLORS['background']};
                selection-background-color: {self.COLORS['primary']};
            }}
            
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
                border: 1px solid #CC0000;  /* 修改为2px的红色边框，与开始下载按钮颜色一致 */
            }}
            
            QPushButton {{
                background-color: {self.COLORS['surface']};
                border: 1px solid {self.COLORS['border']};
                border-radius: 4px;
                padding: 6px 12px;
                color: {self.COLORS['text_primary']};
                font-weight: 500;
            }}
            
            QPushButton:hover {{
                background-color: #E6E6E6;
                border: 1px solid #CCCCCC;
            }}
            
            QPushButton:pressed {{
                background-color: #D6D6D6;
            }}
            
            QPushButton#primaryButton {{
                background-color: {self.COLORS['primary']};
                color: {self.COLORS['text_light']};
                border: none;
            }}
            
            QPushButton#primaryButton:hover {{
                background-color: {self.COLORS['primary_dark']};
            }}
            
            QPushButton#primaryButton:pressed {{
                background-color: #003C8F;
            }}
            
            QProgressBar {{
                border: 1px solid {self.COLORS['border']};
                border-radius: 4px;
                text-align: center;
                background-color: {self.COLORS['surface']};
            }}
            
            QProgressBar::chunk {{
                background-color: {self.COLORS['primary']};
                border-radius: 3px;
            }}
            
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            
            QCheckBox {{
                spacing: 8px;
            }}
            
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid {self.COLORS['border']};
                border-radius: 3px;
            }}
            
            QCheckBox::indicator:checked {{
                background-color: {self.COLORS['primary']};
                border: 1px solid {self.COLORS['primary']};
                image: none;
            }}
            
            /* 白色勾选符号 */
            QCheckBox::indicator:checked {{
                color: white;
                font-weight: bold;
                font-family: Arial;
                font-size: 14px;
                text-align: center;
            }}
            
            QComboBox {{
                padding: 5px;
                border: 1px solid {self.COLORS['border']};
                border-radius: 4px;
                min-width: 6em;
            }}
            
            QComboBox:hover {{
                border: 1px solid #CCCCCC;
            }}
            
            QComboBox:focus {{
                border: 1px solid {self.COLORS['primary']};
            }}
            
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: none;
                border-top-right-radius: 3px;
                border-bottom-right-radius: 3px;
            }}
            
            QWidget#taskWidget {{
                background: {self.COLORS['surface']};
                border: none;
                border-radius: 4px;
                margin: 6px 8px 2px 8px;
            }}
            
            /* 添加滚动区域样式 */
            QScrollArea#tasksScrollArea {{
                background-color: {self.COLORS['surface']};
                border: 1px solid {self.COLORS['border']};
                border-radius: 8px;
                padding: 0px;
            }}
            
            /* 确保滚动区域内的视口也是透明的，不影响圆角 */
            QScrollArea#tasksScrollArea > QWidget {{
                background-color: transparent;
            }}
            
            /* 调整滚动条样式，使其与圆角容器协调 */
            QScrollArea#tasksScrollArea QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 0px;
            }}
            
            QScrollArea#tasksScrollArea QScrollBar::handle:vertical {{
                background: #CCCCCC;
                border-radius: 4px;
            }}
            
            QScrollArea#tasksScrollArea QScrollBar::add-line:vertical,
            QScrollArea#tasksScrollArea QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        self.header_status_label = QLabel(self.main_container)
        self.header_status_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.header_status_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.header_status_label.setStyleSheet(
            f"""
            QLabel {{
                color: {self.COLORS['info']};
                font-size: 9pt;
                font-weight: 500;
                padding: 0 2px;
                background: transparent;
            }}
            """
        )
        self.header_status_label.hide()

        # URL输入区域
        url_label = QLabel("视频链接:")
        url_label.setStyleSheet("""
            font-weight: 600; 
            font-size: 10 pt;
            color: #444444;
            letter-spacing: 0.3px;
        """)  # 优化字体样式，保持原有文本
        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText("在此输入一个或多个YouTube视频链接，每行一个")
        self.url_input.setAcceptRichText(False)
        self.url_input.setFixedHeight(90)  # 减小URL输入区域高度
        layout.addWidget(url_label)
        layout.addWidget(self.url_input)
        
        # 下载位置选择区域
        location_layout = QHBoxLayout()
        location_layout.setContentsMargins(0, 0, 0, 0)  # 减少边距
        location_layout.setSpacing(5)  # 减少间距
        location_label = QLabel("下载位置:")
        self.location_input = QLineEdit()
        
        # 从配置中加载保存的下载路径
        saved_path = self.config.config.get('download_path', '')
        if saved_path and os.path.exists(saved_path):
            self.location_input.setText(saved_path)
        else:
            # 默认使用用户下载文件夹
            self.location_input.setText(os.path.join(os.path.expanduser("~"), "Downloads"))
        
        self.browse_button = QPushButton("浏览...")
        self.browse_button.setFixedWidth(60)  # 设置固定宽度
        self.browse_button.clicked.connect(self.browse_location)  # 确保连接到槽函数
        
        location_layout.addWidget(location_label)
        location_layout.addWidget(self.location_input)
        location_layout.addWidget(self.browse_button)
        layout.addLayout(location_layout)
        
        # 浏览器选择区域 - 调整布局将提示文字放到右侧
        browser_container = QHBoxLayout()  # 创建一个水平容器来放置浏览器选择和提示文字
        browser_container.setContentsMargins(0, 0, 0, 0)  # 减少容器的内边距

        # 左侧放浏览器选择
        browser_layout = QHBoxLayout()
        browser_layout.setContentsMargins(0, 0, 0, 0)  # 减少布局的内边距
        browser_layout.setSpacing(5)  # 减少元素间的间距
        browser_label = QLabel("浏览器:")  # 修改文本
        self.browser_combo = QComboBox()
        self.browser_combo.setFixedWidth(220)  # 缩小下拉框宽度

        # Windows 支持的浏览器
        browsers = [
            ('Firefox 火狐浏览器', 'firefox'),
            ('Chrome 谷歌浏览器 (不支持)', 'chrome'),  # 修改描述更简洁
        ]
        for browser_name, browser_id in browsers:
            self.browser_combo.addItem(browser_name, browser_id)

        browser_layout.addWidget(browser_label)
        browser_layout.addWidget(self.browser_combo)
        browser_layout.addStretch(1)  # 添加弹性空间，使控件靠左对齐

        # 右侧放提示文字
        browser_hint = QLabel("提示: 需在Firefox火狐浏览器中保持登录状态。")
        browser_hint.setProperty("isSubLabel", "true")  # 标记为次要标签
        browser_hint.setStyleSheet(f"color: {self.COLORS['text_secondary']}; font-size: 9pt;")

        # 将浏览器选择和提示文字添加到水平容器
        browser_container.addLayout(browser_layout, 1)  # 浏览器选择占1比例
        browser_container.addWidget(browser_hint, 2)    # 提示文字占2比例

        # 将整个水平容器添加到主布局
        layout.addLayout(browser_container)
        
        # 画质选择和播放列表下载按钮布局调整
        quality_layout = QHBoxLayout()
        quality_layout.setContentsMargins(0, 0, 0, 0)  # 减少边距
        quality_layout.setSpacing(5)  # 减少间距
        quality_label = QLabel("画质选择:")
        self.quality_combo = QComboBox()
        self.quality_combo.addItems([
            "最高画质",
            "最高画质MP4",
            "4K MP4",
            "1080P MP4",
            "480P MP4",
            "仅MP3音频"
        ])
        saved_quality = self.config.config.get('quality_index', 0)
        if 0 <= saved_quality <= 5:
            self.quality_combo.setCurrentIndex(saved_quality)
        self.quality_combo.currentIndexChanged.connect(self._save_quality_setting)

        # 添加字幕下载选项
        self.subtitle_checkbox = QCheckBox("下载字幕")
        self.subtitle_checkbox.setChecked(False)  # 默认不勾选
        self.subtitle_checkbox.setToolTip("下载视频的所有可用字幕(srt格式)")

        # 添加播放列表下载按钮
        self.playlist_button = QPushButton("切换到播放列表/频道模式")
        self.playlist_button.clicked.connect(self.open_playlist_window)
        
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality_combo)
        quality_layout.addWidget(self.subtitle_checkbox)
        quality_layout.addStretch()
        quality_layout.addWidget(self.playlist_button)
        layout.addLayout(quality_layout)
        
        # 控制按钮区域
        button_layout = QHBoxLayout()
        self.download_button = QPushButton("开始下载")
        self.download_button.setObjectName("primaryButton")  # 添加这一行，标记为主要按钮
        self.download_button.setMinimumHeight(36)  # 减小按钮高度
        self.download_button.setCursor(Qt.CursorShape.PointingHandCursor)  # 鼠标悬停显示手型光标
        self.download_button.clicked.connect(self.start_download)
        button_layout.addWidget(self.download_button)
        layout.addLayout(button_layout)
        
        # 添加下载任务显示区域
        downloads_label = QLabel("下载任务:")
        downloads_label.setContentsMargins(0, 0, 0, 2)  # 减少标签下方边距
        layout.addWidget(downloads_label)
        
        # 创建下载任务容器
        self.downloads_area = QWidget()
        self.tasks_layout = QVBoxLayout(self.downloads_area)
        self.tasks_layout.setSpacing(2)  # 增加任务间距
        self.tasks_layout.setContentsMargins(4, 6, 4, 6)  # 增加容器内边距
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.downloads_area)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(230)  # 从260减少到230
        scroll_area.setMaximumHeight(350)  # 从400减少到350
        scroll_area.setObjectName("tasksScrollArea")  # 添加这一行，用于应用样式
        layout.addWidget(scroll_area)
        
        # 修改下载按钮样式，使用与墨绿色协调的灰色系
        self.download_button.setStyleSheet("""
            QPushButton {
                background: #CC0000;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 28px;  /* 减小内边距 */
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
        
    def _save_quality_setting(self, index):
        """保存画质选择到配置"""
        self.config.config['quality_index'] = index
        self.config.save_config()

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

    def browse_location(self):
        """浏览并选择下载位置"""
        current_path = self.location_input.text()
        # 确保使用当前路径作为起始路径（如果存在）
        start_path = current_path if os.path.exists(current_path) else os.path.expanduser("~")
        
        folder = QFileDialog.getExistingDirectory(
            self, "选择下载文件夹", start_path
        )
        
        if folder:
            # 使用os.path.normpath规范化路径，确保使用正确的路径分隔符
            folder = os.path.normpath(folder)
            self.location_input.setText(folder)
            # 保存到配置
            self.config.config['download_path'] = folder
            self.config.save_config()
            
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
        task_widget.setObjectName("taskWidget")  # 添加ID以应用圆角样式
        task_widget.setFixedHeight(75)  # 从80改为75，进一步压缩任务的高度
        
        # 为任务小部件设置背景样式，无边框避免嵌套
        task_widget.setStyleSheet("""
            QWidget#taskWidget {
                background-color: #F5F7FA;
                border: none;
                border-radius: 4px;
                margin: 2px 0;
            }
        """)
        
        layout = QVBoxLayout(task_widget)
        layout.setContentsMargins(10, 2, 10, 2)  # 减少上下内边距
        layout.setSpacing(1)  # 减小元素间距
        
        # 创建内容区域
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(0)  # 减小元素间距
        content_layout.setContentsMargins(0, 1, 0, 1)  # 减少内边距
        
        # 视频标题样式优化
        title_label = QLabel("正在获取视频信息...")
        title_label.setStyleSheet("""
            font-weight: 600; 
            color: #2C3E50;
            font-size: 12px;
            letter-spacing: 0.3px;
            font-family: "Microsoft YaHei UI", "PingFang SC", sans-serif;
        """)
        title_label.setWordWrap(True)
        title_label.setFixedHeight(30)  # 从32减小到30
        
        # URL
        url_label = QLabel(f"URL: {url}")
        url_label.setStyleSheet("""
            color: #666; 
            font-size: 10px;
            line-height: 1;  /* 减小行高 */
        """)
        url_label.setWordWrap(True)
        url_label.setFixedHeight(14)  # 从15减小到14
        content_layout.addWidget(title_label)
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
                background-color: #2196F3;
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
        
        # 实时日志按钮
        log_button = QPushButton("实时下载日志")
        log_button.setCursor(Qt.CursorShape.PointingHandCursor)
        log_button.setStyleSheet("""
            QPushButton {
                border: none;
                color: #666666;
                font-size: 10px;
                padding: 2px 6px;
                background: transparent;
            }
            QPushButton:hover {
                color: #333333;
                text-decoration: underline;
            }
        """)
        status_layout.addWidget(log_button)
        
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
            font-size: 11px;  /* 改回11px */
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
        task_widget.log_button = log_button
        task_widget.video_path = None  # 用于保存视频路径
        task_widget.progress_bar = progress_bar
        
        # 连接日志按钮信号
        log_button.clicked.connect(lambda: self.show_task_log(task_id))
        
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
        output_path = self.location_input.text()
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
        
        # 保存当前路径到配置（确保每次下载都更新配置）
        self.config.config['download_path'] = output_path
        self.config.save_config()

        self._pending_download_request = {
            'urls': urls,
            'output_path': output_path,
            'format_options': format_options,
            'browser': browser,
        }

        if self._requires_youtube_prewarm(urls):
            self._start_youtube_prewarm()
            return

        self._launch_pending_downloads()
        
    def cancel_download(self):
        """取消下载"""
        try:
            if self._prewarm_in_progress:
                self._prewarm_in_progress = False
                self._pending_download_request = None
                self.completed_urls = 0
                self.total_urls = 0
                self._set_header_status("")
                self._enable_controls()
                return

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
        # 处理原生日志和普通消息
        if message.startswith("[RAW_LOG]"):
            # 这是原生日志信息，只发送到日志窗口，不更新UI进度
            raw_log = message[9:]  # 移除前缀
            if task_id in self.log_windows:
                self.log_windows[task_id].append_raw_log(raw_log)
            return  # 不继续处理原生日志（原生日志不包含UI更新信息）
            
        # 同时将普通消息发送到日志窗口
        if task_id in self.log_windows:
            self.log_windows[task_id].append_log(message)
            
        if task_id in self.download_tasks:
            task_widget = self.download_tasks[task_id]
            
            if "开始下载" in message:
                # 简化标题处理
                title = message.replace("开始下载: ", "").strip()
                task_widget.title_label.setText(title)
                task_widget.video_path = os.path.join(self.location_input.text(), title)
                
                # 更新状态
                task_widget.status_label.setText("⏬ 下载中")
                task_widget.status_label.setStyleSheet("""
                    color: #2196F3;
                    font-size: 11px;
                    line-height: 1.1;
                    padding: 2px 8px;
                """)
                task_widget.progress_label.setText("准备下载...")
                task_widget.progress_bar.setValue(0)
                
                # 设置打开文件夹按钮点击事件
                task_widget.open_button.clicked.connect(
                    lambda: self.open_download_folder(self.location_input.text())
                )
            elif "下载进度" in message:
                try:
                    percent = float(message.split('%')[0].split()[-1])
                    task_widget.progress_bar.setValue(int(percent))
                except Exception:
                    pass
                task_widget.progress_label.setText(message)
                task_widget.status_label.setText("⏬ 下载中")
                task_widget.status_label.setStyleSheet("""
                    color: #2196F3;
                    font-size: 11px;
                    line-height: 1.1;
                    padding: 2px 8px;
                """)
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
                task_widget.status_label.setStyleSheet("""
                    color: #4CAF50;
                    font-size: 11px;  /* 改回11px */
                    line-height: 1.1;
                    padding: 2px 8px;
                """)

    def download_finished(self, success, message, title, task_id):
        """处理下载完成事件"""
        if task_id not in self.download_tasks:
            return
            
        task_widget = self.download_tasks[task_id]
        
        if success:
            task_widget.status_label.setText("✓ 已完成")
            task_widget.status_label.setStyleSheet("""
                color: #4CAF50;
                font-size: 11px;  /* 改回11px */
                line-height: 1.1;
                padding: 2px 8px;
            """)
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
            task_widget.status_label.setStyleSheet("""
                color: #F44336;
                font-size: 11px;  /* 改回11px */
                line-height: 1.1;
                padding: 2px 8px;
            """)
            task_widget.open_button.hide()  # 失败时隐藏按钮
        
        self.completed_urls += 1
        
        # 检查是否所有下载都完成了
        if self.completed_urls >= self.total_urls:
            # 重置界面
            self._enable_controls()
            self._set_header_status("")
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
        self.location_input.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.browser_combo.setEnabled(True)

    def _disable_controls(self):
        """禁用控件"""
        self.url_input.setEnabled(False)
        self.location_input.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.browser_combo.setEnabled(False)
        self.download_button.setText("取消下载")
        self.download_button.clicked.disconnect()
        self.download_button.clicked.connect(self.cancel_download)

    def _set_header_status(self, text, is_error=False):
        """更新顶部状态提示。"""
        color = self.COLORS['error'] if is_error else self.COLORS['info']
        self.header_status_label.setStyleSheet(
            f"""
            QLabel {{
                color: {color};
                font-size: 9pt;
                font-weight: 500;
                padding: 0 2px;
                background: transparent;
            }}
            """
        )
        self.header_status_label.setText(text)
        if text:
            self.header_status_label.adjustSize()
            self._position_header_status_label()
            self.header_status_label.show()
            self.header_status_label.raise_()
        else:
            self.header_status_label.hide()

    def _position_header_status_label(self):
        """将顶部状态提示定位到窗口右上角，不占用布局空间。"""
        if not hasattr(self, "header_status_label"):
            return
        right_margin = 16
        top_margin = 10
        x = max(
            right_margin,
            self.main_container.width() - self.header_status_label.width() - right_margin,
        )
        self.header_status_label.move(x, top_margin)

    def resizeEvent(self, event):
        """窗口尺寸变化时保持顶部提示位置稳定。"""
        super().resizeEvent(event)
        if hasattr(self, "header_status_label") and self.header_status_label.isVisible():
            self._position_header_status_label()

    def _requires_youtube_prewarm(self, urls):
        """判断本次任务是否包含 YouTube 下载。"""
        for url in urls:
            url = url.strip()
            if url and self.downloader.detect_platform(url) == 'youtube':
                return True
        return False

    def _start_youtube_prewarm(self):
        """异步预热 YouTube 组件，避免阻塞界面。"""
        if self._prewarm_in_progress:
            return

        self._prewarm_in_progress = True
        self._set_header_status("正在初始化 YouTube 下载组件...")

        threading.Thread(
            target=self._run_youtube_prewarm,
            daemon=True,
        ).start()

    def _run_youtube_prewarm(self):
        """后台执行 YouTube 组件预热。"""
        bin_dir = Path(__file__).parent.parent.parent / "bin"
        ok, message = prewarm_youtube_pot(bin_dir)
        self.youtube_prewarm_finished.emit(ok, message)

    def _handle_youtube_prewarm_finished(self, success, message):
        """处理异步预热完成回调。"""
        was_waiting = self._prewarm_in_progress
        self._prewarm_in_progress = False

        if not was_waiting or self._pending_download_request is None:
            self._set_header_status("")
            return

        if not success:
            self._pending_download_request = None
            self._set_header_status("YouTube 组件初始化失败", is_error=True)
            QMessageBox.critical(self, "初始化失败", message)
            self._enable_controls()
            return

        self._set_header_status("")
        self._launch_pending_downloads()

    def _launch_pending_downloads(self):
        """按既定参数真正启动下载任务。"""
        request = self._pending_download_request
        if not request:
            return

        self._pending_download_request = None
        success = True

        for url in request['urls']:
            url = url.strip()
            if not url:
                continue

            try:
                task_id = f"Task-{len(self.download_tasks)+1}"
                self.create_download_task_widget(url, task_id)

                if not self.downloader.start_download(
                    url,
                    request['output_path'],
                    request['format_options'],
                    request['browser'],
                ):
                    success = False
                    break
            except Exception as e:
                success = False
                error_msg = str(e)
                QMessageBox.critical(
                    self,
                    "下载失败",
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

        return success

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
        self.location_input.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.browser_combo.setEnabled(True)
        
        # 重置下载计数
        self.completed_urls = 0
        self.total_urls = 0
        
        return True
        
    def show_task_log(self, task_id):
        """显示任务的实时日志窗口"""
        # 如果日志窗口已存在，就显示它
        if task_id in self.log_windows:
            log_window = self.log_windows[task_id]
            if log_window.isVisible():
                log_window.raise_()  # 将窗口置前
                log_window.activateWindow()  # 激活窗口
            else:
                log_window.show()
            return
            
        # 创建新的日志窗口
        log_window = LogWindow(task_id, self)
        self.log_windows[task_id] = log_window
        
        # 连接窗口关闭信号，清理引用
        log_window.finished.connect(lambda: self._cleanup_log_window(task_id))
        
        log_window.show()
        
    def _cleanup_log_window(self, task_id):
        """清理日志窗口引用"""
        if task_id in self.log_windows:
            del self.log_windows[task_id]

    def closeEvent(self, event):
        """处理窗口关闭事件"""
        # 关闭所有日志窗口
        for log_window in self.log_windows.values():
            log_window.close()
        self.log_windows.clear()
        
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
