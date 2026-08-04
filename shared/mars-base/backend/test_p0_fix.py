#!/usr/bin/env python
"""
P0 修复验证测试 - C1/C2 集成测试
验证：
  C1: generate_response 同时存 HumanMessage + AIMessage
  C2: compress_context 使用 RemoveMessage 正确删除旧消息
"""
import sys, os, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_core.messages import HumanMessage, AIMessage, RemoveMessage
from agent.compress import compress_context
from agent.graph import generate_response, _reflexive_response
from agent.state import AgentState
from agent.config import config


# === 清理 ChromaDB ===
if os.path.exists(config.chroma_persist_dir):
    shutil.rmtree(config.chroma_persist_dir)
import agent.memory as mem_module
mem_module._memory_store = None


print("=== C1: generate_response 存 HumanMessage + AIMessage ===\n")

# 模拟一轮 deliberate 模式
state = {
    "messages": [],
    "player_input": "氧气还能撑多久？",
    "retrieved_memories": "（无相关记忆）",
    "agent_id": "chen_hao",
    "game_state_context": "Sol-1, 氧气 78%",
    "response_mode": "deliberate",
}
result = generate_response(state)
msgs = result["messages"]
assert len(msgs) == 2, f"Expected 2 messages, got {len(msgs)}"
assert isinstance(msgs[0], HumanMessage), f"Expected HumanMessage, got {type(msgs[0])}"
assert isinstance(msgs[1], AIMessage), f"Expected AIMessage, got {type(msgs[1])}"
assert msgs[0].content == "氧气还能撑多久？"
print(f"✓ generate_response 返回 HumanMessage + AIMessage")
print(f"  Human: {msgs[0].content}")
print(f"  AI:    {msgs[1].content[:50]}...")

# reflexive 模式同样验证
state2 = {
    "messages": [],
    "player_input": "你好",
    "retrieved_memories": "",
    "agent_id": "chen_hao",
    "game_state_context": "",
    "response_mode": "reflexive",
}
result2 = _reflexive_response(state2)
msgs2 = result2["messages"]
assert len(msgs2) == 2
assert isinstance(msgs2[0], HumanMessage)
assert isinstance(msgs2[1], AIMessage)
print(f"✓ _reflexive_response 同样返回 HumanMessage + AIMessage")

print("\n=== C2: compress_context 使用 RemoveMessage ===\n")

# 构造 20 条带 id 的历史消息（模拟多轮对话）
msgs = []
for i in range(10):
    h = HumanMessage(content=f"player_msg_{i}")
    h.id = f"human_{i}"
    a = AIMessage(content=f"ai_reply_{i}")
    a.id = f"ai_{i}"
    msgs.extend([h, a])
# 共 20 条

# deliberate 模式：K=6, threshold=10
state3 = {
    "messages": msgs,
    "response_mode": "deliberate",
    "compressed_count": 0,
}
result3 = compress_context(state3)
result_msgs = result3["messages"]

# 应该返回 14 个 RemoveMessage（删除前 14 条），不是 6 条新消息
assert all(isinstance(m, RemoveMessage) for m in result_msgs), \
    f"Expected all RemoveMessage, got {[type(m).__name__ for m in result_msgs]}"
assert len(result_msgs) == 14, f"Expected 14 RemoveMessage, got {len(result_msgs)}"
assert result3["compressed_count"] == 14
print(f"✓ compress_context 返回 14 个 RemoveMessage（删除旧消息）")
print(f"✓ compressed_count = {result3['compressed_count']}")

# 验证 RemoveMessage 的 id 指向旧消息
removed_ids = [m.id for m in result_msgs]
assert "human_0" in removed_ids
assert "ai_0" in removed_ids
# 20 条消息：human_0, ai_0, human_1, ai_1, ..., human_9, ai_9
# 删除前 14 条（index 0-13），即 human_0..human_6, ai_0..ai_6
assert "human_6" in removed_ids
assert "ai_6" in removed_ids
# 最近 6 条（index 14-19）不应该在删除列表中
assert "human_7" not in removed_ids
assert "ai_9" not in removed_ids
print(f"✓ RemoveMessage 正确指向旧消息 id，保留最近 6 条")

# reflexive 不压缩
state4 = {
    "messages": msgs,
    "response_mode": "reflexive",
    "compressed_count": 0,
}
result4 = compress_context(state4)
assert result4["compressed_count"] == 0
assert "messages" not in result4 or len(result4.get("messages", [])) == 0
print(f"✓ reflexive 模式不压缩")

# 未超阈值不压缩
state5 = {
    "messages": msgs[:6],  # 只有 6 条，未超 threshold=10
    "response_mode": "deliberate",
    "compressed_count": 0,
}
result5 = compress_context(state5)
assert result5["compressed_count"] == 0
assert "messages" not in result5 or len(result5.get("messages", [])) == 0
print(f"✓ 未超阈值不压缩")

print("\n=== C1+C2 完整图链路测试 ===\n")

# 清空 ChromaDB 再次
if os.path.exists(config.chroma_persist_dir):
    shutil.rmtree(config.chroma_persist_dir)
mem_module._memory_store = None

# 模拟 add_messages reducer 行为
import uuid

def _ensure_id(msg):
    """LangGraph add_messages 会自动分配 id"""
    if not hasattr(msg, 'id') or msg.id is None:
        msg.id = str(uuid.uuid4())
    return msg

def simulate_add_messages(existing, new_msgs):
    """模拟 LangGraph add_messages reducer"""
    result = list(existing)
    for msg in new_msgs:
        if isinstance(msg, RemoveMessage):
            result = [m for m in result if m.id != msg.id]
        else:
            _ensure_id(msg)
            # 去重：同 id 替换
            result = [m for m in result if m.id != msg.id]
            result.append(msg)
    return result

# 模拟多轮对话
from agent.graph import build_agent_graph
# 不使用 checkpoint，纯内存模拟
conversation_history = []

for round_idx in range(8):
    player_input = f"第{round_idx+1}轮：氧气情况怎么样？"
    
    # generate_response
    state = {
        "messages": conversation_history,
        "player_input": player_input,
        "retrieved_memories": "",
        "agent_id": "chen_hao",
        "game_state_context": "Sol-1",
        "response_mode": "deliberate",
        "compressed_count": 0,
    }
    
    # 先 compress
    comp_result = compress_context(state)
    conversation_history = simulate_add_messages(conversation_history, comp_result.get("messages", []))
    compressed_count = comp_result["compressed_count"]
    
    # 再 generate
    state["messages"] = conversation_history
    gen_result = generate_response(state)
    conversation_history = simulate_add_messages(conversation_history, gen_result["messages"])
    
    # 检查 HumanMessage 是否被正确存储
    human_msgs = [m for m in conversation_history if isinstance(m, HumanMessage)]
    ai_msgs = [m for m in conversation_history if isinstance(m, AIMessage)]
    
    print(f"  Round {round_idx+1}: history={len(conversation_history)}, "
          f"human={len(human_msgs)}, ai={len(ai_msgs)}, "
          f"compressed={compressed_count}")

# 最终验证
assert len(human_msgs) == len(ai_msgs), "HumanMessage 和 AIMessage 数量应该相等"
print(f"\n✓ 8 轮对话后：HumanMessage({len(human_msgs)}) == AIMessage({len(ai_msgs)})")
print(f"✓ 对话历史总数 {len(conversation_history)} 条（压缩后应在 K=6 附近）")
assert len(conversation_history) <= 12, f"压缩后应 <= 12, got {len(conversation_history)}"
print(f"✓ 压缩生效，历史未无限增长")

print("\n=== 全部 P0 修复验证通过 ===")
