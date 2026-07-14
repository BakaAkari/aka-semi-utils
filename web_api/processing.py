"""Image processing orchestration for the Web API."""

from __future__ import annotations

import warnings
from copy import deepcopy
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps
from PIL.Image import DecompressionBombWarning

import processor  # noqa: F401  # side-effect: register processors
from core.util import get_exif
from processor.core import start_process
from shared.v3_assembler import v3_config_to_processors
from web_api.errors import ApiError
from web_api.settings import WebApiSettings
from web_api.storage import resolve_resource


def process_image_v3(
    input_path: Path,
    output_path: Path,
    config_dict: dict[str, Any],
    settings: WebApiSettings,
    *,
    preview: bool = False,
) -> Path:
    """Run the V3 watermark processor pipeline for one uploaded image."""

    if preview:
        _validate_image(input_path, settings, max_pixels=settings.preview_max_image_pixels, mode="preview")
    else:
        _validate_image(input_path, settings, max_pixels=settings.max_image_pixels, mode="process")

    resolved_config = _resolve_v3_resources(config_dict, settings)
    processors = v3_config_to_processors(resolved_config)
    if not processors:
        raise ApiError(
            code="empty_pipeline",
            message="当前 V3 配置没有生成可执行的水印处理管线",
            status_code=400,
        )

    try:
        exif = get_exif(str(input_path))
        if preview:
            image = _load_preview_image(input_path, settings)
            start_process(
                data=processors,
                input_path=str(input_path),
                output_path=str(output_path),
                initial_buffer=[image],
                pre_loaded_exif=exif,
            )
        else:
            start_process(
                data=processors,
                input_path=str(input_path),
                output_path=str(output_path),
                pre_loaded_exif=exif,
            )
    except ApiError:
        raise
    except Exception as exc:
        import logging
        import traceback
        _logger = logging.getLogger("web_api.processing")
        _logger.error("V3 image processing failed:\n%s", traceback.format_exc())
        output_path.unlink(missing_ok=True)
        raise ApiError(
            code="processing_failed",
            message="图片处理失败",
            status_code=500,
        ) from exc

    if not output_path.exists():
        raise ApiError(
            code="output_missing",
            message="处理完成但未生成输出文件",
            status_code=500,
        )
    return output_path


def _resolve_v3_resources(
    config_dict: dict[str, Any],
    settings: WebApiSettings,
) -> dict[str, Any]:
    """Resolve opaque V3 logo/signature ids after public schema validation.

    User input never reaches a server path sink. Disabled regions and slots are
    intentionally ignored because their resources are not consumed.
    """

    resolved = deepcopy(config_dict)
    for region in resolved.get("regions", []):
        if not region.get("enabled", False):
            continue
        for slot in (region.get("slots") or {}).values():
            if not slot.get("enabled", False):
                continue
            content = slot.get("content")
            if not isinstance(content, dict):
                continue
            resource_id = content.get("path", "")
            if not resource_id:
                continue
            kind = "signature" if "invert_mono" in content else "logo"
            content["path"] = str(resolve_resource(resource_id, kind, settings))
    return resolved


def _validate_image(path: Path, settings: WebApiSettings, *, max_pixels: int, mode: str) -> None:
    """Validate image readability and mode-specific pixel limits."""

    _ = settings
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DecompressionBombWarning)
            with Image.open(path) as image:
                width, height = image.size
                pixels = width * height
                if pixels > max_pixels:
                    megapixels = pixels / 1_000_000
                    limit_megapixels = max_pixels / 1_000_000
                    hint = (
                        "预览模式会先缩小图片，但原图仍超过当前预览保护上限。"
                        if mode == "preview"
                        else "正式处理会按原图分辨率运行，请降低原图尺寸或提高 AKA_SEMI_MAX_IMAGE_PIXELS。"
                    )
                    raise ApiError(
                        code="image_too_large",
                        message=f"图片像素过大：{width}×{height}（约 {megapixels:.1f}MP），当前上限 {limit_megapixels:.1f}MP",
                        status_code=413,
                        detail=hint,
                        context={
                            "width": width,
                            "height": height,
                            "pixels": pixels,
                            "max_pixels": max_pixels,
                            "mode": mode,
                        },
                    )
                image.verify()
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError(
            code="invalid_image",
            message="无法读取图片文件",
            status_code=400,
        ) from exc


def _load_preview_image(path: Path, settings: WebApiSettings) -> Image.Image:
    """Load and downscale an image for fast preview processing."""

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DecompressionBombWarning)
            with Image.open(path) as source:
                image = ImageOps.exif_transpose(source)
    except Exception as exc:
        raise ApiError(
            code="invalid_image",
            message="无法读取图片文件",
            status_code=400,
        ) from exc

    image.thumbnail((settings.preview_max_edge, settings.preview_max_edge))
    return image
