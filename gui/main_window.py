"""主窗口 — 整合所有组件，不做 God Object。"""

from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QPushButton, QLineEdit, QCheckBox,
    QProgressBar, QLabel, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt

from .models import AppState
from .styles import get_stylesheet
from .thumb_grid import ThumbContainer
from .config_panel import ConfigPanel
from .advanced_panel import AdvancedPanel
from .template_manager import TemplateManager
from .template_assembler import state_to_processors


class MainWindow(QMainWindow):
    """主窗口 — 职责：创建框架、实例化 AppState、传给 Tab、连接 START。"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("极简水印")
        self.setMinimumSize(900, 650)
        
        # 项目根目录
        self.project_root = Path(__file__).parent.parent
        
        # 应用 QSS
        self.setStyleSheet(get_stylesheet())
        
        # 初始化 AppState
        self.app_state = AppState()
        self.app_state.load_from_disk(self.project_root)
        
        # 构建 UI
        self._setup_ui()
    
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        
        # === 缩略图容器 ===
        self.thumb_container = ThumbContainer()
        self.thumb_container.file_added.connect(self._on_files_added)
        self.thumb_container.file_removed.connect(self._on_file_removed)
        layout.addWidget(self.thumb_container)
        
        # === 三大 Tab ===
        self.tabs = QTabWidget()
        
        # 水印配置
        self.config_panel = ConfigPanel(self.app_state)
        self.tabs.addTab(self.config_panel, "水印配置")
        
        # 高级设置
        self.advanced_panel = AdvancedPanel(self.app_state)
        self.tabs.addTab(self.advanced_panel, "高级设置")
        
        # 模板管理
        self.template_manager = TemplateManager(self.app_state, self.project_root)
        self.template_manager.template_applied.connect(self._on_template_applied)
        self.tabs.addTab(self.template_manager, "模板")
        
        layout.addWidget(self.tabs, 1)
        
        # === 底部操作区 ===
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(8)
        
        # 输出路径
        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("输出路径："))
        self.output_input = QLineEdit(self.app_state.output.path)
        self.output_input.setPlaceholderText("{source_dir}/logo")
        self.output_input.textChanged.connect(self._on_output_changed)
        output_row.addWidget(self.output_input)
        
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_output)
        output_row.addWidget(browse_btn)
        
        self.override_check = QCheckBox("覆盖已存在")
        self.override_check.setChecked(self.app_state.output.override)
        self.override_check.stateChanged.connect(self._on_output_changed)
        output_row.addWidget(self.override_check)
        output_row.addStretch()
        bottom_layout.addLayout(output_row)
        
        # 进度条 + 状态
        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_row.addWidget(self.progress_bar, 1)
        
        self.status_label = QLabel("就绪")
        self.status_label.setFixedWidth(120)
        progress_row.addWidget(self.status_label)
        bottom_layout.addLayout(progress_row)
        
        # START 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self.cancel_btn)
        
        self.start_btn = QPushButton("START")
        self.start_btn.setObjectName("primary")
        self.start_btn.setFixedWidth(120)
        self.start_btn.setFixedHeight(36)
        self.start_btn.clicked.connect(self._on_start)
        btn_row.addWidget(self.start_btn)
        
        bottom_layout.addLayout(btn_row)
        
        layout.addWidget(bottom)
        
        # 连接 AppState 信号
        self.app_state.files_changed.connect(self._on_state_files_changed)
        self.app_state.progress_changed.connect(self._on_progress_changed)
    
    # ---- 事件处理 ----
    def _on_files_added(self, paths):
        self.app_state.add_files(paths)
    
    def _on_file_removed(self, index):
        self.app_state.remove_file(index)
    
    def _on_state_files_changed(self, files):
        self.thumb_container.set_files(files)
    
    def _on_output_changed(self):
        self.app_state.set_output(
            self.output_input.text(),
            self.override_check.isChecked()
        )
    
    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.output_input.setText(path)
    
    def _on_template_applied(self, name: str):
        """模板应用后同步 UI。"""
        # 高级设置面板需要刷新
        self.advanced_panel._load_state()
        # 水印配置面板需要刷新
        # TODO: ConfigPanel 也需要刷新方法
        QMessageBox.information(self, "模板已应用", f"已应用模板：{name}")
    
    def _on_start(self):
        """开始处理。"""
        if not self.app_state.selected_files:
            QMessageBox.warning(self, "提示", "请先选择图片")
            return
        
        # 准备处理器
        try:
            processors = state_to_processors(self.app_state)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"配置生成失败: {e}")
            return
        
        # 禁用控件
        self._set_processing_state(True)
        
        # TODO: 启动 ProcessThread
        self.app_state.set_processing(True, 0, "处理中...")
        
        # 模拟处理（后续替换为真实处理线程）
        from PyQt6.QtCore import QTimer
        self._progress = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._simulate_progress)
        self._timer.start(100)
    
    def _simulate_progress(self):
        """模拟进度（临时，后续替换为真实线程）。"""
        self._progress += 5
        if self._progress >= 100:
            self._progress = 100
            self._timer.stop()
            self.app_state.set_processing(False, 100, "完成")
            self._set_processing_state(False)
            QMessageBox.information(self, "完成", f"处理了 {len(self.app_state.selected_files)} 张图片")
        else:
            self.app_state.set_processing(True, self._progress, "处理中...")
    
    def _on_cancel(self):
        """取消处理。"""
        if hasattr(self, '_timer') and self._timer.isActive():
            self._timer.stop()
        self.app_state.set_processing(False, 0, "已取消")
        self._set_processing_state(False)
    
    def _on_progress_changed(self, progress: int, status: str):
        self.progress_bar.setValue(progress)
        self.status_label.setText(status)
    
    def _set_processing_state(self, processing: bool):
        """切换处理中/就绪状态。"""
        self.start_btn.setVisible(not processing)
        self.cancel_btn.setVisible(processing)
        self.thumb_container.setEnabled(not processing)
        self.tabs.setEnabled(not processing)
        self.output_input.setEnabled(not processing)
        self.override_check.setEnabled(not processing)
    
    def closeEvent(self, event):
        """退出时保存配置。"""
        self.app_state.save_to_disk(self.project_root)
        event.accept()
