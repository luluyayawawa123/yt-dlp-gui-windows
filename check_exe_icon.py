#!/usr/bin/env python3
"""
检查EXE文件是否包含图标资源
"""

import os
import sys
from pathlib import Path

def check_exe_icon(exe_path):
    """检查EXE文件的图标信息"""
    if not Path(exe_path).exists():
        print(f"[ERROR] EXE文件不存在: {exe_path}")
        return False
        
    print(f"[INFO] 检查文件: {exe_path}")
    print(f"[INFO] 文件大小: {Path(exe_path).stat().st_size:,} 字节")
    
    try:
        # 在Windows上可以通过PE解析检查图标
        import pefile
        pe = pefile.PE(exe_path)
        
        # 检查是否有图标资源
        if hasattr(pe, 'DIRECTORY_ENTRY_RESOURCE'):
            for resource_type in pe.DIRECTORY_ENTRY_RESOURCE.entries:
                if resource_type.name is not None:
                    name = str(resource_type.name)
                elif resource_type.struct.Id == pefile.RESOURCE_TYPE['RT_ICON']:
                    print("[SUCCESS] 找到图标资源!")
                    return True
                elif resource_type.struct.Id == pefile.RESOURCE_TYPE['RT_GROUP_ICON']:
                    print("[SUCCESS] 找到图标组资源!")
                    return True
        
        print("[WARNING] 未找到图标资源")
        return False
        
    except ImportError:
        print("[INFO] 需要安装pefile: pip install pefile")
        return False
    except Exception as e:
        print(f"[ERROR] 检查失败: {e}")
        return False

def main():
    """主函数"""
    print("[CHECK] EXE图标检查工具")
    print("=" * 40)
    
    # 检查最新打包的EXE文件
    base_dir = Path(__file__).parent
    dist_dir = base_dir / "dist"
    
    if not dist_dir.exists():
        print("[ERROR] dist目录不存在，请先运行打包")
        return
    
    # 查找最新的版本目录
    version_dirs = [d for d in dist_dir.iterdir() if d.is_dir() and d.name.startswith("YT-DLP-GUI-Windows-v")]
    if not version_dirs:
        print("[ERROR] 未找到版本目录")
        return
    
    latest_dir = sorted(version_dirs)[-1]
    exe_path = latest_dir / "YT-DLP-GUI-Windows.exe"
    
    print(f"[INFO] 检查目录: {latest_dir}")
    
    if check_exe_icon(exe_path):
        print("\n[SUCCESS] EXE文件包含图标资源")
    else:
        print("\n[ERROR] EXE文件未包含图标资源")
        print("\n[SOLUTION] 解决方案:")
        print("1. 检查图标文件是否存在: icons/app_icon.ico")
        print("2. 重新运行打包: python build.py")
        print("3. 检查PyInstaller版本是否支持图标")

if __name__ == "__main__":
    main()