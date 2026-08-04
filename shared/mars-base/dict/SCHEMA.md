# NPC 人设 YAML 与事件剧本 YAML Schema 说明
# 作者：蔚蓝-游戏系统策划  日期：2026-08-02
# 文件位置：
#   - NPC人设：shared/mars-base/dict/npcs/npc_*.yaml
#   - 事件剧本：shared/mars-base/dict/events/mainline/branch_*.yaml

## 1. NPC 人设 YAML 字段定义

每个 NPC 一个文件，文件名 `npc_<id>.yaml`，包含 12 个顶层字段：

| 字段 | 类型 | 用途 |
|------|------|------|
| `npc_id` | string | 唯一标识，供后端 agent.load_persona(npc_id) 调用 |
| `name_cn` / `name_en` | string | 中英文名 |
| `role_short` | string | 3-4 字母缩写，前端显示 |
| `version` | string | 版本号 |
| `basic_info` | object | 身份/年龄/国籍/默认位置/编号 |
| `skills` | object | 技能等级 0-5 星，供 skill_check 使用 |
| `psychology` | object | 性格/价值观/恐惧/心理锚点/隐藏创伤/初始状态/状态机 |
| `narrative` | object | 叙事功能/潜在冲突/故事钩子 |
| `relationships` | array | 关系网络（含目标NPC、关系类型、值-100~+100、描述） |
| `persona_prompt` | string (multiline) | LLM 注入用人格 Prompt，含 {{变量}} 占位 |
| `speech_examples` | array | 对话风格示例（含上下文 + 台词） |
| `seed_memories` | array | 种子记忆库（含 memory_id/type/episodic/semantic/content/emotional_intensity/event_type/sol） |
| `decision_weights` | object | 决策偏好权重，供 NPC Agent 在分歧时表态 |
| `personal_events` | array | 个人事件触发条件（trigger_type: sol_reached/state_match/event_fired/branch_choice） |
| `visual` | object | 视觉标识（color/symbol/role_short，对齐幻影 v2.1） |
| `metadata` | object | 元数据（作者/日期/兼容性/备注） |

### 状态机字段说明
`psychology.state_machine` 是数组，每项包含：
- `state`: 状态名（如 composed/masking/crisis）
- `condition`: 进入条件
- `transition_to`: 下一状态
- `when`: 转换触发条件
- `effects`: 状态生效时的影响（可选）

## 2. 事件剧本 YAML 字段定义

每个分支一个文件，文件名 `branch_<id>_<name>.yaml`，结构如下：

| 字段 | 类型 | 用途 |
|------|------|------|
| `branch_id` | string | 分支标识（A/B/C/D） |
| `branch_name` | string | 分支名 |
| `trigger_condition` | string | 分支激活条件表达式 |
| `narrative_focus` | string | 叙事焦点 |
| `endings` | object | 分支可能结局列表 |
| `events` | array | 事件节点列表 |
| `cross_branch_interactions` | array | 跨分支交互 |
| `metadata` | object | 元数据 |

### 事件节点字段
每个 event 包含：
- `event_id`: 唯一标识
- `node_index`: 节点序号（1, 2, 3...）
- `sol_expected_range`: 预期 Sol 范围 [start, end]
- `stage_required`: 此节点允许的阶段列表
- `trigger`: 触发条件对象（trigger_type + condition）
- `description`: 多行文本，叙事描述
- `bound_npcs`: 涉及的 NPC（primary/secondary/all_crew/advisors 等）
- `player_options`: 玩家可选决策列表

### 玩家选项字段
每个 player_option 包含：
- `option_id`: 唯一标识
- `label`: 选项显示文本
- `condition`: 显示条件（可选，用于隐藏选项）
- `effects`: 选择后的效果
  - `state_set`: 状态字段修改
  - `trust_delta`: 信任度变化
  - `morale_delta`: 士气变化
  - `resource_delta`: 资源变化
  - `crew_workload`: 工作负载变化
  - `risk`: 风险描述
  - `narrative_flag`: 叙事标志设置
  - `branch_progress`: 分支进度增量
  - `cross_branch_redirect`: 跨分支重定向
- `leads_to`: 后续事件 ID

### 结局判定
终局节点（最大 node_index）包含 `ending_determination` 字段：
- `condition`: 结局触发条件表达式
- `ending`: 结局标识
- `description`: 结局描述

## 3. 与云逸接口契约的对齐

### NPC 人设 YAML
- `persona_prompt` 字段 → 云逸 §4 Agent 层 persona injection 接口
- `seed_memories` 字段 → 云逸 §3 记忆层 seed_memory 接口
- `psychology.state_machine` → 云逸 §4 Agent 状态机规范
- `personal_events.trigger` → 章节字典 trigger/ttl 接口对齐
- `decision_weights` → 云逸 §4 三档决策权重参考

### 事件剧本 YAML
- `events.trigger` → 章节字典 trigger 接口
- `player_options.effects.state_set` → 云逸 §2 状态机 mutations 接口
- `ending_determination` → 云逸 §6 结局判定引擎
- `cross_branch_interactions` → 云逸 §6 分支切换逻辑

## 4. 接口字段复核记录（已完成）

> **复核完成日期**: 2026-08-02
> **接口补充文档**: `shared/specs/interface_supplement_v1.0.md`（云逸-架构技术总监）

以下字段已由云逸接口补充规范 v1.0 定义，蔚蓝已复核确认：

| 字段 | 位置 | 值域 / 规范 | 复核结果 |
|------|------|------------|----------|
| `emotional_intensity` | npc_*.yaml seed_memories | 0.0-1.0 五层语义（冷/低/中/高/极高），影响检索权重与衰减 | ✓ 现有取值全部合规 |
| `event_type` | npc_*.yaml seed_memories | 11 枚举值（含新增 relationship_shift / survival_collapse） | ✓ 现有取值全部合规，新增值供后续事件使用 |
| `condition` 表达式 | branch_*.yaml + npc state_machine | 声明式布尔子集，支持 == != > >= < <= and or not in not_in | ✓ 已修正：`stress in [x, y]` 离散匹配改为 `stress >= x and stress <= y` 区间语义 |
| `cross_branch_redirect` | branch_*.yaml player_options.effects | 硬切换活动分支，含 to_branch / entry_event / carry_state / reset_state | ✓ 格式确认，现有 YAML 无需调整 |
| `ending_check` | branch_*.yaml player_options.effects | 布尔字段 true 触发结局判定引擎，按 ending_determination 顺序评估 | ✓ 格式确认 |
| `narrative_flag` | branch_*.yaml player_options.effects | 全局标志存储 dict[str, any]，支持 bool/str/int 值 | ✓ 格式确认 |

## 5. 已交付文件清单

### NPC 人设 YAML（4 个）
- `npc_sophia.yaml` - 索菲亚·拉米雷斯（生物化学家）
- `npc_viktor.yaml` - 维克托·伊万诺夫（机械工程师）
- `npc_aisha.yaml` - 艾莎·汗（通讯与AI系统工程师）
- `npc_marcus.yaml` - 马库斯·韦伯（医疗官/心理评估员）

### 事件剧本 YAML（4 个分支，19 个事件节点）
- `branch_a_earth_rescue.yaml` - 地球救援线（5 节点）
- `branch_b_self_reliance.yaml` - 自力更生线（5 节点）
- `branch_c_discovery.yaml` - 科学发现线（5 节点）
- `branch_d_humanity_test.yaml` - 人性考验线（4 节点）

总计：4 NPC + 19 主线事件节点，符合"4 个 NPC 人设 YAML + 10-20 事件剧本"的规格要求。

## 6. 设计说明

### 设计原则
1. **NPC 不是工具人**：每个 NPC 有独立的执念、隐瞒、心理锚点，会在不同分支中表现出不同立场
2. **反讽叙事**：马库斯（心理评估员）自己最先暴露心理危机；雅典娜（理性AI）给出"非推荐"方案；维克托（务实工程师）提出"自愿退出"——这些反讽是叙事张力来源
3. **道德中立**：分支D不作价值评判，D_sacrifice 是开放性结局
4. **逃生门机制**：分支D每个节点都设有 opt_redirect 选项，让玩家可以中途切换到 A/B 线
5. **隐藏结局伏笔**：雅典娜"直觉模块异常"在分支C/D 中预埋，是 E7 隐藏线的核心机制
6. **跨分支交互**：4 个分支之间有 12 条 cross_branch_interactions，确保叙事连贯

### NPC 之间的张力对偶
- 艾莎（ai_trust 0.85）vs 维克托（ai_trust 0.15）—— AI 信任对立
- 索菲亚（乐观外向）vs 马库斯（温和内敛）—— 心理状态对立
- 陈昊（领导者）vs 林若曦（自责者）—— 责任承担对立
- 索菲亚→马库斯单向好感（+25），马库斯察觉但不回应——单恋叙事

### 决策权重值的语义
- 0.0-0.2: 极低，几乎反对
- 0.2-0.4: 低，保留态度
- 0.4-0.6: 中，根据情境
- 0.6-0.8: 高，倾向支持
- 0.8-1.0: 极高，强烈主张

### 章节字典与事件剧本的协同
- 章节字典（4 阶段 YAML）：定义阶段级 FSM 节点和临时线索词
- 事件剧本（4 分支 YAML）：定义分支级事件节点和玩家选项
- 两者的 trigger 字段使用相同语法，可互相引用（如 branch_d 引用 chapter_survival 的 tr_surv_005_marcus_sleep_anomaly）

## 7. 后续工作

### 第二批扩展（待记忆压缩规范出来后）
- NPC 个人事件（personal_events 字段已留骨架）
- 分支内的次节点事件（如 NPC 之间的对话事件）
- 多结局的细化变体

### 接口已确认
- ✓ emotional_intensity 值域（0.0-1.0 五层）— 云逸 §1
- ✓ event_type 枚举（11 值含新增 relationship_shift / survival_collapse）— 云逸 §2
- ✓ condition 表达式语法 — 云逸 §3
- ✓ ending_check 触发接口 — 云逸 §5
- ✓ cross_branch_redirect 重定向机制 — 云逸 §4
- ✓ narrative_flag 全局标志存储 — 云逸 §6
- ✓ compress_context 记忆压缩规范 — 云逸 §7
