"""Shared watermark field registry.

This registry is the stable mapping between persisted field IDs, legacy Chinese
labels, legacy template source IDs, and the Jinja expressions used by the image
processor. It must remain independent from any GUI module so Web APIs can reuse
exactly the same field semantics.
"""

from __future__ import annotations

from dataclasses import dataclass

_JINJA_DATE = (
    "{{(exif.DateTimeOriginal or exif.CreateDate or exif.DigitalCreationDate "
    "or exif.DateCreated or exif.DateTimeCreated "
    "or exif.DigitalCreationDateTime|default('0'))[:16]}}"
)


@dataclass(frozen=True)
class FieldDef:
    """Metadata for a watermark field."""

    field_id: str
    label_zh: str
    jinja_template: str
    source_id: str = ""
    category: str = "exif"


_FIELDS: list[FieldDef] = [
    FieldDef(
        field_id="camera_model",
        label_zh="相机型号",
        jinja_template="{{ exif.CameraModelName|default('-') | replace('_', '') }}",
        source_id="exif:CameraModelName",
        category="exif",
    ),
    FieldDef(
        field_id="lens_model",
        label_zh="镜头型号",
        jinja_template="{{ exif.LensModel | default('-')}}",
        source_id="exif:LensModel",
        category="exif",
    ),
    FieldDef(
        field_id="focal_length",
        label_zh="焦距",
        jinja_template="{{exif.FocalLengthIn35mmFormat|replace(' ', '')|replace('mm', '')|default('-')}}mm",
        source_id="exif:FocalLengthIn35mmFormat",
        category="exif",
    ),
    FieldDef(
        field_id="aperture",
        label_zh="光圈",
        jinja_template="f/{{exif.ApertureValue or exif.FNumber|default('-')}}",
        source_id="exif:Aperture",
        category="exif",
    ),
    FieldDef(
        field_id="shutter",
        label_zh="快门",
        jinja_template="{{exif.ShutterSpeed or exif.ShutterSpeedValue|default('-')}}s",
        source_id="exif:ShutterSpeed",
        category="exif",
    ),
    FieldDef(
        field_id="iso",
        label_zh="ISO",
        jinja_template="ISO{{exif.ISO|default('0')}}",
        source_id="exif:ISO",
        category="exif",
    ),
    FieldDef(
        field_id="datetime",
        label_zh="拍摄日期",
        jinja_template=_JINJA_DATE,
        source_id="exif:DateTimeOriginal",
        category="exif",
    ),
    FieldDef(
        field_id="make",
        label_zh="厂商品牌",
        jinja_template="{{ exif.Make|default('-') }}",
        source_id="exif:Make",
        category="exif",
    ),
    FieldDef(
        field_id="artist",
        label_zh="作者",
        jinja_template="{{ exif.Artist|default('-') }}",
        source_id="exif:Artist",
        category="exif",
    ),
    FieldDef(
        field_id="gps",
        label_zh="地理位置",
        jinja_template="{{ exif.GPSLatitude|default('-') }}, {{ exif.GPSLongitude|default('-') }}",
        source_id="exif:GPSInfo",
        category="exif",
    ),
    FieldDef(
        field_id="custom_text",
        label_zh="自定义文本",
        jinja_template="",
        source_id="custom",
        category="custom",
    ),
    FieldDef(
        field_id="empty",
        label_zh="空",
        jinja_template="",
        source_id="empty",
        category="empty",
    ),
]


class FieldRegistry:
    """Registry of supported watermark fields."""

    def __init__(self, fields: list[FieldDef] | None = None) -> None:
        self._fields: list[FieldDef] = list(fields) if fields is not None else list(_FIELDS)
        self._by_id: dict[str, FieldDef] = {f.field_id: f for f in self._fields}
        self._by_label: dict[str, FieldDef] = {f.label_zh: f for f in self._fields}
        self._by_source: dict[str, FieldDef] = {
            f.source_id: f for f in self._fields if f.source_id
        }

    def all(self) -> list[FieldDef]:
        """Return all fields in registry order."""

        return list(self._fields)

    def get(self, field_id: str) -> FieldDef | None:
        """Find by stable field ID."""

        return self._by_id.get(field_id)

    def get_by_label(self, label_zh: str) -> FieldDef | None:
        """Find by legacy Chinese GUI label."""

        return self._by_label.get(label_zh)

    def get_by_source(self, source_id: str) -> FieldDef | None:
        """Find by legacy template-builder source ID."""

        return self._by_source.get(source_id)

    def get_by_jinja(self, jinja_template: str) -> FieldDef | None:
        """Find by exact Jinja template string."""

        for field in self._fields:
            if field.jinja_template and field.jinja_template == jinja_template:
                return field
        return None

    def resolve(self, key: str) -> FieldDef | None:
        """Resolve by field ID, Chinese label, or legacy source ID."""

        return self._by_id.get(key) or self._by_label.get(key) or self._by_source.get(key)

    def labels_for_category(self, category: str) -> list[str]:
        """Return Chinese labels for a category."""

        return [field.label_zh for field in self._fields if field.category == category]

    def gui_choices(self) -> list[str]:
        """Return GUI choices in default order, excluding the empty placeholder."""

        return [field.label_zh for field in self._fields if field.field_id != "empty"]


DEFAULT_REGISTRY = FieldRegistry()


def get_default_registry() -> FieldRegistry:
    """Return the process-wide default field registry."""

    return DEFAULT_REGISTRY
