#!/usr/bin/env python3
"""aka-semi-utils 极简水印 GUI — 按 DESIGN.md 实现。"""

import logging
import os
import platform
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

# 确保项目根目录在路径中
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.config_loader import (
    USER_TEMPLATE_PATH,
    create_default_user_template,
    get_logo_path,
    get_output_folder,
    get_supported_suffixes,
    load_config_ini,
    load_user_template,
    save_config_ini,
    save_user_template,
)
from core.font_manager import font_preview_tk_image, list_fonts
from core.template_builder import build_watermark_processor, render_processors
from core.util import get_exif
from processor.core import start_process

logger = logging.getLogger(__name__)

# ── 系统主题检测 ──
def _is_dark_mode() -> bool:
    """检测系统是否处于暗黑模式。支持 macOS 和 Windows。"""
    system = platform.system()
    if system == "Darwin":
        try:
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, timeout=2,
            )
            return result.stdout.strip().lower() == "dark"
        except Exception:
            return False
    elif system == "Windows":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return value == 0
        except Exception:
            return False
    # Linux / 其他：尝试通过 tkinter 默认背景色推断
    try:
        root = tk.Tk()
        bg = root.cget("bg")
        root.destroy()
        # 如果默认背景色偏暗（RGB 平均值 < 128），视为暗黑模式
        if bg.startswith("#") and len(bg) == 7:
            r, g, b = int(bg[1:3], 16), int(bg[3:5], 16), int(bg[5:7], 16)
            return (r + g + b) / 3 < 128
    except Exception:
        pass
    return False

_IS_DARK = _is_dark_mode()

# 颜色常量（根据系统主题自动切换）
# 构成主义暗色调配色（强制暗色，无视系统主题）
_BG = "#1A1A1A"          # 主背景 — 深黑灰
_FG_PRIMARY = "#E0E0E0"  # 主文字 / 强调元素 — 浅灰（非纯白，避免刺眼）
_FG_SECONDARY = "#999999"  # 次要文字 — 中灰
_BG_SURFACE = "#252525"  # 卡片/区域背景 — 深灰
_BORDER = "#404040"      # 边框灰
_BORDER_STRONG = "#E0E0E0"  # 强边框 — 浅灰
_PROGRESS_BG = "#333333"  # 进度条背景 — 深灰
_ACCENT = "#E0E0E0"      # 强调色

# ── 常量 ──
WINDOW_W, WINDOW_H = 500, 620
SOURCE_OPTIONS = [
    ("相机型号", "exif:CameraModelName"),
    ("镜头型号", "exif:LensModel"),
    ("拍摄参数", "exif:params"),
    ("拍摄日期", "exif:DateTimeOriginal"),
    ("厂商品牌", "exif:Make"),
    ("地理位置", "exif:GPSInfo"),
    ("自定义文本", "custom"),
    ("空", "empty"),
]
SOURCE_LABEL_MAP = {v: k for k, v in SOURCE_OPTIONS}
CORNERS = ("left_top", "left_bottom", "right_top", "right_bottom")


class SimpleWatermarkGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("aka-semi-utils 极简水印")
        self.root.geometry(f"{WINDOW_W}x{WINDOW_H}")
        self.root.resizable(False, False)

        # 配置
        self.config_ini = load_config_ini()
        self.user_template = load_user_template()

        # 状态
        self.selected_paths: list[str] = []
        self.preview_images: dict[str, ImageTk.PhotoImage] = {}  # 防止 GC
        self.failed_files: list[tuple[str, str]] = []  # 累积处理失败的文件

        # ── UI 构建 ──
        self._build_ui()
        self._refresh_output_path()

    # ──────────────────────────────
    #  UI 构建
    # ──────────────────────────────
    def _build_ui(self):
        """构成主义极简主界面：暗色调灰/深灰/偏黑，扁平化，几何分割。"""
        self.root.configure(bg=_BG)

        # ── 顶部工具栏 ──
        toolbar = tk.Frame(self.root, bg=_FG_PRIMARY, height=44)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)
        tk.Label(
            toolbar, text="aka-semi-utils", bg=_FG_PRIMARY, fg=_BG,
            font=("System", 14, "bold")
        ).pack(side=tk.LEFT, padx=16, pady=0)

        # 配置按钮（Frame 模拟以获得精确样式控制）
        cfg_btn = tk.Frame(toolbar, bg=_FG_PRIMARY, width=60, height=28)
        cfg_btn.pack(side=tk.RIGHT, padx=(0, 12), pady=8)
        cfg_btn.pack_propagate(False)
        cfg_lbl = tk.Label(
            cfg_btn, text="配置", bg=_FG_PRIMARY, fg=_BG,
            font=("System", 11)
        )
        cfg_lbl.place(relx=0.5, rely=0.5, anchor="center")
        for w in (cfg_btn, cfg_lbl):
            w.bind("<Button-1>", lambda e: self._open_config_panel())
        # hover 效果（暗色调：白底→深灰底，黑字→白字）
        def _cfg_enter(e):
            cfg_btn.config(bg="#333333")
            cfg_lbl.config(bg="#333333", fg=_FG_PRIMARY)
        def _cfg_leave(e):
            cfg_btn.config(bg=_FG_PRIMARY)
            cfg_lbl.config(bg=_FG_PRIMARY, fg=_BG)
        for w in (cfg_btn, cfg_lbl):
            w.bind("<Enter>", _cfg_enter)
            w.bind("<Leave>", _cfg_leave)

        # ── 图片选择区 ──
        self.drop_frame = tk.Frame(
            self.root, bg=_BG_SURFACE, width=460, height=160,
            highlightbackground=_BORDER_STRONG, highlightthickness=2,
        )
        self.drop_frame.pack(padx=20, pady=(20, 12))
        self.drop_frame.pack_propagate(False)

        self.drop_label = tk.Label(
            self.drop_frame,
            text="选择图片文件\n支持 JPG / PNG / HEIC",
            bg=_BG_SURFACE, fg=_FG_SECONDARY,
            font=("System", 13), justify="center"
        )
        self.drop_label.place(relx=0.5, rely=0.5, anchor="center")
        for w in (self.drop_frame, self.drop_label):
            w.bind("<Button-1>", lambda e: self._select_files())

        # ── 输出路径 ──
        path_row = tk.Frame(self.root, bg=_BG)
        path_row.pack(fill=tk.X, padx=20, pady=8)
        tk.Label(path_row, text="输出路径", bg=_BG, fg=_FG_PRIMARY,
                 font=("System", 11)).pack(side=tk.LEFT)

        self.output_entry = tk.Entry(
            path_row, width=30, bg=_BG, fg=_FG_PRIMARY,
            insertbackground=_FG_PRIMARY, relief=tk.FLAT,
            highlightbackground=_BORDER, highlightthickness=1,
            font=("System", 11)
        )
        self.output_entry.pack(side=tk.LEFT, padx=(12, 8), ipady=3)

        # 浏览按钮（Frame 模拟）
        browse_btn = tk.Frame(path_row, bg=_BG_SURFACE, width=56, height=26,
                             highlightbackground=_BORDER, highlightthickness=1)
        browse_btn.pack(side=tk.LEFT)
        browse_btn.pack_propagate(False)
        browse_lbl = tk.Label(
            browse_btn, text="浏览", bg=_BG_SURFACE, fg=_FG_PRIMARY,
            font=("System", 10)
        )
        browse_lbl.place(relx=0.5, rely=0.5, anchor="center")
        for w in (browse_btn, browse_lbl):
            w.bind("<Button-1>", lambda e: self._browse_output())
        def _br_enter(e):
            browse_btn.config(bg="#333333")
            browse_lbl.config(bg="#333333")
        def _br_leave(e):
            browse_btn.config(bg=_BG_SURFACE)
            browse_lbl.config(bg=_BG_SURFACE)
        for w in (browse_btn, browse_lbl):
            w.bind("<Enter>", _br_enter)
            w.bind("<Leave>", _br_leave)

        # ── 选项行：覆盖勾选 + 文件计数 ──
        opts_row = tk.Frame(self.root, bg=_BG)
        opts_row.pack(fill=tk.X, padx=20, pady=(4, 0))

        self.override_var = tk.BooleanVar(
            value=self.config_ini.getboolean("DEFAULT", "override_existed", fallback=True)
        )
        self.override_chk = tk.Checkbutton(
            opts_row, text="同名文件直接覆盖", variable=self.override_var,
            bg=_BG, fg=_FG_PRIMARY, selectcolor=_BG,
            activebackground=_BG, activeforeground=_FG_PRIMARY,
            font=("System", 11)
        )
        self.override_chk.pack(side=tk.LEFT)

        self.count_label = tk.Label(
            opts_row, text="已选择 0 张", bg=_BG, fg=_FG_SECONDARY,
            font=("System", 11)
        )
        self.count_label.pack(side=tk.RIGHT)

        # ── 进度条 ──
        self.progress = ttk.Progressbar(
            self.root, length=460, mode="determinate",
            maximum=100
        )
        # 进度条样式（ttk style）
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "BW.Horizontal.TProgressbar",
            troughcolor=_PROGRESS_BG,
            background=_FG_PRIMARY,
            borderwidth=0,
            lightcolor=_FG_PRIMARY,
            darkcolor=_FG_PRIMARY,
        )
        self.progress.configure(style="BW.Horizontal.TProgressbar")
        self.progress.pack(padx=20, pady=(16, 4))

        # ── 状态文字 ──
        self.status_label = tk.Label(
            self.root, text="就绪", bg=_BG, fg=_FG_SECONDARY,
            font=("System", 11)
        )
        self.status_label.pack(pady=(0, 12))

        # ── 开始按钮（全宽白色，暗色中的亮点）──
        self.start_frame = tk.Frame(
            self.root, bg=_FG_PRIMARY, height=48,
            highlightbackground=_FG_PRIMARY, highlightthickness=0
        )
        self.start_frame.pack(fill=tk.X, padx=20, pady=(8, 20))
        self.start_frame.pack_propagate(False)

        self.start_label = tk.Label(
            self.start_frame, text="S T A R T", bg=_FG_PRIMARY, fg=_BG,
            font=("System", 14, "bold")
        )
        self.start_label.place(relx=0.5, rely=0.5, anchor="center")

        for w in (self.start_frame, self.start_label):
            w.bind("<Button-1>", lambda e: self._on_start())

        # hover 反色（暗色调：白底黑字 → 深灰底白字+白边框）
        def _start_enter(e):
            self.start_frame.config(bg=_BG, highlightbackground=_FG_PRIMARY, highlightthickness=2)
            self.start_label.config(bg=_BG, fg=_FG_PRIMARY)
        def _start_leave(e):
            self.start_frame.config(bg=_FG_PRIMARY, highlightthickness=0)
            self.start_label.config(bg=_FG_PRIMARY, fg=_BG)
        for w in (self.start_frame, self.start_label):
            w.bind("<Enter>", _start_enter)
            w.bind("<Leave>", _start_leave)

    # ──────────────────────────────
    #  图片选择
    # ──────────────────────────────
    def _select_files(self):
        filetypes = [
            ("图片文件", "*.jpg *.jpeg *.png *.heic *.JPG *.JPEG *.PNG *.HEIC"),
            ("所有文件", "*.*"),
        ]
        paths = filedialog.askopenfilenames(title="选择图片文件（可多选）", filetypes=filetypes)
        if not paths:
            return
        self.selected_paths = list(paths)
        self.count_label.config(text=f"已选择: {len(self.selected_paths)} 张")
        self.status_label.config(text=f"已加载 {len(self.selected_paths)} 张图片")
        self._refresh_output_path()

    def _browse_output(self):
        folder = filedialog.askdirectory(title="选择输出文件夹")
        if folder:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, folder)
            self.config_ini.set("DEFAULT", "output_folder", folder)
            self.config_ini.set("DEFAULT", "remember_output", "True")
            save_config_ini(self.config_ini)

    def _refresh_output_path(self):
        if self.selected_paths:
            src_dir = Path(self.selected_paths[0]).parent
        else:
            src_dir = Path.home() / "Desktop"
        out = get_output_folder(self.config_ini, src_dir)
        self.output_entry.delete(0, tk.END)
        self.output_entry.insert(0, str(out))

    # ──────────────────────────────
    #  配置面板
    # ──────────────────────────────
    def _open_config_panel(self):
        if hasattr(self, "config_win") and self.config_win.winfo_exists():
            self.config_win.lift()
            return

        # 每次打开时重新加载最新配置
        self.config_ini = load_config_ini()
        self.user_template = load_user_template()

        self.config_win = tk.Toplevel(self.root)
        self.config_win.title("水印布局配置")
        self.config_win.geometry("520x780")
        self.config_win.resizable(False, False)

        # macOS 暗黑模式适配
        style = ttk.Style(self.config_win)
        style.configure("TCombobox", foreground=_FG_PRIMARY)
        style.configure("TCombobox", fieldbackground=_BG)
        style.configure("TCombobox", selectbackground=_BG_SURFACE)
        style.configure("TCombobox", selectforeground=_FG_PRIMARY)

        layout = self.user_template.get("layout", {})
        fonts = list_fonts()

        # ── 四角多字段叠加配置（简化版：每行一个下拉框 + 删除按钮）──
        self.corner_sources: dict[str, list[str]] = {}  # corner -> list of source values
        self.corner_rows: dict[str, list[tk.Widget]] = {}  # corner -> list of row frames for cleanup

        for corner in CORNERS:
            cfg = layout.get(corner, {})
            old_source = cfg.get("source", "empty")
            sources = cfg.get("sources", [old_source] if old_source else [])
            if not sources:
                sources = ["empty"]
            self.corner_sources[corner] = sources

            frame = tk.LabelFrame(self.config_win, text=corner.replace("_", " ").title())
            frame.pack(fill=tk.X, padx=12, pady=4)

            # 字段列表容器
            list_container = tk.Frame(frame)
            list_container.pack(fill=tk.X, padx=4, pady=2)
            setattr(self, f"_{corner}_container", list_container)

            # 渲染现有字段行
            self.corner_rows[corner] = []
            total = len(sources)
            for idx, src in enumerate(sources):
                self._build_corner_row(corner, list_container, idx, src, total)

            # 分隔符 + 添加按钮
            ctrl_frame = tk.Frame(frame)
            ctrl_frame.pack(fill=tk.X, padx=4, pady=(0, 4))

            tk.Label(ctrl_frame, text="分隔符:").pack(side=tk.LEFT)
            sep_var = tk.StringVar(value=cfg.get("separator", ""))
            tk.Entry(ctrl_frame, textvariable=sep_var, width=8, fg=_FG_PRIMARY, insertbackground=_FG_PRIMARY).pack(side=tk.LEFT, padx=4)
            setattr(self, f"_{corner}_sep_var", sep_var)

            tk.Button(ctrl_frame, text="+ 添加字段", command=lambda c=corner: self._add_corner_source(c)).pack(side=tk.RIGHT)

        # ── 签名叠加（暂停开发，后续版本恢复）──
        # TODO: 签名功能已暂停，相关代码保留在 git 历史或 memory 中
        # 如需恢复，取消注释以下区块并重新启用 _save_config 和 _process_thread 中的签名逻辑

        # Logo
        logo_frame = tk.LabelFrame(self.config_win, text="Logo")
        logo_frame.pack(fill=tk.X, padx=12, pady=4)
        self.logo_var = tk.StringVar()
        logo_options = ["自动匹配 (auto_logo)", "不使用 Logo"]
        logo_files = sorted([f.name for f in (PROJECT_ROOT / "config" / "logos").glob("*.png")])
        logo_options.extend(logo_files)
        custom_logo = self.config_ini.get("DEFAULT", "logo_path", fallback="").strip()
        if custom_logo and custom_logo not in logo_options:
            logo_options.append(custom_logo)
        logo_cfg = self.user_template.get("logo", {})
        if logo_cfg.get("enabled", True):
            src = logo_cfg.get("source", "auto")
            if src == "auto":
                self.logo_var.set("自动匹配 (auto_logo)")
            elif Path(src).name in logo_files:
                self.logo_var.set(Path(src).name)
            elif custom_logo:
                self.logo_var.set(custom_logo)
            else:
                self.logo_var.set("自动匹配 (auto_logo)")
        else:
            self.logo_var.set("不使用 Logo")
        ttk.Combobox(logo_frame, values=logo_options, textvariable=self.logo_var, state="readonly", width=24, foreground=_FG_PRIMARY).pack(side=tk.LEFT, padx=4, pady=2)
        tk.Button(logo_frame, text="浏览...", command=self._browse_logo).pack(side=tk.LEFT, padx=4)
        ttk.Button(logo_frame, text="配置品牌替换...", command=self._open_logo_config_panel).pack(side=tk.LEFT, padx=4)

        # 自定义文本（全局）
        custom_frame = tk.LabelFrame(self.config_win, text="自定义文本（四角选择「自定义文本」时统一使用此内容）")
        custom_frame.pack(fill=tk.X, padx=12, pady=4)
        self.global_custom_text_var = tk.StringVar(value=self.config_ini.get("custom_text", "text", fallback=""))
        tk.Entry(custom_frame, textvariable=self.global_custom_text_var, width=40, fg=_FG_PRIMARY, insertbackground=_FG_PRIMARY).pack(side=tk.LEFT, padx=4, pady=2)

        # 同名文件处理策略 — 已移至主窗口
        # override_frame = tk.Frame(self.config_win)
        # override_frame.pack(fill=tk.X, padx=12, pady=(4, 0))
        # self.override_var = tk.BooleanVar(value=self.config_ini.getboolean("DEFAULT", "override_existed", fallback=True))
        # tk.Checkbutton(
        #     override_frame,
        #     text="同名文件直接覆盖（不勾选则跳过）",
        #     variable=self.override_var,
        #     fg=_FG_PRIMARY,
        #     selectcolor=_BG if _IS_DARK else "white",
        # ).pack(side=tk.LEFT)

        # 按钮区
        btn_frame = tk.Frame(self.config_win)
        btn_frame.pack(pady=12)
        ttk.Button(btn_frame, text="保存配置", command=self._save_config).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_frame, text="取消", command=self.config_win.destroy).pack(side=tk.LEFT, padx=8)



    def _update_preview(self, label: tk.Label, font_name: str, text: str = ""):
        """生成字体预览图，文字优先使用传入的 text，否则回退到默认。"""
        display_text = text.strip() if text else "字体预览"
        try:
            img = font_preview_tk_image(font_name, text=display_text, master=self.root)
            self.preview_images[font_name] = img  # 保持引用
            label.config(image=img)
        except Exception as e:
            logger.warning(f"预览生成失败: {e}")
            label.config(image="")

    def _browse_logo(self):
        path = filedialog.askopenfilename(title="选择 Logo 图片", filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg;*.jpeg")])
        if path:
            self.logo_var.set(path)

    def _browse_signature(self):
        """选择签名 PNG 图片。"""
        path = filedialog.askopenfilename(
            title="选择签名图片（透明背景 PNG）",
            filetypes=[("PNG", "*.png")],
        )
        if not path:
            logger.info("用户取消选择签名图片")
            return
        # 复制到 config/signatures/ 并生成黑白缓存
        sig_dir = PROJECT_ROOT / "config" / "signatures"
        sig_dir.mkdir(parents=True, exist_ok=True)
        dest = sig_dir / "user_signature.png"
        import shutil
        shutil.copy(path, dest)
        self.sig_path_var.set(str(dest))
        logger.info(f"签名图片已复制到: {dest}")
        # 自动生成黑白两个版本
        try:
            self._generate_signature_cache(dest)
            messagebox.showinfo("成功", "签名图片已加载，自动生成黑白缓存")
        except Exception as e:
            logger.error(f"签名缓存生成失败: {e}")
            messagebox.showerror("失败", f"签名缓存生成失败: {e}")

    def _generate_signature_cache(self, source_path: Path):
        """以 Alpha 为 mask 生成黑白两个版本的签名缓存。"""
        from PIL import Image
        logger.info(f"生成签名缓存: {source_path}")
        img = Image.open(source_path).convert('RGBA')
        r, g, b, a = img.split()
        cache_dir = source_path.parent
        # 黑字版
        black = Image.new('L', img.size, 0)
        Image.merge('RGBA', (black, black, black, a)).save(cache_dir / "user_signature_black.png")
        # 白字版
        white = Image.new('L', img.size, 255)
        Image.merge('RGBA', (white, white, white, a)).save(cache_dir / "user_signature_white.png")
        logger.info(f"签名缓存生成完成: black={cache_dir / 'user_signature_black.png'}, white={cache_dir / 'user_signature_white.png'}")

    def _build_corner_row(self, corner: str, container: tk.Widget, idx: int, source: str, total: int):
        """为指定角构建一行字段选择（横向排列：下拉框 + 删除按钮）。"""
        row = tk.Frame(container)
        row.pack(side=tk.LEFT, padx=2, pady=1)

        # 分隔符标签（除了第一个字段）
        if idx > 0:
            sep_var = getattr(self, f"_{corner}_sep_var", None)
            if sep_var:
                raw = sep_var.get().strip()
            else:
                # 首次渲染时 sep_var 尚未创建，从 template 读取
                raw = self.user_template.get("layout", {}).get(corner, {}).get("separator", "")
            display = "  " if not raw else f" {raw} "
            tk.Label(row, text=display, fg=_FG_PRIMARY).pack(side=tk.LEFT, padx=1)

        label_text = SOURCE_LABEL_MAP.get(source, "空")
        combo = ttk.Combobox(row, values=[opt[0] for opt in SOURCE_OPTIONS], state="readonly", width=7, foreground=_FG_PRIMARY)
        combo.pack(side=tk.LEFT)
        combo.set(label_text)

        # 删除按钮：贴紧下拉框右侧，宽高1:1（width=1 字符单位，近似正方形）
        tk.Button(row, text="×", width=1, height=1, command=lambda c=corner, r=row: self._remove_corner_row(c, r)).pack(side=tk.LEFT, padx=(0, 0))

        # 记录引用
        if corner not in self.corner_rows:
            self.corner_rows[corner] = []
        self.corner_rows[corner].append((row, combo))

    def _get_corner_sources(self, corner: str) -> list[str]:
        """从 UI 控件读取指定角的当前 source 值列表。"""
        sources = []
        for _, combo in self.corner_rows.get(corner, []):
            label = combo.get()  # 直接读取 Combobox 当前显示值
            source_val = "empty"
            for lab, val in SOURCE_OPTIONS:
                if lab == label:
                    source_val = val
                    break
            sources.append(source_val)
        return sources

    def _refresh_corner_rows(self, corner: str):
        """重新渲染指定角的所有行（横向排列）。"""
        container = getattr(self, f"_{corner}_container")
        # 清空现有行
        for row, _ in self.corner_rows.get(corner, []):
            row.destroy()
        self.corner_rows[corner] = []
        # 重新渲染（横向排列）
        total = len(self.corner_sources[corner])
        for idx, src in enumerate(self.corner_sources[corner]):
            self._build_corner_row(corner, container, idx, src, total)

    def _add_corner_source(self, corner: str):
        """为指定角添加一个默认字段到末尾。"""
        self.corner_sources[corner].append("empty")
        self._refresh_corner_rows(corner)

    def _remove_corner_row(self, corner: str, row: tk.Widget):
        """删除指定行。"""
        rows = self.corner_rows.get(corner, [])
        for i, (r, _) in enumerate(rows):
            if r == row:
                del self.corner_sources[corner][i]
                break
        self._refresh_corner_rows(corner)

    def _save_config(self):
        """保存配置到 config.ini 和 user.json。"""
        try:
            # 更新 user.json layout（多字段叠加）
            layout = {}
            for corner in CORNERS:
                sources = self._get_corner_sources(corner)
                sep_var = getattr(self, f"_{corner}_sep_var", None)
                separator = sep_var.get() if sep_var else " · "
                layout[corner] = {
                    "sources": sources,
                    "separator": separator,
                    "font": "NotoSansCJKsc-Bold.otf",  # 强制统一
                    "color": self.user_template.get("layout", {}).get(corner, {}).get("color", "#242424"),
                }

            self.user_template["layout"] = layout

            # Logo
            logo_sel = self.logo_var.get()
            if logo_sel == "不使用 Logo":
                self.user_template["logo"] = {"enabled": False, "source": "auto", "position": "right", "delimiter_color": "#D8D8D6"}
            elif logo_sel == "自动匹配 (auto_logo)":
                self.user_template["logo"] = {"enabled": True, "source": "auto", "position": "right", "delimiter_color": "#D8D8D6"}
                self.config_ini.set("DEFAULT", "logo_path", "")
            else:
                logo_full = PROJECT_ROOT / "config" / "logos" / logo_sel
                self.user_template["logo"] = {"enabled": True, "source": str(logo_full), "position": "right", "delimiter_color": "#D8D8D6"}
                if logo_full.exists():
                    self.config_ini.set("DEFAULT", "logo_path", str(logo_full))

            # 签名功能暂停开发，不保存签名配置
            # sig_enabled = self.sig_enabled_var.get()
            # self.config_ini.set("DEFAULT", "signature_enabled", str(sig_enabled))
            # self.config_ini.set("DEFAULT", "signature_path", self.sig_path_var.get().strip())
            # self.config_ini.set("DEFAULT", "signature_color", self.sig_color_var.get())

            # 自定义文本（全局）
            if not self.config_ini.has_section("custom_text"):
                self.config_ini.add_section("custom_text")
            self.config_ini.set("custom_text", "text", self.global_custom_text_var.get().strip())
            # 兼容旧版：同时设置四个角的值
            for corner in CORNERS:
                self.config_ini.set("custom_text", corner, self.global_custom_text_var.get().strip())

                # 同名文件策略
            self.config_ini.set("DEFAULT", "override_existed", str(self.override_var.get()))

            # 保存
            save_user_template(self.user_template)
            save_config_ini(self.config_ini)
            logger.info("配置保存成功")
            messagebox.showinfo("保存成功", "配置已保存")
            self.config_win.destroy()

        except Exception as e:
            logger.exception("保存配置失败")
            messagebox.showerror("保存失败", str(e))

    def _open_logo_config_panel(self):
        """打开 Logo 品牌替换配置面板。"""
        if hasattr(self, "logo_config_win") and self.logo_config_win.winfo_exists():
            self.logo_config_win.lift()
            return

        self.logo_config_win = tk.Toplevel(self.root)
        self.logo_config_win.title("Logo 品牌替换配置")
        self.logo_config_win.geometry("480x400")
        self.logo_config_win.resizable(False, False)

        # 扫描默认品牌
        default_dir = PROJECT_ROOT / "config" / "logos"
        custom_dir = default_dir / "custom"
        custom_dir.mkdir(parents=True, exist_ok=True)

        # 提取品牌名（去掉 .png）
        default_brands = {f.stem.lower() for f in default_dir.glob("*.png") if f.parent == default_dir}
        custom_brands = {f.stem.lower() for f in custom_dir.glob("*.png")}
        all_brands = sorted(default_brands | custom_brands)

        if not all_brands:
            tk.Label(self.logo_config_win, text="未找到品牌 Logo").pack(pady=20)
            return

        # 品牌列表
        list_frame = tk.Frame(self.logo_config_win)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        # 表头
        header = tk.Frame(list_frame)
        header.pack(fill=tk.X)
        tk.Label(header, text="品牌", width=15, anchor="w").pack(side=tk.LEFT)
        tk.Label(header, text="状态", width=12, anchor="w").pack(side=tk.LEFT)
        tk.Label(header, text="操作", width=20, anchor="w").pack(side=tk.LEFT)

        for brand in all_brands:
            row = tk.Frame(list_frame)
            row.pack(fill=tk.X, pady=2)
            has_custom = brand in custom_brands
            status = "已替换" if has_custom else "默认"
            tk.Label(row, text=brand.title(), width=15, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=status, width=12, anchor="w").pack(side=tk.LEFT)
            if has_custom:
                tk.Button(row, text="恢复默认", command=lambda b=brand: self._restore_default_logo(b)).pack(side=tk.LEFT, padx=2)
            tk.Button(row, text="替换 Logo...", command=lambda b=brand: self._replace_brand_logo(b)).pack(side=tk.LEFT, padx=2)

        ttk.Button(self.logo_config_win, text="关闭", command=self.logo_config_win.destroy).pack(pady=8)

    def _overlay_signature(self, base_img: Image.Image) -> Image.Image:
        """在原图底部居中叠加签名图。"""
        sig_path_str = self.config_ini.get("DEFAULT", "signature_path", fallback="").strip()
        sig_color = self.config_ini.get("DEFAULT", "signature_color", fallback="black")
        logger.info(f"签名叠加开始: enabled=True, path={sig_path_str}, color={sig_color}")
        if not sig_path_str:
            logger.warning("签名路径为空，跳过叠加")
            return base_img
        sig_path = Path(sig_path_str)
        cache_dir = sig_path.parent
        # 使用对应颜色的缓存版本
        cache_path = cache_dir / f"user_signature_{sig_color}.png"
        if not cache_path.exists():
            logger.warning(f"签名缓存不存在: {cache_path}，尝试重新生成")
            if sig_path.exists():
                self._generate_signature_cache(sig_path)
            if not cache_path.exists():
                logger.error(f"签名缓存仍然不存在: {cache_path}，跳过叠加")
                return base_img
        try:
            sig = Image.open(cache_path).convert('RGBA')
            # 签名高度为原图的 4%
            sig_height = int(base_img.height * 0.04)
            sig_width = int(sig.width * (sig_height / sig.height))
            sig = sig.resize((sig_width, sig_height), Image.Resampling.LANCZOS)
            # 底部居中：水平居中，距离底部 5%
            x = (base_img.width - sig_width) // 2
            y = int(base_img.height * 0.95) - sig_height
            logger.info(f"签名叠加位置: x={x}, y={y}, size=({sig_width}x{sig_height})")
            base_img = base_img.convert('RGBA')
            base_img.paste(sig, (x, y), mask=sig)
            logger.info("签名叠加完成")
            return base_img.convert('RGB')
        except Exception as e:
            logger.error(f"签名叠加失败: {e}")
            return base_img

    def _replace_brand_logo(self, brand: str):
        """用户选择图片替换指定品牌的 Logo。"""
        path = filedialog.askopenfilename(
            title=f"选择 {brand.title()} 的 Logo 图片",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg;*.jpeg")],
        )
        if not path:
            return
        custom_dir = PROJECT_ROOT / "config" / "logos" / "custom"
        custom_dir.mkdir(parents=True, exist_ok=True)
        dest = custom_dir / f"{brand}.png"
        try:
            import shutil
            shutil.copy(path, dest)
            messagebox.showinfo("成功", f"已替换 {brand.title()} 的 Logo")
            self.logo_config_win.destroy()
            self._open_logo_config_panel()
        except Exception as e:
            messagebox.showerror("失败", str(e))

    def _restore_default_logo(self, brand: str):
        """删除自定义 Logo，恢复默认。"""
        custom_path = PROJECT_ROOT / "config" / "logos" / "custom" / f"{brand}.png"
        if custom_path.exists():
            try:
                custom_path.unlink()
                messagebox.showinfo("成功", f"已恢复 {brand.title()} 的默认 Logo")
                self.logo_config_win.destroy()
                self._open_logo_config_panel()
            except Exception as e:
                messagebox.showerror("失败", str(e))

    # ──────────────────────────────
    #  处理逻辑
    # ──────────────────────────────
    def _on_start(self):
        if not self.selected_paths:
            messagebox.showwarning("提示", "请先选择图片")
            return

        # 同步主窗口选项到配置
        self.config_ini.set("DEFAULT", "override_existed", str(self.override_var.get()))

        self.start_label.config(text="处理中...")
        self.progress.config(value=0)
        self.status_label.config(text="准备处理...")

        thread = threading.Thread(target=self._process_thread, daemon=True)
        thread.start()

    def _process_thread(self):
        self.failed_files = []
        try:
            total = len(self.selected_paths)
            processors_template = build_watermark_processor(self.user_template, self.config_ini)

            for idx, path in enumerate(self.selected_paths):
                try:
                    exif = get_exif(path)
                    src_dir = Path(path).parent
                    out_dir = get_output_folder(self.config_ini, src_dir)
                    out_dir.mkdir(parents=True, exist_ok=True)

                    # 检查是否已存在（跳过）
                    out_path = out_dir / Path(path).name
                    override = self.config_ini.getboolean("DEFAULT", "override_existed", fallback=False)
                    if out_path.exists() and not override:
                        logger.info(f"跳过已存在: {out_path}")
                        self.root.after(0, lambda i=idx, t=total, name=Path(path).name: self._update_progress(i + 1, t, f"跳过 {name}"))
                        continue

                    # 渲染处理器
                    processors = render_processors(processors_template, exif, path)

                    # 执行处理
                    start_process(processors, input_path=path, output_path=str(out_path))

                    self.root.after(0, lambda i=idx, t=total, name=Path(path).name: self._update_progress(i + 1, t, f"完成 {name}"))

                except Exception as e:
                    err_msg = str(e)
                    logger.error(f"处理失败 {path}: {err_msg}")
                    self.failed_files.append((path, err_msg))
                    self.root.after(0, lambda p=path, err=err_msg: self._handle_file_error(p, err))

            self.root.after(0, lambda: self._finish_processing())

        except Exception as e:
            self.root.after(0, lambda err=e: self._handle_fatal_error(err))

    def _update_progress(self, current: int, total: int, msg: str):
        pct = int(current / total * 100)
        self.progress.config(value=pct)
        self.status_label.config(text=f"{current}/{total} — {msg}")
        self.root.update_idletasks()

    def _handle_file_error(self, path: str, error: str):
        # 单文件失败，更新状态标签显示当前失败文件名
        self.status_label.config(text=f"失败: {Path(path).name}")

    def _handle_fatal_error(self, error: Exception):
        messagebox.showerror("处理失败", f"处理过程中发生错误：{error}")
        self._reset_ui()

    def _finish_processing(self):
        self.progress.config(value=100)
        total = len(self.selected_paths)
        failed_count = len(self.failed_files)
        success_count = total - failed_count

        if failed_count == 0:
            self.status_label.config(text="处理完成")
            messagebox.showinfo("完成", f"所有 {total} 张图片处理完毕")
        else:
            self.status_label.config(text=f"完成: {success_count} 成功, {failed_count} 失败")
            # 构建失败文件列表（最多显示 5 个）
            failed_lines = []
            for i, (p, err) in enumerate(self.failed_files[:5]):
                failed_lines.append(f"• {Path(p).name}: {err[:60]}")
            if failed_count > 5:
                failed_lines.append(f"... 还有 {failed_count - 5} 个文件失败")
            detail = "\n".join(failed_lines)
            messagebox.showwarning(
                "处理完成（部分失败）",
                f"共 {total} 张图片: {success_count} 成功, {failed_count} 失败\n\n失败详情:\n{detail}"
            )
        self._reset_ui()

    def _reset_ui(self):
        self.start_label.config(text="S T A R T")
        self.failed_files = []


# ──────────────────────────────
#  入口
# ──────────────────────────────
def main():
    try:
        import tkinterdnd2
        root = tkinterdnd2.Tk()
    except (ImportError, RuntimeError) as e:
        logger.warning(f"tkinterdnd2 不可用 ({e})，回退到标准 Tk")
        root = tk.Tk()

    app = SimpleWatermarkGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
