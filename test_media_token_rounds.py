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

    def test_twenty_four_attempts_and_only_five_refreshes(self):
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
            self.assertEqual(states, [(r, a) for r in range(1, 7) for a in range(1, 5)])
            self.assertEqual(clear.call_count, 5)
            clear.assert_called_with('04rfnd1YdyU')
        self.assertIn('第2/6轮 第1/4次', self.messages[3])
        self.assertIn('清除旧 Token', self.messages[3])
        self.assertIn('第6/6轮 第4/4次', self.messages[-1])

    def test_cancel_never_refreshes_or_restarts(self):
        self.process.setProperty('cancel_requested', True)
        self.process.setProperty('media_attempt', 4)
        with patch('src.core.downloader.invalidate_cached_youtube_pot') as clear:
            self.assertIsNone(self.reason(self.process))
            self.assertFalse(self.downloader._restart_process(self.process, 'media_403'))
            clear.assert_not_called()

    def test_cache_refresh_failure_stops_without_extra_process(self):
        self.process.setProperty('media_attempt', 4)
        with patch('src.core.downloader.invalidate_cached_youtube_pot', return_value=(False, '缓存写入失败')):
            self.assertFalse(self.downloader._restart_process(self.process, 'media_403'))
        self.assertEqual(self.downloader.processes, [self.process])
        self.assertEqual(self.process.property('token_refresh_error'), '缓存写入失败')

    def test_login_dns_and_subtitles_do_not_gain_token_rounds(self):
        self.assertIsNone(self.reason(self.process, 'ERROR: LOGIN_REQUIRED'))
        self.process.setProperty('retry_count', 5)
        self.assertIsNone(self.reason(self.process, 'ERROR: getaddrinfo failed'))
        self.process.setProperty('subtitle_only_retry', True)
        self.process.setProperty('subtitle_retry_count', 5)
        self.assertIsNone(self.reason(self.process))

    def test_round_limits(self):
        self.assertEqual(next_media_attempt(1, 4), (2, 1))
        self.assertEqual(next_media_attempt(6, 3), (6, 4))
        self.assertIsNone(next_media_attempt(6, 4))

    def test_subtitle_failure_gets_five_independent_subtitle_only_retries(self):
        process = self.process
        process.setProperty('retry_count', 23)
        process.setProperty('command_args', [
            'yt-dlp.exe', '--cookies-from-browser', 'firefox',
            '-f', 'bv+ba', '--write-subs', '--sub-langs', 'zh-Hans',
            '-o', 'same.%(ext)s', self.process.property('url'),
        ])
        error = 'ERROR: Unable to download video subtitles: Did not get any data blocks'
        with patch('src.core.downloader.invalidate_cached_youtube_pot', return_value=(True, '')) as clear:
            for count in range(1, 6):
                self.assertEqual(self.reason(process, error), 'subtitle_download')
                args = process.property('command_args')
                self.assertTrue(self.downloader._restart_process(process, 'subtitle_download'))
                process = self.downloader.processes[0]
                self.assertEqual(process.property('subtitle_retry_count'), count)
                self.assertEqual(process.property('retry_count'), 23)
                self.assertTrue(process.property('subtitle_only_retry'))
                self.assertIn('--skip-download', process.args)
                self.assertNotIn('-f', process.args)
                self.assertIn('--cookies-from-browser', process.args)
                self.assertIn('same.%(ext)s', process.args)
                for key in ('url', 'task_id', 'working_directory'):
                    process.setProperty(key, self.process.property(key))
                process.setProperty('command_args', [args[0], *process.args])
                self.assertIn(f'（{count + 1}/6）', self.messages[-1])
            self.assertEqual(clear.call_count, 5)
            self.assertIsNone(self.reason(process, error))

    def test_cancelled_subtitle_retry_does_not_clear_or_restart(self):
        self.process.setProperty('cancel_requested', True)
        with patch('src.core.downloader.invalidate_cached_youtube_pot') as clear:
            self.assertFalse(self.downloader._restart_process(self.process, 'subtitle_download'))
            clear.assert_not_called()

    def test_dns_during_subtitle_rescue_uses_subtitle_budget_and_refreshes(self):
        self.process.setProperty('subtitle_only_retry', True)
        self.process.setProperty('subtitle_retry_count', 4)
        self.process.setProperty('retry_count', 23)
        self.assertEqual(self.reason(self.process, 'ERROR: getaddrinfo failed'), 'dns_resolution')
        with patch('src.core.downloader.invalidate_cached_youtube_pot', return_value=(True, '')) as clear:
            self.assertTrue(self.downloader._restart_process(self.process, 'dns_resolution'))
        process = self.downloader.processes[0]
        self.assertEqual(process.property('subtitle_retry_count'), 5)
        self.assertEqual(process.property('retry_count'), 23)
        self.assertIn('--skip-download', process.args)
        clear.assert_called_once()
        process.setProperty('url', self.process.property('url'))
        self.assertIsNone(self.reason(process, 'ERROR: getaddrinfo failed'))


if __name__ == '__main__':
    unittest.main()
