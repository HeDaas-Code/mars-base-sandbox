"""
引擎核心层（题材无关）

Phase 2 抽取：将 GameState / EventScheduler / GameLoop 中题材无关的逻辑
封装为可复用的引擎组件，通过注册表模式 + 数据驱动支持多题材。

子模块：
- ending_registry:  结局判定注册表（condition → ending_id）
- command_registry: meta 命令注册表（命令名 → handler）
- persona_registry: 人格模板注册表（npc_id → Jinja2 模板）
- state_schema:     状态字段动态注册（题材包 schema → GameState 字段）
- engine_core:      统一 API 包装（init / tick / handle_meta / handle_option_select）

设计原则：
- 题材无关：引擎核心不含任何"火星基地"特定字段
- 数据驱动：结局/命令/人格/状态字段均由注册表管理
- 渐进式迁移：先作为 wrapper 包装现有代码，原 API 保持向后兼容

作者：锐锋-核心开发工程师  日期：2026-08-09
"""
