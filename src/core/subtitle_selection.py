import json
from dataclasses import dataclass
from typing import Iterable, Mapping


SUBTITLE_GROUP_ORDER = (
    "zh_hans",
    "zh_hant",
    "en",
    "ja",
    "ko",
)

DEFAULT_SUBTITLE_GROUPS = ("en",)

SUBTITLE_GROUP_LABELS = {
    "zh_hans": "简体中文",
    "zh_hant": "繁体中文",
    "en": "英语",
    "ja": "日语",
    "ko": "韩语",
}

_EXACT_PRIORITIES = {
    "zh_hans": ("zh-cn", "zh-hans", "zh-sg", "zh"),
    "zh_hant": ("zh-tw", "zh-hant-tw", "zh-hant", "zh-hk", "zh-hant-hk", "zh-mo"),
    "en": ("en-us", "en", "en-orig", "en-gb"),
    "ja": ("ja-jp", "ja", "ja-orig"),
    "ko": ("ko-kr", "ko", "ko-orig"),
}


@dataclass(frozen=True)
class SubtitleSelection:
    languages: tuple[str, ...]
    messages: tuple[str, ...]


def normalize_subtitle_groups(groups: Iterable[str] | None) -> tuple[str, ...]:
    """过滤未知项并保持界面中的固定显示顺序。"""
    selected = set(groups or ())
    return tuple(group for group in SUBTITLE_GROUP_ORDER if group in selected)


def parse_subtitle_metadata(payload: str) -> tuple[Mapping[str, object], Mapping[str, object]]:
    """从 yt-dlp JSON 中读取作者字幕与自动字幕。"""
    data = json.loads(payload)
    subtitles = data.get("subtitles") or {}
    automatic = data.get("automatic_captions") or {}
    if not isinstance(subtitles, dict):
        subtitles = {}
    if not isinstance(automatic, dict):
        automatic = {}
    return subtitles, automatic


def select_subtitle_languages(
    subtitles: Mapping[str, object],
    automatic_captions: Mapping[str, object],
    groups: Iterable[str],
    allow_automatic: bool = False,
) -> SubtitleSelection:
    """每个语言组只选一个最优标签，作者字幕优先于自动字幕。"""
    selected_languages = []
    messages = []

    for group in normalize_subtitle_groups(groups):
        language = _pick_language(subtitles, group)
        source = "作者字幕"
        if language is None and allow_automatic:
            language = _pick_language(automatic_captions, group)
            source = "自动字幕"

        label = SUBTITLE_GROUP_LABELS[group]
        if language is None:
            messages.append(f"未找到{label}字幕，已跳过")
            continue

        selected_languages.append(language)
        messages.append(f"{label}：{language}（{source}）")

    return SubtitleSelection(tuple(selected_languages), tuple(messages))


def build_subtitle_probe_args(
    url: str,
    special_args: Iterable[str] = (),
    browser: str | None = None,
) -> list[str]:
    """构建只读取元数据、不下载媒体的 yt-dlp 参数。"""
    args = [
        "--dump-single-json",
        "--skip-download",
        "--no-playlist",
        "--encoding",
        "utf-8",
        *special_args,
    ]
    if browser:
        args.extend(["--cookies-from-browser", browser])
    args.append(url)
    return args


def build_subtitle_download_args(
    languages: Iterable[str] | None = None,
    *,
    all_languages: bool = False,
    allow_automatic: bool = False,
) -> list[str]:
    """构建最终字幕下载参数。"""
    args = ["--write-subs"]
    if allow_automatic:
        args.append("--write-auto-subs")

    if all_languages:
        language_value = "all"
    else:
        language_value = ",".join(language for language in (languages or ()) if language)
        if not language_value:
            return []

    args.extend(["--sub-langs", language_value, "--convert-subs", "srt"])
    return args


def build_subtitle_only_retry_args(command_args: Iterable[str]) -> list[str]:
    """把原下载命令收窄为仅补字幕，保留客户端、Cookies 与字幕选择。"""
    args = list(command_args)
    if not args:
        return []

    options_with_value = {
        "-f",
        "--format",
        "--audio-format",
        "--audio-quality",
        "--postprocessor-args",
    }
    media_only_flags = {"-x", "--extract-audio"}
    filtered = []
    index = 0
    while index < len(args):
        value = args[index]
        if value in options_with_value:
            index += 2
            continue
        if value in media_only_flags:
            index += 1
            continue
        filtered.append(value)
        index += 1

    if "--skip-download" not in filtered:
        url_index = next(
            (
                index
                for index, value in enumerate(filtered)
                if str(value).startswith(("https://", "http://"))
            ),
            len(filtered),
        )
        filtered.insert(url_index, "--skip-download")
    return filtered


def _pick_language(available: Mapping[str, object], group: str) -> str | None:
    if not available:
        return None

    normalized_to_original = {}
    for original in available:
        normalized = str(original).strip().lower().replace("_", "-")
        if normalized:
            normalized_to_original.setdefault(normalized, str(original))

    for preferred in _EXACT_PRIORITIES[group]:
        if preferred in normalized_to_original:
            return normalized_to_original[preferred]

    candidates = [
        (normalized, original)
        for normalized, original in normalized_to_original.items()
        if _belongs_to_group(normalized, group)
    ]
    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0].count("-"), item[0]))
    return candidates[0][1]


def _belongs_to_group(language: str, group: str) -> bool:
    if group == "zh_hans":
        return language.startswith(("zh-cn", "zh-hans", "zh-sg"))
    if group == "zh_hant":
        return language.startswith(("zh-tw", "zh-hant", "zh-hk", "zh-mo"))
    if group == "en":
        return language == "en" or language.startswith("en-")
    if group == "ja":
        return language == "ja" or language.startswith("ja-")
    if group == "ko":
        return language == "ko" or language.startswith("ko-")
    return False
