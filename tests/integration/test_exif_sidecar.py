"""测试 EXIF JSON sidecar 输出（Phase 2.3）。

要点：
- 默认 ``emit_exif_json=False`` 时不产生 sidecar 文件；
- ``emit_exif_json=True`` 时产生 ``<basename>.exif.json`` 同目录文件；
- sidecar 内容是合法 JSON 且包含传入的 EXIF 字段；
- 无 EXIF 数据时安全跳过（不抛异常，仍生成图像）；
- ``_exif_sidecar_path`` 路径计算正确。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

# 确保所有处理器装饰器已执行
import processor  # noqa: F401
from processor.core import _exif_sidecar_path, start_process

# ============================================================
# _exif_sidecar_path
# ============================================================


@pytest.mark.parametrize("input_,expected", [
    ("/tmp/foo.jpg", "/tmp/foo.exif.json"),
    ("/tmp/sub/bar.png", "/tmp/sub/bar.exif.json"),
    ("file.jpeg", "file.exif.json"),
    ("/a/b/no_ext", "/a/b/no_ext.exif.json"),
])
def test_exif_sidecar_path(input_, expected):
    assert _exif_sidecar_path(input_) == expected


# ============================================================
# 集成 — 通过 start_process 验证完整链路
# ============================================================


def _minimal_pipeline():
    """返回一个最小可执行的处理器链（仅 resize），用于集成测试。"""
    return [
        {"processor_name": "resize", "ratio": 0.5},
    ]


def _make_input_image(tmp_path: Path) -> Path:
    p = tmp_path / "src.jpg"
    Image.new("RGB", (32, 16), (200, 100, 50)).save(p, format="JPEG", quality=95)
    return p


def test_no_sidecar_by_default(tmp_path):
    """默认不应产生 sidecar 文件。"""
    src = _make_input_image(tmp_path)
    out = tmp_path / "out.jpg"

    start_process(
        data=_minimal_pipeline(),
        input_path=str(src),
        output_path=str(out),
        pre_loaded_exif={"Make": "TestCam"},
    )

    assert out.exists()
    assert not out.with_suffix("").with_suffix(".exif.json").exists()
    assert not (tmp_path / "out.exif.json").exists()


def test_sidecar_emitted_when_flag_true(tmp_path):
    src = _make_input_image(tmp_path)
    out = tmp_path / "out.jpg"
    fake_exif = {"Make": "Sony", "Model": "ILCE-7M4", "FocalLength": "50.0 mm"}

    start_process(
        data=_minimal_pipeline(),
        input_path=str(src),
        output_path=str(out),
        pre_loaded_exif=fake_exif,
        emit_exif_json=True,
    )

    sidecar = tmp_path / "out.exif.json"
    assert out.exists(), "图像输出仍应正常生成"
    assert sidecar.exists(), "sidecar 文件应被写出"

    content = json.loads(sidecar.read_text(encoding="utf-8"))
    assert content == fake_exif


def test_sidecar_with_no_exif_does_not_crash(tmp_path):
    """没有 EXIF 数据时应安全跳过，不影响主输出。"""
    src = _make_input_image(tmp_path)
    out = tmp_path / "out.jpg"

    start_process(
        data=_minimal_pipeline(),
        input_path=str(src),
        output_path=str(out),
        pre_loaded_exif={},  # 空 EXIF
        emit_exif_json=True,
    )

    assert out.exists()
    # 空 EXIF → 不写 sidecar（warning 而已）
    assert not (tmp_path / "out.exif.json").exists()


def test_sidecar_preserves_unicode(tmp_path):
    """sidecar 应使用 ensure_ascii=False，可读保留非 ASCII（虽然 EXIF 通常 ASCII）。"""
    src = _make_input_image(tmp_path)
    out = tmp_path / "out.jpg"
    fake_exif = {"Author": "测试作者", "Comment": "中文注释"}

    start_process(
        data=_minimal_pipeline(),
        input_path=str(src),
        output_path=str(out),
        pre_loaded_exif=fake_exif,
        emit_exif_json=True,
    )

    sidecar = tmp_path / "out.exif.json"
    raw = sidecar.read_text(encoding="utf-8")
    assert "测试作者" in raw  # 非转义形式
    parsed = json.loads(raw)
    assert parsed["Author"] == "测试作者"


def test_sidecar_in_nested_dir(tmp_path):
    """sidecar 与图像同目录，不污染父目录。"""
    src = _make_input_image(tmp_path)
    nested = tmp_path / "deep" / "dir"
    nested.mkdir(parents=True)
    out = nested / "result.jpg"

    start_process(
        data=_minimal_pipeline(),
        input_path=str(src),
        output_path=str(out),
        pre_loaded_exif={"k": "v"},
        emit_exif_json=True,
    )

    assert (nested / "result.exif.json").exists()
    assert not (tmp_path / "result.exif.json").exists()
