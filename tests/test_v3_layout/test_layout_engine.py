"""V3 Layout Engine 单元测试。"""


from shared.v3_layout.layout_engine import (
    CanvasConfig,
    MarginsConfig,
    Rect,
    RegionConfig,
    SlotConfig,
    StyleConfig,
    TextContent,
    WatermarkConfig,
    compute_layout,
)


def _make_chip():
    return {"field_id": "make"}


class TestCanvasSize:
    """画布尺寸计算。"""

    def test_no_margins(self):
        config = WatermarkConfig(
            canvas=CanvasConfig(margins=MarginsConfig()),
        )
        result = compute_layout(config, 1920, 1080)
        assert result.canvas.w == 1920
        assert result.canvas.h == 1080
        assert result.image_rect == Rect(x=0, y=0, w=1920, h=1080)

    def test_with_margins(self):
        config = WatermarkConfig(
            canvas=CanvasConfig(margins=MarginsConfig(top=10, right=20, bottom=30, left=40)),
        )
        result = compute_layout(config, 1000, 800)
        assert result.canvas.w == 1000 + 40 + 20  # 1060
        assert result.canvas.h == 800 + 10 + 30   # 840
        assert result.image_rect == Rect(x=40, y=10, w=1000, h=800)


class TestFontSize:
    """字号解析策略。"""

    def test_absolute_font_size(self):
        style = StyleConfig(font_size=48)
        result = compute_layout(
            WatermarkConfig(
                canvas=CanvasConfig(margins=MarginsConfig(bottom=100)),
                regions=[
                    RegionConfig(
                        id="footer",
                        type="footer-bar",
                        enabled=True,
                        slots={
                            "left-top": SlotConfig(
                                enabled=True,
                                content=TextContent(chips=[_make_chip()]),
                                style=style,
                            )
                        },
                    )
                ],
            ),
            1920, 1080,
        )
        el = result.elements[0]
        assert el.style.font_size == 48

    def test_short_edge_reference(self):
        """使用 short_edge 作为字号基准。"""
        style = StyleConfig(font_size_ratio=0.05, size_reference="short_edge")
        result = compute_layout(
            WatermarkConfig(
                canvas=CanvasConfig(margins=MarginsConfig(bottom=100)),
                regions=[
                    RegionConfig(
                        id="footer",
                        type="footer-bar",
                        enabled=True,
                        slots={
                            "left-top": SlotConfig(
                                enabled=True,
                                content=TextContent(chips=[_make_chip()]),
                                style=style,
                            )
                        },
                    )
                ],
            ),
            1920, 1080,
        )
        el = result.elements[0]
        # 短边 = 1080, ratio = 0.05 → 54px
        assert el.style.font_size == 54

    def test_short_edge_same_for_both_orientations(self):
        """16:9 和 9:16 使用 short_edge 时字号相同。"""
        style = StyleConfig(font_size_ratio=0.05, size_reference="short_edge")
        config = WatermarkConfig(
            canvas=CanvasConfig(margins=MarginsConfig(bottom=100)),
            regions=[
                RegionConfig(
                    id="footer",
                    type="footer-bar",
                    enabled=True,
                    slots={
                        "left-top": SlotConfig(
                            enabled=True,
                            content=TextContent(chips=[_make_chip()]),
                            style=style,
                        )
                    },
                )
            ],
        )

        r1 = compute_layout(config, 1920, 1080)   # 16:9
        r2 = compute_layout(config, 1080, 1920)   # 9:16

        assert r1.elements[0].style.font_size == r2.elements[0].style.font_size == 54

    def test_region_height_reference(self):
        """使用 region_height 作为字号基准（默认）。"""
        style = StyleConfig(font_size_ratio=0.5)
        result = compute_layout(
            WatermarkConfig(
                canvas=CanvasConfig(margins=MarginsConfig(bottom=120)),
                regions=[
                    RegionConfig(
                        id="footer",
                        type="footer-bar",
                        enabled=True,
                        slots={
                            "left-top": SlotConfig(
                                enabled=True,
                                content=TextContent(chips=[_make_chip()]),
                                style=style,
                            )
                        },
                    )
                ],
            ),
            1920, 1080,
        )
        el = result.elements[0]
        # footer-bar 的 left-top 在区域上半部分（高=60）
        # ratio = 0.5 → 字号 = 60 * 0.5 = 30px
        assert el.style.font_size == 30


class TestSideEdge:
    """side-edge 区域。"""

    def test_side_edge_width_pixel(self):
        """side-edge 使用固定像素宽度。"""
        result = compute_layout(
            WatermarkConfig(
                canvas=CanvasConfig(margins=MarginsConfig()),
                regions=[
                    RegionConfig(
                        id="side-left",
                        type="side-edge",
                        enabled=True,
                        edge="left",
                        width={"mode": "pixel", "value": 150},
                        slots={
                            "line1": SlotConfig(
                                enabled=True,
                                content=TextContent(chips=[_make_chip()]),
                            )
                        },
                    )
                ],
            ),
            1920, 1080,
        )
        el = result.elements[0]
        # side-edge 元素在区域内，有 8px 水平 padding
        assert el.rect.x == 8  # 左侧 padding
        assert el.rect.w == 150 - 16  # 区域宽 150px，减去左右 padding
        assert el.rect.h > 0

    def test_side_edge_width_ratio(self):
        """side-edge 使用短边比例宽度。"""
        result = compute_layout(
            WatermarkConfig(
                canvas=CanvasConfig(margins=MarginsConfig()),
                regions=[
                    RegionConfig(
                        id="side-left",
                        type="side-edge",
                        enabled=True,
                        edge="left",
                        width={"mode": "short_edge_ratio", "value": 0.12},
                        slots={
                            "line1": SlotConfig(
                                enabled=True,
                                content=TextContent(chips=[_make_chip()]),
                            )
                        },
                    )
                ],
            ),
            1920, 1080,
        )
        el = result.elements[0]
        # 短边 = 1080, ratio = 0.12 → round(130) 区域宽度，减去 16px padding
        assert el.rect.w == 130 - 16

    def test_side_edge_same_width_both_orientations(self):
        """16:9 和 9:16 使用 short_edge_ratio 时区域宽度相同。"""
        config = WatermarkConfig(
            canvas=CanvasConfig(margins=MarginsConfig()),
            regions=[
                RegionConfig(
                    id="side-left",
                    type="side-edge",
                    enabled=True,
                    edge="left",
                    width={"mode": "short_edge_ratio", "value": 0.12},
                    slots={
                        "line1": SlotConfig(enabled=True, content=TextContent(chips=[_make_chip()]))
                    },
                )
            ],
        )
        r1 = compute_layout(config, 1920, 1080)
        r2 = compute_layout(config, 1080, 1920)
        assert r1.elements[0].rect.w == r2.elements[0].rect.w == 114


class TestFreePosition:
    """自由定位区域。"""

    def test_free_anchor_bottom_right(self):
        """签名在右下角偏移。"""
        result = compute_layout(
            WatermarkConfig(
                canvas=CanvasConfig(margins=MarginsConfig()),
                regions=[
                    RegionConfig(
                        id="sig",
                        type="free",
                        enabled=True,
                        anchor="bottom-right",
                        offset_x=-0.05,
                        offset_y=-0.05,
                        offset_unit="short_edge_ratio",
                    )
                ],
            ),
            1920, 1080,
        )
        # 锚点 = (1920, 1080)，偏移 = -1080*0.05 = -54
        # 最终位置 = (1866, 1026)
        assert result.elements == []  # free 区域没有 slots 时不生成元素


class TestEmptyConfig:
    """空配置边界情况。"""

    def test_no_regions(self):
        result = compute_layout(WatermarkConfig(), 100, 100)
        assert result.canvas.w == 100
        assert result.canvas.h == 100
        assert len(result.elements) == 0

    def test_disabled_region(self):
        result = compute_layout(
            WatermarkConfig(
                regions=[
                    RegionConfig(id="footer", type="footer-bar", enabled=False)
                ]
            ),
            100, 100,
        )
        assert len(result.elements) == 0
