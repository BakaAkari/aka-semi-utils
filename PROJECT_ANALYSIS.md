# aka-semi-utils (极简水印) 项目详细分析

> **版本**: 2.1.8  
> **分析日期**: 2025-07-01  
> **项目路径**: `/Users/baka_akari/code/aka-semi-utils`

---

## 1. 项目概述

### 1.1 项目定位
`aka-semi-utils`（中文名：**极简水印**）是一款面向摄影师的桌面端批量水印处理工具。它基于 **PyQt6** 构建 GUI，使用 **Pillow + numpy** 进行图像处理，通过 **exiftool** 读取照片 EXIF 元数据，实现高度可配置的自动化水印添加流程。

### 1.2 核心功能
- **批量处理**: 支持多文件并行处理，自动回退串行模式（小批量优化）
- **EXIF 驱动水印**: 自动读取相机型号、镜头、焦距、光圈、快门、ISO 等元数据
- **四角水印布局**: 支持四个角落独立配置，每个角可放置多个字段（芯片式布局）
- **Logo 水印**: 支持 3 个 Logo 位置（左上/右上/底部），支持 EXIF 条件匹配自动切换
- **签名水印**: 支持透明背景签名图叠加，智能像素处理（白底透明化、黑白反转、彩色保留）
- **高级滤镜**: 模糊、圆角、阴影、裁剪、缩放、边距、拼接等
- **实时预览**: 处理前可预览效果
- **跨平台**: Windows / macOS / Linux

### 1.3 技术栈

| 层级 | 技术 |
|------|------|
| GUI 框架 | PyQt6 |
| 图像处理 | Pillow (PIL), numpy |
| EXIF 读取 | exiftool (外部二进制) |
| 配置管理 | JSON + INI (混合兼容) |
| 打包发布 | PyInstaller |
| CI/CD | GitHub Actions |
| 包管理 | uv (现代 Python 包管理器) |
| Python 版本 | 3.13 |

---

## 2. 架构设计

### 2.1 整体架构（四层模型）

```
┌─────────────────────────────────────────┐
│  Layer 1: GUI 层 (PyQt6)                │
│  - MainWindow, ConfigPanel, Preview     │
│  - 拖拽文件、进度显示、状态管理            │
├─────────────────────────────────────────┤
│  Layer 2: 状态模型层 (AppState)          │
│  - 单一事实来源 (Single Source of Truth)  │
│  - 自动持久化 (300ms 防抖)                │
├─────────────────────────────────────────┤
│  Layer 3: 处理器管道层 (Processor Pipeline)│
│  - 注册表模式 + AOP 计时                  │
│  - 过滤器、生成器、合并器                 │
├─────────────────────────────────────────┤
│  Layer 4: 核心工具层 (Core Utilities)     │
│  - EXIF 读取、图像 I/O、配置加载          │
│  - 异常体系、性能追踪                     │
└─────────────────────────────────────────┘
```

### 2.2 设计模式应用

| 模式 | 应用位置 | 说明 |
|------|---------|------|
| **注册表模式 (Registry)** | `processor/core.py` | `@register("name")` 装饰器自动注册处理器 |
| **观察者模式 (Observer)** | `gui/models.py` | `AppState` 通过 PyQt Signal 通知 UI 更新 |
| **管道模式 (Pipeline)** | `processor/core.py` | `PipelineEngine` 串联多个处理器节点 |
| **策略模式 (Strategy)** | `processor/filters.py` | 不同过滤器实现相同 `ImageProcessor` 接口 |
| **工厂模式 (Factory)** | `processor/generators.py` | 生成器按需创建图像元素 |
| **模板方法 (Template Method)** | `processor/core.py` | `ImageProcessor` 定义流程，子类实现细节 |
| **单例模式 (Singleton)** | `gui/models.py` | `AppState` 全局唯一实例 |

---

## 3. 模块详细分析

### 3.1 GUI 层 (`gui/`)

#### `main_window.py` — 主窗口控制器
- **职责**:  orchestrate 所有 GUI 组件，管理处理线程生命周期
- **关键类**:
  - `MainWindow`: 主窗口，包含菜单栏、工具栏、中央区域（配置面板 + 预览）
  - `CollapsibleConfigPanel`: 可折叠配置面板，支持动画展开/收起
- **核心流程**:
  1. 文件拖拽 → `AppState.add_files()`
  2. 点击 START → `TemplateAssembler.state_to_processors()` → 创建 `ProcessThread`
  3. `ProcessThread` 运行 `PipelineEngine`
  4. 进度通过 Signal 回传主线程更新 UI

#### `models.py` — 状态管理（项目核心）
- **关键类**: `AppState`
- **设计亮点**:
  - **单一事实来源**: 所有 GUI 状态集中管理，避免数据不一致
  - **Signal 驱动**: `files_changed`, `output_changed`, `watermark_changed`, `advanced_changed`, `state_reloaded`, `progress_changed`
  - **自动持久化**: 300ms 防抖保存到 `config/user.json`
  - **数据类定义**: `FieldChip`, `CornerConfig`, `LogoConfig`, `AdvancedConfig`, `OutputConfig`
- **向后兼容**: 支持从旧版 `config.ini` 迁移配置

#### `config_panel.py` — 水印配置 UI
- **关键组件**:
  - `CornerSection`: 四角配置折叠面板，每个角包含多个 `ChipRowWidget`
  - `ChipRowWidget`: 字段芯片行，支持字段选择、字号、颜色、字体配置
  - `LogoTab`: Logo 设置（位置、缩放、透明度、EXIF 条件匹配）
  - `SignatureTab`: 签名水印设置（位置、缩放、偏移、增强模式）

#### `template_assembler.py` — 状态到管道的转换器
- **职责**: 将 `AppState` 转换为 `PipelineEngine` 可执行的处理器列表
- **映射逻辑**:
  - 高级参数 → 过滤器（margin, rounded_corner, shadow, blur, resize, trim, margin_with_ratio, concat, alignment）
  - 水印配置 → `WatermarkFilter` / `WatermarkWithTimestampFilter`
  - 签名配置 → `SignatureFilter`
  - Logo 配置 → 嵌入水印过滤器

### 3.2 处理器管道层 (`processor/`)

#### `core.py` — 管道引擎核心
- **关键类**:
  - `PipelineContext`: 可变映射，在处理器间传递状态（输入路径、输出路径、图像对象、EXIF 数据等）
  - `ImageProcessor`: 抽象基类，定义 `process(ctx) → ctx` 接口
  - `PipelineEngine`: 构建节点 → 注入初始状态 → 注入 EXIF → 运行 → 保存输出
- **AOP 计时**: 自动记录每个处理器的执行时间，用于性能分析
- **向后兼容**: `start_process()` 函数提供旧版入口

#### `filters.py` — 图像过滤器（最复杂模块）
- **处理器列表**:
  | 处理器 | 功能 | 技术亮点 |
  |--------|------|---------|
  | `BlurFilter` | 高斯模糊 | Pillow `ImageFilter.GaussianBlur` |
  | `ResizeFilter` | 缩放 | 支持长边/短边/百分比模式 |
  | `TrimFilter` | 智能裁剪 | numpy 计算非透明区域 bbox |
  | `MarginFilter` | 固定边距 | 支持四边独立配置 |
  | `MarginWithRatioFilter` | 比例边距 | 基于图像尺寸的百分比边距 |
  | `WatermarkFilter` | 主水印 | **最复杂**，四角文本 + 3 Logo 布局 |
  | `WatermarkWithTimestampFilter` | 时间戳水印 | 在 `WatermarkFilter` 基础上增加时间戳 |
  | `RoundedCornerFilter` | 圆角 | 蒙版实现 |
  | `ShadowFilter` | 阴影 | Alpha 通道渐变衰减 |
  | `CropFilter` | 裁剪 | 支持比例裁剪 |
  | `SignatureFilter` | 签名水印 | **3 类像素处理**：白→透明、黑↔白、彩色保留 |

- **WatermarkFilter 细节**:
  - 支持 4 个角落，每个角可配置多个字段（芯片式布局）
  - 支持 3 个 Logo 位置（左上/右上/底部）
  - 支持 EXIF 条件匹配自动切换 Logo
  - 使用 `RichTextGenerator` / `MultiRichTextGenerator` 生成文本
  - 复杂的对齐和间距计算

- **SignatureFilter 细节** (Phase 26):
  - 3 类像素处理策略：
    1. **白色/近白色** → 完全透明（用于去除白底）
    2. **黑色/近黑色** → 反转为白色（用于黑字签名）
    3. **彩色** → 保留原色（用于彩色签名）
  - 支持位置、缩放、偏移微调

#### `generators.py` — 图像生成器
- **生成器列表**:
  | 生成器 | 功能 |
  |--------|------|
  | `SolidColorGenerator` | 纯色背景 |
  | `GradientColorGenerator` | 渐变背景（numpy 实现 eased 渐变） |
  | `RichTextGenerator` | 富文本渲染（支持多字体、多颜色） |
  | `MultiRichTextGenerator` | 多行富文本 |
  | `ImageLoader` | 图像加载（支持路径/URL） |

#### `mergers.py` — 图像合并器
- `AlignmentMerger`: 对齐合并（支持多种对齐方式）
- `ConcatMerger`: 拼接合并（水平/垂直，支持对齐）

#### `batch.py` — 并行批处理
- **设计亮点**:
  - `BatchTask` / `BatchResultItem` / `BatchResult` 数据类
  - **ProcessPoolExecutor** 并行处理（多进程绕过 GIL）
  - **小批量优化**: `< 3` 文件时自动回退串行（避免进程池开销）
  - **错误分类**: `_classify_error()` 区分文件错误、处理器错误、系统错误
  - **Pickle 安全**: `_to_safe()` 确保跨进程传递的上下文可序列化
  - **进度回调**: 支持实时进度更新和取消操作

#### `perf.py` — 性能追踪
- **关键类**:
  - `PerfRecord`: 单条性能记录（pickle-safe）
  - `BatchPerfReport`: 批次报告（P50/P95/max/mean 统计）
  - `aggregate()`: 聚合多批次报告
  - `measure()`: 上下文管理器，自动计时
- **慢节点警告**: 1000ms 阈值，自动标记慢处理器

### 3.3 核心工具层 (`core/`)

#### `config_loader.py` — 统一配置入口
- **职责**: 整合 `config.ini` + `user.json` 两种配置格式
- **路径常量**: `FONTS_DIR`, `LOGOS_DIR`, `TEMPLATES_DIR`
- **变量替换**: `get_output_folder()` 支持 `{desktop}`, `{pictures}`, `{documents}` 等变量
- **向后兼容**: 保留旧版 `core/configs.py` 的别名

#### `util.py` — EXIF 与文件工具
- **EXIF 读取**:
  - `get_exif()`: 基于 mtime 的 FIFO 缓存（最大 512 条），避免重复调用 exiftool
  - `get_exif_batch()`: 单命令多文件 EXIF 读取（优化批量场景）
  - 使用 subprocess 调用外部 exiftool 二进制
- **文件扫描**: `list_files()` 递归扫描目录
- **格式转换**: `convert_heic_to_jpeg()` HEIC 转 JPEG

#### `image_io.py` — 安全图像 I/O
- **设计目的**: 解决批量处理时的 "too many open files" 问题
- **关键函数**:
  - `load_image_safely()`: 立即加载并复制图像，释放文件句柄
  - `open_image()`: 上下文管理器，懒加载
  - `load_logo()`: 自动转换为 RGBA 模式

#### `exceptions.py` — 异常体系
- **层次结构**:
  ```
  AkaSemiUtilsError
  ├── ConfigError
  │   ├── ConfigKeyError
  │   └── ConfigValueError
  ├── ResourceError
  │   └── ResourceNotFoundError
  └── ProcessorError
      ├── ProcessorNotFoundError
      └── ProcessorRuntimeError
  ```
- **Pickle 安全**: 所有自定义异常支持跨进程序列化

#### `template_builder.py` — 水印配置构建器
- **职责**: 从 `user.json` + `config.ini` 构建水印处理器配置
- **Jinja2 模板**: `_build_source_segment()` 使用 `FieldRegistry` 解析模板
- **多字段处理**: `_build_corner_multi()` 处理多字段角落配置，支持分隔符

#### `jinja2renders.py` — Jinja2 全局函数
- `vw()`: 视口宽度计算
- `vh()`: 视口高度计算
- `auto_logo()`: 基于 EXIF 的 Logo 自动匹配

#### `field_registry.py` — 字段注册表
- **12 个默认字段**:
  | 字段 ID | 中文标签 | 数据源 |
  |---------|---------|--------|
  | camera_model | 相机型号 | EXIF:Model |
  | lens_model | 镜头型号 | EXIF:LensModel |
  | focal_length | 焦距 | EXIF:FocalLength |
  | aperture | 光圈 | EXIF:FNumber |
  | shutter | 快门 | EXIF:ExposureTime |
  | iso | ISO | EXIF:ISO |
  | datetime | 日期时间 | EXIF:DateTimeOriginal |
  | make | 制造商 | EXIF:Make |
  | artist | 艺术家 | EXIF:Artist |
  | gps | GPS | EXIF:GPSInfo |
  | custom_text | 自定义文本 | 用户输入 |
  | empty | 空 | - |
- **多索引支持**: 支持按 `field_id`, `label_zh`, `source_id`, `jinja_template` 查找

---

## 4. 数据流分析

### 4.1 单次处理流程

```
用户操作 (拖拽文件/配置参数)
    ↓
AppState (状态更新, Signal 通知 UI)
    ↓
TemplateAssembler.state_to_processors() (状态 → 处理器列表)
    ↓
PipelineEngine.build_nodes() (构建处理器节点)
    ↓
PipelineEngine.seed_initial_state() (注入初始状态)
    ↓
PipelineEngine.inject_exif() (读取 EXIF 元数据)
    ↓
PipelineEngine.run() (顺序执行处理器)
    │
    ├── Filter 1 (如 ResizeFilter)
    ├── Filter 2 (如 MarginFilter)
    ├── WatermarkFilter (主水印)
    ├── SignatureFilter (签名水印)
    └── ... (其他过滤器)
    ↓
PipelineEngine.save_output() (保存结果)
    ↓
进度 Signal → UI 更新
```

### 4.2 批量处理流程

```
用户选择多个文件
    ↓
BatchTask 创建任务列表
    ↓
判断批量大小:
    ├── < 3 文件: 串行处理 (避免进程池开销)
    └── ≥ 3 文件: ProcessPoolExecutor 并行处理
    ↓
每个工作进程:
    ├── 接收 pickle-safe 上下文 (含 EXIF 数据)
    ├── 独立运行 PipelineEngine
    └── 返回结果或错误
    ↓
主进程聚合结果:
    ├── 成功: 更新进度
    ├── 失败: 错误分类 + 记录
    └── 取消: 终止剩余任务
    ↓
BatchPerfReport 生成性能报告
```

---

## 5. 测试策略

### 5.1 测试覆盖

项目包含约 **30 个测试文件**，覆盖以下维度：

| 测试类型 | 文件示例 | 覆盖内容 |
|---------|---------|---------|
| **单元测试** | `test_models.py` | AppState 持久化、Signal 触发 |
| | `test_field_registry.py` | 字段注册表查找、多索引 |
| | `test_exif_cache.py` | EXIF 缓存 FIFO 行为 |
| | `test_batch_error_classification.py` | 错误分类逻辑 |
| | `test_small_batch_fallback.py` | 小批量回退串行 |
| | `test_processor_schemas.py` | 处理器配置校验 |
| | `test_color_parser.py` | 颜色解析 |
| | `test_jinja2_helpers.py` | Jinja2 函数 |
| | `test_config_loader.py` | 配置加载、变量替换 |
| | `test_image_io.py` | 安全加载、RGBA 转换 |
| | `test_perf.py` | 性能记录、报告聚合 |
| | `test_error_presenter.py` | 错误展示 |
| | `test_exceptions.py` | 异常序列化 |
| | `test_config_unification.py` | 配置合并 |
| | `test_direction_consistency.py` | 方向一致性 |
| | `test_processor_decorator.py` | 注册装饰器 |
| | `test_processor_registry.py` | 注册表功能 |
| | `test_logo_layout.py` | Logo 布局计算 |
| | `test_corner_size_selector.py` | 角落尺寸选择 |
| | `test_chip_migration.py` | 芯片迁移 |
| | `test_signature_filter.py` | 签名过滤器像素处理 |
| **集成测试** | `test_pipeline_engine.py` | 完整管道执行 |
| | `test_batch_parallel.py` | 并行批处理 |
| | `test_exif_sidecar.py` | EXIF 旁路文件 |
| | `test_pipeline_exceptions.py` | 管道异常处理 |
| | `test_batch_perf.py` | 批次性能报告 |

### 5.2 测试设计亮点
- **错误分类测试**: 验证 `_classify_error()` 正确区分文件错误、处理器错误、系统错误
- **Pickle 安全测试**: 验证所有自定义异常和性能记录支持跨进程序列化
- **小批量优化测试**: 验证 `< 3` 文件时正确回退串行模式
- **EXIF 缓存测试**: 验证 mtime 变化和 FIFO 淘汰策略

---

## 6. 构建与部署

### 6.1 打包配置 (`scripts/build.spec`)
- **模式**: Onedir（单目录，非单文件）
- **捆绑资源**:
  - `config/`: 配置文件
  - `static/`: 静态资源（图标等）
  - `exiftool/`: exiftool 二进制
- **发布配置**: 使用 `user.release.json` 重命名为 `user.json`，避免包含开发者个人路径

### 6.2 CI/CD (`.github/workflows/build-release.yml`)
- **触发条件**: Tag 推送
- **构建矩阵**:
  | 平台 | 包格式 | exiftool 安装 |
  |------|--------|---------------|
  | Windows | ZIP | 捆绑 |
  | macOS | tar.gz | `brew install exiftool` |
  | Linux | tar.gz | `apt install exiftool` |
- **流程**:
  1. 安装依赖 (`uv sync`)
  2. PyInstaller 构建
  3. 烟雾测试（验证可执行文件能运行）
  4. 打包 artifact
  5. 创建 GitHub Release

### 6.3 版本同步
版本号需同步更新以下位置：
- `pyproject.toml`
- `uv.lock`
- `README.md`
- `gui/main_window.py`

---

## 7. 配置体系

### 7.1 配置文件结构

```
config/
├── config.ini          # 传统 INI 配置（质量、输出文件夹等）
├── user.json           # 当前用户配置（GUI 状态）
└── user.release.json   # 发布默认配置（干净状态，无个人路径）
```

### 7.2 配置优先级
1. `user.json`（最高优先级，GUI 状态）
2. `config.ini`（传统配置，向后兼容）
3. 默认值

### 7.3 关键配置项

| 配置 | 位置 | 说明 |
|------|------|------|
| 输出质量 | `config.ini` | JPEG 质量 0-100 |
| 输出文件夹 | `config.ini` / `user.json` | 支持变量替换 `{desktop}` 等 |
| 水印字段 | `user.json` | 四角芯片配置 |
| Logo 设置 | `user.json` | 位置、缩放、EXIF 匹配规则 |
| 签名路径 | `user.json` | 签名图片路径（**发布时需清理**） |
| 高级滤镜 | `user.json` | 模糊、圆角、阴影等参数 |

---

## 8. 关键设计决策与亮点

### 8.1 架构设计亮点

1. **单一事实来源 (AppState)**
   - 所有 GUI 状态集中管理，避免多组件间数据不一致
   - Signal 驱动更新，解耦 UI 组件

2. **处理器管道 (Pipeline)**
   - 注册表模式 + 装饰器，新处理器自动注册
   - AOP 计时，无需侵入代码即可性能追踪
   - 上下文传递，处理器间状态共享

3. **EXIF 优化策略**
   - 主进程一次性读取 EXIF，注入管道上下文
   - 避免每个工作进程重复调用 exiftool（N 次 fork）
   - mtime 缓存，减少重复读取

4. **批量处理优化**
   - 小批量自动回退串行（`< 3` 文件）
   - 避免 ProcessPoolExecutor 启动开销
   - 错误分类，区分可恢复/不可恢复错误

5. **图像 I/O 安全层**
   - `load_image_safely()` 立即加载并释放句柄
   - 解决批量处理时的 fd 泄漏问题

6. **签名过滤器智能处理**
   - 3 类像素处理策略，适应不同签名图
   - 白底透明化、黑白反转、彩色保留

### 8.2 向后兼容设计
- 旧版 `config.ini` 配置自动迁移到 `user.json`
- `start_process()` 保留旧版入口
- `core/configs.py` 别名保留

---

## 9. 项目状态与路线图

### 9.1 当前实现状态

| Phase | 功能 | 状态 |
|-------|------|------|
| Phase 6 | GUI 配置持久化 | ✅ 已实现 |
| Phase 7 | 高级滤镜 | ✅ 已实现 |
| Phase 8 | Logo 水印 | ✅ 已实现 |
| Phase 9 | 签名水印 | ✅ 已实现 |
| Phase 10 | 发布流程 | 🔄 持续改进 |

### 9.2 开发哲学
- **"先文档后实现"**: 每个 Phase 先写文档，再写代码
- **Roadmap 驱动**: 明确的 Phase 规划
- **Conventional Commits**: 规范的提交信息
- **发布安全**: 发布版本不得包含开发者个人路径

---

## 10. 优势与改进空间

### 10.1 项目优势

1. **架构清晰**: 四层分离，职责明确
2. **扩展性强**: 注册表模式，新处理器即插即用
3. **性能优化**: 多进程并行、EXIF 缓存、小批量回退
4. **测试完善**: 30+ 测试文件，覆盖单元和集成测试
5. **跨平台**: Windows/macOS/Linux 全支持
6. **配置灵活**: JSON + INI 混合，向后兼容
7. **错误处理**: 完善的异常体系，错误分类，pickle 安全
8. **性能可观测**: AOP 计时，慢节点自动警告

### 10.2 潜在改进空间

1. **配置清理**: `user.json` 可能包含个人路径，发布流程需确保清理
2. **EXIF 依赖**: 依赖外部 exiftool 二进制，可考虑纯 Python 替代（如 `exifread`）
3. **内存优化**: 大批量处理时，所有图像驻留内存，可考虑流式处理
4. **GPU 加速**: 当前纯 CPU 处理，可考虑 CUDA/OpenCL 加速滤镜
5. **插件系统**: 当前处理器注册是代码级，可考虑动态加载插件
6. **国际化**: 当前中文为主，可考虑 i18n 支持
7. **日志系统**: 当前使用 print，可考虑结构化日志（如 `structlog`）

---

## 11. 文件结构总览

```
aka-semi-utils/
├── main.py                    # 入口点
├── pyproject.toml             # 项目配置
├── uv.lock                    # 依赖锁定
├── README.md                  # 项目说明
│
├── core/                      # 核心工具层
│   ├── config_loader.py       # 配置加载
│   ├── util.py                # EXIF/文件工具
│   ├── image_io.py            # 安全图像 I/O
│   ├── exceptions.py          # 异常体系
│   ├── template_builder.py    # 水印配置构建
│   ├── jinja2renders.py       # Jinja2 函数
│   └── field_registry.py      # 字段注册表
│
├── processor/                 # 处理器管道层
│   ├── core.py                # 管道引擎
│   ├── filters.py             # 图像过滤器
│   ├── generators.py          # 图像生成器
│   ├── mergers.py             # 图像合并器
│   ├── batch.py               # 并行批处理
│   └── perf.py                # 性能追踪
│
├── gui/                       # GUI 层
│   ├── main_window.py         # 主窗口
│   ├── models.py              # 状态管理
│   ├── config_panel.py        # 配置面板
│   ├── template_assembler.py  # 状态转管道
│   └── ...                    # 其他组件
│
├── tests/                     # 测试套件
│   ├── unit/                  # 单元测试
│   └── integration/           # 集成测试
│
├── config/                    # 配置文件
│   ├── config.ini
│   ├── user.json
│   └── user.release.json
│
├── scripts/                   # 构建脚本
│   └── build.spec             # PyInstaller 配置
│
├── .github/workflows/         # CI/CD
│   └── build-release.yml      # 发布工作流
│
└── static/                    # 静态资源
    └── icon.ico               # 应用图标
```

---

## 12. 总结

`aka-semi-utils` 是一个架构设计精良、代码质量较高的桌面端图像处理工具。其核心优势在于：

1. **清晰的四层架构**，职责分离明确
2. **强大的处理器管道**，支持灵活的滤镜组合
3. **完善的性能优化**，多进程并行 + 智能回退
4. **全面的测试覆盖**，保障代码质量
5. **专业的摄影工作流**，EXIF 驱动的水印自动化

项目体现了良好的软件工程实践：设计模式应用、向后兼容、错误处理、性能追踪、CI/CD 自动化。对于摄影师用户而言，它提供了高度可定制且高效的批量水印解决方案。
