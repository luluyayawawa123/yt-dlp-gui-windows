from PyQt6.QtCore import QPoint, QSignalBlocker, QSize, Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygon
from PyQt6.QtWidgets import QCheckBox, QMenu, QStyle

from core.subtitle_selection import (
    DEFAULT_SUBTITLE_GROUPS,
    SUBTITLE_GROUP_ORDER,
    SUBTITLE_GROUP_LABELS,
    normalize_subtitle_groups,
)


class PersistentCheckMenu(QMenu):
    """鼠标勾选多选项后保持展开，方便连续选择。"""

    def mouseReleaseEvent(self, event):
        action = self.actionAt(event.position().toPoint())
        if action and action.isEnabled() and action.isCheckable():
            action.setChecked(not action.isChecked())
            action.triggered.emit(action.isChecked())
            event.accept()
            return
        super().mouseReleaseEvent(event)


class SubtitleSelectorCheckBox(QCheckBox):
    """保持复选框原占位不变，并用浮动菜单选择字幕语言。"""

    _CONFIG_GROUPS = "subtitle_language_groups"
    _CONFIG_ALL = "subtitle_all_languages"
    _DROPDOWN_INDICATOR_WIDTH = 14

    def __init__(self, text, config, parent=None, subtitle_only_config_key=None):
        super().__init__(text, parent)
        self._config = config
        self._subtitle_only_config_key = subtitle_only_config_key
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ensure_config()
        self.setChecked(bool(self._config.config.get("subtitle_download_enabled", False)))
        self.toggled.connect(self._handle_enabled_toggled)
        if hasattr(self._config, "subtitle_enabled_changed"):
            self._config.subtitle_enabled_changed.connect(self._sync_enabled_state)
        if hasattr(self._config, "subtitle_options_changed"):
            self._config.subtitle_options_changed.connect(self._update_tooltip)
        self._update_tooltip()

    def selected_groups(self):
        return normalize_subtitle_groups(self._config.config.get(self._CONFIG_GROUPS))

    def all_languages_selected(self):
        return bool(self._config.config.get(self._CONFIG_ALL, False))

    def subtitle_only_selected(self):
        if not self._subtitle_only_config_key:
            return False
        return bool(self._config.config.get(self._subtitle_only_config_key, False))

    def mousePressEvent(self, event):
        indicator = self.style().subElementRect(
            QStyle.SubElement.SE_CheckBoxIndicator,
            self.styleOption(),
            self,
        )
        if event.button() == Qt.MouseButton.LeftButton and not indicator.contains(event.position().toPoint()):
            if not self.isChecked():
                self.setChecked(True)
            self._show_language_menu()
            event.accept()
            return
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        self._show_language_menu()
        event.accept()

    def enterEvent(self, event):
        # 两个窗口共用同一份配置；鼠标移入时重新读取，避免显示另一个窗口修改前的旧状态。
        self._update_tooltip()
        super().enterEvent(event)

    def styleOption(self):
        from PyQt6.QtWidgets import QStyleOptionButton

        option = QStyleOptionButton()
        self.initStyleOption(option)
        return option

    def sizeHint(self):
        size = super().sizeHint()
        return QSize(
            size.width() + self._DROPDOWN_INDICATOR_WIDTH,
            size.height(),
        )

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor("#5F6368" if self.isEnabled() else "#A0A0A0")
        painter.setPen(QPen(color, 1.4))
        center_y = self.height() // 2
        left = self.width() - 10
        painter.drawPolyline(QPolygon([
            QPoint(left, center_y - 2),
            QPoint(left + 4, center_y + 2),
            QPoint(left + 8, center_y - 2),
        ]))

    def _show_language_menu(self):
        self._update_tooltip()
        menu = PersistentCheckMenu(self)
        selected = set(self.selected_groups())
        all_languages = self.all_languages_selected()

        labels = {
            "zh_hans": "简体中文",
            "zh_hant": "繁体中文（优先台湾）",
            "en": "英语（优先美国）",
            "ja": "日语",
            "ko": "韩语",
        }
        group_actions = []
        for group in SUBTITLE_GROUP_ORDER:
            action = menu.addAction(labels[group])
            action.setCheckable(True)
            action.setChecked(group in selected and not all_languages)
            action.setEnabled(not all_languages)
            action.triggered.connect(
                lambda checked, value=group: self._set_group_enabled(value, checked)
            )
            group_actions.append(action)

        menu.addSeparator()
        all_action = menu.addAction("全部其他可用字幕")
        all_action.setCheckable(True)
        all_action.setChecked(all_languages)
        all_action.triggered.connect(
            lambda checked: self._set_all_languages(checked, group_actions)
        )

        if self._subtitle_only_config_key:
            menu.addSeparator()
            subtitle_only_action = menu.addAction("仅下载字幕，不下载视频")
            subtitle_only_action.setCheckable(True)
            subtitle_only_action.setChecked(self.subtitle_only_selected())
            subtitle_only_action.triggered.connect(self._set_subtitle_only)

        menu.addSeparator()
        reset_action = menu.addAction("恢复默认选择")
        reset_action.triggered.connect(self._restore_defaults)
        menu.exec(self.mapToGlobal(QPoint(0, self.height())))

    def _set_group_enabled(self, group, checked):
        selected = set(self.selected_groups())
        if checked:
            selected.add(group)
        else:
            selected.discard(group)
        self._config.config[self._CONFIG_GROUPS] = list(
            normalize_subtitle_groups(selected)
        )
        self._config.config[self._CONFIG_ALL] = False
        if checked:
            self.setChecked(True)
        elif not selected and not self.all_languages_selected():
            self.setChecked(False)
        self._save()

    def _set_all_languages(self, checked, group_actions=None):
        self._config.config[self._CONFIG_ALL] = bool(checked)
        selected = set(self.selected_groups())
        for action, group in zip(group_actions or (), SUBTITLE_GROUP_ORDER):
            action.setEnabled(not checked)
            action.setChecked(group in selected and not checked)
        if checked:
            self.setChecked(True)
        elif not self.selected_groups():
            self.setChecked(False)
        self._save()

    def _restore_defaults(self):
        self._config.config[self._CONFIG_GROUPS] = list(DEFAULT_SUBTITLE_GROUPS)
        self._config.config[self._CONFIG_ALL] = False
        if self._subtitle_only_config_key:
            self._config.config[self._subtitle_only_config_key] = False
        self._save()

    def _set_subtitle_only(self, checked):
        if not self._subtitle_only_config_key:
            return
        self._config.config[self._subtitle_only_config_key] = bool(checked)
        if checked:
            self.setChecked(True)
        self._save()

    def _ensure_config(self):
        raw_groups = self._config.config.get(self._CONFIG_GROUPS)
        if raw_groups is None:
            self._config.config[self._CONFIG_GROUPS] = list(DEFAULT_SUBTITLE_GROUPS)
        else:
            self._config.config[self._CONFIG_GROUPS] = list(
                normalize_subtitle_groups(raw_groups)
            )
        self._config.config.setdefault(self._CONFIG_ALL, False)
        if self._subtitle_only_config_key:
            self._config.config.setdefault(self._subtitle_only_config_key, False)

    def _save(self):
        self._config.save_config()
        if hasattr(self._config, "notify_subtitle_options_changed"):
            self._config.notify_subtitle_options_changed()
        self._update_tooltip()

    def _handle_enabled_toggled(self, enabled):
        if hasattr(self._config, "set_subtitle_enabled"):
            self._config.set_subtitle_enabled(enabled)
            return
        self._config.config["subtitle_download_enabled"] = bool(enabled)
        self._config.save_config()

    def _sync_enabled_state(self, enabled):
        blocker = QSignalBlocker(self)
        self.setChecked(bool(enabled))
        del blocker

    def _update_tooltip(self):
        if self.all_languages_selected():
            summary = "全部其他可用字幕"
        else:
            summary = "、".join(
                SUBTITLE_GROUP_LABELS[group] for group in self.selected_groups()
            ) or "未选择语言"
        self.setToolTip(
            f"当前：{summary}"
            f"{'；仅下载字幕' if self.subtitle_only_selected() else ''}\n"
            "点击文字选择语言；点击方框启用或关闭字幕下载。"
        )
