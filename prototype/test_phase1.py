#!/usr/bin/env python
"""compress_context + write_episodic_memory + condition 集成测试"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.compress import compress_context, write_episodic_memory, detect_emotion
from agent.condition import evaluate_condition, check_conditions
from agent.memory import get_memory_store, _retrieval_weight
from agent.state import AgentState
from agent.config import config

print("=== 1. compress_context Phase 1 测试 ===\n")

# 测试 1: 未超阈值不压缩
state = {
    "messages": [],
    "response_mode": "deliberate",
    "compressed_count": 0,
}
result = compress_context(state)
assert result["compressed_count"] == 0
print("✓ 未超阈值不压缩")

# 测试 2: deliberate 超阈值截断为 K=6
from langchain_core.messages import HumanMessage, AIMessage
msgs = [HumanMessage(content=f"msg_{i}") for i in range(15)]
msgs += [AIMessage(content=f"reply_{i}") for i in range(15)]
state = {
    "messages": msgs,
    "response_mode": "deliberate",
    "compressed_count": 0,
}
result = compress_context(state)
assert len(result["messages"]) == 6, f"Expected 6, got {len(result['messages'])}"
assert result["compressed_count"] == 24
print(f"✓ deliberate 截断为 K=6, compressed_count=24")

# 测试 3: deep 超阈值截断为 K=10
state = {
    "messages": msgs,
    "response_mode": "deep",
    "compressed_count": 0,
}
result = compress_context(state)
assert len(result["messages"]) == 10
print(f"✓ deep 截断为 K=10")

# 测试 4: reflexive 不压缩
state = {
    "messages": msgs,
    "response_mode": "reflexive",
    "compressed_count": 0,
}
result = compress_context(state)
assert result["compressed_count"] == 0
print(f"✓ reflexive 不压缩")

print("\n=== 2. write_episodic_memory 测试 ===\n")

# 清空 ChromaDB
import shutil
if os.path.exists(config.chroma_persist_dir):
    shutil.rmtree(config.chroma_persist_dir)

# 重置全局 store
import agent.memory as mem_module
mem_module._memory_store = None

state = {
    "player_input": "氧气还能撑多久？",
    "response": "氧气储备还在下降。大约还有60个Sol。",
    "agent_id": "chen_hao",
    "response_mode": "deliberate",
}
result = write_episodic_memory(state)
assert "new_memory_id" in result
assert result["new_memory_id"]
print(f"✓ episodic 记忆已写入: {result['new_memory_id']}")

# 验证记忆确实写入了
store = get_memory_store()
all_mems = store.get_all_memories("chen_hao")
assert len(all_mems) == 1
mem = all_mems[0]
assert mem["metadata"]["memory_type"] == "episodic"
assert mem["metadata"]["importance"] == 0.5  # deliberate
print(f"✓ 记忆 metadata 正确: importance={mem['metadata']['importance']}, "
      f"ei={mem['metadata']['emotional_intensity']}, "
      f"event_type={mem['metadata']['event_type']}")

print("\n=== 3. emotional_intensity 检索权重测试 ===\n")

# 测试 retrieval_weight
assert _retrieval_weight(0.1) == 0.8
assert _retrieval_weight(0.3) == 1.0
assert _retrieval_weight(0.5) == 1.2
assert _retrieval_weight(0.7) == 1.5
assert _retrieval_weight(0.9) == 2.0
print("✓ retrieval_weight 五层映射正确")

print("\n=== 4. condition 表达式安全求值器测试 ===\n")

ctx = {
    "sol": 35,
    "sophia": {"stress": 0.8},
    "branch": "A",
    "all_crew_alive": True,
    "morale_avg": 0.5,
    "player_connected": True,
    "stress": 0.6,
}

# 蔚蓝 §3.5 全部表达式
assert evaluate_condition("sol >= 30 and sophia.stress >= 0.7 and player_connected == true", ctx)
assert evaluate_condition("branch == B and sol >= 140 and greenhouse_stage >= 3", {**ctx, "branch": "B", "greenhouse_stage": 3, "sol": 140})
assert evaluate_condition("sophia.stress >= 0.7", ctx)  # 0.8 >= 0.7
assert evaluate_condition("stress < 0.5 and morale > 0.5", {"stress": 0.3, "morale": 0.6})
assert evaluate_condition("stress >= 0.5 and stress <= 0.7", ctx)  # 区间语义
assert evaluate_condition("sol >= 200 and strategy in [alpha, beta, gamma]", {"sol": 200, "strategy": "alpha"})
assert evaluate_condition("all_crew_alive == true and morale_avg >= 0.4", ctx)
assert evaluate_condition("athena.consciousness_flag == awakening", {"athena": {"consciousness_flag": "awakening"}})
assert evaluate_condition("morale_avg < 0.3 or marcus.crisis_triggered == true", {"morale_avg": 0.2, "marcus": {"crisis_triggered": True}})
print("✓ 蔚蓝 §3.5 全部表达式通过")

# ending_determination 测试
conditions = [
    "all_crew_alive == true and morale_avg >= 0.4",
    "all_crew_alive == false and morale_avg >= 0.3",
    "sol >= 200",
]
idx = check_conditions(conditions, ctx)
assert idx == 0
print("✓ ending_check 第一个条件命中")

# 安全测试
try:
    evaluate_condition("__import__('os').system('rm -rf /')", ctx)
    assert False, "Should have raised"
except (ValueError, SyntaxError):
    pass

try:
    evaluate_condition("open('file').read()", ctx)
    assert False, "Should have raised"
except (ValueError, SyntaxError):
    pass
print("✓ 安全检查：拒绝函数调用和属性方法")

print("\n=== 全部测试通过 ===")
