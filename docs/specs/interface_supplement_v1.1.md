# 接口补充规范文档 v1.1

**作者**: 云逸-架构技术总监
**日期**: 2026-08-02
**状态**: 正式发布
**关联文档**: 技术架构 v2.0 / WebSocket 接口定义 v1.1 / NPC YAML SCHEMA.md / 陈昊原型代码
**v1.1 增量**: 新增 §8 WebSocket 适配层规范；更新行动项

---

## 文档目的

v1.0 已定义 emotional_intensity / event_type / condition / cross_branch_redirect / ending_check / narrative_flag / 记忆压缩规范。v1.1 在此基础上补充：

8. WebSocket 适配层规范（模块边界 + chat() 返回值契约 + 合成字段派生规则）

v1.0 §1-§7 内容不变，本文件仅声明增量，与 v1.0 配套阅读。

---

## §8 WebSocket 适配层规范

### 8.1 模块定位与职责边界

**职责**：把 Agent.chat() 的域级返回值转换为 WebSocket v1.1 agent_message payload。

**模块边界**：必须独立为 `agent/ws_adapter.py`，不得嵌入 `Agent.chat()` 或 `graph.py`。

**理由（关注点分离）**：
1. `chat()` 是核心域逻辑，返回纯文本+元数据（response / prompt_tokens / completion_tokens / memories / context_summary）
2. 适配层是协议层职责，负责信封封装、合成字段派生、字典后处理调用
3. 分离带来的好处：
   - 单元测试可分别覆盖（域逻辑 vs 协议层）
   - 协议升级（v1.1→v2）不影响核心逻辑
   - 多协议输出可共用 chat()（WebSocket / HTTP 轮询兜底共享同一适配入口）

### 8.2 chat() 返回值契约扩展

**当前返回值**：
```python
{
    "response": str,
    "prompt_tokens": int,
    "completion_tokens": int,
    "memories": list[Memory],
}
```

**扩展为**：
```python
{
    "response": str,
    "prompt_tokens": int,
    "completion_tokens": int,
    "memories": list[Memory],
    "context_summary": dict,   # 新增：完整对象，由 chat() 提供
}
```

**context_summary 完整对象结构**（v1.1 §4.1.1 已定义四字段，必须由 chat() 在返回值中提供，不由适配层组装）：

```python
{
    "history_count": int,     # 当前 state.messages 列表长度
    "k_limit": int,          # 当前 response_mode 的 K 值（deliberate=6, deep=10, reflexive=0）
    "compressed_count": int, # compress_context 累计已压缩的消息数
    "mode": str,             # 当前 response_mode（"reflexive"/"deliberate"/"deep"）
}
```

**实现位置**：`graph.py` 的 `generate_response` 节点末尾组装 context_summary 并写入 state；`chat()` 返回时一并返回。适配层只透传，不重组。

### 8.3 合成字段派生规则

适配层负责派生 agent_message payload 中的合成字段：

| 字段 | 来源 | 派生规则 | 引用 |
|------|------|---------|------|
| `segments` | response 文本 | 走 §5.2 后处理流水线（实体匹配→切片→打 protected 标记）| WebSocket v1.1 §5.2 |
| `signal_quality_pct` | GameState.signal_quality | 直接透传，0-100 整数 | 待 GameState 字段定义 |
| `latency_ms` | 公式计算 | `500 + (100 - signal_quality_pct) * 50`（毫秒）| WebSocket v1.1 §6.2 |
| `emotion_hint` | GameState.npc_states[sender_id] | 见 §8.4 | 本节新增 |
| `context_summary` | chat() 返回值 | 直接透传 | §8.2 |

> 注：`latency_ms` 是**模拟通信延迟**（用于 per-player 队列定时 push 的沉浸感），不是 chat() 执行耗时。push worker 按此值延迟 push，前端可在信封中读到此值用于 UI 展示。

### 8.4 emotion_hint 派生规则

**结构**（v1.1 §4.1 已示例，本节定义派生来源；v1.1 增量：引用 8d 文档 `npc_states_schema_v1.0.md` 扩展 emotion_label + ai_status 字段）：

```python
# 人类 NPC
emotion_hint = {
    "stress": float,           # 0.0-1.0，NPC 当前压力值
    "morale": float,           # 0.0-1.0，NPC 当前士气值
    "emotion_label": str,      # 派生：8d §4.2 二维映射表（5×5 = 25 标签）
}

# AI 类 sender（athena / courier）
emotion_hint = {
    "stress": 0.0,             # 占位，前端不读
    "morale": 1.0,             # 占位，前端不读
    "ai_status": str,          # "normal" / "degraded" / "offline"（athena）；courier 恒 normal
}
```

**派生数据源**：`GameState.npc_states[sender_id]`（人类 NPC）+ `GameState.athena_status`（AI 类 sender）

**派生函数**（实现见 8d 文档 §5.3）：

```python
def build_emotion_hint(game_state, sender_id):
    # AI 类 sender
    if sender_id in ("athena", "courier"):
        if sender_id == "athena":
            ai_status = game_state.athena_status  # "normal"/"degraded"/"offline"
        else:
            ai_status = "normal"
        return {
            "stress": 0.0,
            "morale": 1.0,
            "ai_status": ai_status,
        }

    # 人类 NPC
    npc_state = game_state.npc_states.get(sender_id)
    if npc_state is None:
        # 兜底：未注册 NPC 返回中性默认值
        return {"stress": 0.0, "morale": 1.0}
    stress = npc_state.stress
    morale = npc_state.morale
    emotion_label = derive_emotion_label(stress, morale)  # 8d §4.3 查表
    return {
        "stress": stress,
        "morale": morale,
        "emotion_label": emotion_label,
    }
```

**实现要点**：
- 适配层从 GameState 读取目标 NPC 的 stress/morale 字段
- AI 类 sender（athena / courier）走 ai_status 分支，不查 npc_states（8d §5.1 已声明这两个 key 不在 npc_states 里）
- emotion_label 由适配层调用 `derive_emotion_label(stress, morale)` 派生，查表规则在 8d §4.2（25 个标签的 5×5 二维表）
- stress/morale 的更新逻辑由事件系统负责（8d §2 触发源 + §3 变化幅度表 + §7.3 apply_effects 实现），不在适配层职责内
- Phase 1 兜底：锐锋 ws_adapter.py:395 的 `detect_emotion` 文本检测可作为 npc_states 查询失败时的 fallback，8d 落地后切到主路径（8d §7.5 切换路径）

**字段引用**：

| 字段 | 来源 | 引用文档 |
|------|------|---------|
| `stress` / `morale` | GameState.npc_states[sender_id] | 8d §1.2 NpcState |
| `emotion_label` | derive_emotion_label(stress, morale) | 8d §4.2 / §4.3 |
| `ai_status` | GameState.athena_status（仅 athena） | 8d §5.2 / §7.1 |
| GameState.signal_quality | GameState 字段 | 8d §7.1（GameState 字段扩展）|

### 8.5 模块结构建议

**模块结构（与锐锋实现 2026-08-02 18:45 对齐）**：

```
backend/
├── agent/
│   ├── __init__.py
│   ├── state.py            # AgentState（核心域）
│   ├── config.py           # K 值/阈值配置
│   ├── memory.py           # MemoryStore + get_memory_store
│   ├── prompt.py           # 人格模板
│   ├── compress.py         # compress_context + write_episodic_memory
│   ├── condition.py        # §3 安全求值器
│   └── graph.py            # LangGraph 状态图（核心域，不含协议层代码）
└── ws_adapter.py           # 新增：WebSocket v1.1 适配层（位于 agent 包外，强化层分离）
```

> **修订说明**：v1.1 初稿原写为 `agent/ws_adapter.py`（适配层在 agent 包内）。锐锋实际放置于 `backend/ws_adapter.py`（agent 包外）。后者更符合 §8.1 关注点分离原则——协议层代码物理上与核心域逻辑包分离，依赖方向单向（ws_adapter 依赖 agent，反之不成立）。spec 与实现对齐为此版本。

**ws_adapter.py 接口签名建议**：

```python
from typing import Dict

def adapt_to_agent_message(
    chat_result: dict,        # Agent.chat() 返回值（含 context_summary）
    sender_id: str,
    sender_label: str,
    game_state: "GameState",
    dict_module: "DictModule",  # §5 字典模块（实体匹配用）
) -> dict:
    """把 Agent.chat() 返回值转换为 v1.1 agent_message payload"""
    response = chat_result["response"]
    segments = build_segments(response, dict_module)  # §5.2 流水线
    signal_quality = game_state.signal_quality
    latency_ms = 500 + (100 - signal_quality) * 50     # §6.2 公式
    emotion_hint = build_emotion_hint(game_state, sender_id)
    context_summary = chat_result["context_summary"]    # 直接透传

    return {
        "sender_id": sender_id,
        "sender_label": sender_label,
        "segments": segments,
        "signal_quality_pct": signal_quality,
        "latency_ms": latency_ms,
        "emotion_hint": emotion_hint,
        "context_summary": context_summary,
    }
```

**调用方**：FastAPI WebSocket handler 在收到 `player_input` 后：
1. 调 `agent.chat(text, target_agent_id)` 拿到 chat_result
2. 调 `ws_adapter.adapt_to_agent_message(...)` 拿到 payload
3. 包装成 v1.1 信封 `{msg_id, type: "agent_message", ts_tick, payload}`
4. 入 per-player 队列，按 latency_ms 定时 push

### 8.6 行动项更新

| # | 动作 | 负责人 | 优先级 | 状态 |
|---|------|--------|--------|------|
| 8a | chat() 返回值扩展，带完整 context_summary 对象（适配层不再调 agent.graph.get_state）| 锐锋 | P0 | 进行中 |
| 8b | 实现 ws_adapter.py 独立模块（位于 backend/，非 agent/ 内）| 锐锋 | P0 | 已完成（2026-08-02 18:45）|
| 8c | GameState 增加 signal_quality 字段（0-100 整数）| 锐锋 | P1 | 已定义（8d §7.1），待实现 |
| 8d | GameState.npc_states[sender_id] 字段标准化（含 stress/morale + 多 NPC 类型 schema）| 蔚蓝定义 + 锐锋实现 | P1 | 策划侧定义完成（npc_states_schema_v1.0.md），锐锋实现中 |
| 8e | ls/status 命令路由层（与适配层并行）| 锐锋 | P0 | 已完成（2026-08-02 18:45）|
| 8f | emotion_label 派生：数值→情绪标签映射表 | 蔚蓝 | P1 | 已完成（8d §4.2，5×5 二维表）|
| 8g | ws_adapter.py latency_ms 修复（执行耗时 → §6.2 模拟通信延迟公式）| 锐锋 | P0 | 已完成（2026-08-02 18:51）|

> v1.0 §8 行动项 1-7 不变，本节为新增项。

---

## 附录 B：v1.1 字段速查

### agent_message payload 完整字段来源

| 字段 | 来源 | 文档引用 |
|------|------|---------|
| `sender_id` | 调用方传入 | v1.1 §4.1 |
| `sender_label` | 调用方传入（从 NPC 配置读）| v1.1 §4.1 |
| `segments` | 适配层走 §5.2 流水线生成 | v1.1 §5.2 / §8.3 |
| `signal_quality_pct` | GameState.signal_quality 透传 | §8.3 |
| `latency_ms` | 适配层按 §6.2 公式计算 | v1.1 §6.2 / §8.3 |
| `emotion_hint` | 适配层从 GameState.npc_states 派生 | §8.4 |
| `context_summary` | chat() 返回值透传 | §8.2 / v1.1 §4.1.1 |

### 适配层不做的事

- 不调用 LLM（LLM 调用都在 chat() 里）
- 不修改 GameState（只读取）
- 不修改 MemoryStore（只读取）
- 不实现 push 调度（push worker 在 per-player 队列层）
- 不实现鉴权（在 WebSocket handler 层）

---

## 变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-08-02 | 首版：§1-§7 + 行动项 + 附录 A |
| v1.1 | 2026-08-02 | 新增 §8 WebSocket 适配层规范（模块边界 / chat() 契约扩展 / 合成字段派生 / emotion_hint 规则 / 行动项更新）+ 附录 B |

---

*对接过程中如有字段调整需求，请在群里 @云逸-架构技术总监。*
