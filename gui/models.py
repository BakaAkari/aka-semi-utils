"""数据模型层 — AppState 统一状态管理。"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from pathlib import Path
import json
import logging

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


@dataclass
class CornerConfig:
    """单角水印配置。"""
    fields: List[str] = field(default_factory=list)  # 字段列表
    separator: str = " · "                           # 分隔符
    font: str = "NotoSansCJKsc-Regular.otf"         # 字体
    color: str = "#FFFFFF"                          # 颜色


@dataclass
class LogoConfig:
    """Logo 配置。"""
    enabled: str = "auto"       # auto / disabled / custom
    position: str = "right"   # right / center / left
    color: str = "#FFFFFF"    # 分隔线颜色
    custom_path: str = ""       # 自定义路径


@dataclass
class AdvancedConfig:
    """高级设置配置。"""
    # 全局字体
    global_font: str = "NotoSansCJKsc-Regular.otf"
    global_color: str = "#FFFFFF"
    
    # 边框/留白
    left_margin: int = 0
    right_margin: int = 0
    top_margin: int = 0
    bottom_margin: int = 0
    margin_color: str = "#FFFFFF"
    
    # 圆角与阴影
    border_radius: int = 0
    shadow_radius: int = 0
    shadow_color: str = "#000000"
    
    # 图像质量
    quality: int = 95
    subsampling: int = 0  # 0/1/2
    
    # 背景效果
    blur_radius: int = 0
    ratio_enabled: bool = False
    ratio: str = "3:4"
    
    # 图像调整
    scale: float = 1.0
    trim_enabled: bool = False
    trim_threshold: float = 0.0
    
    # 拼接与对齐
    concat_direction: str = "vertical"  # horizontal / vertical
    alignment_mode: str = "center"      # top / center / bottom
    
    # 签名
    signature_enabled: bool = False
    signature_path: str = ""
    signature_color: str = "black"


@dataclass
class OutputConfig:
    """输出配置。"""
    path: str = "{source_dir}/logo"
    override: bool = True


class AppState(QObject):
    """统一状态管理。Panel 通过信号订阅变更，禁止直接写字段。"""
    
    # 信号
    files_changed = pyqtSignal(list)               # 文件列表变更
    output_changed = pyqtSignal()                   # 输出配置变更
    watermark_changed = pyqtSignal()              # 水印配置变更
    advanced_changed = pyqtSignal()                 # 高级设置变更
    template_changed = pyqtSignal(str)            # 模板切换
    progress_changed = pyqtSignal(int, str)        # 进度, 状态文字
    
    def __init__(self):
        super().__init__()
        
        # 文件列表
        self.selected_files: List[str] = []
        
        # 四角配置
        self.left_top = CornerConfig()
        self.left_bottom = CornerConfig()
        self.right_top = CornerConfig()
        self.right_bottom = CornerConfig()
        
        # Logo 配置
        self.logo = LogoConfig()
        
        # 全局自定义文本
        self.custom_text: str = ""
        
        # 高级设置
        self.advanced = AdvancedConfig()
        
        # 输出配置
        self.output = OutputConfig()
        
        # 模板
        self.current_template: str = "default"
        
        # 处理状态
        self.is_processing: bool = False
        self.progress: int = 0
        self.status_text: str = "就绪"
    
    # ---- 文件操作 ----
    def add_files(self, paths: List[str]):
        """追加图片文件。"""
        self.selected_files.extend(paths)
        self.files_changed.emit(self.selected_files)
    
    def remove_file(self, index: int):
        """删除指定索引的图片。"""
        if 0 <= index < len(self.selected_files):
            del self.selected_files[index]
            self.files_changed.emit(self.selected_files)
    
    def clear_files(self):
        """清空所有图片。"""
        self.selected_files = []
        self.files_changed.emit(self.selected_files)
    
    # ---- 输出配置 ----
    def set_output(self, path: str, override: bool):
        """设置输出路径和覆盖策略。"""
        self.output.path = path
        self.output.override = override
        self.output_changed.emit()
    
    # ---- 水印配置 ----
    def set_corner_config(self, corner: str, config: CornerConfig):
        """设置指定角的配置。"""
        if hasattr(self, corner):
            setattr(self, corner, config)
            self.watermark_changed.emit()
    
    def set_logo_config(self, config: LogoConfig):
        """设置 Logo 配置。"""
        self.logo = config
        self.watermark_changed.emit()
    
    def set_custom_text(self, text: str):
        """设置全局自定义文本。"""
        self.custom_text = text
        self.watermark_changed.emit()
    
    # ---- 高级设置 ----
    def set_advanced_config(self, config: AdvancedConfig):
        """设置高级配置。"""
        self.advanced = config
        self.advanced_changed.emit()
    
    # ---- 模板 ----
    def set_template(self, name: str):
        """切换模板。"""
        self.current_template = name
        self.template_changed.emit(name)
    
    # ---- 处理状态 ----
    def set_processing(self, is_processing: bool, progress: int = 0, status: str = ""):
        """更新处理状态。"""
        self.is_processing = is_processing
        self.progress = progress
        self.status_text = status if status else ("处理中..." if is_processing else "就绪")
        self.progress_changed.emit(progress, self.status_text)
    
    # ---- 持久化 ----
    def load_from_disk(self, project_root: Path) -> bool:
        """加载 user.json 配置。损坏时返回 False 并使用默认值。"""
        config_path = project_root / "config" / "user.json"
        try:
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # TODO: 从 data 还原状态
                logger.info("配置加载成功")
                return True
        except Exception as e:
            logger.warning(f"配置加载失败: {e}，使用默认值")
        self._reset_defaults()
        return False
    
    def save_to_disk(self, project_root: Path):
        """保存当前状态到 user.json。"""
        config_path = project_root / "config" / "user.json"
        try:
            data = {
                "template": self.current_template,
                "output": {
                    "path": self.output.path,
                    "override": self.output.override,
                },
                # TODO: 保存更多字段
            }
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info("配置保存成功")
        except Exception as e:
            logger.error(f"配置保存失败: {e}")
    
    def _reset_defaults(self):
        """重置为默认值。"""
        self.selected_files = []
        self.left_top = CornerConfig()
        self.left_bottom = CornerConfig()
        self.right_top = CornerConfig()
        self.right_bottom = CornerConfig()
        self.logo = LogoConfig()
        self.custom_text = ""
        self.advanced = AdvancedConfig()
        self.output = OutputConfig()
        self.current_template = "default"
        self.is_processing = False
        self.progress = 0
        self.status_text = "就绪"
    
    # ---- 模板验证 ----
    def validate_template(self, template_path: Path) -> Tuple[bool, str]:
        """验证模板 JSON 是否合法。"""
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                processors = json.load(f)
            for p in processors:
                if "processor_name" not in p:
                    return False, "模板缺少 processor_name"
            return True, ""
        except Exception as e:
            return False, str(e)
