"""Phase 3.1 — PipelineEngine 异常包装行为测试。"""

from __future__ import annotations

import pytest
from PIL import Image

import processor  # noqa: F401  触发处理器自动注册
from core.exceptions import (
    ProcessorError,
    ProcessorNotFoundError,
    ProcessorRuntimeError,
)
from processor.core import (
    PipelineContext,
    PipelineEngine,
    register,
)
from processor.filters import FilterProcessor


@register("test_failing_for_pe")
class _FailingFilter(FilterProcessor):
    """专用于测试的处理器，process() 一进来就抛 ValueError。"""

    def process(self, ctx: PipelineContext):
        raise ValueError("intentional test failure")


class TestProcessorNotFound:
    """PipelineEngine.run() 遇到注册表查不到的 key 时应抛 ProcessorNotFoundError。"""

    def test_unknown_processor_raises_not_found(self, tmp_path):
        # 准备一张测试图
        img_path = tmp_path / "in.png"
        Image.new("RGB", (10, 10), "white").save(img_path)

        eng = PipelineEngine(
            data=[{"processor_name": "this_does_not_exist"}],
            input_path=str(img_path),
        )
        eng.build_nodes()
        eng.seed_initial_state()
        # inject_exif 不必要（处理器都没找到）
        with pytest.raises(ProcessorNotFoundError) as excinfo:
            eng.run()
        assert excinfo.value.key == "this_does_not_exist"

    def test_caught_via_processor_error_base(self, tmp_path):
        img_path = tmp_path / "in.png"
        Image.new("RGB", (10, 10), "white").save(img_path)
        eng = PipelineEngine(
            data=[{"processor_name": "absent"}],
            input_path=str(img_path),
        )
        eng.build_nodes()
        eng.seed_initial_state()
        with pytest.raises(ProcessorError):
            eng.run()


class TestProcessorRuntimeWrap:
    """处理器 process() 内部抛错时应被包装为 ProcessorRuntimeError。"""

    def test_runtime_error_is_wrapped(self, tmp_path):
        img_path = tmp_path / "in.png"
        Image.new("RGB", (10, 10), "white").save(img_path)
        eng = PipelineEngine(
            data=[{"processor_name": "test_failing_for_pe"}],
            input_path=str(img_path),
        )
        eng.build_nodes()
        eng.seed_initial_state()
        with pytest.raises(ProcessorRuntimeError) as excinfo:
            eng.run()
        assert excinfo.value.processor_name == "test_failing_for_pe"
        assert isinstance(excinfo.value.original, ValueError)
        assert "intentional test failure" in str(excinfo.value.original)

    def test_chained_via_from(self, tmp_path):
        """异常链应保留（``raise ... from e``），便于追溯。"""
        img_path = tmp_path / "in.png"
        Image.new("RGB", (10, 10), "white").save(img_path)
        eng = PipelineEngine(
            data=[{"processor_name": "test_failing_for_pe"}],
            input_path=str(img_path),
        )
        eng.build_nodes()
        eng.seed_initial_state()
        with pytest.raises(ProcessorRuntimeError) as excinfo:
            eng.run()
        # __cause__ 应为原 ValueError（来自 raise ... from e）
        assert isinstance(excinfo.value.__cause__, ValueError)
