#!/usr/bin/env python3
"""
清理Windows图标缓存
解决图标不显示的问题
"""

import os
import sys
import subprocess
from pathlib import Path
import tempfile

def clear_windows_icon_cache():
    """清理Windows图标缓存"""
    print("[CACHE] 开始清理Windows图标缓存...")
    
    # 清理方法1：删除IconCache.db文件
    try:
        # Windows 10/11的图标缓存位置
        cache_paths = [
            Path(os.environ['LOCALAPPDATA']) / "Microsoft/Windows/Explorer/IconCache.db",
            Path(os.environ['LOCALAPPDATA']) / "Microsoft/Windows/Explorer/thumbcache_*.db"
        ]
        
        for cache_path_pattern in cache_paths:
            if "*" in str(cache_path_pattern):
                # 处理通配符
                parent = cache_path_pattern.parent
                pattern = cache_path_pattern.name
                if parent.exists():
                    for cache_file in parent.glob(pattern):
                        try:
                            cache_file.unlink()
                            print(f"[OK] 已删除: {cache_file}")
                        except PermissionError:
                            print(f"[WARNING] 无权限删除: {cache_file}")
                        except Exception as e:
                            print(f"[ERROR] 删除失败: {cache_file} - {e}")
            else:
                if cache_path_pattern.exists():
                    try:
                        cache_path_pattern.unlink()
                        print(f"[OK] 已删除: {cache_path_pattern}")
                    except PermissionError:
                        print(f"[WARNING] 无权限删除: {cache_path_pattern}")
                    except Exception as e:
                        print(f"[ERROR] 删除失败: {cache_path_pattern} - {e}")
                        
    except Exception as e:
        print(f"[ERROR] 清理缓存文件失败: {e}")
    
    # 清理方法2：重启Explorer.exe
    try:
        print("[INFO] 重启Windows Explorer...")
        # 结束Explorer进程
        subprocess.run(["taskkill", "/f", "/im", "explorer.exe"], 
                      capture_output=True, check=False)
        
        # 等待一会儿
        import time
        time.sleep(2)
        
        # 重启Explorer
        subprocess.Popen(["explorer.exe"])
        print("[OK] Explorer已重启")
        
    except Exception as e:
        print(f"[ERROR] 重启Explorer失败: {e}")
    
    # 清理方法3：刷新文件关联
    try:
        print("[INFO] 刷新文件关联...")
        # 使用SHChangeNotify刷新系统
        import ctypes
        from ctypes import wintypes
        
        # SHCNE_ASSOCCHANGED = 0x08000000
        shell32 = ctypes.windll.shell32
        shell32.SHChangeNotify(0x08000000, 0, None, None)
        print("[OK] 文件关联已刷新")
        
    except Exception as e:
        print(f"[WARNING] 刷新文件关联失败: {e}")

def create_test_shortcut():
    """创建测试快捷方式"""
    try:
        print("[TEST] 创建测试快捷方式...")
        base_dir = Path(__file__).parent
        dist_dirs = list((base_dir / "dist").glob("YT-DLP-GUI-Windows-v*"))
        
        if not dist_dirs:
            print("[ERROR] 未找到打包后的程序")
            return
            
        latest_dir = sorted(dist_dirs)[-1]
        exe_path = latest_dir / "YT-DLP-GUI-Windows.exe"
        
        if not exe_path.exists():
            print(f"[ERROR] 程序不存在: {exe_path}")
            return
            
        # 在桌面创建快捷方式
        desktop = Path.home() / "Desktop"
        shortcut_path = desktop / "YT-DLP-GUI-Windows-测试图标.lnk"
        
        # 使用Python创建快捷方式
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(shortcut_path))
        shortcut.Targetpath = str(exe_path)
        shortcut.WorkingDirectory = str(exe_path.parent)
        shortcut.IconLocation = str(exe_path)
        shortcut.save()
        
        print(f"[OK] 测试快捷方式已创建: {shortcut_path}")
        print("[INFO] 请检查桌面快捷方式图标是否显示正确")
        
    except ImportError:
        print("[WARNING] 需要安装 pywin32: pip install pywin32")
    except Exception as e:
        print(f"[ERROR] 创建快捷方式失败: {e}")

def main():
    """主函数"""
    print("[ICON-FIX] Windows图标缓存清理工具")
    print("=" * 50)
    
    if not sys.platform.startswith('win'):
        print("[ERROR] 此工具仅适用于Windows系统")
        return
    
    # 检查是否以管理员身份运行
    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        if not is_admin:
            print("[WARNING] 建议以管理员身份运行以获得最佳效果")
    except:
        pass
    
    # 清理图标缓存
    clear_windows_icon_cache()
    
    print("\n" + "=" * 50)
    print("[SUCCESS] 图标缓存清理完成！")
    print("[INFO] 请重新运行程序检查图标是否显示")
    print("[INFO] 如果仍然没有图标，请尝试：")
    print("  1. 重启计算机")
    print("  2. 重新打包程序")
    print("  3. 检查防病毒软件是否阻止了图标")
    
    # 创建测试快捷方式
    create_test_shortcut()

if __name__ == "__main__":
    main()