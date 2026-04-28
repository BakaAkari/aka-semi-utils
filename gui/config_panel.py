"""水印配置面板 — 四角水印 + Logo + 自定义文本。"""

from typing import List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QComboBox,
    QLineEdit, QLabel, QPushButton, QGridLayout, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal

from .models import AppState, CornerConfig, LogoConfig


class CornerEditor(QWidget):
    """单角水印编辑器。"""
    
    changed = pyqtSignal()  # 配置变更信号
    
    def __init__(self, corner_name: str, state: AppState, parent=None):
        super().__init__(parent)
        self.corner_name = corner_name
        self.state = state
        self.corner_attr = {
            "左上": "left_top",
            "左下": "left_bottom",
            "右上": "right_top",
            "右下": "right_bottom",
        }[corner_name]
        
        self._setup_ui()
        self._load_state()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # ---- 字段列表（水平排列，上限3个）----
        fields_header = QHBoxLayout()
        fields_header.addWidget(QLabel("字段："))
        fields_header.addStretch()
        layout.addLayout(fields_header)
        
        # 水平容器
        self.fields_container = QWidget()
        self.fields_flow = QHBoxLayout(self.fields_container)
        self.fields_flow.setSpacing(4)
        self.fields_flow.setContentsMargins(0, 0, 0, 0)
        self.fields_flow.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.fields_container)
        
        # 添加字段按钮
        add_btn = QPushButton("+ 添加字段")
        add_btn.setFixedWidth(100)
        add_btn.setFixedHeight(28)
        add_btn.clicked.connect(self._add_field_row)
        layout.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        
        self.add_btn = add_btn  # 引用用于禁用/启用
        
        # ---- 分隔符 ----
        sep_layout = QHBoxLayout()
        sep_layout.setSpacing(6)
        sep_layout.addWidget(QLabel("分隔符："))
        self.sep_input = QLineEdit(" · ")
        self.sep_input.setFixedWidth(80)
        self.sep_input.textChanged.connect(self._on_changed)
        sep_layout.addWidget(self.sep_input)
        sep_layout.addStretch()
        layout.addLayout(sep_layout)
        
        layout.addStretch()
    
    def _add_field_row(self, field_value: str = ""):
        """添加一个字段行（上限3个）。"""
        # 检查上限
        if self.fields_flow.count() >= 3:
            return
        
        container = QWidget()
        row = QHBoxLayout(container)
        row.setSpacing(4)
        row.setContentsMargins(0, 0, 0, 0)
        
        combo = QComboBox()
        combo.addItems([
            "相机型号", "镜头型号", "拍摄参数", "拍摄日期",
            "厂商品牌", "地理位置", "自定义文本", "空"
        ])
        combo.setFixedWidth(100)
        if field_value:
            idx = combo.findText(field_value)
            if idx >= 0:
                combo.setCurrentIndex(idx)
        combo.currentTextChanged.connect(self._on_changed)
        row.addWidget(combo)
        
        # 删除按钮
        del_btn = QPushButton("×")
        del_btn.setFixedSize(20, 20)
        del_btn.clicked.connect(lambda: self._remove_field_row(container))
        row.addWidget(del_btn)
        
        self.fields_flow.addWidget(container)
        self._update_add_btn()
        self._on_changed()
    
    def _remove_field_row(self, container):
        """删除一个字段行。"""
        container.deleteLater()
        self._update_add_btn()
        self._on_changed()
    
    def _update_add_btn(self):
        """根据字段数量禁用/启用添加按钮。"""
        self.add_btn.setEnabled(self.fields_flow.count() < 3)
        if self.fields_flow.count() >= 3:
            self.add_btn.setText("已达上限")
        else:
            self.add_btn.setText("+ 添加字段")
    
    def _on_changed(self):
        """任何配置变更时保存到 AppState。"""
        fields = []
        for i in range(self.fields_flow.count()):
            item = self.fields_flow.itemAt(i)
            if item and item.widget():
                # 在容器内部找到 QComboBox
                container = item.widget()
                for j in range(container.layout().count()):
                    widget = container.layout().itemAt(j).widget()
                    if isinstance(widget, QComboBox):
                        fields.append(widget.currentText())
                        break
        
        # 字体和颜色从全局 AppState 获取
        config = CornerConfig(
            fields=fields,
            separator=self.sep_input.text(),
            font=self.state.advanced.global_font,
            color=self.state.advanced.global_color,
        )
        self.state.set_corner_config(self.corner_attr, config)
        self.changed.emit()
    
    def _load_state(self):
        """从 AppState 加载配置。"""
        config: CornerConfig = getattr(self.state, self.corner_attr)
        
        # 加载字段（限制最多3个）
        for field in config.fields[:3]:
            self._add_field_row(field)
        if not config.fields:
            self._add_field_row()  # 至少一个空字段
        
        self.sep_input.setText(config.separator)
        
        self._update_add_btn()


class LogoTab(QWidget):
    """Logo + 自定义文本 Tab。"""
    
    changed = pyqtSignal()
    
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._setup_ui()
        self._load_state()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Logo 开关
        logo_enable_layout = QHBoxLayout()
        logo_enable_layout.addWidget(QLabel("Logo："))
        self.logo_combo = QComboBox()
        self.logo_combo.addItems(["自动匹配", "不使用", "指定文件"])
        self.logo_combo.currentTextChanged.connect(self._on_changed)
        logo_enable_layout.addWidget(self.logo_combo)
        layout.addLayout(logo_enable_layout)
        
        # Logo 位置
        pos_layout = QHBoxLayout()
        pos_layout.addWidget(QLabel("位置："))
        self.pos_combo = QComboBox()
        self.pos_combo.addItems(["right", "center", "left"])
        self.pos_combo.currentTextChanged.connect(self._on_changed)
        pos_layout.addWidget(self.pos_combo)
        layout.addLayout(pos_layout)
        
        # Logo 分隔线颜色
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("分隔线颜色："))
        self.logo_color_input = QLineEdit("#FFFFFF")
        self.logo_color_input.setFixedWidth(80)
        self.logo_color_input.textChanged.connect(self._on_changed)
        color_layout.addWidget(self.logo_color_input)
        
        self.logo_color_btn = QPushButton()
        self.logo_color_btn.setFixedSize(24, 24)
        self.logo_color_btn.clicked.connect(self._pick_logo_color)
        color_layout.addWidget(self.logo_color_btn)
        color_layout.addStretch()
        layout.addLayout(color_layout)
        
        # 自定义 Logo 路径
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("自定义路径："))
        self.logo_path_input = QLineEdit()
        self.logo_path_input.setPlaceholderText("选择 Logo 文件...")
        path_layout.addWidget(self.logo_path_input)
        
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_logo)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)
        
        # 品牌替换按钮
        replace_btn = QPushButton("品牌替换...")
        replace_btn.clicked.connect(self._show_logo_dialog)
        layout.addWidget(replace_btn)
        
        # 全局自定义文本
        text_layout = QHBoxLayout()
        text_layout.addWidget(QLabel("自定义文本："))
        self.custom_text = QLineEdit()
        self.custom_text.setPlaceholderText("全局自定义文本...")
        self.custom_text.textChanged.connect(self._on_changed)
        text_layout.addWidget(self.custom_text)
        layout.addLayout(text_layout)
        
        layout.addStretch()
    
    def _pick_logo_color(self):
        color = QColorDialog.getColor(QColor(self.logo_color_input.text()), self)
        if color.isValid():
            hex_color = color.name().upper()
            self.logo_color_input.setText(hex_color)
            self._update_color_btn(hex_color)
    
    def _update_color_btn(self, color: str):
        self.logo_color_btn.setStyleSheet(
            f"background-color: {color}; border-radius: 4px; border: 1px solid #666666;"
        )
    
    def _browse_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 Logo", "", "图片 (*.png *.jpg *.jpeg)"
        )
        if path:
            self.logo_path_input.setText(path)
            self._on_changed()
    
    def _show_logo_dialog(self):
        # TODO: 弹出 LogoDialog
        pass
    
    def _on_changed(self):
        enabled_map = {"自动匹配": "auto", "不使用": "disabled", "指定文件": "custom"}
        config = LogoConfig(
            enabled=enabled_map.get(self.logo_combo.currentText(), "auto"),
            position=self.pos_combo.currentText(),
            color=self.logo_color_input.text(),
            custom_path=self.logo_path_input.text(),
        )
        self.state.set_logo_config(config)
        self.state.set_custom_text(self.custom_text.text())
        self.changed.emit()
    
    def _load_state(self):
        logo = self.state.logo
        enabled_rev = {"auto": "自动匹配", "disabled": "不使用", "custom": "指定文件"}
        idx = self.logo_combo.findText(enabled_rev.get(logo.enabled, "自动匹配"))
        if idx >= 0:
            self.logo_combo.setCurrentIndex(idx)
        
        idx = self.pos_combo.findText(logo.position)
        if idx >= 0:
            self.pos_combo.setCurrentIndex(idx)
        
        self.logo_color_input.setText(logo.color)
        self._update_color_btn(logo.color)
        self.logo_path_input.setText(logo.custom_path)
        self.custom_text.setText(self.state.custom_text)


class ConfigPanel(QWidget):
    """水印配置面板 — 含四角 Tab + Logo Tab。"""
    
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        
        # 四角 Tab
        for name in ["左上", "左下", "右上", "右下"]:
            editor = CornerEditor(name, self.state)
            self.tabs.addTab(editor, name)
        
        # Logo Tab
        self.logo_tab = LogoTab(self.state)
        self.tabs.addTab(self.logo_tab, "Logo + 自定义")
        
        layout.addWidget(self.tabs)
