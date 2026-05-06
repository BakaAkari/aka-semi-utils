"""保证配置层已统一到 [`core.config_loader`](core/config_loader.py:1)。

历史上 [`core/configs.py`](core/configs.py:1) 与 ``core/config_loader.py`` 存在两套定义，
互不同步。本测试守护：``core.configs`` 现已退化为纯转发别名。
"""
from __future__ import annotations

from pathlib import Path

from core import config_loader, configs


def test_path_aliases_match() -> None:
    assert configs.fonts_dir == config_loader.FONTS_DIR
    assert configs.logos_dir == config_loader.LOGOS_DIR
    assert configs.templates_dir == config_loader.TEMPLATES_DIR


def test_load_config_is_load_config_ini() -> None:
    """老 API ``configs.load_config`` 应等价于新 ``config_loader.load_config_ini``。"""
    assert configs.load_config is config_loader.load_config


def test_paths_are_pathlib_objects() -> None:
    assert isinstance(config_loader.FONTS_DIR, Path)
    assert isinstance(config_loader.LOGOS_DIR, Path)
    assert isinstance(config_loader.TEMPLATES_DIR, Path)
    assert isinstance(config_loader.PROJECT_ROOT, Path)


def test_load_project_info_returns_dict() -> None:
    info = config_loader.load_project_info()
    assert isinstance(info, dict)
    assert "project" in info
