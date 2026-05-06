"""品牌替换弹窗 — 管理 Logo 品牌替换。"""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class LogoDialog(QDialog):
    """品牌替换弹窗。"""
    
    def __init__(self, project_root: Path, parent=None):
        super().__init__(parent)
        self.project_root = project_root
        self.logos_dir = project_root / "config" / "logos"
        self.custom_dir = self.logos_dir / "custom"
        self.custom_dir.mkdir(parents=True, exist_ok=True)
        
        self.setWindowTitle("品牌替换")
        self.setMinimumSize(500, 300)
        self._setup_ui()
        self._load_brands()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # 说明文字
        info = QLabel("替换各品牌 Logo 图片。替换后优先使用自定义版本，可恢复默认。")
        info.setStyleSheet("color: #999999; font-size: 12px;")
        layout.addWidget(info)
        
        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["品牌", "状态", "操作"])
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 200)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        layout.addWidget(self.table)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
    
    def _load_brands(self):
        """扫描内置 Logo 目录，列出所有品牌。"""
        # 获取内置品牌列表
        builtin_dir = self.logos_dir / "builtin"
        if not builtin_dir.exists():
            builtin_dir = self.logos_dir  #  fallback
        
        brands = []
        if builtin_dir.exists():
            for f in builtin_dir.iterdir():
                if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg"):
                    brands.append(f.stem)
        
        brands.sort()
        
        self.table.setRowCount(len(brands))
        for i, brand in enumerate(brands):
            # 品牌名
            self.table.setItem(i, 0, QTableWidgetItem(brand))
            
            # 检查是否有自定义版本
            custom_path = self.custom_dir / f"{brand}.png"
            has_custom = custom_path.exists()
            status = "已替换" if has_custom else "默认"
            status_item = QTableWidgetItem(status)
            status_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(i, 1, status_item)
            
            # 操作按钮
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(4, 2, 4, 2)
            btn_layout.setSpacing(6)
            
            replace_btn = QPushButton("替换")
            replace_btn.clicked.connect(lambda checked, b=brand: self._replace_brand(b))
            btn_layout.addWidget(replace_btn)
            
            if has_custom:
                restore_btn = QPushButton("恢复默认")
                restore_btn.clicked.connect(lambda checked, b=brand: self._restore_brand(b))
                btn_layout.addWidget(restore_btn)
            
            btn_layout.addStretch()
            self.table.setCellWidget(i, 2, btn_widget)
    
    def _replace_brand(self, brand: str):
        """替换品牌 Logo。"""
        path, _ = QFileDialog.getOpenFileName(
            self, f"选择 {brand} 的 Logo", "",
            "图片 (*.png *.jpg *.jpeg)"
        )
        if path:
            # 复制到 custom 目录
            import shutil
            dest = self.custom_dir / f"{brand}.png"
            try:
                shutil.copy2(path, dest)
                QMessageBox.information(self, "成功", f"已替换 {brand} Logo")
                self._load_brands()  # 刷新表格
            except Exception as e:
                QMessageBox.warning(self, "错误", f"替换失败: {e}")
    
    def _restore_brand(self, brand: str):
        """恢复默认 Logo。"""
        custom_path = self.custom_dir / f"{brand}.png"
        if custom_path.exists():
            try:
                custom_path.unlink()
                QMessageBox.information(self, "成功", f"已恢复 {brand} 默认 Logo")
                self._load_brands()  # 刷新表格
            except Exception as e:
                QMessageBox.warning(self, "错误", f"恢复失败: {e}")
