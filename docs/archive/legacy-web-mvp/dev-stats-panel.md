# Dev 统计面板 — 设计方案

## 1. 目标

在 web 前端增加一个 `/_dev` 路径的开发者统计面板，用于可视化展示网站运营数据。入口隐藏于主界面右上角（微不显眼的小按钮），需要密码 `23323312` 进入。

## 2. 后端设计（SQLite + FastAPI）

### 2.1 数据库（SQLite 文件 `stats.db`）

存放于 `data_dir` 同级目录，名称为 `stats.db`（`settings.data_dir.parent / "stats.db"`，或随 `data_dir` 同级）。表结构：

```sql
-- 每日聚合统计
create table if not exists daily_stats (
    date text primary key,          -- YYYY-MM-DD
    unique_visitors integer default 0,  -- 当日去重访客
    new_visitors integer default 0,     -- 当日新增访客（首次出现）
    processed_images integer default 0, -- 当日处理图片数（process + preview）
    api_calls integer default 0,       -- 当日 API 调用总次数
    avg_batch_size real default 0,       -- 当日平均批量处理图片数
    p50_latency_ms integer default 0,    -- 处理延迟 P50（仅 process）
    p99_latency_ms integer default 0     -- 处理延迟 P99
);

-- 访客指纹表（用于去重）
create table if not exists visitors (
    visitor_id text primary key,    -- 24 位随机 token
    first_seen date,                -- 首次访问日期
    last_seen date,                -- 最后访问日期
    visit_count integer default 0   -- 总访问次数
);

-- 实时操作日志（最近 7 天，自动清理）
create table if not exists ops_log (
    id integer primary key autoincrement,
    created_at datetime default current_timestamp,
    operation text,                -- 'preview' | 'process' | 'process_all' | 'visit'
    latency_ms integer,            -- 处理耗时（ms）
    batch_count integer default 0, -- 批量处理时的图片数量
    visitor_id text,               -- 关联访客
    preset_name text default ''     -- 使用的预设（可扩展）
);

create index if not exists ops_log_date on ops_log(created_at);
```

### 2.2 数据收集方式

**无需修改中间件/请求处理**——在 main.py 中 `/_run_single_image` 结束后记录 `process` 或 `preview`；新增一个 `/_visit` 轻量端点（前端 `main.tsx` 挂载时 `POST` 一次），用于记录访客。

- 访客指纹：`base64url(random(18))`（24 字符），存储在 localStorage `_dev_visitor_id`
- 每次 `/_visit` 调用：传 `visitor_id`，后端判断是否为新增访客，更新 `visitors` 表和 `daily_stats` 的 `unique_visitors`/`new_visitors`
- 每次 `/_run_single_image` 返回后：记录 `process` 或 `preview` 到 `ops_log`，同时更新 `daily_stats.processed_images` 和 `api_calls`
- 延迟：`time.perf_counter()` 在 `process_image` 线程前后计时

### 2.3 API 端点

```
POST /api/_visit       body: {visitor_id: string}  → 返回 {ok: true, new: bool}
GET  /api/_stats       → 返回完整统计数据
GET  /api/_stats/health → 返回 {ok: true, db: "connected"}
```

**`/_stats` 返回结构**：

```json
{
  "ok": true,
  "today": {
    "unique_visitors": 12,
    "new_visitors": 3,
    "processed_images": 45,
    "api_calls": 67
  },
  "lifetime": {
    "total_visitors": 128,
    "total_processed_images": 892,
    "total_api_calls": 1234
  },
  "trend": {
    "last_7_days": [
      {"date": "2025-07-01", "unique_visitors": 10, "processed_images": 20, ...}
    ],
    "last_30_days": [...]
  },
  "latency": {
    "p50_ms": 340,
    "p99_ms": 1200
  }
}
```

### 2.4 密码保护

FastAPI `/_stats` 端点要求 `X-Dev-Password: 23323312` 请求头，否则返回 `403`。`/_visit` 无需密码。

## 3. 前端设计（Apple 风格）

### 3.1 路由

- 安装 `react-router-dom`（已确认未安装，需 npm install）
- 新文件 `src/AppRouter.tsx`：管理 `BrowserRouter`，两个路由
  - `/` → `HomePage`（现有 `App` 内容提取）
  - `/_dev` → `DevPage`
- `main.tsx` 中 `createRoot` 渲染 `<AppRouter>` 而非 `<App>`
- `App` 被提取为 `HomePage` 组件（保留所有现有逻辑）

### 3.2 入口按钮（TopBar 右上角）

`TopBar.tsx` 右侧添加一个 **12×12px 半透明圆点**（`opacity: 0.15`），hover 时 `opacity: 1` 并放大到 `14×14`。只有开发者知道点击它，普通用户几乎不可见。

按钮链接：`navigate('/_dev')`

### 3.3 密码验证页（`DevPage` 内嵌）

`DevPage` 的初始状态：全屏黑色遮罩（`#000000`），中间白色密码输入框（Apple 风格）。

- 输入框：圆角 8px，无 border，半透明灰色背景 `rgba(255,255,255,0.08)`，输入时发光 `box-shadow`
- 输入正确密码后：输入框区域向上滑动消失，统计面板从底部淡入（`translateY(20px) → 0`，`opacity 0 → 1`，`0.6s cubic-bezier(0.22, 1, 0.36, 1)`）
- 错误时：输入框轻微左右晃动（`shake` 动画），文字变红
- 密码验证通过后将 `sessionStorage` 键 `_dev_auth` 设为 `true`（刷新页面需重新输入，但 SPA 内路由切换保持）

### 3.4 统计面板（Apple 设计语言）

**色彩系统**：
- 背景：`#0a0a0f`（深色极深蓝）
- 卡片背景：`rgba(255,255,255,0.04)` 或 `#111118`
- 强调色：Apple 标准蓝 `#007AFF`（按钮/高亮）、青绿 `#30D158`（增长）、橙红 `#FF453A`（下降）
- 文字：主标题 `#ffffff`，副标题 `#8a8a8e`（Apple 灰）

**布局**：
- 顶部大标题："用量洞察"（`28px, weight 600, letter-spacing: -0.02em`）
- 4 个 KPI 卡片行（2×2 grid，移动端单列）
  - 卡片：圆角 16px，背景 `#111118`，hover 时 `translateY(-2px)` + `box-shadow` 微光
  - 卡片内部：大数字 `36px/700`，趋势百分比（↑/↓ 颜色区分），标签 `12px` 大写灰字
  - 动画：数字进入时从 `0` 计数滚动到实际值（`1.2s ease-out`），用 `requestAnimationFrame` 实现
- 下方两栏：左宽右窄
  - 左侧（60%）：SVG 折线图（7日访问趋势 + 处理趋势）
  - 右侧（40%）：3 个迷你数据卡片（API 延迟、平均批量、活跃比例）
- 底部：数据表格（最近 7 天详细数据，Apple 风格：底部分割线、无垂直边框）

**图表动画**：
- 折线图使用纯 SVG 手绘动画：线条从 `stroke-dashoffset: 1000` 到 `0`（`1.5s ease-out`）
- 数据点逐个 `scale(0) → scale(1)` 弹出（`0.3s cubic-bezier(0.34, 1.56, 0.64, 1)` 弹性效果）
- 面积填充：从 `opacity: 0` 到 `opacity: 0.15` 渐变填充
- 所有动画使用 `requestAnimationFrame` + CSS transition，不引入图表库

**刷新按钮**：右上角圆形刷新按钮，hover 旋转 180°，点击后数据重载，卡片闪烁 `opacity` 动画

### 3.5 响应式

- 移动端（<768px）：KPI 卡片单列，图表全宽，数据表可横向滚动
- 使用 CSS Grid + Flexbox，无框架依赖

## 4. 实现拆分

### Agent 1 — 后端统计层
文件：
- `web_api/stats.py` — 新建，SQLite 初始化、数据记录、查询
- `web_api/main.py` — 修改，新增 `POST /api/_visit`、`GET /api/_stats`（带密码校验）、在 `_run_single_image` 后记录操作

### Agent 2 — 前端路由与基础设施
文件：
- `web_frontend/package.json` — 添加 `react-router-dom` 依赖
- `web_frontend/src/main.tsx` — 渲染 `AppRouter`（修改）
- `web_frontend/src/AppRouter.tsx` — 新建，路由配置
- `web_frontend/src/HomePage.tsx` — 新建，从现有 `App` 提取（保持原有逻辑不变）
- `web_frontend/src/components/TopBar.tsx` — 修改，添加右上角入口按钮
- `web_frontend/src/components/DevButton.tsx` — 新建，入口按钮组件

### Agent 3 — 前端统计面板
文件：
- `web_frontend/src/api.ts` — 修改，添加 `postVisit` 和 `getStats` 方法
- `web_frontend/src/pages/DevPage.tsx` — 新建，密码验证 + 统计面板主组件
- `web_frontend/src/components/dev/PasswordGate.tsx` — 新建，密码验证动画组件
- `web_frontend/src/components/dev/KpiCard.tsx` — 新建，KPI 卡片（带动画数字）
- `web_frontend/src/components/dev/TrendChart.tsx` — 新建，SVG 折线图组件
- `web_frontend/src/components/dev/DataTable.tsx` — 新建，数据表格组件
- `web_frontend/src/styles-dev.css` — 新建，统计面板专用样式（Apple 风格）

## 5. 安全约束

- `/_stats` 端点通过 `X-Dev-Password` 请求头保护，密码硬编码为 `23323312`（纯内部面板，不对外）
- 不返回任何内部路径、堆栈信息
- 访客指纹仅用于统计去重，不关联任何个人信息
- SQLite 文件放在 data_dir 同级，不暴露于静态文件服务

## 6. 验收标准

- [ ] 构建通过：`npm run build` 无错误，`uv run ruff check` 无错误
- [ ] 主页面功能不受影响（水印处理正常）
- [ ] `/_dev` 页面能正常加载，密码校验正确
- [ ] 统计面板显示 4 个 KPI 卡片 + 1 个趋势图 + 1 个数据表
- [ ] 后端 `/_stats` 端点在带密码头时返回有效 JSON
- [ ] 后端 `/_visit` 和 `/_run_single_image` 能正确写入 SQLite
