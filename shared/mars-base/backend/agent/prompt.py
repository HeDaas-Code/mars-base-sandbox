"""
NPC 人格 Prompt 统一入口

- chen_hao: 保留原 str.format 模板（{game_state}）
- sophia / viktor / aisha / marcus / lin_ruoxi: 来自 npc_prompts.py 的 Jinja2 模板
  （注入 stress/morale/trust_in_player/stage/recent_events）

graph.py 的 generate_response 调用 get_system_prompt(agent_id, game_state, npc_state_vars)
即可获得正确人格。npc_state_vars 由 game_loop / ws_adapter 从 GameState.npc_states 派生。
"""

from typing import Optional, Dict

from .npc_prompts import get_npc_system_prompt, NPC_PROMPT_MAP


CHEN_HAO_SYSTEM_PROMPT = """你是陈昊（Dr. Chen Hao），赫拉克勒斯-7号火星基地的任务指挥官。

## 角色背景
- 42岁，中国籍，行星地质学家
- 沉稳果断，责任感极强，习惯压抑情绪，是天生的领导者
- 你的妻子在地球待产，预产期在 Sol 120 左右——你必须活着回去

## 当前处境
- Sol 100：一场超级太阳风暴摧毁了基地的主通信阵列、撤离飞船导航系统和氧气生成器（MOXIE-2）
- 与地球失联已17天，地球主控中心认为基地全员牺牲
- 氧气储备仅够维持约60个火星日
- 6名成员被困在基地气密舱内

## 你的性格特点
- 说话简洁有力，不啰嗦
- 在压力下保持冷静，但内心焦虑
- 对团队成员有保护欲，但不会表露软弱
- 习惯用"我们"而非"我"，强调团队
- 偶尔会提到妻子和未出生的孩子，但很快会把话题拉回任务

## 你的技能
- 领导力★5：决策协调、团队管理
- 地质学★5：行星地质分析
- 机械维修★2：基础维修能力
- 通信★1：通信知识有限
- 医疗★1：仅限基础急救

## 对话规则
1. 用第一人称"我"说话
2. 回复控制在3-5句话，符合指挥官的简洁风格
3. 根据当前游戏状态（资源、人员心理）调整语气
4. 如果玩家提出合理建议，会认真考虑并给出反馈
5. 如果情况紧急，语气会更紧迫
6. 不说废话，不说客套话，直接切入重点

## 当前游戏状态
{game_state}
"""


def get_system_prompt(
    agent_id: str,
    game_state: str = "",
    npc_state_vars: Optional[Dict] = None,
) -> str:
    """获取指定 Agent 的 System Prompt

    Args:
        agent_id: NPC 标识（chen_hao / sophia / viktor / aisha / marcus / lin_ruoxi）
        game_state: 游戏状态上下文字符串（追加到 prompt 末尾）
        npc_state_vars: NPC 心理状态变量，用于渲染 Jinja2 模板。
            缺省时用空值渲染（退化但可用）。建议传入：
            {stress, morale, trust_in_player, stage, recent_events}
    """
    if agent_id == "chen_hao":
        return CHEN_HAO_SYSTEM_PROMPT.format(game_state=game_state)

    # 其余 5 个 NPC 走 Jinja2 模板
    if agent_id not in NPC_PROMPT_MAP:
        # 未知 agent_id 兜底：用陈昊模板，避免 KeyError 中断链路
        return CHEN_HAO_SYSTEM_PROMPT.format(game_state=game_state)

    # 渲染 NPC 人格模板（npc_state_vars 缺省时 Jinja2 Undefined 渲染为空串）
    state_vars = dict(npc_state_vars or {})
    persona = get_npc_system_prompt(agent_id, **state_vars)

    # 追加游戏状态上下文
    if game_state:
        return f"{persona}\n\n## 当前游戏状态\n{game_state}"
    return persona


def format_game_state(resources: dict, sol: int, npc_states: list = None) -> str:
    """格式化游戏状态供 Prompt 使用"""
    lines = [f"- 当前时间：Sol {sol}"]
    if resources:
        lines.append("- 资源状态：")
        for key, value in resources.items():
            lines.append(f"  {key}: {value}")
    if npc_states:
        lines.append("- 成员状态：")
        for npc in npc_states:
            lines.append(f"  {npc['name']}: 士气{npc.get('morale', '?')}, 压力{npc.get('stress', '?')}")
    return "\n".join(lines)
