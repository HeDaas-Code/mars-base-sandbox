"""
记忆压缩中间件 + episodic 记忆写入（接口规范 §7）

图节点位置：
    retrieve_memories → compress_context → generate_response → write_episodic_memory → END

Phase 1（当前）: 滑动窗口 K=6/10 + 硬截断（不生成摘要）
Phase 2-3（等 API Key）: 摘要生成 + 缓存 + write_episodic_memory 完整实现
"""

import time
from typing import Dict, List, Optional

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage, RemoveMessage

from .state import AgentState
from .config import config
from .memory import get_memory_store


# ============================================================
# compress_context 节点
# ============================================================

def compress_context(state: AgentState) -> Dict:
    """节点：滑动窗口压缩对话历史

    Phase 1 实现（接口规范 §7.7）:
    - 根据 response_mode 选择 K 值（deliberate=6, deep=10）
    - 超过阈值时截断旧消息，保留最近 K 条
    - 旧消息暂不生成摘要（Phase 2 等 API Key）

    Returns:
        更新 messages 列表（仅保留最近 K 条）和 compressed_count
    """
    mode = state.get("response_mode", "deliberate")
    messages = state.get("messages", [])

    # reflexive 模式不压缩
    if mode == "reflexive":
        return {"compressed_count": 0}

    k = config.history_window_k.get(mode, 6)
    threshold = config.compress_threshold.get(mode, 10)

    if len(messages) <= threshold:
        # 未超阈值，不压缩
        return {"compressed_count": state.get("compressed_count", 0)}

    # Phase 1: 硬截断，保留最近 K 条
    old_messages = messages[:-k] if k > 0 else messages
    recent_messages = messages[-k:] if k > 0 else []

    # Phase 2 占位：摘要生成（等 API Key）
    # summary = _generate_summary(old_messages, state.get("summary", ""))
    # 当前 Phase 1 直接丢弃旧消息，不生成摘要
    new_compressed_count = state.get("compressed_count", 0) + len(old_messages)

    # 使用 RemoveMessage 让 add_messages reducer 正确删除旧消息
    # （直接返回 recent_messages 会被 add_messages 追加而非替换）
    removals = [RemoveMessage(id=m.id) for m in old_messages if m.id]

    return {
        "messages": removals,
        "compressed_count": new_compressed_count,
    }


def _generate_summary(old_messages: List[BaseMessage], prev_summary: str) -> str:
    """Phase 2: 将旧消息压缩为摘要（需 LLM 调用，等 API Key）

    增量式压缩：prev_summary + old_messages → new_summary
    """
    # TODO: API Key 就绪后实现
    # summary_prompt = f"""请将以下对话历史压缩为简洁摘要（不超过200字），保留：
    # 1. 关键决策和结果
    # 2. NPC情绪变化
    # 3. 未解决的问题
    # 4. 重要承诺或约定
    #
    # 已有摘要：{prev_summary}
    # 新对话：{format_messages_to_text(old_messages)}
    # """
    # llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, max_tokens=200)
    # response = llm.invoke([SystemMessage(content=summary_prompt)])
    # return response.content
    return prev_summary


def format_messages_to_text(messages: List[BaseMessage]) -> str:
    """将消息列表格式化为纯文本"""
    lines = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            lines.append(f"玩家: {msg.content}")
        elif isinstance(msg, AIMessage):
            lines.append(f"NPC: {msg.content}")
        elif isinstance(msg, SystemMessage):
            lines.append(f"系统: {msg.content}")
    return "\n".join(lines)


# ============================================================
# write_episodic_memory 节点
# ============================================================

# 简易情感关键词匹配（Phase 1 临时方案）
_EMOTION_KEYWORDS = {
    "fear": ["害怕", "恐惧", "怕", "担心", "慌", "panic", "fear", "afraid"],
    "despair": ["绝望", "放弃", "死", "完了", "没救", "hopeless", "give up"],
    "anger": ["愤怒", "气", "混蛋", "该死", "angry", "damn", "furious"],
    "joy": ["高兴", "太好了", "成功", "希望", "hope", "great", "wonderful"],
    "tense": ["紧急", "危险", "快", "来不及", "urgent", "danger", "hurry"],
    "calm": ["冷静", "没事", "稳定", "正常", "calm", "fine", "ok"],
}


def detect_emotion(text: str) -> float:
    """基于关键词匹配估算 emotional_intensity

    Returns:
        0.2-1.0 的情感强度值
    """
    text_lower = text.lower()
    for emotion, keywords in _EMOTION_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                # 高情绪关键词映射
                if emotion in ("fear", "despair", "anger"):
                    return 0.8
                elif emotion in ("joy", "tense"):
                    return 0.6
                else:
                    return 0.3
    return 0.3  # 默认低情感


def write_episodic_memory(state: AgentState) -> Dict:
    """节点：将本轮对话写入 episodic 记忆（接口规范 §7.4）

    在 generate_response 之后执行。

    写入频率：每轮对话写入一条 episodic 记忆
    清理策略：当某 agent 记忆数 > 200 时，清理低重要性记忆（Phase 4）
    """
    player_input = state.get("player_input", "")
    response = state.get("response", "")
    agent_id = state.get("agent_id", "unknown")
    mode = state.get("response_mode", "deliberate")

    if not response:
        return {}

    # 判断重要性（接口规范 §7.4.2）
    if mode == "deep":
        importance = 0.7
    elif mode == "deliberate":
        importance = 0.5
    else:
        importance = 0.3

    # 情感强度（Phase 1 关键词匹配）
    emotional_intensity = detect_emotion(player_input + response)

    store = get_memory_store()
    mem_id = store.add_memory(
        agent_id=agent_id,
        content=f"玩家: {player_input}\n{agent_id}: {response}",
        memory_type="episodic",
        timestamp=f"Sol-100",  # TODO: 接入 GameState.sol
        importance=importance,
        emotional_intensity=emotional_intensity,
        event_type="episodic",
        tags=_extract_tags(player_input),
    )

    # Phase 4: 低重要性记忆清理
    _maybe_cleanup_memories(agent_id, store)

    return {"new_memory_id": mem_id}


def _extract_tags(text: str) -> List[str]:
    """从玩家输入中提取标签（简化版）"""
    tags = []
    keyword_map = {
        "oxygen": ["氧气", "oxygen", "MOXIE"],
        "communication": ["通信", "地球", "signal", "contact"],
        "repair": ["修", "repair", "维修"],
        "morale": ["士气", "morale", "情绪", "心理"],
        "evacuation": ["撤离", "逃生", "leave", "evacuate"],
        "danger": ["危险", "danger", "紧急", "emergency"],
    }
    text_lower = text.lower()
    for tag, keywords in keyword_map.items():
        if any(kw.lower() in text_lower for kw in keywords):
            tags.append(tag)
    return tags


def _maybe_cleanup_memories(agent_id: str, store) -> None:
    """Phase 4: 低重要性记忆清理（接口规范 §7.4.3）

    当记忆数 > 200 时，归档 importance < 0.3 且 emotional_intensity < 0.3 的记忆
    professional_knowledge 类型不参与清理
    """
    count = store.count(agent_id)
    if count <= 200:
        return

    # 获取所有记忆，筛选待清理的
    all_mems = store.get_all_memories(agent_id)
    to_delete = []
    for mem in all_mems:
        meta = mem.get("metadata", {})
        if meta.get("event_type") == "professional_knowledge":
            continue
        if meta.get("importance", 0.5) < 0.3 and meta.get("emotional_intensity", 0.5) < 0.3:
            to_delete.append(mem["id"])

    for mid in to_delete:
        store.delete_memory(mid)

    if to_delete:
        print(f"[INFO] 清理 {agent_id} 低重要性记忆 {len(to_delete)} 条")
