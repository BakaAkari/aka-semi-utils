"""Phase 6.9 — FieldRegistry 单元测试。

覆盖：
- 默认 12 个字段的 ID / label / source / jinja 查询（Phase 16：params 套餐拆分为 4 个 + 新增 artist）
- ``resolve`` 优先级（field_id → label_zh → source_id）
- ``labels_for_category`` 分组过滤
- ``gui_choices`` 排除 ``empty``
- 自定义字段注入扩展
- ``DEFAULT_REGISTRY`` 单例性
"""

from __future__ import annotations

import pytest

from gui.field_registry import (
    DEFAULT_REGISTRY,
    FieldDef,
    FieldRegistry,
    get_default_registry,
)

# ============================================================
# 默认字段查询
# ============================================================

class TestFieldRegistryLookups:
    """验证默认 12 个字段每种查询方式都能命中。"""

    def setup_method(self):
        self.reg = FieldRegistry()

    def test_all_returns_default_fields(self):
        all_fields = self.reg.all()
        assert len(all_fields) == 12
        ids = [f.field_id for f in all_fields]
        assert ids == [
            "camera_model",
            "lens_model",
            "focal_length",
            "aperture",
            "shutter",
            "iso",
            "datetime",
            "make",
            "artist",
            "gps",
            "custom_text",
            "empty",
        ]

    def test_get_by_field_id(self):
        f = self.reg.get("camera_model")
        assert f is not None
        assert f.label_zh == "相机型号"
        assert "CameraModelName" in f.jinja_template

    def test_get_unknown_id_returns_none(self):
        assert self.reg.get("not_a_real_field") is None
        assert self.reg.get("") is None

    def test_get_by_label(self):
        assert self.reg.get_by_label("镜头型号").field_id == "lens_model"
        assert self.reg.get_by_label("焦距").field_id == "focal_length"
        assert self.reg.get_by_label("光圈").field_id == "aperture"
        assert self.reg.get_by_label("快门").field_id == "shutter"
        assert self.reg.get_by_label("ISO").field_id == "iso"
        assert self.reg.get_by_label("拍摄日期").field_id == "datetime"
        assert self.reg.get_by_label("厂商品牌").field_id == "make"
        assert self.reg.get_by_label("作者").field_id == "artist"
        assert self.reg.get_by_label("地理位置").field_id == "gps"
        assert self.reg.get_by_label("自定义文本").field_id == "custom_text"
        assert self.reg.get_by_label("空").field_id == "empty"

    def test_get_by_label_unknown(self):
        assert self.reg.get_by_label("不存在的标签") is None

    def test_get_by_source(self):
        assert self.reg.get_by_source("exif:CameraModelName").field_id == "camera_model"
        assert self.reg.get_by_source("exif:LensModel").field_id == "lens_model"
        assert self.reg.get_by_source("exif:FocalLengthIn35mmFormat").field_id == "focal_length"
        assert self.reg.get_by_source("exif:Aperture").field_id == "aperture"
        assert self.reg.get_by_source("exif:ShutterSpeed").field_id == "shutter"
        assert self.reg.get_by_source("exif:ISO").field_id == "iso"
        assert self.reg.get_by_source("exif:DateTimeOriginal").field_id == "datetime"
        assert self.reg.get_by_source("exif:Artist").field_id == "artist"
        assert self.reg.get_by_source("custom").field_id == "custom_text"

    def test_get_by_source_unknown(self):
        assert self.reg.get_by_source("exif:DoesNotExist") is None

    def test_get_by_source_empty_string_not_indexed(self):
        """``custom_text`` / ``empty`` 等空 source 字段不应被空字符串误中。"""
        # custom_text 的 source_id 是 "custom"，不是 ""
        # 真正空 source_id 字段不会被索引（构造器有 if f.source_id 守卫）
        assert self.reg.get_by_source("") is None

    def test_get_by_jinja_camera(self):
        f = self.reg.get_by_jinja(
            "{{ exif.CameraModelName|default('-') | replace('_', '') }}"
        )
        assert f is not None
        assert f.field_id == "camera_model"

    def test_get_by_jinja_unknown(self):
        assert self.reg.get_by_jinja("{{ exif.NonExistent }}") is None

    def test_get_by_jinja_empty_template_returns_none(self):
        """custom_text / empty 的 jinja_template 都是空串；空查询不应误中它们。"""
        assert self.reg.get_by_jinja("") is None


# ============================================================
# resolve 优先级
# ============================================================

class TestResolve:

    def setup_method(self):
        self.reg = FieldRegistry()

    def test_resolve_by_id(self):
        assert self.reg.resolve("camera_model").field_id == "camera_model"

    def test_resolve_by_label(self):
        assert self.reg.resolve("镜头型号").field_id == "lens_model"

    def test_resolve_by_source(self):
        assert self.reg.resolve("exif:DateTimeOriginal").field_id == "datetime"

    def test_resolve_unknown(self):
        assert self.reg.resolve("garbage") is None

    def test_resolve_priority_id_over_label(self):
        """若同一字符串既是 id 又是 label，应优先取 id。"""
        custom = FieldRegistry(fields=[
            FieldDef(field_id="X", label_zh="Y", jinja_template="{{x}}"),
            FieldDef(field_id="Y", label_zh="Z", jinja_template="{{y}}"),
        ])
        # "Y" 既是字段 X 的 label 又是字段 Y 的 id → 优先 id
        result = custom.resolve("Y")
        assert result is not None
        assert result.field_id == "Y"


# ============================================================
# 分组过滤 / GUI 选项
# ============================================================

class TestCategoryFiltering:

    def setup_method(self):
        self.reg = FieldRegistry()

    def test_labels_for_exif(self):
        labels = self.reg.labels_for_category("exif")
        assert "相机型号" in labels
        assert "镜头型号" in labels
        assert "焦距" in labels
        assert "光圈" in labels
        assert "快门" in labels
        assert "ISO" in labels
        assert "拍摄日期" in labels
        assert "厂商品牌" in labels
        assert "作者" in labels
        assert "地理位置" in labels
        assert "拍摄参数" not in labels  # Phase 16：套餐已拆分
        assert "自定义文本" not in labels  # custom 分组
        assert "空" not in labels           # empty 分组

    def test_labels_for_custom(self):
        labels = self.reg.labels_for_category("custom")
        assert labels == ["自定义文本"]

    def test_labels_for_empty(self):
        labels = self.reg.labels_for_category("empty")
        assert labels == ["空"]

    def test_labels_for_unknown_category(self):
        assert self.reg.labels_for_category("not_a_category") == []

    def test_gui_choices_excludes_empty(self):
        choices = self.reg.gui_choices()
        assert "空" not in choices
        assert len(choices) == 11  # 12 - 1
        assert choices[0] == "相机型号"  # 注册顺序保留


# ============================================================
# 扩展性
# ============================================================

class TestExtensibility:

    def test_inject_custom_fields(self):
        custom = FieldRegistry(fields=[
            FieldDef(
                field_id="weather",
                label_zh="天气",
                jinja_template="{{ exif.Weather }}",
                source_id="exif:Weather",
                category="exif",
            ),
        ])
        assert len(custom.all()) == 1
        assert custom.get("weather").label_zh == "天气"
        assert custom.get_by_label("天气").field_id == "weather"
        assert custom.get_by_source("exif:Weather").field_id == "weather"

    def test_empty_registry(self):
        empty = FieldRegistry(fields=[])
        assert empty.all() == []
        assert empty.get("any") is None
        assert empty.gui_choices() == []
        assert empty.labels_for_category("exif") == []


# ============================================================
# 默认单例
# ============================================================

class TestDefaultRegistry:

    def test_default_registry_is_singleton(self):
        a = get_default_registry()
        b = get_default_registry()
        assert a is b
        assert a is DEFAULT_REGISTRY

    def test_default_registry_has_default_fields(self):
        assert len(get_default_registry().all()) == 12


# ============================================================
# FieldDef 不可变性
# ============================================================

class TestFieldDefImmutable:

    def test_frozen(self):
        from dataclasses import FrozenInstanceError
        f = FieldDef(field_id="a", label_zh="A", jinja_template="{{a}}")
        with pytest.raises(FrozenInstanceError):
            f.field_id = "b"  # type: ignore[misc]
