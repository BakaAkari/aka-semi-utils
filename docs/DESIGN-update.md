# aka-semi-utils 极简水印 — 项目设计文档更新

**更新日期**: 2026-04-27  
**更新内容**: GUI 主题自适应（macOS / Windows 亮色/暗色模式兼容）

---

## 新增章节：§8.4 主题自适应

**位置**: 插入到 §8.3 操作流程 之后，§9 已知问题与备忘 之前

**内容**:

### 8.4 主题自适应（macOS / Windows 亮色/暗色模式）

**目标**：GUI 在 macOS 和 Windows 的亮色/暗色模式下文字均可见，不依赖系统默认 tkinter 主题。

**检测机制**：
- **macOS**：`defaults read -g AppleInterfaceStyle` → 返回 `Dark` 为暗色
- **Windows**：注册表 `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize\AppsUseLightTheme` → 值为 `0` 为暗色
- **Linux/其他**：tkinter 默认背景色推断（RGB 平均值 < 128 视为暗色）

**颜色常量**（启动时根据检测结果确定）：

| 模式 | 文字颜色 | 拖放区背景 | 计数/状态 |
|------|---------|-----------|----------|
| 暗色 | `white` | `#333333` | `white` |
| 亮色 | `black` | `#f0f0f0` | `#666666` |

**控件处理**：
- `tk.Label`、`tk.Entry` → 显式设置 `fg=`、`insertbackground=`
- `ttk.Combobox` → `ttk.Style` 配置 `foreground=`
- 按钮统一使用 `ttk.Button`（避免 macOS 上 `tk.Button` 的 `bg=` 与 `fg=` 冲突导致文字消失）

**代码位置**：`gui.py` 顶部 `_is_dark_mode()` 函数 + 全局颜色常量。

---

## §10 待办清单更新

当前实现状态（2026-04-27）：

| 待办项 | 状态 | 备注 |
|--------|------|------|
| 下载思源黑体 | ✅ 完成 | NotoSansCJKsc-Regular + Bold 已放入 config/fonts/ |
| 实现配置系统 | ✅ 完成 | core/config_loader.py |
| 实现模板构建器 | ✅ 完成 | core/template_builder.py |
| 实现字体管理器 | ✅ 完成 | core/font_manager.py |
| 实现配置面板 GUI | ✅ 完成 | gui.py Toplevel 弹窗 |
| 实现输出路径变量解析 | ✅ 完成 | {source_dir} / {desktop} / {home} |
| 完善错误处理 | ✅ 完成 | 分级错误 + 线程安全 |
| 验证实际处理流程 | ✅ 完成 | DSCF9981.jpg 测试通过 |
| **GUI 主题自适应** | ✅ **新增完成** | macOS/Windows 亮色/暗色自动切换 |
| 编写配置文档 | ⏳ 待办 | 需更新飞书云文档 |

---

## 代码片段

```python
# gui.py - 主题检测与颜色常量
import platform
import subprocess
import tkinter as tk

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
        if bg.startswith("#") and len(bg) == 7:
            r, g, b = int(bg[1:3], 16), int(bg[3:5], 16), int(bg[5:7], 16)
            return (r + g + b) / 3 < 128
    except Exception:
        pass
    return False

_IS_DARK = _is_dark_mode()

# 颜色常量（根据系统主题自动切换）
if _IS_DARK:
    _FG = "white"
    _DROP_BG = "#333333"
    _DROP_FG = "white"
    _COUNT_FG = "white"
    _STATUS_FG = "white"
    _LABEL_FG = "white"
    _ENTRY_FG = "white"
    _ENTRY_INSERT = "white"
else:
    _FG = "black"
    _DROP_BG = "#f0f0f0"
    _DROP_FG = "black"
    _COUNT_FG = "#666666"
    _STATUS_FG = "black"
    _LABEL_FG = "black"
    _ENTRY_FG = "black"
    _ENTRY_INSERT = "black"
```
