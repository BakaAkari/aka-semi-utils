"""字体预览组件 — 用 PIL 生成实时预览图。"""

from PIL import Image, ImageDraw, ImageFont
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel

from core.font_manager import resolve_font


class FontPreview(QLabel):
    """字体预览 QLabel，显示预览文字。"""
    
    def __init__(self, font_name: str = "NotoSansCJKsc-Regular.otf", color: str = "#FFFFFF", parent=None):
        super().__init__(parent)
        self.font_name = font_name
        self.color = color
        self.setFixedSize(100, 26)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("border: 1px solid #333333; border-radius: 4px;")
        self.update_preview()
    
    def set_font(self, font_name: str):
        """设置字体并更新预览。"""
        self.font_name = font_name
        self.update_preview()
    
    def set_color(self, color: str):
        """设置颜色并更新预览。"""
        self.color = color
        self.update_preview()
    
    def update_preview(self):
        """重新生成预览图。"""
        try:
            img = self._generate_preview_image()
            # PIL → QPixmap
            data = img.convert("RGBA").tobytes("raw", "RGBA")
            qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
            pixmap = QPixmap.fromImage(qimg)
            self.setPixmap(pixmap)
        except Exception:
            self.setText("预览")
    
    def _generate_preview_image(self) -> Image.Image:
        """PIL 生成预览图。"""
        text = "水印示例"
        size = (100, 26)
        
        # 解析颜色
        color = self.color if self.color.startswith("#") else "#FFFFFF"
        
        # 创建透明背景
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        try:
            font_path = resolve_font(self.font_name)
            font = ImageFont.truetype(str(font_path), 12)
        except Exception:
            font = ImageFont.load_default()
        
        # 计算居中
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = max(0, (size[0] - text_w) // 2)
        y = max(0, (size[1] - text_h) // 2 - bbox[1])
        
        # 绘制文字（带颜色）
        draw.text((x, y), text, fill=color, font=font)
        
        return img
