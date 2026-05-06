"""错误展示层 — Phase 4。

把 :class:`processor.batch.BatchResultItem` 中的结构化错误转换为**用户友好**的
分级提示（severity / 标题 / 详情）。

设计要点：
- **纯逻辑层**：不依赖 PyQt，便于单元测试与替代展示后端（CLI / Web）；
- **i18n-ready**：所有面向用户的字符串集中在 :data:`MESSAGES` 表，便于翻译；
- **聚合**：批处理后端 fan-out 多个 :class:`BatchResultItem`，前端 fan-in
  到一条总结消息（最严重错误 + 计数 + 首例样本）。

严重度映射（高 → 低）：
    fatal   — 配置错误（用户必须修配置才能继续，整批不可恢复）
    error   — 资源错误（缺失字体 / logo / 损坏文件，单文件不可恢复）
    warning — 处理器运行错误（具体某个 processor 跑炸但配置/资源都对）
    info    — 跳过 / 取消等正常状态
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    """UI 层分级 — 字符串 enum 便于直接映射到 QMessageBox.Icon / CSS class。"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


# 错误类别（与 BatchResultItem.error_kind 对齐）→ 严重度
KIND_TO_SEVERITY: dict[str, Severity] = {
    "config": Severity.FATAL,
    "resource": Severity.ERROR,
    "processor": Severity.WARNING,
    "unknown": Severity.WARNING,
}


# 用户友好消息模板（i18n key）
# 占位符遵循 str.format 规范，``context`` 字段名直接出现在花括号里
MESSAGES: dict[str, dict[str, str]] = {
    # --- ProcessorError 子类 ---
    "ProcessorNotFoundError": {
        "title": "未找到处理器",
        "tip": "处理器 '{key}' 未在注册表中找到，请检查模板配置。",
    },
    "ProcessorRuntimeError": {
        "title": "处理器执行失败",
        "tip": "处理器 '{processor_name}' 运行出错（{original_type}）。",
    },
    # --- ResourceError 子类 ---
    "ResourceNotFoundError": {
        "title": "资源缺失",
        "tip": "找不到资源文件 '{path}'（类型：{kind}）。请检查路径是否正确。",
    },
    "ExifToolError": {
        "title": "EXIF 工具异常",
        "tip": "调用 exiftool 失败（返回码 {returncode}）：{stderr}",
    },
    # --- ConfigError 子类 ---
    "ConfigKeyError": {
        "title": "配置键缺失",
        "tip": "缺少配置项 '{key}'（来源：{source}）。",
    },
    "ConfigValueError": {
        "title": "配置值无效",
        "tip": "配置 '{key}' 的值 '{value}' 不合法，期望：{expected}。",
    },
    # --- fallback ---
    "_unknown_": {
        "title": "处理失败",
        "tip": "{message}",
    },
}


@dataclass
class PresentedError:
    """单条已格式化的错误（UI 层直接消费）。"""

    severity: Severity
    title: str
    detail: str
    file_path: str | None = None
    raw_class: str | None = None
    raw_context: dict = field(default_factory=dict)


def present_one(
    *,
    error_kind: str | None,
    error_class: str | None,
    error_context: dict[str, Any] | None,
    error_message: str | None,
    file_path: str | None = None,
) -> PresentedError:
    """把 BatchResultItem 字段格式化为 :class:`PresentedError`。

    可单独调用（测试用），无需构造 BatchResultItem。
    """
    severity = KIND_TO_SEVERITY.get(error_kind or "unknown", Severity.WARNING)
    template = MESSAGES.get(error_class or "", MESSAGES["_unknown_"])
    title = template["title"]
    ctx = dict(error_context or {})
    # 兜底字段，模板里 {message} 占位时使用
    ctx.setdefault("message", error_message or "（无详情）")
    try:
        detail = template["tip"].format(**ctx)
    except KeyError:
        # context 字段不齐 — 退回原始 message
        detail = error_message or "（无详情）"
    return PresentedError(
        severity=severity,
        title=title,
        detail=detail,
        file_path=file_path,
        raw_class=error_class,
        raw_context=dict(error_context or {}),
    )


def present_item(item) -> PresentedError | None:
    """从 :class:`BatchResultItem` 提取并格式化错误。成功项返回 ``None``。"""
    if getattr(item, "success", False):
        return None
    return present_one(
        error_kind=getattr(item, "error_kind", None),
        error_class=getattr(item, "error_class", None),
        error_context=getattr(item, "error_context", {}),
        error_message=getattr(item, "error", None),
        file_path=getattr(item, "input_path", None),
    )


@dataclass
class BatchSummary:
    """整批结果的汇总（用于"全部完成"对话框）。"""

    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    cancelled: bool = False
    # 已格式化的错误列表（按出现顺序）
    errors: list[PresentedError] = field(default_factory=list)

    @property
    def severity(self) -> Severity:
        """整批的最高严重度 — 用于状态栏图标 / 弹窗类型选择。"""
        if not self.errors:
            return Severity.INFO
        order = [Severity.INFO, Severity.WARNING, Severity.ERROR, Severity.FATAL]
        return max(self.errors, key=lambda e: order.index(e.severity)).severity

    @property
    def headline(self) -> str:
        """单行总结文案（状态栏使用）。"""
        if self.cancelled:
            return f"已取消 — 成功 {self.success}，失败 {self.failed}，跳过 {self.skipped}"
        parts = [f"成功 {self.success}"]
        if self.failed:
            parts.append(f"失败 {self.failed}")
        if self.skipped:
            parts.append(f"跳过 {self.skipped}")
        return "完成 — " + "，".join(parts)

    @property
    def is_all_success(self) -> bool:
        return self.failed == 0 and self.skipped == 0 and not self.cancelled


def summarize(
    items: list,
    *,
    skipped_count: int = 0,
    cancelled: bool = False,
) -> BatchSummary:
    """聚合一批 :class:`BatchResultItem` 为 :class:`BatchSummary`。"""
    total = len(items)
    success = sum(1 for it in items if getattr(it, "success", False))
    failed = total - success
    errors: list[PresentedError] = []
    for it in items:
        pe = present_item(it)
        if pe is not None:
            errors.append(pe)
    return BatchSummary(
        total=total + skipped_count,
        success=success,
        failed=failed,
        skipped=skipped_count,
        cancelled=cancelled,
        errors=errors,
    )


__all__ = [
    "KIND_TO_SEVERITY",
    "MESSAGES",
    "BatchSummary",
    "PresentedError",
    "Severity",
    "present_item",
    "present_one",
    "summarize",
]
