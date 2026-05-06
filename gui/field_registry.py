"""字段注册表 — Phase 6.4。

把原先散落在 :mod:`gui.template_assembler`（3 处重复）和
:mod:`core.template_builder`（if/elif 链）的字段枚举统一收编到这里。

每个 :class:`FieldDef` 描述一种水印字段：

- ``field_id``：稳定英文 ID（用于 JSON 持久化、JSON 模板 source 字段）
- ``label_zh``：GUI 中文展示标签（向后兼容老 user.json 中文字段）
- ``jinja_template``：渲染时使用的 Jinja2 表达式
- ``source_id``：与旧 :mod:`core.template_builder` 兼容的 ``exif:CameraModelName`` 风格 ID
- ``category``：字段分组（用于 UI 分组下拉框）

使用：

>>> from gui.field_registry import FieldRegistry
>>> reg = FieldRegistry()
>>> reg.get("camera_model").jinja_template
"{{ exif.CameraModelName|default('-') | replace('_', '') }}"
>>> reg.get_by_label("相机型号").field_id
'camera_model'
>>> reg.get_by_source("exif:CameraModelName").field_id
'camera_model'
"""

from __future__ import annotations

from dataclasses import dataclass

# ---- 公共 Jinja 片段（避免在多个地方重复硬编码） ----

_JINJA_PARAMS = (
    "{{exif.FocalLengthIn35mmFormat|replace(' ', '')|default('-')}} "
    "f/{{exif.ApertureValue or exif.FNumber|default('-')}} "
    "{{exif.ShutterSpeed or exif.ShutterSpeedValue|default('-')}}s "
    "ISO{{exif.ISO|default('0')}}"
)

_JINJA_DATE = (
    "{{(exif.DateTimeOriginal or exif.CreateDate or exif.DigitalCreationDate "
    "or exif.DateCreated or exif.DateTimeCreated "
    "or exif.DigitalCreationDateTime|default('0'))[:16]}}"
)


@dataclass(frozen=True)
class FieldDef:
    """单个字段的元信息（不可变）。"""

    field_id: str          # 稳定英文 ID（snake_case）
    label_zh: str          # 中文 GUI 标签
    jinja_template: str    # 渲染所用 Jinja2 表达式
    source_id: str = ""    # core.template_builder 旧 ID（如 ``exif:CameraModelName``）；空表示该字段无对应旧 ID
    category: str = "exif"  # 分组：``exif`` / ``custom`` / ``empty``


# ---- 注册表数据 ----

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
        field_id="params",
        label_zh="拍摄参数",
        jinja_template=_JINJA_PARAMS,
        source_id="exif:params",
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
        field_id="gps",
        label_zh="地理位置",
        jinja_template="{{ exif.GPSLatitude|default('-') }}, {{ exif.GPSLongitude|default('-') }}",
        source_id="exif:GPSInfo",
        category="exif",
    ),
    FieldDef(
        field_id="custom_text",
        label_zh="自定义文本",
        jinja_template="",  # 占位，由 chip.custom_text 在运行时注入
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
    """字段注册中心 — 单例式访问；可注入新字段以做扩展。"""

    def __init__(self, fields: list[FieldDef] | None = None) -> None:
        # 注意：显式传入空列表应被尊重（不要回退到默认）；只有 None 才使用默认。
        self._fields: list[FieldDef] = list(fields) if fields is not None else list(_FIELDS)
        self._by_id: dict[str, FieldDef] = {f.field_id: f for f in self._fields}
        self._by_label: dict[str, FieldDef] = {f.label_zh: f for f in self._fields}
        self._by_source: dict[str, FieldDef] = {
            f.source_id: f for f in self._fields if f.source_id
        }

    # ---- 查询 ----

    def all(self) -> list[FieldDef]:
        """返回全部字段（保持注册顺序）。"""
        return list(self._fields)

    def get(self, field_id: str) -> FieldDef | None:
        """按 ``field_id`` 精确查找，未命中返回 ``None``。"""
        return self._by_id.get(field_id)

    def get_by_label(self, label_zh: str) -> FieldDef | None:
        """按中文标签查找（用于读取老 user.json）。"""
        return self._by_label.get(label_zh)

    def get_by_source(self, source_id: str) -> FieldDef | None:
        """按旧 source_id 查找（用于读取老模板 JSON）。"""
        return self._by_source.get(source_id)

    def get_by_jinja(self, jinja_template: str) -> FieldDef | None:
        """按 Jinja 模板字符串反查（用于 ``_apply_watermark_config`` 反序列化）。"""
        for f in self._fields:
            if f.jinja_template and f.jinja_template == jinja_template:
                return f
        return None

    # ---- 解析 / 解析快捷方式 ----

    def resolve(self, key: str) -> FieldDef | None:
        """按任意标识符查找（field_id → label_zh → source_id 优先级）。"""
        return (
            self._by_id.get(key)
            or self._by_label.get(key)
            or self._by_source.get(key)
        )

    def labels_for_category(self, category: str) -> list[str]:
        """返回某个分组下所有中文标签（用于 GUI 下拉框）。"""
        return [f.label_zh for f in self._fields if f.category == category]

    def gui_choices(self) -> list[str]:
        """返回 GUI 下拉框默认顺序的中文标签列表（不含 ``空``）。"""
        return [f.label_zh for f in self._fields if f.field_id != "empty"]


# ---- 默认共享实例（应用全局唯一） ----

DEFAULT_REGISTRY = FieldRegistry()


def get_default_registry() -> FieldRegistry:
    """获取默认注册表单例。"""
    return DEFAULT_REGISTRY
