"""模拟清单 DNS 故障；验证重试、取消和失败后继续视频，不联网。"""
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from core.downloader import Downloader
from core.youtube_recovery import should_retry_subtitle_probe
from gui.playlist_window import PlaylistWindow
from test_playlist_media_rounds import FakeWindow


class ProbeProcess:
    def __init__(self):
        self.properties = {
            'task_id': 'Task-1', 'url': 'https://youtu.be/LaAt4KJO4Dk',
            'working_directory': 'output', 'subtitle_groups': ['zh_hans'],
            'probe_args': ['yt-dlp.exe', '--dump-single-json', 'https://youtu.be/LaAt4KJO4Dk'],
            'download_args': ['yt-dlp.exe', '-f', 'bv+ba', 'https://youtu.be/LaAt4KJO4Dk'],
        }
        self.stdout = ''
        self.stderr = 'ERROR: Failed to resolve www.youtube.com: getaddrinfo failed'
        self.starts = []
        self.deleted = False
        self.timer_starts = []
        self._subtitle_probe_timer = SimpleNamespace(
            stop=lambda: None, start=self.timer_starts.append,
        )

    def property(self, name):
        return self.properties.get(name)

    def setProperty(self, name, value):
        self.properties[name] = value

    def readAllStandardOutput(self):
        return SimpleNamespace(data=lambda: self.stdout.encode('utf-8'))

    def readAllStandardError(self):
        return SimpleNamespace(data=lambda: self.stderr.encode('utf-8'))

    def start(self, program, args):
        self.starts.append((program, args))

    def deleteLater(self):
        self.deleted = True


class PlaylistProbeWindow(FakeWindow):
    _handle_subtitle_probe_finished = PlaylistWindow._handle_subtitle_probe_finished

    def __init__(self):
        super().__init__()
        self._subtitle_probe_in_progress = True
        self._subtitle_probe_retry_count = 0
        self._active_download_start['subtitle_tags_by_video_id'] = {}
        self.probes = []

    def _start_subtitle_probe(self, item, retry_count=0):
        self.probes.append((item.video_id, retry_count))
        self._subtitle_probe_retry_count = retry_count
        self._subtitle_probe_in_progress = True


class SubtitleProbeRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.downloader = Downloader()
        self.process = ProbeProcess()
        self.downloader.processes = [self.process]
        self.created = []

        def create(**kwargs):
            self.created.append(kwargs)
            return ProbeProcess()

        self.downloader._create_download_process = create

    def test_normal_dns_then_success_keeps_subtitle_request(self):
        self.downloader._subtitle_probe_finished(self.process, 1, None)
        self.assertEqual(len(self.process.starts), 1)
        self.assertFalse(self.created)
        self.assertFalse(self.process.deleted)
        self.process.stdout = json.dumps({'subtitles': {'zh-Hans': [{}]}})
        self.process.stderr = ''
        self.downloader._subtitle_probe_finished(self.process, 0, None)
        self.assertEqual(len(self.created), 1)
        self.assertIn('--write-subs', self.created[0]['args'])
        self.assertIn('zh-Hans', self.created[0]['args'])
        self.assertTrue(self.process.deleted)

    def test_normal_dns_exhaustion_stops_at_six_and_reports_failure(self):
        messages = []
        self.downloader.output_received.connect(lambda task, message: messages.append(message))
        for _ in range(5):
            self.downloader._subtitle_probe_finished(self.process, 1, None)
        self.assertFalse(self.created)
        self.assertEqual(len(self.process.starts), 5)
        self.downloader._subtitle_probe_finished(self.process, 1, None)
        self.assertEqual(len(self.process.starts), 5)
        self.assertEqual(len(self.created), 1)
        self.assertTrue(any('字幕清单读取失败' in msg for msg in messages))

    def test_normal_cancel_prevents_probe_retry_and_video_start(self):
        self.process.setProperty('cancel_requested', True)
        self.downloader._subtitle_probe_finished(self.process, 1, None)
        self.assertFalse(self.process.starts)
        self.assertFalse(self.created)

    def test_normal_no_matching_subtitle_is_not_a_retryable_failure(self):
        self.process.stdout = json.dumps({'subtitles': {}})
        self.process.stderr = ''
        self.downloader._subtitle_probe_finished(self.process, 0, None)
        self.assertFalse(self.process.starts)
        self.assertEqual(len(self.created), 1)
        self.assertNotIn('--write-subs', self.created[0]['args'])

    def test_normal_timeout_retries_and_resets_timeout_flag(self):
        self.process.setProperty('probe_timed_out', True)
        self.process.stderr = ''
        self.downloader._subtitle_probe_finished(self.process, 1, None)
        self.assertEqual(len(self.process.starts), 1)
        self.assertFalse(self.process.property('probe_timed_out'))
        self.assertEqual(self.process.timer_starts, [120000])

    def test_playlist_dns_then_success_keeps_subtitle_selection(self):
        window = PlaylistProbeWindow()
        window._handle_subtitle_probe_finished('LaAt4KJO4Dk', None, 'ERROR: getaddrinfo failed')
        self.assertEqual(window.probes, [('LaAt4KJO4Dk', 1)])
        self.assertFalse(window.starts)
        selection = SimpleNamespace(languages=('zh-Hans',), messages=())
        window._handle_subtitle_probe_finished('LaAt4KJO4Dk', selection, '')
        self.assertEqual(window._active_download_start['subtitle_tags_by_video_id']['LaAt4KJO4Dk'], ('zh-Hans',))
        self.assertEqual(window.states['LaAt4KJO4Dk']['subtitle_status'], 'pending')
        self.assertEqual(window.starts, [{'refresh_pot_cache': False}])

    def test_playlist_dns_exhaustion_reports_failed_subtitles(self):
        window = PlaylistProbeWindow()
        for _ in range(6):
            window._handle_subtitle_probe_finished('LaAt4KJO4Dk', None, 'ERROR: getaddrinfo failed')
        self.assertEqual(len(window.probes), 5)
        self.assertEqual(len(window.starts), 1)
        self.assertEqual(window.states['LaAt4KJO4Dk']['subtitle_status'], 'failed')
        self.assertEqual(window._active_download_start['subtitle_tags_by_video_id']['LaAt4KJO4Dk'], ())

    def test_playlist_cancel_does_not_retry_or_start_video(self):
        window = PlaylistProbeWindow()
        window._cancel_requested = True
        window._handle_subtitle_probe_finished('LaAt4KJO4Dk', None, 'ERROR: getaddrinfo failed')
        self.assertFalse(window.probes)
        self.assertFalse(window.starts)

    def test_login_not_retried_and_timeout_is_bounded(self):
        self.assertFalse(should_retry_subtitle_probe('', 'ERROR: LOGIN_REQUIRED getaddrinfo failed', 0))
        self.assertTrue(should_retry_subtitle_probe('', '', 4, timed_out=True))
        self.assertFalse(should_retry_subtitle_probe('', '', 5, timed_out=True))
        self.assertFalse(should_retry_subtitle_probe('', 'ERROR: private video', 0))


if __name__ == '__main__':
    unittest.main()
