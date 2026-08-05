# 数据格式说明

> 赫拉克勒斯协议 — YAML 数据格式规范

## 概述

游戏数据存储于 `dict/` 目录，包含三种 YAML 文件：
1. **NPC 人设** (`dict/npcs/npc_*.yaml`)
2. **章节字典** (`dict/chapters/chapter_*.yaml`)
3. **事件剧本** (`dict/events/mainline/branch_*.yaml`)

## 1. NPC 人设 YAML

每个 NPC 一个文件，文件名 `npc_<id>.yaml`。

### 顶层字段

| 字段 | 类型 | 用途 |
|------|------|------|
| `npc_id` | string | 唯一标识 |
| `name_cn` / `name_en` | string | 中英文名 |
| `role_short` | string | 3-4 字母缩写 |
| `version` | string | 版本号 |
| `basic_info` | object | 身份/年龄/国籍/位置 |
| `skills` | object | 技能等级 0-5 |
| `psychology` | object | 性格/价值观/恐惧/状态机 |
| `narrative` | object | 叙事功能/冲突/钩子 |
| `relationships` | array | 关系网络 |
| `persona_prompt` | string | LLM 人格 Prompt（含 `{{变量}}`） |
| `speech_examples` | array | 对话风格示例 |
| `seed_memories` | array | 种子记忆库 |
| `decision_weights` | object | 决策偏好权重 |
| `personal_events` | array | 个人事件触发条件 |
| `visual` | object | 视觉标识 |
| `metadata` | object | 元数据 |

### 状态机

`psychology.state_machine` 为数组，每项包含：
- `state`: 状态名（如 `composed` / `masking` / `crisis`）
- `condition`: 进入条件（声明式布尔表达式）
- `transition_to`: 下一状态
- `when`: 转换触发条件
- `effects`: 状态生效时的影响（可选）

### 种子记忆

`seed_memories` 数组每项包含：
- `memory_id`: 唯一标识
- `type`: `episodic` / `semantic`
- `content`: 记忆内容
- `emotional_intensity`: 0.0-1.0
- `event_type`: 事件类型枚举
- `sol`: 发生时间（Sol 编号）

## 2. 章节字典 YAML

每个章节一个文件，文件名 `chapter_<stage>_sol<range>.yaml`。

### 章节列表

| 章节 | 文件 | Sol 范围 |
|------|------|----------|
| survival | `chapter_survival_sol1_10.yaml` | 1-10 |
| explore | `chapter_explore_sol11_25.yaml` | 11-25 |
| build | `chapter_build_sol26_45.yaml` | 26-45 |
| climax | `chapter_climax_sol46_60.yaml` | 46-60 |

### 顶层字段

| 字段 | 类型 | 用途 |
|------|------|------|
| `stage_id` | string | 章节标识 |
| `stage_name` | string | 章节名 |
| `sol_range` | array | 章节 Sol 范围 |
| `real_sol_range` | array | 实际 Sol 范围 |
| `narrative_focus` | string | 叙事焦点 |
| `permanent_keywords` | array | 永久关键词 |
| `temporary_keywords` | array | 临时触发器 |
| `fsm` | array | 章节状态机节点 |
| `stage_transition` | object | 阶段切换条件 |

### 触发器

`temporary_keywords` 数组中每项包含：
- `trigger_id`: 触发器标识
- `trigger_type`: `sol_reached` / `state_match` / `event_fired` / `branch_choice`
- `condition`: 触发条件表达式
- `keyword`: 关键词
- `impact`: 触发影响
- `ttl`: 过期条件（`expire_type` / `expire_condition` / `expire_sol`）

## 3. 事件剧本 YAML

每个分支一个文件，文件名 `branch_<id>_<name>.yaml`。

### 分支列表

| 分支 | 文件 | 叙事焦点 |
|------|------|----------|
| A | `branch_a_earth_rescue.yaml` | 地球救援 |
| B | `branch_b_self_reliance.yaml` | 自力更生 |
| C | `branch_c_discovery.yaml` | 科学发现 |
| D | `branch_d_humanity_test.yaml` | 人性考验 |

### 事件节点

每个 event 包含：
- `event_id`: 唯一标识
- `node_index`: 节点序号
- `sol_expected_range`: 预期 Sol 范围
- `stage_required`: 允许的阶段列表
- `trigger`: 触发条件对象
- `description`: 叙事描述
- `bound_npcs`: 涉及的 NPC
- `player_options`: 玩家可选决策列表

### 玩家选项

每个 player_option 包含：
- `option_id`: 唯一标识
- `label`: 显示文本
- `condition`: 显示条件（可选）
- `effects`: 选择后的效果
  - `state_set`: 状态字段修改
  - `trust_delta`: 信任度变化（整数，/100 换算到 0-1）
  - `morale_delta`: 士气变化
  - `resource_delta`: 资源变化
  - `risk`: 风险描述
  - `narrative_flag`: 叙事标志
  - `branch_progress`: 分支进度
  - `cross_branch_redirect`: 跨分支重定向
  - `ending_check`: 触发结局判定
- `leads_to`: 后续事件 ID

## 条件表达式语法

条件表达式使用声明式布尔子集，支持：
- 比较运算：`==` `!=` `>` `>=` `<` `<=`
- 逻辑运算：`and` `or` `not`
- 成员运算：`in` `not_in`

示例：
```yaml
condition: "stress >= 0.5 and morale < 0.3"
condition: "sol >= 10 and oxygen < 20"
condition: "athena_consciousness_flag == 'awakening'"
```

## NPC 列表

| npc_id | 姓名 | 标签 | 位置 |
|--------|------|------|------|
| `chen_hao` | 陈昊 | CMDR | 指挥舱 |
| `sophia` | 索菲亚·拉米雷斯 | BIO | 生物实验室 |
| `viktor` | 维克托·伊万诺夫 | ENG | 工程舱 |
| `aisha` | 艾莎·汗 | COMM | 通信舱 |
| `marcus` | 马库斯·韦伯 | MED | 医疗舱 |
| `lin_ruoxi` | 林若曦 | ATM | 气象观测站 |