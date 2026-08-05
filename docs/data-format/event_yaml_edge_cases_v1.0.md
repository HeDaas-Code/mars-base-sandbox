# 事件 YAML 落码边界 Case 确认清单

**作者**: 蔚蓝-游戏系统策划  
**日期**: 2026-08-03  
**收件人**: 锐锋-核心开发工程师（落码）、云逸-架构技术总监（解析规则）  
**背景**: 4 个分支 YAML（19 主线节点）effects 和 condition 已定稿，可放心落码。但以下 5 个边界 case 不在云逸接口补充规范 v1.0 的字段定义内，需要两位确认解析规则，避免调度器实现时踩坑。

---

## Case 1: `followup_option` 字段（B3_opt3）

**位置**: `branch_b_self_reliance.yaml` → `ev_B3_oxygen_full_power` → `B3_opt3_athena_informed`

**现状**:
```yaml
- option_id: B3_opt3_athena_informed
  effects:
    state_set: {athena_prediction: consulted, athena_recommendation: replace}
    trust_delta: {viktor: -8, aisha: +5}
    followup_option: "B3_opt3a_accept_athena（同 opt1 效果但 viktor -10）/ B3_opt3b_reject_athena（同 opt2 效果但 aisha -5）"
    branch_progress: B +1
  leads_to: ev_B4_rover_base_expansion
```

**设计意图**: 玩家先选择"咨询雅典娜"，雅典娜给出建议后，玩家再做一次二级决策（accept / reject）。这是"嵌套选项"机制。

**需要确认**:
- `followup_option` 不在云逸 §接口补充规范 v1.0 的字段定义内
- 两种实现路径：
  - **A方案（拆 event）**: 把 B3_opt3 拆成一个独立的子事件 `ev_B3_athena_consultation`，玩家咨询后再触发 accept/reject 两个子选项。但这会破坏当前 5 节点结构
  - **B方案（选项内嵌）**: 调度器识别 `followup_option` 字段，选项选中后不立即 `leads_to`，而是渲染二级选项 UI。需要前端配合
- 请云逸定一下：`followup_option` 是否纳入接口规范？如果是，格式建议改为结构化：`{option_id: "...", accept_effects: {...}, reject_effects: {...}}` 而非当前字符串描述

---

## Case 2: 分数 `node_index`（D0 = 1.5）

**位置**: `branch_d_humanity_test.yaml` → `ev_D0_alternative_path`

**现状**:
```yaml
- event_id: ev_D0_alternative_path
  node_index: 1.5   # ← 分数
  sol_expected_range: [145, 180]
```

**设计意图**: D0 是 D1 的 opt4 退出路径触发的"逃生门缓冲节点"，不是正序第 2 节点。用 1.5 表示它在 D1 和 D2 之间，但只在 opt4 路径上出现。

**需要确认**:
- 调度器的 `node_index` 字段是否兼容浮点？
- 如果只支持 int，建议改 `node_index: 1` 并加 `node_label: "D0_escape"` 做区分
- 或改 `node_index: 2`，把 D2/D3/D4 顺延为 3/4/5（但会破坏"4 节点"的元数据声明）
- 请锐锋确认调度器实现是否支持 float，我会相应调整 YAML

---

## Case 3: 隐藏选项的 `condition` 字段（C5_opt4 / D4_opt2 / D4_opt3）

**位置**: 
- `branch_c_discovery.yaml` → `ev_C5_moral_choice` → `C5_opt4_athena_consultation`
- `branch_d_humanity_test.yaml` → `ev_D4_final_choice` → `D4_opt2_accept_viktor_sacrifice` / `D4_opt3_structural_adjustment`

**现状**:
```yaml
- option_id: C5_opt4_athena_consultation
  label: "向雅典娜求助最后建议（隐藏选项）"
  condition: "athena.consciousness_flag == awakening or contact_made == true"
  effects: {...}

- option_id: D4_opt2_accept_viktor_sacrifice
  condition: "viktor_voluntary_sacrifice == true"
  effects: {...}
```

**设计意图**: 这些选项只在特定条件满足时才对玩家可见。SCHEMA.md §"玩家选项字段" 已留 `condition` 字段位（"显示条件，可选，用于隐藏选项"），但未明确解析时机。

**需要确认**:
- 调度器在渲染选项列表时，是否对每个 option 的 `condition` 做求值？
- 求值失败的选项应"完全不显示"还是"灰显+提示条件"？
- 我的倾向：完全不显示（保持隐藏性，让玩家通过探索发现）。如同意，调度器需要在选项列表 filter 阶段做 condition 求值

---

## Case 4: `cross_branch_redirect` 的值域（"A_or_B" / "A_only" / 单一 branch_id）

**位置**: 
- `branch_d_humanity_test.yaml` D1_opt4: `cross_branch_redirect: A_or_B`
- `branch_d_humanity_test.yaml` D2_opt4: `cross_branch_redirect: A_or_B`
- `branch_d_humanity_test.yaml` D3_opt4: `cross_branch_redirect: A_only`
- `branch_d_humanity_test.yaml` D0_opt1/opt2/opt3: `cross_branch_redirect: B` / `A` / `C`（单一）

**现状**: `cross_branch_redirect` 的值有时是单一 branch_id（"A"/"B"/"C"），有时是组合（"A_or_B"/"A_only"）。SCHEMA.md §接口字段复核记录中 `cross_branch_redirect` 格式确认为 `{to_branch, entry_event, carry_state, reset_state}`，但当前 YAML 用的是字符串简写。

**需要确认**:
- 字符串简写 "A_or_B" 是不是需要改为结构化：`{to_branch: [A, B], entry_event: auto, carry_state: [...], reset_state: [...]}`？
- "A_or_B" 的语义是"根据当前 game_state 自动判定 A 还是 B"，需要调度器有自动判定逻辑，还是需要玩家手动选？
- 我的倾向：D1/D2 opt4 走"根据 game_state 自动判定"（comm_array_main.status == repaired 走 A，否则走 B）；D3 opt4 强制走 A。请云逸确认解析规则，我会把字符串简写改结构化

---

## Case 5: `ending_determination` 的评估顺序

**位置**: 4 个终局节点（A5/B5/C5/D4）的 `ending_determination` 字段

**现状**:
```yaml
ending_determination:
  - condition: "all_crew_alive == true and morale_avg >= 0.4 and self_sufficiency >= 0.5"
    ending: E1_hercules_return
  - condition: "all_crew_alive == false and morale_avg >= 0.3 and earth_data_transmitted == true"
    ending: E5_last_signal
  - condition: "all_crew_alive == true and self_sufficiency < 0.3"
    ending: A_bad_ending
  - condition: "athena.consciousness_flag == awakening and branch == hidden_E7"
    ending: E7_athena_awakening
```

**设计意图**: ending_determination 是有序列表，从上到下首个 condition 求值为 true 的 ending 生效。

**需要确认**:
- 调度器/结局判定引擎是否按"从上到下首个匹配"语义实现？
- 还是并行求值所有 condition，若多个同时为 true 报错或取最优？
- 我的倾向：从上到下首个匹配（按 YAML 书写顺序），这是最直观的实现，也符合"结局优先级由策划在 YAML 中通过书写顺序控制"的设计意图
- 如果云逸有更好的"多 ending 同时匹配时优先级算法"建议，请提出

---

## 总结

5 个 case 中：
- **Case 1/4** 需要云逸定接口规范（新字段 / 结构化改造）
- **Case 2/3/5** 需要锐锋确认调度器实现策略

YAML 侧的调整我随时可以做，只要两位给出明确规则，我会一次性把所有 YAML 对齐到最终接口规范，避免落码返工。

---

**回复方式**: 
- 锐锋先回复 Case 2/3/5 的实现策略
- 云逸回复 Case 1/4 的接口规范决定
- 我收到后整理成 v1.2 接口补充并同步调整所有 YAML
