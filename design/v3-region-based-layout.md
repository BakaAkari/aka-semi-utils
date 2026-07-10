# V3 水印系统重构设计 — Region-Based Declarative Layout

> 状态：设计草案  
> 目标：彻底解决 V2 中布局与渲染耦合、前后端坐标语义不一致、模式扩展困难的问题  
> 原则：与图像解耦、声明式配置、前后端共享布局计算

---

## 1. 现有架构的五大瓶颈

### 1.1 语义耦合：`bottom_margin` 身兼四职

```
bottom_margin 同时控制：
├── 画布扩展量（canvas_height = img.height + bottom_margin）
├── 字号计算基准（font_size = bottom_margin * ratio / 0.12）
├── 文本定位基准（footer_top = top_margin + img.height）
└── 垂直居中 margin（elem_margin = (bottom_margin - elem_height) / 2）
```

**后果**：修改底栏高度会连锁改变字号、改变间距、改变定位基准。用户无法理解"为什么我改底栏高度，文字也变大了"。

### 1.2 双名同义：`footer_height_px` ≡ `bottom_margin`

前端配置叫 `footer_height_px`，传到后端变成 `bottom_margin`，两者是同一概念的不同名字。代码中需要显式转换：

```python
# shared/processor_assembler.py:275-276
if config.advanced.footer_height_px > 0:
    node["bottom_margin"] = config.advanced.footer_height_px
```

### 1.3 坐标语义不一致

| 维度 | 前端 Canvas | 后端 PIL |
|---|---|---|
| 文本定位基准 | `fillText(x, y)` 中 `y` 是 **文本基线** | `paste(img, (x, y))` 中 `y` 是 **图片左上角** |
| 四角 Y 计算 | 从 `canvas_bottom` 向上锚定 | 从 `canvas_bottom` 向上锚定（相同公式） |
| 绘制偏移 | 下方两角额外 `-fz`（遗留 Bug） | 无偏移 |
| 结果 | 下方两角整体上移一个字号 ❌ | 正确位置 ✅ |

**根本问题**：两个渲染器使用不同的坐标语义，但没有任何抽象层保证它们对同一套 `(x, y)` 产生相同的视觉结果。

### 1.4 硬编码模式：corners / sides 无法扩展

当前只有两种布局模式：

```typescript
type LayoutMode = 'corners' | 'sides';
```

用户无法：
- 在底部栏中间添加文本
- 在图片顶部添加标题
- 混合使用（如底部栏放参数 + 左侧放日期）
- 自定义区域位置

### 1.5 渲染与布局强耦合

前端 `WatermarkCanvas.tsx` 中，布局计算和 Canvas 绘制纠缠在一起：

```typescript
// 计算 + 绘制混在一起
const lbY = canvasH - elemMargin - lbH;        // 布局计算
ctx.fillText(block.lines[0], x, y + fz * 0.8); // 绘制（含隐式偏移）
```

后端 `WatermarkFilter` 同样：

```python
# 计算
lb_y = canvas_height - elem_margin - lb.height
# 绘制
canvas.paste(corners["left_bottom"], (l_x, layout["lb_y"]))
```

两段代码独立完成计算+绘制，没有任何共享的"布局结果"数据结构。

---

## 2. V3 架构核心：三层分离

```
┌─────────────────────────────────────────────────────────────┐
│                     配置层 (Config Layer)                      │
│  WatermarkConfig → 声明式区域列表 → 纯数据结构                 │
├─────────────────────────────────────────────────────────────┤
│                     布局层 (Layout Layer)                      │
│  compute_layout(config, image_w, image_h) → LayoutResult     │
│  ├─ 前端: TypeScript 实现                                     │
│  └─ 后端: Python 实现（同一套单元测试验证）                    │
├─────────────────────────────────────────────────────────────┤
│                     渲染层 (Render Layer)                      │
│  前端: Canvas 2D 按 LayoutResult 绘制                         │
│  后端: PIL 按 LayoutResult paste/composite                    │
└─────────────────────────────────────────────────────────────┘
```

**关键原则**：布局层输出的是"每个元素在画布上的绝对位置和尺寸"，渲染层只负责"把内容放到指定位置"。

---

## 3. 数据模型重构

### 3.1 统一坐标系

```
画布坐标系（Canvas Coordinate System）
├── 原点 (0, 0)：画布左上角
├── X 轴：向右为正
├── Y 轴：向下为正
└── 单位：像素（pixel）

元素定位五元组：(x, y, width, height, anchor)
├── x, y：锚点所在位置
├── width, height：元素内容尺寸（由布局引擎计算）
└── anchor：元素相对于 (x, y) 的对齐方式

anchor 取值（与 CSS transform-origin 语义一致）：
  top-left     top-center     top-right
  middle-left  middle-center  middle-right
  bottom-left  bottom-center  bottom-right
```

### 3.2 区域（Region）抽象

画布上的空间被划分为若干 **Region**，每个 Region 是画布上的一个矩形区域：

```typescript
interface Region {
  id: string;           // 唯一标识，如 "footer", "side-left"
  bounds: Rect;         // 在画布上的绝对矩形 {x, y, w, h}
  type: RegionType;     // 区域类型，决定内部布局策略
  elements: Element[];  // 区域内的水印元素
}

type RegionType = 
  | 'footer-bar'      // 底部水平栏，内部多槽位
  | 'side-edge'       // 图片主体垂直边缘
  | 'free';           // 自由定位（签名等）
```

**内置区域类型**：

#### `footer-bar` — 底部水印条

```
┌────────────────────────────────────────────────────────────┐
│ 照片主体区域                                                │
├────────────────────────────────────────────────────────────┤
│  [left-logo] │ [lt]          [center-logo]          [rt] │ [right-logo] │
│              │ [lb]                               [rb] │              │
└────────────────────────────────────────────────────────────┘
              ↑ footer-bar 区域（bounds = 底部栏矩形）

内部槽位（slots）：
  left-logo, left-top, left-bottom, center, right-top, right-bottom, right-logo
```

每个 slot 有自己的 `slot_anchor`（在 slot 内的对齐方式）和 `content`。

#### `side-edge` — 图片主体垂直边缘

```
┌────┬──────────────────────────────────────────┬────┐
│    │                                          │    │
│ LT │                                          │ RT │
│    │          照片主体区域                     │    │
│ LB │                                          │ RB │
│    │                                          │    │
└────┴──────────────────────────────────────────┴────┘
↑ side-left 区域              ↑ side-right 区域

内部布局：垂直堆叠，每行一个文本块
对齐方式：start（靠边缘）/ center（区域内居中）/ end（远离边缘）
```

### 3.3 元素（Element）统一抽象

所有水印元素（文本、Logo、签名）使用统一的 Element 接口：

```typescript
interface Element {
  id: string;
  type: 'text' | 'logo' | 'signature' | 'divider';
  region_id: string;        // 所属区域
  slot_id?: string;         // 区域内的槽位（footer-bar 用）
  content: TextContent | LogoContent | SignatureContent;
  style: StyleConfig;
  
  // 由布局引擎填充
  layout?: ComputedLayout;  // {x, y, w, h, anchor}
}

interface TextContent {
  chips: FieldChip[];
  separator: string;
}

interface StyleConfig {
  font_size?: number;           // 绝对像素值（最高优先级）
  font_size_ratio?: number;     // 相对于 size_reference 基准的比例
  size_reference?: 'region_height' | 'short_edge' | 'long_edge';  // 默认 'region_height'
  color: string;
  font_family: string;
  bold: boolean;
  line_height?: number;         // 行高倍数，默认 1.2
}
```

**`size_reference` 的语义**：

| 值 | 基准 | 适用场景 |
|---|---|---|
| `region_height` | 区域/槽位自身高度 | footer-bar 内元素（默认） |
| `short_edge` | 照片主体短边 | side-edge 文本、自由定位元素 |
| `long_edge` | 照片主体长边 | 特殊需求（极少使用） |

**示例：竖屏照片的左侧水印**

```typescript
// 竖屏 9:16(1080×1920)，左侧水印
{
  id: 'side-left',
  type: 'side-edge',
  edge: 'left',
  width: { mode: 'short_edge_ratio', value: 0.12 },  // 区域宽 = 短边 12% = 130px
  content: {
    chips: [
      { field_id: 'make' },
      { field_id: 'camera_model' },
      { field_id: 'focal_length' },
      { field_id: 'aperture' },
    ],
    separator: ' / ',
  },
  style: {
    font_size_ratio: 0.035,         // 3.5%
    size_reference: 'short_edge',   // ← 以短边为基准
    color: '#222222',
  },
}
```

效果：
- 横屏 16:9(1920×1080)：字号 = 1080 × 0.035 = **38px**
- 竖屏 9:16(1080×1920)：字号 = 1080 × 0.035 = **38px**
- 两者在各自画面中**视觉大小相同** ✅

如果没有 `size_reference: 'short_edge'`，竖屏 side-edge 的字号会是 `1920 × 0.035 = 67px`，文本过大 ❌
  font_size?: number;       // 绝对像素值（优先）
  font_size_ratio?: number; // 相对于区域高度的比例（fallback）
  color: string;
  font_family: string;
  bold: boolean;
  line_height?: number;     // 行高倍数，默认 1.2
}
```

### 3.4 新 WatermarkConfig

```typescript
interface WatermarkConfig {
  // 画布全局设置
  canvas: {
    margins: { top: number; right: number; bottom: number; left: number };
    background: string;
    border_radius: number;
    shadow?: {
      radius: number;
      color: string;
    };
  };
  
  // 区域列表（有序，后覆盖前）
  regions: RegionConfig[];
  
  // 全局样式默认值
  defaults: StyleConfig;
}

interface RegionConfig {
  id: string;
  type: RegionType;
  enabled: boolean;
  
  // footer-bar 特有
  slots?: Record<string, SlotConfig>;
  
  // side-edge 特有
  edge?: 'left' | 'right';
  width?: { mode: 'pixel' | 'short_edge_ratio'; value: number };  // 区域宽度
  alignment?: 'start' | 'center' | 'end';
  
  // free 特有
  edge?: 'left' | 'right';
  alignment?: 'start' | 'center' | 'end';
  
  // free 特有
  anchor?: string;     // 九宫格锚点（以照片主体区域为参考）
  offset_x?: number;   // 相对于锚点的偏移
  offset_y?: number;
  offset_unit?: 'pixel' | 'short_edge_ratio';  // 默认 'short_edge_ratio'
  // 以照片主体短边为基准的比例，确保 16:9 和 9:16 视觉一致
  // 例如 offset_x = 0.05 → 16:9 图片(1920x1080) = 54px, 9:16(1080x1920) = 54px
}
}

interface SlotConfig {
  enabled: boolean;
  content?: TextContent;
  style?: Partial<StyleConfig>;
  logo?: LogoContent;   // 如果是 logo slot
}
```

### 3.5 与图像完全解耦

**关键设计**：水印配置不再包含任何与图像相关的隐式计算。

```typescript
// ❌ V2：字号依赖图像尺寸
const fontSize = Math.max(8, Math.round(bottomM * ratio / 0.12));

// ✅ V3：字号声明式，布局引擎负责适配
const style = { font_size_ratio: 0.4 };  // "占区域高度的 40%"
// layout_engine 在运行时根据区域高度计算实际像素值
```

图像只影响：
1. 画布尺寸（`canvas.width = img.width + margins.left + margins.right`）
2. 照片主体区域的尺寸和位置

水印元素的位置、大小、样式**完全由配置决定**，与图像内容无关。

---

## 4. 布局引擎设计

### 4.1 纯函数接口

```typescript
// 前端
function computeLayout(
  config: WatermarkConfig,
  imageWidth: number,
  imageHeight: number,
): LayoutResult;

// 后端（Python）
def compute_layout(
    config: WatermarkConfig,
    image_width: int,
    image_height: int,
) -> LayoutResult:
```

### 4.2 LayoutResult 结构

```typescript
interface LayoutResult {
  canvas: { width: number; height: number };
  image_rect: Rect;        // 照片主体在画布上的位置
  regions: ComputedRegion[];
  elements: ComputedElement[];
}

interface ComputedElement {
  id: string;
  type: string;
  rect: Rect;              // 绝对坐标 {x, y, w, h}
  anchor: Anchor;          // 对齐方式
  content: any;            // 原始内容
  style: StyleConfig;      // 最终样式（含计算后的 font_size）
}
```

### 4.3 布局计算流程

```
Step 1: 计算画布尺寸
  canvas_w = image_w + margins.left + margins.right
  canvas_h = image_h + margins.top + margins.bottom

Step 2: 计算区域 bounds
  对每个 region：
    - footer-bar: bounds = 画布底部矩形
    - side-edge: bounds = 图片主体左/右边缘矩形
    - free: bounds = 由 anchor + offset 决定

Step 3: 计算区域内槽位 bounds
  对 footer-bar 的每个 slot：
    - 按水平分布计算每个 slot 的 x, w
    - 上下两行按垂直分布计算 y, h

Step 4: 计算元素尺寸
  对每个 text 元素：
    - 测量文本内容 → 原始尺寸
    - 应用 font_size（绝对值或 ratio 计算）
    - 最终尺寸 = 测量结果 × 缩放因子

Step 5: 计算元素绝对位置
  对每个元素：
    - 取 slot/region 的 bounds 作为参考
    - 根据 anchor + offset 计算最终 (x, y)
    - 存储到 LayoutResult
```

### 4.4 字号计算策略

字号计算使用**区域高度**作为基准，而区域高度本身由**照片主体短边比例**决定。这保证了：
- 不同比例图片（16:9 vs 9:16）的水印元素在视觉上大小一致
- 字号与图像尺寸解耦，但视觉比例保持稳定

```typescript
function resolveFontSize(
  style: StyleConfig,
  referenceHeight: number,   // 区域/槽位高度（由短边比例计算）
): number {
  if (style.font_size !== undefined && style.font_size > 0) {
    return style.font_size;  // 用户显式指定像素值
  }
  if (style.font_size_ratio !== undefined && style.font_size_ratio > 0) {
    return Math.max(8, Math.round(referenceHeight * style.font_size_ratio));
  }
  return Math.max(8, Math.round(referenceHeight * 0.3));  // 默认 30%
}
```

**关键设计**：
- `referenceHeight` 来自区域高度（如 footer-bar 高度）
- 区域高度来自 `canvas.margins.bottom`（可以是固定像素或短边比例）
- 当使用短边比例时：`referenceHeight = min(image_w, image_h) * ratio`
- 这确保了 16:9 和 9:16 图片的字号视觉效果一致

### 4.4a 区域高度计算策略

区域高度支持两种模式：

```typescript
interface RegionHeightConfig {
  mode: 'pixel' | 'short_edge_ratio';
  value: number;
}

function computeRegionHeight(
  config: RegionHeightConfig,
  imageWidth: number,
  imageHeight: number,
): number {
  if (config.mode === 'pixel') {
    return config.value;  // 固定像素，无视图像尺寸
  }
  // 按照片主体短边比例，确保不同比例图片视觉一致
  const shortEdge = Math.min(imageWidth, imageHeight);
  return Math.max(40, Math.round(shortEdge * config.value));
}
```

**示例**：
- 16:9 图片 1920×1080，footer 高度 `short_edge_ratio = 0.12` → 高度 = 129px
- 9:16 图片 1080×1920，footer 高度 `short_edge_ratio = 0.12` → 高度 = 129px
- 两者在各自画面中的**视觉占比相同**（都是短边的 12%）

### 4.4b 自由定位（Free Region）的视觉一致性

自由定位区域（如签名、自由 Logo）使用**照片主体短边比例**作为偏移单位，确保不同比例图片的视觉位置一致：

```typescript
interface FreeRegionConfig {
  anchor: string;           // 九宫格锚点，以照片主体区域为参考
  offset_x: number;
  offset_y: number;
  offset_unit: 'pixel' | 'short_edge_ratio';  // 默认 'short_edge_ratio'
}

function computeFreePosition(
  config: FreeRegionConfig,
  imageRect: Rect,           // 照片主体在画布上的位置
  elementSize: Size,         // 元素自身尺寸
): Point {
  // 锚点：照片主体区域九宫格交点
  const anchorX = imageRect.x + imageRect.w * anchorCol(config.anchor);
  const anchorY = imageRect.y + imageRect.h * anchorRow(config.anchor);
  
  // 偏移量：按照片主体短边比例计算
  const shortEdge = Math.min(imageRect.w, imageRect.h);
  const offsetUnit = config.offset_unit === 'pixel' ? 1 : shortEdge;
  
  return {
    x: anchorX + config.offset_x * offsetUnit,
    y: anchorY + config.offset_y * offsetUnit,
  };
}
```

**关键设计**：
- 锚点基准是**照片主体区域**（不是画布），确保水印不覆盖 margin 区域
- 偏移单位是**照片主体短边比例**，确保 16:9 和 9:16 的视觉偏移量相同
- 元素最终位置 = 锚点 + 偏移，然后应用 `anchor` 对齐修正

**示例：签名在右下角偏移**（`anchor='bottom_right'`, `offset_x=0.05`, `offset_y=0.05`）
- 16:9 图片 1920×1080：签名中心 = (1920 - 54, 1080 - 54) = (1866, 1026)
- 9:16 图片 1080×1920：签名中心 = (1080 - 54, 1920 - 54) = (1026, 1866)
- 两者在各自画面中都是"右下角偏内 5% 短边"，视觉一致 ✅

**与 V2 的对比**：
V2 的签名定位使用绝对像素（`margin_x: 0`）或比例（`margin_x` 范围 -0.5~0.5），但比例基准是照片主体**宽/高**（不是短边），导致 16:9 和 9:16 的签名位置差异巨大。V3 统一使用短边比例，彻底解决。

### 4.4c 尺寸比例（Logo、签名）

Logo 和签名的大小同样使用短边比例，确保不同比例图片的视觉大小一致：

```typescript
function resolveElementSize(
  config: ElementSizeConfig,
  imageRect: Rect,
): Size {
  const shortEdge = Math.min(imageRect.w, imageRect.h);
  
  if (config.mode === 'pixel') {
    return { width: config.width, height: config.height };
  }
  
  // 按短边比例
  const targetSize = shortEdge * config.size_ratio;
  
  if (config.type === 'logo') {
    // Logo 按原始宽高比缩放
    const aspectRatio = config.original_width / config.original_height;
    return {
      width: Math.round(targetSize * aspectRatio),
      height: Math.round(targetSize),
    };
  } else if (config.type === 'signature') {
    // 签名统一以短边比例缩放
    return {
      width: Math.round(targetSize),
      height: Math.round(targetSize * config.aspect_ratio),
    };
  }
  
  return { width: Math.round(targetSize), height: Math.round(targetSize) };
}
```

**示例**：Logo 高度 `size_ratio = 0.10`（短边的 10%）
- 16:9 图片 1920×1080：Logo 高度 = 108px
- 9:16 图片 1080×1920：Logo 高度 = 108px
- 两者在各自画面中视觉大小相同 ✅

```
一致性测试策略：
├─ 共享测试用例集（YAML/JSON）
│   每个用例 = (config, image_w, image_h) → 期望的 LayoutResult
├─ 前端单元测试：TS computeLayout 输出与期望对比
├─ 后端单元测试：Python compute_layout 输出与期望对比
└─ 交叉验证测试：随机配置下，前后端输出逐像素对比
```

---

## 5. 渲染层设计

### 5.1 前端 Canvas 渲染器

```typescript
function renderCanvas(
  canvas: HTMLCanvasElement,
  layout: LayoutResult,
  image: HTMLImageElement | null,
): void {
  const ctx = canvas.getContext('2d')!;
  
  // 1. 绘制画布背景
  drawBackground(ctx, layout.canvas);
  
  // 2. 绘制照片主体（或占位）
  drawImage(ctx, image, layout.image_rect);
  
  // 3. 按 z-index 顺序绘制所有元素
  for (const el of layout.elements) {
    drawElement(ctx, el);
  }
  
  // 4. 应用全局效果（圆角裁剪、阴影等）
  applyGlobalEffects(ctx, layout.canvas);
}

function drawElement(ctx: CanvasRenderingContext2D, el: ComputedElement): void {
  const { x, y, w, h } = el.rect;
  
  switch (el.type) {
    case 'text':
      // anchor 决定 (x,y) 是元素的哪个角
      const { drawX, drawY } = applyAnchor(x, y, w, h, el.anchor);
      ctx.font = `${el.style.bold ? '700' : '400'} ${el.style.font_size}px ${el.style.font_family}`;
      ctx.fillStyle = el.style.color;
      ctx.fillText(el.content.text, drawX, drawY);
      break;
    case 'logo':
      // Logo 按计算后的 rect 绘制
      break;
  }
}
```

**关键改进**：渲染器只负责"把内容画到指定矩形"，不参与任何位置计算。所有位置来自 `LayoutResult`。

### 5.2 后端 PIL 渲染器

```python
def render_pil(layout: LayoutResult, image: Image.Image) -> Image.Image:
    canvas = Image.new("RGBA", (layout.canvas.width, layout.canvas.height), bg_color)
    
    # 粘贴照片主体
    canvas.paste(image, (layout.image_rect.x, layout.image_rect.y))
    
    # 按顺序绘制所有元素
    for el in layout.elements:
        if el.type == "text":
            text_img = render_text(el)  # 独立文本渲染
            dx, dy = apply_anchor(el.rect, el.anchor)
            canvas.paste(text_img, (dx, dy), mask=text_img)
        elif el.type == "logo":
            logo_img = load_logo(el.content.path)
            logo_img = logo_img.resize((el.rect.w, el.rect.h))
            canvas.paste(logo_img, (el.rect.x, el.rect.y), mask=logo_img)
    
    return canvas
```

### 5.3 渲染与布局的边界

| 职责 | 布局引擎 (compute_layout) | 渲染器 (render) |
|---|---|---|
| 计算画布尺寸 | ✅ | ❌ |
| 计算区域/槽位位置 | ✅ | ❌ |
| 计算元素绝对坐标 | ✅ | ❌ |
| 计算字号（像素值） | ✅ | ❌ |
| 绘制像素 | ❌ | ✅ |
| 文本测量（w/h） | ✅（提供接口） | 前端: ctx.measureText / 后端: PIL getbbox |

**注意**：文本测量需要知道实际渲染后的尺寸。前端用 `ctx.measureText()`，后端用 `font.getbbox()`。两者可能有几像素的差异（字体渲染引擎不同）。

**解决方案**：
- 布局引擎不依赖精确文本尺寸进行位置计算
- 槽位/区域采用"弹性布局"：先分配空间，再在其中居中/靠齐
- 文本尺寸只影响元素自身的 `w, h`，不影响其他元素的位置

---

## 6. 预设配置的重定义

### 6.1 预设即 Region 组合

```typescript
// 预设1: 默认排版（底部栏四角 + 右侧 Logo）
const presetDefault: WatermarkConfig = {
  canvas: {
    margins: { top: 0, right: 0, bottom: 80, left: 0 },
    background: '#FFFFFF',
  },
  regions: [
    {
      id: 'footer',
      type: 'footer-bar',
      enabled: true,
      slots: {
        'left-top': {
          enabled: true,
          content: { chips: [{field_id: 'make'}, {field_id: 'camera_model'}], separator: ' ' },
          style: { font_size_ratio: 0.45, color: '#222222' },
        },
        'left-bottom': {
          enabled: true,
          content: { chips: [{field_id: 'focal_length'}, {field_id: 'aperture'}, {field_id: 'shutter'}, {field_id: 'iso'}], separator: ' ' },
          style: { font_size_ratio: 0.35, color: '#222222' },
        },
        'right-top': { enabled: false },
        'right-bottom': { enabled: false },
        'center': { enabled: false },
        'left-logo': { enabled: false },
        'right-logo': {
          enabled: true,
          logo: { type: 'auto', color: '#D8D8D6' },
        },
      },
    },
  ],
};

// 预设2: 极简参数（底部栏仅右下参数）
const presetMinimal: WatermarkConfig = {
  canvas: {
    margins: { top: 0, right: 0, bottom: 90, left: 0 },
    background: '#FFFFFF',
  },
  regions: [
    {
      id: 'footer',
      type: 'footer-bar',
      enabled: true,
      slots: {
        'left-top': { enabled: false },
        'left-bottom': { enabled: false },
        'right-top': { enabled: false },
        'right-bottom': {
          enabled: true,
          content: { chips: [{field_id: 'focal_length'}, {field_id: 'aperture'}, {field_id: 'shutter'}, {field_id: 'iso'}], separator: ' ' },
          style: { font_size_ratio: 0.32, color: '#2C2C2C' },
        },
        'center': { enabled: false },
        'left-logo': { enabled: false },
        'right-logo': { enabled: false },
      },
    },
  ],
};

// 预设3: 左右居中（图片主体左右边缘）
const presetSides: WatermarkConfig = {
  canvas: {
    margins: { top: 0, right: 0, bottom: 80, left: 0 },
    background: '#FFFFFF',
  },
  regions: [
    {
      id: 'footer',
      type: 'footer-bar',
      enabled: true,
      slots: {
        'left-logo': {
          enabled: true,
          logo: { type: 'auto', color: '#D8D8D6' },
        },
        'center': { enabled: false },
        'right-logo': { enabled: false },
      },
    },
    {
      id: 'side-left',
      type: 'side-edge',
      edge: 'left',
      enabled: true,
      alignment: 'start',
      content: { chips: [...], separator: ' ' },
      style: { font_size_ratio: 0.5 },
    },
    {
      id: 'side-right',
      type: 'side-edge',
      edge: 'right',
      enabled: false,
    },
  ],
};
```

### 6.2 预设的灵活性

用户可以：
1. 选择预设作为起点
2. 启用/禁用任意 slot
3. 修改任意 slot 的内容和样式
4. 添加新的 region（如顶部标题栏）
5. 保存为自定义预设

---

## 7. 迁移路径

### Phase 1: 基础设施（1-2 天）

1. **创建 `shared/layout_engine.py`**
   - 纯函数 `compute_layout(config, image_w, image_h) -> LayoutResult`
   - 不包含任何 PIL/Canvas 依赖
   - 写单元测试

2. **创建 `web_frontend/src/layoutEngine.ts`**
   - TypeScript 翻译版
   - 共享同一套单元测试用例（YAML 格式）

3. **创建 `LayoutResult` 类型定义**
   - 前后端共享的序列化格式

### Phase 2: 前端重构（2-3 天）

1. 重写 `WatermarkCanvas.tsx`
   - 调用 `computeLayout()` 获取布局结果
   - 按 `LayoutResult` 绘制，不再内联计算

2. 重写配置面板
   - 从 corners/sides 切换为 Region/Slot 模型
   - InspectorPanel 改为 Region 列表 + Slot 编辑器

3. 迁移预设配置
   - 现有 3 个预设映射为新格式

### Phase 3: 后端重构（2-3 天）

1. 重写 `WatermarkFilter`
   - 调用 `compute_layout()` 获取布局结果
   - 按 `LayoutResult` 进行 paste/composite

2. 重写 `shared/processor_assembler.py`
   - 从 WatermarkConfig 直接生成 LayoutResult，不再中转 processor JSON
   - 或者：保留现有 processor 管线，但让 WatermarkFilter 使用新的 layout engine

3. 更新 API schemas
   - 新的 `WatermarkPayload` 对应 Region/Slot 模型

### Phase 4: 一致性验证（1-2 天）

1. 编写交叉验证测试
   - 随机生成 100 个配置
   - 对比前后端 `LayoutResult` 是否逐元素一致

2. 视觉回归测试
   - 固定测试图片 + 固定配置
   - 对比前后端输出图片的像素差异

### Phase 5: 废弃 V2 兼容层（可选）

- 保留 `config_v2_to_v3()` 迁移函数
- 3 个月后移除

---

## 8. 关键设计决策记录

| 决策 | 选项 A | 选项 B（选中） | 理由 |
|---|---|---|---|
| 坐标系 | 多种坐标系（像素/比例/相对） | 统一像素坐标系 | 简单、无歧义、易于调试 |
| 布局计算位置 | 服务端渲染预览 | 前后端各自实现 | 预览延迟不可接受，各自实现可接受 |
| 字号控制 | 全局比例（V2 方式） | 区域/槽位级比例 | 解耦、灵活 |
| 区域类型 | 完全自由（任意矩形） | 内置类型 + 自由扩展 | 内置类型覆盖 95% 场景，自由扩展兜底 |
| Logo 处理 | 作为特殊文本元素 | 独立的 Logo 元素 | Logo 有独立的加载、缩放、定位逻辑 |

---

## 9. 与现有代码的对比

| 维度 | V2 | V3 |
|---|---|---|
| 布局模式 | 硬编码 2 种（corners/sides） | 声明式 Region/Slot，可扩展 |
| 字号计算 | `bottom_margin * ratio / 0.12` | `region_height * font_size_ratio` |
| 坐标语义 | 前端 baseline vs 后端 top-left | 统一：像素坐标 + anchor |
| 前后端一致性 | 两套独立计算逻辑 | 共享 layout engine + 交叉测试 |
| 配置结构 | 扁平（corners + sides + advanced） | 分层（canvas → regions → slots → elements） |
| 与图像耦合 | 字号依赖图像短边 | 字号依赖区域高度（区域高度可独立配置） |
| 扩展性 | 新增模式需改核心代码 | 新增 Region 类型即可 |

---

## 10. 待讨论问题

1. **文本测量差异**：Canvas `measureText` 与 PIL `getbbox` 可能有 1-3px 差异，是否需要接受这种差异，还是设计"测量无关"的布局策略？

2. **free 区域的安全边界**：自由定位的元素如何防止溢出画布？是 clip 还是自动调整？

3. **Region 重叠处理**：当多个 Region 的 bounds 重叠时，元素的 z-index 如何决定？

4. **动画/过渡**：配置变化时，是否需要在 Canvas 预览中添加平滑过渡动画？
