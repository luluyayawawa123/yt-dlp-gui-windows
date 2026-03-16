from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                           QPushButton, QLineEdit, QLabel, QMessageBox, QTextEdit, QHBoxLayout, QFileDialog, QComboBox, QCheckBox, QDialog,
                           QStyle, QSizePolicy, QApplication)
from PyQt6.QtCore import Qt, QProcess, QProcessEnvironment, pyqtSignal
from PyQt6.QtGui import QTextCursor, QIcon
from .saved_urls_dialog import SavedURLsDialog
from core.youtube_pot import prewarm_youtube_pot
import os
import logging
import re
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import threading

class PlaylistWindow(QMainWindow):
    youtube_prewarm_finished = pyqtSignal(bool, str)
    _YOUTUBE_RETRY_ERROR_MARKERS = (
        "po token",
        "bgutil",
        "requested format is not available",
        "failed to check script version",
        "timeoutexpired",
        "timed out",
        "script-deno",
        "gvs po token",
        "generate_once.ts",
    )
    _MAX_YOUTUBE_RECOVERY_RETRIES = 2

    def __init__(self, config, parent=None):
        super().__init__()
        self.config = config
        self.parent_window = parent
        self.process = None
        self._pending_download_start = None
        self._active_download_start = None
        self._prewarm_in_progress = False
        self._youtube_retry_count = 0
        self._saw_download_progress = False
        self._cancel_requested = False
        self._last_process_output = ""
        self._last_process_error = ""
        self.youtube_prewarm_finished.connect(self._handle_youtube_prewarm_finished)
        self._reset_download_tracking()
        self.setup_ui()
        
    def setup_ui(self):
        """设置界面"""
        # 获取应用程序实例和版本号
        app = QApplication.instance()
        version = app.applicationVersion()
        self.setWindowTitle(f"播放列表/频道下载模式 v{version}")
        self.setMinimumSize(700, 500)
        self.setMaximumWidth(800)  # 限制最大宽度
        self.resize(700, 650)
        
        # 设置窗口图标
        self.set_window_icon()
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)  # 设置边距

        self.header_status_label = QLabel(central_widget)
        self.header_status_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
        )
        self.header_status_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.header_status_label.setStyleSheet("""
            QLabel {
                color: #0288D1;
                font-size: 9pt;
                font-weight: 500;
                padding: 0 2px;
                background: transparent;
            }
        """)
        self.header_status_label.hide()
        
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
        
        # 下载位置选择区域
        location_layout = QHBoxLayout()
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
        self.browse_button.clicked.connect(self.browse_location)
        
        location_layout.addWidget(location_label)
        location_layout.addWidget(self.location_input)
        location_layout.addWidget(self.browse_button)
        layout.addLayout(location_layout)
        
        # 画质选择区域 (独立的布局)
        quality_layout = QHBoxLayout()
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

        # 网络稳健重试（播放列表模式专用）
        self.resilient_retry_checkbox = QCheckBox("网络稳健重试（推荐）")
        self.resilient_retry_checkbox.setChecked(
            self.config.config.get('playlist_resilient_retry', True)
        )
        self.resilient_retry_checkbox.setToolTip(
            "遇到网络抖动会自动退避重试，成功率更高，但失败时等待会稍长"
        )
        self.resilient_retry_checkbox.stateChanged.connect(self._save_resilient_retry_setting)
        archive_layout.addWidget(self.resilient_retry_checkbox)
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

        # 次级按钮行：返回
        secondary_button_layout = QHBoxLayout()
        secondary_button_layout.setContentsMargins(0, 0, 0, 0)
        secondary_button_layout.setSpacing(8)

        self.back_button = QPushButton("返回普通下载")
        self.back_button.clicked.connect(self.back_to_main)
        secondary_button_layout.addWidget(self.back_button)

        layout.addLayout(secondary_button_layout)
        
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
        
    def _save_quality_setting(self, index):
        """保存画质选择到配置"""
        self.config.config['quality_index'] = index
        self.config.save_config()

    def _save_resilient_retry_setting(self, state):
        """保存播放列表模式的稳健重试开关"""
        self.config.config['playlist_resilient_retry'] = (state == Qt.CheckState.Checked.value)
        self.config.save_config()

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

    def _reset_download_tracking(self):
        """重置当前下载任务的状态追踪"""
        self.item_states = {}
        self.current_item_id = None
        self.current_merging_id = None
        self.total_items_expected = 0
        self.stdout_buffer = ""
        self.stderr_buffer = ""

    def _ensure_item_state(self, video_id, title=None):
        """确保视频条目状态存在并返回状态字典"""
        if not video_id:
            return None

        state = self.item_states.get(video_id)
        if not state:
            state = {
                "id": video_id,
                "title": video_id,
                "status": "unknown",
                "stage": "",
                "reason_code": "",
                "reason_text": "",
                "pending_retry_exhausted": False,
                "seen_merger": False,
                "final_merged": False,
                "order": len(self.item_states) + 1
            }
            self.item_states[video_id] = state

        if title and (not state["title"] or state["title"] == video_id):
            state["title"] = title
        return state

    def _extract_video_id(self, text):
        """从日志文本中提取视频ID"""
        if not text:
            return None

        # YouTube ID 通常为 11 位，这里放宽为 10-20 位以兼容少量变体并避免误匹配 [download] 等标签
        bracket_match = re.search(r'\[([A-Za-z0-9_-]{10,20})\](?:\.[A-Za-z0-9_-]+)?', text)
        if bracket_match:
            return bracket_match.group(1)

        watch_match = re.search(r'[?&]v=([A-Za-z0-9_-]{10,20})', text)
        if watch_match:
            return watch_match.group(1)

        return None

    def _extract_display_title(self, path_text):
        """从文件路径中提取可读标题"""
        if not path_text:
            return None
        filename = os.path.basename(path_text.strip())
        if not filename:
            return None
        title = os.path.splitext(filename)[0]
        # 去掉中间格式后缀，例如 .f401 / .f140-1
        title = re.sub(r'\.f\d+(?:-\d+)?$', '', title)
        return title.strip() or None

    def _mark_item_failed(self, video_id, reason_code, reason_text, stage):
        """标记条目失败"""
        state = self._ensure_item_state(video_id)
        if not state or state["final_merged"]:
            return

        state["status"] = "failed"
        state["reason_code"] = reason_code
        state["reason_text"] = (reason_text or "").strip()[:300]
        state["stage"] = stage
        state["pending_retry_exhausted"] = False

    def _mark_item_completed(self, video_id, merged=False):
        """标记条目成功完成"""
        state = self._ensure_item_state(video_id)
        if not state:
            return

        state["status"] = "ok"
        state["pending_retry_exhausted"] = False
        state["reason_code"] = ""
        state["reason_text"] = ""
        if merged:
            state["seen_merger"] = True
            state["final_merged"] = True
            state["stage"] = "merge"

    def _mark_retry_exhausted_pending(self, video_id, reason_text):
        """标记达到重试上限，等待后续判断是否真正失败"""
        state = self._ensure_item_state(video_id)
        if not state or state["final_merged"]:
            return

        state["pending_retry_exhausted"] = True
        state["reason_code"] = "retries_exhausted"
        state["reason_text"] = (reason_text or "").strip()[:300]
        if not state["stage"]:
            state["stage"] = "download"

    def _finalize_pending_for_item(self, video_id, switched_to_next=False):
        """在切换条目或任务结束时，确认是否应将重试上限条目标记为失败"""
        if not video_id:
            return

        state = self.item_states.get(video_id)
        if not state:
            return

        if state["pending_retry_exhausted"] and state["status"] != "ok":
            reason = state["reason_text"] or "网络读取不完整，重试已达到上限（10/10）"
            if switched_to_next:
                reason = f"{reason}，并已切换到下一个条目"
            self._mark_item_failed(video_id, "retries_exhausted", reason, "download")
        state["pending_retry_exhausted"] = False

    def _parse_stream_text(self, text, is_error=False):
        """解析 stdout/stderr 流并进行条目状态追踪"""
        buffer_name = "stderr_buffer" if is_error else "stdout_buffer"
        combined = getattr(self, buffer_name) + text
        normalized = combined.replace('\r\n', '\n').replace('\r', '\n')
        parts = normalized.split('\n')

        if normalized.endswith('\n'):
            lines = parts[:-1]
            remainder = ""
        else:
            lines = parts[:-1]
            remainder = parts[-1] if parts else ""

        setattr(self, buffer_name, remainder)

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            self._track_line(line, is_error=is_error)

    def _flush_stream_buffers(self):
        """处理残留在缓冲区中的最后一行文本"""
        if self.stdout_buffer.strip():
            self._track_line(self.stdout_buffer.strip(), is_error=False)
        if self.stderr_buffer.strip():
            self._track_line(self.stderr_buffer.strip(), is_error=True)
        self.stdout_buffer = ""
        self.stderr_buffer = ""

    def _track_line(self, line, is_error=False):
        """按行跟踪下载/合并状态"""
        # 某些失败会发生在 Destination 之前，先尽量从 URL/INFO 行绑定当前条目ID
        extracting_match = re.search(
            r'\[youtube\]\s+Extracting URL:\s+https?://[^\s]+[?&]v=([A-Za-z0-9_-]{10,20})',
            line
        )
        if extracting_match:
            video_id = extracting_match.group(1)
            self.current_item_id = video_id
            state = self._ensure_item_state(video_id)
            if state and not state["stage"]:
                state["stage"] = "download"

        info_match = re.search(r'^\[info\]\s+([A-Za-z0-9_-]{10,20}):', line)
        if info_match:
            video_id = info_match.group(1)
            self.current_item_id = video_id
            state = self._ensure_item_state(video_id)
            if state and not state["stage"]:
                state["stage"] = "download"

        youtube_step_match = re.search(r'^\[youtube\]\s+([A-Za-z0-9_-]{10,20}):', line)
        if youtube_step_match:
            video_id = youtube_step_match.group(1)
            self.current_item_id = video_id
            state = self._ensure_item_state(video_id)
            if state and not state["stage"]:
                state["stage"] = "download"

        item_match = re.search(r'\[download\] Downloading item (\d+) of (\d+)', line)
        if item_match:
            _, total = item_match.groups()
            try:
                self.total_items_expected = max(self.total_items_expected, int(total))
            except ValueError:
                pass
            self._finalize_pending_for_item(self.current_item_id, switched_to_next=True)
            self.current_item_id = None
            self.current_merging_id = None
            return

        if '[download] Destination: ' in line:
            path_text = line.split('[download] Destination: ', 1)[-1].strip()
            video_id = self._extract_video_id(path_text)
            title = self._extract_display_title(path_text)
            if video_id:
                self.current_item_id = video_id
                state = self._ensure_item_state(video_id, title)
                if state:
                    state["stage"] = "download"
            return

        if '[Merger] Merging formats into ' in line:
            merged_path = line.split('[Merger] Merging formats into ', 1)[-1].strip().strip('"')
            video_id = self._extract_video_id(merged_path) or self.current_item_id
            if video_id:
                self.current_merging_id = video_id
                state = self._ensure_item_state(video_id, self._extract_display_title(merged_path))
                if state:
                    state["seen_merger"] = True
                    state["stage"] = "merge"
            return

        if line.startswith('Deleting original file '):
            video_id = self._extract_video_id(line)
            if video_id:
                self._mark_item_completed(video_id, merged=True)
                if self.current_merging_id == video_id:
                    self.current_merging_id = None
            return

        if 'has already been downloaded and merged' in line:
            video_id = self._extract_video_id(line) or self.current_item_id
            if video_id:
                self._mark_item_completed(video_id, merged=True)
            return

        if 'Retrying (10/10)' in line:
            video_id = self.current_item_id
            if video_id:
                self._mark_retry_exhausted_pending(video_id, line)
            return

        if 'Giving up after 10 retries' in line:
            video_id = self.current_item_id
            if video_id:
                self._mark_item_failed(video_id, "retries_exhausted", line, "download")
            return

        lower = line.lower()
        if is_error or 'error:' in lower:
            target_id = self.current_merging_id or self.current_item_id
            if not target_id:
                return

            if any(key in lower for key in ['ffmpeg', 'merger', 'postprocess', 'conversion failed']):
                self._mark_item_failed(target_id, "merge_failed", line, "merge")
            elif any(key in lower for key in ['unable to download', 'video unavailable']):
                self._mark_item_failed(target_id, "download_failed", line, "download")
            elif 'error:' in lower:
                self._mark_item_failed(target_id, "download_failed", line, "download")

    def _format_failure_reason(self, state):
        """将失败状态格式化为用户可读原因"""
        code = state.get("reason_code")
        raw_text = state.get("reason_text", "")
        if code == "retries_exhausted":
            return "下载失败：网络读取不完整，重试达到上限（10/10）"
        if code == "merge_failed":
            return f"合并失败：{raw_text or 'ffmpeg 后处理阶段报错'}"
        if code == "download_failed":
            return f"下载失败：{raw_text or '下载阶段出现错误'}"
        return f"失败：{raw_text or '未知错误'}"

    def _append_download_summary(self):
        """在任务结束后追加失败摘要"""
        sorted_states = sorted(self.item_states.values(), key=lambda x: x["order"])
        failed_items = [state for state in sorted_states if state.get("status") == "failed"]
        ok_items = [state for state in sorted_states if state.get("status") == "ok"]

        observed_total = len(self.item_states)
        total_count = self.total_items_expected if self.total_items_expected > 0 else observed_total
        failed_count = len(failed_items)
        success_count = len(ok_items)
        unknown_count = max(total_count - success_count - failed_count, 0)

        summary_lines = [
            "",
            "========== 下载结果摘要 ==========",
            f"总条目: {total_count}，成功: {success_count}，失败: {failed_count}"
        ]
        if unknown_count > 0:
            summary_lines.append(f"未判定: {unknown_count}（日志可能被截断或缺少关键行）")

        if failed_items:
            summary_lines.append("失败条目：")
            for state in failed_items:
                title = state.get("title") or state["id"]
                reason = self._format_failure_reason(state)
                summary_lines.append(f"- [{state['id']}] {title}：{reason}")
            summary_lines.append(
                "建议：对同一播放列表再次执行下载，并勾选“跳过曾经下载过的视频”。"
                "程序会跳过已完成条目，优先补齐本次失败条目。"
            )
        else:
            summary_lines.append("本次下载未发现失败条目。")

        summary_lines.append("==================================")
        self.output_text.append("\n".join(summary_lines))
        self.output_text.moveCursor(QTextCursor.MoveOperation.End)
    
    def start_download(self):
        """开始下载播放列表"""
        if self.download_button.text() == "取消下载":
            self.cancel_download()
            return

        url = self.url_combo.currentText().strip()
        # 如果是完整格式(标题 - URL)，提取URL部分
        if " - http" in url:
            url = url.split(" - ")[-1]
        
        if not url:
            QMessageBox.warning(self, "错误", "请输入播放列表或频道URL")
            return
            
        try:
            self._reset_download_tracking()
            self._youtube_retry_count = 0
            self._saw_download_progress = False
            self._cancel_requested = False
            self._last_process_output = ""
            self._last_process_error = ""

            # 获取下载路径并规范化
            output_path = os.path.normpath(self.location_input.text())
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
            bin_dir = os.path.normpath(os.path.join(root_dir, "bin"))
            process_env.insert("PATH", bin_dir + os.pathsep + process_env.value("PATH", ""))
            self.process.setProcessEnvironment(process_env)
            
            self.process.readyReadStandardOutput.connect(self.handle_output)
            self.process.readyReadStandardError.connect(self.handle_error)
            self.process.finished.connect(self.download_finished)
            
            # 构建命令
            program = os.path.normpath(os.path.join(root_dir, "bin", "yt-dlp.exe"))
            # 为避免播放列表中同名视频互相覆盖，追加唯一视频ID
            output_template = os.path.normpath(os.path.join(
                output_path,
                "%(playlist_title,channel,uploader,playlist_id,channel_id|未知频道)s",
                "%(title)s [%(id)s].%(ext)s"
            ))
            
            # 根据画质选择设置下载参数
            quality_index = self.quality_combo.currentIndex()
            format_option = ('bv*+ba' if quality_index == 0 else 
                            'bv[ext=mp4]+ba[ext=m4a]' if quality_index == 1 else 
                            'bv[ext=mp4][height<=2160]+ba[ext=m4a]' if quality_index == 2 else
                            'bv[ext=mp4][height<=1080]+ba[ext=m4a]' if quality_index == 3 else
                            'bv[ext=mp4][height<=480]+ba[ext=m4a]' if quality_index == 4 else
                            'ba/b')  # 选择最佳音频
            
            args = [
                url,
                "--no-restrict-filenames",  # 允许文件名包含特殊字符
                "--encoding", "utf-8",      # 强制使用 UTF-8 编码
                "-f", format_option,        # 使用选择的画质/格式
                "--ffmpeg-location", os.path.normpath(os.path.join(root_dir, "bin", "ffmpeg.exe")),
                "--no-overwrites",
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
            
            # 添加 PO Token 参数（YouTube SABR 协议需要）
            pot_server_home = os.path.normpath(os.path.join(root_dir, "bin", "bgutil-ytdlp-pot-provider", "server"))
            if os.path.exists(pot_server_home):
                args.extend([
                    "--extractor-args",
                    f"youtubepot-bgutilscript:server_home={pot_server_home}"
                ])

            # 添加其他参数
            args.extend([
                "--cookies-from-browser", "firefox",
                "--verbose",
                "-o", output_template
            ])

            # 稳健重试参数：平衡成功率与等待体验
            if self.resilient_retry_checkbox.isChecked():
                args.extend([
                    "--retries", "10",
                    "--fragment-retries", "10",
                    "--retry-sleep", "http:exp=1:8",
                    "--retry-sleep", "fragment:exp=1:8",
                    "--socket-timeout", "15"
                ])
            
            # 如果选择了 MP3 格式，添加音频提取和转换参数
            if quality_index == 5:  # MP3 选项
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

            bin_dir_path = Path(root_dir) / "bin"
            self._pending_download_start = {
                "program": program,
                "args": args,
                "output_path": output_path,
                "url": url,
            }

            if "youtube.com" in url.lower() or "youtu.be" in url.lower():
                self._start_youtube_prewarm(bin_dir_path)
                return

            self._start_pending_download_process()
            
        except Exception as e:
            logging.error(f"下载出错: {str(e)}", exc_info=True)
            self.status_label.setText(f"下载出错: {str(e)}")
            QMessageBox.critical(self, "错误", f"下载失败：{str(e)}")

    def cancel_download(self):
        """取消当前播放列表下载或预热。"""
        self._cancel_requested = True

        if self._prewarm_in_progress:
            self._prewarm_in_progress = False
            self._pending_download_start = None
            self._active_download_start = None
            self._set_header_status("")
            self.status_label.setText("已取消")
            self._set_download_button_idle()
            self.back_button.setEnabled(True)
            return

        if self.process and self.process.state() == QProcess.ProcessState.Running:
            self.process.kill()
    
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
            self._last_process_output += text
            self._parse_stream_text(text, is_error=False)
            
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
                        self._saw_download_progress = True
                        # 兼容普通格式和 SABR 格式（带流编号前缀如 "2:"）
                        progress_match = re.search(
                            r'\[download\]\s+([\d.]+)%\s+of\s+~?\s*([\d.]+\S+)\s+at\s+([\d.]+\S+)\s+ETA\s+(\S+)',
                            text
                        )
                        if progress_match:
                            percent = progress_match.group(1) + '%'
                            size = progress_match.group(2)
                            speed = progress_match.group(3)
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
            self._last_process_error += data
            self._parse_stream_text(data, is_error=True)
            
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
        self._flush_stream_buffers()

        if self._should_retry_youtube_failure(exit_code):
            current_attempt = self._youtube_retry_count + 2
            total_attempts = self._MAX_YOUTUBE_RECOVERY_RETRIES + 1
            retry_message = (
                f"YouTube 初始化失败，正在自动重试（第 {current_attempt}/{total_attempts} 次尝试）..."
            )
            self.output_text.append(retry_message)
            self.status_label.setText(retry_message)
            logging.warning("YouTube 下载首次失败，准备自动重试一次")
            self._youtube_retry_count += 1
            self._reset_download_tracking()
            self._saw_download_progress = False
            self._last_process_output = ""
            self._last_process_error = ""
            self._start_active_download_process()
            return

        self._finalize_pending_for_item(self.current_item_id, switched_to_next=False)
        self._append_download_summary()
        self._set_download_button_idle()
        self.back_button.setEnabled(True)
        self._active_download_start = None
        if exit_code == 0:
            self.status_label.setText("下载完成")
            logging.info("下载成功完成")
        else:
            if self._cancel_requested:
                self.status_label.setText("已取消")
            else:
                self.status_label.setText(f"下载失败 (退出码: {exit_code})")
            logging.error(f"下载失败 - 退出码: {exit_code}")

    def _should_retry_youtube_failure(self, exit_code):
        """仅对 YouTube 首次初始化类失败自动补一次重试。"""
        if exit_code == 0 or self._cancel_requested:
            return False

        if self._youtube_retry_count >= self._MAX_YOUTUBE_RECOVERY_RETRIES:
            return False

        active = self._active_download_start or {}
        url = (active.get("url") or "").lower()
        if "youtube.com" not in url and "youtu.be" not in url:
            return False

        if self._saw_download_progress:
            return False

        combined = f"{self._last_process_output}\n{self._last_process_error}".lower()
        return any(marker in combined for marker in self._YOUTUBE_RETRY_ERROR_MARKERS)
    
    def back_to_main(self):
        """返回主窗口"""
        if self._prewarm_in_progress:
            self._prewarm_in_progress = False
            self._pending_download_start = None
            self._active_download_start = None
            self._cancel_requested = True
            self._set_download_button_idle()
            self.parent_window.show()
            self.hide()
            return

        if self.process and self.process.state() == QProcess.ProcessState.Running:
            reply = QMessageBox.question(
                self,
                "确认返回",
                "下载正在进行中，确定要返回吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
            self._cancel_requested = True
            self.process.kill()
        
        # 直接显示主窗口并关闭当前窗口，不触发closeEvent
        self.parent_window.show()
        self.hide()  # 改用hide而不是close
    
    def closeEvent(self, event):
        """关闭窗口事件"""
        if self._prewarm_in_progress:
            self._prewarm_in_progress = False
            self._pending_download_start = None
            self._active_download_start = None
            self._cancel_requested = True
            self._set_download_button_idle()
            if self.parent_window:
                self.parent_window.show()
            event.accept()
            return

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
            
            self._cancel_requested = True
            self.process.kill()
        
        # 如果用户确认关闭或没有正在进行的下载，则关闭窗口
        if self.parent_window:
            self.parent_window.show()
        event.accept()

    def _set_header_status(self, text, is_error=False):
        """更新顶部状态提示。"""
        color = "#D32F2F" if is_error else "#0288D1"
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
        """将顶部状态提示固定在窗口右上角，不占用布局空间。"""
        right_margin = 12
        top_margin = 10
        x = max(
            right_margin,
            self.centralWidget().width() - self.header_status_label.width() - right_margin,
        )
        self.header_status_label.move(x, top_margin)

    def resizeEvent(self, event):
        """窗口尺寸变化时保持顶部提示位置稳定。"""
        super().resizeEvent(event)
        if self.header_status_label.isVisible():
            self._position_header_status_label()

    def _start_youtube_prewarm(self, bin_dir):
        """异步预热 YouTube 组件，避免界面卡死。"""
        if self._prewarm_in_progress:
            return

        self._prewarm_in_progress = True
        self._set_download_button_cancel_mode()
        self.back_button.setEnabled(False)
        self.output_text.append("正在初始化 YouTube 下载组件...")
        self.output_text.moveCursor(QTextCursor.MoveOperation.End)

        threading.Thread(
            target=self._run_youtube_prewarm,
            args=(Path(bin_dir),),
            daemon=True,
        ).start()

    def _run_youtube_prewarm(self, bin_dir):
        """后台执行预热。"""
        ok, message = prewarm_youtube_pot(bin_dir)
        self.youtube_prewarm_finished.emit(ok, message)

    def _handle_youtube_prewarm_finished(self, success, message):
        """处理预热完成后的界面与启动逻辑。"""
        was_waiting = self._prewarm_in_progress
        self._prewarm_in_progress = False

        if not was_waiting or self._pending_download_start is None:
            self._set_download_button_idle()
            self.back_button.setEnabled(True)
            return

        if not success:
            self._set_download_button_idle()
            self.back_button.setEnabled(True)
            self.status_label.setText("初始化失败")
            self.output_text.append(f"YouTube 下载组件初始化失败：{message}")
            self.output_text.moveCursor(QTextCursor.MoveOperation.End)
            pending = self._pending_download_start
            self._pending_download_start = None
            logging.error(f"YouTube 组件初始化失败: {message}")
            QMessageBox.critical(self, "错误", f"下载失败：{message}")
            if pending and pending.get("output_path"):
                self.config.config['download_path'] = pending["output_path"]
                self.config.save_config()
            return

        self._start_pending_download_process()

    def _start_pending_download_process(self):
        """真正启动已准备好的播放列表下载进程。"""
        pending = self._pending_download_start
        if not pending:
            return

        self._active_download_start = pending
        self._pending_download_start = None
        self._start_active_download_process()
        self.back_button.setEnabled(True)
        logging.info(f"开始下载播放列表: {pending['url']}")

        self.config.config['download_path'] = pending["output_path"]
        self.config.save_config()

    def _start_active_download_process(self):
        """按当前活动请求启动或重启播放列表下载进程。"""
        active = self._active_download_start
        if not active:
            return

        self._cancel_requested = False
        self.process.start(active["program"], active["args"])
        self._set_download_button_cancel_mode()
        self.back_button.setEnabled(True)
        self.status_label.setText("下载中...")

    def _set_download_button_cancel_mode(self):
        """将主按钮切换为取消下载。"""
        self.download_button.setEnabled(True)
        self.download_button.setText("取消下载")

    def _set_download_button_idle(self):
        """将主按钮恢复为开始下载。"""
        self.download_button.setEnabled(True)
        self.download_button.setText("开始下载")

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
        url = url.lower()  # 转换为小写进行比較
        return ('youtube.com' in url or 'youtu.be' in url) and url.startswith('http')
    
    def set_window_icon(self):
        """设置窗口图标"""
        try:
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
                    logging.debug(f"已设置播放列表窗口图标: {icon_path}")
                    return
                    
            logging.warning("播放列表窗口未找到图标文件")
        except Exception as e:
            logging.error(f"设置播放列表窗口图标失败: {e}") 
