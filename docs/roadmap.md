# Roadmap / 开发路线图

本文件记录 `aka-semi-utils / V3 水印工具` 的当前状态、阶段拆分和下一步优先级。较大功能开发必须先更新 roadmap 或对应设计文档，再实现。

## 产品目标

- 面向普通摄影用户，稳定生成高级感、品牌级摄影水印。
- 用 V3 Region-Based Layout 保持排版能力灵活，同时通过产品层限制避免布局失控。
- 前端预览与后端输出保持一致。
- 线上部署可验证、可回滚、无 V1/V2 旧功能入口。

## 当前状态

- 当前主线：`dev/v3-region-layout`。
- 当前线上：`https://baka-akari.zone/tools/watermark-v3/`。
- 当前架构：V3 Region / Slot / Content。
- 桌面版：冻结在 `v2.1.9`，归档于 `archive/desktop-v2`。
- V1：`/tools/watermark/` 只显示“回炉重塑中”。
- V2：代码、路由、服务和 SPA fallback 已移除。

## 已完成阶段

### Phase A：Web MVP 原型归档

旧 Web MVP 已完成验证，但其 V1/V2 文档和四角配置模型已归档到 `docs/archive/legacy-web-mvp/`，不再作为当前实现依据。

### Phase B：V3 Region-Based Layout 基础架构

已完成：

- V3 配置模型：`web_frontend/src/v3Types.ts` / `web_api/schemas_v3.py`。
- 前端布局引擎：`web_frontend/src/v3_layout/layoutEngine.ts`。
- 后端布局引擎：`shared/v3_layout/layout_engine.py`。
- 后端 V3 渲染：`processor/v3_watermark.py`。
- V3 API 处理链：上传、预览、处理、下载。
- V1/V2 清理：旧前端、旧 schema、旧 assembler、旧路由和旧服务下线。
- 全量测试通过：`uv run pytest`。

## 当前阶段

### Phase C：V3 控制面收敛与布局 Guardrails

设计文档：`design/v3-control-surface-guardrails.md`。

目标：

- 把底层 Region / Slot / Content 灵活性收敛成普通用户可理解的控制面。
- 明确哪些设置在主界面、哪些进高级、哪些暂时隐藏。
- 增加布局重叠、越界和无意义组合的检测/提示。
- 让“预设”从配置样例升级为安全模板。

优先级：

1. 主界面只保留预设、图片、内容开关、少量安全样式参数。
2. 高级区保留 Region / Slot 编辑器，但默认折叠并加风险提示。
3. 暂时隐藏任意新增 Region、任意 slot id、自由定位和底层单位切换。
4. 增加重叠/越界检测和恢复预设能力。
5. 再评估拖拽定位、撤销/重做、模板保存。

## Backlog

- 用户自定义预设保存。
- 自定义品牌 Logo 库。
- 多模板批量应用。
- ZIP 打包下载。
- 移动端适配。
- 所见即所得模板编辑器。
- 撤销/重做。
- 模板分享机制。

## 阶段完成定义

一个阶段完成必须满足：

1. roadmap 或阶段设计文档已更新。
2. 目标、范围、非目标、风险和验收标准明确。
3. 代码实现完成并通过相关自动化测试。
4. 线上部署后完成 health、路由、视觉截图和真实处理链验证。
5. 用户完成真实 GUI 测试，关键反馈已修复或记录为 backlog。
6. 变更形成清晰 commit，并按需推送到 GitHub。
