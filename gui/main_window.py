"""主窗口 — 整合所有组件，不做 God Object。"""

from pathlib import Path
import logging

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QPushButton, QLineEdit, QCheckBox,
    QProgressBar, QLabel, QFileDialog, QMessageBox,
    QFrame, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal

from .models import AppState
from .styles import get_stylesheet
from .thumb_grid import ThumbContainer
from .config_panel import ConfigPanel
from .advanced_panel import AdvancedPanel
from .template_manager import TemplateManager
from .template_assembler import state_to_processors
from .process_thread import ProcessThread


class CollapsibleConfigPanel(QFrame):
    """可折叠配置抽屉 — 包含三大 Tab。"""
    
    def __init__(self, state: AppState, project_root: Path, parent=None):
        super().__init__(parent)
        self.state = state
        self.project_root = project_root
        self._expanded = False
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 折叠标题栏
        self.header = QPushButton("▶ 高级配置")
        self.header.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: #1E1E1E;
                color: #999999;
                padding: 10px 12px;
                text-align: left;
                font-weight: bold;
                font-size: 13px;
                border-top: 1px solid #333333;
                border-bottom: 1px solid #333333;
            }
            QPushButton:hover {
                background-color: #2A2A2A;
                color: #E0E0E0;
            }
        """)
        self.header.clicked.connect(self._toggle)
        layout.addWidget(self.header)
        
        # 内容区域（默认隐藏）
        self.content = QWidget()
        self.content.setVisible(False)
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(8)
        
        # 三大 Tab（自适应高度，避免小屏幕溢出）
        self.tabs = QTabWidget()
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        self.config_panel = ConfigPanel(self.state)
        self.tabs.addTab(self.config_panel, "水印配置")
        
        self.advanced_panel = AdvancedPanel(self.state)
        self.tabs.addTab(self.advanced_panel, "高级设置")
        
        self.template_manager = TemplateManager(self.state, self.project_root)
        self.template_manager.template_applied.connect(self._on_template_applied)
        self.tabs.addTab(self.template_manager, "模板")
        
        content_layout.addWidget(self.tabs)
        layout.addWidget(self.content)
    
    def _toggle(self):
        self._expanded = not self._expanded
        self.content.setVisible(self._expanded)
        self.header.setText("▼ 高级配置" if self._expanded else "▶ 高级配置")
    
    def _on_template_applied(self, name: str):
        self.advanced_panel._load_state()
        QMessageBox.information(self, "模板已应用", f"已应用模板：{name}")
    
    def setEnabled(self, enabled: bool):
        self.content.setEnabled(enabled)
        # 标题栏保持可点击


class MainWindow(QMainWindow):
    """主窗口 — 职责：创建框架、实例化 AppState、传给 Tab、连接 START。"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("极简水印")
        self.setMinimumSize(450, 550)
        self.resize(500, 600)
        
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
        
        # === 上层：缩略图容器 ===
        self.thumb_container = ThumbContainer()
        self.thumb_container.file_added.connect(self._on_files_added)
        self.thumb_container.file_removed.connect(self._on_file_removed)
        layout.addWidget(self.thumb_container)
        
        # === 中层：底部操作区 + 配置抽屉 ===
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(6)
        
        # 输出路径行：输入框自适应，浏览/覆盖右对齐
        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("输出路径："))
        self.output_input = QLineEdit(self.app_state.output.path)
        self.output_input.setPlaceholderText("{source_dir}/logo")
        self.output_input.textChanged.connect(self._on_output_changed)
        output_row.addWidget(self.output_input, 1)  # stretch=1，自适应
        
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_output)
        output_row.addWidget(browse_btn)
        
        self.override_check = QCheckBox("覆盖")
        self.override_check.setChecked(self.app_state.output.override)
        self.override_check.stateChanged.connect(self._on_output_changed)
        output_row.addWidget(self.override_check)
        
        bottom_layout.addLayout(output_row)
        
        # 进度条 + START按钮（同一行）
        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(28)
        progress_row.addWidget(self.progress_bar, 1)
        
        # START / 取消按钮
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        progress_row.addWidget(self.cancel_btn)
        
        self.start_btn = QPushButton("START")
        self.start_btn.setObjectName("primary")
        self.start_btn.setFixedWidth(80)
        self.start_btn.setFixedHeight(28)
        self.start_btn.clicked.connect(self._on_start)
        progress_row.addWidget(self.start_btn)
        
        bottom_layout.addLayout(progress_row)
        
        # 配置抽屉（紧接进度条下方）
        self.config_drawer = CollapsibleConfigPanel(self.app_state, self.project_root)
        bottom_layout.addWidget(self.config_drawer)
        
        layout.addWidget(bottom)
        
        # === 关键：把所有多余空间推到底部 ===
        layout.addStretch(1)
        
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
        """开始处理 — 启动真实处理线程。"""
        if not self.app_state.selected_files:
            QMessageBox.warning(self, "提示", "请先选择图片")
            return
        
        # 准备处理器配置
        try:
            processors = state_to_processors(self.app_state)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"配置生成失败: {e}")
            return
        
        # 解析输出路径模式
        output_pattern = self.output_input.text().strip() or "{source_dir}/logo"
        
        # 禁用控件
        self._set_processing_state(True)
        
        # 启动处理线程
        self._thread = ProcessThread(
            files=self.app_state.selected_files,
            processors=processors,
            output_pattern=output_pattern,
            override=self.override_check.isChecked(),
            parent=self,
        )
        self._thread.progress.connect(self._on_thread_progress)
        self._thread.file_done.connect(self._on_file_done)
        self._thread.finished_all.connect(self._on_finished_all)
        self._thread.start()
    
    def _on_thread_progress(self, progress: int, status: str):
        """接收线程进度更新。"""
        self.app_state.set_processing(True, progress, status)
    
    def _on_file_done(self, file_path: str, success: bool, message: str):
        """单个文件处理完成。"""
        if not success:
            logging.getLogger(__name__).warning(f"处理失败: {file_path} — {message}")
    
    def _on_finished_all(self, all_success: bool, message: str):
        """全部处理完成。"""
        self._set_processing_state(False)
        self.app_state.set_processing(False, 100 if all_success else 0, "完成" if all_success else "部分失败")
        
        if all_success:
            QMessageBox.information(self, "完成", message)
        else:
            QMessageBox.warning(self, "处理结果", message)
    
    def _on_cancel(self):
        """取消处理。"""
        if hasattr(self, '_thread') and self._thread.isRunning():
            self._thread.cancel()
            self._thread.wait(3000)  # 等待最多 3 秒
        self.app_state.set_processing(False, 0, "已取消")
        self._set_processing_state(False)
    
    def _on_progress_changed(self, progress: int, status: str):
        self.progress_bar.setValue(progress)
        # 进度条文字直接显示状态
        self.progress_bar.setFormat(f"{status} %p%")
    
    def _set_processing_state(self, processing: bool):
        """切换处理中/就绪状态。"""
        self.start_btn.setVisible(not processing)
        self.cancel_btn.setVisible(processing)
        self.thumb_container.setEnabled(not processing)
        self.config_drawer.setEnabled(not processing)
        self.output_input.setEnabled(not processing)
        self.override_check.setEnabled(not processing)
    
    def closeEvent(self, event):
        """退出时保存配置。"""
        self.app_state.save_to_disk(self.project_root)
        event.accept()
