#!/usr/bin/env python
"""
WebSocket 联调验证脚本 v1.0
================================
启动 ws_server.py 后运行此脚本，模拟前端客户端发送各类型消息，
验证后端返回格式是否符合 v1.1 协议规范。

用法：
  # 终端 1: 启动服务器
  cd backend
  python3 ws_server.py

  # 终端 2: 运行验证脚本
  cd backend
  python3 ../tests/test_integration.py
"""

import asyncio
import json
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend'))

try:
    import websockets
except ImportError:
    print("[FATAL] 需要安装 websockets: pip install websockets")
    sys.exit(1)

# ============================================================
# 测试配置
# ============================================================

WS_URL = "ws://localhost:8000/ws"
TIMEOUT = 30  # 单次操作超时（秒）


# ============================================================
# 测试客户端
# ============================================================

class TestClient:
    """模拟前端 WebSocket 客户端"""

    def __init__(self, url: str = WS_URL):
        self.url = url
        self.ws = None
        self.session_id = None
        self.received_messages = []

    async def connect(self):
        """建立连接"""
        print(f"[连接] {self.url} ...")
        self.ws = await asyncio.wait_for(
            websockets.connect(self.url),
            timeout=TIMEOUT,
        )
        print("[连接] 成功")

    async def send(self, msg: dict) -> dict:
        """发送消息并等待响应"""
        msg_json = json.dumps(msg, ensure_ascii=False)
        await self.ws.send(msg_json)
        # 等待响应
        raw = await asyncio.wait_for(self.ws.recv(), timeout=TIMEOUT)
        response = json.loads(raw)
        self.received_messages.append(response)
        return response

    async def send_hello(self) -> dict:
        """发送 hello"""
        msg = {
            "msg_id": f"test-hello-{int(time.time()*1000)}",
            "type": "hello",
            "ts_tick": 0,
            "payload": {
                "token": "test-token-001",
                "client_version": "0.1.0",
                "last_session_id": None,
            },
        }
        return await self.send(msg)

    async def send_player_input(self, text: str, target_agent_id: str = None) -> dict:
        """发送 player_input"""
        payload = {"text": text}
        if target_agent_id:
            payload["target_agent_id"] = target_agent_id
        msg = {
            "msg_id": f"test-pi-{int(time.time()*1000)}",
            "type": "player_input",
            "ts_tick": 0,
            "payload": payload,
        }
        return await self.send(msg)

    async def send_command(self, raw: str, args: list = None) -> dict:
        """发送 command"""
        msg = {
            "msg_id": f"test-cmd-{int(time.time()*1000)}",
            "type": "command",
            "ts_tick": 0,
            "payload": {"raw": raw, "args": args or []},
        }
        return await self.send(msg)

    async def send_ping(self) -> dict:
        """发送 ping"""
        msg = {
            "msg_id": f"test-ping-{int(time.time()*1000)}",
            "type": "ping",
            "ts_tick": 0,
            "payload": {},
        }
        return await self.send(msg)

    async def close(self):
        """关闭连接"""
        if self.ws:
            await self.ws.close()
            print("[连接] 已关闭")


# ============================================================
# 断言工具
# ============================================================

def assert_eq(actual, expected, label: str):
    """相等断言"""
    if actual != expected:
        raise AssertionError(f"[FAIL] {label}: 期望 {expected!r}, 实际 {actual!r}")
    print(f"  [PASS] {label}")

def assert_in(item, container, label: str):
    """包含断言"""
    if item not in container:
        raise AssertionError(f"[FAIL] {label}: {item!r} 不在 {container!r} 中")
    print(f"  [PASS] {label}")

def assert_true(condition, label: str):
    """真值断言"""
    if not condition:
        raise AssertionError(f"[FAIL] {label}")
    print(f"  [PASS] {label}")

def assert_key(d: dict, key: str, label: str):
    """键存在断言"""
    if key not in d:
        raise AssertionError(f"[FAIL] {label}: 键 {key!r} 不存在")
    print(f"  [PASS] {label}")


# ============================================================
# 测试用例
# ============================================================

async def test_01_hello_and_session_init(client: TestClient):
    """测试 1: hello → session_init"""
    print("\n=== 测试 1: hello → session_init ===")

    resp = await client.send_hello()

    assert_eq(resp["type"], "session_init", "消息类型")
    assert_key(resp, "msg_id", "msg_id 存在")
    assert_key(resp, "ts_tick", "ts_tick 存在")
    assert_key(resp, "payload", "payload 存在")

    payload = resp["payload"]
    assert_key(payload, "session_id", "session_id 存在")
    assert_key(payload, "resume_mode", "resume_mode 存在")
    assert_key(payload, "player_state", "player_state 存在")
    assert_key(payload, "world_snapshot", "world_snapshot 存在")
    assert_key(payload, "signal_quality_pct", "signal_quality_pct 存在")

    # 保存 session_id
    client.session_id = payload["session_id"]
    print(f"  session_id: {client.session_id}")

    # 验证 world_snapshot 结构
    ws = payload["world_snapshot"]
    assert_key(ws, "sol", "world_snapshot.sol")
    assert_key(ws, "mars_time", "world_snapshot.mars_time")
    assert_key(ws, "base", "world_snapshot.base")
    assert_key(ws, "agents", "world_snapshot.agents")

    # 验证 agents 列表
    agents = ws["agents"]
    assert_true(len(agents) == 6, f"agents 列表含 6 个 NPC (实际 {len(agents)})")

    # 每个 agent 应有 stress/morale
    for a in agents:
        assert_key(a, "agent_id", f"agent {a.get('agent_id')} agent_id")
        assert_key(a, "stress", f"agent {a.get('agent_id')} stress")
        assert_key(a, "morale", f"agent {a.get('agent_id')} morale")
        assert_key(a, "label", f"agent {a.get('agent_id')} label")

    # 验证 signal_quality_pct
    sq = payload["signal_quality_pct"]
    assert_true(isinstance(sq, int) and 0 <= sq <= 100, f"signal_quality_pct 是 0-100 整数 (实际 {sq})")
    print(f"  signal_quality_pct: {sq}")


async def test_02_ping_pong(client: TestClient):
    """测试 2: ping → pong"""
    print("\n=== 测试 2: ping → pong ===")

    resp = await client.send_ping()
    assert_eq(resp["type"], "pong", "消息类型")
    assert_key(resp, "msg_id", "msg_id 存在")
    print(f"  pong msg_id: {resp['msg_id']}")


async def test_03_command_ls(client: TestClient):
    """测试 3: command ls → command_response"""
    print("\n=== 测试 3: command ls → command_response ===")

    resp = await client.send_command("ls")
    assert_eq(resp["type"], "command_response", "消息类型")
    assert_key(resp, "msg_id", "msg_id 存在")
    assert_key(resp, "payload", "payload 存在")

    payload = resp["payload"]
    assert_key(payload, "output_segments", "output_segments 存在")

    segments = payload["output_segments"]
    assert_true(len(segments) == 6, f"segments 含 6 行 (实际 {len(segments)})")

    # 验证每行格式
    for seg in segments:
        assert_key(seg, "text", "segment.text 存在")
        assert_key(seg, "tag", "segment.tag 存在")
        assert_eq(seg["tag"], "command_response", "segment.tag 值")

    # data 字段
    data = payload.get("data")
    assert_true(data is not None, "data 非空")
    assert_key(data, "entries", "data.entries 存在")
    assert_true(len(data["entries"]) == 6, f"data.entries 含 6 条 (实际 {len(data['entries'])})")

    print(f"  ls 返回 6 个 NPC 条目 ✓")


async def test_04_command_status(client: TestClient):
    """测试 4: command status → command_response"""
    print("\n=== 测试 4: command status → command_response ===")

    resp = await client.send_command("status")
    assert_eq(resp["type"], "command_response", "消息类型")

    payload = resp["payload"]
    segments = payload["output_segments"]
    assert_true(len(segments) > 0, "segments 非空")

    # 首行应含 "赫拉克勒斯"
    first_text = segments[0]["text"]
    assert_in("赫拉克勒斯", first_text, "首行含基地名")

    # data 字段
    data = payload["data"]
    assert_key(data, "sol", "data.sol 存在")
    assert_key(data, "resources", "data.resources 存在")
    assert_key(data["resources"], "oxygen", "data.resources.oxygen 存在")

    print(f"  Sol {data['sol']}, 氧气 {data['resources']['oxygen']['current']}%")


async def test_05_command_help(client: TestClient):
    """测试 5: command help → command_response"""
    print("\n=== 测试 5: command help ===")

    resp = await client.send_command("help")
    assert_eq(resp["type"], "command_response", "消息类型")

    segments = resp["payload"]["output_segments"]
    assert_true(len(segments) > 0, "segments 非空")

    # 验证含 "ls" 指令说明
    all_text = "".join(s["text"] for s in segments)
    assert_in("ls", all_text, "help 含 ls 说明")
    assert_in("talk", all_text, "help 含 talk 说明")


async def test_06_command_talk_switch(client: TestClient):
    """测试 6: command talk chen_hao（无文本）→ 切换确认"""
    print("\n=== 测试 6: command talk chen_hao（切换目标）===")

    resp = await client.send_command("talk", ["chen_hao"])
    assert_eq(resp["type"], "command_response", "消息类型")

    segments = resp["payload"]["output_segments"]
    all_text = "".join(s["text"] for s in segments)
    assert_in("陈昊", all_text, "返回 NPC 名称")
    assert_in("CMDR", all_text, "返回 NPC 标签")

    data = resp["payload"].get("data") or {}
    assert_eq(data.get("target_agent"), "chen_hao", "target_agent 字段")
    print(f"  已切换到 chen_hao [CMDR]")


async def test_07_player_input_natural_language(client: TestClient):
    """测试 7: player_input 自然语言 → agent_message"""
    print("\n=== 测试 7: player_input 自然语言 → agent_message ===")

    resp = await client.send_player_input(
        "氧气还能撑多久？",
        target_agent_id="chen_hao",
    )
    assert_eq(resp["type"], "agent_message", "消息类型")
    assert_key(resp, "msg_id", "msg_id 存在")
    assert_key(resp, "ts_tick", "ts_tick 存在")

    payload = resp["payload"]
    assert_key(payload, "sender_id", "sender_id 存在")
    assert_key(payload, "sender_label", "sender_label 存在")
    assert_key(payload, "segments", "segments 存在")
    assert_key(payload, "signal_quality_pct", "signal_quality_pct 存在")
    assert_key(payload, "latency_ms", "latency_ms 存在")
    assert_key(payload, "emotion_hint", "emotion_hint 存在")

    # sender_id 应为 chen_hao
    assert_eq(payload["sender_id"], "chen_hao", "sender_id 值")
    assert_eq(payload["sender_label"], "CMDR", "sender_label 值")

    # segments 结构验证
    segments = payload["segments"]
    assert_true(len(segments) >= 2, f"segments 至少 2 段 (实际 {len(segments)})")
    assert_eq(segments[0]["tag"], "speaker_label", "首段 tag 是 speaker_label")
    assert_eq(segments[0]["text"], "[CMDR]> ", "首段 text 是 [CMDR]> ")

    # latency_ms 应为正整数
    latency = payload["latency_ms"]
    assert_true(isinstance(latency, int) and latency > 0, f"latency_ms 正整数 (实际 {latency})")

    # emotion_hint 应含 stress/morale/emotion_label（人类 NPC）
    eh = payload["emotion_hint"]
    assert_key(eh, "stress", "emotion_hint.stress")
    assert_key(eh, "morale", "emotion_hint.morale")
    assert_key(eh, "emotion_label", "emotion_hint.emotion_label")

    # signal_quality_pct 是 0-100 整数
    sq = payload["signal_quality_pct"]
    assert_true(isinstance(sq, int) and 0 <= sq <= 100, f"signal_quality_pct 0-100 整数 (实际 {sq})")

    # context_summary
    assert_key(payload, "context_summary", "context_summary 存在")
    cs = payload["context_summary"]
    assert_key(cs, "history_count", "context_summary.history_count")
    assert_key(cs, "k_limit", "context_summary.k_limit")
    assert_key(cs, "compressed_count", "context_summary.compressed_count")
    assert_key(cs, "mode", "context_summary.mode")

    print(f"  回复: {segments[1]['text'][:60]}...")
    print(f"  latency={latency}ms, signal={sq}%")
    print(f"  emotion: {eh}")
    print(f"  context_summary: {cs}")


async def test_08_command_talk_with_text(client: TestClient):
    """测试 8: command talk chen_hao <text> → agent_message"""
    print("\n=== 测试 8: command talk chen_hao <text> → agent_message ===")

    resp = await client.send_command("talk", ["chen_hao", "基地现在情况怎么样？"])
    assert_eq(resp["type"], "agent_message", "消息类型")

    payload = resp["payload"]
    assert_eq(payload["sender_id"], "chen_hao", "sender_id")
    assert_eq(payload["sender_label"], "CMDR", "sender_label")

    segments = payload["segments"]
    assert_true(len(segments) >= 2, "segments 至少 2 段")

    print(f"  回复: {segments[1]['text'][:60]}...")


async def test_09_emotion_hint_variety(client: TestClient):
    """测试 9: 不同 NPC 的 emotion_hint 应有差异"""
    print("\n=== 测试 9: 不同 NPC emotion_hint 差异 ===")

    # 先 talk sophia
    await client.send_command("talk", ["sophia_ramirez"])
    resp_sophia = await client.send_player_input("你好")
    assert_eq(resp_sophia["type"], "agent_message", "sophia 响应类型")

    eh_sophia = resp_sophia["payload"]["emotion_hint"]
    print(f"  sophia: {eh_sophia}")

    # 切换到 viktor
    await client.send_command("talk", ["viktor_ivanov"])
    resp_viktor = await client.send_player_input("电力系统如何？")
    assert_eq(resp_viktor["type"], "agent_message", "viktor 响应类型")

    eh_viktor = resp_viktor["payload"]["emotion_hint"]
    print(f"  viktor: {eh_viktor}")

    # 两者 emotion_label 或 stress/morale 应有差异
    assert_true(
        eh_sophia.get("emotion_label") != eh_viktor.get("emotion_label")
        or eh_sophia.get("stress") != eh_viktor.get("stress"),
        "sophia 与 viktor emotion_hint 有差异",
    )


async def test_10_empty_input_error(client: TestClient):
    """测试 10: 空输入 → error"""
    print("\n=== 测试 10: 空输入 → error ===")

    resp = await client.send_player_input("", target_agent_id="chen_hao")
    assert_eq(resp["type"], "error", "消息类型")
    assert_key(resp, "payload", "payload 存在")
    assert_key(resp["payload"], "code", "error code 存在")
    print(f"  error code: {resp['payload']['code']}")


async def test_11_unknown_command(client: TestClient):
    """测试 11: 未知命令"""
    print("\n=== 测试 11: 未知命令 ===")

    resp = await client.send_command("foobarxyz", [])
    # 未知命令会被 process_input 当作自然语言处理 → agent_message
    # 或者返回 command_response not found
    # 两种都可以接受
    assert_true(
        resp["type"] in ("command_response", "agent_message"),
        f"响应类型合理 (实际 {resp['type']})",
    )
    print(f"  响应类型: {resp['type']}")


async def test_12_conversation_continuity(client: TestClient):
    """测试 12: 多轮对话连续性（context_summary.history_count 应递增）"""
    print("\n=== 测试 12: 多轮对话连续性 ===")

    # 切换到 chen_hao
    await client.send_command("talk", ["chen_hao"])

    # 第一轮
    resp1 = await client.send_player_input("氧气还能撑多久？")
    cs1 = resp1["payload"].get("context_summary", {})
    h1 = cs1.get("history_count", 0)
    print(f"  第1轮 history_count={h1}")

    # 第二轮
    resp2 = await client.send_player_input("通信能修好吗？")
    cs2 = resp2["payload"].get("context_summary", {})
    h2 = cs2.get("history_count", 0)
    print(f"  第2轮 history_count={h2}")

    # history_count 应该递增（或至少不减少）
    assert_true(
        h2 >= h1,
        f"history_count 递增或不减 (h1={h1}, h2={h2})",
    )


async def test_13_latency_formula(client: TestClient):
    """测试 13: latency_ms 公式验证（§8.3: 500 + (100 - signal_quality) * 50）"""
    print("\n=== 测试 13: latency_ms 公式验证 ===")

    resp = await client.send_player_input("你好", target_agent_id="chen_hao")
    payload = resp["payload"]
    sq = payload["signal_quality_pct"]
    latency = payload["latency_ms"]
    expected = 500 + (100 - sq) * 50

    assert_eq(latency, expected, f"latency_ms = 500 + (100 - {sq}) * 50 = {expected}")
    print(f"  signal={sq}%, latency={latency}ms, 公式验证通过 ✓")


# ============================================================
# 主流程
# ============================================================

async def main():
    print("=" * 60)
    print("WebSocket 联调验证脚本 v1.0")
    print(f"目标: {WS_URL}")
    print("=" * 60)

    client = TestClient()

    try:
        await client.connect()

        # 依次执行测试
        await test_01_hello_and_session_init(client)
        await test_02_ping_pong(client)
        await test_03_command_ls(client)
        await test_04_command_status(client)
        await test_05_command_help(client)
        await test_06_command_talk_switch(client)
        await test_07_player_input_natural_language(client)
        await test_08_command_talk_with_text(client)
        await test_09_emotion_hint_variety(client)
        await test_10_empty_input_error(client)
        await test_11_unknown_command(client)
        await test_12_conversation_continuity(client)
        await test_13_latency_formula(client)

        # 汇总
        print("\n" + "=" * 60)
        print(f"全部 13 项联调测试通过 ✓")
        print(f"共收到 {len(client.received_messages)} 条响应消息")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
