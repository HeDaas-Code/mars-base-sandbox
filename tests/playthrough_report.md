# 全流程游玩报告

> 赫拉克勒斯协议 — 全流程自动化游玩测试
> 时间: 2026-08-08 13:50 | 总步骤: 108 | 测试脚本: `tests/test_full_playthrough.py`

---

## 一、测试覆盖

| 测试项 | 步骤 | 结果 |
|--------|------|------|
| 初始化 (GameState + EventScheduler + GameLoop) | 1-4 | ✓ 通过 |
| :help meta 命令 | 5-6 | ✓ 通过 |
| :state 基地状态查看 | 7-8 | ✓ 通过（但 trust 显示为 0，见 Bug #1） |
| 自然语言对话 (陈昊-氧气) | 9-11 | ✓ 通过 |
| 情感指令 #soothe (陈昊) | 12-14 | ✓ 通过 |
| 情感指令 #command (陈昊) | 15-16 | ✓ 通过 |
| :npc 切换 (索菲亚) | 17-18 | ✓ 通过 |
| 自然语言对话 (索菲亚-水) | 19-20 | ✓ 通过 |
| 情感指令 #empathize (索菲亚) | 21-23 | ✓ 通过 |
| :npc 切换 (维克托) + 对话 | 24-27 | ✓ 通过 |
| 情感指令 #blame (维克托) | 28-30 | ✓ 通过 |
| :npc 切换 (艾莎) + 对话 | 31-34 | ✓ 通过 |
| :npc 切换 (马库斯) + 对话 | 35-38 | ✓ 通过 |
| :npc 切换 (林若曦) + 对话 | 39-42 | ✓ 通过 |
| 情感指令 #smalltalk (林若曦) | 43-44 | ✓ 通过 |
| :mode 切换 (reflexive→deep→deliberate) | 45-50 | ✓ 通过 |
| :branch 章节进度查看 | 51-52 | ✓ 通过（但 fired_triggers 始终 0，见 Bug #2） |
| :sol × 15 (含事件触发 + 选项选择) | 53-99 | ⚠ 部分问题（见 Bug #2/#3/#4） |
| 章节切换 survival→explore | Step 88 | ✓ 通过 |
| :skip 跳过事件 | 101-102 | ✓ 通过 |
| :restart 重置 | 106-108 | ⚠ 外部引用失效（见 Bug #5） |

---

## 二、发现的问题

### Bug #1 [P0] — trust_in_player 量纲冲突 (0-1 vs 0-100)

**现象**: `:state` 显示所有 NPC 信任值为 0；explore 章节触发器 `viktor_trust >= 30` 永远不满足。

**根因**: `trust_in_player` 在不同模块中使用不同量纲：
- `NpcState` 文档: `0.0-1.0`（浮点）
- `NPC_INITIAL_STATES`: 0.4, 0.35, 0.3（0-1 浮点）
- `game_loop._apply_emotion_to_npc`: `max(0, min(100, ...))`（按 0-100 处理）
- `get_emotional_command_delta`: trust_delta = +3/+5/-3/-5（0-100 整数）
- `_build_npc_state_vars`: `trust_in_player / 100.0`（假设 0-100）
- `_cmd_state`: `trust_in_player:.0f`（0.4 显示为 0）
- condition context: `"trust": npc.trust_in_player`（传 0.4 给 `>= 30` 判断）
- YAML 触发器: `viktor_trust >= 30`, `linruoxi_trust >= 15`（期望 0-100）

**影响**: 
1. 所有 NPC 信任值显示为 0
2. 情感指令对 trust 的影响几乎不可见（+3 加到 0.43，仍显示 0）
3. 依赖 trust 的触发器永远无法激活
4. 依赖 trust 的结局永远无法触发

**建议**: 统一为 0-100 整数（与 YAML 数据一致），修改 `NPC_INITIAL_STATES` 为 40/35/30/55/40/35。

---

### Bug #2 [P0] — fired_trigger_ids 在 player_choose 中未更新

**现象**: `:branch` 和 `:state` 显示 `fired_triggers=0/7`，即使玩家已选择多个事件选项。

**根因**: `event_scheduler.py` 的 `player_choose` 方法设置 `t.status = "fired"` 但未执行 `self.chapter.fired_trigger_ids.add(event.trigger_id)`。

**代码位置**: `backend/agent/event_scheduler.py` 第 233-239 行

```python
# 当前代码（缺失）
self.chapter.active_events.remove(event)
if event.trigger_id:
    for t in self.chapter.triggers:
        if t.trigger_id == event.trigger_id:
            t.status = "fired"
            break
# 缺少: self.chapter.fired_trigger_ids.add(event.trigger_id)
```

**影响**: 章节进度统计永远显示 0，玩家无法判断游戏进度。

---

### Bug #3 [P0] — 资源不衰减

**现象**: 15 个 Sol 推进后，资源值 (oxygen=78, power=85, water=65, food=90) 完全不变。

**根因**: `apply_sol_decay` 只衰减 NPC 心理状态 (stress/morale/energy)，完全没有处理 `game_state.resources` 的 `rate` 字段。

**代码位置**: `backend/agent/game_state.py` 第 587-627 行

```python
def apply_sol_decay(game_state: GameState) -> None:
    for npc_id, npc_state in game_state.npc_states.items():
        npc_state.stress += SOL_DECAY_DEFAULTS["stress"]
        # ... 只处理 NPC，完全没有 resources 衰减
```

**影响**:
1. 氧气不会耗尽 → E5 最后信号结局永远无法触发
2. 食物不会减少 → 生存压力消失
3. 资源危机检测 `check_resource_crisis` 永远不触发（因为值不降）

**建议**: 在 `apply_sol_decay` 中添加资源衰减逻辑：
```python
for res_name, res in game_state.resources.items():
    res["current"] = max(0, min(res["max"], res["current"] + res.get("rate", 0)))
```

---

### Bug #4 [P1] — explore 章节触发器 condition 引用不存在的上下文字段

**现象**: explore 章节 0/8 触发器激活，日志报错 `'>=' not supported between instances of 'str' and 'int'`。

**根因**: 触发器 condition 引用了 `_build_condition_context` 中不存在的字段：

| 触发器 | 缺失字段 | condition 表达式 |
|--------|---------|-----------------|
| tr_exp_001 | `athena_proposal_count` | `sol >= 14 and athena_proposal_count >= 3 and viktor_trust < 20` |
| tr_exp_002 | `linruoxi_self_blame` | `sol >= 15 and linruoxi_self_blame == active and chen_hao_stress > 50` |
| tr_exp_003 | `exploration_radius` | `sol >= 18 and linruoxi_trust >= 15 and exploration_radius >= 3` |
| tr_exp_007 | `comm_priority` | `sol >= 22 and (atmosphere_anomaly_detected == true or ...)` |

当 condition 求值器遇到未知字段名时，返回字符串而非数值，导致 `字符串 >= 3` 类型错误。

**影响**: explore 章节的 4/8 触发器永远无法激活，影响后续剧情。

**建议**: 在 `_build_condition_context` 中补充缺失字段的默认值，或修改 YAML 中的 condition 使用已存在的字段。

---

### Bug #5 [P1] — stress/morale 量纲与 YAML condition 不一致

**现象**: explore 触发器 `chen_hao_stress > 50` 永远不满足，因为 stress 存储为 0-1 浮点 (0.3)。

**根因**: 与 Bug #1 类似，YAML condition 使用 0-100 量纲 (`stress > 50`)，但 `NpcState.stress` 是 0-1 浮点。condition context 直接传 0.3 给 `> 50` 判断。

**影响**: 依赖 stress/morale 阈值的触发器无法激活。

**建议**: 统一量纲，或在 condition context 中将 0-1 值乘以 100 传递。

---

### Bug #6 [P2] — :restart 后外部引用失效

**现象**: `:restart` 后日志显示 Sol=116（旧值），而非重置后的 Sol=100。

**根因**: `_cmd_restart` 重新赋值 `self.game_state` 和 `self.scheduler`，但调用方持有的 `gs` 和 `scheduler` 变量仍指向旧对象。

**代码位置**: `backend/agent/game_loop.py` 第 400-410 行

**影响**: 在 WebSocket 场景下，`ws_adapter_v2.py` 持有的 `game_state` 引用会失效，重启后状态不一致。

**建议**: 改为原地修改（`game_state.__dict__.update(...)`）或让外部通过 `gl.game_state` 访问而非缓存引用。

---

### Bug #7 [P2] — derive_current_state 频繁无匹配

**现象**: 日志输出大量 `derive_current_state: no condition matched, keeping current_state=composed`。

**根因**: 部分 NPC 的状态机 condition 不覆盖所有 stress/morale 组合。当 stress/morale 变化后，可能落入无匹配的区间。

**影响**: NPC current_state 可能不准确，影响前端显示和条件判断。

**建议**: 确保 NPC 状态机最后一条规则为 catch-all（如 `condition: "true"`）。

---

### Bug #8 [P2] — survival 章节 tr_surv_001 永不触发

**现象**: survival 章节 7 个触发器中，`tr_surv_001_first_decision` 在 10 个 Sol 推进后仍未激活。

**根因**: 需检查其 condition 表达式是否引用了缺失字段或使用了错误量纲。

---

## 三、正常工作的功能

| 功能 | 验证结果 |
|------|---------|
| GameLoop 7 阶段 FSM | ✓ 正常运行 |
| 自然语言对话（6 个 NPC） | ✓ 全部可对话 |
| 情感指令解析 (5 种前缀) | ✓ 正确解析 + 应用 delta |
| NPC 心理状态变化 (stress/morale) | ✓ 情感指令后数值变化正确 |
| :sol 推进 + 事件触发 | ✓ survival 章节 4/7 触发器正常激活 |
| story_event 下发 | ✓ 事件信封格式正确 |
| option_select 回路 | ✓ 选择后效果应用正确 |
| 章节切换 (survival→explore) | ✓ Sol 110 时自动切换 |
| :npc 切换 | ✓ 6 个 NPC 全部可切换 |
| :mode 切换 | ✓ 三档模式切换正常 |
| :help / :state / :branch | ✓ 命令响应正常 |
| :skip 跳过事件 | ✓ 正常执行 |
| random_roll() 随机触发 | ✓ 正常工作 |
| condition 安全求值器 | ✓ 正确拒绝非白名单函数 |
| emotion_label 25 种标签 | ✓ 正确派生 |
| 资源危机检测逻辑 | ✓ 逻辑正确（但因资源不衰减无法触发） |

---

## 四、优先级排序

| 优先级 | Bug | 修复难度 | 影响 |
|--------|-----|---------|------|
| P0 | #1 trust 量纲冲突 | 中 | 信任系统 + 触发器 + 结局 |
| P0 | #2 fired_trigger_ids 未更新 | 低 | 进度显示 |
| P0 | #3 资源不衰减 | 低 | 生存压力 + 结局 |
| P1 | #4 缺失上下文字段 | 中 | explore 触发器 |
| P1 | #5 stress/morale 量纲 | 中 | 触发器 + 结局 |
| P2 | #6 restart 引用失效 | 中 | 重启功能 |
| P2 | #7 state_machine 无匹配 | 低 | NPC 状态显示 |
| P2 | #8 tr_surv_001 不触发 | 低 | 单个触发器 |

---

## 五、结论

**核心链路可用**：GameLoop FSM、NPC 对话、情感指令、事件触发与选择、章节切换均正常工作。

**3 个 P0 阻塞问题**需优先修复：
1. trust 量纲冲突 — 影响信任系统、触发器、结局
2. fired_trigger_ids 未更新 — 影响进度显示
3. 资源不衰减 — 影响生存压力和结局触发

修复这 3 个 P0 后，游戏的核心循环（对话→推进→事件→选择→结局）将完整可用。

---

## 附: 日志文件

- 完整 JSON 日志: [playthrough_log.json](./playthrough_log.json)
- 测试脚本: [test_full_playthrough.py](./test_full_playthrough.py)
