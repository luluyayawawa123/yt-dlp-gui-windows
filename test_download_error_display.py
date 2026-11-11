import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.downloader import Downloader
from gui.main_window import MainWindow


class _FakeLabel:
    def __init__(self, text=""):
        self.text = text
        self.tooltip = ""

    def setText(self, text):
        self.text = text

    def setStyleSheet(self, _style):
        pass

    def setToolTip(self, text):
        self.tooltip = text


class _FakeButton:
    def show(self):
        pass

    def hide(self):
        pass


class _FakeTaskWidget:
    def __init__(self):
        self.progress_label = _FakeLabel("GoogleVideo 域名 DNS 解析失败，正在自动重试")
        self.status_label = _FakeLabel()
        self.open_button = _FakeButton()
        self.retry_button = _FakeButton()


class _FakeWindow:
    _compact_task_message = staticmethod(MainWindow._compact_task_message)
    _set_task_progress_message = MainWindow._set_task_progress_message

    def __init__(self):
        self.download_tasks = {"Task-1": _FakeTaskWidget()}
        self.completed_urls = 0
        self.total_urls = 2


class DownloadErrorDisplayTests(unittest.TestCase):
    def test_manual_retry_refreshes_token_and_preserves_request(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        window = _FakeWindow()
        window.downloader = SimpleNamespace(processes=[])
        window._prewarm_in_progress = False
        window._queue_download_request = Mock()
        task = window.download_tasks['Task-1']
        task.source_url = 'https://www.youtube.com/watch?v=04rfnd1YdyU'
        task.download_path = 'existing-output'
        task.format_options = {'format': 'bv[ext=mp4]+ba[ext=m4a]'}
        task.browser = 'firefox'
        MainWindow._retry_failed_task(window, 'Task-1')
        window._queue_download_request.assert_called_once_with(
            [task.source_url], task.download_path, task.format_options,
            'firefox', refresh_pot_cache=True,
        )

    def test_normal_progress_hides_rounds_and_preserves_speed_and_eta(self):
        from types import SimpleNamespace
        window = _FakeWindow()
        window.task_log_history = {}
        window.log_windows = {}
        task = window.download_tasks['Task-1']
        task.progress_bar = SimpleNamespace(setValue=lambda value: None)
        MainWindow.update_output(window, 'Task-1', '[ATTEMPT]第3/3轮 第2/3次')
        progress = '下载进度: 12% (大小: 305MiB, 速度: 3MiB/s, 剩余: 01:30)'
        MainWindow.update_output(window, 'Task-1', progress)
        self.assertEqual(task.progress_label.text, progress)
        self.assertNotIn('轮', task.progress_label.text)
        self.assertEqual(task.progress_label.tooltip, '')

    def test_retry_context_is_shown_before_download_resumes(self):
        window = _FakeWindow()
        MainWindow.update_output(window, 'Task-1', '[ATTEMPT]第2/3轮 第1/3次')
        task = window.download_tasks['Task-1']
        self.assertEqual(task.attempt_context, '第2/3轮 第1/3次')
        self.assertIn('第2/3轮 第1/3次', task.progress_label.text)

    def test_media_403_and_subtitle_failure_are_both_reported(self):
        downloader = Downloader()
        message = downloader._format_platform_error(
            'ERROR: Did not get any data blocks\n'
            'File "yt_dlp/YoutubeDL.py", in _write_subtitles\n'
            'ERROR: unable to download video data: HTTP Error 403: Forbidden',
            'youtube', 'https://www.youtube.com/watch?v=abc', 1,
        )
        self.assertIn('403', message)
        self.assertIn('视频', message)
        self.assertIn('字幕也下载失败', message)

    def test_subtitle_only_error_remains_specific(self):
        message = Downloader()._format_platform_error(
            'ERROR: Did not get any data blocks\n_write_subtitles',
            'youtube', 'https://www.youtube.com/watch?v=abc', 1,
        )
        self.assertEqual(message, '字幕下载失败：未返回有效数据')

    def test_recovery_event_replaces_stale_speed_without_keyword_matching(self):
        window = _FakeWindow()
        task = window.download_tasks['Task-1']
        task.progress_label.setText('下载进度: 10% 速度: 3MiB/s')
        message = 'HTTP 403，正在重新解析下载地址并自动重试（2/6）...'
        MainWindow.update_recovery_status(window, 'Task-1', message)
        self.assertEqual(task.status_label.text, '正在重试')
        self.assertIn('2/6', task.progress_label.text)
        self.assertNotIn('MiB/s', task.progress_label.text)

    def test_internal_retry_emits_recovery_event(self):
        from PyQt6.QtCore import QByteArray, QProcess
        downloader = Downloader()
        process = QProcess()
        process.setProperty('task_id', 'Task-1')
        events = []
        downloader.recovery_updated.connect(lambda task, msg: events.append((task, msg)))
        downloader._handle_process_output(process, QByteArray(
            b'[download] Got error: HTTP Error 403: Forbidden. Retrying (1/10)...\n'
        ))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], 'Task-1')
        self.assertIn('403', events[0][1])

    def test_login_required_replaces_previous_dns_retry_message(self):
        window = _FakeWindow()
        final_message = "YouTube 要求登录验证；请更换 IP 后重新下载"

        MainWindow.download_finished(
            window,
            False,
            final_message,
            "测试视频",
            "Task-1",
        )

        task = window.download_tasks["Task-1"]
        self.assertEqual(task.progress_label.text, final_message)
        self.assertEqual(task.status_label.text, "❌ 下载失败")

    def test_long_error_is_compact_but_full_text_is_preserved(self):
        window = _FakeWindow()
        final_message = "下载失败：" + "这是一段非常长的错误信息" * 8

        MainWindow.download_finished(
            window,
            False,
            final_message,
            "测试视频",
            "Task-1",
        )

        task = window.download_tasks["Task-1"]
        self.assertLessEqual(len(task.progress_label.text), 42)
        self.assertTrue(task.progress_label.text.endswith("…"))
        self.assertEqual(task.progress_label.tooltip, final_message)

    def test_login_required_is_formatted_as_a_specific_error(self):
        downloader = Downloader()
        error = "ERROR: [youtube] abc: LOGIN_REQUIRED: Sign in to confirm you’re not a bot"

        message = downloader._format_platform_error(
            error,
            "youtube",
            "https://www.youtube.com/watch?v=abc",
            1,
        )

        self.assertIn("要求登录验证", message)
        self.assertNotIn("DNS", message)


if __name__ == "__main__":
    unittest.main()
