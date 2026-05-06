"""Phase 3.1 — 自定义异常体系单元测试。"""

from __future__ import annotations

import pytest

from core.exceptions import (
    AkaSemiUtilsError,
    ConfigError,
    ConfigKeyError,
    ConfigValueError,
    ExifToolError,
    ProcessorError,
    ProcessorNotFoundError,
    ProcessorRuntimeError,
    ResourceError,
    ResourceNotFoundError,
)


# ---------------------------------------------------------------- 继承层级
class TestExceptionHierarchy:
    """所有自定义异常都应根植于 ``AkaSemiUtilsError`` 与 ``Exception``。"""

    @pytest.mark.parametrize("exc_cls", [
        ConfigError, ConfigKeyError, ConfigValueError,
        ResourceError, ResourceNotFoundError, ExifToolError,
        ProcessorError, ProcessorNotFoundError, ProcessorRuntimeError,
    ])
    def test_inherits_from_root(self, exc_cls):
        assert issubclass(exc_cls, AkaSemiUtilsError)
        assert issubclass(exc_cls, Exception)

    def test_config_subclasses(self):
        assert issubclass(ConfigKeyError, ConfigError)
        assert issubclass(ConfigValueError, ConfigError)

    def test_resource_subclasses(self):
        assert issubclass(ResourceNotFoundError, ResourceError)
        assert issubclass(ExifToolError, ResourceError)

    def test_processor_subclasses(self):
        assert issubclass(ProcessorNotFoundError, ProcessorError)
        assert issubclass(ProcessorRuntimeError, ProcessorError)


# ---------------------------------------------------------------- 字段语义
class TestExceptionFields:
    def test_root_message_and_context(self):
        exc = AkaSemiUtilsError("boom", {"a": 1})
        assert exc.message == "boom"
        assert exc.context == {"a": 1}
        assert "boom" in str(exc)
        assert "a=1" in str(exc)

    def test_root_no_context(self):
        exc = AkaSemiUtilsError("just message")
        assert str(exc) == "just message"
        assert exc.context == {}

    def test_config_key_error(self):
        exc = ConfigKeyError("watermark", source="user.json")
        assert exc.key == "watermark"
        assert exc.source == "user.json"
        assert "watermark" in str(exc)

    def test_config_value_error(self):
        exc = ConfigValueError("ratio", "abc", "float")
        assert exc.key == "ratio"
        assert exc.value == "abc"
        assert exc.expected == "float"

    def test_resource_not_found(self):
        exc = ResourceNotFoundError("/no/such.png", kind="logo")
        assert exc.path == "/no/such.png"
        assert exc.kind == "logo"
        assert "logo" in str(exc) and "/no/such.png" in str(exc)

    def test_exiftool_error(self):
        exc = ExifToolError("subprocess died", returncode=127, stderr="not found")
        assert exc.returncode == 127
        assert exc.stderr == "not found"

    def test_processor_not_found(self):
        exc = ProcessorNotFoundError("nonexistent")
        assert exc.key == "nonexistent"
        assert "nonexistent" in str(exc)

    def test_processor_runtime_error_chains_original(self):
        original = ValueError("inner")
        exc = ProcessorRuntimeError("blur", original)
        assert exc.processor_name == "blur"
        assert exc.original is original
        assert "blur" in str(exc)


# ----------------------------------------------------- 兼容 except 块捕获
class TestExceptionCatchability:
    def test_can_catch_via_root(self):
        with pytest.raises(AkaSemiUtilsError):
            raise ProcessorNotFoundError("foo")

    def test_can_catch_via_category(self):
        with pytest.raises(ResourceError):
            raise ResourceNotFoundError("/x")

    def test_can_catch_via_exception(self):
        # 项目根仍是内置 Exception 子类，旧代码 try/except Exception 仍能兜底
        # 用 AkaSemiUtilsError 而非 blind Exception（满足 ruff B017）
        from core.exceptions import AkaSemiUtilsError
        with pytest.raises(AkaSemiUtilsError):
            raise ConfigKeyError("k")
