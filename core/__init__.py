"""``core`` 包入口。

历史上此处暴露过 ``CONFIG_PATH`` / ``PROJECT_INFO`` 字符串常量，
现已迁移至 [`core.config_loader`](core/config_loader.py:1)：
- ``CONFIG_INI_PATH`` 替代 ``CONFIG_PATH``
- ``PROJECT_INFO_PATH`` 替代 ``PROJECT_INFO``

为保持向后兼容，原名仍以 ``Path`` → ``str`` 转发的方式可用。
"""
from __future__ import annotations

from core.config_loader import CONFIG_INI_PATH, PROJECT_INFO_PATH

# 兼容旧字符串常量（部分老代码以字符串路径传给 configparser）
CONFIG_PATH = str(CONFIG_INI_PATH)
PROJECT_INFO = str(PROJECT_INFO_PATH)

__all__ = ["CONFIG_INI_PATH", "CONFIG_PATH", "PROJECT_INFO", "PROJECT_INFO_PATH"]
