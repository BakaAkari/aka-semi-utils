"""水印角落字号下拉菜单行为测试。"""

from __future__ import annotations

import pytest

from gui.config_panel import CornerSection
from gui.models import AppState, CornerConfig, FieldChip
from gui.template_assembler import _build_watermark_config


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def _state_with_left_top(font_size_ratio: float) -> AppState:
    state = AppState()
    state.left_top = CornerConfig(
        chips=[FieldChip(field_id="camera_model")],
        font_size_ratio=font_size_ratio,
    )
    return state


def test_corner_size_combo_exposes_inherit_option(qapp):
    state = _state_with_left_top(0.0)
    section = CornerSection("left_top", state)

    assert section.corner_size.currentData() == 0.0
    assert state.left_top.font_size_ratio == 0.0
    assert section.corner_size.findData(0.0) >= 0


def test_corner_size_combo_updates_state_and_watermark_height_ratio(qapp):
    state = _state_with_left_top(0.0)
    section = CornerSection("left_top", state)

    section.corner_size.setCurrentIndex(section.corner_size.findData(0.06))

    assert state.left_top.font_size_ratio == 0.06
    node = _build_watermark_config(state)["left_top"]
    assert node["height_ratio"] == 0.06


def test_corner_size_combo_reset_returns_to_inherit(qapp):
    state = _state_with_left_top(0.06)
    section = CornerSection("left_top", state)

    section._reset_corner_style()

    assert section.corner_size.currentData() == 0.0
    assert state.left_top.font_size_ratio == 0.0
    node = _build_watermark_config(state)["left_top"]
    assert "height_ratio" not in node


def test_legacy_too_small_font_size_normalizes_to_safe_option(qapp):
    state = _state_with_left_top(0.018)
    section = CornerSection("left_top", state)

    assert section.corner_size.currentData() == 0.02
    assert state.left_top.font_size_ratio == 0.02
    node = _build_watermark_config(state)["left_top"]
    assert node["height_ratio"] == 0.02
