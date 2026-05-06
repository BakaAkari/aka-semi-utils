"""测试 [`core.util.get_exif_batch`](core/util.py:1) — EXIF 批量读取。

要点：
- ``get_exif_batch([])`` 返回空 dict；
- 单文件 / 多文件均能正确解析（依赖 exiftool 可用）；
- 子进程出错时降级到逐文件读取（容错性）；
- 私有 ``_parse_exiftool_block`` 解析正确性（不依赖 exiftool 二进制）。
"""

from __future__ import annotations

import shutil
from unittest.mock import patch

import pytest
from PIL import Image

from core.util import _parse_exiftool_block, get_exif_batch

EXIFTOOL_AVAILABLE = shutil.which("exiftool") is not None


# ============================================================
# _parse_exiftool_block — 不依赖二进制
# ============================================================


def test_parse_block_basic():
    block = """ExifTool Version Number         : 12.50
File Name                       : test.jpg
File Size                       : 1.0 MiB
Image Width                     : 1920
Image Height                    : 1080"""
    parsed = _parse_exiftool_block(block)
    assert parsed["ExifToolVersionNumber"] == "12.50"
    assert parsed["FileName"] == "test.jpg"
    assert parsed["ImageWidth"] == "1920"
    assert parsed["ImageHeight"] == "1080"


def test_parse_block_strips_non_ascii():
    block = "Make                            : 索尼Sony"
    parsed = _parse_exiftool_block(block)
    # 非 ASCII 字符（"索尼"）应被过滤
    assert parsed["Make"] == "Sony"


def test_parse_block_handles_colon_in_value():
    block = "Date/Time Original              : 2024-01-01 12:34:56"
    parsed = _parse_exiftool_block(block)
    # 注意 key 里的 / 会被移除
    assert parsed["DateTimeOriginal"] == "2024-01-01 12:34:56"


def test_parse_block_skips_lines_without_colon():
    block = """File Name : test.jpg
no colon here
Image Width : 100"""
    parsed = _parse_exiftool_block(block)
    assert parsed.get("FileName") == "test.jpg"
    assert parsed.get("ImageWidth") == "100"
    assert "nocolonhere" not in parsed  # 被跳过


# ============================================================
# get_exif_batch — 边界
# ============================================================


def test_get_exif_batch_empty_input():
    assert get_exif_batch([]) == {}


def test_get_exif_batch_subprocess_failure_falls_back(tmp_path):
    """exiftool 调用失败时应降级到逐文件读取，且不抛异常。"""
    # 准备两张假 jpg
    p1 = tmp_path / "a.jpg"
    p2 = tmp_path / "b.jpg"
    Image.new("RGB", (4, 4), "red").save(p1, format="JPEG")
    Image.new("RGB", (4, 4), "blue").save(p2, format="JPEG")

    # 模拟批量调用炸了 — 应回落到逐文件 get_exif
    with patch("core.util.subprocess.check_output", side_effect=OSError("boom")):
        result = get_exif_batch([str(p1), str(p2)])

    # 即使 exiftool 失败，也应返回每个 path → dict（可能为空）
    assert set(result.keys()) == {str(p1), str(p2)}
    assert isinstance(result[str(p1)], dict)
    assert isinstance(result[str(p2)], dict)


@pytest.mark.skipif(not EXIFTOOL_AVAILABLE, reason="exiftool 不可用")
def test_get_exif_batch_real_single_file(tmp_path):
    """真实 exiftool 单文件读取。"""
    p = tmp_path / "x.jpg"
    Image.new("RGB", (16, 16), "white").save(p, format="JPEG")

    result = get_exif_batch([str(p)])
    assert str(p) in result
    # 至少应包含 FileName 或 ImageWidth 之一
    info = result[str(p)]
    assert any(k in info for k in ("FileName", "ImageWidth", "ImageSize"))


@pytest.mark.skipif(not EXIFTOOL_AVAILABLE, reason="exiftool 不可用")
def test_get_exif_batch_real_multiple_files(tmp_path):
    """真实 exiftool 多文件读取 — 一次调用解析所有。"""
    paths = []
    for i in range(3):
        p = tmp_path / f"f{i}.jpg"
        Image.new("RGB", (8 + i, 8 + i), "red").save(p, format="JPEG")
        paths.append(str(p))

    result = get_exif_batch(paths)
    assert set(result.keys()) == set(paths)
    # 每个文件都应解析出一些信息
    for p in paths:
        assert isinstance(result[p], dict)


@pytest.mark.skipif(not EXIFTOOL_AVAILABLE, reason="exiftool 不可用")
def test_get_exif_batch_calls_subprocess_once(tmp_path):
    """关键性能保证：3 个文件只触发 1 次 subprocess.check_output。"""
    paths = []
    for i in range(3):
        p = tmp_path / f"perf_{i}.jpg"
        Image.new("RGB", (8, 8), "red").save(p, format="JPEG")
        paths.append(str(p))

    import core.util as util_mod

    real = util_mod.subprocess.check_output
    call_count = {"n": 0}

    def counting(*args, **kwargs):
        call_count["n"] += 1
        return real(*args, **kwargs)

    with patch.object(util_mod.subprocess, "check_output", side_effect=counting):
        get_exif_batch(paths)

    assert call_count["n"] == 1, f"批量读取应当只调一次 subprocess，实际 {call_count['n']}"
