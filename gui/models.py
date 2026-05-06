"""数据模型层 — AppState 统一状态管理。

Phase 6.1 / 6.2:
- ``save_to_disk`` / ``load_from_disk`` 全字段持久化（含 corners / logo / advanced / custom_text）
- 任意 ``*_changed`` 信号触发 300ms debounce 自动保存
- 向后兼容旧 ``user.json``（含 ``template`` 字段的旧版本会被忽略并丢弃）

Phase 15：模板系统已完全拆除。
- 移除 ``current_template`` 字段、``set_template()``、``template_changed`` 信号、``validate_template()``
- 新增 ``state_reloaded`` 信号取代原 ``template_changed`` 的"外部全量替换"广播语义
  （load_from_disk / reset_to_defaults / 任何外部一次性替换整组字段时发射）
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from dataclasses import fields as dc_fields
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

logger = logging.getLogger(__name__)


# Phase 6 user.json 版本号；老格式（无 version 字段）按 v1 兼容处理
USER_CONFIG_VERSION = 2

# 自动保存防抖窗口（毫秒）
AUTOSAVE_DEBOUNCE_MS = 300


@dataclass
class FieldChip:
    """单个字段 chip — Phase 6.3 数据模型。

    一个 chip 对应水印一行中的某一个字段（例如「相机型号」）。

    继承链（绘制时实际使用的 font/color）::

        chip.font / chip.color  ->  corner.font / corner.color  ->  global_font / global_color

    属性为空字符串时表示「继承上级」；非空表示「本 chip 自定义覆盖」。
    """

    field_id: str = "empty"          # FieldRegistry 中的英文 ID
    custom_text: str = ""             # 仅当 field_id == "custom_text" 时使用
    font: str = ""                    # 空 = 继承 corner.font
    color: str = ""                   # 空 = 继承 corner.color


@dataclass
class CornerConfig:
    """单角水印配置。

    Phase 6.3 数据模型升级：

    - 新增 ``chips``（``List[FieldChip]``）—— 推荐写法
    - 旧 ``fields``（``List[str]``）—— 仅作向后兼容；
      ``load_from_disk`` 会自动迁移成 ``chips``
    - ``font`` / ``color`` —— 升级为「角级」默认样式（覆盖全局）
    """

    chips: list[FieldChip] = field(default_factory=list)  # Phase 6.3 主数据
    fields: list[str] = field(default_factory=list)          # 旧兼容字段（中文标签）
    separator: str = " "                                      # 分隔符（默认空格）
    font: str = ""                                            # 空 = 继承 advanced.global_font
    color: str = ""                                           # 空 = 继承 advanced.global_color


@dataclass
class LogoConfig:
    """Logo 配置。"""
    enabled: str = "auto"       # auto / disabled / custom
    position: str = "right"     # right / center / left
    color: str = "#D8D8D6"      # 分隔线颜色（浅灰，参考标准水印模板）
    custom_path: str = ""       # 自定义路径


@dataclass
class AdvancedConfig:
    """高级设置配置。"""
    # 全局字体
    global_font: str = "NotoSansCJKsc-Regular.otf"
    global_color: str = "#242424"  # 深灰，与默认白底水印对比

    # Phase 11：固定像素尺寸（消除"按图片高度自适应"的不一致）。
    # 全部为 0 时回退到旧的比例自适应；非 0 时强制锁定像素，不论原图尺寸。
    corner_text_height_px: int = 0   # 角落文本图高度（不再随 bottom_margin*0.3 漂移）
    footer_height_px: int = 0        # 底部水印条高度（不再随 img.height*0.12 漂移）
    logo_height_px: int = 0          # 中央 logo 高度（不再撑满整条水印）

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


# ---- dataclass 序列化辅助 ----

def _dc_to_dict(obj: Any) -> dict[str, Any]:
    """安全地把 dataclass 转 dict（兼容嵌套字段）。"""
    return asdict(obj)


def _dc_from_dict(cls, data: dict[str, Any] | None):
    """从 dict 构造 dataclass，未知字段忽略，缺失字段用默认值。"""
    if not isinstance(data, dict):
        return cls()
    valid_keys = {f.name for f in dc_fields(cls)}
    filtered = {k: v for k, v in data.items() if k in valid_keys}
    try:
        return cls(**filtered)
    except (TypeError, ValueError) as e:
        logger.warning(f"还原 {cls.__name__} 失败 ({e})，使用默认值")
        return cls()


def _corner_from_dict(data: dict[str, Any] | None) -> CornerConfig:
    """从 dict 还原 :class:`CornerConfig`（含 ``chips`` 与旧 ``fields`` 双轨兼容）。

    迁移规则：

    - 若 dict 含 ``chips``：按新模型反序列化为 ``List[FieldChip]``
    - 若 dict 仅含 ``fields``（老 user.json）：把每个中文标签转成对应 ``FieldChip(field_id=...)``
    - ``font`` / ``color`` 缺失时为空字符串（含义：继承上级）
    """
    if not isinstance(data, dict):
        return CornerConfig()

    raw_chips = data.get("chips")
    chips: list[FieldChip] = []
    if isinstance(raw_chips, list):
        for c in raw_chips:
            if isinstance(c, dict):
                chips.append(_dc_from_dict(FieldChip, c))
    else:
        # 老 user.json：从中文标签 fields 列表迁移
        from gui.field_registry import get_default_registry  # 避免循环导入
        registry = get_default_registry()
        for label in data.get("fields", []) or []:
            if not isinstance(label, str):
                continue
            fdef = registry.get_by_label(label) or registry.resolve(label)
            chips.append(
                FieldChip(
                    field_id=fdef.field_id if fdef else "empty",
                    custom_text="",
                )
            )

    return CornerConfig(
        chips=chips,
        fields=list(data.get("fields", []) or []),  # 仍保留中文 fields，便于旧消费方读取
        separator=str(data.get("separator", " ")),
        font=str(data.get("font", "")),
        color=str(data.get("color", "")),
    )


def _corner_to_dict(corner: CornerConfig) -> dict[str, Any]:
    """把 :class:`CornerConfig` 转成可 JSON 序列化的 dict。"""
    return {
        "chips": [_dc_to_dict(c) for c in corner.chips],
        "fields": list(corner.fields),
        "separator": corner.separator,
        "font": corner.font,
        "color": corner.color,
    }


class AppState(QObject):
    """统一状态管理。Panel 通过信号订阅变更，禁止直接写字段。"""

    # 信号
    files_changed = pyqtSignal(list)            # 文件列表变更
    output_changed = pyqtSignal()               # 输出配置变更
    watermark_changed = pyqtSignal()            # 水印配置变更
    advanced_changed = pyqtSignal()             # 高级设置变更
    state_reloaded = pyqtSignal()               # 外部全量替换（load/reset/任何整组字段重置）
    progress_changed = pyqtSignal(int, str)     # 进度, 状态文字

    def __init__(self):
        super().__init__()

        # 文件列表
        self.selected_files: list[str] = []

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

        # 处理状态（不持久化）
        self.is_processing: bool = False
        self.progress: int = 0
        self.status_text: str = "就绪"

        # 自动保存（Phase 6.2）
        self._project_root: Path | None = None
        self._autosave_enabled: bool = False
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(AUTOSAVE_DEBOUNCE_MS)
        self._save_timer.timeout.connect(self._do_autosave)

        # 把所有数据类信号汇聚到 debounce 定时器
        # Phase 15：state_reloaded 是"全量替换"边沿信号，由 load/reset 主动触发；
        # 不挂 autosave 因为它本身代表"刚从磁盘读入"或"刚 reset 后立即写盘"，重复写盘多余。
        for sig in (
            self.files_changed,
            self.output_changed,
            self.watermark_changed,
            self.advanced_changed,
        ):
            sig.connect(self._schedule_autosave)

    # ---- 文件操作 ----
    def set_files(self, paths: list[str]):
        """**替换**整个文件列表（SSOT 写入入口）。

        与 :meth:`add_files` 的区别：``set_files`` 是 replace 语义；``add_files``
        是 append 语义。GUI 用户操作（如 thumb_grid 的 ``add_files`` 信号）应通过
        ``add_files``；外部全量替换（如配置加载、reset）应通过 ``set_files``。
        """
        self.selected_files = list(paths)
        self.files_changed.emit(self.selected_files)

    def add_files(self, paths: list[str]):
        """**追加**图片文件（用户增量操作）。"""
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

    # ---- 处理状态 ----
    def set_processing(self, is_processing: bool, progress: int = 0, status: str = ""):
        """切换处理边沿（START / 完成 / 取消）— 同时把进度归零或拉满。

        Phase 10.1 (P3)：与 :meth:`update_progress` 分离职责。
        - ``set_processing`` 只在"开始/结束/取消"三处被调用（边沿事件）
        - 中途的进度刷新走 :meth:`update_progress`，避免反复触发"is_processing=True"
        """
        self.is_processing = is_processing
        self.progress = progress
        self.status_text = status if status else ("处理中..." if is_processing else "就绪")
        self.progress_changed.emit(progress, self.status_text)

    def update_progress(self, progress: int, status: str = "") -> None:
        """处理过程中刷新进度 — 不改 ``is_processing``，仅 emit ``progress_changed``。

        Phase 10.1 (P3)：取代原先在 ``_on_thread_progress`` 里反复调
        ``set_processing(True, ...)`` 的反向竞争模式。
        """
        self.progress = progress
        if status:
            self.status_text = status
        self.progress_changed.emit(progress, self.status_text)

    # ---- 持久化 ----
    def load_from_disk(self, project_root: Path) -> bool:
        """加载 user.json 配置 — Phase 9：加载完成后发出全套 ``*_changed`` 信号让 GUI 同步。

        信号合规化设计要点：
        - 加载期间订阅者**已经连接**（调用方负责保证调用顺序）
        - ``_apply_loaded_data`` 末尾会 emit 4 个数据类信号 → 触发一次 autosave debounce
          但磁盘内容与内存相等，无副作用（除非 ``selected_files`` 被过滤过，那次写盘恰好把
          幽灵记录从磁盘清掉，这是期望行为）

        Returns:
            ``True`` 表示成功（含部分字段还原）；``False`` 表示文件缺失或损坏，已用默认值替代。
        """
        # 记录 project_root 以便后续 autosave
        self._project_root = project_root

        # Phase 9：先发全套同步信号让 GUI 完成首屏渲染，**再**开启 autosave。
        # 这样首屏 emit 不会触发 debounce 写盘（数据来自磁盘本身，无需立即写回）。

        config_path = project_root / "config" / "user.json"
        if not config_path.exists():
            logger.info("user.json 不存在，使用默认配置")
            self._reset_defaults()
            self._emit_full_refresh()
            self._autosave_enabled = True
            return False

        try:
            with open(config_path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"配置加载失败: {e}，使用默认值")
            self._reset_defaults()
            self._emit_full_refresh()
            self._autosave_enabled = True
            return False

        try:
            self._apply_loaded_data(data)
            logger.info("配置加载成功 (version=%s)", data.get("version", "legacy"))
            self._emit_full_refresh()
            self._autosave_enabled = True
            return True
        except Exception as e:
            logger.exception(f"配置应用失败: {e}，使用默认值")
            self._reset_defaults()
            self._emit_full_refresh()
            self._autosave_enabled = True
            return False

    def _emit_full_refresh(self) -> None:
        """发出全套数据类信号 — 用于"外部全量替换 AppState 字段"后通知所有 GUI 订阅者。

        顺序：files → output → watermark → advanced → state_reloaded
        （state_reloaded 放最后是因为它会触发 ConfigPanel 整树重建，应当在原子字段就位后再发）
        """
        self.files_changed.emit(self.selected_files)
        self.output_changed.emit()
        self.watermark_changed.emit()
        self.advanced_changed.emit()
        self.state_reloaded.emit()

    def _apply_loaded_data(self, data: dict[str, Any]) -> None:
        """把磁盘 dict 反序列化到 AppState 字段。

        Phase 15：旧版 user.json 里的 ``template`` 字段直接忽略（模板系统已移除）。
        """
        # 输出
        self.output = _dc_from_dict(OutputConfig, data.get("output"))

        # 文件列表 — Phase 13：不再持久化图像列表，每次启动都是空列表。
        # 旧版会保留 selected_files 并在启动时过滤不存在的路径；现已废弃该契约。
        # 即便磁盘里残留旧字段也忽略，确保会话边界干净。
        self.selected_files = []

        # 四角配置（含 Phase 6.3 chips 反序列化）
        corners = data.get("corners", {}) if isinstance(data.get("corners"), dict) else {}
        self.left_top = _corner_from_dict(corners.get("left_top"))
        self.left_bottom = _corner_from_dict(corners.get("left_bottom"))
        self.right_top = _corner_from_dict(corners.get("right_top"))
        self.right_bottom = _corner_from_dict(corners.get("right_bottom"))

        # Logo / 自定义文本 / 高级
        self.logo = _dc_from_dict(LogoConfig, data.get("logo"))
        self.custom_text = data.get("custom_text", "") or ""
        self.advanced = _dc_from_dict(AdvancedConfig, data.get("advanced"))

    def save_to_disk(self, project_root: Path | None = None) -> bool:
        """保存当前状态到 user.json。

        Args:
            project_root: 项目根目录；若不传，使用 ``load_from_disk`` 时记录的路径。

        Returns:
            是否写盘成功。
        """
        root = project_root or self._project_root
        if root is None:
            logger.warning("save_to_disk 未指定 project_root，跳过写盘")
            return False

        config_dir = root / "config"
        config_path = config_dir / "user.json"
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            # Phase 13：不持久化 selected_files —— 图像列表是会话级数据。
            # Phase 15：不持久化模板字段（模板系统已移除）。
            data: dict[str, Any] = {
                "version": USER_CONFIG_VERSION,
                "output": _dc_to_dict(self.output),
                "corners": {
                    "left_top": _corner_to_dict(self.left_top),
                    "left_bottom": _corner_to_dict(self.left_bottom),
                    "right_top": _corner_to_dict(self.right_top),
                    "right_bottom": _corner_to_dict(self.right_bottom),
                },
                "logo": _dc_to_dict(self.logo),
                "custom_text": self.custom_text,
                "advanced": _dc_to_dict(self.advanced),
            }
            # 原子写：先写 .tmp，再 rename，避免 crash 中途留残缺文件
            tmp_path = config_path.with_suffix(config_path.suffix + ".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            tmp_path.replace(config_path)
            logger.debug("配置保存成功: %s", config_path)
            return True
        except OSError as e:
            logger.error(f"配置保存失败: {e}")
            return False

    # ---- 自动保存（Phase 6.2） ----

    def _schedule_autosave(self, *_args, **_kwargs):
        """任何 *_changed 信号触发；在 debounce 窗口内重启计时器。"""
        if not self._autosave_enabled or self._project_root is None:
            return
        # 处理状态变化期间不写盘（避免 ProcessThread 频繁触发）
        if self.is_processing:
            return
        self._save_timer.start()

    def _do_autosave(self) -> None:
        """debounce 触发后的真正写盘。"""
        if self._project_root is None:
            return
        ok = self.save_to_disk(self._project_root)
        if ok:
            logger.debug("自动保存完成")

    def flush_autosave(self) -> bool:
        """立即同步写盘（如关闭窗口前调用）。"""
        # 如果计时器还在等待，强制取消并立即写
        if self._save_timer.isActive():
            self._save_timer.stop()
        return self.save_to_disk(self._project_root) if self._project_root else False

    def _reset_defaults(self):
        """重置为默认值（不发信号，仅用于初始化）。"""
        self.selected_files = []
        self.left_top = CornerConfig()
        self.left_bottom = CornerConfig()
        self.right_top = CornerConfig()
        self.right_bottom = CornerConfig()
        self.logo = LogoConfig()
        self.custom_text = ""
        self.advanced = AdvancedConfig()
        self.output = OutputConfig()
        self.is_processing = False
        self.progress = 0
        self.status_text = "就绪"

    def reset_to_defaults(self) -> None:
        """Phase 6.10：用户主动恢复默认 — 重置后发出全部 *_changed 信号让 GUI 刷新。

        Phase 9：复用 :meth:`_emit_full_refresh` 统一信号契约。
        """
        self._reset_defaults()
        self._emit_full_refresh()
        # 持久化（用户操作 → 立即同步）
        if self._project_root is not None:
            try:
                self.save_to_disk(self._project_root)
            except Exception as e:
                logger.warning("reset_to_defaults 保存失败: %s", e)
