"""主窗口 — 整合所有组件，不做 God Object。"""

import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .advanced_panel import AdvancedPanel
from .config_panel import ConfigPanel
from .error_presenter import BatchSummary, PresentedError, Severity
from .models import AppState
from .preview_panel import PreviewPanel
from .process_thread import ProcessThread
from .styles import get_stylesheet
from .template_assembler import state_to_processors
from .thumb_grid import ThumbContainer


class CollapsibleConfigPanel(QFrame):
    """可折叠配置抽屉 — 包含「水印配置 / 全局参数」两个 Tab。

    Phase 27：预览 Tab 已抽离到右侧 :class:`CollapsiblePreviewSidebar`，
    本面板只负责水印配置 + 全局参数。
    """

    def __init__(self, state: AppState, project_root: Path, parent=None, expanded: bool = True):
        super().__init__(parent)
        self.state = state
        self.project_root = project_root
        self._expanded = expanded

        self._setup_ui()
        # Phase 6.10：默认展开配置抽屉，让新用户立即看到水印配置入口
        if self._expanded:
            self.content.setVisible(True)
            self.header.setText("▼ 全局参数")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 折叠标题栏
        self.header = QPushButton("▶ 全局参数")
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

        # 内容区域（可见性由 _expanded 控制，default 为展开）
        self.content = QWidget()
        self.content.setVisible(self._expanded)
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(8)

        # Tab 区（Phase 27：预览 Tab 已迁出，只剩水印配置 + 全局参数）
        self.tabs = QTabWidget()
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.config_panel = ConfigPanel(self.state)
        self.tabs.addTab(self.config_panel, "水印配置")

        self.advanced_panel = AdvancedPanel(self.state)
        self.tabs.addTab(self.advanced_panel, "全局参数")

        content_layout.addWidget(self.tabs)
        layout.addWidget(self.content)

    def _toggle(self):
        self._expanded = not self._expanded
        self.content.setVisible(self._expanded)
        self.header.setText("▼ 全局参数" if self._expanded else "▶ 全局参数")

    def setEnabled(self, enabled: bool):
        self.content.setEnabled(enabled)
        # 标题栏保持可点击


class MainWindow(QMainWindow):
    """主窗口 — 职责：创建框架、实例化 AppState、传给 Tab、连接 START。"""

    PREVIEW_WIDTH = 360  # 预览侧栏固定宽度

    def __init__(self):
        super().__init__()
        self.setWindowTitle("极简水印")
        # Phase 13：默认高度统一 +50px，给缩略图 2 行 + 居中布局留更舒展的视觉空间
        self.setMinimumSize(450, 600)
        self.resize(500, 650)

        # 项目根目录
        self.project_root = Path(__file__).parent.parent

        # 应用 QSS
        self.setStyleSheet(get_stylesheet())

        # Phase 9：信号回写守卫（防止从 AppState 回填 UI 时再触发 _on_*_changed 写回 AppState）
        self._output_loading: bool = False

        # 初始化 AppState（Phase 9：先空状态构建 UI 让所有信号订阅就位，再 load_from_disk
        # 让 _emit_full_refresh 推送给所有订阅者完成首次同步）
        self.app_state = AppState()

        # 构建 UI（订阅 *_changed 信号）
        self._setup_ui()

        # 加载持久化配置 — 此时所有 GUI 订阅者已就位，会通过 _emit_full_refresh 收到完整刷新
        self.app_state.load_from_disk(self.project_root)
    
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        # === 顶层水平双列 — 左原内容 + 右预览侧栏 ===
        root = QHBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(0)

        # ---- 左列：纵向布局（缩略图 + 底部操作 + 配置抽屉） ----
        left_col = QWidget()
        layout = QVBoxLayout(left_col)
        layout.setContentsMargins(0, 0, 0, 0)
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
        self.output_input = QLineEdit()
        self.output_input.setPlaceholderText("{source_dir}/logo")
        self.output_input.textChanged.connect(self._on_output_changed)
        output_row.addWidget(self.output_input, 1)  # stretch=1，自适应

        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_output)
        output_row.addWidget(browse_btn)

        self.override_check = QCheckBox("覆盖")
        self.override_check.stateChanged.connect(self._on_output_changed)
        output_row.addWidget(self.override_check)

        bottom_layout.addLayout(output_row)

        # 进度条 + START按钮 + 预览切换（同一行）
        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(28)
        progress_row.addWidget(self.progress_bar, 1)

        self.about_btn = QPushButton("关于")
        self.about_btn.setFixedHeight(28)
        self.about_btn.setToolTip("查看极简水印版本与项目说明")
        self.about_btn.clicked.connect(self._show_about)
        progress_row.addWidget(self.about_btn)

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

        # 预览切换按钮（正方形，字符图标）
        self.preview_toggle_btn = QPushButton("▸")
        self.preview_toggle_btn.setFixedSize(28, 28)
        self.preview_toggle_btn.setToolTip("显示实时预览")
        self.preview_toggle_btn.clicked.connect(self._toggle_preview)
        progress_row.addWidget(self.preview_toggle_btn)

        bottom_layout.addLayout(progress_row)

        # 配置抽屉（紧接进度条下方）
        self.config_drawer = CollapsibleConfigPanel(self.app_state, self.project_root)
        bottom_layout.addWidget(self.config_drawer)

        layout.addWidget(bottom)

        # === 关键：把所有多余空间推到底部 ===
        layout.addStretch(1)

        root.addWidget(left_col, 1)  # 左列吃满剩余宽度

        # ---- 右列：预览侧栏（默认折叠，由按钮控制） ----
        self.preview_sidebar = QWidget()
        self.preview_sidebar.setFixedWidth(self.PREVIEW_WIDTH)
        self.preview_sidebar.setVisible(False)
        sidebar_layout = QVBoxLayout(self.preview_sidebar)
        sidebar_layout.setContentsMargins(8, 8, 8, 8)
        sidebar_layout.setSpacing(0)

        self.preview_panel = PreviewPanel(self.app_state)
        sidebar_layout.addWidget(self.preview_panel)
        root.addWidget(self.preview_sidebar)

        # 连接 AppState 信号（Phase 9：output_changed 也接入，让持久化值能驱动 UI）
        self.app_state.files_changed.connect(self._on_state_files_changed)
        self.app_state.output_changed.connect(self._on_state_output_changed)
        self.app_state.progress_changed.connect(self._on_progress_changed)

    def _toggle_preview(self) -> None:
        visible = not self.preview_sidebar.isVisible()

        if visible:
            # 展开：预览区宽度 = 当前主窗口宽度的 1.5 倍
            preview_w = int(self.width() * 1.5)
            self.preview_sidebar.setFixedWidth(preview_w)
            # 先拓展主窗口，再显示预览区，避免瞬间挤压左列 UI
            new_w = self.width() + preview_w
            self.resize(max(new_w, self.minimumWidth()), self.height())
            self.preview_sidebar.setVisible(True)
            self.preview_panel.set_active(True)
            self.preview_toggle_btn.setText("◂")
            self.preview_toggle_btn.setToolTip("隐藏预览")
        else:
            # 折叠：先隐藏预览区，再收回宽度
            self.preview_sidebar.setVisible(False)
            self.preview_panel.set_active(False)
            self.preview_toggle_btn.setText("▸")
            self.preview_toggle_btn.setToolTip("显示实时预览")
            new_w = max(self.width() - self.preview_sidebar.width(), self.minimumWidth())
            self.resize(new_w, self.height())
    
    # ---- 事件处理 ----
    def _on_files_added(self, paths):
        self.app_state.add_files(paths)
    
    def _on_file_removed(self, index):
        self.app_state.remove_file(index)
    
    def _on_state_files_changed(self, files):
        self.thumb_container.set_files(files)
    
    def _on_output_changed(self):
        # Phase 9：守卫期间是 AppState → UI 的回填，不能再写回去
        if self._output_loading:
            return
        self.app_state.set_output(
            self.output_input.text(),
            self.override_check.isChecked()
        )

    def _on_state_output_changed(self):
        """AppState.output 变更 → 把字段刷到 UI（Phase 9：消除启动顺序耦合）。"""
        self._output_loading = True
        try:
            self.output_input.setText(self.app_state.output.path)
            self.override_check.setChecked(self.app_state.output.override)
        finally:
            self._output_loading = False
    
    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.output_input.setText(path)

    def _show_about(self):
        """展示当前 GUI 版本的项目说明。"""
        QMessageBox.about(
            self,
            "关于 极简水印",
            """
            <h3>极简水印 aka-semi-utils</h3>
            <p>面向摄影照片的 PyQt6 图形化批量水印工具。</p>
            <p>
              支持 EXIF 信息水印、品牌 Logo、签名水印、实时预览、
              批量处理、错误汇总和三平台打包发布。
            </p>
            <p><b>版本：</b>2.1.7</p>
            <p><b>项目：</b>github.com/BakaAkari/aka-semi-utils</p>
            <p><b>许可证：</b>Apache License 2.0</p>
            """.strip(),
        )

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

        # Phase 9：旧线程残留保护 — 理论上不该发生，仅做兜底
        if getattr(self, "_thread", None) is not None and self._thread.isRunning():
            QMessageBox.warning(self, "提示", "已有处理任务在运行")
            return

        # 禁用控件
        self._set_processing_state(True)

        # 启动处理线程（Phase 9：统一生命周期管理）
        thread = ProcessThread(
            files=self.app_state.selected_files,
            processors=processors,
            output_pattern=output_pattern,
            override=self.override_check.isChecked(),
            parent=self,
        )
        thread.progress.connect(self._on_thread_progress)
        thread.file_done.connect(self._on_file_done)
        thread.file_failed_detail.connect(self._on_file_failed_detail)
        thread.finished_all.connect(self._on_finished_all)
        thread.finished_summary.connect(self._on_finished_summary)
        # 生命周期在源头解耦：finished → 清 Python 引用 + Qt 释放 C++
        thread.finished.connect(self._on_process_thread_finished)
        thread.finished.connect(thread.deleteLater)
        # Phase 4：用 list 暂存所有失败详情，结束时统一展示
        self._failed_details: list[PresentedError] = []
        self._latest_summary: BatchSummary | None = None
        self._thread = thread
        thread.start()

    def _on_process_thread_finished(self) -> None:
        """ProcessThread 结束信号槽：清空 Python 引用，避免持有已被 deleteLater 销毁的 wrapper。

        sender 守卫防止"前一个线程比新线程晚发 finished"误清。
        """
        sender = self.sender()
        if sender is getattr(self, "_thread", None):
            self._thread = None
    
    def _on_thread_progress(self, progress: int, status: str):
        """接收线程进度更新。

        Phase 10.1 (P3)：改用 ``update_progress``，不再每次刷新都 ``set_processing(True,...)``
        — 后者只在 ``_on_start`` 与 ``_on_finished_all/_on_cancel`` 这种边沿事件调用。
        """
        self.app_state.update_progress(progress, status)
    
    def _on_file_done(self, file_path: str, success: bool, message: str):
        """单个文件处理完成（向后兼容信号）。"""
        if not success:
            logging.getLogger(__name__).warning(f"处理失败: {file_path} — {message}")

    def _on_file_failed_detail(self, presented: PresentedError):
        """收到结构化错误 — Phase 4：暂存以便结束时聚合展示。"""
        self._failed_details.append(presented)

    def _on_finished_summary(self, summary: BatchSummary):
        """Phase 4：收到结构化批结果汇总（在 finished_all 之前 emit）。"""
        self._latest_summary = summary

    def _on_finished_all(self, all_success: bool, message: str):
        """全部处理完成 — Phase 4：分级展示。"""
        self._set_processing_state(False)
        self.app_state.set_processing(
            False,
            100 if all_success else 0,
            "完成" if all_success else "部分失败",
        )

        # 优先用结构化 summary（包含 severity 与详细错误列表）
        summary = self._latest_summary
        if summary is None:
            # 兜底：旧路径
            (QMessageBox.information if all_success else QMessageBox.warning)(
                self, "完成" if all_success else "处理结果", message
            )
            return

        self._show_summary_dialog(summary)

    def _show_summary_dialog(self, summary: BatchSummary):
        """根据 summary.severity 选择 QMessageBox 类型并展示详情。"""
        sev_to_icon = {
            Severity.INFO: QMessageBox.Icon.Information,
            Severity.WARNING: QMessageBox.Icon.Warning,
            Severity.ERROR: QMessageBox.Icon.Critical,
            Severity.FATAL: QMessageBox.Icon.Critical,
        }
        sev_to_title = {
            Severity.INFO: "完成",
            Severity.WARNING: "完成（部分失败）",
            Severity.ERROR: "处理出错",
            Severity.FATAL: "严重错误",
        }
        box = QMessageBox(self)
        box.setIcon(sev_to_icon[summary.severity])
        box.setWindowTitle(sev_to_title[summary.severity])
        box.setText(summary.headline)
        # 详情：聚合前 N 条错误（避免对话框过长）
        if summary.errors:
            from collections import Counter
            kinds = Counter(e.title for e in summary.errors)
            kind_summary = "，".join(f"{title}×{count}" for title, count in kinds.most_common(5))
            sample_lines = []
            for pe in summary.errors[:5]:
                file_part = f"[{Path(pe.file_path).name}] " if pe.file_path else ""
                sample_lines.append(f"• {file_part}{pe.title}：{pe.detail}")
            if len(summary.errors) > 5:
                sample_lines.append(f"...（另 {len(summary.errors) - 5} 条）")
            box.setInformativeText(f"错误分类：{kind_summary}")
            box.setDetailedText("\n".join(sample_lines))
        box.exec()
    
    def _on_cancel(self):
        """取消处理（Phase 9：使用安全的 None 检查与生命周期协议）。"""
        thread = getattr(self, "_thread", None)
        if thread is not None and thread.isRunning():
            thread.cancel()
            thread.wait(3000)  # 等待最多 3 秒
            # 不在这里清 self._thread —— 由 finished → _on_process_thread_finished 统一清
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
        self.about_btn.setEnabled(not processing)
        self.thumb_container.setEnabled(not processing)
        self.config_drawer.setEnabled(not processing)
        self.preview_sidebar.setEnabled(not processing)
        self.preview_toggle_btn.setEnabled(not processing)
        self.output_input.setEnabled(not processing)
        self.override_check.setEnabled(not processing)
    
    def closeEvent(self, event):
        """退出时：取消运行中的所有后台线程 + 立即同步保存配置（取消未发的 debounce 计时）。

        Phase 9：统一在窗口关闭时回收 ProcessThread / PreviewRenderThread / ThumbLoaderThread，
        避免 Qt 抛 ``QThread: Destroyed while thread is still running`` 警告或 SIGABRT。
        """
        log = logging.getLogger(__name__)

        # 1) 处理线程（最重，先取消）
        thread = getattr(self, "_thread", None)
        if thread is not None and thread.isRunning():
            try:
                thread.cancel()
                thread.wait(3000)
            except Exception as e:
                log.warning(f"退出取消处理线程失败: {e}")

        # 2) 预览渲染线程
        try:
            preview_thread = getattr(self.preview_panel, "_thread", None)
            if preview_thread is not None and preview_thread.isRunning():
                preview_thread.cancel()
                preview_thread.wait(2000)
        except Exception as e:
            log.warning(f"退出取消预览线程失败: {e}")

        # 3) 缩略图加载线程
        try:
            loader = getattr(self.thumb_container, "loader_thread", None)
            if loader is not None and loader.isRunning():
                loader.cancel()
                loader.wait(2000)
        except Exception as e:
            log.warning(f"退出取消缩略图线程失败: {e}")

        # 4) 持久化
        try:
            self.app_state.flush_autosave()
        except Exception as e:
            log.warning(f"退出保存失败: {e}")
        event.accept()
