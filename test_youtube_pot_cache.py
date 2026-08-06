import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.core.youtube_pot import (
    extract_youtube_video_id,
    invalidate_cached_youtube_pot,
    prewarm_youtube_pot,
)


class YouTubePoTokenCacheTests(unittest.TestCase):
    def test_extract_common_youtube_video_urls(self):
        video_id = "LaAt4KJO4Dk"
        urls = [
            video_id,
            f"https://www.youtube.com/watch?v={video_id}&t=10s",
            f"https://youtu.be/{video_id}",
            f"https://www.youtube.com/shorts/{video_id}",
            f"https://www.youtube.com/live/{video_id}",
            f"https://www.youtube.com/embed/{video_id}",
        ]

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(extract_youtube_video_id(url), video_id)

    def test_invalidate_only_target_video_cache(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            cache_dir = Path(temporary_dir)
            cache_path = cache_dir / "cache.json"
            cache_path.write_text(
                json.dumps({
                    "LaAt4KJO4Dk": {"poToken": "target", "expiresAt": "2099-01-01"},
                    "4vMxxo5Y8Jw": {"poToken": "keep", "expiresAt": "2099-01-01"},
                }),
                encoding="utf-8",
            )

            ok, message = invalidate_cached_youtube_pot("LaAt4KJO4Dk", cache_dir)

            self.assertTrue(ok, message)
            remaining = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertNotIn("LaAt4KJO4Dk", remaining)
            self.assertEqual(remaining["4vMxxo5Y8Jw"]["poToken"], "keep")

    def test_missing_cache_is_already_fresh(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            ok, message = invalidate_cached_youtube_pot(
                "LaAt4KJO4Dk",
                Path(temporary_dir),
            )

        self.assertTrue(ok, message)

    def test_invalid_cache_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            cache_dir = Path(temporary_dir)
            cache_path = cache_dir / "cache.json"
            cache_path.write_text("not-json", encoding="utf-8")

            ok, message = invalidate_cached_youtube_pot("LaAt4KJO4Dk", cache_dir)

            self.assertFalse(ok)
            self.assertIn("刷新 YouTube PO Token 缓存失败", message)
            self.assertEqual(cache_path.read_text(encoding="utf-8"), "not-json")

    def test_prewarm_runs_before_every_download_request(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root_dir = Path(temporary_dir)
            bin_dir = root_dir / "bin"
            server_dir = bin_dir / "bgutil-ytdlp-pot-provider" / "server"
            (server_dir / "src").mkdir(parents=True)
            (server_dir / "node_modules").mkdir()
            (bin_dir / "deno.exe").touch()
            (server_dir / "src" / "generate_once.ts").touch()
            cache_dir = root_dir / "cache"

            completed = SimpleNamespace(returncode=0, stdout="", stderr="")
            with (
                patch("src.core.youtube_pot._get_cache_dir", return_value=cache_dir),
                patch("src.core.youtube_pot.subprocess.run", return_value=completed) as run,
            ):
                first_ok, first_message = prewarm_youtube_pot(bin_dir)
                second_ok, second_message = prewarm_youtube_pot(bin_dir)

            self.assertTrue(first_ok, first_message)
            self.assertTrue(second_ok, second_message)
            self.assertEqual(run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
