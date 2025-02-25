from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, 
                           QPushButton, QLabel, QMessageBox)
from PyQt6.QtCore import Qt

class SavedURLsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("管理收藏的播放列表")
        self.setMinimumSize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # 添加说明文字
        tip = QLabel("在这里管理您收藏的播放列表和频道。双击可以编辑URL。")
        tip.setStyleSheet("color: #666666; font-size: 12px;")
        layout.addWidget(tip)
        
        # URL列表
        self.url_list = QListWidget()
        self.url_list.setAlternatingRowColors(True)
        saved_items = self.config.config.get('saved_playlists', [])
        for item in saved_items:
            self.url_list.addItem(f"{item['title']} - {item['url']}")
        layout.addWidget(self.url_list)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.delete_button = QPushButton("删除选中")
        self.delete_button.clicked.connect(self.delete_selected)
        
        self.clear_button = QPushButton("清空列表")
        self.clear_button.clicked.connect(self.clear_list)
        
        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.accept)
        
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def delete_selected(self):
        """删除选中的URL"""
        selected_items = self.url_list.selectedItems()
        if not selected_items:
            return
            
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除选中的 {len(selected_items)} 个URL吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            for item in selected_items:
                self.url_list.takeItem(self.url_list.row(item))
            self.save_changes()
    
    def clear_list(self):
        """清空URL列表"""
        if self.url_list.count() == 0:
            return
            
        reply = QMessageBox.question(
            self,
            "确认清空",
            "确定要清空所有收藏的URL吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.url_list.clear()
            self.save_changes()
    
    def save_changes(self):
        """保存更改到配置文件"""
        items = []
        for i in range(self.url_list.count()):
            text = self.url_list.item(i).text()
            title, url = text.split(" - ", 1)
            items.append({
                'title': title,
                'url': url
            })
        self.config.config['saved_playlists'] = items
        self.config.save_config() 