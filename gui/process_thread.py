"""处理线程 — 在后台运行图像处理管道。"""

from pathlib import Path
from typing import List, Dict, Any
import logging
import os

from PyQt6.QtCore import QThread, pyqtSignal

from core.template_builder import render_processors
from processor.core import start_process

import threading

logger = logging.getLogger(__name__)


class ProcessThread(QThread):
    """后台处理线程 — 逐文件执行 watermark pipeline。"""

    progress = pyqtSignal(int, str)          # 进度百分比, 状态文字
    file_done = pyqtSignal(str, bool, str)   # 文件路径, 是否成功, 消息
    finished_all = pyqtSignal(bool, str)     # 是否全部成功, 汇总消息

    def __init__(
        self,
        files: List[str],
        processors: List[Dict[str, Any]],
        output_pattern: str,
        override: bool,
        parent=None,
    ):
        super().__init__(parent)
        self.files = files
        self.processors = processors
        self.output_pattern = output_pattern
        self.override = override
        self._cancelled = threading.Event()

    def cancel(self):
        """请求取消（下个文件检查点会终止）。"""
        self._cancelled.set()

    def run(self):
        total = len(self.files)
        success_count = 0
        fail_count = 0

        for idx, file_path in enumerate(self.files):
            if self._cancelled.is_set():
                self.progress.emit(
                    int(idx / total * 100), "已取消"
                )
                break

            self.progress.emit(
                int(idx / total * 100),
                f"处理中 {idx + 1}/{total}...",
            )

            try:
                self._process_one(file_path)
                success_count += 1
                self.file_done.emit(file_path, True, "成功")
            except Exception as e:
                fail_count += 1
                logger.exception(f"处理失败: {file_path}")
                self.file_done.emit(file_path, False, str(e))

        self.progress.emit(100, "完成")

        if self._cancelled:
            self.finished_all.emit(False, f"已取消 — 成功 {success_count}，失败 {fail_count}")
        elif fail_count == 0:
            self.finished_all.emit(True, f"完成 — 处理了 {success_count} 张图片")
        else:
            self.finished_all.emit(
                False, f"完成 — 成功 {success_count}，失败 {fail_count}"
            )

    def _process_one(self, file_path: str):
        """处理单个文件。"""
        input_path = Path(file_path)

        # 解析输出路径
        output_path = self._resolve_output_path(input_path)

        # 检查覆盖
        if output_path.exists() and not self.override:
            raise FileExistsError(f"输出已存在: {output_path}")

        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 获取 EXIF 并渲染 processors
        from core.util import get_exif
        exif = get_exif(str(input_path))
        rendered = render_processors(self.processors, exif, str(input_path))

        # 执行处理
        start_process(rendered, input_path=str(input_path), output_path=str(output_path))

    def _resolve_output_path(self, input_path: Path) -> Path:
        """根据模式解析输出路径。"""
        source_dir = input_path.parent
        stem = input_path.stem

        pattern = self.output_pattern
        # 使用 str.format() 替代字符串替换，更规范且可扩展
        pattern = pattern.replace("{", "{{").replace("}", "}}")
        pattern = pattern.replace("{{source_dir}}", str(source_dir))
        pattern = pattern.replace("{{filename}}", stem)
        # 还原真实占位符
        pattern = pattern.replace("{{", "{").replace("}}", "}")
        
        try:
            pattern = pattern.format(source_dir=str(source_dir), filename=stem)
        except (KeyError, IndexError):
            pass  # 保留未知占位符原样

        # 如果以目录结尾（不含扩展名），追加 _logo.jpg
        if not Path(pattern).suffix:
            pattern = os.path.join(pattern, f"{stem}_logo.jpg")

        return Path(pattern)
