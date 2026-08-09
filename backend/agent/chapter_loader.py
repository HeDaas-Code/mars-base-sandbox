"""
章节与事件 YAML 加载器

从蔚蓝交付的 YAML 加载：
1. 章节字典（chapter_survival_sol1_10.yaml 等4个章节）
2. 主线分支事件（branch_a_earth_rescue.yaml 等4个分支）
3. 临时触发器（temporary_keywords 中的 trigger/ttl）
4. 永久关键词（permanent_keywords）

YAML 路径（基于本文件位置推导，避免硬编码绝对路径）：
- <project_root>/dict/chapters/chapter_<stage>_sol<range>.yaml
- <project_root>/dict/events/mainline/branch_<id>_<name>.yaml

作者：锐锋-核心开发工程师  日期：2026-08-03
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


# ============================================================
# 路径常量（基于 __file__ 推导，跨机器可移植）
# ============================================================

# backend/agent/chapter_loader.py → 向上两级到项目根目录
_PROJECT_ROOT: str = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
DICT_ROOT: str = os.path.join(_PROJECT_ROOT, "dict")
CHAPTERS_DIR: str = os.path.join(DICT_ROOT, "chapters")
BRANCHES_DIR: str = os.path.join(DICT_ROOT, "events", "mainline")
NPCS_DIR: str = os.path.join(DICT_ROOT, "npcs")


# ============================================================
# 章节加载
# ============================================================

@lru_cache(maxsize=8)
def load_chapter(stage_id: str) -> Optional[Dict[str, Any]]:
    """加载章节字典

    Args:
        stage_id: 章节ID，如 "survival" / "explore" / "build" / "climax"

    Returns:
        章节字典数据，包含：
        - stage_id / stage_name / sol_range / real_sol_range
        - narrative_focus / self_sufficiency_target
        - permanent_keywords: 永久关键词
        - temporary_keywords: 临时触发器（含 trigger/ttl/impact）
        - fsm: 章节状态机节点
        - stage_transition: 阶段切换条件
    """
    if not os.path.isdir(CHAPTERS_DIR):
        logger.error(f"chapters dir not found: {CHAPTERS_DIR}")
        return None

    for fname in os.listdir(CHAPTERS_DIR):
        if not fname.endswith(".yaml"):
            continue
        fpath = os.path.join(CHAPTERS_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data and data.get("stage_id") == stage_id:
                logger.info(f"loaded chapter: {stage_id} from {fname}")
                return data
        except Exception as e:
            logger.error(f"failed to load chapter {fname}: {e}")

    logger.warning(f"chapter not found: {stage_id}")
    return None


def list_chapters() -> List[str]:
    """列出所有可用章节ID（仅返回能成功解析的）"""
    if not os.path.isdir(CHAPTERS_DIR):
        return []
    result = []
    for fname in os.listdir(CHAPTERS_DIR):
        if not fname.endswith(".yaml"):
            continue
        fpath = os.path.join(CHAPTERS_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data and data.get("stage_id"):
                result.append(data["stage_id"])
        except Exception:
            # 跳过有语法错误的文件，不中断列表
            pass
    return result


# ============================================================
# 分支加载
# ============================================================

_BRANCH_ID_MAP = {
    "A": "branch_a_earth_rescue",
    "B": "branch_b_self_reliance",
    "C": "branch_c_discovery",
    "D": "branch_d_humanity_test",
}


@lru_cache(maxsize=8)
def load_branch(branch_id: str) -> Optional[Dict[str, Any]]:
    """加载主线分支事件剧本

    Args:
        branch_id: 分支ID，"A" / "B" / "C" / "D"

    Returns:
        分支数据，包含：
        - branch_id / branch_name / trigger_condition / endings
        - events: 主线节点事件
        - cross_branch_interactions: 跨分支交互
    """
    file_key = _BRANCH_ID_MAP.get(branch_id)
    if not file_key:
        logger.warning(f"unknown branch_id: {branch_id}")
        return None

    fpath = os.path.join(BRANCHES_DIR, f"{file_key}.yaml")
    if not os.path.isfile(fpath):
        logger.error(f"branch file not found: {fpath}")
        return None

    try:
        with open(fpath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        logger.info(f"loaded branch: {branch_id} from {file_key}.yaml")
        return data
    except Exception as e:
        logger.error(f"failed to load branch {branch_id}: {e}")
        return None


def list_branches() -> List[str]:
    """列出所有可用分支ID"""
    return list(_BRANCH_ID_MAP.keys())


# ============================================================
# 触发器提取
# ============================================================

def extract_triggers(chapter_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从章节字典提取临时触发器"""
    triggers = []
    for kw in chapter_data.get("temporary_keywords", []):
        trig = kw.get("trigger", {})
        if not trig.get("trigger_id"):
            continue
        trigger_entry = {
            "trigger_id": trig["trigger_id"],
            "trigger_type": trig.get("trigger_type", "state_match"),
            "condition": trig.get("condition", ""),
            "ttl": kw.get("ttl", {}),
            "keyword": kw.get("keyword", ""),
            "description": kw.get("description", ""),
            "bound_npc": kw.get("bound_npc", ""),
            "impact": kw.get("impact", []),
            "narrative_branch": kw.get("narrative_branch", ""),
            "proposed_by": kw.get("proposed_by", ""),
            "approval_required": kw.get("approval_required", ""),
        }
        triggers.append(trigger_entry)
    return triggers


def extract_fsm_nodes(chapter_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从章节字典提取 FSM 节点"""
    return chapter_data.get("fsm", []) or chapter_data.get("fsm_nodes", [])


def extract_stage_transition(chapter_data: Dict[str, Any]) -> Dict[str, Any]:
    """提取阶段切换条件"""
    return chapter_data.get("stage_transition", {})


# ============================================================
# 分支事件提取
# ============================================================

def extract_branch_events(branch_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从分支数据提取事件节点"""
    events = []
    for evt in branch_data.get("events", []):
        events.append({
            "event_id": evt.get("event_id", ""),
            "sol": evt.get("sol", 0),
            "npc": evt.get("npc", ""),
            "title": evt.get("title", ""),
            "description": evt.get("description", ""),
            "trigger": evt.get("trigger", {}),
            "player_options": evt.get("player_options", []),
            "ending_determination": evt.get("ending_determination", {}),
            "narrative_function": evt.get("narrative_function", ""),
        })
    return events


# ============================================================
# NPC 人设加载
# ============================================================

@lru_cache(maxsize=16)
def load_npc(npc_id: str) -> Optional[Dict[str, Any]]:
    """加载单个 NPC 的 YAML 人设

    Args:
        npc_id: NPC 标识（如 chen_hao / sophia）

    Returns:
        NPC 人设字典，或 None（未找到）
    """
    yaml_path = os.path.join(NPCS_DIR, f"npc_{npc_id}.yaml")
    if not os.path.exists(yaml_path):
        logger.warning(f"NPC YAML 未找到: {yaml_path}")
        return None
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        logger.debug(f"NPC YAML 加载成功: {npc_id}")
        return data
    except yaml.YAMLError as e:
        logger.error(f"NPC YAML 解析失败 {npc_id}: {e}")
        return None


def load_all_npcs() -> Dict[str, Dict[str, Any]]:
    """加载全部 NPC 人设

    Returns:
        {npc_id: npc_data} 字典
    """
    result: Dict[str, Dict[str, Any]] = {}
    if not os.path.isdir(NPCS_DIR):
        logger.warning(f"NPC 目录不存在: {NPCS_DIR}")
        return result
    for fname in sorted(os.listdir(NPCS_DIR)):
        if not fname.startswith("npc_") or not fname.endswith(".yaml"):
            continue
        npc_id = fname[4:-5]  # 去掉 "npc_" 前缀和 ".yaml" 后缀
        data = load_npc(npc_id)
        if data is not None:
            result[npc_id] = data
    return result


def extract_seed_memories(npc_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从 NPC 人设提取种子记忆列表

    NPC YAML 的 seed_memories 字段结构：
        - memory_id / type / content / emotional_intensity / event_type / sol

    Returns:
        种子记忆字典列表，每项补充 agent_id 字段
    """
    npc_id = npc_data.get("npc_id", "")
    memories = []
    for mem in npc_data.get("seed_memories", []):
        memories.append({
            "agent_id": npc_id,
            "memory_id": mem.get("memory_id", ""),
            "content": mem.get("content", ""),
            "memory_type": mem.get("type", "episodic"),
            "timestamp": f"Sol-{mem.get('sol', 0)}",
            "importance": mem.get("emotional_intensity", 0.5),  # 用情感强度作为重要性
            "emotional_intensity": mem.get("emotional_intensity", 0.5),
            "event_type": mem.get("event_type", "episodic"),
            "tags": [],
        })
    return memories


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    print("chapters:", list_chapters())
    print("branches:", list_branches())
