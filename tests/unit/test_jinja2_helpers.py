"""测试 [`core.jinja2renders.vw`](core/jinja2renders.py:7) / [`vh`](core/jinja2renders.py:13) / [`auto_logo`](core/jinja2renders.py:19)。"""
from __future__ import annotations

from jinja2 import Template

from core.jinja2renders import auto_logo, vh, vw


def _render(expr: str, exif: dict) -> str:
    tpl = Template(expr)
    tpl.globals["vw"] = vw
    tpl.globals["vh"] = vh
    tpl.globals["auto_logo"] = auto_logo
    return tpl.render(exif=exif)


class TestVwVh:
    def test_vw_basic(self) -> None:
        assert _render("{{ vw(50) }}", {"ImageWidth": "1000", "ImageHeight": "800"}) == "500"

    def test_vh_basic(self) -> None:
        assert _render("{{ vh(25) }}", {"ImageWidth": "1000", "ImageHeight": "800"}) == "200"

    def test_vw_zero_when_no_exif(self) -> None:
        assert _render("{{ vw(50) }}", {}) == "0"


class TestAutoLogo:
    def test_returns_none_for_unknown_brand(self) -> None:
        # 用 Jinja 的 default 过滤来测 None 行为
        out = _render("{{ auto_logo()|default('NONE', true) }}", {"Make": "PHOTON-9000-NOT-A-BRAND"})
        assert out == "NONE"

    def test_matches_known_brand(self) -> None:
        # config/logos/nikon.png 仓库自带；smoke 测试匹配是否走通
        out = _render("{{ auto_logo() }}", {"Make": "NIKON"})
        # 命中应包含 nikon
        assert "nikon" in out.lower()
