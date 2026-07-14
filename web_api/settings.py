"""Runtime settings for the Web API."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WebApiSettings:
    """Configuration for upload/output storage and request safety limits."""

    data_dir: Path
    upload_dir: Path
    output_dir: Path
    resources_dir: Path
    tmp_dir: Path
    api_prefix: str = "/tools/watermark/api"
    # ~80MB for GFX100S2 RAW files
    max_upload_bytes: int = 80 * 1024 * 1024
    max_resource_bytes: int = 5 * 1024 * 1024
    # 100M px supports GFX100S2 and larger medium format
    max_image_pixels: int = 100_000_000
    preview_max_image_pixels: int = 100_000_000
    max_resource_pixels: int = 25_000_000
    preview_max_edge: int = 1200
    output_quality: int = 95
    max_concurrent_jobs: int = 1
    file_ttl_seconds: int = 3600
    allowed_extensions: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff", ".webp"})

    @classmethod
    def from_env(cls) -> WebApiSettings:
        """Create settings from environment with safe local defaults."""

        root = Path(
            os.environ.get(
                "AKA_SEMI_DATA_DIR",
                str(Path(tempfile.gettempdir()) / "aka-semi-utils-web"),
            )
        ).expanduser()
        return cls(
            data_dir=root,
            upload_dir=root / "uploads",
            output_dir=root / "outputs",
            resources_dir=root / "resources",
            tmp_dir=root / "tmp",
            api_prefix=os.environ.get("AKA_SEMI_API_PREFIX", "/tools/watermark/api"),
            max_upload_bytes=int(os.environ.get("AKA_SEMI_MAX_UPLOAD_BYTES", 80 * 1024 * 1024)),
            max_resource_bytes=int(os.environ.get("AKA_SEMI_MAX_RESOURCE_BYTES", 5 * 1024 * 1024)),
            max_image_pixels=int(os.environ.get("AKA_SEMI_MAX_IMAGE_PIXELS", 100_000_000)),
            preview_max_image_pixels=int(os.environ.get("AKA_SEMI_PREVIEW_MAX_IMAGE_PIXELS", 100_000_000)),
            max_resource_pixels=int(os.environ.get("AKA_SEMI_MAX_RESOURCE_PIXELS", 25_000_000)),
            preview_max_edge=int(os.environ.get("AKA_SEMI_PREVIEW_MAX_EDGE", 1200)),
            output_quality=int(os.environ.get("AKA_SEMI_OUTPUT_QUALITY", 95)),
            max_concurrent_jobs=int(os.environ.get("AKA_SEMI_MAX_CONCURRENT_JOBS", 1)),
            file_ttl_seconds=int(os.environ.get("AKA_SEMI_FILE_TTL_SECONDS", 3600)),
        )

    def ensure_dirs(self) -> None:
        """Create all runtime storage directories."""

        for path in (self.data_dir, self.upload_dir, self.output_dir, self.resources_dir, self.tmp_dir):
            path.mkdir(parents=True, exist_ok=True)


settings = WebApiSettings.from_env()
settings.ensure_dirs()
