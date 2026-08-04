"""
LangGraph 状态图 - 核心 Agent 链路
流程：System Prompt(人格) → 记忆检索 Top-3 → 玩家输入 → LLM 回复

支持三档响应模式：
- reflexive:  不调 LLM，基于规则匹配快速回复
- deliberate: GPT-4o-mini，平衡速度与质量
- deep:       GPT-4o，深思熟虑的高质量回复
"""

import time
from typing import Dict

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END

from .state import AgentState
from .config import config
from .prompt import get_system_prompt, format_game_state
from .memory import MemoryStore, format_memories_for_prompt, get_memory_store
from .compress import compress_context, write_episodic_memory


# ============================================================
# Mock LLM - 无 API Key 时用于基础链路验证
# ============================================================

class MockLLM:
    """Mock LLM，模拟回复用于无 API Key 环境下的链路验证"""

    def invoke(self, messages):
        # 提取最后一条用户消息
        user_msg = ""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_msg = msg.content
                break

        # 基于关键词的简单规则匹配
        if any(kw in user_msg for kw in ["氧气", "oxygen", "MOXIE"]):
            reply = "氧气储备还在下降。MOXIE-2 损毁后我们只能靠备用氧气罐撑着——大约还有60个Sol。我在想怎么修，但现在别浪费时间讨论这个，先把手头的活干完。"
        elif any(kw in user_msg for kw in ["通信", "地球", "contact", "earth"]):
            reply = "主通信阵列彻底报废了。备用频段我试过，信号到不了地球。我们只能靠自己，直到有人发现我们还活着。"
        elif any(kw in user_msg for kw in ["修", "repair", "维修"]):
            reply = "维修方案我已经在脑子里过了三遍。问题是缺零件。如果你有想法，说。如果没有，我按我的来。"
        elif any(kw in user_msg for kw in ["士气", "morale", "情绪", "心理"]):
            reply = "大家的心理状态我一直在盯。这种情况下，谁崩溃都不意外。但只要任务还在推进，人就有盼头。我们继续。"
        elif any(kw in user_msg for kw in ["撤离", "逃生", "leave", "evacuate"]):
            reply = "撤离飞船导航系统烧了，飞不起来。修导航比修通信还难。我们不走，我们留下——想办法活下去。"
        else:
            reply = "收到。情况我了解了。现在需要的是行动方案，不是分析。你有什么具体建议？"

        # 模拟 token 计数
        prompt_tokens = sum(len(m.content) // 4 for m in messages)
        completion_tokens = len(reply) // 4

        return MockResponse(reply, prompt_tokens, completion_tokens)


class MockResponse:
    """Mock LLM 响应对象"""
    def __init__(self, content: str, prompt_tokens: int, completion_tokens: int):
        self.content = content
        self.usage_metadata = {
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }


# ============================================================
# LangGraph 节点函数
# ============================================================


def retrieve_memories(state: AgentState) -> Dict:
    """节点：检索 Top-K 记忆"""
    store = get_memory_store()
    memories = store.retrieve(
        agent_id=state["agent_id"],
        query=state["player_input"],
        top_k=config.memory_top_k,
    )

    memory_text = format_memories_for_prompt(memories)
    return {"retrieved_memories": memory_text}


def generate_response(state: AgentState) -> Dict:
    """节点：根据模式生成回复"""
    mode = state.get("response_mode", "deliberate")
    agent_id = state["agent_id"]
    game_state = state.get("game_state_context", "")
    memories = state.get("retrieved_memories", "（无相关记忆）")
    player_input = state["player_input"]

    # 构建 System Prompt
    sys_prompt = get_system_prompt(agent_id, game_state)
    full_system = f"""{sys_prompt}

## 相关记忆
{memories}

## 响应模式
{"[快速响应模式] 简短直接回复，不超过2句话。" if mode == "reflexive" else ""}
{"[标准响应模式] 正常回复，3-5句话。" if mode == "deliberate" else ""}
{"[深度思考模式] 仔细思考后回复，可以更详细，但不超过8句话。" if mode == "deep" else ""}
"""

    messages = [
        SystemMessage(content=full_system),
    ]

    # 追加历史消息（compress_context 已按 K 值截断，直接使用）
    history = state.get("messages", [])
    for msg in history:
        messages.append(msg)

    # 当前玩家输入
    messages.append(HumanMessage(content=player_input))

    # 选择 LLM
    if mode == "reflexive":
        # 反射式：不调 LLM，基于规则匹配
        return _reflexive_response(state)

    elif mode == "deliberate":
        try:
            llm = ChatOpenAI(
                model=config.model_deliberate,
                temperature=0.7,
                max_tokens=400,
                api_key=config.llm_api_key,
                base_url=config.llm_base_url,
            )
        except Exception:
            print("[WARN] LLM 初始化失败，降级到 Mock 模式")
            llm = MockLLM()
    elif mode == "deep":
        try:
            llm = ChatOpenAI(
                model=config.model_deep,
                temperature=0.8,
                max_tokens=800,
                api_key=config.llm_api_key,
                base_url=config.llm_base_url,
            )
        except Exception:
            print("[WARN] LLM 初始化失败，降级到 Mock 模式")
            llm = MockLLM()
    else:
        llm = MockLLM()

    # 调用 LLM
    start_time = time.time()
    try:
        response = llm.invoke(messages)
        elapsed = time.time() - start_time

        content = response.content
        usage = getattr(response, "usage_metadata", {})
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)

    except Exception as e:
        # API 调用失败，降级到 Mock
        print(f"[WARN] LLM 调用失败 ({e})，降级到 Mock 模式")
        mock = MockLLM()
        response = mock.invoke(messages)
        content = response.content
        usage = response.usage_metadata
        prompt_tokens = usage["input_tokens"]
        completion_tokens = usage["output_tokens"]
        elapsed = 0

    return {
        "response": content,
        "messages": [HumanMessage(content=player_input), AIMessage(content=content)],
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }


def _reflexive_response(state: AgentState) -> Dict:
    """反射式响应：不调 LLM，基于规则快速匹配"""
    player_input = state["player_input"]
    memories = state.get("retrieved_memories", "")

    # 从记忆中提取关键词辅助匹配
    memory_context = memories.lower() if memories else ""

    if any(kw in player_input for kw in ["氧气", "oxygen", "MOXIE", "moxie"]):
        reply = "氧气还能撑一阵，先处理眼前的问题。"
    elif any(kw in player_input for kw in ["通信", "地球", "contact", "earth", "signal"]):
        reply = "通信暂时没指望，靠自己。"
    elif any(kw in player_input for kw in ["修", "repair", "维修", "fix"]):
        reply = "能修就修，缺零件再说。"
    elif any(kw in player_input for kw in ["撤离", "逃生", "leave", "evacuate", "逃"]):
        reply = "走不了，留下来想办法。"
    elif any(kw in player_input for kw in ["危险", "danger", "紧急", "emergency"]):
        reply = "冷静。说具体情况。"
    elif any(kw in player_input for kw in ["你好", "hello", "hi", "在吗"]):
        reply = "在。说正事。"
    else:
        reply = "收到。说重点。"

    return {
        "response": reply,
        "messages": [HumanMessage(content=player_input), AIMessage(content=reply)],
        "prompt_tokens": len(player_input) // 4,
        "completion_tokens": len(reply) // 4,
    }


# ============================================================
# 构建 LangGraph 状态图
# ============================================================

def build_agent_graph():
    """构建状态图

    流程: retrieve_memories → compress_context → generate_response → write_episodic_memory → END
    """
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("retrieve_memories", retrieve_memories)
    graph.add_node("compress_context", compress_context)
    graph.add_node("generate_response", generate_response)
    graph.add_node("write_episodic_memory", write_episodic_memory)

    # 设置入口和边
    graph.set_entry_point("retrieve_memories")
    graph.add_edge("retrieve_memories", "compress_context")
    graph.add_edge("compress_context", "generate_response")
    graph.add_edge("generate_response", "write_episodic_memory")
    graph.add_edge("write_episodic_memory", END)

    # 编译（使用 SQLite checkpoint）
    # 注意：实际使用 SqliteSaver 需要 langgraph-checkpoint-sqlite
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        import sqlite3
        import os

        os.makedirs(os.path.dirname(config.checkpoint_db_path), exist_ok=True)
        conn = sqlite3.connect(config.checkpoint_db_path, check_same_thread=False)
        saver = SqliteSaver(conn)
        app = graph.compile(checkpointer=saver)
    except ImportError:
        print("[WARN] langgraph-checkpoint-sqlite 未安装，使用无 checkpoint 模式")
        app = graph.compile()
    except Exception as e:
        print(f"[WARN] SQLite checkpoint 初始化失败 ({e})，使用无 checkpoint 模式")
        app = graph.compile()

    return app


# ============================================================
# Agent 调用入口
# ============================================================

class Agent:
    """陈昊 Agent 封装"""

    def __init__(self, agent_id: str = "chen_hao"):
        self.agent_id = agent_id
        self.graph = build_agent_graph()
        self.thread_id = f"thread_{agent_id}"

    def chat(
        self,
        player_input: str,
        game_state: str = "",
        response_mode: str = "deliberate",
        thread_id: str = None,
    ) -> Dict:
        """
        与 Agent 对话

        Args:
            player_input: 玩家输入文本
            game_state: 游戏状态上下文字符串
            response_mode: reflexive / deliberate / deep
            thread_id: 会话线程 ID（用于多会话隔离）

        Returns:
            包含 response, prompt_tokens, completion_tokens 的字典
        """
        tid = thread_id or self.thread_id

        initial_state = {
            "messages": [],
            "player_input": player_input,
            "retrieved_memories": "",
            "agent_id": self.agent_id,
            "game_state_context": game_state,
            "response_mode": response_mode,
            "response": None,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "summary": "",
            "compressed_count": 0,
            "new_memory_id": "",
        }

        config_thread = {"configurable": {"thread_id": tid}}

        result = self.graph.invoke(initial_state, config=config_thread)

        return {
            "response": result.get("response", ""),
            "prompt_tokens": result.get("prompt_tokens", 0),
            "completion_tokens": result.get("completion_tokens", 0),
            "memories": result.get("retrieved_memories", ""),
            "compressed_count": result.get("compressed_count", 0),
            "messages": result.get("messages", []),
        }
