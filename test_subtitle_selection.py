import json
import unittest

from src.core.subtitle_selection import (
    DEFAULT_SUBTITLE_GROUPS,
    SUBTITLE_GROUP_ORDER,
    build_subtitle_download_args,
    build_subtitle_only_retry_args,
    normalize_subtitle_groups,
    parse_subtitle_metadata,
    select_subtitle_languages,
)


class SubtitleSelectionTests(unittest.TestCase):
    def test_default_group_is_english(self):
        self.assertEqual(DEFAULT_SUBTITLE_GROUPS, ("en",))
        self.assertEqual(
            SUBTITLE_GROUP_ORDER,
            ("zh_hans", "zh_hant", "en", "ja", "ko"),
        )

    def test_each_group_selects_only_one_preferred_author_subtitle(self):
        subtitles = {
            "zh-Hans": [],
            "zh-CN": [],
            "zh-HK": [],
            "zh-TW": [],
            "en-GB": [],
            "en-US": [],
            "ja": [],
            "ja-JP": [],
            "ko": [],
            "ko-KR": [],
        }
        result = select_subtitle_languages(
            subtitles,
            {},
            SUBTITLE_GROUP_ORDER,
        )
        self.assertEqual(
            result.languages,
            ("zh-CN", "zh-TW", "en-US", "ja-JP", "ko-KR"),
        )

    def test_author_subtitle_wins_over_automatic_caption(self):
        result = select_subtitle_languages(
            {"en-GB": []},
            {"en-US": []},
            ["en"],
            allow_automatic=True,
        )
        self.assertEqual(result.languages, ("en-GB",))
        self.assertIn("作者字幕", result.messages[0])

    def test_automatic_caption_is_used_only_as_fallback(self):
        result = select_subtitle_languages(
            {},
            {"ja": [], "ko": []},
            ["ja", "ko"],
            allow_automatic=True,
        )
        self.assertEqual(result.languages, ("ja", "ko"))
        self.assertTrue(all("自动字幕" in message for message in result.messages))

    def test_metadata_and_download_args(self):
        subtitles, automatic = parse_subtitle_metadata(json.dumps({
            "subtitles": {"zh-CN": []},
            "automatic_captions": {"en": []},
        }))
        self.assertIn("zh-CN", subtitles)
        self.assertIn("en", automatic)
        self.assertEqual(
            build_subtitle_download_args(["zh-CN", "en"]),
            ["--write-subs", "--sub-langs", "zh-CN,en", "--convert-subs", "srt"],
        )

    def test_group_order_is_stable(self):
        self.assertEqual(
            normalize_subtitle_groups(["ko", "en", "unknown"]),
            ("en", "ko"),
        )

    def test_all_languages_download_args(self):
        self.assertEqual(
            build_subtitle_download_args(all_languages=True),
            ["--write-subs", "--sub-langs", "all", "--convert-subs", "srt"],
        )

    def test_subtitle_retry_args_skip_media_only_options(self):
        original = [
            "yt-dlp.exe",
            "--progress",
            "-f",
            "bv*+ba",
            "-x",
            "--audio-format",
            "mp3",
            "--write-subs",
            "--sub-langs",
            "zh-Hans",
            "--convert-subs",
            "srt",
            "-o",
            "%(title)s.%(ext)s",
            "https://www.youtube.com/watch?v=abcdefghijk",
        ]

        retry_args = build_subtitle_only_retry_args(original)

        self.assertIn("--skip-download", retry_args)
        self.assertIn("--write-subs", retry_args)
        self.assertIn("zh-Hans", retry_args)
        self.assertNotIn("-f", retry_args)
        self.assertNotIn("bv*+ba", retry_args)
        self.assertNotIn("-x", retry_args)
        self.assertNotIn("--audio-format", retry_args)

    def test_subtitle_retry_args_keep_playlist_output_pair(self):
        original = [
            "https://www.youtube.com/watch?v=abcdefghijk",
            "-f",
            "bv*+ba",
            "--write-subs",
            "--sub-langs",
            "en-US",
            "-o",
            "playlist/%(title)s.%(ext)s",
        ]

        retry_args = build_subtitle_only_retry_args(original)

        output_index = retry_args.index("-o")
        self.assertEqual(retry_args[output_index + 1], "playlist/%(title)s.%(ext)s")
        self.assertEqual(retry_args[0], "--skip-download")
        self.assertEqual(retry_args[1], original[0])


if __name__ == "__main__":
    unittest.main()
