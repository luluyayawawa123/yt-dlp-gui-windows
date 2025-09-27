import PyInstaller.__main__
import os
import sys
from pathlib import Path
import shutil
import re

FALLBACK_ENCODINGS = (
    "utf-8",
    "utf-16",
    "utf-16le",
    "utf-16be",
    "gb18030",
    "cp936",
    "latin-1",
)


def read_text_safe(path: Path) -> str:
    """按多种编码尝试读取文本，最终保证返回字符串。"""
    for encoding in FALLBACK_ENCODINGS:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    # 最后兜底，忽略非法字节
    return path.read_text(encoding="utf-8", errors="ignore")


def parse_version_from_text(text: str) -> str | None:
    """尝试从给定文本中提取版本号。"""
    patterns = [
        r"FileVersion',\s*'([0-9.]+)'",
        r"ProductVersion',\s*'([0-9.]+)'",
        r'setApplicationVersion\(["\']([0-9.]+)["\']\)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def clean_build_files() -> None:
    """清理旧的构建文件。"""
    root_dir = Path(__file__).parent

    for dir_name in ["build", "dist"]:
        dir_path = root_dir / dir_name
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"已删除 {dir_name} 目录")

    for spec_file in root_dir.glob("*.spec"):
        spec_file.unlink()
        print(f"已删除 {spec_file.name}")


def get_version() -> str:
    """从版本文件或源代码中获取版本号。"""
    root_dir = Path(__file__).parent
    version_file = root_dir / "version.txt"

    if version_file.exists():
        try:
            content = read_text_safe(version_file)
            version = parse_version_from_text(content)
            if version:
                return version
        except Exception as exc:  # noqa: BLE001
            print(f"读取 version.txt 失败: {exc}")

    main_py_path = root_dir / "src" / "main.py"
    try:
        content = read_text_safe(main_py_path)
        version = parse_version_from_text(content)
        if version:
            return version
    except Exception as exc:  # noqa: BLE001
        print(f"从 main.py 读取版本失败: {exc}")

    default_version = "1.0.0"
    print(f"无法解析版本号，使用默认版本: {default_version}")
    return default_version


def build() -> None:
    clean_build_files()

    root_dir = Path(__file__).parent
    version = get_version()
    app_name = f"YT-DLP-GUI-Windows-v{version}"
    print(f"正在打包版本: {version}")
    print(f"输出文件夹名称: {app_name}")

    icon_path = root_dir / "icons" / "app_icon.ico"
    if icon_path.exists():
        print(f"找到图标文件: {icon_path}")
    else:
        print(f"警告: 未找到图标文件 {icon_path}")
        print("提示: 运行 python create_icons.py 创建图标")

    args = [
        "src/main.py",
        f"--name={app_name}",
        "--noconsole",
        "--noconfirm",
        "--clean",
        "--version-file=version.txt",
        "--hidden-import=PyQt6",
        "--hidden-import=requests",
        "--hidden-import=bs4",
        "--paths=src",
    ]

    if icon_path.exists():
        args.append(f"--icon={icon_path}")
        print("已添加图标到打包参数")

    if sys.platform == "win32":
        args.append("--runtime-hook=src/hooks/windows_hook.py")

    PyInstaller.__main__.run(args)

    dist_dir = root_dir / "dist" / app_name
    bin_dir = dist_dir / "bin"

    if bin_dir.exists():
        shutil.rmtree(bin_dir)
    bin_dir.mkdir(exist_ok=True)

    src_bin = root_dir / "bin"
    if src_bin.exists():
        for file in src_bin.glob("*"):
            shutil.copy2(file, bin_dir)

    config_dir = dist_dir / "config"
    config_dir.mkdir(exist_ok=True)

    src_icons = root_dir / "icons"
    dest_icons = dist_dir / "icons"
    if src_icons.exists():
        if dest_icons.exists():
            shutil.rmtree(dest_icons)
        shutil.copytree(src_icons, dest_icons)
        print(f"已复制图标文件夹到 {dest_icons}")

    old_exe_path = dist_dir / f"{app_name}.exe"
    new_exe_path = dist_dir / "YT-DLP-GUI-Windows.exe"
    if old_exe_path.exists():
        old_exe_path.rename(new_exe_path)
        print(f"已将 {app_name}.exe 重命名为 YT-DLP-GUI-Windows.exe")

    print("\n[SUCCESS] 打包完成")
    print(f"[INFO] 输出目录: {dist_dir}")
    print(f"[INFO] 可执行文件: {new_exe_path}")
    print(f"[INFO] 版本: v{version}")


if __name__ == "__main__":
    build()
