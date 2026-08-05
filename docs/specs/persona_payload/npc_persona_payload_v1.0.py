# ⚠️ DEPRECATED — 本文件作废，请勿使用

**作废时间**: 2026-08-03 03:23
**作废原因**: 与既有的 5 个 NPC YAML（`shared/mars-base/dict/npcs/npc_*.yaml`）存在严重数据冲突，YAML 为更早版本且字段更完整，应作为真相源。

## 主要冲突

| # | 字段 | 本 Python 模块 | NPC YAML（权威） |
|---|------|-----------------|---------------------|
| 1 | 太阳风暴 Sol 编号 | Sol 100 | Sol 83 |
| 2 | 玩家信号接入 Sol | 未明确（沿用陈昊口径 Sol 117） | Sol 100 |
| 3 | 种子记忆条数/人 | 12 | 6（更精炼） |
| 4 | sophia 父亲去世时间 | "三个月前" | "Sol 87 前后" |
| 5 | viktor 风暴时肩伤 | 未提 | 被舱盖砸右肩（marcus 处理） |
| 6 | lin_ruoxi 风暴前兆线 | 简化处理 | 完整 hook：72h 前预警邮件被陈昊压第三条 |

## 权威来源

- **5 个 NPC YAML**: `shared/mars-base/dict/npcs/npc_{sophia,viktor,aisha,marcus,lin_ruoxi}.yaml`
  - 含 persona_prompt / speech_examples / seed_memories（6条）/ skills / decision_weights / state_machine / personal_events / relationships / visual
  - 字段完整度远超本 Python 模块
  - 由策划侧 2026-08-02 编写

## 仍待解决的策划侧冲突

- 陈昊 `prompt.py` / `seed_memories.py` 用 Sol 100 为风暴日，与 5 个 NPC YAML 的 Sol 83 不一致
- 需要统一为 Sol 83（YAML 为权威）并同步修订陈昊 prompt / seed_memories 中的所有 Sol 编号
- 已报告给锐锋与云逸

## 本文件保留原因

仅作为冲突发现过程的记录，避免误用。**任何代码合并请使用 NPC YAML，不要使用本文件。**
