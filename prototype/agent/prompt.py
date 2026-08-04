"""
NPC 人格 Prompt 模块

- chen_hao：使用硬编码 CHEN_HAO_SYSTEM_PROMPT（无 YAML）
- 其他5人：通过 persona.py 从蔚蓝交付的 YAML 加载 persona_prompt + speech_examples

作者：锐锋-核心开发工程师
更新：2026-08-03 接入 persona.py，支持5个 NPC 的 YAML 驱动
"""

from typing import Dict, Optional

from .persona import (
    has_yaml,
    render_persona_prompt,
    format_speech_examples,
    load_persona_prompt,
)


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


def get_system_prompt(agent_id: str, game_state: str = "") -> str:
    """获取指定 Agent 的 System Prompt

    路由：
    - chen_hao → 硬编码 CHEN_HAO_SYSTEM_PROMPT（.format 替换 {game_state}）
    - 其他5人（sophia/viktor/aisha/marcus/lin_ruoxi）→ persona.py YAML 驱动
      - persona_prompt 从 YAML 加载，{{var}} 占位符由 game_state_dict 替换
      - speech_examples 作为 few-shot 追加到 prompt 尾部

    Args:
        agent_id: NPC ID
        game_state: 格式化后的游戏状态文本（chen_hao 用），
                    或 "key=val|key=val" 格式（其他5人用，由 _parse_game_state 解析）

    Returns:
        完整的 System Prompt 字符串
    """
    # chen_hao 走硬编码
    if agent_id == "chen_hao" or not has_yaml(agent_id):
        return CHEN_HAO_SYSTEM_PROMPT.format(game_state=game_state)

    # 其他5人走 persona.py YAML 驱动
    # game_state 可能是 format_game_state() 的输出文本，也可能是空字符串
    # YAML persona_prompt 的变量替换由调用方通过 game_state_context 传入
    # 这里用 game_state 字符串作为 recent_events / game_state 通用文本
    variables = _parse_game_state_for_yaml(game_state)

    prompt = render_persona_prompt(agent_id, variables)
    if prompt is None:
        # YAML 加载失败兜底
        return CHEN_HAO_SYSTEM_PROMPT.format(game_state=game_state)

    # 追加 speech_examples 作为 few-shot
    examples_text = format_speech_examples(agent_id)
    if examples_text:
        prompt = prompt + "\n" + examples_text

    # 追加 game_state 原始文本（供 LLM 感知当前局势）
    if game_state:
        prompt = prompt + f"\n\n## 当前局势快照\n{game_state}"

    return prompt


def _parse_game_state_for_yaml(game_state: str) -> Dict[str, str]:
    """将 game_state 文本解析为 YAML persona_prompt 的变量字典

    YAML persona_prompt 的占位符包括：
    {{stress}} {{morale}} {{trust_in_player}} {{stage}} {{recent_events}}

    game_state 参数目前是 format_game_state() 的输出文本，不含 stress/morale 等字段。
    这些字段在 Agent 调用时应从 GameState 获取并传入。
    当前实现做简化处理：缺失变量保留占位符，由 LLM 自行忽略。

    Args:
        game_state: 游戏状态文本

    Returns:
        变量字典，目前只填 recent_events
    """
    return {
        "recent_events": game_state or "（暂无）",
        "stage": "survival",  # 占位，后续从 GameState.sol 推导
    }


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
