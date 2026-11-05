import os
import json
import logging
from pathlib import Path
from datetime import datetime
import sys
from PyQt6.QtCore import QObject, pyqtSignal

class Config(QObject):
    quality_index_changed = pyqtSignal(int)
    subtitle_enabled_changed = pyqtSignal(bool)
    subtitle_options_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
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
                'quality_index': 0,
                'format_settings': {
                    'mode': 'best',
                    'custom_format': ''
                }
            }
            self.save_config()

        changed = False
        quality_index = self.config.get('quality_index', 0)
        if not isinstance(quality_index, int) or not 0 <= quality_index <= 6:
            quality_index = 0
            self.config['quality_index'] = 0
            changed = True

        if quality_index == 6:
            # 斗地主模式只属于普通下载；播放列表保留通用画质。
            self.config.setdefault('main_quality_index', 6)
            self.config['quality_index'] = 0
            changed = True
        elif 'main_quality_index' not in self.config:
            self.config['main_quality_index'] = quality_index
            changed = True

        main_quality_index = self.config.get('main_quality_index', quality_index)
        if not isinstance(main_quality_index, int) or not 0 <= main_quality_index <= 6:
            self.config['main_quality_index'] = self.config['quality_index']
            changed = True

        if 'subtitle_download_enabled' not in self.config:
            self.config['subtitle_download_enabled'] = False
            changed = True

        if 'playlist_subtitle_only' not in self.config:
            self.config['playlist_subtitle_only'] = False
            changed = True

        if changed:
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

    def set_quality_index(self, index):
        """保存两个模式共用的画质，并通知所有已打开窗口。"""
        if not isinstance(index, int) or not 0 <= index <= 5:
            return
        changed = (
            self.config.get('quality_index') != index
            or self.config.get('main_quality_index') != index
        )
        if not changed:
            return
        self.config['quality_index'] = index
        self.config['main_quality_index'] = index
        self.save_config()
        self.quality_index_changed.emit(index)

    def set_main_quality_index(self, index):
        """保存普通模式画质；斗地主模式不覆盖播放列表的通用画质。"""
        if index != 6:
            self.set_quality_index(index)
            return
        if self.config.get('main_quality_index') == 6:
            return
        self.config['main_quality_index'] = 6
        self.save_config()

    def set_subtitle_enabled(self, enabled):
        """保存共用字幕开关，并通知两个窗口实时同步。"""
        enabled = bool(enabled)
        if self.config.get('subtitle_download_enabled') == enabled:
            return
        self.config['subtitle_download_enabled'] = enabled
        self.save_config()
        self.subtitle_enabled_changed.emit(enabled)

    def notify_subtitle_options_changed(self):
        """通知其他字幕控件刷新共享语言状态。"""
        self.subtitle_options_changed.emit()
