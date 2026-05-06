"""实时预览面板 — Phase 6.7。

职责：
- 选取当前 ``state.files`` 第一张图作为预览源
- 在后台线程渲染 watermark pipeline（避免阻塞 UI）
- debounce：水印/高级配置变化 → 500ms 后才触发渲染
- 渲染结果用 QPixmap 显示在缩略框中

设计要点：
- 与正式批处理共用 :func:`processor.core.start_process`，保证所见即所得
- 输出文件路径设为 ``None``，纯内存渲染
- 多次快速变化时只保留最后一次（debounce + 单线程互斥）
"""

from __future__ import annotations

import io
import logging
import traceback
from pathlib import Path
from typing import Any

from PIL import Image
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.template_builder import render_processors
from core.util import get_exif
from processor.core import start_process

from .models import AppState
from .template_assembler import state_to_processors

_log = logging.getLogger(__name__)


# ---- 工具：PIL → QPixmap ----------------------------------------------------

def _pil_to_qpixmap(img: Image.Image) -> QPixmap:
    """把 PIL Image 转 QPixmap（通过 PNG bytes，兼容性最好，避免 RGBA strides 坑）。"""
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qimg = QImage()
    qimg.loadFromData(buf.getvalue(), "PNG")
    return QPixmap.fromImage(qimg)


# ---- 渲染线程 ---------------------------------------------------------------

class PreviewRenderThread(QThread):
    """单图预览渲染 — 后台线程，结果通过信号送回 UI。"""

    preview_ready = pyqtSignal(QPixmap)
    preview_failed = pyqtSignal(str)  # 失败原因（用户友好的短消息）

    def __init__(
        self,
        file_path: str,
        processors_template: list[dict[str, Any]],
        max_size: int = 480,
        parent=None,
    ):
        super().__init__(parent)
        self.file_path = file_path
        self.processors_template = processors_template
        self.max_size = max_size
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        if self._cancelled:
            return
        try:
            # 1) 读 EXIF
            try:
                exif = get_exif(self.file_path)
            except Exception:
                exif = {}

            if self._cancelled:
                return

            # 2) 渲染 Jinja → 真实 processors
            rendered = render_processors(
                self.processors_template, exif, self.file_path
            )

            if self._cancelled:
                return

            # 3) 跑 pipeline（不写盘）
            img = start_process(
                data=rendered,
                input_path=self.file_path,
                output_path=None,
                pre_loaded_exif=exif if exif else None,
                emit_exif_json=False,
            )

            if self._cancelled or img is None:
                return

            # 4) 缩放到 max_size 内（保持比例）
            if img.width > self.max_size or img.height > self.max_size:
                img.thumbnail(
                    (self.max_size, self.max_size),
                    Image.Resampling.LANCZOS,
                )

            pix = _pil_to_qpixmap(img)
            if not self._cancelled:
                self.preview_ready.emit(pix)

        except Exception as e:
            _log.warning("preview render failed: %s\n%s", e, traceback.format_exc())
            if not self._cancelled:
                self.preview_failed.emit(str(e) or e.__class__.__name__)


# ---- 面板 -------------------------------------------------------------------

class PreviewPanel(QWidget):
    """实时预览面板 — 显示当前配置渲染后的第一张图。

    交互：
    - 文件列表变化 / 水印变化 / 高级变化 → 500ms debounce → 触发渲染
    - 渲染期间显示"渲染中…"，完成后显示缩略图，失败显示错误
    - "刷新" 按钮立即触发一次（绕过 debounce）
    """

    DEBOUNCE_MS = 500
    PREVIEW_MAX_SIZE = 480

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._thread: PreviewRenderThread | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._do_render)

        self._setup_ui()

        # 订阅状态变化
        state.files_changed.connect(self._schedule_render)
        state.watermark_changed.connect(self._schedule_render)
        state.advanced_changed.connect(self._schedule_render)
        # 模板切换 / 自定义文本 / logo 都已由 watermark_changed 涵盖

        # 首次进入：若已有文件则立即渲染
        if self.state.selected_files:
            self._schedule_render()
        else:
            self._set_status("（尚未选择图片）")

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 标题行
        header = QHBoxLayout()
        header.addWidget(QLabel("实时预览"))
        header.addStretch(1)
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setFixedWidth(60)
        self.refresh_btn.clicked.connect(self._do_render)
        header.addWidget(self.refresh_btn)
        layout.addLayout(header)

        # 缩略图区域（带边框）
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(240, 180)
        self.image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.image_label.setFrameShape(QFrame.Shape.Box)
        self.image_label.setStyleSheet(
            "QLabel { background-color: #1A1A1A; color: #888; border: 1px solid #333; }"
        )
        layout.addWidget(self.image_label, 1)

        # 状态行
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #999; font-size: 11px;")
        layout.addWidget(self.status_label)

    # ---- API ----

    def _schedule_render(self, *_args, **_kwargs) -> None:
        """请求一次渲染（debounce）。"""
        self._timer.start(self.DEBOUNCE_MS)

    def _do_render(self) -> None:
        """实际触发渲染（取消旧线程，开新线程）。"""
        if not self.state.selected_files:
            self._set_status("（尚未选择图片）")
            self.image_label.clear()
            self.image_label.setText("（无预览）")
            return

        # 取消正在运行的旧线程
        # 注：self._thread 仅在 _on_thread_finished 中清空，所以此处非 None
        # 即代表线程仍在运行（或刚发完 finished 还没来得及处理槽，此时 quit 也安全）
        if self._thread is not None:
            self._thread.cancel()
            self._thread.quit()
            # 不等待 — 让 Qt 自然回收
            # 立即清空引用：旧线程从此与本面板"脱钩"，由 deleteLater 自行释放 C++
            self._thread = None

        # 准备 processors（在 UI 线程做 — 必须读 state）
        try:
            processors = state_to_processors(self.state)
        except Exception as e:
            self._set_status(f"配置组装失败: {e}")
            return

        first_file = self.state.selected_files[0]
        if not Path(first_file).exists():
            self._set_status(f"文件不存在: {first_file}")
            return

        self._set_status("渲染中…")

        thread = PreviewRenderThread(
            file_path=first_file,
            processors_template=processors,
            max_size=self.PREVIEW_MAX_SIZE,
            parent=self,
        )
        thread.preview_ready.connect(self._on_preview_ready)
        thread.preview_failed.connect(self._on_preview_failed)
        # 生命周期在源头解耦：线程结束 → 清空 Python 引用 → 让 Qt 释放 C++ 对象
        thread.finished.connect(self._on_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        thread.start()

    def _on_thread_finished(self) -> None:
        """线程结束信号槽：清空 Python 引用，避免持有已被 deleteLater 销毁的 wrapper。

        只有当 sender 是当前 self._thread 时才清空 —— 防止"旧线程比新线程晚发 finished"
        这种竞争把刚创建的 self._thread 误清掉。
        """
        sender = self.sender()
        if sender is self._thread:
            self._thread = None

    def _on_preview_ready(self, pixmap: QPixmap) -> None:
        # 缩放到 label 大小（保持比例）
        scaled = pixmap.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        self._original_pix = pixmap  # 保留原图用于 resize
        self._set_status(f"已渲染 · {pixmap.width()}×{pixmap.height()}")

    def _on_preview_failed(self, reason: str) -> None:
        self.image_label.clear()
        self.image_label.setText("（渲染失败）")
        self._set_status(f"⚠ {reason}")

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 重新缩放保留的原图
        pix = getattr(self, "_original_pix", None)
        if pix is not None and not pix.isNull():
            scaled = pix.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled)
