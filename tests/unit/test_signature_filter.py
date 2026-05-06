"""Phase 18 — SignatureFilter 单元测试。

覆盖：

- 直通分支：``signature_enabled=False`` / 缺 path / 文件不存在 / 区域非正
- ``_apply_alpha_tint`` 数学正确性（alpha 蒙版、灰度反转、全局 alpha 缩放）
- ``_compute_paste_xy`` 9 宫格 × 四向 offset 的所有粘贴坐标
- 实际渲染：粘贴位置落在【原图区域】内（margins 不为 0 时验证扣边）
- 高度比例基于【原图区域高度】（而非 bottom_margin）
- 宽度等比缩放、超出区域时自动按 area_w 等比缩
- ``height_ratio`` clamp 到 [0.005, 1.0]
- ``_build_signature_config`` 对 GUI AppState 的转换契约（含 4 个 offset 字段）
"""

from __future__ import annotations

from typing import ClassVar

import numpy as np
import pytest
from PIL import Image

from processor.core import PipelineContext
from processor.filters import SignatureFilter

# ---- helpers ----------------------------------------------------------------


def _make_canvas(w: int = 400, h: int = 300, color=(255, 255, 255, 255)) -> Image.Image:
    """生成纯色 RGBA 画布。"""
    return Image.new("RGBA", (w, h), color)


def _make_signature_png(tmp_path, *, w: int = 100, h: int = 40, with_alpha: bool = True):
    """生成测试用签名 PNG：左半边黑色 / 右半边白色背景。

    Phase 19：永远把 RGB 灰度反转作蒙版 → 黑色变不透明、白色变透明。
    所以这个 helper 用 *白底黑字* 的方式生成：左半黑 → 输出不透明；
    右半白 → 输出透明。`with_alpha` 参数仅决定文件 mode（不影响最终蒙版）。
    """
    img = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    for x in range(w // 2):
        for y in range(h):
            img.putpixel((x, y), (0, 0, 0, 255))
    if not with_alpha:
        img = img.convert("RGB")
    path = tmp_path / "sig.png"
    img.save(path)
    return str(path)


def _make_full_opaque_signature_png(tmp_path, *, w: int = 80, h: int = 20):
    """生成一张全不透明黑色签名 PNG —— 位置测试用，便于推断完整 bbox。"""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    path = tmp_path / "sig_opaque.png"
    img.save(path)
    return str(path)


def _ctx(buffer, **extras) -> PipelineContext:
    cfg = {"buffer": buffer, "buffer_loaded": True, **extras}
    return PipelineContext(cfg)


def _find_color_bbox(img: Image.Image, *, r_hi=False, g_hi=False, b_hi=False):
    """根据指定 RGB 通道阈值找出 bbox (xmin, xmax, ymin, ymax)，无匹配返回 None。"""
    arr = np.asarray(img)
    r_cond = (arr[:, :, 0] > 200) if r_hi else (arr[:, :, 0] < 50)
    g_cond = (arr[:, :, 1] > 200) if g_hi else (arr[:, :, 1] < 50)
    b_cond = (arr[:, :, 2] > 200) if b_hi else (arr[:, :, 2] < 50)
    a_cond = arr[:, :, 3] > 0
    mask = r_cond & g_cond & b_cond & a_cond
    ys, xs = np.where(mask)
    if xs.size == 0:
        return None
    return int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())


# ---- 跳过分支 ----------------------------------------------------------------


class TestSignatureFilterSkips:
    """各种边界情况下应当直通，不抛异常、不修改主 buffer。"""

    def test_disabled_skips_processing(self, tmp_path):
        canvas = _make_canvas()
        ctx = _ctx([canvas], signature_enabled=False, signature_path="/nope.png")
        SignatureFilter().process(ctx)
        assert ctx.get_buffer()[0] is canvas

    def test_missing_path_skips(self):
        canvas = _make_canvas()
        ctx = _ctx([canvas], signature_enabled=True, signature_path="")
        SignatureFilter().process(ctx)
        assert ctx.get_buffer()[0] is canvas

    def test_nonexistent_file_skips_without_raising(self, tmp_path):
        canvas = _make_canvas()
        ctx = _ctx(
            [canvas],
            signature_enabled=True,
            signature_path=str(tmp_path / "does_not_exist.png"),
        )
        SignatureFilter().process(ctx)
        assert ctx.get_buffer()[0] is canvas

    def test_empty_buffer_skips(self, tmp_path):
        sig_path = _make_signature_png(tmp_path)
        ctx = _ctx([], signature_enabled=True, signature_path=sig_path)
        SignatureFilter().process(ctx)
        assert ctx.get_buffer() == []

    def test_zero_image_area_skips(self, tmp_path):
        """margins 完全把画布吃光时应直通。"""
        canvas = _make_canvas(100, 100)
        sig_path = _make_signature_png(tmp_path)
        ctx = _ctx(
            [canvas],
            signature_enabled=True,
            signature_path=sig_path,
            top_margin=60,
            bottom_margin=60,
            left_margin=60,
            right_margin=60,
        )
        SignatureFilter().process(ctx)
        # 不抛异常即可；buffer 内容未被修改
        assert ctx.get_buffer()[0] is canvas


# ---- alpha tint 正确性 -------------------------------------------------------


class TestAlphaTint:
    """Phase 19：永远用 RGB 灰度反转作蒙版（白→透明，黑→不透明），
    彻底忽略源图 alpha 通道。"""

    def test_tint_white_bg_black_text_keeps_only_text(self):
        """白底黑字签名：白色背景 → 完全透明；黑色笔画 → 完全不透明。"""
        sig = Image.new("RGB", (4, 2), (255, 255, 255))
        # 左半边涂黑（笔画）
        for y in range(2):
            for x in range(2):
                sig.putpixel((x, y), (0, 0, 0))

        tinted = SignatureFilter._apply_alpha_tint(sig, (0, 128, 0, 255))
        arr = np.asarray(tinted)
        # 笔画区：被着色为绿色，且不透明
        assert (arr[:, :2, 1] == 128).all()
        assert (arr[:, :2, 3] == 255).all()
        # 白底区：完全透明
        assert (arr[:, 2:, 3] == 0).all()

    def test_tint_ignores_source_alpha_channel(self):
        """RGBA 输入：源 alpha 应被忽略，蒙版完全由 RGB 灰度反转决定。

        构造场景：左半边像素 RGB=(50,50,50) alpha=200；右半边 RGB=(255,255,255) alpha=255。
        若旧逻辑生效，输出 alpha 会取自源 alpha (200/255)；
        新逻辑下，左半边由灰度 50 反转得 205；右半边由灰度 255 反转得 0。
        """
        sig = Image.new("RGBA", (4, 2), (255, 255, 255, 255))
        for y in range(2):
            for x in range(2):
                sig.putpixel((x, y), (50, 50, 50, 200))

        tinted = SignatureFilter._apply_alpha_tint(sig, (255, 0, 0, 255))
        arr = np.asarray(tinted)
        # 笔画区：RGB 替换为红色；alpha 来自反转灰度 = 255 - 50 = 205（不再是源 200）
        assert (arr[:, :2, 0] == 255).all()
        assert (arr[:, :2, 1] == 0).all()
        assert (arr[:, :2, 2] == 0).all()
        assert (arr[:, :2, 3] == 205).all()
        # 白底区：alpha = 255 - 255 = 0，完全透明（即便源 alpha=255 也无视）
        assert (arr[:, 2:, 3] == 0).all()

    def test_tint_gray_pixel_uses_inverted_grayscale_value(self):
        """中间灰度像素：alpha = 255 - 灰度值。"""
        # 纯灰色 (128,128,128) → 灰度 128 → 反转 127
        sig = Image.new("RGB", (2, 2), (128, 128, 128))
        tinted = SignatureFilter._apply_alpha_tint(sig, (0, 0, 0, 255))
        arr = np.asarray(tinted)
        assert (arr[:, :, 3] == 127).all()

    def test_tint_global_alpha_scaling(self):
        """``rgba[3] < 255`` 时整体蒙版按比例缩放。"""
        # 黑色像素 → 灰度 0 → 反转 255 → 全局 alpha 缩放 × 128/255 ≈ 128
        sig = Image.new("RGB", (2, 2), (0, 0, 0))
        tinted = SignatureFilter._apply_alpha_tint(sig, (10, 20, 30, 128))
        arr = np.asarray(tinted)
        expected = int(255 * (128 / 255))  # = 128
        assert abs(int(arr[0, 0, 3]) - expected) <= 1
        # RGB 通道按颜色填充
        assert (arr[:, :, 0] == 10).all()
        assert (arr[:, :, 1] == 20).all()
        assert (arr[:, :, 2] == 30).all()

    def test_tint_global_alpha_scaling_on_gray_pixel(self):
        """灰度像素 + 全局 alpha 缩放叠加。"""
        # 灰度 64 → 反转 191 → × 128/255 ≈ 95
        sig = Image.new("RGB", (2, 2), (64, 64, 64))
        tinted = SignatureFilter._apply_alpha_tint(sig, (0, 0, 0, 128))
        arr = np.asarray(tinted)
        expected = int(191 * (128 / 255))
        # 允许 ±1 像素误差（uint8 量化）
        assert abs(int(arr[0, 0, 3]) - expected) <= 1


# ---- _compute_paste_xy 单元测试 ---------------------------------------------


class TestComputePasteXY:
    """直接验证 9 宫格 × 四向 offset 的几何计算。"""

    AREA: ClassVar[dict] = dict(area_left=0, area_top=0, area_right=400, area_bottom=300)
    SIZE: ClassVar[dict] = dict(target_w=80, target_h=20)
    NO_OFF: ClassVar[dict] = dict(offset_top=0, offset_bottom=0, offset_left=0, offset_right=0)

    def _call(self, position: str, **overrides):
        kw = {**self.AREA, **self.SIZE, **self.NO_OFF, **overrides}
        return SignatureFilter._compute_paste_xy(position=position, **kw)

    # 9 宫格基础位置（无 offset）
    def test_top_left_no_offset(self):
        assert self._call("top_left") == (0, 0)

    def test_top_center_no_offset(self):
        x, y = self._call("top_center")
        assert x == (400 - 80) // 2
        assert y == 0

    def test_top_right_no_offset(self):
        assert self._call("top_right") == (400 - 80, 0)

    def test_middle_left_no_offset(self):
        x, y = self._call("middle_left")
        assert x == 0
        assert y == (300 - 20) // 2

    def test_middle_center_no_offset(self):
        x, y = self._call("middle_center")
        assert x == (400 - 80) // 2
        assert y == (300 - 20) // 2

    def test_middle_right_no_offset(self):
        x, y = self._call("middle_right")
        assert x == 400 - 80
        assert y == (300 - 20) // 2

    def test_bottom_left_no_offset(self):
        assert self._call("bottom_left") == (0, 300 - 20)

    def test_bottom_center_no_offset(self):
        x, y = self._call("bottom_center")
        assert x == (400 - 80) // 2
        assert y == 300 - 20

    def test_bottom_right_no_offset(self):
        assert self._call("bottom_right") == (400 - 80, 300 - 20)

    # 锚定方向 offset 内推
    def test_top_left_with_offsets(self):
        x, y = self._call("top_left", offset_top=15, offset_left=25)
        assert x == 25
        assert y == 15

    def test_bottom_right_with_offsets(self):
        x, y = self._call("bottom_right", offset_bottom=10, offset_right=20)
        assert x == 400 - 80 - 20
        assert y == 300 - 20 - 10

    def test_top_right_with_matching_offsets(self):
        x, y = self._call("top_right", offset_top=5, offset_right=8)
        assert x == 400 - 80 - 8
        assert y == 5

    def test_bottom_left_with_matching_offsets(self):
        x, y = self._call("bottom_left", offset_bottom=12, offset_left=7)
        assert x == 7
        assert y == 300 - 20 - 12

    # 非锚定方向的 offset 应被忽略
    def test_top_left_ignores_bottom_right_offsets(self):
        # offset_bottom / offset_right 对 top_left 锚点无效
        x, y = self._call("top_left", offset_bottom=999, offset_right=999)
        assert (x, y) == (0, 0)

    def test_bottom_right_ignores_top_left_offsets(self):
        x, y = self._call("bottom_right", offset_top=999, offset_left=999)
        assert x == 400 - 80
        assert y == 300 - 20

    def test_middle_center_ignores_all_offsets(self):
        # middle_center 没有锚定边，所有 offset 都被忽略
        x, y = self._call(
            "middle_center",
            offset_top=100, offset_bottom=100,
            offset_left=100, offset_right=100,
        )
        assert x == (400 - 80) // 2
        assert y == (300 - 20) // 2

    def test_middle_left_only_offset_left_applies(self):
        x, y = self._call(
            "middle_left",
            offset_top=999, offset_bottom=999,
            offset_left=30, offset_right=999,
        )
        assert x == 30
        assert y == (300 - 20) // 2

    def test_top_center_only_offset_top_applies(self):
        x, y = self._call(
            "top_center",
            offset_top=20,
            offset_bottom=999, offset_left=999, offset_right=999,
        )
        assert x == (400 - 80) // 2
        assert y == 20

    # 区域偏移（margins 把区域推离原点）
    def test_area_offset_applied(self):
        kw = {
            "area_left": 50, "area_top": 30,
            "area_right": 350, "area_bottom": 250,
            **self.SIZE, **self.NO_OFF,
        }
        x, y = SignatureFilter._compute_paste_xy(position="top_left", **kw)
        assert (x, y) == (50, 30)
        x, y = SignatureFilter._compute_paste_xy(position="bottom_right", **kw)
        assert x == 350 - 80
        assert y == 250 - 20


# ---- 实际渲染：位置落在原图区域内 -------------------------------------------


class TestSignatureRendering:
    """端到端：跑 process()，验证粘贴像素的位置 / 尺寸。"""

    def _render(
        self,
        tmp_path,
        position: str,
        *,
        canvas_size=(400, 300),
        height_ratio=0.5,
        margins=None,
        offsets=None,
    ):
        canvas = _make_canvas(*canvas_size)
        sig_path = _make_full_opaque_signature_png(tmp_path, w=80, h=20)
        extras = {
            "signature_enabled": True,
            "signature_path": sig_path,
            "signature_color": "#FF0000",
            "signature_position": position,
            "signature_height_ratio": height_ratio,
        }
        if margins:
            extras.update(margins)
        if offsets:
            extras.update(offsets)
        ctx = _ctx([canvas], **extras)
        SignatureFilter().process(ctx)
        return ctx.get_buffer()[0]

    # 基础 9 宫格 — 验证落在画布对应区域
    def test_top_left_paste_top_and_left(self, tmp_path):
        out = self._render(tmp_path, "top_left", height_ratio=0.05)
        bbox = _find_color_bbox(out, r_hi=True)
        assert bbox is not None
        xmin, _, ymin, _ = bbox
        assert xmin < int(out.width * 0.1)
        assert ymin < int(out.height * 0.1)

    def test_top_right_paste_top_and_right(self, tmp_path):
        out = self._render(tmp_path, "top_right", height_ratio=0.05)
        bbox = _find_color_bbox(out, r_hi=True)
        assert bbox is not None
        _, xmax, ymin, _ = bbox
        assert xmax > int(out.width * 0.9)
        assert ymin < int(out.height * 0.1)

    def test_bottom_left_paste_bottom_and_left(self, tmp_path):
        out = self._render(tmp_path, "bottom_left", height_ratio=0.05)
        bbox = _find_color_bbox(out, r_hi=True)
        assert bbox is not None
        xmin, _, _, ymax = bbox
        assert xmin < int(out.width * 0.1)
        assert ymax > int(out.height * 0.9)

    def test_bottom_right_paste_bottom_and_right(self, tmp_path):
        out = self._render(tmp_path, "bottom_right", height_ratio=0.05)
        bbox = _find_color_bbox(out, r_hi=True)
        assert bbox is not None
        _, xmax, _, ymax = bbox
        assert xmax > int(out.width * 0.9)
        assert ymax > int(out.height * 0.9)

    def test_middle_center_paste_centered(self, tmp_path):
        out = self._render(tmp_path, "middle_center", height_ratio=0.05)
        bbox = _find_color_bbox(out, r_hi=True)
        assert bbox is not None
        xmin, xmax, ymin, ymax = bbox
        cx = (xmin + xmax) / 2
        cy = (ymin + ymax) / 2
        assert abs(cx - out.width / 2) < out.width * 0.05
        assert abs(cy - out.height / 2) < out.height * 0.05

    def test_unknown_position_falls_back_to_bottom_right(self, tmp_path):
        out = self._render(tmp_path, "garbage_value", height_ratio=0.05)
        bbox = _find_color_bbox(out, r_hi=True)
        assert bbox is not None
        _, xmax, _, ymax = bbox
        assert xmax > int(out.width * 0.9)
        assert ymax > int(out.height * 0.9)

    # 验证：图像内定位避开 watermark margins
    def test_position_respects_margins(self, tmp_path):
        """有 bottom_margin 时，bottom_right 签名应粘贴在【原图区域底部】，
        而非画布底部（不应进入 margin 条带）。"""
        # canvas 400x300，bottom_margin=60 → 原图区域 y ∈ [0, 240)
        out = self._render(
            tmp_path,
            "bottom_right",
            height_ratio=0.05,
            margins={"bottom_margin": 60},
        )
        bbox = _find_color_bbox(out, r_hi=True)
        assert bbox is not None
        _, _, _, ymax = bbox
        # ymax 应严格小于 area_bottom = 300 - 60 = 240
        assert ymax < 240

    def test_position_respects_top_margin(self, tmp_path):
        """top_left 签名应在 top_margin 之下。"""
        out = self._render(
            tmp_path,
            "top_left",
            height_ratio=0.05,
            margins={"top_margin": 50},
        )
        bbox = _find_color_bbox(out, r_hi=True)
        assert bbox is not None
        _, _, ymin, _ = bbox
        assert ymin >= 50

    def test_position_respects_left_margin(self, tmp_path):
        """top_left 签名应在 left_margin 之右。"""
        out = self._render(
            tmp_path,
            "top_left",
            height_ratio=0.05,
            margins={"left_margin": 40},
        )
        bbox = _find_color_bbox(out, r_hi=True)
        assert bbox is not None
        xmin, _, _, _ = bbox
        assert xmin >= 40

    # offset 内推
    def test_offset_top_pushes_inward(self, tmp_path):
        """top_left + offset_top=20 → 签名上沿距区域顶 20px。"""
        out = self._render(
            tmp_path,
            "top_left",
            height_ratio=0.05,
            offsets={"signature_offset_top": 20, "signature_offset_left": 0},
        )
        bbox = _find_color_bbox(out, r_hi=True)
        assert bbox is not None
        _, _, ymin, _ = bbox
        assert ymin == 20

    def test_offset_left_pushes_inward(self, tmp_path):
        out = self._render(
            tmp_path,
            "top_left",
            height_ratio=0.05,
            offsets={"signature_offset_top": 0, "signature_offset_left": 30},
        )
        bbox = _find_color_bbox(out, r_hi=True)
        assert bbox is not None
        xmin, _, _, _ = bbox
        assert xmin == 30

    def test_offset_bottom_pushes_upward(self, tmp_path):
        """bottom_right + offset_bottom=15 → 签名下沿距区域底 15px。"""
        out = self._render(
            tmp_path,
            "bottom_right",
            height_ratio=0.05,
            offsets={"signature_offset_bottom": 15},
        )
        bbox = _find_color_bbox(out, r_hi=True)
        assert bbox is not None
        _, _, _, ymax = bbox
        # canvas h=300, area_bottom=300, ymax = 300 - 1 - 15 = 284
        # （max y index 是高 - 1）
        assert ymax == 300 - 1 - 15

    def test_offset_right_pushes_leftward(self, tmp_path):
        out = self._render(
            tmp_path,
            "bottom_right",
            height_ratio=0.05,
            offsets={"signature_offset_right": 25},
        )
        bbox = _find_color_bbox(out, r_hi=True)
        assert bbox is not None
        _, xmax, _, _ = bbox
        # area_right = 400, xmax = 400 - 1 - 25 = 374
        assert xmax == 400 - 1 - 25

    def test_unrelated_offset_ignored(self, tmp_path):
        """top_left + offset_bottom 应不改变粘贴位置（无锚定边）。"""
        out_no_off = self._render(tmp_path, "top_left", height_ratio=0.05)
        bbox_no = _find_color_bbox(out_no_off, r_hi=True)

        out_with_off = self._render(
            tmp_path, "top_left",
            height_ratio=0.05,
            offsets={"signature_offset_bottom": 100, "signature_offset_right": 100},
        )
        bbox_with = _find_color_bbox(out_with_off, r_hi=True)
        assert bbox_no == bbox_with


# ---- 高度 / 尺寸缩放 ---------------------------------------------------------


class TestSignatureSizing:
    def test_height_follows_ratio_times_area_h(self, tmp_path):
        """target_h ≈ area_h * signature_height_ratio。"""
        canvas = _make_canvas(400, 300)
        # 签名原图 100x40
        sig_path = _make_signature_png(tmp_path, w=100, h=40)
        ctx = _ctx(
            [canvas],
            signature_enabled=True,
            signature_path=sig_path,
            signature_color="#00FF00",
            signature_position="middle_center",
            signature_height_ratio=0.1,
            # 无 margins → area_h = 300
        )
        SignatureFilter().process(ctx)
        out = ctx.get_buffer()[0]
        bbox = _find_color_bbox(out, g_hi=True)
        assert bbox is not None
        _, _, ymin, ymax = bbox
        actual_h = ymax - ymin + 1
        # 期望：300 * 0.1 = 30
        assert abs(actual_h - 30) <= 2

    def test_height_uses_area_not_canvas_when_margins(self, tmp_path):
        """有 margins 时，签名高度基于 area_h（而不是 canvas.height）。"""
        canvas = _make_canvas(400, 400)
        sig_path = _make_signature_png(tmp_path, w=100, h=40)
        ctx = _ctx(
            [canvas],
            signature_enabled=True,
            signature_path=sig_path,
            signature_color="#00FF00",
            signature_position="middle_center",
            signature_height_ratio=0.1,
            top_margin=50,
            bottom_margin=50,
            # area_h = 400 - 100 = 300
        )
        SignatureFilter().process(ctx)
        out = ctx.get_buffer()[0]
        bbox = _find_color_bbox(out, g_hi=True)
        assert bbox is not None
        _, _, ymin, ymax = bbox
        actual_h = ymax - ymin + 1
        # 期望：300 * 0.1 = 30
        assert abs(actual_h - 30) <= 2

    def test_width_scales_proportionally(self, tmp_path):
        """高度变化时宽度应按原图比例（100:40 = 2.5:1）等比缩放。"""
        canvas = _make_canvas(400, 300)
        sig_path = _make_signature_png(tmp_path, w=100, h=40)
        ctx = _ctx(
            [canvas],
            signature_enabled=True,
            signature_path=sig_path,
            signature_color="#0000FF",
            signature_position="middle_center",
            signature_height_ratio=0.1,
        )
        SignatureFilter().process(ctx)
        out = ctx.get_buffer()[0]
        bbox = _find_color_bbox(out, b_hi=True)
        assert bbox is not None
        xmin, xmax, _, _ = bbox
        # 原签名只有左半（50/100）不透明；高 30 → 总宽 75，不透明半宽 37~38
        actual_w = xmax - xmin + 1
        assert 35 <= actual_w <= 40

    def test_width_clamped_to_area_when_too_wide(self, tmp_path):
        """target_w 超出 area_w 时应等比缩到 area_w 内。"""
        canvas = _make_canvas(100, 300)
        # 大签名：500x40 → 高度比 0.1 → target_h=30, scale=0.75 → target_w=375 > 100
        sig_path = _make_full_opaque_signature_png(tmp_path, w=500, h=40)
        ctx = _ctx(
            [canvas],
            signature_enabled=True,
            signature_path=sig_path,
            signature_color="#FFFF00",  # yellow = R+G high, B low
            signature_position="middle_center",
            signature_height_ratio=0.1,
        )
        SignatureFilter().process(ctx)
        out = ctx.get_buffer()[0]
        bbox = _find_color_bbox(out, r_hi=True, g_hi=True)
        assert bbox is not None
        xmin, xmax, _, _ = bbox
        actual_w = xmax - xmin + 1
        # 应 ≤ canvas 宽度
        assert actual_w <= 100

    def test_height_ratio_clamped_to_safe_range(self, tmp_path):
        """超出 [0.005, 1.0] 的占比应被限制（不抛、不崩）。"""
        canvas = _make_canvas(200, 150)
        sig_path = _make_signature_png(tmp_path, w=40, h=20)
        ctx = _ctx(
            [canvas],
            signature_enabled=True,
            signature_path=sig_path,
            signature_color="#FF00FF",
            signature_position="middle_center",
            signature_height_ratio=99.0,  # 异常值 → clamp 到 1.0
        )
        SignatureFilter().process(ctx)
        out = ctx.get_buffer()[0]
        # 不应崩溃；签名渲染出来即可
        bbox = _find_color_bbox(out, r_hi=True, b_hi=True)
        assert bbox is not None


# ---- Phase 20：signature_scale 缩放倍数 ------------------------------------


class TestSignatureScale:
    """验证 ``signature_scale`` 在 ``height_ratio`` 之上整体等比缩放。"""

    def _render_with_scale(self, tmp_path, *, scale, height_ratio=0.1, area_h=300):
        canvas = _make_canvas(400, area_h)
        # 用全黑不透明签名 80x20
        sig_path = _make_full_opaque_signature_png(tmp_path, w=80, h=20)
        ctx = _ctx(
            [canvas],
            signature_enabled=True,
            signature_path=sig_path,
            signature_color="#FF0000",
            signature_position="middle_center",
            signature_height_ratio=height_ratio,
            signature_scale=scale,
        )
        SignatureFilter().process(ctx)
        return ctx.get_buffer()[0]

    def test_scale_1_matches_height_ratio_alone(self, tmp_path):
        """scale=1.0 时与无 scale 行为一致。"""
        out = self._render_with_scale(tmp_path, scale=1.0)
        bbox = _find_color_bbox(out, r_hi=True)
        assert bbox is not None
        _, _, ymin, ymax = bbox
        actual_h = ymax - ymin + 1
        # 期望：300 * 0.1 * 1.0 = 30
        assert abs(actual_h - 30) <= 2

    def test_scale_2_doubles_target_size(self, tmp_path):
        """scale=2.0 → 高度为 baseline × 2，宽度同步等比放大。"""
        out_1 = self._render_with_scale(tmp_path, scale=1.0)
        out_2 = self._render_with_scale(tmp_path, scale=2.0)

        bbox1 = _find_color_bbox(out_1, r_hi=True)
        bbox2 = _find_color_bbox(out_2, r_hi=True)
        assert bbox1 is not None and bbox2 is not None

        h1 = bbox1[3] - bbox1[2] + 1
        h2 = bbox2[3] - bbox2[2] + 1
        w1 = bbox1[1] - bbox1[0] + 1
        w2 = bbox2[1] - bbox2[0] + 1

        # 高 / 宽都应放大约 2 倍（uint8 量化误差 ±2）
        assert abs(h2 - h1 * 2) <= 2
        assert abs(w2 - w1 * 2) <= 2

    def test_scale_half_halves_target_size(self, tmp_path):
        """scale=0.5 → 高度为 baseline × 0.5，宽度等比缩小。"""
        out_1 = self._render_with_scale(tmp_path, scale=1.0, height_ratio=0.2)
        out_h = self._render_with_scale(tmp_path, scale=0.5, height_ratio=0.2)

        bbox1 = _find_color_bbox(out_1, r_hi=True)
        bboxh = _find_color_bbox(out_h, r_hi=True)
        assert bbox1 is not None and bboxh is not None

        h1 = bbox1[3] - bbox1[2] + 1
        hh = bboxh[3] - bboxh[2] + 1

        # scale=0.5 → 大约一半（uint8 量化误差 ±2）
        assert abs(hh * 2 - h1) <= 2

    def test_scale_preserves_aspect_ratio(self, tmp_path):
        """不同 scale 下宽高比恒定。"""
        ratios = []
        for s in [0.5, 1.0, 2.0, 3.0]:
            out = self._render_with_scale(tmp_path, scale=s)
            bbox = _find_color_bbox(out, r_hi=True)
            assert bbox is not None
            xmin, xmax, ymin, ymax = bbox
            w = xmax - xmin + 1
            h = ymax - ymin + 1
            ratios.append(w / h)
        # 各 scale 下宽高比应几乎一致（max 与 min 差 ≤ 0.2）
        assert max(ratios) - min(ratios) < 0.2

    def test_scale_below_min_is_clamped(self, tmp_path):
        """scale < MIN_SCALE 应被 clamp 到 MIN_SCALE（0.1），不崩。"""
        out = self._render_with_scale(tmp_path, scale=0.001)
        bbox = _find_color_bbox(out, r_hi=True)
        # 极小 scale 仍应渲染出至少 1 像素
        assert bbox is not None

    def test_scale_above_max_clamps_and_fits_area(self, tmp_path):
        """scale 远超 MAX_SCALE，且乘以 height_ratio 后可能超出区域 →
        应自动等比缩到区域内，不溢出，不崩。"""
        # height_ratio=0.5, scale=99 → target_h 名义 = 300 * 0.5 * 5 (clamp) = 750 → 超 area_h=300
        # 应自动缩到 area_h 内
        out = self._render_with_scale(
            tmp_path, scale=99.0, height_ratio=0.5, area_h=300
        )
        bbox = _find_color_bbox(out, r_hi=True)
        assert bbox is not None
        _, _, ymin, ymax = bbox
        actual_h = ymax - ymin + 1
        # 应不超过画布高度
        assert actual_h <= 300

    def test_scale_string_invalid_falls_back_to_default(self, tmp_path):
        """ctx 里 signature_scale 是非法字符串 → 回退到默认 1.0，不抛。"""
        canvas = _make_canvas(400, 300)
        sig_path = _make_full_opaque_signature_png(tmp_path, w=80, h=20)
        ctx = _ctx(
            [canvas],
            signature_enabled=True,
            signature_path=sig_path,
            signature_color="#FF0000",
            signature_position="middle_center",
            signature_height_ratio=0.1,
            signature_scale="not_a_number",
        )
        # 不应抛
        SignatureFilter().process(ctx)
        out = ctx.get_buffer()[0]
        bbox = _find_color_bbox(out, r_hi=True)
        assert bbox is not None
        _, _, ymin, ymax = bbox
        actual_h = ymax - ymin + 1
        # 与 scale=1.0 等价：30
        assert abs(actual_h - 30) <= 2


# ---- template_assembler 桥接契约 --------------------------------------------


class TestSignatureConfigBuild:
    """验证 ``_build_signature_config`` 把 GUI AppState 翻译为 processor JSON 的契约。"""

    def _make_state_with_signature(self, **overrides):
        from gui.models import AdvancedConfig, AppState

        state = AppState()
        cfg = AdvancedConfig(
            signature_enabled=overrides.get("enabled", True),
            signature_path=overrides.get("path", "/tmp/sig.png"),
            signature_color=overrides.get("color", "#FF0000"),
            signature_position=overrides.get("position", "bottom_right"),
            signature_height_ratio=overrides.get("height_ratio", 0.05),
            signature_offset_top=overrides.get("offset_top", 0),
            signature_offset_bottom=overrides.get("offset_bottom", 0),
            signature_offset_left=overrides.get("offset_left", 0),
            signature_offset_right=overrides.get("offset_right", 0),
        )
        state.set_advanced_config(cfg)
        return state

    def test_disabled_returns_empty(self, qapp):
        from gui.template_assembler import _build_signature_config

        state = self._make_state_with_signature(enabled=False)
        assert _build_signature_config(state) == {}

    def test_missing_path_returns_empty(self, qapp):
        from gui.template_assembler import _build_signature_config

        state = self._make_state_with_signature(enabled=True, path="")
        assert _build_signature_config(state) == {}

    def test_enabled_emits_full_config(self, qapp):
        from gui.template_assembler import _build_signature_config

        state = self._make_state_with_signature(
            enabled=True,
            path="/sig.png",
            color="#ABCDEF",
            position="top_center",
            height_ratio=0.42,
            offset_top=10,
            offset_bottom=20,
            offset_left=30,
            offset_right=40,
        )
        out = _build_signature_config(state)
        assert out["signature_enabled"] is True
        assert out["signature_path"] == "/sig.png"
        assert out["signature_color"] == "#ABCDEF"
        assert out["signature_position"] == "top_center"
        assert out["signature_height_ratio"] == 0.42
        assert out["signature_offset_top"] == 10
        assert out["signature_offset_bottom"] == 20
        assert out["signature_offset_left"] == 30
        assert out["signature_offset_right"] == 40

    def test_no_bottom_margin_emitted(self, qapp):
        """Phase 18：_build_signature_config 不再透传 bottom_margin
        （SignatureFilter 直接读 ctx 中由 watermark/margin filter 写入的 margins）。"""
        from gui.template_assembler import _build_signature_config

        state = self._make_state_with_signature()
        out = _build_signature_config(state)
        assert "bottom_margin" not in out
        assert "top_margin" not in out
        assert "left_margin" not in out
        assert "right_margin" not in out

    def test_state_to_processors_includes_signature_after_watermark(self, qapp):
        from gui.template_assembler import state_to_processors

        state = self._make_state_with_signature()
        procs = state_to_processors(state)
        names = [p.get("processor_name") for p in procs]
        assert "watermark" in names
        assert "signature" in names
        assert names.index("watermark") < names.index("signature")

    def test_state_to_processors_omits_signature_when_disabled(self, qapp):
        from gui.template_assembler import state_to_processors

        state = self._make_state_with_signature(enabled=False)
        procs = state_to_processors(state)
        names = [p.get("processor_name") for p in procs]
        assert "signature" not in names


# ---- qapp fixture for AppState（QObject 信号需要 QApplication） ------------


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
