"""Phase 6.9 — CornerConfig chip 迁移与序列化单元测试。

覆盖：
- ``_corner_from_dict`` 老格式（仅 ``fields`` 中文标签）→ 新 ``chips`` 列表的迁移
- ``_corner_from_dict`` 新格式（``chips`` 列表）正常反序列化
- ``_corner_from_dict`` 同时含两者时优先使用 ``chips``
- ``_corner_to_dict`` round-trip 等价
- 边界：空 dict / None / 无效条目
- ``font`` / ``color`` 默认值（空字符串 = 继承上级）
"""

from __future__ import annotations

from gui.models import (
    CornerConfig,
    FieldChip,
    _corner_from_dict,
    _corner_to_dict,
)

# ============================================================
# 老格式迁移：fields → chips
# ============================================================

class TestLegacyFieldsMigration:
    """老 user.json 仅有中文 ``fields`` 列表 — 应自动迁移为 ``chips``。"""

    def test_legacy_fields_migrate_to_chips(self):
        data = {
            "fields": ["相机型号", "镜头型号"],
            "separator": " · ",
        }
        corner = _corner_from_dict(data)
        assert len(corner.chips) == 2
        assert corner.chips[0].field_id == "camera_model"
        assert corner.chips[1].field_id == "lens_model"
        # fields 仍保留（不丢失）
        assert corner.fields == ["相机型号", "镜头型号"]

    def test_legacy_fields_with_unknown_label_becomes_empty(self):
        data = {"fields": ["相机型号", "未知字段"]}
        corner = _corner_from_dict(data)
        assert len(corner.chips) == 2
        assert corner.chips[0].field_id == "camera_model"
        assert corner.chips[1].field_id == "empty"

    def test_legacy_fields_skips_non_string_entries(self):
        data = {"fields": ["相机型号", 123, None, "镜头型号"]}
        corner = _corner_from_dict(data)
        # 非字符串被忽略
        assert len(corner.chips) == 2
        assert corner.chips[0].field_id == "camera_model"
        assert corner.chips[1].field_id == "lens_model"

    def test_legacy_all_fields_supported(self):
        data = {
            "fields": [
                "相机型号", "镜头型号", "焦距", "光圈", "快门", "ISO",
                "拍摄日期", "厂商品牌", "作者", "地理位置",
                "自定义文本", "空",
            ],
        }
        corner = _corner_from_dict(data)
        ids = [c.field_id for c in corner.chips]
        assert ids == [
            "camera_model", "lens_model", "focal_length", "aperture", "shutter", "iso",
            "datetime", "make", "artist", "gps",
            "custom_text", "empty",
        ]

    def test_legacy_label_pai_she_can_shu_expands_to_four_chips(self):
        """Phase 16：legacy 中文标签 ``"拍摄参数"`` 静默展开为 4 个独立 chip。"""
        data = {"fields": ["相机型号", "拍摄参数", "镜头型号"]}
        corner = _corner_from_dict(data)
        ids = [c.field_id for c in corner.chips]
        assert ids == [
            "camera_model",
            "focal_length", "aperture", "shutter", "iso",
            "lens_model",
        ]

    def test_legacy_empty_fields_list(self):
        corner = _corner_from_dict({"fields": []})
        assert corner.chips == []


# ============================================================
# 新格式反序列化
# ============================================================

class TestNewChipsDeserialize:

    def test_chips_with_full_attrs(self):
        data = {
            "chips": [
                {
                    "field_id": "camera_model",
                    "custom_text": "",
                },
                {
                    "field_id": "custom_text",
                    "custom_text": "拍于云南",
                },
            ],
            "separator": " | ",
        }
        corner = _corner_from_dict(data)
        assert len(corner.chips) == 2
        c0 = corner.chips[0]
        assert c0.field_id == "camera_model"
        c1 = corner.chips[1]
        assert c1.field_id == "custom_text"
        assert c1.custom_text == "拍于云南"
        assert corner.separator == " | "
        assert corner.font_size == 0

    def test_chips_with_partial_attrs_use_defaults(self):
        """缺失字段应回退到默认值（空字符串等）。"""
        data = {"chips": [{"field_id": "camera_model"}]}
        corner = _corner_from_dict(data)
        assert len(corner.chips) == 1
        c = corner.chips[0]
        assert c.field_id == "camera_model"
        assert c.custom_text == ""

    def test_chips_skips_non_dict_entries(self):
        data = {"chips": [{"field_id": "lens_model"}, "garbage", None, 42]}
        corner = _corner_from_dict(data)
        assert len(corner.chips) == 1
        assert corner.chips[0].field_id == "lens_model"

    def test_chips_with_unknown_keys_ignored(self):
        """``_dc_from_dict`` 应忽略未知 key，不抛错。"""
        data = {"chips": [{
            "field_id": "make",
            "custom_text": "",
            "unknown_key": "should_be_ignored",
        }]}
        corner = _corner_from_dict(data)
        assert len(corner.chips) == 1
        assert corner.chips[0].field_id == "make"


# ============================================================
# chips 优先级（同时含 chips 与 fields）
# ============================================================

class TestChipsPreferredOverFields:

    def test_chips_present_skips_fields_migration(self):
        """同时含 chips 与 fields 时，应使用 chips。"""
        data = {
            "chips": [{"field_id": "make"}],
            "fields": ["相机型号", "镜头型号"],  # 应被忽略
        }
        corner = _corner_from_dict(data)
        assert len(corner.chips) == 1
        assert corner.chips[0].field_id == "make"
        # fields 仍被保留作为兼容数据
        assert corner.fields == ["相机型号", "镜头型号"]


# ============================================================
# Phase 16：legacy ``params`` chip 静默展开
# ============================================================

class TestLegacyParamsExpansion:
    """Phase 16：旧 user.json 里 ``field_id="params"`` 的 chip 应在反序列化时
    静默展开为 4 个独立 chip（focal_length / aperture / shutter / iso），
    并继承原 chip 的 font / color。"""

    def test_params_chip_expands_to_four(self):
        data = {"chips": [{"field_id": "params"}]}
        corner = _corner_from_dict(data)
        ids = [c.field_id for c in corner.chips]
        assert ids == ["focal_length", "aperture", "shutter", "iso"]

    def test_params_chip_with_custom_text_does_not_leak(self):
        """params 拆分后子 chip 不携带原 custom_text。"""
        data = {"chips": [{
            "field_id": "params",
            "custom_text": "should-not-leak",
        }]}
        corner = _corner_from_dict(data)
        assert len(corner.chips) == 4
        for c in corner.chips:
            assert c.custom_text == ""

    def test_params_chip_mixed_with_other_chips(self):
        data = {"chips": [
            {"field_id": "camera_model"},
            {"field_id": "params"},
            {"field_id": "lens_model"},
        ]}
        corner = _corner_from_dict(data)
        ids = [c.field_id for c in corner.chips]
        assert ids == [
            "camera_model",
            "focal_length", "aperture", "shutter", "iso",
            "lens_model",
        ]


# ============================================================
# 边界条件
# ============================================================

class TestEdgeCases:

    def test_none_returns_default(self):
        corner = _corner_from_dict(None)
        assert isinstance(corner, CornerConfig)
        assert corner.chips == []
        assert corner.fields == []
        assert corner.separator == " "
        assert corner.font_size == 0

    def test_empty_dict_returns_default(self):
        corner = _corner_from_dict({})
        assert corner.chips == []
        assert corner.fields == []

    def test_non_dict_returns_default(self):
        # 非 dict 输入安全降级
        for bad in ["string", 42, [1, 2, 3], True]:
            corner = _corner_from_dict(bad)  # type: ignore[arg-type]
            assert corner.chips == []

    def test_separator_default(self):
        corner = _corner_from_dict({"chips": []})
        assert corner.separator == " "

    def test_separator_custom(self):
        corner = _corner_from_dict({"chips": [], "separator": " - "})
        assert corner.separator == " - "

    def test_font_size_inherit_when_missing(self):
        corner = _corner_from_dict({"chips": []})
        assert corner.font_size == 0


# ============================================================
# Round-trip：to_dict → from_dict 等价
# ============================================================

class TestRoundTrip:

    def test_roundtrip_simple(self):
        original = CornerConfig(
            chips=[
                FieldChip(field_id="camera_model"),
                FieldChip(field_id="lens_model"),
            ],
            separator=" · ",
        )
        serialized = _corner_to_dict(original)
        restored = _corner_from_dict(serialized)
        assert len(restored.chips) == 2
        assert restored.chips[0].field_id == "camera_model"
        assert restored.chips[1].field_id == "lens_model"
        assert restored.separator == " · "

    def test_roundtrip_with_custom_styles(self):
        original = CornerConfig(
            chips=[
                FieldChip(
                    field_id="custom_text",
                    custom_text="HELLO",
                ),
            ],
            separator=" | ",
            font_size=24,
        )
        serialized = _corner_to_dict(original)
        restored = _corner_from_dict(serialized)

        assert len(restored.chips) == 1
        c = restored.chips[0]
        assert c.field_id == "custom_text"
        assert c.custom_text == "HELLO"
        assert restored.separator == " | "
        assert restored.font_size == 24

    def test_roundtrip_empty(self):
        original = CornerConfig()
        restored = _corner_from_dict(_corner_to_dict(original))
        assert restored.chips == []
        assert restored.separator == " "

    def test_to_dict_shape(self):
        """``_corner_to_dict`` 应总返回稳定的 4 个 key。"""
        d = _corner_to_dict(CornerConfig())
        assert set(d.keys()) == {"chips", "fields", "separator", "font_size"}
        assert d["chips"] == []
        assert d["fields"] == []
        assert d["separator"] == " "
        assert d["font_size"] == 0

    def test_to_dict_chips_serialize_to_dicts(self):
        corner = CornerConfig(chips=[FieldChip(field_id="make")])
        d = _corner_to_dict(corner)
        assert isinstance(d["chips"], list)
        assert isinstance(d["chips"][0], dict)
        assert d["chips"][0]["field_id"] == "make"
