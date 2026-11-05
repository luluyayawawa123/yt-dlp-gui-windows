import unittest

from PyQt6.QtCore import QObject

from src.core.config import Config


def make_config(values):
    config = Config.__new__(Config)
    QObject.__init__(config)
    config.config = dict(values)
    config.save_count = 0

    def save_config():
        config.save_count += 1

    config.save_config = save_config
    return config


class SettingsSyncTests(unittest.TestCase):
    def test_common_quality_updates_both_saved_indices_and_emits(self):
        config = make_config({"quality_index": 1, "main_quality_index": 6})
        received = []
        config.quality_index_changed.connect(received.append)

        config.set_quality_index(3)

        self.assertEqual(config.config["quality_index"], 3)
        self.assertEqual(config.config["main_quality_index"], 3)
        self.assertEqual(received, [3])

    def test_landlord_mode_does_not_replace_playlist_quality(self):
        config = make_config({"quality_index": 2, "main_quality_index": 2})
        received = []
        config.quality_index_changed.connect(received.append)

        config.set_main_quality_index(6)

        self.assertEqual(config.config["quality_index"], 2)
        self.assertEqual(config.config["main_quality_index"], 6)
        self.assertEqual(received, [])

    def test_subtitle_enabled_state_emits_only_when_changed(self):
        config = make_config({"subtitle_download_enabled": False})
        received = []
        config.subtitle_enabled_changed.connect(received.append)

        config.set_subtitle_enabled(True)
        config.set_subtitle_enabled(True)

        self.assertTrue(config.config["subtitle_download_enabled"])
        self.assertEqual(received, [True])


if __name__ == "__main__":
    unittest.main()
