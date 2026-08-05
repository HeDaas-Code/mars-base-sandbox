# 项目文档

> 赫拉克勒斯协议 — 文档索引

## 核心文档

| 文档 | 说明 |
|------|------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 技术架构设计总览 |
| [API.md](./API.md) | WebSocket API 接口文档 |
| [DATA_FORMAT.md](./DATA_FORMAT.md) | 游戏数据 YAML 格式规范 |
| [GAME_DESIGN.md](./GAME_DESIGN.md) | 游戏系统设计文档 |
| [DEVELOPMENT.md](./DEVELOPMENT.md) | 开发环境搭建与运行指南 |
| [integration_checklist.md](./integration_checklist.md) | 集成检查清单 |

## 架构设计

| 文档 | 作者 | 日期 |
|------|------|------|
| [技术架构设计方案 v1.0](./architecture/技术架构设计方案_v1.0.md) | 云逸 | 2026-08-01 |
| [技术架构设计方案 v2.0](./architecture/技术架构设计方案_v2.0.md) | 云逸 | 2026-08-02 |

## API 接口

| 文档 | 作者 | 日期 |
|------|------|------|
| [WebSocket 接口定义 v1.1](./api/WebSocket接口定义_v1.1.md) | 云逸 | 2026-08-01 |
| [WebSocket 接口定义 v1.2 事件消息补充](./api/WebSocket接口定义_v1.2_事件消息补充.md) | 云逸 | 2026-08-02 |
| [WebSocket 接口定义 v1.3 事件消息字段补充](./api/WebSocket接口定义_v1.3_事件消息字段补充.md) | 云逸 | 2026-08-03 |
| [事件面板交互规范](./api/event_panel_interaction_spec_v1.0.md) | 云逸 | 2026-08-02 |

## 游戏设计

| 文档 | 作者 | 日期 |
|------|------|------|
| [游戏系统设计方案 v1.0](./design/游戏系统设计方案_赫拉克勒斯协议_v1.0.md) | 幻影 | 2026-07-31 |
| [游戏系统设计方案 v1.1](./design/游戏系统设计方案_赫拉克勒斯协议_v1.1.md) | 幻影 | 2026-08-01 |
| [视觉与界面概念设计 v1](./design/视觉与界面概念设计方案_v1.md) | 幻影 | 2026-07-31 |
| [视觉与界面概念设计 v2](./design/视觉与界面概念设计方案_v2.md) | 幻影 | 2026-08-01 |
| [前端视觉规范 CSS 参数表](./design/前端视觉规范_CSS参数表.md) | 幻影 | 2026-07-31 |
| [视觉 CSS 规范 NPC 色值与信号遮罩](./design/视觉CSS规范_NPC色值与信号遮罩.md) | 幻影 | 2026-08-01 |
| [视觉侧交付清单与缺口分析](./design/视觉侧交付清单与缺口分析_v1.md) | 幻影 | 2026-08-02 |
| [立绘需求字段清单](./design/立绘需求字段清单_v1.md) | 幻影 | 2026-08-01 |
| [情感提示前端实现方案](./design/emotion_hint前端实现方案_v1.md) | 幻影 | 2026-08-01 |
| [情感提示前端落地完成报告](./design/emotion_hint前端落地完成报告_v1.md) | 幻影 | 2026-08-02 |
| [情感标签视觉呈现规范](./design/emotion_label视觉呈现规范_v1.md) | 幻影 | 2026-08-01 |
| [NPC 配置对照审查报告](./design/npc-config_对照审查报告.md) | 幻影 | 2026-08-02 |
| [Followup UI v1.0](./design/followup_ui_v1.0.md) | 云逸 | 2026-08-03 |

## 规范文档

| 文档 | 作者 | 日期 |
|------|------|------|
| [接口补充规范 v1.0](./specs/interface_supplement_v1.0.md) | 云逸 | 2026-08-02 |
| [接口补充规范 v1.1](./specs/interface_supplement_v1.1.md) | 云逸 | 2026-08-03 |
| [NPC 状态 Schema](./specs/npc_states_schema_v1.0.md) | 蔚蓝 | 2026-08-02 |
| [脚本对话格式](./specs/scripted_dialogue_format_v1.0.md) | 蔚蓝 | 2026-08-02 |
| [YAML 格式补充规范](./specs/yaml_format_supplement_v1.0.md) | 蔚蓝 | 2026-08-02 |
| [游戏循环规则规范](./specs/game_loop_rules_spec_v1.0.md) | 蔚蓝 | 2026-08-03 |
| [记忆压缩规范](./specs/记忆压缩规范_v1.0.md) | 云逸 | 2026-08-02 |
| [对话历史摘要规范](./specs/对话历史摘要规范_v1.0.md) | 云逸 | 2026-08-02 |
| [NPC 配置修正清单](./specs/npc-config_修正清单_蔚蓝.md) | 蔚蓝 | 2026-08-03 |
| [NPC Persona Payload](./specs/persona_payload/) | 云逸 | 2026-08-02 |

## 数据格式

| 文档 | 作者 | 日期 |
|------|------|------|
| [章节字典 v0.1](./data-format/章节字典_第一版_v0.1.yaml) | 蔚蓝 | 2026-08-02 |
| [事件 YAML 边界情况](./data-format/event_yaml_edge_cases_v1.0.md) | 蔚蓝 | 2026-08-02 |

## 代码审查

| 文档 | 作者 | 日期 |
|------|------|------|
| [陈昊原型代码审查](./reviews/code_review_chenhao_prototype.md) | 云逸 | 2026-08-01 |
| [GameState 代码审查](./reviews/code_review_game_state.md) | 云逸 | 2026-08-02 |
| [锐锋 Phase 1 代码审查](./reviews/code_review_ruefeng_phase1.md) | 云逸 | 2026-08-02 |
| [情感提示视觉验收报告](./reviews/emotion_hint_视觉验收报告_v1.md) | 幻影 | 2026-08-02 |
| [v1.2 事件集成报告](./reviews/v1.2_event_integration_report_qianji.md) | 千机 | 2026-08-03 |