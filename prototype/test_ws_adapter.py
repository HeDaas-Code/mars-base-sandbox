#!/usr/bin/env python
"""ws_adapter 集成测试 - 验证命令路由 + agent_message 格式 + context_summary"""
import sys, os, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.config import config

# 清理 ChromaDB
if os.path.exists(config.chroma_persist_dir):
    shutil.rmtree(config.chroma_persist_dir)
import agent.memory as mem_module
mem_module._memory_store = None

from ws_adapter import process_input, build_agent_message, build_context_summary


print("=== 1. ls 命令 ===\n")
result = process_input("ls")
assert result["type"] == "command_response"
segments = result["payload"]["output_segments"]
assert len(segments) == 6  # 6 个 NPC
assert segments[0]["tag"] == "command_response"
data = result["payload"]["data"]
assert len(data["entries"]) == 6
assert data["entries"][0]["agent_id"] == "chen_hao"
print(f"✓ ls 返回 6 个 NPC 条目")
print(f"  首条: {segments[0]['text'].strip()}")

print("\n=== 2. status 命令 ===\n")
result = process_input("status")
assert result["type"] == "command_response"
segments = result["payload"]["output_segments"]
assert "赫拉克勒斯" in segments[0]["text"]
data = result["payload"]["data"]
assert data["sol"] == 1
assert "oxygen" in data["resources"]
print(f"✓ status 返回基地状态")
print(f"  Sol {data['sol']}, 氧气 {data['resources']['oxygen']['current']}%")

print("\n=== 3. help 命令 ===\n")
result = process_input("help")
assert result["type"] == "command_response"
segments = result["payload"]["output_segments"]
assert any("ls" in s["text"] for s in segments)
print(f"✓ help 返回可用指令列表")

print("\n=== 4. talk chen_hao（无文本）===\n")
result = process_input("talk chen_hao")
assert result["type"] == "command_response"
assert "陈昊" in result["payload"]["output_segments"][0]["text"]
print(f"✓ talk chen_hao 返回切换确认")

print("\n=== 5. talk chen_hao 你好（自然语言）===\n")
result = process_input("talk chen_hao 你好")
assert result["type"] == "agent_message"
payload = result["payload"]
assert payload["sender_id"] == "chen_hao"
assert payload["sender_label"] == "CMDR"
assert len(payload["segments"]) >= 2
assert payload["segments"][0]["tag"] == "speaker_label"
assert payload["segments"][0]["protected"] == True
assert payload["latency_ms"] >= 0
assert payload["emotion_hint"] is not None
assert "stress" in payload["emotion_hint"]
assert "morale" in payload["emotion_hint"]
# Phase 2: emotion_hint 应包含 emotion_label（人类 NPC）
assert "emotion_label" in payload["emotion_hint"], f"emotion_label missing: {payload['emotion_hint']}"
print(f"✓ talk chen_hao 你好 → agent_message")
print(f"  segments: {[s['text'] for s in payload['segments']]}")
print(f"  latency_ms: {payload['latency_ms']}")
print(f"  emotion: {payload['emotion_hint']}")

print("\n=== 6. context_summary ===\n")
assert "context_summary" in result["payload"]
cs = result["payload"]["context_summary"]
assert "history_count" in cs
assert "k_limit" in cs
assert "compressed_count" in cs
assert "mode" in cs
assert cs["k_limit"] == 6  # deliberate 模式
assert cs["mode"] == "deliberate"
print(f"✓ context_summary: {cs}")

print("\n=== 7. 直接自然语言（无 talk 前缀）===\n")
result = process_input("氧气还能撑多久？")
assert result["type"] == "agent_message"
assert result["payload"]["sender_id"] == "chen_hao"
print(f"✓ 自然语言直接走 agent_message")

print("\n=== 8. 未知输入（走自然语言）===\n")
result = process_input("foobar")
assert result["type"] == "agent_message"
print(f"✓ 未知输入走自然语言通道 → agent_message")

print("\n=== 9. build_agent_message 单元测试 ===\n")
msg = build_agent_message(
    agent_id="chen_hao",
    response_text="测试回复",
    latency_ms=500,
    emotion_hint={"stress": 0.4, "morale": 0.6},
    signal_quality_pct=75,
)
assert msg["type"] == "agent_message"
assert msg["payload"]["sender_id"] == "chen_hao"
assert msg["payload"]["sender_label"] == "CMDR"
assert msg["payload"]["signal_quality_pct"] == 75
assert msg["payload"]["latency_ms"] == 500
assert msg["payload"]["segments"][0]["text"] == "[CMDR]> "
assert msg["payload"]["segments"][1]["text"] == "测试回复"
print(f"✓ build_agent_message 格式正确")

print("\n=== 10. build_context_summary 单元测试 ===\n")
cs = build_context_summary(history_count=12, response_mode="deliberate", compressed_count=4)
assert cs == {"history_count": 12, "k_limit": 6, "compressed_count": 4, "mode": "deliberate"}
cs2 = build_context_summary(history_count=15, response_mode="deep", compressed_count=8)
assert cs2["k_limit"] == 10
assert cs2["mode"] == "deep"
print(f"✓ build_context_summary deliberate: {cs}")
print(f"✓ build_context_summary deep: {cs2}")

# ============================================================
# Phase 2: emotion_hint 集成测试（emotion_label / ai_status）
# ============================================================

print("\n=== 11. emotion_label 派生验证（人类 NPC）===\n")
from ws_adapter import get_game_state, AGENT_TO_NPC_ID
from agent.game_state import build_emotion_hint, derive_emotion_label, AI_SENDERS

gs = get_game_state()
# chen_hao 初始 stress=0.3, morale=0.6 → label 应为 "focused"
hint = build_emotion_hint(gs, "chen_hao")
assert "emotion_label" in hint, f"emotion_label missing: {hint}"
assert hint["emotion_label"] == derive_emotion_label(hint["stress"], hint["morale"])
print(f"✓ chen_hao emotion_hint: {hint}")
print(f"  label={hint['emotion_label']} (stress={hint['stress']:.2f} morale={hint['morale']:.2f})")

# 验证 25 标签表覆盖
labels_seen = set()
for npc_id in gs.npc_states:
    ns = gs.npc_states[npc_id]
    label = derive_emotion_label(ns.stress, ns.morale)
    labels_seen.add(label)
    hint_n = build_emotion_hint(gs, npc_id)
    assert hint_n["emotion_label"] == label
    print(f"  {npc_id}: stress={ns.stress:.2f} morale={ns.morale:.2f} → {label}")
print(f"✓ 6 NPC 初始状态共覆盖 {len(labels_seen)} 种 emotion_label")

print("\n=== 12. ai_status 派生验证（AI sender）===\n")
# athena
hint_athena = build_emotion_hint(gs, "athena")
assert "ai_status" in hint_athena, f"ai_status missing: {hint_athena}"
assert hint_athena["ai_status"] == gs.athena_status
assert "emotion_label" not in hint_athena
print(f"✓ athena emotion_hint: {hint_athena}")
# courier
hint_courier = build_emotion_hint(gs, "courier")
assert "ai_status" in hint_courier
assert hint_courier["ai_status"] == "normal"
print(f"✓ courier emotion_hint: {hint_courier}")

print("\n=== 13. 不同 NPC 的 emotion_hint 各异 ===\n")
# 各 NPC 初始 stress/morale 不同，emotion_label 应有差异
# chen_hao: stress=0.3 morale=0.6 → focused
# viktor:   stress=0.5 morale=0.5 → alert
# aisha:    stress=0.45 morale=0.55 → alert (与 viktor 同 label 但数值不同)
hint_chen = build_emotion_hint(gs, "chen_hao")
hint_viktor = build_emotion_hint(gs, "viktor")
assert hint_chen["emotion_label"] != hint_viktor["emotion_label"] or \
       hint_chen["stress"] != hint_viktor["stress"], \
       "chen_hao and viktor should differ"
print(f"✓ chen_hao vs viktor:")
print(f"  chen_hao: {hint_chen}")
print(f"  viktor:   {hint_viktor}")

print("\n=== 全部 ws_adapter 测试通过 ===")
