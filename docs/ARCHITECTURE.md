# 技术架构设计

> 赫拉克勒斯协议 — 技术架构总览

## 系统概述

赫拉克勒斯协议是一个基于 LLM 的多智能体交互式叙事游戏系统，采用前后端分离架构，通过 WebSocket 协议进行实时通信。

## 整体架构

```
┌──────────────────────────────────────────────────────────┐
│                        Frontend                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │ Terminal │ │  Crew    │ │  Event   │ │  Resource │  │
│  │  (xterm) │ │  Panel   │ │  Panel   │ │  Panel    │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬─────┘  │
│       └─────────────┴────────────┴─────────────┘        │
│                        │ WebSocket                       │
└────────────────────────┼────────────────────────────────┘
                         │
┌────────────────────────┼────────────────────────────────┐
│                        │          Backend                │
│  ┌─────────────────────┴──────────────────────┐         │
│  │           ws_server.py                      │         │
│  │  (WebSocket 服务器 + 消息分发)              │         │
│  └──────────┬─────────────────────────────────┘         │
│             │                                            │
│  ┌──────────┴─────────────────────────────────┐         │
│  │         ws_adapter_v2.py                    │         │
│  │  (协议适配层 + GameLoop 集成)              │         │
│  └──────────┬─────────────────────────────────┘         │
│             │                                            │
│  ┌──────────┴─────────────────────────────────┐         │
│  │           GameLoop (game_loop.py)           │         │
│  │  ┌───────────────────────────────────────┐ │         │
│  │  │    7 阶段 FSM 主循环                   │ │         │
│  │  │  P1 通信接收 → P2 信息分析            │ │         │
│  │  │  → P3 决策制定 → P4 指令下达          │ │         │
│  │  │  → P5 执行演算 → P6 结果反馈          │ │         │
│  │  │  → P7 事件触发                         │ │         │
│  │  └───────────────────────────────────────┘ │         │
│  └──────┬──────────────┬──────────────────────┘         │
│         │              │                                 │
│  ┌──────┴──────┐ ┌────┴──────────────────────┐         │
│  │ GameState   │ │  EventScheduler            │         │
│  │ (世界状态)  │ │  (事件调度 + 章节管理)     │         │
│  └──────┬──────┘ └────────┬──────────────────┘         │
│         │                 │                              │
│  ┌──────┴─────────────────┴──────────────────┐         │
│  │              Agent Engine                  │         │
│  │  ┌────────┐ ┌────────┐ ┌──────────────┐  │         │
│  │  │ graph  │ │ prompt │ │   memory     │  │         │
│  │  │(LangG) │ │(人格)  │ │ (ChromaDB)  │  │         │
│  │  └────────┘ └────────┘ └──────────────┘  │         │
│  └───────────────────────────────────────────┘         │
│                                                         │
│  ┌───────────────────────────────────────────┐         │
│  │           Data Layer                       │         │
│  │  chapter_loader.py → dict/ (YAML)         │         │
│  └───────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────┘
```

## 核心模块

### 1. GameLoop（游戏主循环）

**文件**: `backend/agent/game_loop.py`

7 阶段 FSM 处理玩家每回合输入：

| 阶段 | 名称 | 职责 |
|------|------|------|
| P1 | 通信接收 | 解析玩家输入（自然语言 / 情感指令前缀） |
| P2 | 信息分析 | 构建 condition 上下文 + 游戏状态摘要 |
| P3 | 决策制定 | 检查事件触发器（由 EventScheduler 维护） |
| P4 | 指令下达 | 调度 NPC 回复 / 事件下发 |
| P5 | 执行演算 | 应用情感 delta + Agent.chat + apply_sol_decay |
| P6 | 结果反馈 | 构建 agent_message / story_event / option_result 信封 |
| P7 | 事件触发 | 检查章节切换 / 结局判定 |

### 2. GameState（世界状态）

**文件**: `backend/agent/game_state.py`

管理游戏世界级状态，与 AgentState（对话级）分离：

- **NpcState**: NPC 心理状态（stress/morale/trust_in_player/energy/current_state）
- **资源系统**: oxygen/power/water/food/parts
- **信号质量**: 影响通信延迟
- **雅典娜状态**: normal/degraded/offline（隐藏结局联动）
- **emotion_label**: 5×5 二维情绪标签（25 种）
- **资源危机检测**: 阈值触发 + 责任区 NPC stress 翻倍
- **Sol 自然衰减**: 每 Sol 自动结算

### 3. EventScheduler（事件调度器）

**文件**: `backend/agent/event_scheduler.py`

- 从章节 YAML 加载触发器列表
- Sol 推进时检查 trigger condition（安全表达式求值）
- 激活事件供玩家选择
- 玩家选择后 `apply_effects` 写入 GameState
- TTL 自动失效过期触发器
- 章节切换（stage_transition 条件求值）

### 4. Agent Engine（Agent 引擎）

**文件**: `backend/agent/graph.py`

LangGraph 状态图处理流程：

```
System Prompt(人格) → 记忆检索 Top-3 → 玩家输入 → LLM 回复
```

三档响应模式：
- `reflexive`: 不调 LLM，规则匹配快速回复
- `deliberate`: 平衡速度与质量
- `deep`: 深思熟虑的高质量回复

### 5. Prompt System（人格系统）

**文件**: `backend/agent/prompt.py`, `backend/agent/npc_prompts.py`

- 陈昊：`str.format` 模板
- 其余 5 个 NPC：Jinja2 模板，注入 stress/morale/trust_in_player/stage/recent_events
- 模板变量使 NPC 对话随心理状态动态变化

### 6. Memory（记忆系统）

**文件**: `backend/agent/memory.py`

- ChromaDB 单库 + metadata 过滤
- metadata: agent_id / memory_type / timestamp / importance / tags / emotional_intensity / event_type
- 语义检索 Top-K 召回
- 支持种子记忆注入与对话记忆写入

## 数据流

```
玩家输入 → ws_server → ws_adapter_v2 → GameLoop.tick()
  → P1 解析情感指令
  → P5 应用情感 delta
  → P2 构建 NPC 状态
  → P4/P5 Agent.chat() → graph → prompt(人格) → memory(检索) → LLM
  → P6 构建 agent_message 信封
  → ws_server → WebSocket → 前端
```

## 消息协议

前端与后端通过 WebSocket 通信，协议版本 v1.1-v1.3：

| 方向 | 消息类型 | 说明 |
|------|---------|------|
| C→S | `hello` | 握手，建立会话 |
| C→S | `player_input` | 玩家自然语言输入 |
| C→S | `option_select` | 事件选项选择 |
| C→S | `command` | 系统命令（ls/status/talk 等） |
| C→S | `ping` | 心跳 |
| S→C | `session_init` | 会话初始化（含世界快照） |
| S→C | `agent_message` | NPC 回复（含 emotion_hint） |
| S→C | `story_event` | 事件激活（含选项列表） |
| S→C | `option_result` | 选项结果反馈 |
| S→C | `command_response` | 命令响应 |
| S→C | `error` | 错误消息 |

## 技术选型

| 组件 | 技术 | 理由 |
|------|------|------|
| Agent 框架 | LangGraph | 状态图建模，支持 checkpoint |
| LLM 接口 | OpenAI 兼容 | 多模型兼容（MiniMax-M3 / GPT-4o） |
| 向量数据库 | ChromaDB | 轻量嵌入式，无需独立服务 |
| 通信协议 | WebSocket | 双向实时通信 |
| 前端终端 | xterm.js | 终端风格 UI |
| 数据格式 | YAML | 可读性强，适合策划编辑 |
| 模板引擎 | Jinja2 | 灵活的人格模板渲染 |