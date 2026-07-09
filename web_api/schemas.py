"""Strict public request schemas and internal config conversion."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from shared.watermark_schema import (
    AdvancedConfig,
    CornerConfig,
    FieldChip,
    LogoConfig,
    SignatureConfig,
    WatermarkConfig,
)
from web_api.errors import ApiError

Color = str
ResourceId = str


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class FieldChipPayload(StrictModel):
    field_id: Literal[
        "camera_model", "lens_model", "focal_length", "aperture", "shutter",
        "iso", "datetime", "make", "artist", "gps", "custom_text", "empty",
    ] = "empty"
    custom_text: str = Field(default="", max_length=160)


class CornerPayload(StrictModel):
    chips: list[FieldChipPayload] = Field(default_factory=list, max_length=12)
    separator: str = Field(default=" ", max_length=8)
    font_size_ratio: float = Field(default=0.0, ge=0.0, le=0.2)


class LogoPayload(StrictModel):
    enabled: Literal["auto", "disabled", "custom"] = "auto"
    position: Literal["left", "center", "right"] = "right"
    color: Color = "#D8D8D6"
    custom_path: ResourceId = Field(
        default="",
        max_length=128,
        pattern=r"^(?:[A-Za-z0-9_-]{20,64}\.(?:png|jpg|jpeg|webp))?$",
    )
    free_position: bool = False
    anchor: Literal[
        "top_left", "top_center", "top_right", "middle_left", "middle_center",
        "middle_right", "bottom_left", "bottom_center", "bottom_right",
    ] = "middle_center"
    margin_x: float = Field(default=0.0, ge=-0.5, le=0.5)
    margin_y: float = Field(default=0.0, ge=-0.5, le=0.5)
    size_ratio: float = Field(default=0.2, ge=0.01, le=1.0)

    @field_validator("color")
    @classmethod
    def valid_color(cls, value: str) -> str:
        return _validate_color(value)


class SignaturePayload(StrictModel):
    enabled: bool = False
    path: ResourceId = Field(
        default="",
        max_length=128,
        pattern=r"^(?:[A-Za-z0-9_-]{20,64}\.(?:png|jpg|jpeg|webp))?$",
    )
    invert_mono: bool = False
    enhancement: Literal["none", "soft_shadow", "soft_glow", "soft_outline"] = "none"
    enhancement_strength: int = Field(default=50, ge=0, le=100)
    anchor: Literal[
        "top_left", "top_center", "top_right", "middle_left", "middle_center",
        "middle_right", "bottom_left", "bottom_center", "bottom_right",
    ] = "middle_center"
    margin_x: float = Field(default=0.0, ge=-0.5, le=0.5)
    margin_y: float = Field(default=0.0, ge=-0.5, le=0.5)
    size_ratio: float = Field(default=0.2, ge=0.01, le=1.0)


class AdvancedPayload(StrictModel):
    footer_height_px: int = Field(default=120, ge=0, le=600)
    logo_height_px: int = Field(default=0, ge=0, le=300)
    corner_text_ratio: float = Field(default=0.0, ge=0.0, le=0.2)
    global_font: Literal["NotoSansCJKsc-Regular.otf", "NotoSansCJKsc-Bold.otf"] = "NotoSansCJKsc-Bold.otf"
    global_color: Color = "#242424"
    margin_color: Color = "#FFFFFF"
    left_margin: int = Field(default=0, ge=0, le=600)
    right_margin: int = Field(default=0, ge=0, le=600)
    top_margin: int = Field(default=0, ge=0, le=600)
    bottom_margin: int = Field(default=0, ge=0, le=600)
    border_radius: int = Field(default=0, ge=0, le=300)
    shadow_radius: int = Field(default=0, ge=0, le=120)
    shadow_color: Color = "#000000"
    blur_radius: int = Field(default=0, ge=0, le=60)
    quality: int = Field(default=95, ge=70, le=100)
    subsampling: Literal[0, 1, 2] = 0
    scale: float = Field(default=1.0, ge=0.1, le=2.0)
    trim_enabled: bool = False
    trim_threshold: float = Field(default=0.0, ge=0.0, le=255.0)
    ratio_enabled: bool = False
    ratio: str = Field(default="3:4", pattern=r"^[1-9][0-9]?:[1-9][0-9]?$", max_length=5)
    concat_direction: Literal["horizontal", "vertical"] = "vertical"
    alignment_mode: Literal["top", "center", "bottom"] = "center"

    @field_validator("global_color", "margin_color", "shadow_color")
    @classmethod
    def valid_color(cls, value: str) -> str:
        return _validate_color(value)


class CornersPayload(StrictModel):
    left_top: CornerPayload = Field(default_factory=CornerPayload)
    left_bottom: CornerPayload = Field(default_factory=CornerPayload)
    right_top: CornerPayload = Field(default_factory=CornerPayload)
    right_bottom: CornerPayload = Field(default_factory=CornerPayload)


class WatermarkPayload(StrictModel):
    corners: CornersPayload = Field(default_factory=CornersPayload)
    logo: LogoPayload = Field(default_factory=LogoPayload)
    signature: SignaturePayload = Field(default_factory=SignaturePayload)
    advanced: AdvancedPayload = Field(default_factory=AdvancedPayload)
    custom_text: str = Field(default="", max_length=160)
    footer_position: Literal["bottom", "top", "left", "right"] = "bottom"
    layout_mode: Literal["corners", "sides"] = "corners"


def _validate_color(value: str) -> str:
    if len(value) != 7 or not value.startswith("#"):
        raise ValueError("颜色必须使用 #RRGGBB 格式")
    try:
        int(value[1:], 16)
    except ValueError as exc:
        raise ValueError("颜色必须使用 #RRGGBB 格式") from exc
    return value.upper()


def config_from_payload(payload: dict[str, Any] | None) -> WatermarkConfig:
    try:
        parsed = WatermarkPayload.model_validate(payload or {})
    except ValidationError as exc:
        first = exc.errors(include_url=False)[0]
        location = ".".join(str(part) for part in first["loc"])
        raise ApiError(
            code="invalid_config",
            message="水印配置不合法",
            status_code=422,
            detail=f"{location}: {first['msg']}",
        ) from exc

    corners = parsed.corners
    return WatermarkConfig(
        left_top=_corner(corners.left_top),
        left_bottom=_corner(corners.left_bottom),
        right_top=_corner(corners.right_top),
        right_bottom=_corner(corners.right_bottom),
        logo=LogoConfig(**parsed.logo.model_dump()),
        signature=SignatureConfig(**parsed.signature.model_dump()),
        advanced=AdvancedConfig(**parsed.advanced.model_dump()),
        custom_text=parsed.custom_text,
        footer_position=parsed.footer_position,
        layout_mode=parsed.layout_mode,
    )


def _corner(value: CornerPayload) -> CornerConfig:
    return CornerConfig(
        chips=[FieldChip(**chip.model_dump()) for chip in value.chips],
        separator=value.separator,
        font_size_ratio=value.font_size_ratio,
    )


def success_response(**data: Any) -> dict[str, Any]:
    return {"ok": True, **data}
