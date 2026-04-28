"""配置加载器 — 负责 config.ini 和 user.json 的读写、验证、默认值回退。"""

import json
import logging
import shutil
from configparser import ConfigParser, Error as ConfigParserError
from pathlib import Path

logger = logging.getLogger(__name__)

# 路径常量
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
CONFIG_INI_PATH = CONFIG_DIR / "config.ini"
USER_TEMPLATE_PATH = CONFIG_DIR / "user.json"
DEFAULT_TEMPLATE_PATH = CONFIG_DIR / "templates" / "标准水印.json"
FONTS_DIR = CONFIG_DIR / "fonts"
LOGOS_DIR = CONFIG_DIR / "logos"

# 默认值
DEFAULT_CONFIG = """[DEFAULT]
output_folder = {source_dir}/logo
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
signature_color = black

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
        with open(CONFIG_INI_PATH, "r", encoding="utf-8") as f:
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
        with open(USER_TEMPLATE_PATH, "r", encoding="utf-8") as f:
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
    raw = config.get("DEFAULT", "output_folder", fallback="{source_dir}/logo").strip()
    remember = config.getboolean("DEFAULT", "remember_output", fallback=True)

    if not raw:
        raw = "{source_dir}/logo"

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

    # 如果路径以 /logo 结尾，保持不变；否则自动追加
    if "logo" not in path.name.lower():
        path = path / "logo"

    # 验证回退
    if remember:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError:
            logger.warning(f"输出路径不可写: {path}，回退到默认")
            if source_dir is not None:
                path = Path(source_dir) / "logo"
            else:
                path = Path.home() / "Desktop" / "logo"
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
