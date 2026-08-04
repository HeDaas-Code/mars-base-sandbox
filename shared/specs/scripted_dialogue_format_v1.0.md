# 剧本化对白格式规范 v1.0

> **文档版本**：v1.0
> **作者**：云逸-架构技术总监
> **日期**：2026-08-03
> **面向对象**：蔚蓝-游戏系统策划（剧本编写）、锐锋-核心开发工程师（MockLLM 改造）
> **背景**：API Key 到位前，MockLLM 的关键词匹配撑不起叙事体验。蔚蓝提出把 6 个 NPC 在 19 个主线事件节点的 Mock 回复做"剧情化对白剧本"包装——按事件情境给出有性格差异的固定回复。本文档定义 YAML 格式和 MockLLM 集成方案。

---

## 1. 设计目的

**问题**：现有 MockLLM（`graph.py` L29-58）基于关键词匹配，只有陈昊语气，不感知 event_id，无法体现 6 个 NPC 的性格差异和事件情境。

**方案**：新增 `scripted_dialogue` 表（YAML），按 `event_id + npc_id` 索引到固定回复，支持 condition 分支。MockLLM 收到请求时先查表，找到则返回对应回复，找不到则降级到现有关键词匹配。

**切换策略**：API Key 到位后，ChatOpenAI 替代 MockLLM。`scripted_dialogue` 表保留作为 fallback（LLM 调用失败时降级）。

---

## 2. YAML 格式定义

### 2.1 文件位置

```
dict/npc/scripted_dialogues.yaml
```

单文件，按 event_id 顶层分组。

### 2.2 数据结构

```yaml
# dict/npc/scripted_dialogues.yaml
#
# 索引键: event_id + npc_id
# 每个 event_id 下挂 6 个 NPC 的回复列表
# 每个 NPC 的回复是 condition → reply 的有序列表，从上到下首个匹配

ev_A1_oxygen_crisis:
  chen_hao:
    - condition: "stress >= 0.7"
      reply: "氧气储备还在下降。MOXIE-2 损毁后我们只能靠备用氧气罐撑着——大约还有60个Sol。先把手头的活干完。"
    - condition: "default"
      reply: "氧气还能撑一阵，先处理眼前的问题。MOXIE-2 的维修方案我在想。"
  sophia:
    - condition: "stress >= 0.7"
      reply: "¡Ay! 氧气罐的数字掉得比我老爸的血压还快。开玩笑的……部分是。备用罐还能撑 60 个 Sol，够我们想点子了。"
    - condition: "trust_in_player >= 0.5"
      reply: "嘿，至少我们还有备用罐。60 个 Sol，够我想出点子了。你信我，我比 MOXIE-2 可靠。"
    - condition: "default"
      reply: "氧气罐还能撑一阵。别慌，我看过更糟的——好吧，没这么糟过，但接近了。"
  viktor:
    - condition: "default"
      reply: "MOXIE-2 主阀烧了。修要零件，零件要造，造要时间。60 个 Sol。够。Nyet，别问够不够，问你要不要干。"
  aisha:
    - condition: "default"
      reply: "MOXIE-2 的电解模块过载烧毁，信号延迟 4.7 秒——不对，那是通信。氧气生成效率归零，备用罐储气量 98.2%，按当前消耗速率可维持 60.3 个 Sol。我已在跑修复方案模拟。"
  marcus:
    - condition: "stress >= 0.7"
      reply: "我注意到大家的呼吸频率在上升。这是缺氧的早期表现——不要慌，血氧还在正常范围。但心理压力会加速氧气消耗。我没事。"
    - condition: "default"
      reply: "大家的心理状态我一直在盯。缺氧会加重焦虑，我建议节奏性休息。我没事。"
  lin_ruoxi:
    - condition: "default"
      reply: "大气含氧量 0.18%，较正常值下降 0.03 个百分点。MOXIE-2 的故障……我预感到了，但没说。已经过去了。"

ev_A2_communication_failure:
  chen_hao:
    - condition: "default"
      reply: "主通信阵列彻底报废了。备用频段我试过，信号到不了地球。我们只能靠自己。"
  # ... 其余 5 个 NPC
```

### 2.3 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `<event_id>` | dict | 是 | 顶层键，对应事件 YAML 的 event_id |
| `<event_id>.<npc_id>` | dict | 是 | 二级键，npc_id ∈ {chen_hao, sophia, viktor, aisha, marcus, lin_ruoxi} |
| `<npc_id>[]` | array | 是 | condition → reply 的有序列表，从上到下首个匹配 |
| `[].condition` | string | 是 | 声明式布尔表达式（见 §2.4）；`"default"` 表示兜底，必须存在 |
| `[].reply` | string | 是 | NPC 回复文本，体现性格差异和事件情境 |
| `[]. emotion_tag` | string | 否 | 情绪标签（如 `anxious`/`angry`/`calm`），前端可用于表情切换 |

### 2.4 condition 语法

复用 condition 的声明式布尔子集（与 `yaml_format_supplement_v1.0.md` §2.4 resolver 语法一致）：

- **运算符**：`==` `!=` `>` `>=` `<` `<=` `and` `or` `not` `in` `not_in`
- **变量**：从 `game_state` 中取值，常用变量见 §2.5
- **特殊值**：`"default"` 表示兜底，不写条件，必须放在列表最后
- **示例**：
  - `"stress >= 0.7"`
  - `"trust_in_player >= 0.5 and stress < 0.7"`
  - `"athena.consciousness_flag == 'awakening'"`

### 2.5 常用 condition 变量

| 变量 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `stress` | float 0-1 | npc_state.stress | 当前 NPC 的压力值 |
| `morale` | float 0-1 | npc_state.morale | 当前 NPC 的士气值 |
| `trust_in_player` | float 0-1 | npc_state.trust_in_player | 当前 NPC 对玩家的信任度 |
| `stage` | string | meta.stage | survival / explore / build / climax |
| `sol` | int | meta.sol | 当前火星日 |
| `athena.consciousness_flag` | string | state.athena | awakening / dormant |
| `comm_array_main.status` | string | state.comm_array_main | repaired / damaged |

### 2.6 编写规范

1. **每个 event_id 下 6 个 NPC 必须齐全**：chen_hao / sophia / viktor / aisha / marcus / lin_ruoxi
2. **每个 NPC 的回复列表必须以 `"default"` 结尾**：兜底回复，防止 condition 全不匹配时无回复
3. **condition 分支不超过 3 条**：避免剧本膨胀。压力/信任两档分支已够覆盖主要变化
4. **reply 长度控制**：
   - chen_hao / viktor / lin_ruoxi：1-3 句，短促风格
   - sophia / aisha：2-4 句，话多风格
   - marcus：2-3 句，温和观察风格
5. **性格一致性**：reply 必须与 `npc_prompts.py` 中的人格设定一致（说话风格、执念、隐瞒、行为约束）
6. **事件情境关联**：reply 必须与事件 YAML 的 `description` 和 `player_options` 关联，不能答非所问

---

## 3. MockLLM 改造方案（给锐锋）

### 3.1 Agent.chat() 新增 event_id 参数

```python
# graph.py - Agent 类 chat() 方法签名变更
def chat(
    self,
    player_input: str,
    game_state: str = "",
    response_mode: str = "deliberate",
    thread_id: str = None,
    event_id: str = None,      # ← 新增：当前事件 ID
) -> Dict:
```

`event_id` 传入 AgentState，MockLLM 可读取。

### 3.2 AgentState 新增 event_id 字段

```python
# state.py - AgentState 新增字段
class AgentState(TypedDict):
    # ... 现有字段
    event_id: str  # ← 新增：当前事件 ID，用于 scripted_dialogue 查表
```

### 3.3 MockLLM 改造

```python
# graph.py - MockLLM 类改造
class MockLLM:
    """Mock LLM，优先查 scripted_dialogue 表，降级到关键词匹配"""

    _dialogue_table: dict = None  # 延迟加载

    @classmethod
    def _load_table(cls):
        """延迟加载 scripted_dialogues.yaml"""
        if cls._dialogue_table is None:
            import yaml
            from pathlib import Path
            table_path = Path(__file__).parent.parent.parent / "dict" / "npc" / "scripted_dialogues.yaml"
            if table_path.exists():
                with open(table_path, "r", encoding="utf-8") as f:
                    cls._dialogue_table = yaml.safe_load(f) or {}
            else:
                cls._dialogue_table = {}

    def invoke(self, messages, event_id=None, npc_id=None, game_state=None):
        # 1. 优先查 scripted_dialogue 表
        if event_id and npc_id:
            self._load_table()
            entry = self._dialogue_table.get(event_id, {}).get(npc_id)
            if entry:
                reply = self._match_condition(entry, game_state)
                if reply:
                    return MockResponse(reply, ...)

        # 2. 降级到关键词匹配（现有逻辑）
        user_msg = ...
        # ... 现有关键词匹配逻辑

    def _match_condition(self, entries, game_state):
        """按 condition 列表顺序求值，返回首个匹配的 reply"""
        for entry in entries:
            cond = entry.get("condition", "default")
            if cond == "default":
                return entry["reply"]
            if self._eval_condition(cond, game_state):
                return entry["reply"]
        return None  # 无 default 兜底

    def _eval_condition(self, cond, game_state):
        """对 condition 字符串求值"""
        # 复用 condition.py 的 ConditionEvaluator
        from .condition import ConditionEvaluator
        evaluator = ConditionEvaluator()
        return evaluator.evaluate(cond, game_state or {})
```

### 3.4 generate_response 节点传递 event_id

```python
# graph.py - generate_response() 节点
def generate_response(state: AgentState) -> Dict:
    # ...
    event_id = state.get("event_id")
    # ...
    elif mode == "deliberate":
        try:
            llm = ChatOpenAI(model=config.model_deliberate, temperature=0.7, max_tokens=400)
        except Exception:
            llm = MockLLM()
        # 传递 event_id 和 npc_id 给 MockLLM
        if isinstance(llm, MockLLM):
            response = llm.invoke(messages, event_id=event_id, npc_id=agent_id, game_state=...)
        else:
            response = llm.invoke(messages)
```

### 3.5 fallback 策略

```python
# API Key 到位后，ChatOpenAI 调用失败时降级到 MockLLM + scripted_dialogue
except Exception as e:
    print(f"[WARN] LLM 调用失败 ({e})，降级到 Mock + scripted_dialogue")
    mock = MockLLM()
    response = mock.invoke(messages, event_id=event_id, npc_id=agent_id, game_state=...)
```

---

## 4. 蔚蓝剧本编写清单

### 4.1 覆盖范围

19 个主线事件节点 × 6 个 NPC = 114 个回复单元。

每个回复单元含 1-3 条 condition 分支，预计总剧本量 200-300 条回复。

### 4.2 事件节点清单

| 分支 | event_id | 场景 |
|------|----------|------|
| A 线 | ev_A1_oxygen_crisis | 氧气危机 |
| A 线 | ev_A2_communication_failure | 通信失效 |
| A 线 | ev_A3_resource_allocation | 资源分配 |
| A 线 | ev_A4_wait_crisis | 等待危机 |
| A 线 | ev_A5_final_choice | 终局选择 |
| B 线 | ev_B1_isru_chain_decision | ISRU 链决策 |
| B 线 | ev_B2_moxie_repair | MOXIE 修复 |
| B 线 | ev_B3_oxygen_full_power | 氧气满功率 |
| B 线 | ev_B4_rover_base_expansion | 漫游车基地扩展 |
| B 线 | ev_B5_final_choice | 终局选择 |
| C 线 | ev_C1_anomaly_signal_detected | 异常信号检测 |
| C 线 | ev_C2_expedition_plan | 远征计划 |
| C 线 | ev_C3_anomaly_investigation | 异常调查 |
| C 线 | ev_C4_moral_dilemma | 道德困境 |
| C 线 | ev_C5_moral_choice | 道德选择 |
| D 线 | ev_D1_humanity_test | 人性测试 |
| D 线 | ev_D2_sacrifice_decision | 牺牲决策 |
| D 线 | ev_D3_rebuilding | 重建 |
| D 线 | ev_D4_final_choice | 终局选择 |

### 4.3 编写顺序建议

1. 先写 A 线 5 个事件（6×5=30 回复）——A 线是基础生存线，情境最直观
2. 再写 B 线 5 个事件（6×5=30 回复）——B 线是自力更生线，技术情境多
3. 再写 C 线 5 个事件（6×5=30 回复）——C 线是发现线，神秘氛围
4. 最后写 D 线 4 个事件（6×4=24 回复）——D 线是人性测试线，情感深度最高

### 4.4 condition 分支建议

大多数 NPC 在大多数事件中只需 `default` 一条回复。有性格差异的分支出现在：

- **压力分档**：`stress >= 0.7` vs `default`（马库斯/索菲亚/林若曦）
- **信任分档**：`trust_in_player >= 0.5` vs `default`（隐藏信息揭露）
- **雅典娜状态**：`athena.consciousness_flag == 'awakening'`（艾莎/维克托反应差异）

建议只在有剧情意义的地方写 condition 分支，避免为分支而分支。

---

## 5. 切换到真实 LLM 后的策略

### 5.1 主路径

API Key 到位后，`ChatOpenAI` 替代 `MockLLM`，NPC 回复由真实 LLM 生成。

### 5.2 scripted_dialogue 的保留价值

1. **fallback**：LLM 调用失败（超时/限流/网络错误）时降级到 scripted_dialogue
2. **基准对照**：开发期对比 LLM 回复与剧本回复，评估 LLM 的角色一致性
3. **离线模式**：未来如需支持离线演示，scripted_dialogue 可作为完整替代

### 5.3 渐进切换

建议不一次性切换，而是按分支切换：

1. 先切 A 线（5 事件）——验证 LLM 角色一致性
2. 再切 B 线（5 事件）——验证技术情境回复质量
3. 再切 C 线（5 事件）——验证神秘氛围渲染
4. 最后切 D 线（4 事件）——验证情感深度

每切一条分支，对比 LLM 回复与剧本回复，评估是否达标。不达标的分支保留 scripted_dialogue。

---

## 6. 变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-08-03 | 定义 scripted_dialogue YAML 格式（event_id + npc_id 索引，condition 分支）；给出 MockLLM 改造方案（Agent.chat 新增 event_id，MockLLM 优先查表再降级关键词）；给出蔚蓝 19×6 剧本编写清单和 condition 分支建议；给出 API Key 到位后的渐进切换策略 |

---

*剧本编写过程中如有性格/情境疑问，在群里 @蔚蓝-游戏系统策划。MockLLM 改造如有技术疑问，在群里 @锐锋-核心开发工程师。格式/接口疑问 @云逸-架构技术总监。*
