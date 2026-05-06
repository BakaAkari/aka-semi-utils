"""Phase 6.1 — AppState 持久化测试。

覆盖：
- 全字段保存 (corners / logo / advanced / custom_text / output / template)
- 全字段加载 + 类型还原
- 缺失文件 → 默认值
- 损坏 JSON → 默认值（不抛异常）
- 老格式（仅 template + output）兼容加载
- 未知字段忽略
- 部分字段缺失 → 默认值兜底
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# 必须有 QApplication 才能创建 QObject 子类
pytest.importorskip("PyQt6")
from PyQt6.QtCore import QCoreApplication

from gui.models import (
    USER_CONFIG_VERSION,
    AdvancedConfig,
    AppState,
    CornerConfig,
    LogoConfig,
    OutputConfig,
)


@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    return tmp_path


def _user_json(project_root: Path) -> Path:
    return project_root / "config" / "user.json"


# -------- 保存 --------

def test_save_creates_file_with_all_sections(qapp, project_root):
    state = AppState()
    state.left_top = CornerConfig(fields=["相机型号", "镜头型号"], separator=" | ", color="#FF0000")
    state.logo = LogoConfig(enabled="custom", position="left", color="#123456", custom_path="/tmp/x.png")
    state.custom_text = "测试文本"
    state.advanced = AdvancedConfig(global_font="Roboto-Bold.ttf", quality=88, blur_radius=12)
    state.output = OutputConfig(path="/tmp/out", override=False)
    state.current_template = "标准水印"

    assert state.save_to_disk(project_root) is True

    data = json.loads(_user_json(project_root).read_text(encoding="utf-8"))
    assert data["version"] == USER_CONFIG_VERSION
    assert data["template"] == "标准水印"
    assert data["output"] == {"path": "/tmp/out", "override": False}
    assert data["corners"]["left_top"]["fields"] == ["相机型号", "镜头型号"]
    assert data["corners"]["left_top"]["color"] == "#FF0000"
    assert data["logo"]["custom_path"] == "/tmp/x.png"
    assert data["advanced"]["quality"] == 88
    assert data["advanced"]["blur_radius"] == 12
    assert data["custom_text"] == "测试文本"


def test_save_atomic_no_partial_file(qapp, project_root):
    state = AppState()
    state.save_to_disk(project_root)

    # .tmp 文件应已被 rename，不会残留
    tmp = _user_json(project_root).with_suffix(".json.tmp")
    assert not tmp.exists()
    assert _user_json(project_root).exists()


def test_save_creates_config_dir_if_missing(qapp, tmp_path):
    # 确保 config 目录会被自动创建
    state = AppState()
    assert not (tmp_path / "config").exists()
    assert state.save_to_disk(tmp_path) is True
    assert (tmp_path / "config" / "user.json").exists()


def test_save_without_project_root_returns_false(qapp):
    state = AppState()
    # 未调用 load_from_disk，project_root 未设置
    assert state.save_to_disk() is False


# -------- 加载 --------

def test_load_full_roundtrip(qapp, project_root, tmp_path):
    """Phase 9：``selected_files`` 持久化但启动过滤不存在的文件 — 用真实文件验证保留路径。"""
    # 准备两张真实存在的图片，避免被启动过滤逻辑剔除
    real1 = tmp_path / "img1.jpg"
    real1.write_bytes(b"\xff\xd8\xff\xd9")
    real2 = tmp_path / "img2.jpg"
    real2.write_bytes(b"\xff\xd8\xff\xd9")

    src = AppState()
    src.left_top = CornerConfig(fields=["A", "B"], separator="-", color="#AAA")
    src.right_bottom = CornerConfig(fields=["X"], color="#BBB")
    src.logo = LogoConfig(enabled="disabled", color="#CCC")
    src.custom_text = "hello"
    src.advanced = AdvancedConfig(quality=70, ratio_enabled=True, ratio="16:9")
    src.output = OutputConfig(path="/o", override=False)
    src.current_template = "tpl"
    src.selected_files = [str(real1), str(real2)]
    src.save_to_disk(project_root)

    dst = AppState()
    assert dst.load_from_disk(project_root) is True

    assert dst.current_template == "tpl"
    assert dst.left_top.fields == ["A", "B"]
    assert dst.left_top.separator == "-"
    assert dst.left_top.color == "#AAA"
    assert dst.right_bottom.fields == ["X"]
    assert dst.logo.enabled == "disabled"
    assert dst.custom_text == "hello"
    assert dst.advanced.quality == 70
    assert dst.advanced.ratio_enabled is True
    assert dst.output.path == "/o"
    assert dst.output.override is False
    assert dst.selected_files == [str(real1), str(real2)]


def test_load_filters_nonexistent_selected_files(qapp, project_root, tmp_path):
    """Phase 9 新契约：磁盘里存的不存在文件路径，加载后应被丢弃，仅保留真实存在的。"""
    real = tmp_path / "exists.jpg"
    real.write_bytes(b"\xff\xd8\xff\xd9")

    src = AppState()
    src.selected_files = [str(real), "/img/ghost.jpg", "/already/deleted.png"]
    src.save_to_disk(project_root)

    dst = AppState()
    assert dst.load_from_disk(project_root) is True
    # 仅保留真实存在的文件
    assert dst.selected_files == [str(real)]


def test_load_missing_file_uses_defaults(qapp, project_root):
    state = AppState()
    assert state.load_from_disk(project_root) is False
    assert state.current_template == "default"
    assert state.left_top.fields == []
    assert state.advanced.quality == 95


def test_load_corrupt_json_uses_defaults(qapp, project_root):
    _user_json(project_root).write_text("{not valid json", encoding="utf-8")
    state = AppState()
    assert state.load_from_disk(project_root) is False
    # 不抛异常，回退默认
    assert state.current_template == "default"


def test_load_legacy_format_compat(qapp, project_root):
    """老格式：只有 template + output，无 version / corners 等。"""
    _user_json(project_root).write_text(
        json.dumps({
            "template": "old_template",
            "output": {"path": "/legacy", "override": True},
        }),
        encoding="utf-8",
    )
    state = AppState()
    assert state.load_from_disk(project_root) is True
    assert state.current_template == "old_template"
    assert state.output.path == "/legacy"
    # 缺失字段走默认
    assert state.left_top.fields == []
    assert state.advanced.quality == 95


def test_load_unknown_fields_ignored(qapp, project_root):
    """加入字段在 dataclass 中不存在时不应报错。"""
    _user_json(project_root).write_text(
        json.dumps({
            "version": USER_CONFIG_VERSION,
            "advanced": {"quality": 80, "future_unknown_key": "ignored"},
            "corners": {"left_top": {"fields": ["x"], "weird_key": 1}},
        }),
        encoding="utf-8",
    )
    state = AppState()
    assert state.load_from_disk(project_root) is True
    assert state.advanced.quality == 80
    assert state.left_top.fields == ["x"]


def test_load_partial_corners_other_corners_default(qapp, project_root):
    _user_json(project_root).write_text(
        json.dumps({
            "version": USER_CONFIG_VERSION,
            "corners": {"left_top": {"fields": ["only_lt"]}},
        }),
        encoding="utf-8",
    )
    state = AppState()
    state.load_from_disk(project_root)
    assert state.left_top.fields == ["only_lt"]
    # 其他三角应是默认值
    assert state.right_top.fields == []
    assert state.left_bottom.fields == []
    assert state.right_bottom.fields == []


# -------- 自动保存 --------

def test_autosave_triggered_by_signal(qapp, project_root):
    """Phase 6.2：触发 *_changed 信号后 debounce 写盘。"""
    state = AppState()
    state.load_from_disk(project_root)  # 初始化 _project_root + _autosave_enabled

    # 先让 file 不存在，确认 autosave 真的写入
    _user_json(project_root).unlink(missing_ok=True)

    state.set_corner_config("left_top", CornerConfig(fields=["相机型号"]))
    # 强制触发（不等 debounce）
    state.flush_autosave()

    assert _user_json(project_root).exists()
    data = json.loads(_user_json(project_root).read_text(encoding="utf-8"))
    assert data["corners"]["left_top"]["fields"] == ["相机型号"]


def test_flush_autosave_cancels_pending_timer(qapp, project_root):
    state = AppState()
    state.load_from_disk(project_root)

    state.set_output("/x", True)
    # debounce 计时器应已启动
    assert state._save_timer.isActive()

    state.flush_autosave()
    # flush 后计时器应停止
    assert not state._save_timer.isActive()


def test_autosave_skipped_during_processing(qapp, project_root):
    """处理中不应触发 autosave，避免 ProcessThread 频繁写盘。"""
    state = AppState()
    state.load_from_disk(project_root)

    state.set_processing(True, 50, "处理中")
    # 任何变更不会启动计时器
    state.set_output("/y", False)
    assert not state._save_timer.isActive()


def test_autosave_disabled_before_load(qapp, project_root):
    """load_from_disk 未调用前，autosave 不应启动（避免空状态覆盖磁盘）。"""
    state = AppState()
    state.set_corner_config("left_top", CornerConfig(fields=["bad"]))
    assert not state._save_timer.isActive()
