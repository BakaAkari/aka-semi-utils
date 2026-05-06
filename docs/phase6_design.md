# Phase 6 设计文档 — 全面重构 GUI 配置体验

> **目标**：解决两个核心痛点
> 1. **配置不持久** — `AppState.save_to_disk / load_from_disk` 是 stub，关闭程序后水印配置全部丢失
> 2. **GUI 交互差** — 4-Tab 角落编辑器无空间映射；字段写死中文枚举；`CornerConfig.font/color` 形同摆设；无实时预览
>
> **方案**：C-Track 全面重构 = chip 拖拽 + 每角独立字体色 + JSON 模板双向同步 + 自动保存 + 2×2 网格 + 实时预览

---

## 1. 现状诊断

### 1.1 配置丢失链路

[`gui/models.py`](gui/models.py:202)：

```python
def save_to_disk(self, project_root: Path):
    data = {
        "template": self.current_template,
        "output": {...},
        # TODO: 保存更多字段     ← 四角配置 / Logo / 自定义文本 / 高级 全部没保存
    }
```

[`gui/models.py`](gui/models.py:187) 的 `load_from_disk` 同样只读 `template + output`，启动时永远走 `_reset_defaults()`。

### 1.2 字段定义三处重复

| 位置 | 内容 | 风格 |
|------|------|------|
| [`gui/config_panel.py`](gui/config_panel.py:86) | `["相机型号", "镜头型号", ...]` | 写死中文 QComboBox |
| [`gui/template_assembler.py`](gui/template_assembler.py:156) | `_FIELD_TEMPLATES = {"相机型号": "{{ exif.CameraModelName ...}}"}` | Jinja 模板 |
| [`core/template_builder.py`](core/template_builder.py:84) | `_build_source_segment(source)` 用 `exif:CameraModelName` 风格 source-id | 独立词汇表 |

新增字段需在 3 处同步修改 → 极易遗忘。

### 1.3 `CornerConfig.font / color` 已废弃

[`gui/config_panel.py`](gui/config_panel.py:122) 注释：
> `字体和颜色从全局 AppState 获取（CornerConfig 中的 font/color 已废弃）`

但 [`gui/models.py`](gui/models.py:14) 中字段还在 → 数据模型与运行行为不一致。

### 1.4 4-Tab 无空间感知

[`gui/config_panel.py`](gui/config_panel.py:296) 用 QTabWidget 平铺 `左上 / 左下 / 右上 / 右下`，用户必须想象空间映射。

### 1.5 配置抽屉默认折叠

[`gui/main_window.py`](gui/main_window.py:41) `CollapsibleConfigPanel._expanded = False`，新用户找不到配置入口。

---

## 2. 新数据模型

### 2.1 `FieldChip` — 单个字段单元

```python
@dataclass
class FieldChip:
    """单个水印字段（chip）。"""
    field_id: str           # FieldRegistry key, e.g. "camera_model"
    custom_text: str = ""   # field_id == "custom" 时使用
    font: Optional[str] = None    # None → 继承角配置 → 全局
    color: Optional[str] = None   # 同上
```

### 2.2 `CornerConfig` 重构

```python
@dataclass
class CornerConfig:
    chips: List[FieldChip] = field(default_factory=list)  # 替代 fields: List[str]
    separator: str = " · "
    font: Optional[str] = None    # 角级覆盖；None → 继承全局
    color: Optional[str] = None   # 角级覆盖；None → 继承全局
```

> **样式继承链**：`FieldChip.color` → `CornerConfig.color` → `AdvancedConfig.global_color`
> 未来若想"整角统一色"只设 `CornerConfig.color`；若想"个别字段高亮"再覆盖 `FieldChip.color`。

### 2.3 兼容老配置

`load_from_disk` 检测旧格式 `fields: List[str]` 并自动迁移：
```python
if "fields" in corner_data:
    chips = [FieldChip(field_id=field_label_to_id(label)) for label in corner_data["fields"]]
```

---

## 3. `FieldRegistry` — 单一事实源

### 3.1 数据结构

```python
# gui/field_registry.py（新文件）
@dataclass(frozen=True)
class FieldDef:
    field_id: str           # 内部稳定 ID，e.g. "camera_model"
    label_zh: str           # GUI 显示名，e.g. "相机型号"
    jinja_template: str     # e.g. "{{ exif.CameraModelName|default('-') }}"
    source_id: str          # template_builder 风格，e.g. "exif:CameraModelName"
    category: str = "exif"  # exif / custom / param / signature

FIELD_REGISTRY: Dict[str, FieldDef] = {
    "camera_model":  FieldDef("camera_model", "相机型号", "{{ exif.CameraModelName|default('-') | replace('_','') }}", "exif:CameraModelName"),
    "lens_model":    FieldDef("lens_model", "镜头型号", "{{ exif.LensModel|default('-') }}", "exif:LensModel"),
    "datetime":      FieldDef("datetime", "拍摄时间", "{{ exif.DateTimeOriginal|default('-') }}", "exif:DateTimeOriginal"),
    "params":        FieldDef("params", "参数", "{{ params }}", "param:full"),
    "focal_length":  FieldDef("focal_length", "焦距", "{{ exif.FocalLength|default('-') }}", "exif:FocalLength"),
    "aperture":      FieldDef("aperture", "光圈", "{{ exif.FNumber|default('-') }}", "exif:FNumber"),
    "shutter":       FieldDef("shutter", "快门", "{{ exif.ExposureTime|default('-') }}", "exif:ExposureTime"),
    "iso":           FieldDef("iso", "ISO", "ISO {{ exif.ISO|default('-') }}", "exif:ISO"),
    "custom":        FieldDef("custom", "自定义文本", "", "custom:text", category="custom"),
}
```

### 3.2 取代位置

| 旧位置 | 新行为 |
|--------|--------|
| [`gui/config_panel.py`](gui/config_panel.py:86) | `[f.label_zh for f in FIELD_REGISTRY.values()]` |
| [`gui/template_assembler.py`](gui/template_assembler.py:156) | `FIELD_REGISTRY[chip.field_id].jinja_template` |
| [`core/template_builder.py`](core/template_builder.py:84) | 接受 `source_id`，从 registry 反查 jinja |

### 3.3 扩展性

新增字段（如"GPS 坐标"）只需在 `FIELD_REGISTRY` 加一行，全 GUI 立即可用。

---

## 4. `CornerEditor` 重做：chip 拖拽

### 4.1 视觉

```
┌─ 左上 ────────────────────────────────────────┐
│  [相机型号 ✕] [镜头型号 ✕] [+ 添加字段 ▼]      │
│  分隔符: [ · ]   字体: [继承]  颜色: [继承]    │
└──────────────────────────────────────────────┘
```

### 4.2 核心组件

```python
class FieldChipWidget(QFrame):
    """单个 chip — 显示 label + 删除按钮 + 双击编辑色/字体。
    支持鼠标拖拽（QDrag MIME=application/x-akafield）。"""
    chip_changed = pyqtSignal()
    chip_deleted = pyqtSignal()

class ChipFlowLayout(QLayout):
    """横向自动换行 layout（参考 PyQt FlowLayout 官方示例）。"""

class CornerEditor(QWidget):
    """单角编辑器 — chips + 分隔符 + 角级 font/color 覆盖。"""
    def _on_chip_dropped(self, src_idx, dst_idx): ...   # 重排
```

### 4.3 拖拽语义

* **同 corner 内拖拽** → 重排
* **跨 corner 拖拽** → 复制（按住 Shift = 移动）
* **从"+ 添加字段"下拉** → 创建新 chip 追加到末尾

---

## 5. 2×2 角落网格

替代 `QTabWidget`，用 `QGridLayout(2, 2)`：

```
┌───────────────┬───────────────┐
│  [左上 corner] │  [右上 corner] │
├───────────────┼───────────────┤
│  [左下 corner] │  [右下 corner] │
└───────────────┴───────────────┘
```

每格 = 一个 [`gui/advanced_panel.CollapsibleGroup`](gui/advanced_panel.py:14)（复用现有控件），标题 `左上`/`左下`/`右上`/`右下`，内含 `CornerEditor`。

---

## 6. 实时预览面板

### 6.1 数据流

```
state.*_changed ─┐
                 ├─→ debounce(300ms) ─→ render_first_image() ─→ QLabel(QPixmap)
state.files_changed ─┘
```

### 6.2 实现要点

* 选 `state.files[0]`（无文件 → 显示提示）
* 用 [`processor.core.start_process`](processor/core.py:552) 渲染到 `tempfile`，读回 `QPixmap`
* 缩放至预览框宽度 `<= 360px`，保持纵横比
* 渲染在 `QThread` 中跑，避免阻塞 UI
* 失败时显示错误文字（不弹框）

### 6.3 位置

主窗口右侧新增 `PreviewDock`（`QDockWidget`），可关闭。

---

## 7. 自动保存（debounce）

### 7.1 信号汇聚

```python
# AppState.__init__
self._save_timer = QTimer(self)
self._save_timer.setSingleShot(True)
self._save_timer.setInterval(300)
self._save_timer.timeout.connect(lambda: self.save_to_disk(self._project_root))

# 任何 *_changed 信号都重启计时器
for sig in [self.files_changed, self.output_changed, self.watermark_changed,
            self.advanced_changed, self.template_changed]:
    sig.connect(lambda *_: self._save_timer.start())
```

### 7.2 完整保存格式

```jsonc
// config/user.json (v2)
{
  "version": 2,
  "template": "标准水印",
  "output": { "path": "...", "override": false },
  "corners": {
    "left_top":   { "chips": [{"field_id": "camera_model"}], "separator": " · ", "font": null, "color": null },
    "left_bottom":{ ... },
    "right_top":  { ... },
    "right_bottom": { ... }
  },
  "logo":        { "enabled": true, "position": "left", "color": "#D8D8D6", "custom_path": "" },
  "custom_text": "",
  "advanced":    { "global_font": "...", "global_color": "#242424", ... }
}
```

向后兼容：缺字段时走 `_reset_defaults()` 默认值；老格式 `fields: List[str]` 自动迁移。

---

## 8. JSON 模板双向同步

### 8.1 当前状态

[`gui/template_assembler.py`](gui/template_assembler.py:67) 已有 `state_to_processors / processors_to_state`，但 `processors_to_state` 没把 chip 化的新模型考虑进去。

### 8.2 改造点

* `_build_watermark_config(state)` 改用 `chip.field_id` → `FIELD_REGISTRY[id].jinja_template`
* `_apply_watermark_config` 反向：从 jinja 字符串里反查 registry → 还原 `FieldChip`
  - 若找不到匹配（用户手改了 jinja）→ 创建 `FieldChip(field_id="custom", custom_text=jinja_raw)`
* 新增 `gui/json_template_editor.py` —— 一个简易 JSON 编辑器 Tab：
  - 左：QTextEdit (JSON)，右：当前 GUI 状态预览
  - "应用"按钮：JSON 解析 → `processors_to_state` → AppState
  - "导出"按钮：`state_to_processors` → 写 QTextEdit
  - diff 警告：若 GUI ↔ JSON 不一致，显示 `⚠ 未同步`

### 8.3 防丢失策略

任何 `processors_to_state` 失败 / 字段无法识别都进 `state.last_template_warnings: List[str]`，UI 顶部显示横幅。

---

## 9. UX 兜底

| 项 | 现状 | 改造 |
|----|------|------|
| 默认折叠抽屉 | [`gui/main_window.py`](gui/main_window.py:41) `_expanded=False` | 改为 `True` |
| 无"恢复默认" | 手动 | 抽屉顶部加 `🔄 恢复默认` |
| 模板应用无提示 | 静默 | 应用后底部状态栏显示 `已应用模板：xxx`，3 秒淡出 |
| 字段名硬编码中文 | i18n 不友好 | `FieldDef.label_zh` 留接口位（暂不上 i18n） |

---

## 10. 实施顺序（11 个 sub-phase）

| # | 名称 | 文件 | 风险 |
|---|------|------|------|
| 6.0 | 设计文档（本文档） | `docs/phase6_design.md` | 低 |
| 6.1 | `save_to_disk / load_from_disk` 全字段持久化 + 老格式迁移 | `gui/models.py` | **中**（迁移逻辑） |
| 6.2 | debounce QTimer 自动保存 | `gui/models.py` | 低 |
| 6.3 | `FieldChip` + `CornerConfig` 重构 + 单测 | `gui/models.py`, `tests/unit/test_models.py` | **中**（破坏现有调用方） |
| 6.4 | `FieldRegistry` + 替换 3 处重复 | `gui/field_registry.py`, `gui/template_assembler.py`, `core/template_builder.py`, `gui/config_panel.py` | **高**（影响 template_builder 测试） |
| 6.5 | `FieldChipWidget` + `ChipFlowLayout` + 新 `CornerEditor` | `gui/config_panel.py`（重写） | **高**（PyQt 拖拽容易踩坑） |
| 6.6 | 2×2 网格替换 Tab | `gui/config_panel.py` | 低 |
| 6.7 | 实时预览 dock + 渲染线程 | `gui/preview_panel.py`（新） | **中**（QThread + tempfile） |
| 6.8 | JSON 模板编辑器 + 双向同步告警 | `gui/json_template_editor.py`（新）, `gui/template_assembler.py` | **中** |
| 6.9 | 全套测试 + ruff + mypy | `tests/unit/test_field_registry.py`, `tests/unit/test_models_persistence.py` 等 | 低 |
| 6.10 | UX 兜底 — 默认展开 / 恢复默认 / 模板提示横幅 | `gui/main_window.py`, `gui/config_panel.py` | 低 |

---

## 11. 验收标准

* [ ] **Persistence**：手动改任意字段 → 关程序 → 重启，配置完整恢复
* [ ] **Auto-save**：手改字段 300ms 内 `config/user.json` 文件写入（用 `stat -f %m` 验证）
* [ ] **Drag-Drop**：左上 chip 拖到左下，鼠标松开后字段确实出现在左下
* [ ] **Per-Chip Color**：单 chip 设红色，其他保持继承 → 渲染图中只该字段是红
* [ ] **JSON Sync**：JSON 编辑器改 jinja → 应用 → GUI chip 反映；GUI 改 chip → 导出 → JSON 内容更新
* [ ] **Tests**：`uv run pytest -q` 全绿（≥ 296 + 新增 ≥ 20）
* [ ] **Lint**：`uv run ruff check .` 干净；`uv run mypy gui/ core/ processor/` 干净
* [ ] **Backward**：旧 `user.json`（只有 `template` + `output`）能加载不崩溃

---

## 12. 关键风险与对冲

| 风险 | 对冲 |
|------|------|
| `processors_to_state` 老模板兼容破坏 | 保留旧 `_FIELD_TEMPLATES` 反查表作为 fallback；保留 `tests/integration/test_pipeline_engine.py` 现有断言 |
| PyQt6 QDrag 在 macOS 偶发不发 dropEvent | 同时支持点击"上下移动箭头"作为备用排序方式 |
| `FieldChip.font` 继承链导致 watermark filter 渲染分支爆炸 | `_build_watermark_config` 把每 chip 解析成独立 `TextSegment`，沿用 `multi_rich_text` |
| `core/template_builder.py` 的 `source:id` 词汇表已被外部模板使用 | `FieldDef.source_id` 与 jinja 模板**双向映射**，老 source-id 仍能解析 |

---

## 13. 不在本 Phase 范围

* i18n / 英文 GUI
* 字段拖拽到模板预览（直接所见即所得）
* 撤销/重做（QUndoStack）
* 多模板并行编辑

> 这些留待 Phase 7。
