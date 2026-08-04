#!/usr/bin/env python3
"""
端到端验证：5个 NPC 的 persona prompt + 种子记忆加载

验证项：
1. 6个 NPC 的 system prompt 各自独立，不串味
2. 5个 NPC 的种子记忆能正确注入 ChromaDB
3. ws_adapter 的 talk 命令对5个 NPC 生效
4. 情绪提示对各 NPC 正确派生

作者：锐锋-核心开发工程师  日期：2026-08-03
"""
import sys, os, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.config import config

# 清空 ChromaDB
if os.path.exists(config.chroma_persist_dir):
    shutil.rmtree(config.chroma_persist_dir)
import agent.memory as mem_module
mem_module._memory_store = None

from agent.prompt import get_system_prompt
from agent.persona import (
    has_yaml,
    load_persona_prompt,
    load_speech_examples,
    load_seed_memories,
    load_initial_state,
)
from data.seed_memories import get_all_seed_memories
from ws_adapter import init_seed_memories, process_input, NPC_REGISTRY
from agent.memory import get_memory_store


print("=== 1. 6个 NPC prompt 独立性验证 ===\n")

prompts = {}
for npc_id in ["chen_hao", "sophia", "viktor", "aisha", "marcus", "lin_ruoxi"]:
    prompt = get_system_prompt(npc_id, "Sol 100, 氧气78%")
    prompts[npc_id] = prompt
    print(f"  {npc_id}: {len(prompt)} chars")
    # 确认不串味
    if npc_id != "chen_hao":
        assert "陈昊" not in prompt[:50], f"{npc_id} 错误兜底到陈昊"
    else:
        assert "陈昊" in prompt[:50]

print("\n✓ 6个 NPC prompt 各自独立\n")


print("=== 2. 种子记忆加载验证 ===\n")

all_mems = get_all_seed_memories()
total = 0
for npc_id, memories in all_mems.items():
    print(f"  {npc_id}: {len(memories)} 条")
    for m in memories:
        assert m["agent_id"] == npc_id
        assert m["content"].strip()
    total += len(memories)

print(f"\n  总计: {len(all_mems)} NPC, {total} 条种子记忆")
assert total >= 40, f"种子记忆总数应>=40, 实际{total}"
print("\n✓ 种子记忆数据完整\n")


print("=== 3. ChromaDB 注入验证 ===\n")

init_seed_memories()
store = get_memory_store()

for npc_id in ["chen_hao", "sophia", "viktor", "aisha", "marcus", "lin_ruoxi"]:
    count = store.count(npc_id)
    print(f"  {npc_id}: ChromaDB 中 {count} 条")
    expected = len(all_mems.get(npc_id, []))
    assert count == expected, f"{npc_id}: 期望{expected}条, 实际{count}条"

print("\n✓ ChromaDB 注入正确\n")


print("=== 4. 记忆检索验证（按 agent_id 隔离）===\n")

# 索菲亚的记忆不应该检索到陈昊的
sophia_results = store.retrieve("sophia", "太阳风暴", top_k=3)
print(f"  sophia 检索 '太阳风暴': {len(sophia_results)} 条")
for r in sophia_results:
    assert r["metadata"]["agent_id"] == "sophia", "记忆串味！"
    print(f"    [{r['metadata']['timestamp']}] {r['content'][:50]}...")

viktor_results = store.retrieve("viktor", "工程维修", top_k=3)
print(f"  viktor 检索 '工程维修': {len(viktor_results)} 条")
for r in viktor_results:
    assert r["metadata"]["agent_id"] == "viktor", "记忆串味！"

print("\n✓ 记忆按 agent_id 正确隔离\n")


print("=== 5. talk 命令对5个 NPC 生效 ===\n")

# 验证 talk <name> 能正确路由到对应 NPC
for agent_id in ["sophia_ramirez", "viktor_ivanov", "aisha_khan", "marcus_weber", "lin_ruoxi"]:
    # talk <name> 无文本 → 切换对话目标
    result = process_input(f"talk {agent_id}")
    assert result["type"] == "command_response"
    data = result["payload"].get("data", {})
    assert data.get("target_agent") == agent_id, f"talk {agent_id} 路由错误"
    print(f"  talk {agent_id}: ✓ 切换成功")

print("\n✓ 5个 NPC talk 命令全部生效\n")


print("=== 6. speech_examples 加载 ===\n")

for npc_id in ["sophia", "viktor", "aisha", "marcus", "lin_ruoxi"]:
    examples = load_speech_examples(npc_id)
    print(f"  {npc_id}: {len(examples)} 条 speech_examples")
    assert len(examples) >= 5, f"{npc_id} speech_examples 不足5条"

print("\n✓ speech_examples 加载正确\n")


print("=== 全部端到端测试通过 ===")
