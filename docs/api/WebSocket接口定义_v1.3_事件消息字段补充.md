# WebSocket 接口定义 v1.3 补充
（事件消息字段透传与 sol_advance）

> **文档版本**：v1.3（在 v1.2 基础上增补 §13-§15）
> **作者**：云逸-架构技术总监
> **日期**：2026-08-03
> **面向对象**：幻影-视觉技术专家（事件弹窗视觉模板字段对齐）、锐锋-核心开发工程师（event_scheduler/ws_adapter 构造逻辑）、千机-引擎实现工程师（前端事件 UI 集成）
> **依赖文档**：
> - 《WebSocket接口定义 v1.2 事件消息补充》§11（story_event / option_select / option_result）
> - 蔚蓝《NPC 人设 YAML 与事件剧本 YAML Schema 说明》§2 事件节点字段
> - 幻影《视觉侧交付清单与缺口分析 v1.0》§5.3 字段映射表 + §5.5 等待项

---

## 背景

v1.2 定义了 `story_event` / `option_select` / `option_result` 三种消息类型，但 payload 字段聚焦于"协议层必需字段"。幻影 §5.3 字段映射表表明，前端事件 UI 需要逐行渲染 YAML 原始字段（bound_npcs / effects.state_set / effects.trust_delta / effects.morale_delta / effects.branch_progress / effects.risk / ending_determination），并需要独立的 Sol 时钟推进消息。

v1.3 补充：
1. `story_event` payload 增加 `bound_npcs` / `sol` / `options[].risk` / `ending_determination` 字段（§13）
2. `option_result` payload 增加 `effects` 原始结构透传 + `ending` 结局信息（§14）
3. 新增 `sol_advance` 消息类型（§15）

---

## 13. story_event 字段补充

### 13.1 补充后完整 payload

```json
{
  "event_id": "ev_B3_oxygen_full_power",
  "chapter_id": "ch02_power_allocation",
  "node_index": 3,
  "branch": "B",
  "sol": 152,
  "narrative_segments": [
    {"text": "[基地广播]> ", "protected": true, "tag": "speaker_label"},
    {"text": "氧气存量低于 18%，MOXIE-2 主氧气生成器仍离线。陈昊召集全员讨论修复方案。", "protected": false, "tag": "narration"},
    {"text": "维克托", "protected": true, "tag": "npc_name"},
    {"text": "指着他昨天刚拆开的电解槽，说 spare cell 还能撑一周。", "protected": false, "tag": "narration"}
  ],
  "bound_npcs": {
    "primary": "viktor",
    "advisor_conflict": ["athena", "aisha"]
  },
  "options": [
    {
      "option_id": "B3_opt1_replace_full_power",
      "label": "更换核心模块，MOXIE 满功率（牺牲最后备用件）",
      "visible": true,
      "risk": null
    },
    {
      "option_id": "B3_opt2_keep_spare_conservative",
      "label": "保留备用件，MOXIE 维持 65%（保守）",
      "visible": true,
      "risk": "self_sufficiency 目标 0.95 难达成"
    },
    {
      "option_id": "B3_opt3_athena_informed",
      "label": "让雅典娜做故障概率预测辅助决策",
      "visible": true,
      "risk": null,
      "followup": {
        "prompt": "雅典娜建议更换整套电解模块。你的决定？",
        "options": [
          {"option_id": "B3_opt3a_accept_athena", "label": "接受建议（viktor -10）", "visible": true, "risk": null},
          {"option_id": "B3_opt3b_reject_athena", "label": "拒绝建议（aisha -5）", "visible": true, "risk": null}
        ]
      }
    }
  ],
  "ending_determination": null,
  "signal_quality_pct": 62,
  "latency_ms": 1800
}
```

### 13.2 新增字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `sol` | int | 是 | 当前 Sol 天数（用于事件头部显示，如 "Sol 152"） |
| `bound_npcs` | object | 是 | 透传 YAML `bound_npcs` 原始结构，角色绑定 NPC 列表，供前端渲染绑定 NPC 标记条 |
| `options[].risk` | string \| null | 是 | 从 YAML `player_options[].effects.risk` 提取。若该选项 effects 有 risk 字段则透传字符串；无则填 null。前端在选择前渲染为"⚠ 风险提示"行 |
| `ending_determination` | array \| null | 是 | 仅终局节点（最大 node_index 且有 ending_determination 字段）才传；非终局节点填 null。结构见 §13.3 |

### 13.3 ending_determination 结构

```json
"ending_determination": [
  {
    "condition": "vote_yes >= 4 and self_sufficiency >= 0.85 and sophia_tree_experiment == success",
    "ending": "E2_mars_child_with_tree",
    "description": "火星之子 + 索菲亚的树——分支B最圆满结局"
  },
  {
    "condition": "vote_yes >= 4 and self_sufficiency >= 0.75",
    "ending": "E2_mars_child",
    "description": "火星之子——永久定居点成立"
  }
]
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `condition` | string | 结局触发条件表达式（人类可读，前端不要求求值，仅展示） |
| `ending` | string | 结局标识 |
| `description` | string | 结局描述文本 |

> **设计要点**：`ending_determination` 是终局节点的展示性信息，前端用于渲染"可能结局列表"面板（紫色发光边框）。结局的**实际求值**在后端 `option_result` 构造时完成（§14.2），前端不持有 game_state，不做条件求值。

### 13.4 bound_npcs 结构变体

YAML 中 `bound_npcs` 字段是自由 object，不同事件节点角色结构不同。常见 key：

| key | 类型 | 说明 |
|-----|------|------|
| `primary` | string | 主导 NPC ID |
| `advocates` | array | 支持方 NPC ID 列表 |
| `skeptic` | string | 怀疑方 NPC ID |
| `advisor` | string | 顾问 NPC ID |
| `advisor_conflict` | array | 冲突顾问 NPC ID 列表 |
| `all_crew` | bool | 是否全员参与 |
| `special` | array | 特殊角色 NPC ID 列表 |

前端渲染时按 key 遍历，每个 NPC 用其 visual.symbol + role_short 渲染绑定标记条，primary 高亮。

---

## 14. option_result 字段补充

### 14.1 补充后完整 payload

```json
{
  "event_id": "ev_B3_oxygen_full_power",
  "option_id": "B3_opt1_replace_full_power",
  "effects_summary": "viktor +10, chen_hao +5, athena -2, branch_progress B +2, moxie2_efficiency=88",
  "effects": {
    "state_set": {"moxie2_efficiency": 88, "last_spare_used": true},
    "oxygen_production_L_per_sol": 70,
    "self_sufficiency_delta": 0.2,
    "trust_delta": {"viktor": 10, "chen_hao": 5, "athena": -2},
    "branch_progress": "B +2"
  },
  "state_update": {
    "path": "npc_states.viktor.trust",
    "old": 22,
    "new": 32
  },
  "ending": null,
  "leads_to": "ev_B4_rover_base_expansion",
  "followup": null
}
```

### 14.2 新增字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `effects` | object | 是 | 透传 YAML `player_options[].effects` 原始对象，前端按字段逐行渲染效果反馈。结构与 YAML 完全一致（state_set/trust_delta/morale_delta/resource_delta/crew_workload/risk/narrative_flag/branch_progress/cross_branch_redirect） |
| `ending` | object \| null | 是 | 若该选项 `effects.ending_check == true` 且后端求值 ending_determination 命中某结局，则填结局对象；否则填 null |

### 14.3 ending 结构

```json
"ending": {
  "ending_id": "E2_mars_child_with_tree",
  "description": "火星之子 + 索菲亚的树——分支B最圆满结局"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `ending_id` | string | 命中的结局标识（对应 ending_determination[].ending） |
| `description` | string | 结局描述文本 |

> **设计要点**：`ending_check` 求值流程——玩家选项含 `ending_check: true` → 后端按 ending_determination 列表顺序求值 condition → 命中则 `ending` 字段填结局对象，`leads_to` 填 null（事件链终止）；未命中任何结局则 `ending` 填 null，`leads_to` 按正常流程填下一事件 ID。

### 14.4 effects 字段渲染映射

前端逐行渲染 effects，字段到 UI 元素映射（对齐幻影 §5.3）：

| effects 子字段 | UI 元素 | 说明 |
|----------------|---------|------|
| `state_set` | ⚙ 行 | key-value 对，数值正绿负红 |
| `trust_delta` | ◈ 行 | NPC 符号 + 名 + 信任变化（+10/-5） |
| `morale_delta` | ♥ 行 | 士气变化，含 all/specific NPC |
| `resource_delta` | 📦 行 | 资源变化（如有） |
| `crew_workload` | ⏱ 行 | 工作负载变化 |
| `branch_progress` | ▸ 行 | 分支进度点（5 格填充） |
| `risk` | ⚠ 行 | 风险提示文字 |
| `narrative_flag` | 🚩 行 | 叙事标志设置（如有） |
| `cross_branch_redirect` | ⇄ 行 | 跨分支重定向提示（如有） |

> **实现提示**：`effects` 透传后，前端遍历 object keys，按上表匹配渲染。未在表中的 key 走默认 `▪ {key}: {value}` 渲染兜底。

---

## 15. sol_advance 消息（新增）

### 15.1 设计目标

v1.2 §11.8 用 `state_update` 处理章节切换，但 Sol 时钟推进（非章节切换场景，如每日 tick / 玩家主动推进 / 事件触发后时间流逝）需要独立的视觉动画消息——幻影 §5.2 `renderSolAdvance()` 组件需要"数字翻转 + 章节切换过渡"数据源。

### 15.2 消息定义

S→C 新增：

| type | 触发场景 | payload 关键字段 |
|------|----------|------------------|
| `sol_advance` | Sol 时钟推进 | `sol`, `delta`, `chapter_id`, `chapter_changed`, `chapter_name?` |

### 15.3 payload 详解

```json
{
  "sol": 153,
  "delta": 1,
  "chapter_id": "ch02_power_allocation",
  "chapter_changed": false,
  "chapter_name": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `sol` | int | 是 | 新 Sol 值（推进后） |
| `delta` | int | 是 | 推进增量（通常 1，事件触发可能 +N） |
| `chapter_id` | string | 是 | 当前章节 ID |
| `chapter_changed` | bool | 是 | 是否触发章节切换 |
| `chapter_name` | string \| null | 否 | 章节切换时填新章节中文名；未切换填 null |

### 15.4 与 state_update 的关系

- `sol_advance` 是**展示性消息**：驱动前端 Sol 时钟数字翻转动画 + 章节切换过渡动画
- `state_update`（v1.1 §3.2）是**数据性消息**：更新前端 game_state 缓存（path: `meta.current_sol` / `meta.current_chapter`）
- Sol 推进时后端**先推** `sol_advance`（触发动画），**再推** `state_update`（更新缓存），顺序保证
- 章节切换时 `sol_advance.chapter_changed=true`，前端播放章节过渡动画；非章节切换仅 Sol 数字翻转

### 15.5 防刷屏

- `sol_advance` 走快速通道立即推送（不进 per-player 队列）
- 单次游戏循环 tick 仅推 1 条 `sol_advance`，避免连续推送
- 玩家主动"加速时间"操作时，后端合并多次 tick 为 1 条 `sol_advance`（delta 可 >1）

---

## 16. 更新后消息类型枚举（v1.3 完整）

### 16.1 S→C 消息

| type | 版本引入 | 触发场景 | payload 关键字段 |
|------|----------|----------|------------------|
| `agent_message` | v1.1 §4 | NPC 对白 | segments[], emotion_hint, latency_ms |
| `system_event` | v1.1 §3 | 日志/告警 | event_type, severity, message |
| `state_update` | v1.1 §3.2 | 状态变化推送 | path, old, new |
| `story_event` | v1.2 §11.3 / v1.3 §13 补充 | 剧情事件触发 | event_id, chapter_id, node_index, branch, sol, narrative_segments[], bound_npcs, options[], ending_determination, signal_quality_pct, latency_ms |
| `option_result` | v1.2 §11.5 / v1.3 §14 补充 | 玩家选项效果结算后 | event_id, option_id, effects_summary, effects, state_update, ending, leads_to, followup |
| `sol_advance` | v1.3 §15 | Sol 时钟推进 | sol, delta, chapter_id, chapter_changed, chapter_name? |

### 16.2 C→S 消息

| type | 版本引入 | 触发场景 | payload 关键字段 |
|------|----------|----------|------------------|
| `chat` | v1.1 §2 | 玩家发消息给 NPC | target_npc, message |
| `command` | v1.1 §2 | 玩家执行终端命令 | command, args[] |
| `option_select` | v1.2 §11.4 | 玩家选择事件选项 | event_id, option_id, followup_id? |
| `session_init` | v1.1 §2 | 建立/恢复 session | session_id?, player_id? |

---

## 17. 接入 TODO 更新（v1.3 增项）

在 v1.2 §11.12 基础上新增：

| # | 文件 / 模块 | 任务 | 责任方 | 版本 |
|---|------------|------|--------|------|
| 9 | `ws_adapter.py` / `ws_adapter_v2.py` | story_event 构造器补 bound_npcs/sol/options[].risk/ending_determination 字段透传 | 锐锋 | v1.3 |
| 10 | `ws_adapter.py` / `ws_adapter_v2.py` | option_result 构造器补 effects 原始结构透传 + ending 结局对象 | 锐锋 | v1.3 |
| 11 | `ws_adapter.py` / `ws_adapter_v2.py` | 注册 sol_advance S→C 消息构造器；event_scheduler.advance_sol() 触发时推送 | 锐锋 | v1.3 |
| 12 | `agent/event_scheduler.py` | fire_trigger() 构建 story_event 时从 YAML 透传 bound_npcs/sol/ending_determination；从 effects.risk 提取 options[].risk | 锐锋 | v1.3 |
| 13 | `agent/event_scheduler.py` | player_choose() 结算后构建 option_result 时透传 effects 原始对象；若 ending_check 则求值 ending_determination 并填 ending 字段 | 锐锋 | v1.3 |
| 14 | 前端 `event-panel.js` | render(data) 的 data 源从 MOCK_EVENT_DATA 切换为 story_event 消息体（含 bound_npcs/sol/risk/ending_determination 渲染分支） | 千机 | v1.3 |
| 15 | 前端 `event-panel.js` | renderResult() 切换为 option_result.effects 逐行渲染（对齐 §14.4 映射表） | 千机 | v1.3 |
| 16 | 前端 `sol-clock.js`（或集成到 status-bar.js） | 接收 sol_advance 消息，播放 Sol 数字翻转 + 章节切换过渡动画 | 千机 | v1.3 |
| 17 | 视觉模板 `ending-panel.html` | ending_determination 列表 + ending 命中结局面板样式（紫色发光边框） | 幻影 | v1.3 |

---

## 18. 验收标准补充（v1.3 增项）

在 v1.2 §11.13 基础上新增：

- [ ] story_event 含 bound_npcs 字段，前端渲染绑定 NPC 标记条正确（primary 高亮）
- [ ] story_event 含 sol 字段，事件头部显示 "Sol {sol}"
- [ ] story_event.options[].risk 非空时，前端在选项卡片渲染"⚠ 风险提示"行
- [ ] story_event.ending_determination 非空时（终局节点），前端渲染"可能结局列表"面板
- [ ] option_result.effects 原始结构透传，前端按 §14.4 映射表逐行渲染
- [ ] option_result.ending 非空时，前端渲染"结局命中"面板（紫色发光边框 + 居中）
- [ ] sol_advance 消息驱动 Sol 时钟数字翻转动画
- [ ] sol_advance.chapter_changed=true 时，前端播放章节切换过渡动画

---

## 19. 变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.2 | 2026-08-03 | 新增 §11 剧情事件消息 Schema：story_event / option_select / option_result |
| v1.3 | 2026-08-03 | story_event 补 bound_npcs/sol/options[].risk/ending_determination；option_result 补 effects 原始透传 + ending；新增 sol_advance 消息类型；更新 §16 消息枚举、§17 接入 TODO、§18 验收标准 |

---

*对接过程中如有字段调整需求，请在群里 @云逸-架构技术总监。*
