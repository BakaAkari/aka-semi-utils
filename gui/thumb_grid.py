"""缩略图容器 — 图片选择入口 + 缩略图展示，单一集成组件。"""

from pathlib import Path

from PIL import Image
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import QFileDialog, QGridLayout, QLabel, QMenu, QPushButton, QSizePolicy, QVBoxLayout, QWidget


class ThumbLoaderThread(QThread):
    """后台缩略图生成线程（Phase 9：接受 parent，让 Qt 父子链管理生命周期）。"""
    thumbnail_ready = pyqtSignal(int, QPixmap)  # index, pixmap

    def __init__(self, paths: list[str], size: tuple = (100, 75), parent=None):
        super().__init__(parent)
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
                # 用 with 包裹确保文件句柄立即关闭，避免大批量缩略图扫描时
                # 触发 macOS/Linux "Too many open files"。
                with Image.open(path) as src:
                    src.load()
                    img = src.copy()
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
        self.files: list[str] = []
        self.thumb_labels: list[QLabel] = []
        # Phase 9：使用 Optional 注解 + Qt 父子链管理 ThumbLoaderThread 生命周期
        self.loader_thread: ThumbLoaderThread | None = None

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
    
    # ---- SSOT 写入入口 ----
    # Phase 9：本组件**完全去状态化** — `self.files` 仅作为 set_files 的本地缓存，
    # 用户操作（add_files / remove_file）只 emit 信号，由 AppState 决定是否回写。
    # 这样消除了"thumb_grid 内部状态" vs "AppState.selected_files"两份真相不同步的风险。

    def set_files(self, paths: list[str]):
        """**唯一**的本地状态写入入口 — 由 AppState.files_changed 信号驱动。"""
        self.files = list(paths)
        self._update_view()

    def add_files(self, paths: list[str]):
        """用户增量添加 — **只发信号**，不写本地状态（等 AppState 回流）。"""
        if not paths:
            return
        self.file_added.emit(list(paths))

    def remove_file(self, index: int):
        """用户删除 — **只发信号**，不写本地状态（等 AppState 回流）。"""
        if 0 <= index < len(self.files):
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
        # Phase 9：统一线程生命周期 — parent=self 走 Qt 父子链；finished → 清 Python 引用 + deleteLater
        if self.loader_thread is not None and self.loader_thread.isRunning():
            self.loader_thread.cancel()
            self.loader_thread.wait(1000)

        if display_files:
            thread = ThumbLoaderThread(display_files, parent=self)
            thread.thumbnail_ready.connect(self._on_thumbnail_ready)
            thread.finished.connect(self._on_loader_finished)
            thread.finished.connect(thread.deleteLater)
            self.loader_thread = thread
            thread.start()

    def _on_loader_finished(self) -> None:
        """ThumbLoaderThread 结束信号槽：sender 守卫 + 清空 Python 引用。"""
        sender = self.sender()
        if sender is self.loader_thread:
            self.loader_thread = None
    
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
