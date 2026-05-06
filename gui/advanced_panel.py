"""高级设置面板 - 所有分组默认折叠。"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .models import AdvancedConfig, AppState


class CollapsibleGroup(QFrame):
    """可折叠分组组件。"""

    toggled = pyqtSignal(bool)

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._expanded = False
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #333333;
                border-radius: 4px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题栏(可点击)
        self.header = QPushButton(f"▶ {title}")
        self.header.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: transparent;
                color: #999999;
                padding: 8px 12px;
                text-align: left;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #E0E0E0;
                background-color: #2A2A2A;
            }
        """)
        self.header.clicked.connect(self._toggle)
        layout.addWidget(self.header)

        # 内容区域
        self.content = QWidget()
        self.content.setVisible(False)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(12, 8, 12, 12)
        self.content_layout.setSpacing(8)
        layout.addWidget(self.content)

    def add_widget(self, widget):
        """向内容区域添加控件。"""
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        """向内容区域添加布局。"""
        self.content_layout.addLayout(layout)

    def _toggle(self):
        self._expanded = not self._expanded
        self.content.setVisible(self._expanded)
        text = self.header.text()[2:]  # 去掉箭头
        arrow = "▼" if self._expanded else "▶"
        self.header.setText(f"{arrow} {text}")
        self.toggled.emit(self._expanded)

    def set_expanded(self, expanded: bool):
        if expanded != self._expanded:
            self._toggle()


class AdvancedPanel(QWidget):
    """高级设置面板 — 内部可滚动。"""

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        # Phase 9：写回循环守卫 — _load_state 期间所有控件 setValue/setText 触发的
        # *_changed → _on_changed → state.set_advanced_config 都被此 flag 短路。
        self._loading: bool = False
        self._setup_ui()
        self._load_state()
        # Phase 9：自订阅 advanced_changed —— 模板加载、reset_to_defaults 等外部全量
        # 替换会发此信号；本面板不再依赖主窗口手工调 _load_state()。
        self.state.advanced_changed.connect(self._load_state)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        # 内容面板
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        # 分组: 字体与颜色
        font_group = CollapsibleGroup("字体与颜色")
        self._setup_font_group(font_group)
        content_layout.addWidget(font_group)

        # 分组 1: 边框/留白
        margin_group = CollapsibleGroup("边框/留白")
        self._setup_margin_group(margin_group)
        content_layout.addWidget(margin_group)

        # 分组 2: 圆角与阴影
        corner_group = CollapsibleGroup("圆角与阴影")
        self._setup_corner_group(corner_group)
        content_layout.addWidget(corner_group)

        # 分组 3: 图像质量
        quality_group = CollapsibleGroup("图像质量")
        self._setup_quality_group(quality_group)
        content_layout.addWidget(quality_group)

        # 分组 4: 背景效果
        blur_group = CollapsibleGroup("背景效果")
        self._setup_blur_group(blur_group)
        content_layout.addWidget(blur_group)

        # 分组 5: 拼接与对齐
        concat_group = CollapsibleGroup("拼接与对齐")
        self._setup_concat_group(concat_group)
        content_layout.addWidget(concat_group)

        # 分组 6: 图像调整
        resize_group = CollapsibleGroup("图像调整")
        self._setup_resize_group(resize_group)
        content_layout.addWidget(resize_group)

        # 分组 7: 签名（Phase 17：完整接入渲染管线）
        sig_group = CollapsibleGroup("签名")
        self._setup_signature_group(sig_group)
        content_layout.addWidget(sig_group)

        content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _setup_font_group(self, group: CollapsibleGroup):
        """字体与颜色设置。"""
        # 字体选择
        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("字体："))
        self.global_font = QComboBox()
        from core.font_manager import list_fonts
        self.global_font.addItems(list_fonts())
        self.global_font.setFixedWidth(200)
        self.global_font.currentTextChanged.connect(self._on_changed)
        font_row.addWidget(self.global_font)
        font_row.addStretch()
        group.add_layout(font_row)
        
        # 颜色选择
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("颜色："))
        self.global_color = QLineEdit("#FFFFFF")
        self.global_color.setFixedWidth(80)
        self.global_color.textChanged.connect(self._on_changed)
        color_row.addWidget(self.global_color)
        
        self.global_color_btn = QPushButton()
        self.global_color_btn.setFixedSize(24, 24)
        self.global_color_btn.setStyleSheet("border-radius: 4px; border: 1px solid #666666;")
        self.global_color_btn.clicked.connect(lambda: self._pick_color(self.global_color, self.global_color_btn))
        color_row.addWidget(self.global_color_btn)
        color_row.addStretch()
        group.add_layout(color_row)

        # Phase 11：固定像素尺寸（0 = 旧自适应）
        size_hint = QLabel("固定像素尺寸（0 = 按图片比例自适应；非 0 = 锁定为统一像素，不再随原图尺寸变化）")
        size_hint.setWordWrap(True)
        size_hint.setStyleSheet("color: #888888; font-size: 11px;")
        group.add_widget(size_hint)

        text_h_row = QHBoxLayout()
        text_h_row.addWidget(QLabel("角落字体高度(px)："))
        self.corner_text_height_px = QSpinBox()
        self.corner_text_height_px.setRange(0, 2000)
        self.corner_text_height_px.setValue(0)
        self.corner_text_height_px.setFixedWidth(90)
        self.corner_text_height_px.valueChanged.connect(self._on_changed)
        text_h_row.addWidget(self.corner_text_height_px)
        text_h_row.addStretch()
        group.add_layout(text_h_row)

        footer_h_row = QHBoxLayout()
        footer_h_row.addWidget(QLabel("水印条高度(px)："))
        self.footer_height_px = QSpinBox()
        self.footer_height_px.setRange(0, 5000)
        self.footer_height_px.setValue(0)
        self.footer_height_px.setFixedWidth(90)
        self.footer_height_px.valueChanged.connect(self._on_changed)
        footer_h_row.addWidget(self.footer_height_px)
        footer_h_row.addStretch()
        group.add_layout(footer_h_row)

        logo_h_row = QHBoxLayout()
        logo_h_row.addWidget(QLabel("Logo 高度(px)："))
        self.logo_height_px = QSpinBox()
        self.logo_height_px.setRange(0, 5000)
        self.logo_height_px.setValue(0)
        self.logo_height_px.setFixedWidth(90)
        self.logo_height_px.valueChanged.connect(self._on_changed)
        logo_h_row.addWidget(self.logo_height_px)
        logo_h_row.addStretch()
        group.add_layout(logo_h_row)

    def _setup_margin_group(self, group: CollapsibleGroup):
        """边框/留白设置。"""
        for name, attr in [("左", "left_margin"), ("右", "right_margin"),
                           ("上", "top_margin"), ("下", "bottom_margin")]:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{name}边距:"))
            spin = QSpinBox()
            spin.setRange(0, 2000)
            spin.setSuffix(" px")
            spin.setFixedWidth(100)
            setattr(self, f"{attr}_spin", spin)
            spin.valueChanged.connect(self._on_changed)
            row.addWidget(spin)
            row.addStretch()
            group.add_layout(row)

        # 边距颜色
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("边距颜色:"))
        self.margin_color = QLineEdit("#FFFFFF")
        self.margin_color.setFixedWidth(80)
        color_row.addWidget(self.margin_color)
        self.margin_color_btn = QPushButton()
        self.margin_color_btn.setFixedSize(24, 24)
        self.margin_color_btn.clicked.connect(lambda: self._pick_color(self.margin_color, self.margin_color_btn))
        color_row.addWidget(self.margin_color_btn)
        color_row.addStretch()
        group.add_layout(color_row)

    def _setup_corner_group(self, group: CollapsibleGroup):
        """圆角与阴影设置。"""
        # 圆角
        radius_row = QHBoxLayout()
        radius_row.addWidget(QLabel("圆角半径:"))
        self.border_radius = QSpinBox()
        self.border_radius.setRange(0, 100)
        self.border_radius.setSuffix(" px")
        self.border_radius.valueChanged.connect(self._on_changed)
        radius_row.addWidget(self.border_radius)
        radius_row.addStretch()
        group.add_layout(radius_row)

        # 阴影半径
        shadow_row = QHBoxLayout()
        shadow_row.addWidget(QLabel("阴影半径:"))
        self.shadow_radius = QSpinBox()
        self.shadow_radius.setRange(0, 200)
        self.shadow_radius.setSuffix(" px")
        self.shadow_radius.valueChanged.connect(self._on_changed)
        shadow_row.addWidget(self.shadow_radius)
        shadow_row.addStretch()
        group.add_layout(shadow_row)

        # 阴影颜色
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("阴影颜色:"))
        self.shadow_color = QLineEdit("#000000")
        self.shadow_color.setFixedWidth(80)
        color_row.addWidget(self.shadow_color)
        self.shadow_color_btn = QPushButton()
        self.shadow_color_btn.setFixedSize(24, 24)
        self.shadow_color_btn.clicked.connect(lambda: self._pick_color(self.shadow_color, self.shadow_color_btn))
        color_row.addWidget(self.shadow_color_btn)
        color_row.addStretch()
        group.add_layout(color_row)

    def _setup_quality_group(self, group: CollapsibleGroup):
        """图像质量设置。"""
        # JPEG 质量
        quality_row = QHBoxLayout()
        quality_row.addWidget(QLabel("JPEG 质量:"))
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(95)
        self.quality_slider.valueChanged.connect(self._on_changed)
        quality_row.addWidget(self.quality_slider)
        self.quality_label = QLabel("95")
        self.quality_label.setFixedWidth(30)
        quality_row.addWidget(self.quality_label)
        quality_row.addStretch()
        group.add_layout(quality_row)

        # 子采样
        sub_row = QHBoxLayout()
        sub_row.addWidget(QLabel("子采样:"))
        self.subsampling = QComboBox()
        self.subsampling.addItems(["0 (4:4:4)", "1 (4:2:2)", "2 (4:2:0)"])
        self.subsampling.currentIndexChanged.connect(self._on_changed)
        sub_row.addWidget(self.subsampling)
        sub_row.addStretch()
        group.add_layout(sub_row)

    def _setup_blur_group(self, group: CollapsibleGroup):
        """背景效果设置。"""
        # 模糊
        blur_row = QHBoxLayout()
        blur_row.addWidget(QLabel("模糊半径:"))
        self.blur_radius = QSpinBox()
        self.blur_radius.setRange(0, 50)
        self.blur_radius.setSuffix(" px")
        self.blur_radius.valueChanged.connect(self._on_changed)
        blur_row.addWidget(self.blur_radius)
        blur_row.addStretch()
        group.add_layout(blur_row)

        # 按比例留白
        ratio_row = QHBoxLayout()
        self.ratio_enabled = QCheckBox("按比例留白")
        self.ratio_enabled.stateChanged.connect(self._on_changed)
        ratio_row.addWidget(self.ratio_enabled)
        self.ratio = QLineEdit("3:4")
        self.ratio.setFixedWidth(60)
        self.ratio.textChanged.connect(self._on_changed)
        ratio_row.addWidget(self.ratio)
        ratio_row.addStretch()
        group.add_layout(ratio_row)

    def _setup_resize_group(self, group: CollapsibleGroup):
        """图像调整设置。"""
        # 缩放
        scale_row = QHBoxLayout()
        scale_row.addWidget(QLabel("缩放比例："))
        self.scale = QDoubleSpinBox()
        self.scale.setRange(0.1, 3.0)
        self.scale.setSingleStep(0.1)
        self.scale.setValue(1.0)
        self.scale.valueChanged.connect(self._on_changed)
        scale_row.addWidget(self.scale)
        scale_row.addStretch()
        group.add_layout(scale_row)
        
        # 裁剪空白边
        trim_row = QHBoxLayout()
        self.trim_enabled = QCheckBox("自动裁剪空白边")
        self.trim_enabled.stateChanged.connect(self._on_changed)
        trim_row.addWidget(self.trim_enabled)
        trim_row.addWidget(QLabel("阈值："))
        self.trim_threshold = QDoubleSpinBox()
        self.trim_threshold.setRange(0.0, 255.0)
        self.trim_threshold.setValue(0.0)
        self.trim_threshold.valueChanged.connect(self._on_changed)
        trim_row.addWidget(self.trim_threshold)
        trim_row.addStretch()
        group.add_layout(trim_row)

    def _setup_concat_group(self, group: CollapsibleGroup):
        """拼接与对齐设置。"""
        # 拼接方向
        concat_row = QHBoxLayout()
        concat_row.addWidget(QLabel("拼接方向："))
        self.concat_direction = QComboBox()
        self.concat_direction.addItems(["vertical", "horizontal"])
        self.concat_direction.currentTextChanged.connect(self._on_changed)
        concat_row.addWidget(self.concat_direction)
        concat_row.addStretch()
        group.add_layout(concat_row)
        
        # 对齐模式
        align_row = QHBoxLayout()
        align_row.addWidget(QLabel("对齐模式："))
        self.alignment_mode = QComboBox()
        self.alignment_mode.addItems(["top", "center", "bottom"])
        self.alignment_mode.currentTextChanged.connect(self._on_changed)
        align_row.addWidget(self.alignment_mode)
        align_row.addStretch()
        group.add_layout(align_row)

    def _setup_signature_group(self, group: CollapsibleGroup):
        """签名设置（Phase 18：图像内 9 宫格定位 + 四向偏移）。"""
        enable_row = QHBoxLayout()
        self.sig_enabled = QCheckBox("启用签名")
        self.sig_enabled.stateChanged.connect(self._on_changed)
        enable_row.addWidget(self.sig_enabled)
        enable_row.addStretch()
        group.add_layout(enable_row)

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("签名图片:"))
        self.sig_path = QLineEdit()
        self.sig_path.setPlaceholderText("选择签名图片(PNG / JPG)...")
        self.sig_path.textChanged.connect(self._on_changed)
        path_row.addWidget(self.sig_path)
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_signature)
        path_row.addWidget(browse_btn)
        group.add_layout(path_row)

        # 颜色：色板按钮（与全局颜色 / 边距颜色一致的交互）
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("颜色:"))
        self.sig_color = QLineEdit("#000000")
        self.sig_color.setFixedWidth(80)
        self.sig_color.textChanged.connect(self._on_changed)
        color_row.addWidget(self.sig_color)
        self.sig_color_btn = QPushButton()
        self.sig_color_btn.setFixedSize(24, 24)
        self.sig_color_btn.clicked.connect(lambda: self._pick_color(self.sig_color, self.sig_color_btn))
        color_row.addWidget(self.sig_color_btn)
        color_row.addStretch()
        group.add_layout(color_row)

        # 位置（9 宫格）
        pos_row = QHBoxLayout()
        pos_row.addWidget(QLabel("位置:"))
        self.sig_position = QComboBox()
        # 内部 value 与中文标签按相同顺序排列；行优先（左上→中中→右下）
        self._sig_position_values = [
            "top_left", "top_center", "top_right",
            "middle_left", "middle_center", "middle_right",
            "bottom_left", "bottom_center", "bottom_right",
        ]
        self.sig_position.addItems([
            "左上", "上方居中", "右上",
            "左侧居中", "正中心", "右侧居中",
            "左下", "下方居中", "右下",
        ])
        self.sig_position.currentIndexChanged.connect(self._on_changed)
        pos_row.addWidget(self.sig_position)
        pos_row.addStretch()
        group.add_layout(pos_row)

        # 高度占比（相对原图区域高度，0.5%~100%） + 缩放倍数（Phase 20）
        height_row = QHBoxLayout()
        height_row.addWidget(QLabel("高度占比:"))
        self.sig_height_ratio = QDoubleSpinBox()
        self.sig_height_ratio.setRange(0.005, 1.0)
        self.sig_height_ratio.setSingleStep(0.01)
        self.sig_height_ratio.setDecimals(3)
        self.sig_height_ratio.setValue(0.05)
        self.sig_height_ratio.setSuffix(" × 原图高度")
        self.sig_height_ratio.valueChanged.connect(self._on_changed)
        height_row.addWidget(self.sig_height_ratio)
        height_row.addSpacing(16)
        height_row.addWidget(QLabel("缩放倍数:"))
        self.sig_scale = QDoubleSpinBox()
        self.sig_scale.setRange(0.1, 5.0)
        self.sig_scale.setSingleStep(0.1)
        self.sig_scale.setDecimals(2)
        self.sig_scale.setValue(1.0)
        self.sig_scale.setSuffix(" ×")
        self.sig_scale.setToolTip("在高度占比的基础上再整体等比缩放（保持宽高比）")
        self.sig_scale.valueChanged.connect(self._on_changed)
        height_row.addWidget(self.sig_scale)
        height_row.addStretch()
        group.add_layout(height_row)

        # 四向偏移（像素，正向"内推" — 由 position 锚点决定哪两个生效）
        offset_row1 = QHBoxLayout()
        offset_row1.addWidget(QLabel("上偏移:"))
        self.sig_offset_top = QSpinBox()
        self.sig_offset_top.setRange(0, 9999)
        self.sig_offset_top.setSuffix(" px")
        self.sig_offset_top.valueChanged.connect(self._on_changed)
        offset_row1.addWidget(self.sig_offset_top)
        offset_row1.addSpacing(16)
        offset_row1.addWidget(QLabel("下偏移:"))
        self.sig_offset_bottom = QSpinBox()
        self.sig_offset_bottom.setRange(0, 9999)
        self.sig_offset_bottom.setSuffix(" px")
        self.sig_offset_bottom.valueChanged.connect(self._on_changed)
        offset_row1.addWidget(self.sig_offset_bottom)
        offset_row1.addStretch()
        group.add_layout(offset_row1)

        offset_row2 = QHBoxLayout()
        offset_row2.addWidget(QLabel("左偏移:"))
        self.sig_offset_left = QSpinBox()
        self.sig_offset_left.setRange(0, 9999)
        self.sig_offset_left.setSuffix(" px")
        self.sig_offset_left.valueChanged.connect(self._on_changed)
        offset_row2.addWidget(self.sig_offset_left)
        offset_row2.addSpacing(16)
        offset_row2.addWidget(QLabel("右偏移:"))
        self.sig_offset_right = QSpinBox()
        self.sig_offset_right.setRange(0, 9999)
        self.sig_offset_right.setSuffix(" px")
        self.sig_offset_right.valueChanged.connect(self._on_changed)
        offset_row2.addWidget(self.sig_offset_right)
        offset_row2.addStretch()
        group.add_layout(offset_row2)

    def _pick_color(self, input_field, btn):
        """通用颜色选择。"""
        color = QColorDialog.getColor(QColor(input_field.text()), self)
        if color.isValid():
            hex_color = color.name().upper()
            input_field.setText(hex_color)
            btn.setStyleSheet(f"background-color: {hex_color}; border-radius: 4px; border: 1px solid #666666;")
            self._on_changed()

    def _browse_signature(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "选择签名图片", "", "图片 (*.png *.jpg *.jpeg)")
        if path:
            self.sig_path.setText(path)
            # textChanged 信号已自动触发 _on_changed，无需显式调用

    def _on_changed(self):
        """配置变更时保存到 AppState（Phase 9：写回循环守卫）。"""
        if self._loading:
            # _load_state 期间触发的 *_changed 信号一律忽略，避免写回循环
            return
        self.quality_label.setText(str(self.quality_slider.value()))

        config = AdvancedConfig(
            global_font=self.global_font.currentText(),
            global_color=self.global_color.text(),
            left_margin=self.left_margin_spin.value(),
            right_margin=self.right_margin_spin.value(),
            top_margin=self.top_margin_spin.value(),
            bottom_margin=self.bottom_margin_spin.value(),
            margin_color=self.margin_color.text(),
            border_radius=self.border_radius.value(),
            shadow_radius=self.shadow_radius.value(),
            shadow_color=self.shadow_color.text(),
            quality=self.quality_slider.value(),
            subsampling=self.subsampling.currentIndex(),
            blur_radius=self.blur_radius.value(),
            ratio_enabled=self.ratio_enabled.isChecked(),
            ratio=self.ratio.text(),
            scale=self.scale.value(),
            trim_enabled=self.trim_enabled.isChecked(),
            trim_threshold=self.trim_threshold.value(),
            concat_direction=self.concat_direction.currentText(),
            alignment_mode=self.alignment_mode.currentText(),
            signature_enabled=self.sig_enabled.isChecked(),
            signature_path=self.sig_path.text(),
            signature_color=self.sig_color.text(),
            signature_position=self._sig_position_values[self.sig_position.currentIndex()],
            signature_height_ratio=self.sig_height_ratio.value(),
            signature_scale=self.sig_scale.value(),
            signature_offset_top=self.sig_offset_top.value(),
            signature_offset_bottom=self.sig_offset_bottom.value(),
            signature_offset_left=self.sig_offset_left.value(),
            signature_offset_right=self.sig_offset_right.value(),
            corner_text_height_px=self.corner_text_height_px.value(),
            footer_height_px=self.footer_height_px.value(),
            logo_height_px=self.logo_height_px.value(),
        )
        self.state.set_advanced_config(config)

    def _load_state(self, *_args):
        """从 AppState 加载配置（Phase 9：用 self._loading 守卫包裹整个加载过程）。

        被以下场景调用：
        1. 构造函数末尾首次同步
        2. 自订阅 ``state.advanced_changed`` 信号（模板加载、reset 后由 AppState 主动通知）
        """
        self._loading = True
        try:
            cfg = self.state.advanced

            # 全局字体与颜色
            idx = self.global_font.findText(cfg.global_font)
            if idx >= 0:
                self.global_font.setCurrentIndex(idx)
            self.global_color.setText(cfg.global_color)
            self.global_color_btn.setStyleSheet(f"background-color: {cfg.global_color}; border-radius: 4px; border: 1px solid #666666;")

            # Phase 11：固定像素尺寸
            self.corner_text_height_px.setValue(cfg.corner_text_height_px)
            self.footer_height_px.setValue(cfg.footer_height_px)
            self.logo_height_px.setValue(cfg.logo_height_px)

            # 边距
            self.left_margin_spin.setValue(cfg.left_margin)
            self.right_margin_spin.setValue(cfg.right_margin)
            self.top_margin_spin.setValue(cfg.top_margin)
            self.bottom_margin_spin.setValue(cfg.bottom_margin)
            self.margin_color.setText(cfg.margin_color)
            self.margin_color_btn.setStyleSheet(f"background-color: {cfg.margin_color}; border-radius: 4px; border: 1px solid #666666;")

            self.border_radius.setValue(cfg.border_radius)
            self.shadow_radius.setValue(cfg.shadow_radius)
            self.shadow_color.setText(cfg.shadow_color)
            self.shadow_color_btn.setStyleSheet(f"background-color: {cfg.shadow_color}; border-radius: 4px; border: 1px solid #666666;")

            self.quality_slider.setValue(cfg.quality)
            self.quality_label.setText(str(cfg.quality))
            self.subsampling.setCurrentIndex(cfg.subsampling)

            self.blur_radius.setValue(cfg.blur_radius)
            self.ratio_enabled.setChecked(cfg.ratio_enabled)
            self.ratio.setText(cfg.ratio)

            self.scale.setValue(cfg.scale)
            self.trim_enabled.setChecked(cfg.trim_enabled)
            self.trim_threshold.setValue(cfg.trim_threshold)

            idx = self.concat_direction.findText(cfg.concat_direction)
            if idx >= 0:
                self.concat_direction.setCurrentIndex(idx)
            idx = self.alignment_mode.findText(cfg.alignment_mode)
            if idx >= 0:
                self.alignment_mode.setCurrentIndex(idx)

            self.sig_enabled.setChecked(cfg.signature_enabled)
            self.sig_path.setText(cfg.signature_path)
            self.sig_color.setText(cfg.signature_color)
            self.sig_color_btn.setStyleSheet(
                f"background-color: {cfg.signature_color}; border-radius: 4px; border: 1px solid #666666;"
            )
            try:
                pos_idx = self._sig_position_values.index(cfg.signature_position)
            except ValueError:
                # 兜底回到 bottom_right
                pos_idx = self._sig_position_values.index("bottom_right")
            self.sig_position.setCurrentIndex(pos_idx)
            self.sig_height_ratio.setValue(cfg.signature_height_ratio)
            self.sig_scale.setValue(cfg.signature_scale)
            self.sig_offset_top.setValue(cfg.signature_offset_top)
            self.sig_offset_bottom.setValue(cfg.signature_offset_bottom)
            self.sig_offset_left.setValue(cfg.signature_offset_left)
            self.sig_offset_right.setValue(cfg.signature_offset_right)
        finally:
            self._loading = False
