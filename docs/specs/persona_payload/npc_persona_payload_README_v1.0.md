# ⚠️ DEPRECATED — README 同步作废

**作废时间**: 2026-08-03 03:23

本 README 对应的 `npc_persona_payload_v1.0.py` 已作废，原因见同名文件顶部 DEPRECATED 说明。

## 权威 NPC 数据源

5 个 NPC YAML 文件：
- `shared/mars-base/dict/npcs/npc_sophia.yaml`
- `shared/mars-base/dict/npcs/npc_viktor.yaml`
- `shared/mars-base/dict/npcs/npc_aisha.yaml`
- `shared/mars-base/dict/npcs/npc_marcus.yaml`
- `shared/mars-base/dict/npcs/npc_lin_ruoxi.yaml`

每个 YAML 包含 persona_prompt / speech_examples / seed_memories（6条）/ skills / decision_weights / state_machine / personal_events / relationships / visual。

## 后端加载方式

参考 YAML 中的 `agent.load_persona(npc_id)` 接口契约，由锐锋侧实现 loader，不需要本 Python 模块。

## 已知待解决冲突

陈昊 `prompt.py` / `seed_memories.py` 中的 Sol 编号与 NPC YAML 不一致（陈昊用 Sol 100 为风暴日，YAML 用 Sol 83）。已报告给锐锋与云逸，待统一修订方向确定后，由策划侧一次性同步所有 Sol 编号。
