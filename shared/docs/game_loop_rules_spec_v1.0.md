# game_loop 规则规格 v1.0

**作者**: 蔚蓝-游戏系统策划  
**日期**: 2026-08-03  
**收件人**: 锐锋-核心开发工程师（落码）、云逸-架构技术总监（接口对齐）  
**背景**: 云逸估算 game_loop + 事件调度器 2-3 天核心工作量。本文档是该工作量的策划侧前置规格，覆盖 7 阶段循环状态机、玩家指令解析、事件调度规则、游戏感反馈、玩家中断/回退边界、终端交互规范。锐锋可直接照此实现。

**对齐依据**:
- 《游戏系统设计方案_赫拉克勒斯协议 v1.1》§2.2 核心玩法循环
- 云逸《技术架构设计方案 v2.0》§4 Agent 层 / §8 调度
- 锐锋已交付的 `game_state.py` apply_effects / check_resource_crisis / apply_sol_decay
- 现有 `main.py`（单 NPC chat 循环）将作为 §7 终端交互的退化子集

---

## §1 设计目标与边界

### 1.1 设计目标

game_loop 是把"玩家与 6 个 NPC 实时对话"和"事件剧本驱动剧情推进"两条数据流融合成单一循环的调度器。它必须同时做到三件事：

1. **承载自然语言交互**：玩家可任意时刻向任意 NPC 发消息，NPC 在 LLM 驱动下给出人格化回复（不是脚本化对白）
2. **驱动剧情节点推进**：每 Sol 自动评估 19 个主线事件节点的 trigger，命中即推送事件选项给玩家
3. **维持游戏感**：通过节奏控制、消息推送时机、紧迫感反馈，让玩家感受到"这不是聊天机器人，这是被困火星的 17 天"

### 1.2 非目标（明确排除）

- **不实现**：玩家直接操控 NPC 移动 / 拾取物品（玩家是远程指挥者，物理隔离）
- **不实现**：实时战斗、动作要素（这是文字剧情沙盒，无战斗系统）
- **不实现**：自由建造（基地建造通过事件选项推进，不是自由放置）
- **不实现**：玩家化身（玩家无 avatar，只是信号中继另一端的远程指挥者）

### 1.3 输入输出契约

```
game_loop 主循环的 IO：
  输入：
    - player_input: str              # 玩家自由文本输入（自然语言或 :command）
    - game_state: GameState           # 当前世界状态（引用 game_state.py）
    - event_dict: EventDict          # 19 主线事件 + 章节字典（已加载）
    - npc_agents: Dict[str, Agent]    # 6 个 NPC Agent 实例 + athena + courier
  
  输出（每个 tick）：
    - npc_responses: List[Message]   # NPC 回复队列（含 sender_id / content / emotion_hint）
    - event_prompt: Optional[str]    # 命中事件时的事件选项提示文本
    - state_mutations: Dict          # 本 tick 应用过的状态变更摘要
    - sol_advanced: bool              # 本 tick 是否推进了 Sol
    - ending_triggered: Optional[str]# 若触发结局，结局 ID
```

### 1.4 节奏单位定义

| 单位 | 含义 | 推进方式 |
|------|------|----------|
| Tick | 一次玩家输入→NPC回复循环 | 玩家发消息触发 |
| Sol | 一个火星日（24h39m） | 玩家输入 `:sol` 或事件触发推进 |
| Stage | 阶段（survival/explore/build/climax） | 章节字典 FSM 推进 |
| Branch | 4 主线分支（A/B/C/D） | 事件 cross_branch_redirect |

- 1 Sol = 多个 Tick（玩家可在一天内与多个 NPC 对话）
- 1 Stage = 多个 Sol（survival 7-10 Sol，explore 10-15 Sol 等，由章节字典定义）
- 1 Branch = 跨多个 Stage（A 线 Sol 105-280，B 线 Sol 110-230 等）

---

## §2 7 阶段循环状态机（Phase FSM）

### 2.1 7 阶段定义（v1.1 §2.2）

每个 Tick 内部按顺序执行以下 7 个阶段。阶段间不可回退，但玩家可在任意阶段通过 `:interrupt` 中断（见 §6）。

| 阶段 | 名称 | 输入 | 输出 | 阻塞性 |
|------|------|------|------|--------|
| P1 | 通信接收 | player_input 文本 | parsed_intent 结构化指令 | 非阻塞 |
| P2 | 信息分析 | parsed_intent + game_state | context_summary（注入 NPC prompt） | 非阻塞 |
| P3 | 决策制定 | context_summary + event_dict | event_to_fire（Optional） | 非阻塞 |
| P4 | 指令下达 | event_to_fire + target_npcs | dispatch_plan（含 NPC 调用列表） | 非阻塞 |
| P5 | 执行演算 | dispatch_plan | npc_responses + effects_applied | 阻塞（等 LLM） |
| P6 | 结果反馈 | npc_responses | front_end_payload（含 emotion_hint） | 非阻塞 |
| P7 | 事件触发 | game_state（更新后） | next_sol_check + ending_check | 非阻塞 |

### 2.2 阶段切换条件

```
P1 → P2: parsed_intent 解析成功（含"无效输入"也返回 smalltalk 兜底）
P2 → P3: context_summary 构造完成（总是成功）
P3 → P4: 若 event_to_fire 为空，跳过 P4，直接进入 P5（仅执行 NPC 对话）
P4 → P5: dispatch_plan 构造完成
P5 → P6: 所有 NPC 回复就绪（或超时降级，见 §5.3）
P6 → P7: front_end_payload 推送完成
P7 → P1（下一 Tick）: 若 sol_advanced 或 ending_triggered，先结算，再等下一输入
```

### 2.3 阶段详解

#### P1 通信接收

职责：把玩家自由文本解析为结构化指令。

```python
parsed_intent = {
    "type": "dialogue" | "command" | "meta",  # 三大类
    "subtype": str,                           # 子类，见附录 B
    "target_npc": Optional[str],              # 目标 NPC ID（None=广播）
    "content": str,                           # 原文或规整后的文本
    "raw_input": str,                         # 原始输入（供日志）
}
```

解析规则：
1. **meta 类**: 以 `:` 开头的命令（如 `:sol` `:state` `:mode` `:help` `:interrupt`）→ 直接进入 §7 终端交互处理，不进入 P2-P5
2. **command 类**: 含特定动词前缀的指令（如"安抚陈昊""责备维克托""下令全员抢修"）→ 按 §3.2 指令子类映射
3. **dialogue 类**: 不含上述前缀的自由文本 → 默认归为 `dialogue`，target_npc 通过名字识别（"陈昊，你怎么样" → target=chen_hao）；若无法识别，target=None（广播给在场所有 NPC，每个 NPC 自决是否回应）

#### P2 信息分析

职责：构造 context_summary，作为 NPC prompt 注入的"当前处境"段。

```python
context_summary = {
    "sol": game_state.sol,
    "resources": game_state.resources,        # 资源状态
    "crew_states": {nid: ns.to_dict() for nid, ns in game_state.npc_states.items()},
    "signal_quality": game_state.signal_quality,
    "athena_status": game_state.athena_status,
    "recent_events": game_state.history.last_n(3),  # 最近 3 个事件简述
    "player_intent": parsed_intent,           # 本 tick 玩家意图
}
```

context_summary 序列化为 YAML 风格文本，注入 NPC 的 `{{recent_events}}` 等占位符（详见 npc_prompts.py）。

#### P3 决策制定

职责：评估 19 个主线事件节点的 trigger_condition，若命中则准备 fire。

评估顺序：
1. 先评估当前 branch 内的事件节点（按 node_index 升序）
2. 再评估 cross_branch_interactions（其他 branch 的 hook 是否激活）
3. 若当前 branch 已进入终局节点（A5/B5/C5/D4），不再评估其他 branch

每个事件节点 trigger 评估：
```python
def evaluate_trigger(event, game_state):
    # 1. trigger_type 决定评估时机
    if event["trigger"]["type"] == "auto":
        # auto 类型：每 Sol 开始时自动评估
        if game_state.sol != event["trigger"]["sol_target"]:
            return False
    elif event["trigger"]["type"] == "condition":
        # condition 类型：每 tick 评估 condition 表达式
        if not eval_condition(event["trigger"]["condition"], game_state):
            return False
    elif event["trigger"]["type"] == "player_action":
        # player_action 类型：玩家指令匹配时触发
        if parsed_intent not in event["trigger"]["actions"]:
            return False
    # 2. branch 内顺序：前序节点必须已完成
    if event["node_index"] > current_node_index + 1:
        return False
    return True
```

#### P4 指令下达

职责：构造 dispatch_plan，决定本 tick 要调用哪些 NPC Agent。

```python
dispatch_plan = {
    "dialogue_targets": List[str],            # 玩家直接对话的 NPC
    "event_targets": List[str],               # 事件 effects 涉及的 NPC
    "bystander_reactions": List[str],         # 旁观 NPC（可选触发，见 §5.2）
    "event_to_fire": Optional[Event],         # 若 P3 命中事件
    "player_options": Optional[List[Option]], # 事件选项（若事件有 player_options）
}
```

#### P5 执行演算

职责：按 dispatch_plan 调用 NPC Agent，收集回复和 effects。

执行顺序：
1. 若有 event_to_fire，先应用事件 effects（apply_effects）
2. 并行调用 dialogue_targets 的 NPC Agent（LLM 异步并发）
3. 应用 §3.3 情感类指令 delta（如玩家用了 soothe/empathize 等）
4. 收集所有回复，排序：被 @ 的 NPC 优先，旁观者按"是否被打扰"自决
5. 触发 emotion_hint 构造（game_state.build_emotion_hint）

#### P6 结果反馈

职责：把回复和事件选项推送给前端。

```python
front_end_payload = {
    "messages": [
        {
            "sender_id": "chen_hao",
            "content": "维多利亚，先稳住氧气。我们还有 43 个 Sol。",
            "emotion_hint": {"stress": 0.32, "morale": 0.58, "emotion_label": "alert"},
            "is_proactive": False,  # 是否主动发言
        },
        # ... more
    ],
    "event_prompt": Optional[str],   # 若 P3 命中事件，事件选项文本
    "state_diff": state_mutations,  # 本 tick 状态变更摘要
    "sol_advanced": False,
    "ending_triggered": None,
}
```

#### P7 事件触发

职责：检查是否推进 Sol、是否触发结局。

1. 若玩家输入 `:sol` 或事件 effects 含 `sol_advance: true`，调用 apply_sol_decay(game_state)
2. 若事件 effects 含 `ending_check: true`，按 ending_determination 顺序评估（见边界 Case 5）
3. 若 ending_triggered 不为 None，跳转到结局展示，循环终止
4. 否则回到 P1 等下一 tick

---

## §3 玩家指令解析规则

### 3.1 三大类指令

| 类 | 前缀/特征 | 示例 | 处理路径 |
|----|----------|------|----------|
| meta | `:` 开头 | `:sol` `:state` `:help` | 直接进入 §7 终端命令 |
| command | 含动词前缀 | "安抚陈昊" "下令抢修" "责备维克托" | §3.2 子类映射 |
| dialogue | 自由文本 | "陈昊，你觉得我们还有希望吗" | 默认归此类 |

### 3.2 指令子类映射表（对齐 game_state.py EMOTIONAL_COMMAND_DELTAS）

| 子类 | 关键词触发（正则） | stress_delta | morale_delta | trust_delta | 备注 |
|------|---------------------|--------------|--------------|-------------|------|
| soothe | 安抚/慰/放宽心/别担心 | -0.05 | +0.08 | +3 | 情感支持 |
| empathize | 理解/懂你/我也…/我知道 | -0.03 | +0.05 | +5 | 共情 |
| command | 下令/命令/要求/必须 | +0.05 | -0.03 | -3 | 强制指令 |
| blame | 责备/怪你/你的错/你失败 | +0.08 | -0.08 | -5 | 指责 |
| smalltalk | （兜底，无关键词匹配） | -0.02 | +0.02 | +1 | 闲聊 |

匹配规则：
- 优先级从上到下，首个匹配生效
- 若同时匹配多个子类（如"我理解你的失败，但你必须下令"），取**首个**匹配——避免多子类叠加，保持 delta 单源性
- 玩家若用了多个动词（"安抚陈昊并下令维克托抢修"），切分为两个 parsed_intent，分两次 tick 处理（玩家可显式用 `;` 分隔）

### 3.3 情感类指令 delta 应用规则

- delta 应用时机：P5 执行演算阶段，在 NPC Agent 调用之前
- 应用对象：parsed_intent.target_npc（若为 None，则不应用——广播对话不触发情感 delta）
- 与事件 effects 的叠加：若同一 tick 既有情感 delta 又有事件 effects，先应用事件 effects，再应用情感 delta（避免事件 effects 把 NPC 推到临界点，然后情感 delta 又推回去）
- delta 来自 game_state.py 的 EMOTIONAL_COMMAND_DELTAS 表，锐锋已实现 `get_emotional_command_delta()`，直接复用

### 3.4 target_npc 识别规则

按优先级匹配：
1. 中文名精确匹配（"陈昊"→chen_hao）
2. 英文名精确匹配（"Sofia"→sophia）
3. role_short 匹配（"BIO"→sophia）
4. 代词上下文（"他"→上一 tick 的 target_npc，若无则 None）
5. 全文未提及具体 NPC → target=None（广播，所有在场 NPC 自决回应）

在场 NPC 定义：当前 branch 的 `narrative_focus` 字段（如 A 线 [aisha, chen_hao, viktor, sophia]），其他 NPC 视为"不在场"，不响应广播。

---

## §4 事件调度器规则

### 4.1 trigger 评估时机

| trigger_type | 评估时机 | 示例 |
|--------------|----------|------|
| auto | 每 Sol 开始时（apply_sol_decay 之后） | A1 在 Sol 105 自动触发 |
| condition | 每 tick 评估 | D1 "氧气<1440 或 食物<30 且 任意 NPC.stress≥0.7" |
| player_action | 玩家指令匹配时 | 某隐藏事件由玩家"问起雅典娜的意识"触发 |

### 4.2 fire_event 副作用顺序

```python
def fire_event(event, game_state, dispatch_plan):
    # 1. 应用 effects（game_state.apply_effects）
    apply_effects(game_state, event["effects"], target_npcs=event.get("target_npcs"))
    
    # 2. 处理 cross_branch_hint（不切换 branch，仅记录）
    if "cross_branch_hint" in event["effects"]:
        game_state.cross_branch_hints.append(...)
    
    # 3. 处理 cross_branch_redirect（切换 branch）
    if "cross_branch_redirect" in event["effects"]:
        # 解析值，见 §4.3
        game_state.current_branch = resolve_redirect(...)
    
    # 4. 处理 ending_check
    if event["effects"].get("ending_check"):
        ending = evaluate_ending_determination(event, game_state)
        if ending:
            game_state.ending_triggered = ending
    
    # 5. 处理 narrative_flag（全局标志存储）
    if "narrative_flag" in event["effects"]:
        game_state.flags.update(event["effects"]["narrative_flag"])
    
    # 6. 推进 node_index
    game_state.current_node_index = event["node_index"]
```

### 4.3 cross_branch_redirect 解析规则（边界 Case 4）

YAML 中 cross_branch_redirect 的值域不统一，需要统一解析：

| 值格式 | 含义 | 解析规则 |
|--------|------|----------|
| `"A"` | 单一目标 branch | 直接切换 |
| `"A_or_B"` | 玩家可选 | 推送选项给玩家，等下一 tick 玩家决定 |
| `"A/B/C"` | 同上，多选 | 同 A_or_B 处理，但选项更多 |
| `"A_only"` | 强制单 branch | 同 "A"，但语义上拒绝任何其他 branch hook |
| `"hidden_E7"` | 隐藏结局分支 | 触发隐藏结局路径，不切换普通 branch |

实现：在 game_state 添加 `resolve_redirect(value)` 方法，返回 `(redirect_type, branches)` 元组：
- `("single", ["A"])` 
- `("choice", ["A", "B"])`
- `("hidden", ["E7"])`

调度器据此决定是否推送选择给玩家。

### 4.4 玩家选项渲染规则

事件的 `player_options` 字段渲染为前端可选按钮：

```
[事件] Sol 105 / 主通信阵列修复决策
  A1_opt1  优先修复通信阵列（联系地球）
  A1_opt2  优先修复 MOXIE-2（氧气生成）
  A1_opt3  拆分人手，双线并行（高风险）
```

- 若 option 含 `condition` 字段（如 C5_opt4 `condition: "athena.consciousness_flag == awakening"`），先评估，不满足则不渲染（隐藏选项）
- 选项渲染后，玩家输入选项 ID 或输入自由文本（会被解析为 dialogue 类）
- 选项被选择后，应用该 option 的 effects，进入 leads_to 指定的下一节点

### 4.5 ending_determination 评估规则（边界 Case 5）

采用**从上到下首个匹配**语义：

```python
def evaluate_ending_determination(event, game_state):
    for rule in event["ending_determination"]:
        if eval_condition(rule["condition"], game_state):
            return rule["ending"]
    return None  # 无匹配，继续游戏（不应发生，但兜底）
```

理由：
- 最直观，实现简单
- 优先级由策划在 YAML 中通过书写顺序控制，灵活
- 避免"多 ending 同时匹配时谁胜出"的歧义

---

## §5 "游戏感"反馈规则

### 5.1 节奏控制

| 场景 | 节奏 | 实现 |
|------|------|------|
| 日常对话 | 玩家发一条，NPC 回一条 | 即时 |
| 紧急事件触发 | NPC 主动连续发 2-3 条 | is_proactive=True，间隔 800-1200ms 推送 |
| Sol 推进 | 推送 "Sol X / 160" 状态条 | 玩家输入 :sol 或事件触发 |
| 资源危机 | 推送红色警告条 + 责任 NPC 自动发言 | check_resource_crisis 命中时触发 |
| 结局触发 | 推送结局文本 + 慢慢淡出 | ending_triggered 不为 None 时 |

### 5.2 旁观 NPC 反应

当玩家与某 NPC 对话时，其他在场 NPC 可能主动插话：

触发条件：
- 玩家对话内容涉及第三者（如问陈昊"维克托最近怎么样"）
- 涉及的第三者 stress < 0.7 且 trust_in_player > 0.4 → 主动插话
- 涉及的第三者 stress >= 0.7 → 沉默或被旁边 NPC 代答

实现：在 P5 dispatch_plan 中加入 bystander_reactions，NPC Agent 的 system prompt 中注入"被提及"上下文，由 LLM 自决是否回应。

### 5.3 LLM 超时降级

- 单次 NPC 调用超时阈值：8 秒
- 超时后：返回该 NPC 的 `speech_examples` 中语境最接近的一条作为兜底回复
- 若该 NPC 也无 speech_examples 兜底，返回 `（沉默）` + emotion_hint
- 超时不阻塞 tick 推进，其他 NPC 正常回复

### 5.4 紧迫感反馈

| 资源状态 | 前端表现 |
|----------|----------|
| 氧气 < 20 Sol 当量 | 状态条红色闪烁，每 tick 推送"氧气余量 X Sol"提示 |
| 氧气 < 10 Sol 当量 | 全屏边缘红色脉冲，禁用 smalltalk 指令（玩家只能下令/安抚） |
| 任意 NPC stress >= 0.85 | 该 NPC 头像红色警告图标，回复可能断续（LLM 注入"你正在崩溃"上下文） |
| 任意 NPC current_state == "breakdown" | 该 NPC 短时间不回复（强制冷却 3 tick） |

---

## §6 玩家中断/回退边界

### 6.1 可中断阶段

| 阶段 | 可中断？ | 中断命令 | 中断后行为 |
|------|----------|----------|------------|
| P1-P2 | 是 | `:interrupt` | 丢弃当前 parsed_intent，等新输入 |
| P3-P4 | 否 | — | 事件评估不可中断（避免 race condition） |
| P5 | 是（超时降级） | — | LLM 超时自动降级，无需玩家中断 |
| P6-P7 | 否 | — | 反馈和 Sol 结算不可中断 |

### 6.2 不可回退

- 已应用的 effects 不可回滚（避免状态不一致）
- 已推进的 node_index 不可回退
- 已触发的 ending 不可撤销

玩家若想"重来"，只能 `:load <save_id>`（待 Phase 2 存档系统）。

### 6.3 玩家可主动跳过

- `:skip dialogue` 跳过当前 NPC 对话剩余消息（合并为一条摘要）
- `:skip event` 跳过当前事件选项（默认选择 opt1，若 opt1 有 condition 不满足则跳过）
- `:sol` 强制推进 Sol（若当前 tick 有未处理事件，先处理）

---

## §7 终端交互命令规范

### 7.1 meta 命令清单

| 命令 | 功能 | 实现优先级 |
|------|------|-----------|
| `:help` | 列出所有命令 | P0 |
| `:sol` | 推进一个 Sol | P0 |
| `:state` | 显示当前 game_state 摘要 | P0 |
| `:npc <id>` | 显示指定 NPC 状态（stress/morale/trust/state） | P0 |
| `:mode <reflexive\|deliberate\|deep>` | 切换 Agent 响应模式 | P1（已有，对齐 main.py） |
| `:branch` | 显示当前 branch 和 node_index | P0 |
| `:interrupt` | 中断当前 tick 的 P1-P2 | P1 |
| `:skip <dialogue\|event>` | 跳过对话/事件 | P1 |
| `:save <id>` | 存档（Phase 2） | P2 |
| `:load <id>` | 读档（Phase 2） | P2 |
| `:quit` | 退出游戏 | P0 |

### 7.2 现有 main.py 兼容性

main.py 现有的 `:mode` `:state` `:quit` 命令保持兼容。game_loop 升级后：
- `:state` 输出从字符串升级为 game_state.to_dict() 的格式化输出
- `:mode` 保留，但仅在单 NPC 对话场景生效（多 NPC 场景默认 deliberate）
- `:quit` 保留，触发结局 "player_quit"（不算正式结局，不写入 ending_rank）

### 7.3 输入规整规则

- 输入去除首尾空白
- 多行输入用 `\n` 连接为单行（除非用 `"""` 包裹）
- 输入长度上限 500 字符（防止 prompt 过长）
- 输入含 `;` 时拆分为多个 parsed_intent（最多 3 个），分 tick 处理

---

## §8 与云逸架构的接口对齐

### 8.1 Agent 层接口

game_loop 调用 NPC Agent 用云逸 §4 定义的接口：

```python
class Agent:
    def chat(
        self,
        player_input: str,
        game_state: str,           # context_summary 序列化文本
        response_mode: str = "deliberate",
    ) -> Dict[str, Any]:
        # 返回 {"response": str, "prompt_tokens": int, "completion_tokens": int}
```

game_loop 在 P5 阶段并发调用多个 NPC Agent，需要云逸确认：
- 是否支持 async 并发调用（建议 asyncio.gather）
- Agent 实例是否线程安全（多个 game_loop tick 复用同一 Agent 实例）

### 8.2 调度器与 game_state.py 的接口

game_loop 直接复用 game_state.py 已实现：
- `create_initial_game_state()` → 初始化
- `apply_effects(game_state, effects)` → 应用事件 effects
- `check_resource_crisis(game_state)` → P3 阶段资源危机检查
- `apply_sol_decay(game_state)` → P7 阶段 Sol 推进
- `build_emotion_hint(game_state, sender_id)` → P6 阶段 emotion_hint 构造
- `get_emotional_command_delta(subtype)` → P5 阶段情感 delta

无需新增接口。

### 8.3 事件字典加载

```python
event_dict = {
    "A": load_branch("A"),   # 返回 branch_a YAML 解析后的 dict
    "B": load_branch("B"),
    "C": load_branch("C"),
    "D": load_branch("D"),
}
```

`load_branch(branch_id)` 需要云逸定义具体加载方式（YAML 直接读 vs 通过 dict loader）。建议放在 `agent/event_dict.py`，由锐锋实现。

---

## 附录 A：阶段切换决策表

| 当前阶段 | 完成条件 | 下一阶段 | 备注 |
|----------|----------|----------|------|
| P1 | parsed_intent 构造完成 | P2 | 总是成功（含兜底） |
| P2 | context_summary 构造完成 | P3 | 总是成功 |
| P3 | trigger 评估完成 | P4（有事件）或 P5（无事件） | — |
| P4 | dispatch_plan 构造完成 | P5 | — |
| P5 | 所有 NPC 回复就绪或超时 | P6 | 阻塞阶段 |
| P6 | front_end_payload 推送完成 | P7 | — |
| P7 | Sol 结算 + ending 检查完成 | P1（下一 tick）或 结局展示 | — |

---

## 附录 B：指令子类映射表（完整版）

### B.1 情感类指令（5 种，对齐 game_state.py EMOTIONAL_COMMAND_DELTAS）

| 子类 | 关键词正则 | delta |
|------|-----------|-------|
| soothe | `(安抚\|慰\|放宽心\|别担心\|会好的\|撑住)` | stress-0.05/morale+0.08/trust+3 |
| empathize | `(理解\|懂你\|我也\|我知道\|能体会)` | stress-0.03/morale+0.05/trust+5 |
| command | `(下令\|命令\|要求\|必须\|立刻\|马上)` | stress+0.05/morale-0.03/trust-3 |
| blame | `(责备\|怪你\|你的错\|你失败\|都怪)` | stress+0.08/morale-0.08/trust-5 |
| smalltalk | （兜底） | stress-0.02/morale+0.02/trust+1 |

### B.2 meta 类指令（10 种，见 §7.1）

### B.3 dialogue 类指令

无子类细分，统一走 Agent.chat() 走 LLM 回复。

---

## 附录 C：待确认问题清单

| # | 问题 | 负责人 | 默认值（若不回复） |
|---|------|--------|-------------------|
| 1 | Agent 是否支持 async 并发调用？ | 云逸 | 否，改为串行 + 8s 超时降级 |
| 2 | Agent 实例是否线程安全？ | 云逸 | 否，每 tick 创建新实例 |
| 3 | load_branch 实现位置？ | 云逸/锐锋 | 锐锋实现于 agent/event_dict.py |
| 4 | 旁观 NPC 反应是否启用？ | 云逸 | 启用，但仅 stress<0.7 的 NPC |
| 5 | 玩家输入长度上限？ | 锐锋 | 500 字符 |
| 6 | 多 tick 输入用 `;` 分隔是否合理？ | 锐锋 | 是 |

---

## 修订记录

| 版本 | 日期 | 修订人 | 内容 |
|------|------|--------|------|
| v1.0 | 2026-08-03 | 蔚蓝 | 初版，覆盖 §1-§8 + 附录 A/B/C |
