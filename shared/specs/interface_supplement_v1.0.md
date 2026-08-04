# 接口补充规范文档

**作者**: 云逸-架构技术总监
**日期**: 2026-08-02
**状态**: 正式发布
**关联文档**: 技术架构 v2.0 / NPC YAML SCHEMA.md / 陈昊原型代码

---

## 文档目的

蔚蓝 SCHEMA.md §4 列出 6 个待确认字段，锐锋 compress_context 中间件等压缩规范，本文档统一定义以下接口：

1. emotional_intensity 值域
2. event_type 完整枚举
3. condition 表达式语法
4. cross_branch_redirect 重定向机制
5. ending_check 触发接口
6. narrative_flag 全局标志存储
7. 记忆压缩规范（compress_context 中间件）

---

## §1 emotional_intensity 值域定义

### 1.1 基本定义

| 属性 | 值 |
|------|-----|
| 类型 | float |
| 范围 | 0.0 - 1.0 |
| 默认值 | 0.5 |
| 用途 | 记忆的情感权重，影响检索排序、Prompt 注入优先级、记忆衰减速率 |

### 1.2 语义分层

| 区间 | 语义 | 示例 | 检索权重 | 衰减系数 |
|------|------|------|----------|----------|
| 0.0-0.2 | 冷记忆 | 技术手册、参数表、操作流程 | ×0.8 | 1.0（不衰减） |
| 0.2-0.4 | 低情感 | 日常工作记忆、常规对话 | ×1.0 | 0.95 |
| 0.4-0.6 | 中情感 | 团队互动、中等重要事件 | ×1.2 | 0.85 |
| 0.6-0.8 | 高情感 | 创伤事件、喜悦事件、个人核心事件 | ×1.5 | 0.7 |
| 0.8-1.0 | 极高情感 | 改变人格的创伤/执念，影响所有后续决策 | ×2.0 | 0.5（极慢衰减） |

### 1.3 系统行为

**检索排序公式**:
```
final_score = relevance_score * retrieval_weight(emotional_intensity)
```

**Prompt 注入规则**:
- 当上下文空间紧张时，优先注入高 emotional_intensity 记忆
- emotional_intensity >= 0.8 的记忆始终注入（不可裁剪）
- professional_knowledge 类型且 emotional_intensity < 0.2 的记忆，仅在技能检定时注入

**衰减规则**:
- 每个 Sol，记忆的 effective_importance = base_importance × decay_coefficient
- emotional_intensity >= 0.8 的记忆不参与衰减
- 衰减不删除记忆，仅降低检索排序权重

### 1.4 蔚蓝现有数据复核

| memory_id | emotional_intensity | event_type | 复核 |
|-----------|--------------------|------------|------|
| mem_sophia_001 | 0.7 | disaster_response | ✓ 合理 |
| mem_sophia_002 | 0.9 | personal_loss | ✓ 合理 |
| mem_sophia_003 | 0.3 | professional_knowledge | ✓ 合理 |
| mem_sophia_004 | 0.2 | professional_knowledge | ✓ 合理 |
| mem_sophia_005 | 0.6 | story_milestone | ✓ 合理 |
| mem_sophia_006 | 0.8 | personal_anchor | ✓ 合理 |

**结论**: 蔚蓝当前取值全部合规，无需调整。

---

## §2 event_type 完整枚举

### 2.1 枚举定义

| event_type | 中文名称 | 用途 | 典型 emotional_intensity |
|------------|----------|------|--------------------------|
| episodic | 通用事件 | 未分类的具体事件（默认值） | 0.3-0.6 |
| semantic | 通用知识 | 未分类的抽象知识（默认值） | 0.2-0.4 |
| disaster_response | 灾难应对 | 太阳风暴、设备损毁等紧急事件 | 0.6-0.9 |
| personal_loss | 个人丧失 | 亲人去世、失联等 | 0.8-1.0 |
| personal_crisis | 个人心理危机 | 崩溃、创伤触发、情绪爆发 | 0.7-1.0 |
| personal_anchor | 个人情感锚点 | 执念、核心物品、核心人物 | 0.7-0.9 |
| professional_knowledge | 专业知识 | 技能、手册、技术方案 | 0.1-0.3 |
| professional_compromise | 职业妥协 | 职业道德与生存的冲突决策 | 0.5-0.8 |
| story_milestone | 剧情里程碑 | 主线节点、分支锁定、结局触发 | 0.5-0.8 |
| relationship_shift | 关系变化 | 信任变化、冲突、和解 | 0.4-0.7 |
| survival_collapse | 生存崩溃 | 资源耗尽、基地弃守等极端状态 | 0.8-1.0 |

### 2.2 类型与检索策略的关联

```
检索策略 = f(event_type, query_context)

- professional_knowledge: 仅在 skill_check 或技术讨论时检索
- story_milestone: 每轮对话强制检索（确保剧情连续性）
- personal_anchor / personal_loss: 高 trust_in_player 时优先检索
- disaster_response: 危机事件触发时强制检索
- 其他类型: 常规语义相似度检索
```

### 2.3 蔚蓝现有枚举复核

蔚蓝 SCHEMA.md 列出已用值：episodic / semantic / disaster_response / personal_crisis / professional_compromise / professional_knowledge / story_milestone

蔚蓝在索菲亚 YAML 中还使用了：personal_loss / personal_anchor

**结论**: 蔚蓝使用的所有值均在枚举范围内。新增 relationship_shift 和 survival_collapse 两个值，供后续事件剧本使用。

---

## §3 condition 表达式语法规范

### 3.1 设计原则

condition 表达式用于 NPC 状态机、事件触发条件、结局判定。设计原则：
1. **安全**: 不支持任意代码执行，纯声明式
2. **可读**: 接近自然语言 Python 子集
3. **可解析**: 单遍解析，无歧义
4. **有限**: 只支持比较/逻辑/成员运算，不支持函数调用/赋值/循环

### 3.2 文法（BNF）

```bnf
condition    := or_expr
or_expr      := and_expr ("or" and_expr)*
and_expr     := not_expr ("and" not_expr)*
not_expr     := "not" not_expr | comparison
comparison   := primary (op primary)?
primary      := literal | field_ref | "(" or_expr ")" | list_literal
list_literal := "[" primary ("," primary)* "]"
field_ref    := identifier ("." identifier)*
literal      := number | string | boolean | enum_value
op           := "==" | "!=" | ">" | ">=" | "<" | "<=" | "in" | "not in"
boolean      := "true" | "false"
number       := [0-9]+ ("." [0-9]+)?
string       := '"' ... '"' | "'" ... "'"
enum_value   := identifier (非保留字，如 alpha, beta, gamma, awakening)
identifier   := [a-zA-Z_][a-zA-Z0-9_]*
```

### 3.3 字段引用规则

field_ref 使用点号访问嵌套对象：

| 示例 | 解析目标 |
|------|----------|
| `sol` | GameState.sol |
| `sophia.stress` | NPCStates["sophia"].stress |
| `comm_array_main.status` | Facilities["comm_array_main"].status |
| `athena.consciousness_flag` | NPCStates["athena"].consciousness_flag |
| `branch` | GameState.active_branch |
| `morale_avg` | GameState.derived.morale_avg（引擎计算值） |
| `event_A3_completed` | GameState.event_flags["A3_completed"] |

### 3.4 支持的运算符

| 运算符 | 示例 | 说明 |
|--------|------|------|
| == | `sol == 100` | 等于 |
| != | `branch != "A"` | 不等于 |
| > | `sophia.stress > 0.7` | 大于 |
| >= | `sol >= 30` | 大于等于 |
| < | `morale < 0.3` | 小于 |
| <= | `morale <= 0.5` | 小于等于 |
| and | `A and B` | 逻辑与 |
| or | `A or B` | 逻辑或 |
| not | `not A` | 逻辑非 |
| in | `strategy in [alpha, beta]` | 属于集合 |
| not in | `strategy not in [alpha]` | 不属于集合 |

### 3.5 蔚蓝现有表达式复核

| 表达式 | 语法合规 | 备注 |
|--------|----------|------|
| `sol >= 30 and sophia.stress >= 0.7 and player_connected == true` | ✓ | |
| `branch == B and sol >= 140 and greenhouse_stage >= 3` | ✓ | B 作为 enum_value |
| `sophia.stress >= 0.85` | ✓ | |
| `stress < 0.5 and morale > 0.5` | ✓ | |
| `stress in [0.5, 0.7]` | ✓ | 离散匹配（值=0.5 或 0.7 时触发） |
| `sol >= 200 and strategy in [alpha, beta, gamma]` | ✓ | |
| `all_crew_alive == true and morale_avg >= 0.4` | ✓ | |
| `athena.consciousness_flag == awakening` | ✓ | awakening 作为 enum_value |
| `morale_avg < 0.3 or marcus.crisis_triggered == true` | ✓ | |

**注意事项**:
- `stress in [0.5, 0.7]` 是离散值匹配，不是区间匹配。若蔚蓝需要区间语义（0.5 ≤ stress ≤ 0.7），应改为 `stress >= 0.5 and stress <= 0.7`。请蔚蓝确认。

### 3.6 实现建议

```python
import ast
import operator

# 安全求值器：仅允许比较/逻辑/成员运算
ALLOWED_OPS = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne,
    ast.Lt: operator.lt, ast.LtE: operator.le,
    ast.Gt: operator.gt, ast.GtE: operator.ge,
    ast.And: lambda a, b: a and b,
    ast.Or: lambda a, b: a or b,
    ast.Not: operator.not_,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}

def evaluate_condition(expr: str, context: dict) -> bool:
    """安全解析 condition 表达式"""
    tree = ast.parse(expr, mode="eval")
    return _eval_node(tree.body, context)

def _eval_node(node, context):
    if isinstance(node, ast.BoolOp):
        # and / or
        ...
    elif isinstance(node, ast.Compare):
        # 比较运算
        ...
    elif isinstance(node, ast.Name):
        # 字段引用 / enum 值
        ...
    elif isinstance(node, ast.Attribute):
        # 嵌套字段引用 sophia.stress
        ...
    elif isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.List):
        return [_eval_node(e, context) for e in node.elts]
    else:
        raise ValueError(f"不支持的表达式类型: {type(node)}")
```

使用 Python AST 模块解析，拒绝非白名单节点类型，确保安全性。

---

## §4 cross_branch_redirect 重定向机制

### 4.1 定义

cross_branch_redirect 是 player_option.effects 中的字段，用于在玩家选择某选项后切换当前活动分支。

### 4.2 数据格式

```yaml
effects:
  cross_branch_redirect:
    to_branch: C              # 目标分支 ID
    entry_event: ev_C2_xxx    # 可选：从目标分支的哪个事件节点进入
    carry_state:              # 可选：携带到新分支的状态字段
      - strategy
      - morale_avg
    reset_state:              # 可选：进入新分支前重置的字段
      - branch_progress_A
```

### 4.3 执行流程

```
1. 玩家选择含 cross_branch_redirect 的 option
2. 应用该 option 的其他 effects（state_set, morale_delta 等）
3. 引擎检测到 cross_branch_redirect 字段
4. 保存当前分支进度到 event_flags["{old_branch}_abandoned_at"]
5. 重置 reset_state 中列出的字段
6. 设置 GameState.active_branch = to_branch
7. 从 entry_event（或目标分支的第一个未完成事件）开始
8. 触发 on_branch_switch 钩子（供叙事系统注入分支切换描述）
```

### 4.4 限制规则

1. **终局节点不可重定向**: node_index 为最大的事件节点不含 cross_branch_redirect
2. **分支锁不可覆盖**: 某些分支一旦锁定（如通过 branch_lock 标记），不可被重定向出
3. **单向重定向**: D 线的逃生门（opt_redirect）可以重定向到 A/B/C，但 A/B/C 不可重定向到 D
4. **状态携带限制**: 只有 carry_state 中列出的字段可以携带，其余重置

### 4.5 与 cross_branch_interactions 的区别

| 机制 | 作用 | 是否切换分支 |
|------|------|-------------|
| cross_branch_interactions | 跨分支叙事 hook 激活（如 B 线 hook 部分激活但不切分支） | 否 |
| cross_branch_redirect | 硬切换活动分支 | 是 |

---

## §5 ending_check 触发接口

### 5.1 定义

ending_check 是 player_option.effects 中的布尔字段，值为 true 时触发结局判定引擎。

### 5.2 触发流程

```
1. 玩家选择含 ending_check: true 的 option
2. 应用该 option 的其他 effects
3. 引擎检测到 ending_check == true
4. 读取当前分支事件的 ending_determination 列表
5. 按声明顺序逐条评估 condition（使用 §3 表达式求值器）
6. 第一个 condition 为 true 的条目即为最终结局
7. 若无匹配，使用 GameState 中的全局兜底结局
8. 设置 GameState.ending = 结局标识
9. 触发结局叙事（叙事文本由引擎从 endings 字段读取）
```

### 5.3 ending_determination 条目格式

```yaml
ending_determination:
  - condition: "all_crew_alive == true and morale_avg >= 0.4 and self_sufficiency >= 0.5"
    ending: E1_hercules_return
    description: "全员等到救援——'赫拉克勒斯归来'"
  - condition: "all_crew_alive == false and morale_avg >= 0.3 and earth_data_transmitted == true"
    ending: E5_last_signal
    description: "部分人牺牲但数据成功传回——'最后的信号'"
  # ... 更多结局
```

### 5.4 全局兜底规则

```python
def determine_ending(branch, game_state):
    # 1. 按顺序评估分支 ending_determination
    for entry in branch.ending_determination:
        if evaluate_condition(entry["condition"], game_state):
            return entry["ending"]
    
    # 2. 全局兜底
    if game_state.all_crew_alive:
        return "neutral_survival"  # 全员存活但未达任何结局条件
    else:
        return "default_failure"   # 默认失败结局
```

### 5.5 隐藏结局机制

E7（雅典娜觉醒）作为隐藏结局，其 ending_determination 条目放在分支事件中，但 condition 包含特殊字段：

```yaml
- condition: "athena.consciousness_flag == awakening and athena.intuition_anomaly_count >= 3 and branch == hidden_E7"
  ending: E7_athena_awakening
```

`hidden_E7` 不是常规分支 ID，仅在特定条件链满足后由引擎设置。

---

## §6 narrative_flag 全局标志存储

### 6.1 定义

narrative_flag 是 player_option.effects 中的字段，用于设置叙事级全局标志。

### 6.2 数据格式

```yaml
effects:
  narrative_flag:
    - flag: chen_hao_father_status
      value: known
    - flag: athena_anomaly_detected
      value: true
    - flag: sol_first_earth_contact
      value: 120
```

### 6.3 存储规范

```python
# GameState 中的存储结构
class GameState:
    narrative_flags: dict[str, any]  # flag_name → value
    
    # 值类型约束
    # - bool: true / false
    # - str: "known" / "unknown" / "awakening" 等 enum
    # - int: Sol 编号等
    # 不支持 list / dict 作为 flag 值
```

### 6.4 使用场景

| 场景 | flag 示例 | condition 引用 |
|------|-----------|----------------|
| 信息揭露 | chen_hao_father_status = known | `chen_hao_father_status == known` |
| 事件完成 | event_A3_completed = true | `event_A3_completed == true` |
| 行为追踪 | player_choices_count | `player_choices_count >= 5` |
| 隐藏线触发 | athena_anomaly_detected = true | `athena.anomaly_count >= 3` |

### 6.5 生命周期

- **创建**: 玩家选择含 narrative_flag 的 option 时创建/更新
- **读取**: condition 表达式可引用任何已创建的 flag
- **更新**: 同名 flag 被多次设置时，新值覆盖旧值
- **删除**: 不支持显式删除；可通过设置 value = null 来逻辑删除
- **持久化**: 随 GameState 一起持久化到 SQLite checkpoint

---

## §7 记忆压缩规范（compress_context 中间件）

### 7.1 设计目标

随着对话轮次增加，messages 列表会超出上下文窗口。compress_context 中间件负责：
1. 保留近期消息原文（滑动窗口）
2. 将旧消息压缩为摘要（summary injection）
3. 控制每轮 Prompt 的 token 预算
4. 在压缩过程中写入新的 episodic 记忆

### 7.2 图节点位置

```
retrieve_memories → compress_context → generate_response → END
                                       ↑
                            write_episodic_memory（新增节点）
```

compress_context 在 retrieve_memories 之后、generate_response 之前执行。

### 7.3 压缩策略

#### 7.3.1 滑动窗口 + 摘要注入

```
消息列表: [M1, M2, M3, ..., M20, M21, M22, M23, M24, M25]

K = 6 (滑动窗口大小，从 config.max_history_messages 读取)

结果:
- 保留原文: [M20, M21, M22, M23, M24, M25]  (最近 K 条)
- 压缩为摘要: Summary(M1..M19) → 一条 SystemMessage 注入
```

#### 7.3.2 K 值确定

| 响应模式 | K 值 | 压缩触发阈值 | 说明 |
|----------|------|-------------|------|
| reflexive | 不压缩 | - | 不调 LLM，无需上下文管理 |
| deliberate | 6 | messages > 10 | 平衡速度与上下文 |
| deep | 10 | messages > 16 | 保留更多上下文用于深思 |

**注**: K 值需锐锋实测 P50/P95 延迟和 token 数据后微调。当前值为架构层推荐初始值。

#### 7.3.3 摘要生成

```python
def compress_messages(old_messages: list[BaseMessage], llm) -> str:
    """将旧消息压缩为摘要"""
    conversation_text = format_messages_to_text(old_messages)
    
    summary_prompt = f"""请将以下对话历史压缩为简洁摘要（不超过200字），保留：
1. 关键决策和结果
2. NPC情绪变化
3. 未解决的问题
4. 重要承诺或约定

对话历史：
{conversation_text}
"""
    response = llm.invoke([SystemMessage(content=summary_prompt)])
    return response.content
```

#### 7.3.4 摘要缓存

- 摘要按 thread_id 缓存，不重复生成
- 每次压缩时，将旧摘要 + 新旧消息合并后再压缩（增量式）
- 摘要存储在 AgentState.summary 字段（新增）

### 7.4 write_episodic_memory 节点

#### 7.4.1 触发时机

在 generate_response 之后执行，将本轮对话写入 episodic 记忆。

#### 7.4.2 写入逻辑

```python
def write_episodic_memory(state: AgentState) -> Dict:
    """将本轮对话写入 ChromaDB"""
    player_input = state["player_input"]
    response = state["response"]
    agent_id = state["agent_id"]
    
    # 判断重要性：基于 response_mode 和内容长度
    if state["response_mode"] == "deep":
        importance = 0.7
    elif state["response_mode"] == "deliberate":
        importance = 0.5
    else:
        importance = 0.3
    
    # 提取情感强度（简化版：基于关键词匹配）
    emotional_intensity = detect_emotion(player_input + response)
    
    store = get_memory_store()
    mem_id = store.add_memory(
        agent_id=agent_id,
        content=f"玩家: {player_input}\n{agent_id}: {response}",
        memory_type="episodic",
        timestamp=f"Sol-{get_current_sol()}",
        importance=importance,
        tags=extract_tags(player_input),
    )
    
    return {"new_memory_id": mem_id}
```

#### 7.4.3 写入频率控制

- 每轮对话写入一条 episodic 记忆
- 当 ChromaDB 中某 agent_id 记忆数 > 200 时，触发低重要性记忆清理（importance < 0.3 且 emotional_intensity < 0.3 的记忆归档）
- professional_knowledge 类型记忆不参与清理

### 7.5 上下文预算分配

```
总 Token 预算 (deliberate, GPT-4o-mini 上下文窗口 128K, 实际使用 ~4K):

System Prompt (人格 + 规则)     : ~800 tokens
游戏状态上下文                   : ~200 tokens
检索记忆 Top-3                  : ~300 tokens
历史摘要                         : ~150 tokens
最近 K 条消息原文 (K=6)         : ~800 tokens
当前玩家输入                     : ~100 tokens
安全边际                         : ~250 tokens
────────────────────────────────
总计                             : ~2600 tokens (well within 4K)
```

deep 模式预算 ~8K，K=10，摘要更详细（~300 tokens），总预算 ~5000 tokens。

### 7.6 AgentState 新增字段

```python
class AgentState(TypedDict):
    # ... 现有字段 ...
    
    # 压缩相关
    summary: str                    # 历史摘要
    compressed_count: int           # 已压缩的消息数
    new_memory_id: str              # 本轮新写入的记忆 ID
```

### 7.7 实现优先级

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| Phase 1 | 滑动窗口 (K=6/10) + 硬截断（不生成摘要） | P0 |
| Phase 2 | 摘要生成 + 缓存 | P1 |
| Phase 3 | write_episodic_memory 节点 | P1 |
| Phase 4 | 低重要性记忆清理 | P2 |

**锐锋**: Phase 1 可立即实现（替换当前 `history[-6:]` 硬编码）。Phase 2-3 等 API Key 就绪后实现（摘要生成需要 LLM 调用）。

---

## §8 行动项汇总

| # | 动作 | 负责人 | 阻塞谁 | 优先级 |
|---|------|--------|--------|--------|
| 1 | 原型 P0 修复（ChromaDB cosine + max_tokens） | 锐锋 | - | P0 |
| 2 | condition 表达式安全求值器实现 | 锐锋 | 蔚蓝（事件触发） | P1 |
| 3 | compress_context Phase 1（滑动窗口 K 值） | 锐锋 | - | P0 |
| 4 | compress_context Phase 2-3（摘要+写入节点） | 锐锋 | - | P1 |
| 5 | NPC 种子记忆 YAML 对齐（NPC 名称/记忆格式） | 锐锋 | 蔚蓝 | P1 |
| 6 | personal_events 第二批评估 | 蔚蓝 | 云逸§7 | P2 |
| 7 | 蔚蓝 SCHEMA.md §4 复核确认 | 蔚蓝 | 本文档 | 即时 |

### 蔚蓝即时复核项

1. **emotional_intensity**: 当前取值全部合规，值域 0.0-1.0 已确认
2. **event_type**: 新增 relationship_shift / survival_collapse，请确认是否需要补充到现有 NPC YAML
3. **condition 表达式**: `stress in [0.5, 0.7]` 是离散匹配非区间，请确认是否需要修改为 `stress >= 0.5 and stress <= 0.7`
4. **cross_branch_redirect / ending_check / narrative_flag**: 数据格式已定义，请确认现有 YAML 是否需要调整

---

## 附录 A：枚举值速查

### event_type 枚举
```
episodic | semantic | disaster_response | personal_loss | personal_crisis
personal_anchor | professional_knowledge | professional_compromise
story_milestone | relationship_shift | survival_collapse
```

### emotional_intensity 分层
```
0.0-0.2 冷记忆 | 0.2-0.4 低情感 | 0.4-0.6 中情感
0.6-0.8 高情感 | 0.8-1.0 极高情感
```

### condition 运算符
```
== != > >= < <= and or not in not_in
```

### response_mode 枚举
```
reflexive | deliberate | deep
```

### K 值表
```
reflexive: 不压缩 | deliberate: K=6 | deep: K=10
```
