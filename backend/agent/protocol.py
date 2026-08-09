"""
统一信封构造中心（ProtocolEngine Phase 1）

职责：
1. 统一所有 S→C 消息信封的构造逻辑，消除 game_loop / ws_adapter_v2 / ws_server 三处重复
2. 提供统一的消息 ID 生成与时间戳工具
3. 为后续引擎化的 ProtocolEngine（消息类型注册表 + 协议版本管理）预留扩展点

设计依据：云逸《WebSocket 接口定义 v1.1/v1.2/v1.3》

作者：锐锋-核心开发工程师  日期：2026-08-08
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional


# ============================================================
# 基础工具
# ============================================================

def gen_msg_id() -> str:
    """生成消息 ID"""
    return f"msg-{uuid.uuid4().hex[:12]}"


def now_ts() -> int:
    """当前时间戳（秒）"""
    return int(time.time())


def _envelope(msg_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """构造统一信封骨架

    Args:
        msg_type: 消息类型（agent_message / story_event / command_response / ...）
        payload: 消息体

    Returns:
        完整信封 {msg_id, type, ts_tick, payload}
    """
    return {
        "msg_id": gen_msg_id(),
        "type": msg_type,
        "ts_tick": now_ts(),
        "payload": payload,
    }


def seg(text: str, protected: bool = True, tag: str = "command_response") -> Dict[str, str]:
    """构造 output_segments 中的一个片段"""
    return {"text": text, "protected": protected, "tag": tag}


# ============================================================
# S→C 消息构造器
# ============================================================

def build_command_response(
    segments: List[Dict[str, str]],
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """构造 command_response 信封"""
    return _envelope("command_response", {
        "output_segments": segments,
        "data": data,
    })


def build_system_message(text: str) -> Dict[str, Any]:
    """构造纯文本系统消息（command_response 的便捷封装）"""
    return build_command_response([seg(text)], None)


def build_agent_message(
    agent_id: str,
    sender_label: str,
    response_text: str,
    latency_ms: int,
    emotion_hint: Optional[Dict[str, Any]] = None,
    signal_quality_pct: int = 85,
    context_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """构造 agent_message 信封（v1.1 §3.3）

    Args:
        agent_id: NPC 的 agent_id
        sender_label: 发送者显示标签（如 CMDR / SOPH）
        response_text: AI 回复文本
        latency_ms: 响应延迟（毫秒）
        emotion_hint: 情绪提示 {stress, morale, emotion_label, ai_status?}
        signal_quality_pct: 信号质量 0-100
        context_summary: 记忆上下文摘要（可选）
    """
    segments = [
        {"text": f"[{sender_label}]> ", "protected": True, "tag": "speaker_label"},
        {"text": response_text, "protected": False, "tag": "speech"},
    ]
    payload: Dict[str, Any] = {
        "sender_id": agent_id,
        "sender_label": sender_label,
        "segments": segments,
        "signal_quality_pct": signal_quality_pct,
        "latency_ms": latency_ms,
        "emotion_hint": emotion_hint,
    }
    if context_summary is not None:
        payload["context_summary"] = context_summary
    return _envelope("agent_message", payload)


def build_story_event(
    event_id: str,
    chapter_id: str,
    node_index: int,
    title: str,
    npc: str,
    description: str,
    options: List[Dict[str, Any]],
    signal_quality_pct: int,
    latency_ms: int,
) -> Dict[str, Any]:
    """构造 story_event 信封（v1.2 §11 S→C）"""
    return _envelope("story_event", {
        "event_id": event_id,
        "chapter_id": chapter_id,
        "node_index": node_index,
        "title": title,
        "npc": npc,
        "description": description,
        "options": options,
        "signal_quality_pct": signal_quality_pct,
        "latency_ms": latency_ms,
    })


def build_option_result(
    event_id: str,
    option_id: str,
    effects_summary: str,
    signal_quality_pct: int,
    selected_option_id: Optional[str] = None,
    state_update: Optional[List] = None,
    leads_to: str = "",
    ending: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """构造 option_result 信封（v1.2 §11 S→C）"""
    payload: Dict[str, Any] = {
        "event_id": event_id,
        "option_id": option_id,
        "selected_option_id": selected_option_id or option_id,
        "effects_summary": effects_summary,
        "state_update": state_update if state_update is not None else [],
        "signal_quality_pct": signal_quality_pct,
    }
    if leads_to:
        payload["leads_to"] = leads_to
    if ending:
        payload["ending"] = ending
    return _envelope("option_result", payload)


def build_option_result_error(
    event_id: str,
    reason: str,
    signal_quality_pct: int,
) -> Dict[str, Any]:
    """构造 option_result 错误信封"""
    return _envelope("option_result", {
        "event_id": event_id,
        "effects_summary": f"[错误] {reason}",
        "state_update": [],
        "signal_quality_pct": signal_quality_pct,
    })


def build_session_init(
    session_id: str,
    player_id: str,
    player_name: str,
    signal_quality_pct: int,
    sol: int,
    agents_list: List[Dict[str, Any]],
    resources: Optional[Dict[str, Dict]] = None,
    base_integrity: float = 0.78,
    base_name: str = "赫拉克勒斯-7号基地",
    mars_time: str = "08:00",
    theme_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """构造 session_init 信封（v1.1 §3.2）

    Args:
        theme_meta: 题材元信息（由 EngineCore.get_theme_meta() 提供），
            缺省时 world_snapshot 不含 theme 字段（向后兼容）。
    """
    world_snapshot: Dict[str, Any] = {
        "sol": sol,
        "mars_time": mars_time,
        "base": {
            "name": base_name,
            "integrity": base_integrity,
            "resources": resources or {},
        },
        "agents": agents_list,
    }
    if theme_meta is not None:
        world_snapshot["theme"] = theme_meta
    return _envelope("session_init", {
        "session_id": session_id,
        "resume_mode": "cold",
        "player_state": {
            "player_id": player_id,
            "player_name": player_name,
            "established_at": "2087-04-15T08:00:00Z",
            "signal_quality_pct": signal_quality_pct,
        },
        "world_snapshot": world_snapshot,
        "signal_quality_pct": signal_quality_pct,
    })


def build_state_update(
    signal_quality_pct: int,
    world: Optional[Dict] = None,
    base: Optional[Dict] = None,
    agents: Optional[List] = None,
) -> Dict[str, Any]:
    """构造 state_update 信封"""
    payload: Dict[str, Any] = {"signal_quality_pct": signal_quality_pct}
    if world is not None:
        payload["world"] = world
    if base is not None:
        payload["base"] = base
    if agents is not None:
        payload["agents"] = agents
    return _envelope("state_update", payload)


def build_system_event(
    event_id: str,
    category: str,
    severity: str,
    text: str,
) -> Dict[str, Any]:
    """构造 system_event 信封"""
    return _envelope("system_event", {
        "event_id": event_id,
        "category": category,
        "severity": severity,
        "text": text,
    })


def build_alert(level: str, code: str, text: str) -> Dict[str, Any]:
    """构造 alert 信封"""
    return _envelope("alert", {"level": level, "code": code, "text": text})


def build_error(code: str, message: str) -> Dict[str, Any]:
    """构造 error 信封"""
    return _envelope("error", {"code": code, "message": message})


def build_pong() -> Dict[str, Any]:
    """构造 pong 信封"""
    return _envelope("pong", {})


def build_ack(acked_msg_id: str) -> Dict[str, Any]:
    """构造 ack 信封"""
    return _envelope("ack", {"acked_msg_id": acked_msg_id})
