# aka-semi-utils (极简水印) UI/UX 深度分析报告

> **版本**: 2.1.8  
> **分析日期**: 2025-07-01  
> **分析范围**: GUI 布局架构、UI 组件体系、状态管理、交互流程、视觉设计、用户体验全链路

---

## 目录

1. [UI 布局架构总览](#1-ui-布局架构总览)
2. [窗口层级与空间分配](#2-窗口层级与空间分配)
3. [UI 组件体系详解](#3-ui-组件体系详解)
4. [状态管理与数据流架构](#4-状态管理与数据流架构)
5. [UX 交互流程全链路](#5-ux-交互流程全链路)
6. [视觉设计系统](#6-视觉设计系统)
7. [交互细节与微交互](#7-交互细节与微交互)
8. [错误处理与用户反馈](#8-错误处理与用户反馈)
9. [性能与响应式设计](#9-性能与响应式设计)
10. [UX 设计决策分析](#10-ux-设计决策分析)
11. [可改进空间与建议](#11-可改进空间与建议)

---

## 1. UI 布局架构总览

### 1.1 顶层窗口结构

```
QMainWindow (极简水印)
└── centralWidget (QWidget)
    └── root_layout (QHBoxLayout)          # 顶层水平双列
        ├── left_col (QWidget)              # 左列：主内容区
        │   └── layout (QVBoxLayout)
        │       ├── thumb_container         # 上层：缩略图容器
        │       └── bottom (QWidget)        # 中层：底部操作区
        │           └── bottom_layout (QVBoxLayout)
        │               ├── output_row      # 输出路径行
        │               ├── progress_row  # 进度条 + 按钮行
        │               └── config_drawer   # 配置抽屉（可折叠）
        │                   └── tabs (QTabWidget)
        │                       ├── "水印配置" Tab
        │                       │   ├── ConfigPanel
        │                       │   │   ├── "水印" Tab (CornerSection × 4)
        │                       │   ├── "Logo" Tab (LogoTab)
        │                       │   └── "签名" Tab (SignatureTab)
        │                       └── "全局参数" Tab
        │                           └── AdvancedPanel (CollapsibleGroup × 7)
        └── preview_sidebar (QWidget)       # 右列：预览侧栏（默认折叠）
            └── PreviewPanel
```

### 1.2 布局设计哲学

| 设计原则 | 实现方式 | 目的 |
|---------|---------|------|
| **双列自适应** | 左列 `stretch=1` 吃满剩余宽度，右列固定宽度 | 主内容优先，预览按需展开 |
| **垂直三段式** | 缩略图 → 操作区 → 配置抽屉 | 符合用户认知流程：选图 → 设置 → 执行 |
| **折叠收纳** | 配置抽屉默认展开，预览侧栏默认折叠 | 新用户立即看到配置入口，高级功能按需展开 |
| **空间弹性** | 最小尺寸 450×660，默认 500×740 | 适配小屏幕，给签名设置留出纵向空间 |

---

## 2. 窗口层级与空间分配

### 2.1 主窗口尺寸策略

```python
self.setMinimumSize(450, 660)   # 最小：保证所有控件可见
self.resize(500, 740)            # 默认：签名设置页舒展空间
```

**设计考量**：
- **最小高度 660px**：容纳 2 行缩略图(170-200px) + 输出路径行(28px) + 进度行(28px) + 配置抽屉(≥400px)
- **默认高度 740px**：给新增签名设置页留出更舒展的纵向空间
- **最小宽度 450px**：保证配置面板内表单不被过度挤压

### 2.2 预览侧栏动态尺寸

```python
PREVIEW_WIDTH = 360               # 初始固定宽度
preview_w = int(self.width() * 1.5)  # 展开时 = 主窗口宽度的 1.5 倍
```

**交互策略**：
1. **展开时**：先拓展主窗口宽度，再显示预览区 → 避免瞬间挤压左列 UI
2. **折叠时**：先隐藏预览区，再收回宽度 → 平滑过渡
3. **动态计算**：预览宽度随主窗口当前宽度变化，保持比例感

### 2.3 缩略图容器尺寸约束

```python
setMinimumHeight(170)
setMaximumHeight(200)
```

**设计意图**：
- 固定高度区域，不随窗口拉伸而无限扩展
- 2 行 × 3 列网格，每格 100×75px + 8px 间距
- 超出 5 张显示 "+N" 占位，第 6 格固定为 ➕ 追加卡

---

## 3. UI 组件体系详解

### 3.1 缩略图容器 (ThumbContainer)

#### 视觉状态机

```
┌─────────────────────────────────────┐
│  空状态                              │
│  ┌─────────────────────────────┐   │
│  │      选择图片文件            │   │  ← QPushButton (虚线边框)
│  │   (点击或拖拽到此区域)        │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  有图状态 (3列×2行网格)               │
│  ┌─────┐ ┌─────┐ ┌─────┐           │
│  │ img │ │ img │ │ img │           │
│  └─────┘ └─────┘ └─────┘           │
│  ┌─────┐ ┌─────┐ ┌─────┐           │
│  │ img │ │ +3  │ │  +  │           │  ← +N 占位 / ➕ 追加卡
│  └─────┘ └─────┘ └─────┘           │
└─────────────────────────────────────┘
```

#### 交互矩阵

| 操作 | 目标 | 响应 |
|------|------|------|
| 左键点击 | 空白区域 / ➕ 卡 | 打开文件选择对话框 |
| 右键点击 | 真实缩略图 | 显示上下文菜单（删除） |
| 拖拽文件 | 整个容器 | 接受文件路径列表 |
| 点击 | +N 占位 | 无操作（仅提示剩余数量） |

#### 二态切换动画

- **空 → 有图**：`empty_btn.setVisible(False)` + `grid_host.setVisible(True)`
- **有图 → 空**：反向切换
- 无过渡动画（即时切换），保持响应速度

#### 缩略图加载策略

```
用户添加文件 → emit file_added → AppState 更新 → files_changed Signal
    → ThumbContainer.set_files() → _update_view() → _refresh_grid()
        → 清空旧网格 → 构建新网格 → 启动 ThumbLoaderThread
            → 后台逐张生成缩略图 → thumbnail_ready Signal → 更新 QLabel
```

**关键设计**：
- **异步加载**：避免阻塞 UI，大批量图片时仍可操作
- **取消机制**：新加载请求自动取消旧线程
- **占位图**：加载失败时显示 "?" 占位，不阻塞流程
- **文件句柄安全**：`with Image.open(path) as src` 确保立即关闭

---

### 3.2 配置抽屉 (CollapsibleConfigPanel)

#### 折叠机制

```python
# 标题栏（始终可见）
▶ 设置  ← 点击展开
▼ 设置  ← 点击折叠
```

**样式设计**：
```css
QPushButton {
    border: none;
    background-color: #1E1E1E;
    color: #999999;
    padding: 10px 12px;
    text-align: left;
    font-weight: bold;
    font-size: 13px;
    border-top: 1px solid #333333;
    border-bottom: 1px solid #333333;
}
QPushButton:hover {
    background-color: #2A2A2A;
    color: #E0E0E0;
}
```

**UX 决策**：
- **默认展开** (`_expanded = True`)：Phase 6.10 明确改为展开，让新用户立即看到配置入口
- **处理中禁用**：`setEnabled(False)` 但标题栏保持可点击（用户可查看配置但不可修改）
- **无动画**：直接 `setVisible()`，避免动画延迟影响操作效率

---

### 3.3 配置面板 (ConfigPanel) — 三 Tab 结构

#### Tab 1: 水印（最复杂）

```
┌─────────────────────────────────────────┐
│ 水印                                    │
├─────────────────────────────────────────┤
│ ┌─ ↖ 左上 (2 字段) ─────────────────┐  │
│ │ ▼                                 │  │  ← 可折叠 CornerSection
│ │ [相机型号 ▼] [⚙] [↑] [↓] [×]      │  │  ← ChipRowWidget
│ │ [镜头型号 ▼] [⚙] [↑] [↓] [×]      │  │
│ │ + 添加字段    分隔符: [ ]  字号:[继承▼]│  │
│ └────────────────────────────────────┘  │
│ ┌─ ↗ 右上 (0 字段) ─────────────────┐  │
│ │ ▶                                 │  │  ← 折叠状态
│ └────────────────────────────────────┘  │
│ ┌─ ↙ 左下 (4 字段) ─────────────────┐  │
│ │ ▼                                 │  │
│ │ [焦距 ▼] ... [光圈 ▼] ...          │  │
│ │ [快门 ▼] ... [ISO ▼] ...           │  │
│ └────────────────────────────────────┘  │
│ ┌─ ↘ 右下 (0 字段) ─────────────────┐  │
│ │ ▶                                 │  │
│ └────────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

#### CornerSection 内部结构

**标题行**：
```
[▼] [↖ 左上] [(2 字段)] ─────────── [字号] [继承▼] [⤺]
```
- 折叠按钮：`▼`/`▶` 切换
- 角标 + 名称：`↖ 左上`
- 字段计数：`(2 字段)` — 实时更新
- 字号下拉：预定义选项（继承/小32px/标准48px/大80px/特大96px/超大128px）
- 重置按钮：`⤺` — 重置角级字号为继承

**内容区**：
- Chip 列表：垂直堆叠的 `ChipRowWidget`
- 控制行：`+ 添加字段` 按钮 + `分隔符` 输入框

#### ChipRowWidget 控件布局

```
┌─────────────────────────────────────────────────────────┐
│ [相机型号 ▼──────] [⚙] [↑] [↓] [×]                      │
│  字段类型下拉(最小110px) 详情 上移 下移 删除              │
└─────────────────────────────────────────────────────────┘
```

**控件细节**：
| 控件 | 尺寸 | 功能 | Tooltip |
|------|------|------|---------|
| 字段下拉 | minWidth=110 | 选择水印字段 | - |
| ⚙ 详情 | 28px | 编辑自定义文本 | "编辑此字段的自定义文本" |
| ↑ 上移 | 24px | 排序提前 | "上移（排序提前）" |
| ↓ 下移 | 24px | 排序后移 | "下移（排序后移）" |
| × 删除 | 24px | 删除字段 | "删除此字段" |

**⚙ 高亮状态**：当 `field_id == custom_text` 且有内容时，⚙ 显示为 `⚙ •` + 蓝色文字

#### Tab 2: Logo

```
┌─────────────────────────────────────────┐
│ Logo                                    │
├─────────────────────────────────────────┤
│ Logo 模式：    [自动（按品牌）▼]          │
│ Logo 位置：    [右侧▼]                  │
│ 分隔线颜色：   [████████ #D8D8D6]       │  ← 颜色按钮，点击打开 QColorDialog
│ 自定义路径：   [____________] [浏览...]   │
└─────────────────────────────────────────┘
```

**Logo 模式选项**：
- `auto`：自动按品牌匹配（基于 EXIF 的 Make 字段）
- `disabled`：禁用 Logo
- `custom`：使用自定义路径

**颜色选择器交互**：
- 按钮背景显示当前颜色
- 点击打开系统颜色对话框
- 实时更新按钮样式

#### Tab 3: 签名（Phase 25 新增）

```
┌─────────────────────────────────────────┐
│ 签名                                    │
├─────────────────────────────────────────┤
│ [✓] 启用签名                            │
│ 签名图片：     [____________] [浏览...] │
│ 反向签名色：   [黑色文字▼]               │  ← 黑↔白二值切换
│ 签名增强：     [柔和投影▼] [强度:═══50%]│  ← ComboBox + Slider
│ 位置：         [正中心▼]                │  ← 9宫格锚点
│ 大小：         [20 %]                   │
│ X：            [80 px]    Y：[60 px]    │  ← 有符号偏移
└─────────────────────────────────────────┘
```

**签名增强选项**：
- `none`：关闭
- `soft_shadow`：柔和投影
- `soft_glow`：轻微外发光
- `soft_outline`：柔和描边

**强度滑块**：0-100%，步进 5%，实时显示百分比

**9 宫格锚点**：
```
┌─────────┬─────────┬─────────┐
│ 左上    │ 上方居中 │ 右上    │
├─────────┼─────────┼─────────┤
│ 左侧居中 │ 正中心  │ 右侧居中 │
├─────────┼─────────┼─────────┤
│ 左下    │ 下方居中 │ 右下    │
└─────────┴─────────┴─────────┘
```

---

### 3.4 全局参数面板 (AdvancedPanel)

#### 7 个可折叠分组

```
┌─────────────────────────────────────────┐
│ ▶ 字体与颜色                            │  ← 默认折叠
├─────────────────────────────────────────┤
│ ▶ 边框/留白                             │
├─────────────────────────────────────────┤
│ ▶ 圆角与阴影                            │
├─────────────────────────────────────────┤
│ ▶ 图像质量                              │
├─────────────────────────────────────────┤
│ ▶ 背景效果                              │
├─────────────────────────────────────────┤
│ ▶ 拼接与对齐                            │
├─────────────────────────────────────────┤
│ ▶ 图像调整                              │
├─────────────────────────────────────────┤
│ ▶ 重置                                  │  ← 危险操作分组
│   ⚠ 此操作会清除所有配置...             │
│   [恢复默认]                            │
└─────────────────────────────────────────┘
```

**CollapsibleGroup 组件**：
- 标题栏：`▶ 分组名` → 点击展开为 `▼ 分组名`
- 内容区：默认隐藏
- 边框：1px solid #333333，圆角 4px
- 悬停效果：标题颜色从 #999 变为 #E0E0E0

#### 字体选择器 (FontSelector)

```
┌─────────────────────────────────────────────────────────┐
│ 字体：[NotoSansCJKsc-Regular.otf ▼] [预览图] [继承] [⟳] [📁] │
└─────────────────────────────────────────────────────────┘
```

**设计亮点**：
- **实时预览**：右侧 100×26px QLabel，PIL 实时渲染 "水印示例"
- **继承按钮**：清空字体覆盖，继承上级设置
- **刷新按钮**：重新扫描 fonts 目录
- **打开文件夹**：一键打开字体目录，用户可自行拖入新字体
- **零系统依赖**：只读 `config/fonts/` 目录，不依赖系统字体，打包后行为一致

---

### 3.5 底部操作区

```
┌─────────────────────────────────────────────────────────┐
│ 输出路径：[{source_dir}/output        ] [浏览...] [✓覆盖] │
├─────────────────────────────────────────────────────────┤
│ [══════════════ 处理中 3/10... ══════════════] [关于] [取消] [START] [▸] │
└─────────────────────────────────────────────────────────┘
```

**输出路径行**：
- 输入框自适应宽度 (`stretch=1`)
- 浏览按钮：打开目录选择对话框
- 覆盖复选框：控制是否覆盖已有输出文件

**进度行**：
- 进度条：显示百分比 + 状态文字（`处理中 3/10... 30%`）
- 关于按钮：显示版本信息（固定高度 28px）
- START/取消按钮：互斥显示
- 预览切换按钮：`▸`/`◂` 正方形 28×28px，字符图标

---

### 3.6 预览侧栏 (PreviewPanel)

```
┌─────────────────────────────────────────┐
│ 实时预览                           [刷新] │
├─────────────────────────────────────────┤
│                                         │
│    ┌─────────────────────────────┐      │
│    │                             │      │
│    │      渲染后的图片预览        │      │  ← QLabel + QPixmap
│    │                             │      │
│    └─────────────────────────────┘      │
│                                         │
├─────────────────────────────────────────┤
│ 已渲染 · 480×320                        │  ← 状态行
└─────────────────────────────────────────┘
```

**交互状态**：
| 状态 | 显示内容 | 触发条件 |
|------|---------|---------|
| 折叠 | （不可见） | 默认状态 |
| 无图片 | "（尚未选择图片）" | 未选择文件时展开 |
| 渲染中 | "渲染中…" | 配置变化后 500ms debounce |
| 成功 | 缩略图 + 尺寸信息 | 渲染完成 |
| 失败 | "（渲染失败）" + 错误原因 | 渲染异常 |

**动态宽度策略**：
- 展开时宽度 = 当前主窗口宽度的 1.5 倍
- 主窗口同步扩展，避免挤压左列
- 折叠时先隐藏再收缩，平滑过渡

---

## 4. 状态管理与数据流架构

### 4.1 AppState — 单一事实来源 (SSOT)

```python
class AppState(QObject):
    # 信号定义
    files_changed = pyqtSignal(list)        # 文件列表变更
    output_changed = pyqtSignal()            # 输出配置变更
    watermark_changed = pyqtSignal()         # 水印配置变更
    advanced_changed = pyqtSignal()        # 全局参数变更
    state_reloaded = pyqtSignal()            # 外部全量替换
    progress_changed = pyqtSignal(int, str)  # 进度更新
```

**数据模型层次**：

```
AppState (单一事实来源)
├── selected_files: list[str]              # 文件列表（不持久化）
├── left_top: CornerConfig                 # 左上配置
├── left_bottom: CornerConfig            # 左下配置
├── right_top: CornerConfig              # 右上配置
├── right_bottom: CornerConfig           # 右下配置
├── logo: LogoConfig                       # Logo 配置
├── custom_text: str                       # 全局自定义文本
├── advanced: AdvancedConfig             # 全局参数
│   ├── global_font: str                 # 全局字体
│   ├── global_color: str                # 全局颜色
│   ├── corner_text_height_px: int       # 固定像素尺寸
│   ├── left/right/top/bottom_margin     # 边距
│   ├── border_radius: int               # 圆角
│   ├── shadow_radius: int               # 阴影
│   ├── quality: int                     # JPEG 质量
│   ├── blur_radius: int                 # 模糊
│   ├── scale: float                     # 缩放
│   ├── signature_*                      # 签名相关（10+ 字段）
│   └── ...
├── output: OutputConfig                 # 输出配置
│   ├── path: str                        # 输出路径模式
│   └── override: bool                   # 是否覆盖
└── 处理状态（不持久化）
    ├── is_processing: bool
    ├── progress: int
    └── status_text: str
```

### 4.2 信号驱动更新流程

```
用户操作（如修改字段）
    ↓
控件直接 mutate AppState 中的 dataclass 引用
    ↓
调用 AppState.set_corner_config() / set_advanced_config() 等
    ↓
emit watermark_changed / advanced_changed Signal
    ↓
├─→ 订阅者 1: PreviewPanel._schedule_render() → 500ms debounce → 实时预览
├─→ 订阅者 2: AppState._schedule_autosave() → 300ms debounce → 持久化
├─→ 订阅者 3: MainWindow._on_progress_changed() → 更新进度条（仅 progress_changed）
└─→ 订阅者 4: AdvancedPanel._load_state() → 刷新 UI（仅 advanced_changed + state_reloaded）
```

### 4.3 关键设计：不订阅自己的写

**ConfigPanel 的订阅策略**：
```python
# 仅订阅外部全量替换信号
self.state.state_reloaded.connect(self._reload_all_from_state)

# 不订阅 watermark_changed —— 避免自激发循环
# 用户编辑 → mutate chip → push to state → watermark_changed
# 如果 ConfigPanel 订阅了 watermark_changed 并重建 UI，就会循环
```

**AdvancedPanel / SignatureTab 的订阅策略**：
```python
# 自订阅 advanced_changed，但用 _loading 守卫
self.state.advanced_changed.connect(self._load_state)

# _load_state 中:
self._loading = True
# ... setValue/setText ...
self._loading = False

# _on_changed 中:
if self._loading:
    return  # 忽略加载期间触发的信号
```

### 4.4 持久化流程

```
任何 *_changed 信号（除 state_reloaded）
    ↓
AppState._schedule_autosave()
    ↓
QTimer.start(300ms)  # SingleShot, 防抖
    ↓
（300ms 内无新信号）
    ↓
AppState._do_autosave()
    ↓
AppState.save_to_disk()
    ↓
原子写：.tmp → rename → user.json
```

**持久化内容**：
```json
{
  "version": 2,
  "output": { "path": "...", "override": true },
  "corners": {
    "left_top": { "chips": [...], "separator": " ", "font_size": 0 },
    ...
  },
  "logo": { "enabled": "auto", "position": "right", ... },
  "custom_text": "",
  "advanced": { "global_font": "...", "quality": 95, ... }
}
```

**不持久化**：
- `selected_files`：会话级数据，每次启动为空
- `is_processing/progress/status_text`：运行时状态

---

## 5. UX 交互流程全链路

### 5.1 首次打开应用

```
[启动]
    ↓
MainWindow.__init__()
    ├── 设置窗口标题 "极简水印"
    ├── 应用 QSS 暗色主题
    ├── 初始化 AppState（空状态）
    ├── _setup_ui() —— 构建所有控件，连接信号
    └── app_state.load_from_disk() —— 加载持久化配置
        ├── 读取 config/user.json
        ├── 反序列化到 AppState 字段
        ├── _emit_full_refresh() —— 发出全套信号
        │   ├── files_changed → ThumbContainer.set_files([])
        │   ├── output_changed → MainWindow._on_state_output_changed()
        │   ├── watermark_changed → PreviewPanel._schedule_render()
        │   ├── advanced_changed → AdvancedPanel._load_state()
        │   └── state_reloaded → ConfigPanel._reload_all_from_state()
        └── _autosave_enabled = True
    ↓
[界面呈现]
┌─────────────────────────────────────────────────────────┐
│ 极简水印                                    [_] [□] [×] │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐│
│ │                                                     ││
│ │              选择图片文件                            ││  ← 空状态
│ │         (点击空白处或拖拽到此区域)                    ││
│ │                                                     ││
│ └─────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────┤
│ 输出路径：[{source_dir}/output        ] [浏览...] [✓覆盖] │
│ [═══════════════════════════════════════] [关于] [START] [▸]│
├─────────────────────────────────────────────────────────┤
│ ▼ 设置                                                  │
│ ┌─────────────────────────────────────────────────────┐│
│ │ [水印] [Logo] [签名] │ [全局参数]                      ││
│ │                                                     ││
│ │ ┌─ ↖ 左上 (2 字段) ─────────────────────────────┐  ││
│ │ │ [相机型号 ▼] [⚙] [↑] [↓] [×]                  │  ││
│ │ │ [镜头型号 ▼] [⚙] [↑] [↓] [×]                  │  ││
│ │ │ + 添加字段    分隔符: [ ]  字号:[继承▼]          │  ││
│ │ └─────────────────────────────────────────────────┘  ││
│ │ ┌─ ↙ 左下 (4 字段) ─────────────────────────────┐  ││
│ │ │ [焦距 ▼] ... [光圈 ▼] ... [快门 ▼] ... [ISO ▼]...│  ││
│ │ └─────────────────────────────────────────────────┘  ││
│ │ ...                                                 ││
│ └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

**新用户引导设计**：
- 配置抽屉默认展开，立即看到水印配置入口
- 空状态区域大而明显，提示 "选择图片文件"
- 默认配置已预置常用字段（左上：厂商+相机型号，左下：焦距/光圈/快门/ISO）

### 5.2 添加图片流程

**路径 A：点击空状态区域**
```
点击 "选择图片文件" 按钮 / 点击空白区域
    ↓
QFileDialog.getOpenFileNames()
    └── 过滤器: "图片 (*.jpg *.jpeg *.png *.heic *.tiff *.webp)"
    ↓
ThumbContainer.add_files(paths) —— 只 emit 信号
    └── file_added.emit(paths)
    ↓
MainWindow._on_files_added() → AppState.add_files()
    └── selected_files.extend(paths)
    └── files_changed.emit(selected_files)
    ↓
├─→ ThumbContainer.set_files(files) → _update_view()
│   ├── empty_btn.hide()
│   ├── grid_host.show()
│   └── _refresh_grid() → 启动 ThumbLoaderThread
│       └── 异步加载缩略图 → thumbnail_ready → 更新 QLabel
│
└─→ PreviewPanel._schedule_render() → 500ms debounce
    └── _do_render() → 启动 PreviewRenderThread
        └── 渲染第一张图 → preview_ready → 显示预览
```

**路径 B：拖拽文件**
```
拖拽文件到 ThumbContainer
    ↓
dragEnterEvent() → acceptProposedAction()
dropEvent() → 提取本地文件路径 → add_files(paths)
    ↓
（同上流程）
```

**路径 C：点击 ➕ 追加卡**
```
点击网格中的 ➕ 卡
    ↓
_on_select_files() → QFileDialog → add_files()
    ↓
（同上流程）
```

### 5.3 配置水印流程

**添加字段**：
```
点击 "+ 添加字段"
    ↓
CornerSection._on_add_chip()
    ├── 检查 MAX_CHIPS (8) 限制
    ├── 创建 FieldChip(field_id="camera_model")
    ├── 添加到 corner.chips 列表
    ├── 创建 ChipRowWidget 并加入布局
    ├── _refresh_summary() → 更新标题计数
    ├── _refresh_add_btn() → 满 8 个时禁用按钮
    └── _push_to_state() → state.set_corner_config()
        └── watermark_changed.emit()
```

**修改字段类型**：
```
下拉选择新字段类型
    ↓
ChipRowWidget._on_type_changed()
    ├── 更新 chip.field_id
    ├── _refresh_detail_indicator() → 更新 ⚙ 高亮
    └── changed.emit()
    ↓
CornerSection._on_chip_changed()
    ├── _refresh_summary()
    └── _push_to_state()
```

**调整字段顺序**：
```
点击 ↑ / ↓ 按钮
    ↓
CornerSection._on_move_left() / _on_move_right()
    ├── 数据层：交换 chips 列表中的位置
    ├── UI 层：交换 _chip_rows 列表，removeWidget + insertWidget
    └── _push_to_state()
```

**删除字段**：
```
点击 × 按钮 / 右键缩略图选择删除
    ↓
CornerSection._on_delete_chip() / AppState.remove_file()
    ├── 从数据列表移除
    ├── 从 UI 列表移除
    ├── deleteLater() 释放控件
    ├── _refresh_summary() / _refresh_add_btn()
    └── _push_to_state()
```

### 5.4 实时预览流程

```
配置变化（watermark_changed / advanced_changed / files_changed）
    ↓
PreviewPanel._schedule_render()
    ├── 检查 _active（侧栏是否展开）
    └── QTimer.start(500ms)  # debounce
    ↓
（500ms 内无新变化）
    ↓
PreviewPanel._do_render()
    ├── 检查是否有文件
    ├── 取消旧线程（如果正在运行）
    ├── state_to_processors(state) → 生成处理器配置
    ├── 创建 PreviewRenderThread
    │   ├── get_exif() → 读取 EXIF
    │   ├── render_processors() → Jinja2 模板渲染
    │   ├── start_process() → 执行管道（不写盘）
    │   ├── thumbnail 缩放至 max_size (480px)
    │   └── _pil_to_qpixmap() → PIL 转 QPixmap
    └── 启动线程
    ↓
PreviewRenderThread.preview_ready → _on_preview_ready()
    ├── 缩放至 label 大小（保持比例）
    ├── label.setPixmap(scaled)
    ├── 保留原图 _original_pix（用于 resizeEvent 重缩放）
    └── _set_status(f"已渲染 · {w}×{h}")
```

**关键设计**：
- **500ms debounce**：避免快速连续修改时频繁渲染
- **单线程互斥**：新渲染请求自动取消旧线程
- **不写盘**：预览纯内存渲染，输出路径设为 None
- **所见即所得**：与正式批处理共用同一套处理器配置

### 5.5 批处理流程

```
点击 START 按钮
    ↓
MainWindow._on_start()
    ├── 检查是否有文件 → 无则 QMessageBox.warning("请先选择图片")
    ├── state_to_processors(state) → 生成处理器列表
    │   └── 失败则 QMessageBox.warning("配置生成失败")
    ├── 检查旧线程是否仍在运行
    ├── _set_processing_state(True) → 禁用所有控件
    │   ├── start_btn.hide() / cancel_btn.show()
    │   ├── 禁用 thumb_container / config_drawer / preview_sidebar
    │   └── 禁用 output_input / override_check
    ├── 创建 ProcessThread
    │   ├── files, processors, output_pattern, override
    │   └── 连接信号: progress / file_done / file_failed_detail / finished_all / finished_summary
    └── thread.start()
    ↓
ProcessThread.run()（后台线程）
    ├── get_exif_batch(files) → 批量读取 EXIF
    ├── 过滤已存在且不允许覆盖的输出
    ├── build_tasks() → 构造 BatchTask 列表
    ├── process_batch() → 并行/串行执行
    │   ├── 小批量 (<3) → 串行处理
    │   └── 大批量 → ProcessPoolExecutor
    └── 汇总结果 → BatchSummary
    ↓
信号回传主线程:
├─→ progress → MainWindow._on_thread_progress()
│   └── AppState.update_progress() → progress_changed
│       └── MainWindow._on_progress_changed() → 更新进度条
├─→ file_done → 记录日志
├─→ file_failed_detail → 暂存到 _failed_details 列表
├─→ finished_summary → 暂存到 _latest_summary
└─→ finished_all → MainWindow._on_finished_all()
    ├── _set_processing_state(False)
    ├── 更新进度: 100% / 0%
    └── _show_summary_dialog() → 分级展示结果
```

**结果展示策略**：

| 严重度 | 图标 | 标题 | 详情 |
|--------|------|------|------|
| INFO | Information | "完成" | 成功 N 张 |
| WARNING | Warning | "完成（部分失败）" | 成功 N，失败 M，跳过 K |
| ERROR | Critical | "处理出错" | 错误分类 + 前 5 条样本 |
| FATAL | Critical | "严重错误" | 整批不可恢复错误 |

**错误详情聚合**：
```python
# 按错误类型计数
kinds = Counter(e.title for e in summary.errors)
# 显示前 5 条样本
sample_lines = [f"• [{文件名}] {标题}：{详情}"]
# 超过 5 条显示 "...（另 N 条）"
```

### 5.6 取消流程

```
点击 取消 按钮
    ↓
MainWindow._on_cancel()
    ├── thread.cancel() → 设置 threading.Event
    ├── thread.wait(3000) → 等待最多 3 秒
    ├── AppState.set_processing(False, 0, "已取消")
    └── _set_processing_state(False)
    ↓
ProcessThread.run() 中检测到 cancelled
    ├── 停止启动新 worker
    ├── 当前 worker 继续跑完（不强制中断）
    └── 返回已处理结果
```

**设计考量**：
- **协作式取消**：不强制 kill 线程，避免资源泄漏
- **3 秒等待**：给正在运行的 worker 完成时间
- **线程生命周期**：finished → _on_process_thread_finished → 清空引用 → deleteLater

### 5.7 关闭应用流程

```
点击关闭按钮 / Cmd+Q
    ↓
MainWindow.closeEvent()
    ├── 取消处理线程（如果正在运行）
    │   ├── thread.cancel()
    │   └── thread.wait(3000)
    ├── 取消预览线程
    │   ├── preview_thread.cancel()
    │   └── preview_thread.wait(2000)
    ├── 取消缩略图加载线程
    │   ├── loader.cancel()
    │   └── loader.wait(2000)
    ├── 立即持久化
    │   ├── _save_timer.stop()（取消未发的 debounce）
    │   └── app_state.flush_autosave() → save_to_disk()
    └── event.accept()
```

**关键设计**：
- **三线程依次取消**：处理线程最重，先取消；预览次之；缩略图最轻
- **立即持久化**：取消 debounce 计时器，强制同步写盘
- **原子写**：.tmp → rename，避免 crash 留残缺文件

---

## 6. 视觉设计系统

### 6.1 暗色主题配色

```python
COLORS = {
    "BG": "#121212",              # 主背景
    "SURFACE": "#1E1E1E",         # 卡片/输入框背景
    "SURFACE_HOVER": "#2A2A2A",   # 悬停背景
    "BORDER": "#333333",          # 边框
    "BORDER_HOVER": "#666666",    # 悬停边框
    "TEXT_PRIMARY": "#E0E0E0",    # 主文字
    "TEXT_SECONDARY": "#999999",   # 次要文字
    "TEXT_DISABLED": "#666666",    # 禁用文字
    "ACCENT": "#E0E0E0",          # 强调色（主按钮）
    "ACCENT_HOVER": "#FFFFFF",     # 强调悬停
    "DANGER": "#EF4444",          # 危险操作
}
```

### 6.2 组件样式映射

| 组件 | 背景 | 文字 | 边框 | 悬停效果 |
|------|------|------|------|---------|
| QWidget (全局) | #121212 | #E0E0E0 | - | - |
| QMainWindow | #121212 | - | - | - |
| QTabBar::tab | #1E1E1E | #999999 | 1px #333 | bg→#2A2A2A |
| QTabBar::tab:selected | #121212 | #E0E0E0 | 底部 2px #E0E0E0 | - |
| QPushButton | #1E1E1E | #E0E0E0 | 1px #333 | bg→#2A2A2A, border→#666 |
| QPushButton#primary | #E0E0E0 | #121212 | none | bg→#FFFFFF |
| QPushButton#danger | #EF4444 | white | none | - |
| QLineEdit | #1E1E1E | #E0E0E0 | 1px #333 | border→#E0E0E0 (focus) |
| QComboBox | #1E1E1E | #E0E0E0 | 1px #333 | border→#E0E0E0 (focus) |
| QSpinBox | #1E1E1E | #E0E0E0 | 1px #333 | border→#E0E0E0 (focus) |
| QProgressBar | #1E1E1E | #E0E0E0 | 1px #333 | chunk→#E0E0E0 |
| QGroupBox | - | #E0E0E0 | 1px #333 | - |
| QMenu | #1E1E1E | #E0E0E0 | 1px #333 | item→#2A2A2A |
| QScrollBar::handle | - | - | - | bg→#666666 |

### 6.3 字体栈

```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
font-size: 13px;
```

**设计考量**：
- 系统字体优先，跨平台一致
- 13px 基础字号，适合密集配置界面
- 中文场景使用 NotoSansCJKsc 作为水印字体

### 6.4 尺寸规范

| 元素 | 尺寸 | 说明 |
|------|------|------|
| 缩略图 | 100×75px | 3:4 比例，cover 裁切 |
| 按钮高度 | 28px | 进度行按钮统一高度 |
| 输入框最小高度 | 24px | 保证触摸/点击区域 |
| 滑块 handle | 14×14px | 圆形，-5px margin |
| 滑块 groove | 4px | 圆角 2px |
| 复选框 indicator | 16×16px | 圆角 3px |
| 滚动条宽度 | 8px | 圆角 4px |
| 圆角半径 | 4px | 全局统一 |
| 间距 | 6-12px | 紧凑但不拥挤 |

---

## 7. 交互细节与微交互

### 7.1 滚轮保护 (WheelGuard)

**问题**：配置面板放在 QScrollArea 中时，QSpinBox/QComboBox/QSlider 默认会吃掉鼠标滚轮并改变值，导致用户想滚动设置页时误改配置。

**解决方案**：
```python
class _WheelGuardFilter(QObject):
    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Wheel:
            event.ignore()
            return True  # 拦截滚轮事件
        return False

def guard_wheel(widget):
    widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    widget.installEventFilter(_WheelGuardFilter(widget))
```

**应用范围**：
- `guard_wheel()`：单个控件
- `guard_wheel_for_children()`：父容器下所有值控件（递归 findChildren）

**效果**：
- 鼠标滚轮不再改变 SpinBox/ComboBox/Slider 的值
- 滚轮事件被忽略，自然传递给父级滚动区域
- 控件仍可通过点击/Tab 聚焦后使用键盘上下箭头调整

### 7.2 折叠动画

**实现方式**：无动画，直接 `setVisible()`

**理由**：
- PyQt6 动画框架增加复杂度
- 配置面板内容多，动画可能卡顿
- 即时反馈更符合工具类应用调性

**视觉补偿**：
- 箭头符号变化：`▶` → `▼`
- 颜色变化：标题悬停时 #999 → #E0E0E0
- 边框变化：折叠分组有 1px 边框，展开后内容区与边框融合

### 7.3 实时预览 Debounce

```python
DEBOUNCE_MS = 500  # PreviewPanel
AUTOSAVE_DEBOUNCE_MS = 300  # AppState
```

**双重 debounce 设计**：
1. **预览 debounce (500ms)**：用户连续修改配置时，只在停顿后渲染一次
2. **保存 debounce (300ms)**：配置变化后 300ms 内无新变化才写盘

**为什么预览比保存慢**：
- 预览需要执行完整图像管道（读 EXIF + Jinja2 渲染 + Pillow 处理）
- 保存只是 JSON 序列化，开销小
- 预览 500ms 保证用户输入完成后再渲染，避免中间状态

### 7.4 信号回写守卫

**问题**：AppState 加载持久化配置后回填 UI，UI 控件的 `setValue/setText` 会触发 `valueChanged/textChanged` 信号，信号 handler 又写回 AppState，形成循环。

**解决方案**：
```python
# MainWindow
self._output_loading: bool = False

def _on_state_output_changed(self):
    self._output_loading = True
    try:
        self.output_input.setText(self.app_state.output.path)
        self.override_check.setChecked(self.app_state.output.override)
    finally:
        self._output_loading = False

def _on_output_changed(self):
    if self._output_loading:
        return  # 守卫期间忽略信号
    self.app_state.set_output(...)
```

**应用位置**：
- MainWindow：output 路径和覆盖复选框
- AdvancedPanel：所有高级参数（`_loading` 守卫）
- SignatureTab：所有签名参数（`_loading` 守卫）
- LogoTab：Logo 配置（`_loading` 守卫）

### 7.5 线程生命周期管理

**统一模式**：
```python
# 创建线程
thread = SomeThread(parent=self)
thread.some_signal.connect(self._handler)
thread.finished.connect(self._on_thread_finished)
thread.finished.connect(thread.deleteLater)
self._thread = thread
thread.start()

# 结束处理
def _on_thread_finished(self):
    sender = self.sender()
    if sender is self._thread:  # sender 守卫
        self._thread = None  # 清空 Python 引用
```

**为什么需要 sender 守卫**：
- 防止"旧线程比新线程晚发 finished"的竞争条件
- 避免误清空刚创建的 self._thread

**应用场景**：
- ProcessThread（批处理）
- PreviewRenderThread（预览渲染）
- ThumbLoaderThread（缩略图加载）

---

## 8. 错误处理与用户反馈

### 8.1 错误分类体系

```python
class Severity(StrEnum):
    INFO = "info"       # 跳过 / 取消等正常状态
    WARNING = "warning" # 处理器运行错误（可恢复）
    ERROR = "error"     # 资源错误（单文件不可恢复）
    FATAL = "fatal"     # 配置错误（整批不可恢复）
```

**错误类别映射**：
| error_kind | 严重度 | 示例 |
|-----------|--------|------|
| config | FATAL | 处理器未找到、配置键缺失 |
| resource | ERROR | 字体缺失、Logo 缺失、exiftool 失败 |
| processor | WARNING | 某个滤镜执行失败 |
| unknown | WARNING | 未分类异常 |

### 8.2 用户友好消息模板

```python
MESSAGES = {
    "ProcessorNotFoundError": {
        "title": "未找到处理器",
        "tip": "处理器 '{key}' 未在注册表中找到，请检查模板配置。",
    },
    "ResourceNotFoundError": {
        "title": "资源缺失",
        "tip": "找不到资源文件 '{path}'（类型：{kind}）。请检查路径是否正确。",
    },
    "ExifToolError": {
        "title": "EXIF 工具异常",
        "tip": "调用 exiftool 失败（返回码 {returncode}）：{stderr}",
    },
    # ...
}
```

**设计原则**：
- **纯逻辑层**：不依赖 PyQt，便于单元测试和替代展示后端
- **i18n-ready**：所有面向用户的字符串集中在 MESSAGES 表
- **上下文填充**：用 str.format 填充具体错误上下文

### 8.3 错误展示策略

**批量处理结果对话框**：
```
┌─────────────────────────────────────────┐
│  [图标]  完成（部分失败）                │
├─────────────────────────────────────────┤
│ 成功 8，失败 2                          │  ← headline
├─────────────────────────────────────────┤
│ 错误分类：资源缺失×2                     │  ← informativeText
├─────────────────────────────────────────┤
│ • [IMG_001.jpg] 资源缺失：找不到资源文件  │  ← detailedText
│   'fonts/NotoSans.ttf'（类型：font）。   │
│ • [IMG_002.jpg] 资源缺失：找不到资源文件  │
│   'logos/canon.png'（类型：logo）。      │
│ ...（另 0 条）                          │
├─────────────────────────────────────────┤
│              [确定]                      │
└─────────────────────────────────────────┘
```

**设计亮点**：
- **分级展示**：图标 + 标题 + 摘要 + 详情
- **错误聚合**：按类型计数，避免重复
- **样本展示**：前 5 条，超出显示 "...（另 N 条）"
- **文件名提取**：只显示文件名，不暴露完整路径（隐私保护）

### 8.4 空状态与边界情况

| 场景 | 处理方式 | UI 反馈 |
|------|---------|---------|
| 未选择文件点击 START | QMessageBox.warning | "请先选择图片" |
| 配置生成失败 | QMessageBox.warning | "配置生成失败: {e}" |
| 已有任务运行中 | QMessageBox.warning | "已有处理任务在运行" |
| 输出已存在且不覆盖 | 跳过该文件 | file_done 信号标记失败 |
| EXIF 读取失败 | 构造 FATAL summary | "读取 EXIF 失败" |
| 预览渲染失败 | 显示错误文字 | "（渲染失败）⚠ {reason}" |
| 字体文件不存在 | 回退到空（继承） | 预览显示 "继承" |

---

## 9. 性能与响应式设计

### 9.1 多线程架构

```
主线程 (UI)
├── ThumbContainer ── ThumbLoaderThread（缩略图加载）
├── PreviewPanel ──── PreviewRenderThread（预览渲染）
└── MainWindow ────── ProcessThread（批处理）
    └── ProcessPoolExecutor（多进程并行）
```

**线程隔离原则**：
- **UI 操作只在主线程**：所有 QWidget 操作通过 Signal 回传
- **图像处理在后台线程**：避免阻塞 UI
- **多进程绕过 GIL**：CPU 密集型处理使用 ProcessPoolExecutor

### 9.2 小批量优化

```python
SMALL_BATCH_THRESHOLD = 3

if len(files) < 3:
    # 串行处理：避免进程池启动开销
    for task in tasks:
        process_one(task)
else:
    # 并行处理：ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=...) as pool:
        ...
```

**为什么 3 是阈值**：
- 进程池启动开销（fork/spawn + 序列化）约 100-500ms
- 单张处理时间约 1-3s
- 3 张以下串行更快，3 张以上并行收益超过开销

### 9.3 EXIF 批量读取优化

```python
# 主进程一次性批量读取
exif_map = get_exif_batch(self.files)

# 传递给每个 worker，避免 N 次 fork exiftool
pre_loaded_exif_map={f: exif_map.get(f, {}) for f in files_to_process}
```

**收益**：
- 100 张图片：从 100 次 exiftool fork → 1 次批量读取
- 显著减少 I/O 和进程开销

### 9.4 图像 I/O 安全

```python
def load_image_safely(path):
    """立即加载并复制图像，释放文件句柄。"""
    with Image.open(path) as src:
        src.load()
        return src.copy()
```

**解决的问题**：
- 大批量处理时 "Too many open files" 错误
- Windows 文件锁定问题（无法删除正在处理的文件）

### 9.5 响应式布局策略

| 窗口宽度 | 布局行为 |
|---------|---------|
| < 450px | 达到最小宽度，水平滚动 |
| 450-580px | 左列收缩，配置面板内表单换行（WrapLongRows） |
| 580-800px | 标准布局，配置抽屉舒适 |
| > 800px | 左列扩展，配置抽屉更宽 |
| 展开预览 | 主窗口宽度 += 预览宽度(1.5×) |

**响应式组件**：
- **QFormLayout + WrapLongRows**：窄窗口下 label 自动换行，不被截断
- **QScrollArea**：内容超出时纵向滚动，不出现横向溢出
- **QHBoxLayout + stretch**：输入框自适应，按钮固定宽度

---

## 10. UX 设计决策分析

### 10.1 为什么默认展开配置抽屉？

**Phase 6.10 决策**：`_expanded = True`

**理由**：
- 新用户首次打开需要立即看到水印配置入口
- 折叠状态（`▶ 设置`）对新用户不直观，可能找不到配置
- 工具类应用用户目标明确（来加水印的），不需要"简洁首页"
- 最小高度 660px 已考虑展开后的空间需求

### 10.2 为什么预览侧栏默认折叠？

**理由**：
- 预览需要消耗 CPU（渲染管道执行）
- 新用户先需要理解基本流程（选图 → 配置 → START）
- 预览是高级功能，按需展开符合渐进披露原则
- `▸` 按钮明确提示"显示实时预览"

### 10.3 为什么用字符图标而非 SVG？

**图标清单**：
- `▶`/`▼`：折叠/展开
- `↖`/`↗`/`↙`/`↘`：四角方向
- `↑`/`↓`：字段排序
- `×`：删除
- `⚙`：详情设置
- `⤺`：重置
- `⟳`：刷新
- `📁`：打开文件夹
- `▸`/`◂`：预览切换

**理由**：
- 无需打包图标资源，减少发布包体积
- 跨平台一致（不依赖系统图标主题）
- 暗色主题下 Unicode 字符对比度足够
- 开发迭代快，无需设计师参与

### 10.4 为什么缩略图固定 100×75px？

**理由**：
- 3:4 比例与常见照片比例接近
- 100px 宽度在 3 列网格中总宽 ≈ 316px + 间距，适合最小窗口 450px
- 75px 高度 × 2 行 = 150px + 间距，容器固定 170-200px
- Cover 裁切保证视觉统一，不拉伸变形

### 10.5 为什么签名使用 9 宫格 + 偏移而非直接坐标？

**签名定位模型**：
```
位置 = 9宫格锚点 + (margin_x, margin_y)
```

**理由**：
- 不同尺寸照片的直接坐标意义不同（100px 在大图和小图中位置不同）
- 9 宫格提供语义化位置（"正中心"、"右下"）
- 偏移是相对于锚点的有符号像素值，微调更直观
- 签名大小使用"占短边比例"，自适应不同尺寸

### 10.6 为什么处理中禁用配置面板？

```python
def _set_processing_state(self, processing: bool):
    self.config_drawer.setEnabled(not processing)
    self.thumb_container.setEnabled(not processing)
    self.preview_sidebar.setEnabled(not processing)
    ...
```

**理由**：
- 避免处理过程中修改配置导致"当前处理的是什么配置"的困惑
- 防止用户在处理中点击 START 启动重复任务
- 配置抽屉标题栏保持可点击（用户可查看但不可修改）

### 10.7 为什么输出路径用模式字符串而非固定目录？

```python
path: str = "{source_dir}/output"  # 默认模式
```

**支持的变量**：
- `{source_dir}`：源文件所在目录
- `{filename}`：源文件名（不含扩展名）

**理由**：
- 批量处理时通常希望输出到每个源文件同级目录
- 模式字符串比固定路径更灵活
- 用户可自定义为固定路径（如 `/Users/xxx/Desktop/output`）

---

## 11. 可改进空间与建议

### 11.1 已识别的问题

| 问题 | 当前状态 | 建议 |
|------|---------|------|
| 无首次使用引导 | 新用户面对空状态和展开的配置面板可能不知所措 | 添加简单的引导提示（如"1. 选择图片 → 2. 配置水印 → 3. 点击 START"） |
| 预览失败无重试 | 预览渲染失败只显示错误文字 | 添加"重试"按钮或自动重试机制 |
| 无撤销/重做 | 用户误删字段或误改配置无法恢复 | 引入 QUndoStack（已在 Backlog 中） |
| 配置面板纵向过长 | 4 个 CornerSection + 3 个 Tab 内容较多 | 考虑添加"快速预设"下拉，一键切换常用配置 |
| 无批量导入配置 | 用户无法保存/加载多套水印风格 | 模板导入/导出功能（Phase 8 计划中） |
| 错误提示不够具体 | "配置生成失败"等提示缺少具体指导 | 在错误消息中增加"如何解决"的建议 |
| 无处理历史 | 用户无法查看之前处理过的文件 | 添加简单的处理日志或历史记录 |

### 11.2 可访问性 (A11y) 改进

| 方面 | 当前状态 | 建议 |
|------|---------|------|
| 键盘导航 | 基本支持 Tab 切换 | 添加快捷键（如 Ctrl+O 打开文件、Ctrl+R 刷新预览、Esc 取消） |
| 屏幕阅读器 | 未测试 | 添加 QLabel 的 buddy 关系、QGroupBox 的标题描述 |
| 高对比度 | 暗色主题固定 | 支持系统高对比度模式或提供浅色主题 |
| 字体缩放 | 跟随系统 | 验证 125%/150% 缩放下的布局完整性 |

### 11.3 国际化 (i18n) 准备

当前代码已做的准备：
- `FieldDef.label_zh` 字段预留
- `MESSAGES` 错误消息表集中管理
- 所有用户可见字符串集中在各自模块

还需完成：
- 引入 Qt 的 `QTranslator` 机制
- 所有字符串标记为 `self.tr()`
- 提取 `.ts` 文件供翻译

### 11.4 移动端/触控适配

当前问题：
- 按钮/控件尺寸基于桌面鼠标设计（28px 高度对触控偏小）
- 滚轮保护在触控设备上无意义
- 右键菜单在触控设备上难以触发

建议：
- 检测触控设备，自动增大触控目标至 44×44px
- 为缩略图添加长按菜单替代右键
- 支持手势操作（如滑动删除缩略图）

---

## 附录 A：组件交互矩阵

| 组件 | 用户操作 | 直接响应 | 信号发出 | 信号订阅者 | 副作用 |
|------|---------|---------|---------|-----------|--------|
| ThumbContainer | 点击空状态 | 打开文件对话框 | file_added | MainWindow → AppState.add_files | 启动缩略图加载线程 |
| ThumbContainer | 拖拽文件 | 接受路径 | file_added | MainWindow → AppState.add_files | 同上 |
| ThumbContainer | 右键缩略图 | 显示上下文菜单 | file_removed | MainWindow → AppState.remove_file | 更新网格 |
| ChipRowWidget | 下拉改字段 | 更新 chip.field_id | changed | CornerSection → _on_chip_changed | push to state → autosave + preview |
| ChipRowWidget | 点击 ⚙ | 打开 ChipDetailPopup | - | - | 编辑 custom_text |
| ChipRowWidget | 点击 ↑/↓ | 交换位置 | move_left/right | CornerSection → 重排 | push to state |
| ChipRowWidget | 点击 × | 删除字段 | delete | CornerSection → 移除 | push to state |
| CornerSection | 点击 + | 添加字段 | - | - | push to state |
| CornerSection | 改分隔符 | 更新 separator | - | - | push to state |
| CornerSection | 改字号 | 更新 font_size | - | - | push to state |
| CornerSection | 点击标题 | 折叠/展开 | - | - | 无数据变化 |
| LogoTab | 改模式/位置 | 更新 LogoConfig | - | - | push to state |
| LogoTab | 选颜色 | 打开 QColorDialog | - | - | push to state |
| SignatureTab | 改任何字段 | 更新 AdvancedConfig | - | - | push to state |
| AdvancedPanel | 改任何字段 | 更新 AdvancedConfig | - | - | push to state |
| AdvancedPanel | 点击恢复默认 | QMessageBox 确认 | - | - | state.reset_to_defaults() |
| MainWindow | 点击 START | 启动 ProcessThread | - | - | 禁用控件，显示进度 |
| MainWindow | 点击 取消 | 取消线程 | - | - | 恢复控件状态 |
| MainWindow | 点击 预览切换 | 展开/折叠侧栏 | - | - | 调整窗口宽度 |
| PreviewPanel | 配置变化 | 500ms debounce | - | - | 启动 PreviewRenderThread |
| AppState | 任何数据变化 | - | *_changed | 多个订阅者 | 300ms debounce → autosave |

---

## 附录 B：文件与 UI 组件映射

| 文件 | 核心组件 | 职责 |
|------|---------|------|
| `gui/main_window.py` | MainWindow, CollapsibleConfigPanel | 窗口框架、组件组装、信号连接 |
| `gui/models.py` | AppState, FieldChip, CornerConfig, LogoConfig, AdvancedConfig, OutputConfig | 状态管理、持久化、信号发射 |
| `gui/config_panel.py` | ConfigPanel, CornerSection, ChipRowWidget, ChipDetailPopup, LogoTab, SignatureTab | 水印配置 UI、字段编辑、Logo/签名设置 |
| `gui/advanced_panel.py` | AdvancedPanel, CollapsibleGroup | 全局参数、可折叠分组、危险操作 |
| `gui/preview_panel.py` | PreviewPanel, PreviewRenderThread | 实时预览、后台渲染、debounce |
| `gui/thumb_grid.py` | ThumbContainer, ThumbLoaderThread | 缩略图网格、文件拖拽、异步加载 |
| `gui/process_thread.py` | ProcessThread | 批处理线程、EXIF 批量读取、进度回传 |
| `gui/template_assembler.py` | state_to_processors | 状态到处理器配置的正向转换 |
| `gui/error_presenter.py` | BatchSummary, PresentedError, Severity | 错误分类、消息格式化、汇总 |
| `gui/styles.py` | get_stylesheet | QSS 暗色主题、全局样式 |
| `gui/font_selector.py` | FontSelector | 字体选择、实时预览、文件夹打开 |
| `gui/font_preview.py` | FontPreview | PIL 字体预览图生成 |
| `gui/logo_dialog.py` | LogoDialog | 品牌 Logo 替换管理 |
| `gui/field_registry.py` | FieldRegistry, FieldDef | 字段元信息、多索引查询 |
| `gui/wheel_guard.py` | guard_wheel, guard_wheel_for_children | 滚轮事件拦截、防误触 |

---

*报告结束*
