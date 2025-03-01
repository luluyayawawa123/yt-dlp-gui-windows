import os
import sys
from pathlib import Path

def setup_environment():
    # 获取程序运行目录
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的运行目录
        base_dir = Path(sys._MEIPASS)
    else:
        # 开发环境运行目录
        base_dir = Path(__file__).parent.parent.parent
    
    # 添加bin目录到PATH
    bin_dir = base_dir / "bin"
    if bin_dir.exists():
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"

setup_environment() 