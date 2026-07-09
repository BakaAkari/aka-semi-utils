"""Safe file handling for uploaded images and generated outputs."""

from __future__ import annotations

import secrets
import time
from pathlib import Path

from fastapi import UploadFile
from PIL import Image

from web_api.errors import ApiError
from web_api.settings import WebApiSettings

# Resource kinds that can be uploaded
ALLOWED_RESOURCE_KINDS: frozenset[str] = frozenset({"logo", "signature"})


def validate_filename(filename: str, settings: WebApiSettings) -> str:
    """Validate the client filename and return its lowercase suffix."""

    suffix = Path(filename or "").suffix.lower()
    if suffix not in settings.allowed_extensions:
        raise ApiError(
            code="unsupported_file_type",
            message="暂不支持该图片格式",
            status_code=415,
            detail=f"Allowed extensions: {', '.join(sorted(settings.allowed_extensions))}",
        )
    return suffix


async def save_upload(upload: UploadFile, settings: WebApiSettings) -> Path:
    """Persist an uploaded image under a random server-side filename."""

    suffix = validate_filename(upload.filename or "", settings)
    settings.ensure_dirs()
    cleanup_expired_files(settings)
    target = settings.upload_dir / f"{secrets.token_urlsafe(18)}{suffix}"

    size = 0
    try:
        with target.open("wb") as file:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise ApiError(
                        code="file_too_large",
                        message="上传图片过大",
                        status_code=413,
                        detail=f"Max upload size is {settings.max_upload_bytes} bytes",
                    )
                file.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    if size == 0:
        target.unlink(missing_ok=True)
        raise ApiError(
            code="empty_file",
            message="上传文件为空",
            status_code=400,
        )
    upload_pixel_limit = max(settings.max_image_pixels, settings.preview_max_image_pixels)
    _verify_image_file(target, upload_pixel_limit, message="上传文件不是有效图片")
    return target


async def save_resource(upload: UploadFile, settings: WebApiSettings, *, kind: str) -> Path:
    """Persist a logo or signature resource under a stable directory."""

    if kind not in ALLOWED_RESOURCE_KINDS:
        raise ApiError(
            code="invalid_resource_kind",
            message="不支持该资源类型",
            status_code=400,
            detail=f"Allowed kinds: {', '.join(sorted(ALLOWED_RESOURCE_KINDS))}",
        )

    suffix = validate_filename(upload.filename or "", settings)
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ApiError(
            code="unsupported_resource_type",
            message="Logo 和签名仅支持 PNG、JPEG 或 WebP",
            status_code=415,
        )
    settings.ensure_dirs()
    cleanup_expired_files(settings)
    target = settings.resources_dir / kind / f"{secrets.token_urlsafe(18)}{suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)

    size = 0
    try:
        with target.open("wb") as file:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_resource_bytes:
                    raise ApiError(
                        code="file_too_large",
                        message="上传资源过大",
                        status_code=413,
                    )
                file.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    if size == 0:
        target.unlink(missing_ok=True)
        raise ApiError(
            code="empty_file",
            message="上传文件为空",
            status_code=400,
        )
    _verify_image_file(target, settings.max_resource_pixels, message="Logo 或签名不是有效图片")
    return target


def _verify_image_file(path: Path, max_pixels: int, *, message: str) -> None:
    try:
        with Image.open(path) as image:
            width, height = image.size
            if width * height > max_pixels:
                raise ApiError(
                    code="image_too_large",
                    message="图片像素过大",
                    status_code=413,
                )
            image.verify()
    except ApiError:
        path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        path.unlink(missing_ok=True)
        raise ApiError(code="invalid_image", message=message, status_code=400) from exc


def new_output_path(input_path: Path, settings: WebApiSettings, *, prefix: str) -> Path:
    """Allocate a random output path."""

    settings.ensure_dirs()
    suffix = ".jpg" if input_path.suffix.lower() in {".heic", ".heif", ".tif", ".tiff"} else input_path.suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"
    return settings.output_dir / f"{prefix}-{secrets.token_urlsafe(18)}{suffix}"


def public_file_payload(path: Path, *, download_filename: str | None = None, api_prefix: str = "/tools/watermark/api") -> dict[str, str]:
    """Return file metadata safe for API clients.

    When *download_filename* is given it becomes the suggested filename for
    browser downloads and is appended as a query parameter so the download
    endpoint can set the matching Content-Disposition header.
    """

    payload: dict[str, str] = {
        "filename": path.name,
        "download_url": f"{api_prefix}/files/{path.name}",
    }
    if download_filename:
        payload["download_filename"] = download_filename
        payload["download_url"] = (
            f"{api_prefix}/files/{path.name}"
            f"?download_filename={download_filename}"
        )
    return payload


def resolve_public_output(filename: str, settings: WebApiSettings) -> Path:
    """Resolve a public output filename without allowing path traversal."""

    if not filename or Path(filename).name != filename:
        raise ApiError(
            code="invalid_file_name",
            message="文件名不合法",
            status_code=400,
        )
    # Try output_dir first, then resources_dir subdirs
    for base in (settings.output_dir, settings.resources_dir / "logo", settings.resources_dir / "signature"):
        path = base / filename
        if path.exists() and path.is_file():
            return path
    raise ApiError(
        code="file_not_found",
        message="文件不存在或已过期",
        status_code=404,
    )


def resolve_upload(image_id: str, settings: WebApiSettings) -> Path:
    """Resolve an opaque upload id inside the upload directory."""

    return _resolve_in_directory(image_id, settings.upload_dir, "上传图片不存在或已过期")


def resolve_resource(resource_id: str, kind: str, settings: WebApiSettings) -> Path:
    """Resolve a resource id only in its declared resource kind."""

    if kind not in ALLOWED_RESOURCE_KINDS:
        raise ApiError(code="invalid_resource_kind", message="资源类型不合法", status_code=400)
    return _resolve_in_directory(resource_id, settings.resources_dir / kind, "资源不存在或已过期")


def _resolve_in_directory(filename: str, directory: Path, message: str) -> Path:
    if not filename or Path(filename).name != filename:
        raise ApiError(code="invalid_file_name", message="文件标识不合法", status_code=400)
    path = directory / filename
    if not path.is_file():
        raise ApiError(code="file_not_found", message=message, status_code=404)
    return path


def cleanup_expired_files(settings: WebApiSettings, *, now: float | None = None) -> int:
    """Delete expired anonymous uploads, outputs, and resources."""

    cutoff = (time.time() if now is None else now) - settings.file_ttl_seconds
    deleted = 0
    for directory in (
        settings.upload_dir,
        settings.output_dir,
        settings.resources_dir / "logo",
        settings.resources_dir / "signature",
        settings.tmp_dir,
    ):
        if not directory.exists():
            continue
        for path in directory.iterdir():
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
                deleted += 1
    return deleted
