import json
import os
import re
import subprocess
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

_PREWARM_TIMEOUT_SECONDS = 60
_prewarm_lock = threading.Lock()
_pot_cache_lock = threading.Lock()
_YOUTUBE_VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _get_cache_dir() -> Path:
    xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache_home:
        return Path(xdg_cache_home) / "bgutil-ytdlp-pot-provider"

    home_dir = os.environ.get("HOME") or os.environ.get("USERPROFILE")
    if home_dir:
        return Path(home_dir) / ".cache" / "bgutil-ytdlp-pot-provider"

    return Path.cwd() / "bgutil-ytdlp-pot-provider-cache"


def extract_youtube_video_id(value: str) -> str | None:
    """从常见 YouTube 视频链接或原始 ID 中提取 11 位视频 ID。"""
    value = (value or "").strip()
    if _YOUTUBE_VIDEO_ID_PATTERN.fullmatch(value):
        return value

    try:
        parsed = urlsplit(value)
    except ValueError:
        return None

    host = (parsed.hostname or "").lower()
    path_parts = [part for part in parsed.path.split("/") if part]

    candidate = None
    if host == "youtu.be" or host.endswith(".youtu.be"):
        if path_parts:
            candidate = path_parts[0]
    elif host == "youtube.com" or host.endswith(".youtube.com"):
        if parsed.path.rstrip("/") == "/watch":
            candidate = parse_qs(parsed.query).get("v", [None])[0]
        elif len(path_parts) >= 2 and path_parts[0] in {"embed", "live", "shorts"}:
            candidate = path_parts[1]

    if candidate and _YOUTUBE_VIDEO_ID_PATTERN.fullmatch(candidate):
        return candidate
    return None


def invalidate_cached_youtube_pot(
    content_binding: str,
    cache_dir: Path | None = None,
) -> tuple[bool, str]:
    """仅删除指定视频的 bgutil PO Token 磁盘缓存。"""
    if not _YOUTUBE_VIDEO_ID_PATTERN.fullmatch((content_binding or "").strip()):
        return False, "无法识别当前 YouTube 视频 ID，未刷新 PO Token 缓存。"

    cache_path = Path(cache_dir) / "cache.json" if cache_dir else _get_cache_dir() / "cache.json"
    if not cache_path.exists():
        return True, ""

    temporary_path = cache_path.with_name(
        f"{cache_path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
    )
    with _pot_cache_lock:
        try:
            with cache_path.open("r", encoding="utf-8") as cache_file:
                cache_data = json.load(cache_file)
            if not isinstance(cache_data, dict):
                raise ValueError("缓存内容不是 JSON 对象")

            if content_binding not in cache_data:
                return True, ""

            del cache_data[content_binding]
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with temporary_path.open("w", encoding="utf-8", newline="") as cache_file:
                json.dump(cache_data, cache_file, ensure_ascii=False, separators=(",", ":"))
            os.replace(temporary_path, cache_path)
            return True, ""
        except Exception as exc:  # noqa: BLE001
            return False, f"刷新 YouTube PO Token 缓存失败：{exc}"
        finally:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def _build_prewarm_command(bin_dir: Path, server_dir: Path, cache_dir: Path) -> list[str]:
    node_modules_dir = server_dir / "node_modules"
    script_path = server_dir / "src" / "generate_once.ts"

    return [
        str(bin_dir / "deno.exe"),
        "run",
        "--allow-env",
        "--allow-net",
        f"--allow-ffi={node_modules_dir}",
        f"--allow-write={cache_dir}",
        f"--allow-read={cache_dir},{node_modules_dir}",
        str(script_path),
        "--version",
    ]


def prewarm_youtube_pot(bin_dir: Path) -> tuple[bool, str]:
    """每次启动下载前预热 Deno/bgutil，避免 yt-dlp 的 15 秒检查超时。"""
    bin_dir = Path(bin_dir).resolve()
    server_dir = bin_dir / "bgutil-ytdlp-pot-provider" / "server"
    deno_exe = bin_dir / "deno.exe"
    script_path = server_dir / "src" / "generate_once.ts"
    node_modules_dir = server_dir / "node_modules"

    if not deno_exe.exists():
        return False, f"未找到 Deno 运行时：{deno_exe}"
    if not script_path.exists():
        return False, f"未找到 PO Token 脚本：{script_path}"
    if not node_modules_dir.exists():
        return False, f"未找到 PO Token 依赖目录：{node_modules_dir}"

    cache_dir = _get_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["DENO_NO_PROMPT"] = "1"
    env["DENO_NO_UPDATE_CHECK"] = "1"
    env["FORCE_COLOR"] = "false"

    command = _build_prewarm_command(bin_dir, server_dir, cache_dir)
    creationflags = 0
    startupinfo = None
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    # 预热进程本身不会常驻；每次下载前重新执行，确保紧随其后的 yt-dlp
    # 能直接使用已加载到系统文件缓存中的 Deno/bgutil 组件。
    with _prewarm_lock:
        try:
            result = subprocess.run(
                command,
                cwd=str(server_dir),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=_PREWARM_TIMEOUT_SECONDS,
                creationflags=creationflags,
                startupinfo=startupinfo,
            )
        except subprocess.TimeoutExpired:
            return False, (
                f"PO Token 组件启动超时（>{_PREWARM_TIMEOUT_SECONDS} 秒）。"
                "请稍后重试。"
            )
        except Exception as exc:  # noqa: BLE001
            return False, f"PO Token 组件启动失败：{exc}"

    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        if details:
            details = details.splitlines()[-1]
            return False, f"PO Token 组件启动失败：{details}"
        return False, f"PO Token 组件启动失败，返回码：{result.returncode}"

    return True, ""
