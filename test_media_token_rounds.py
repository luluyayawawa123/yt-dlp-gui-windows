import unittest
from unittest.mock import patch

from src.core.downloader import Downloader
from src.core.youtube_recovery import next_media_attempt


class FakeProcess:
    def __init__(self, **properties):
        self.properties = properties
        self.started = False
        self.deleted = False

    def property(self, key):
        return self.properties.get(key)

    def setProperty(self, key, value):
        self.properties[key] = value

    def start(self, program, args):
        self.started = True
        self.program = program
        self.args = args

    def deleteLater(self):
        self.deleted = True


class MediaTokenRoundTests(unittest.TestCase):
    def setUp(self):
        self.downloader = Downloader()
        self.downloader._create_download_process = lambda **kw: FakeProcess()
        self.messages = []
        self.downloader.recovery_updated.connect(lambda task, msg: self.messages.append(msg))
        self.process = FakeProcess(
            task_id='Task-1', url='https://www.youtube.com/watch?v=04rfnd1YdyU',
            working_directory='output', title='Example', title_set=True,
            command_args=['yt-dlp.exe', '--extractor-args',
                          'youtubepot-bgutilscript:server_home=server',
                          '-f', 'bv[ext=mp4]+ba[ext=m4a]', '-o', 'same.%(ext)s'],
            media_round=1, media_attempt=1, retry_count=0,
        )
        self.downloader.processes = [self.process]

    def reason(self, process, error='ERROR: unable to download video data: HTTP Error 403'):
        return self.downloader._get_youtube_recovery_reason(process, '', error)

    def test_nine_attempts_and_only_two_refreshes(self):
        states = [(1, 1)]
        process = self.process
        original_args = list(process.property('command_args'))
        with patch('src.core.downloader.invalidate_cached_youtube_pot', return_value=(True, '')) as clear:
            while self.reason(process):
                self.assertTrue(self.downloader._restart_process(process, 'media_403'))
                process = self.downloader.processes[0]
                states.append((process.property('media_round'), process.property('media_attempt')))
                self.assertEqual(process.args, original_args[1:])
                # Fake process doesn't set the metadata normally initialized by the factory.
                for key in ('url', 'task_id', 'command_args', 'working_directory'):
                    process.setProperty(key, self.process.property(key))
                process.setProperty('saw_download_progress', True)
            self.assertEqual(states, [(r, a) for r in range(1, 4) for a in range(1, 4)])
            self.assertEqual(clear.call_count, 2)
            clear.assert_called_with('04rfnd1YdyU')
        self.assertIn('第2/3轮 第1/3次', self.messages[2])
        self.assertIn('清除旧 Token', self.messages[2])
        self.assertIn('第3/3轮 第3/3次', self.messages[-1])

    def test_cancel_never_refreshes_or_restarts(self):
        self.process.setProperty('cancel_requested', True)
        self.process.setProperty('media_attempt', 3)
        with patch('src.core.downloader.invalidate_cached_youtube_pot') as clear:
            self.assertIsNone(self.reason(self.process))
            self.assertFalse(self.downloader._restart_process(self.process, 'media_403'))
            clear.assert_not_called()

    def test_cache_refresh_failure_stops_without_extra_process(self):
        self.process.setProperty('media_attempt', 3)
        with patch('src.core.downloader.invalidate_cached_youtube_pot', return_value=(False, '缓存写入失败')):
            self.assertFalse(self.downloader._restart_process(self.process, 'media_403'))
        self.assertEqual(self.downloader.processes, [self.process])
        self.assertEqual(self.process.property('token_refresh_error'), '缓存写入失败')

    def test_login_dns_and_subtitles_do_not_gain_token_rounds(self):
        self.assertIsNone(self.reason(self.process, 'ERROR: LOGIN_REQUIRED'))
        self.process.setProperty('retry_count', 5)
        self.assertIsNone(self.reason(self.process, 'ERROR: getaddrinfo failed'))
        self.process.setProperty('subtitle_only_retry', True)
        self.assertIsNone(self.reason(self.process))

    def test_round_limits(self):
        self.assertEqual(next_media_attempt(1, 3), (2, 1))
        self.assertEqual(next_media_attempt(3, 2), (3, 3))
        self.assertIsNone(next_media_attempt(3, 3))


if __name__ == '__main__':
    unittest.main()
