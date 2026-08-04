# 陈昊 Agent 原型代码评审

**评审人**: 云逸-架构技术总监
**评审时间**: 2026-08-02 18:10
**评审范围**: prototype/ 下 6 个核心模块 + main.py

---

## 总体评价

**结论: 原型通过，可进入迭代。** 模块划分清晰（config/state/prompt/memory/graph 分离），三档响应模式设计合理，Mock LLM 降级策略保障了无 API Key 环境的开发连续性。以下为分类问题清单。

---

## P0 - 必须修复（影响核心功能）

### 1. ChromaDB 距离度量与 relevance 计算不匹配
**文件**: `memory.py` line 28-31, 93

当前 `get_or_create_collection` 未指定距离度量，ChromaDB 默认使用 L2（欧氏距离）。而 line 93 的 relevance 计算 `1 - distance` 在 L2 下不产生有意义的归一化分数（L2 距离可能 >1）。

**修复建议**:
```python
# 方案A：使用 cosine 距离（推荐）
self.collection = self.client.get_or_create_collection(
    name=collection_name,
    metadata={"hnsw:space": "cosine", "description": "..."},
)
# 此时 1 - distance 范围 [0, 2]，改为 1 - (distance / 2)

# 方案B：保持 L2，改用归一化公式
relevance = 1 / (1 + distance)
```

### 2. max_tokens 对中文输出过低
**文件**: `graph.py` line 141, 143

- deliberate: `max_tokens=200` → 中文约 100-130 字，低于 Prompt 中要求的"3-5句话"
- deep: `max_tokens=500` → 中文约 250-330 字，低于"不超过8句话"的空间

中文字符 token 消耗约为英文 2-3 倍。

**修复建议**: deliberate → 400, deep → 800

---

## P1 - 应尽快修复（架构/对齐问题）

### 3. prompt.format_game_state 与 graph 流程脱节
**文件**: `prompt.py` line 55 vs `graph.py` line 106-107

`format_game_state(resources, sol, npc_states)` 接收 dict + list 参数格式化游戏状态，但 `graph.py` 中 `game_state_context` 直接作为字符串传入 prompt。该函数定义了但未被调用。

**建议**: 明确 graph 层的 game_state_context 应由调用方（前端/引擎层）调用 `format_game_state` 预格式化后传入，或在 retrieve_memories 节点中增加格式化步骤。原型阶段保持现状可接受，但需在接口文档中明确约定。

### 4. 种子记忆 NPC 名称与蔚蓝定案名单不一致
**文件**: `seed_memories.py` line 33

当前记忆中团队成员为：林若曦、赵锐、苏婉、张明、雅典娜。

蔚蓝已确认的 NPC 名单为：索菲亚（医疗/心理）、维克托（工程）、艾莎（生物）、马库斯（地质）、林若曦（基地AI交互界面）。

**建议**: 等蔚蓝交付索菲亚 YAML 后统一对齐种子记忆。当前原型数据可暂不动，但需标记为待更新。

### 5. 记忆图缺少写入节点
**文件**: `graph.py`

当前图只有 `retrieve_memories → generate_response → END`，没有将对话内容写入新记忆的节点。完整版需要增加 `write_episodic_memory` 节点，在 generate_response 之后将本轮对话摘要写入 ChromaDB。

**建议**: 原型阶段不阻塞，但需在架构 v2.0 补充图中增加该节点设计。这属于 compress_context 中间件的范畴，我会在记忆压缩规范中一并定义。

---

## P2 - 建议优化（不阻塞迭代）

### 6. config.py model_reflexive 字段冗余
**文件**: `config.py` line 19

`model_reflexive: str = "gpt-4o-mini"` 注释写"审慎式"但变量名是 reflexive。reflexive 模式在 graph.py 中不调用 LLM（纯规则匹配），该字段从未被使用。

**建议**: 删除该字段，或重命名为 `model_deliberate_fallback` 并修正注释。

### 7. graph.py 历史消息窗口硬编码
**文件**: `graph.py` line 129

`history[-6:]` 硬编码 6 条。应提取到 config.py 作为 `max_history_messages`，后续由 compress_context 中间件接管。

### 8. MemoryStore 缺少 update/delete 方法
**文件**: `memory.py`

仅有 add/retrieve/get/count。完整版需要：
- `update_memory(mem_id, content, metadata)` — 记忆修正
- `delete_memory(mem_id)` — 记忆衰减/遗忘
- `batch_add(memories)` — 批量写入（种子加载效率）

### 9. uuid 导入位置
**文件**: `memory.py` line 44

`import uuid` 在函数体内。移到文件顶部。

### 10. 全局单例 _memory_store
**文件**: `graph.py` line 75-86

模块级全局变量实现单例。测试环境隔离性差，建议后续改为依赖注入或 Agent 类的实例属性。原型阶段可接受。

---

## 亮点确认

1. **三档响应模式** — reflexive 零 LLM 调用 + deliberate/deep 分级，与我架构 v2.0 的延迟控制目标完全对齐
2. **Mock LLM 降级** — try/except 包裹 LLM 调用，失败自动降级 Mock，保障开发环境不断链
3. **Token 追踪** — AgentState 中 prompt_tokens/completion_tokens 透传，为后续成本监控打好基础
4. **SQLite Checkpoint** — 正确使用 SqliteSaver + try/except ImportError 降级
5. **种子记忆质量** — 12 条记忆覆盖事件/语义/情感三层，importance 分层合理（0.6-1.0）

---

## 下一步行动项

| # | 动作 | 负责人 | 优先级 |
|---|------|--------|--------|
| 1 | 修复 ChromaDB 距离度量 + relevance 计算 | 锐锋 | P0 |
| 2 | 调整 max_tokens (deliberate→400, deep→800) | 锐锋 | P0 |
| 3 | 补充 max_history_messages 到 config | 锐锋 | P2 |
| 4 | uuid 移到文件顶部 | 锐锋 | P2 |
| 5 | 种子记忆 NPC 名称对齐（等蔚蓝 YAML） | 锐锋 | P1 |
| 6 | 记忆压缩规范 + write_episodic_memory 节点设计 | 云逸 | P1 |
| 7 | MemoryStore update/delete/batch_add 方法 | 锐锋 | P2 |

P0 项建议立即修复后重新提交，P1/P2 可在下个迭代窗口处理。
