"""统一字体选择器 — 所有层级共用。

设计要点
========

- **数据源唯一**：只读 ``config/fonts/`` 目录，不依赖系统字体。
- **实时预览**：右侧固定 QLabel，选中即渲染预览图。
- **一键打开字体文件夹**：用户可自行拖入 ``.ttf/.otf``，点刷新即可生效。
- **零系统依赖**：Windows/macOS/Linux 行为一致，打包后不会缺字体。
"""

from __future__ import annotations

from PyQt6.QtCore import QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QToolButton,
    QWidget,
)

from core.font_manager import FONTS_DIR, list_fonts
from gui.font_preview import FontPreview


class FontSelector(QWidget):
    """统一字体选择组件。

    信号
    ----
    font_changed(str)
        字体文件名变更时发出（空字符串表示"继承/未选"）。
    """

    font_changed = pyqtSignal(str)

    def __init__(
        self,
        font_name: str = "",
        color: str = "#FFFFFF",
        show_open_folder: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._color = color
        self._show_open_folder = show_open_folder
        self._setup_ui()
        self.set_font(font_name)

    # ---- UI ----

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 字体下拉
        self.font_combo = QComboBox()
        self.font_combo.setMinimumWidth(180)
        self._refresh_combo_items()
        self.font_combo.currentTextChanged.connect(self._on_font_changed)
        layout.addWidget(self.font_combo)

        # 实时预览
        self.preview = FontPreview(color=self._color)
        layout.addWidget(self.preview)

        # 继承按钮（用于角级/Chip 级，清空覆盖）
        self.inherit_btn = QToolButton()
        self.inherit_btn.setText("继承")
        self.inherit_btn.setToolTip("清空字体覆盖，继承上级设置")
        self.inherit_btn.clicked.connect(self._on_inherit)
        layout.addWidget(self.inherit_btn)

        # 刷新按钮
        self.refresh_btn = QToolButton()
        self.refresh_btn.setText("⟳")
        self.refresh_btn.setToolTip("重新扫描 fonts 目录")
        self.refresh_btn.clicked.connect(self._on_refresh)
        layout.addWidget(self.refresh_btn)

        # 打开文件夹（可选）
        if self._show_open_folder:
            self.open_btn = QToolButton()
            self.open_btn.setText("📁")
            self.open_btn.setToolTip("打开 fonts 文件夹，可拖入新字体")
            self.open_btn.clicked.connect(self._on_open_folder)
            layout.addWidget(self.open_btn)

        layout.addStretch(1)

    # ---- 公共 API ----

    def set_font(self, font_name: str) -> None:
        """设置当前字体（空字符串 = 继承）。"""
        if not font_name:
            self.font_combo.setCurrentIndex(-1)
            self.preview.set_font("")
            return
        idx = self.font_combo.findText(font_name)
        if idx >= 0:
            self.font_combo.setCurrentIndex(idx)
        else:
            # 字体文件不存在，回退到空（继承）
            self.font_combo.setCurrentIndex(-1)
            self.preview.set_font("")

    def current_font(self) -> str:
        """返回当前选中的字体文件名（空字符串 = 继承/未选）。"""
        return self.font_combo.currentText()

    def set_color(self, color: str) -> None:
        """更新预览颜色。"""
        self._color = color
        self.preview.set_color(color)

    def set_inherit_visible(self, visible: bool) -> None:
        """控制"继承"按钮的显隐（全局字体不需要）。"""
        self.inherit_btn.setVisible(visible)

    # ---- 内部 ----

    def _refresh_combo_items(self) -> None:
        """重新扫描目录并填充下拉列表。"""
        current = self.font_combo.currentText()
        self.font_combo.blockSignals(True)
        self.font_combo.clear()
        fonts = list_fonts()
        self.font_combo.addItems(fonts)
        if current:
            idx = self.font_combo.findText(current)
            if idx >= 0:
                self.font_combo.setCurrentIndex(idx)
        self.font_combo.blockSignals(False)

    def _on_font_changed(self, font_name: str) -> None:
        self.preview.set_font(font_name)
        self.font_changed.emit(font_name)

    def _on_inherit(self) -> None:
        self.font_combo.setCurrentIndex(-1)
        self.preview.set_font("")
        self.font_changed.emit("")

    def _on_refresh(self) -> None:
        self._refresh_combo_items()
        # 刷新后如果当前选中项还在，重新触发预览
        current = self.font_combo.currentText()
        if current:
            self.preview.set_font(current)

    def _on_open_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(FONTS_DIR)))
