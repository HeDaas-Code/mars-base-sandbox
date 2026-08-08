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
from .game_state import GameState, apply_effects, derive_current_state

logger = logging.getLogger(__name__)


# ============================================================
# 数据结构
# ============================================================

@dataclass
class Trigger:
    """触发器实例"""
    trigger_id: str
    trigger_type: str          # sol_reached / state_match / event_fired / branch_choice
    condition: str
    description: str = ""
    keyword: str = ""
    impact: Any = None
    ttl_expire_type: str = ""
    ttl_expire_condition: str = ""
    ttl_expire_sol: int = 0
    status: str = "inactive"   # inactive / active / fired / expired
    fired_sol: int = 0


@dataclass
class ActiveEvent:
    """已激活的事件（等待玩家选择）"""
    event_id: str
    trigger_id: str
    description: str
    npc: str = ""
    proposed_by: str = ""
    approval_required: str = ""
    player_options: List[Dict[str, Any]] = field(default_factory=list)
    impact: Any = None
    branch_id: str = ""
    sol: int = 0
    title: str = ""
    followup: Optional[Dict[str, Any]] = None


@dataclass
class ChapterState:
    """章节运行时状态"""
    stage_id: str = "survival"
    sol: int = 1
    real_sol: int = 100
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
        self._branch_events: Dict[str, List[Dict[str, Any]]] = {}

    # --------------------------------------------------------
    # 章节初始化
    # --------------------------------------------------------

    def init_chapter(self, stage_id: str = "survival") -> None:
        """加载章节，初始化触发器列表"""
        yaml_data = load_chapter(stage_id)
        if yaml_data is None:
            logger.error(f"无法加载章节: {stage_id}")
            return

        self._chapter_yaml = yaml_data
        self.chapter.stage_id = stage_id
        self.chapter.sol = yaml_data.get("sol_range", [1, 10])[0]
        self.chapter.real_sol = yaml_data.get("real_sol_range", [100, 110])[0]

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

        # 章节加载后立即检查初始触发器（如 sol == 1 的触发器）
        self._check_initial_triggers()

    def _check_initial_triggers(self) -> None:
        """章节初始化后检查满足条件的初始触发器"""
        ctx = self._build_condition_context()
        for t in self.chapter.triggers:
            if t.status != "inactive":
                continue
            if t.trigger_id in self.chapter.fired_trigger_ids:
                continue
            try:
                if evaluate_condition(t.condition, ctx):
                    t.status = "active"
                    t.fired_sol = self.chapter.sol
                    evt = self._trigger_to_event(t)
                    if evt:
                        self.chapter.active_events.append(evt)
                    logger.info(f"初始触发器激活: {t.trigger_id} (Sol {self.chapter.sol})")
            except (ValueError, SyntaxError, TypeError) as e:
                logger.warning(f"初始触发器 condition 求值失败 {t.trigger_id}: {e}")

    # --------------------------------------------------------
    # Sol 推进
    # --------------------------------------------------------

    def advance_sol(self) -> List[Trigger]:
        """推进一个 Sol，返回本次激活的触发器列表"""
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

        # 自动把新激活的触发器转为 ActiveEvent（供前端展示）
        for t in newly_fired:
            evt = self._trigger_to_event(t)
            if evt is not None:
                self.chapter.active_events.append(evt)

        return newly_fired

    def fire_trigger(self, trigger_id: str) -> Optional[ActiveEvent]:
        """手动激活触发器（如 FSM 节点 trigger_fires）"""
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

        Returns:
            效果摘要字典，含 leads_to / option_label / effects_applied，
            或 None（事件未找到 / 索引越界）
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

        if effects:
            apply_effects(self.game_state, effects)
            for npc_id in self.game_state.npc_states:
                derive_current_state(self.game_state.npc_states[npc_id])

        self.chapter.active_events.remove(event)

        if event.trigger_id:
            self.chapter.fired_trigger_ids.add(event.trigger_id)
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
            "effects_summary": option.get("effects_summary", ""),
        }

    # --------------------------------------------------------
    # 章节切换
    # --------------------------------------------------------

    def check_stage_transition(self) -> Optional[str]:
        """检查是否满足章节切换条件"""
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
        return self.chapter.active_events

    def get_pending_triggers(self) -> List[Trigger]:
        return [t for t in self.chapter.triggers if t.status == "active"]

    def get_chapter_info(self) -> Dict[str, Any]:
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

        支持两种字段引用风格：
        - 点号风格：viktor.trust >= 30
        - 下划线风格：viktor_trust >= 30
        """
        gs = self.game_state
        ctx: Dict[str, Any] = {
            "sol": self.chapter.sol,
            "real_sol": self.chapter.real_sol,
            "signal_quality": gs.signal_quality,
            "athena_status": gs.athena_status,
            "athena_consciousness_flag": gs.athena_consciousness_flag,
            "player_connected": True,
        }

        # NPC 状态（点号风格 + 下划线风格）
        # stress/morale 存储为 0-1 浮点，YAML condition 使用 0-100 量纲（如 stress > 50）
        # 因此下划线风格的 *_stress/*_morale 乘以 100 传递
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
            ctx[f"{npc_id}_stress"] = round(npc.stress * 100)
            ctx[f"{npc_id}_morale"] = round(npc.morale * 100)
            ctx[f"{npc_id}_trust"] = npc.trust_in_player
            ctx[f"{npc_id}_energy"] = npc.energy
            ctx[f"{npc_id}_current_state"] = npc.current_state

        # 资源（取 current 值，而非整个 dict，避免 condition 拿到 dict 比较）
        for res_name in ("oxygen", "power", "water", "food", "parts"):
            res = gs.resources.get(res_name)
            if isinstance(res, dict):
                ctx[res_name] = res.get("current", 0)
                ctx[f"{res_name}_L"] = res.get("current", 0)  # 兼容 oxygen_L 等别名
            else:
                ctx[res_name] = 0
                ctx[f"{res_name}_L"] = 0

        # 派生值
        n = max(len(gs.npc_states), 1)
        ctx["morale_avg"] = sum(x.morale for x in gs.npc_states.values()) / n
        ctx["stress_avg"] = sum(x.stress for x in gs.npc_states.values()) / n
        ctx["trust_avg"] = sum(x.trust_in_player for x in gs.npc_states.values()) / n
        ctx["all_crew_alive"] = True

        # 特殊状态标记默认值（后续从 state_flags 更新）
        ctx.setdefault("moxie2_status", "damaged")
        ctx.setdefault("comm_array_main", "damaged")
        ctx.setdefault("rover_alpha_status", "damaged")
        ctx.setdefault("greenhouse_status", "not_built")
        ctx.setdefault("tutorial_choice", "")
        ctx.setdefault("branch_fork_visible", False)
        ctx.setdefault("atmosphere_anomaly_detected", False)
        ctx.setdefault("athena_proposal_count", 0)
        ctx.setdefault("linruoxi_self_blame", "inactive")
        ctx.setdefault("exploration_radius", 0)
        ctx.setdefault("comm_priority", "normal")
        ctx.setdefault("decision_first_made", False)
        ctx.setdefault("crew_workload", gs.crew_workload)
        ctx.setdefault("base_integrity", gs.base_integrity)

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
                            "effects_summary": item.get("design_intent", ""),
                        })
                    elif "if_rejected" in item:
                        player_options.append({
                            "label": "拒绝",
                            "effects": item["if_rejected"],
                            "leads_to": item.get("leads_to", ""),
                            "effects_summary": item.get("design_intent", ""),
                        })
        elif isinstance(impact, dict):
            if "if_approved" in impact:
                player_options.append({
                    "label": "批准",
                    "effects": impact["if_approved"],
                    "effects_summary": impact.get("design_intent", ""),
                })
            if "if_rejected" in impact:
                player_options.append({
                    "label": "拒绝",
                    "effects": impact["if_rejected"],
                    "effects_summary": impact.get("design_intent", ""),
                })

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
