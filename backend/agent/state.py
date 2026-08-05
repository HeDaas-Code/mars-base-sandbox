"""
LangGraph 状态定义
定义 Agent 状态图中的数据结构
"""

from typing import TypedDict, Optional, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Agent 状态 - LangGraph 状态图的节点状态"""

    # 消息历史（LangGraph 自动管理追加）
    messages: Annotated[list[BaseMessage], add_messages]

    # 当前玩家输入
    player_input: str

    # 检索到的记忆
    retrieved_memories: list[str]

    # Agent ID
    agent_id: str

    # 游戏状态上下文
    game_state_context: str

    # 回复模式：reflexive / deliberate / deep
    response_mode: str

    # LLM 回复
    response: Optional[str]

    # Token 使用量
    prompt_tokens: int
    completion_tokens: int

    # --- 记忆压缩相关 (接口规范 §7.6) ---
    summary: str                   # 历史摘要（增量式）
    compressed_count: int           # 已压缩的消息数
    new_memory_id: str              # 本轮新写入的记忆 ID

    # --- NPC 人格渲染变量（game_loop / ws_adapter 注入）---
    # 用于渲染 sophia/viktor/aisha/marcus/lin_ruoxi 的 Jinja2 人格模板
    # 缺省时模板变量渲染为空串（退化但可用）
    npc_state_vars: Optional[dict]
