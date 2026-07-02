from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

import web_api.main as web_main
import web_api.processing as web_processing
from web_api.main import app
from web_api.settings import WebApiSettings, settings

client = TestClient(app)


def _make_image(path: Path, size: tuple[int, int] = (320, 240)) -> Path:
    image = Image.new("RGB", size, (60, 80, 120))
    image.save(path, format="JPEG")
    return path


def _minimal_config() -> dict:
    return {
        "corners": {
            "left_top": {
                "chips": [{"field_id": "custom_text", "custom_text": "WEB MVP"}],
                "font_size_ratio": 0.08,
            }
        },
        "logo": {"enabled": "disabled"},
        "advanced": {
            "footer_height_px": 80,
            "global_color": "#222222",
        },
    }


def _post_image(endpoint: str, image_path: Path, config: dict | None = None):
    with image_path.open("rb") as file:
        return client.post(
            endpoint,
            files={"file": (image_path.name, file, "image/jpeg")},
            data={"config": json.dumps(config if config is not None else _minimal_config())},
        )


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "status": "ok"}


def test_process_image_generates_downloadable_file(tmp_path: Path) -> None:
    image_path = _make_image(tmp_path / "input.jpg")

    response = _post_image("/api/process", image_path)

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    filename = payload["file"]["filename"]
    assert filename.startswith("process-")
    assert (settings.output_dir / filename).exists()

    download = client.get(payload["file"]["download_url"])
    assert download.status_code == 200
    assert download.content


def test_preview_image_generates_downloadable_file(tmp_path: Path) -> None:
    image_path = _make_image(tmp_path / "input.jpg", size=(900, 600))

    response = _post_image("/api/preview", image_path)

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    filename = payload["file"]["filename"]
    assert filename.startswith("preview-")
    assert (settings.output_dir / filename).exists()


def test_web_api_renders_exif_jinja_before_processing(tmp_path: Path, monkeypatch) -> None:
    image_path = _make_image(tmp_path / "exif.jpg")
    captured: dict = {}

    def fake_get_exif(path: str) -> dict:
        assert Path(path).exists()
        return {"ISO": "640", "CameraModelName": "X-T5"}

    def fake_start_process(**kwargs):
        captured.update(kwargs)
        output_path = Path(kwargs["output_path"])
        Image.new("RGB", (32, 32), (1, 2, 3)).save(output_path)
        return Image.new("RGB", (32, 32), (1, 2, 3))

    monkeypatch.setattr(web_processing, "get_exif", fake_get_exif)
    monkeypatch.setattr(web_processing, "start_process", fake_start_process)

    response = _post_image(
        "/api/process",
        image_path,
        {
            "corners": {
                "left_top": {
                    "chips": [{"field_id": "iso"}, {"field_id": "camera_model"}],
                    "separator": "|",
                    "font_size_ratio": 0.05,
                }
            },
            "logo": {"enabled": "disabled"},
        },
    )

    assert response.status_code == 200, response.json()
    watermark = captured["data"][-1]
    segments = watermark["left_top"]["text_segments"]
    assert segments[0]["text"] == "ISO640"
    assert segments[2]["text"] == "X-T5"
    assert captured["pre_loaded_exif"] == {"ISO": "640", "CameraModelName": "X-T5"}


def test_process_pixel_limit_message_is_actionable(tmp_path: Path, monkeypatch) -> None:
    image_path = _make_image(tmp_path / "large.jpg", size=(120, 120))
    test_settings = WebApiSettings(
        data_dir=settings.data_dir,
        upload_dir=settings.upload_dir,
        output_dir=settings.output_dir,
        resources_dir=settings.resources_dir,
        tmp_dir=settings.tmp_dir,
        max_image_pixels=10_000,
        preview_max_image_pixels=settings.preview_max_image_pixels,
    )
    monkeypatch.setattr(web_main, "settings", test_settings)

    response = _post_image("/api/process", image_path)

    assert response.status_code == 413
    payload = response.json()
    assert payload["error"]["code"] == "image_too_large"
    assert "120×120" in payload["error"]["message"]
    assert "AKA_SEMI_MAX_IMAGE_PIXELS" in payload["error"]["detail"]
    assert payload["error"]["context"]["mode"] == "process"


def test_preview_uses_separate_larger_pixel_limit(tmp_path: Path, monkeypatch) -> None:
    image_path = _make_image(tmp_path / "preview-large.jpg", size=(120, 120))
    test_settings = WebApiSettings(
        data_dir=settings.data_dir,
        upload_dir=settings.upload_dir,
        output_dir=settings.output_dir,
        resources_dir=settings.resources_dir,
        tmp_dir=settings.tmp_dir,
        max_image_pixels=10_000,
        preview_max_image_pixels=20_000,
    )
    monkeypatch.setattr(web_main, "settings", test_settings)

    response = _post_image("/api/preview", image_path)

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_settings_expose_separate_preview_pixel_limit(tmp_path: Path) -> None:
    custom = WebApiSettings(
        data_dir=tmp_path,
        upload_dir=tmp_path / "uploads",
        output_dir=tmp_path / "outputs",
        resources_dir=tmp_path / "resources",
        tmp_dir=tmp_path / "tmp",
        max_image_pixels=1,
        preview_max_image_pixels=2,
    )

    assert custom.max_image_pixels == 1
    assert custom.preview_max_image_pixels == 2


def test_rejects_invalid_config_json(tmp_path: Path) -> None:
    image_path = _make_image(tmp_path / "input.jpg")
    with image_path.open("rb") as file:
        response = client.post(
            "/api/process",
            files={"file": ("input.jpg", file, "image/jpeg")},
            data={"config": "{"},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_config_json"


def test_rejects_unsupported_extension(tmp_path: Path) -> None:
    file_path = tmp_path / "input.txt"
    file_path.write_text("not an image", encoding="utf-8")
    with file_path.open("rb") as file:
        response = client.post(
            "/api/process",
            files={"file": ("input.txt", file, "text/plain")},
            data={"config": json.dumps(_minimal_config())},
        )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_custom_text_is_never_evaluated_as_jinja(tmp_path: Path, monkeypatch) -> None:
    image_path = _make_image(tmp_path / "literal.jpg")
    captured: dict = {}

    def fake_start_process(**kwargs):
        captured.update(kwargs)
        Image.new("RGB", (16, 16)).save(kwargs["output_path"])

    monkeypatch.setattr(web_processing, "start_process", fake_start_process)
    response = _post_image(
        "/api/process",
        image_path,
        {
            "corners": {
                "left_top": {
                    "chips": [{"field_id": "custom_text", "custom_text": "probe={{ 7 * 7 }}"}],
                }
            },
            "logo": {"enabled": "disabled"},
        },
    )

    assert response.status_code == 200
    assert captured["data"][-1]["left_top"]["text"] == "probe={{ 7 * 7 }}"


def test_rejects_arbitrary_server_resource_path(tmp_path: Path) -> None:
    image_path = _make_image(tmp_path / "path.jpg")
    config = _minimal_config()
    config["logo"] = {
        "enabled": "custom",
        "position": "right",
        "color": "#D8D8D6",
        "custom_path": "/etc/passwd",
    }

    response = _post_image("/api/process", image_path, config)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_config"


def test_upload_once_then_process_by_image_id(tmp_path: Path) -> None:
    image_path = _make_image(tmp_path / "reused.jpg")
    with image_path.open("rb") as file:
        upload = client.post("/api/uploads", files={"file": (image_path.name, file, "image/jpeg")})
    assert upload.status_code == 200

    response = client.post(
        "/api/preview",
        data={"image_id": upload.json()["image_id"], "config": json.dumps(_minimal_config())},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
