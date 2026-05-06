"""Phase 5.7 — EXIF 缓存层单元测试。

覆盖 [`core.util`](core/util.py:1) 的 Phase 5.2 缓存特性：

- ``get_exif`` / ``get_exif_batch`` 同进程二次调用复用缓存（无 exiftool 调用）；
- 文件 mtime 变化后缓存失效（key 含 mtime_ns）；
- 容量超限按 FIFO 淘汰最旧条目；
- ``clear_exif_cache`` / ``exif_cache_size`` 工具行为正确；
- 失败 / 空结果不写入缓存（保留下次重试机会）。
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from core import util as core_util
from core.util import (
    _exif_cache_key,
    _exif_cache_put,
    clear_exif_cache,
    exif_cache_size,
    get_exif,
    get_exif_batch,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    """每个测试前后都清空缓存，防止互相污染。"""
    clear_exif_cache()
    yield
    clear_exif_cache()


@pytest.fixture
def fake_jpeg(tmp_path: Path) -> Path:
    p = tmp_path / "img.jpg"
    p.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-bytes")
    return p


# ============================================================
# _exif_cache_key
# ============================================================


class TestCacheKey:
    def test_existing_file_returns_tuple(self, fake_jpeg):
        key = _exif_cache_key(fake_jpeg)
        assert key is not None
        abspath, mtime_ns = key
        assert os.path.isabs(abspath)
        assert isinstance(mtime_ns, int)

    def test_missing_file_returns_none(self, tmp_path):
        assert _exif_cache_key(tmp_path / "nope.jpg") is None

    def test_key_is_stable_until_mtime_changes(self, fake_jpeg):
        k1 = _exif_cache_key(fake_jpeg)
        k2 = _exif_cache_key(fake_jpeg)
        assert k1 == k2

    def test_key_changes_on_mtime_update(self, fake_jpeg):
        k1 = _exif_cache_key(fake_jpeg)
        # 强制修改 mtime（睡眠太慢；直接用 os.utime）
        st = os.stat(fake_jpeg)
        new_mtime = st.st_mtime + 10.0
        os.utime(fake_jpeg, (st.st_atime, new_mtime))
        k2 = _exif_cache_key(fake_jpeg)
        assert k1 != k2


# ============================================================
# _exif_cache_put 与 FIFO 淘汰
# ============================================================


class TestCachePut:
    def test_empty_value_not_stored(self):
        _exif_cache_put(("/x", 1), {})
        assert exif_cache_size() == 0

    def test_non_empty_value_stored(self):
        _exif_cache_put(("/x", 1), {"Make": "Nikon"})
        assert exif_cache_size() == 1

    def test_overwrite_same_key(self):
        _exif_cache_put(("/x", 1), {"Make": "A"})
        _exif_cache_put(("/x", 1), {"Make": "B"})
        # 同 key 覆盖，size 仍为 1
        assert exif_cache_size() == 1

    def test_fifo_eviction_when_exceed_maxsize(self, monkeypatch):
        """超过容量时弹出最早插入的条目。"""
        monkeypatch.setattr(core_util, "_EXIF_CACHE_MAXSIZE", 3)
        _exif_cache_put(("/a", 1), {"x": 1})
        _exif_cache_put(("/b", 1), {"x": 2})
        _exif_cache_put(("/c", 1), {"x": 3})
        assert exif_cache_size() == 3
        # 再加一个，应淘汰最早的 ("/a", 1)
        _exif_cache_put(("/d", 1), {"x": 4})
        assert exif_cache_size() == 3
        assert ("/a", 1) not in core_util._EXIF_CACHE
        assert ("/d", 1) in core_util._EXIF_CACHE


# ============================================================
# clear / size 工具
# ============================================================


class TestCacheUtil:
    def test_clear_resets_size(self):
        _exif_cache_put(("/a", 1), {"x": 1})
        _exif_cache_put(("/b", 1), {"x": 2})
        assert exif_cache_size() == 2
        clear_exif_cache()
        assert exif_cache_size() == 0

    def test_size_after_no_inserts(self):
        assert exif_cache_size() == 0


# ============================================================
# get_exif 命中缓存（mock subprocess）
# ============================================================


class TestGetExifCached:
    def test_first_call_invokes_exiftool_then_caches(self, fake_jpeg):
        fake_output = b"Make: TestMake\nCameraModelName: TestModel\n"
        with patch("core.util.subprocess.check_output", return_value=fake_output) as mock_exif:
            r1 = get_exif(str(fake_jpeg))
            assert mock_exif.call_count == 1
            assert r1.get("Make") == "TestMake"
            # 缓存应已填入
            assert exif_cache_size() == 1

            # 二次调用 — 不再触发 subprocess
            r2 = get_exif(str(fake_jpeg))
            assert mock_exif.call_count == 1  # 仍是 1，未再调用
            assert r2 == r1

    def test_failure_returns_empty_and_does_not_cache(self, fake_jpeg):
        with patch(
            "core.util.subprocess.check_output", side_effect=RuntimeError("boom")
        ):
            r = get_exif(str(fake_jpeg))
        assert r == {}
        assert exif_cache_size() == 0

    def test_mtime_change_invalidates_cache(self, fake_jpeg):
        outputs = [
            b"Make: First\n",
            b"Make: Second\n",
        ]
        call_idx = {"i": 0}

        def fake_check(*args, **kwargs):
            i = call_idx["i"]
            call_idx["i"] += 1
            return outputs[i]

        with patch("core.util.subprocess.check_output", side_effect=fake_check):
            r1 = get_exif(str(fake_jpeg))
            assert r1.get("Make") == "First"

            # 修改 mtime → 缓存 key 改变 → 再次触发 exiftool
            st = os.stat(fake_jpeg)
            os.utime(fake_jpeg, (st.st_atime, st.st_mtime + 5.0))
            r2 = get_exif(str(fake_jpeg))
            assert r2.get("Make") == "Second"
            assert call_idx["i"] == 2


# ============================================================
# get_exif_batch 缓存命中
# ============================================================


class TestGetExifBatchCached:
    def test_all_hits_skip_exiftool(self, tmp_path):
        # 准备两个文件
        a = tmp_path / "a.jpg"
        b = tmp_path / "b.jpg"
        a.write_bytes(b"a")
        b.write_bytes(b"b")
        # 直接预热缓存
        ka = _exif_cache_key(a)
        kb = _exif_cache_key(b)
        assert ka and kb
        _exif_cache_put(ka, {"Make": "A"})
        _exif_cache_put(kb, {"Make": "B"})

        with patch("core.util.subprocess.check_output") as mock_exif:
            r = get_exif_batch([str(a), str(b)])
        # 全部命中缓存 → 不应调用 exiftool
        mock_exif.assert_not_called()
        assert r[str(a)].get("Make") == "A"
        assert r[str(b)].get("Make") == "B"

    def test_partial_miss_triggers_exiftool_for_misses_only(self, tmp_path):
        a = tmp_path / "a.jpg"
        b = tmp_path / "b.jpg"
        a.write_bytes(b"a")
        b.write_bytes(b"b")

        # 只预热 a 的缓存
        ka = _exif_cache_key(a)
        assert ka
        _exif_cache_put(ka, {"Make": "Cached-A"})

        # b 仍 miss → exiftool 应被调用，且参数中只含 b
        fake_output = (
            f"======== {b}\nMake: Fresh-B\n".encode()
        )
        with patch(
            "core.util.subprocess.check_output", return_value=fake_output
        ) as mock_exif:
            r = get_exif_batch([str(a), str(b)])

        assert mock_exif.call_count == 1
        called_args = mock_exif.call_args[0][0]
        # 命令行参数中应包含 b，但不含 a
        assert any(str(b) == arg for arg in called_args)
        assert all(str(a) != arg for arg in called_args)
        assert r[str(a)].get("Make") == "Cached-A"
        assert r[str(b)].get("Make") == "Fresh-B"

    def test_writes_back_misses_into_cache(self, tmp_path):
        a = tmp_path / "a.jpg"
        a.write_bytes(b"a")
        fake_output = b"Make: NewVal\n"
        with patch("core.util.subprocess.check_output", return_value=fake_output):
            get_exif_batch([str(a)])
        # 写回缓存
        ka = _exif_cache_key(a)
        assert ka in core_util._EXIF_CACHE
        assert core_util._EXIF_CACHE[ka].get("Make") == "NewVal"

    def test_empty_paths_returns_empty_dict(self):
        with patch("core.util.subprocess.check_output") as mock_exif:
            r = get_exif_batch([])
        mock_exif.assert_not_called()
        assert r == {}
