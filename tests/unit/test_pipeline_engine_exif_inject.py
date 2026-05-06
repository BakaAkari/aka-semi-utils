"""测试 [`processor.core.PipelineEngine`](processor/core.py:1) 的 ``pre_loaded_exif`` 注入。

要点：
- 提供 ``pre_loaded_exif`` 时不应再调用 ``get_exif``（性能保证）；
- 未提供时回落到 input_path 读取；
- 都不提供时应静默 no-op；
- ``inject_exif`` 不会覆盖节点已有的 ``exif`` 键（保持 idempotent）。
"""

from __future__ import annotations

from unittest.mock import patch

from processor.core import PipelineEngine


def _build(data, **kwargs):
    eng = PipelineEngine(data=data, **kwargs)
    eng.build_nodes()
    return eng


def test_pre_loaded_exif_skips_get_exif_call():
    """提供 pre_loaded_exif 时，不应触发 exiftool 子进程。"""
    fake_exif = {"Make": "TestCam", "Model": "X1"}
    data = [{"processor_name": "blur", "radius": 1}]

    eng = _build(data, input_path="/non/existent/file.jpg", pre_loaded_exif=fake_exif)

    with patch("processor.core.get_exif") as mock_get:
        eng.inject_exif()
        mock_get.assert_not_called()

    assert eng.nodes[0]["exif"] == fake_exif


def test_inject_exif_uses_input_path_when_no_preload():
    fake_exif = {"FocalLength": "50.0 mm"}
    data = [{"processor_name": "blur", "radius": 1}]
    eng = _build(data, input_path="/some/path.jpg")

    with patch("processor.core.get_exif", return_value=fake_exif) as mock_get:
        eng.inject_exif()
        mock_get.assert_called_once_with("/some/path.jpg")

    assert eng.nodes[0]["exif"] == fake_exif


def test_inject_exif_no_input_no_preload_is_noop():
    """既无 input_path 也无 pre_loaded_exif，应静默不做事，不抛异常。"""
    data = [{"processor_name": "blur", "radius": 1}]
    eng = _build(data)

    with patch("processor.core.get_exif") as mock_get:
        eng.inject_exif()
        mock_get.assert_not_called()

    assert "exif" not in eng.nodes[0]


def test_inject_exif_does_not_overwrite_existing():
    """节点已有 exif 时不应被覆盖。"""
    custom_exif = {"manual": "value"}
    data = [{"processor_name": "blur", "radius": 1, "exif": custom_exif}]
    eng = _build(data, pre_loaded_exif={"different": "preloaded"})

    eng.inject_exif()

    assert eng.nodes[0]["exif"] == custom_exif


def test_pre_loaded_exif_broadcasts_to_all_nodes():
    fake_exif = {"Make": "Canon"}
    data = [
        {"processor_name": "blur", "radius": 1},
        {"processor_name": "resize", "ratio": 0.5},
        {"processor_name": "trim"},
    ]
    eng = _build(data, pre_loaded_exif=fake_exif)
    eng.inject_exif()

    for node in eng.nodes:
        assert node["exif"] == fake_exif
