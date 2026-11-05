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
