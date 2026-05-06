"""SignatureFilter 单元测试（Phase 18 引入；Phase 22 重构为宽度占比模型；
Phase 26 重构为「保留彩色像素 + 黑白二值切换」算法）。

覆盖：

- 直通分支：``signature_enabled=False`` / 缺 path / 文件不存在 / 区域非正
- ``_apply_color_swap`` 三分类（近白→透明 / 近黑↔白可切换 / 彩色保留原色）
- ``_compute_paste_xy`` 9 宫格 × 四向 offset 的所有粘贴坐标
- 实际渲染：粘贴位置落在【原图区域】内（margins 不为 0 时验证扣边）
- Phase 22 尺寸模型：``target_w = area_w × signature_width_ratio``
- ``_build_signature_config`` 对 GUI AppState 的转换契约（含 signature_invert_mono）
- Phase 26 红点回归：彩色装饰像素在 invert_mono 切换下 RGB 不被改变
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

    Phase 26：白底→透明、黑笔画→不透明（默认 invert_mono=False）。
    `with_alpha` 参数仅决定文件 mode（不影响最终蒙版）。
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
    """生成一张全不透明黑色签名 PNG —— 位置/尺寸测试用，便于推断完整 bbox。"""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    path = tmp_path / "sig_opaque.png"
    img.save(path)
    return str(path)


def _make_signature_with_red_dot(tmp_path, *, w: int = 80, h: int = 20):
    """生成带红色装饰点的签名 PNG（Phase 26 回归测试用）。

    布局：白底 + 左半边黑笔画 + 右上角 4×4 红色块（彩色像素）。
    """
    img = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    # 左半边黑笔画
    for x in range(w // 2):
        for y in range(h):
            img.putpixel((x, y), (0, 0, 0, 255))
    # 右上角红色装饰（远离黑笔画区域）
    for x in range(w - 6, w - 2):
        for y in range(2, 6):
            img.putpixel((x, y), (255, 0, 0, 255))
    path = tmp_path / "sig_with_red_dot.png"
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


def _find_black_bbox(img: Image.Image):
    """找出图中所有 alpha>0 且 RGB 接近黑色的像素 bbox。"""
    return _find_color_bbox(img, r_hi=False, g_hi=False, b_hi=False)


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


# ---- Phase 26：_apply_color_swap 三分类正确性 -------------------------------


class TestColorSwap:
    """Phase 26：``_apply_color_swap`` 算法 — 三分类像素处理。

    分类规则（参见 SignatureFilter 类常量 WHITE_THRESHOLD/BLACK_THRESHOLD/CHROMA_TOL）：
        - 近白（无色 + 各通道≥240）：alpha=0（完全透明）
        - 近黑（无色 + 各通道≤20）：黑↔白由 invert_mono 决定，不透明
        - 彩色（chroma > CHROMA_TOL）：RGB 完全保留，alpha 由亮度推导
        - 中间灰度（无色 + 介于黑白之间）：跟随 stroke 颜色，alpha 由亮度推导

    核心契约：彩色像素永远不被「黑白切换」开关修改 RGB（红点回归）。
    """

    def test_white_pixel_becomes_transparent_when_not_inverted(self):
        """纯白像素 → alpha=0（默认 invert_mono=False）。"""
        sig = Image.new("RGB", (2, 2), (255, 255, 255))
        out = SignatureFilter._apply_color_swap(sig, invert_mono=False)
        arr = np.asarray(out)
        assert (arr[:, :, 3] == 0).all()

    def test_white_pixel_becomes_transparent_when_inverted(self):
        """纯白像素 → alpha=0（即便 invert_mono=True 也透明）。"""
        sig = Image.new("RGB", (2, 2), (255, 255, 255))
        out = SignatureFilter._apply_color_swap(sig, invert_mono=True)
        arr = np.asarray(out)
        assert (arr[:, :, 3] == 0).all()

    def test_near_white_pixel_also_transparent(self):
        """近白像素（如 245,248,250）也应被视作背景 → alpha=0。"""
        sig = Image.new("RGB", (2, 2), (245, 248, 250))
        out = SignatureFilter._apply_color_swap(sig, invert_mono=False)
        arr = np.asarray(out)
        assert (arr[:, :, 3] == 0).all()

    def test_black_pixel_stays_black_when_not_inverted(self):
        """invert_mono=False：纯黑像素 → 输出黑色不透明。"""
        sig = Image.new("RGB", (2, 2), (0, 0, 0))
        out = SignatureFilter._apply_color_swap(sig, invert_mono=False)
        arr = np.asarray(out)
        assert (arr[:, :, 0] == 0).all()
        assert (arr[:, :, 1] == 0).all()
        assert (arr[:, :, 2] == 0).all()
        assert (arr[:, :, 3] == 255).all()

    def test_black_pixel_becomes_white_when_inverted(self):
        """invert_mono=True：纯黑像素 → 输出白色不透明（黑↔白切换）。"""
        sig = Image.new("RGB", (2, 2), (0, 0, 0))
        out = SignatureFilter._apply_color_swap(sig, invert_mono=True)
        arr = np.asarray(out)
        assert (arr[:, :, 0] == 255).all()
        assert (arr[:, :, 1] == 255).all()
        assert (arr[:, :, 2] == 255).all()
        assert (arr[:, :, 3] == 255).all()

    def test_near_black_pixel_treated_as_black(self):
        """近黑像素（如 15,15,15）也按黑笔画处理。"""
        sig = Image.new("RGB", (2, 2), (15, 15, 15))
        out = SignatureFilter._apply_color_swap(sig, invert_mono=False)
        arr = np.asarray(out)
        # invert=False → 输出黑色不透明
        assert (arr[:, :, 0] == 0).all()
        assert (arr[:, :, 3] == 255).all()

    def test_red_pixel_preserved_when_not_inverted(self):
        """彩色（红）像素：invert_mono=False 时 RGB 完全保留。"""
        sig = Image.new("RGB", (2, 2), (255, 0, 0))
        out = SignatureFilter._apply_color_swap(sig, invert_mono=False)
        arr = np.asarray(out)
        assert (arr[:, :, 0] == 255).all()
        assert (arr[:, :, 1] == 0).all()
        assert (arr[:, :, 2] == 0).all()
        # 红色亮度低 → alpha 较高（不透明）
        assert (arr[:, :, 3] > 100).all()

    def test_red_pixel_preserved_when_inverted(self):
        """**Phase 26 关键回归**：彩色（红）像素 invert_mono=True 时 RGB 仍完全保留。

        即使开了「白色文字」开关，红点也不应被改色 / 反相。
        """
        sig = Image.new("RGB", (2, 2), (255, 0, 0))
        out = SignatureFilter._apply_color_swap(sig, invert_mono=True)
        arr = np.asarray(out)
        # 即便切到 invert_mono=True，红色 RGB 完全不变
        assert (arr[:, :, 0] == 255).all()
        assert (arr[:, :, 1] == 0).all()
        assert (arr[:, :, 2] == 0).all()
        # alpha 不为 0（彩色像素不被透明化）
        assert (arr[:, :, 3] > 100).all()

    def test_blue_pixel_preserved_in_both_modes(self):
        """彩色蓝色像素在两个模式下 RGB 都完全保留。"""
        sig = Image.new("RGB", (2, 2), (0, 0, 255))
        for invert in (False, True):
            out = SignatureFilter._apply_color_swap(sig, invert_mono=invert)
            arr = np.asarray(out)
            assert (arr[:, :, 0] == 0).all()
            assert (arr[:, :, 1] == 0).all()
            assert (arr[:, :, 2] == 255).all()
            assert (arr[:, :, 3] > 100).all()

    def test_mid_gray_follows_stroke_color(self):
        """中间灰度像素（无色但既非近白也非近黑）→ 跟随 stroke 颜色。"""
        # 灰 128 → 介于 BLACK_THRESHOLD(20) 和 WHITE_THRESHOLD(240) 之间
        sig = Image.new("RGB", (2, 2), (128, 128, 128))

        # invert=False：跟随黑色 stroke
        out = SignatureFilter._apply_color_swap(sig, invert_mono=False)
        arr = np.asarray(out)
        assert (arr[:, :, 0] == 0).all()
        assert (arr[:, :, 1] == 0).all()
        assert (arr[:, :, 2] == 0).all()
        # alpha = 255 - luminance ≈ 255 - 128 = 127
        assert abs(int(arr[0, 0, 3]) - 127) <= 2

        # invert=True：跟随白色 stroke
        out2 = SignatureFilter._apply_color_swap(sig, invert_mono=True)
        arr2 = np.asarray(out2)
        assert (arr2[:, :, 0] == 255).all()
        assert (arr2[:, :, 1] == 255).all()
        assert (arr2[:, :, 2] == 255).all()
        assert abs(int(arr2[0, 0, 3]) - 127) <= 2

    def test_chromatic_alpha_from_luminance(self):
        """彩色像素的 alpha 由亮度计算（255 - 0.299R - 0.587G - 0.114B）。"""
        # 纯绿 (0,255,0) → luminance ≈ 0.587×255 = 149.7 → alpha ≈ 105
        sig = Image.new("RGB", (2, 2), (0, 255, 0))
        out = SignatureFilter._apply_color_swap(sig, invert_mono=False)
        arr = np.asarray(out)
        assert (arr[:, :, 1] == 255).all()  # G 通道保留
        # alpha 在合理范围
        a = int(arr[0, 0, 3])
        assert 100 <= a <= 110

    def test_mixed_image_three_classes(self):
        """同一张图三种像素混合 → 各自分类正确。"""
        sig = Image.new("RGB", (3, 1), (255, 255, 255))
        sig.putpixel((0, 0), (0, 0, 0))        # 黑
        sig.putpixel((1, 0), (255, 0, 0))      # 红
        sig.putpixel((2, 0), (255, 255, 255))  # 白
        out = SignatureFilter._apply_color_swap(sig, invert_mono=False)
        arr = np.asarray(out)
        # 黑像素：黑色不透明
        assert tuple(arr[0, 0]) == (0, 0, 0, 255)
        # 红像素：RGB 保留
        assert arr[0, 1, 0] == 255
        assert arr[0, 1, 1] == 0
        assert arr[0, 1, 2] == 0
        assert arr[0, 1, 3] > 100
        # 白像素：完全透明
        assert arr[0, 2, 3] == 0


# ---- _compute_paste_xy 单元测试 ---------------------------------------------


class TestComputePasteXY:
    """Phase 24：直接验证 9 宫格 base 坐标 + (offset_x, offset_y) 全局位移向量。

    语义：
        offset_x：正向 → 向右；负向 → 向左
        offset_y：正向 → 向下；负向 → 向上
    任意 9 个 position 锚点下，offset_x/y 都生效。
    """

    AREA: ClassVar[dict] = dict(area_left=0, area_top=0, area_right=400, area_bottom=300)
    SIZE: ClassVar[dict] = dict(target_w=80, target_h=20)
    NO_OFF: ClassVar[dict] = dict(offset_x=0, offset_y=0)

    def _call(self, position: str, **overrides):
        kw = {**self.AREA, **self.SIZE, **self.NO_OFF, **overrides}
        return SignatureFilter._compute_paste_xy(position=position, **kw)

    # ---- 9 宫格基础位置（无 offset）----
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

    # ---- offset_x/y 在每个 position 都按 (base + offset) 叠加 ----
    def test_top_left_with_positive_offsets(self):
        # base=(0,0)，向右下推
        x, y = self._call("top_left", offset_x=25, offset_y=15)
        assert (x, y) == (25, 15)

    def test_bottom_right_with_negative_offsets(self):
        # base=(320,280)，向左上推
        x, y = self._call("bottom_right", offset_x=-20, offset_y=-10)
        assert (x, y) == (400 - 80 - 20, 300 - 20 - 10)

    def test_middle_center_with_positive_offsets(self):
        # base=(160,140)；offset 在 middle_center 也生效（与旧版 Phase 18 行为相反）
        x, y = self._call("middle_center", offset_x=30, offset_y=40)
        assert x == (400 - 80) // 2 + 30
        assert y == (300 - 20) // 2 + 40

    def test_middle_center_with_negative_offsets(self):
        # 中心锚点 + 负偏移 → 向左上偏移
        x, y = self._call("middle_center", offset_x=-30, offset_y=-40)
        assert x == (400 - 80) // 2 - 30
        assert y == (300 - 20) // 2 - 40

    def test_top_right_with_mixed_offsets(self):
        # base=(320,0)；向左推 8、向下推 5
        x, y = self._call("top_right", offset_x=-8, offset_y=5)
        assert (x, y) == (400 - 80 - 8, 5)

    def test_bottom_left_with_mixed_offsets(self):
        # base=(0,280)；向右推 7、向上推 12
        x, y = self._call("bottom_left", offset_x=7, offset_y=-12)
        assert (x, y) == (7, 300 - 20 - 12)

    def test_offsets_apply_uniformly_to_all_positions(self):
        """对所有 9 个锚点，加同一个 (offset_x, offset_y) 应整体平移同样距离。"""
        all_positions = [
            "top_left", "top_center", "top_right",
            "middle_left", "middle_center", "middle_right",
            "bottom_left", "bottom_center", "bottom_right",
        ]
        dx, dy = 17, -23
        for pos in all_positions:
            base_x, base_y = self._call(pos)
            shifted_x, shifted_y = self._call(pos, offset_x=dx, offset_y=dy)
            assert shifted_x == base_x + dx, f"{pos}: x 平移失败"
            assert shifted_y == base_y + dy, f"{pos}: y 平移失败"

    def test_zero_offsets_match_no_offset(self):
        # offset_x=0, offset_y=0 应等价于不传 offset
        for pos in ["top_left", "middle_center", "bottom_right"]:
            assert self._call(pos) == self._call(pos, offset_x=0, offset_y=0)

    # ---- 区域偏移（margins 把区域推离原点）----
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

    def test_area_offset_with_offset_xy(self):
        """area 偏移 + offset_x/y 同时叠加（base 由 area 决定，偏移再叠加）。"""
        kw = {
            "area_left": 50, "area_top": 30,
            "area_right": 350, "area_bottom": 250,
            **self.SIZE,
            "offset_x": 10, "offset_y": -5,
        }
        x, y = SignatureFilter._compute_paste_xy(position="top_left", **kw)
        assert (x, y) == (60, 25)


# ---- 实际渲染：位置落在原图区域内 -------------------------------------------


class TestSignatureRendering:
    """端到端：跑 process()，验证粘贴像素的位置 / 尺寸。

    Phase 26：默认 invert_mono=False → 黑笔画 PNG 渲染后仍是黑色像素。
    用 :func:`_find_black_bbox` 检测黑色 bbox。
    """

    SIG_W: ClassVar[int] = 80
    SIG_H: ClassVar[int] = 20

    def _render(
        self,
        tmp_path,
        position: str,
        *,
        canvas_size=(400, 300),
        width_ratio: float = 0.05,
        margins=None,
        offsets=None,
    ):
        canvas = _make_canvas(*canvas_size)
        sig_path = _make_full_opaque_signature_png(tmp_path, w=self.SIG_W, h=self.SIG_H)
        extras = {
            "signature_enabled": True,
            "signature_path": sig_path,
            "signature_invert_mono": False,
            "signature_position": position,
            "signature_width_ratio": width_ratio,
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
        out = self._render(tmp_path, "top_left")
        bbox = _find_black_bbox(out)
        assert bbox is not None
        xmin, _, ymin, _ = bbox
        assert xmin < int(out.width * 0.1)
        assert ymin < int(out.height * 0.1)

    def test_top_right_paste_top_and_right(self, tmp_path):
        out = self._render(tmp_path, "top_right")
        bbox = _find_black_bbox(out)
        assert bbox is not None
        _, xmax, ymin, _ = bbox
        assert xmax > int(out.width * 0.9)
        assert ymin < int(out.height * 0.1)

    def test_bottom_left_paste_bottom_and_left(self, tmp_path):
        out = self._render(tmp_path, "bottom_left")
        bbox = _find_black_bbox(out)
        assert bbox is not None
        xmin, _, _, ymax = bbox
        assert xmin < int(out.width * 0.1)
        assert ymax > int(out.height * 0.9)

    def test_bottom_right_paste_bottom_and_right(self, tmp_path):
        out = self._render(tmp_path, "bottom_right")
        bbox = _find_black_bbox(out)
        assert bbox is not None
        _, xmax, _, ymax = bbox
        assert xmax > int(out.width * 0.9)
        assert ymax > int(out.height * 0.9)

    def test_middle_center_paste_centered(self, tmp_path):
        out = self._render(tmp_path, "middle_center")
        bbox = _find_black_bbox(out)
        assert bbox is not None
        xmin, xmax, ymin, ymax = bbox
        cx = (xmin + xmax) / 2
        cy = (ymin + ymax) / 2
        assert abs(cx - out.width / 2) < out.width * 0.05
        assert abs(cy - out.height / 2) < out.height * 0.05

    def test_unknown_position_falls_back_to_middle_center(self, tmp_path):
        """Phase 23：未知 position 回退到 middle_center（图像中心对齐）。"""
        out = self._render(tmp_path, "garbage_value")
        bbox = _find_black_bbox(out)
        assert bbox is not None
        xmin, xmax, ymin, ymax = bbox
        cx = (xmin + xmax) / 2
        cy = (ymin + ymax) / 2
        # 中心点应在画布中心 ±10% 容差内
        assert abs(cx - out.width / 2) < out.width * 0.1
        assert abs(cy - out.height / 2) < out.height * 0.1

    # 验证：图像内定位避开 watermark margins
    def test_position_respects_margins(self, tmp_path):
        """有 bottom_margin 时，bottom_right 签名应粘贴在【原图区域底部】，
        而非画布底部（不应进入 margin 条带）。"""
        # canvas 400x300，bottom_margin=60 → 原图区域 y ∈ [0, 240)
        out = self._render(
            tmp_path,
            "bottom_right",
            margins={"bottom_margin": 60},
        )
        bbox = _find_black_bbox(out)
        assert bbox is not None
        _, _, _, ymax = bbox
        # ymax 应严格小于 area_bottom = 300 - 60 = 240
        assert ymax < 240

    def test_position_respects_top_margin(self, tmp_path):
        """top_left 签名应在 top_margin 之下。"""
        out = self._render(
            tmp_path,
            "top_left",
            margins={"top_margin": 50},
        )
        bbox = _find_black_bbox(out)
        assert bbox is not None
        _, _, ymin, _ = bbox
        assert ymin >= 50

    def test_position_respects_left_margin(self, tmp_path):
        """top_left 签名应在 left_margin 之右。"""
        out = self._render(
            tmp_path,
            "top_left",
            margins={"left_margin": 40},
        )
        bbox = _find_black_bbox(out)
        assert bbox is not None
        xmin, _, _, _ = bbox
        assert xmin >= 40

    # ---- Phase 24：offset_x/y 带正负号微调（任意 position 下都生效）----
    def test_offset_y_positive_pushes_down(self, tmp_path):
        """top_left + offset_y=20 → 签名上沿距画布顶 20px（向下推）。"""
        out = self._render(
            tmp_path,
            "top_left",
            offsets={"signature_offset_x": 0, "signature_offset_y": 20},
        )
        bbox = _find_black_bbox(out)
        assert bbox is not None
        _, _, ymin, _ = bbox
        assert ymin == 20

    def test_offset_x_positive_pushes_right(self, tmp_path):
        """top_left + offset_x=30 → 签名左沿距画布左 30px（向右推）。"""
        out = self._render(
            tmp_path,
            "top_left",
            offsets={"signature_offset_x": 30, "signature_offset_y": 0},
        )
        bbox = _find_black_bbox(out)
        assert bbox is not None
        xmin, _, _, _ = bbox
        assert xmin == 30

    def test_offset_y_negative_pushes_up(self, tmp_path):
        """bottom_right + offset_y=-15 → 签名下沿距画布底 15px（向上推）。"""
        out = self._render(
            tmp_path,
            "bottom_right",
            offsets={"signature_offset_x": 0, "signature_offset_y": -15},
        )
        bbox = _find_black_bbox(out)
        assert bbox is not None
        _, _, _, ymax = bbox
        # canvas h=300, base_y = 300 - target_h；offset_y=-15 → ymax = 300 - 1 - 15
        assert ymax == 300 - 1 - 15

    def test_offset_x_negative_pushes_left(self, tmp_path):
        """bottom_right + offset_x=-25 → 签名右沿距画布右 25px（向左推）。"""
        out = self._render(
            tmp_path,
            "bottom_right",
            offsets={"signature_offset_x": -25, "signature_offset_y": 0},
        )
        bbox = _find_black_bbox(out)
        assert bbox is not None
        _, xmax, _, _ = bbox
        assert xmax == 400 - 1 - 25

    def test_offset_xy_works_at_middle_center(self, tmp_path):
        """Phase 24 关键修复：middle_center 锚点下 offset_x/y 也生效。"""
        out_no_off = self._render(tmp_path, "middle_center")
        bbox_no = _find_black_bbox(out_no_off)
        assert bbox_no is not None
        x_center_no = (bbox_no[0] + bbox_no[1]) / 2
        y_center_no = (bbox_no[2] + bbox_no[3]) / 2

        out_with_off = self._render(
            tmp_path,
            "middle_center",
            offsets={"signature_offset_x": 40, "signature_offset_y": -30},
        )
        bbox_with = _find_black_bbox(out_with_off)
        assert bbox_with is not None
        x_center_with = (bbox_with[0] + bbox_with[1]) / 2
        y_center_with = (bbox_with[2] + bbox_with[3]) / 2

        # 中心向右推 40、向上推 30
        assert abs((x_center_with - x_center_no) - 40) <= 1
        assert abs((y_center_with - y_center_no) - (-30)) <= 1

    def test_offset_xy_combined_diagonal_shift(self, tmp_path):
        """top_left + (offset_x=20, offset_y=10) → 同时右移 20、下移 10。"""
        out = self._render(
            tmp_path,
            "top_left",
            offsets={"signature_offset_x": 20, "signature_offset_y": 10},
        )
        bbox = _find_black_bbox(out)
        assert bbox is not None
        xmin, _, ymin, _ = bbox
        assert xmin == 20
        assert ymin == 10


# ---- Phase 26：黑↔白切换 + 红点回归（端到端） ------------------------------


class TestInvertMonoEndToEnd:
    """Phase 26：``signature_invert_mono`` 端到端语义。"""

    def test_invert_mono_false_renders_black_strokes(self, tmp_path):
        """invert_mono=False → 渲染后画布上有黑色像素（黑笔画保留）。"""
        canvas = _make_canvas(400, 300)
        sig_path = _make_full_opaque_signature_png(tmp_path, w=80, h=20)
        ctx = _ctx(
            [canvas],
            signature_enabled=True,
            signature_path=sig_path,
            signature_invert_mono=False,
            signature_position="middle_center",
            signature_width_ratio=0.5,
        )
        SignatureFilter().process(ctx)
        out = ctx.get_buffer()[0]
        # 应能找到黑色 bbox
        bbox = _find_black_bbox(out)
        assert bbox is not None

    def test_invert_mono_true_renders_white_strokes_on_dark_bg(self, tmp_path):
        """invert_mono=True → 渲染后白色像素被画上深色画布上。"""
        # 用深色画布以让白笔画可见
        canvas = _make_canvas(400, 300, color=(0, 0, 0, 255))
        sig_path = _make_full_opaque_signature_png(tmp_path, w=80, h=20)
        ctx = _ctx(
            [canvas],
            signature_enabled=True,
            signature_path=sig_path,
            signature_invert_mono=True,
            signature_position="middle_center",
            signature_width_ratio=0.5,
        )
        SignatureFilter().process(ctx)
        out = ctx.get_buffer()[0]
        # 在深色画布上应能找到白色像素
        arr = np.asarray(out)
        white_mask = (
            (arr[:, :, 0] > 240)
            & (arr[:, :, 1] > 240)
            & (arr[:, :, 2] > 240)
        )
        assert white_mask.any(), "invert_mono=True 应在深色画布上画出白色笔画"

    @staticmethod
    def _has_reddish_pixel(img: Image.Image) -> bool:
        """检测画布上是否存在「带红色调」的像素（R 显著大于 G 和 B）。

        端到端测试中，签名经过 LANCZOS 缩放 + alpha 混合后红色会被周围像素稀释，
        所以不能用纯红 (R>200, G<50, B<50) 阈值；改用「色调判定」：
            R - G > 50 AND R - B > 50 AND R > 100
        """
        arr = np.asarray(img).astype(np.int16)
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        a = arr[:, :, 3]
        mask = (r - g > 50) & (r - b > 50) & (r > 100) & (a > 0)
        return bool(mask.any())

    def test_red_dot_preserved_when_invert_mono_false(self, tmp_path):
        """**Phase 26 红点回归**：invert_mono=False 时红色装饰被保留。

        用 ratio=0.2 让 target_w=80 等于 PNG 原始宽度，避免 LANCZOS 缩放稀释颜色。
        """
        canvas = _make_canvas(400, 300)
        sig_path = _make_signature_with_red_dot(tmp_path, w=80, h=20)
        ctx = _ctx(
            [canvas],
            signature_enabled=True,
            signature_path=sig_path,
            signature_invert_mono=False,
            signature_position="middle_center",
            signature_width_ratio=0.2,  # target_w=80 = 原始宽度，无缩放
        )
        SignatureFilter().process(ctx)
        out = ctx.get_buffer()[0]
        assert self._has_reddish_pixel(out), "invert_mono=False 时红点应被保留"

    def test_red_dot_preserved_when_invert_mono_true(self, tmp_path):
        """**Phase 26 关键回归**：即便 invert_mono=True，红色装饰也保留原色。"""
        canvas = _make_canvas(400, 300)
        sig_path = _make_signature_with_red_dot(tmp_path, w=80, h=20)
        ctx = _ctx(
            [canvas],
            signature_enabled=True,
            signature_path=sig_path,
            signature_invert_mono=True,  # 切换到白笔画模式
            signature_position="middle_center",
            signature_width_ratio=0.2,  # target_w=80 = 原始宽度，无缩放
        )
        SignatureFilter().process(ctx)
        out = ctx.get_buffer()[0]
        assert self._has_reddish_pixel(out), (
            "Phase 26 契约违反：invert_mono=True 时红色装饰像素被错误地修改了 RGB"
        )

    def test_red_dot_unit_level_preserved_in_both_modes(self, tmp_path):
        """单元级回归：直接对原始签名图调用 _apply_color_swap，不经过任何缩放/合成。

        这是最严格的契约测试：``_apply_color_swap`` 必须保留每一个红色像素的 RGB。
        """
        from PIL import Image as PILImage
        sig = PILImage.open(_make_signature_with_red_dot(tmp_path, w=80, h=20))
        for invert in (False, True):
            out = SignatureFilter._apply_color_swap(sig.convert("RGB"), invert_mono=invert)
            arr = np.asarray(out)
            # 右上角 4×4 红色块（行 2..5, 列 74..77）应保持 R=255 G=0 B=0
            red_region = arr[2:6, 74:78]
            assert (red_region[:, :, 0] == 255).all(), (
                f"invert_mono={invert}: 红点 R 通道被改变"
            )
            assert (red_region[:, :, 1] == 0).all(), (
                f"invert_mono={invert}: 红点 G 通道被改变"
            )
            assert (red_region[:, :, 2] == 0).all(), (
                f"invert_mono={invert}: 红点 B 通道被改变"
            )
            assert (red_region[:, :, 3] > 100).all(), (
                f"invert_mono={invert}: 红点 alpha 不应为 0"
            )


# ---- Phase 22：尺寸模型 — target_w = area_w × ratio -------------------------


class TestSignatureSizing:
    """Phase 22：签名宽度由【原图区域宽度 × ratio】决定，分辨率无关；
    高度按签名 PNG 原始宽高比等比推算。"""

    def test_width_equals_area_w_times_ratio(self, tmp_path):
        """canvas 400×300，ratio=0.5 → target_w ≈ 200。"""
        canvas = _make_canvas(400, 300)
        # 签名 100×40，宽高比 2.5:1
        sig_path = _make_full_opaque_signature_png(tmp_path, w=100, h=40)
        ctx = _ctx(
            [canvas],
            signature_enabled=True,
            signature_path=sig_path,
            signature_invert_mono=False,
            signature_position="middle_center",
            signature_width_ratio=0.5,
        )
        SignatureFilter().process(ctx)
        out = ctx.get_buffer()[0]
        bbox = _find_black_bbox(out)
        assert bbox is not None
        xmin, xmax, ymin, ymax = bbox
        actual_w = xmax - xmin + 1
        actual_h = ymax - ymin + 1
        # area_w=400 → target_w=200；按 100:40=2.5 → target_h=200/2.5=80
        assert abs(actual_w - 200) <= 2
        assert abs(actual_h - 80) <= 2

    def test_width_scales_with_ratio(self, tmp_path):
        """ratio=0.25 → target_w ≈ 100（canvas=400）。"""
        canvas = _make_canvas(400, 300)
        sig_path = _make_full_opaque_signature_png(tmp_path, w=100, h=40)
        ctx = _ctx(
            [canvas],
            signature_enabled=True,
            signature_path=sig_path,
            signature_invert_mono=False,
            signature_position="middle_center",
            signature_width_ratio=0.25,
        )
        SignatureFilter().process(ctx)
        out = ctx.get_buffer()[0]
        bbox = _find_black_bbox(out)
        assert bbox is not None
        xmin, xmax, ymin, ymax = bbox
        actual_w = xmax - xmin + 1
        actual_h = ymax - ymin + 1
        # target_w=100, target_h=100/2.5=40
        assert abs(actual_w - 100) <= 2
        assert abs(actual_h - 40) <= 2

    def test_width_resolution_independent(self, tmp_path):
        """同一 ratio 在不同分辨率下，输出宽占图比应一致（分辨率无关）。"""
        sig_path = _make_full_opaque_signature_png(tmp_path, w=100, h=40)

        def _render(canvas_w: int, canvas_h: int) -> float:
            canvas = _make_canvas(canvas_w, canvas_h)
            ctx = _ctx(
                [canvas],
                signature_enabled=True,
                signature_path=sig_path,
                signature_invert_mono=False,
                signature_position="middle_center",
                signature_width_ratio=0.2,
            )
            SignatureFilter().process(ctx)
            out = ctx.get_buffer()[0]
            bbox = _find_black_bbox(out)
            assert bbox is not None
            xmin, xmax, _, _ = bbox
            actual_w = xmax - xmin + 1
            return actual_w / canvas_w

        ratio_small = _render(400, 300)
        ratio_large = _render(2000, 1500)
        # 分辨率无关：占图宽比应几乎一致（量化误差容忍）
        assert abs(ratio_small - 0.2) < 0.02
        assert abs(ratio_large - 0.2) < 0.02
        assert abs(ratio_small - ratio_large) < 0.02

    def test_width_shrinks_with_horizontal_margins(self, tmp_path):
        """left/right margin 缩小 area_w → 签名宽度按比例同步缩小。"""
        sig_path = _make_full_opaque_signature_png(tmp_path, w=100, h=40)

        def _render(margins: dict) -> int:
            canvas = _make_canvas(400, 400)
            ctx = _ctx(
                [canvas],
                signature_enabled=True,
                signature_path=sig_path,
                signature_invert_mono=False,
                signature_position="middle_center",
                signature_width_ratio=0.5,
                **margins,
            )
            SignatureFilter().process(ctx)
            out = ctx.get_buffer()[0]
            bbox = _find_black_bbox(out)
            assert bbox is not None
            xmin, xmax, _, _ = bbox
            return xmax - xmin + 1

        w_no_margin = _render({})
        w_with_margin = _render({"left_margin": 50, "right_margin": 50})
        # 无 margin: area_w=400 → target_w≈200
        # 有 margin: area_w=300 → target_w≈150
        assert abs(w_no_margin - 200) <= 2
        assert abs(w_with_margin - 150) <= 2

    def test_aspect_ratio_preserved(self, tmp_path):
        """不同 ratio 下，输出 w/h 恒等于 PNG 原始 w/h。"""
        # 签名宽高比 100:40 = 2.5
        sig_path = _make_full_opaque_signature_png(tmp_path, w=100, h=40)

        def _render(width_ratio: float) -> tuple[int, int]:
            canvas = _make_canvas(400, 300)
            ctx = _ctx(
                [canvas],
                signature_enabled=True,
                signature_path=sig_path,
                signature_invert_mono=False,
                signature_position="middle_center",
                signature_width_ratio=width_ratio,
            )
            SignatureFilter().process(ctx)
            out = ctx.get_buffer()[0]
            bbox = _find_black_bbox(out)
            assert bbox is not None
            xmin, xmax, ymin, ymax = bbox
            return (xmax - xmin + 1, ymax - ymin + 1)

        for r in [0.1, 0.25, 0.5, 0.75]:
            w, h = _render(r)
            assert h > 0
            ratio = w / h
            assert abs(ratio - 2.5) < 0.2

    def test_oversize_height_fits_into_area(self, tmp_path):
        """target_h 超出 area_h 时应等比缩到 area 内（不溢出）。"""
        # 高瘦签名 50×500（宽高比 1:10）+ canvas 400×100
        # ratio=1.0 → target_w=400, target_h=400×10=4000 远超 area_h=100
        canvas = _make_canvas(400, 100)
        sig_path = _make_full_opaque_signature_png(tmp_path, w=50, h=500)
        ctx = _ctx(
            [canvas],
            signature_enabled=True,
            signature_path=sig_path,
            signature_invert_mono=False,
            signature_position="middle_center",
            signature_width_ratio=1.0,
        )
        SignatureFilter().process(ctx)
        out = ctx.get_buffer()[0]
        bbox = _find_black_bbox(out)
        assert bbox is not None
        xmin, xmax, ymin, ymax = bbox
        actual_w = xmax - xmin + 1
        actual_h = ymax - ymin + 1
        # 应被 fit 到 area 内
        assert actual_w <= 400
        assert actual_h <= 100


# ---- Phase 22：signature_width_ratio clamp / 异常输入 -----------------------


class TestSignatureWidthRatio:
    """Phase 22：``signature_width_ratio`` 的 clamp 行为与异常输入容错。"""

    def _render_with_ratio(self, tmp_path, *, ratio, area_h=300):
        canvas = _make_canvas(400, area_h)
        # 全黑不透明签名 80×20（宽高比 4:1）
        sig_path = _make_full_opaque_signature_png(tmp_path, w=80, h=20)
        ctx = _ctx(
            [canvas],
            signature_enabled=True,
            signature_path=sig_path,
            signature_invert_mono=False,
            signature_position="middle_center",
            signature_width_ratio=ratio,
        )
        SignatureFilter().process(ctx)
        return ctx.get_buffer()[0]

    def test_default_ratio_15pct_yields_60px_on_400_canvas(self, tmp_path):
        """默认 ratio=0.15 在 400px 宽画布上 → target_w=60。"""
        out = self._render_with_ratio(tmp_path, ratio=0.15)
        bbox = _find_black_bbox(out)
        assert bbox is not None
        xmin, xmax, ymin, ymax = bbox
        actual_w = xmax - xmin + 1
        actual_h = ymax - ymin + 1
        # target_w = 400 × 0.15 = 60；target_h = 60 × (20/80) = 15
        assert abs(actual_w - 60) <= 2
        assert abs(actual_h - 15) <= 2

    def test_ratio_05_yields_200px_on_400_canvas(self, tmp_path):
        """ratio=0.5 → target_w=200。"""
        out = self._render_with_ratio(tmp_path, ratio=0.5)
        bbox = _find_black_bbox(out)
        assert bbox is not None
        xmin, xmax, _, _ = bbox
        actual_w = xmax - xmin + 1
        assert abs(actual_w - 200) <= 2

    def test_ratio_10_fills_area_width(self, tmp_path):
        """ratio=1.0 → target_w 接近 area_w。"""
        out = self._render_with_ratio(tmp_path, ratio=1.0)
        bbox = _find_black_bbox(out)
        assert bbox is not None
        xmin, xmax, _, _ = bbox
        actual_w = xmax - xmin + 1
        # target_w=400, target_h=400×(20/80)=100，area_h=300 OK 不 fit
        assert abs(actual_w - 400) <= 2

    def test_ratio_below_min_is_clamped(self, tmp_path):
        """ratio < MIN_WIDTH_RATIO (0.01) 应被 clamp，不崩。"""
        out = self._render_with_ratio(tmp_path, ratio=0.0001)
        bbox = _find_black_bbox(out)
        # 极小 ratio clamp 到 0.01 → target_w=4，仍可见
        assert bbox is not None
        xmin, xmax, _, _ = bbox
        actual_w = xmax - xmin + 1
        # 0.01 × 400 = 4
        assert 1 <= actual_w <= 6

    def test_ratio_above_max_is_clamped_to_one(self, tmp_path):
        """ratio > MAX_WIDTH_RATIO (1.0) → clamp 到 1.0，不超出 area。"""
        out = self._render_with_ratio(tmp_path, ratio=99.0)
        bbox = _find_black_bbox(out)
        assert bbox is not None
        xmin, xmax, ymin, ymax = bbox
        actual_w = xmax - xmin + 1
        actual_h = ymax - ymin + 1
        # 应不超过画布
        assert actual_w <= 400
        assert actual_h <= 300

    def test_ratio_string_invalid_falls_back_to_default(self, tmp_path):
        """ctx 里 signature_width_ratio 是非法字符串 → 回退到默认 0.15，不抛。"""
        canvas = _make_canvas(400, 300)
        sig_path = _make_full_opaque_signature_png(tmp_path, w=80, h=20)
        ctx = _ctx(
            [canvas],
            signature_enabled=True,
            signature_path=sig_path,
            signature_invert_mono=False,
            signature_position="middle_center",
            signature_width_ratio="not_a_number",
        )
        # 不应抛
        SignatureFilter().process(ctx)
        out = ctx.get_buffer()[0]
        bbox = _find_black_bbox(out)
        assert bbox is not None
        xmin, xmax, ymin, ymax = bbox
        actual_w = xmax - xmin + 1
        actual_h = ymax - ymin + 1
        # 与 ratio=0.15 等价 → target_w=60, target_h=15
        assert abs(actual_w - 60) <= 2
        assert abs(actual_h - 15) <= 2


# ---- template_assembler 桥接契约 --------------------------------------------


class TestSignatureConfigBuild:
    """验证 ``_build_signature_config`` 把 GUI AppState 翻译为 processor JSON 的契约。"""

    def _make_state_with_signature(self, **overrides):
        from gui.models import AdvancedConfig, AppState

        state = AppState()
        cfg = AdvancedConfig(
            signature_enabled=overrides.get("enabled", True),
            signature_path=overrides.get("path", "/tmp/sig.png"),
            # Phase 26：signature_color → signature_invert_mono
            signature_invert_mono=overrides.get("invert_mono", False),
            signature_position=overrides.get("position", "bottom_right"),
            signature_width_ratio=overrides.get("width_ratio", 0.15),
            # Phase 24：offset_x/y 带正负号
            signature_offset_x=overrides.get("offset_x", 0),
            signature_offset_y=overrides.get("offset_y", 0),
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
            invert_mono=True,
            position="top_center",
            width_ratio=0.3,
            offset_x=-15,
            offset_y=25,
        )
        out = _build_signature_config(state)
        assert out["signature_enabled"] is True
        assert out["signature_path"] == "/sig.png"
        # Phase 26：signature_color 字段被替换为 signature_invert_mono
        assert out["signature_invert_mono"] is True
        assert out["signature_position"] == "top_center"
        assert out["signature_width_ratio"] == 0.3
        # Phase 24：offset_x/y 带正负号
        assert out["signature_offset_x"] == -15
        assert out["signature_offset_y"] == 25
        # Phase 22：旧字段 height_ratio / scale 都不应出现
        assert "signature_height_ratio" not in out
        assert "signature_scale" not in out
        # Phase 24：旧 4 向 offset 字段不应再出现
        assert "signature_offset_top" not in out
        assert "signature_offset_bottom" not in out
        assert "signature_offset_left" not in out
        assert "signature_offset_right" not in out
        # Phase 26：signature_color 不应再出现
        assert "signature_color" not in out

    def test_invert_mono_false_emits_false(self, qapp):
        """Phase 26：invert_mono=False 也应被透传（不是简单 truthy 过滤）。"""
        from gui.template_assembler import _build_signature_config

        state = self._make_state_with_signature(invert_mono=False)
        out = _build_signature_config(state)
        assert out["signature_invert_mono"] is False

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
