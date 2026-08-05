"""
WebSocket 适配层 - 将 Agent.chat() 输出转换为前端 v1.1 协议格式

职责：
1. 将纯文本 response 转换为 segments[] 格式
2. 构造完整的 agent_message 信封（含 signal_quality_pct / latency_ms / emotion_hint）
3. 生成 context_summary 对象
4. 处理 ls/status/talk 系统命令路由

依赖：云逸《WebSocket 接口定义 v1.1》
"""

import time
import uuid
import logging
from typing import Dict, List, Optional

from agent.config import config
from agent.graph import Agent
from agent.compress import detect_emotion
from agent.game_state import (
    GameState,
    create_initial_game_state,
    build_emotion_hint,
    AI_SENDERS,
)

logger = logging.getLogger(__name__)


# ============================================================
# NPC 注册表（Phase 1 仅陈昊，Phase 2 扩展）
# ============================================================

NPC_REGISTRY = {
    "chen_hao": {
        "agent_id": "chen_hao",
        "label": "CMDR",
        "name": "陈昊",
        "location": "指挥舱",
    },
    "sophia_ramirez": {
        "agent_id": "sophia_ramirez",
        "label": "BIO",
        "name": "索菲亚",
        "location": "生物实验室",
    },
    "viktor_ivanov": {
        "agent_id": "viktor_ivanov",
        "label": "ENG",
        "name": "维克托",
        "location": "工程舱",
    },
    "aisha_khan": {
        "agent_id": "aisha_khan",
        "label": "COMM",
        "name": "艾莎",
        "location": "通信舱",
    },
    "marcus_weber": {
        "agent_id": "marcus_weber",
        "label": "MED",
        "name": "马库斯",
        "location": "医疗舱",
    },
    "lin_ruoxi": {
        "agent_id": "lin_ruoxi",
        "label": "ATM",
        "name": "林若曦",
        "location": "气象观测站",
    },
}


# ============================================================
# 模拟游戏状态（Phase 2 接入 GameState）
# ============================================================

# 全局 GameState 实例（单例）
# Phase 2: 从 MOCK_GAME_STATE 切换到真实 GameState
_game_state: Optional[GameState] = None


def get_game_state() -> GameState:
    """获取全局 GameState 单例
    
    首次调用时初始化，包含所有 NPC 初始状态。
    """
    global _game_state
    if _game_state is None:
        _game_state = create_initial_game_state()
        logger.info("GameState 初始化完成: %d NPCs, signal=%d, athena=%s",
                    len(_game_state.npc_states),
                    _game_state.signal_quality,
                    _game_state.athena_status)
    return _game_state


# agent_id (前端协议) → npc_id (GameState.npc_states 键) 映射
AGENT_TO_NPC_ID: Dict[str, str] = {
    "chen_hao": "chen_hao",
    "sophia_ramirez": "sophia",
    "viktor_ivanov": "viktor",
    "aisha_khan": "aisha",
    "marcus_weber": "marcus",
    "lin_ruoxi": "lin_ruoxi",
    # AI senders
    "athena": "athena",
    "courier": "courier",
}

# canonical 短名别名：让 build_agent_message / get_agent 既能接受 registry id
# （如 sophia_ramirez）也能接受短名（sophia），二者指向同一 NPC 配置
for _rid, _npc in list(NPC_REGISTRY.items()):
    _short = AGENT_TO_NPC_ID.get(_rid)
    if _short and _short not in NPC_REGISTRY:
        NPC_REGISTRY[_short] = _npc


def normalize_agent_id(agent_id: str) -> str:
    """将任意 agent_id 归一化为 canonical 短名（game_state.npc_states 键）

    registry id (sophia_ramirez) → short (sophia)
    short id (sophia) → short (sophia)
    未知 → chen_hao
    """
    if agent_id in AGENT_TO_NPC_ID:
        return AGENT_TO_NPC_ID[agent_id]
    # 已经是短名且在 npc_states 中
    return agent_id if agent_id in NPC_REGISTRY else "chen_hao"

# 保留旧 MOCK_GAME_STATE 的 sol/mars_time 等字段用于 status 命令（Phase 2 过渡）
# TODO: 后续完全迁移到 GameState


MOCK_GAME_STATE = {
    "sol": 1,
    "mars_time": "08:00",
    "base": {
        "name": "赫拉克勒斯-7号基地",
        "integrity": 0.78,
        "resources": {
            "oxygen": {"current": 78, "max": 100, "rate": -0.3},
            "power": {"current": 85, "max": 100, "rate": 0.5},
            "water": {"current": 65, "max": 100, "rate": -0.1},
            "food": {"current": 90, "max": 100, "rate": -0.5},
        },
    },
    "signal_quality_pct": 62,
}


# ============================================================
# 系统命令路由
# ============================================================

def handle_command(command: str, args: List[str], agent: Agent) -> Dict:
    """处理系统命令（ls / status / help 等）

    Args:
        command: 命令名（如 "ls", "status"）
        args: 命令参数
        agent: Agent 实例

    Returns:
        command_response 格式的消息信封
    """
    if command == "ls":
        return _cmd_ls()
    elif command == "status":
        return _cmd_status()
    elif command == "help":
        return _cmd_help()
    elif command in ("clear", "history", "man", "pwd", "cd", "cat", "less", "head", "tail"):
        # 这些命令前端自行处理，后端返回空
        return _build_command_response([], None)
    else:
        return _build_command_response(
            [{"text": f"command not found: {command}. 输入 help 查看可用指令。", "protected": True, "tag": "command_response"}],
            None,
        )


def _cmd_ls() -> Dict:
    """ls: 列出基地当前可交互的舱室/NPC"""
    segments = []
    data_entries = []
    for npc_id, npc in NPC_REGISTRY.items():
        line = f"{npc['location']:<12} {npc_id:<16} [{npc['label']}]  在线\n"
        segments.append({"text": line, "protected": True, "tag": "command_response"})
        data_entries.append({
            "location": npc["location"],
            "agent_id": npc["agent_id"],
            "label": npc["label"],
            "online": True,
        })

    return _build_command_response(segments, {"entries": data_entries})


def _cmd_status() -> Dict:
    """status: 基地状态摘要"""
    gs = MOCK_GAME_STATE
    base = gs["base"]
    res = base["resources"]

    segments = [
        {"text": f"═══ {base['name']} 状态报告 ═══\n", "protected": True, "tag": "command_response"},
        {"text": f"Sol {gs['sol']}  火星时间 {gs['mars_time']}  基地完整度 {int(base['integrity']*100)}%\n", "protected": True, "tag": "command_response"},
        {"text": "───────────────────────────\n", "protected": False, "tag": "command_response"},
        {"text": f"氧气  {res['oxygen']['current']}%  电力  {res['power']['current']}%  水  {res['water']['current']}%  食物  {res['food']['current']}%\n", "protected": True, "tag": "command_response"},
        {"text": "───────────────────────────\n", "protected": False, "tag": "command_response"},
        {"text": f"在岗人员 {len(NPC_REGISTRY)}/{len(NPC_REGISTRY)}  信号质量 {gs['signal_quality_pct']}%  警报 0\n", "protected": True, "tag": "command_response"},
        {"text": "───────────────────────────\n", "protected": False, "tag": "command_response"},
    ]

    data = {
        "sol": gs["sol"],
        "mars_time": gs["mars_time"],
        "integrity": base["integrity"],
        "resources": {
            "oxygen": {"current": res["oxygen"]["current"], "max": 100},
            "power": {"current": res["power"]["current"], "max": 100},
            "water": {"current": res["water"]["current"], "max": 100},
            "food": {"current": res["food"]["current"], "max": 100},
        },
        "agent_count": len(NPC_REGISTRY),
        "signal_quality_pct": gs["signal_quality_pct"],
        "alert_count": 0,
    }

    return _build_command_response(segments, data)


def _cmd_help() -> Dict:
    """help: 可用指令列表"""
    segments = [
        {"text": "可用指令：\n", "protected": True, "tag": "command_response"},
        {"text": "  ls          列出基地人员和舱室\n", "protected": False, "tag": "command_response"},
        {"text": "  status      基地状态报告\n", "protected": False, "tag": "command_response"},
        {"text": "  talk <name> 与指定人员对话（如 talk chen_hao）\n", "protected": False, "tag": "command_response"},
        {"text": "  help        显示此帮助\n", "protected": False, "tag": "command_response"},
        {"text": "  clear       清屏\n", "protected": False, "tag": "command_response"},
    ]
    return _build_command_response(segments, None)


def _build_command_response(segments: List[Dict], data: Optional[Dict]) -> Dict:
    """构造 command_response 消息信封"""
    return {
        "msg_id": f"msg-{uuid.uuid4().hex[:8]}",
        "type": "command_response",
        "ts_tick": int(time.time()),
        "payload": {
            "output_segments": segments,
            "data": data,
        },
    }


# ============================================================
# 自然语言 -> agent_message 适配
# ============================================================

# 系统命令集合（与前端 shell.js 对齐）
SYSTEM_COMMANDS = {
    "ls", "cd", "pwd", "cat", "less", "head", "tail",
    "status", "top", "watch",
    "talk", "broadcast", "ping",
    "relay", "connect", "signal",
    "help", "history", "clear", "man",
}


def is_system_command(text: str) -> bool:
    """判断输入是否为系统命令"""
    parts = text.strip().split()
    first_word = parts[0].lower() if parts else ""
    return first_word in SYSTEM_COMMANDS


def parse_command(text: str):
    """解析命令输入，返回 (command, args) 元组"""
    parts = text.strip().split()
    if not parts:
        return None, []
    return parts[0].lower(), parts[1:]


# ============================================================
# 核心适配函数
# ============================================================

# Agent 实例缓存（按 agent_id）
_agents: Dict[str, Agent] = {}


def get_agent(agent_id: str = "chen_hao") -> Agent:
    """获取或创建 Agent 实例（单例缓存）"""
    if agent_id not in _agents:
        _agents[agent_id] = Agent(agent_id=agent_id)
    return _agents[agent_id]


def build_agent_message(
    agent_id: str,
    response_text: str,
    latency_ms: int,
    emotion_hint: Optional[Dict] = None,
    signal_quality_pct: int = 85,
) -> Dict:
    """构造 v1.1 agent_message 消息信封

    Args:
        agent_id: NPC 的 agent_id
        response_text: AI 回复文本
        latency_ms: 响应延迟（毫秒）
        emotion_hint: 情绪提示 {stress, morale}
        signal_quality_pct: 信号质量 0-100

    Returns:
        v1.1 agent_message 消息信封
    """
    npc = NPC_REGISTRY.get(agent_id, NPC_REGISTRY["chen_hao"])

    # 将纯文本拆分为 segments
    # Phase 1: 简单拆分——speaker_label + 正文
    segments = [
        {"text": f"[{npc['label']}]> ", "protected": True, "tag": "speaker_label"},
        {"text": response_text, "protected": False, "tag": "speech"},
    ]

    return {
        "msg_id": f"msg-{uuid.uuid4().hex[:8]}",
        "type": "agent_message",
        "ts_tick": int(time.time()),
        "payload": {
            "sender_id": agent_id,
            "sender_label": npc["label"],
            "segments": segments,
            "signal_quality_pct": signal_quality_pct,
            "latency_ms": latency_ms,
            "emotion_hint": emotion_hint,
        },
    }


def build_context_summary(
    history_count: int,
    response_mode: str,
    compressed_count: int,
) -> Dict:
    """构造 context_summary 对象

    Args:
        history_count: 当前 messages 列表长度
        response_mode: reflexive / deliberate / deep
        compressed_count: 已压缩的消息数

    Returns:
        {history_count, k_limit, compressed_count, mode}
    """
    k_map = {"reflexive": 0, "deliberate": 6, "deep": 10}
    return {
        "history_count": history_count,
        "k_limit": k_map.get(response_mode, 6),
        "compressed_count": compressed_count,
        "mode": response_mode,
    }


def process_input(
    raw_input: str,
    agent_id: str = "chen_hao",
    response_mode: str = "deliberate",
) -> Dict:
    """处理玩家输入（统一入口）

    自动区分系统命令和自然语言，分别走 command 通道和 player_input 通道。

    Args:
        raw_input: 玩家原始输入
        agent_id: 目标 NPC 的 agent_id
        response_mode: 响应模式

    Returns:
        v1.1 消息信封（command_response 或 agent_message）
        + context_summary（仅 agent_message 时附带）
    """
    text = raw_input.strip()
    if not text:
        return _build_command_response(
            [{"text": "输入不能为空。", "protected": True, "tag": "command_response"}], None
        )

    # 判断是否为系统命令
    parts = text.split()
    first_word = parts[0].lower() if parts else ""

    if first_word == "talk":
        # talk <name>: 转发到 player_input 通道，走完整 Agent 链路
        if len(parts) < 2:
            return _build_command_response(
                [{"text": "用法: talk <name>（如 talk chen_hao）", "protected": True, "tag": "command_response"}],
                None,
            )
        target = parts[1].lower()
        # 如果后面有更多内容，作为玩家输入文本
        player_text = " ".join(parts[2:]) if len(parts) > 2 else ""
        if not player_text:
            # talk <name> 无后续文本 → 切换对话目标，返回确认
            npc = NPC_REGISTRY.get(target)
            if npc:
                return _build_command_response(
                    [{"text": f"已切换到 {npc['name']} [{npc['label']}]。说点什么？\n", "protected": True, "tag": "command_response"}],
                    {"target_agent": target},
                )
            else:
                return _build_command_response(
                    [{"text": f"未知人员: {target}。输入 ls 查看可用人员。\n", "protected": True, "tag": "command_response"}],
                    None,
                )
        # 有文本 → 走 Agent 链路
        agent_id = target if target in NPC_REGISTRY else "chen_hao"
        return _process_natural_language(player_text, agent_id, response_mode)

    elif first_word in SYSTEM_COMMANDS:
        # 其他系统命令 → command 通道
        command, args = first_word, parts[1:]
        agent = get_agent(agent_id)
        return handle_command(command, args, agent)

    else:
        # 自然语言 → player_input 通道
        return _process_natural_language(text, agent_id, response_mode)


def _process_natural_language(
    player_input: str,
    agent_id: str,
    response_mode: str,
    npc_state_vars: Optional[Dict] = None,
) -> Dict:
    """处理自然语言输入，走完整 Agent 链路

    Args:
        npc_state_vars: NPC 心理状态变量，传给 graph 用于渲染 Jinja2 人格模板
    """
    agent = get_agent(agent_id)

    # 游戏状态字符串
    gs = get_game_state()
    game_state = f"Sol {gs.sol}, 信号质量 {gs.signal_quality}%"

    result = agent.chat(
        player_input=player_input,
        game_state=game_state,
        response_mode=response_mode,
        npc_state_vars=npc_state_vars,
    )
    # §8.3: latency_ms 是模拟通信延迟，不是 chat() 执行耗时
    # 公式: 500 + (100 - signal_quality) * 50
    latency_ms = 500 + (100 - gs.signal_quality) * 50

    # 构造 agent_message
    response_text = result["response"]

    # 情绪提示（主路径：从 GameState.npc_states 派生 emotion_label / ai_status）
    npc_id = AGENT_TO_NPC_ID.get(agent_id, agent_id)
    try:
        emotion_hint = build_emotion_hint(gs, npc_id)
    except Exception as e:
        # fallback: detect_emotion 关键词匹配（Phase 1 逻辑）
        logger.warning("build_emotion_hint failed (agent_id=%s): %s, using fallback", agent_id, e)
        ei = detect_emotion(player_input + response_text)
        emotion_hint = {
            "stress": min(0.9, ei * 0.8),
            "morale": max(0.2, 1.0 - ei * 0.5),
        }

    msg = build_agent_message(
        agent_id=agent_id,
        response_text=response_text,
        latency_ms=latency_ms,
        emotion_hint=emotion_hint,
        signal_quality_pct=gs.signal_quality,
    )

    # 附带 context_summary
    # history_count 从 graph state 获取；无 checkpointer 时从 chat() 返回值获取
    try:
        state = agent.graph.get_state(
            {"configurable": {"thread_id": agent.thread_id}}
        )
        history_count = len(state.values.get("messages", []))
    except (ValueError, Exception):
        # 无 checkpointer，从 chat() 返回值获取
        history_count = len(result.get("messages", []))

    msg["payload"]["context_summary"] = build_context_summary(
        history_count=history_count,
        response_mode=response_mode,
        compressed_count=result.get("compressed_count", 0),
    )

    return msg


# ============================================================
# GameLoop 集成（B 计划：事件驱动游戏循环）
# ============================================================

# 全局 GameLoop 单例（首次访问时初始化）
_game_loop = None

# meta 命令前缀（与 game_loop._META_PREFIX 一致）
_META_PREFIX = ":"


def _chat_fn(player_input: str, agent_id: str, response_mode: str, npc_state_vars: Dict) -> Dict:
    """game_loop 注入的 chat 回调：复用 _process_natural_language 的全部信封构建逻辑

    与直接调 process_input 的区别：这里始终走自然语言路径，且注入 npc_state_vars。
    """
    return _process_natural_language(player_input, agent_id, response_mode, npc_state_vars)


def get_game_loop():
    """获取全局 GameLoop 单例

    首次调用时初始化 GameState + EventScheduler + GameLoop，并启动 survival 章节。
    """
    global _game_loop
    if _game_loop is None:
        from agent.event_scheduler import EventScheduler
        from agent.game_loop import GameLoop
        gs = get_game_state()
        scheduler = EventScheduler(gs)
        _game_loop = GameLoop(gs, scheduler, chat_fn=_chat_fn)
        _game_loop.start()
        logger.info("GameLoop 初始化完成: stage=%s, Sol=%d",
                    scheduler.chapter.stage_id, gs.sol)
    return _game_loop


def process_player_turn(raw_input: str, agent_id: str = "chen_hao",
                        response_mode: str = "deliberate") -> List[Dict]:
    """玩家回合统一入口（B 计划）

    自动区分：
    - meta 命令（: 开头）→ game_loop.handle_meta
    - 自然语言 / 情感指令 → game_loop.tick
    - 系统命令（ls/status/talk 等前端 shell 命令）→ 沿用 handle_command

    Returns:
        待发送的消息信封列表（可能多条，如 :sol 后跟 story_event）
    """
    text = raw_input.strip()
    if not text:
        return [_build_command_response(
            [{"text": "输入不能为空。", "protected": True, "tag": "command_response"}], None
        )]

    gl = get_game_loop()

    # meta 命令
    if text.startswith(_META_PREFIX):
        parts = text[1:].split()
        command = parts[0].lower() if parts else ""
        args = parts[1:]
        msg = gl.handle_meta(command, args)
        # :sol 可能附带后续 story_event
        results = [msg]
        for evt in msg.pop("_followup_story_events", []):
            results.append(evt)
        return results

    # 前端 shell 系统命令（ls/status/talk 等）仍走原路径，保持兼容
    parts = text.split()
    first_word = parts[0].lower() if parts else ""
    if first_word in SYSTEM_COMMANDS:
        command, args = first_word, parts[1:]
        agent = get_agent(agent_id)
        return [handle_command(command, args, agent)]

    # 自然语言 / 情感指令 → game_loop.tick
    # 归一化为 canonical 短名；若前端未指定（默认 chen_hao）则用 game_loop.active_npc
    target = normalize_agent_id(agent_id)
    if target == "chen_hao" and agent_id == "chen_hao":
        # 前端用默认值 → 沿用 game_loop 当前对话目标
        target = gl.active_npc
    return gl.tick(text, target, response_mode)


def handle_option_select(event_id: str, option_id: str,
                         followup_id: Optional[str] = None) -> Dict:
    """option_select 入口（B 计划 v1.2 §11.4 C→S）"""
    gl = get_game_loop()
    return gl.handle_option_select(event_id, option_id, followup_id)
