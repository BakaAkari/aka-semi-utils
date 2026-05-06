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
                target_size = (int(width), int(height))
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
                target_size = (int(img.width * scale_f), int(img.height * scale_f))

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
    - :meth:`_paste_main_and_left`    — 主图 + 左 logo
    - :meth:`_paste_center_logo`      — 中央 logo（含按高度 resize）
    - :meth:`_compute_text_layout`    — 计算四角文本坐标
    - :meth:`_paste_texts`            — 粘贴四角文本
    - :meth:`_paste_right_logo`       — 右 logo + 分隔线
    """

    def process(self, ctx: PipelineContext):
        img = ctx.get_buffer()[0]
        params = self._collect_params(ctx, img)

        corners = self._render_corner_texts(ctx, params)
        logos = self._load_logos(ctx)

        canvas_width = img.width + params["left_margin"] + params["right_margin"]
        canvas_height = img.height + params["top_margin"] + params["bottom_margin"]
        common_spacing = int(0.02 * canvas_width)

        canvas = Image.new("RGBA", (canvas_width, canvas_height), params["color"])
        footer_start_y = params["top_margin"] + img.height

        left_logo_width = self._paste_main_and_left(
            canvas, img, logos["left_logo"], params, footer_start_y
        )
        self._paste_center_logo(canvas, logos["center_logo"], ctx, footer_start_y)

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
                corners=corners,
                params=params,
                canvas_width=canvas_width,
                footer_start_y=footer_start_y,
                elem_margin=layout["elem_margin"],
                elem_height=layout["elem_height"],
                common_spacing=common_spacing,
            )

        ctx.update_buffer([canvas]).save_buffer(self.name()).success()

    def name(self) -> str:
        return "watermark"

    # ------------------------------------------------------------- helpers
    def _collect_params(self, ctx: PipelineContext, img: Image.Image) -> dict:
        """把 ctx 中散落的字符串键收拢为一个局部参数 dict。"""
        bottom_margin = ctx.getint("bottom_margin", int(img.height * 0.12))
        return {
            "color": ctx.get("color", "white"),
            "delimiter_color": ctx.get("delimiter_color", "black"),
            "delimiter_width": ctx.getint("delimiter_width", int(img.width * 0.003)),
            "left_margin": ctx.getint("left_margin", 0),
            "right_margin": ctx.getint("right_margin", 0),
            "top_margin": ctx.getint("top_margin", 0),
            "bottom_margin": bottom_margin,
            "middle_spacing": ctx.getint("middle_spacing", int(bottom_margin * 0.05)),
            "right_alignment": ctx.getenum("right_alignment", Alignment.RIGHT, Alignment),
        }

    def _render_corner_texts(self, ctx: PipelineContext, params: dict) -> dict[str, Image.Image]:
        """渲染左上/左下/右上/右下四个角落的文本图。

        Phase 11：彻底关闭"按画布宽度自动缩放文本"的行为 —
        仅当 corner 配置未显式指定 ``height`` 时，才用 ``bottom_margin * 0.3`` 作为兜底；
        对超宽文本只记录 warning 不再 resize，保证字号在不同分辨率源图下完全一致。
        """
        bottom_margin = params["bottom_margin"]
        for t_s in [ctx.get("left_top"), ctx.get("left_bottom"),
                    ctx.get("right_top"), ctx.get("right_bottom")]:
            if t_s and "height" not in t_s:
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

        # Phase 11：禁用自动缩放 —— 仅在文本超过画布安全宽度时给出 warning，绝不 resize。
        img = ctx.get_buffer()[0]
        canvas_width = img.width + params["left_margin"] + params["right_margin"]
        effective_width = canvas_width - params["left_margin"] - params["right_margin"]
        max_text_width = max(1, int(effective_width * 0.42))

        for corner_name, text_img in corners.items():
            if text_img.width > max_text_width:
                logger.warning(
                    f"[WatermarkFilter] {corner_name} 文本宽度 {text_img.width}px 超过画布安全宽度 "
                    f"{max_text_width}px（可能被画布裁剪）。"
                    f"Phase 11 已禁用自动缩放以保证字号统一 —— 请减小 corner.height 或精简文本。"
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
            except FileNotFoundError:
                logger.warning(f"Logo 文件不存在: {path}")
        return logos

    def _paste_main_and_left(
        self,
        canvas: Image.Image,
        img: Image.Image,
        left_logo: Image.Image | None,
        params: dict,
        footer_start_y: int,
    ) -> int:
        """粘贴主图 + 左 logo（按 footer 高度等比缩放，不压扁），返回实际渲染宽度。

        Phase 14（方案 C）：左 logo 改为按高度等比缩放，宽度由原图比例决定，
        不再强制压成正方形。返回值 left_logo_width 喂给 _compute_text_layout，
        让左侧文本起始 X 坐标自动避开可变宽度的 logo。
        """
        canvas.paste(
            img,
            (params["left_margin"], params["top_margin"]),
            mask=img if img.mode == "RGBA" else None,
        )
        if not left_logo:
            return 0
        logo_height = canvas.height - footer_start_y
        if left_logo.height > 0:
            scale = logo_height / left_logo.height
            target_w = max(1, round(left_logo.width * scale))
        else:
            target_w = logo_height
        left_logo = left_logo.resize((target_w, logo_height), Image.Resampling.LANCZOS)
        canvas.paste(
            left_logo,
            (params["left_margin"], footer_start_y),
            mask=left_logo if left_logo.mode == "RGBA" else None,
        )
        return left_logo.width

    def _paste_center_logo(
        self,
        canvas: Image.Image,
        center_logo: Image.Image | None,
        ctx: PipelineContext,
        footer_start_y: int,
    ) -> None:
        """粘贴中央 logo（先用 ResizeFilter 按高度等比缩放再居中粘贴）。"""
        if not center_logo:
            return
        center_logo_height = ctx.getint("center_logo_height")
        logo_height = center_logo_height if center_logo_height else canvas.height - footer_start_y

        resize_ctx = PipelineContext({"buffer": [center_logo], "height": logo_height})
        resize_processor = get_processor("resize")
        if resize_processor:
            resize_processor().process(resize_ctx)
            center_logo = resize_ctx.get_buffer()[0]
        else:
            logger.warning("ResizeFilter not found in registry, skipping logo resize")

        center_x = (canvas.width - center_logo.width) // 2
        center_y = footer_start_y + ((canvas.height - footer_start_y) - center_logo.height) // 2
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
        corners: dict,
        params: dict,
        canvas_width: int,
        footer_start_y: int,
        elem_margin: int,
        elem_height: int,
        common_spacing: int,
    ) -> None:
        """粘贴右 logo + 与文本之间的分隔线。

        Phase 14（方案 C）：右 logo 按高度等比缩放（高度 = ``elem_height``），
        宽度由原图比例决定；右 logo X 坐标根据**实际渲染宽度**反推，让横长 logo
        也能完整显示。分隔线高度仍以 elem_height 为基准（与文本块高度匹配）。
        """
        logo_height = elem_height
        delimiter = Image.new(
            "RGBA",
            (params["delimiter_width"], int(logo_height * 1.1)),
            params["delimiter_color"],
        )
        rt, rb = corners["right_top"], corners["right_bottom"]
        delimiter_x = (
            canvas_width
            - params["right_margin"]
            - max(rt.width, rb.width)
            - 2 * common_spacing
            - delimiter.width
        )
        delimiter_y = int(footer_start_y + elem_margin - logo_height * 0.05)
        canvas.paste(delimiter, (delimiter_x, delimiter_y), mask=delimiter)

        # 等比缩放：宽度 = round(orig_w * target_h / orig_h)
        if right_logo.height > 0:
            scale = logo_height / right_logo.height
            target_w = max(1, round(right_logo.width * scale))
        else:
            target_w = logo_height
        right_logo = right_logo.resize((target_w, logo_height), Image.Resampling.LANCZOS)
        right_logo_x = delimiter_x - common_spacing - right_logo.width
        right_logo_y = footer_start_y + elem_margin
        canvas.paste(
            right_logo,
            (right_logo_x, right_logo_y),
            mask=right_logo if right_logo.mode == "RGBA" else None,
        )


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


