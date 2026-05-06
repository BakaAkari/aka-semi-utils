"""JSON 模板双向同步编辑器 — Phase 6.8。

提供一个 :class:`JsonEditorPanel`，让高级用户直接编辑 processors JSON：

- "从 GUI 同步" → 把当前 :class:`AppState` 序列化为 JSON 显示
- "应用到 GUI" → 解析编辑器内容并通过 :func:`processors_to_state` 回写
- 实时校验：每次编辑后立刻试 ``json.loads``，错误内联高亮
- 状态变化时若用户没改过 JSON，会自动同步（避免显示陈旧内容）

设计要点：
- 保留用户脏标记 ``_user_dirty``，仅当 JSON 等于"上次同步内容"时
  才允许 state 信号自动覆盖；否则提示用户先确认
- 校验只检查 JSON 语法 + 顶层是 list；语义校验交给
  :func:`processors_to_state` 在"应用"时进行
"""

from __future__ import annotations

import json
import logging

from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .models import AppState
from .template_assembler import processors_to_state, state_to_processors

_log = logging.getLogger(__name__)


class JsonEditorPanel(QWidget):
    """processors JSON 双向编辑器。"""

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._user_dirty: bool = False  # 用户是否已编辑（未应用）
        self._suppress_text_change: bool = False
        self._last_synced_text: str = ""  # 最后一次"从 GUI 同步"的内容

        self._setup_ui()

        # 首次同步
        self._sync_from_state()

        # 状态变化 → 若未脏，自动同步
        state.watermark_changed.connect(self._auto_resync)
        state.advanced_changed.connect(self._auto_resync)

    # ---- UI ----

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 标题 + 说明
        layout.addWidget(QLabel("Processors JSON（高级用户）"))
        hint = QLabel(
            "直接编辑底层 processors 列表，点击\"应用到 GUI\"使其生效。\n"
            "GUI 配置变化时若未编辑，将自动同步。"
        )
        hint.setStyleSheet("color: #888; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # 编辑器
        self.editor = QPlainTextEdit()
        font = QFont("Menlo, Monaco, Consolas, monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(11)
        self.editor.setFont(font)
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.editor.setTabStopDistance(28)
        self.editor.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.editor, 1)

        # 状态行
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #999; font-size: 11px;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self.sync_btn = QPushButton("从 GUI 同步")
        self.sync_btn.clicked.connect(self._on_sync_clicked)
        btn_row.addWidget(self.sync_btn)

        self.apply_btn = QPushButton("应用到 GUI")
        self.apply_btn.setObjectName("primary")
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        btn_row.addWidget(self.apply_btn)

        self.format_btn = QPushButton("格式化")
        self.format_btn.clicked.connect(self._on_format_clicked)
        btn_row.addWidget(self.format_btn)

        btn_row.addStretch(1)
        layout.addLayout(btn_row)

    # ---- 同步 ↔ 应用 ----

    def _sync_from_state(self) -> None:
        try:
            processors = state_to_processors(self.state)
            text = json.dumps(processors, indent=2, ensure_ascii=False)
        except Exception as e:
            _log.warning("state_to_processors failed: %s", e)
            self._set_status(f"⚠ 序列化失败：{e}", error=True)
            return

        self._suppress_text_change = True
        try:
            self.editor.setPlainText(text)
        finally:
            self._suppress_text_change = False
        self._last_synced_text = text
        self._user_dirty = False
        self._set_status("已从 GUI 同步")

    def _auto_resync(self, *_args, **_kwargs) -> None:
        """state 变化时自动同步 — 仅在用户未编辑时执行。"""
        if self._user_dirty:
            self._set_status(
                "⚠ GUI 已变化但 JSON 编辑器有未应用的修改，请手动同步或应用",
                error=True,
            )
            return
        self._sync_from_state()

    def _on_sync_clicked(self) -> None:
        if self._user_dirty:
            ret = QMessageBox.question(
                self,
                "确认覆盖",
                "JSON 编辑器有未应用的修改，是否丢弃并从 GUI 重新同步？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ret != QMessageBox.StandardButton.Yes:
                return
        self._sync_from_state()

    def _on_apply_clicked(self) -> None:
        text = self.editor.toPlainText()
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            self._set_status(f"⚠ JSON 解析错误（行 {e.lineno}, 列 {e.colno}）：{e.msg}", error=True)
            self._highlight_error(e.lineno)
            return

        if not isinstance(data, list):
            self._set_status("⚠ 顶层必须是数组（list）", error=True)
            return

        try:
            processors_to_state(data, self.state)
        except Exception as e:
            _log.warning("processors_to_state failed: %s", e)
            self._set_status(f"⚠ 应用失败：{e}", error=True)
            return

        # 应用成功 — state 信号会触发 _auto_resync，但我们不希望它"覆盖"用户内容；
        # 通过提前清脏标记 + 更新 last_synced_text 实现"幂等"
        self._last_synced_text = text
        self._user_dirty = False
        self._set_status(f"✓ 已应用 {len(data)} 个 processor 到 GUI")

    def _on_format_clicked(self) -> None:
        text = self.editor.toPlainText()
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            self._set_status(f"⚠ 无法格式化：{e.msg}", error=True)
            return
        formatted = json.dumps(data, indent=2, ensure_ascii=False)
        if formatted == text:
            self._set_status("（已是规范格式）")
            return
        self.editor.setPlainText(formatted)
        self._set_status("已格式化")

    # ---- 内部 ----

    def _on_text_changed(self) -> None:
        if self._suppress_text_change:
            return
        text = self.editor.toPlainText()
        self._user_dirty = text != self._last_synced_text

        # 实时语法校验（不弹窗，仅状态行提示）
        if not text.strip():
            self._set_status("（编辑器为空）")
            return
        try:
            data = json.loads(text)
            if not isinstance(data, list):
                self._set_status("⚠ 顶层必须是数组", error=True)
            else:
                self._set_status(
                    f"已编辑 · {len(data)} 个 processor · 点击\"应用到 GUI\"生效"
                )
        except json.JSONDecodeError as e:
            self._set_status(
                f"⚠ JSON 错误（行 {e.lineno}, 列 {e.colno}）：{e.msg}",
                error=True,
            )

    def _set_status(self, text: str, error: bool = False) -> None:
        self.status_label.setText(text)
        if error:
            self.status_label.setStyleSheet("color: #EF4444; font-size: 11px;")
        else:
            self.status_label.setStyleSheet("color: #999; font-size: 11px;")

    def _highlight_error(self, lineno: int) -> None:
        """把光标移到出错行（让用户立即看到位置）。"""
        try:
            doc = self.editor.document()
            block = doc.findBlockByLineNumber(max(0, lineno - 1))
            if not block.isValid():
                return
            cursor = QTextCursor(block)
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
            self.editor.setTextCursor(cursor)
            self.editor.ensureCursorVisible()
        except Exception:
            pass
