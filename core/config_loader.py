"""配置加载器 — 项目级**唯一**配置入口。

负责：
- ``config.ini`` 与 ``user.json`` 的读写、验证、默认值回退
- 项目内所有可配置路径常量的定义（FONTS_DIR / LOGOS_DIR / TEMPLATES_DIR …）
- 加载项目元信息（``pyproject.toml``）

历史上曾存在 [`core/configs.py`](core/configs.py:1) 作为另一份配置入口，
现已退化为本模块的兼容别名 shim。所有新代码请直接 ``from core.config_loader import ...``。
"""

from __future__ import annotations

import json
import logging
import shutil  # noqa: F401  保留以兼容外部 import
import tomllib
from configparser import ConfigParser
from configparser import Error as ConfigParserError
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─────────── 路径常量 ───────────
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
CONFIG_INI_PATH = CONFIG_DIR / "config.ini"
USER_TEMPLATE_PATH = CONFIG_DIR / "user.json"
DEFAULT_TEMPLATE_PATH = CONFIG_DIR / "templates" / "标准水印.json"
FONTS_DIR = CONFIG_DIR / "fonts"
LOGOS_DIR = CONFIG_DIR / "logos"
TEMPLATES_DIR = CONFIG_DIR / "templates"
PROJECT_INFO_PATH = PROJECT_ROOT / "pyproject.toml"

# 兼容历史（旧名）：原 [`core/configs.py`](core/configs.py:8) 暴露的字段
fonts_dir = FONTS_DIR
logos_dir = LOGOS_DIR
templates_dir = TEMPLATES_DIR

# 默认值
DEFAULT_CONFIG = """[DEFAULT]
output_folder = {source_dir}/output
remember_output = True
quality = 60
subsampling = 2
supported_file_suffixes = .jpeg,.jpg,.png,.heic
author_name =
author_font = NotoSansCJKsc-Bold.otf
logo_path =
override_existed = True
signature_enabled = False
signature_path =

[gui]
window_width = 480
window_height = 420

[custom_text]
left_top =
left_bottom =
right_top =
right_bottom =
"""


def _ensure_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    (CONFIG_DIR / "templates").mkdir(parents=True, exist_ok=True)


def create_default_config() -> ConfigParser:
    """创建默认 config.ini 并写入磁盘。"""
    _ensure_dir()
    config = ConfigParser()
    config.read_string(DEFAULT_CONFIG)
    with open(CONFIG_INI_PATH, "w", encoding="utf-8") as f:
        config.write(f)
    logger.info("已创建默认 config.ini")
    return config


def load_config_ini() -> ConfigParser:
    """
    加载 config.ini。若不存在或损坏则创建默认配置。
    """
    _ensure_dir()
    if not CONFIG_INI_PATH.exists():
        return create_default_config()

    config = ConfigParser()
    try:
        with open(CONFIG_INI_PATH, encoding="utf-8") as f:
            config.read_file(f)
    except ConfigParserError as e:
        logger.error(f"config.ini 语法错误: {e}")
        return create_default_config()
    except Exception as e:
        logger.error(f"config.ini 读取失败: {e}")
        return create_default_config()

    return config


def save_config_ini(config: ConfigParser) -> None:
    """保存 config.ini，自动补全缺失的必要 section。"""
    _ensure_dir()
    for section in ["gui", "custom_text"]:
        if not config.has_section(section):
            config.add_section(section)
    with open(CONFIG_INI_PATH, "w", encoding="utf-8") as f:
        config.write(f)


def create_default_user_template() -> dict:
    """创建默认 user.json 并写入磁盘。"""
    _ensure_dir()
    default = {
        "version": 1,
        "layout": {
            "left_top": {"source": "exif:CameraModelName", "font": "NotoSansCJKsc-Bold.otf", "color": "black"},
            "left_bottom": {"source": "exif:params", "font": "NotoSansCJKsc-Bold.otf", "color": "#242424"},
            "right_top": {"source": "author", "font": "NotoSansCJKsc-Bold.otf", "color": "#242424"},
            "right_bottom": {"source": "exif:DateTimeOriginal", "font": "NotoSansCJKsc-Bold.otf", "color": "#242424"},
        },
        "logo": {"enabled": True, "source": "auto", "position": "right", "delimiter_color": "#D8D8D6"},
        "background": {"color": "white"},
    }
    with open(USER_TEMPLATE_PATH, "w", encoding="utf-8") as f:
        json.dump(default, f, ensure_ascii=False, indent=2)
    logger.info("已创建默认 user.json")
    return default


def load_user_template() -> dict:
    """
    加载 user.json。若不存在或损坏则复制默认模板。
    """
    _ensure_dir()
    if not USER_TEMPLATE_PATH.exists():
        return create_default_user_template()

    try:
        with open(USER_TEMPLATE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("user.json 根节点不是对象")
        return data
    except (json.JSONDecodeError, ValueError, OSError) as e:
        logger.warning(f"user.json 损坏或读取失败: {e}，将复制默认模板")
        return create_default_user_template()


def save_user_template(data: dict) -> None:
    """保存 user.json。"""
    _ensure_dir()
    with open(USER_TEMPLATE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── 便捷 getter ──

def get_output_folder(config: ConfigParser, source_dir: Path | str | None = None) -> Path:
    """
    解析输出路径。支持变量和回退。
    """
    raw = config.get("DEFAULT", "output_folder", fallback="{source_dir}/output").strip()
    remember = config.getboolean("DEFAULT", "remember_output", fallback=True)

    if not raw:
        raw = "{source_dir}/output"

    # 变量替换
    if raw.startswith("{"):
        if source_dir is not None:
            src = Path(source_dir)
            raw = raw.replace("{source_dir}", str(src))
            raw = raw.replace("{source_parent}", str(src.parent))
        raw = raw.replace("{desktop}", str(Path.home() / "Desktop"))
        raw = raw.replace("{home}", str(Path.home()))

    path = Path(raw).expanduser()
    if not path.is_absolute() and source_dir is not None:
        path = Path(source_dir) / path

    # 如果路径以 /output 结尾，保持不变；否则自动追加
    if "output" not in path.name.lower():
        path = path / "output"

    # 验证回退
    if remember:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            logger.warning(f"输出路径不可写: {path}，回退到默认")
            path = Path(source_dir) / "output" if source_dir is not None else Path.home() / "Desktop" / "output"
            path.mkdir(parents=True, exist_ok=True)

    return path


def get_supported_suffixes(config: ConfigParser) -> set[str]:
    raw = config.get("DEFAULT", "supported_file_suffixes", fallback=".jpeg,.jpg,.png,.heic")
    return {s.strip().lower() for s in raw.split(",") if s.strip()}


def get_custom_text(config: ConfigParser, corner: str = "") -> str:
    """读取自定义文本。优先读取全局 text，其次回退到按角读取（兼容旧版）。"""
    # 新版全局自定义文本
    global_text = config.get("custom_text", "text", fallback="").strip()
    if global_text:
        return global_text
    # 旧版按角读取
    if corner:
        return config.get("custom_text", corner, fallback="").strip()
    return ""


def get_logo_path(config: ConfigParser) -> Path | None:
    """读取 logo_path，空则返回 None。"""
    raw = config.get("DEFAULT", "logo_path", fallback="").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        # 相对路径基于项目根目录
        path = PROJECT_ROOT / path
    return path if path.exists() else None


# ─────────── 兼容别名（原 core/configs.py 的 API） ───────────

def load_config() -> ConfigParser:
    """读取 ``config.ini`` 的快捷方式。

    .. deprecated::
        新代码请直接调用 [`load_config_ini`](core/config_loader.py:65)。
        此函数仅作为迁移期的桥接，保持与历史调用的二进制兼容。
    """
    return load_config_ini()


def load_project_info() -> dict[str, Any]:
    """读取 ``pyproject.toml`` 项目元信息。"""
    with open(PROJECT_INFO_PATH, "rb") as f:
        return tomllib.load(f)
