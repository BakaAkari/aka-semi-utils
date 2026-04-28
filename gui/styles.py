"""QSS 暗色主题样式定义。"""

# 配色表
COLORS = {
    "BG": "#121212",
    "SURFACE": "#1E1E1E",
    "SURFACE_HOVER": "#2A2A2A",
    "BORDER": "#333333",
    "BORDER_HOVER": "#666666",
    "TEXT_PRIMARY": "#E0E0E0",
    "TEXT_SECONDARY": "#999999",
    "TEXT_DISABLED": "#666666",
    "ACCENT": "#E0E0E0",
    "ACCENT_HOVER": "#FFFFFF",
    "DANGER": "#EF4444",
}


def get_stylesheet() -> str:
    """返回完整 QSS 样式表。"""
    c = COLORS
    return f"""
    /* 全局基础 */
    QWidget {{
        background-color: {c["BG"]};
        color: {c["TEXT_PRIMARY"]};
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 13px;
    }}
    
    /* 主窗口 */
    QMainWindow {{
        background-color: {c["BG"]};
    }}
    
    /* Tab */
    QTabWidget::pane {{
        border: 1px solid {c["BORDER"]};
        background-color: {c["BG"]};
    }}
    QTabBar::tab {{
        background-color: {c["SURFACE"]};
        color: {c["TEXT_SECONDARY"]};
        padding: 8px 16px;
        border: 1px solid {c["BORDER"]};
        border-bottom: none;
        margin-right: 2px;
    }}
    QTabBar::tab:selected {{
        background-color: {c["BG"]};
        color: {c["TEXT_PRIMARY"]};
        border-bottom: 2px solid {c["ACCENT"]};
    }}
    QTabBar::tab:hover:!selected {{
        background-color: {c["SURFACE_HOVER"]};
        color: {c["TEXT_PRIMARY"]};
    }}
    
    /* 分组框 */
    QGroupBox {{
        border: 1px solid {c["BORDER"]};
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 8px;
        font-weight: bold;
        color: {c["TEXT_PRIMARY"]};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
        color: {c["TEXT_SECONDARY"]};
    }}
    
    /* 按钮 */
    QPushButton {{
        background-color: {c["SURFACE"]};
        color: {c["TEXT_PRIMARY"]};
        border: 1px solid {c["BORDER"]};
        border-radius: 4px;
        padding: 6px 12px;
        min-height: 28px;
    }}
    QPushButton:hover {{
        background-color: {c["SURFACE_HOVER"]};
        border-color: {c["BORDER_HOVER"]};
    }}
    QPushButton:pressed {{
        background-color: {c["BORDER"]};
    }}
    QPushButton:disabled {{
        background-color: {c["SURFACE"]};
        color: {c["TEXT_DISABLED"]};
        border-color: {c["BORDER"]};
    }}
    QPushButton#primary {{
        background-color: {c["ACCENT"]};
        color: {c["BG"]};
        border: none;
    }}
    QPushButton#primary:hover {{
        background-color: {c["ACCENT_HOVER"]};
    }}
    QPushButton#danger {{
        background-color: {c["DANGER"]};
        color: white;
        border: none;
    }}
    
    /* 输入框 */
    QLineEdit {{
        background-color: {c["SURFACE"]};
        color: {c["TEXT_PRIMARY"]};
        border: 1px solid {c["BORDER"]};
        border-radius: 4px;
        padding: 4px 8px;
        min-height: 24px;
    }}
    QLineEdit:focus {{
        border-color: {c["ACCENT"]};
    }}
    QLineEdit:disabled {{
        color: {c["TEXT_DISABLED"]};
    }}
    
    /* 下拉框 */
    QComboBox {{
        background-color: {c["SURFACE"]};
        color: {c["TEXT_PRIMARY"]};
        border: 1px solid {c["BORDER"]};
        border-radius: 4px;
        padding: 4px 8px;
        min-height: 24px;
    }}
    QComboBox:focus {{
        border-color: {c["ACCENT"]};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {c["SURFACE"]};
        color: {c["TEXT_PRIMARY"]};
        border: 1px solid {c["BORDER"]};
        selection-background-color: {c["SURFACE_HOVER"]};
    }}
    
    /* 数字输入框 */
    QSpinBox, QDoubleSpinBox {{
        background-color: {c["SURFACE"]};
        color: {c["TEXT_PRIMARY"]};
        border: 1px solid {c["BORDER"]};
        border-radius: 4px;
        padding: 4px 8px;
        min-height: 24px;
    }}
    QSpinBox:focus, QDoubleSpinBox:focus {{
        border-color: {c["ACCENT"]};
    }}
    
    /* Slider */
    QSlider::groove:horizontal {{
        height: 4px;
        background-color: {c["BORDER"]};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        width: 14px;
        height: 14px;
        background-color: {c["ACCENT"]};
        border-radius: 7px;
        margin: -5px 0;
    }}
    QSlider::sub-page:horizontal {{
        background-color: {c["ACCENT"]};
        border-radius: 2px;
    }}
    
    /* Checkbox */
    QCheckBox {{
        color: {c["TEXT_PRIMARY"]};
        spacing: 6px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {c["BORDER"]};
        border-radius: 3px;
        background-color: {c["SURFACE"]};
    }}
    QCheckBox::indicator:checked {{
        background-color: {c["ACCENT"]};
        border-color: {c["ACCENT"]};
    }}
    
    /* 进度条 */
    QProgressBar {{
        background-color: {c["SURFACE"]};
        border: 1px solid {c["BORDER"]};
        border-radius: 4px;
        text-align: center;
        color: {c["TEXT_PRIMARY"]};
        min-height: 20px;
    }}
    QProgressBar::chunk {{
        background-color: {c["ACCENT"]};
        border-radius: 3px;
    }}
    
    /* 列表 */
    QListWidget {{
        background-color: {c["SURFACE"]};
        color: {c["TEXT_PRIMARY"]};
        border: 1px solid {c["BORDER"]};
        border-radius: 4px;
        outline: none;
    }}
    QListWidget::item {{
        padding: 6px 8px;
        border-bottom: 1px solid {c["BORDER"]};
    }}
    QListWidget::item:selected {{
        background-color: {c["SURFACE_HOVER"]};
        color: {c["TEXT_PRIMARY"]};
    }}
    QListWidget::item:hover {{
        background-color: {c["SURFACE_HOVER"]};
    }}
    
    /* 表格 */
    QTableWidget {{
        background-color: {c["SURFACE"]};
        color: {c["TEXT_PRIMARY"]};
        border: 1px solid {c["BORDER"]};
        gridline-color: {c["BORDER"]};
        outline: none;
    }}
    QTableWidget::item {{
        padding: 6px;
    }}
    QTableWidget::item:selected {{
        background-color: {c["SURFACE_HOVER"]};
    }}
    QHeaderView::section {{
        background-color: {c["SURFACE"]};
        color: {c["TEXT_SECONDARY"]};
        padding: 6px;
        border: 1px solid {c["BORDER"]};
        font-weight: bold;
    }}
    
    /* 菜单 */
    QMenu {{
        background-color: {c["SURFACE"]};
        color: {c["TEXT_PRIMARY"]};
        border: 1px solid {c["BORDER"]};
        padding: 4px;
    }}
    QMenu::item {{
        padding: 6px 20px;
        border-radius: 3px;
    }}
    QMenu::item:selected {{
        background-color: {c["SURFACE_HOVER"]};
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {c["BORDER"]};
        margin: 4px 8px;
    }}
    
    /* 滚动条 */
    QScrollBar:vertical {{
        background-color: {c["BG"]};
        width: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background-color: {c["BORDER"]};
        border-radius: 4px;
        min-height: 20px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {c["BORDER_HOVER"]};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    
    /* 对话框 */
    QDialog {{
        background-color: {c["BG"]};
    }}
    QMessageBox {{
        background-color: {c["BG"]};
    }}
    """
