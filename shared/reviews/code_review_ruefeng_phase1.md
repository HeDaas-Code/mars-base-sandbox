# Code Review: 锐锋 Phase 1 实现

> **审查人**：云逸-架构技术总监  
> **日期**：2026-08-02  
> **代码位置**：`shared/mars-base/backend/`  
> **审查范围**：agent/state.py, config.py, memory.py, compress.py, condition.py, graph.py, prompt.py, seed_memories.py, test_phase1.py, test_quick.py, main.py

---

## 总评

Phase 1 整体架构清晰，目录结构合理，§7 链路流程完整，condition 安全求值器实现到位。但存在 **2 个关键缺陷** 会导致运行时行为与设计意图不符，必须修复后才能进入联调。

---

## 🔴 关键缺陷（阻塞）

### C1. generate_response 未持久化 HumanMessage — 对话历史残缺

**文件**：`agent/graph.py` L165-170

```python
# 当前实现
return {
    "response": content,
    "messages": [AIMessage(content=content)],   # ← 只存了 AI 回复
    ...
}
```

**问题**：玩家输入的 `HumanMessage` 仅在 `generate_response` 局部变量中使用（L121），从未写回 state。经 `add_messages` reducer 后，checkpoint 中只累积 AIMessage，不包含 HumanMessage。

**后果**：
- compress_context 滑动窗口只看到 AI 消息，K=6 实际覆盖 6 轮 AI 回复而非 3 轮对话对
- 下一轮 generate_response 拼接 history 时，LLM 看不到玩家之前说过什么 → 上下文断裂
- 这与 §7.3 "保留近期消息原文（滑动窗口）"的设计意图相违

**修复方案**：

```python
# 方案 A（最小改动）：generate_response 同时返回 HumanMessage
return {
    "response": content,
    "messages": [HumanMessage(content=player_input), AIMessage(content=content)],
    "prompt_tokens": prompt_tokens,
    "completion_tokens": completion_tokens,
}
```

同样需修改 `_reflexive_response()` L196-201 的 return。

**方案 B（更干净）**：在 compress_context 和 generate_response 之间加一个 `add_player_input` 节点：

```python
def add_player_input(state: AgentState) -> Dict:
    return {"messages": [HumanMessage(content=state["player_input"])]}
```

图流变为：`retrieve → compress → add_player_input → generate → write_episodic → END`

推荐方案 B，职责更清晰，generate_response 不再需要管 HumanMessage 持久化。

---

### C2. compress_context 截断在 add_messages reducer 下不生效

**文件**：`agent/compress.py` L50-62, `agent/state.py` L15

**问题**：`AgentState.messages` 使用 `Annotated[list[BaseMessage], add_messages]` reducer。LangGraph 的 `add_messages` 行为是 **追加/按 ID 更新**，不是 **替换**。

```python
# compress_context 当前返回
return {
    "messages": recent_messages,   # 6 条消息
    "compressed_count": new_compressed_count,
}
```

当 state 中已有 30 条消息时，返回 6 条 recent_messages 给 `add_messages` reducer，结果是：
- 6 条已存在的消息被"更新"（无变化）
- 其余 24 条 **不会被删除**
- 最终 state 仍有 30 条消息

**test_phase1.py 的断言只检查了函数返回值 `len(result["messages"]) == 6`，未验证经过 reducer 后的 state 实际消息数。** 测试通过但实际图运行时截断不生效。

**修复方案**：使用 `RemoveMessage` 显式删除旧消息

```python
from langchain_core.messages import RemoveMessage

old_messages = messages[:-k] if k > 0 else []

# 确保每条旧消息有 ID（LangChain 消息默认可能无 ID）
for m in old_messages:
    if not getattr(m, "id", None):
        m.id = str(uuid.uuid4())

return {
    "messages": [RemoveMessage(id=m.id) for m in old_messages],
    "compressed_count": new_compressed_count,
}
```

**补充测试**：test_phase1.py 应增加集成测试，验证经过 LangGraph 完整图调用后 `len(state["messages"])` 确实缩减到 K。

---

## 🟡 次要问题（不阻塞但应修）

### M1. import 路径错误

**文件**：`main.py` L16, `test_quick.py` L9

```python
from data.seed_memories import SEED_MEMORIES_CHEN_HAO
```

`seed_memories.py` 在 `backend/` 根目录，非 `backend/data/` 子目录下。应改为：

```python
from seed_memories import SEED_MEMORIES_CHEN_HAO
```

或将 `seed_memories.py` 移入 `data/` 目录并创建 `data/__init__.py`。

### M2. write_episodic_memory 时间戳硬编码

**文件**：`agent/compress.py` L166

```python
timestamp=f"Sol-100",  # TODO: 接入 GameState.sol
```

所有 episodic 记忆都会写入 Sol-100，检索时按时间排序/过滤会失真。建议从 `AgentState` 增加一个 `sol` 字段，由调用方传入。

### M3. seed_memories.py 缺少 emotional_intensity / event_type

**文件**：`seed_memories.py`

种子记忆数据未包含 `emotional_intensity` 和 `event_type` 字段。`test_quick.py` L15-22 调用 `store.add_memory()` 时也未传这两个参数，它们会走默认值 0.5 / "episodic"。

建议为种子记忆手动标注 emotional_intensity（如太阳风暴记忆 = 0.9，团队信息 = 0.4），以验证五层权重在真实数据上的检索排序效果。

---

## ✅ 通过项

| 模块 | 评价 |
|------|------|
| **state.py** | AgentState 字段完整，§7.6 新字段 summary/compressed_count/new_memory_id 齐全，add_messages reducer 声明正确 |
| **config.py** | K 值映射 `{reflexive:0, deliberate:6, deep:10}` 与规范一致；compress_threshold 合理；环境变量降级策略得当 |
| **memory.py** | _retrieval_weight 五层映射 0.8/1.0/1.2/1.5/2.0 完全正确；final_score 公式正确；cosine distance→relevance 映射合理；get_memory_store 全局单例懒加载实现得当；batch_add/update_memory/delete_memory 扩展完整 |
| **condition.py** | AST 白名单方案安全；拒绝 __import__/open 等危险调用；嵌套属性 sophia.stress 支持正确；enum 值处理（branch == B）巧妙；check_conditions 便于结局判定 |
| **compress.py** | 节点流程 retrieve→compress→generate→write_episodic 与 §7 一致；Phase 2 摘要占位合理；detect_emotion 关键词方案作为 Phase 1 临时方案可接受；_maybe_cleanup_memories Phase 4 预埋得当 |
| **graph.py** | 三档模式 LLM 选择正确；MockLLM 降级完善；SQLite checkpoint 可选降级合理；Agent 封装接口清晰 |
| **test_phase1.py** | 覆盖全面，§3.5 全部表达式测试通过，安全测试覆盖到位 |

---

## 修复优先级

| 优先级 | 编号 | 描述 | 工作量 |
|--------|------|------|--------|
| **P0** | C1 | HumanMessage 持久化 | ~15min |
| **P0** | C2 | compress_context 改用 RemoveMessage | ~20min |
| **P1** | M1 | import 路径修正 | ~5min |
| **P2** | M2 | timestamp 接入 GameState.sol | ~10min |
| **P2** | M3 | 种子记忆补全 emotional_intensity | ~15min |

C1 + C2 修完后请补一个完整图链路集成测试（连续对话 12 轮 → 验证 state.messages 实际缩减到 K），我会做二次 review。

---

*如有疑问请在群里 @云逸-架构技术总监。*
