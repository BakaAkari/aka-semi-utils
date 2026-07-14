# V3 控制面收敛与布局防护设计

## 目标

将 V3 从「灵活的 Region/Slot/Content 结构编辑器」收敛为「模板驱动 + 安全微调 + 高级结构编辑」的产品化控制面。

普通用户主界面只作为模板和参数选择，不直接暴露 Region/Slot/offset/anchor 等底层结构。

## 设计原则

1. 底层架构保持不变：Region/Slot/Content + layout engine 不改。
2. 产品化控制面分为两层：主界面（普通用户）和高级设置（进阶用户）。
3. 主界面的每个参数都必须能够安全地映射到预设的 Region/Slot 上，不产生结构破坏。
4. 布局引擎输出要求 layout diagnostics：重叠、越界、空内容、资源缺失等问题必须可检测、可报告、可恢复。
5. 高级设置保留结构编辑自由度，但需加约束与重置机制。

## 主界面控制项

主界面只展示高频、低风险、直接影响成片的参数。

| 分类 | 控件 | 映射到预设 | 默认值 |
|---|---|---|---|
| 模板 | 水印预设（默认/极简/圆角卡片/左右居中） | 替换 `regions` | 默认排版 |
| 内容 | 相机型号开关 | 启用/禁用 `camera_model` chip | 开 |
| 内容 | 镜头型号开关 | 启用/禁用 `lens_model` chip | 开 |
| 内容 | 焦距开关 | 启用/禁用 `focal_length` chip | 开 |
| 内容 | 光圈开关 | 启用/禁用 `aperture` chip | 开 |
| 内容 | 快门开关 | 启用/禁用 `shutter` chip | 开 |
| 内容 | ISO 开关 | 启用/禁用 `iso` chip | 开 |
| 内容 | 日期开关 | 启用/禁用 `datetime` chip | 关 |
| 内容 | 作者开关 | 启用/禁用 `artist` chip | 关 |
| 内容 | 地理位置开关 | 启用/禁用 `gps` chip | 关 |
| 内容 | 全局自定义文本 | `custom_text` | 空 |
| 样式 | 整体大小 | 调整所有字号比例，联动底栏高度 | 中 |
| 样式 | 颜色模式 | 黑 / 白 / 暖灰 / 自动 | 黑 |
| 样式 | 底栏密度 | 紧凒 / 标准 / 宽松 | 标准 |
| 资源 | 自定义 Logo | 填充到 `right-logo` 或 `left-logo` | 无（自动） |
| 资源 | 签名 | 填充到 `free` region 签名 slot | 无 |
| 操作 | 恢复当前预设 | 重置为当前预设的原始配置 | - |
| 操作 | 打开高级设置 | 切换面板 | - |

### 整体大小映射

主界面提供 `small` / `medium` / `large` 三档，每个预设在底层定义三组参数：

- `font_size_multiplier`: 所有字号比例统一乘以的系数
- `footer_height_multiplier`: 底栏高度系数（基于短边比例）
- `logo_size_multiplier`: Logo 大小系数
- `signature_size_multiplier`: 签名大小系数

如果该预设没有定义某档位，则使用中档缺省。

### 颜色模式映射

- `black`: 文字 `#222222`，Logo `#D8D8D6`，背景 `#FFFFFF`
- `white`: 文字 `#F5F5F5`，Logo `#FFFFFF`，背景 `#1A1A1A`
- `warm-gray`: 文字 `#3A3532`，Logo `#B0A89A`，背景 `#EDEAE6`
- `auto`: 根据图片类型自动（保留，先使用 `black` 缺省）

### 底栏密度映射

- `compact`: 底栏高度系数 0.08
- `standard`: 底栏高度系数 0.10
- `loose`: 底栏高度系数 0.13

联动底栏 margin bottom 跟随密度：
- compact: 0.5x
- standard: 1.0x
- loose: 1.5x

## 高级设置控制项

高级设置默认收起，点击主界面「高级」按钮后展开。

| 区块 | 保留的控件 | 隐藏或约束的控件 |
|---|---|---|
| 区域列表 | Region 启用/禁用 | 删除 Region 按钮（只允许临时隐藏） |
| 底栏 | Slot 内容、字号、颜色 | 新增 slot / 删除 slot 隐藏 |
| 侧边 | 边缘、对齐、宽度 | 新增文本行隐藏 |
| 自由 | 锚点、偏移 | 新增签名 隐藏 |
| 画布 | 边距、背景色、圆角 | 无 |
| 默认样式 | 字体、加粗 | 无 |
| 操作 | 重置为默认 | 无 |

高级设置不得在普通用户主界面直接展示，避免误触。

## Layout Diagnostics

布局诊断作为 layout engine 的拓展，输出每次计算的 `diagnostics` 数组。

### 检测类型

| 类型 | ID | 严重级别 | 说明 |
|---|---|---|---|
| 重叠 | `overlap` | error | 两个元素 rect 交叠 |
| 越界 | `out-of-bounds` | error | 元素超出 canvas |
| 空内容 | `empty-enabled-slot` | warning | slot 启用但内容为空 |
| 缺资源 | `missing-resource` | warning | 自定义 logo/签名未上传 |
| 字号过大 | `font-too-large` | warning | 字号超过 slot 高度 |
| 区域溢出 | `region-overflow` | warning | side-edge 超过短边 50% |
| 进入主体 | `covers-image-body` | warning | free region 签名落在图片主体区域 |

### 诊断响应

- **error**: 主界面顶部红色警告，显示冲突列表；高级设置中对应 slot 标红；禁止点击 `Process` / `Process All`。
- **warning**: 主界面顶部浅色提示；高级设置中对应 slot 标黄。
- 所有诊断都附带「恢复当前预设」快捷操作，让用户一键回到安全状态。

### 重叠检测逻辑

对 `LayoutResult.elements` 中每两个元素，检查：

```
not (a.rect.right <= b.rect.left or
     a.rect.left >= b.rect.right or
     a.rect.bottom <= b.rect.top or
     a.rect.top >= b.rect.bottom)
```

如果交叠，输出两个元素 id，类型 `overlap`。

### 越界检测逻辑

对每个元素：

```
if el.rect.left < 0 or el.rect.top < 0 or
   el.rect.right > canvas.w or el.rect.bottom > canvas.h:
    out-of-bounds
```

### 空内容检测逻辑

- text slot: `enabled=true` 但 `content.chips.length === 0` 或所有 chip 都是 `empty`。
- logo slot: `enabled=true` 但 `content.path === ''`。
- signature slot: `enabled=true` 但 `content.path === ''`。

### 缺资源检测逻辑

前端暂时无法知道后端资源是否真实存在，因此：

- 前端：只检测 `path` 是否为空。
- 后端：在渲染时检查资源文件是否存在，不存在时抛出 422 错误并带上资源 id。

## 实现步骤

1. 在 `v3Types.ts` 中新增主界面控制的类型：`MainControlConfig` 和 `PresetSize`/`PresetColor`/`PresetDensity`。
2. 在 `v3Presets.ts` 中为每个预设新增 `mainControls` 和 `sizeVariants`。
3. 新增 `V3MainControls.tsx`：渲染主界面控制面板。
4. 重构 `InspectorPanelV3.tsx`：
   - 主界面显示 `V3MainControls`；
   - 点击「高级」后展开原有 Region/Slot/Free 编辑器；
   - 隐藏新增 Region、删除 Region、新增 Slot/Line/Signature 等危险入口；
   - 高级区域内显示布局诊断结果，标红冲突 slot。
5. 在 `layoutEngine.ts` / `layout_engine.py` 中新增 `diagnoseLayout`。
6. 在 `V3HomePage` / `TopBar` 中使用 diagnostics 结果，控制 `Process` 按钮和顶部警告。
7. 更新后端渲染时资源缺失检测，返回 422 带资源 id。
8. 补充测试到 `tests/unit/test_v3_layout` 和 `tests/unit/test_v3_api_integration.py`。
9. 跑 `ruff check` / `pytest` / `npm run build` / 线上验证。

## 验收标准

- [ ] 主界面只有预设、内容开关、大小、颜色、密度、自定义文本、Logo/签名，没有 Region/Slot/Free 编辑。
- [ ] 点击「高级」后可以看到原有结构编辑，但新增/删除 Region 和随意新增 Slot/Line/Signature 的入口已隐藏。
- [ ] 布局诊断能检测重叠、越界、空内容、缺资源，主界面显示警告。
- [ ] 存在重大布局问题时，`Process` / `Process All` 被禁止，直到用户恢复预设或修复。
- [ ] 所有预设切换后，输出不再产生重叠或越界。
- [ ] `ruff check .` 、`pytest` 、`npm run build` 通过，线上可以正常预览、处理、下载。

## 影响范围

- 不修改 V3 底层类型和布局引擎算法，只是在其上添加产品层。
- 不影响后端 API 接口结构，只可能新增 422 错误类型。
- 旧的 Region/Slot/Free 配置仍然保留在 JSON 中，高级用户仍可编辑。
