"""水印配置面板 — Phase 8 干净重构（单视图 Accordion + 就地编辑 MVVM）。

设计原则
========

1. **只有一棵控件树** —— 4 个角始终是垂直堆叠的 Accordion，无双视图、无 ``QStackedLayout``、
   无 ``resizeEvent`` 切换。窗口宽度从 580px 到 1600px 都用同一份布局。

2. **就地编辑 (in-place mutate)** —— Chip 行控件持有 :class:`FieldChip` 引用，
   用户操作直接 mutate 该 dataclass。父级 :class:`CornerSection` 持有 :class:`CornerConfig`
   引用，对其 chips/separator/font_size 字段同样 mutate。
   font 和 color 统一由全局参数决定，不在水印配置中覆盖。

3. **不订阅自己的写** —— 控件改 state 后，通过 :meth:`AppState.set_corner_config`
   写回（触发 ``watermark_changed`` 用于 autosave + 预览刷新），但本面板**不订阅**
   ``watermark_changed`` 进行 reload。仅订阅 ``state_reloaded`` 这种"外部全量替换"
   信号（load_from_disk / reset_to_defaults）做整树重建。

4. **没有 commit / reload 往返** —— 因此也就没有 ``_committing`` / ``_suppress_reload``
   等 flag，没有 ``setParent(None)`` workaround，没有 ``deleteLater`` 时序问题。

代码组织
========

- :class:`ChipDetailPopup`     —— ⚙ 弹窗：编辑 chip 级 custom_text
- :class:`ChipRowWidget`       —— 单行：``[字段▼] [⚙] [◀] [▶] [×]``
- :class:`CornerSection`       —— 单角 Accordion：标题行 + chip 列表 + 控制行
- :class:`LogoTab`             —— Logo + 全局自定义文本
- :class:`SignatureTab`        —— Phase 25：签名（位置/缩放/偏移）独立子 Tab
- :class:`ConfigPanel`         —— 顶层 Tab：水印 / Logo / 签名
"""

from __future__ import annotations

from dataclasses import replace
from typing import ClassVar

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gui.field_registry import FieldRegistry, get_default_registry
from gui.models import AppState, CornerConfig, FieldChip, LogoConfig
from gui.wheel_guard import guard_wheel, guard_wheel_for_children

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
    """编辑单个 :class:`FieldChip` 的覆盖项（仅 custom_text）。

    使用模式：直接 mutate 传入的 chip 引用。点击"取消"则回滚为 popup 打开时的快照。
    """

    def __init__(self, chip: FieldChip, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.chip = chip

        # 快照用于取消时回滚
        self._snapshot = chip.custom_text

        self.setWindowTitle("字段详情")
        self.setModal(True)
        self.setMinimumWidth(300)
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

        # 按钮栏
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_ok)
        button_box.rejected.connect(self._on_cancel)
        form.addRow(button_box)

    # ---- 提交 / 取消 ----

    def _on_ok(self) -> None:
        # 提交 custom_text 的最新值
        self.chip.custom_text = self.custom_text_input.text()
        self.accept()

    def _on_cancel(self) -> None:
        # 回滚快照
        self.chip.custom_text = self._snapshot
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
        guard_wheel(self.type_combo)
        layout.addWidget(self.type_combo, 1)

        # ⚙ 详情
        self.detail_btn = QToolButton()
        self.detail_btn.setText("⚙")
        self.detail_btn.setToolTip("编辑此字段的自定义文本")
        self.detail_btn.setFixedWidth(28)
        self.detail_btn.clicked.connect(self._open_detail_popup)
        layout.addWidget(self.detail_btn)

        # ↑ ↓ ×
        # 字段在 UI 中是纵向列表，但渲染时仍按列表顺序做左右排序：
        # ↑ = 排序提前（原左移），↓ = 排序后移（原右移）。
        self.left_btn = QToolButton()
        self.left_btn.setText("↑")
        self.left_btn.setFixedWidth(24)
        self.left_btn.setToolTip("上移（排序提前）")
        self.left_btn.clicked.connect(lambda: self.move_left_requested.emit(self))
        layout.addWidget(self.left_btn)

        self.right_btn = QToolButton()
        self.right_btn.setText("↓")
        self.right_btn.setFixedWidth(24)
        self.right_btn.setToolTip("下移（排序后移）")
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
        has_override = (
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
    - 标题栏（``▼ ↖ 左上 (3 字段)``）+ 角级字号（紧凑）
    - 内容区（chip 列表 + ``+ 添加字段`` + ``分隔符: [_]``）

    持有 :class:`CornerConfig` 引用，所有用户操作直接 mutate；
    然后调用 ``state.set_corner_config(corner_attr, config)`` 触发 autosave / 预览刷新。

    font 和 color 统一由全局参数决定，本区块仅控制字号覆盖。
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

        # 角级字号比例（占图片短边比例）：下拉菜单提供常用比例。
        header.addWidget(QLabel("字号比例"))
        self.corner_size = QComboBox()
        self.corner_size.setFixedWidth(100)
        for label, value in self._corner_size_options():
            self.corner_size.addItem(label, value)
        self.corner_size.currentIndexChanged.connect(self._on_corner_size_changed)
        header.addWidget(self.corner_size)

        # 重置角级字号比例
        reset_btn = QToolButton()
        reset_btn.setText("⤺")
        reset_btn.setToolTip("重置角级字号比例（继承全局）")
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

        # 角级字号比例：旧配置中可能残留 font_size 字段，忽略之，使用比例。
        self.corner_size.blockSignals(True)
        normalized_ratio = self._set_corner_size_combo(self.corner.font_size_ratio)
        self.corner_size.blockSignals(False)
        self.corner.font_size_ratio = normalized_ratio
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

    # ---- 角级字号比例 ----

    @staticmethod
    def _corner_size_options() -> list[tuple[str, float]]:
        """角级字号占图片短边比例选项；0.0 表示继承全局/自适应。"""
        return [
            ("继承", 0.0),
            ("极小 1%", 0.01),
            ("小 2%", 0.02),
            ("较小 3%", 0.03),
            ("标准 4%", 0.04),
            ("中等 5%", 0.05),
            ("较大 6%", 0.06),
            ("大 8%", 0.08),
            ("特大 10%", 0.10),
            ("超大 12%", 0.12),
            ("极限 15%", 0.15),
        ]

    def _set_corner_size_combo(self, value: float) -> float:
        """根据持久化字号比例刷新下拉。"""
        normalized = self._nearest_corner_ratio(value)
        idx = self.corner_size.findData(normalized)
        self.corner_size.setCurrentIndex(idx if idx >= 0 else 0)
        return normalized

    def _nearest_corner_ratio(self, value: float) -> float:
        """把旧配置或任意值映射为当前下拉菜单支持的比例。"""
        if value <= 0:
            return 0.0
        choices = [v for _label, v in self._corner_size_options() if v > 0]
        # 距离相等时优先取较大的比例（更接近用户意图）
        return min(choices, key=lambda choice: (abs(choice - value), -choice))

    def _on_corner_size_changed(self, _idx: int) -> None:
        value = self.corner_size.currentData()
        self.corner.font_size_ratio = float(value) if isinstance(value, (int, float)) and value > 0 else 0.0
        self._push_to_state()

    def _reset_corner_style(self) -> None:
        if not self.corner.font_size_ratio:
            return
        self.corner.font_size_ratio = 0.0
        self.corner_size.blockSignals(True)
        self._set_corner_size_combo(0.0)
        self.corner_size.blockSignals(False)
        self._push_to_state()

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
    """Logo 设置。

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

        outer.addLayout(form)
        outer.addStretch(1)
        guard_wheel_for_children(self)

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
# SignatureTab — Phase 25：签名（位置 / 缩放 / 偏移）独立子 Tab
# =============================================================================


class SignatureTab(QWidget):
    """签名子 Tab — Phase 25 从 AdvancedPanel 拆出，与水印/Logo 平级。

    设计要点
    --------
    - **写回策略**：用 :func:`dataclasses.replace` 局部更新 ``state.advanced`` 中的
      签名字段（``signature_*``），不覆盖 :class:`AdvancedPanel` 持有的非签名
      字段。``set_advanced_config`` 触发 ``advanced_changed`` 信号后，AdvancedPanel
      的 ``_load_state`` 会把所有非签名字段刷一遍——但因 ``_loading`` 守卫不会再回写。
    - **加载守卫**：与 LogoTab 一致的 ``self._loading`` 模式，避免 ``setValue`` /
      ``setText`` 触发的 ``*_changed`` 信号导致循环。
    - **订阅**：自订阅 ``advanced_changed``，模板加载 / reset 后整个 Tab 重新刷值。
    """

    # 9 宫格 anchor 内部 value。
    _POSITION_VALUES: ClassVar[list[str]] = [
        "top_left", "top_center", "top_right",
        "middle_left", "middle_center", "middle_right",
        "bottom_left", "bottom_center", "bottom_right",
    ]
    _POSITION_LABELS: ClassVar[list[str]] = [
        "左上", "上方居中", "右上",
        "左侧居中", "正中心", "右侧居中",
        "左下", "下方居中", "右下",
    ]

    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self._loading = False
        self._setup_ui()
        self._load_state()
        # Phase 25：自订阅 advanced_changed —— 模板加载 / reset 等外部全量替换由
        # AppState 主动通知；本 Tab 不需要主窗口手工同步。
        self.state.advanced_changed.connect(self._load_state)

    # ---- UI ----

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 签名设置同样放入滚动区域，避免主窗口缩小时表单被纵向挤压。
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(8)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(8)

        # 启用开关
        self.enabled_check = QCheckBox("启用签名")
        self.enabled_check.stateChanged.connect(self._on_changed)
        form.addRow("", self.enabled_check)

        # 签名图片路径
        path_row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("选择签名图片(PNG / JPG)...")
        self.path_input.setMinimumWidth(0)
        self.path_input.textChanged.connect(self._on_changed)
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_signature)
        path_row.addWidget(self.path_input, 1)
        path_row.addWidget(browse_btn)
        form.addRow("签名图片：", path_row)

        # Phase 26：反向签名色（黑↔白二值切换；彩色像素始终保留原色）
        self.invert_mono_combo = QComboBox()
        self.invert_mono_combo.setMinimumWidth(0)
        self.invert_mono_combo.addItem("黑色文字（保留彩色像素）", False)
        self.invert_mono_combo.addItem("白色文字（保留彩色像素）", True)
        self.invert_mono_combo.setToolTip(
            "切换签名笔画的黑白色：仅作用于近黑/近白的无色像素，"
            "签名上的彩色装饰（如红点、印章）始终保留原色不被修改。"
        )
        self.invert_mono_combo.currentIndexChanged.connect(self._on_changed)
        form.addRow("反向签名色：", self.invert_mono_combo)

        # 签名增强（基于抠像后的 alpha 蒙版）
        enhancement_row = QHBoxLayout()
        self.enhancement_combo = QComboBox()
        self.enhancement_combo.setFixedWidth(128)
        self.enhancement_combo.addItem("关闭", "none")
        self.enhancement_combo.addItem("柔和投影", "soft_shadow")
        self.enhancement_combo.addItem("轻微外发光", "soft_glow")
        self.enhancement_combo.addItem("柔和描边", "soft_outline")
        self.enhancement_combo.setToolTip(
            "在透明签名下方增加低调视觉增强，避免签名与照片细节混杂："
            "柔和投影更自然，外发光更干净，描边可读性最强。"
        )
        self.enhancement_combo.currentIndexChanged.connect(self._on_enhancement_changed)
        enhancement_row.addWidget(self.enhancement_combo)
        enhancement_row.addWidget(QLabel("强度："))
        self.enhancement_strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.enhancement_strength_slider.setRange(0, 100)
        self.enhancement_strength_slider.setSingleStep(5)
        self.enhancement_strength_slider.setPageStep(10)
        self.enhancement_strength_slider.setValue(50)
        self.enhancement_strength_slider.setToolTip(
            "控制签名增强效果强度：0% 为无增强，100% 为最大增强。"
        )
        self.enhancement_strength_slider.setMinimumWidth(0)
        self.enhancement_strength_slider.valueChanged.connect(
            self._on_enhancement_strength_changed
        )
        enhancement_row.addWidget(self.enhancement_strength_slider, 1)
        self.enhancement_strength_label = QLabel("50%")
        self.enhancement_strength_label.setMinimumWidth(36)
        enhancement_row.addWidget(self.enhancement_strength_label)
        form.addRow("签名增强：", enhancement_row)

        # 位置（9 宫格 ComboBox）
        self.position_combo = QComboBox()
        self.position_combo.setMinimumWidth(0)
        self.position_combo.setToolTip(
            "位置决定照片主体区域内的九宫格参考点，不包含底部白色水印区；"
            "水平/垂直偏移作用于签名中心，改大小时视觉中心不漂移。"
        )
        for value, label in zip(
            self._POSITION_VALUES, self._POSITION_LABELS, strict=True
        ):
            self.position_combo.addItem(label, value)
        self.position_combo.currentIndexChanged.connect(self._on_anchor_changed)
        form.addRow("位置：", self.position_combo)

        # 签名大小 + 偏移：同一行内用网格分栏，而不是单条不可换行的 HBox；
        # 这样滚动页只需要竖向滚动，窄窗口不会出现横向溢出或内容被裁切。
        size_offset_grid = QGridLayout()
        size_offset_grid.setContentsMargins(0, 0, 0, 0)
        size_offset_grid.setHorizontalSpacing(10)
        size_offset_grid.setVerticalSpacing(6)
        size_offset_grid.setColumnMinimumWidth(1, 96)
        size_offset_grid.setColumnMinimumWidth(3, 108)
        size_offset_grid.setColumnMinimumWidth(5, 108)
        size_offset_grid.setColumnStretch(1, 1)
        size_offset_grid.setColumnStretch(3, 1)
        size_offset_grid.setColumnStretch(5, 1)
        size_offset_grid.addWidget(QLabel("大小："), 0, 0)
        self.size_ratio_spin = QSpinBox()
        self.size_ratio_spin.setRange(1, 100)
        self.size_ratio_spin.setSingleStep(1)
        self.size_ratio_spin.setValue(20)
        self.size_ratio_spin.setSuffix(" %")
        self.size_ratio_spin.setMinimumWidth(96)
        self.size_ratio_spin.setToolTip(
            "签名宽度占【照片主体短边】的百分比；"
            "高度按签名图片原始宽高比等比；超出照片主体区域时自动 fit。"
        )
        self.size_ratio_spin.valueChanged.connect(self._on_changed)
        size_offset_grid.addWidget(self.size_ratio_spin, 0, 1)

        # 偏移参数：签名中心相对九宫格参考点的有符号偏移。
        self.margin_x_label = QLabel("X：")
        self.margin_x_label.setToolTip("签名中心的水平偏移；正数向右，负数向左。")
        size_offset_grid.addWidget(self.margin_x_label, 0, 2)
        self.margin_x_spin = QSpinBox()
        self.margin_x_spin.setRange(-9999, 9999)
        self.margin_x_spin.setValue(80)
        self.margin_x_spin.setSuffix(" px")
        self.margin_x_spin.setMinimumWidth(108)
        self.margin_x_spin.valueChanged.connect(self._on_changed)
        size_offset_grid.addWidget(self.margin_x_spin, 0, 3)
        self.margin_y_label = QLabel("Y：")
        self.margin_y_label.setToolTip("签名中心的垂直偏移；正数向下，负数向上。")
        size_offset_grid.addWidget(self.margin_y_label, 0, 4)
        self.margin_y_spin = QSpinBox()
        self.margin_y_spin.setRange(-9999, 9999)
        self.margin_y_spin.setValue(60)
        self.margin_y_spin.setSuffix(" px")
        self.margin_y_spin.setMinimumWidth(108)
        self.margin_y_spin.valueChanged.connect(self._on_changed)
        size_offset_grid.addWidget(self.margin_y_spin, 0, 5)
        form.addRow("", size_offset_grid)

        content_layout.addLayout(form)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        content.adjustSize()
        content.setMinimumWidth(0)
        guard_wheel_for_children(content)
        outer.addWidget(scroll)

    # ---- 加载 / 提交 ----

    def _load_state(self, *_args) -> None:
        """从 AppState 加载签名字段（带 ``_loading`` 守卫）。"""
        self._loading = True
        try:
            cfg = self.state.advanced
            self.enabled_check.setChecked(cfg.signature_enabled)
            self.path_input.setText(cfg.signature_path)
            # Phase 26：bool → ComboBox index（False=0=黑色，True=1=白色）
            self.invert_mono_combo.setCurrentIndex(1 if cfg.signature_invert_mono else 0)
            self._set_combo_by_data(
                self.enhancement_combo,
                cfg.signature_enhancement,
                fallback="none",
            )
            self.enhancement_strength_slider.setValue(
                max(0, min(100, cfg.signature_enhancement_strength))
            )
            self._refresh_enhancement_controls()
            try:
                idx = self._POSITION_VALUES.index(cfg.signature_anchor)
            except ValueError:
                # 兜底：未知 anchor → 回到默认 middle_center（与 dataclass 一致）
                idx = self._POSITION_VALUES.index("middle_center")
            self.position_combo.setCurrentIndex(idx)
            # 内部 0.01~1.0 → UI 1~100 整数百分比
            self.size_ratio_spin.setValue(
                max(1, min(100, round(cfg.signature_size_ratio * 100)))
            )
            self.margin_x_spin.setValue(cfg.signature_margin_x)
            self.margin_y_spin.setValue(cfg.signature_margin_y)
            self._refresh_distance_labels()
        finally:
            self._loading = False

    def _on_changed(self, *_args) -> None:
        """签名字段任意变更 → 局部 replace 写回 state.advanced。"""
        if self._loading:
            return
        new_cfg = replace(
            self.state.advanced,
            signature_enabled=self.enabled_check.isChecked(),
            signature_path=self.path_input.text(),
            signature_invert_mono=bool(self.invert_mono_combo.currentData()),
            signature_enhancement=str(self.enhancement_combo.currentData() or "none"),
            signature_enhancement_strength=self.enhancement_strength_slider.value(),
            signature_anchor=(
                self.position_combo.currentData() or "middle_center"
            ),
            signature_size_ratio=self.size_ratio_spin.value() / 100.0,
            signature_margin_x=self.margin_x_spin.value(),
            signature_margin_y=self.margin_y_spin.value(),
        )
        self.state.set_advanced_config(new_cfg)

    def _on_anchor_changed(self, *_args) -> None:
        self._refresh_distance_labels()
        self._on_changed()

    def _on_enhancement_changed(self, *_args) -> None:
        self._refresh_enhancement_controls()
        self._on_changed()

    def _on_enhancement_strength_changed(self, value: int) -> None:
        self.enhancement_strength_label.setText(f"{value}%")
        self._on_changed()

    def _refresh_enhancement_controls(self) -> None:
        value = self.enhancement_strength_slider.value()
        self.enhancement_strength_label.setText(f"{value}%")
        enabled = (self.enhancement_combo.currentData() or "none") != "none"
        self.enhancement_strength_slider.setEnabled(enabled)
        self.enhancement_strength_label.setEnabled(enabled)

    def _refresh_distance_labels(self) -> None:
        """刷新偏移控件文案。

        签名定位统一采用「九宫格参考点 + 签名中心偏移」语义，
        因此两个方向都允许正负值，不再按边缘锚点切换为距边距离。
        """
        self.margin_x_spin.setMinimum(-9999)
        self.margin_y_spin.setMinimum(-9999)
        self.margin_x_label.setText("X：")
        self.margin_y_label.setText("Y：")
        self.margin_x_spin.setToolTip(
            "签名中心相对九宫格参考点的水平偏移；正数向右，负数向左。"
        )
        self.margin_y_spin.setToolTip(
            "签名中心相对九宫格参考点的垂直偏移；正数向下，负数向上。"
        )

    # ---- 辅助 ----

    @staticmethod
    def _set_combo_by_data(combo: QComboBox, value: str, *, fallback: str) -> None:
        idx = combo.findData(value)
        if idx < 0:
            idx = combo.findData(fallback)
        combo.setCurrentIndex(max(0, idx))

    def _browse_signature(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择签名图片", "", "图片 (*.png *.jpg *.jpeg)"
        )
        if path:
            self.path_input.setText(path)
            # textChanged 信号已自动触发 _on_changed


# =============================================================================
# ConfigPanel — 顶层 Tab 容器
# =============================================================================


class ConfigPanel(QWidget):
    """水印配置主面板（单视图 Accordion）。

    架构（Phase 25：3 个子 Tab）：
    - Tab "水印"：4 个 :class:`CornerSection` 垂直堆叠 + 滚动条
    - Tab "Logo"：:class:`LogoTab`
    - Tab "签名"：:class:`SignatureTab`

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
        guard_wheel_for_children(wm_inner)
        wm_layout.addWidget(scroll)
        self.tabs.addTab(watermark_tab, "水印")

        # Tab 2：Logo
        self.logo_tab = LogoTab(self.state)
        self.tabs.addTab(self.logo_tab, "Logo")

        # Tab 3：签名（Phase 25：从 AdvancedPanel 拆出独立成 Tab）
        self.signature_tab = SignatureTab(self.state)
        self.tabs.addTab(self.signature_tab, "签名")

    # ---- 外部触发的整树重建 ----

    def _reload_all_from_state(self, *_args) -> None:
        """``load_from_disk`` / ``reset_to_defaults`` 等外部全量替换后整体重建 UI。"""
        for section in self._sections.values():
            section._rebuild_from_state()
        # LogoTab 自订阅了 state_reloaded？没有 —— 显式刷一遍以保证一致。
        # SignatureTab 自订阅了 advanced_changed —— state_reloaded 后 AppState
        # 会再发 advanced_changed，故无需显式调用；为保险显式刷一次更稳妥。
        self.signature_tab._load_state()
        self.logo_tab._load_state()
