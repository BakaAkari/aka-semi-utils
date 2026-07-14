import json
import re
from abc import ABC

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from core.logger import logger
from processor.core import ImageProcessor, PipelineContext, get_processor, register, start_process
from processor.types import Alignment


class FilterProcessor(ImageProcessor, ABC):
    processor_category = "filter"

    def category(self) -> str:
        return "filter"


@register("blur")
class BlurFilter(FilterProcessor):
    def process(self, ctx: PipelineContext):
        radius = ctx.getint("blur_radius", 5)

        buffer = []
        for img in ctx.get_buffer():
            if img.mode != "RGB":
                img = img.convert("RGB")
            ret_img = img.filter(ImageFilter.GaussianBlur(radius=radius))
            buffer.append(ret_img)
        ctx.update_buffer(buffer).save_buffer(self.name()).success()

    def name(self) -> str:
        return "blur"


@register("resize")
class ResizeFilter(FilterProcessor):
    def process(self, ctx: PipelineContext):
        width, height = ctx.get("width"), ctx.get("height")
        scale = ctx.get("scale")

        buffer = []
        for img in ctx.get_buffer():
            if width and height:
                target_size = (max(1, int(width)), max(1, int(height)))
            else:
                if width:
                    scale_f = float(width) / img.width
                elif height:
                    scale_f = float(height) / img.height
                elif scale:
                    scale_f = float(scale)
                else:
                    ctx.set("success", False)
                    return
                target_size = (max(1, int(img.width * scale_f)), max(1, int(img.height * scale_f)))

            ret_img = img.resize(target_size, resample=Image.Resampling.LANCZOS)
            buffer.append(ret_img)
        ctx.update_buffer(buffer).save_buffer(self.name()).success()

    def name(self) -> str:
        return "resize"


@register("trim")
class TrimFilter(FilterProcessor):
    # 注：原代码 ``threshold = 10.0,`` 末尾误带逗号导致变成单元素 tuple，
    # 这里修正为标量 float（实际未被外部读取，仅作为类级默认配置占位）。
    threshold: float = 10.0
    padding: int = 0

    def process(self, ctx: PipelineContext):
        buffer = []
        for image in ctx.get_buffer():
            if image.height * image.width == 0:
                continue
            bbox = self.get_foreground_bbox(image, trim_left=ctx.get("trim_left", True),
                                            trim_right=ctx.get("trim_right", True),
                                            trim_top=ctx.get("trim_top", True),
                                            trim_bottom=ctx.get("trim_bottom", True))
            buffer.append(image.crop(bbox))
        ctx.update_buffer(buffer).save_buffer(self.name()).success()

    def name(self) -> str:
        return "trim"

    def _get_background_color(self, img_array: np.ndarray) -> np.ndarray:
        """取四角像素均值作为背景色"""
        corners = np.array([
            img_array[0, 0],  # 左上角
            img_array[0, -1],  # 右上角
            img_array[-1, 0],  # 左下角
            img_array[-1, -1]  # 右下角
        ])
        return np.mean(corners, axis=0)

    def _shrink_bbox(
            self,
            diff: np.ndarray,
            threshold: float,
            width: int,
            height: int
    ) -> tuple[int, int, int, int]:
        """
        从四个方向向内收缩边界框

        Args:
            diff: 每个像素与背景的差异矩阵 shape: (height, width)
            threshold: 差异阈值
            width: 图像宽度
            height: 图像高度

        Returns:
            (left, right, top, bottom) 收缩后的边界
        """
        # 判断每个像素是否超过阈值（与背景有明显差异）
        exceeds = diff > threshold

        # 统计每列是否存在超过阈值的像素
        col_exceeds = np.any(exceeds, axis=0)  # shape: (width,)
        # 统计每行是否存在超过阈值的像素
        row_exceeds = np.any(exceeds, axis=1)  # shape: (height,)

        # 如果整张图都是背景（没有前景），返回原始边界
        if not np.any(col_exceeds):
            return 0, width, 0, height

        # 从左→右扫描：找到第一个超过阈值的列（argmax 返回第一个 True 的索引）
        # 从右→左扫描：反转后找第一个 True，再换算回原索引
        left = int(np.argmax(col_exceeds))
        right = int(width - np.argmax(col_exceeds[::-1]))
        top = int(np.argmax(row_exceeds))
        bottom = int(height - np.argmax(row_exceeds[::-1]))

        return left, right, top, bottom

    def get_foreground_bbox(
            self,
            image: Image.Image,
            threshold: float = 10.0,
            padding: int = 0,
            trim_left: bool = True,
            trim_right: bool = True,
            trim_top: bool = True,
            trim_bottom: bool = True,
    ) -> tuple[int, int, int, int]:
        img_array = np.array(image, dtype=np.float32)

        # 处理灰度图（2D → 3D）
        if img_array.ndim == 2:
            img_array = img_array[:, :, np.newaxis]

        height, width, _channels = img_array.shape

        # ===== 第一步：取四角像素均值作为背景色 =====
        background_color = self._get_background_color(img_array)

        # ===== 第二步：计算每个像素与背景的差异（Phase 5.6：用平方距离避开 sqrt） =====
        # 原: diff = sqrt(sum((img - bg)^2)) ；阈值比较等价于 diff^2 > threshold^2，
        # 省掉每像素的 sqrt（在大图上是显著的 numpy ufunc 节省）。
        delta = img_array - background_color
        # einsum 一次完成逐像素平方求和（比 (a**2).sum(axis=-1) 快、内存更省）
        diff_sq = np.einsum("ijk,ijk->ij", delta, delta)
        threshold_sq = float(threshold) * float(threshold)

        # ===== 第三步：从四个方向向内扫描，收缩边界框（用 squared threshold） =====
        left, right, top, bottom = self._shrink_bbox(diff_sq, threshold_sq, width, height)

        if not trim_left:
            left = 0
        if not trim_right:
            right = width
        if not trim_top:
            top = 0
        if not trim_bottom:
            bottom = height
        # ===== 第四步：应用 padding 并确保边界合法 =====
        left = max(0, left - padding)
        top = max(0, top - padding)
        right = min(width, right + padding)
        bottom = min(height, bottom + padding)

        return left, top, right, bottom


@register("margin")
class MarginFilter(FilterProcessor):

    def process(self, ctx: PipelineContext):
        left_margin = ctx.getint("left_margin", 0)
        right_margin = ctx.getint("right_margin", 0)
        top_margin = ctx.getint("top_margin", 0)
        bottom_margin = ctx.getint("bottom_margin", 0)
        color = ctx.get("margin_color", "white")

        buffer = []
        for img in ctx.get_buffer():
            # 获取原图尺寸
            original_width, original_height = img.size

            # 计算新画布尺寸
            new_width = original_width + left_margin + right_margin
            new_height = original_height + top_margin + bottom_margin

            # 创建新画布，填充指定颜色
            new_img = Image.new(img.mode, (new_width, new_height), color)

            # 计算偏移量（原图粘贴位置）
            offset_x = left_margin
            offset_y = top_margin

            # 将原图粘贴到新画布上
            new_img.paste(img, (offset_x, offset_y))
            buffer.append(new_img)

        ctx.update_buffer(buffer).save_buffer(self.name()).success()

    def name(self) -> str:
        return "margin"


@register("margin_with_ratio")
class MarginWithRatioFilter(FilterProcessor):
    ratio_pattern = re.compile('[0-9.]+:[0-9.]+')
    ratio_threshold = 0.01

    def process(self, ctx: PipelineContext):
        buffer = ctx.get_buffer()
        if not buffer:
            return
        real_ratio = 1. * int(ctx.get_exif().get('ImageWidth')) / int(ctx.get_exif().get('ImageHeight'))
        if 'ratio' in ctx and MarginWithRatioFilter.ratio_pattern.match(ctx.get("ratio")):
            ratio_w, ratio_h = ctx.get("ratio").split(':')
            real_ratio = 1. * float(ratio_w) / float(ratio_h)
        img = buffer[0]
        cur_ratio = 1. * img.width / img.height
        if cur_ratio - real_ratio > MarginWithRatioFilter.ratio_threshold:
            # 图片太宽, 增加高度
            new_h = int(img.width / real_ratio)
            pad_vertical = new_h - img.height
            ctx.set('top_margin', pad_vertical / 2)
            ctx.set('bottom_margin', pad_vertical - pad_vertical / 2)
        elif cur_ratio - real_ratio < MarginWithRatioFilter.ratio_threshold:
            # 图片太窄, 增加宽度
            new_w = int(img.height * real_ratio)
            pad_horizontal = new_w - img.width
            ctx.set('left_margin', pad_horizontal / 2)
            ctx.set('right_margin', pad_horizontal - pad_horizontal / 2)
        else:
            return
        MarginFilter().process(ctx)
        ctx.save_buffer(self.name()).success()

    def name(self) -> str:
        return "margin_with_ratio"


@register("watermark")
class WatermarkFilter(FilterProcessor):
    """主水印滤镜 — 在图像底部添加四角文本 + 三处 logo（左/中/右）。

    process() 已按职责拆分为多个私有方法：

    - :meth:`_collect_params`         — 从 ctx 收集所有参数为局部 dict
    - :meth:`_render_corner_texts`    — 渲染四角文本（含自适应缩放）
    - :meth:`_load_logos`             — 加载左/中/右三个 logo（容错）
    - :meth:`_paste_main_and_left`    — 主图 + 左 logo + 左分隔线
    - :meth:`_paste_center_logo`      — 中央 logo（含按高度 resize）
    - :meth:`_compute_text_layout`    — 计算四角文本坐标
    - :meth:`_paste_texts`            — 粘贴四角文本
    - :meth:`_paste_right_logo`       — 右 logo + 右分隔线
    """

    def process(self, ctx: PipelineContext):
        img = ctx.get_buffer()[0]

        if ctx.get("layout_mode") == "sides":
            self._process_sides(ctx, img)
            return

        params = self._collect_params(ctx, img)

        corners = self._render_corner_texts(ctx, params)
        logos = self._load_logos(ctx)

        canvas_width = img.width + params["left_margin"] + params["right_margin"]
        canvas_height = img.height + params["top_margin"] + params["bottom_margin"]
        common_spacing = int(0.02 * canvas_width)

        canvas = Image.new("RGBA", (canvas_width, canvas_height), params["color"])
        footer_start_y = params["top_margin"] + img.height

        left_logo_width = self._paste_main_and_left(
            canvas, img, logos["left_logo"], params, footer_start_y, common_spacing
        )
        self._paste_center_logo(canvas, logos["center_logo"], params, footer_start_y)

        layout = self._compute_text_layout(
            corners=corners,
            params=params,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            left_logo_width=left_logo_width,
            common_spacing=common_spacing,
        )
        self._paste_texts(canvas, corners, layout)

        if logos["right_logo"]:
            self._paste_right_logo(
                canvas=canvas,
                right_logo=logos["right_logo"],
                params=params,
                layout=layout,
                footer_start_y=footer_start_y,
                common_spacing=common_spacing,
            )

        ctx.update_buffer([canvas]).save_buffer(self.name()).success()

    def name(self) -> str:
        return "watermark"

    # ------------------------------------------------------------- helpers
    def _collect_params(self, ctx: PipelineContext, img: Image.Image) -> dict:
        """把 ctx 中散落的字符串键收拢为一个局部参数 dict。"""
        short_edge = min(img.width, img.height)
        bottom_margin = ctx.getint("bottom_margin", 0)
        # 如果用户没设置（0 或不存在），自动计算：短边 × 12%，最小 60px
        if bottom_margin <= 0:
            bottom_margin = max(60, int(short_edge * 0.12))

        return {
            "color": ctx.get("color", "white"),
            "delimiter_color": ctx.get("delimiter_color", "black"),
            "delimiter_width": ctx.getint("delimiter_width", int(img.width * 0.003)),
            "logo_height": ctx.getint("logo_height", ctx.getint("center_logo_height", 0)),
            "left_margin": ctx.getint("left_margin", 0),
            "right_margin": ctx.getint("right_margin", 0),
            "top_margin": ctx.getint("top_margin", 0),
            "bottom_margin": bottom_margin,
            "middle_spacing": ctx.getint("middle_spacing", int(bottom_margin * 0.05)),
            "right_alignment": ctx.getenum("right_alignment", Alignment.RIGHT, Alignment),
        }

    def _render_corner_texts(self, ctx: PipelineContext, params: dict) -> dict[str, Image.Image]:
        """渲染左上/左下/右上/右下四个角落的文本图。

        Phase 28+：字号联动底部白条高度 —
        若 corner 配置包含 ``height_ratio``，按底部白条高度计算实际像素高度
        （保证不同分辨率下字号与底部白条的比例一致，避免挤压）。
        若显式指定 ``height``（旧配置），直接沿用；
        否则用 ``bottom_margin * 0.3`` 兜底。
        """
        img = ctx.get_buffer()[0]
        bottom_margin = params["bottom_margin"]
        for t_s in [ctx.get("left_top"), ctx.get("left_bottom"),
                    ctx.get("right_top"), ctx.get("right_bottom")]:
            if t_s:
                if "height_ratio" in t_s:
                    # 用户传的 ratio 是相对于短边的（如 0.055）
                    # bottom_margin 现在也是相对于短边的（0.12）
                    # 联动：字号 = bottom_margin * (ratio / 0.12)
                    t_s["height"] = int(bottom_margin * t_s["height_ratio"] / 0.12)
                elif "height" not in t_s:
                    t_s["height"] = int(bottom_margin * 0.3)

        def _process_corner(corner_cfg):
            if corner_cfg is None:
                return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
            return start_process([corner_cfg])

        corners = {
            "left_top": _process_corner(ctx.get("left_top")),
            "left_bottom": _process_corner(ctx.get("left_bottom")),
            "right_top": _process_corner(ctx.get("right_top")),
            "right_bottom": _process_corner(ctx.get("right_bottom")),
        }

        # Phase 28：禁用自动缩放 —— 仅在文本超过画布安全宽度时给出 warning，绝不 resize。
        canvas_width = img.width + params["left_margin"] + params["right_margin"]
        effective_width = canvas_width - params["left_margin"] - params["right_margin"]
        max_text_width = max(1, int(effective_width * 0.42))

        for corner_name, text_img in corners.items():
            if text_img.width > max_text_width:
                logger.warning(
                    f"[WatermarkFilter] {corner_name} 文本宽度 {text_img.width}px 超过画布安全宽度 "
                    f"{max_text_width}px（可能被画布裁剪）。"
                    f"Phase 28 已禁用自动缩放以保证字号统一 —— 请减小 corner.height 或精简文本。"
                )

        return corners

    def _load_logos(self, ctx: PipelineContext) -> dict[str, Image.Image | None]:
        """加载三个 logo（缺失时记 warning 但不抛错）。"""
        from core.image_io import load_logo

        logos: dict[str, Image.Image | None] = {
            "left_logo": None,
            "right_logo": None,
            "center_logo": None,
        }
        for key in ("left_logo", "right_logo", "center_logo"):
            path = ctx.get(key)
            if not path:
                continue
            try:
                logos[key] = load_logo(path)
            except (FileNotFoundError, OSError):
                logger.warning("Logo 文件无法加载: %s", path)
        return logos

    def _paste_main_and_left(
        self,
        canvas: Image.Image,
        img: Image.Image,
        left_logo: Image.Image | None,
        params: dict,
        footer_start_y: int,
        common_spacing: int,
    ) -> int:
        """粘贴主图 + 左 logo + 左分隔线，返回左侧占用宽度。

        Logo 高度统一使用 ``logo_height``；未配置时退回到底部水印条完整高度，
        保持旧左侧 logo 的默认视觉大小。左/右分隔线均固定在 logo 右侧。
        """
        canvas.paste(
            img,
            (params["left_margin"], params["top_margin"]),
            mask=img if img.mode == "RGBA" else None,
        )
        if not left_logo:
            return 0

        left_logo = self._resize_logo_to_target_height(left_logo, canvas, params, footer_start_y)
        logo_x = params["left_margin"]
        logo_y = self._logo_y(canvas, left_logo.height, footer_start_y)
        canvas.paste(
            left_logo,
            (logo_x, logo_y),
            mask=left_logo if left_logo.mode == "RGBA" else None,
        )

        delimiter = self._make_logo_delimiter(params, left_logo.height)
        delimiter_x = logo_x + left_logo.width + common_spacing
        delimiter_y = self._delimiter_y(logo_y, left_logo.height)
        canvas.paste(delimiter, (delimiter_x, delimiter_y), mask=delimiter)
        return left_logo.width + common_spacing + delimiter.width

    def _paste_center_logo(
        self,
        canvas: Image.Image,
        center_logo: Image.Image | None,
        params: dict,
        footer_start_y: int,
    ) -> None:
        """粘贴中央 logo（统一按 logo_height / footer 高度等比缩放）。"""
        if not center_logo:
            return
        center_logo = self._resize_logo_to_target_height(center_logo, canvas, params, footer_start_y)

        center_x = (canvas.width - center_logo.width) // 2
        center_y = self._logo_y(canvas, center_logo.height, footer_start_y)
        canvas.paste(
            center_logo,
            (center_x, center_y),
            mask=center_logo if center_logo.mode == "RGBA" else None,
        )

    def _compute_text_layout(
        self,
        corners: dict[str, Image.Image],
        params: dict,
        canvas_width: int,
        canvas_height: int,
        left_logo_width: int,
        common_spacing: int,
    ) -> dict:
        """计算四角文本的粘贴坐标与块高度元信息。"""
        lt, lb = corners["left_top"], corners["left_bottom"]
        rt, rb = corners["right_top"], corners["right_bottom"]
        middle_spacing = params["middle_spacing"]
        bottom_margin = params["bottom_margin"]

        elem_height = max(lt.height + lb.height, rt.height + rb.height) + middle_spacing
        elem_margin = int((bottom_margin - elem_height) / 2)

        l_x = params["left_margin"] + left_logo_width + common_spacing
        right_content_end_x = canvas_width - params["right_margin"]

        # 左上 / 左下 Y 坐标（基于底部对齐）
        bottom_dist_lt = elem_margin + lb.height + middle_spacing + lt.height
        lt_y = canvas_height - bottom_dist_lt
        bottom_dist_lb = elem_margin + lb.height
        lb_y = canvas_height - bottom_dist_lb

        # 右上 / 右下 Y 坐标（与对应左侧底部对齐）
        rt_y = (lt_y + lt.height) - rt.height
        rt_x = right_content_end_x - rt.width - common_spacing
        rb_y = (lb_y + lb.height) - rb.height
        rb_x = right_content_end_x - rb.width - common_spacing

        if params["right_alignment"] == Alignment.LEFT:
            rt_x = rb_x = min(rt_x, rb_x)

        return {
            "elem_height": elem_height,
            "elem_margin": elem_margin,
            "l_x": l_x,
            "lt_y": lt_y,
            "lb_y": lb_y,
            "rt_x": rt_x,
            "rt_y": rt_y,
            "rb_x": rb_x,
            "rb_y": rb_y,
        }

    def _paste_texts(self, canvas: Image.Image, corners: dict, layout: dict) -> None:
        """把四角文本图粘贴到画布上（用 mask 处理透明背景）。"""
        l_x = layout["l_x"]
        canvas.paste(corners["left_top"], (l_x, layout["lt_y"]),
                     mask=corners["left_top"] if corners["left_top"].mode == "RGBA" else None)
        canvas.paste(corners["left_bottom"], (l_x, layout["lb_y"]),
                     mask=corners["left_bottom"] if corners["left_bottom"].mode == "RGBA" else None)
        canvas.paste(corners["right_top"], (layout["rt_x"], layout["rt_y"]),
                     mask=corners["right_top"] if corners["right_top"].mode == "RGBA" else None)
        canvas.paste(corners["right_bottom"], (layout["rb_x"], layout["rb_y"]),
                     mask=corners["right_bottom"] if corners["right_bottom"].mode == "RGBA" else None)

    def _paste_right_logo(
        self,
        canvas: Image.Image,
        right_logo: Image.Image,
        params: dict,
        layout: dict,
        footer_start_y: int,
        common_spacing: int,
    ) -> None:
        """粘贴右 logo + 右分隔线。

        右侧对齐恢复旧模式：右侧文字保持靠右，logo + 分隔线整体贴在右侧文字左边；
        分隔线仍固定在 logo 右侧，因此视觉顺序为：logo → 分隔线 → 右侧文字。
        """
        right_logo = self._resize_logo_to_target_height(right_logo, canvas, params, footer_start_y)
        delimiter = self._make_logo_delimiter(params, right_logo.height)
        text_left_x = min(layout["rt_x"], layout["rb_x"])
        delimiter_x = text_left_x - common_spacing - delimiter.width
        delimiter_y = self._delimiter_y(self._logo_y(canvas, right_logo.height, footer_start_y), right_logo.height)
        canvas.paste(delimiter, (delimiter_x, delimiter_y), mask=delimiter)

        right_logo_x = delimiter_x - common_spacing - right_logo.width
        right_logo_y = self._logo_y(canvas, right_logo.height, footer_start_y)
        canvas.paste(
            right_logo,
            (right_logo_x, right_logo_y),
            mask=right_logo if right_logo.mode == "RGBA" else None,
        )

    # ------------------------------------------------------- sides layout

    def _process_sides(self, ctx: PipelineContext, img: Image.Image) -> None:
        """Render the sides (左右居中) layout: vertically-stacked text blocks
        on the left and right edges of the image, with logo in the bottom bar."""
        params = self._collect_params(ctx, img)
        side_images = self._render_side_texts(ctx, params, img)
        logos = self._load_logos(ctx)

        canvas_width = img.width + params["left_margin"] + params["right_margin"]
        canvas_height = img.height + params["top_margin"] + params["bottom_margin"]
        common_spacing = int(0.02 * canvas_width)

        canvas = Image.new("RGBA", (canvas_width, canvas_height), params["color"])
        footer_start_y = params["top_margin"] + img.height

        canvas.paste(
            img,
            (params["left_margin"], params["top_margin"]),
            mask=img if img.mode == "RGBA" else None,
        )

        # Left-side text block — vertically centered on left edge
        left_img = side_images.get("left_side")
        if left_img is not None:
            left_x = params["left_margin"] + common_spacing
            left_y = params["top_margin"] + (img.height - left_img.height) // 2
            canvas.paste(
                left_img, (left_x, left_y),
                mask=left_img if left_img.mode == "RGBA" else None,
            )

        # Right-side text block — vertically centered on right edge
        right_img = side_images.get("right_side")
        if right_img is not None:
            right_x = canvas_width - params["right_margin"] - common_spacing - right_img.width
            right_y = params["top_margin"] + (img.height - right_img.height) // 2
            canvas.paste(
                right_img, (right_x, right_y),
                mask=right_img if right_img.mode == "RGBA" else None,
            )

        # Bottom bar: left logo
        left_logo = logos.get("left_logo")
        if left_logo is not None:
            self._paste_left_logo_bar(canvas, left_logo, params, footer_start_y, common_spacing)

        # Bottom bar: center logo
        self._paste_center_logo(canvas, logos["center_logo"], params, footer_start_y)

        # Bottom bar: right logo
        right_logo = logos.get("right_logo")
        if right_logo is not None:
            self._paste_right_logo(
                canvas=canvas,
                right_logo=right_logo,
                params=params,
                layout={
                    "rt_x": canvas_width - params["right_margin"] - common_spacing,
                    "rb_x": canvas_width - params["right_margin"] - common_spacing,
                },
                footer_start_y=footer_start_y,
                common_spacing=common_spacing,
            )

        ctx.update_buffer([canvas]).save_buffer(self.name()).success()

    def _paste_left_logo_bar(
        self,
        canvas: Image.Image,
        left_logo: Image.Image,
        params: dict,
        footer_start_y: int,
        common_spacing: int,
    ) -> None:
        """Paste the left logo in the bottom bar area (no image re-paste, no delimiter)."""
        left_logo = self._resize_logo_to_target_height(left_logo, canvas, params, footer_start_y)
        logo_x = params["left_margin"]
        logo_y = self._logo_y(canvas, left_logo.height, footer_start_y)
        canvas.paste(
            left_logo, (logo_x, logo_y),
            mask=left_logo if left_logo.mode == "RGBA" else None,
        )

    def _render_side_texts(
        self, ctx: PipelineContext, params: dict, img: Image.Image,
    ) -> dict[str, Image.Image | None]:
        """Render left and right side texts as vertically-stacked image blocks.

        Each side's text lines are rendered individually via ``start_process``
        and then composited into a single vertical strip.
        """
        bottom_margin = params["bottom_margin"]
        result: dict[str, Image.Image | None] = {"left_side": None, "right_side": None}

        for side_key in ("left_side", "right_side"):
            side_cfg = ctx.get(side_key)
            if not isinstance(side_cfg, dict) or "lines" not in side_cfg:
                continue

            lines = side_cfg["lines"]
            if not lines:
                continue

            height_ratio = side_cfg.get("height_ratio", 0) or 0.04
            font_height = max(8, int(bottom_margin * height_ratio / 0.12))

            line_images: list[Image.Image] = []
            for line_info in lines:
                proc_config = {
                    "processor_name": "rich_text",
                    "text": line_info["text"],
                    "color": line_info["color"],
                    "font_path": line_info["font_path"],
                    "height": font_height,
                }
                try:
                    rendered = start_process([proc_config])
                    line_images.append(rendered)
                except Exception:
                    logger.warning(
                        "Failed to render side text line: %s", line_info.get("text", "")
                    )

            if not line_images:
                continue

            gap = max(2, font_height // 6)
            stack_w = max(img.width for img in line_images)
            stack_h = sum(img.height for img in line_images) + gap * (len(line_images) - 1)
            stack = Image.new("RGBA", (stack_w, stack_h), (0, 0, 0, 0))

            y = 0
            for line_img in line_images:
                stack.paste(
                    line_img, (0, y),
                    mask=line_img if line_img.mode == "RGBA" else None,
                )
                y += line_img.height + gap

            result[side_key] = stack

        return result

    @staticmethod
    def _target_logo_height(params: dict, _footer_start_y: int) -> int:
        """统一 logo 高度：显式 logo_height 优先；0 则退回旧左侧 logo 的 footer 高度。"""
        return max(1, params["logo_height"] or params["bottom_margin"] or 1)

    def _resize_logo_to_target_height(
        self,
        logo: Image.Image,
        _canvas: Image.Image,
        params: dict,
        footer_start_y: int,
    ) -> Image.Image:
        """按统一目标高度等比缩放 logo。"""
        logo_height = self._target_logo_height(params, footer_start_y)
        target_w = max(1, round(logo.width * logo_height / logo.height)) if logo.height > 0 else logo_height
        return logo.resize((target_w, logo_height), Image.Resampling.LANCZOS)

    @staticmethod
    def _logo_y(canvas: Image.Image, logo_height: int, footer_start_y: int) -> int:
        """让 logo 在底部水印条内垂直居中。"""
        return footer_start_y + ((canvas.height - footer_start_y) - logo_height) // 2

    @staticmethod
    def _make_logo_delimiter(params: dict, logo_height: int) -> Image.Image:
        """创建高度为 logo 渲染高度 80% 的分隔线。"""
        return Image.new(
            "RGBA",
            (params["delimiter_width"], int(logo_height * 0.8)),
            params["delimiter_color"],
        )

    @staticmethod
    def _delimiter_y(logo_y: int, logo_height: int) -> int:
        """分隔线相对 logo 垂直居中。"""
        return int(logo_y + logo_height * 0.1)


@register("watermark_with_timestamp")
class WatermarkWithTimestampFilter(FilterProcessor):
    def process(self, ctx: PipelineContext):
        img = ctx.get_buffer()[0]

        if "height" not in ctx:
            ctx.set("height", int(img.height * .02))
        # 使用注册表动态获取处理器，避免直接导入
        multi_text_processor = get_processor("multi_rich_text")
        if multi_text_processor:
            multi_text_processor().process(ctx)
        else:
            raise RuntimeError("multi_rich_text processor not found")
        text = ctx.get_buffer()[0]

        text_x = int(img.width * .93) - text.width
        text_y = int(img.height * .95)

        img.paste(text, (text_x, text_y), mask=text)
        ctx.update_buffer([img]).save_buffer(self.name()).success()

    def name(self) -> str:
        return "watermark_with_timestamp"


@register("rounded_corner")
class RoundedCornerFilter(FilterProcessor):
    def process(self, ctx: PipelineContext):
        # CSS风格: border-radius, 单位px
        radius = ctx.getint("border_radius", 10)

        buffer = []
        for img in ctx.get_buffer():
            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            width, height = img.size

            # 创建圆角蒙版
            mask = Image.new('L', (width, height), 0)
            draw = ImageDraw.Draw(mask)

            # 绘制圆角矩形
            draw.rounded_rectangle([(0, 0), (width, height)], radius=radius, fill=255)

            # 应用蒙版
            output = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            output.paste(img, (0, 0))
            output.putalpha(mask)

            buffer.append(output)
        ctx.update_buffer(buffer).save_buffer(self.name()).success()

    def name(self) -> str:
        return "rounded_corner"


@register("shadow")
class ShadowFilter(FilterProcessor):

    def process(self, ctx: PipelineContext):
        shadow_color = ctx.getcolor("shadow_color", (0, 0, 0, 180))
        shadow_radius = ctx.getint("shadow_radius", 30)
        # 新参数：衰减强度，值越大边缘越干净（推荐 1.5 ~ 3.0）
        falloff = 1.5
        buffer = []
        for img in ctx.get_buffer():
            original_img = img.convert('RGBA') if img.mode != 'RGBA' else img
            w, h = original_img.size
            if shadow_radius <= 0:
                buffer.append(img)
                continue
            padding = int(shadow_radius * 2)
            full_width = w + padding * 2
            full_height = h + padding * 2
            # 1. 生成剪影阴影
            background = Image.new('RGBA', (full_width, full_height), (0, 0, 0, 0))
            shadow_layer = Image.new('RGBA', (w, h), shadow_color)
            shadow_layer.putalpha(original_img.getchannel('A'))
            background.paste(shadow_layer, (padding, padding))
            # 2. 高斯模糊
            shadow_blurred = background.filter(ImageFilter.GaussianBlur(shadow_radius))
            # 3. 关键：应用透明度衰减曲线，消除边缘残留
            shadow_blurred = self._apply_alpha_falloff(shadow_blurred, falloff)
            # 4. 合成原图
            shadow_blurred.paste(original_img, (padding, padding), mask=original_img)
            buffer.append(shadow_blurred)
        ctx.update_buffer(buffer).save_buffer(self.name()).success()

    def _apply_alpha_falloff(self, img: Image.Image, gamma: float) -> Image.Image:
        """
        对 Alpha 通道应用幂函数衰减
        公式: new_alpha = (alpha / 255) ^ gamma * 255
        gamma > 1 时，低透明度像素会被压制得更低，边缘更干净

        Phase 5.6：避免 ``img.split()`` 把 RGB 三通道也分裂出来（对大图是
        显著的内存拷贝）；改为 :meth:`Image.getchannel` 仅取 alpha；
        numpy 全程 in-place 运算减少中间数组分配。
        """
        # 仅取 alpha 通道（不解构其他三通道，省一次 split 拷贝）
        alpha_band = img.getchannel("A")
        # uint8 → float32：复用底层缓冲区
        alpha_array = np.asarray(alpha_band, dtype=np.float32)

        # in-place 缩放到 [0,1] 并应用幂函数（避免再分配中间数组）
        alpha_array *= 1.0 / 255.0
        np.power(alpha_array, gamma, out=alpha_array)

        # 硬截断极低透明度（in-place mask）
        alpha_array[alpha_array < 0.01] = 0.0

        # in-place 缩放回 [0,255] 并转 uint8
        alpha_array *= 255.0
        new_alpha = Image.fromarray(alpha_array.astype(np.uint8), mode="L")
        img.putalpha(new_alpha)
        return img

    def name(self) -> str:
        return "shadow"

@register("crop")
class CropFilter(FilterProcessor):

    def process(self, ctx: PipelineContext):
        width = ctx.getint("width", 0)
        height = ctx.getint("height", 0)
        offset = json.loads(ctx.get("offset", "[]"))

        buffer = []
        for img in ctx.get_buffer():
            img_width, img_height = img.size

            # 默认原图像尺寸
            if width <= 0:
                width = img_width
            if height <= 0:
                height = img_height

            # 默认居中
            left = (img_width - width) // 2
            top = (img_height - height) // 2

            # 处理偏移量
            offset_x = offset[0] if len(offset) > 0 else 0
            offset_y = offset[1] if len(offset) > 1 else 0
            left += offset_x
            top += offset_y

            # 计算边界
            left = max(0, min(left, img_width - width))
            top = max(0, min(top, img_height - height))
            right = left + width
            bottom = top + height

            # 执行裁剪
            cropped_img = img.crop((left, top, right, bottom))
            buffer.append(cropped_img)

        ctx.update_buffer(buffer).save_buffer(self.name()).success()

    def name(self) -> str:
        return "crop"


@register("signature")
class SignatureFilter(FilterProcessor):
    """签名水印滤镜（Phase 26）— 在【原图区域内】粘贴用户签名图（保留彩色像素 + 黑白二值切换）。

    设计要点：

    - **像素三分类**（Phase 26 重构）：处理器把签名图每个像素归为三类：

      1. *近白*（R/G/B 均 ≥ 240 且接近灰度）→ alpha 置 0（视为白底/纸张）；
      2. *近黑*（R/G/B 均 ≤ 20 且接近灰度）→ 笔画像素，根据
         ``signature_invert_mono`` 切换为黑（False）或白（True）；
      3. *彩色*（任何带色相的像素，如签名上的红点）→ **RGB 完全保留**，
         alpha 由 RGB 亮度推导以处理抗锯齿边缘。

      → 用户的彩色装饰（红点 / 印章 / 颜色笔画）永不会被破坏，
      ``signature_invert_mono`` 仅在黑↔白笔画间切换。
    - **粘贴区域**：原图区域 = 画布去掉 watermark margins 后的内层矩形：
      ``[top_margin, canvas.height - bottom_margin) × [left_margin, canvas.width - right_margin)``。
      若 watermark 未启用，所有 margins 都是 0 → 区域 = 整张画布。
    - **9 宫格锚点**：``{top|middle|bottom}_{left|center|right}``，共 9 种锚点。
    - **定位策略**：9 宫格锚点先确定照片主体区域内的参考点；
      ``signature_margin_x`` / ``signature_margin_y`` 表示签名边缘（left/right/top/bottom
      锚点）或签名中心（center/middle 锚点）相对该参考点的有符号偏移。
    - **尺寸策略**：``target_w = min(area_w, area_h) * signature_size_ratio``，
      以照片主体短边为统一基准，降低 9:16 / 16:9 / 1:1 间的视觉尺寸漂移。
      高度按签名 PNG 原始宽高比等比推算；若高度超出区域，按 area_h 等比 fit。
    - **增强策略**：可选 ``none`` / ``soft_shadow`` / ``soft_glow`` / ``soft_outline``，
      基于抠像后的 alpha 蒙版生成柔和投影、外发光或描边。
    - **接入位置**：在 ``watermark`` 之后；若签名文件缺失，记 warning 并直通。
    """

    # 签名宽度占照片主体短边比例（target_w = min(area_w, area_h) × ratio）
    DEFAULT_SIZE_RATIO = 0.20
    MIN_SIZE_RATIO = 0.01
    MAX_SIZE_RATIO = 1.0
    # 9 宫格锚点常量
    _VALID_ENHANCEMENTS = frozenset({
        "none", "soft_shadow", "soft_glow", "soft_outline",
    })
    _VALID_ANCHORS = frozenset({
        "top_left", "top_center", "top_right",
        "middle_left", "middle_center", "middle_right",
        "bottom_left", "bottom_center", "bottom_right",
    })

    def process(self, ctx: PipelineContext):
        if not ctx.get("signature_enabled", False):
            ctx.success()
            return

        sig_path = ctx.get("signature_path", "")
        if not sig_path:
            logger.warning("[SignatureFilter] signature_enabled=True 但未提供 signature_path，跳过。")
            ctx.success()
            return

        buffer = ctx.get_buffer()
        if not buffer:
            ctx.success()
            return
        canvas = buffer[0]
        if canvas.mode != "RGBA":
            canvas = canvas.convert("RGBA")

        # 加载签名图
        try:
            from core.image_io import load_logo
            sig_img = load_logo(sig_path)
        except FileNotFoundError:
            logger.warning(f"[SignatureFilter] 签名文件不存在: {sig_path}，跳过。")
            ctx.success()
            return

        # 计算"原图区域"边界（剥掉 WatermarkFilter 添加的四边 margin）
        top_m = max(0, ctx.getint("top_margin", 0))
        bottom_m = max(0, ctx.getint("bottom_margin", 0))
        left_m = max(0, ctx.getint("left_margin", 0))
        right_m = max(0, ctx.getint("right_margin", 0))

        area_left = left_m
        area_top = top_m
        area_right = canvas.width - right_m
        area_bottom = canvas.height - bottom_m
        area_w = max(0, area_right - area_left)
        area_h = max(0, area_bottom - area_top)
        if area_w <= 0 or area_h <= 0:
            logger.warning("[SignatureFilter] 原图区域尺寸非正，跳过。")
            ctx.success()
            return

        # 宽度占照片主体短边比例 — target_w = min(area_w, area_h) × ratio。
        try:
            user_ratio = float(ctx.get("signature_size_ratio", self.DEFAULT_SIZE_RATIO))
        except (TypeError, ValueError):
            user_ratio = self.DEFAULT_SIZE_RATIO
        user_ratio = max(self.MIN_SIZE_RATIO, min(self.MAX_SIZE_RATIO, user_ratio))

        target_w = max(1, int(min(area_w, area_h) * user_ratio))
        # 按 PNG 原始宽高比等比推算高度（防御 sig_img.width=0）
        if sig_img.width > 0:
            target_h = max(1, int(target_w * sig_img.height / sig_img.width))
        else:
            target_h = max(1, sig_img.height)
        # 防止高度超出区域：若 target_h > area_h，按 area_h 等比 fit
        if target_h > area_h:
            fit_ratio = area_h / target_h
            target_h = max(1, area_h)
            target_w = max(1, int(target_w * fit_ratio))
        sig_resized = sig_img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        # Phase 26：白→透明 / 黑↔白二值切换 / 彩色像素保留原色
        invert_mono = bool(ctx.get("signature_invert_mono", False))
        tinted = self._apply_color_swap(sig_resized, invert_mono=invert_mono)
        enhancement = str(ctx.get("signature_enhancement", "none")).lower()
        if enhancement not in self._VALID_ENHANCEMENTS:
            logger.warning(f"[SignatureFilter] 未知签名增强模式 {enhancement!r}，回退 none。")
            enhancement = "none"
        strength = self._normalize_enhancement_strength(
            ctx.get("signature_enhancement_strength", 50)
        )
        enhanced = self._apply_enhancement(
            tinted,
            mode=enhancement,
            invert_mono=invert_mono,
            strength=strength,
        )

        anchor = str(ctx.get("signature_anchor", "middle_center")).lower()
        if anchor not in self._VALID_ANCHORS:
            logger.warning(f"[SignatureFilter] 未知签名锚点 {anchor!r}，回退 middle_center。")
            anchor = "middle_center"

        # 比例值 → 像素值：margin_x 基准为 area_w，margin_y 基准为 area_h
        margin_x = int(float(ctx.get("signature_margin_x", 0.0) or 0.0) * area_w)
        margin_y = int(float(ctx.get("signature_margin_y", 0.0) or 0.0) * area_h)

        paste_x, paste_y = self._compute_paste_xy(
            anchor=anchor,
            area_left=area_left, area_top=area_top,
            area_right=area_right, area_bottom=area_bottom,
            target_w=target_w, target_h=target_h,
            margin_x=margin_x, margin_y=margin_y,
        )

        canvas.alpha_composite(enhanced, (paste_x, paste_y))
        ctx.update_buffer([canvas]).save_buffer(self.name()).success()

    def name(self) -> str:
        return "signature"

    @staticmethod
    def _compute_paste_xy(
        *,
        anchor: str,
        area_left: int, area_top: int,
        area_right: int, area_bottom: int,
        target_w: int, target_h: int,
        margin_x: float, margin_y: float,
    ) -> tuple[int, int]:
        """根据 9 宫格参考点计算签名左上角粘贴坐标。

        语义：
        - 所有锚点（left/right/top/bottom/center/middle）：``margin_x/y`` 均表示签名
          中心相对锚点参考点的偏移（像素）。修改签名大小时，中心位置保持不变，
          签名从中心向四周缩放。
        上游已由比例值（占 area_w/area_h 比例）换算为像素。x 正向右，y 正向下。
        """
        area_w = area_right - area_left
        area_h = area_bottom - area_top
        vertical, _, horizontal = anchor.partition("_")

        if horizontal == "left":
            center_x = area_left + margin_x
            paste_x = center_x - target_w / 2
        elif horizontal == "right":
            center_x = area_right + margin_x
            paste_x = center_x - target_w / 2
        else:  # center
            paste_x = area_left + area_w / 2 + margin_x - target_w / 2

        if vertical == "top":
            center_y = area_top + margin_y
            paste_y = center_y - target_h / 2
        elif vertical == "bottom":
            center_y = area_bottom + margin_y
            paste_y = center_y - target_h / 2
        else:  # middle
            paste_y = area_top + area_h / 2 + margin_y - target_h / 2

        return int(paste_x), int(paste_y)

    @staticmethod
    def _normalize_enhancement_strength(value: object) -> float:
        """把 0~100 的 UI 强度值归一化为 0.0~1.0。"""
        try:
            strength = float(value)
        except (TypeError, ValueError):
            strength = 50.0
        return max(0.0, min(100.0, strength)) / 100.0

    @staticmethod
    def _apply_enhancement(
        img: Image.Image,
        *,
        mode: str,
        invert_mono: bool,
        strength: float = 0.5,
    ) -> Image.Image:
        """基于签名 alpha 蒙版生成增强层，并返回同尺寸合成结果。"""
        # UI 仍然保持 0~100% 的用户语义，但把 100% 对应的实际增强强度翻倍，
        # 方便用户在滑到最右侧时获得更明显的投影 / 外发光 / 描边效果。
        strength = max(0.0, min(1.0, strength)) * 2.0
        if mode == "none" or strength <= 0:
            return img

        alpha = img.getchannel("A")
        if mode == "soft_shadow":
            effect = Image.new("RGBA", img.size, (0, 0, 0, 0))
            # 不扩展画布，保持现有正向偏移模型；通过更大的 blur 半径扩大投影面积，
            # 并让边缘更柔和，避免新增尺寸变化影响签名定位。
            shadow = alpha.filter(ImageFilter.GaussianBlur(radius=24))
            shadow = shadow.point(lambda p: int(p * 0.70 * strength))
            effect.putalpha(shadow)
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            layer.alpha_composite(effect, (4, 4))
        elif mode == "soft_glow":
            glow_rgb = (0, 0, 0) if invert_mono else (255, 255, 255)
            glow = alpha.filter(ImageFilter.GaussianBlur(radius=5))
            glow = glow.point(lambda p: int(p * 0.64 * strength))
            layer = Image.new("RGBA", img.size, (*glow_rgb, 0))
            layer.putalpha(glow)
        elif mode == "soft_outline":
            outline_rgb = (0, 0, 0) if invert_mono else (255, 255, 255)
            outline = alpha.filter(ImageFilter.MaxFilter(size=5))
            outline = outline.filter(ImageFilter.GaussianBlur(radius=1.2))
            outline = outline.point(lambda p: int(p * 1.10 * strength))
            layer = Image.new("RGBA", img.size, (*outline_rgb, 0))
            layer.putalpha(outline)
        else:
            return img

        out = Image.new("RGBA", img.size, (0, 0, 0, 0))
        out.alpha_composite(layer)
        out.alpha_composite(img)
        return out

    # ── Phase 26：颜色处理阈值 ──
    # 近白判定：R/G/B 均 ≥ WHITE_THRESHOLD 且 |max-min| ≤ CHROMA_TOL → 视为纸张
    WHITE_THRESHOLD = 240
    # 近黑判定：R/G/B 均 ≤ BLACK_THRESHOLD 且 |max-min| ≤ CHROMA_TOL → 视为笔画
    BLACK_THRESHOLD = 20
    # 色度容差：max(R,G,B) - min(R,G,B) ≤ CHROMA_TOL → "无色"（灰阶）
    CHROMA_TOL = 15

    @staticmethod
    def _apply_color_swap(img: Image.Image, *, invert_mono: bool) -> Image.Image:
        """Phase 26：按像素三分类处理签名图 — 白底→透明、黑↔白可切换、彩色保留。

        像素分类（基于源图 RGB，忽略源图 alpha）：

        1. **近白**（R/G/B 均 ≥ ``WHITE_THRESHOLD`` 且 |max-min| ≤ ``CHROMA_TOL``）
           → ``alpha=0``（视为纸张/白底）。
        2. **近黑**（R/G/B 均 ≤ ``BLACK_THRESHOLD`` 且 |max-min| ≤ ``CHROMA_TOL``）
           → 笔画：``invert_mono=False`` → 输出黑色 (0,0,0,255)；
                  ``invert_mono=True`` → 输出白色 (255,255,255,255)。
        3. **彩色**（任何带色相像素，如签名上的红点）
           → RGB 原样保留；alpha 由 RGB 亮度推导（亮度越低 → alpha 越高），
              保证抗锯齿边缘平滑融合。

        中间灰度（既非近白也非近黑的"无色"像素，例如黑笔画的抗锯齿边缘）
        被作为笔画延伸处理：RGB 跟随 ``invert_mono`` 切换，alpha 由亮度推导。
        """
        # 强制丢弃源图 alpha，统一从 RGB 三通道推导
        rgb = np.asarray(img.convert("RGB"), dtype=np.uint8)  # (H, W, 3)
        r = rgb[..., 0].astype(np.int16)
        g = rgb[..., 1].astype(np.int16)
        b = rgb[..., 2].astype(np.int16)

        max_c = np.maximum(np.maximum(r, g), b)
        min_c = np.minimum(np.minimum(r, g), b)
        chroma = max_c - min_c  # 色度差；越小越接近灰阶

        is_achromatic = chroma <= SignatureFilter.CHROMA_TOL
        is_near_white = is_achromatic & (min_c >= SignatureFilter.WHITE_THRESHOLD)
        is_near_black = is_achromatic & (max_c <= SignatureFilter.BLACK_THRESHOLD)
        is_chromatic = ~is_achromatic  # 真彩色像素
        is_mid_gray = is_achromatic & ~is_near_white & ~is_near_black

        h, w = rgb.shape[:2]
        out = np.zeros((h, w, 4), dtype=np.uint8)

        # 笔画颜色（黑或白）— 由 invert_mono 控制
        stroke_rgb = (255, 255, 255) if invert_mono else (0, 0, 0)

        # ── 类 1：近白 → 全透明（out 已初始化为 0） ──

        # ── 类 2：近黑 → 笔画完全不透明 ──
        out[is_near_black, 0] = stroke_rgb[0]
        out[is_near_black, 1] = stroke_rgb[1]
        out[is_near_black, 2] = stroke_rgb[2]
        out[is_near_black, 3] = 255

        # 亮度（标准 luminance 近似）：0.299R + 0.587G + 0.114B；用于推导 alpha
        luminance = (0.299 * r + 0.587 * g + 0.114 * b).astype(np.float32)
        alpha_from_luminance = np.clip(255.0 - luminance, 0, 255).astype(np.uint8)

        # ── 类 3：彩色像素 → 保留原 RGB；alpha 由亮度推导 ──
        out[is_chromatic, 0] = rgb[is_chromatic, 0]
        out[is_chromatic, 1] = rgb[is_chromatic, 1]
        out[is_chromatic, 2] = rgb[is_chromatic, 2]
        out[is_chromatic, 3] = alpha_from_luminance[is_chromatic]

        # ── 中间灰度（笔画抗锯齿边缘）→ 跟随 stroke 颜色，alpha 由亮度推导 ──
        out[is_mid_gray, 0] = stroke_rgb[0]
        out[is_mid_gray, 1] = stroke_rgb[1]
        out[is_mid_gray, 2] = stroke_rgb[2]
        out[is_mid_gray, 3] = alpha_from_luminance[is_mid_gray]

        return Image.fromarray(out, mode="RGBA")
