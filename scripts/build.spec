# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — 三平台通用打包配置（onedir 模式）。

用法（在任意平台的 CI 或本地）：
    pyinstaller scripts/build.spec --clean --noconfirm

平台差异自动处理：
- Windows：EXE 名带 .exe 后缀，console=False（GUI 无黑窗）
- macOS ：不生成 .app bundle（onedir 模式足够），无后缀
- Linux ：无后缀

资源解析约定（见 core/util.py:62 与 core/config_loader.py:27）：
- 字体 / logo / 模板：通过 Path(__file__).parent.parent → _internal/
- exiftool 二进制：通过 Path(sys.executable).parent → EXE 同级目录
"""

from __future__ import annotations

import platform
from pathlib import Path

# spec 由 PyInstaller 直接 exec，SPECPATH 是 PyInstaller 注入变量。
PROJECT_ROOT = Path(SPECPATH).parent  # type: ignore[name-defined]

APP_NAME = "aka-semi-utils"
ENTRY = str(PROJECT_ROOT / "main.py")
ICON = str(PROJECT_ROOT / "static" / "icon.ico")

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"

# ---------------------------------------------------------------------------
# 数据资源
# ---------------------------------------------------------------------------
# Release 包不直接打入开发者本机自动保存的 config/user.json，避免把私人路径、
# 自定义签名或自定义 Logo 一起分发。打包时使用干净的 release 默认配置。
# PyInstaller datas 的二元组目标值是目录，因此先打入 config/user.release.json，
# 再由下方 Tree/TOC 规则重命名成包内的 config/user.json。
datas = [
    (str(PROJECT_ROOT / "config" / "config.ini"), "config"),
    (str(PROJECT_ROOT / "config" / "user.release.json"), "config"),
    (str(PROJECT_ROOT / "config" / "fonts"), "config/fonts"),
    (str(PROJECT_ROOT / "config" / "logos"), "config/logos"),
    (str(PROJECT_ROOT / "config" / "presets"), "config/presets"),
    (str(PROJECT_ROOT / "config" / "signatures"), "config/signatures"),
    (str(PROJECT_ROOT / "config" / "templates"), "config/templates"),
    (str(PROJECT_ROOT / "static"), "static"),
    (str(PROJECT_ROOT / "render.jinja2"), "."),
]

# ---------------------------------------------------------------------------
# Hidden imports
# ---------------------------------------------------------------------------
hiddenimports = [
    "processor.filters",
    "processor.generators",
    "processor.mergers",
    "processor.batch",
    "processor.perf",
    "processor.schemas",
    "processor.types",
    "processor.core",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PIL.Image",
    "PIL.ImageDraw",
    "PIL.ImageFont",
    "PIL.ImageFilter",
    "pillow_heif",
]

# ---------------------------------------------------------------------------
# 排除项 — 减小体积
# ---------------------------------------------------------------------------
excludes = [
    "tkinter",
    "test",
    "unittest",
    "pytest",
    "mypy",
    "ruff",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtNetwork",
    "PyQt6.QtSql",
    "PyQt6.Qt3DCore",
    "PyQt6.QtMultimedia",
    "PyQt6.QtBluetooth",
    "PyQt6.QtPositioning",
    "PyQt6.QtSerialPort",
    "PyQt6.QtTest",
]


a = Analysis(  # noqa: F821 - PyInstaller 注入
    [ENTRY],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

# 把 release 默认配置在产物中重命名为 config/user.json，同时确保不会把开发机
# config/user.json 打入 release 包。
a.datas = [
    ("config/user.json" if dest == "config/user.release.json" else dest, src, typ)
    for dest, src, typ in a.datas
    if dest != "config/user.json"
]

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=not IS_WINDOWS,     # Linux/macOS 可 strip 减体积
    upx=False,
    console=False,            # GUI 程序
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON if IS_WINDOWS else None,  # .ico 仅 Windows 有效
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=not IS_WINDOWS,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
