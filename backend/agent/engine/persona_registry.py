"""
人格模板注册表

将 npc_prompts.py 的 6 个硬编码模板升级为可注册的 PersonaRegistry，
优先从 NPC YAML 的 persona_prompt 字段加载（数据驱动），回退到硬编码模板。

模板渲染使用 Jinja2（{{var}} 语法），注入变量：
    stress / morale / trust_in_player / stage / recent_events

作者：锐锋-核心开发工程师  日期：2026-08-09
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class PersonaEntry:
    """人格模板注册项"""
    npc_id: str
    template: str           # Jinja2 模板字符串
    source: str = "yaml"    # yaml / hardcoded / custom


class PersonaRegistry:
    """人格模板注册表

    用法：
        reg = PersonaRegistry()
        reg.register("chen_hao", template_str, source="yaml")
        prompt = reg.render("chen_hao", stress=0.4, morale=0.6, ...)
    """

    def __init__(self) -> None:
        self._entries: Dict[str, PersonaEntry] = {}

    def register(
        self,
        npc_id: str,
        template: str,
        source: str = "custom",
    ) -> None:
        """注册一个人格模板

        Args:
            npc_id: NPC 标识
            template: Jinja2 模板字符串（使用 {{var}} 占位）
            source: 来源标记（yaml / hardcoded / custom）
        """
        self._entries[npc_id] = PersonaEntry(
            npc_id=npc_id,
            template=template,
            source=source,
        )
        logger.debug(f"PersonaRegistry 注册: {npc_id} (source={source})")

    def register_from_yaml(self, npc_id: str, npc_data: Dict[str, Any]) -> bool:
        """从 NPC YAML 数据注册人格模板

        Args:
            npc_id: NPC 标识
            npc_data: chapter_loader.load_npc() 返回的字典

        Returns:
            True 注册成功，False（YAML 无 persona_prompt 字段）
        """
        template = npc_data.get("persona_prompt")
        if not template:
            return False
        # YAML 中 npc_id 字段优先
        canonical_id = npc_data.get("npc_id", npc_id)
        self.register(canonical_id, template, source="yaml")
        return True

    def unregister(self, npc_id: str) -> bool:
        if npc_id in self._entries:
            del self._entries[npc_id]
            return True
        return False

    def get_template(self, npc_id: str) -> Optional[str]:
        """获取原始模板字符串"""
        entry = self._entries.get(npc_id)
        return entry.template if entry else None

    def render(self, npc_id: str, **state_vars) -> str:
        """渲染人格模板

        Args:
            npc_id: NPC 标识
            **state_vars: 注入变量（stress / morale / trust_in_player / stage / recent_events）

        Returns:
            渲染后的 system prompt 字符串

        Raises:
            KeyError: npc_id 未注册
        """
        entry = self._entries.get(npc_id)
        if entry is None:
            raise KeyError(f"PersonaRegistry: unknown npc_id '{npc_id}'")

        return _render_jinja2(entry.template, state_vars)

    def has(self, npc_id: str) -> bool:
        return npc_id in self._entries

    def list_personas(self) -> Dict[str, str]:
        """列出所有已注册人格（npc_id → source）"""
        return {nid: e.source for nid, e in self._entries.items()}

    def __len__(self) -> int:
        return len(self._entries)


# ============================================================
# Jinja2 渲染工具
# ============================================================

def _render_jinja2(template: str, variables: Dict[str, Any]) -> str:
    """用 Jinja2 渲染模板，缺依赖时退化到字符串替换

    Args:
        template: Jinja2 模板字符串
        variables: 注入变量字典

    Returns:
        渲染后的字符串
    """
    try:
        from jinja2 import Template
        return Template(template).render(**variables)
    except ImportError:
        # 退化方案：手动替换 {{var}}
        result = template
        for key, val in variables.items():
            result = result.replace("{{" + key + "}}", str(val))
        return result


# ============================================================
# 默认人格注册表（向后兼容 prompt.py + npc_prompts.py）
# ============================================================

def create_default_persona_registry() -> PersonaRegistry:
    """创建默认人格注册表

    优先从 NPC YAML 加载 persona_prompt；缺失则回退到 npc_prompts.py 硬编码模板。
    """
    reg = PersonaRegistry()

    # 1. 尝试从 NPC YAML 加载（数据驱动主路径）
    try:
        from ..chapter_loader import load_all_npcs
        all_npcs = load_all_npcs()
        for npc_id, npc_data in all_npcs.items():
            reg.register_from_yaml(npc_id, npc_data)
    except Exception as e:
        logger.warning(f"PersonaRegistry: 从 NPC YAML 加载失败: {e}")

    # 2. 回退到硬编码模板（npc_prompts.py + prompt.py）
    try:
        from ..npc_prompts import NPC_PROMPT_MAP
        from ..prompt import CHEN_HAO_SYSTEM_PROMPT
        # chen_hao 硬编码模板（str.format 语法，转 Jinja2 兼容）
        if not reg.has("chen_hao"):
            # chen_hao 原模板用 {game_state}，需保留为 Jinja2 兼容形式
            # 由于原模板无 {{var}} 占位，直接注册为静态模板
            reg.register("chen_hao", CHEN_HAO_SYSTEM_PROMPT, source="hardcoded")
        for npc_id, template in NPC_PROMPT_MAP.items():
            if not reg.has(npc_id):
                reg.register(npc_id, template, source="hardcoded")
    except ImportError as e:
        logger.warning(f"PersonaRegistry: 加载硬编码模板失败: {e}")

    return reg
