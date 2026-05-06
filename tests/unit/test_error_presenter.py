"""Phase 4.6 — 错误展示层（gui.error_presenter）单元测试。

纯逻辑层，不需要 PyQt / 显示器。覆盖：
- :class:`Severity` 枚举语义；
- :data:`KIND_TO_SEVERITY` 映射；
- :func:`present_one` 对各异常类的格式化（成功/缺字段/未知类）；
- :func:`present_item` 从 BatchResultItem-like 对象提取；
- :func:`summarize` 聚合（空/全成功/混合/全失败/取消/跳过）；
- :class:`BatchSummary` 的 ``severity`` / ``headline`` / ``is_all_success``。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from gui.error_presenter import (
    KIND_TO_SEVERITY,
    MESSAGES,
    BatchSummary,
    PresentedError,
    Severity,
    present_item,
    present_one,
    summarize,
)


# ---------------------------------------------------------------------------
# 测试辅助：构造一个鸭子类型的 BatchResultItem-like 对象
# ---------------------------------------------------------------------------
@dataclass
class _FakeItem:
    input_path: str = "/tmp/in.jpg"
    output_path: str = "/tmp/out.jpg"
    success: bool = True
    error: str | None = None
    error_kind: str | None = None
    error_class: str | None = None
    error_context: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Severity / KIND_TO_SEVERITY
# ---------------------------------------------------------------------------
class TestSeverityEnum:
    def test_values_are_lowercase_strings(self):
        assert Severity.INFO.value == "info"
        assert Severity.WARNING.value == "warning"
        assert Severity.ERROR.value == "error"
        assert Severity.FATAL.value == "fatal"

    def test_str_enum_can_compare_to_string(self):
        assert Severity.FATAL == "fatal"

    def test_kind_to_severity_complete(self):
        # 这四个 kind 必须全部映射，否则 present_one 会走默认 WARNING 兜底
        assert KIND_TO_SEVERITY["config"] == Severity.FATAL
        assert KIND_TO_SEVERITY["resource"] == Severity.ERROR
        assert KIND_TO_SEVERITY["processor"] == Severity.WARNING
        assert KIND_TO_SEVERITY["unknown"] == Severity.WARNING


# ---------------------------------------------------------------------------
# present_one — 各异常类
# ---------------------------------------------------------------------------
class TestPresentOneByExceptionClass:
    def test_processor_not_found(self):
        pe = present_one(
            error_kind="processor",
            error_class="ProcessorNotFoundError",
            error_context={"key": "fancy_filter"},
            error_message="processor 'fancy_filter' not registered",
        )
        assert pe.severity == Severity.WARNING
        assert pe.title == "未找到处理器"
        assert "fancy_filter" in pe.detail
        assert pe.raw_class == "ProcessorNotFoundError"
        assert pe.raw_context == {"key": "fancy_filter"}

    def test_processor_runtime_error(self):
        pe = present_one(
            error_kind="processor",
            error_class="ProcessorRuntimeError",
            error_context={"processor_name": "watermark", "original_type": "ValueError"},
            error_message="watermark crashed",
        )
        assert pe.severity == Severity.WARNING
        assert pe.title == "处理器执行失败"
        assert "watermark" in pe.detail
        assert "ValueError" in pe.detail

    def test_resource_not_found(self):
        pe = present_one(
            error_kind="resource",
            error_class="ResourceNotFoundError",
            error_context={"path": "/no/such.png", "kind": "logo"},
            error_message="logo missing",
        )
        assert pe.severity == Severity.ERROR
        assert pe.title == "资源缺失"
        assert "/no/such.png" in pe.detail
        assert "logo" in pe.detail

    def test_exiftool_error(self):
        pe = present_one(
            error_kind="resource",
            error_class="ExifToolError",
            error_context={"returncode": 1, "stderr": "nope"},
            error_message="exiftool failed",
        )
        assert pe.severity == Severity.ERROR
        assert pe.title == "EXIF 工具异常"
        assert "1" in pe.detail
        assert "nope" in pe.detail

    def test_config_key_error(self):
        pe = present_one(
            error_kind="config",
            error_class="ConfigKeyError",
            error_context={"key": "watermark.font", "source": "user.json"},
            error_message="missing key",
        )
        assert pe.severity == Severity.FATAL
        assert pe.title == "配置键缺失"
        assert "watermark.font" in pe.detail

    def test_config_value_error(self):
        pe = present_one(
            error_kind="config",
            error_class="ConfigValueError",
            error_context={
                "key": "watermark.opacity",
                "value": "200",
                "expected": "0..100",
            },
            error_message="bad value",
        )
        assert pe.severity == Severity.FATAL
        assert pe.title == "配置值无效"
        assert "200" in pe.detail
        assert "0..100" in pe.detail


class TestPresentOneFallback:
    def test_unknown_class_uses_message(self):
        pe = present_one(
            error_kind="unknown",
            error_class="ZeroDivisionError",
            error_context={},
            error_message="division by zero",
        )
        assert pe.severity == Severity.WARNING
        assert pe.title == MESSAGES["_unknown_"]["title"]
        assert "division by zero" in pe.detail

    def test_missing_context_field_falls_back_to_message(self):
        # ProcessorRuntimeError 模板需要 {processor_name} 和 {original_type}，但 context 缺失
        pe = present_one(
            error_kind="processor",
            error_class="ProcessorRuntimeError",
            error_context={},  # ← 缺字段
            error_message="raw fallback message",
        )
        assert pe.severity == Severity.WARNING
        # 缺字段时 detail 退回原始 message
        assert pe.detail == "raw fallback message"

    def test_no_message_no_context_yields_placeholder(self):
        pe = present_one(
            error_kind=None,
            error_class=None,
            error_context=None,
            error_message=None,
        )
        # severity 走 unknown → WARNING
        assert pe.severity == Severity.WARNING
        # detail 应是占位符，不抛异常
        assert pe.detail
        assert pe.title == MESSAGES["_unknown_"]["title"]

    def test_unknown_kind_defaults_to_warning(self):
        pe = present_one(
            error_kind="totally-bogus-kind",
            error_class="WhateverError",
            error_context={},
            error_message="x",
        )
        assert pe.severity == Severity.WARNING


class TestPresentOneFilePath:
    def test_file_path_passthrough(self):
        pe = present_one(
            error_kind="processor",
            error_class="ProcessorNotFoundError",
            error_context={"key": "x"},
            error_message="x",
            file_path="/data/photo.jpg",
        )
        assert pe.file_path == "/data/photo.jpg"


# ---------------------------------------------------------------------------
# present_item
# ---------------------------------------------------------------------------
class TestPresentItem:
    def test_success_returns_none(self):
        item = _FakeItem(success=True)
        assert present_item(item) is None

    def test_failure_returns_presented_error(self):
        item = _FakeItem(
            success=False,
            error="oops",
            error_kind="processor",
            error_class="ProcessorNotFoundError",
            error_context={"key": "k"},
            input_path="/in/a.jpg",
        )
        pe = present_item(item)
        assert pe is not None
        assert pe.severity == Severity.WARNING
        assert pe.file_path == "/in/a.jpg"
        assert pe.raw_class == "ProcessorNotFoundError"

    def test_failure_without_structured_fields(self):
        # 老格式（pre-Phase4）— 只有 error 字符串
        item = _FakeItem(
            success=False,
            error="legacy error string",
            error_kind=None,
            error_class=None,
            error_context={},
        )
        pe = present_item(item)
        assert pe is not None
        # 走 fallback：severity=WARNING（unknown），detail 含原始消息
        assert pe.severity == Severity.WARNING
        assert "legacy error string" in pe.detail


# ---------------------------------------------------------------------------
# summarize / BatchSummary
# ---------------------------------------------------------------------------
class TestSummarizeEmpty:
    def test_empty_list(self):
        s = summarize([])
        assert s.total == 0
        assert s.success == 0
        assert s.failed == 0
        assert s.skipped == 0
        assert s.errors == []
        assert s.severity == Severity.INFO
        assert s.is_all_success is True

    def test_empty_with_skipped(self):
        s = summarize([], skipped_count=3)
        assert s.total == 3
        assert s.skipped == 3
        assert s.is_all_success is False  # 跳过算非全成功


class TestSummarizeAllSuccess:
    def test_all_success(self):
        items = [_FakeItem(success=True), _FakeItem(success=True)]
        s = summarize(items)
        assert s.total == 2
        assert s.success == 2
        assert s.failed == 0
        assert s.errors == []
        assert s.severity == Severity.INFO
        assert s.is_all_success is True
        assert s.headline.startswith("完成")
        assert "成功 2" in s.headline


class TestSummarizeMixed:
    def test_mixed_success_and_failure(self):
        items = [
            _FakeItem(success=True),
            _FakeItem(
                success=False,
                error_kind="processor",
                error_class="ProcessorRuntimeError",
                error_context={"processor_name": "p", "original_type": "ValueError"},
                error="x",
            ),
            _FakeItem(success=True),
        ]
        s = summarize(items)
        assert s.total == 3
        assert s.success == 2
        assert s.failed == 1
        assert len(s.errors) == 1
        assert s.severity == Severity.WARNING
        assert s.is_all_success is False
        assert "失败 1" in s.headline


class TestSummarizeSeverityEscalation:
    def test_picks_highest_severity(self):
        # 一个 warning + 一个 error + 一个 fatal → 整体 fatal
        items = [
            _FakeItem(
                success=False,
                error_kind="processor",
                error_class="ProcessorNotFoundError",
                error_context={"key": "x"},
            ),
            _FakeItem(
                success=False,
                error_kind="resource",
                error_class="ResourceNotFoundError",
                error_context={"path": "/x", "kind": "logo"},
            ),
            _FakeItem(
                success=False,
                error_kind="config",
                error_class="ConfigKeyError",
                error_context={"key": "k", "source": "s"},
            ),
        ]
        s = summarize(items)
        assert s.severity == Severity.FATAL

    def test_only_warnings(self):
        items = [
            _FakeItem(
                success=False,
                error_kind="processor",
                error_class="ProcessorNotFoundError",
                error_context={"key": "x"},
            )
        ]
        s = summarize(items)
        assert s.severity == Severity.WARNING


class TestSummarizeCancelled:
    def test_cancelled_headline(self):
        items = [_FakeItem(success=True)]
        s = summarize(items, cancelled=True)
        assert s.cancelled is True
        assert s.is_all_success is False
        assert "已取消" in s.headline


class TestBatchSummaryProperties:
    def test_severity_no_errors_is_info(self):
        s = BatchSummary(total=0, success=0, failed=0)
        assert s.severity == Severity.INFO

    def test_is_all_success_strict(self):
        # failed=0, skipped=0, cancelled=False → True
        assert BatchSummary(total=1, success=1).is_all_success is True
        # 任一非零都会 False
        assert BatchSummary(total=1, success=0, failed=1).is_all_success is False
        assert BatchSummary(total=1, success=1, skipped=1).is_all_success is False
        assert BatchSummary(total=1, success=1, cancelled=True).is_all_success is False

    def test_headline_with_skipped(self):
        s = BatchSummary(total=3, success=2, failed=0, skipped=1)
        assert "跳过 1" in s.headline


# ---------------------------------------------------------------------------
# 模板完整性兜底
# ---------------------------------------------------------------------------
class TestMessagesTableIntegrity:
    @pytest.mark.parametrize(
        "key",
        [
            "ProcessorNotFoundError",
            "ProcessorRuntimeError",
            "ResourceNotFoundError",
            "ExifToolError",
            "ConfigKeyError",
            "ConfigValueError",
            "_unknown_",
        ],
    )
    def test_template_has_title_and_tip(self, key):
        assert key in MESSAGES
        assert "title" in MESSAGES[key]
        assert "tip" in MESSAGES[key]
        assert MESSAGES[key]["title"]
        assert MESSAGES[key]["tip"]


class TestPresentedErrorDataclass:
    def test_construct_with_defaults(self):
        pe = PresentedError(severity=Severity.INFO, title="t", detail="d")
        assert pe.file_path is None
        assert pe.raw_class is None
        assert pe.raw_context == {}
