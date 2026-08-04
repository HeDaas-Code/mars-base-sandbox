"""
NPC Persona 加载模块

从蔚蓝交付的 YAML 文件加载：
1. persona_prompt — 注入 LLM system message 的人格模板
2. speech_examples — few-shot 强化对话风格
3. seed_memories — 启动时注入 ChromaDB 的初始记忆
4. initial_state — NPC 心理状态初值（stress/morale/trust/energy）
5. state_machine — 状态机阈值转移规则
6. skills / decision_weights / relationships — 供事件系统与决策演算使用

YAML 路径：/home/z/my-project/shared/mars-base/dict/npcs/npc_<id>.yaml
chen_hao 无 YAML，走 prompt.py 的硬编码 CHEN_HAO_SYSTEM_PROMPT。

变量替换：YAML persona_prompt 使用 {{var}} Jinja 风格占位符，
本模块在运行时替换为 GameState 中的实值。

作者：锐锋-核心开发工程师  日期：2026-08-03
"""

from __future__ import annotations

import logging
import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

# ============================================================
# 路径与常量
# ============================================================

# NPC YAML 根目录（蔚蓝交付）
_NPC_YAML_DIR: str = "/home/z/my-project/shared/mars-base/dict/npcs"

# chen_hao 无 YAML，硬编码在 prompt.py 中
_HAS_YAML: frozenset[str] = frozenset({"sophia", "viktor", "aisha", "marcus", "lin_ruoxi"})

# 变量占位符正则：{{var_name}}
_VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")


# ============================================================
# YAML 加载（带缓存）
# ============================================================

@lru_cache(maxsize=16)
def _load_yaml(npc_id: str) -> Optional[Dict[str, Any]]:
    """加载并缓存单个 NPC YAML 全量数据

    Args:
        npc_id: NPC ID（如 sophia / viktor / aisha / marcus / lin_ruoxi）

    Returns:
        YAML 解析后的完整字典，不存在返回 None
    """
    yaml_path = os.path.join(_NPC_YAML_DIR, f"npc_{npc_id}.yaml")
    if not os.path.exists(yaml_path):
        logger.warning(f"persona YAML not found: {yaml_path}")
        return None

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        logger.debug(f"loaded persona YAML: {npc_id} ({yaml_path})")
        return data
    except yaml.YAMLError as e:
        logger.error(f"YAML parse error for {npc_id}: {e}")
        return None
    except OSError as e:
        logger.error(f"file read error for {npc_id}: {e}")
        return None


# ============================================================
# persona_prompt 加载与变量替换
# ============================================================

def load_persona_prompt(npc_id: str) -> Optional[str]:
    """加载 NPC 的 persona_prompt 原始模板（未替换变量）

    Args:
        npc_id: NPC ID

    Returns:
        persona_prompt 字符串，不存在返回 None
    """
    data = _load_yaml(npc_id)
    if data is None:
        return None
    prompt = data.get("persona_prompt")
    if not prompt:
        logger.warning(f"persona_prompt empty for {npc_id}")
        return None
    return prompt


def render_persona_prompt(
    npc_id: str,
    variables: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """渲染 persona_prompt，替换 {{var}} 占位符

    支持的变量（来自 NPC YAML persona_prompt 的占位符定义）：
    - {{stress}}          — 压力值 0-1
    - {{morale}}          — 士气值 0-1
    - {{trust_in_player}} — 对玩家信任度 0-1
    - {{stage}}           — 当前游戏阶段（如 survival / explore / build / climax）
    - {{recent_events}}   — 最近事件摘要

    Args:
        npc_id: NPC ID
        variables: 变量字典，缺失的变量保留占位符原样

    Returns:
        渲染后的 persona_prompt 字符串，NPC 不存在返回 None
    """
    template = load_persona_prompt(npc_id)
    if template is None:
        return None

    if variables is None:
        variables = {}

    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        if var_name in variables:
            return str(variables[var_name])
        # 缺失变量保留占位符
        return match.group(0)

    return _VAR_PATTERN.sub(_replace, template)


# ============================================================
# speech_examples 加载
# ============================================================

def load_speech_examples(npc_id: str) -> List[Dict[str, str]]:
    """加载 NPC 的对话风格示例

    用于 few-shot 注入 system prompt 强化对话风格。

    Args:
        npc_id: NPC ID

    Returns:
        示例列表，每项含 context 和 line 字段。不存在返回空列表。
    """
    data = _load_yaml(npc_id)
    if data is None:
        return []
    examples = data.get("speech_examples", [])
    if not isinstance(examples, list):
        return []
    return examples


def format_speech_examples(npc_id: str) -> str:
    """将 speech_examples 格式化为可注入 prompt 的文本

    Args:
        npc_id: NPC ID

    Returns:
        格式化后的文本块，无示例返回空字符串
    """
    examples = load_speech_examples(npc_id)
    if not examples:
        return ""

    lines = ["\n## 对话风格示例（参考语气，不要逐字复用）"]
    for ex in examples:
        context = ex.get("context", "")
        line = ex.get("line", "")
        if context and line:
            lines.append(f"- [{context}] {line}")
    return "\n".join(lines)


# ============================================================
# seed_memories 加载
# ============================================================

def load_seed_memories(npc_id: str) -> List[Dict[str, Any]]:
    """加载 NPC 的种子记忆

    将 YAML 的 seed_memories 字段转换为 ChromaDB MemoryStore 所需格式：
    - agent_id: 注入 npc_id
    - content: 记忆内容
    - memory_type: episodic / semantic
    - timestamp: f"Sol-{sol}"
    - importance: 默认 0.5（deliberate 模式标准权重）
    - tags: 从 event_type 派生

    YAML 字段映射：
    | YAML 字段            | MemoryStore 字段  |
    |----------------------|-------------------|
    | content              | content           |
    | type                 | memory_type       |
    | sol                  | timestamp (Sol-N)  |
    | emotional_intensity  | importance        |
    | event_type           | tags              |

    Args:
        npc_id: NPC ID

    Returns:
        记忆字典列表，格式与 seed_memories.py SEED_MEMORIES_CHEN_HAO 对齐
    """
    data = _load_yaml(npc_id)
    if data is None:
        return []
    raw_memories = data.get("seed_memories", [])
    if not isinstance(raw_memories, list):
        return []

    formatted: List[Dict[str, Any]] = []
    for mem in raw_memories:
        if not isinstance(mem, dict):
            continue
        # 跳过空记录（YAML 格式问题可能产生空项）
        content = mem.get("content", "")
        if not content or not content.strip():
            logger.warning(
                f"seed_memory skipped (empty content) for {npc_id}: "
                f"memory_id={mem.get('memory_id')}"
            )
            continue

        sol = mem.get("sol", 0)
        timestamp = f"Sol-{sol}" if sol else "Sol-0"

        formatted.append({
            "agent_id": npc_id,
            "content": content,
            "memory_type": mem.get("type", "episodic"),
            "timestamp": timestamp,
            "importance": mem.get("emotional_intensity", 0.5),
            "tags": mem.get("event_type", ""),
        })
    return formatted


# ============================================================
# initial_state / state_machine 加载
# ============================================================

def load_initial_state(npc_id: str) -> Optional[Dict[str, float]]:
    """加载 NPC 的心理状态初值

    Args:
        npc_id: NPC ID

    Returns:
        含 stress/morale/trust_in_player/energy 的字典，不存在返回 None
    """
    data = _load_yaml(npc_id)
    if data is None:
        return None
    psychology = data.get("psychology", {})
    return psychology.get("initial_state")


def load_state_machine(npc_id: str) -> List[Dict[str, Any]]:
    """加载 NPC 的状态机定义

    Args:
        npc_id: NPC ID

    Returns:
        状态机列表，不存在返回空列表
    """
    data = _load_yaml(npc_id)
    if data is None:
        return []
    psychology = data.get("psychology", {})
    return psychology.get("state_machine", [])


# ============================================================
# 元数据加载（供事件系统使用）
# ============================================================

def load_npc_metadata(npc_id: str) -> Dict[str, Any]:
    """加载 NPC 的完整元数据（skills / relationships / decision_weights 等）

    供事件系统、决策演算、章节字典使用。

    Args:
        npc_id: NPC ID

    Returns:
        元数据字典，不存在返回空字典
    """
    data = _load_yaml(npc_id)
    if data is None:
        return {}
    return {
        "npc_id": data.get("npc_id"),
        "name_cn": data.get("name_cn"),
        "name_en": data.get("name_en"),
        "role_short": data.get("role_short"),
        "basic_info": data.get("basic_info", {}),
        "skills": data.get("skills", {}),
        "psychology": data.get("psychology", {}),
        "narrative": data.get("narrative", {}),
        "relationships": data.get("relationships", []),
        "decision_weights": data.get("decision_weights", {}),
        "personal_events": data.get("personal_events", []),
        "visual": data.get("visual", {}),
    }


def has_yaml(npc_id: str) -> bool:
    """判断 NPC 是否有 YAML 人设文件"""
    return npc_id in _HAS_YAML


# ============================================================
# 模块自测
# ============================================================

def _self_test() -> None:
    """模块自测——验证5个 NPC YAML 加载正确"""
    print("=== persona.py 自测 ===\n")

    for npc_id in ["sophia", "viktor", "aisha", "marcus", "lin_ruoxi"]:
        print(f"--- {npc_id} ---")

        # 1. persona_prompt
        prompt = load_persona_prompt(npc_id)
        assert prompt is not None, f"persona_prompt missing for {npc_id}"
        print(f"  persona_prompt: {len(prompt)} chars, first 60: {prompt[:60]!r}")

        # 2. 变量替换
        rendered = render_persona_prompt(npc_id, {
            "stress": 0.45,
            "morale": 0.55,
            "trust_in_player": 0.35,
            "stage": "survival",
            "recent_events": "（暂无）",
        })
        assert rendered is not None
        # 确认所有占位符都被替换
        remaining = _VAR_PATTERN.findall(rendered)
        assert not remaining, f"unreplaced vars: {remaining}"
        print(f"  rendered: all {{}} replaced ✓")

        # 3. speech_examples
        examples = load_speech_examples(npc_id)
        assert len(examples) >= 5, f"too few speech_examples for {npc_id}: {len(examples)}"
        formatted = format_speech_examples(npc_id)
        assert "对话风格示例" in formatted
        print(f"  speech_examples: {len(examples)} 条")

        # 4. seed_memories
        memories = load_seed_memories(npc_id)
        assert len(memories) >= 6, f"too few seed_memories for {npc_id}: {len(memories)}"
        for mem in memories:
            assert mem["agent_id"] == npc_id
            assert mem["content"].strip()  # 允许有空白但非空
            assert mem["memory_type"] in ("episodic", "semantic")
            assert isinstance(mem["importance"], (int, float))
        print(f"  seed_memories: {len(memories)} 条, agent_id={memories[0]['agent_id']}")

        # 5. initial_state
        state = load_initial_state(npc_id)
        assert state is not None
        for key in ("stress", "morale", "trust_in_player", "energy"):
            assert key in state, f"{key} missing in initial_state"
        print(f"  initial_state: {state}")

        # 6. state_machine
        sm = load_state_machine(npc_id)
        assert len(sm) >= 3, f"too few state_machine nodes for {npc_id}: {len(sm)}"
        print(f"  state_machine: {len(sm)} 节点")

        # 7. metadata
        meta = load_npc_metadata(npc_id)
        assert meta["name_cn"]
        assert meta["skills"]
        assert meta["decision_weights"]
        print(f"  metadata: name={meta['name_cn']}, skills={len(meta['skills'])}项")

        print()

    # chen_hao 无 YAML
    assert not has_yaml("chen_hao")
    assert load_persona_prompt("chen_hao") is None
    assert load_seed_memories("chen_hao") == []
    print("--- chen_hao (无 YAML，走 prompt.py 硬编码) ---")
    print(f"  has_yaml(chen_hao) = {has_yaml('chen_hao')} ✓")
    print(f"  load_persona_prompt(chen_hao) = None ✓")
    print(f"  load_seed_memories(chen_hao) = [] ✓")

    print("\n=== 全部测试通过 ===")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    _self_test()
