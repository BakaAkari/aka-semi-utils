"""FastAPI application for the aka-semi-utils Web MVP."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import time
import zipfile
from pathlib import Path
from typing import Any

# Allow large file uploads (100MB) for GFX100S2 RAW files
os.environ.setdefault("MULTIPART_MAX_FILE_SIZE", "100000000")

from fastapi import BackgroundTasks, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from web_api import stats
from web_api.errors import ApiError
from web_api.processing import process_image_v3
from web_api.schemas_v3 import is_v3_payload, success_response, validate_v3_payload
from web_api.settings import settings
from web_api.storage import (
    cleanup_expired_files,
    new_output_path,
    public_file_payload,
    resolve_public_output,
    resolve_upload,
    save_resource,
    save_upload,
)

_api = settings.api_prefix

app = FastAPI(title="aka-semi-utils Web API", version="0.1.0")
_job_slots = asyncio.Semaphore(max(1, settings.max_concurrent_jobs))
_MAX_CONFIG_JSON_BYTES = 64 * 1024

# Serve fonts and logos as static files from the source config directories
_project_root = Path(__file__).parent.parent
_fonts_dir = _project_root / "config" / "fonts"
if _fonts_dir.exists():
    app.mount(f"{_api}/fonts", StaticFiles(directory=str(_fonts_dir)), name="fonts")

_logos_dir = _project_root / "config" / "logos"
if _logos_dir.exists():
    app.mount(f"{_api}/logos", StaticFiles(directory=str(_logos_dir)), name="logos")

# Frontend static files are served by Caddy; API only serves fonts/logos and endpoints here.


@app.exception_handler(ApiError)
async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    """Render structured API errors."""

    return JSONResponse(status_code=exc.status_code, content=exc.to_payload())


@app.get(f"{_api}/health")
def health() -> dict[str, Any]:
    """Health check for local, Caddy, and systemd probes."""

    return success_response(status="ok")


@app.post(f"{_api}/_visit")
async def visit_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    """Record a visitor fingerprint."""
    visitor_id = payload.get("visitor_id", "")
    if not visitor_id or not isinstance(visitor_id, str):
        raise ApiError(code="invalid_visitor", message="visitor_id 不能为空", status_code=400)
    new = stats.record_visit(visitor_id)
    return success_response(new=new)


@app.get(f"{_api}/_stats")
def stats_endpoint(request: Request) -> dict[str, Any]:
    """Return full statistics (requires X-Dev-Password header)."""
    password = request.headers.get("X-Dev-Password", "")
    if password != "23323312":
        raise ApiError(code="forbidden", message="禁止访问", status_code=403)
    return stats.get_stats()


@app.get(f"{_api}/_stats/health")
def stats_health() -> dict[str, Any]:
    """Check stats database connectivity."""
    return stats.health_check()


@app.post(f"{_api}/uploads")
async def upload_image(file: UploadFile = File(...)) -> dict[str, Any]:
    """Upload an input image once and return an expiring opaque id."""

    path = await save_upload(file, settings)
    return success_response(
        image_id=path.name,
        expires_in=settings.file_ttl_seconds,
        original_filename=file.filename or "image.jpg",
    )


@app.post(f"{_api}/upload-resource")
async def upload_resource(
    file: UploadFile = File(...),
    kind: str = Form(default="logo"),  # "logo" or "signature"
) -> dict[str, Any]:
    """Upload a logo or signature image resource. Returns a server-side filename."""

    path = await save_resource(file, settings, kind=kind)
    return success_response(
        filename=path.name,
        kind=kind,
        resource_id=path.name,
    )


@app.post(f"{_api}/process")
async def process_endpoint(
    file: UploadFile | None = File(default=None),
    image_id: str = Form(default=""),
    config: str = Form(default="{}"),
    original_filename: str = Form(default=""),
) -> dict[str, Any]:
    """Process a single uploaded image with the full-resolution pipeline."""

    return await _run_single_image(
        file=file, image_id=image_id, config_json=config,
        original_filename=original_filename, preview=False
    )


@app.post(f"{_api}/preview")
async def preview_endpoint(
    file: UploadFile | None = File(default=None),
    image_id: str = Form(default=""),
    config: str = Form(default="{}"),
    original_filename: str = Form(default=""),
) -> dict[str, Any]:
    """Process a single uploaded image with preview downscaling."""

    return await _run_single_image(
        file=file, image_id=image_id, config_json=config,
        original_filename=original_filename, preview=True
    )


@app.get(f"{_api}/files/{{filename}}")
def get_output_file(filename: str, download_filename: str = "") -> FileResponse:
    """Download a generated output or uploaded resource by server-side filename.

    When *download_filename* is provided via query parameter it is used as the
    Content-Disposition filename so browsers save the file under its original
    name rather than the opaque server-side name.
    """

    path = resolve_public_output(filename, settings)
    return FileResponse(path, filename=download_filename or path.name)


@app.post(f"{_api}/batch-download")
async def batch_download_endpoint(payload: dict[str, Any], background_tasks: BackgroundTasks) -> FileResponse:
    """Download multiple processed images as a zip archive."""

    filenames = payload.get("filenames", [])
    if not filenames or not isinstance(filenames, list) or len(filenames) == 0:
        raise ApiError(
            code="invalid_request",
            message="请提供至少一个文件名",
            status_code=400,
        )
    if len(filenames) > 50:
        raise ApiError(
            code="too_many_files",
            message="一次最多下载 50 个文件",
            status_code=400,
        )

    valid_paths: list[tuple[str, Path]] = []
    for filename in filenames:
        if not isinstance(filename, str) or not filename:
            continue
        try:
            path = resolve_public_output(filename, settings)
            valid_paths.append((filename, path))
        except ApiError:
            continue

    if not valid_paths:
        raise ApiError(
            code="no_files",
            message="没有可下载的文件或文件已过期",
            status_code=404,
        )

    settings.ensure_dirs()
    zip_name = f"batch-{secrets.token_urlsafe(12)}.zip"
    zip_path = settings.tmp_dir / zip_name

    def _create_zip() -> None:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for arcname, path in valid_paths:
                zf.write(path, arcname=arcname)

    await run_in_threadpool(_create_zip)

    # Schedule cleanup after response is sent
    background_tasks.add_task(zip_path.unlink, missing_ok=True)

    return FileResponse(
        zip_path,
        filename="batch-download.zip",
        media_type="application/zip",
    )


async def _run_single_image(
    file: UploadFile | None,
    image_id: str,
    config_json: str,
    original_filename: str,
    *,
    preview: bool,
) -> dict[str, Any]:
    config_payload = _parse_config_json(config_json)
    cleanup_expired_files(settings)
    if file is not None:
        input_path = await save_upload(file, settings)
        original_filename = file.filename or original_filename or "image.jpg"
    elif image_id:
        input_path = resolve_upload(image_id, settings)
    else:
        raise ApiError(code="missing_image", message="请先上传图片", status_code=400)

    output_path = new_output_path(
        input_path, settings, prefix="preview" if preview else "process",
    )

    try:
        await asyncio.wait_for(_job_slots.acquire(), timeout=30.0)
    except TimeoutError as exc:
        raise ApiError(
            code="server_busy",
            message="服务器正在处理其他图片，请稍后重试",
            status_code=429,
        ) from exc

    try:
        t0 = time.perf_counter()

        if is_v3_payload(config_payload):
            v3_config = validate_v3_payload(config_payload)
            result_path = await run_in_threadpool(
                process_image_v3,
                input_path,
                output_path,
                v3_config,
                settings,
                preview=preview,
            )
        else:
            raise ApiError(
                code="legacy_config_removed",
                message="旧版水印配置已下线，请使用 V3 Region 配置",
                status_code=410,
            )

        latency_ms = int((time.perf_counter() - t0) * 1000)
    finally:
        _job_slots.release()

    stats.record_process(
        operation="preview" if preview else "process",
        latency_ms=max(0, latency_ms),
        batch_count=1,
        visitor_id="",
        preset_name="",
    )
    # Derive the download filename from the original upload name while
    # keeping the actual output suffix (HEIC inputs become .jpg, etc.).
    orig_stem = Path(original_filename).stem if original_filename else "image"
    download_filename = f"{orig_stem}{result_path.suffix}"
    return success_response(file=public_file_payload(result_path, download_filename=download_filename, api_prefix=_api))


def _parse_config_json(raw: str) -> dict[str, Any]:
    if len(raw.encode("utf-8")) > _MAX_CONFIG_JSON_BYTES:
        raise ApiError(
            code="config_too_large",
            message="水印配置过大",
            status_code=413,
        )

    def reject_non_finite(value: str) -> None:
        raise ValueError(f"不允许非有限数值: {value}")

    try:
        payload = json.loads(raw or "{}", parse_constant=reject_non_finite)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ApiError(
            code="invalid_config_json",
            message="配置不是合法 JSON",
            status_code=400,
            detail=str(exc),
        ) from exc
    if not isinstance(payload, dict):
        raise ApiError(
            code="invalid_config",
            message="配置必须是 JSON 对象",
            status_code=400,
        )
    return payload
