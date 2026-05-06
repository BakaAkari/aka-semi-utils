"""水印配置面板 — Phase 8 干净重构（单视图 Accordion + 就地编辑 MVVM）。

设计原则
========

1. **只有一棵控件树** —— 4 个角始终是垂直堆叠的 Accordion，无双视图、无 ``QStackedLayout``、
   无 ``resizeEvent`` 切换。窗口宽度从 580px 到 1600px 都用同一份布局。

2. **就地编辑 (in-place mutate)** —— Chip 行控件持有 :class:`FieldChip` 引用，
   用户操作直接 mutate 该 dataclass。父级 :class:`CornerSection` 持有 :class:`CornerConfig`
   引用，对其 chips/separator/font/color 字段同样 mutate。

3. **不订阅自己的写** —— 控件改 state 后，通过 :meth:`AppState.set_corner_config`
   写回（触发 ``watermark_changed`` 用于 autosave + 预览刷新），但本面板**不订阅**
   ``watermark_changed`` 进行 reload。仅订阅 ``state_reloaded`` 这种"外部全量替换"
   信号（load_from_disk / reset_to_defaults）做整树重建。

4. **没有 commit / reload 往返** —— 因此也就没有 ``_committing`` / ``_suppress_reload``
   等 flag，没有 ``setParent(None)`` workaround，没有 ``deleteLater`` 时序问题。

代码组织
========

- :class:`ChipDetailPopup`     —— ⚙ 弹窗：编辑 chip 级 color / font / custom_text
- :class:`ChipRowWidget`       —— 单行：``[字段▼] [⚙] [◀] [▶] [×]``
- :class:`CornerSection`       —— 单角 Accordion：标题行 + chip 列表 + 控制行
- :class:`LogoTab`             —— Logo + 全局自定义文本
- :class:`ConfigPanel`         —— 顶层 Tab：水印 / Logo
"""

from __future__ import annotations

from typing import ClassVar

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFontDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gui.field_registry import FieldRegistry, get_default_registry
from gui.models import AppState, CornerConfig, FieldChip, LogoConfig

# ---------- 常量 ----------

DEFAULT_SEPARATOR = " "  # 默认分隔符为空格（用户反馈）

CORNER_LABELS: dict[str, tuple[str, str]] = {
    "left_top": ("↖", "左上"),
    "right_top": ("↗", "右上"),
    "left_bottom": ("↙", "左下"),
    "right_bottom": ("↘", "右下"),
}

CORNER_ORDER: list[str] = ["left_top", "right_top", "left_bottom", "right_bottom"]


# =============================================================================
# ChipDetailPopup — chip 级覆盖项弹窗
# =============================================================================


class ChipDetailPopup(QDialog):
    """编辑单个 :class:`FieldChip` 的覆盖项（custom_text / color / font）。

    使用模式：直接 mutate 传入的 chip 引用。点击"取消"则回滚为 popup 打开时的快照。
    """

    def __init__(self, chip: FieldChip, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.chip = chip

        # 快照用于取消时回滚
        self._snapshot = (chip.custom_text, chip.font, chip.color)

        self.setWindowTitle("字段详情")
        self.setModal(True)
        self.setMinimumWidth(360)
        self._setup_ui()

    # ---- UI ----

    def _setup_ui(self) -> None:
        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        # 自定义文本（仅 custom_text 字段可编辑）
        self.custom_text_input = QLineEdit(self.chip.custom_text)
        self.custom_text_input.setPlaceholderText("仅「自定义文本」字段使用")
        self.custom_text_input.setEnabled(self.chip.field_id == "custom_text")
        form.addRow("自定义文本：", self.custom_text_input)

        # 字段颜色（空 = 继承）
        color_row = QHBoxLayout()
        self.color_btn = QPushButton()
        self.color_btn.setFixedHeight(28)
        self.color_btn.setMinimumWidth(120)
        self.color_btn.clicked.connect(self._pick_color)
        clear_color_btn = QToolButton()
        clear_color_btn.setText("继承")
        clear_color_btn.setToolTip("清空此 chip 的颜色覆盖，继承角级颜色")
        clear_color_btn.clicked.connect(self._clear_color)
        color_row.addWidget(self.color_btn, 1)
        color_row.addWidget(clear_color_btn)
        self._refresh_color_btn()
        form.addRow("字段颜色：", color_row)

        # 字段字体（空 = 继承）
        font_row = QHBoxLayout()
        self.font_btn = QPushButton(self.chip.font or "（继承）")
        self.font_btn.setFixedHeight(28)
        self.font_btn.clicked.connect(self._pick_font)
        clear_font_btn = QToolButton()
        clear_font_btn.setText("继承")
        clear_font_btn.setToolTip("清空此 chip 的字体覆盖，继承角级字体")
        clear_font_btn.clicked.connect(self._clear_font)
        font_row.addWidget(self.font_btn, 1)
        font_row.addWidget(clear_font_btn)
        form.addRow("字段字体：", font_row)

        # 按钮栏
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_ok)
        button_box.rejected.connect(self._on_cancel)
        form.addRow(button_box)

    # ---- 颜色 ----

    def _pick_color(self) -> None:
        initial = QColor(self.chip.color) if self.chip.color else QColor("#FFFFFF")
        color = QColorDialog.getColor(initial, self, "选择字段颜色")
        if color.isValid():
            self.chip.color = color.name()
            self._refresh_color_btn()

    def _clear_color(self) -> None:
        self.chip.color = ""
        self._refresh_color_btn()

    def _refresh_color_btn(self) -> None:
        if self.chip.color:
            self.color_btn.setText(self.chip.color)
            self.color_btn.setStyleSheet(
                f"QPushButton {{ background:{self.chip.color}; color: black; border: 1px solid #888; }}"
            )
        else:
            self.color_btn.setText("（继承）")
            self.color_btn.setStyleSheet("")

    # ---- 字体 ----

    def _pick_font(self) -> None:
        initial = QFont(self.chip.font) if self.chip.font else QFont()
        font, ok = QFontDialog.getFont(initial, self, "选择字段字体")
        if ok:
            self.chip.font = font.family()
            self.font_btn.setText(self.chip.font)

    def _clear_font(self) -> None:
        self.chip.font = ""
        self.font_btn.setText("（继承）")

    # ---- 提交 / 取消 ----

    def _on_ok(self) -> None:
        # 提交 custom_text 的最新值
        self.chip.custom_text = self.custom_text_input.text()
        self.accept()

    def _on_cancel(self) -> None:
        # 回滚快照
        self.chip.custom_text, self.chip.font, self.chip.color = self._snapshot
        self.reject()


# =============================================================================
# ChipRowWidget — 单行紧凑控件（5 个可视控件）
# =============================================================================


class ChipRowWidget(QFrame):
    """单个 :class:`FieldChip` 的紧凑行控件。

    布局：``[字段类型 ComboBox] [stretch] [⚙] [◀] [▶] [×]``

    - 直接持有 ``FieldChip`` 引用，就地 mutate
    - ``changed`` 信号在数据变化时发出，由父 :class:`CornerSection` 接收并把
      最新 :class:`CornerConfig` 推回 :class:`AppState`
    """

    changed = pyqtSignal()
    move_left_requested = pyqtSignal(object)   # ChipRowWidget
    move_right_requested = pyqtSignal(object)  # ChipRowWidget
    delete_requested = pyqtSignal(object)      # ChipRowWidget

    def __init__(
        self,
        chip: FieldChip,
        registry: FieldRegistry | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.chip = chip
        self.registry = registry or get_default_registry()
        self._loading = False
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self._setup_ui()
        self._sync_from_chip()

    # ---- UI ----

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        # 字段类型下拉
        self.type_combo = QComboBox()
        self.type_combo.setMinimumWidth(110)
        for fdef in self.registry.all():
            if fdef.field_id == "empty":
                continue
            self.type_combo.addItem(fdef.label_zh, userData=fdef.field_id)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        layout.addWidget(self.type_combo, 1)

        # ⚙ 详情
        self.detail_btn = QToolButton()
        self.detail_btn.setText("⚙")
        self.detail_btn.setToolTip("编辑此字段的颜色 / 字体 / 自定义文本")
        self.detail_btn.setFixedWidth(28)
        self.detail_btn.clicked.connect(self._open_detail_popup)
        layout.addWidget(self.detail_btn)

        # ◀ ▶ ×
        self.left_btn = QToolButton()
        self.left_btn.setText("◀")
        self.left_btn.setFixedWidth(24)
        self.left_btn.setToolTip("左移")
        self.left_btn.clicked.connect(lambda: self.move_left_requested.emit(self))
        layout.addWidget(self.left_btn)

        self.right_btn = QToolButton()
        self.right_btn.setText("▶")
        self.right_btn.setFixedWidth(24)
        self.right_btn.setToolTip("右移")
        self.right_btn.clicked.connect(lambda: self.move_right_requested.emit(self))
        layout.addWidget(self.right_btn)

        self.delete_btn = QToolButton()
        self.delete_btn.setText("×")
        self.delete_btn.setFixedWidth(24)
        self.delete_btn.setToolTip("删除此字段")
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self))
        layout.addWidget(self.delete_btn)

    # ---- 同步 ----

    def _sync_from_chip(self) -> None:
        """根据 self.chip 刷新控件显示。"""
        self._loading = True
        try:
            # 选中对应 field_id
            target_idx = -1
            for i in range(self.type_combo.count()):
                if self.type_combo.itemData(i) == self.chip.field_id:
                    target_idx = i
                    break
            if target_idx >= 0:
                self.type_combo.setCurrentIndex(target_idx)
            self._refresh_detail_indicator()
        finally:
            self._loading = False

    def _refresh_detail_indicator(self) -> None:
        """⚙ 上有覆盖项时高亮（蓝点 + 蓝色文字）。"""
        has_override = bool(self.chip.color or self.chip.font) or (
            self.chip.field_id == "custom_text" and bool(self.chip.custom_text)
        )
        if has_override:
            self.detail_btn.setText("⚙ •")
            self.detail_btn.setStyleSheet("QToolButton { color: #1976d2; font-weight: bold; }")
        else:
            self.detail_btn.setText("⚙")
            self.detail_btn.setStyleSheet("")

    # ---- 事件 ----

    def _on_type_changed(self, _idx: int) -> None:
        if self._loading:
            return
        new_id = self.type_combo.currentData()
        if isinstance(new_id, str) and new_id != self.chip.field_id:
            self.chip.field_id = new_id
            self._refresh_detail_indicator()
            self.changed.emit()

    def _open_detail_popup(self) -> None:
        popup = ChipDetailPopup(self.chip, self)
        if popup.exec() == QDialog.DialogCode.Accepted:
            self._refresh_detail_indicator()
            self.changed.emit()


# =============================================================================
# CornerSection — 单角 Accordion（标题 + 内容）
# =============================================================================


class CornerSection(QFrame):
    """单角配置的可折叠区块。

    包含：
    - 标题栏（``▼ ↖ 左上 (3 字段)``）+ 角级色 / 字体（紧凑）
    - 内容区（chip 列表 + ``+ 添加字段`` + ``分隔符: [_]``）

    持有 :class:`CornerConfig` 引用，所有用户操作直接 mutate；
    然后调用 ``state.set_corner_config(corner_attr, config)`` 触发 autosave / 预览刷新。
    """

    MAX_CHIPS = 8

    def __init__(
        self,
        corner_attr: str,
        state: AppState,
        registry: FieldRegistry | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.corner_attr = corner_attr
        self.state = state
        self.registry = registry or get_default_registry()

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)

        self._chip_rows: list[ChipRowWidget] = []
        self._expanded = True
        self._setup_ui()
        self._rebuild_from_state()

    # ---- UI ----

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # ── 标题行 ──
        header = QHBoxLayout()
        header.setSpacing(6)

        self.toggle_btn = QToolButton()
        self.toggle_btn.setText("▼")
        self.toggle_btn.setFixedWidth(22)
        self.toggle_btn.clicked.connect(self._toggle)
        header.addWidget(self.toggle_btn)

        icon, name = CORNER_LABELS[self.corner_attr]
        self.title_label = QLabel(f"{icon} {name}")
        self.title_label.setStyleSheet("font-weight: bold;")
        header.addWidget(self.title_label)

        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("color: #888;")
        header.addWidget(self.summary_label)
        header.addStretch(1)

        # 角级颜色
        header.addWidget(QLabel("色"))
        self.corner_color_btn = QPushButton()
        self.corner_color_btn.setFixedSize(56, 24)
        self.corner_color_btn.clicked.connect(self._pick_corner_color)
        header.addWidget(self.corner_color_btn)

        # 角级字体
        self.corner_font_btn = QPushButton("字体")
        self.corner_font_btn.setFixedHeight(24)
        self.corner_font_btn.clicked.connect(self._pick_corner_font)
        header.addWidget(self.corner_font_btn)

        # 重置角级样式
        reset_btn = QToolButton()
        reset_btn.setText("⤺")
        reset_btn.setToolTip("重置角级颜色 / 字体（继承全局）")
        reset_btn.clicked.connect(self._reset_corner_style)
        header.addWidget(reset_btn)

        layout.addLayout(header)

        # ── 内容区（可折叠） ──
        self.content = QFrame()
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(8, 0, 0, 0)
        content_layout.setSpacing(4)

        # chip 列表容器
        self.chips_container = QWidget()
        self.chips_layout = QVBoxLayout(self.chips_container)
        self.chips_layout.setContentsMargins(0, 0, 0, 0)
        self.chips_layout.setSpacing(3)
        content_layout.addWidget(self.chips_container)

        # 控制行：+ 添加字段 + 分隔符
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(8)
        self.add_btn = QPushButton("+ 添加字段")
        self.add_btn.setFixedHeight(26)
        self.add_btn.clicked.connect(self._on_add_chip)
        ctrl_row.addWidget(self.add_btn)

        ctrl_row.addStretch(1)
        ctrl_row.addWidget(QLabel("分隔符："))
        self.sep_input = QLineEdit()
        self.sep_input.setFixedWidth(70)
        self.sep_input.setMaxLength(8)
        self.sep_input.editingFinished.connect(self._on_separator_changed)
        ctrl_row.addWidget(self.sep_input)

        content_layout.addLayout(ctrl_row)
        layout.addWidget(self.content)

    # ---- 数据访问辅助 ----

    @property
    def corner(self) -> CornerConfig:
        """返回当前 :class:`CornerConfig`（直接持有 AppState 中的引用）。"""
        return getattr(self.state, self.corner_attr)

    def _push_to_state(self) -> None:
        """把当前 corner 推回 :class:`AppState` —— 触发 autosave + 预览刷新。

        注意：本面板 *不* 订阅 ``watermark_changed`` 信号，因此此调用不会回弹到
        本面板的 reload 逻辑，没有重入风险。
        """
        self.state.set_corner_config(self.corner_attr, self.corner)

    # ---- 整树重建（仅在外部全量替换时调用） ----

    def _rebuild_from_state(self) -> None:
        """根据 :attr:`corner` 重建所有 chip 行 + 标题 + 控制行。

        本方法仅在 :class:`ConfigPanel` 收到 ``state_reloaded``（外部全量替换：
        load_from_disk / reset_to_defaults）信号时被调用。日常用户操作不走此路径。
        """
        # 清空旧 chip 行
        while self.chips_layout.count():
            item = self.chips_layout.takeAt(0)
            w = item.widget() if item else None
            if w is not None:
                w.deleteLater()
        self._chip_rows.clear()

        # 重建 chip 行
        for chip in self.corner.chips:
            self._add_chip_widget(chip)

        # 分隔符
        self.sep_input.blockSignals(True)
        self.sep_input.setText(self.corner.separator)
        self.sep_input.blockSignals(False)

        # 角级色 / 字体
        self._refresh_corner_color_btn()
        self._refresh_corner_font_btn()
        self._refresh_summary()
        self._refresh_add_btn()

    def _add_chip_widget(self, chip: FieldChip) -> ChipRowWidget:
        row = ChipRowWidget(chip, registry=self.registry, parent=self.chips_container)
        row.changed.connect(self._on_chip_changed)
        row.move_left_requested.connect(self._on_move_left)
        row.move_right_requested.connect(self._on_move_right)
        row.delete_requested.connect(self._on_delete_chip)
        self.chips_layout.addWidget(row)
        self._chip_rows.append(row)
        return row

    # ---- chip 事件 ----

    def _on_chip_changed(self) -> None:
        # 单 chip 内部已经 mutate 完毕，这里只需 push 到 state
        self._refresh_summary()
        self._push_to_state()

    def _on_add_chip(self) -> None:
        if len(self.corner.chips) >= self.MAX_CHIPS:
            return
        new_chip = FieldChip(field_id="camera_model")
        self.corner.chips.append(new_chip)
        self._add_chip_widget(new_chip)
        self._refresh_summary()
        self._refresh_add_btn()
        self._push_to_state()

    def _on_delete_chip(self, row: ChipRowWidget) -> None:
        if row not in self._chip_rows:
            return
        idx = self._chip_rows.index(row)
        # 同步从数据 + UI 列表中移除
        del self.corner.chips[idx]
        self._chip_rows.remove(row)
        self.chips_layout.removeWidget(row)
        row.deleteLater()
        self._refresh_summary()
        self._refresh_add_btn()
        self._push_to_state()

    def _on_move_left(self, row: ChipRowWidget) -> None:
        if row not in self._chip_rows:
            return
        idx = self._chip_rows.index(row)
        if idx <= 0:
            return
        # 数据交换
        chips = self.corner.chips
        chips[idx - 1], chips[idx] = chips[idx], chips[idx - 1]
        # UI 交换
        self._chip_rows[idx - 1], self._chip_rows[idx] = self._chip_rows[idx], self._chip_rows[idx - 1]
        self.chips_layout.removeWidget(row)
        self.chips_layout.insertWidget(idx - 1, row)
        self._push_to_state()

    def _on_move_right(self, row: ChipRowWidget) -> None:
        if row not in self._chip_rows:
            return
        idx = self._chip_rows.index(row)
        if idx >= len(self._chip_rows) - 1:
            return
        chips = self.corner.chips
        chips[idx], chips[idx + 1] = chips[idx + 1], chips[idx]
        self._chip_rows[idx], self._chip_rows[idx + 1] = self._chip_rows[idx + 1], self._chip_rows[idx]
        self.chips_layout.removeWidget(row)
        self.chips_layout.insertWidget(idx + 1, row)
        self._push_to_state()

    # ---- 分隔符 ----

    def _on_separator_changed(self) -> None:
        new_sep = self.sep_input.text()
        if new_sep != self.corner.separator:
            self.corner.separator = new_sep
            self._push_to_state()

    # ---- 角级色 / 字体 ----

    def _pick_corner_color(self) -> None:
        initial = QColor(self.corner.color) if self.corner.color else QColor("#FFFFFF")
        color = QColorDialog.getColor(initial, self, "选择角级颜色")
        if color.isValid():
            self.corner.color = color.name()
            self._refresh_corner_color_btn()
            self._push_to_state()

    def _pick_corner_font(self) -> None:
        initial = QFont(self.corner.font) if self.corner.font else QFont()
        font, ok = QFontDialog.getFont(initial, self, "选择角级字体")
        if ok:
            self.corner.font = font.family()
            self._refresh_corner_font_btn()
            self._push_to_state()

    def _reset_corner_style(self) -> None:
        if not self.corner.color and not self.corner.font:
            return
        self.corner.color = ""
        self.corner.font = ""
        self._refresh_corner_color_btn()
        self._refresh_corner_font_btn()
        self._push_to_state()

    def _refresh_corner_color_btn(self) -> None:
        if self.corner.color:
            self.corner_color_btn.setText(self.corner.color)
            self.corner_color_btn.setStyleSheet(
                f"QPushButton {{ background:{self.corner.color}; color: black; border: 1px solid #888; }}"
            )
        else:
            self.corner_color_btn.setText("继承")
            self.corner_color_btn.setStyleSheet("")

    def _refresh_corner_font_btn(self) -> None:
        self.corner_font_btn.setText(self.corner.font or "字体")

    # ---- 标题摘要 / 添加按钮可见性 ----

    def _refresh_summary(self) -> None:
        n = len(self.corner.chips)
        self.summary_label.setText(f"({n} 字段)")

    def _refresh_add_btn(self) -> None:
        self.add_btn.setEnabled(len(self.corner.chips) < self.MAX_CHIPS)

    # ---- 折叠 ----

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self.content.setVisible(self._expanded)
        self.toggle_btn.setText("▼" if self._expanded else "▶")

    def set_expanded(self, expanded: bool) -> None:
        if expanded != self._expanded:
            self._toggle()


# =============================================================================
# LogoTab — Logo + 全局自定义文本
# =============================================================================


class LogoTab(QWidget):
    """Logo + 全局自定义文本。

    用 :class:`QFormLayout` 配合 ``WrapLongRows`` 策略，窄窗口下 label 不会被截断。
    """

    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self._loading = False
        self._setup_ui()
        self._load_state()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(8)

        # Logo 模式
        self.enabled_combo = QComboBox()
        self.enabled_combo.addItem("自动（按品牌）", "auto")
        self.enabled_combo.addItem("禁用", "disabled")
        self.enabled_combo.addItem("自定义", "custom")
        self.enabled_combo.currentIndexChanged.connect(self._on_changed)
        form.addRow("Logo 模式：", self.enabled_combo)

        # Logo 位置
        self.position_combo = QComboBox()
        self.position_combo.addItem("右侧", "right")
        self.position_combo.addItem("居中", "center")
        self.position_combo.addItem("左侧", "left")
        self.position_combo.currentIndexChanged.connect(self._on_changed)
        form.addRow("Logo 位置：", self.position_combo)

        # 分隔线颜色
        color_row = QHBoxLayout()
        self.color_btn = QPushButton()
        self.color_btn.setFixedHeight(28)
        self.color_btn.setMinimumWidth(120)
        self.color_btn.clicked.connect(self._pick_logo_color)
        color_row.addWidget(self.color_btn, 1)
        form.addRow("分隔线颜色：", color_row)

        # 自定义 Logo 路径
        path_row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.editingFinished.connect(self._on_changed)
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_logo)
        path_row.addWidget(self.path_input, 1)
        path_row.addWidget(browse_btn)
        form.addRow("自定义路径：", path_row)

        # 全局自定义文本
        self.custom_text_input = QLineEdit()
        self.custom_text_input.setPlaceholderText("可在 chip 类型为「自定义文本」时使用")
        self.custom_text_input.editingFinished.connect(self._on_custom_text_changed)
        form.addRow("全局自定义文本：", self.custom_text_input)

        outer.addLayout(form)
        outer.addStretch(1)

    # ---- 加载 / 提交 ----

    def _load_state(self) -> None:
        self._loading = True
        try:
            logo = self.state.logo
            idx = self.enabled_combo.findData(logo.enabled)
            self.enabled_combo.setCurrentIndex(idx if idx >= 0 else 0)
            idx = self.position_combo.findData(logo.position)
            self.position_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self.path_input.setText(logo.custom_path)
            self._refresh_color_btn(logo.color)
            self.custom_text_input.setText(self.state.custom_text)
        finally:
            self._loading = False

    def _on_changed(self, *_args) -> None:
        if self._loading:
            return
        new_logo = LogoConfig(
            enabled=self.enabled_combo.currentData() or "auto",
            position=self.position_combo.currentData() or "right",
            color=self.state.logo.color,
            custom_path=self.path_input.text(),
        )
        self.state.set_logo_config(new_logo)

    def _on_custom_text_changed(self) -> None:
        if self._loading:
            return
        self.state.set_custom_text(self.custom_text_input.text())

    # ---- 颜色 ----

    def _pick_logo_color(self) -> None:
        initial = QColor(self.state.logo.color) if self.state.logo.color else QColor("#D8D8D6")
        color = QColorDialog.getColor(initial, self, "选择分隔线颜色")
        if color.isValid():
            new_logo = LogoConfig(
                enabled=self.state.logo.enabled,
                position=self.state.logo.position,
                color=color.name(),
                custom_path=self.state.logo.custom_path,
            )
            self.state.set_logo_config(new_logo)
            self._refresh_color_btn(color.name())

    def _refresh_color_btn(self, color: str) -> None:
        self.color_btn.setText(color or "（默认）")
        if color:
            self.color_btn.setStyleSheet(
                f"QPushButton {{ background:{color}; color: black; border: 1px solid #888; }}"
            )
        else:
            self.color_btn.setStyleSheet("")

    # ---- Logo 浏览 ----

    def _browse_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 Logo 文件", "", "图片文件 (*.png *.jpg *.jpeg)"
        )
        if path:
            self.path_input.setText(path)
            self._on_changed()


# =============================================================================
# ConfigPanel — 顶层 Tab 容器
# =============================================================================


class ConfigPanel(QWidget):
    """水印配置主面板（单视图 Accordion）。

    架构：
    - Tab "水印"：4 个 :class:`CornerSection` 垂直堆叠 + 滚动条
    - Tab "Logo"：:class:`LogoTab`

    本面板**不订阅** ``state.watermark_changed``，因此用户编辑不会触发重入式重建。
    仅订阅 ``state.state_reloaded``（外部全量替换：load/reset）做整树重建。
    """

    CORNER_ATTRS: ClassVar[list[str]] = CORNER_ORDER

    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self.registry = get_default_registry()
        self._sections: dict[str, CornerSection] = {}
        self._setup_ui()

        # 仅订阅"外部全量替换"信号；不订阅 watermark_changed（避免自激发循环）
        self.state.state_reloaded.connect(self._reload_all_from_state)

    # ---- UI ----

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs)

        # Tab 1：水印
        watermark_tab = QWidget()
        wm_layout = QVBoxLayout(watermark_tab)
        wm_layout.setContentsMargins(0, 0, 0, 0)
        wm_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        wm_inner = QWidget()
        wm_inner_layout = QVBoxLayout(wm_inner)
        wm_inner_layout.setContentsMargins(8, 8, 8, 8)
        wm_inner_layout.setSpacing(8)

        for corner_attr in self.CORNER_ATTRS:
            section = CornerSection(corner_attr, self.state, registry=self.registry)
            self._sections[corner_attr] = section
            wm_inner_layout.addWidget(section)

        wm_inner_layout.addStretch(1)
        scroll.setWidget(wm_inner)
        wm_layout.addWidget(scroll)
        self.tabs.addTab(watermark_tab, "水印")

        # Tab 2：Logo
        self.logo_tab = LogoTab(self.state)
        self.tabs.addTab(self.logo_tab, "Logo")

    # ---- 外部触发的整树重建 ----

    def _reload_all_from_state(self, *_args) -> None:
        """``load_from_disk`` / ``reset_to_defaults`` 等外部全量替换后整体重建 UI。"""
        for section in self._sections.values():
            section._rebuild_from_state()
        self.logo_tab._load_state()
