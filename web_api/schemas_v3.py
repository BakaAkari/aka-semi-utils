"""V3 watermark request schemas and payload validation.

Mirrors the TypeScript types in web_frontend/src/v3Types.ts.
All validators are strict (extra=forbid) to prevent accidental field injection.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from web_api.errors import ApiError

Color = str


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


# ── Leaf models ──────────────────────────────────────────────────────────


class FieldChipPayload(StrictModel):
    field_id: Literal[
        "camera_model", "lens_model", "focal_length", "aperture", "shutter",
        "iso", "datetime", "make", "artist", "gps", "custom_text", "empty",
    ] = "empty"
    custom_text: str = Field(default="", max_length=160)


class TextContentPayload(StrictModel):
    chips: list[FieldChipPayload] = Field(default_factory=list, max_length=20)
    separator: str = Field(default=" ", max_length=8)


class LogoContentPayload(StrictModel):
    path: str = Field(default="", max_length=256)
    color: Color = "#D8D8D6"

    @field_validator("color")
    @classmethod
    def valid_color(cls, value: str) -> str:
        return _validate_color(value)


class SignatureContentPayload(StrictModel):
    path: str = Field(default="", max_length=256)
    invert_mono: bool = False
    size_ratio: float = Field(default=0.20, ge=0.01, le=1.0)


class StyleConfigPayload(StrictModel):
    font_size: int | None = Field(default=None, ge=4, le=200)
    font_size_ratio: float | None = Field(default=None, ge=0.0, le=0.5)
    size_reference: Literal["region_height", "short_edge", "long_edge"] = "region_height"
    color: Color = "#222222"
    font_family: str = Field(default="NotoSansCJKsc-Bold.otf", max_length=128)
    bold: bool = True
    line_height: float = Field(default=1.2, ge=0.5, le=3.0)

    @field_validator("color")
    @classmethod
    def valid_color(cls, value: str) -> str:
        return _validate_color(value)


class SlotConfigPayload(StrictModel):
    enabled: bool = False
    content: TextContentPayload | LogoContentPayload | SignatureContentPayload | None = None
    style: StyleConfigPayload | None = None


class WidthPayload(StrictModel):
    mode: Literal["pixel", "short_edge_ratio"] = "short_edge_ratio"
    value: float = Field(default=0.05, ge=0.0, le=1.0)


class RegionConfigPayload(StrictModel):
    id: str = Field(default="", max_length=64)
    type: Literal["footer-bar", "side-edge", "free"] = "footer-bar"
    enabled: bool = True
    slots: dict[str, SlotConfigPayload] = Field(default_factory=dict)
    edge: Literal["left", "right"] | None = None
    width: WidthPayload | None = None
    alignment: Literal["start", "center", "end"] | None = "start"
    anchor: str | None = None
    offset_x: float = 0.0
    offset_y: float = 0.0
    offset_unit: Literal["pixel", "short_edge_ratio"] = "short_edge_ratio"


class MarginsConfigPayload(StrictModel):
    top: int = Field(default=0, ge=0, le=600)
    right: int = Field(default=0, ge=0, le=600)
    bottom: int = Field(default=0, ge=0, le=600)
    left: int = Field(default=0, ge=0, le=600)


class CanvasConfigPayload(StrictModel):
    margins: MarginsConfigPayload = Field(default_factory=MarginsConfigPayload)
    background: Color = "#FFFFFF"
    border_radius: int = Field(default=0, ge=0, le=300)

    @field_validator("background")
    @classmethod
    def valid_color(cls, value: str) -> str:
        return _validate_color(value)


# ── Root payload ─────────────────────────────────────────────────────────


class WatermarkPayloadV3(StrictModel):
    canvas: CanvasConfigPayload = Field(default_factory=CanvasConfigPayload)
    regions: list[RegionConfigPayload] = Field(default_factory=list, max_length=10)
    defaults: StyleConfigPayload = Field(default_factory=StyleConfigPayload)
    custom_text: str = Field(default="", max_length=160)


# ── Helpers ──────────────────────────────────────────────────────────────


def is_v3_payload(payload: dict[str, Any]) -> bool:
    """Heuristic: V3 payloads always contain a ``regions`` list."""
    return isinstance(payload, dict) and "regions" in payload


def validate_v3_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Validate a V3 config dict and return the cleaned dict.

    Raises ApiError (422) on validation failure.
    """
    try:
        parsed = WatermarkPayloadV3.model_validate(payload or {})
    except ValidationError as exc:
        first = exc.errors(include_url=False)[0]
        location = ".".join(str(part) for part in first["loc"])
        raise ApiError(
            code="invalid_config",
            message="水印配置不合法",
            status_code=422,
            detail=f"{location}: {first['msg']}",
        ) from exc
    # Return as plain dict so downstream can use _dict_to_watermark_config
    return parsed.model_dump()


def _validate_color(value: str) -> str:
    if len(value) != 7 or not value.startswith("#"):
        raise ValueError("颜色必须使用 #RRGGBB 格式")
    try:
        int(value[1:], 16)
    except ValueError as exc:
        raise ValueError("颜色必须使用 #RRGGBB 格式") from exc
    return value.upper()
