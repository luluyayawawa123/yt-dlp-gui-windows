"""YouTube 下载故障分类与自动恢复规则。"""

import re

MAX_YOUTUBE_RECOVERY_RETRIES = 5
MAX_SUBTITLE_RECOVERY_RETRIES = 1

RECOVERABLE_FAILURES = frozenset({
    "media_403",
    "dns_resolution",
    "pot_startup",
    "pot_generation",
    "subtitle_download",
})

RECOVERY_MESSAGES = {
    "media_403": "HTTP 403，正在重新解析下载地址并自动重试",
    "dns_resolution": "DNS 解析失败，正在自动重试",
    "pot_startup": "PO Token 组件启动超时，正在自动重试",
    "pot_generation": "PO Token 生成失败，正在自动重试",
    "subtitle_download": "字幕未返回有效数据，正在刷新 Token 并仅重试字幕",
}

FAILURE_TITLES = {
    "login_required": "YouTube 要求登录验证",
    "cookies_unavailable": "无法读取 Firefox Cookies",
    "media_403": "媒体下载被拒绝（HTTP 403）",
    "dns_resolution": "DNS 解析失败",
    "pot_startup": "PO Token 组件启动超时",
    "pot_generation": "PO Token 生成失败",
    "subtitle_download": "字幕下载失败：未返回有效数据",
    "format_unavailable": "所选画质不可用",
    "video_unavailable": "视频不可用或无权访问",
    "download_failed": "下载阶段出现错误",
    "merge_failed": "音视频合并失败",
}

FAILURE_ADVICE = {
    "login_required": "请先在 Firefox 登录 YouTube，再重新开始播放列表下载。",
    "cookies_unavailable": "请确认已安装 Firefox，并使用标准配置文件登录过 YouTube。",
    "media_403": "请稍后重试；若持续失败，检查 Firefox 登录状态并尝试更换出口网络。",
    "dns_resolution": "请检查网络、VPN、代理和 DNS 设置后重试。",
    "pot_startup": "请重启软件；若仍失败，检查 Deno 与 bgutil Provider 是否完整且版本配套。",
    "pot_generation": "请稍后重试；若持续失败，更新 yt-dlp 与整套 bgutil Provider 后再测试。",
    "subtitle_download": "请重新执行下载；已有视频会被跳过，程序将重新尝试下载字幕。",
    "format_unavailable": "请改选较低画质或“最高画质”后重试。",
    "video_unavailable": "请检查视频是否被删除、设为私密、限制地区或需要账号权限。",
    "download_failed": "请重新执行播放列表下载，并保留完整日志继续排查。",
    "merge_failed": "请检查 FFmpeg、磁盘空间和输出目录权限。",
}


def classify_youtube_failure(output: str, error: str) -> str | None:
    """根据完整 yt-dlp 输出返回稳定的故障代码。"""
    combined = f"{output}\n{error}".lower()

    if any(marker in combined for marker in (
        "login_required",
        "sign in to confirm you",
        "sign in to confirm you’re not a bot",
        "sign in to confirm you're not a bot",
    )):
        return "login_required"

    if any(marker in combined for marker in (
        "could not find firefox cookies database",
        "failed to decrypt with the current method",
        "failed to extract cookies from firefox",
    )):
        return "cookies_unavailable"

    if "http error 403" in combined and (
        "googlevideo.com/videoplayback" in combined
        or "unable to download video data" in combined
    ):
        return "media_403"

    if any(marker in combined for marker in (
        "failed to resolve",
        "getaddrinfo failed",
        "errno 11002",
    )):
        return "dns_resolution"

    if (
        "generate_once.ts" in combined
        and "--version" in combined
        and any(marker in combined for marker in (
            "timed out after",
            "timeoutexpired",
            "failed to check script version",
        ))
    ):
        return "pot_startup"

    if any(marker in combined for marker in (
        "failed while generating pot",
        "error fetching po token",
        "failed to generate an integrity token",
    )):
        return "pot_generation"

    subtitle_context = any(marker in combined for marker in (
        "writing video subtitles to:",
        "downloading subtitles:",
        "_write_subtitles",
        "unable to download video subtitles",
    ))
    if subtitle_context and any(marker in combined for marker in (
        "did not get any data blocks",
        "unable to download video subtitles",
    )):
        return "subtitle_download"

    if any(marker in combined for marker in (
        "requested format is not available",
        "no video formats found",
        "only images are available for download",
    )):
        return "format_unavailable"

    if any(marker in combined for marker in (
        "video unavailable",
        "private video",
        "this video is not available",
    )):
        return "video_unavailable"

    return None


def classify_recoverable_youtube_failure(output: str, error: str) -> str | None:
    """只返回适合自动重新解析的故障。"""
    reason = classify_youtube_failure(output, error)
    return reason if reason in RECOVERABLE_FAILURES else None


def should_retry_youtube_failure(
    reason: str | None,
    retry_count: int,
    saw_download_progress: bool = False,
) -> bool:
    """判断当前失败是否仍适合重启 yt-dlp 重新解析。"""
    if reason not in RECOVERABLE_FAILURES:
        return False
    retry_limit = (
        MAX_SUBTITLE_RECOVERY_RETRIES
        if reason == "subtitle_download"
        else MAX_YOUTUBE_RECOVERY_RETRIES
    )
    if retry_count >= retry_limit:
        return False
    if reason in {"pot_startup", "pot_generation"} and saw_download_progress:
        return False
    return True


def recovery_total_attempts(reason: str | None) -> int:
    """返回指定故障的总尝试次数（包含首次尝试）。"""
    if reason == "subtitle_download":
        return MAX_SUBTITLE_RECOVERY_RETRIES + 1
    return MAX_YOUTUBE_RECOVERY_RETRIES + 1


def failure_title(reason: str) -> str:
    return FAILURE_TITLES.get(reason, FAILURE_TITLES["download_failed"])


def failure_advice(reason: str) -> str:
    return FAILURE_ADVICE.get(reason, FAILURE_ADVICE["download_failed"])


def extract_failure_detail(output: str, error: str) -> str:
    """提取最后一条有效错误，避免把日志开头当作失败原因。"""
    combined = f"{output}\n{error}"
    matches = re.findall(r"(?im)^\s*ERROR:\s*(.+?)\s*$", combined)
    if matches:
        return matches[-1].strip()

    ignored_prefixes = (
        "extracting cookies from ",
        "extracted ",
        "[youtube] extracting url:",
        "[youtube] ",
        "[debug] ",
    )
    for raw_line in reversed(combined.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        if line.lower().startswith(ignored_prefixes):
            continue
        return line
    return "下载进程异常退出"
