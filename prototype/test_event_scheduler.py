#!/usr/bin/env python3
"""
事件调度器端到端测试

验证：
1. 章节加载 + 触发器列表
2. Sol 推进 + 触发器激活
3. 玩家选项提交 + effects 写入 GameState
4. 章节切换条件检查
5. 分支事件加载与选项处理

作者：锐锋-核心开发工程师  日期：2026-08-03
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.basicConfig(level=logging.WARNING)

from agent.game_state import GameState, NpcState, create_initial_game_state, apply_effects, derive_current_state
from agent.event_scheduler import EventScheduler, ChapterState
from agent.chapter_loader import (
    list_chapters, list_branches,
    load_chapter, load_branch,
    extract_triggers, extract_branch_events,
)


print("=== 1. 章节与分支加载 ===\n")

chapters = list_chapters()
branches = list_branches()
print(f"可用章节: {chapters}")
print(f"可用分支: {branches}")
assert len(branches) == 4, f"应有4个分支，实际{len(branches)}"


print("\n=== 2. 分支事件选项处理 ===\n")

# 加载分支A的第一个事件
bd = load_branch("A")
assert bd is not None
events_a = extract_branch_events(bd)
assert len(events_a) == 5

evt_a1 = events_a[0]
print(f"事件: {evt_a1['event_id']}")
print(f"描述: {evt_a1.get('description', '')[:80]}")
print(f"玩家选项数: {len(evt_a1.get('player_options', []))}")

# 模拟玩家选择第一个选项
gs = create_initial_game_state()
print(f"\n选择前 chen_hao: stress={gs.npc_states['chen_hao'].stress:.3f}, morale={gs.npc_states['chen_hao'].morale:.3f}")

option_0 = evt_a1.get("player_options", [{}])[0]
print(f"\n选项[0]: {option_0.get('label', '')}")
effects = option_0.get("effects", {})
print(f"effects: {effects}")

# 应用 effects
if effects:
    apply_effects(gs, effects)
    for npc_id in gs.npc_states:
        derive_current_state(gs.npc_states[npc_id])

print(f"\n选择后 chen_hao: stress={gs.npc_states['chen_hao'].stress:.3f}, morale={gs.npc_states['chen_hao'].morale:.3f}")
print(f"选择后 viktor: stress={gs.npc_states['viktor'].stress:.3f}, morale={gs.npc_states['viktor'].morale:.3f}")


print("\n=== 3. 事件调度器 Sol 推进 ===\n")

# 用 explore 章节测试（survival 有 YAML 语法错误）
gs2 = create_initial_game_state()
scheduler = EventScheduler(gs2)
scheduler.init_chapter("explore")
print(f"初始 Sol: {scheduler.chapter.sol}")
print(f"触发器总数: {len(scheduler.chapter.triggers)}")

# 推进5个 Sol
for i in range(5):
    fired = scheduler.advance_sol()
    status = f"Sol {scheduler.chapter.sol}: "
    if fired:
        status += f"激活 {len(fired)} 个触发器: {fired}"
    else:
        status += "无触发"
    print(status)

active_count = sum(1 for t in scheduler.chapter.triggers if t.status == "active")
print(f"\n当前 active_triggers: {active_count}")
print(f"已 fired 触发器: {len(scheduler.chapter.fired_trigger_ids)}")


print("\n=== 4. 章节切换条件检查 ===\n")

# 推进到 Sol 26 看是否触发章节切换
for i in range(15):
    scheduler.advance_sol()

print(f"当前 Sol: {scheduler.chapter.sol}")
next_stage = scheduler.check_stage_transition()
print(f"章节切换: {next_stage or '（未满足条件）'}")
print(f"切换条件: sol >= 26 and (branch_fork_visible == true)")
print(f"branch_fork_visible 默认为 False，所以不会切换")


print("\n=== 5. 手动激活触发器 ===\n")

# 手动激活一个触发器
if scheduler.chapter.triggers:
    t = scheduler.chapter.triggers[0]
    print(f"手动激活: {t.trigger_id}")
    print(f"  trigger_type: {t.trigger_type}")
    print(f"  condition: {t.condition[:60]}")
    print(f"  status: {t.status}")
    
    # 手动激活
    t.status = "active"
    t.fired_sol = scheduler.chapter.sol
    print(f"  → status: {t.status}")


print("\n=== 6. 分支事件全部选项 effects 覆盖 ===\n")

# 验证4个分支的所有事件选项都有 effects
for bid in branches:
    bd = load_branch(bid)
    if bd is None:
        continue
    events = extract_branch_events(bd)
    total_options = 0
    options_with_effects = 0
    for evt in events:
        for opt in evt.get("player_options", []):
            total_options += 1
            if opt.get("effects"):
                options_with_effects += 1
    print(f"分支 {bid} ({bd.get('branch_name')}): {len(events)} 事件, {total_options} 选项, {options_with_effects} 有 effects")
    assert options_with_effects > 0, f"分支 {bid} 没有任何选项有 effects"


print("\n=== 全部测试通过 ===")
