"""Pure watermark configuration schema shared by desktop and Web.

The classes in this module intentionally avoid any UI framework dependency. They
represent the domain configuration that can be persisted, validated, converted to
processor JSON, or transported through a Web API.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from typing import Any, TypeVar


@dataclass
class FieldChip:
    """A single text field chip rendered in a watermark corner."""

    field_id: str = "empty"
    custom_text: str = ""


@dataclass
class CornerConfig:
    """Watermark configuration for one corner."""

    chips: list[FieldChip] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)
    separator: str = " "
    font_size_ratio: float = 0.0


@dataclass
class LogoConfig:
    """Logo placement and source configuration."""

    enabled: str = "auto"  # auto / disabled / custom
    position: str = "right"  # right / center / left
    color: str = "#D8D8D6"
    custom_path: str = ""
    # Free-positioning mode (脱离底条自由定位)
    free_position: bool = False
    anchor: str = "middle_center"
    margin_x: float = 0.0
    margin_y: float = 0.0
    size_ratio: float = 0.20


@dataclass
class SignatureConfig:
    """Signature watermark placement and style configuration."""

    enabled: bool = False
    path: str = ""
    invert_mono: bool = False
    enhancement: str = "none"
    enhancement_strength: int = 50
    anchor: str = "middle_center"
    margin_x: float = 0.0
    margin_y: float = 0.0
    size_ratio: float = 0.20


@dataclass
class AdvancedConfig:
    """Global image/watermark processing options."""

    global_font: str = "NotoSansCJKsc-Bold.otf"
    global_color: str = "#242424"

    corner_text_ratio: float = 0.0
    footer_height_px: int = 120
    logo_height_px: int = 0

    left_margin: int = 0
    right_margin: int = 0
    top_margin: int = 0
    bottom_margin: int = 0
    margin_color: str = "#FFFFFF"

    border_radius: int = 0
    shadow_radius: int = 0
    shadow_color: str = "#000000"

    quality: int = 95
    subsampling: int = 0

    blur_radius: int = 0
    ratio_enabled: bool = False
    ratio: str = "3:4"

    scale: float = 1.0
    trim_enabled: bool = False
    trim_threshold: float = 0.0

    concat_direction: str = "vertical"
    alignment_mode: str = "center"

    # --- Frame mode (白边相框) ---
    frame_border_width: int = 40         # 白边宽度 (px)，0=关闭
    frame_bar_bg: str = "#FFFFFF"        # 信息条底色
    frame_text_primary: str = "#333333"  # 型号/镜头文字色
    frame_text_secondary: str = "#888888" # 参数文字色

    # Legacy signature fields (kept for backward compatibility with desktop)
    signature_enabled: bool = False
    signature_path: str = ""
    signature_enhancement: str = "none"
    signature_enhancement_strength: int = 50
    signature_invert_mono: bool = False
    signature_anchor: str = "middle_center"
    signature_margin_x: float = 0.0
    signature_margin_y: float = 0.0
    signature_size_ratio: float = 0.20


@dataclass
class OutputConfig:
    """Output path and overwrite policy for desktop batch processing."""

    path: str = "{source_dir}/output"
    override: bool = True


@dataclass
class WatermarkConfig:
    """Complete watermark configuration independent from runtime UI state."""

    left_top: CornerConfig = field(default_factory=CornerConfig)
    left_bottom: CornerConfig = field(default_factory=CornerConfig)
    right_top: CornerConfig = field(default_factory=CornerConfig)
    right_bottom: CornerConfig = field(default_factory=CornerConfig)
    # Side-bar config (used by layout_mode=sides and layout_mode=framed)
    left_side: CornerConfig = field(default_factory=CornerConfig)
    right_side: CornerConfig = field(default_factory=CornerConfig)
    logo: LogoConfig = field(default_factory=LogoConfig)
    custom_text: str = ""
    signature: SignatureConfig = field(default_factory=SignatureConfig)
    advanced: AdvancedConfig = field(default_factory=AdvancedConfig)
    footer_position: str = "bottom"
    layout_mode: str = "corners"


T = TypeVar("T")


__all__ = [
    "AdvancedConfig",
    "CornerConfig",
    "FieldChip",
    "LogoConfig",
    "OutputConfig",
    "SignatureConfig",
    "WatermarkConfig",
    "dataclass_from_dict",
    "dataclass_to_dict",
]


def dataclass_to_dict(obj: Any) -> dict[str, Any]:
    """Serialize a dataclass object to a plain dictionary."""

    return asdict(obj)


def dataclass_from_dict(cls: type[T], data: dict[str, Any] | None) -> T:  # noqa: UP047
    """Build a dataclass from a dict, ignoring unknown fields.

    Invalid payloads fall back to class defaults. This keeps old user configs and
    Web API payloads forward-compatible while preventing accidental attribute
    injection.
    """

    if not isinstance(data, dict):
        return cls()
    if not is_dataclass(cls):
        return cls()
    valid_keys = {f.name for f in fields(cls)}
    filtered = {k: v for k, v in data.items() if k in valid_keys}
    try:
        return cls(**filtered)
    except (TypeError, ValueError):
        return cls()
