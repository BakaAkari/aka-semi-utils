"""缩略图容器 — 图片选择入口 + 缩略图展示，单一集成组件。"""

from pathlib import Path

from PIL import Image
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


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
    file_selected = pyqtSignal(int, str)  # 用户左键选中某张图片（index, path）
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.files: list[str] = []
        self.thumb_labels: list[QLabel] = []
        self._selected_index: int = -1   # 当前选中预览的索引，-1 = 未选中
        # Phase 9：使用 Optional 注解 + Qt 父子链管理 ThumbLoaderThread 生命周期
        self.loader_thread: ThumbLoaderThread | None = None

        self._setup_ui()
    
    # Phase 12：网格改 3 列 × 2 行；前 5 格放缩略图（满 5 后第 5 格变 +N），第 6 格固定为 ➕ 追加卡。
    GRID_COLS = 3
    MAX_DISPLAY = 5  # 前 5 格用于缩略图 / +N 占位
    THUMB_W = 100
    THUMB_H = 75

    def _setup_ui(self):
        # 高度需容下 2 行（2 × 75 + 间距 + 边距），适当放宽上下限
        self.setMinimumHeight(170)
        self.setMaximumHeight(200)
        self.setAcceptDrops(True)
        self.setToolTip("点击空白处或 ➕ 卡追加图片，也可直接拖拽到此区域")

        # 主布局 - 无外边距，按钮撑满
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # 空状态：选择按钮（撑满）
        self.empty_btn = QPushButton("选择图片文件")
        self.empty_btn.setMinimumHeight(100)
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

        # 有图状态：外层 HBox 把 grid_widget 水平居中（Phase 13：自适应居中对齐）
        self.grid_host = QWidget()
        host_hbox = QHBoxLayout(self.grid_host)
        host_hbox.setContentsMargins(0, 0, 0, 0)
        host_hbox.setSpacing(0)
        host_hbox.addStretch(1)

        self.grid_widget = QWidget()
        # 关键：让 grid_widget 只占必需宽度，多出的空间由两侧 stretch 吃掉
        self.grid_widget.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(8)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        host_hbox.addWidget(self.grid_widget)
        host_hbox.addStretch(1)

        self.grid_host.setVisible(False)
        self.layout.addWidget(self.grid_host)
    
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
        self.grid_host.setVisible(has_files)

        if has_files:
            self._refresh_grid()
    
    def _refresh_grid(self):
        """刷新缩略图网格（Phase 13：3 列 × ≤2 行；➕ 卡跟随最后一张缩略图）。

        - N=1: 一行 [thumb, ➕]，外层 HBox 把整块网格居中
        - N=2: 一行 [t1, t2, ➕]
        - N=3: 第 1 行 [t1,t2,t3] + 第 2 行 [➕]
        - N=4: [t1,t2,t3] / [t4,➕]
        - N=5（无溢出）: [t1,t2,t3] / [t4,t5,➕]
        - N≥6（溢出）: [t1,t2,t3] / [t4,+N,➕]，+N 占第 5 格
        """
        # 清空旧网格
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.thumb_labels = []

        cols = self.GRID_COLS
        max_display = self.MAX_DISPLAY
        display_files = self.files[:max_display]
        overflow = len(self.files) > max_display

        # 前 max_display 格：缩略图，最后一格在溢出时变 +N 占位
        for i, path in enumerate(display_files):
            row = i // cols
            col = i % cols

            thumb = QLabel()
            thumb.setFixedSize(self.THUMB_W, self.THUMB_H)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb.setCursor(Qt.CursorShape.PointingHandCursor)

            is_last_slot = (i == max_display - 1) and overflow
            if is_last_slot:
                # 第 5 格作为 +N 占位，包含被覆盖的第 5 张本身
                remain = len(self.files) - (max_display - 1)
                thumb.setText(f"+{remain}")
                thumb.setStyleSheet(self._thumb_style(selected=False, is_placeholder=True))
                thumb.setToolTip(f"还有 {remain} 张未展示（共 {len(self.files)} 张）")
            else:
                is_selected = (i == self._selected_index)
                thumb.setStyleSheet(self._thumb_style(selected=is_selected))
                thumb.setToolTip(Path(path).name)
                # 左键选中预览
                thumb.mousePressEvent = lambda event, idx=i, p=path: self._on_thumb_clicked(event, idx, p)
                # 仅真实缩略图支持右键删除
                thumb.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                thumb.customContextMenuRequested.connect(
                    lambda pos, idx=i: self._show_context_menu(pos, idx)
                )

            self.grid_layout.addWidget(thumb, row, col)
            self.thumb_labels.append(thumb)

        # ➕ 追加卡：紧跟最后一张缩略图（Phase 13：自适应位置）
        add_idx = len(display_files)  # 0..max_display
        self.add_card = self._build_add_card()
        self.grid_layout.addWidget(self.add_card, add_idx // cols, add_idx % cols)

        # 启动异步加载（仅真实缩略图，跳过 +N 占位格）
        load_count = max_display - 1 if overflow else len(display_files)
        load_files = display_files[:load_count]

        # Phase 9：统一线程生命周期 — parent=self 走 Qt 父子链；finished → 清 Python 引用 + deleteLater
        if self.loader_thread is not None and self.loader_thread.isRunning():
            self.loader_thread.cancel()
            self.loader_thread.wait(1000)

        if load_files:
            thread = ThumbLoaderThread(load_files, parent=self)
            thread.thumbnail_ready.connect(self._on_thumbnail_ready)
            thread.finished.connect(self._on_loader_finished)
            thread.finished.connect(thread.deleteLater)
            self.loader_thread = thread
            thread.start()

    def _thumb_style(self, selected: bool = False, is_placeholder: bool = False) -> str:
        """生成缩略图 QLabel 的样式表。"""
        if is_placeholder:
            return """
                QLabel {
                    border: 1px solid #333333;
                    border-radius: 4px;
                    color: #999999;
                    font-size: 18px;
                    font-weight: bold;
                    background-color: #1E1E1E;
                }
            """
        if selected:
            return """
                QLabel {
                    border: 2px solid #4A9EFF;
                    border-radius: 4px;
                    background-color: #1A2A3A;
                }
            """
        return """
            QLabel {
                border: 1px solid #333333;
                border-radius: 4px;
            }
            QLabel:hover {
                border: 1px solid #666666;
            }
        """

    def _on_thumb_clicked(self, event, index: int, path: str) -> None:
        """缩略图左键点击 — 选中为预览源。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._select_thumbnail(index)
            self.file_selected.emit(index, path)

    def _select_thumbnail(self, index: int) -> None:
        """更新选中状态的高亮边框。"""
        prev = self._selected_index
        self._selected_index = index
        # 刷新旧选中和新选中的样式
        if 0 <= prev < len(self.thumb_labels) and prev != index:
            label = self.thumb_labels[prev]
            if not label.text().startswith("+"):
                label.setStyleSheet(self._thumb_style(selected=False))
        if 0 <= index < len(self.thumb_labels):
            label = self.thumb_labels[index]
            if not label.text().startswith("+"):
                label.setStyleSheet(self._thumb_style(selected=True))

    def _build_add_card(self) -> QToolButton:
        """构建第 6 格的 ➕ 追加卡（QToolButton 支持 :hover 伪类与无障碍焦点）。"""
        btn = QToolButton()
        btn.setText("＋")
        btn.setFixedSize(self.THUMB_W, self.THUMB_H)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip("添加更多图片（也可直接拖拽到此区域）")
        btn.setStyleSheet("""
            QToolButton {
                border: 2px dashed #666666;
                border-radius: 4px;
                color: #999999;
                font-size: 28px;
                font-weight: bold;
                background-color: transparent;
            }
            QToolButton:hover {
                border-color: #E0E0E0;
                color: #E0E0E0;
                background-color: #2A2A2A;
            }
            QToolButton:pressed {
                background-color: #1E1E1E;
            }
        """)
        btn.clicked.connect(self._on_select_files)
        return btn

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
        """左键点击空白处追加图片（Phase 12：兜底逻辑 — 非缩略图区域均触发追加）。

        注意：QToolButton（➕ 卡）和 QPushButton（empty_btn）会自行消费鼠标事件，
        其 ``clicked`` 信号已连接到 ``_on_select_files``；此处仅处理事件冒泡到容器自身的情况
        （即点中 grid_widget 空白 / 缩略图之间的间隙 / 容器 padding 等）。
        """
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.pos())
            # 命中真实缩略图或 +N 占位 → 让事件继续向下分发（右键菜单等）
            if child in self.thumb_labels:
                super().mousePressEvent(event)
                return
            # 其他所有情况（grid_widget 空白 / 容器边距）→ 触发追加
            self._on_select_files()
