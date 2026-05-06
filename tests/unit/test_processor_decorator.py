"""Phase 1.3 守卫测试 — 装饰器化注册。

验证：
1. ``@register("name")`` 装饰器正确将类登记到注册表。
2. 注册过程**不**强制实例化（即：构造函数需要参数的处理器也能注册）。
3. ``__init_subclass__`` 的 AOP 计时仍生效（``process`` 方法被包装）。
4. 中间抽象基类 ``FilterProcessor`` / ``Generator`` / ``Merger`` 不会被错误地登记到注册表。
"""

from __future__ import annotations

import processor  # noqa: F401  # 触发自动注册副作用
from processor import core as proc_core
from processor.core import (
    ImageProcessor,
    PipelineContext,
    get_all_processors,
    get_processor,
    register,
)
from processor.filters import (
    BlurFilter,
    FilterProcessor,
    ResizeFilter,
)
from processor.generators import Generator
from processor.mergers import Merger

# ---------------------------------------------------------------------------
# 1. 装饰器把类挂到注册表
# ---------------------------------------------------------------------------


def test_register_decorator_attaches_class_attribute():
    """@register 应设置 processor_name 类属性。"""
    assert BlurFilter.processor_name == "blur"
    assert ResizeFilter.processor_name == "resize"


def test_get_processor_returns_class_not_instance():
    """注册表里存的是类，不是实例。"""
    cls = get_processor("blur")
    assert cls is BlurFilter
    assert isinstance(cls, type)


# ---------------------------------------------------------------------------
# 2. 注册过程不强制实例化（构造参数友好）
# ---------------------------------------------------------------------------


def test_register_does_not_instantiate_class():
    """@register 装饰器在注册时**不**调用 ``cls()``。

    通过定义一个构造函数会抛异常的处理器来验证：注册过程绝不能触发 ``__init__``。
    """
    init_call_count = {"n": 0}

    @register("__test_no_instantiate__")
    class NoInitProcessor(ImageProcessor):
        processor_category = "filter"

        def __init__(self, required_arg):
            init_call_count["n"] += 1
            self.required_arg = required_arg

        def process(self, ctx: PipelineContext):
            return ctx

    try:
        # 注册成功
        assert get_processor("__test_no_instantiate__") is NoInitProcessor
        # 关键：注册过程没有触发 __init__
        assert init_call_count["n"] == 0
        # 但用户主动实例化（带参数）仍可工作
        instance = NoInitProcessor("foo")
        assert init_call_count["n"] == 1
        assert instance.required_arg == "foo"
        # name() 来自 processor_name 类属性
        assert instance.name() == "__test_no_instantiate__"
    finally:
        # 清理避免污染其他用例
        proc_core._processor_registry.pop("__test_no_instantiate__", None)


# ---------------------------------------------------------------------------
# 3. AOP 计时仍生效
# ---------------------------------------------------------------------------


def test_process_method_is_aop_wrapped():
    """子类的 process 方法被打上 ``__aop_timed__`` 标记。"""
    assert getattr(BlurFilter.process, "__aop_timed__", False) is True
    assert getattr(ResizeFilter.process, "__aop_timed__", False) is True


def test_aop_wrapping_is_idempotent():
    """重复触发 __init_subclass__ 不会重复包装。

    通过手工创建一个继承自已包装类的子类并验证 process 仍然只有一层包装。
    """

    class DerivedBlur(BlurFilter):
        # 不重写 process，应继承父类已包装版本
        pass

    # DerivedBlur 没有自己定义 process，所以 __init_subclass__ 跳过包装
    # 它继承的就是 BlurFilter.process（已包装版本）
    assert DerivedBlur.process is BlurFilter.process


# ---------------------------------------------------------------------------
# 4. 中间抽象基类不入注册表
# ---------------------------------------------------------------------------


def test_intermediate_abstract_classes_not_registered():
    """FilterProcessor / Generator / Merger 这类不带 @register 的中间类不应进入注册表。"""
    registry = get_all_processors()
    registered_classes = set(registry.values())
    assert FilterProcessor not in registered_classes
    assert Generator not in registered_classes
    assert Merger not in registered_classes


def test_intermediate_classes_have_category_but_no_name():
    """中间基类只设置了 processor_category，没有 processor_name。"""
    assert FilterProcessor.processor_category == "filter"
    assert Generator.processor_category == "generator"
    assert Merger.processor_category == "merger"
    # 没有名字（空字符串就是默认值）
    assert FilterProcessor.processor_name == ""


# ---------------------------------------------------------------------------
# 5. register() 参数校验
# ---------------------------------------------------------------------------


def test_register_rejects_empty_name():
    import pytest

    with pytest.raises(ValueError):

        @register("")
        class _Bad(ImageProcessor):
            def process(self, ctx):
                pass


def test_register_rejects_non_processor_class():
    import pytest

    with pytest.raises(TypeError):

        @register("__test_not_processor__")
        class _NotProcessor:
            pass
