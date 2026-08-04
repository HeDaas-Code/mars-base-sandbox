"""
章节与事件 YAML 加载器

从蔚蓝交付的 YAML 加载：
1. 章节字典（chapter_survival_sol1_10.yaml 等4个章节）
2. 主线分支事件（branch_a_earth_rescue.yaml 等4个分支）
3. 临时触发器（temporary_keywords 中的 trigger/ttl）
4. 永久关键词（permanent_keywords）

YAML 路径：
- /home/z/my-project/shared/mars-base/dict/chapters/chapter_<stage>_sol<range>.yaml
- /home/z/my-project/shared/mars-base/dict/events/mainline/branch_<id>_<name>.yaml

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
# 路径常量
# ============================================================

DICT_ROOT: str = "/home/z/my-project/shared/mars-base/dict"
CHAPTERS_DIR: str = os.path.join(DICT_ROOT, "chapters")
BRANCHES_DIR: str = os.path.join(DICT_ROOT, "events", "mainline")


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
    # 遍历 chapters 目录查找匹配 stage_id 的文件
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
    """列出所有可用章节ID"""
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
        - events: 5个主线节点事件
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
    """从章节字典提取临时触发器

    Args:
        chapter_data: load_chapter() 返回的章节字典

    Returns:
        触发器列表，每个触发器包含：
        - trigger_id / trigger_type / condition
        - ttl: {expire_type, expire_condition}
        - keyword / description / bound_npc / impact
    """
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
    """从章节字典提取 FSM 节点

    Returns:
        FSM 节点列表，每个节点包含：
        - node_id / sol / trigger_fires / description / next
    """
    return chapter_data.get("fsm", [])


def extract_stage_transition(chapter_data: Dict[str, Any]) -> Dict[str, Any]:
    """提取阶段切换条件"""
    return chapter_data.get("stage_transition", {})


# ============================================================
# 分支事件提取
# ============================================================

def extract_branch_events(branch_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从分支数据提取事件节点

    Args:
        branch_data: load_branch() 返回的分支数据

    Returns:
        事件节点列表，每个事件包含：
        - event_id / sol / npc / description
        - trigger: {trigger_type, condition}
        - player_options: 玩家可选项（含 effects / leads_to）
        - ending_determination: 结局判定条件
    """
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
# 模块自测
# ============================================================

def _self_test():
    print("=== chapter_loader.py 自测 ===\n")

    # 1. 章节列表
    chapters = list_chapters()
    print(f"可用章节: {chapters}")
    # survival/climax 有 YAML 语法错误，蔚蓝待修复；explore/build 正常
    assert "explore" in chapters or "build" in chapters, "至少 explore/build 应可用"

    # 2. 加载 explore 章节（survival 有 YAML 语法错误，暂用 explore 测试）
    test_stage = "explore" if "explore" in chapters else chapters[0] if chapters else None
    assert test_stage, "没有可用的章节"
    surv = load_chapter(test_stage)
    assert surv is not None
    print(f"\n--- {test_stage} 章节 ---")
    print(f"  stage_name: {surv['stage_name']}")
    print(f"  sol_range: {surv['sol_range']}")
    print(f"  permanent_keywords: {len(surv.get('permanent_keywords', []))} 条")
    print(f"  temporary_keywords: {len(surv.get('temporary_keywords', []))} 条")
    print(f"  fsm nodes: {len(surv.get('fsm', []))} 个")

    # 3. 提取触发器
    triggers = extract_triggers(surv)
    print(f"\n--- 触发器 ---")
    for t in triggers:
        print(f"  {t['trigger_id']}: type={t['trigger_type']}, condition='{t['condition'][:50]}'")
    print(f"  共 {len(triggers)} 条触发器")

    # 4. FSM 节点
    fsm = extract_fsm_nodes(surv)
    print(f"\n--- FSM 节点 ---")
    for node in fsm:
        print(f"  {node.get('node_id')}: Sol {node.get('sol')}, fires={node.get('trigger_fires', [])}")

    # 5. 阶段切换条件
    trans = extract_stage_transition(surv)
    print(f"\n--- 阶段切换 ---")
    print(f"  next_stage: {trans.get('next_stage_id')}")
    print(f"  condition: {trans.get('transition_condition')}")

    # 6. 分支加载
    branches = list_branches()
    print(f"\n--- 分支列表: {branches} ---")
    for bid in branches:
        bd = load_branch(bid)
        assert bd is not None
        events = extract_branch_events(bd)
        print(f"  {bid} ({bd['branch_name']}): {len(events)} 事件节点")
        for evt in events[:2]:
            print(f"    {evt['event_id']}: Sol {evt['sol']}, npc={evt['npc']}, options={len(evt['player_options'])}")

    # 7. 检查 survival/climax 的 YAML 语法错误
    for broken_stage in ("survival", "climax"):
        if broken_stage not in chapters:
            print(f"\n[警告] {broken_stage} 章节有 YAML 语法错误，需蔚蓝修复")

    print("\n=== 全部测试通过 ===")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    _self_test()
