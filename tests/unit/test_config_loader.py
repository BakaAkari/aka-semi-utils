"""测试 [`core.config_loader`](core/config_loader.py:1) — 配置加载/默认值/容错。"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import config_loader


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """重定向 config_loader 的全局路径常量到 tmp_path，每个测试隔离。"""
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "fonts").mkdir()
    (cfg_dir / "logos").mkdir()
    (cfg_dir / "templates").mkdir()

    monkeypatch.setattr(config_loader, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config_loader, "CONFIG_INI_PATH", cfg_dir / "config.ini")
    monkeypatch.setattr(config_loader, "USER_TEMPLATE_PATH", cfg_dir / "user.json")
    monkeypatch.setattr(config_loader, "FONTS_DIR", cfg_dir / "fonts")
    monkeypatch.setattr(config_loader, "LOGOS_DIR", cfg_dir / "logos")
    return cfg_dir


class TestLoadConfigIni:
    def test_creates_default_when_missing(self, sandbox: Path) -> None:
        cfg = config_loader.load_config_ini()
        assert (sandbox / "config.ini").exists()
        # 默认值合理
        assert cfg.getint("DEFAULT", "quality", fallback=0) == 60

    def test_recovers_from_corrupted_file(self, sandbox: Path) -> None:
        (sandbox / "config.ini").write_text("not = valid\n[[[", encoding="utf-8")
        cfg = config_loader.load_config_ini()
        # 应当回退到默认配置
        assert cfg.getint("DEFAULT", "quality", fallback=0) == 60

    def test_save_then_load_roundtrip(self, sandbox: Path) -> None:
        cfg = config_loader.load_config_ini()
        cfg.set("DEFAULT", "author_name", "Alice")
        config_loader.save_config_ini(cfg)

        cfg2 = config_loader.load_config_ini()
        assert cfg2.get("DEFAULT", "author_name") == "Alice"


class TestLoadUserTemplate:
    def test_creates_default_when_missing(self, sandbox: Path) -> None:
        data = config_loader.load_user_template()
        assert "layout" in data and "logo" in data

    def test_recovers_from_invalid_json(self, sandbox: Path) -> None:
        (sandbox / "user.json").write_text("{broken json", encoding="utf-8")
        data = config_loader.load_user_template()
        # 损坏后应回退到默认
        assert "layout" in data

    def test_recovers_when_root_is_not_object(self, sandbox: Path) -> None:
        (sandbox / "user.json").write_text("[1, 2, 3]", encoding="utf-8")
        data = config_loader.load_user_template()
        assert isinstance(data, dict)
        assert "layout" in data

    def test_save_then_load_roundtrip(self, sandbox: Path) -> None:
        payload = {"version": 99, "layout": {}, "logo": {"enabled": False}, "background": {}}
        config_loader.save_user_template(payload)
        loaded = config_loader.load_user_template()
        assert loaded["version"] == 99
        assert loaded["logo"]["enabled"] is False


class TestGetSupportedSuffixes:
    def test_default_suffixes(self, sandbox: Path) -> None:
        cfg = config_loader.load_config_ini()
        sfx = config_loader.get_supported_suffixes(cfg)
        assert ".jpg" in sfx and ".heic" in sfx

    def test_lowercased(self, sandbox: Path) -> None:
        cfg = config_loader.load_config_ini()
        cfg.set("DEFAULT", "supported_file_suffixes", ".JPG,.PNG")
        sfx = config_loader.get_supported_suffixes(cfg)
        assert sfx == {".jpg", ".png"}


class TestGetCustomText:
    def test_global_text_takes_priority(self, sandbox: Path) -> None:
        cfg = config_loader.load_config_ini()
        if not cfg.has_section("custom_text"):
            cfg.add_section("custom_text")
        cfg.set("custom_text", "text", "GLOBAL")
        cfg.set("custom_text", "left_top", "CORNER")
        assert config_loader.get_custom_text(cfg, "left_top") == "GLOBAL"

    def test_corner_fallback_when_no_global(self, sandbox: Path) -> None:
        cfg = config_loader.load_config_ini()
        if not cfg.has_section("custom_text"):
            cfg.add_section("custom_text")
        cfg.set("custom_text", "text", "")
        cfg.set("custom_text", "left_top", "CORNER")
        assert config_loader.get_custom_text(cfg, "left_top") == "CORNER"
