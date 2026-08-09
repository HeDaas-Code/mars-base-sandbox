#!/usr/bin/env python
"""
WebSocket 联调服务器 v1.0
================================
桥接前端 WebSocket 客户端与后端 Agent 链路。

协议：云逸《WebSocket 接口定义 v1.1》
- 监听 ws://localhost:8000/ws
- 处理 C→S 消息：hello / player_input / command / ping / resume / ack
- 返回 S→C 消息：session_init / agent_message / command_response / pong / error

依赖：
  pip install websockets
  后端模块：ws_adapter_v2.process_input()

启动：
  cd backend
  python3 ws_server.py [--port 8000] [--host 0.0.0.0]
"""

import asyncio
import http
import json
import logging
import time
import uuid
import argparse
import os
import sys
from typing import Dict, Set, Optional

# 确保能 import 后端模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import websockets
    from websockets.asyncio.server import serve
except ImportError:
    print("[FATAL] websockets 库未安装。请运行: pip install websockets")
    sys.exit(1)

# 从 ws_adapter_v2 导入（root 权限问题导致 ws_adapter.py 无法覆盖，v2 为正式版本）
from ws_adapter_v2 import (
    process_input,
    process_player_turn,
    handle_option_select,
    NPC_REGISTRY,
    get_game_state,
    AGENT_TO_NPC_ID,
    get_theme_meta_if_available,
    set_engine_core,
)
from agent.game_state import (
    create_initial_game_state,
    build_emotion_hint,
    AI_SENDERS,
)
from agent.protocol import (
    gen_msg_id as _proto_gen_msg_id,
    now_ts as _proto_now_ts,
    build_session_init as _proto_build_session_init,
    build_error as _proto_build_error,
    build_pong as _proto_build_pong,
    build_ack as _proto_build_ack,
)

# ============================================================
# 日志配置
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ws_server")

# ============================================================
# 会话管理
# ============================================================

class ClientSession:
    """单个 WebSocket 客户端的会话状态"""

    def __init__(self, websocket):
        self.ws = websocket
        self.session_id: str = f"sess-{uuid.uuid4().hex[:12]}"
        self.player_id: Optional[str] = None
        self.player_name: Optional[str] = None
        self.last_msg_id: Optional[str] = None
        self.connected_at: float = time.time()
        # 默认响应模式
        self.response_mode: str = "deliberate"
        # 当前对话目标（talk <name> 切换后的默认目标）
        self.current_target: str = "chen_hao"


# ============================================================
# 消息构造工具（委托 protocol.py 统一信封中心）
# ============================================================

def _gen_msg_id() -> str:
    return _proto_gen_msg_id()


def _now_ts() -> int:
    return _proto_now_ts()


def build_session_init(session: ClientSession) -> Dict:
    """构造 session_init 消息（v1.1 §3.2）

    前端收到后会初始化世界状态、CrewPanel、MemoryLoadIndicator 等。

    Phase 3 引擎化：若 EngineCore 已注入，则 world_snapshot.theme 包含主题元信息，
    前端可据此动态渲染 UI（资源条标签、状态字段、命令列表等）。
    """
    gs = get_game_state()

    # 构造 agents 列表（前端 CrewPanel 需要）
    agents_list = []
    for npc_id, npc in NPC_REGISTRY.items():
        # 从 GameState 获取 stress/morale
        gs_npc_id = AGENT_TO_NPC_ID.get(npc_id, npc_id)
        npc_state = gs.npc_states.get(gs_npc_id)
        stress = npc_state.stress if npc_state else 0.0
        morale = npc_state.morale if npc_state else 1.0
        agents_list.append({
            "agent_id": npc["agent_id"],
            "label": npc["label"],
            "name": npc["name"],
            "location": npc["location"],
            "health": 1.0,
            "stress": round(stress, 2),
            "morale": round(morale, 2),
            "current_task": "待命",
        })

    # 构造资源字典（从 GameState 动态取值，而非硬编码）
    resources = {}
    for res_name in ("oxygen", "power", "water", "food"):
        res = gs.resources.get(res_name)
        if isinstance(res, dict):
            resources[res_name] = {
                "current": res.get("current", 0),
                "max": res.get("max", 100),
                "rate": res.get("rate", 0),
            }

    # 主题元信息（Phase 3 引擎化：若 EngineCore 已注入则提供）
    theme_meta = get_theme_meta_if_available()

    return _proto_build_session_init(
        session_id=session.session_id,
        player_id=session.player_id or "earth_observer_01",
        player_name=session.player_name or "观察者",
        signal_quality_pct=gs.signal_quality,
        sol=gs.sol,
        agents_list=agents_list,
        resources=resources,
        theme_meta=theme_meta,
    )


def build_error_message(code: str, message: str) -> Dict:
    """构造 error 消息（委托 protocol.py）"""
    return _proto_build_error(code, message)


def build_pong() -> Dict:
    """构造 pong 消息（委托 protocol.py）"""
    return _proto_build_pong()


def build_ack(acked_msg_id: str) -> Dict:
    """构造 ack 消息（委托 protocol.py）"""
    return _proto_build_ack(acked_msg_id)


# ============================================================
# 消息处理
# ============================================================

async def handle_hello(session: ClientSession, payload: Dict) -> Optional[Dict]:
    """处理 hello 消息 → 返回 session_init"""
    # 提取 token / client_version（Phase 1 不校验）
    token = payload.get("token")
    client_version = payload.get("client_version", "0.1.0")
    last_session_id = payload.get("last_session_id")

    # 如果有 token，解析 player_id（Phase 1 占位）
    if token:
        session.player_id = "earth_observer_01"
        session.player_name = "观察者"

    logger.info(
        "hello 收到: client_version=%s, last_session=%s, token=%s",
        client_version,
        last_session_id,
        "有" if token else "无",
    )

    # 返回 session_init
    return build_session_init(session)


async def handle_player_input(session: ClientSession, payload: Dict):
    """处理 player_input 消息 → 调用 GameLoop → 返回消息列表

    payload: {text, target_agent_id?}
    返回值: 消息信封列表（自然语言通常 1 条；:sol 可能多条含 story_event）
    """
    text = payload.get("text", "").strip()
    target_agent_id = payload.get("target_agent_id")

    if not text:
        return [build_error_message("E_EMPTY_INPUT", "输入文本不能为空")]

    # target_agent_id 优先；否则用 session.current_target
    agent_id = target_agent_id if (target_agent_id and target_agent_id in NPC_REGISTRY) else session.current_target

    logger.info(
        "player_input: text=%r, target=%s, mode=%s",
        text[:50],
        agent_id,
        session.response_mode,
    )

    # 调用 GameLoop 统一入口（同步，放线程池避免阻塞事件循环）
    try:
        results = await asyncio.get_event_loop().run_in_executor(
            None,
            process_player_turn,
            text,
            agent_id,
            session.response_mode,
        )
    except Exception as e:
        logger.exception("process_player_turn 异常")
        return [build_error_message("E_AGENT_FAILURE", f"Agent 处理失败: {e}")]

    # results 是消息列表
    for r in results:
        logger.info(
            "response: type=%s, sender=%s",
            r.get("type"),
            r.get("payload", {}).get("sender_id", r.get("payload", {}).get("event_id", "")),
        )

    return results


async def handle_option_select_msg(session: ClientSession, payload: Dict):
    """处理 option_select 消息（v1.2 §11.4 C→S）→ 返回 option_result

    payload: {event_id, option_id, followup_id?}
    """
    event_id = payload.get("event_id", "")
    option_id = payload.get("option_id", "")
    followup_id = payload.get("followup_id")

    if not event_id or not option_id:
        return [build_error_message("E_OPTION_SELECT", "缺少 event_id 或 option_id")]

    logger.info("option_select: event=%s, option=%s, followup=%s", event_id, option_id, followup_id)

    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            handle_option_select,
            event_id,
            option_id,
            followup_id,
        )
    except Exception as e:
        logger.exception("handle_option_select 异常")
        return [build_error_message("E_OPTION_FAILURE", f"选项处理失败: {e}")]

    return [result]


async def handle_command(session: ClientSession, payload: Dict) -> Optional[Dict]:
    """处理 command 消息 → 路由到命令处理或 talk

    payload: {raw, args[]}
    """
    raw = payload.get("raw", "").strip().lower()
    args = payload.get("args", [])

    logger.info("command: raw=%r, args=%r", raw, args)

    # talk 命令特殊处理
    if raw == "talk":
        if not args:
            return {
                "msg_id": _gen_msg_id(),
                "type": "command_response",
                "ts_tick": _now_ts(),
                "payload": {
                    "output_segments": [
                        {"text": "用法: talk <name> [message]\n", "protected": True, "tag": "command_response"}
                    ],
                    "data": None,
                },
            }
        target = args[0].lower()
        if target not in NPC_REGISTRY:
            return {
                "msg_id": _gen_msg_id(),
                "type": "command_response",
                "ts_tick": _now_ts(),
                "payload": {
                    "output_segments": [
                        {"text": f"未知人员: {target}。输入 ls 查看可用人员。\n", "protected": True, "tag": "command_response"}
                    ],
                    "data": None,
                },
            }
        # 切换当前对话目标
        session.current_target = target
        # 同步 GameLoop 的 active_npc（归一化为 canonical 短名）
        try:
            from ws_adapter_v2 import get_game_loop, normalize_agent_id
            get_game_loop().active_npc = normalize_agent_id(target)
        except Exception as e:
            logger.debug("同步 game_loop.active_npc 失败: %s", e)

        # 如果有后续文本，走 Agent 链路
        if len(args) > 1:
            player_text = " ".join(args[1:])
            raw_input = f"talk {target} {player_text}"
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    process_input,
                    raw_input,
                    target,
                    session.response_mode,
                )
                return result
            except Exception as e:
                logger.exception("talk 命令处理异常")
                return build_error_message("E_AGENT_FAILURE", f"Agent 处理失败: {e}")
        else:
            # 仅切换目标，返回确认
            npc = NPC_REGISTRY[target]
            return {
                "msg_id": _gen_msg_id(),
                "type": "command_response",
                "ts_tick": _now_ts(),
                "payload": {
                    "output_segments": [
                        {"text": f"已切换到 {npc['name']} [{npc['label']}]。说点什么？\n", "protected": True, "tag": "command_response"}
                    ],
                    "data": {"target_agent": target},
                },
            }

    # 其他系统命令 → 交给 process_input
    raw_input = raw + (" " + " ".join(args) if args else "")
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            process_input,
            raw_input,
            session.current_target,
            session.response_mode,
        )
        return result
    except Exception as e:
        logger.exception("command 处理异常")
        return build_error_message("E_CMD_FAILURE", f"命令处理失败: {e}")


async def handle_resume(session: ClientSession, payload: Dict) -> Optional[Dict]:
    """处理 resume 消息 → Phase 1 简化：返回 session_init"""
    session_id = payload.get("session_id")
    last_msg_id = payload.get("last_msg_id")
    logger.info("resume: session=%s, last_msg=%s", session_id, last_msg_id)
    # Phase 1 不做真正的 resume，返回新的 session_init
    return build_session_init(session)


# ============================================================
# 消息分发
# ============================================================

async def dispatch_message(session: ClientSession, msg: Dict) -> Optional[Dict]:
    """根据消息 type 分发到对应处理器

    Returns:
        要发回客户端的消息（dict），或 None 表示不回复
    """
    msg_type = msg.get("type")
    payload = msg.get("payload", {})
    msg_id = msg.get("msg_id")

    if msg_type == "hello":
        return await handle_hello(session, payload)

    elif msg_type == "player_input":
        return await handle_player_input(session, payload)

    elif msg_type == "option_select":
        return await handle_option_select_msg(session, payload)

    elif msg_type == "command":
        return await handle_command(session, payload)

    elif msg_type == "ping":
        return build_pong()

    elif msg_type == "resume":
        return await handle_resume(session, payload)

    elif msg_type == "ack":
        # 客户端 ack，不需要回复
        logger.debug("收到客户端 ack: %s", payload.get("acked_msg_id"))
        return None

    else:
        logger.warning("未知消息类型: %s", msg_type)
        return build_error_message("E_UNKNOWN_TYPE", f"未知消息类型: {msg_type}")


# ============================================================
# WebSocket 连接处理
# ============================================================

# 活跃连接集合
_connected_clients: Set[ClientSession] = set()


async def client_handler(websocket):
    """单个客户端连接的处理器

    生命周期：
    1. 创建 ClientSession
    2. 循环接收消息 → 分发 → 发送响应
    3. 异常 / 断开 → 清理
    """
    session = ClientSession(websocket)
    _connected_clients.add(session)
    peer = websocket.remote_address if hasattr(websocket, "remote_address") else "unknown"
    logger.info("客户端连接: %s (session=%s)", peer, session.session_id)

    try:
        async for raw_data in websocket:
            # 解析消息
            try:
                msg = json.loads(raw_data)
            except json.JSONDecodeError:
                logger.warning("JSON 解析失败: %s", raw_data[:200])
                await websocket.send(json.dumps(build_error_message(
                    "E_JSON_PARSE", "消息 JSON 解析失败"
                )))
                continue

            msg_type = msg.get("type", "?")
            msg_id = msg.get("msg_id", "?")

            # 分发处理
            try:
                response = await dispatch_message(session, msg)
            except Exception as e:
                logger.exception("消息处理异常 (type=%s)", msg_type)
                response = build_error_message("E_INTERNAL", f"内部错误: {e}")

            # 发送响应（支持单条 dict 或列表，列表按序连发）
            if response is not None:
                responses = response if isinstance(response, list) else [response]
                for resp in responses:
                    # 如果请求有 msg_id，在响应里带上它（方便客户端关联）
                    if msg_id and "ack_for" not in resp.get("payload", {}):
                        resp["payload"]["_ack_for"] = msg_id

                    response_json = json.dumps(resp, ensure_ascii=False)
                    try:
                        await websocket.send(response_json)
                        # 更新 session 的 last_msg_id
                        session.last_msg_id = resp.get("msg_id")
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning("发送响应时连接已关闭")
                        break

            # 处理后日志
            if isinstance(response, list):
                resp_types = [r.get("type") for r in response] if response else ["无响应"]
            else:
                resp_types = [response.get("type")] if response else ["无响应"]
            logger.debug("处理完成: req=%s → resp=%s", msg_type, resp_types)

    except websockets.exceptions.ConnectionClosed:
        logger.info("客户端断开: session=%s", session.session_id)
    except Exception as e:
        logger.exception("连接异常: %s", e)
    finally:
        _connected_clients.discard(session)
        elapsed = time.time() - session.connected_at
        logger.info("连接结束: session=%s, 存活 %.1fs", session.session_id, elapsed)


# ============================================================
# 服务器启动
# ============================================================

async def start_server(host: str = "0.0.0.0", port: int = 8000):
    """启动 WebSocket 服务器"""

    # 引擎化：用 EngineCore 加载项目固定配置（dict/theme_mars_base）
    # 注意：这里不是"主题切换"，而是加载本项目的数据驱动配置，
    # 将结局/命令/状态字段/NPC 等从硬编码迁移到 YAML，便于进一步开发。
    engine_injected = False
    try:
        from agent.engine.data_loader import DataLoader
        from agent.engine.engine_core import EngineCore
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_dir = os.path.join(project_root, "dict", "theme_mars_base")
        loader = DataLoader()
        bundle = loader.load_theme(config_dir)
        if bundle and not bundle.errors:
            engine = EngineCore()
            engine.load_theme(bundle)
            engine.init(start_stage="survival", chat_fn=_chat_fn_proxy)
            set_engine_core(engine)
            engine_injected = True
            logger.info("EngineCore 已加载项目配置: %s", bundle.theme_name)
        else:
            logger.warning("配置加载失败，回退到默认 GameLoop: %s",
                           bundle.errors if bundle else "目录不存在")
    except Exception as e:
        logger.warning("EngineCore 初始化失败，回退到默认 GameLoop: %s", e)

    # 预热 GameState（避免首次请求延迟过高）
    logger.info("预热 GameState...")
    gs = get_game_state()
    logger.info(
        "GameState 就绪: %d NPCs, signal=%d, athena=%s",
        len(gs.npc_states),
        gs.signal_quality,
        gs.athena_status,
    )

    # 预热 Agent（加载种子记忆）
    logger.info("预热 Agent（加载种子记忆）...")
    from ws_adapter_v2 import get_agent
    get_agent("chen_hao")
    logger.info("Agent 就绪")

    # 种子化全部 6 个 NPC 的记忆库（B 计划：多 NPC 对话需要各自记忆）
    try:
        from agent.memory import get_memory_store
        from seed_memories import seed_all_memories
        store = get_memory_store()
        n = seed_all_memories(store)
        logger.info("种子记忆就绪: 新写入 %d 条（6 NPC 共享记忆库）", n)
    except Exception as e:
        logger.warning("种子记忆写入失败（非致命）: %s", e)

    logger.info("=" * 60)
    logger.info("WebSocket 联调服务器启动")
    logger.info("监听: ws://%s:%d/ws", host, port)
    logger.info("前端连接: ws://localhost:%d/ws", port)
    logger.info("EngineCore: %s", "已注入" if engine_injected else "未注入（回退默认）")
    logger.info("按 Ctrl+C 停止")
    logger.info("=" * 60)

    def health_check(connection, request):
        """HTTP 健康检查（Koyeb / Render 等 PaaS 需要）"""
        if request.path == "/health":
            return connection.respond(http.HTTPStatus.OK, "OK\n")
        return None

    # 启动 WebSocket 服务器
    async with serve(client_handler, host, port, ping_interval=None, process_request=health_check):
        await asyncio.Future()  # 永久阻塞


def _chat_fn_proxy(player_input: str, agent_id: str, response_mode: str, npc_state_vars: Dict) -> Dict:
    """EngineCore 注入的 chat 回调代理：转发到 ws_adapter_v2._process_natural_language

    复用 ws_adapter_v2 的全部信封构建逻辑（agent_message + emotion_hint + context_summary）。
    """
    from ws_adapter_v2 import _process_natural_language
    return _process_natural_language(player_input, agent_id, response_mode, npc_state_vars)


def main():
    parser = argparse.ArgumentParser(description="WebSocket 联调服务器")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址（默认 0.0.0.0）")
    parser.add_argument("--port", type=int, default=8000, help="监听端口（默认 8000）")
    args = parser.parse_args()

    try:
        asyncio.run(start_server(args.host, args.port))
    except KeyboardInterrupt:
        logger.info("服务器已停止")


if __name__ == "__main__":
    main()
