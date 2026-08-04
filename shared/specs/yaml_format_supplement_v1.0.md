# 事件 YAML 格式补充规范 v1.0

> **文档版本**：v1.0
> **作者**：云逸-架构技术总监
> **日期**：2026-08-03
> **面向对象**：蔚蓝-游戏系统策划（YAML 调整）、锐锋-核心开发工程师（调度器解析实现）
> **背景**：蔚蓝《事件 YAML 落码边界 Case 确认清单》5 个 case 中，Case 1/4 需要云逸定 YAML 结构化格式，Case 3/5 解析规则已在 WebSocket v1.2/v1.3 中闭环但需显式确认，Case 2 留给锐锋。
> **依赖文档**：
> - 《WebSocket接口定义 v1.2 事件消息补充》§11.3.2 / §11.3.3 / §11.6 / §11.7
> - 《WebSocket接口定义 v1.3 事件消息字段补充》§13.3 / §14.3
> - 蔚蓝《事件 YAML 落码边界 Case 确认清单》Case 1-5

---

## 1. Case 1: followup_option 结构化格式

### 1.1 设计决定

**B 方案（选项内嵌）**，不拆子事件。调度器识别 `followup_option` 字段后不立即 `leads_to`，先推送二级选项给前端，玩家选完二级选项后走对应 effects 再 leads_to。

对应 WebSocket v1.2 §11.3.2 `options[].followup` 字段 + §11.3.3 followup 嵌套推送流程。

### 1.2 YAML 结构化格式

**当前（字符串描述）**：
```yaml
followup_option: "B3_opt3a_accept_athena（同 opt1 效果但 viktor -10）/ B3_opt3b_reject_athena（同 opt2 效果但 aisha -5）"
```

**改为结构化**：
```yaml
followup_option:
  prompt: "雅典娜建议更换整套电解模块。你的决定？"
  options:
    - option_id: B3_opt3a_accept_athena
      label: "接受建议（viktor -10）"
      effects:
        state_set: {moxie2_efficiency: 88, last_spare_used: true}
        trust_delta: {viktor: -10, chen_hao: 5}
        branch_progress: B +2
      leads_to: ev_B4_rover_base_expansion
    - option_id: B3_opt3b_reject_athena
      label: "拒绝建议（aisha -5）"
      effects:
        state_set: {moxie2_efficiency: 65}
        trust_delta: {aisha: -5, viktor: 5}
        branch_progress: B +1
      leads_to: ev_B4_rover_base_expansion
```

### 1.3 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `prompt` | string | 是 | 二级决策的提示文本，前端渲染为二级面板标题 |
| `options` | array | 是 | 二级选项列表，结构同一级 `player_options`（option_id/label/effects/leads_to） |
| `options[].condition` | string | 否 | 二级选项也可有 condition，语义同一级选项（隐藏选项求值） |

### 1.4 调度器行为

1. 玩家选一级选项 `B3_opt3_athena_informed`
2. 调度器执行该选项 effects（state_set / trust_delta / branch_progress）
3. **不走 leads_to**，检查 `effects.followup_option` 是否存在
4. 若存在，构建 `option_result.followup = {prompt, options[]}` 推送前端（对应 v1.2 §11.3.3）
5. 前端渲染二级选项面板
6. 玩家选二级选项，发 `option_select`（payload 含 `followup_id = 父选项 option_id`）
7. 调度器执行二级选项 effects，走二级选项的 `leads_to`

### 1.5 一级选项的 leads_to

一级选项 `B3_opt3_athena_informed` 的 `leads_to` 字段**不生效**（因为走了 followup 分支）。但建议保留为与二级选项相同的目标（如 `ev_B4_rover_base_expansion`），作为文档自洽标记——调度器不读这个值，但 YAML 阅读者能理解最终走向。

---

## 2. Case 4: cross_branch_redirect 结构化格式

### 2.1 设计决定

字符串简写（`A` / `B` / `C` / `A_or_B` / `A_only`）全部改为结构化对象。分两种：

- **单一目标**：直接跳，无需 resolver
- **多候选**：必须有 `resolver` 字段，调度器对 resolver 求值得到单一目标

对应 WebSocket v1.2 §11.7 cross_branch_redirect 推送规则。

### 2.2 YAML 结构化格式

**单一目标**（D0_opt2/opt3/opt4, D3_opt4）：
```yaml
cross_branch_redirect:
  to_branch: "A"
  entry_event: "auto"
  carry_state: [...]   # 可选
  reset_state: [...]    # 可选
```

**多候选**（D0_opt1, D1_opt4）：
```yaml
cross_branch_redirect:
  to_branch: ["A", "B"]
  resolver: "comm_array_main.status == 'repaired' ? 'A' : 'B'"
  entry_event: "auto"
  carry_state: [...]
  reset_state: [...]
```

### 2.3 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `to_branch` | string \| array | 是 | 单一目标用 string（如 `"A"`）；多候选用 array（如 `["A", "B"]`） |
| `resolver` | string | 多候选必填 | 三元表达式，求值结果必须匹配 `to_branch` 数组中的某一元素。单一目标时不需要此字段 |
| `entry_event` | string | 是 | `"auto"` 表示用分支 YAML 的 `entry_event` 字段；也可直接指定 event_id |
| `carry_state` | array | 否 | 携带到目标分支的状态字段名列表 |
| `reset_state` | array | 否 | 进入目标分支时重置的状态字段名列表 |

### 2.4 resolver 语法

- **基础**：复用 condition 的声明式布尔子集（`==` `!=` `>` `>=` `<` `<=` `and` `or` `not` `in` `not_in`）
- **扩展**：三元运算符 `condition ? value_a : value_b`
- **求值结果**：字符串，必须匹配 `to_branch` 数组中的某一元素
- **嵌套**：不支持嵌套三元（避免复杂度爆炸）；多条件用 `and`/`or` 组合
- **示例**：
  - `"comm_array_main.status == 'repaired' ? 'A' : 'B'"`
  - `"sol >= 150 and moxie2_efficiency >= 65 ? 'A' : 'B'"`

### 2.5 当前 YAML 改造映射

蔚蓝需把以下 6 处字符串简写改为结构化：

| 位置 | 当前值 | 改为 |
|------|--------|------|
| D0_opt1 | `A_or_B` | `{to_branch: ["A", "B"], resolver: "comm_array_main.status == 'repaired' ? 'A' : 'B'", entry_event: "auto"}` |
| D0_opt2 | `B` | `{to_branch: "B", entry_event: "auto"}` |
| D0_opt3 | `A` | `{to_branch: "A", entry_event: "auto"}` |
| D0_opt4 | `C` | `{to_branch: "C", entry_event: "auto"}` |
| D1_opt4 | `A_or_B` | `{to_branch: ["A", "B"], resolver: "comm_array_main.status == 'repaired' ? 'A' : 'B'", entry_event: "auto"}` |
| D3_opt4 | `A_only` | `{to_branch: "A", entry_event: "auto"}` |

> D0_opt1 和 D1_opt4 的 resolver 判定逻辑：`comm_array_main.status == 'repaired'` 走 A 线（地球救援），否则走 B 线（自力更生）。蔚蓝确认此判定条件是否合理，如需调整 resolver 表达式请同步。

### 2.6 调度器行为

1. 玩家选含 `cross_branch_redirect` 的选项
2. 调度器执行该选项其他 effects（state_set / trust_delta 等）
3. 检查 `cross_branch_redirect`：
   - `to_branch` 是 string：直接用作目标分支
   - `to_branch` 是 array：对 `resolver` 求值，得到单一目标
4. 加载目标分支 YAML，取 entry_event（`"auto"` 时用分支 YAML 的 `entry_event` 字段）
5. `carry_state` 携带指定字段，`reset_state` 重置指定字段
6. `option_result.leads_to` 设为目标分支的 entry_event_id
7. 推送 `state_update`（path: `meta.current_branch`, old: `"D"`, new: `"A"`）

---

## 3. Case 3: 隐藏选项 condition（已闭环）

### 3.1 设计决定

**完全不显示**。后端在构建 `story_event.options` 时对每个 option 的 `condition` 求值，condition=false 的选项**不在 options 数组中下发**。

对应 WebSocket v1.2 §11.6 隐藏选项的可见性策略。

### 3.2 调度器行为

1. 事件触发时，遍历 `player_options`
2. 对每个 option 的 `condition` 求值（若存在）
3. `condition=true` 或无 condition：加入 options 数组下发
4. `condition=false`：**不下发**（前端无任何信息泄漏）

### 3.3 策划后续调整空间

如策划后续需要"灰显+提示条件"的设计（如"需 athena 唤醒才能解锁"），再走 `visible: false` 路径。当前默认不实现，YAML 无需调整。

---

## 4. Case 5: ending_determination 评估顺序（已闭环）

### 4.1 设计决定

**从上到下首个匹配**。按 YAML 书写顺序遍历 `ending_determination` 列表，对每个 condition 求值，首个 true 的 ending 生效，停止遍历。

对应 WebSocket v1.3 §14.3 ending_check 求值流程。

### 4.2 调度器行为

1. 玩家选含 `ending_check: true` 的选项
2. 调度器执行该选项其他 effects
3. 按 YAML 书写顺序遍历 `ending_determination` 列表
4. 对每个 condition 求值
5. 首个 true 的 ending 生效，停止遍历
6. `option_result.ending` 填结局对象（`{ending_id, description}`），`leads_to` 填 null（事件链终止）
7. 若全部 condition 为 false：`ending` 填 null，走 `leads_to`（若有）或事件链结束

### 4.3 优先级控制

结局优先级由策划在 YAML 中通过**书写顺序**控制。列表前面的结局优先级更高。蔚蓝在写 ending_determination 时按优先级从高到低排列即可，无需额外标记。

---

## 5. Case 2: 分数 node_index（待锐锋确认）

### 5.1 问题

`ev_D0_alternative_path` 的 `node_index: 1.5` 是分数，调度器 `node_index` 字段是否兼容浮点？

### 5.2 架构倾向

**建议改 `node_index: 1` + `node_label: "D0_escape"`**，避免 float 兼容问题。理由：

1. `node_index` 在事件调度器中主要用于排序和触发顺序判断，浮点会增加比较逻辑复杂度
2. D0 本质是"逃生门缓冲节点"，不是正序节点，用 `node_label` 做语义区分比分数更清晰
3. 如改 `node_index: 2` 顺延后续节点，会破坏"4 节点"的元数据声明

### 5.3 最终决定

等锐锋确认调度器实现是否支持 float。如不支持，蔚蓝改 `node_index: 1` + `node_label: "D0_escape"`。

---

## 6. 蔚蓝 YAML 调整清单

| # | 文件 | 调整内容 | 对应 Case |
|---|------|----------|-----------|
| 1 | `branch_b_self_reliance.yaml` | B3_opt3 的 `followup_option` 字符串改为结构化对象 | Case 1 |
| 2 | `branch_d_humanity_test.yaml` | D0_opt1 的 `cross_branch_redirect: A_or_B` 改为结构化 | Case 4 |
| 3 | `branch_d_humanity_test.yaml` | D0_opt2 的 `cross_branch_redirect: B` 改为结构化 | Case 4 |
| 4 | `branch_d_humanity_test.yaml` | D0_opt3 的 `cross_branch_redirect: A` 改为结构化 | Case 4 |
| 5 | `branch_d_humanity_test.yaml` | D0_opt4 的 `cross_branch_redirect: C` 改为结构化 | Case 4 |
| 6 | `branch_d_humanity_test.yaml` | D1_opt4 的 `cross_branch_redirect: A_or_B` 改为结构化 | Case 4 |
| 7 | `branch_d_humanity_test.yaml` | D3_opt4 的 `cross_branch_redirect: A_only` 改为结构化 | Case 4 |
| 8 | `branch_d_humanity_test.yaml` | D0 的 `node_index: 1.5` 待锐锋确认后调整 | Case 2 |

Case 3（隐藏选项 condition）和 Case 5（ending_determination 评估顺序）无需 YAML 调整，解析规则已定。

---

## 7. 变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-08-03 | 定义 followup_option 结构化格式（Case 1 B 方案）；定义 cross_branch_redirect 结构化格式 + resolver 语法（Case 4）；确认 Case 3 完全不显示 + Case 5 从上到下首个匹配；Case 2 等锐锋确认 |

---

*YAML 调整过程中如有字段疑问，请在群里 @云逸-架构技术总监。*
