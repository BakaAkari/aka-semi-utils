"""Phase 4 — :mod:`processor.batch` 错误分类辅助函数单元测试。

覆盖：
- :func:`_classify_error` 区分 ProcessorError / ResourceError / ConfigError / 未知；
- :func:`_to_safe` 对 pickle-safe 转换的处理（基础类型保留，其他 ``str(v)``）。
"""

from __future__ import annotations

import pytest

from core.exceptions import (
    ConfigKeyError,
    ConfigValueError,
    ExifToolError,
    ProcessorNotFoundError,
    ProcessorRuntimeError,
    ResourceNotFoundError,
)
from processor.batch import _classify_error, _to_safe


class TestClassifyError:
    def test_processor_not_found(self):
        e = ProcessorNotFoundError(key="fancy")
        kind, cls_name, ctx = _classify_error(e)
        assert kind == "processor"
        assert cls_name == "ProcessorNotFoundError"
        assert ctx.get("key") == "fancy"

    def test_processor_runtime_error(self):
        original = ValueError("boom")
        e = ProcessorRuntimeError(processor_name="watermark", original=original)
        kind, cls_name, ctx = _classify_error(e)
        assert kind == "processor"
        assert cls_name == "ProcessorRuntimeError"
        assert ctx.get("processor_name") == "watermark"
        # context 只保留原始异常**类名**（非实例，pickle-safe）
        assert ctx.get("original_type") == "ValueError"

    def test_resource_not_found(self):
        e = ResourceNotFoundError(path="/x.png", kind="logo")
        kind, cls_name, ctx = _classify_error(e)
        assert kind == "resource"
        assert cls_name == "ResourceNotFoundError"
        assert ctx.get("path") == "/x.png"
        assert ctx.get("kind") == "logo"

    def test_exiftool_error(self):
        e = ExifToolError("invocation failed", returncode=2, stderr="oops")
        kind, cls_name, ctx = _classify_error(e)
        assert kind == "resource"
        assert cls_name == "ExifToolError"
        assert ctx.get("returncode") == 2
        assert ctx.get("stderr") == "oops"

    def test_config_key_error(self):
        e = ConfigKeyError(key="a.b", source="user.json")
        kind, cls_name, ctx = _classify_error(e)
        assert kind == "config"
        assert cls_name == "ConfigKeyError"
        assert ctx.get("key") == "a.b"
        assert ctx.get("source") == "user.json"

    def test_config_value_error(self):
        e = ConfigValueError(key="opacity", value=200, expected="0..100")
        kind, cls_name, _ctx = _classify_error(e)
        assert kind == "config"
        assert cls_name == "ConfigValueError"

    def test_unknown_exception(self):
        e = ZeroDivisionError("bad")
        kind, cls_name, ctx = _classify_error(e)
        assert kind == "unknown"
        assert cls_name == "ZeroDivisionError"
        assert ctx == {}


class TestToSafe:
    @pytest.mark.parametrize(
        "v",
        [None, True, 0, 1, -1, 3.14, "hello", ""],
    )
    def test_passthrough_basic(self, v):
        assert _to_safe(v) == v

    def test_list(self):
        assert _to_safe([1, "a", None]) == [1, "a", None]

    def test_tuple_becomes_list(self):
        assert _to_safe((1, 2, 3)) == [1, 2, 3]

    def test_dict(self):
        assert _to_safe({"k": 1, "x": [1, 2]}) == {"k": 1, "x": [1, 2]}

    def test_dict_non_str_key_stringified(self):
        out = _to_safe({1: "a"})
        assert out == {"1": "a"}

    def test_exception_becomes_str(self):
        e = RuntimeError("boom")
        out = _to_safe(e)
        assert isinstance(out, str)
        assert "boom" in out

    def test_custom_object_becomes_str(self):
        class Foo:
            def __str__(self):
                return "foo-instance"

        assert _to_safe(Foo()) == "foo-instance"

    def test_pickle_safe_round_trip(self):
        """`_to_safe` 处理后的结果必须能 pickle，以便跨进程返回。"""
        import pickle

        data = {
            "exc": _to_safe(RuntimeError("x")),
            "nums": _to_safe([1, 2, 3]),
            "nested": _to_safe({"inner": [RuntimeError("y")]}),
        }
        # 不抛异常即测试通过
        roundtrip = pickle.loads(pickle.dumps(data))
        assert isinstance(roundtrip["exc"], str)
        assert roundtrip["nums"] == [1, 2, 3]
