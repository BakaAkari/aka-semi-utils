"""Phase 1.4 集成测试 — PipelineEngine 与 start_process 行为等价性。

通过实际跑一个最小 pipeline（solid_color 生成器 → 单图输出）来验证：
1. ``PipelineEngine`` 拆分后的方法链能正确组合执行；
2. ``start_process`` 旧入口与 ``PipelineEngine.execute`` 输出一致；
3. ``run`` 不依赖 ``output_path``，可纯内存运行；
4. ``inject_exif`` 在 ``input_path=None`` 时不抛错。
"""

from __future__ import annotations

from PIL import Image

import processor  # noqa: F401  # 触发处理器自动注册
from processor.core import PipelineEngine, start_process

# ---------------------------------------------------------------------------
# 最小 pipeline：单一 solid_color 节点直接生成纯色图，避免文件 I/O
# ---------------------------------------------------------------------------


def _solid_color_pipeline_data() -> list[dict]:
    """生成一个最小可运行的处理器配置 — 单个 solid_color 节点。

    注意：``solid_color`` 直接把 ``color`` 字段传给 ``Image.new``，因此用元组。
    """
    return [
        {
            "processor_name": "solid_color",
            "color": (10, 20, 30, 255),
            "width": 32,
            "height": 16,
        }
    ]


def test_pipeline_engine_pure_memory_run():
    """无 input_path / output_path，仅内存运行，应得到 PIL Image。"""
    engine = PipelineEngine(data=_solid_color_pipeline_data())
    result = engine.execute()

    assert isinstance(result, Image.Image)
    assert result.size == (32, 16)
    # 验证是纯色：取中心像素
    pixel = result.convert("RGBA").getpixel((16, 8))
    assert pixel == (10, 20, 30, 255)


def test_start_process_matches_pipeline_engine():
    """旧入口 start_process 与 PipelineEngine.execute 应返回等价结果。"""
    data = _solid_color_pipeline_data()
    legacy = start_process(data=data)
    new = PipelineEngine(data=_solid_color_pipeline_data()).execute()

    assert isinstance(legacy, Image.Image)
    assert isinstance(new, Image.Image)
    assert legacy.size == new.size
    assert legacy.tobytes() == new.tobytes()


def test_pipeline_engine_save_to_disk(tmp_path):
    """提供 output_path 时应写入磁盘。"""
    output_file = tmp_path / "out.jpg"
    engine = PipelineEngine(
        data=_solid_color_pipeline_data(),
        output_path=str(output_file),
    )
    engine.execute()

    assert output_file.exists()
    assert output_file.stat().st_size > 0

    # 重新读回，验证是有效 JPEG
    with Image.open(output_file) as reopened:
        assert reopened.size == (32, 16)


def test_build_and_seed_separately():
    """单独调用 build_nodes / seed_initial_state，验证可组合性。"""
    engine = PipelineEngine(data=_solid_color_pipeline_data())
    nodes = engine.build_nodes()
    assert len(nodes) == 1
    assert nodes[0].get_processor_name() == "solid_color"

    # 还没 seed，不应有 buffer / buffer_path
    assert "buffer" not in nodes[0]
    assert "buffer_path" not in nodes[0]

    # seed 之后（无 input_path、无 initial_buffer）也不会爆
    engine.seed_initial_state()
    # solid_color 不依赖 buffer，能正常 run
    engine.run()
    final = engine.save_output()
    assert isinstance(final, Image.Image)


def test_inject_exif_noop_without_input_path():
    """无 input_path 时 inject_exif 应当静默跳过（不抛异常、不写入 exif 键）。"""
    engine = PipelineEngine(data=_solid_color_pipeline_data())
    engine.build_nodes()
    engine.inject_exif()  # 不应抛错

    assert "exif" not in engine.nodes[0]


def test_pipeline_engine_initial_buffer():
    """提供 initial_buffer 时，应跳过文件加载使用提供的图像。"""
    custom_img = Image.new("RGB", (8, 8), (123, 45, 67))

    # pipeline：blur 滤镜（应用于 initial_buffer）
    data = [
        {
            "processor_name": "blur",
            "blur_radius": 0,  # 0 半径 = 几乎不变
        }
    ]
    engine = PipelineEngine(data=data, initial_buffer=[custom_img])
    result = engine.execute()

    assert isinstance(result, Image.Image)
    assert result.size == (8, 8)
