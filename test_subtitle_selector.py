import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QApplication, QCheckBox, QMenu

from core.config import Config
from gui.subtitle_selector import SubtitleSelectorCheckBox


class DummyConfig:
    def __init__(self, values=None):
        self.config = dict(values or {})
        self.save_count = 0

    def save_config(self):
        self.save_count += 1


class SubtitleSelectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_fresh_config_defaults_to_english_only(self):
        config = DummyConfig()
        selector = SubtitleSelectorCheckBox("下载字幕", config)
        self.assertEqual(selector.selected_groups(), ("en",))
        self.assertFalse(selector.all_languages_selected())

    def test_all_languages_disables_named_groups_and_restores_them(self):
        config = DummyConfig({"subtitle_language_groups": ["en", "ja"]})
        selector = SubtitleSelectorCheckBox("下载字幕", config)
        menu = QMenu()
        actions = []
        for label in ("简体中文", "繁体中文", "英语", "日语", "韩语"):
            action = menu.addAction(label)
            action.setCheckable(True)
            actions.append(action)

        selector._set_all_languages(True, actions)
        self.assertTrue(selector.all_languages_selected())
        self.assertTrue(all(not action.isEnabled() for action in actions))
        self.assertTrue(all(not action.isChecked() for action in actions))

        selector._set_all_languages(False, actions)
        self.assertFalse(selector.all_languages_selected())
        self.assertTrue(all(action.isEnabled() for action in actions))
        self.assertTrue(actions[2].isChecked())
        self.assertTrue(actions[3].isChecked())

    def test_control_size_matches_original_layout(self):
        config = DummyConfig()
        ordinary = SubtitleSelectorCheckBox("下载字幕", config)
        playlist = SubtitleSelectorCheckBox("下载字幕(.srt格式)", config)
        self.assertEqual(ordinary.text(), "下载字幕")
        self.assertEqual(playlist.text(), "下载字幕(.srt格式)")
        self.assertGreater(ordinary.sizeHint().width(), QCheckBox("下载字幕").sizeHint().width())
        self.assertGreater(
            playlist.sizeHint().width(),
            QCheckBox("下载字幕(.srt格式)").sizeHint().width(),
        )

    def test_enabled_switch_is_shared_between_two_selectors(self):
        config = Config.__new__(Config)
        QObject.__init__(config)
        config.config = {
            "subtitle_download_enabled": False,
            "subtitle_language_groups": ["en"],
            "subtitle_all_languages": False,
        }
        config.save_config = lambda: None
        ordinary = SubtitleSelectorCheckBox("下载字幕", config)
        playlist = SubtitleSelectorCheckBox("下载字幕(.srt格式)", config)

        ordinary.setChecked(True)
        self.assertTrue(playlist.isChecked())

        playlist.setChecked(False)
        self.assertFalse(ordinary.isChecked())

    def test_playlist_subtitle_only_state_does_not_exist_in_ordinary_selector(self):
        config = DummyConfig({"subtitle_language_groups": ["en"]})
        ordinary = SubtitleSelectorCheckBox("下载字幕", config)
        playlist = SubtitleSelectorCheckBox(
            "下载字幕(.srt格式)",
            config,
            subtitle_only_config_key="playlist_subtitle_only",
        )

        playlist._set_subtitle_only(True)

        self.assertTrue(playlist.subtitle_only_selected())
        self.assertFalse(ordinary.subtitle_only_selected())
        self.assertTrue(config.config["playlist_subtitle_only"])


if __name__ == "__main__":
    unittest.main()
