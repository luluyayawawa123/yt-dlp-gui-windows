import PyInstaller.__main__
import os
import sys
from pathlib import Path
import shutil

def clean_build_files():
    """清理旧的构建文件"""
    root_dir = Path(__file__).parent
    
    # 删除build和dist目录
    for dir_name in ['build', 'dist']:
        dir_path = root_dir / dir_name
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"已删除 {dir_name} 目录")
    
    # 删除spec文件
    for spec_file in root_dir.glob("*.spec"):
        spec_file.unlink()
        print(f"已删除 {spec_file.name}")

def build():
    # 清理旧的构建文件
    clean_build_files()
    
    # 获取项目根目录
    root_dir = Path(__file__).parent
    
    # 设置打包参数
    args = [
        'src/main.py',  # 主程序入口
        '--name=YT-DLP-GUI-Windows',  # 生成的exe名称
        '--noconsole',  # 不显示控制台
        '--noconfirm',  # 覆盖已存在的打包文件
        '--clean',  # 清理临时文件
        '--version-file=version.txt',  # 取消注释，启用版本信息
        '--hidden-import=PyQt6',
        '--hidden-import=requests',
        '--hidden-import=bs4',
        '--paths=src',  # 添加源码目录到Python路径
    ]
    
    # Windows特定配置
    if sys.platform == 'win32':
        args.extend([
            '--runtime-hook=src/hooks/windows_hook.py',  # Windows运行时钩子
        ])
    
    # 开始打包
    PyInstaller.__main__.run(args)
    
    # 复制必要的运行时文件
    dist_dir = root_dir / "dist" / "YT-DLP-GUI-Windows"
    bin_dir = dist_dir / "bin"
    
    # 如果bin目录已存在，先删除
    if bin_dir.exists():
        shutil.rmtree(bin_dir)
    bin_dir.mkdir(exist_ok=True)
    
    # 复制yt-dlp和ffmpeg到打包目录
    src_bin = root_dir / "bin"
    if src_bin.exists():
        for file in src_bin.glob("*"):
            shutil.copy2(file, bin_dir)
            
    # 创建config目录
    config_dir = dist_dir / "config"
    config_dir.mkdir(exist_ok=True)

if __name__ == "__main__":
    build() 