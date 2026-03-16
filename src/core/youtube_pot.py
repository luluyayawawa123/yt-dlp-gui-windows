import os
import subprocess
import threading
import time
from pathlib import Path

_PREWARM_TIMEOUT_SECONDS = 60
_PREWARM_VALID_SECONDS = 3600
_prewarmed_server_dirs = {}
_prewarm_lock = threading.Lock()


def _get_cache_dir() -> Path:
    xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache_home:
        return Path(xdg_cache_home) / "bgutil-ytdlp-pot-provider"

    home_dir = os.environ.get("HOME") or os.environ.get("USERPROFILE")
    if home_dir:
        return Path(home_dir) / ".cache" / "bgutil-ytdlp-pot-provider"

    return Path.cwd() / "bgutil-ytdlp-pot-provider-cache"


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
    """在启动 yt-dlp 前预热 Deno/bgutil，避免首次检查超时。"""
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

    server_key = os.path.normcase(str(server_dir.resolve()))
    now = time.monotonic()
    with _prewarm_lock:
        last_prewarm_time = _prewarmed_server_dirs.get(server_key)
        if (
            last_prewarm_time is not None
            and now - last_prewarm_time < _PREWARM_VALID_SECONDS
        ):
            return True, ""

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
            f"YouTube 下载组件初始化超时（>{_PREWARM_TIMEOUT_SECONDS} 秒）。"
            "请稍后重试。"
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"YouTube 下载组件初始化失败：{exc}"

    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        if details:
            details = details.splitlines()[-1]
            return False, f"YouTube 下载组件初始化失败：{details}"
        return False, f"YouTube 下载组件初始化失败，返回码：{result.returncode}"

    with _prewarm_lock:
        _prewarmed_server_dirs[server_key] = time.monotonic()

    return True, ""
