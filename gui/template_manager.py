"""模板管理器 — 模板列表、预览、保存、应用。"""

from pathlib import Path
from typing import List, Dict, Any
import json
import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QMessageBox, QInputDialog, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage

from .models import AppState
from .template_assembler import load_template, save_template, processors_to_state

logger = logging.getLogger(__name__)


class TemplateManager(QWidget):
    """模板管理面板。"""
    
    template_applied = pyqtSignal(str)  # 应用模板名称
    
    def __init__(self, state: AppState, project_root: Path, parent=None):
        super().__init__(parent)
        self.state = state
        self.project_root = project_root
        self.templates_dir = project_root / "config" / "templates"
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        self._setup_ui()
        self._load_templates()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 左右分栏
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：模板列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.list_widget = QListWidget()
        self.list_widget.setMinimumWidth(200)
        self.list_widget.itemClicked.connect(self._on_template_selected)
        self.list_widget.itemDoubleClicked.connect(self._on_template_applied)
        left_layout.addWidget(self.list_widget)
        
        # 右侧：操作按钮 + 预览
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(12, 0, 0, 0)
        right_layout.setSpacing(8)
        
        # 模板信息
        self.info_label = QLabel("选择一个模板查看详情")
        self.info_label.setStyleSheet("color: #999999; font-size: 12px;")
        self.info_label.setWordWrap(True)
        right_layout.addWidget(self.info_label)
        
        # 预览区域
        self.preview_label = QLabel()
        self.preview_label.setFixedSize(240, 160)
        self.preview_label.setStyleSheet("border: 1px solid #333333; border-radius: 4px; background-color: #1E1E1E;")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.preview_label)
        
        # 操作按钮
        self.apply_btn = QPushButton("应用此模板")
        self.apply_btn.clicked.connect(self._on_template_applied)
        right_layout.addWidget(self.apply_btn)
        
        save_btn = QPushButton("保存当前为模板")
        save_btn.clicked.connect(self._save_current_as_template)
        right_layout.addWidget(save_btn)
        
        save_as_btn = QPushButton("模板另存为...")
        save_as_btn.clicked.connect(self._save_as_template)
        right_layout.addWidget(save_as_btn)
        
        self.delete_btn = QPushButton("删除模板")
        self.delete_btn.setStyleSheet("QPushButton { color: #EF4444; }")
        self.delete_btn.clicked.connect(self._delete_template)
        right_layout.addWidget(self.delete_btn)
        
        right_layout.addStretch()
        
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([300, 300])
        layout.addWidget(splitter)
    
    def _load_templates(self):
        """加载所有模板。"""
        self.list_widget.clear()
        
        # 内置模板
        builtin_dir = self.templates_dir / "builtin"
        if builtin_dir.exists():
            for f in sorted(builtin_dir.iterdir()):
                if f.suffix == ".json":
                    self._add_template_item(f.stem, "内置", str(f))
        
        # 自定义模板
        for f in sorted(self.templates_dir.iterdir()):
            if f.is_file() and f.suffix == ".json":
                self._add_template_item(f.stem, "自定义", str(f))
    
    def _add_template_item(self, name: str, tag: str, path: str):
        """添加模板列表项。"""
        item = QListWidgetItem(f"{name}  [{tag}]")
        item.setData(Qt.ItemDataRole.UserRole, path)
        item.setData(Qt.ItemDataRole.UserRole + 1, tag)
        self.list_widget.addItem(item)
    
    def _get_selected_template(self) -> tuple:
        """获取当前选中的模板 (name, path, tag)。"""
        item = self.list_widget.currentItem()
        if not item:
            return None, None, None
        text = item.text()
        name = text.split("  [")[0]
        path = item.data(Qt.ItemDataRole.UserRole)
        tag = item.data(Qt.ItemDataRole.UserRole + 1)
        return name, path, tag
    
    def _on_template_selected(self):
        """选中模板时更新预览。"""
        name, path, tag = self._get_selected_template()
        if not name:
            return
        
        self.info_label.setText(f"模板：{name}\n类型：{tag}")
        
        # 生成预览
        self._generate_preview(path)
        
        # 自定义模板才可删除
        self.delete_btn.setEnabled(tag == "自定义")
    
    def _generate_preview(self, template_path: str):
        """生成模板预览图。"""
        # 简化预览：显示模板 JSON 中的 processor 列表
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                processors = json.load(f)
            names = [p.get("processor_name", "未知") for p in processors[:5]]
            text = "处理器:\n" + "\n".join(names)
            if len(processors) > 5:
                text += f"\n... 等 {len(processors)} 个处理器"
            self.preview_label.setText(text)
            self.preview_label.setStyleSheet("""
                QLabel {
                    border: 1px solid #333333;
                    border-radius: 4px;
                    background-color: #1E1E1E;
                    color: #E0E0E0;
                    font-size: 11px;
                    padding: 8px;
                }
            """)
        except Exception:
            self.preview_label.setText("预览生成失败")
    
    def _on_template_applied(self):
        """应用选中模板。"""
        name, path, tag = self._get_selected_template()
        if not name:
            QMessageBox.warning(self, "提示", "请先选择一个模板")
            return
        
        try:
            processors = load_template(Path(path))
            processors_to_state(processors, self.state)
            self.state.set_template(name)
            self.template_applied.emit(name)
            QMessageBox.information(self, "成功", f"已应用模板：{name}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"应用模板失败: {e}")
    
    def _save_current_as_template(self):
        """保存当前配置为新模板。"""
        from .template_assembler import state_to_processors
        
        name, ok = QInputDialog.getText(self, "保存模板", "模板名称：")
        if not ok or not name:
            return
        
        # 检查是否已存在
        template_path = self.templates_dir / f"{name}.json"
        if template_path.exists():
            reply = QMessageBox.question(
                self, "确认", f"模板 '{name}' 已存在，是否覆盖？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        try:
            processors = state_to_processors(self.state)
            save_template(processors, template_path)
            self._load_templates()
            QMessageBox.information(self, "成功", f"模板 '{name}' 已保存")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存失败: {e}")
    
    def _save_as_template(self):
        """另存为（复制现有模板）。"""
        name, path, tag = self._get_selected_template()
        if not name:
            QMessageBox.warning(self, "提示", "请先选择一个模板")
            return
        
        new_name, ok = QInputDialog.getText(self, "另存为", "新模板名称：", text=f"{name}_副本")
        if not ok or not new_name:
            return
        
        new_path = self.templates_dir / f"{new_name}.json"
        if new_path.exists():
            QMessageBox.warning(self, "提示", f"'{new_name}' 已存在")
            return
        
        try:
            import shutil
            shutil.copy2(path, new_path)
            self._load_templates()
            QMessageBox.information(self, "成功", f"已另存为 '{new_name}'")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"另存失败: {e}")
    
    def _delete_template(self):
        """删除自定义模板。"""
        name, path, tag = self._get_selected_template()
        if not name:
            return
        
        if tag == "内置":
            QMessageBox.warning(self, "提示", "内置模板不能删除")
            return
        
        reply = QMessageBox.question(
            self, "确认", f"确定删除模板 '{name}'？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                Path(path).unlink()
                self._load_templates()
                self.preview_label.clear()
                self.preview_label.setStyleSheet("border: 1px solid #333333; border-radius: 4px; background-color: #1E1E1E;")
                self.info_label.setText("选择一个模板查看详情")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"删除失败: {e}")
