"""缩略图容器 — 图片选择入口 + 缩略图展示，单一集成组件。"""

import os
from typing import List
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QPushButton, QGridLayout, QLabel, QFileDialog,
    QMenu, QApplication, QVBoxLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QFont, QAction
from PIL import Image


class ThumbLoaderThread(QThread):
    """后台缩略图生成线程。"""
    thumbnail_ready = pyqtSignal(int, QPixmap)  # index, pixmap
    
    def __init__(self, paths: List[str], size: tuple = (100, 75)):
        super().__init__()
        self.paths = paths
        self.size = size
        self._cancelled = False
    
    def cancel(self):
        self._cancelled = True
    
    def run(self):
        for i, path in enumerate(self.paths):
            if self._cancelled:
                return
            try:
                img = Image.open(path)
                img.thumbnail(self.size, Image.Resampling.LANCZOS)
                # 转成方形：cover 裁切
                w, h = img.size
                target_w, target_h = self.size
                ratio = max(target_w / w, target_h / h)
                new_w = int(w * ratio)
                new_h = int(h * ratio)
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                left = (new_w - target_w) // 2
                top = (new_h - target_h) // 2
                img = img.crop((left, top, left + target_w, top + target_h))
                
                # PIL → QPixmap
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                data = img.tobytes("raw", "RGBA")
                qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
                pixmap = QPixmap.fromImage(qimg)
                self.thumbnail_ready.emit(i, pixmap)
            except Exception:
                # 生成占位图
                pixmap = self._create_placeholder()
                self.thumbnail_ready.emit(i, pixmap)
    
    def _create_placeholder(self) -> QPixmap:
        pm = QPixmap(self.size[0], self.size[1])
        pm.fill(QColor("#2A2A2A"))
        painter = QPainter(pm)
        painter.setPen(QColor("#666666"))
        painter.setFont(QFont("-apple-system", 10))
        painter.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "?")
        painter.end()
        return pm


class ThumbContainer(QWidget):
    """缩略图容器 — 空状态/有图状态二态切换。"""
    
    file_added = pyqtSignal(list)      # 新增文件路径列表
    file_removed = pyqtSignal(int)   # 删除指定索引
    files_cleared = pyqtSignal()      # 清空所有
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.files: List[str] = []
        self.thumb_labels: List[QLabel] = []
        self.loader_thread: ThumbLoaderThread = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        self.setMinimumHeight(120)
        self.setMaximumHeight(160)
        self.setAcceptDrops(True)
        
        # 主布局 - 无外边距，按钮撑满
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # 空状态：选择按钮（撑满）
        self.empty_btn = QPushButton("选择图片文件")
        self.empty_btn.setMinimumHeight(100)
        self.empty_btn.setMaximumHeight(140)
        self.empty_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.empty_btn.setStyleSheet("""
            QPushButton {
                border: 2px dashed #666666;
                border-radius: 8px;
                color: #999999;
                font-size: 14px;
            }
            QPushButton:hover {
                border-color: #E0E0E0;
                color: #E0E0E0;
                background-color: #2A2A2A;
            }
        """)
        self.empty_btn.clicked.connect(self._on_select_files)
        self.layout.addWidget(self.empty_btn)
        
        # 有图状态：网格布局（初始隐藏）
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(8)
        self.grid_widget.setVisible(False)
        self.layout.addWidget(self.grid_widget)
    
    def set_files(self, paths: List[str]):
        """设置文件列表（外部调用，如从 AppState 同步）。"""
        self.files = list(paths)
        self._update_view()
    
    def add_files(self, paths: List[str]):
        """追加文件。"""
        self.files.extend(paths)
        self._update_view()
        self.file_added.emit(paths)
    
    def remove_file(self, index: int):
        """删除指定索引。"""
        if 0 <= index < len(self.files):
            del self.files[index]
            self._update_view()
            self.file_removed.emit(index)
    
    def _update_view(self):
        """根据文件数量切换状态。"""
        has_files = len(self.files) > 0
        self.empty_btn.setVisible(not has_files)
        self.grid_widget.setVisible(has_files)
        
        if has_files:
            self._refresh_grid()
    
    def _refresh_grid(self):
        """刷新缩略图网格。"""
        # 清空旧网格
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.thumb_labels = []
        
        # 最多显示 10 张（5列 × 2排）
        max_display = 10
        display_files = self.files[:max_display]
        
        for i, path in enumerate(display_files):
            row = i // 5
            col = i % 5
            
            thumb = QLabel()
            thumb.setFixedSize(100, 75)
            thumb.setStyleSheet("border: 1px solid #333333; border-radius: 4px;")
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb.setToolTip(Path(path).name)
            
            # 右键菜单
            thumb.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            thumb.customContextMenuRequested.connect(
                lambda pos, idx=i: self._show_context_menu(pos, idx)
            )
            
            # 超出显示 +N
            if i == max_display - 1 and len(self.files) > max_display:
                remain = len(self.files) - max_display + 1
                thumb.setText(f"+{remain}")
                thumb.setStyleSheet("""
                    QLabel {
                        border: 1px solid #333333;
                        border-radius: 4px;
                        color: #999999;
                        font-size: 18px;
                        font-weight: bold;
                        background-color: #1E1E1E;
                    }
                """)
            
            self.grid_layout.addWidget(thumb, row, col)
            self.thumb_labels.append(thumb)
        
        # 启动异步加载（前10张优先）
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.cancel()
            self.loader_thread.wait(1000)
        
        if display_files:
            self.loader_thread = ThumbLoaderThread(display_files)
            self.loader_thread.thumbnail_ready.connect(self._on_thumbnail_ready)
            self.loader_thread.start()
    
    def _on_thumbnail_ready(self, index: int, pixmap: QPixmap):
        """缩略图加载完成回调。"""
        if 0 <= index < len(self.thumb_labels):
            label = self.thumb_labels[index]
            # 检查是否是 +N 占位
            if not label.text().startswith("+"):
                label.setPixmap(pixmap)
    
    def _on_select_files(self):
        """打开文件选择对话框。"""
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择图片", "",
            "图片 (*.jpg *.jpeg *.png *.heic *.tiff *.webp);;所有文件 (*.*)"
        )
        if paths:
            self.add_files(paths)
    
    def _show_context_menu(self, pos, index: int):
        """显示右键菜单。"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1E1E1E;
                color: #E0E0E0;
                border: 1px solid #333333;
            }
            QMenu::item:selected {
                background-color: #2A2A2A;
            }
        """)
        
        delete_action = QAction("删除", self)
        delete_action.triggered.connect(lambda: self.remove_file(index))
        menu.addAction(delete_action)
        
        menu.exec(self.thumb_labels[index].mapToGlobal(pos))
    
    # ---- 拖放支持 ----
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls()
                 if url.isLocalFile()]
        if paths:
            self.add_files(paths)
    
    def mousePressEvent(self, event):
        """左键点击空白处追加图片。"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 检查是否点击在空白区域
            child = self.childAt(event.pos())
            if child is None or child == self.empty_btn:
                self._on_select_files()
