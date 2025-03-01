import os
import json
import logging
from pathlib import Path
from datetime import datetime
import sys

class Config:
    def __init__(self):
        # 获取程序运行目录
        if getattr(sys, 'frozen', False):
            # PyInstaller打包后的运行目录
            base_dir = Path(sys._MEIPASS).parent
        else:
            # 开发环境运行目录
            base_dir = Path(__file__).parent.parent.parent
            
        # 配置目录设置为程序根目录下的config文件夹
        self.config_dir = base_dir / "config"
        
        self.config_file = self.config_dir / "config.json"
        self.log_file = self.config_dir / "debug.log"
        self.ensure_config_dir()
        
        # 初始化日志
        self.setup_logging()
        
        self.load_config()
        
        # 添加下载记录文件路径
        self.archive_file = self.config_dir / "downloaded_videos_list.txt"
        
        # 确保下载记录文件存在
        if not self.archive_file.exists():
            self.archive_file.touch()
        
    def ensure_config_dir(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
    def setup_logging(self):
        """设置日志"""
        # 创建格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 设置文件处理器
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        
        # 设置控制台处理器
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        console.setFormatter(formatter)
        
        # 配置根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # 移除所有现有的处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 添加新的处理器
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console)
        
    def log(self, message, level=logging.INFO):
        """记录日志"""
        logging.log(level, message)
        
    def load_config(self):
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = {
                'last_download_path': str(Path.home() / "Downloads"),
                'browser': 'firefox',
                'format_settings': {
                    'mode': 'best',
                    'custom_format': ''
                }
            }
            self.save_config()
            
    def save_config(self):
        try:
            # 创建临时文件
            temp_file = self.config_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            # 成功写入后才替换原文件
            temp_file.replace(self.config_file)
        except Exception as e:
            print(f"保存配置文件失败: {e}") 