import json
import os
import tempfile
import unittest

from src.core.playlist_download import (
    PLAYLIST_CLIENT,
    SUBTITLE_ONLY_MAX_ATTEMPTS,
    build_playlist_item_args,
    parse_playlist_metadata,
    playlist_client_requires_cookies,
    playlist_client_requires_pot,
    safe_playlist_folder_name,
    should_retry_subtitle_only_failure,
)
from src.core.subtitle_selection import build_subtitle_only_retry_args


class PlaylistDownloadTests(unittest.TestCase):
    def setUp(self):
        payload = {
            "id": "PL123",
            "title": "Running: Education/Series",
            "entries": [
                {"id": "LaAt4KJO4Dk", "title": "Part 15", "url": "LaAt4KJO4Dk"},
                {"id": "4vMxxo5Y8Jw", "title": "Part 14", "webpage_url": "https://youtu.be/4vMxxo5Y8Jw"},
            ],
        }
        self.metadata = parse_playlist_metadata(json.dumps(payload))

    def test_parse_playlist_metadata(self):
        self.assertEqual(self.metadata.title, "Running: Education/Series")
        self.assertEqual(len(self.metadata.items), 2)
        self.assertEqual(
            self.metadata.items[0].url,
            "https://www.youtube.com/watch?v=LaAt4KJO4Dk",
        )

    def test_fixed_client(self):
        self.assertEqual(PLAYLIST_CLIENT, "mweb")
        self.assertTrue(playlist_client_requires_pot())
        self.assertTrue(playlist_client_requires_cookies())
        self.assertTrue(playlist_client_requires_pot("mweb"))
        self.assertTrue(playlist_client_requires_pot("web_creator"))
        self.assertTrue(playlist_client_requires_cookies("mweb"))
        self.assertTrue(playlist_client_requires_cookies("web_creator"))

    def test_mweb_args_use_provider_with_firefox_cookies(self):
        item = self.metadata.items[0]
        with tempfile.TemporaryDirectory() as pot_home:
            args = build_playlist_item_args(item, ["-f", "bv*+ba"], "out", pot_home)

        self.assertIn("--cookies-from-browser", args)
        cookies_index = args.index("--cookies-from-browser")
        self.assertEqual(args[cookies_index + 1], "firefox")
        self.assertTrue(any("server_home=" in arg for arg in args))
        self.assertIn("youtube:player_client=mweb", args)
        self.assertNotIn("youtube:player_client=android_vr", args)
        self.assertNotIn("youtube:player_client=web_creator", args)

    def test_item_args_accept_exact_subtitle_languages(self):
        item = self.metadata.items[0]
        args = build_playlist_item_args(
            item,
            ["-f", "bv*+ba"],
            "out",
            "",
            subtitle_args=[
                "--write-subs",
                "--sub-langs",
                "zh-CN,zh-TW,en-US,ja-JP,ko-KR",
                "--convert-subs",
                "srt",
            ],
        )
        self.assertIn("--write-subs", args)
        language_index = args.index("--sub-langs")
        self.assertEqual(
            args[language_index + 1],
            "zh-CN,zh-TW,en-US,ja-JP,ko-KR",
        )

    def test_safe_folder_name(self):
        self.assertEqual(
            safe_playlist_folder_name(self.metadata.title, self.metadata.playlist_id),
            "Running_ Education_Series",
        )

    def test_subtitle_only_mode_retries_recoverable_failures_six_times(self):
        self.assertEqual(SUBTITLE_ONLY_MAX_ATTEMPTS, 6)
        self.assertTrue(should_retry_subtitle_only_failure("subtitle_download", 0))
        self.assertTrue(should_retry_subtitle_only_failure("pot_generation", 4))
        self.assertFalse(should_retry_subtitle_only_failure("subtitle_download", 5))
        self.assertFalse(should_retry_subtitle_only_failure("login_required", 0))

    def test_subtitle_only_args_keep_auth_but_remove_media_download(self):
        item = self.metadata.items[0]
        args = build_playlist_item_args(
            item,
            ["-f", "bv*+ba", "--no-overwrites"],
            "out/%(title)s.%(ext)s",
            "",
            subtitle_args=["--write-subs", "--sub-langs", "en-US"],
        )

        subtitle_only_args = build_subtitle_only_retry_args(args)

        self.assertIn("--skip-download", subtitle_only_args)
        self.assertIn("--write-subs", subtitle_only_args)
        self.assertIn("--cookies-from-browser", subtitle_only_args)
        self.assertNotIn("-f", subtitle_only_args)
        self.assertNotIn("bv*+ba", subtitle_only_args)

if __name__ == "__main__":
    unittest.main()
