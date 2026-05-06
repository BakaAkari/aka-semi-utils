"""pytest 全局 fixtures。

提供：
- ``project_root``：项目根目录（aka-semi-utils/）
- ``tmp_config_dir``：每个测试函数独立的临时 config 目录
- ``sample_exif``：典型的 EXIF 字典 stub
- ``sample_image``：内存中的 PIL 测试图（带 EXIF 转向已经处理）
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture(scope="session")
def project_root() -> Path:
    """项目根目录，用于定位 config / static 等只读资源。"""
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """每个测试一个干净的 config 目录，避免相互污染。"""
    cfg = tmp_path / "config"
    (cfg / "fonts").mkdir(parents=True)
    (cfg / "logos").mkdir(parents=True)
    (cfg / "templates").mkdir(parents=True)
    return cfg


@pytest.fixture
def sample_exif() -> dict[str, str]:
    """一份"长得像真实 ExifTool 输出"的字典。"""
    return {
        "Make": "NIKON",
        "CameraModelName": "NIKON Z 7",
        "LensModel": "NIKKOR Z 24-70mm f/2.8 S",
        "FocalLengthIn35mmFormat": "50 mm",
        "ApertureValue": "2.8",
        "FNumber": "2.8",
        "ShutterSpeed": "1/200",
        "ShutterSpeedValue": "1/200",
        "ISO": "400",
        "DateTimeOriginal": "2024-08-01 12:34:56",
        "ImageWidth": "6048",
        "ImageHeight": "4024",
    }


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    """生成一张 100×80 的纯色 jpg 用作 pipeline 端到端测试。"""
    path = tmp_path / "sample.jpg"
    Image.new("RGB", (100, 80), (200, 150, 100)).save(path, format="JPEG", quality=85)
    return path
