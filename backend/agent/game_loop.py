"""
游戏主循环（7 阶段 FSM）

依据《game_loop_rules_spec_v1.0》实现玩家每回合的 7 阶段处理：
  P1 通信接收  → 解析玩家输入（自然语言 / 情感指令前缀）
  P2 信息分析  → 构建 condition 上下文 + 游戏状态摘要
  P3 决策制定  → 检查事件触发器（由 EventScheduler 维护）
  P4 指令下达  → 调度 NPC 回复 / 事件下发
  P5 执行演算  → 应用情感 delta + Agent.chat + apply_sol_decay（仅 :sol 时）
  P6 结果反馈  → 构建 agent_message / story_event / option_result 信封
  P7 事件触发  → 检查章节切换 / 结局判定

同时提供 meta 命令处理（:sol / :state / :npc / :branch / :mode / :help / :skip）
与 option_select 回路。

依赖：game_state / event_scheduler / graph.Agent / ws_adapter_v2
作者：锐锋-核心开发工程师  日期：2026-08-04
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .game_state import (
    GameState,
    NpcState,
    apply_effects,
    derive_current_state,
    build_emotion_hint,
    get_emotional_command_delta,
    check_resource_crisis,
    apply_sol_decay,
)
from .event_scheduler import EventScheduler, ActiveEvent
from .condition import evaluate_condition
from .protocol import (
    build_command_response as _proto_command_response,
    build_system_message as _proto_system_message,
    build_story_event as _proto_story_event,
    build_option_result as _proto_option_result,
    build_option_result_error as _proto_option_result_error,
    seg as _proto_seg,
)

logger = logging.getLogger(__name__)


# ============================================================
# 常量
# ============================================================

# 情感指令前缀 → subtype（8d §3.5）
_EMOTION_PREFIXES = {
    "#soothe": "soothe",
    "#empathize": "empathize",
    "#command": "command",
    "#blame": "blame",
    "#smalltalk": "smalltalk",
    "#安抚": "soothe",
    "#共情": "empathize",
    "#命令": "command",
    "#责备": "blame",
    "#闲聊": "smalltalk",
}

# meta 命令前缀
_META_PREFIX = ":"

# NPC 显示名（用于剧情事件 title）
_NPC_DISPLAY = {
    "chen_hao": "陈昊",
    "sophia": "索菲亚",
    "viktor": "维克托",
    "aisha": "艾莎",
    "marcus": "马库斯",
    "lin_ruoxi": "林若曦",
    "athena": "雅典娜",
    "courier": "信使",
}

# 结局简表（climax §5.6）：condition → ending_id
# 数据驱动：condition 为声明式布尔表达式字符串，由 condition.evaluate_condition 求值
# 命中即终局；按列表顺序评估，首个命中者生效
# Phase 2 引擎化后可从题材包 YAML 加载此表
_ENDING_TABLE = [
    # (ending_id, display_name, condition_str)
    ("E7_athena_awakening", "E7 雅典娜觉醒", 'athena_consciousness_flag == "awakening"'),
    ("E1_hercules_return", "E1 赫拉克勒斯归航", "all_crew_alive == true and sol >= 60 and oxygen > 30"),
    ("E5_last_signal", "E5 最后的信号", "oxygen <= 0"),
    ("E6_collapse", "E6 守墓人", "morale_avg < 0.2"),
    ("E2_mars_child", 'E2 火星之子', 'greenhouse_status == "built"'),
]


# ============================================================
# GameLoop
# ============================================================

class GameLoop:
    """游戏主循环

    生命周期：
    1. init(game_state, scheduler, chat_fn) → 注入依赖
    2. start() → 加载 survival 章节
    3. tick(player_input, agent_id, response_mode) → 玩家自然语言回合
    4. handle_meta(command, args) → meta 命令
    5. handle_option_select(event_id, option_id) → 选项回路
    """

    def __init__(
        self,
        game_state: GameState,
        scheduler: EventScheduler,
        chat_fn=None,
    ):
        self.game_state = game_state
        self.scheduler = scheduler
        # chat_fn(player_input, agent_id, response_mode, npc_state_vars) → agent_message dict
        # 由 ws_adapter 注入，复用其 emotion_hint/latency/context_summary 构建
        self.chat_fn = chat_fn

        self.active_npc: str = "chen_hao"
        self.response_mode: str = "deliberate"
        self.ending: Optional[Dict[str, Any]] = None
        self._started = False

        # Phase 2 引擎化：可注入的注册表（缺省时回退到硬编码 _ENDING_TABLE）
        self.ending_registry = None    # EndingRegistry 实例
        self.persona_registry = None   # PersonaRegistry 实例

    # --------------------------------------------------------
    # 启动
    # --------------------------------------------------------

    def start(self, stage_id: str = "survival") -> None:
        """加载起始章节"""
        self.scheduler.init_chapter(stage_id)
        # 同步 game_state.sol 到章节 real_sol
        self.game_state.sol = self.scheduler.chapter.real_sol
        self._started = True
        logger.info(f"GameLoop 启动: 章节={stage_id}, Sol={self.game_state.sol}")

    # --------------------------------------------------------
    # P1-P7 主循环（自然语言回合）
    # --------------------------------------------------------

    def tick(
        self,
        player_input: str,
        agent_id: Optional[str] = None,
        response_mode: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """处理一回合玩家自然语言输入

        Returns:
            待发送的消息信封列表（按顺序）
        """
        if self.ending is not None:
            return [self._build_system_message("游戏已结束。输入 :restart 重新开始。")]

        if not self._started:
            self.start()

        target_npc = agent_id or self.active_npc
        mode = response_mode or self.response_mode

        messages: List[Dict[str, Any]] = []

        # === P1 通信接收 + 情感指令解析 ===
        emotion_subtype, clean_input = self._parse_emotion_prefix(player_input)

        # === P5 执行演算（前置）：应用情感 delta ===
        if emotion_subtype:
            self._apply_emotion_to_npc(target_npc, emotion_subtype, messages)

        # === P2 信息分析：构建 npc_state_vars + game_state 字符串 ===
        npc_state_vars = self._build_npc_state_vars(target_npc)
        # clean_input 可能为空（纯情感指令无文本）→ 给一个占位
        chat_input = clean_input if clean_input else "（玩家向你投来关注的目光）"

        # === P4/P5 指令下达 + 执行：调用 Agent.chat ===
        if self.chat_fn is not None:
            try:
                agent_msg = self.chat_fn(chat_input, target_npc, mode, npc_state_vars)
                messages.append(agent_msg)
            except Exception as e:
                logger.error(f"chat_fn 执行失败: {e}", exc_info=True)
                messages.append(self._build_system_message(f"[通信异常] {e}"))
        else:
            messages.append(self._build_system_message("[GameLoop] chat_fn 未注入"))

        # === P7 事件触发：检查待处理事件（非 advance_sol 触发的） ===
        # 自然语言回合不主动推进 Sol，但若 scheduler 已有待选事件，提示玩家
        # （事件由 :sol 推进或 FSM 触发产生，这里只做透传提示）

        return messages

    # --------------------------------------------------------
    # meta 命令
    # --------------------------------------------------------

    def handle_meta(self, command: str, args: List[str]) -> Dict[str, Any]:
        """处理 : 开头的 meta 命令

        Returns:
            command_response 信封
        """
        if self.ending is not None and command not in ("restart", "help"):
            return self._build_command_response(
                [self._seg("游戏已结束。输入 :restart 重新开始。")], None
            )

        if command == "sol":
            return self._cmd_advance_sol()
        elif command == "state":
            return self._cmd_state()
        elif command == "npc":
            return self._cmd_npc(args)
        elif command == "branch":
            return self._cmd_branch()
        elif command == "mode":
            return self._cmd_mode(args)
        elif command == "skip":
            return self._cmd_skip()
        elif command == "restart":
            return self._cmd_restart()
        elif command == "help":
            return self._cmd_help()
        else:
            return self._build_command_response(
                [self._seg(f"未知命令: :{command}。输入 :help 查看可用指令。")], None
            )

    # --------------------------------------------------------
    # option_select 回路
    # --------------------------------------------------------

    def handle_option_select(
        self,
        event_id: str,
        option_id: str,
        followup_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """处理玩家选项选择 → 返回 option_result 信封

        option_id 格式: "opt_<index>"
        """
        if self.ending is not None:
            return self._build_system_message("游戏已结束。")

        # 解析 option_index
        try:
            option_index = int(option_id.replace("opt_", ""))
        except (ValueError, AttributeError):
            return self._build_option_result_error(event_id, "无效的 option_id")

        # 调用 scheduler 应用效果
        result = self.scheduler.player_choose(event_id, option_index)
        if result is None:
            return self._build_option_result_error(event_id, "事件未找到或选项无效")

        # === P7 事件触发：检查结局 ===
        ending = self._check_ending()
        if ending is not None:
            self.ending = ending
            # 返回 option_result + 后续 ending 消息（前端 event-panel 渲染 ending 字段）
            return self._build_option_result(event_id, option_id, result, ending=ending)

        # 检查 leads_to：是否有后续事件
        leads_to = result.get("leads_to", "")
        return self._build_option_result(event_id, option_id, result, leads_to=leads_to)

    # --------------------------------------------------------
    # :sol 推进
    # --------------------------------------------------------

    def _cmd_advance_sol(self) -> Dict[str, Any]:
        """:sol → 推进一个 Sol，返回章节信息 + 新激活事件"""
        if not self._started:
            self.start()

        # P5: apply_sol_decay（资源/NPC 衰减）
        apply_sol_decay(self.game_state)

        # 推进 Sol + 检查触发器
        fired = self.scheduler.advance_sol()
        # 同步 game_state.sol
        self.game_state.sol = self.scheduler.chapter.real_sol

        segments = [self._seg(f"═══ Sol {self.scheduler.chapter.real_sol} 开始 ═══\n")]
        info = self.scheduler.get_chapter_info()
        segments.append(self._seg(
            f"章节: {info['stage_id']}  进度: {info['fired_triggers']}/{info['total_triggers']} 触发器已激活\n"
        ))

        # 资源危机检查
        crisis = check_resource_crisis(self.game_state)
        if crisis:
            segments.append(self._seg(
                f"⚠ 资源危机: " + " ".join(f"{k}={v:.0f}%" for k, v in crisis.items()) + "\n"
            ))

        # 结局检查
        ending = self._check_ending()
        if ending is not None:
            self.ending = ending
            segments.append(self._seg(f"\n◆◆◆ 结局达成: {ending['display_name']} ◆◆◆\n"))
            return self._build_command_response(segments, {
                "sol": self.game_state.sol,
                "ending": ending,
            })

        # 章节切换检查
        next_stage = self.scheduler.check_stage_transition()
        if next_stage:
            segments.append(self._seg(f"\n▶ 章节切换: → {next_stage}\n"))
            self.scheduler.init_chapter(next_stage)
            self.game_state.sol = self.scheduler.chapter.real_sol

        data = {
            "sol": self.game_state.sol,
            "stage_id": self.scheduler.chapter.stage_id,
            "fired_count": len(fired),
            "pending_events": len(self.scheduler.get_active_events()),
        }

        msg = self._build_command_response(segments, data)

        # 若有新激活事件，附带 story_event 消息（由 ws_server 连发）
        active = self.scheduler.get_active_events()
        if active:
            msg["_followup_story_events"] = [self._build_story_event(e) for e in active]

        return msg

    # --------------------------------------------------------
    # 其他 meta 命令
    # --------------------------------------------------------

    def _cmd_state(self) -> Dict[str, Any]:
        gs = self.game_state
        segs = [self._seg(f"═══ 基地状态 Sol {gs.sol} ═══\n")]
        segs.append(self._seg("资源:\n"))
        for r in ("oxygen", "power", "water", "food", "parts"):
            rv = gs.resources.get(r, {})
            segs.append(self._seg(f"  {r}: {rv.get('current', 0)}/{rv.get('max', 100)} (rate {rv.get('rate', 0)})\n"))
        segs.append(self._seg("成员:\n"))
        for nid, npc in gs.npc_states.items():
            segs.append(self._seg(
                f"  {_NPC_DISPLAY.get(nid, nid)}: 士气{npc.morale:.2f} 压力{npc.stress:.2f} 信任{npc.trust_in_player:.0f} 状态{npc.current_state}\n"
            ))
        segs.append(self._seg(f"信号质量: {gs.signal_quality}%  雅典娜: {gs.athena_status}\n"))
        if self.scheduler.chapter.stage_id:
            info = self.scheduler.get_chapter_info()
            segs.append(self._seg(f"章节: {info['stage_id']}  待处理事件: {info['pending_events']}\n"))
        return self._build_command_response(segs, {
            "sol": gs.sol,
            "resources": {k: v.get("current", 0) for k, v in gs.resources.items()},
            "signal_quality": gs.signal_quality,
        })

    def _cmd_npc(self, args: List[str]) -> Dict[str, Any]:
        if not args:
            return self._build_command_response(
                [self._seg(f"当前对话: {_NPC_DISPLAY.get(self.active_npc, self.active_npc)}\n"),
                 self._seg("可用: chen_hao / sophia / viktor / aisha / marcus / lin_ruoxi\n")],
                None,
            )
        target = args[0].lower()
        if target in _NPC_DISPLAY:
            self.active_npc = target
            return self._build_command_response(
                [self._seg(f"已切换到 {_NPC_DISPLAY[target]}。说点什么？\n")],
                {"active_npc": target},
            )
        return self._build_command_response(
            [self._seg(f"未知 NPC: {target}\n")], None,
        )

    def _cmd_branch(self) -> Dict[str, Any]:
        info = self.scheduler.get_chapter_info()
        return self._build_command_response(
            [self._seg(f"章节: {info['stage_id']}  Sol {info['sol']} (real Sol {info['real_sol']})\n"),
             self._seg(f"触发器: {info['fired_triggers']}/{info['total_triggers']} 已激活  待处理事件: {info['pending_events']}\n")],
            info,
        )

    def _cmd_mode(self, args: List[str]) -> Dict[str, Any]:
        if not args or args[0] not in ("reflexive", "deliberate", "deep"):
            return self._build_command_response(
                [self._seg(f"当前模式: {self.response_mode}\n可用: reflexive / deliberate / deep\n")],
                None,
            )
        self.response_mode = args[0]
        return self._build_command_response(
            [self._seg(f"响应模式 → {self.response_mode}\n")], {"mode": self.response_mode},
        )

    def _cmd_skip(self) -> Dict[str, Any]:
        """跳过当前所有待处理事件（标记为 fired）"""
        active = self.scheduler.get_active_events()
        for e in list(active):
            self.scheduler.chapter.active_events.remove(e)
            for t in self.scheduler.chapter.triggers:
                if t.trigger_id == e.trigger_id:
                    t.status = "fired"
                    break
        return self._build_command_response(
            [self._seg(f"已跳过 {len(active)} 个待处理事件。\n")], {"skipped": len(active)},
        )

    def _cmd_restart(self) -> Dict[str, Any]:
        from .game_state import create_initial_game_state
        new_gs = create_initial_game_state()
        self.game_state.__dict__.update(new_gs.__dict__)
        self.scheduler.game_state = self.game_state
        self.scheduler.init_chapter("survival")
        self.game_state.sol = self.scheduler.chapter.real_sol
        self.ending = None
        self.active_npc = "chen_hao"
        self.response_mode = "deliberate"
        self._started = True
        return self._build_command_response(
            [self._seg("◆ 游戏已重置，进入 Sol 100 survival 章节 ◆\n")], {"sol": self.game_state.sol},
        )

    def _cmd_help(self) -> Dict[str, Any]:
        segs = [
            self._seg("═══ meta 命令（以 : 开头）═══\n"),
            self._seg("  :sol          推进一个 Sol（触发事件检查 + 资源衰减）\n"),
            self._seg("  :state        查看基地与成员状态\n"),
            self._seg("  :npc <id>     切换对话目标（chen_hao/sophia/viktor/aisha/marcus/lin_ruoxi）\n"),
            self._seg("  :branch       查看章节进度与触发器\n"),
            self._seg("  :mode <m>     切换响应模式（reflexive/deliberate/deep）\n"),
            self._seg("  :skip         跳过所有待处理事件\n"),
            self._seg("  :restart      重置游戏\n"),
            self._seg("  :help         显示此帮助\n"),
            self._seg("\n═══ 情感指令（前缀，影响 NPC 心理）═══\n"),
            self._seg("  #soothe <text>    安抚（stress-, morale+, trust+）\n"),
            self._seg("  #empathize <text> 共情（trust++）\n"),
            self._seg("  #command <text>   命令（stress+, trust-）\n"),
            self._seg("  #blame <text>     责备（stress++, morale--, trust--）\n"),
            self._seg("  #smalltalk <text> 闲聊（轻微正向）\n"),
            self._seg("\n═══ 自然语言 ═══\n"),
            self._seg("  直接输入文字即与当前 NPC 对话。事件选项通过事件面板点击选择。\n"),
        ]
        return self._build_command_response(segs, None)

    # --------------------------------------------------------
    # 内部：情感指令
    # --------------------------------------------------------

    def _parse_emotion_prefix(self, text: str) -> Tuple[Optional[str], str]:
        """解析情感指令前缀，返回 (subtype, clean_text)"""
        stripped = text.strip()
        for prefix, subtype in _EMOTION_PREFIXES.items():
            if stripped.startswith(prefix):
                rest = stripped[len(prefix):].strip()
                return subtype, rest
        return None, stripped

    def _apply_emotion_to_npc(
        self, npc_id: str, subtype: str, messages: List[Dict[str, Any]]
    ) -> None:
        """应用情感指令 delta 到指定 NPC"""
        # AI sender 不受情感影响
        if npc_id in ("athena", "courier"):
            return
        npc = self.game_state.npc_states.get(npc_id)
        if npc is None:
            return
        delta = get_emotional_command_delta(subtype)
        npc.stress = max(0.0, min(1.0, npc.stress + delta["stress_delta"]))
        npc.morale = max(0.0, min(1.0, npc.morale + delta["morale_delta"]))
        npc.trust_in_player = max(0, min(100, npc.trust_in_player + delta["trust_delta"]))
        derive_current_state(npc)
        logger.info(
            f"情感指令 {subtype} → {npc_id}: "
            f"stress{delta['stress_delta']:+.2f} morale{delta['morale_delta']:+.2f} trust{delta['trust_delta']:+.0f}"
        )

    # --------------------------------------------------------
    # 内部：状态构建
    # --------------------------------------------------------

    def _build_npc_state_vars(self, npc_id: str) -> Dict[str, Any]:
        """构建 NPC 心理状态变量，用于渲染 Jinja2 人格模板"""
        npc = self.game_state.npc_states.get(npc_id)
        if npc is None:
            return {}
        stage = self.scheduler.chapter.stage_id if self._started else "survival"
        return {
            "stress": round(npc.stress, 2),
            "morale": round(npc.morale, 2),
            "trust_in_player": round(npc.trust_in_player / 100.0, 2),  # 模板期望 0-1
            "stage": stage,
            "recent_events": "",  # 可扩展：从 fired_triggers 摘要
        }

    def _build_condition_context(self) -> Dict[str, Any]:
        """构建结局判定上下文（复用 scheduler 的上下文构建逻辑）"""
        return self.scheduler._build_condition_context()

    # --------------------------------------------------------
    # 内部：结局判定
    # --------------------------------------------------------

    def _check_ending(self) -> Optional[Dict[str, Any]]:
        """检查是否命中结局

        Phase 2 引擎化：优先使用注入的 EndingRegistry（题材包可配置），
        回退到硬编码 _ENDING_TABLE（向后兼容）。

        Returns:
            {ending_id, display_name} 或 None
        """
        ctx = self._build_condition_context()

        # 优先走 EndingRegistry（Phase 2）
        if self.ending_registry is not None and len(self.ending_registry) > 0:
            result = self.ending_registry.evaluate(ctx)
            if result is not None:
                return {"ending_id": result.ending_id, "display_name": result.display_name}
            return None

        # 回退：硬编码 _ENDING_TABLE（向后兼容）
        for ending_id, display_name, cond_str in _ENDING_TABLE:
            try:
                if evaluate_condition(cond_str, ctx):
                    logger.info(f"结局命中: {ending_id}")
                    return {"ending_id": ending_id, "display_name": display_name}
            except (ValueError, SyntaxError, TypeError) as e:
                logger.warning(f"结局判定异常 {ending_id}: {e}")
        return None

    # --------------------------------------------------------
    # 内部：消息信封构建（委托 protocol.py 统一构造中心）
    # --------------------------------------------------------

    def _seg(self, text: str, protected: bool = True) -> Dict[str, str]:
        return _proto_seg(text, protected=protected)

    def _build_command_response(self, segments: List[Dict], data: Optional[Dict]) -> Dict[str, Any]:
        return _proto_command_response(segments, data)

    def _build_system_message(self, text: str) -> Dict[str, Any]:
        return _proto_system_message(text)

    def _build_story_event(self, event: ActiveEvent) -> Dict[str, Any]:
        """构建 story_event 信封（v1.2 §11 S→C）"""
        options = []
        for i, opt in enumerate(event.player_options):
            options.append({
                "option_id": f"opt_{i}",
                "label": opt.get("label", f"选项{i+1}"),
                "visible": True,
            })
        sq = self.game_state.signal_quality
        return _proto_story_event(
            event_id=event.event_id,
            chapter_id=self.scheduler.chapter.stage_id,
            node_index=event.sol,
            title=event.title or _NPC_DISPLAY.get(event.npc, "事件"),
            npc=event.npc or event.proposed_by or "athena",
            description=event.description,
            options=options,
            signal_quality_pct=sq,
            latency_ms=500 + (100 - sq) * 50,
        )

    def _build_option_result(
        self,
        event_id: str,
        option_id: str,
        result: Dict[str, Any],
        leads_to: str = "",
        ending: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """构建 option_result 信封（v1.2 §11 S→C）"""
        effects_summary = result.get("effects_summary", "") or f"已选择: {result.get('option_label', '')}"
        return _proto_option_result(
            event_id=event_id,
            option_id=option_id,
            effects_summary=effects_summary,
            signal_quality_pct=self.game_state.signal_quality,
            leads_to=leads_to,
            ending=ending,
        )

    def _build_option_result_error(self, event_id: str, reason: str) -> Dict[str, Any]:
        return _proto_option_result_error(
            event_id=event_id,
            reason=reason,
            signal_quality_pct=self.game_state.signal_quality,
        )
