"""
交互式对话入口
启动后可实时与陈昊对话，测试 Agent 链路
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.config import config
from agent.graph import Agent
from agent.memory import MemoryStore
from agent.prompt import format_game_state
from data.seed_memories import SEED_MEMORIES_CHEN_HAO


GAME_STATE = """Sol 117 / 160
氧气储备: 42% (约43 Sol)
食物: 充足 (60 Sol)
电力: 65% (太阳能板部分受损)
水: 55% (回收系统正常)
成员士气: 偏低
压力指数: 7.2/10"""


def init():
    """初始化记忆库"""
    store = MemoryStore(
        persist_dir=config.chroma_persist_dir,
        collection_name=config.chroma_collection_name,
    )
    if store.count("chen_hao") == 0:
        print("[INFO] 初始化记忆库...")
        for mem in SEED_MEMORIES_CHEN_HAO:
            store.add_memory(
                agent_id=mem["agent_id"],
                content=mem["content"],
                memory_type=mem["memory_type"],
                timestamp=mem["timestamp"],
                importance=mem["importance"],
                tags=mem["tags"].split(","),
            )
        print(f"[INFO] 已加载 {len(SEED_MEMORIES_CHEN_HAO)} 条记忆\n")


def main():
    print("=" * 60)
    print("  赫拉克勒斯协议 - 陈昊 Agent 交互测试")
    print("  输入消息与指挥官对话，输入 :quit 退出")
    print("  输入 :mode <reflexive|deliberate|deep> 切换响应模式")
    print("  输入 :state 查看当前游戏状态")
    print("=" * 60)

    config.validate()
    init()

    agent = Agent(agent_id="chen_hao")
    mode = "deliberate"

    print(f"\n[当前模式: {mode}]")
    print("陈昊: 我是陈昊。情况你也看到了，60个Sol的氧气，没有通信，没有救援。")
    print("       有什么想法直接说，别浪费时间。\n")

    while True:
        try:
            user_input = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[退出]")
            break

        if not user_input:
            continue
        if user_input == ":quit":
            print("[退出]")
            break
        if user_input.startswith(":mode"):
            parts = user_input.split()
            if len(parts) >= 2 and parts[1] in ["reflexive", "deliberate", "deep"]:
                mode = parts[1]
                print(f"[模式切换: {mode}]\n")
            else:
                print(f"[无效模式，当前: {mode}]\n")
            continue
        if user_input == ":state":
            print(f"[游戏状态]\n{GAME_STATE}\n")
            continue

        start = time.time()
        result = agent.chat(
            player_input=user_input,
            game_state=GAME_STATE,
            response_mode=mode,
        )
        elapsed = time.time() - start

        response = result["response"]
        pt = result["prompt_tokens"]
        ct = result["completion_tokens"]

        print(f"\n陈昊> {response}")
        print(f"  ({elapsed:.2f}s | token: {pt}+{ct}={pt+ct})\n")


if __name__ == "__main__":
    main()
