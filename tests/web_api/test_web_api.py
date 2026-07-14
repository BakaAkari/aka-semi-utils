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


def _minimal_v3_config(custom_text: str = "V3 WEB") -> dict:
    return {
        "canvas": {
            "margins": {"top": 0, "right": 0, "bottom": 80, "left": 0},
            "background": "#FFFFFF",
            "border_radius": 0,
        },
        "regions": [
            {
                "id": "footer",
                "type": "footer-bar",
                "enabled": True,
                "slots": {
                    "left-top": {
                        "enabled": True,
                        "content": {
                            "chips": [{"field_id": "custom_text", "custom_text": custom_text}],
                            "separator": " ",
                        },
                        "style": None,
                    },
                },
            },
        ],
        "defaults": {
            "font_size": None,
            "font_size_ratio": 0.35,
            "size_reference": "region_height",
            "color": "#222222",
            "font_family": "NotoSansCJKsc-Bold.otf",
            "bold": True,
            "line_height": 1.2,
        },
        "custom_text": "",
    }


def _legacy_config() -> dict:
    return {
        "corners": {
            "left_top": {
                "chips": [{"field_id": "custom_text", "custom_text": "WEB MVP"}],
                "font_size_ratio": 0.08,
            }
        },
        "logo": {"enabled": "disabled"},
    }


def _post_image(endpoint: str, image_path: Path, config: dict | None = None):
    with image_path.open("rb") as file:
        return client.post(
            endpoint,
            files={"file": (image_path.name, file, "image/jpeg")},
            data={"config": json.dumps(config if config is not None else _minimal_v3_config())},
        )


def test_health() -> None:
    response = client.get("/tools/watermark/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "status": "ok"}


def test_v3_process_image_generates_downloadable_file(tmp_path: Path) -> None:
    image_path = _make_image(tmp_path / "input-v3.jpg")

    response = _post_image("/tools/watermark/api/process", image_path)

    assert response.status_code == 200, response.json()
    payload = response.json()
    assert payload["ok"] is True
    filename = payload["file"]["filename"]
    assert filename.startswith("process-")
    assert (settings.output_dir / filename).exists()

    download = client.get(payload["file"]["download_url"])
    assert download.status_code == 200
    assert download.content


def test_v3_preview_image_generates_downloadable_file(tmp_path: Path) -> None:
    image_path = _make_image(tmp_path / "input-v3.jpg", size=(900, 600))

    response = _post_image("/tools/watermark/api/preview", image_path)

    assert response.status_code == 200, response.json()
    payload = response.json()
    assert payload["ok"] is True
    filename = payload["file"]["filename"]
    assert filename.startswith("preview-")
    assert (settings.output_dir / filename).exists()


def test_legacy_config_is_removed(tmp_path: Path) -> None:
    image_path = _make_image(tmp_path / "legacy.jpg")

    response = _post_image("/tools/watermark/api/process", image_path, _legacy_config())

    assert response.status_code == 410
    assert response.json()["error"]["code"] == "legacy_config_removed"


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

    response = _post_image("/tools/watermark/api/process", image_path)

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

    response = _post_image("/tools/watermark/api/preview", image_path)

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
            "/tools/watermark/api/process",
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
            "/tools/watermark/api/process",
            files={"file": ("input.txt", file, "text/plain")},
            data={"config": json.dumps(_minimal_v3_config())},
        )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_v3_custom_text_is_never_evaluated_as_jinja(tmp_path: Path, monkeypatch) -> None:
    image_path = _make_image(tmp_path / "literal-v3.jpg")
    captured: dict = {}

    def fake_start_process(**kwargs):
        captured.update(kwargs)
        Image.new("RGB", (16, 16)).save(kwargs["output_path"])

    monkeypatch.setattr(web_processing, "start_process", fake_start_process)
    response = _post_image(
        "/tools/watermark/api/process",
        image_path,
        _minimal_v3_config(custom_text="probe={{ 7 * 7 }}"),
    )

    assert response.status_code == 200
    chips = captured["data"][0]["v3_config"]["regions"][0]["slots"]["left-top"]["content"]["chips"]
    assert chips[0]["custom_text"] == "probe={{ 7 * 7 }}"


def test_rejects_non_finite_and_oversized_config(tmp_path: Path) -> None:
    image_path = _make_image(tmp_path / "bad-config.jpg")

    with image_path.open("rb") as file:
        non_finite = client.post(
            "/tools/watermark/api/process",
            files={"file": (image_path.name, file, "image/jpeg")},
            data={"config": '{"regions": [], "custom_text": NaN}'},
        )
    assert non_finite.status_code == 400
    assert non_finite.json()["error"]["code"] == "invalid_config_json"

    with image_path.open("rb") as file:
        oversized = client.post(
            "/tools/watermark/api/process",
            files={"file": (image_path.name, file, "image/jpeg")},
            data={"config": json.dumps({"regions": [], "padding": "x" * (64 * 1024)})},
        )
    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "config_too_large"


def test_rejects_arbitrary_server_resource_path(tmp_path: Path) -> None:
    image_path = _make_image(tmp_path / "path.jpg")
    config = _minimal_v3_config()
    slot = config["regions"][0]["slots"]["left-top"]
    slot["content"] = {"path": "/etc/passwd", "color": "#D8D8D6"}

    response = _post_image("/tools/watermark/api/process", image_path, config)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_config"


def test_upload_once_then_process_by_image_id(tmp_path: Path) -> None:
    image_path = _make_image(tmp_path / "reused.jpg")
    with image_path.open("rb") as file:
        upload = client.post("/tools/watermark/api/uploads", files={"file": (image_path.name, file, "image/jpeg")})
    assert upload.status_code == 200

    response = client.post(
        "/tools/watermark/api/preview",
        data={"image_id": upload.json()["image_id"], "config": json.dumps(_minimal_v3_config())},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
