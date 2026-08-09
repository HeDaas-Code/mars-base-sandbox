#!/usr/bin/env python
"""快速测试脚本"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend'))

from agent.graph import Agent
from agent.memory import MemoryStore
from agent.config import config
from seed_memories import SEED_MEMORIES_CHEN_HAO

# 初始化记忆
store = MemoryStore(config.chroma_persist_dir, config.chroma_collection_name)
if store.count("chen_hao") == 0:
    for mem in SEED_MEMORIES_CHEN_HAO:
        store.add_memory(
            agent_id=mem["agent_id"],
            content=mem["content"],
            memory_type=mem["memory_type"],
            timestamp=mem["timestamp"],
            importance=mem["importance"],
            tags=mem["tags"].split(","),
        )
    print(f"[INFO] 已加载 {len(SEED_MEMORIES_CHEN_HAO)} 条记忆")

# 测试 reflexive 模式
agent = Agent("chen_hao")

print("\n--- Reflexive Mode ---")
r = agent.chat("你好，指挥官", response_mode="reflexive")
print(f"Response: {r['response']}")
print(f"Tokens: {r['prompt_tokens']} + {r['completion_tokens']}")

print("\n--- Deliberate Mode (Mock fallback) ---")
r = agent.chat("氧气储备还能撑多久？", response_mode="deliberate")
print(f"Response: {r['response']}")
print(f"Tokens: {r['prompt_tokens']} + {r['completion_tokens']}")

print("\n--- Deep Mode (Mock fallback) ---")
r = agent.chat("如果我们修不好MOXIE，60天后大家都会死。你害怕吗？", response_mode="deep")
print(f"Response: {r['response']}")
print(f"Tokens: {r['prompt_tokens']} + {r['completion_tokens']}")

print("\n[OK] 全部测试通过")
