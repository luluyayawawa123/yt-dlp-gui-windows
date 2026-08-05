import json
import os
import tempfile
import unittest

from src.core.playlist_download import (
    PLAYLIST_CLIENT,
    build_playlist_item_args,
    parse_playlist_metadata,
    playlist_client_requires_pot,
    safe_playlist_folder_name,
)


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
        self.assertEqual(PLAYLIST_CLIENT, "android_vr")
        self.assertFalse(playlist_client_requires_pot())
        self.assertTrue(playlist_client_requires_pot("mweb"))
        self.assertTrue(playlist_client_requires_pot("web_creator"))

    def test_android_vr_args_exclude_cookies_and_provider(self):
        item = self.metadata.items[0]
        with tempfile.TemporaryDirectory() as pot_home:
            args = build_playlist_item_args(item, ["-f", "bv*+ba"], "out", pot_home)

        self.assertNotIn("--cookies-from-browser", args)
        self.assertFalse(any("server_home=" in arg for arg in args))
        self.assertIn("youtube:player_client=android_vr", args)
        self.assertNotIn("youtube:player_client=mweb", args)
        self.assertNotIn("youtube:player_client=web_creator", args)

    def test_safe_folder_name(self):
        self.assertEqual(
            safe_playlist_folder_name(self.metadata.title, self.metadata.playlist_id),
            "Running_ Education_Series",
        )

if __name__ == "__main__":
    unittest.main()
