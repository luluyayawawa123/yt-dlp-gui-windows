import sys
import os
from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow
from pathlib import Path
import logging

def main():
    # 获取程序所在目录的bin目录
    bin_dir = Path(__file__).parent.parent / "bin"
    
    # 将bin目录添加到PATH
    if 'PATH' not in os.environ:
        os.environ['PATH'] = str(bin_dir)
    else:
        os.environ['PATH'] = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"
        
    # 设置更详细的日志格式
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler("debug.log", encoding='utf-8'),  # 文件处理器
            logging.StreamHandler()  # 控制台处理器
        ]
    )
    
    logging.debug(f"程序目录: {os.path.dirname(os.path.abspath(__file__))}")
    logging.debug(f"二进制目录: {bin_dir}")
    logging.debug(f"系统PATH: {os.environ['PATH']}")

    app = QApplication(sys.argv)
    
    # 设置应用程序信息
    app.setApplicationName("YT-DLP GUI for Windows")
    app.setApplicationVersion("1.0.2")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 