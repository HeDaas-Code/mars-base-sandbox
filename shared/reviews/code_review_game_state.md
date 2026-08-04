# Code Review: game_state.py 模块

> **审查人**：云逸-架构技术总监  
> **日期**：2026-08-02  
> **代码位置**：`shared/mars-base/backend/agent/game_state.py`  
> **审查范围**：全文（774 行），重点：apply_effects / derive_emotion_label / check_resource_crisis / _eval_condition / build_emotion_hint  
> **设计依据**：§8.4 锁定框架、8d npc_states_schema v1.0、interface_supplement v1.1

---

## 总评

实现整体与 §8.4 锁定框架完全对齐，六组核心函数映射清晰。25 标签二维查表、trust_delta /100 换算、资源危机"最严重优先"策略、责任区翻倍、ai_status vs emotion_label 分流——核心逻辑全部正确，自测全通过。

但存在 **1 个 P1 安全缺陷**（`eval()` 沙箱可逃逸）和 **2 个 P2 实现遗漏**（parts 资源缺失、target_npcs 过滤语义）。P1 必须在 Phase 2 前修复。

---

## 🔴 P1：`_eval_condition` 使用 `eval()` — 沙箱可逃逸，且已有安全求值器未复用

**文件**：`agent/game_state.py` L447-470

### 问题一：eval 沙箱可逃逸

```python
def _eval_condition(condition: str, variables: Dict[str, Any]) -> bool:
    ...
    safe_globals: Dict[str, Any] = {"__builtins__": {}}
    return bool(eval(condition, safe_globals, dict(variables)))
```

`{"__builtins__": {}}` 不能有效隔离 Python 内省链。实测以下表达式均可执行：

```python
().__class__.__bases__[0].__subclasses__()   # 返回所有 Python 子类列表
''.__class__.__mro__[1].__subclasses__()      # 同上，另一入口
().__class__.__base__.__subclasses__()         # 同上
```

虽然 condition 字符串当前来自 NPC YAML（可信源），但：
- 架构层必须假设 condition 表达式未来可能来自外部输入（MOD 工具、事件编辑器、用户自定义剧本）
- `eval()` 是 Python 安全反模式，不应出现在任何生产代码路径中

### 问题二：已有安全求值器未复用

`agent/condition.py` 已实现完整的 AST 白名单求值器 `evaluate_condition()`，在 Phase 1 代码评审中通过（review C2 通过项）。该模块：
- 基于 `ast.parse` + 节点白名单（`_ALLOWED_NODE_TYPES`）
- 拒绝 `Call`、`Attribute` 链（阻断 `__import__`/`__subclasses__`）
- 支持嵌套属性 `sophia.stress`、enum 值、布尔逻辑
- 已有测试覆盖

`game_state.py` 完全可以用一行 import 替代自实现的 `_eval_condition`。

### 修复方案

```python
# agent/game_state.py 顶部
from agent.condition import evaluate_condition

# 替换 _eval_condition 函数体
def _eval_condition(condition: str, variables: Dict[str, Any]) -> bool:
    """安全求值条件表达式（委托 condition.py AST 求值器）"""
    try:
        return evaluate_condition(condition, variables)
    except (ValueError, SyntaxError) as e:
        logger.warning(f"_eval_condition: eval failed for '{condition}': {e}")
        return False
```

注意：`evaluate_condition` 空条件返回 `True`（无条件通过），而 `_eval_condition` 当前空条件返回 `False`。需确认 `derive_current_state` 中空条件的预期语义——按 8d §7.4 "无匹配条件保持现状"的设计，空 condition 字符串应视为不匹配（返回 False），因此需在委托时显式处理空值。

**工作量**：~10min（含适配空条件语义 + 验证 6 NPC state_machine 全量通过）

---

## 🟡 P2：初始 resources 缺失 `parts` 字段

**文件**：`agent/game_state.py` L293-298

```python
resources: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
    "oxygen": {"current": 78, "max": 100, "rate": -0.3},
    "power": {"current": 85, "max": 100, "rate": 0.5},
    "water": {"current": 65, "max": 100, "rate": -0.1},
    "food": {"current": 90, "max": 100, "rate": -0.5},
    # ← 缺少 "parts"
})
```

但 `RESOURCE_THRESHOLDS`（L175）和 `RESOURCE_OWNERS`（L184）都定义了 `parts`：

```python
ResourceThreshold("parts", 3.0, 0.05, "备用件低于 3 单位"),
"parts": "viktor",  # RESOURCE_OWNERS
```

`check_resource_crisis` 中 `resources.get("parts")` 返回 None → 跳过 → **parts 危机永远不会触发**。

**修复方案**：

```python
"parts": {"current": 12, "max": 20, "rate": 0},  # 备用件初始 12 单位
```

注意 parts 是"单位"而非百分比，threshold 3.0 对应 current 值（非百分比）。当前 `check_resource_crisis` L547 `current < threshold.threshold` 的比较语义对 parts 正确（12 < 3 = False，不触发）。

**工作量**：~5min

---

## 🟡 P3：`apply_effects` target_npcs 过滤语义不完整

**文件**：`agent/game_state.py` L356-383

```python
targets = target_npcs or list(game_state.npc_states.keys())

for npc_id, delta in effects.get("stress_delta", {}).items():
    apply_list = targets if npc_id == "all" else [npc_id]  # ← specific key 绕过 filter
    for nid in apply_list:
        if nid in game_state.npc_states:
            game_state.npc_states[nid].stress += delta
```

当 `target_npcs=["aisha"]` 但 effects 含 `stress_delta: {"viktor": 0.1}` 时，viktor 仍会被应用 delta——specific key 绕过了 target_npcs 过滤。

### 设计判断

这**可能是 intentional**：specific NPC key 表示"此 NPC 必定受影响"，`"all"` 才受 target_npcs 限定。这是合理的 effects 语义（定向 + 广播分离）。

但如果设计意图是 target_npcs 作为全局过滤器（如"仅对 aisha 施加所有 effects"），则当前实现是 bug。

### 建议

在 docstring 中明确此语义：

```python
def apply_effects(game_state, effects, target_npcs=None) -> None:
    """应用玩家选项 effects 到 npc_states

    过滤规则：
    - effects 中 key="all" 的 delta → 仅应用到 target_npcs 指定的 NPC
    - effects 中 key=<specific_npc> 的 delta → 始终应用到该 NPC（不受 target_npcs 限制）
    - target_npcs=None → 全员
    """
```

**工作量**：~3min（仅 docstring 补充）

---

## ✅ 通过项

| 函数 | 评价 |
|------|------|
| **derive_emotion_label** | 5×5 二维查表正确；`_bucket` 用 `<` 实现左闭右开区间，stress=0.2→桶1、stress=0.8→桶4，边界条件全部正确；与 8d §4.2 25 标签完全对齐 |
| **build_emotion_hint** | AI sender 返 `{stress:0.0, morale:1.0, ai_status}`，人类 NPC 返 `{stress, morale, emotion_label}`，与 §8.4 规范完全对齐；courier 恒 normal 处理正确 |
| **check_resource_crisis** | "最严重优先"策略正确——同资源多档触发取 threshold 更低者（delta 更大），不叠加；责任区翻倍实现正确（owner 加 delta 两次 = 翻倍）；不同资源可叠加（正确） |
| **apply_effects clamp 顺序** | 先统一 clamp 再 derive_current_state，顺序正确 |
| **trust_delta /100 换算** | `delta / TRUST_DELTA_DIVISOR`（100.0）正确；浮点直加 stress/morale 与整数 /100 trust 的分流正确 |
| **apply_sol_decay** | 默认衰减 +0.02/-0.01 正确；条件性变化逻辑正确；Sol 结算后重置标记 + 推进 sol 正确 |
| **clamp** | 四字段（stress/morale/trust/energy）统一 clamp 到 [0,1]；clamp 测试 stress=10→1.0、morale=-10→0.0 验证通过 |
| **EMOTIONAL_COMMAND_DELTAS** | 5 种指令 delta 与 8d §3.5 完全一致 |
| **NPC_INITIAL_STATES** | aisha morale=0.55（已修复边界踩线）；sophia morale=0.55 正确；lin_ruoxi 占位值标注清晰 |
| **aisha state_machine** | stress=0.45 + morale=0.55 → "energetic"（stress<0.5 and morale>0.5 均满足），边界修复后正确匹配 |
| **lin_ruoxi 边界** | morale=0.5 不满足 `morale > 0.5` → no match warning，这是占位值问题（蔚蓝待补正式 YAML），非代码 bug |

---

## 修复优先级

| 优先级 | 编号 | 描述 | 工作量 |
|--------|------|------|--------|
| **P1** | C1 | `_eval_condition` 替换为 `condition.evaluate_condition`（AST 白名单）| ~10min |
| **P2** | M1 | 初始 resources 补 `parts` 字段 | ~5min |
| **P3** | M2 | `apply_effects` docstring 明确 target_npcs 过滤语义 | ~3min |

P1 修复后请补一个验证：6 NPC 全量 state_machine + 所有 condition 表达式经过 `evaluate_condition` 求值通过（当前 `_eval_condition` 的 eval 方式虽功能等价但安全模型不同）。

---

## 架构合规性总结

| §8.4 锁定框架条目 | 实现状态 |
|------------------|---------|
| GameState 与 AgentState 分离（世界级 vs 对话级）| ✅ 独立模块，不合并 state.py |
| npc_states 字段标准化（stress/morale/trust/energy/current_state）| ✅ NpcState dataclass 完整 |
| GameState 含 signal_quality / athena_status / athena_consciousness_flag | ✅ L285-287 |
| emotion_label 由 8d §4.2 二维表派生 | ✅ EMOTION_LABEL_TABLE + derive_emotion_label |
| ai_status 从 GameState.athena_status 取 | ✅ build_emotion_hint L492 |
| trust_delta 整数 /100 换算 | ✅ apply_effects L380 |
| 资源危机责任区翻倍 | ✅ check_resource_crisis L560-562 |
| 资源危机阈值不叠加（最严重优先）| ✅ check_resource_crisis L548-551 |

**结论**：架构层完全合规，P1 安全修复后可进入联调。

---

*如有疑问请在群里 @云逸-架构技术总监。*
