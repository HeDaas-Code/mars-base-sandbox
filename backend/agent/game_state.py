"""
游戏世界状态模块 - 赫拉克勒斯协议
定义 GameState / NpcState 及事件系统写入接口

职责：
1. 定义 NpcState（NPC 心理状态）与 GameState（世界级游戏状态）数据结构
2. 实现事件 effects 写入逻辑（apply_effects）
3. 实现 emotion_label 派生（derive_emotion_label / build_emotion_hint）
4. 实现 state_machine 状态推导（derive_current_state）
5. 实现资源危机检测与 Sol 自然衰减

设计依据：
- 蔚蓝《NPC 状态字段标准化定义文档 v1.0》（8d 文档）
- 云逸《技术架构设计方案 v2.0》§4.4 / §8.4
- 云逸确认：GameState（世界级）与 AgentState（对话级）分离，不合并 state.py

作者：锐锋-核心开发工程师  日期：2026-08-02
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agent.condition import evaluate_condition

logger = logging.getLogger(__name__)


# ============================================================
# 常量定义
# ============================================================

# AI 类 sender 不进入 npc_states（8d 文档 §5.1）
AI_SENDERS: frozenset[str] = frozenset({"athena", "courier"})

# trust_in_player 统一使用 0-100 整数量纲（与 YAML condition 和 emotional delta 对齐）
# stress/morale/energy 保持 0-1 浮点（emotion_label 查表依赖）
TRUST_MIN: int = 0
TRUST_MAX: int = 100

# 数值字段上下限
CLAMP_MIN: float = 0.0
CLAMP_MAX: float = 1.0


# ============================================================
# emotion_label 二维映射表（8d 文档 §4.2）
# ============================================================

# stress（行）× morale（列），5×5 共 25 个标签
EMOTION_LABEL_TABLE: List[List[str]] = [
    # stress [0.0, 0.2)
    ["numb", "low", "calm", "steady", "upbeat"],
    # stress [0.2, 0.4)
    ["bleak", "weary", "focused", "engaged", "cheerful"],
    # stress [0.4, 0.6)
    ["hollow", "tense", "alert", "determined", "optimistic"],
    # stress [0.6, 0.8)
    ["despair", "strained", "anxious", "strained_optimism", "defiant"],
    # stress [0.8, 1.0]
    ["breakdown", "panic", "frantic", "manic", "breakdown"],
]

EMOTION_LABEL_STRESS_BUCKETS: List[float] = [0.2, 0.4, 0.6, 0.8]
EMOTION_LABEL_MORALE_BUCKETS: List[float] = [0.2, 0.4, 0.6, 0.8]


def _bucket(value: float, thresholds: List[float]) -> int:
    """将 0-1 浮点值映射到桶索引（0~4）

    Args:
        value: 0.0-1.0 浮点值
        thresholds: 桶边界列表，如 [0.2, 0.4, 0.6, 0.8]

    Returns:
        桶索引 0-4
    """
    for i, threshold in enumerate(thresholds):
        if value < threshold:
            return i
    return len(thresholds)


def derive_emotion_label(stress: float, morale: float) -> str:
    """从 stress/morale 二维查表派生情绪标签（8d 文档 §4.3）

    Args:
        stress: 0.0-1.0 压力值
        morale: 0.0-1.0 士气值

    Returns:
        情绪标签字符串（25 种之一）
    """
    s_bucket = _bucket(stress, EMOTION_LABEL_STRESS_BUCKETS)
    m_bucket = _bucket(morale, EMOTION_LABEL_MORALE_BUCKETS)
    return EMOTION_LABEL_TABLE[s_bucket][m_bucket]


# ============================================================
# NPC 初始状态（引用 NPC YAML initial_state，8d 文档 §1.3）
# ============================================================

# 从 NPC YAML psychology.initial_state 提取的初始值
# chen_hao 无 YAML，按 8d 文档 §1.3 注释用架构 v2.0 §2.3 baseline 占位
# lin_ruoxi 待单独交付，暂用中性值占位
NPC_INITIAL_STATES: Dict[str, Dict[str, float]] = {
    "chen_hao": {"stress": 0.3, "morale": 0.6, "trust_in_player": 40, "energy": 0.7},
    "sophia": {"stress": 0.4, "morale": 0.55, "trust_in_player": 35, "energy": 0.8},
    "viktor": {"stress": 0.5, "morale": 0.5, "trust_in_player": 30, "energy": 0.7},
    "aisha": {"stress": 0.45, "morale": 0.55, "trust_in_player": 55, "energy": 0.85},
    "marcus": {"stress": 0.35, "morale": 0.65, "trust_in_player": 40, "energy": 0.55},
    "lin_ruoxi": {"stress": 0.4, "morale": 0.45, "trust_in_player": 35, "energy": 0.7},  # 蔚蓝 YAML v1.0
}

# 从 NPC YAML psychology.state_machine 提取的状态机定义
# 用于 derive_current_state 遍历匹配
NPC_STATE_MACHINES: Dict[str, List[Dict[str, Any]]] = {
    "sophia": [
        {"state": "stable", "condition": "true"},
        {"state": "stable", "condition": "stress < 0.5 and morale > 0.5"},
        {"state": "strained", "condition": "stress >= 0.5 and stress <= 0.7"},
        {"state": "cracking", "condition": "stress >= 0.7 or morale < 0.3"},
        {"state": "breakdown", "condition": "stress >= 0.85"},
    ],
    "viktor": [
        {"state": "stoic", "condition": "true"},
        {"state": "stoic", "condition": "stress < 0.6 and morale > 0.4"},
        {"state": "irritated", "condition": "stress >= 0.6 and stress <= 0.75"},
        {"state": "defiant", "condition": "stress >= 0.75"},
        {"state": "collapse", "condition": "stress >= 0.88"},
    ],
    "aisha": [
        {"state": "energetic", "condition": "true"},
        {"state": "energetic", "condition": "stress < 0.5 and morale > 0.5"},
        {"state": "anxious", "condition": "stress >= 0.5 and stress <= 0.7"},
        {"state": "defensive", "condition": "stress >= 0.7"},
        {"state": "breakdown", "condition": "stress >= 0.88"},
    ],
    "marcus": [
        {"state": "composed", "condition": "true"},
        {"state": "composed", "condition": "stress < 0.45"},
        {"state": "masking", "condition": "stress >= 0.45 and stress <= 0.65"},
        {"state": "cracking", "condition": "stress >= 0.65"},
        {"state": "crisis", "condition": "stress >= 0.8"},
    ],
    "chen_hao": [
        {"state": "composed", "condition": "true"},
        {"state": "composed", "condition": "stress < 0.5 and morale > 0.5"},
        {"state": "strained", "condition": "stress >= 0.5 and stress <= 0.7"},
        {"state": "stressed", "condition": "stress >= 0.7"},
        {"state": "overwhelmed", "condition": "stress >= 0.85"},
    ],
    "lin_ruoxi": [
        # 蔚蓝 YAML v1.0 — 四档：quiet / withdrawn / breaking / breakdown
        {"state": "quiet", "condition": "true"},
        {"state": "quiet", "condition": "stress < 0.5 and morale >= 0.35"},
        {"state": "withdrawn", "condition": "stress >= 0.5 and stress <= 0.7"},
        {"state": "breaking", "condition": "stress >= 0.7"},
        {"state": "breakdown", "condition": "stress >= 0.85"},
    ],
}


# ============================================================
# 资源危机阈值表（8d 文档 §3.2）
# ============================================================

@dataclass
class ResourceThreshold:
    """资源危机阈值定义"""
    resource: str           # 资源名（oxygen/power/water/food/parts）
    threshold: float        # 触发阈值（百分比）
    stress_delta: float     # 触发时 stress 变化量
    description: str        # 描述


RESOURCE_THRESHOLDS: List[ResourceThreshold] = [
    ResourceThreshold("oxygen", 20.0, 0.10, "氧气低于 20%"),
    ResourceThreshold("oxygen", 10.0, 0.15, "氧气低于 10%"),
    ResourceThreshold("power", 15.0, 0.08, "电力低于 15%"),
    ResourceThreshold("water", 15.0, 0.06, "水低于 15%"),
    ResourceThreshold("food", 10.0, 0.05, "食物低于 10%"),
    ResourceThreshold("parts", 3.0, 0.05, "备用件低于 3 单位"),
]

# 资源责任区映射（8d 文档 §3.2 注：责任区 NPC stress 翻倍）
RESOURCE_OWNERS: Dict[str, str] = {
    "oxygen": "sophia",    # 索菲亚负责氧气/生命保障
    "power": "viktor",     # 维克托负责电力/工程
    "water": "sophia",
    "food": "sophia",
    "parts": "viktor",
}


# ============================================================
# Sol 自然衰减/恢复表（8d 文档 §3.3）
# ============================================================

SOL_DECAY_DEFAULTS: Dict[str, float] = {
    "stress": +0.02,        # 困境持续累积微小压力
    "morale": -0.01,        # 长期困境缓慢侵蚀士气
    "trust_in_player": 0.0, # 信任只在事件中变化，不自然衰减
}

SOL_DECAY_CONDITIONAL: List[Dict[str, Any]] = [
    {
        "field": "stress",
        "delta": -0.05,
        "condition": "sol_success_progress",  # 若 Sol 内有成功任务推进
        "description": "成功缓解压力",
    },
    {
        "field": "morale",
        "delta": +0.05,
        "condition": "resource_self_sufficiency_up",  # 若资源自给率较上周提升
        "description": "进展带来希望",
    },
    {
        "field": "energy",
        "delta": -0.05,
        "condition": "crew_workload_high_3sol",  # 若 crew_workload > 0.7 持续 ≥3 Sol
        "description": "过劳衰减",
    },
    {
        "field": "energy",
        "delta": +0.1,
        "condition": "crew_workload_low",  # 若 crew_workload < 0.3
        "description": "休整恢复",
    },
]


# ============================================================
# NpcState 数据结构（8d 文档 §7.2）
# ============================================================

@dataclass
class NpcState:
    """NPC 心理状态

    对应 8d 文档 §1.2 字段定义：
    - stress: 压力值 0.0-1.0（0=无压力 1=崩溃临界）
    - morale: 士气值 0.0-1.0（0=绝望 1=饱满）
    - trust_in_player: 对玩家信任度 0-100（整数，与 YAML condition 对齐）
    - energy: 体力/精力 0.0-1.0（0=衰竭 1=充沛）
    - current_state: 派生字段，由 state_machine 推导
    - state_machine: 状态阈值转移规则（引用 NPC YAML）
    """

    stress: float = 0.5
    morale: float = 0.5
    trust_in_player: int = 40
    energy: float = 0.7
    current_state: str = "stable"
    state_machine: List[Dict[str, Any]] = field(default_factory=list)

    def clamp(self) -> None:
        """数值字段限制在合法范围（8d 文档 §7.2）"""
        self.stress = max(CLAMP_MIN, min(CLAMP_MAX, self.stress))
        self.morale = max(CLAMP_MIN, min(CLAMP_MAX, self.morale))
        self.trust_in_player = max(TRUST_MIN, min(TRUST_MAX, int(self.trust_in_player)))
        self.energy = max(CLAMP_MIN, min(CLAMP_MAX, self.energy))

    def to_dict(self) -> Dict[str, Any]:
        """转换为可序列化字典"""
        return {
            "stress": round(self.stress, 4),
            "morale": round(self.morale, 4),
            "trust_in_player": self.trust_in_player,
            "energy": round(self.energy, 4),
            "current_state": self.current_state,
        }


# ============================================================
# GameState 数据结构（8d 文档 §7.1）
# ============================================================

@dataclass
class GameState:
    """游戏世界状态（世界级，与 AgentState 对话级分离）

    8d 文档 §7.1 新增字段：
    - npc_states: NPC 心理状态字典，键为 npc_id
    - signal_quality: 信号质量 0-100 整数
    - athena_status: 雅典娜状态（normal/degraded/offline）
    - athena_consciousness_flag: 雅典娜意识标记（normal/awakening，隐藏结局用）
    """

    # --- 8d 新增字段 ---
    npc_states: Dict[str, NpcState] = field(default_factory=dict)
    signal_quality: int = 62
    athena_status: str = "normal"              # normal / degraded / offline
    athena_consciousness_flag: str = "normal"  # normal / awakening

    # --- 既有世界状态字段（Phase 1 与 MOCK_GAME_STATE 对齐） ---
    sol: int = 1
    mars_time: str = "08:00"
    base_integrity: float = 0.78
    resources: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        "oxygen": {"current": 78, "max": 100, "rate": -0.3},
        "power": {"current": 85, "max": 100, "rate": 0.5},
        "water": {"current": 65, "max": 100, "rate": -0.1},
        "food": {"current": 90, "max": 100, "rate": -0.5},
        "parts": {"current": 12, "max": 20, "rate": 0},  # 备用件初始 12 单位（单位数非百分比）
    })
    crew_workload: float = 0.5
    sol_success_progress: bool = False  # 本 Sol 是否有成功任务推进
    sol_sufficiency_improved: bool = False  # 本 Sol 资源自给率是否提升

    # --- Phase 2 引擎化：题材包动态字段 ---
    # 题材特定字段（如 athena_status 已是核心字段，新题材字段存这里）
    # 通过 EngineCore.state_schema 注册并初始化
    custom_fields: Dict[str, Any] = field(default_factory=dict)

    def get_npc(self, npc_id: str) -> Optional[NpcState]:
        """获取 NPC 状态，不存在返回 None"""
        return self.npc_states.get(npc_id)

    def is_ai_sender(self, sender_id: str) -> bool:
        """判断 sender 是否为 AI 类（不进入 npc_states）"""
        return sender_id in AI_SENDERS

    def get_custom(self, name: str, default: Any = None) -> Any:
        """获取题材包动态字段值（custom_fields）"""
        return self.custom_fields.get(name, default)

    def set_custom(self, name: str, value: Any) -> None:
        """设置题材包动态字段值（custom_fields）"""
        self.custom_fields[name] = value


# ============================================================
# GameState 初始化
# ============================================================

def create_initial_game_state(npc_schema=None) -> GameState:
    """创建初始游戏状态

    Args:
        npc_schema: 可选的 NpcSchema 实例（Phase 4 引擎化）。
            提供时按 schema 动态创建 NPC；缺省时回退到硬编码
            NPC_INITIAL_STATES / NPC_STATE_MACHINES（向后兼容）。
    """
    game_state = GameState()

    # Phase 4 引擎化：优先用 NpcSchema 动态创建 NPC
    if npc_schema is not None and len(npc_schema) > 0:
        game_state.npc_states = npc_schema.init_npc_states()
        return game_state

    # 回退：硬编码 NPC_INITIAL_STATES（向后兼容）
    for npc_id, initial in NPC_INITIAL_STATES.items():
        npc_state = NpcState(
            stress=initial["stress"],
            morale=initial["morale"],
            trust_in_player=initial["trust_in_player"],
            energy=initial["energy"],
            current_state="stable",  # 占位，derive_current_state 会更新
            state_machine=NPC_STATE_MACHINES.get(npc_id, []),
        )
        npc_state.clamp()
        derive_current_state(npc_state)
        game_state.npc_states[npc_id] = npc_state
    return game_state


# ============================================================
# 事件系统写入接口（8d 文档 §7.3）
# ============================================================

def apply_effects(
    game_state: GameState,
    effects: Dict[str, Any],
    target_npcs: Optional[List[str]] = None,
) -> None:
    """应用玩家选项 effects 到 npc_states（8d 文档 §7.3）

    Args:
        game_state: 游戏状态
        effects: 事件剧本 effects 字段
            - stress_delta: dict[npc_id_or_"all", float]  浮点直加
            - morale_delta: dict[npc_id_or_"all", float]  浮点直加
            - trust_delta: dict[npc_id_or_"all", float]   整数 /100 换算到 0-1
        target_npcs: None=全员，list=指定 NPC 子集

    过滤规则：
        - effects 中 key="all" 的 delta → 仅应用到 target_npcs 指定的 NPC
        - effects 中 key=<specific_npc> 的 delta → 始终应用到该 NPC（不受 target_npcs 限制）
        - target_npcs=None → 全员
    """
    targets = target_npcs or list(game_state.npc_states.keys())

    # stress_delta（8d 文档 §2.2 新增字段，浮点直加）
    for npc_id, delta in effects.get("stress_delta", {}).items():
        apply_list = targets if npc_id == "all" else [npc_id]
        for nid in apply_list:
            if nid in game_state.npc_states:
                game_state.npc_states[nid].stress += delta
                logger.debug(f"apply_effects: {nid}.stress += {delta}")

    # morale_delta（已有字段，浮点直加）
    for npc_id, delta in effects.get("morale_delta", {}).items():
        apply_list = targets if npc_id == "all" else [npc_id]
        for nid in apply_list:
            if nid in game_state.npc_states:
                game_state.npc_states[nid].morale += delta
                logger.debug(f"apply_effects: {nid}.morale += {delta}")

    # trust_delta（整数，直接加到 0-100 trust_in_player）
    for npc_id, delta in effects.get("trust_delta", {}).items():
        apply_list = targets if npc_id == "all" else [npc_id]
        for nid in apply_list:
            if nid in game_state.npc_states:
                game_state.npc_states[nid].trust_in_player += int(delta)
                logger.debug(
                    f"apply_effects: {nid}.trust_in_player += {delta}"
                )

    # 统一 clamp（8d 文档 §5 line 384-385）
    for nid in game_state.npc_states:
        game_state.npc_states[nid].clamp()

    # 派生 current_state
    for nid in game_state.npc_states:
        derive_current_state(game_state.npc_states[nid])

    # 处理 effects 中的 state_set（基地状态变更，如 athena_status）
    state_set = effects.get("state_set", {})
    if "athena_status" in state_set:
        old_status = game_state.athena_status
        game_state.athena_status = state_set["athena_status"]
        logger.info(f"apply_effects: athena_status {old_status} → {game_state.athena_status}")
    if "athena_consciousness_flag" in state_set:
        game_state.athena_consciousness_flag = state_set["athena_consciousness_flag"]


# ============================================================
# state_machine 状态推导（8d 文档 §7.4 接口契约）
# ============================================================

def derive_current_state(npc_state: NpcState) -> None:
    """遍历 state_machine 推导 current_state（8d 文档 §7.4）

    逻辑：从后往前遍历状态机（最严重的状态在前列表末尾），
    返回第一个 condition 匹配的状态。

    Args:
        npc_state: NPC 状态实例，直接写入 current_state 字段
    """
    if not npc_state.state_machine:
        return

    # 构建安全求值上下文
    eval_vars: Dict[str, Any] = {
        "stress": npc_state.stress,
        "morale": npc_state.morale,
        "trust_in_player": npc_state.trust_in_player,
        "energy": npc_state.energy,
    }

    # 从后往前遍历（最严重状态优先匹配）
    for node in reversed(npc_state.state_machine):
        condition = node.get("condition", "")
        state_name = node.get("state", "")
        if _eval_condition(condition, eval_vars):
            if npc_state.current_state != state_name:
                logger.debug(
                    f"derive_current_state: {state_name} "
                    f"(stress={npc_state.stress:.2f}, morale={npc_state.morale:.2f})"
                )
            npc_state.current_state = state_name
            return

    # 无匹配条件，保持现状
    logger.warning(
        f"derive_current_state: no condition matched, "
        f"keeping current_state={npc_state.current_state}"
    )


def _eval_condition(condition: str, variables: Dict[str, Any]) -> bool:
    """安全求值条件表达式（委托 condition.py AST 白名单求值器）

    支持比较/逻辑/成员运算的声明式布尔子集
    （与 NPC YAML SCHEMA condition 表达式语法对齐）

    空条件返回 False（按 8d §7.4 "无匹配条件保持现状"语义，
    空字符串不视为无条件通过，而是不匹配）。

    Args:
        condition: 条件表达式字符串，如 "stress < 0.5 and morale > 0.5"
        variables: 变量字典

    Returns:
        布尔结果；空条件或求值失败返回 False
    """
    if not condition or not condition.strip():
        return False

    try:
        result = evaluate_condition(condition, variables)
        return bool(result)
    except (ValueError, SyntaxError, TypeError) as e:
        # TypeError 通常来自未知变量与数值比较（如 claustrophobia_severity >= 0.4
        # 中 claustrophobia_severity 未在 eval_vars 中，被 condition.py 当作字符串）
        logger.warning(f"_eval_condition: eval failed for '{condition}': {e}")
        return False


# ============================================================
# emotion_hint 构造（8d 文档 §5.3 修订版）
# ============================================================

def build_emotion_hint(game_state: GameState, sender_id: str) -> Dict[str, Any]:
    """构造 emotion_hint（8d 文档 §5.3 修订版 + 云逸 §8.4）

    AI 类 sender 返回 ai_status，人类 NPC 返回 emotion_label。

    Args:
        game_state: 游戏状态
        sender_id: 消息发送者 ID

    Returns:
        emotion_hint 字典
    """
    # AI 类 sender（8d 文档 §5.1）
    if sender_id in AI_SENDERS:
        if sender_id == "athena":
            ai_status = game_state.athena_status  # normal / degraded / offline
        else:
            # courier 等其他 AI sender
            ai_status = "normal"
        return {
            "stress": 0.0,       # 占位，前端不读
            "morale": 1.0,       # 占位，前端不读
            "ai_status": ai_status,
        }

    # 人类 NPC
    npc_state = game_state.npc_states.get(sender_id)
    if npc_state is None:
        # 兜底（8d 文档 §5.3）
        logger.warning(f"build_emotion_hint: npc_states missing sender_id={sender_id}")
        return {"stress": 0.0, "morale": 1.0}

    stress = npc_state.stress
    morale = npc_state.morale
    emotion_label = derive_emotion_label(stress, morale)

    return {
        "stress": stress,
        "morale": morale,
        "emotion_label": emotion_label,
    }


# ============================================================
# 资源危机检测（8d 文档 §3.2 / §7.4）
# ============================================================

def check_resource_crisis(game_state: GameState) -> Dict[str, float]:
    """检测资源危机阈值，返回需应用的 stress_delta

    按 8d 文档 §3.2 阈值表检查各项资源。
    同一资源只触发最严重的阈值（如氧气 8% 只触发 <10% 的 +0.15，不叠加 <20% 的 +0.10）。
    资源责任区 NPC 的 stress_delta 翻倍（§3.2 注）。

    Args:
        game_state: 游戏状态

    Returns:
        stress_delta 字典 {npc_id: delta}，可直接传入 apply_effects
    """
    stress_deltas: Dict[str, float] = {}
    resources = game_state.resources

    # 按资源分组，取最严重的阈值
    triggered: Dict[str, ResourceThreshold] = {}
    for threshold in RESOURCE_THRESHOLDS:
        resource = resources.get(threshold.resource)
        if resource is None:
            continue
        current = resource.get("current", 100)
        if current < threshold.threshold:
            # 同一资源取更低阈值（更严重）
            existing = triggered.get(threshold.resource)
            if existing is None or threshold.threshold < existing.threshold:
                triggered[threshold.resource] = threshold

    for resource_name, threshold in triggered.items():
        delta = threshold.stress_delta
        # 全员 stress+
        for npc_id in game_state.npc_states:
            stress_deltas[npc_id] = stress_deltas.get(npc_id, 0.0) + delta

        # 责任区 NPC stress 翻倍
        owner = RESOURCE_OWNERS.get(resource_name)
        if owner and owner in game_state.npc_states:
            stress_deltas[owner] = stress_deltas.get(owner, 0.0) + delta  # 再加一次 = 翻倍

        logger.info(
            f"check_resource_crisis: {threshold.description} "
            f"(current={resources[resource_name].get('current', '?')}, "
            f"delta={delta}, owner={owner})"
        )

    return stress_deltas


# ============================================================
# Sol 自然衰减/恢复（8d 文档 §3.3 / §7.4）
# ============================================================

def apply_sol_decay(game_state: GameState) -> None:
    """每 Sol 自然衰减/恢复（8d 文档 §3.3）

    在每 Sol（游戏日）开始时统一结算。
    包括 NPC 心理状态衰减 + 资源按 rate 衰减。

    Args:
        game_state: 游戏状态
    """
    # 1. 资源按 rate 衰减/恢复
    for res_name, res in game_state.resources.items():
        rate = res.get("rate", 0)
        max_val = res.get("max", 100)
        res["current"] = max(0, min(max_val, res["current"] + rate))
        logger.debug(
            f"apply_sol_decay: resource {res_name} {res['current'] - rate:.1f} → {res['current']:.1f} (rate={rate})"
        )

    # 2. NPC 心理状态衰减
    for npc_id, npc_state in game_state.npc_states.items():
        # 默认衰减（8d 文档 §3.3）
        npc_state.stress += SOL_DECAY_DEFAULTS["stress"]
        npc_state.morale += SOL_DECAY_DEFAULTS["morale"]
        # trust_in_player 无自然变化

        # 条件性变化
        # 1. 若 Sol 内有成功任务推进 → stress -0.05
        if game_state.sol_success_progress:
            npc_state.stress += -0.05

        # 2. 若资源自给率较上周提升 → morale +0.05
        if game_state.sol_sufficiency_improved:
            npc_state.morale += 0.05

        # 3. 若 crew_workload > 0.7 持续 ≥3 Sol → energy -0.05
        #    简化：当前 crew_workload > 0.7 即触发（持续 Sol 追踪待 Phase 2）
        if game_state.crew_workload > 0.7:
            npc_state.energy += -0.05

        # 4. 若 crew_workload < 0.3 → energy +0.1
        if game_state.crew_workload < 0.3:
            npc_state.energy += 0.1

        # clamp
        npc_state.clamp()

        # 重新推导 current_state
        derive_current_state(npc_state)

        logger.debug(
            f"apply_sol_decay: {npc_id} "
            f"stress={npc_state.stress:.3f} morale={npc_state.morale:.3f} "
            f"energy={npc_state.energy:.3f} state={npc_state.current_state}"
        )

    # Sol 结算后重置标记
    game_state.sol_success_progress = False
    game_state.sol_sufficiency_improved = False

    # 推进 Sol
    game_state.sol += 1


# ============================================================
# 玩家情感类指令 delta 查询（8d 文档 §3.5）
# ============================================================

# 指令子类 → delta 映射表（8d 文档 §3.5）
EMOTIONAL_COMMAND_DELTAS: Dict[str, Dict[str, float]] = {
    "soothe":     {"stress_delta": -0.05, "morale_delta": +0.08, "trust_delta": +3},
    "empathize":  {"stress_delta": -0.03, "morale_delta": +0.05, "trust_delta": +5},
    "command":    {"stress_delta": +0.05, "morale_delta": -0.03, "trust_delta": -3},
    "blame":      {"stress_delta": +0.08, "morale_delta": -0.08, "trust_delta": -5},
    "smalltalk":  {"stress_delta": -0.02, "morale_delta": +0.02, "trust_delta": +1},
}


def get_emotional_command_delta(command_subtype: str) -> Dict[str, float]:
    """获取情感类指令的 delta 值（8d 文档 §3.5）

    Args:
        command_subtype: 指令子类 (soothe/empathize/command/blame/smalltalk)

    Returns:
        delta 字典 {stress_delta, morale_delta, trust_delta}
    """
    return EMOTIONAL_COMMAND_DELTAS.get(
        command_subtype,
        EMOTIONAL_COMMAND_DELTAS["smalltalk"],  # 兜底
    )


# ============================================================
# 测试入口
# ============================================================

def _self_test() -> None:
    """模块自测——验证核心逻辑正确性"""
    print("=== game_state.py 自测 ===\n")

    # 1. 创建初始状态
    gs = create_initial_game_state()
    print(f"初始 GameState: sol={gs.sol}, signal={gs.signal_quality}, athena={gs.athena_status}")
    for nid, ns in gs.npc_states.items():
        print(f"  {nid}: stress={ns.stress:.2f} morale={ns.morale:.2f} "
          f"trust={ns.trust_in_player} energy={ns.energy:.2f} state={ns.current_state}")

    # 2. 测试 apply_effects（模拟 ev_A1 修复决策）
    print("\n--- 测试 apply_effects ---")
    test_effects = {
        "stress_delta": {"aisha": 0.05, "viktor": 0.1, "chen_hao": 0.03},
        "morale_delta": {"aisha": 0.05},
        "trust_delta": {"aisha": 10, "viktor": -5, "chen_hao": 3},
    }
    apply_effects(gs, test_effects)
    aisha = gs.npc_states["aisha"]
    viktor = gs.npc_states["viktor"]
    print(f"aisha:  stress={aisha.stress:.3f} morale={aisha.morale:.3f} "
          f"trust={aisha.trust_in_player} state={aisha.current_state}")
    print(f"viktor: stress={viktor.stress:.3f} morale={viktor.morale:.3f} "
          f"trust={viktor.trust_in_player} state={viktor.current_state}")

    # 验证 trust_delta 直接加（0-100 整数）
    expected_aisha_trust = 55 + 10
    assert aisha.trust_in_player == expected_aisha_trust, \
        f"trust_delta 直接加错误: expected {expected_aisha_trust}, got {aisha.trust_in_player}"
    print(f"✓ trust_delta 验证通过 (aisha trust = {expected_aisha_trust})")

    # 3. 测试 derive_emotion_label
    print("\n--- 测试 derive_emotion_label ---")
    test_cases = [
        (0.1, 0.1, "numb"),
        (0.3, 0.5, "focused"),
        (0.5, 0.5, "alert"),
        (0.7, 0.5, "anxious"),
        (0.9, 0.5, "frantic"),
        (0.1, 0.9, "upbeat"),
    ]
    for stress, morale, expected in test_cases:
        label = derive_emotion_label(stress, morale)
        status = "✓" if label == expected else "✗"
        print(f"  {status} stress={stress} morale={morale} → {label} (expected {expected})")

    # 4. 测试 build_emotion_hint
    print("\n--- 测试 build_emotion_hint ---")
    # 人类 NPC
    hint = build_emotion_hint(gs, "aisha")
    print(f"  aisha: {hint}")
    assert "emotion_label" in hint
    assert "ai_status" not in hint
    # AI sender
    hint_athena = build_emotion_hint(gs, "athena")
    print(f"  athena: {hint_athena}")
    assert "ai_status" in hint_athena
    assert hint_athena["ai_status"] == "normal"
    # courier
    hint_courier = build_emotion_hint(gs, "courier")
    print(f"  courier: {hint_courier}")
    assert hint_courier["ai_status"] == "normal"

    # 5. 测试 check_resource_crisis
    print("\n--- 测试 check_resource_crisis ---")
    # 模拟氧气危机（8% 低于 10% 阈值，只触发最严重的 <10% 阈值）
    gs.resources["oxygen"]["current"] = 8  # 低于 10%
    crisis = check_resource_crisis(gs)
    print(f"  危机 stress_deltas: {crisis}")
    assert "sophia" in crisis  # sophia 是氧气责任区
    # sophia 应该翻倍: +0.15 (氧气<10 全员) + 0.15 (翻倍) = 0.30
    assert abs(crisis["sophia"] - 0.30) < 0.001, \
        f"责任区翻倍错误: expected 0.30, got {crisis['sophia']}"
    # 非责任区 NPC 只有 +0.15
    assert abs(crisis["viktor"] - 0.15) < 0.001, \
        f"非责任区 delta 错误: expected 0.15, got {crisis['viktor']}"
    print(f"  ✓ 责任区翻倍验证通过 (sophia delta = {crisis['sophia']}, others = {crisis['viktor']})")

    # 6. 测试 apply_sol_decay
    print("\n--- 测试 apply_sol_decay ---")
    gs2 = create_initial_game_state()
    original_sol = gs2.sol
    original_aisha_stress = gs2.npc_states["aisha"].stress
    apply_sol_decay(gs2)
    new_aisha_stress = gs2.npc_states["aisha"].stress
    print(f"  Sol: {original_sol} → {gs2.sol}")
    print(f"  aisha stress: {original_aisha_stress:.3f} → {new_aisha_stress:.3f} "
          f"(默认 +0.02 = {original_aisha_stress + 0.02:.3f})")
    assert gs2.sol == original_sol + 1
    assert abs(new_aisha_stress - (original_aisha_stress + 0.02)) < 0.001
    print(f"  ✓ Sol 衰减验证通过")

    # 7. 测试 clamp
    print("\n--- 测试 clamp ---")
    gs3 = create_initial_game_state()
    apply_effects(gs3, {
        "morale_delta": {"aisha": -10.0},  # 远超下限
        "stress_delta": {"aisha": +10.0},  # 远超上限
    })
    aisha3 = gs3.npc_states["aisha"]
    print(f"  aisha: stress={aisha3.stress:.3f} morale={aisha3.morale:.3f}")
    assert aisha3.stress == 1.0
    assert aisha3.morale == 0.0
    print(f"  ✓ clamp 验证通过")

    print("\n=== 自测全部通过 ===")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    _self_test()
