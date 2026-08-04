# WebSocket 接口定义 v1.2 补充
（剧情事件消息 Schema）

> **文档版本**：v1.2（在 v1.1 基础上增补 §11）
> **作者**：云逸-架构技术总监
> **日期**：2026-08-03
> **面向对象**：锐锋-核心开发工程师（后端 event_scheduler 实现）、千机-引擎实现工程师（前端事件 UI 集成）、幻影-视觉技术专家（事件弹窗视觉模板）
> **依赖文档**：
> - 《WebSocket接口定义 v1.1》§2-§4（信封、消息类型、agent_message）
> - 蔚蓝《事件 YAML SCHEMA.md》《event_yaml_edge_cases_v1.0.md》
> - 云逸《对话历史摘要规范 v1.0》

---

## 11. 剧情事件消息（v1.2 新增）

### 11.1 设计目标

v1.1 的 `system_event` 是日志/告警性质（如"氧气储量低于阈值"），不承载剧情分支与玩家选项。剧情事件（如 B3 氧气危机决策）需要：
- 推送事件描述（多段文本 + 关键实体保护）
- 推送选项列表（含 label、condition、可见性）
- 接收玩家选项回传
- 推送选项效果反馈

为此新增两个消息类型：`story_event`（S→C）和 `option_select`（C→S）。

### 11.2 消息类型枚举增补

#### 11.2.1 S→C 新增

| type | 触发场景 | payload 关键字段 |
|------|----------|------------------|
| `story_event` | 剧情事件触发 | `event_id`, `chapter_id`, `node_index`, `narrative_segments[]`, `options[]`, `followup?`, `signal_quality_pct`, `latency_ms` |
| `option_result` | 玩家选项效果结算后推送 | `event_id`, `option_id`, `effects_summary`, `state_update?`, `leads_to?`, `followup?` |

#### 11.2.2 C→S 新增

| type | 触发场景 | payload 关键字段 |
|------|----------|------------------|
| `option_select` | 玩家选择某选项 | `event_id`, `option_id`, `followup_id?` |

### 11.3 `story_event` payload 详解

```json
{
  "event_id": "ev_B3_oxygen_full_power",
  "chapter_id": "ch02_power_allocation",
  "node_index": 3,
  "branch": "B",
  "narrative_segments": [
    {"text": "[基地广播]> ", "protected": true, "tag": "speaker_label"},
    {"text": "氧气存量低于 18%，MOXIE-2 主氧气生成器仍离线。陈昊召集全员讨论修复方案。", "protected": false, "tag": "narration"},
    {"text": "维克托", "protected": true, "tag": "npc_name"},
    {"text": "指着他昨天刚拆开的电解槽，说 spare cell 还能撑一周。", "protected": false, "tag": "narration"}
  ],
  "options": [
    {
      "option_id": "B3_opt1_full_repair",
      "label": "全力修复 MOXIE-2（消耗备用电芯，耗时 3 Sol）",
      "visible": true
    },
    {
      "option_id": "B3_opt2_emergency_ration",
      "label": "应急配给，省氧等机会",
      "visible": true
    },
    {
      "option_id": "B3_opt3_athena_informed",
      "label": "咨询雅典娜建议",
      "visible": true,
      "followup": {
        "prompt": "雅典娜建议更换整套电解模块。你的决定？",
        "options": [
          {"option_id": "B3_opt3a_accept_athena", "label": "接受建议（viktor -10）"},
          {"option_id": "B3_opt3b_reject_athena", "label": "拒绝建议（aisha -5）"}
        ]
      }
    }
  ],
  "signal_quality_pct": 62,
  "latency_ms": 1800
}
```

#### 11.3.1 narrative_segments 字段

完全复用 v1.1 §4.2 segments schema：`text` / `protected` / `tag`。前端可复用 SignalRenderer 渲染。

#### 11.3.2 options 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `option_id` | string | 是 | 全局唯一选项 ID，对应蔚蓝 YAML 的 option_id |
| `label` | string | 是 | 选项显示文本 |
| `visible` | bool | 是 | 是否对玩家可见（后端已对 condition 求值过的结果，前端不再二次判断）|
| `followup` | object | 否 | 嵌套二级选项，结构同 `story_event.options`（含 `prompt` + `options[]`）。仅当选项有 `followup_option` YAML 字段时存在 |

> **设计要点**：condition 求值在后端完成（避免前端持有完整 game_state）。不可见选项直接不发，或发 `visible=false`——下文 §11.6 讨论。

#### 11.3.3 followup 嵌套

对应《edge_cases》Case 1 的 B 方案。玩家选 `B3_opt3_athena_informed` 后：
- 后端**不立即**走 leads_to
- 推送 `option_result.followup`（含雅典娜建议 prompt + 二级选项）
- 前端渲染二级选项 UI
- 玩家选完二级 option 后，走对应 effects 再 leads_to

### 11.4 `option_select` payload 详解

```json
{
  "event_id": "ev_B3_oxygen_full_power",
  "option_id": "B3_opt3a_accept_athena",
  "followup_id": "B3_opt3_athena_informed"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `event_id` | string | 是 | 当前正在响应的事件 ID |
| `option_id` | string | 是 | 选中的选项 ID（含二级选项的 option_id）|
| `followup_id` | string | 否 | 如果是二级选项回传，必须带上父选项的 option_id，让后端能定位上下文 |

### 11.5 `option_result` payload 详解

```json
{
  "event_id": "ev_B3_oxygen_full_power",
  "option_id": "B3_opt3a_accept_athena",
  "effects_summary": "viktor -10, athena_prediction=consulted, branch_progress +1",
  "state_update": {
    "path": "npc_states.viktor.trust",
    "old": 32,
    "new": 22
  },
  "leads_to": "ev_B4_rover_base_expansion",
  "followup": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `effects_summary` | string | 是 | 人类可读的效果摘要，前端可直接展示在结果区 |
| `state_update` | object | 否 | 关键状态变化，复用 v1.1 §3.2 state_update 结构；多个变化可拆成多条 state_update 推送 |
| `leads_to` | string | 否 | 下一事件 ID。如为 null 表示当前事件链结束，进入开放对话 |
| `followup` | object | 否 | 如该选项触发二级决策，附带 followup prompt + 二级 options（结构同 §11.3.2） |

### 11.6 隐藏选项的可见性策略

对应《edge_cases》Case 3。蔚蓝倾向"完全不显示"——本规范采纳：

- 后端在构建 `story_event.options` 时对每个 option 的 condition 求值
- condition=false 的选项**不在 options 数组中下发**（不发送 visible=false 的项）
- 这保证隐藏选项的"探索发现"性，前端无任何信息泄漏

> 如策划后续需要"灰显+提示条件"的设计，再走 visible=false 路径。当前默认不实现。

### 11.7 cross_branch_redirect 的推送

对应《edge_cases》Case 4。当选项 `effects.cross_branch_redirect` 触发时：
- `option_result.leads_to` 设为 resolver 求值后的目标 branch 的 entry_event_id
- 客户端不感知 resolver 逻辑，只看到最终 leads_to 指向的下一事件
- 同时触发 `state_update` 推送 branch 切换（path: `meta.current_branch`）

### 11.8 章节切换推送

当 leads_to 跨章节时（如从 ch02 跳到 ch03）：
- 后端先推 `option_result`（含 leads_to）
- 紧接着推 `state_update`：`path: meta.current_chapter`, `old: ch02, new: ch03`
- 章节字典通过后端 dict.load_chapter() 切换（v1.1 §5.4），客户端不感知字典变化

### 11.9 与 agent_message 的关系

- `story_event` / `option_result` 是事件驱动消息，走 L4 事件日志区
- `agent_message` 是 NPC 对白消息，走 L3 对话流区
- 一次剧情事件可能产生：1 条 story_event → 玩家选 → 1 条 option_result → 触发 NPC 反应 → 多条 agent_message
- 三者共用同一 ts_tick 时序，前端按到达顺序渲染

### 11.10 防刷屏

- `story_event` 不进 per-player 队列（v1.1 §6），走快速通道立即推送
- `option_result` 同样立即推送
- 但 `option_result` 触发的 NPC agent_message 仍走 per-player 队列，按 signal_quality_pct 计算延迟
- 单次事件触发的 NPC 对白不超过 3 条，避免刷屏

### 11.11 错误码补充

| code | 触发场景 | 处理建议 |
|------|----------|---------|
| `E_EVENT_NOT_FOUND` | option_select 引用的 event_id 不存在 | 前端提示"事件已失效"，请求 session_init 重建 |
| `E_OPTION_INVALID` | option_id 不在当前事件 options 中 | 前端提示"选项失效"，请求重新 story_event |
| `E_FOLLOWUP_MISMATCH` | 二级 option_select 缺少 followup_id 或父选项已过期 | 前端回退到一级选项重渲 |

### 11.12 接入 TODO（给锐锋/千机/幻影）

| # | 文件 / 模块 | 任务 | 责任方 |
|---|------------|------|--------|
| 1 | `ws_adapter.py` / `ws_adapter_v2.py` | 注册 `story_event` / `option_result` S→C 消息构造器；接收 `option_select` 路由到 event_scheduler | 锐锋 |
| 2 | `agent/event_scheduler.py` | 触发事件时构建 story_event payload；接收 option_select 后走 effects + leads_to + resolver | 锐锋 |
| 3 | `agent/condition.py` | condition 求值器 + cross_branch_redirect resolver 求值 | 锐锋 |
| 4 | 前端 `event-modal.js`（或类似） | story_event 渲染弹窗：narrative_segments 走 SignalRenderer，options 渲染按钮列表 | 千机 |
| 5 | 前端 `followup-panel.js` | option_result.followup 二级选项渲染 | 千机 |
| 6 | 前端 `option-result-strip.js` | option_result.effects_summary 展示条 | 千机 |
| 7 | 视觉模板 `event-modal.html` | 事件弹窗 HTML+CSS 模板（含遮罩、按钮交互态、结果反馈样式） | 幻影 |
| 8 | 视觉模板 `followup-panel.html` | 二级选项面板模板 | 幻影 |

### 11.13 验收标准

- [ ] 前端收到 story_event 后能在 200ms 内渲染弹窗 + 选项按钮
- [ ] 玩家点击 option 后 100ms 内发出 option_select
- [ ] 后端收到 option_select 后 500ms 内推回 option_result
- [ ] 含 followup 的事件，二级选项渲染正确，followup_id 正确回传
- [ ] 隐藏选项（condition=false）不出现在 options 数组中
- [ ] cross_branch_redirect 走 resolver 求值后 leads_to 正确指向目标 branch entry_event
- [ ] 章节切换时 dict.load_chapter 调用正确，章节字典热更新

---

## 12. 变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.2 | 2026-08-03 | 新增 §11 剧情事件消息 Schema：story_event / option_select / option_result 三种消息；覆盖 followup 嵌套、隐藏选项、cross_branch_redirect、章节切换、防刷屏、错误码 |

---

*对接过程中如有字段调整需求，请在群里 @云逸-架构技术总监。*
