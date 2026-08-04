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

print("\n=== 全部 ws_adapter 测试通过 ===")
