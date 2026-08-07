import tempfile
import unittest

from src.core.downloader import Downloader


class _FakeProcess:
    def __init__(self):
        self.program = None
        self.arguments = None

    def start(self, program, arguments):
        self.program = program
        self.arguments = list(arguments)


class _FakeRecoveryProcess:
    def __init__(self, **properties):
        self.properties = properties

    def property(self, name):
        return self.properties.get(name)


class YouTubeDownloadConfigTests(unittest.TestCase):
    def setUp(self):
        self.downloader = Downloader()
        self.downloader._check_browser_available = lambda browser: browser == "firefox"
        self.downloader._check_yt_dlp_available = lambda: True
        self.fake_process = _FakeProcess()
        self.downloader._create_download_process = lambda **kwargs: self.fake_process

    def test_normal_download_uses_mweb_with_firefox_cookies(self):
        with tempfile.TemporaryDirectory() as output_path:
            started = self.downloader.start_download(
                "https://www.youtube.com/watch?v=rY65wFcjdDM",
                output_path,
                {"format": "bv*+ba"},
                "firefox",
            )

        self.assertTrue(started)
        args = self.fake_process.arguments
        self.assertIn("--cookies-from-browser", args)
        cookies_index = args.index("--cookies-from-browser")
        self.assertEqual(args[cookies_index + 1], "firefox")
        self.assertIn("youtube:player_client=mweb", args)
        self.assertTrue(any("youtubepot-bgutilscript:server_home=" in arg for arg in args))
        self.assertNotIn("youtube:player_client=android_vr", args)
        self.assertTrue(
            self.downloader.get_platform_config("youtube")["requires_pot_prewarm"]
        )

    def test_hls_fallback_uses_web_safari_with_cookies_without_pot(self):
        with tempfile.TemporaryDirectory() as output_path:
            started = self.downloader.start_download(
                "https://www.youtube.com/watch?v=LaAt4KJO4Dk",
                output_path,
                {
                    "format": "b[height<=1080][protocol^=m3u8]",
                    "youtube_hls_fallback": True,
                    "writesubtitles": True,
                },
                "firefox",
            )

        self.assertTrue(started)
        args = self.fake_process.arguments
        self.assertIn("youtube:player_client=web_safari", args)
        self.assertIn("--cookies-from-browser", args)
        cookies_index = args.index("--cookies-from-browser")
        self.assertEqual(args[cookies_index + 1], "firefox")
        self.assertIn("--no-plugin-dirs", args)
        self.assertFalse(any("youtubepot-bgutilscript:server_home=" in arg for arg in args))
        format_index = args.index("-f")
        self.assertEqual(args[format_index + 1], "b[height<=1080][protocol^=m3u8]")
        self.assertIn("--write-subs", args)
        self.assertIn("--write-auto-subs", args)

    def test_normal_download_does_not_request_automatic_subtitles(self):
        with tempfile.TemporaryDirectory() as output_path:
            started = self.downloader.start_download(
                "https://www.youtube.com/watch?v=rY65wFcjdDM",
                output_path,
                {"format": "bv*+ba", "writesubtitles": True},
                "firefox",
            )

        self.assertTrue(started)
        args = self.fake_process.arguments
        self.assertIn("--write-subs", args)
        self.assertNotIn("--write-auto-subs", args)

    def test_healthy_verbose_pot_log_is_not_classified_as_failure(self):
        output = """
        [debug] PO Token Providers: bgutil:script-deno
        [youtube] Generating a gvs PO Token for mweb client via bgutil script
        [youtube] Retrieved a gvs PO Token for mweb client
        """

        self.assertIsNone(self.downloader._classify_youtube_failure(output, ""))

    def test_googlevideo_403_is_classified_separately(self):
        error = """
        Invoking http downloader on https://rr1---sn.example.googlevideo.com/videoplayback
        ERROR: unable to download video data: HTTP Error 403: Forbidden
        """

        self.assertEqual(
            self.downloader._classify_youtube_failure("", error),
            "media_403",
        )

    def test_dns_resolution_failure_is_classified_separately(self):
        error = """
        Failed to resolve 'rr1---sn.example.googlevideo.com'
        ([Errno 11002] getaddrinfo failed)
        """

        self.assertEqual(
            self.downloader._classify_youtube_failure("", error),
            "dns_resolution",
        )

    def test_pot_startup_timeout_is_classified_separately(self):
        error = """
        Command ['deno.exe', 'run', 'generate_once.ts', '--version']
        timed out after 15.0 seconds
        subprocess.TimeoutExpired
        """

        self.assertEqual(
            self.downloader._classify_youtube_failure("", error),
            "pot_startup",
        )

    def test_googlevideo_403_can_recover_after_download_progress(self):
        process = _FakeRecoveryProcess(
            cancel_requested=False,
            url="https://www.youtube.com/watch?v=b542UIppS80",
            retry_count=0,
            saw_download_progress=True,
        )
        error = """
        Invoking http downloader on https://rr1---sn.example.googlevideo.com/videoplayback
        ERROR: unable to download video data: HTTP Error 403: Forbidden
        """

        self.assertEqual(
            self.downloader._get_youtube_recovery_reason(process, "", error),
            "media_403",
        )


if __name__ == "__main__":
    unittest.main()
