"""
结局判定注册表

将 game_loop._ENDING_TABLE 从硬编码列表升级为可注册的 EndingRegistry。
支持从题材包 YAML 加载结局定义，按优先级顺序求值 condition。

注册项结构：
    EndingEntry(
        ending_id="E7_athena_awakening",
        display_name="E7 雅典娜觉醒",
        condition='athena_consciousness_flag == "awakening"',
        priority=0,  # 数字越小优先级越高（默认按注册顺序）
    )

作者：锐锋-核心开发工程师  日期：2026-08-09
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..condition import evaluate_condition

logger = logging.getLogger(__name__)


@dataclass
class EndingEntry:
    """结局定义项"""
    ending_id: str
    display_name: str
    condition: str
    priority: int = 100  # 默认优先级，数字越小越先评估


@dataclass
class EndingResult:
    """结局判定结果"""
    ending_id: str
    display_name: str


class EndingRegistry:
    """结局判定注册表

    用法：
        reg = EndingRegistry()
        reg.register("E7_athena_awakening", "E7 雅典娜觉醒",
                     'athena_consciousness_flag == "awakening"', priority=0)
        reg.register("E5_last_signal", "E5 最后的信号", "oxygen <= 0", priority=10)

        result = reg.evaluate(context_dict)
        if result:
            print(f"结局命中: {result.ending_id}")
    """

    def __init__(self) -> None:
        self._entries: List[EndingEntry] = []

    def register(
        self,
        ending_id: str,
        display_name: str,
        condition: str,
        priority: int = 100,
    ) -> None:
        """注册一个结局判定项

        Args:
            ending_id: 结局唯一标识
            display_name: 显示名
            condition: 条件表达式字符串（由 condition.evaluate_condition 求值）
            priority: 优先级（数字越小越先评估，默认 100）
        """
        # 若 ending_id 已存在，覆盖旧定义
        for i, e in enumerate(self._entries):
            if e.ending_id == ending_id:
                self._entries[i] = EndingEntry(ending_id, display_name, condition, priority)
                logger.debug(f"EndingRegistry 覆盖注册: {ending_id}")
                return
        self._entries.append(EndingEntry(ending_id, display_name, condition, priority))
        logger.debug(f"EndingRegistry 注册: {ending_id} (priority={priority})")

    def register_from_list(self, endings: List[Dict[str, Any]]) -> None:
        """从列表批量注册（题材包 YAML 结构）

        YAML 格式：
            endings:
              - id: E7_athena_awakening
                display_name: E7 雅典娜觉醒
                condition: 'athena_consciousness_flag == "awakening"'
                priority: 0
        """
        for item in endings or []:
            self.register(
                ending_id=item.get("id") or item.get("ending_id", ""),
                display_name=item.get("display_name") or item.get("name", ""),
                condition=item.get("condition", ""),
                priority=item.get("priority", 100),
            )

    def unregister(self, ending_id: str) -> bool:
        """注销一个结局项"""
        for i, e in enumerate(self._entries):
            if e.ending_id == ending_id:
                self._entries.pop(i)
                return True
        return False

    def evaluate(self, context: Dict[str, Any]) -> Optional[EndingResult]:
        """按优先级评估所有结局条件，返回首个命中项

        Args:
            context: 条件求值上下文（通常由 EventScheduler._build_condition_context 构建）

        Returns:
            EndingResult 或 None（无命中）
        """
        # 按 priority 升序排列（数字小优先），同 priority 按注册顺序
        sorted_entries = sorted(
            enumerate(self._entries),
            key=lambda x: (x[1].priority, x[0]),
        )
        for _, entry in sorted_entries:
            if not entry.condition:
                continue
            try:
                if evaluate_condition(entry.condition, context):
                    logger.info(f"结局命中: {entry.ending_id}")
                    return EndingResult(
                        ending_id=entry.ending_id,
                        display_name=entry.display_name,
                    )
            except (ValueError, SyntaxError, TypeError) as e:
                logger.warning(f"结局判定异常 {entry.ending_id}: {e}")
        return None

    def list_endings(self) -> List[Dict[str, Any]]:
        """列出所有已注册结局（按优先级排序）"""
        sorted_entries = sorted(
            enumerate(self._entries),
            key=lambda x: (x[1].priority, x[0]),
        )
        return [
            {
                "ending_id": e.ending_id,
                "display_name": e.display_name,
                "condition": e.condition,
                "priority": e.priority,
            }
            for _, e in sorted_entries
        ]

    def __len__(self) -> int:
        return len(self._entries)


# ============================================================
# 默认结局表（火星基地题材，向后兼容 game_loop._ENDING_TABLE）
# ============================================================

def create_default_ending_registry() -> EndingRegistry:
    """创建默认结局注册表（火星基地题材 5 结局）

    与 game_loop._ENDING_TABLE 保持一致，用于向后兼容。
    题材包可通过 register_from_list 覆盖。
    """
    reg = EndingRegistry()
    reg.register("E7_athena_awakening", "E7 雅典娜觉醒",
                 'athena_consciousness_flag == "awakening"', priority=0)
    reg.register("E1_hercules_return", "E1 赫拉克勒斯归航",
                 "all_crew_alive == true and sol >= 60 and oxygen > 30", priority=10)
    reg.register("E5_last_signal", "E5 最后的信号",
                 "oxygen <= 0", priority=20)
    reg.register("E6_collapse", "E6 守墓人",
                 "morale_avg < 0.2", priority=30)
    reg.register("E2_mars_child", "E2 火星之子",
                 'greenhouse_status == "built"', priority=40)
    return reg
