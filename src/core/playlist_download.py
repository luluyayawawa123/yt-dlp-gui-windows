import json
import os
import re
from dataclasses import dataclass
from typing import Iterable


# 播放列表与普通下载模式保持一致：mweb + PO Token，不读取账户 Cookies。
PLAYLIST_CLIENT = "mweb"
_POT_CLIENTS = {"mweb", "web_creator"}
_COOKIE_CLIENTS = {"web_creator"}
_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


@dataclass(frozen=True)
class PlaylistItem:
    video_id: str
    title: str
    url: str
    index: int


@dataclass(frozen=True)
class PlaylistMetadata:
    playlist_id: str
    title: str
    items: tuple[PlaylistItem, ...]


def parse_playlist_metadata(payload: str) -> PlaylistMetadata:
    """解析 yt-dlp --flat-playlist --dump-single-json 的结果。"""
    data = json.loads(payload)
    playlist_id = str(data.get("id") or "未知播放列表")
    title = str(data.get("title") or playlist_id)
    items = []

    for entry in data.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        video_id = str(entry.get("id") or "").strip()
        if not video_id:
            continue
        item_title = str(entry.get("title") or video_id).strip()
        item_url = str(entry.get("webpage_url") or entry.get("url") or "").strip()
        if not item_url.startswith(("http://", "https://")):
            item_url = f"https://www.youtube.com/watch?v={video_id}"
        items.append(
            PlaylistItem(
                video_id=video_id,
                title=item_title,
                url=item_url,
                index=len(items) + 1,
            )
        )

    return PlaylistMetadata(playlist_id=playlist_id, title=title, items=tuple(items))


def safe_playlist_folder_name(title: str, fallback: str) -> str:
    """生成适用于 Windows 的播放列表目录名。"""
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", (title or "").strip())
    value = re.sub(r"\s+", " ", value).rstrip(" .")
    if not value:
        value = fallback or "未知播放列表"
    if value.upper() in _WINDOWS_RESERVED_NAMES:
        value = f"_{value}"
    return value[:120].rstrip(" .") or "未知播放列表"


def playlist_client_requires_pot(client: str = PLAYLIST_CLIENT) -> bool:
    """返回客户端是否需要 PO Token provider 和预热流程。"""
    return client in _POT_CLIENTS


def playlist_client_requires_cookies(client: str = PLAYLIST_CLIENT) -> bool:
    """返回客户端是否需要浏览器账户 Cookies。"""
    return client in _COOKIE_CLIENTS


def build_playlist_item_args(
    item: PlaylistItem,
    common_args: Iterable[str],
    output_template: str,
    pot_server_home: str,
    browser: str = "firefox",
) -> list[str]:
    """为单个播放列表条目构建当前固定客户端参数。"""
    args = [item.url, "--no-playlist", *common_args]
    if playlist_client_requires_pot():
        if pot_server_home and os.path.isdir(pot_server_home):
            args.extend([
                "--extractor-args",
                f"youtubepot-bgutilscript:server_home={pot_server_home}",
            ])
    if playlist_client_requires_cookies() and browser:
        args.extend(["--cookies-from-browser", browser])

    args.extend([
        "--extractor-args",
        f"youtube:player_client={PLAYLIST_CLIENT}",
        "--verbose",
        "-o",
        output_template,
    ])
    return args
