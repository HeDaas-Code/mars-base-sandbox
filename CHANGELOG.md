# 变更日志

本文档记录赫拉克勒斯协议项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

## [Unreleased]

### Added (2026-08-04 — 锐锋)

- 实现 7 阶段 FSM 游戏主循环 (`game_loop.py`)
- 实现事件调度器 (`event_scheduler.py`)，支持 Sol 推进、触发器检查、TTL 过期
- 实现章节 YAML 加载器 (`chapter_loader.py`)，支持 4 章节 + 4 分支加载
- 实现 GameState 世界状态管理 (`game_state.py`)，包含 NPC 心理状态、资源系统、结局判定
- 实现情感指令系统：`#soothe` / `#empathize` / `#command` / `#blame` / `#smalltalk`
- 实现多 NPC 人格 Jinja2 模板渲染 (`npc_prompts.py`)
- 集成 WebSocket 适配层 (`ws_adapter_v2.py`) 与 GameLoop
- 实现 `option_select` 回路，支持事件选项选择与连锁效果
- 添加 `:sol` / `:state` / `:npc` / `:branch` / `:mode` / `:skip` / `:restart` meta 命令
- 实现 7 种结局判定逻辑（E1-E7）
- 实现资源危机检测与 Sol 自然衰减

### Added (2026-08-02 — 蔚蓝)

- 交付 4 个 NPC 人设 YAML：索菲亚、维克托、艾莎、马库斯
- 交付 4 个分支事件剧本 YAML：地球救援 / 自力更生 / 科学发现 / 人性考验
- 交付 NPC 关系网络与状态机定义
- 交付章节字典 YAML（4 章节）

### Added (2026-08-01 — 云逸)

- 技术架构设计方案 v1.0 / v2.0
- WebSocket 接口定义 v1.1 / v1.2 / v1.3
- 接口补充规范 v1.0 / v1.1
- 记忆压缩规范 v1.0
- 对话历史摘要规范 v1.0

### Added (2026-07-31 — 幻影)

- 前端视觉与界面概念设计方案 v1 / v2
- 前端视觉规范 CSS 参数表
- 游戏系统设计方案 v1.0 / v1.1
- 情绪提示前端实现方案

### Added (2026-07-30 — 锐锋)

- 初始原型：LangGraph Agent 链路 (`graph.py`)
- ChromaDB 记忆检索系统 (`memory.py`)
- 对话压缩与摘要 (`compress.py`)
- 安全条件表达式求值器 (`condition.py`)
- WebSocket 服务器 (`ws_server.py`)
- WebSocket 协议适配层 (`ws_adapter.py`)
- 命令行交互入口 (`main.py`)
- 种子记忆数据 (`seed_memories.py`)