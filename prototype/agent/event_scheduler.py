"""
事件调度器

职责：
1. 管理 active_triggers 列表（从 chapter YAML 加载）
2. Sol 推进时检查 trigger condition 是否满足
3. 满足则激活事件，供玩家选择
4. 玩家选择后 apply_effects 写入 GameState
5. TTL 自动失效过期触发器
6. 章节切换（stage_transition 条件求值）

依赖：
- chapter_loader.py：YAML 加载
- game_state.py：GameState / apply_effects / derive_current_state
- condition.py：安全求值器

作者：锐锋-核心开发工程师  日期：2026-08-03
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .chapter_loader import (
    load_chapter,
    extract_triggers,
    extract_fsm_nodes,
    extract_stage_transition,
    load_branch,
    extract_branch_events,
)
from .condition import evaluate_condition
from .game_state import GameState, apply_effects, derive_current_state, NpcState

logger = logging.getLogger(__name__)


# ============================================================
# 数据结构
# ============================================================

@dataclass
class Trigger:
    """触发器实例

    从 chapter YAML 的 temporary_keywords 加载。
    """
    trigger_id: str
    trigger_type: str          # sol_reached / state_match / event_fired / branch_choice
    condition: str            # 安全求值表达式
    description: str = ""
    keyword: str = ""         # 关联的关键词
    impact: Any = None         # impact 结构（玩家选项的 effects）
    ttl_expire_type: str = ""  # on_state_change / on_sol / permanent
    ttl_expire_condition: str = ""
    ttl_expire_sol: int = 0
    status: str = "inactive"   # inactive / active / fired / expired
    fired_sol: int = 0          # 触发的 Sol


@dataclass
class ActiveEvent:
    """已激活的事件（等待玩家选择）

    从 chapter YAML 的 temporary_keywords 或 branch events 加载。
    """
    event_id: str
    trigger_id: str
    description: str
    npc: str = ""               # 关联 NPC
    proposed_by: str = ""       # 提议者
    approval_required: str = "" # 需谁批准
    player_options: List[Dict[str, Any]] = field(default_factory=list)  # 玩家选项列表
    impact: Any = None          # 原始 impact 结构
    branch_id: str = ""         # 所属分支
    sol: int = 0                # 触发 Sol


@dataclass
class ChapterState:
    """章节运行时状态"""
    stage_id: str = "survival"
    sol: int = 1                # 章节内相对 Sol
    real_sol: int = 100          # 游戏内实际 Sol
    triggers: List[Trigger] = field(default_factory=list)
    active_events: List[ActiveEvent] = field(default_factory=list)
    fired_trigger_ids: Set[str] = field(default_factory=set)
    current_fsm_node: str = ""


# ============================================================
# EventScheduler 核心类
# ============================================================

class EventScheduler:
    """事件调度器

    生命周期：
    1. init_chapter(stage_id) → 加载章节 YAML，初始化 triggers
    2. advance_sol() → Sol +1，检查所有 trigger condition
    3. fire_trigger(trigger_id) → 激活事件，加入 active_events
    4. player_choose(event_id, option_index) → 玩家选择，apply_effects
    5. check_stage_transition() → 检查章节切换条件
    """

    def __init__(self, game_state: GameState):
        self.game_state = game_state
        self.chapter = ChapterState()
        self._chapter_yaml: Optional[Dict[str, Any]] = None
        self._branch_events: Dict[str, List[Dict[str, Any]]] = {}  # branch_id → events

    # --------------------------------------------------------
    # 章节初始化
    # --------------------------------------------------------

    def init_chapter(self, stage_id: str = "survival") -> None:
        """加载章节，初始化触发器列表

        Args:
            stage_id: survival / explore / build / climax
        """
        yaml_data = load_chapter(stage_id)
        if yaml_data is None:
            logger.error(f"无法加载章节: {stage_id}")
            return

        self._chapter_yaml = yaml_data
        self.chapter.stage_id = stage_id
        self.chapter.sol = yaml_data.get("sol_range", [1, 10])[0]
        self.chapter.real_sol = yaml_data.get("real_sol_range", [100, 110])[0]

        # 加载触发器
        raw_triggers = extract_triggers(yaml_data)
        self.chapter.triggers = []
        for rt in raw_triggers:
            t = Trigger(
                trigger_id=rt.get("trigger_id", ""),
                trigger_type=rt.get("trigger_type", ""),
                condition=rt.get("condition", ""),
                description=rt.get("description", ""),
                keyword=rt.get("keyword", ""),
                impact=rt.get("impact"),
                ttl_expire_type=rt.get("ttl", {}).get("expire_type", ""),
                ttl_expire_condition=rt.get("ttl", {}).get("expire_condition", ""),
                ttl_expire_sol=rt.get("ttl", {}).get("expire_sol", 0),
                status="inactive",
            )
            self.chapter.triggers.append(t)

        logger.info(
            f"章节初始化: {stage_id}, Sol {self.chapter.sol}, "
            f"{len(self.chapter.triggers)} 个触发器"
        )

    # --------------------------------------------------------
    # Sol 推进
    # --------------------------------------------------------

    def advance_sol(self) -> List[Trigger]:
        """推进一个 Sol，返回本次激活的触发器列表

        流程：
        1. sol += 1
        2. 检查 TTL 过期
        3. 检查所有 inactive 触发器的 condition
        4. 满足条件的触发器变为 active 状态

        Returns:
            本次激活的 Trigger 列表
        """
        self.chapter.sol += 1
        self.chapter.real_sol += 1

        # 1. TTL 过期检查
        self._check_ttl_expiry()

        # 2. Condition 检查
        ctx = self._build_condition_context()
        newly_fired: List[Trigger] = []

        for t in self.chapter.triggers:
            if t.status != "inactive":
                continue
            if t.trigger_id in self.chapter.fired_trigger_ids:
                continue

            try:
                if evaluate_condition(t.condition, ctx):
                    t.status = "active"
                    t.fired_sol = self.chapter.sol
                    newly_fired.append(t)
                    logger.info(f"触发器激活: {t.trigger_id} (Sol {self.chapter.sol})")
            except (ValueError, SyntaxError, TypeError) as e:
                logger.warning(f"触发器 condition 求值失败 {t.trigger_id}: {e}")

        return newly_fired

    def fire_trigger(self, trigger_id: str) -> Optional[ActiveEvent]:
        """手动激活触发器（如 FSM 节点 trigger_fires）

        Args:
            trigger_id: 触发器ID

        Returns:
            激活的 ActiveEvent，或 None
        """
        for t in self.chapter.triggers:
            if t.trigger_id == trigger_id and t.status == "inactive":
                t.status = "active"
                t.fired_sol = self.chapter.sol
                event = self._trigger_to_event(t)
                if event:
                    self.chapter.active_events.append(event)
                    self.chapter.fired_trigger_ids.add(trigger_id)
                    return event
        return None

    # --------------------------------------------------------
    # 玩家选择
    # --------------------------------------------------------

    def player_choose(self, event_id: str, option_index: int) -> Optional[Dict[str, Any]]:
        """玩家选择事件选项，apply_effects 写入 GameState

        Args:
            event_id: 事件ID
            option_index: 选项索引（0-based）

        Returns:
            效果摘要字典，或 None
        """
        event = None
        for e in self.chapter.active_events:
            if e.event_id == event_id:
                event = e
                break

        if event is None:
            logger.warning(f"事件未找到或已处理: {event_id}")
            return None

        if option_index < 0 or option_index >= len(event.player_options):
            logger.warning(f"选项索引越界: {option_index}/{len(event.player_options)}")
            return None

        option = event.player_options[option_index]
        effects = option.get("effects", {})

        # 应用效果到 GameState
        if effects:
            apply_effects(self.game_state, effects)
            # 重新派生 NPC 状态
            for npc_id in self.game_state.npc_states:
                derive_current_state(self.game_state.npc_states[npc_id])

        # 标记事件已处理
        event_description = event.description
        self.chapter.active_events.remove(event)

        # 标记关联触发器已 fired
        if event.trigger_id:
            for t in self.chapter.triggers:
                if t.trigger_id == event.trigger_id:
                    t.status = "fired"
                    break

        logger.info(f"玩家选择事件 {event_id} 选项 {option_index}: {option.get('label', '')}")

        return {
            "event_id": event_id,
            "option_label": option.get("label", ""),
            "effects_applied": bool(effects),
            "leads_to": option.get("leads_to", ""),
        }

    # --------------------------------------------------------
    # 章节切换
    # --------------------------------------------------------

    def check_stage_transition(self) -> Optional[str]:
        """检查是否满足章节切换条件

        Returns:
            下一章节ID，或 None（未满足）
        """
        if self._chapter_yaml is None:
            return None

        trans = extract_stage_transition(self._chapter_yaml)
        condition = trans.get("transition_condition", "")
        next_stage = trans.get("next_stage_id", "")

        if not condition or not next_stage:
            return None

        ctx = self._build_condition_context()
        try:
            if evaluate_condition(condition, ctx):
                logger.info(f"章节切换: {self.chapter.stage_id} → {next_stage}")
                return next_stage
        except (ValueError, SyntaxError, TypeError) as e:
            logger.warning(f"章节切换条件求值失败: {e}")

        return None

    # --------------------------------------------------------
    # 查询
    # --------------------------------------------------------

    def get_active_events(self) -> List[ActiveEvent]:
        """获取当前等待玩家选择的事件列表"""
        return self.chapter.active_events

    def get_pending_triggers(self) -> List[Trigger]:
        """获取已激活但未处理的事件触发器"""
        return [t for t in self.chapter.triggers if t.status == "active"]

    def get_chapter_info(self) -> Dict[str, Any]:
        """获取章节信息摘要"""
        return {
            "stage_id": self.chapter.stage_id,
            "sol": self.chapter.sol,
            "real_sol": self.chapter.real_sol,
            "total_triggers": len(self.chapter.triggers),
            "active_triggers": len([t for t in self.chapter.triggers if t.status == "active"]),
            "fired_triggers": len(self.chapter.fired_trigger_ids),
            "pending_events": len(self.chapter.active_events),
        }

    # --------------------------------------------------------
    # 内部方法
    # --------------------------------------------------------

    def _build_condition_context(self) -> Dict[str, Any]:
        """构建 condition 求值上下文

        从 GameState 派生 condition 表达式所需的变量。
        同时支持两种字段引用风格：
        - 点号风格：viktor.trust >= 30
        - 下划线风格：viktor_trust >= 30

        YAML condition 表达式常见字段：
        - sol / real_sol / signal_quality / athena_status
        - npc.stress / npc.morale / npc.trust / npc.energy / npc.current_state
        - oxygen / power / water / food / parts
        - morale_avg / stress_avg / trust_avg / all_crew_alive
        - 特殊状态标记：moxie2_status / comm_array_main / rover_alpha_status 等
        """
        gs = self.game_state
        ctx: Dict[str, Any] = {
            "sol": self.chapter.sol,
            "real_sol": self.chapter.real_sol,
            "signal_quality": gs.signal_quality,
            "athena_status": gs.athena_status,
            "player_connected": True,  # 玩家已接入
        }

        # NPC 状态（点号风格 + 下划线风格）
        for npc_id, npc in gs.npc_states.items():
            npc_dict = {
                "stress": npc.stress,
                "morale": npc.morale,
                "trust": npc.trust_in_player,
                "trust_in_player": npc.trust_in_player,
                "energy": npc.energy,
                "current_state": npc.current_state,
            }
            ctx[npc_id] = npc_dict

            # 下划线风格别名：viktor_trust / viktor_stress / viktor_morale 等
            ctx[f"{npc_id}_stress"] = npc.stress
            ctx[f"{npc_id}_morale"] = npc.morale
            ctx[f"{npc_id}_trust"] = npc.trust_in_player
            ctx[f"{npc_id}_energy"] = npc.energy
            ctx[f"{npc_id}_current_state"] = npc.current_state

        # 资源
        ctx["oxygen"] = gs.resources.get("oxygen", 0)
        ctx["power"] = gs.resources.get("power", 0)
        ctx["water"] = gs.resources.get("water", 0)
        ctx["food"] = gs.resources.get("food", 0)
        ctx["parts"] = gs.resources.get("parts", 0)

        # 派生值
        ctx["morale_avg"] = sum(n.morale for n in gs.npc_states.values()) / max(len(gs.npc_states), 1)
        ctx["stress_avg"] = sum(n.stress for n in gs.npc_states.values()) / max(len(gs.npc_states), 1)
        ctx["trust_avg"] = sum(n.trust_in_player for n in gs.npc_states.values()) / max(len(gs.npc_states), 1)
        ctx["all_crew_alive"] = True  # 简化

        # 特殊状态标记（默认值，后续从 state_flags 更新）
        ctx.setdefault("moxie2_status", "damaged")
        ctx.setdefault("comm_array_main", "damaged")
        ctx.setdefault("rover_alpha_status", "damaged")
        ctx.setdefault("greenhouse_status", "not_built")
        ctx.setdefault("tutorial_choice", "")
        ctx.setdefault("branch_fork_visible", False)
        ctx.setdefault("atmosphere_anomaly_detected", False)

        # 从 GameState 的 state_flags 合并（如果有）
        if hasattr(gs, "state_flags") and isinstance(gs.state_flags, dict):
            ctx.update(gs.state_flags)

        return ctx

    def _check_ttl_expiry(self) -> None:
        """检查 TTL 过期，标记过期触发器"""
        ctx = self._build_condition_context()
        for t in self.chapter.triggers:
            if t.status != "active":
                continue
            if not t.ttl_expire_type:
                continue

            if t.ttl_expire_type == "on_sol" and self.chapter.sol >= t.ttl_expire_sol:
                t.status = "expired"
                logger.info(f"触发器过期 (TTL on_sol): {t.trigger_id}")
            elif t.ttl_expire_type == "on_state_change" and t.ttl_expire_condition:
                try:
                    if evaluate_condition(t.ttl_expire_condition, ctx):
                        t.status = "expired"
                        logger.info(f"触发器过期 (TTL on_state_change): {t.trigger_id}")
                except (ValueError, SyntaxError, TypeError):
                    pass

    def _trigger_to_event(self, trigger: Trigger) -> Optional[ActiveEvent]:
        """将触发器转换为可交互事件"""
        # 从 impact 提取玩家选项
        player_options: List[Dict[str, Any]] = []
        impact = trigger.impact
        if isinstance(impact, list):
            for item in impact:
                if isinstance(item, dict):
                    if "if_approved" in item:
                        player_options.append({
                            "label": "批准",
                            "effects": item["if_approved"],
                            "leads_to": item.get("leads_to", ""),
                        })
                    elif "if_rejected" in item:
                        player_options.append({
                            "label": "拒绝",
                            "effects": item["if_rejected"],
                            "leads_to": item.get("leads_to", ""),
                        })
        elif isinstance(impact, dict):
            if "if_approved" in impact:
                player_options.append({
                    "label": "批准",
                    "effects": impact["if_approved"],
                })
            if "if_rejected" in impact:
                player_options.append({
                    "label": "拒绝",
                    "effects": impact["if_rejected"],
                })

        # 如果没有 impact 结构，至少给一个空选项
        if not player_options:
            player_options = [{"label": "确认", "effects": {}}]

        return ActiveEvent(
            event_id=f"evt_{trigger.trigger_id}",
            trigger_id=trigger.trigger_id,
            description=trigger.description or trigger.keyword,
            player_options=player_options,
            impact=impact,
            sol=self.chapter.sol,
        )


# ============================================================
# 模块自测
# ============================================================

def _self_test():
    """自测"""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from agent.game_state import create_initial_game_state

    print("=== event_scheduler.py 自测 ===\n")

    # 1. 初始化
    gs = create_initial_game_state()
    scheduler = EventScheduler(gs)

    # 用 explore 章节（survival 有 YAML 语法错误）
    scheduler.init_chapter("explore")
    info = scheduler.get_chapter_info()
    print(f"--- 章节信息 ---")
    print(f"  stage_id: {info['stage_id']}")
    print(f"  sol: {info['sol']}")
    print(f"  total_triggers: {info['total_triggers']}")
    print(f"  active_triggers: {info['active_triggers']}")

    # 2. Sol 推进
    print(f"\n--- Sol 推进测试 ---")
    for i in range(5):
        fired = scheduler.advance_sol()
        if fired:
            for t in fired:
                print(f"  Sol {scheduler.chapter.sol}: 触发 {t.trigger_id} ({t.description[:30]})")
        else:
            print(f"  Sol {scheduler.chapter.sol}: 无触发")

    # 3. 条件上下文
    ctx = scheduler._build_condition_context()
    print(f"\n--- 条件上下文 ---")
    print(f"  sol: {ctx['sol']}")
    print(f"  morale_avg: {ctx['morale_avg']:.3f}")
    print(f"  stress_avg: {ctx['stress_avg']:.3f}")
    print(f"  trust_avg: {ctx['trust_avg']:.3f}")
    print(f"  oxygen: {ctx['oxygen']}")
    print(f"  signal_quality: {ctx['signal_quality']}")

    # 4. 章节切换检查
    next_stage = scheduler.check_stage_transition()
    print(f"\n--- 章节切换 ---")
    print(f"  next_stage: {next_stage or '（未满足条件）'}")

    # 5. 加载分支事件
    print(f"\n--- 分支事件加载 ---")
    from agent.chapter_loader import list_branches, load_branch, extract_branch_events
    branches = list_branches()
    for bid in branches:
        bd = load_branch(bid)
        if bd is None:
            continue
        events = extract_branch_events(bd)
        print(f"  分支 {bid} ({bd.get('branch_name')}): {len(events)} 事件")
        if events:
            evt = events[0]
            print(f"    首个事件: {evt['event_id']}")
            print(f"    描述: {evt.get('description', '')[:50]}")
            print(f"    玩家选项: {len(evt.get('player_options', []))} 个")
            for i, opt in enumerate(evt.get("player_options", [])):
                print(f"      [{i}] {opt.get('label', '')}")

    print("\n=== 全部测试通过 ===")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    _self_test()
