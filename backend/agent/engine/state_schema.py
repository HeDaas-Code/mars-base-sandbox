"""
状态字段动态注册（StateSchema）

将 GameState 中硬编码的题材特定字段（athena_status / moxie2_status 等）升级为
可动态注册的字段，题材包通过 schema 声明所需字段，引擎按 schema 初始化。

字段定义结构：
    FieldDef(
        name="athena_consciousness_flag",
        type="str",
        default="normal",
        description="雅典娜意识标记",
    )

GameState 仍保留核心字段（sol / signal_quality / resources / npc_states），
题材特定字段存入 game_state.custom_fields 字典，通过 __getattr__ 透明访问。

作者：锐锋-核心开发工程师  日期：2026-08-09
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FieldDef:
    """状态字段定义"""
    name: str
    type: str = "str"            # str / int / float / bool
    default: Any = None
    description: str = ""

    def cast(self, value: Any) -> Any:
        """将值转换为字段类型"""
        if value is None:
            return self.default
        try:
            if self.type == "str":
                return str(value)
            elif self.type == "int":
                return int(value)
            elif self.type == "float":
                return float(value)
            elif self.type == "bool":
                if isinstance(value, str):
                    return value.lower() in ("true", "1", "yes")
                return bool(value)
        except (ValueError, TypeError) as e:
            logger.warning(f"FieldDef.cast('{self.name}', {value!r}) 失败: {e}")
            return self.default
        return value


class StateSchema:
    """状态字段 schema 注册表

    用法：
        schema = StateSchema()
        schema.register_field("athena_status", type="str", default="normal")
        schema.register_field("greenhouse_status", type="str", default="not_built")

        # 初始化 GameState 的 custom_fields
        game_state.custom_fields = schema.init_fields()
    """

    # 已知的核心字段（GameState 既有字段，不进入 custom_fields）
    CORE_FIELDS = frozenset({
        "sol", "mars_time", "base_integrity", "resources",
        "crew_workload", "sol_success_progress", "sol_sufficiency_improved",
        "npc_states", "signal_quality",
        # 火星基地既有字段保留在 GameState（向后兼容）
        "athena_status", "athena_consciousness_flag",
    })

    def __init__(self) -> None:
        self._fields: Dict[str, FieldDef] = {}

    def register_field(
        self,
        name: str,
        type: str = "str",
        default: Any = None,
        description: str = "",
    ) -> None:
        """注册一个状态字段

        Args:
            name: 字段名
            type: 字段类型（str / int / float / bool）
            default: 默认值
            description: 字段描述
        """
        self._fields[name] = FieldDef(
            name=name,
            type=type,
            default=default,
            description=description,
        )
        logger.debug(f"StateSchema 注册字段: {name} ({type}, default={default!r})")

    def register_from_list(self, fields: List[Dict[str, Any]]) -> None:
        """从列表批量注册（题材包 YAML 结构）

        YAML 格式：
            state_schema:
              fields:
                - {name: sol, type: int, default: 1}
                - {name: athena_status, type: str, default: normal}
        """
        for f in fields or []:
            self.register_field(
                name=f.get("name", ""),
                type=f.get("type", "str"),
                default=f.get("default"),
                description=f.get("description", ""),
            )

    def init_fields(self) -> Dict[str, Any]:
        """初始化所有已注册字段的默认值字典

        Returns:
            {field_name: default_value} 字典
        """
        return {name: fdef.default for name, fdef in self._fields.items()}

    def get_field(self, name: str) -> Optional[FieldDef]:
        return self._fields.get(name)

    def list_fields(self) -> List[Dict[str, Any]]:
        """列出所有已注册字段"""
        return [
            {
                "name": f.name,
                "type": f.type,
                "default": f.default,
                "description": f.description,
            }
            for f in self._fields.values()
        ]

    def __len__(self) -> int:
        return len(self._fields)


# ============================================================
# 资源定义（题材包可声明资源 schema）
# ============================================================

@dataclass
class ResourceDef:
    """资源定义"""
    name: str
    max: float = 100.0
    rate: float = 0.0
    threshold: float = 0.0       # 危机阈值
    owner: str = ""              # 责任区 NPC
    initial: Optional[float] = None  # 初始值（缺省时用 max）


class ResourceSchema:
    """资源定义注册表

    用法：
        rs = ResourceSchema()
        rs.register("oxygen", max=100, rate=-0.3, threshold=20, owner="sophia")
        rs.register("power", max=100, rate=0.5, threshold=15, owner="viktor")

        resources = rs.init_resources()  # {"oxygen": {"current":100,"max":100,"rate":-0.3}, ...}
    """

    def __init__(self) -> None:
        self._defs: Dict[str, ResourceDef] = {}

    def register(
        self,
        name: str,
        max: float = 100.0,
        rate: float = 0.0,
        threshold: float = 0.0,
        owner: str = "",
        initial: Optional[float] = None,
    ) -> None:
        self._defs[name] = ResourceDef(
            name=name,
            max=max,
            rate=rate,
            threshold=threshold,
            owner=owner,
            initial=initial,
        )
        logger.debug(f"ResourceSchema 注册: {name} (max={max}, rate={rate})")

    def register_from_list(self, resources: List[Dict[str, Any]]) -> None:
        """从列表批量注册（题材包 YAML 结构）

        YAML 格式：
            resources:
              - {name: oxygen, max: 100, rate: -0.3, threshold: 30, owner: sophia}
        """
        for r in resources or []:
            self.register(
                name=r.get("name", ""),
                max=r.get("max", 100.0),
                rate=r.get("rate", 0.0),
                threshold=r.get("threshold", 0.0),
                owner=r.get("owner", ""),
                initial=r.get("initial"),
            )

    def init_resources(self) -> Dict[str, Dict[str, float]]:
        """初始化资源字典（GameState.resources 格式）"""
        result: Dict[str, Dict[str, float]] = {}
        for name, rdef in self._defs.items():
            current = rdef.initial if rdef.initial is not None else rdef.max
            result[name] = {
                "current": current,
                "max": rdef.max,
                "rate": rdef.rate,
            }
        return result

    def list_resources(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": r.name,
                "max": r.max,
                "rate": r.rate,
                "threshold": r.threshold,
                "owner": r.owner,
                "initial": r.initial,
            }
            for r in self._defs.values()
        ]

    def __len__(self) -> int:
        return len(self._defs)


# ============================================================
# NPC schema（题材包动态注册 NPC 初始状态 + 状态机）
# ============================================================

@dataclass
class NpcDef:
    """NPC 定义（初始状态 + 状态机）"""
    npc_id: str
    initial_state: Dict[str, Any]            # stress/morale/trust_in_player/energy
    state_machine: List[Dict[str, Any]] = field(default_factory=list)
    source: str = "yaml"                     # yaml / hardcoded / default


class NpcSchema:
    """NPC 定义注册表

    将 game_state.py 中硬编码的 NPC_INITIAL_STATES / NPC_STATE_MACHINES
    升级为可动态注册的 schema，题材包通过 NPC YAML 的 psychology 字段声明。

    用法：
        schema = NpcSchema()
        schema.register_from_yaml("sophia", npc_data)  # 从 NPC YAML 加载
        npc_states = schema.init_npc_states()           # 创建 NpcState 字典

    量纲处理：
        YAML 中 trust_in_player 是 0-1 浮点（如 0.35）
        NpcState.trust_in_player 是 0-100 整数
        register_from_yaml 自动转换：int(trust * 100)
    """

    # 默认初始状态（NPC YAML 缺失 psychology 时的回退值）
    DEFAULT_INITIAL_STATE: Dict[str, Any] = {
        "stress": 0.5,
        "morale": 0.5,
        "trust_in_player": 40,    # 已是 0-100 整数量纲
        "energy": 0.7,
    }

    # 默认状态机（通用四档：stable / strained / cracking / breakdown）
    DEFAULT_STATE_MACHINE: List[Dict[str, Any]] = [
        {"state": "stable", "condition": "true"},
        {"state": "stable", "condition": "stress < 0.5 and morale > 0.4"},
        {"state": "strained", "condition": "stress >= 0.5 and stress <= 0.7"},
        {"state": "cracking", "condition": "stress >= 0.7 or morale < 0.3"},
        {"state": "breakdown", "condition": "stress >= 0.85"},
    ]

    def __init__(self) -> None:
        self._defs: Dict[str, NpcDef] = {}

    def register(
        self,
        npc_id: str,
        initial_state: Optional[Dict[str, Any]] = None,
        state_machine: Optional[List[Dict[str, Any]]] = None,
        source: str = "custom",
    ) -> None:
        """注册一个 NPC 定义"""
        self._defs[npc_id] = NpcDef(
            npc_id=npc_id,
            initial_state=initial_state or dict(self.DEFAULT_INITIAL_STATE),
            state_machine=state_machine or list(self.DEFAULT_STATE_MACHINE),
            source=source,
        )
        logger.debug(f"NpcSchema 注册: {npc_id} (source={source})")

    def register_from_yaml(self, npc_id: str, npc_data: Dict[str, Any]) -> bool:
        """从 NPC YAML 数据注册 NPC 定义

        从 npc_data["psychology"]["initial_state"] 和
        npc_data["psychology"]["state_machine"] 提取。

        量纲转换：
            YAML trust_in_player (0-1 浮点) → NpcState (0-100 整数)

        Returns:
            True 注册成功，False（YAML 无 psychology 字段，用默认值注册）
        """
        canonical_id = npc_data.get("npc_id", npc_id)
        psychology = npc_data.get("psychology", {}) or {}
        initial_state = dict(self.DEFAULT_INITIAL_STATE)
        state_machine = list(self.DEFAULT_STATE_MACHINE)
        has_psychology = False

        if psychology:
            yaml_initial = psychology.get("initial_state", {})
            if yaml_initial:
                has_psychology = True
                # 量纲转换：trust_in_player 0-1 → 0-100
                initial_state["stress"] = float(yaml_initial.get("stress", 0.5))
                initial_state["morale"] = float(yaml_initial.get("morale", 0.5))
                initial_state["energy"] = float(yaml_initial.get("energy", 0.7))
                trust = yaml_initial.get("trust_in_player", 0.4)
                if isinstance(trust, (int, float)) and trust <= 1.0:
                    initial_state["trust_in_player"] = int(trust * 100)
                else:
                    initial_state["trust_in_player"] = int(trust)

            yaml_sm = psychology.get("state_machine", [])
            if yaml_sm:
                state_machine = yaml_sm

        self.register(
            npc_id=canonical_id,
            initial_state=initial_state,
            state_machine=state_machine,
            source="yaml" if has_psychology else "default",
        )
        return has_psychology

    def init_npc_states(self) -> Dict[str, Any]:
        """初始化所有已注册 NPC 的 NpcState 字典

        Returns:
            {npc_id: NpcState} 字典
        """
        # 延迟导入避免循环依赖
        from ..game_state import NpcState, derive_current_state

        result: Dict[str, Any] = {}
        for npc_id, ndef in self._defs.items():
            init = ndef.initial_state
            npc_state = NpcState(
                stress=float(init.get("stress", 0.5)),
                morale=float(init.get("morale", 0.5)),
                trust_in_player=int(init.get("trust_in_player", 40)),
                energy=float(init.get("energy", 0.7)),
                current_state="stable",
                state_machine=ndef.state_machine,
            )
            npc_state.clamp()
            derive_current_state(npc_state)
            result[npc_id] = npc_state
        return result

    def get_def(self, npc_id: str) -> Optional[NpcDef]:
        return self._defs.get(npc_id)

    def list_npcs(self) -> List[Dict[str, Any]]:
        return [
            {
                "npc_id": d.npc_id,
                "initial_state": d.initial_state,
                "source": d.source,
                "state_machine_size": len(d.state_machine),
            }
            for d in self._defs.values()
        ]

    def __len__(self) -> int:
        return len(self._defs)
