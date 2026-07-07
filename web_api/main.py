"""FastAPI application for the aka-semi-utils Web MVP."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

# Allow large file uploads (100MB) for GFX100S2 RAW files
os.environ.setdefault("MULTIPART_MAX_FILE_SIZE", "100000000")

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from web_api.errors import ApiError
from web_api.processing import process_image
from web_api.schemas import config_from_payload, success_response
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

app = FastAPI(title="aka-semi-utils Web API", version="0.1.0")
_job_slots = asyncio.Semaphore(max(1, settings.max_concurrent_jobs))

# Serve fonts as static files
_fonts_dir = Path(__file__).parent.parent / "config" / "fonts"
if _fonts_dir.exists():
    app.mount("/api/fonts", StaticFiles(directory=str(_fonts_dir)), name="fonts")

# Serve web frontend static files (production build)
_web_dist = Path(__file__).parent.parent / "web_frontend" / "dist"
if _web_dist.exists():
    from fastapi.responses import HTMLResponse

    _static_files = StaticFiles(directory=str(_web_dist), html=True)
    app.mount("/semi-utils", _static_files, name="web_frontend")

    @app.get("/semi-utils/{path:path}")
    async def spa_fallback(_path: str) -> HTMLResponse:
        """SPA fallback: serve index.html for any unmatched route."""
        return HTMLResponse(content=(_web_dist / "index.html").read_text())


@app.exception_handler(ApiError)
async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    """Render structured API errors."""

    return JSONResponse(status_code=exc.status_code, content=exc.to_payload())


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Health check for local, Caddy, and systemd probes."""

    return success_response(status="ok")


@app.post("/api/uploads")
async def upload_image(file: UploadFile = File(...)) -> dict[str, Any]:
    """Upload an input image once and return an expiring opaque id."""

    path = await save_upload(file, settings)
    return success_response(image_id=path.name, expires_in=settings.file_ttl_seconds)


@app.post("/api/upload-resource")
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


@app.post("/api/process")
async def process_endpoint(
    file: UploadFile | None = File(default=None),
    image_id: str = Form(default=""),
    config: str = Form(default="{}"),
) -> dict[str, Any]:
    """Process a single uploaded image with the full-resolution pipeline."""

    return await _run_single_image(file=file, image_id=image_id, config_json=config, preview=False)


@app.post("/api/preview")
async def preview_endpoint(
    file: UploadFile | None = File(default=None),
    image_id: str = Form(default=""),
    config: str = Form(default="{}"),
) -> dict[str, Any]:
    """Process a single uploaded image with preview downscaling."""

    return await _run_single_image(file=file, image_id=image_id, config_json=config, preview=True)


@app.get("/api/files/{filename}")
def get_output_file(filename: str) -> FileResponse:
    """Download a generated output or uploaded resource by server-side filename."""

    path = resolve_public_output(filename, settings)
    return FileResponse(path, filename=path.name)


async def _run_single_image(
    file: UploadFile | None,
    image_id: str,
    config_json: str,
    *,
    preview: bool,
) -> dict[str, Any]:
    cleanup_expired_files(settings)
    if file is not None:
        input_path = await save_upload(file, settings)
    elif image_id:
        input_path = resolve_upload(image_id, settings)
    else:
        raise ApiError(code="missing_image", message="请先上传图片", status_code=400)
    config_payload = _parse_config_json(config_json)
    watermark_config = config_from_payload(config_payload)
    output_path = new_output_path(input_path, settings, prefix="preview" if preview else "process")
    try:
        await asyncio.wait_for(_job_slots.acquire(), timeout=0.01)
    except TimeoutError as exc:
        raise ApiError(
            code="server_busy",
            message="服务器正在处理其他图片，请稍后重试",
            status_code=429,
        ) from exc
    try:
        result_path = await run_in_threadpool(
            process_image,
            input_path,
            output_path,
            watermark_config,
            settings,
            preview=preview,
        )
    finally:
        _job_slots.release()
    return success_response(file=public_file_payload(result_path))


def _parse_config_json(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
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
