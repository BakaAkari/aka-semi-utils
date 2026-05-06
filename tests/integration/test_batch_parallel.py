"""测试 [`processor.batch`](processor/batch.py:1) — 并行批处理（Phase 2.1）。

要点：
- ``_resolve_max_workers`` 在各种输入下行为正确；
- 串行模式（max_workers=0）等价于逐文件循环，无 ProcessPool 开销；
- 并行模式（max_workers>0）真实加速 + 输出与串行**字节级一致**；
- 单文件失败不影响其他任务（错误隔离）；
- ``on_progress`` 回调收到正确的 ``(idx, total, item)``；
- ``build_tasks`` 正确分发 EXIF + 调用 ``render_per_file``；
- 取消（``cancel_check``）能阻止新任务但不破坏已 dispatch 的。
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image

import processor  # noqa: F401  - 触发处理器注册
from processor.batch import (
    BatchResult,
    BatchResultItem,
    BatchTask,
    _resolve_max_workers,
    build_tasks,
    process_batch,
)

# ============================================================
# _resolve_max_workers
# ============================================================


def test_resolve_max_workers_zero_returns_zero():
    assert _resolve_max_workers(0, 5) == 0


def test_resolve_max_workers_no_tasks_returns_zero():
    assert _resolve_max_workers(4, 0) == 0


def test_resolve_max_workers_negative_uses_cpu_minus_one():
    import multiprocessing as mp

    expected = max(1, mp.cpu_count() - 1)
    assert _resolve_max_workers(-1, 100) == expected


def test_resolve_max_workers_caps_to_tasks():
    """请求 8 个 worker 但只有 3 个任务 → 实际 ≤ 3。"""
    assert _resolve_max_workers(8, 3) <= 3


def test_resolve_max_workers_at_least_one():
    """非零请求至少返回 1。"""
    assert _resolve_max_workers(1, 1) >= 1


# ============================================================
# 公用辅助 — 构造可运行的最小 pipeline
# ============================================================


def _make_input(tmp_path: Path, name: str, color=(200, 100, 50), size=(32, 16)) -> Path:
    p = tmp_path / name
    Image.new("RGB", size, color).save(p, format="JPEG", quality=95)
    return p


def _minimal_processors():
    return [{"processor_name": "resize", "ratio": 0.5}]


def _build_tasks_n(tmp_path: Path, n: int) -> list[BatchTask]:
    out_dir = tmp_path / "out"
    out_dir.mkdir(exist_ok=True)
    tasks = []
    for i in range(n):
        src = _make_input(tmp_path, f"src_{i}.jpg", color=(100 + i * 30, 50, 200))
        tasks.append(
            BatchTask(
                input_path=str(src),
                output_path=str(out_dir / f"out_{i}.jpg"),
                processors=_minimal_processors(),
                pre_loaded_exif={"FileIdx": str(i)},
                emit_exif_json=False,
            )
        )
    return tasks


# ============================================================
# 串行模式
# ============================================================


def test_serial_mode_processes_all_tasks(tmp_path):
    tasks = _build_tasks_n(tmp_path, 3)
    result = process_batch(tasks, max_workers=0)

    assert isinstance(result, BatchResult)
    assert result.total == 3
    assert result.success_count == 3
    assert result.fail_count == 0
    assert result.all_success is True

    # 每个输出文件实际生成
    for t in tasks:
        assert os.path.exists(t.output_path)


def test_serial_mode_progress_callback(tmp_path):
    tasks = _build_tasks_n(tmp_path, 4)
    progress_calls: list[tuple[int, int, BatchResultItem]] = []

    def cb(done, total, item):
        progress_calls.append((done, total, item))

    process_batch(tasks, max_workers=0, on_progress=cb)

    assert len(progress_calls) == 4
    # idx 应递增 1..4，total 始终 4
    assert [c[0] for c in progress_calls] == [1, 2, 3, 4]
    assert all(c[1] == 4 for c in progress_calls)
    assert all(c[2].success for c in progress_calls)


def test_serial_mode_cancel_stops_early(tmp_path):
    tasks = _build_tasks_n(tmp_path, 5)

    state = {"count": 0}

    def cancel():
        state["count"] += 1
        # 第一次问就取消（应当一项也不处理）
        return state["count"] > 1

    # 取消逻辑：循环开头检查；count=1 不取消，处理 1 项；
    # count=2 时取消，停止。
    result = process_batch(tasks, max_workers=0, cancel_check=cancel)
    assert result.success_count <= 1


# ============================================================
# 并行模式
# ============================================================


def test_parallel_mode_processes_all_tasks(tmp_path):
    tasks = _build_tasks_n(tmp_path, 4)
    result = process_batch(tasks, max_workers=2)

    assert result.total == 4
    assert result.success_count == 4
    assert result.all_success is True
    for t in tasks:
        assert os.path.exists(t.output_path)


def test_parallel_output_matches_serial(tmp_path):
    """并行与串行的输出在像素级别完全一致（确定性）。"""
    # 串行
    serial_dir = tmp_path / "serial"
    serial_dir.mkdir()
    serial_tasks = []
    for i in range(3):
        src = _make_input(tmp_path, f"src_{i}.jpg", color=(40 + i * 50, 80, 200))
        serial_tasks.append(
            BatchTask(
                input_path=str(src),
                output_path=str(serial_dir / f"out_{i}.jpg"),
                processors=_minimal_processors(),
            )
        )
    process_batch(serial_tasks, max_workers=0)

    # 并行（使用相同的输入文件）
    parallel_dir = tmp_path / "parallel"
    parallel_dir.mkdir()
    parallel_tasks = []
    for i in range(3):
        src = tmp_path / f"src_{i}.jpg"
        parallel_tasks.append(
            BatchTask(
                input_path=str(src),
                output_path=str(parallel_dir / f"out_{i}.jpg"),
                processors=_minimal_processors(),
            )
        )
    process_batch(parallel_tasks, max_workers=2)

    # 逐字节比较
    for i in range(3):
        s = (serial_dir / f"out_{i}.jpg").read_bytes()
        p = (parallel_dir / f"out_{i}.jpg").read_bytes()
        assert s == p, f"out_{i}.jpg 串行与并行结果不一致"


def test_parallel_progress_callback_count(tmp_path):
    tasks = _build_tasks_n(tmp_path, 5)
    progress_count = {"n": 0}

    def cb(done, total, item):
        progress_count["n"] += 1
        assert total == 5
        assert item.success

    process_batch(tasks, max_workers=2, on_progress=cb)
    assert progress_count["n"] == 5


# ============================================================
# 错误隔离
# ============================================================


def test_error_isolation_one_bad_does_not_kill_batch(tmp_path):
    """混入一个不存在的输入路径，应只该项失败，其他成功。"""
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    good1 = _make_input(tmp_path, "good1.jpg")
    good2 = _make_input(tmp_path, "good2.jpg")

    tasks = [
        BatchTask(
            input_path=str(good1),
            output_path=str(out_dir / "g1.jpg"),
            processors=_minimal_processors(),
        ),
        BatchTask(
            input_path=str(tmp_path / "DOES_NOT_EXIST.jpg"),
            output_path=str(out_dir / "bad.jpg"),
            processors=_minimal_processors(),
        ),
        BatchTask(
            input_path=str(good2),
            output_path=str(out_dir / "g2.jpg"),
            processors=_minimal_processors(),
        ),
    ]

    result = process_batch(tasks, max_workers=2)
    assert result.total == 3
    assert result.success_count == 2
    assert result.fail_count == 1

    # 失败项含有 error 与 traceback
    failed = [r for r in result.items if not r.success]
    assert len(failed) == 1
    assert failed[0].error is not None
    assert failed[0].traceback is not None
    assert "DOES_NOT_EXIST" in failed[0].input_path


def test_serial_error_isolation(tmp_path):
    """串行模式同样保证错误隔离。"""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    good = _make_input(tmp_path, "good.jpg")
    tasks = [
        BatchTask(input_path=str(tmp_path / "missing.jpg"),
                  output_path=str(out_dir / "x.jpg"),
                  processors=_minimal_processors()),
        BatchTask(input_path=str(good),
                  output_path=str(out_dir / "g.jpg"),
                  processors=_minimal_processors()),
    ]
    result = process_batch(tasks, max_workers=0)
    assert result.success_count == 1
    assert result.fail_count == 1


# ============================================================
# build_tasks
# ============================================================


def test_build_tasks_with_pre_loaded_exif_map(tmp_path):
    """显式提供 EXIF map 时不应触发 get_exif_batch。"""
    f1 = str(_make_input(tmp_path, "f1.jpg"))
    f2 = str(_make_input(tmp_path, "f2.jpg"))
    pre = {f1: {"Make": "A"}, f2: {"Make": "B"}}

    tasks = build_tasks(
        files=[f1, f2],
        processors_template=_minimal_processors(),
        resolve_output=lambda p: p.replace(".jpg", "_out.jpg"),
        pre_loaded_exif_map=pre,
    )

    assert len(tasks) == 2
    assert tasks[0].pre_loaded_exif == {"Make": "A"}
    assert tasks[1].pre_loaded_exif == {"Make": "B"}
    assert tasks[0].output_path.endswith("f1_out.jpg")


def test_build_tasks_render_per_file_invoked(tmp_path):
    f = str(_make_input(tmp_path, "render.jpg"))
    captured = []

    def fake_render(template, exif, file_path):
        captured.append((tuple(map(tuple, [d.items() for d in template])), exif, file_path))
        # 返回不同的 processors（验证调用结果传到 task）
        return [{"processor_name": "blur", "radius": 1}]

    tasks = build_tasks(
        files=[f],
        processors_template=_minimal_processors(),
        resolve_output=lambda p: p + ".out",
        render_per_file=fake_render,
        pre_loaded_exif_map={f: {"k": "v"}},
    )

    assert len(captured) == 1
    assert captured[0][1] == {"k": "v"}
    assert captured[0][2] == f
    assert tasks[0].processors == [{"processor_name": "blur", "radius": 1}]


def test_build_tasks_emit_exif_json_propagates(tmp_path):
    f = str(_make_input(tmp_path, "x.jpg"))
    tasks = build_tasks(
        files=[f],
        processors_template=_minimal_processors(),
        resolve_output=lambda p: p + ".out.jpg",
        emit_exif_json=True,
        pre_loaded_exif_map={f: {}},
    )
    assert tasks[0].emit_exif_json is True
