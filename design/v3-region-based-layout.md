# V3 Region-Based Layout / 当前架构说明

状态：已实现，当前主线。

V3 的目标是把水印从 V1/V2 的固定四角模板，升级为声明式 Region / Slot / Content 架构，同时保证前端预览和后端输出使用一致的布局语义。

## 架构分层

```text
Config Layer
  WatermarkConfigV3 / schemas_v3.py
      ↓
Layout Layer
  layoutEngine.ts / layout_engine.py
      ↓ LayoutResult
Render Layer
  WatermarkCanvasV3.tsx / processor/v3_watermark.py
```

原则：

- Layout engine 只计算位置、尺寸和顺序。
- Renderer 只按 `LayoutResult` 绘制，不再自行计算坐标。
- Canvas 与 PIL 使用统一坐标系：左上角为原点，X 向右，Y 向下。
- API 只接受 V3 payload；旧 V1/V2 config 返回 `410 legacy_config_removed`。

## 核心模型

```text
WatermarkConfigV3
  ├─ canvas
  ├─ defaults
  └─ regions[]
       ├─ footer-bar
       ├─ side-edge
       └─ free
            └─ slots{}
                 └─ content + style
```

### Region

- `footer-bar`：底部水印条，使用固定槽位。
- `side-edge`：图片主体左右侧边信息。
- `free`：自由定位区域，目前应作为高级/实验能力，不应直接暴露给普通用户。

### Slot

Region 内的具体承载位置。例如 `footer-bar` 支持：

- `left-logo`
- `left-top`
- `left-bottom`
- `center`
- `right-top`
- `right-bottom`
- `right-logo`

### Content

- `text`：字段 chip 组合。
- `logo`：品牌 Logo。
- `signature`：签名图。

### Style

Slot 级样式，可覆盖全局默认值：

- 字号或字号比例。
- size reference。
- 颜色。
- 字体。
- 粗细。
- 行高。

## 关键文件

| 层 | 文件 | 说明 |
|---|---|---|
| Config | `web_frontend/src/v3Types.ts` | 前端类型与预设 |
| Config | `web_api/schemas_v3.py` | API 严格校验 |
| Layout | `web_frontend/src/v3_layout/layoutEngine.ts` | 前端布局计算 |
| Layout | `shared/v3_layout/layout_engine.py` | 后端布局计算 |
| Render | `web_frontend/src/WatermarkCanvasV3.tsx` | Canvas 预览 |
| Render | `processor/v3_watermark.py` | PIL 输出 |
| API | `web_api/main.py` / `web_api/processing.py` | 上传、预览、处理 |

## 已移除内容

V1/V2 的以下内容已从主线删除：

- 四角配置前端：`HomePage.tsx`、`WatermarkCanvas.tsx`、`InspectorPanel.tsx` 等。
- 旧 schema 和 assembler：`web_api/schemas.py`、`shared/watermark_schema.py`、`shared/processor_assembler.py`。
- V2 SPA route：`/v2`。
- 线上 `/tools/watermark-v2/`。
- V1 活跃 API 反代。

## 当前问题

底层架构已经足够灵活，但普通用户控制面过于接近底层模型，容易导致：

- 元素重叠。
- 元素越界。
- 用户理解成本过高。
- 模板被破坏后难以恢复。

下一阶段见：`design/v3-control-surface-guardrails.md`。
