#!/usr/bin/env python3
"""
简单测试脚本：测试实时下载日志功能
"""

import sys
import os
from pathlib import Path

# 将src目录添加到Python路径
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow

def test_log_window():
    """测试日志窗口功能"""
    app = QApplication(sys.argv)
    
    # 创建主窗口
    main_window = MainWindow()
    main_window.show()
    
    print("=" * 50)
    print("实时下载日志功能测试")
    print("=" * 50)
    print("1. 程序已启动")
    print("2. 在URL输入框中输入一个YouTube链接")
    print("3. 点击'开始下载'")
    print("4. 在下载任务条目中点击'实时下载日志'按钮")
    print("5. 验证极客风格的日志窗口是否正常打开（黑色背景、绿色文字）")
    print("6. 验证实时日志是否正常显示（微软雅黑字体）")
    print("7. 验证复制功能是否正常工作（点击复制按钮）")
    print("8. 验证中文提示信息是否正确显示")
    print("=" * 50)
    
    app.exec()

if __name__ == "__main__":
    test_log_window()