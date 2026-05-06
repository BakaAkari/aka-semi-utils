"""向后兼容 shim — 原配置入口现已并入 [`core.config_loader`](core/config_loader.py:1)。

.. deprecated::
    所有新代码请直接 ``from core.config_loader import ...``。
    本模块仅作为迁移期的别名转发，未来版本将被移除。
"""
from __future__ import annotations

from core.config_loader import (
    fonts_dir,
    load_config,
    load_project_info,
    logos_dir,
    templates_dir,
)

__all__ = [
    "fonts_dir",
    "load_config",
    "load_project_info",
    "logos_dir",
    "templates_dir",
]
