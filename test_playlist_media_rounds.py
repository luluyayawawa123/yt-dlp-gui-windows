"""播放列表自动恢复的离线回归；不联网，不替代真实下载验证。"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent / "src"))

from gui.playlist_window import PlaylistWindow


class FakeLabel:
    def setText(self, value):
        self.text = value


class FakeWindow:
    download_finished = PlaylistWindow.download_finished
    _media_attempt_context = PlaylistWindow._media_attempt_context
    _restart_playlist_item = PlaylistWindow._restart_playlist_item
    _advance_playlist_item = PlaylistWindow._advance_playlist_item

    def __init__(self):
        self._cancel_requested = False
        self._media_round = self._media_attempt = 1
        self._item_recovery_count = self._subtitle_recovery_count = 0
        self._process_subtitle_only = self._process_is_subtitle_retry = False
        self._saw_download_progress = True
        self._active_download_start = {"subtitle_only_mode": False}
        self._playlist_metadata = SimpleNamespace(items=[
            SimpleNamespace(video_id="LaAt4KJO4Dk", title="Example"),
            SimpleNamespace(video_id="4vMxxo5Y8Jw", title="Next"),
        ])
        self._playlist_item_index = 0
        self._last_process_output = ""
        self._last_process_error = "ERROR: unable to download video data: HTTP Error 403"
        self.status_label = FakeLabel()
        self.logs = []
        self.starts = []
        self.states = {}
        self.failures = []
        self.finished = False

    def _flush_stream_buffers(self):
        pass

    def _ensure_item_state(self, video_id, title=None):
        return self.states.setdefault(video_id, {})

    def _set_subtitle_status(self, video_id, status):
        self._ensure_item_state(video_id)["subtitle_status"] = status

    def _append_output_log(self, message):
        self.logs.append(message)

    def _start_active_download_process(self, **kwargs):
        self.starts.append(kwargs)

    def _mark_item_failed(self, *args):
        self.failures.append(args)

    def _mark_item_completed(self, video_id, **kwargs):
        self._ensure_item_state(video_id)["video_status"] = "ok"

    def _format_failure_reason(self, state):
        return "媒体下载被拒绝"

    def _finish_playlist_download(self, **kwargs):
        self.finished = True


class PlaylistMediaRoundTests(unittest.TestCase):
    def setUp(self):
        self.window = FakeWindow()
        self.callbacks = []
        self.timer = patch(
            "gui.playlist_window.QTimer.singleShot",
            side_effect=lambda delay, callback: self.callbacks.append(callback),
        )
        self.timer.start()
        self.addCleanup(self.timer.stop)

    def fail(self):
        self.window.download_finished(1, None)

    def test_24_attempts_refresh_only_at_five_round_boundaries(self):
        states = [(1, 1)]
        for _ in range(23):
            self.fail()
            self.assertEqual(len(self.callbacks), 1)
            self.callbacks.pop()()
            states.append((self.window._media_round, self.window._media_attempt))
        self.assertEqual(states, [(r, a) for r in range(1, 7) for a in range(1, 5)])
        refreshes = [i + 2 for i, args in enumerate(self.window.starts)
                     if args["refresh_pot_cache"]]
        self.assertEqual(refreshes, [5, 9, 13, 17, 21])
        self.assertTrue(all(not args["subtitle_only"] for args in self.window.starts))
        self.assertEqual(self.window._item_recovery_count, 0)
        self.assertIn("第6/6轮 第4/4次", self.window.status_label.text)
        self.fail()
        self.assertFalse(self.callbacks)
        self.assertEqual(len(self.window.failures), 1)
        self.assertEqual(self.window._playlist_item_index, 1)
        self.assertEqual((self.window._media_round, self.window._media_attempt), (1, 1))
        self.assertIn("第6/6轮 第4/4次失败", self.window.logs[-2])

    def test_success_after_recovery_advances_and_resets_rounds(self):
        self.window._media_round, self.window._media_attempt = 3, 2
        self.window.download_finished(0, None)
        self.assertEqual(self.window._playlist_item_index, 1)
        self.assertEqual((self.window._media_round, self.window._media_attempt), (1, 1))
        self.assertEqual(self.window.states["LaAt4KJO4Dk"]["video_status"], "ok")
        self.assertFalse(self.window.failures)
        self.assertEqual(len(self.window.starts), 1)

    def test_cancelled_callback_does_not_restart(self):
        self.fail()
        self.window._cancel_requested = True
        self.callbacks.pop()()
        self.assertFalse(self.window.starts)

    def test_old_task_callback_does_not_restart_new_task(self):
        self.fail()
        self.window._active_download_start = {"subtitle_only_mode": False}
        self.callbacks.pop()()
        self.assertFalse(self.window.starts)

    def test_old_item_callback_does_not_restart_next_item(self):
        self.fail()
        self.window._playlist_item_index = 1
        self.callbacks.pop()()
        self.assertFalse(self.window.starts)

    def test_dns_retains_six_attempt_limit_and_does_not_refresh_token(self):
        self.window._last_process_error = "ERROR: getaddrinfo failed"
        self.window._item_recovery_count = 4
        self.fail()
        self.callbacks.pop()()
        self.assertFalse(self.window.starts[-1]["refresh_pot_cache"])
        self.assertEqual((self.window._media_round, self.window._media_attempt), (1, 1))
        self.fail()
        self.assertFalse(self.callbacks)
        self.assertEqual(len(self.window.failures), 1)

    def test_subtitle_only_retains_six_attempts_refreshing_every_retry(self):
        self.window._active_download_start["subtitle_only_mode"] = True
        self.window._process_subtitle_only = True
        for _ in range(5):
            self.fail()
            self.callbacks.pop()()
        self.assertEqual(len(self.window.starts), 5)
        self.assertTrue(all(args["refresh_pot_cache"] and args["subtitle_only"]
                            for args in self.window.starts))
        self.assertEqual((self.window._media_round, self.window._media_attempt), (1, 1))
        self.fail()
        self.assertFalse(self.callbacks)

    def test_subtitle_rescue_does_not_gain_media_rounds(self):
        self.window._process_is_subtitle_retry = True
        self.window._process_subtitle_only = True
        self.fail()
        self.assertFalse(self.callbacks)
        self.assertEqual(len(self.window.failures), 1)

    def test_login_stops_playlist_without_retry(self):
        self.window._last_process_error = "ERROR: Sign in to confirm you're not a bot"
        self.fail()
        self.assertFalse(self.callbacks)
        self.assertTrue(self.window.finished)
        self.assertEqual(self.window._playlist_item_index, 0)

    def test_cache_refresh_failure_stops_before_starting_process(self):
        self.window._active_download_start["write_subtitles"] = False
        with (
            patch("gui.playlist_window.invalidate_cached_youtube_pot",
                  return_value=(False, "缓存写入失败")) as clear,
            patch("gui.playlist_window.QMessageBox.critical"),
        ):
            PlaylistWindow._start_active_download_process(self.window, refresh_pot_cache=True)
        clear.assert_called_once_with("LaAt4KJO4Dk")
        self.assertTrue(self.window.finished)
        self.assertFalse(self.window.starts)
        self.assertEqual(self.window.failures[0][1], "pot_cache_refresh_failed")


if __name__ == "__main__":
    unittest.main()
