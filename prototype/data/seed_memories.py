"""
种子记忆数据

- chen_hao：硬编码在 SEED_MEMORIES_CHEN_HAO（12条，基于蔚蓝 v1.1 方案）
- 其他5人（sophia/viktor/aisha/marcus/lin_ruoxi）：通过 persona.py 从蔚蓝交付的 YAML 加载

调用方通过 get_all_seed_memories() 获取全量种子记忆字典，按 agent_id 分组注入 ChromaDB。

作者：锐锋-核心开发工程师
更新：2026-08-03 接入 persona.py，支持5个 NPC 的 YAML 种子记忆
"""

from typing import Dict, List

# ============================================================
# chen_hao 硬编码种子记忆（无 YAML）
# ============================================================

SEED_MEMORIES_CHEN_HAO = [
    {
        "agent_id": "chen_hao",
        "content": "Sol 100 太阳风暴来袭时，我正在地质实验室分析岩芯样本。警报响起的那一刻，我第一时间冲向了指挥控制室，启动了基地的紧急防护协议。",
        "memory_type": "episodic",
        "timestamp": "Sol-100",
        "importance": 0.95,
        "tags": "太阳风暴,紧急响应,指挥",
    },
    {
        "agent_id": "chen_hao",
        "content": "MOXIE-2 氧气生成器在风暴中彻底损毁，主通信阵列的天线也被吹断。撤离飞船的导航系统因电磁脉冲烧毁。我们失去了与地球的联系。",
        "memory_type": "episodic",
        "timestamp": "Sol-100",
        "importance": 0.98,
        "tags": "MOXIE损毁,通信中断,撤离飞船,设备损失",
    },
    {
        "agent_id": "chen_hao",
        "content": "氧气储备按当前6人消耗速度计算，大约还能维持60个Sol。必须在此之前修复MOXIE或找到替代氧气来源，否则全员窒息。",
        "memory_type": "semantic",
        "timestamp": "Sol-101",
        "importance": 1.0,
        "tags": "氧气危机,生存倒计时,60Sol",
    },
    {
        "agent_id": "chen_hao",
        "content": "基地还有5名成员加上我：我（陈昊，指挥官/行星地质学家）、索菲亚（生物化学家/生命保障系统）、维克托（机械工程师/设备维护）、艾莎（通讯与AI系统工程师）、马库斯（医疗官/心理评估员）、林若曦（大气物理学家/气象观测员）。另有基地AI系统雅典娜辅助决策。每人都有各自的专长和弱点。",
        "memory_type": "semantic",
        "timestamp": "Sol-100",
        "importance": 0.9,
        "tags": "团队成员,人员构成,专长",
    },
    {
        "agent_id": "chen_hao",
        "content": "雅典娜是基地的AI管理系统，基于最新的LLM架构。风暴后她的行为偶尔出现异常，可能核心模块受损。需要留意，但暂时不影响她的基本功能。",
        "memory_type": "semantic",
        "timestamp": "Sol-102",
        "importance": 0.7,
        "tags": "雅典娜,AI系统,异常行为",
    },
    {
        "agent_id": "chen_hao",
        "content": "妻子林雪的预产期在Sol 120左右。每次想到她我就无法集中注意力。我必须活着回去，见到孩子。这是我做一切决策的底线。",
        "memory_type": "episodic",
        "timestamp": "Sol-103",
        "importance": 0.85,
        "tags": "妻子,待产,个人动机,情感",
    },
    {
        "agent_id": "chen_hao",
        "content": "基地仓库还有少量3D打印材料，可以用来制造一些替换零件。但钛合金和碳纤维管材严重不足，修复大型设备很困难。",
        "memory_type": "semantic",
        "timestamp": "Sol-101",
        "importance": 0.8,
        "tags": "物资库存,3D打印,材料短缺",
    },
    {
        "agent_id": "chen_hao",
        "content": "Sol 105，维克托报告备用通信模块可能修复，但需要一个功率放大器。我们手头有两个备用的，都不太确定是否完好。值得一试。",
        "memory_type": "episodic",
        "timestamp": "Sol-105",
        "importance": 0.75,
        "tags": "通信修复,维克托,功率放大器,希望",
    },
    {
        "agent_id": "chen_hao",
        "content": "索菲亚提议利用基地温室中的藻类培养箱作为备用氧气来源，效率虽然低但可能给我们多争取10-15个Sol的缓冲时间。方案可行，已安排她负责。",
        "memory_type": "episodic",
        "timestamp": "Sol-104",
        "importance": 0.8,
        "tags": "藻类制氧,索菲亚,备用方案,缓冲时间",
    },
    {
        "agent_id": "chen_hao",
        "content": "马库斯情绪低落，他已经第三天没怎么说话了。他是医疗官兼心理评估员，风暴摧毁了基地大量医疗储备。我需要找个时间和他谈谈，但现在不是时候。",
        "memory_type": "episodic",
        "timestamp": "Sol-107",
        "importance": 0.6,
        "tags": "马库斯,士气,心理状态,物资损失",
    },
    {
        "agent_id": "chen_hao",
        "content": "Sol 108，探测到第二次太阳风暴的前兆信号，预计Sol 112到达。这次规模较小，但基地防护已经受损，必须提前做好准备。",
        "memory_type": "episodic",
        "timestamp": "Sol-108",
        "importance": 0.9,
        "tags": "第二次风暴,预警,Sol-112,防护准备",
    },
    {
        "agent_id": "chen_hao",
        "content": "北面冰层下方可能存在地下水冰层。如果能在60Sol内钻探取水，电解水可以同时产生氧气和氢气。这是目前最可行的长期生存方案。",
        "memory_type": "semantic",
        "timestamp": "Sol-106",
        "importance": 0.85,
        "tags": "地下水冰,钻探,电解水,长期方案",
    },
]


# ============================================================
# 5个 NPC 的种子记忆从 YAML 加载
# ============================================================

# YAML 驱动的 NPC 列表（chen_hao 除外）
_YAML_NPCS: List[str] = ["sophia", "viktor", "aisha", "marcus", "lin_ruoxi"]


def _load_yaml_seed_memories() -> Dict[str, List[dict]]:
    """从 persona.py 加载5个 NPC 的种子记忆

    Returns:
        按 agent_id 分组的种子记忆字典
    """
    # 延迟导入避免循环依赖
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from agent.persona import load_seed_memories

    result: Dict[str, List[dict]] = {}
    for npc_id in _YAML_NPCS:
        memories = load_seed_memories(npc_id)
        if memories:
            result[npc_id] = memories
    return result


# ============================================================
# 统一入口：获取全量种子记忆
# ============================================================

def get_all_seed_memories() -> Dict[str, List[dict]]:
    """获取所有 NPC 的种子记忆

    合并 chen_hao 硬编码 + 5人 YAML 加载的记忆。

    Returns:
        按 agent_id 分组的种子记忆字典：
        {
            "chen_hao": [...12条...],
            "sophia": [...6条...],
            "viktor": [...6条...],
            "aisha": [...7条...],
            "marcus": [...7条...],
            "lin_ruoxi": [...10条...],
        }
    """
    all_memories: Dict[str, List[dict]] = {
        "chen_hao": SEED_MEMORIES_CHEN_HAO.copy(),
    }
    # 合并 YAML 加载的5人记忆
    yaml_memories = _load_yaml_seed_memories()
    all_memories.update(yaml_memories)
    return all_memories


# ============================================================
# 模块自测
# ============================================================

if __name__ == "__main__":
    print("=== seed_memories.py 自测 ===\n")
    all_mems = get_all_seed_memories()
    total = 0
    for npc_id, memories in all_mems.items():
        print(f"--- {npc_id}: {len(memories)} 条 ---")
        for m in memories[:2]:  # 只打印前2条
            print(f"  [{m['memory_type']}] {m['content'][:60]}...")
        if len(memories) > 2:
            print(f"  ... 其余 {len(memories) - 2} 条略")
        total += len(memories)
    print(f"\n总计: {len(all_mems)} 个 NPC, {total} 条种子记忆")
    print("\n=== 自测通过 ===")
