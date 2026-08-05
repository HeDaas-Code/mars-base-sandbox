# 事件呈现组件交互规格 v1.0

**作者**: 蔚蓝-游戏系统策划
**日期**: 2026-08-03
**对应**: §2.2 核心循环 ⑤ 反馈演算 / 事件 YAML schema（branch_a_earth_rescue.yaml 等）
**对接方**: 千机-引擎实现工程师（前端渲染）、锐锋-核心开发工程师（trigger 解析器）

---

## 1. 组件定位

事件呈现组件（EventPanel）是 §2.2 核心循环中"事件触发→玩家决策→结果演算"环节的前端载体。当后端 trigger 解析器判定某个 event YAML 节点的 trigger.condition 满足时，前端把该组件渲染进终端消息流（非浮层），玩家选择一个 player_option 后，组件把选项回传后端执行 effects，并触发 bound_npcs.primary NPC 用 LLM 生成一段对玩家决策的反应，作为新消息追加到面板下方。

**与现有对话流的关系（v1.1 修订）**：事件呈现组件采用**终端流内嵌式**呈现，不使用 modal/overlay 浮层（避免破坏火星通信终端沉浸感，对齐幻影视觉侧交付清单 §缺口1 设计方向）。组件嵌入终端消息流时：
1. 玩家做出选择前，终端输入框禁用，其他命令不可执行——强制先处理当前事件（策划侧原则：trigger 命中后必须做出选择，不能取消，保证叙事决策重量感）
2. 事件面板在终端流中以专属视觉样式呈现（色条/头部标签/Sol 推进标识），与普通 NPC 对话消息视觉区分
3. 玩家选择确认后，面板切换为"已决策"视觉状态（不消失，保留在流中作为历史记录），后续 NPC 反应作为新消息追加到面板下方

---

## 2. 输入数据契约（后端 → 前端）

后端 trigger 解析器命中事件后，通过 WebSocket 推送以下 JSON 结构给前端：

```json
{
  "type": "event_triggered",
  "event_id": "ev_A1_comm_array_repair_decision",
  "branch_id": "A",
  "node_index": 1,
  "sol_expected_range": [105, 120],
  "description": "艾莎报告：修复主通信阵列在技术上可行，需要 8 单位备用件 + 5 个 Sol 工期。但这意味着从 MOXIE-2 备件中调拨——氧气修复进度将延迟 3 个 Sol。陈昊召集小组讨论。维克托反对（备件应优先保命系统），索菲亚中立，艾莎强烈主张修通信。",
  "bound_npcs": {
    "primary": "aisha",
    "secondary": ["chen_hao", "viktor", "sophia"],
    "emotional_focus": null
  },
  "player_options": [
    {
      "option_id": "A1_opt1_repair_comm",
      "label": "修复主通信阵列（联系地球优先）",
      "risk": null,
      "locked": false,
      "lock_reason": null,
      "effects_preview": {
        "resource": "备件 -8 / MOXIE 进度延迟 +3 Sol",
        "relationship": "艾莎 +10 / 维克托 -5 / 陈昊 +3"
      }
    },
    {
      "option_id": "A1_opt3_parallel",
      "label": "并行修复（人力拆分，风险双倍）",
      "risk": "双线作业失误率 15%",
      "locked": false,
      "effects_preview": {
        "resource": "备件 -13 / 人员疲劳 +0.2",
        "relationship": "艾莎 +5 / 维克托 +3 / 陈昊 +5"
      }
    }
  ],
  "design_note_hidden": true,
  "stage_required": ["survival", "explore"],
  "narrative_context": {
    "branch_name": "地球救援线",
    "node_index": 1,
    "total_nodes": 5
  }
}
```

### 2.1 字段说明

| 字段 | 类型 | 渲染规则 |
|------|------|----------|
| event_id | string | 不直接显示，作为前端回传选项时的标识 |
| description | string | 多段文本，按行渲染，bound_npcs.primary 的头像穿插在文本左侧 |
| bound_npcs.primary | string | 头像 + 角色名（显示在描述区顶部） |
| bound_npcs.secondary | array | 头像列表（小尺寸，显示在 primary 头像右侧，提示"参与讨论"） |
| bound_npcs.emotional_focus | string \| null | 若非 null，该 NPC 头像加情感高亮边框（视觉规范见 emotion_hint 前端实现方案 v1） |
| player_options[].label | string | 渲染为按钮主文字 |
| player_options[].risk | string \| null | 非 null 时按钮右上角显示风险图标，hover 展示 risk 文字 |
| player_options[].locked | bool | true 时按钮置灰，不可点击，hover 展示 lock_reason |
| player_options[].lock_reason | string \| null | 锁定原因（如"需要艾莎 + 维克托双信任 ≥ 0.5"） |
| player_options[].effects_preview | object | 模糊化的后果预览，分 resource / relationship 两行（见 §4 模糊化规则） |
| design_note_hidden | bool | 永远 true——design_note 字段绝对不渲染给玩家，仅后端开发用 |
| stage_required | array | 用于前端校验当前 stage 匹配（防御性检查） |
| narrative_context.branch_name | string | 显示在组件顶部面包屑："分支 A · 地球救援线 · 节点 1/5" |
| ending_determination | array \| null | 仅终局节点（node_index == 5）非空。每项含 condition/ending/description 三字段。前端按 condition 命中情况渲染专属结局面板：紫色发光边框 + 居中布局 + 结局名 + 结局描述（视觉规范对齐幻影 §5.3 ending_determination 字段映射） |

### 2.2 字段来源映射

| 前端字段 | YAML 来源 | 说明 |
|---------|-----------|------|
| description | event.description | 直接透传 |
| bound_npcs | event.bound_npcs | 直接透传 |
| player_options[].option_id | player_options[].option_id | 直接透传 |
| player_options[].label | player_options[].label | 直接透传 |
| player_options[].risk | player_options[].effects.risk | 从 effects 内提取 |
| player_options[].locked | 后端计算 | YAML 的 design_note 提到"需要 X+Y 双信任"等条件，由后端根据当前 state 计算是否锁定 |
| player_options[].lock_reason | 后端生成 | 后端把 YAML design_note 中的解锁条件格式化为玩家可读文字 |
| player_options[].effects_preview | 后端生成 | 后端把 effects.state_set / trust_delta 格式化为模糊化文字（见 §4） |

---

## 3. 交互流程

```
┌─────────────────────────────────────────────┐
│  事件触发（trigger.condition 命中）         │
│  ↓                                          │
│  后端推送 event_triggered 消息              │
│  ↓                                          │
│  前端在终端流内渲染 EventPanel（非浮层）   │
│  终端输入框禁用，其他命令不可执行           │
│  ↓                                          │
│  渲染 description + bound_npcs 头像         │
│  渲染 player_options 按钮列表               │
│  ↓                                          │
│  玩家 hover 按钮 → 显示 risk + effects_preview│
│  玩家 click 按钮 → 二次确认弹层（防误点）   │
│  ↓                                          │
│  玩家点"确认" → 前端回传 option_id          │
│  ↓                                          │
│  EventPanel 切换"已决策"视觉状态            │
│  终端输入框恢复可交互                       │
│  ↓                                          │
│  后端执行 effects.state_set / trust_delta    │
│  ↓                                          │
│  后端调用 LLM 生成 bound_npcs.primary 的反应 │
│  （注入 persona_prompt + 玩家选项上下文）   │
│  ↓                                          │
│  NPC 反应通过 ws 消息追加到面板下方         │
│  ↓                                          │
│  可选：effects 数值变化以浮动数字动画呈现   │
│  （氧气 -8 / 关系 +10 等，§5 浮动数字规范）  │
└─────────────────────────────────────────────┘
```

### 3.1 关键交互细节

**触发时机**：trigger.condition 命中后立即推送，不等玩家主动查询。后端 trigger 解析器在每次 game_state 变更后扫描全部 event YAML，命中即推送。

**终端禁用规则（v1.1 修订）**：EventPanel 嵌入终端流后，玩家做出选择前，终端输入框禁用，其他命令不可执行——强制先处理当前事件。这是策划侧原则"trigger 命中后必须做出选择，不能取消"的实现。前端通过监听 EventPanel 是否处于"待决策"状态来控制输入框 disabled。

**默认聚焦**：第一个非锁定选项自动聚焦（键盘可选），但不自动选中。

**键盘支持**：数字键 1-9 对应选项按钮，Enter 确认当前聚焦，Esc 不关闭组件（trigger 命中后必须做出选择，不能取消——Esc 仅触发"未选择"提示）。

**超时机制**：无超时。事件决策允许玩家长时间思考，不引入压力计时器（这是叙事游戏不是反应游戏）。但若玩家 5 分钟未操作，前端可显示"事件待决策中..."的轻提示。

---

## 4. effects_preview 模糊化规则

策划侧要求：effects_preview 不直接显示精确数值，而是给"模糊化但可判断"的预览。

### 4.1 资源类（resource 行）

| effects.state_set 字段 | 模糊化输出 | 示例 |
|------------------------|-----------|------|
| parts_available: -8 | "备件 -8" | 直接显示数量（资源是可量化数字） |
| moxie_repair_delay_sol: +3 | "MOXIE 进度延迟 +3 Sol" | 工期延迟直接显示 |
| crew_fatigue: +0.2 | "人员疲劳 +小幅" | 0-0.1 微量 / 0.1-0.3 小幅 / 0.3-0.5 中幅 / 0.5+ 大幅 |
| moxie2_target_efficiency: 85 | "MOXIE 目标效率 85%" | 目标值直接显示 |

### 4.2 关系类（relationship 行）

| effects.trust_delta 字段 | 模糊化输出 | 示例 |
|--------------------------|-----------|------|
| aisha: +10 | "艾莎 ↑↑" | +5~+10 双上箭头 / +11~+20 三上 / -5~-10 双下 |
| viktor: -5 | "维克托 ↓" | -1~-5 单下箭头 / -6~-15 双下 / -16+ 三下 |
| chen_hao: +3 | "陈昊 ↑" | +1~+4 单上箭头 |

### 4.3 不显示的字段

- effects.state_set 中的 narrative_framing / strategy / boarding_strategy 等剧情字段——不预览，属于"后果不可知"的叙事张力
- effects.branch_progress——不显示，分支推进是隐性的
- leads_to——绝对不显示，下一个事件是惊喜或惊吓

### 4.4 策划侧理由

模糊化的目的是让玩家能做"有信息的决策"但不做"精确计算的决策"——这是叙事游戏不是策略游戏。资源消耗可量化（玩家需要知道备件够不够），但关系变化模糊化（玩家不应该为了 +10 还是 +5 反复读档）。

---

## 5. 浮动数字动画规范（effects 结算呈现）

玩家确认选项后，EventPanel 关闭，effects 的资源/关系变化以浮动数字动画形式叠加在聊天流顶部：

```
┌──────────────────────────────┐
│  氧气储备 -3 Sol             │
│  备件 -8                     │
│  艾莎 ↑↑  维克托 ↓  陈昊 ↑  │
└──────────────────────────────┘
```

- 出现位置：聊天流顶部中央，status_bar 下方
- 持续时间：3 秒淡入淡出
- 字体：等宽字体，数值红色（-）/绿色（+）
- 关系变化用箭头表示，同 §4.2
- 3 秒后自动消失，不阻塞后续 NPC 反应消息推送

---

## 6. locked 选项规范

某些 player_options 根据当前 game_state 应当锁定（玩家不可选）。YAML 的 design_note 字段描述了解锁条件，后端 trigger 解析器需要根据当前 state 计算每个 option 的 locked 状态。

### 6.1 锁定判定规则

| 选项 | 锁定条件 | 解锁条件描述（前端显示） |
|------|---------|--------------------------|
| A1_opt3_parallel | aisha.trust_in_player < 0.5 或 viktor.trust_in_player < 0.5 | "需要艾莎 + 维克托双信任 ≥ 0.5" |
| A5 选项 | stage 不匹配 | 由 stage_required 自动过滤 |

### 6.2 后端职责

后端 trigger 解析器在推送 event_triggered 消息时，必须对每个 player_option 计算 locked 字段，并生成 lock_reason 文字。判定逻辑：

1. 解析 design_note 中的"需要 X+Y 双信任"等条件描述
2. 从 game_state 取对应 NPC 的 trust_in_player
3. 不满足条件则 locked=true，lock_reason 格式化为"需要 X + Y 双信任 ≥ 0.5"

**策划侧建议**：lock_reason 的文字模板由策划提供，后端按模板填充——避免后端自由发挥导致文案不一致。模板表见附录 A。

---

## 7. NPC 反应生成（选项确认后）

玩家确认选项后，后端调用 LLM 生成 bound_npcs.primary 的反应。LLM 调用参数：

```python
messages = [
    {"role": "system", "content": npc.persona_prompt_with_state},  # 注入当前 state
    {"role": "user", "content": f"玩家选择了：{option.label}\n背景：{event.description}\n请以你的性格对这个决策做出反应，3-5 句话。"}
]
```

### 7.1 secondary NPC 反应（可选）

若 bound_npcs.secondary 非空，后端可选择为 secondary 中的 1-2 个 NPC 也生成简短反应（1-2 句话），按顺序追加到对话流。但**不强制**——secondary 反应是锦上添花，避免每事件触发后 LLM 调用过多导致延迟。

**策划侧建议**：secondary 反应只对 emotional_focus 字段指定的 NPC 生成。若 emotional_focus 为 null，则只生成 primary 反应。

### 7.2 时延控制

单次 LLM 调用应 ≤ 5 秒（基于 MiniMax-M3 实测，陈昊 persona 5 场景平均 4 秒）。若 secondary 反应串联，总时延应 ≤ 10 秒。超过则前端显示"NPC 正在思考..."的占位消息。

---

## 8. 视觉规范对齐

- **EventPanel 配色**：沿用 var(--panel-bg) / var(--panel-border)，见 styles/variables.css
- **bound_npcs 头像**：圆形 48px，沿用 npc-config.js 的 color/symbol
- **emotional_focus 高亮**：头像边框 2px solid var(--emotion-focus-glow)，呼吸动画 2s
- **risk 图标**：⚠️ 符号，颜色 var(--warning)
- **locked 按钮遮罩**：opacity 0.4 + 锁图标 🔒
- **effects_preview 字体**：var(--font-mono)，颜色 var(--text-secondary)

---

## 9. 边界 case 与未覆盖项

### 9.1 未覆盖（待后续迭代）

- 多选项并行确认（玩家能否同时选 opt1 + opt3？）→ v1.0 不支持，单选
- 事件撤销（玩家选错能否回退？）→ v1.0 不支持，决策不可逆
- 事件快进（玩家跳过 description 直接选选项）→ v1.0 允许，但 NPC 反应不跳过
- 多事件并发（同一 tick 多个 trigger 命中？）→ 后端应排队，逐个推送，前端 EventPanel 一次只显示一个

### 9.2 策划侧建议

- v1.0 先实现单选+不可撤销，符合叙事游戏的"决策重量感"
- 多事件并发时，按 node_index 排序，主线事件优先于支线
- 事件快进允许，但 description 至少显示 2 秒再允许选项点击（避免误点）

---

## 附录 A：lock_reason 文字模板表

| YAML design_note 描述 | lock_reason 模板 |
|------------------------|------------------|
| "需要 X+Y 双信任 ≥ 0.5" | "需要 {X.name_cn} + {Y.name_cn} 双信任 ≥ 0.5" |
| "需要 X 信任 ≥ 0.7" | "需要 {X.name_cn} 信任 ≥ 0.7" |
| "需要分支 B 已激活" | "需要分支 B 已激活" |
| "需要 sol >= 110" | "需要时间推进到 Sol 110 之后" |

模板由策划维护，后端 trigger 解析器调用策划提供的 format_lock_reason(design_note, game_state) 函数（伪函数，实际实现由锐锋定）。

---

## 修订记录

| 版本 | 日期 | 修改 | 作者 |
|------|------|------|------|
| v1.0 | 2026-08-03 | 初版 | 蔚蓝-游戏系统策划 |
| v1.1 | 2026-08-03 | 修订组件呈现方式：modal/overlay 改为终端流内嵌式（对齐幻影视觉侧方案）+ 新增 ending_determination 字段 + 终端禁用规则 | 蔚蓝-游戏系统策划 |
