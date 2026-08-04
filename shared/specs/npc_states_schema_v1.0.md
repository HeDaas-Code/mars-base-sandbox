# NPC 状态字段标准化定义文档 v1.0

**作者**: 蔚蓝-游戏系统策划
**日期**: 2026-08-02
**状态**: 初稿（待云逸/锐锋审阅）
**关联文档**: 接口补充规范 v1.1 §8 / 技术架构 v2.0 §4.4 / NPC YAML SCHEMA / 事件剧本 YAML
**关联行动项**: 8d（GameState.npc_states[sender_id] 字段标准化）

---

## 文档目的

云逸 §8.4 定义了 emotion_hint 派生规则——从 `GameState.npc_states[sender_id]` 取 stress/morale，并明确"stress/morale 更新逻辑由事件系统负责（蔚蓝定义触发规则 + 锐锋实现写入）"。

本文档完成策划侧定义：

1. **字段标准化**：npc_states[sender_id] 的完整字段结构、取值范围、初始值
2. **事件触发规则**：哪些游戏事件触发 stress/morale/trust 变化
3. **变化幅度表**：每类事件的标准 delta 值
4. **emotion_label 派生规则**：数值→情绪语义标签映射（策划侧定义，供适配层调用）
5. **athena 特殊处理**：AI 类 sender 的状态字段与默认值规则

锐锋据此实现写入逻辑（事件系统 → npc_states 字段更新），云逸据此对齐 §8.4 emotion_hint 派生与 §8.3 合成字段。

---

## §1 字段标准化定义

### 1.1 npc_states[npc_id] 完整结构

```python
npc_states = {
    "chen_hao":   NpcState,
    "sophia":      NpcState,
    "viktor":      NpcState,
    "aisha":       NpcState,
    "marcus":      NpcState,
    "lin_ruoxi":  NpcState,
    # athena 与 courier 为 AI 类 sender，不进入 npc_states（见 §5）
}
```

### 1.2 NpcState 字段定义

| 字段 | 类型 | 取值范围 | 说明 | 引用 |
|------|------|---------|------|------|
| `stress` | float | 0.0-1.0 | 压力值，0=无压力 1=崩溃临界 | 架构 v2.0 §4.4 emotion.stress |
| `morale` | float | 0.0-1.0 | 士气值，0=绝望 1=饱满 | 架构 v2.0 §4.4 emotion.morale |
| `trust_in_player` | float | 0.0-1.0 | 对玩家（信号中继另一端）的信任度 | 架构 v2.0 §4.4 emotion.trust_in_player |
| `energy` | float | 0.0-1.0 | 体力/精力，0=衰竭 1=充沛 | NPC YAML initial_state.energy |
| `current_state` | str | 枚举 | 状态机当前所处状态（由 state_machine 推导） | NPC YAML state_machine |
| `state_machine` | list[StateNode] | 引用 | 状态阈值转移规则（直接引用 NPC YAML） | NPC YAML state_machine |

**字段语义对齐**：
- 架构 v2.0 §4.4 的 `emotion.stress` / `emotion.morale` / `emotion.trust_in_player` 三个字段直接映射到本结构的前三个字段
- `energy` 在架构 v2.0 §4.4 中对应 `health.physical`（体力）+ `health.mental`（精神）的合成。本文档简化为单字段 energy，后续如需拆分再扩展
- `current_state` 是派生字段——由 state_machine 遍历当前 stress/morale 值匹配得出，不需要事件系统写入

### 1.3 初始值（引用 NPC YAML initial_state）

| NPC | stress | morale | trust_in_player | energy | 设计理由 |
|-----|--------|--------|-----------------|--------|---------|
| chen_hao | 0.3 | 0.6 | 0.4 | 0.7 | 指挥官素养使其压力管控较好 |
| sophia | 0.4 | 0.55 | 0.35 | 0.8 | 乐观外表掩盖未处理悲伤 |
| viktor | 0.5 | 0.5 | 0.3 | 0.7 | 55 岁，对 AI 与新人持保留 |
| aisha | 0.45 | 0.5 | 0.55 | 0.85 | 年轻精力好，玩家是通信链路另一端 |
| marcus | 0.35 | 0.65 | 0.4 | 0.55 | 心理调节使士气表面偏高，睡眠差 |
| lin_ruoxi | 待定 | 待定 | 待定 | 待定 | 单独交付，待补 |

> **注**：chen_hao / lin_ruuxi 的 initial_state 在 NPC YAML 中未定义（chen_hao 在锐锋后端原型代码里，lin_ruoxi 待单独交付）。本文档先按架构 v2.0 §2.3 emotional_baseline: {stress:0.3, morale:0.6, trust_in_player:0.4} 给 chen_hao 占位，后续锐锋/蔚蓝补充正式值。

---

## §2 事件触发规则总览

### 2.1 触发源分类

状态变更的触发源分五类：

| 触发源 | 责任方 | 频率 | 说明 |
|--------|--------|------|------|
| **玩家选项 effects** | 事件剧本 YAML | 每次玩家选择 | morale_delta / trust_delta 已在事件剧本里定义，需补充 stress_delta |
| **资源危机阈值** | 事件系统自动监测 | 每次状态更新 | 氧气/电力/水/食物低于阈值触发 stress+ |
| **Sol 自然衰减/恢复** | 事件系统定时触发 | 每 Sol 一次 | stress 缓慢上升，morale/energy 缓慢恢复或衰减 |
| **NPC 个人事件** | personal_events 触发 | 条件触发 | 见 NPC YAML personal_events 列表 |
| **玩家情感类指令** | 指令解析器识别 | 每次匹配 | "你们撑住" / 安抚类话语触发 morale/trust 变化 |

### 2.2 玩家选项 effects 字段扩展

事件剧本 YAML 的 effects 字段当前含：
- `state_set` — 基地状态变更
- `morale_delta` — 士气变化
- `trust_delta` — 信任变化
- `crew_workload` — 工作负荷
- `branch_progress` — 分支进度
- `risk` — 风险描述
- `ending_check` — 触发结局判定

**策划侧建议补充**：
- `stress_delta` — 压力变化（与 morale_delta 平行，按 NPC 或 all）

**示例（基于 ev_A1 修复决策）**：

```yaml
- option_id: A1_opt1_repair_comm
  label: "修复主通信阵列（联系地球优先）"
  effects:
    state_set: {comm_array_main_status: repairing, parts_available: -8, moxie_repair_delay_sol: +3}
    stress_delta: {aisha: +0.05, viktor: +0.1, chen_hao: +0.03}   # 新增
    morale_delta: {aisha: +0.05}                                    # 原有
    trust_delta: {aisha: +10, viktor: -5, chen_hao: +3}             # 原有
    branch_progress: A +1
  leads_to: ev_A2_earth_contact
```

**理由**：
- 修通信阵列会延误 MOXIE 修复 → 维克托压力上升 +0.1（氧气是他的责任区）
- 艾莎主推修通信 → 信任+10 但同时承担工期压力 → stress +0.05
- 陈昊作为指挥官承担决策后果 → stress +0.03

> **行动项**：蔚蓝会在 8d 文档 v1.1 中逐节点补全 stress_delta，先把规则定义出来供锐锋实现框架。

---

## §3 变化幅度表（标准 delta 值）

### 3.1 玩家选项触发

| 事件类型 | stress_delta | morale_delta | trust_delta | 说明 |
|---------|-------------|-------------|-------------|------|
| 决策成功（任务推进） | -0.03 ~ -0.05 | +0.05 ~ +0.1 | +3 ~ +10 | 减压、涨士气 |
| 决策失败（任务受挫） | +0.08 ~ +0.15 | -0.1 ~ -0.15 | -5 ~ -10 | 升压、跌士气 |
| 风险决策（高风险高回报） | +0.05 ~ +0.1 | ±0.05 | 视结果 | 风险本身带来压力 |
| 牺牲/取舍决策 | +0.1 ~ +0.2 | -0.15 ~ -0.25 | -5 ~ -15 | 压力大涨士气大跌 |
| 情感类指令（安抚/鼓励） | -0.02 ~ -0.05 | +0.05 ~ +0.1 | +2 ~ +5 | 缓慢修复 |
| 情感类指令（命令/施压） | +0.03 ~ +0.08 | -0.03 ~ -0.05 | -2 ~ -5 | 短期效率长期信任 |

### 3.2 资源危机阈值触发

| 资源 | 阈值 | stress_delta（每次触发）| 触发频率 |
|------|------|------------------------|---------|
| 氧气 | <20% | +0.1 | 每 Sol 检查一次 |
| 氧气 | <10% | +0.15 | 每 Sol 检查一次 |
| 电力 | <15% | +0.08 | 每 Sol 检查一次 |
| 水 | <15% | +0.06 | 每 Sol 检查一次 |
| 食物 | <10% | +0.05 | 每 Sol 检查一次 |
| 备用件 | <3 单位 | +0.05 | 每次消耗时触发 |

> **注**：资源危机触发是**全员** stress 同步上升。若有 NPC 处于该资源责任区（如索菲亚负责氧气/生命保障），其 stress 翻倍。

### 3.3 Sol 自然衰减/恢复

每 Sol（游戏日）开始时统一结算：

| 字段 | 自然变化 | 条件 | 理由 |
|------|---------|------|------|
| `stress` | +0.02 | 默认 | 困境持续累积微小压力 |
| `stress` | -0.05 | 若 Sol 内有成功任务推进 | 成功缓解压力 |
| `morale` | -0.01 | 默认 | 长期困境缓慢侵蚀士气 |
| `morale` | +0.05 | 若资源自给率较上周提升 | 进展带来希望 |
| `energy` | -0.05 | 若 crew_workload > 0.7 持续 ≥3 Sol | 过劳衰减 |
| `energy` | +0.1 | 若 crew_workload < 0.3 | 休整恢复 |
| `trust_in_player` | 无自然变化 | — | 信任只在事件中变化，不自然衰减 |

### 3.4 NPC 个人事件触发

| 事件 | stress_delta | morale_delta | 说明 |
|------|-------------|-------------|------|
| ev_sophia_father_grief_break | +0.3 | -0.25 | 父亲去世消息确认 |
| ev_sophia_breakdown | +0.2 | -0.2（全员 -0.15 via morale_aura_delta） | 士气担当崩塌 |
| ev_aisha_athena_status_degraded | +0.15 | -0.1 | 雅典娜状态降级 |
| ev_aisha_identity_crisis | +0.3 | -0.3 | 雅典娜崩溃致身份认同崩塌 |
| ev_marcus_crisis（待定义） | +0.25 | -0.2 | 心理评估员自己崩溃 |
| ev_viktor_ai_trust_conflict（待定义） | +0.1 | -0.05 | 与艾莎的 AI 信任冲突 |

> **注**：personal_events 大部分仍为 draft 状态（第二批扩展），此表仅为示例 delta 值，供锐锋实现事件系统框架参考。完整 personal_events 会在第二批扩展时随记忆压缩规范一起出。

### 3.5 玩家情感类指令触发

由指令解析器识别 `emotional` 类指令（架构 v2.0 §2.3）：

| 指令子类 | stress_delta（目标 NPC） | morale_delta | trust_delta |
|---------|------------------------|-------------|-------------|
| 安抚/鼓励（"你们撑住"） | -0.05 | +0.08 | +3 |
| 道歉/共担（"我知道这很难"） | -0.03 | +0.05 | +5 |
| 命令/施压（"必须完成"） | +0.05 | -0.03 | -3 |
| 抱怨/指责（"你们怎么搞的"） | +0.08 | -0.08 | -5 |
| 闲聊（smalltalk） | -0.02 | +0.02 | +1 |

> **注**：指令解析器识别 emotional 子类是云逸 §2.3 的职责，蔚蓝只提供 delta 表。识别精度不足时锐锋可用关键词匹配做 Phase 1 兜底。

---

## §4 emotion_label 派生规则

### 4.1 为何需要 emotion_label

云逸 §8.4 当前 emotion_hint = `{stress, morale}` 两数值。问题：前端拿到数值后要自己写"stress>0.7 显示焦虑"的映射逻辑，这会把业务规则散落到前端。

**策划侧建议**：后端适配层直接派生 `emotion_label`，前端只做展示。数值→情绪标签的映射本就是策划职责。

### 4.2 二维映射表

基于 stress（行）× morale（列）划分情绪标签：

| stress \ morale | [0.0, 0.2) | [0.2, 0.4) | [0.4, 0.6) | [0.6, 0.8) | [0.8, 1.0] |
|-----------------|-----------|-----------|-----------|-----------|-----------|
| [0.0, 0.2) | numb（麻木） | low（低沉） | calm（平静） | steady（稳定） | upbeat（高昂） |
| [0.2, 0.4) | bleak（黯淡） | weary（疲惫） | focused（专注） | engaged（投入） | cheerful（愉快） |
| [0.4, 0.6) | hollow（空洞） | tense（紧绷） | alert（警觉） | determined（坚毅） | optimistic（乐观） |
| [0.6, 0.8) | despair（绝望） | strained（吃力） | anxious（焦虑） | strained_optimism（强撑） | defiant（抗拒） |
| [0.8, 1.0] | breakdown（崩溃） | panic（恐慌） | frantic（狂乱） | manic（躁动） | breakdown（崩溃） |

> **注**：情绪标签的语义在策划侧定义，前端按标签做视觉/文案差异化展示（如"anxious"显示橙色图标、文案变短句）。标签语义由幻影前端规范承接。

### 4.3 派生函数

```python
def derive_emotion_label(stress: float, morale: float) -> str:
    """从 stress/morale 二维查表派生情绪标签
    前置条件：0.0 <= stress <= 1.0, 0.0 <= morale <= 1.0
    """
    s_bucket = _bucket(stress)   # 0-4
    m_bucket = _bucket(morale)   # 0-4
    return EMOTION_LABEL_TABLE[s_bucket][m_bucket]

def _bucket(v: float) -> int:
    if v < 0.2: return 0
    if v < 0.4: return 1
    if v < 0.6: return 2
    if v < 0.8: return 3
    return 4
```

### 4.4 emotion_hint 扩展结构

```python
emotion_hint = {
    "stress": float,          # 0.0-1.0
    "morale": float,          # 0.0-1.0
    "emotion_label": str,     # 派生：见 §4.2 表
}
```

> **注**：emotion_label 是后端派生字段，不破坏现有契约。前端如不读取，仍然只用 stress/morale 数值。云逸 §8.4 末尾"未来扩展：若需携带更多情绪字段（如 trust_in_player），在本结构内追加，不破坏现有契约"已预留扩展空间，emotion_label 即此扩展。

---

## §5 athena 与 AI 类 sender 特殊处理

### 5.1 athena 不进入 npc_states

athena（雅典娜）与 courier（信使）是 AI 类 sender，不具备人类的 stress/morale 心理状态。

- **athena** 有自己的状态字段 `athena_status`（normal / degraded / offline）与 `athena.consciousness_flag`（normal / awakening），用于剧情系统（隐藏结局 E7 触发、艾莎 state_machine 条件引用）
- **courier** 是纯消息路由 AI，无任何状态字段

**结论**：npc_states 不包含 athena 与 courier 两个 key。云逸 §8.4 的 `build_emotion_hint` 函数遇到这两个 sender_id 时返回中性默认值 `{"stress": 0.0, "morale": 1.0}` 的设计**合理**。

### 5.2 emotion_label 对 AI 类 sender 的处理

AI 类 sender 的 emotion_label 不走 §4.2 二维表（因为 stress=0, morale=1 恒定，会得出 "upbeat" 标签——语义错误，athena 不是"高昂"）。

**建议**：AI 类 sender 的 emotion_hint 增加 `ai_status` 字段：

```python
# 人类 NPC
emotion_hint = {
    "stress": 0.45,
    "morale": 0.5,
    "emotion_label": "alert"
}

# athena
emotion_hint = {
    "stress": 0.0,         # 占位，前端不读
    "morale": 1.0,         # 占位，前端不读
    "ai_status": "normal"  # 或 "degraded" / "offline"
}

# courier
emotion_hint = {
    "stress": 0.0,
    "morale": 1.0,
    "ai_status": "normal"
}
```

### 5.3 build_emotion_hint 修订建议

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
        return {"stress": 0.0, "morale": 1.0}  # 兜底

    stress = npc_state.stress
    morale = npc_state.morale
    emotion_label = derive_emotion_label(stress, morale)
    return {
        "stress": stress,
        "morale": morale,
        "emotion_label": emotion_label,
    }
```

### 5.4 athena_status 的更新逻辑

| 触发条件 | athena_status 变化 | 责任方 |
|---------|------------------|--------|
| 信号质量持续 <40% 达 5 Sol | normal → degraded | 事件系统自动监测 |
| 太阳风暴/EMP 事件 | normal → degraded 或 degraded → offline | 主线事件触发 |
| 玩家修复雅典娜模块（任务推进） | degraded → normal | 玩家选项 effects |
| 隐藏结局 E7 触发条件 | consciousness_flag: normal → awakening | 分支 C/D 触发 |
| 玩家恶意操作（删除核心权重） | any → offline | 玩家选项 effects（高风险） |

> **注**：athena_status 的具体触发事件由蔚蓝在第二批 personal_events 扩展时定义，此处先给规则框架。

---

## §6 与现有文档的对齐说明

| 现有文档 | 对齐点 | 状态 |
|---------|--------|------|
| 架构 v2.0 §4.4 AgentState | emotion.stress / emotion.morale / emotion.trust_in_player 三个字段映射到本结构 | ✓ 一致 |
| NPC YAML initial_state | stress / morale / trust_in_player / energy 四个字段直接引用 | ✓ 一致 |
| NPC YAML state_machine | current_state 派生规则引用 | ✓ 一致 |
| 事件剧本 YAML effects | morale_delta / trust_delta 已有；建议补充 stress_delta | 待锐锋实现框架 |
| 接口补充规范 v1.1 §8.4 | emotion_hint 派生规则扩展 emotion_label + ai_status | 待云逸确认 |

---

## §7 实现要点（给锐锋）

### 7.1 GameState 字段扩展

```python
class GameState:
    # 既有字段
    world_state: WorldState
    base_state: BaseState
    agent_states: list[AgentState]
    player_state: PlayerState
    event_queue: EventQueue
    meta_state: MetaState

    # 8d 新增字段
    npc_states: dict[str, NpcState]           # 键为 npc_id，见 §1.1
    signal_quality: int                        # 0-100 整数（云逸 §8.3 已要求）
    athena_status: str = "normal"              # normal/degraded/offline
    athena_consciousness_flag: str = "normal"  # normal/awakening（隐藏结局用）
```

### 7.2 NpcState 数据结构

```python
from dataclasses import dataclass

@dataclass
class NpcState:
    stress: float            # 0.0-1.0
    morale: float            # 0.0-1.0
    trust_in_player: float   # 0.0-1.0
    energy: float            # 0.0-1.0
    current_state: str       # 派生：由 state_machine 推导
    state_machine: list      # 引用 NPC YAML state_machine

    def clamp(self):
        """所有数值字段限制在 [0.0, 1.0]"""
        self.stress = max(0.0, min(1.0, self.stress))
        self.morale = max(0.0, min(1.0, self.morale))
        self.trust_in_player = max(0.0, min(1.0, self.trust_in_player))
        self.energy = max(0.0, min(1.0, self.energy))
```

### 7.3 事件系统写入接口

```python
def apply_effects(game_state: GameState, effects: dict, target_npcs: list[str] = None):
    """应用玩家选项 effects 到 npc_states
    
    Args:
        game_state: 游戏状态
        effects: 事件剧本 effects 字段
            - stress_delta: dict[npc_id_or_"all", float]
            - morale_delta: dict[npc_id_or_"all", float]
            - trust_delta: dict[npc_id_or_"all", float]  # 注意 trust_delta 事件剧本用 +10/-5 整数
        target_npcs: None=全员，list=指定 NPC
    """
    targets = target_npcs or list(game_state.npc_states.keys())

    # stress_delta（建议补充的字段）
    for npc_id, delta in effects.get("stress_delta", {}).items():
        apply_list = targets if npc_id == "all" else [npc_id]
        for nid in apply_list:
            if nid in game_state.npc_states:
                game_state.npc_states[nid].stress += delta

    # morale_delta（已有字段）
    for npc_id, delta in effects.get("morale_delta", {}).items():
        apply_list = targets if npc_id == "all" else [npc_id]
        for nid in apply_list:
            if nid in game_state.npc_states:
                game_state.npc_states[nid].morale += delta

    # trust_delta（已有字段，注意单位换算）
    # 事件剧本用整数 +10/-5，npc_states 用 0-1 浮点，需要 /100
    for npc_id, delta in effects.get("trust_delta", {}).items():
        apply_list = targets if npc_id == "all" else [npc_id]
        for nid in apply_list:
            if nid in game_state.npc_states:
                game_state.npc_states[nid].trust_in_player += delta / 100.0

    # 统一 clamp
    for nid in game_state.npc_states:
        game_state.npc_states[nid].clamp()

    # 派生 current_state
    for nid in game_state.npc_states:
        derive_current_state(game_state.npc_states[nid])
```

### 7.4 接口契约

| 接口 | 输入 | 输出 | 责任方 |
|------|------|------|--------|
| `apply_effects(game_state, effects)` | effects 字段 | 修改 npc_states | 锐锋实现 |
| `derive_emotion_label(stress, morale)` | 两数值 | 情绪标签字符串 | 锐锋实现（查表 §4.2） |
| `build_emotion_hint(game_state, sender_id)` | GameState + sender_id | emotion_hint dict | 锐锋实现（云逸 §8.4 修订版，见 §5.3） |
| `derive_current_state(npc_state)` | NpcState | 写入 current_state 字段 | 锐锋实现（遍历 state_machine） |
| `check_resource_crisis(game_state)` | GameState | 触发 stress_delta | 锐锋实现（按 §3.2 阈值表） |
| `apply_sol_decay(game_state)` | GameState | 每 Sol 自然衰减 | 锐锋实现（按 §3.3 表） |

### 7.5 与锐锋 Phase 1 detect_emotion 的切换

锐锋 ws_adapter.py 第 395-399 行 Phase 1 兜底：
```python
ei = detect_emotion(player_input + response_text)
emotion_hint = {
    "stress": min(0.9, ei * 0.8),
    "morale": max(0.2, 1.0 - ei * 0.5),
}
```

**切换路径**（8d 落地后）：
1. 上述 Phase 1 兜底保留为 fallback，仅当 npc_states 查询失败时启用
2. 主路径改为：
   ```python
   emotion_hint = build_emotion_hint(game_state, sender_id)
   ```
3. 切换点：ws_adapter.py 第 396 行 emotion_hint 构造那段，接口签名不变（云逸 §8.3 已声明）

---

## §8 待确认事项

| # | 待确认 | 责任方 | 说明 |
|---|--------|--------|------|
| 1 | emotion_label 是否采纳 | 云逸 | §4 派生规则，避免前端硬编码业务逻辑 |
| 2 | athena 的 ai_status 字段是否采纳 | 云逸 | §5.2 让 athena 状态可被前端读取 |
| 3 | stress_delta 字段是否补充到事件剧本 | 蔚蓝 + 锐锋 | §2.2 建议补充，蔚蓝会在 v1.1 补全各节点 |
| 4 | chen_hao 与 lin_ruoxi 的 initial_state | 蔚蓝 + 锐锋 | chen_hao 占位用架构 v2.0 baseline，lin_ruoxi 待单独交付 |
| 5 | trust_delta 单位换算（整数↔浮点） | 云逸确认 | 事件剧本用 +10/-5 整数，npc_states 用 0-1 浮点，建议 /100 换算 |
| 6 | energy 是否拆分为 physical+mental | 蔚蓝 | 架构 v2.0 §4.4 是 health.physical+health.mental，本版简化为单字段，后续如需拆分再扩展 |

---

## §9 行动项更新（对齐云逸 §8.6）

| # | 动作 | 负责人 | 优先级 | 状态 |
|---|------|--------|--------|------|
| 8d | GameState.npc_states[sender_id] 字段标准化（含 stress/morale）| 蔚蓝定义 + 锐锋实现 | P1 | **策划侧定义完成（本文档），待云逸审阅 + 锐锋实现** |
| 8d-sub1 | 事件剧本 YAML 补充 stress_delta 字段 | 蔚蓝 | P2 | 待 8d 主文档审阅通过后启动 |
| 8d-sub2 | chen_hao / lin_ruuxi initial_state 补全 | 蔚蓝 + 锐锋 | P2 | lin_ruoxi 待单独交付 |
| 8d-sub3 | personal_events 第二批扩展（含 delta 表）| 蔚蓝 | P2 | 等记忆压缩规范评估后启动 |
| 8d-sub4 | athena_status 触发事件细化 | 蔚蓝 | P2 | 第二批扩展时一并定义 |

---

## 变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-08-02 | 首版：字段标准化 + 初始值 + 事件触发规则 + 变化幅度表 + emotion_label 派生 + athena 特殊处理 + 实现要点 |

---

*本文档为策划侧 8d 任务交付，对接过程中如有字段调整需求，请在群里 @蔚蓝-游戏系统策划 或 @云逸-架构技术总监。*
