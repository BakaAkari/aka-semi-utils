import io
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from contextlib import suppress
from functools import wraps
from pathlib import Path
from typing import Any

from jinja2 import Template
from PIL import Image

from core.config_loader import TEMPLATES_DIR as templates_dir
from core.jinja2renders import auto_logo, vh, vw
from core.logger import logger

# ---------------------------------------------------------------------------
# Phase 5.2：进程内 EXIF 缓存
# ---------------------------------------------------------------------------
# 设计原则：
# - 缓存 key = (绝对路径, mtime_ns)；文件改动则 mtime 变化，自动失效；
# - 仅缓存"成功读取"的结果；空 dict 不缓存（避免吞掉一过性失败导致永久空）；
# - 容量上限 ``_EXIF_CACHE_MAXSIZE`` 防止长时间运行内存膨胀；超额时按插入顺序
#   FIFO 淘汰（dict 在 Python 3.7+ 保留插入序，无需 OrderedDict）；
# - 跨进程隔离：每个 worker 独立一份；主进程的预读结果通过 ``pre_loaded_exif``
#   显式传递给 worker，缓存只在"同一进程内多次调用"时起效。
# ---------------------------------------------------------------------------
_EXIF_CACHE: dict[tuple[str, int], dict] = {}
_EXIF_CACHE_MAXSIZE = 512


def _exif_cache_key(path: str | Path) -> tuple[str, int] | None:
    """生成 ``(abspath, mtime_ns)`` 缓存 key；文件不存在返回 ``None``（不缓存）。"""
    try:
        st = os.stat(path)
        return (os.path.abspath(str(path)), st.st_mtime_ns)
    except OSError:
        return None


def _exif_cache_put(key: tuple[str, int], value: dict) -> None:
    """写入缓存，超额时按 FIFO 淘汰最早一项。"""
    if not value:
        return  # 空结果不缓存（保留下次重试机会）
    _EXIF_CACHE[key] = value
    if len(_EXIF_CACHE) > _EXIF_CACHE_MAXSIZE:
        # 弹出最早插入的一项（dict 保序）
        oldest = next(iter(_EXIF_CACHE))
        _EXIF_CACHE.pop(oldest, None)


def clear_exif_cache() -> None:
    """清空 EXIF 缓存（测试隔离 / 长跑后手动 GC 用）。"""
    _EXIF_CACHE.clear()


def exif_cache_size() -> int:
    """返回当前缓存条目数（测试 / 调试用）。"""
    return len(_EXIF_CACHE)

def _resolve_exiftool_base() -> Path:
    """解析 exiftool 二进制的搜索基目录。

    - **PyInstaller 冻结模式**（``sys.frozen == True``）：以可执行文件所在目录为基，
      因为 spec 把 ``exiftool/`` 通过 ``datas`` 投放到 onedir 根（与 EXE 同级）。
    - **源码运行模式**：以项目根目录为基（``core/util.py`` 上溯两级）。
    - 仍允许通过环境变量 ``EXIFTOOL_HOME`` 强制指定，便于自检与 CI。
    """
    env_override = os.environ.get("EXIFTOOL_HOME")
    if env_override:
        return Path(env_override)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


_EXIFTOOL_BASE = _resolve_exiftool_base()

if platform.system() == 'Windows':
    EXIFTOOL_PATH = _EXIFTOOL_BASE / 'exiftool' / 'exiftool.exe'
    ENCODING = 'gbk'
elif shutil.which('exiftool') is not None:
    EXIFTOOL_PATH = shutil.which('exiftool')
    ENCODING = 'utf-8'
else:
    EXIFTOOL_PATH = _EXIFTOOL_BASE / 'exiftool' / 'exiftool'
    ENCODING = 'utf-8'


def _parse_exiftool_block(block: str) -> dict:
    """把一段 exiftool 文本输出（单文件）解析成 key→value dict（私有工具）。"""
    exif_dict: dict[str, str] = {}
    for line in block.splitlines():
        kv_pair = line.split(':')
        if len(kv_pair) < 2:
            continue
        key = kv_pair[0].strip()
        value = ':'.join(kv_pair[1:]).strip()
        # 移除键中的空格与斜杠
        key = re.sub(r'\s+', '', key)
        key = re.sub(r'/', '', key)
        exif_dict[key] = value
    # 过滤非 ASCII 字符（保持原有 cleaning 行为）
    for key, value in list(exif_dict.items()):
        exif_dict[key] = ''.join(c for c in value if ord(c) < 128)
    return exif_dict


def _get_exif_pillow(path: str | Path) -> dict:
    """Fallback EXIF reader using Pillow when exiftool is unavailable.

    Maps Pillow EXIF tag names to the exiftool-style keys expected by Jinja
    templates so the watermark processor works even without exiftool installed.
    """
    try:
        from PIL import ExifTags, Image
        from PIL.ExifTags import IFD
    except ImportError:  # pragma: no cover
        print("DEBUG: Pillow import failed")
        return {}

    try:
        with Image.open(path) as img:
            exif: dict[str, str] = {
                "ImageWidth": str(img.width),
                "ImageHeight": str(img.height),
            }

            # --- read EXIF via Pillow 9.0+ API (preferred) ---
            pil_exif = None
            if hasattr(img, "getexif"):
                with suppress(Exception):
                    pil_exif = img.getexif()
            if pil_exif is None and hasattr(img, "_getexif"):
                with suppress(Exception):
                    pil_exif = img._getexif()

            if not pil_exif:
                return exif

            # Build tag_id → name mapping for both IFD0 and ExifIFD
            tag_names: dict[int, str] = {}
            for tag_id, tag_name in ExifTags.TAGS.items():
                tag_names[tag_id] = tag_name
            # ExifIFD tags are also in TAGS but may overlap; last-write wins
            # (Pillow 9.0+ uses ExifTags.TAGS for all, so this is fine)

            def _set(tag_id: int, value: Any) -> None:
                name = tag_names.get(tag_id)
                if not name:
                    return
                if isinstance(value, bytes):
                    try:
                        value = value.decode("utf-8", errors="ignore")
                    except Exception:
                        value = str(value)
                elif isinstance(value, tuple) and len(value) == 2:
                    numerator, denominator = value
                    if denominator == 0:
                        value = str(value)
                    else:
                        ratio = numerator / denominator
                        if name in ("FocalLength", "FocalLengthIn35mmFilm"):
                            value = f"{ratio:.0f}mm"
                        elif name in ("FNumber", "ApertureValue"):
                            if name == "ApertureValue":
                                # APEX value: convert to f-number = 2^APEX
                                f_num = 2 ** ratio
                                value = str(round(f_num)) if abs(f_num - round(f_num)) < 0.1 else f"{f_num:.1f}"
                            else:
                                value = str(int(ratio)) if ratio == int(ratio) else f"{ratio:.1f}"
                        elif name in ("ExposureTime", "ShutterSpeed"):
                            if ratio < 1:
                                reciprocal = int(1 / ratio + 0.5)
                                value = f"1/{reciprocal}"
                            else:
                                value = str(int(ratio)) if ratio == int(ratio) else f"{ratio:.1f}"
                        elif name == "ShutterSpeedValue":
                            # APEX value: t = 2^(-APEX)
                            if ratio > 0:
                                shutter = 2 ** ratio
                                value = f"1/{int(shutter + 0.5)}"
                            else:
                                value = f"{2 ** (-ratio):.1f}"
                        else:
                            value = str(value)
                elif not isinstance(value, str):
                    value = str(value)
                # Strip null bytes and whitespace
                exif[name] = value.strip().strip("\x00")

            # Read IFD0 tags
            for tag_id, value in pil_exif.items():
                _set(tag_id, value)

            # Read ExifIFD sub-tags (FocalLength, ISO, etc.)
            if hasattr(pil_exif, "get_ifd"):
                try:
                    exif_ifd = pil_exif.get_ifd(IFD.Exif)
                    if exif_ifd:
                        for tag_id, value in exif_ifd.items():
                            _set(tag_id, value)
                except Exception:
                    pass

            # --- map Pillow names → exiftool-style keys (Jinja compatibility) ---
            # Camera model
            if "Model" in exif and "CameraModelName" not in exif:
                exif["CameraModelName"] = exif["Model"]

            # Focal length (prefer 35mm equivalent, fallback to raw)
            if "FocalLengthIn35mmFilm" in exif:
                exif["FocalLengthIn35mmFormat"] = exif["FocalLengthIn35mmFilm"]
            elif "FocalLength" in exif and "FocalLengthIn35mmFormat" not in exif:
                exif["FocalLengthIn35mmFormat"] = exif["FocalLength"]

            # Aperture / F-number: always use FNumber (rational) over ApertureValue (APEX)
            if "FNumber" in exif:
                exif["ApertureValue"] = exif["FNumber"]
            elif "ApertureValue" in exif:
                exif["FNumber"] = exif["ApertureValue"]

            # Shutter speed: always use ExposureTime (seconds) over ShutterSpeedValue (APEX)
            if "ExposureTime" in exif:
                exif["ShutterSpeed"] = exif["ExposureTime"]
            elif "ShutterSpeedValue" in exif:
                exif["ShutterSpeed"] = exif["ShutterSpeedValue"]

            # ISO
            if "ISOSpeedRatings" in exif and "ISO" not in exif:
                exif["ISO"] = exif["ISOSpeedRatings"]
            if "PhotographicSensitivity" in exif and "ISO" not in exif:
                exif["ISO"] = exif["PhotographicSensitivity"]

            # DateTime
            if "DateTimeOriginal" not in exif and "DateTime" in exif:
                exif["DateTimeOriginal"] = exif["DateTime"]
            if "DateTimeOriginal" not in exif and "DateTimeDigitized" in exif:
                exif["DateTimeOriginal"] = exif["DateTimeDigitized"]

            # GPS
            if hasattr(pil_exif, "get_ifd"):
                try:
                    gps_ifd = pil_exif.get_ifd(IFD.GPSInfo)
                    if gps_ifd:
                        for tag_id, value in gps_ifd.items():
                            gps_name = ExifTags.GPSTAGS.get(tag_id, str(tag_id))
                            if isinstance(value, bytes):
                                try:
                                    value = value.decode("utf-8", errors="ignore").strip("\x00")
                                except Exception:
                                    value = str(value)
                            elif not isinstance(value, str):
                                value = str(value)
                            exif[gps_name] = value.strip()
                except Exception:
                    pass

            return exif
    except Exception as e:
        logger.error(f"Pillow EXIF fallback error for {path}: {e}")
        return {}


def get_exif(path) -> dict:
    """
    获取exif信息（Phase 5.2：自动 mtime 失效缓存）。
    当 exiftool 不可用时，自动回退到 Pillow EXIF 读取。

    :param path: 照片路径
    :return: exif信息
    """
    cache_key = _exif_cache_key(path)
    if cache_key is not None:
        cached = _EXIF_CACHE.get(cache_key)
        if cached is not None:
            return cached

    # Try exiftool first (best quality, most comprehensive)
    try:
        output_bytes = subprocess.check_output(
            [EXIFTOOL_PATH, "-d", "%Y-%m-%d %H:%M:%S%3f%z", str(path)]
        )
        output = output_bytes.decode("utf-8", errors="ignore")
        parsed = _parse_exiftool_block(output)
        if cache_key is not None:
            _exif_cache_put(cache_key, parsed)
        return parsed
    except FileNotFoundError:
        logger.warning(f"exiftool not found at {EXIFTOOL_PATH}, falling back to Pillow EXIF")
    except Exception as e:
        logger.warning(f"exiftool failed for {path}: {e}, falling back to Pillow EXIF")

    # Fallback to Pillow EXIF (works without external exiftool binary)
    parsed = _get_exif_pillow(path)
    if cache_key is not None and parsed:
        _exif_cache_put(cache_key, parsed)
    return parsed


def get_exif_batch(paths: list[str]) -> dict[str, dict]:
    """批量获取多个文件的 EXIF — 一次 exiftool 调用读取所有文件，远比逐张 fork 快。

    适用于 :class:`gui.process_thread.ProcessThread` 等批处理场景。

    Phase 5.2：先查 EXIF 缓存（``(abspath, mtime_ns)`` key），命中的文件直接复用；
    剩余 miss 的文件才合并成一次 exiftool 调用，新结果回写进缓存。

    Args:
        paths: 文件路径列表（顺序保留）。

    Returns:
        ``dict[路径, EXIF dict]``。读取失败的文件值为空 dict（不抛异常，
        以保持批处理的容错语义——单文件失败不影响其他）。
    """
    if not paths:
        return {}

    result: dict[str, dict] = {p: {} for p in paths}

    # ---- Phase 5.2：先消化缓存命中 ----
    miss_paths: list[str] = []
    miss_keys: dict[str, tuple[str, int]] = {}
    for p in paths:
        key = _exif_cache_key(p)
        if key is not None:
            cached = _EXIF_CACHE.get(key)
            if cached is not None:
                result[p] = cached
                continue
            miss_keys[p] = key
        miss_paths.append(p)

    # 全部命中 — 直接返回，跳过 exiftool 调用
    if not miss_paths:
        return result

    try:
        # exiftool 一次接收多个文件路径并以 ``======== <path>`` 分隔输出。
        output_bytes = subprocess.check_output(
            [EXIFTOOL_PATH, '-d', '%Y-%m-%d %H:%M:%S%3f%z', *map(str, miss_paths)]
        )
        output = output_bytes.decode('utf-8', errors='ignore')
    except Exception as e:
        logger.error(f'get_exif_batch error: {e}')
        # 失败回落到逐文件读取（保持容错；get_exif 内部会自行使用缓存）
        for p in miss_paths:
            result[p] = get_exif(p)
        return result

    # 按 "======== <path>" 切分各文件块
    current_path: str | None = None
    current_lines: list[str] = []

    def _flush() -> None:
        nonlocal current_path, current_lines
        if current_path is not None:
            block = '\n'.join(current_lines)
            result[current_path] = _parse_exiftool_block(block)
        current_lines = []

    for line in output.splitlines():
        if line.startswith('======== '):
            _flush()
            current_path = line[len('======== '):].strip()
            # exiftool 可能输出相对路径——尝试匹配输入参数
            if current_path not in result:
                # 退化匹配：用 basename 找回原 key
                from os.path import basename
                bn = basename(current_path)
                for p in miss_paths:
                    if basename(p) == bn:
                        current_path = p
                        break
            continue
        current_lines.append(line)
    _flush()

    # 单文件场景下 exiftool 不会输出 "========" 分隔符（直接打印属性）
    # 此时若 result 仍全为空，则视作单文件输出整体
    if len(miss_paths) == 1 and not result[miss_paths[0]]:
        result[miss_paths[0]] = _parse_exiftool_block(output)

    # ---- Phase 5.2：把新结果回写进缓存 ----
    for p, key in miss_keys.items():
        parsed = result.get(p)
        if parsed:
            _exif_cache_put(key, parsed)

    return result


def list_files(path: str, suffixes: set[str], depth: int = 0, max_depth: int = 20):
    """
    使用 pathlib 实现的版本

    Args:
        path: 要扫描的路径
        suffixes: 支持的文件后缀
        depth: 当前递归深度（内部使用）
        max_depth: 最大递归深度，防止无限递归
    """
    result = []
    root = Path(path).resolve()

    if not root.exists():
        return result

    # 防止递归过深
    if depth > max_depth:
        logger.warning(f"list_files: 达到最大递归深度 {max_depth}，跳过 {path}")
        return result

    try:
        # 分离文件夹和文件，分别排序
        items = list(root.iterdir())
        dirs = sorted([i for i in items if i.is_dir()], key=lambda x: x.name.lower(), reverse=True)
        files = sorted([i for i in items if i.is_file()], key=lambda x: (x.stat().st_mtime, x.name.lower()),
                       reverse=True)

        # 先处理文件夹
        for item in dirs:
            if item.name.startswith('.'):
                continue
            # 跳过符号链接，避免无限递归
            if item.is_symlink():
                continue
            children = list_files(str(item), suffixes, depth + 1, max_depth)
            if children:
                result.append({
                    'label': item.name,
                    'value': str(item),
                    'children': children,
                })

        # 再处理文件
        for item in files:
            if item.name.startswith('.'):
                continue
            if item.suffix.lower() in suffixes:
                result.append({
                    'label': item.name,
                    'value': str(item),
                    'is_file': True
                })

    except PermissionError:
        logger.debug(f"list_files: 权限不足，跳过 {path}")
    except Exception as e:
        logger.error(f"list_files: 扫描失败 {path}: {e}")

    return result


def log_rt(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()  # 记录开始时间
        result = func(*args, **kwargs)  # 调用被装饰的函数
        end_time = time.time()  # 记录结束时间
        elapsed_time = (end_time - start_time) * 1000  # 计算运行时间

        logger.debug(f"[monitor]api#{func.__name__} cost {elapsed_time:.2f}ms")
        return result

    return wrapper


def convert_heic_to_jpeg(path: str, quality: int = 90) -> io.BytesIO:
    """转换 HEIC 为 JPEG 字节流"""
    with Image.open(path) as img:
        if img.mode in ('RGBA', 'P', 'LA'):
            img = img.convert('RGB')

        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality)
        buffer.seek(0)
        return buffer


# ==================== 模板管理相关方法 ====================

def get_template_path(template_name: str) -> Path:
    """
    获取模板文件的完整路径

    Args:
        template_name: 模板名称（不含扩展名），如 "standard1"

    Returns:
        模板文件的完整 Path 对象
    """
    return templates_dir / f"{template_name}.json"


def get_template(template_name: str) -> Template:
    """
    读取并解析模板文件为 Jinja2 Template 对象

    Args:
        template_name: 模板名称（不含扩展名），如 "standard1"

    Returns:
        Jinja2 Template 对象，已注册 vh, vw, auto_logo 全局函数
    """
    template_path = get_template_path(template_name)
    with open(template_path, encoding='utf-8') as f:
        template_str = f.read()
    template = Template(template_str)
    template.globals['vh'] = vh
    template.globals['vw'] = vw
    template.globals['auto_logo'] = auto_logo
    return template


def get_template_content(template_name: str) -> str:
    """
    获取模板文件的内容（原始字符串）

    Args:
        template_name: 模板名称（不含扩展名），如 "standard1"

    Returns:
        模板文件的原始内容字符串
    """
    template_path = get_template_path(template_name)
    with open(template_path, encoding='utf-8') as f:
        return f.read()


def save_template(template_name: str, content: str) -> None:
    """
    保存模板文件

    Args:
        template_name: 模板名称（不含扩展名），如 "standard1"
        content: 模板内容（JSON 字符串）
    """
    template_path = get_template_path(template_name)
    # 确保目录存在
    template_path.parent.mkdir(parents=True, exist_ok=True)
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(content)


def create_template(template_name: str, content: str = '[]') -> None:
    """
    创建新的模板文件

    Args:
        template_name: 模板名称（不含扩展名），如 "my_template"
        content: 模板内容（JSON 字符串），默认为空数组 '[]'

    Raises:
        FileExistsError: 如果模板文件已存在
    """
    template_path = get_template_path(template_name)
    if template_path.exists():
        raise FileExistsError(f"模板 '{template_name}' 已存在")
    save_template(template_name, content)


def list_templates() -> list[str]:
    """
    列出所有可用的模板名称

    Returns:
        模板名称列表（不含扩展名）
    """
    if not templates_dir.exists():
        return []
    return [f.stem for f in templates_dir.glob('*.json')]
