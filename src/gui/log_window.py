from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTextEdit, QPushButton, 
                            QHBoxLayout, QApplication, QLabel)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont


class LogWindow(QDialog):
    """极客风格的实时日志窗口"""
    
    def __init__(self, task_id, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.log_content = []  # 存储所有日志内容
        self._auto_scroll_follow_bottom = True
        self.init_ui()
        
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle(f"实时下载日志 - 任务 {self.task_id}")
        self.setFixedSize(900, 650)
        
        # 设置窗口标志：无边框、置顶
        self.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint
        )
        
        # 创建主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 创建主容器
        container = self.create_main_container()
        layout.addWidget(container)
        
        # 设置窗口样式（黑色背景）
        self.setStyleSheet("""
            QDialog {
                background-color: #000000;
                border: 2px solid #33FF33;
                border-radius: 8px;
            }
        """)
        
        # 居中显示窗口
        self.center_window()
        
    def create_main_container(self):
        """创建主容器"""
        from PyQt6.QtWidgets import QWidget
        
        container = QWidget()
        container.setStyleSheet("background-color: #000000;")
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        # 创建标题栏
        title_bar = self.create_title_bar()
        layout.addWidget(title_bar)
        
        # 创建日志显示区域
        self.log_display = self.create_log_display()
        layout.addWidget(self.log_display)
        
        # 创建底部按钮栏
        button_bar = self.create_button_bar()
        layout.addWidget(button_bar)
        
        return container
        
    def create_title_bar(self):
        """创建标题栏"""
        from PyQt6.QtWidgets import QWidget
        
        title_bar = QWidget()
        title_bar.setFixedHeight(30)
        title_bar.setStyleSheet("background-color: #001100; border-radius: 4px;")
        
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(8, 6, 8, 6)
        
        # 标题文字
        title_label = QLabel(f">>> 实时下载日志 - 任务 {self.task_id} <<<")
        title_label.setStyleSheet("""
            color: #33FF33;
            font-family: "微软雅黑", "Microsoft YaHei", "黑体", "SimHei";
            font-size: 12px;
            font-weight: bold;
            background: transparent;
        """)
        
        layout.addWidget(title_label)
        layout.addStretch()
        
        # 关闭按钮
        close_button = QPushButton("✕")
        close_button.setFixedSize(20, 20)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #FF0000;
                color: white;
                border: none;
                border-radius: 2px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FF3333;
            }
            QPushButton:pressed {
                background-color: #CC0000;
            }
        """)
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)
        
        return title_bar
        
    def create_log_display(self):
        """创建日志显示区域"""
        log_display = QTextEdit()
        log_display.setReadOnly(True)
        
        # 设置中文字体
        font = QFont("微软雅黑", 10)
        if not font.exactMatch():
            font = QFont("Microsoft YaHei", 10)
            if not font.exactMatch():
                font = QFont("黑体", 10)
                if not font.exactMatch():
                    font = QFont("SimHei", 10)
        
        log_display.setFont(font)
        
        # 极客风格样式
        log_display.setStyleSheet("""
            QTextEdit {
                background-color: #000000;
                color: #33FF33;
                border: 1px solid #003300;
                border-radius: 4px;
                padding: 8px;
                selection-background-color: #333333;
                selection-color: #00FF00;
            }
            QScrollBar:vertical {
                background-color: #001100;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #33FF33;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #00FF00;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)
        
        # 初始化显示
        log_display.setText(f"""
>>> YT-DLP 实时下载日志监控器 <<<
===========================================
[系统] 任务ID: {self.task_id}
[系统] 状态: 等待下载数据...
[系统] 提示: 使用 Ctrl+A 全选文本
[系统] 提示: 点击复制按钮复制日志
===========================================

""")

        log_display.verticalScrollBar().valueChanged.connect(
            self._handle_log_scroll_changed
        )
        
        return log_display
        
    def create_button_bar(self):
        """创建底部按钮栏"""
        from PyQt6.QtWidgets import QWidget
        
        button_bar = QWidget()
        button_bar.setFixedHeight(40)
        button_bar.setStyleSheet("background-color: #001100; border-radius: 4px;")
        
        layout = QHBoxLayout(button_bar)
        layout.setContentsMargins(8, 8, 8, 8)
        
        
        # 复制日志按钮
        copy_button = QPushButton("📋 复制日志到剪贴板")
        copy_button.setStyleSheet("""
            QPushButton {
                background-color: #002200;
                color: #33FF33;
                border: 1px solid #33FF33;
                border-radius: 4px;
                padding: 6px 12px;
                font-family: "微软雅黑", "Microsoft YaHei", "黑体", "SimHei";
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #003300;
                color: #00FF00;
                border-color: #00FF00;
            }
            QPushButton:pressed {
                background-color: #004400;
            }
        """)
        copy_button.clicked.connect(self.copy_logs_to_clipboard)
        
        layout.addStretch()
        layout.addWidget(copy_button)
        layout.addStretch()
        
        return button_bar
        
    def center_window(self):
        """居中显示窗口"""
        if self.parent():
            parent_geo = self.parent().geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            self.move(x, y)
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            x = (screen.width() - self.width()) // 2
            y = (screen.height() - self.height()) // 2
            self.move(x, y)
            
    def append_log(self, text):
        """添加日志内容"""
        self.log_content.append(text)
        
        # 格式化日志文本（添加时间戳和前缀）
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_text = f"[{timestamp}] {text}"
        
        self._append_to_display(formatted_text)
        
    def append_raw_log(self, text):
        """添加原生日志内容（不添加时间戳格式化）"""
        self.log_content.append(text)
        self._append_to_display(text)

    def _handle_log_scroll_changed(self, _value):
        """用户离开底部时暂停自动滚动，回到底部后恢复。"""
        scrollbar = self.log_display.verticalScrollBar()
        self._auto_scroll_follow_bottom = scrollbar.value() >= scrollbar.maximum()

    def _append_to_display(self, text):
        """向日志窗口追加文本，并按需跟随到底部。"""
        should_scroll = self._auto_scroll_follow_bottom
        self.log_display.append(text)
        if should_scroll:
            scrollbar = self.log_display.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        
    def copy_logs_to_clipboard(self):
        """复制日志到剪贴板"""
        clipboard = QApplication.clipboard()
        
        # 获取所有日志内容
        all_logs = self.log_display.toPlainText()
        clipboard.setText(all_logs)
        
        # 临时显示复制成功提示
        button = self.sender()
        original_text = button.text()
        button.setText("✓ 已复制!")
        button.setStyleSheet("""
            QPushButton {
                background-color: #004400;
                color: #00FF00;
                border: 1px solid #00FF00;
                border-radius: 4px;
                padding: 6px 12px;
                font-family: "微软雅黑", "Microsoft YaHei", "黑体", "SimHei";
                font-size: 10px;
                font-weight: bold;
            }
        """)
        
        # 1秒后恢复原始文本
        QTimer.singleShot(1000, lambda: self._restore_copy_button(button, original_text))
        
    def _restore_copy_button(self, button, original_text):
        """恢复复制按钮原始状态"""
        if button:
            button.setText(original_text)
            button.setStyleSheet("""
                QPushButton {
                    background-color: #002200;
                    color: #33FF33;
                    border: 1px solid #33FF33;
                    border-radius: 4px;
                    padding: 6px 12px;
                    font-family: "微软雅黑", "Microsoft YaHei", "黑体", "SimHei";
                    font-size: 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #003300;
                    color: #00FF00;
                    border-color: #00FF00;
                }
                QPushButton:pressed {
                    background-color: #004400;
                }
            """)
                
    def mousePressEvent(self, event):
        """鼠标按下事件 - 用于窗口拖动"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            
    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 拖动窗口"""
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, 'drag_position'):
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
