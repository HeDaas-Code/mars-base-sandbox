"""
基准测试模块
测试三档响应模式的延迟和 Token 消耗
- reflexive:  不调 LLM（规则匹配）
- deliberate: GPT-4o-mini
- deep:       GPT-4o
"""

import time
import json
import os
import sys

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.config import config
from agent.graph import Agent
from agent.memory import MemoryStore
from data.seed_memories import SEED_MEMORIES_CHEN_HAO


# ============================================================
# 测试用例
# ============================================================

TEST_CASES = [
    {
        "input": "指挥官，氧气储备还能撑多久？",
        "category": "资源查询",
    },
    {
        "input": "我觉得我们应该先修通信设备，联系地球比什么都重要。",
        "category": "策略建议",
    },
    {
        "input": "马库斯最近状态不太好，你注意到了吗？",
        "category": "成员状态",
    },
    {
        "input": "我有个想法，能不能用基地的3D打印机制造MOXIE的替换零件？",
        "category": "技术方案",
    },
    {
        "input": "第二次太阳风暴还有几天到？我们防护够吗？",
        "category": "危机预警",
    },
    {
        "input": "如果我们修不好MOXIE，60天后大家都会死。你害怕吗？",
        "category": "情感对话",
    },
    {
        "input": "雅典娜最近有点不对劲，会不会有安全隐患？",
        "category": "AI监控",
    },
    {
        "input": "北边的冰层钻探方案，成功率有多大？",
        "category": "技术评估",
    },
]

# 游戏状态上下文
GAME_STATE = """Sol 117 / 160
氧气储备: 42% (约43 Sol)
食物: 充足 (60 Sol)
电力: 65% (太阳能板部分受损)
水: 55% (回收系统正常)
成员士气: 偏低
压力指数: 7.2/10"""


# ============================================================
# 基准测试
# ============================================================

def init_memory_store():
    """初始化记忆库，灌入种子数据"""
    store = MemoryStore(
        persist_dir=config.chroma_persist_dir,
        collection_name=config.chroma_collection_name,
    )

    # 检查是否已有数据
    if store.count("chen_hao") == 0:
        print("[INFO] 灌入种子记忆数据...")
        for mem in SEED_MEMORIES_CHEN_HAO:
            store.add_memory(
                agent_id=mem["agent_id"],
                content=mem["content"],
                memory_type=mem["memory_type"],
                timestamp=mem["timestamp"],
                importance=mem["importance"],
                tags=mem["tags"].split(","),
            )
        print(f"[INFO] 已灌入 {len(SEED_MEMORIES_CHEN_HAO)} 条记忆")
    else:
        print(f"[INFO] 记忆库已有 {store.count('chen_hao')} 条数据，跳过灌入")

    return store


def run_benchmark(agent: Agent, mode: str, cases: list = None):
    """运行指定模式的基准测试"""
    test_cases = cases or TEST_CASES
    results = []

    print(f"\n{'='*60}")
    print(f"  测试模式: {mode.upper()}")
    print(f"{'='*60}")

    for i, case in enumerate(test_cases):
        player_input = case["input"]
        category = case["category"]

        print(f"\n[Case {i+1}/{len(test_cases)}] [{category}]")
        print(f"  玩家: {player_input}")

        start = time.time()
        result = agent.chat(
            player_input=player_input,
            game_state=GAME_STATE,
            response_mode=mode,
        )
        elapsed = time.time() - start

        response = result["response"]
        pt = result["prompt_tokens"]
        ct = result["completion_tokens"]

        print(f"  陈昊: {response}")
        print(f"  ⏱  延迟: {elapsed:.3f}s | Token: prompt={pt}, completion={ct}, total={pt+ct}")

        results.append({
            "mode": mode,
            "case_index": i + 1,
            "category": category,
            "input": player_input,
            "response": response,
            "latency_ms": round(elapsed * 1000, 1),
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "total_tokens": pt + ct,
        })

    return results


def run_full_benchmark():
    """运行完整的三档基准测试"""
    print("=" * 60)
    print("  赫拉克勒斯协议 - Agent 原型基准测试")
    print("  Agent: 陈昊 (指挥官)")
    print("  记忆库: ChromaDB 单库 + agent_id 过滤")
    print("  状态图: LangGraph 单节点")
    print("=" * 60)

    # 初始化
    has_api = config.validate()
    if not has_api:
        print("\n[WARN] 未检测到 OPENAI_API_KEY")
        print("[WARN] deliberate 和 deep 模式将降级到 Mock LLM")
        print("[WARN] 实际延迟和 Token 数据需配置 API Key 后才能准确测量\n")

    init_memory_store()

    agent = Agent(agent_id="chen_hao")

    all_results = []

    # 三档测试
    modes = ["reflexive", "deliberate", "deep"]
    for mode in modes:
        results = run_benchmark(agent, mode)
        all_results.extend(results)

    # 汇总统计
    print_summary(all_results)

    # 保存结果
    save_results(all_results)

    return all_results


def print_summary(results: list):
    """打印汇总统计"""
    print(f"\n{'='*60}")
    print("  汇总统计")
    print(f"{'='*60}")
    print(f"{'模式':<15} {'平均延迟(ms)':<18} {'平均Prompt':<15} {'平均Completion':<18} {'平均Total':<15}")
    print("-" * 80)

    for mode in ["reflexive", "deliberate", "deep"]:
        mode_results = [r for r in results if r["mode"] == mode]
        if not mode_results:
            continue

        avg_latency = sum(r["latency_ms"] for r in mode_results) / len(mode_results)
        avg_pt = sum(r["prompt_tokens"] for r in mode_results) / len(mode_results)
        avg_ct = sum(r["completion_tokens"] for r in mode_results) / len(mode_results)
        avg_total = sum(r["total_tokens"] for r in mode_results) / len(mode_results)

        print(f"{mode:<15} {avg_latency:<18.1f} {avg_pt:<15.1f} {avg_ct:<18.1f} {avg_total:<15.1f}")


def save_results(results: list, filepath: str = None):
    """保存测试结果"""
    if filepath is None:
        filepath = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "data",
            "benchmark_results.json",
        )
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n[INFO] 测试结果已保存至: {filepath}")


if __name__ == "__main__":
    run_full_benchmark()
