import unittest

from src.core.youtube_recovery import (
    MAX_YOUTUBE_RECOVERY_RETRIES,
    MAX_SUBTITLE_RECOVERY_RETRIES,
    classify_youtube_failure,
    extract_failure_detail,
    failure_advice,
    recovery_total_attempts,
    should_retry_youtube_failure,
)


class YouTubeRecoveryTests(unittest.TestCase):
    def test_media_403_is_recoverable_until_limit(self):
        error = """
        Invoking http downloader on https://rr1.example.googlevideo.com/videoplayback
        ERROR: unable to download video data: HTTP Error 403: Forbidden
        """
        reason = classify_youtube_failure("", error)

        self.assertEqual(reason, "media_403")
        self.assertTrue(should_retry_youtube_failure(reason, 0))
        self.assertFalse(
            should_retry_youtube_failure(reason, MAX_YOUTUBE_RECOVERY_RETRIES)
        )
        self.assertEqual(recovery_total_attempts(reason), 6)

    def test_dns_failure_is_recoverable(self):
        reason = classify_youtube_failure(
            "",
            "Failed to resolve host ([Errno 11002] getaddrinfo failed)",
        )

        self.assertEqual(reason, "dns_resolution")
        self.assertTrue(should_retry_youtube_failure(reason, 0))

    def test_login_required_is_not_retried_and_has_advice(self):
        reason = classify_youtube_failure(
            "",
            "ERROR: LOGIN_REQUIRED: Sign in to confirm you’re not a bot",
        )

        self.assertEqual(reason, "login_required")
        self.assertFalse(should_retry_youtube_failure(reason, 0))
        self.assertIn("Firefox", failure_advice(reason))

    def test_pot_failure_after_progress_is_not_retried(self):
        reason = classify_youtube_failure(
            "",
            "Error fetching PO Token: Failed to generate an integrity token",
        )

        self.assertEqual(reason, "pot_generation")
        self.assertTrue(should_retry_youtube_failure(reason, 0, False))
        self.assertFalse(should_retry_youtube_failure(reason, 0, True))

    def test_format_failure_is_not_retried_and_has_advice(self):
        reason = classify_youtube_failure(
            "",
            "ERROR: Requested format is not available",
        )

        self.assertEqual(reason, "format_unavailable")
        self.assertFalse(should_retry_youtube_failure(reason, 0))
        self.assertIn("画质", failure_advice(reason))

    def test_empty_subtitle_response_is_recoverable(self):
        output = "[info] Writing video subtitles to: example.zh-Hans.vtt"
        error = """
        ERROR: Did not get any data blocks
        File "yt_dlp\\YoutubeDL.py", line 4400, in _write_subtitles
        """
        reason = classify_youtube_failure(output, error)

        self.assertEqual(reason, "subtitle_download")
        self.assertTrue(should_retry_youtube_failure(reason, 0))
        self.assertFalse(
            should_retry_youtube_failure(reason, MAX_SUBTITLE_RECOVERY_RETRIES)
        )
        self.assertEqual(recovery_total_attempts(reason), 2)

    def test_empty_media_response_is_not_misclassified_as_subtitle(self):
        reason = classify_youtube_failure(
            "[download] Destination: example.mp4",
            "ERROR: Did not get any data blocks",
        )

        self.assertIsNone(reason)

    def test_last_error_is_used_for_failure_detail(self):
        output = "Extracting cookies from firefox\nERROR: first error"
        error = "ERROR: Did not get any data blocks\nTraceback detail"

        self.assertEqual(
            extract_failure_detail(output, error),
            "Did not get any data blocks",
        )


if __name__ == "__main__":
    unittest.main()
