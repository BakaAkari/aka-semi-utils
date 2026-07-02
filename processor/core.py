from __future__ import annotations

import contextlib
import functools
import json
import os
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterator, MutableMapping
from enum import Enum
from itertools import chain
from typing import Any

from PIL import Image, ImageColor

# 允许处理大图片（临时提升炸弹保护阈值，而非全局禁用）
# 必须在导入下游 core.* 模块前完成（它们间接使用 PIL），故以下 import 故意放在此处。
_original_max_pixels = Image.MAX_IMAGE_PIXELS
Image.MAX_IMAGE_PIXELS = int(1e9)  # 临时提升到 10 亿像素，处理完恢复

from core.config_loader import load_config_ini as load_config  # noqa: E402
from core.exceptions import ProcessorNotFoundError, ProcessorRuntimeError  # noqa: E402
from core.image_io import load_image_safely  # noqa: E402
from core.logger import logger  # noqa: E402
from core.util import get_exif  # noqa: E402


class PipelineContext(MutableMapping):
    """管道上下文"""

    def __init__(self, config: dict[str, Any]):
        self._config = config

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key) if key in self._config and self._config.get(key) is not None else default

    def get_exif(self) -> dict[str, Any]:
        return self.get('exif')

    def getcolor(self, key: str, default: Any = None) -> tuple[int, int, int, int]:
        return _parse_color(self._config.get(key, default))

    def getint(self, key: str, default: int = 0) -> int:
        return int(self.get(key, default))

    def getenum(self, key: str, default: Any = None, enum: type[Enum] | None = None) -> Any:
        value = self.get(key, default)

        # 未指定枚举类型，直接返回原值
        if enum is None:
            return value

        # 已经是目标枚举类型，直接返回
        if isinstance(value, enum):
            return value

        # 尝试通过 name 查找 (如 "RED" -> Color.RED)
        if isinstance(value, str):
            try:
                return enum[value]
            except KeyError:
                pass
            try:
                return enum[value.upper()]
            except KeyError:
                pass

        # 尝试通过 value 查找 (如 1 -> Color.RED)
        try:
            return enum(value)
        except ValueError:
            pass

        # 都找不到，返回默认值
        return default

    def get_processor_name(self) -> str | None:
        return self.get("processor_name")

    def get_buffer(self) -> list[Image.Image]:
        if not self.get("buffer_loaded", False) and self.get("buffer_path"):
            # 立即关闭文件句柄并返回独立内存对象，避免批量场景下泄漏 fd。
            self.set(
                "buffer",
                [load_image_safely(path, transpose_exif=True) for path in self.get("buffer_path")],
            )
            self.set("buffer_loaded", True)
        return self.get("buffer", [])

    def set(self, key: str, value: Any) -> PipelineContext:
        self._config[key] = value
        return self

    def save_buffer(self, processor_name: str, force_save: bool = False) -> PipelineContext:
        if not (force_save or self.get("save_buffer", False)):
            return self
        directory = self.get("output", "./tmp")
        if not os.path.isdir(directory):
            os.makedirs(directory)
        buffer_path = []
        for img in self.get_buffer():
            if img.mode == "RGB":
                file_ext = "jpg"
            elif img.mode == "RGBA":
                file_ext = "png"
            else:
                raise RuntimeError(f"Unsupported image mode {img.mode}")

            new_filename = f"{processor_name}_{uuid.uuid4().hex}.{file_ext}"
            path = os.path.join(directory, new_filename)
            img.save(path)
            logger.debug(f"Saved image: {path}")
            buffer_path.append(path)
        self.set("buffer_path", buffer_path)
        return self

    def update_buffer(self, buffer: list[Image.Image]) -> PipelineContext:
        self.set("buffer", buffer)
        return self

    def success(self, success: bool = True) -> PipelineContext:
        self.set("success", success)
        return self

    # MutableMapping 要求实现的抽象方法
    def __getitem__(self, key: str) -> Any:
        return self._config[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._config[key] = value

    def __delitem__(self, key: str) -> None:
        del self._config[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._config)

    def __len__(self) -> int:
        return len(self._config)

    def __contains__(self, key: object) -> bool:
        return key in self._config


class ImageProcessor(ABC):
    """图像处理器抽象基类。

    子类**必须**：
    - 实现 ``process(self, ctx)`` 方法。
    - 通过 ``@register("xxx")`` 装饰器注册（推荐），或在类上声明
      ``processor_name`` 类属性 + 使用 ``register_class`` 显式注册。

    向后兼容：
    - 仍允许通过 ``name(self) -> str`` 实例方法返回名称（旧代码路径）。
      若同时存在类属性 ``processor_name``，以类属性为准。
    - ``category(self) -> str`` 同理（``processor_category`` 类属性 + 方法兜底）。

    AOP：``__init_subclass__`` 仍负责给 ``process`` 包装高精度计时日志，
    但**不再**进行强制实例化注册（解决子类需要构造参数时无法注册的问题）。
    """

    # 类级别的元信息（推荐通过 @register 装饰器或子类直接覆盖）
    processor_name: str = ""
    processor_category: str = ""

    @abstractmethod
    def process(self, ctx: PipelineContext):
        ...

    def name(self) -> str:
        """返回处理器名称。优先使用类属性 ``processor_name``，否则要求子类覆写。"""
        if self.processor_name:
            return self.processor_name
        raise NotImplementedError(
            f"{type(self).__name__} 未声明 processor_name，也未覆写 name() 方法"
        )

    def category(self) -> str:
        """返回处理器分类。优先使用类属性 ``processor_category``。"""
        if self.processor_category:
            return self.processor_category
        raise NotImplementedError(
            f"{type(self).__name__} 未声明 processor_category，也未覆写 category() 方法"
        )

    def __init_subclass__(cls, **kwargs):
        """子类定义时自动给 ``process`` 方法套上计时 AOP（不做注册）。"""
        super().__init_subclass__(**kwargs)

        # 仅当子类自己定义了 process（非继承自父类已包装版本）时才包装一次，
        # 避免对中间抽象类（FilterProcessor / Generator / Merger）重复包装。
        if "process" not in cls.__dict__:
            return

        original_process = cls.__dict__["process"]
        # 已经被包装过的就别再包装（idempotent）
        if getattr(original_process, "__aop_timed__", False):
            return

        @functools.wraps(original_process)
        def wrapper(self, ctx: PipelineContext):
            start_time = time.perf_counter()
            try:
                return original_process(self, ctx)
            finally:
                end_time = time.perf_counter()
                cost_ms = (end_time - start_time) * 1000
                try:
                    proc_name = self.name()
                except Exception:
                    proc_name = type(self).__name__
                logger.debug(f"[monitor]processor#{proc_name} cost {cost_ms:.2f}ms")
                # Phase 5.1：若 ctx 中绑定了 PerfRecord，则同时记录到样本列表，
                # 供 PipelineEngine.execute() 收集后随 BatchResultItem 跨进程返回。
                rec = ctx.get("_perf_record") if hasattr(ctx, "get") else None
                if rec is not None:
                    # 性能采样**绝不**影响主流程，吞掉所有异常
                    with contextlib.suppress(Exception):
                        rec.add(proc_name, cost_ms)

        wrapper.__aop_timed__ = True  # type: ignore[attr-defined]  # 标记已包装
        cls.process = wrapper  # type: ignore[method-assign]


# Direction 枚举的"权威定义"位于 [`processor/types.py:8`](processor/types.py:8)
# 这里仅作为向后兼容的转发别名，避免 ``from processor.core import Direction``
# 的旧代码路径失效。
from processor.types import Direction  # noqa: E402,F401  (re-export)


def _parse_color(color: Any) -> tuple[int, int, int, int]:
    """
    解析颜色为 RGBA 元组

    支持格式:
    - 元组: (255, 255, 255) 或 (255, 255, 255, 128)
    - 字符串元组: '(255,255,255,0)' 或 '255,255,255,0'
    - 十六进制: '#FFFFFF' 或 '#FFFFFFFF'
    - 颜色名称: 'red', 'blue' 等
    """
    # 已经是元组或列表
    if isinstance(color, (tuple, list)):
        if len(color) == 3:
            return *color, 255
        return tuple(color)

    # 字符串处理
    if isinstance(color, str):
        color = color.strip()

        # 处理元组格式字符串: '(255,255,255,0)' 或 '255,255,255,0'
        color_clean = color.strip('()')
        if ',' in color_clean:
            try:
                parts = [int(x.strip()) for x in color_clean.split(',')]
                if len(parts) == 3:
                    return (parts[0], parts[1], parts[2], 255)
                elif len(parts) == 4:
                    return (parts[0], parts[1], parts[2], parts[3])
            except ValueError:
                pass

        # 处理十六进制或颜色名称
        try:
            rgba = ImageColor.getrgb(color)
            if len(rgba) == 3:
                return (rgba[0], rgba[1], rgba[2], 255)
            return (rgba[0], rgba[1], rgba[2], rgba[3])
        except ValueError:
            pass

    raise ValueError(f"无法解析颜色: {color}")


_processor_registry: dict[str, type[ImageProcessor]] = {}


def get_all_processors() -> dict[str, type[ImageProcessor]]:
    """获取所有已注册的处理器"""
    return _processor_registry.copy()


def get_processor(key: str) -> type[ImageProcessor] | None:
    """从注册表获取处理器类

    Args:
        key: 处理器名称

    Returns:
        处理器类，如果未找到则返回 None
    """
    return _processor_registry.get(key)


def register_processor(key: str, processor_cls: type[ImageProcessor]):
    """注册处理器到全局注册表（首次注册生效，重复注册忽略）。"""
    if key in _processor_registry:
        existing = _processor_registry[key]
        if existing is not processor_cls:
            logger.warning(
                f"Processor key {key!r} already registered to "
                f"{existing.__name__}, ignoring {processor_cls.__name__}"
            )
        return
    _processor_registry[key] = processor_cls
    logger.debug(f"Registered processor: {key} -> {processor_cls.__name__}")


def register(name: str, category: str | None = None):
    """处理器注册装饰器（推荐方式）。

    用法::

        @register("blur")
        class BlurFilter(FilterProcessor):
            def process(self, ctx): ...

    - 自动设置 ``processor_name`` 类属性（供 ``name()`` 默认实现使用）。
    - 若提供 ``category``，则同时设置 ``processor_category``。
    - 注册到全局注册表 ``_processor_registry``。

    Args:
        name: 处理器在模板 JSON 中使用的 key（如 "blur"、"resize"）。
        category: 可选，处理器分类（filter / generator / merger）。
    """
    if not name or not isinstance(name, str):
        raise ValueError(f"register() 需要一个非空字符串作为 name，得到: {name!r}")

    def _decorator(cls: type[ImageProcessor]) -> type[ImageProcessor]:
        if not isinstance(cls, type) or not issubclass(cls, ImageProcessor):
            raise TypeError(
                f"@register 只能装饰 ImageProcessor 子类，得到: {cls!r}"
            )
        cls.processor_name = name
        if category is not None:
            cls.processor_category = category
        register_processor(name, cls)
        return cls

    return _decorator


class PipelineEngine:
    """处理器管道执行引擎。

    把原 ``start_process`` God Function 拆为多个有清晰单一职责的方法：

    1. :meth:`build_nodes`        — 把 dict 列表转为 ``PipelineContext`` 列表。
    2. :meth:`seed_initial_state` — 注入初始 buffer / 文件路径。
    3. :meth:`inject_exif`        — 给所有节点填充 EXIF（若有）。
    4. :meth:`run`                — 顺序执行节点（含 select / merger 路由）。
    5. :meth:`save_output`        — 写出最终图像到磁盘。
    6. :meth:`execute`            — 一键串起以上五步（兼容 ``start_process`` 旧签名）。

    设计要点：
    - 所有方法都是**幂等且可复用**的，方便测试单独组合；
    - 不做并发、不做 I/O 异步——本类聚焦"单文件处理"，并发由更外层负责。
    """

    def __init__(
        self,
        data: list[dict],
        input_path: str | None = None,
        output_path: str | None = None,
        initial_buffer: list | None = None,
        pre_loaded_exif: dict | None = None,
        emit_exif_json: bool = False,
        perf_record: Any | None = None,
    ) -> None:
        self.data = data
        self.input_path = input_path
        self.output_path = output_path
        self.initial_buffer = initial_buffer
        # 允许外部传入已读取好的 EXIF（避免每个文件 spawn 两次 exiftool）
        self.pre_loaded_exif = pre_loaded_exif
        # 是否在输出图旁同时写出 *.exif.json sidecar 文件
        self.emit_exif_json = emit_exif_json
        # Phase 5.1：性能采样容器；None 表示禁用采样（零开销）
        self.perf_record = perf_record
        self.nodes: list[PipelineContext] = []
        self.all_buffer: list[list[Image.Image]] = []
        self.last_merger_idx: int = -1

    # ------------------------------------------------------------------ build
    def build_nodes(self) -> list[PipelineContext]:
        """把配置 dict 列表转换为 ``PipelineContext`` 节点列表。

        Phase 5.1：若启用了 ``perf_record``，将其引用塞进每个节点的 ctx，
        AOP wrapper 在 :meth:`processor.core.ImageProcessor.process` 完成后
        会把 ``(processor_name, ms)`` 写入。
        """
        self.nodes = [PipelineContext(datum) for datum in self.data]
        if self.perf_record is not None:
            for node in self.nodes:
                node.set("_perf_record", self.perf_record)
        return self.nodes

    def seed_initial_state(self) -> None:
        """给首节点注入初始 buffer 或文件路径（懒加载）。"""
        if not self.nodes:
            return
        head = self.nodes[0]
        if self.initial_buffer is not None:
            head.set("buffer", self.initial_buffer)
            head.set("buffer_loaded", True)
        elif self.input_path is not None:
            head.set("buffer_path", [self.input_path])

    def inject_exif(self) -> None:
        """读取一次 EXIF 并广播到所有节点（缺失才填，已有则保留）。

        若构造时已注入 ``pre_loaded_exif``，**直接复用**，跳过 exiftool 调用。
        """
        if self.pre_loaded_exif is not None:
            exif = self.pre_loaded_exif
        elif self.input_path is not None:
            exif = get_exif(self.input_path)
        else:
            return
        for node in self.nodes:
            if "exif" not in node:
                node["exif"] = exif

    # -------------------------------------------------------------- routing
    def _route_buffer(self, idx: int, node: PipelineContext, instance: ImageProcessor) -> None:
        """根据节点类型（select / merger / 普通）路由 buffer 到 ``node``。"""
        if "select" in node:
            indexes = json.loads(node["select"])
            flattened = list(chain.from_iterable([self.all_buffer[i] for i in indexes]))
            node.update_buffer(flattened)
            return

        if instance.category() != "merger":
            # 普通节点：使用上一节点的输出
            node.update_buffer(self.all_buffer[-1])
            return

        # merger 节点：收集 last_merger_idx+1 ~ idx 之间所有 buffer 并展平
        # 注意 all_buffer 起始已经包含 head_output，因此切片需 +1 偏移
        buffers_to_merge = self.all_buffer[self.last_merger_idx + 1 : idx + 1]
        flattened = list(chain.from_iterable(buffers_to_merge))
        node.update_buffer(flattened)
        self.last_merger_idx = idx

    # --------------------------------------------------------------- execute
    def run(self) -> list[Image.Image]:
        """顺序执行所有处理器节点，返回最终 buffer。"""
        # 头节点的输出（首次调用 get_buffer 触发懒加载）
        head_output = self.nodes[0].get_buffer()
        self.all_buffer = [head_output]
        self.last_merger_idx = -1

        for idx, node in enumerate(self.nodes):
            proc_name = node.get_processor_name()
            if proc_name is None:
                raise ProcessorNotFoundError("<missing>")
            proc_cls = get_processor(proc_name)
            if proc_cls is None:
                raise ProcessorNotFoundError(proc_name)

            instance: ImageProcessor = proc_cls()
            self._route_buffer(idx, node, instance)
            try:
                instance.process(node)
            except (ProcessorNotFoundError, ProcessorRuntimeError):
                raise  # 已是项目自定义异常，原样向上抛
            except Exception as e:
                # 包装为 ProcessorRuntimeError，保留原异常 chain
                raise ProcessorRuntimeError(proc_name, e) from e
            self.all_buffer.append(node.get_buffer())

        return self.nodes[-1].get_buffer()

    def save_output(self) -> Image.Image | None:
        """把最后节点的首张图保存到 ``output_path``（若已配置）。"""
        if not self.nodes:
            return None

        last_node = self.nodes[-1]
        last_node.save_buffer("final").success()
        if self.output_path is None:
            return last_node.get_buffer()[0]

        cfg = load_config()
        first_image = last_node.get_buffer()[0]
        quality = last_node.getint("quality", cfg.getint("DEFAULT", "quality"))
        subsampling = last_node.getint("subsampling", cfg.getint("DEFAULT", "subsampling"))
        first_image.convert("RGB").save(
            self.output_path,
            quality=quality,
            subsampling=subsampling,
        )
        logger.success(f"Generated new image: {self.output_path}")

        # 可选 EXIF JSON sidecar 输出
        if self.emit_exif_json:
            self._write_exif_sidecar()

        return first_image

    # -------------------------------------------------------- exif sidecar
    def _write_exif_sidecar(self) -> None:
        """把 EXIF dict 序列化为与输出图同目录的 ``<basename>.exif.json``。

        - 找最后节点的 ``exif`` 键作为数据源；若不存在则尝试 pre_loaded_exif；
          都没有则记录 warning 跳过（不抛异常，避免阻断主输出）。
        - JSON 序列化用 ``ensure_ascii=False`` 保留可读字符，indent=2 便于 diff。
        """
        if not self.output_path:
            return
        last_node = self.nodes[-1]
        exif: dict | None = last_node.get("exif") or self.pre_loaded_exif
        if not exif:
            logger.warning(
                f"emit_exif_json=True 但找不到 EXIF 数据，跳过 sidecar: {self.output_path}"
            )
            return

        sidecar_path = _exif_sidecar_path(self.output_path)
        try:
            os.makedirs(os.path.dirname(sidecar_path) or ".", exist_ok=True)
            with open(sidecar_path, "w", encoding="utf-8") as f:
                json.dump(exif, f, ensure_ascii=False, indent=2, default=str)
            logger.debug(f"Wrote EXIF sidecar: {sidecar_path}")
        except OSError as e:
            logger.error(f"Failed to write EXIF sidecar {sidecar_path}: {e}")

    def execute(self) -> Image.Image:
        """串起 build → seed → exif → run → save 的一键入口。

        Phase 5.1：若提供了 ``perf_record``，会自动测量端到端总耗时并写入
        :attr:`processor.perf.PerfRecord.total_ms`。
        """
        pipeline_start = time.perf_counter() if self.perf_record is not None else 0.0
        self.build_nodes()
        self.seed_initial_state()
        self.inject_exif()
        self.run()
        result = self.save_output()
        # save_output 永远返回 first_image（除非节点为空）
        if result is None:
            raise RuntimeError("Pipeline produced no output (empty node list)")
        if self.perf_record is not None:
            self.perf_record.total_ms = (time.perf_counter() - pipeline_start) * 1000.0
        return result


def _exif_sidecar_path(output_path: str) -> str:
    """根据图像输出路径计算 EXIF JSON sidecar 路径（``foo.jpg`` → ``foo.exif.json``）。"""
    root, _ = os.path.splitext(output_path)
    return f"{root}.exif.json"


def start_process(
    data: list[dict],
    input_path: str | None = None,
    output_path: str | None = None,
    initial_buffer: list | None = None,
    pre_loaded_exif: dict | None = None,
    emit_exif_json: bool = False,
    perf_record: Any | None = None,
) -> Image.Image:
    """向后兼容的过程式入口 — 内部委托给 :class:`PipelineEngine`。

    Args:
        data: 处理器配置列表（每项是一个 dict，描述一个处理器节点）。
        input_path: 输入文件路径，用于读取 EXIF 与默认 buffer。
        output_path: 输出文件路径；若为 ``None`` 则只在内存中处理。
        initial_buffer: 直接提供的初始图像列表（绕过 ``input_path`` 加载）。
        pre_loaded_exif: 已读取好的 EXIF dict；若提供，将跳过 exiftool 调用。
        emit_exif_json: 是否同时写出 ``<basename>.exif.json`` sidecar 文件。
        perf_record: 可选的 :class:`processor.perf.PerfRecord`；若提供，
            管道运行时会自动累加各 processor 耗时与端到端 total_ms。

    Returns:
        最终输出的首张 PIL Image。
    """
    return PipelineEngine(
        data=data,
        input_path=input_path,
        output_path=output_path,
        initial_buffer=initial_buffer,
        pre_loaded_exif=pre_loaded_exif,
        emit_exif_json=emit_exif_json,
        perf_record=perf_record,
    ).execute()
