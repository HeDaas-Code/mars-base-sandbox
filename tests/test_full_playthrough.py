#!/usr/bin/env python3
"""
全流程游玩日志脚本
==================
模拟完整游戏流程，记录所有输入输出，输出日志和问题报告。

用法:
  cd backend
  python ../tests/test_full_playthrough.py
"""

import sys
import os
import json
import time
import random
import traceback
from io import StringIO
from datetime import datetime

# 路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend'))

from agent.game_state import (
    create_initial_game_state,
    derive_current_state,
    build_emotion_hint,
    derive_emotion_label,
    check_resource_crisis,
    apply_sol_decay,
    NpcState,
)
from agent.event_scheduler import EventScheduler
from agent.game_loop import GameLoop


# ============================================================
# Mock chat_fn — 模拟 NPC 回复（无 LLM API Key 时）
# ============================================================

_NPC_REPLIES = {
    "chen_hao": {
        "氧气": "氧气储备还在下降。MOXIE-2 损毁后我们只能靠备用氧气罐撑着——大约还有60个Sol。",
        "通信": "主通信阵列彻底报废了。备用频段我试过，信号到不了地球。",
        "修": "维修方案我已经在脑子里过了三遍。问题是缺零件。",
        "士气": "大家的心理状态我一直在盯。只要任务还在推进，人就有盼头。",
        "撤离": "撤离飞船导航系统烧了，飞不起来。我们不走，我们留下。",
        "default": "收到。情况我了解了。现在需要的是行动方案，不是分析。",
    },
    "sophia": {
        "氧气": "MOXIE-2 的问题我知道。备用罐还有，但我在想办法修复循环系统。",
        "水": "水循环系统目前运行正常，但回收率只有70%，我需要更多过滤芯。",
        "食物": "食品储备还能撑40个Sol。如果温室建起来，可以延长。",
        "default": "我在实验室里忙着呢。有什么具体问题可以问我。",
    },
    "viktor": {
        "修": "修东西是我的老本行。但零件不够，巧妇难为无米之炊。",
        "电力": "太阳能板还在工作，但效率只有原来的60%。我在想办法清洁。",
        "default": "说重点。我不喜欢浪费时间。",
    },
    "aisha": {
        "通信": "我一直在尝试各种频率。说不定哪天地球就能收到我们的信号。",
        "雅典娜": "雅典娜系统有些异常响应。我在排查，但暂时没发现严重问题。",
        "default": "通讯舱这边一切正常。有消息我会第一时间通知。",
    },
    "marcus": {
        "伤": "目前没有严重伤员。但大家的精神状态需要关注，特别是长期隔离的压力。",
        "心理": "我建议定期进行心理评估。这种环境下，谁都可能出问题。",
        "default": "医疗舱随时待命。有身体不适立刻报告。",
    },
    "lin_ruoxi": {
        "风暴": "那场太阳风暴...我应该在预警阶段就发现异常的。是我的失职。",
        "气象": "目前火星表面天气稳定。但下一波太阳活动周期预计在Sol 180左右。",
        "default": "气象站运行正常。有异常我会报告。",
    },
}


def mock_chat_fn(player_input: str, agent_id: str, mode: str, npc_state_vars: dict) -> dict:
    """模拟 NPC 回复，返回 agent_message 信封"""
    replies = _NPC_REPLIES.get(agent_id, _NPC_REPLIES["chen_hao"])
    reply_text = replies.get("default", replies["default"])
    for keyword, text in replies.items():
        if keyword != "default" and keyword in player_input:
            reply_text = text
            break

    stress = npc_state_vars.get("stress", 0.3)
    morale = npc_state_vars.get("morale", 0.6)
    emotion_label = derive_emotion_label(stress, morale)
    label = agent_id[:4].upper()

    return {
        "msg_id": f"msg-mock-{int(time.time()*1000)%100000}",
        "type": "agent_message",
        "ts_tick": int(time.time()),
        "payload": {
            "sender_id": agent_id,
            "sender_label": label,
            "segments": [
                {"text": f"[{label}]> ", "protected": True, "tag": "speaker_label"},
                {"text": reply_text, "protected": False, "tag": "speech"},
            ],
            "signal_quality_pct": 62,
            "latency_ms": 800 + random.randint(0, 400),
            "emotion_hint": {
                "stress": round(stress, 2),
                "morale": round(morale, 2),
                "emotion_label": emotion_label,
            },
            "context_summary": {
                "history_count": 0,
                "k_limit": 6,
                "compressed_count": 0,
                "mode": mode,
            },
        },
    }


# ============================================================
# 日志记录器
# ============================================================

class PlaythroughLogger:
    def __init__(self):
        self.entries = []
        self.issues = []
        self.step = 0

    def log_input(self, action_type: str, content: str, extra: dict = None):
        self.step += 1
        entry = {
            "step": self.step,
            "timestamp": datetime.now().isoformat(),
            "direction": "INPUT",
            "type": action_type,
            "content": content,
        }
        if extra:
            entry["extra"] = extra
        self.entries.append(entry)
        print(f"\n{'='*60}")
        print(f"[Step {self.step}] INPUT ({action_type}): {content}")
        if extra:
            for k, v in extra.items():
                print(f"  {k}: {v}")

    def log_output(self, msgs):
        if not isinstance(msgs, list):
            msgs = [msgs]
        for msg in msgs:
            self.step += 1
            entry = {
                "step": self.step,
                "timestamp": datetime.now().isoformat(),
                "direction": "OUTPUT",
                "type": msg.get("type", "unknown"),
                "content": self._extract_text(msg),
                "raw": msg,
            }
            self.entries.append(entry)
            print(f"[Step {self.step}] OUTPUT ({msg.get('type', 'unknown')}): {self._extract_text(msg)[:200]}")

    def log_state(self, label: str, gs, scheduler):
        self.step += 1
        npc_summary = {}
        for nid, npc in gs.npc_states.items():
            npc_summary[nid] = {
                "stress": round(npc.stress, 2),
                "morale": round(npc.morale, 2),
                "trust": round(npc.trust_in_player, 1),
                "state": npc.current_state,
            }
        resources = {k: v.get("current", 0) for k, v in gs.resources.items()}
        info = scheduler.get_chapter_info()
        entry = {
            "step": self.step,
            "timestamp": datetime.now().isoformat(),
            "direction": "STATE",
            "label": label,
            "sol": gs.sol,
            "resources": resources,
            "npcs": npc_summary,
            "chapter": info,
            "athena": gs.athena_status,
            "signal": gs.signal_quality,
        }
        self.entries.append(entry)
        print(f"[Step {self.step}] STATE ({label}): Sol={gs.sol}, chapter={info['stage_id']}, "
              f"triggers={info['fired_triggers']}/{info['total_triggers']}, pending={info['pending_events']}")

    def log_issue(self, severity: str, description: str, context: dict = None):
        issue = {
            "step": self.step,
            "severity": severity,
            "description": description,
        }
        if context:
            issue["context"] = context
        self.issues.append(issue)
        marker = "🔴" if severity == "ERROR" else "🟡" if severity == "WARN" else "🔵"
        print(f"  {marker} ISSUE [{severity}]: {description}")

    def _extract_text(self, msg) -> str:
        payload = msg.get("payload", {})
        segs = payload.get("output_segments", payload.get("segments", []))
        if segs:
            return " ".join(s.get("text", "") for s in segs)
        if "description" in payload:
            return payload["description"]
        if "effects_summary" in payload:
            return payload["effects_summary"]
        return json.dumps(payload, ensure_ascii=False)[:200]

    def save_log(self, filepath: str):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"entries": self.entries, "issues": self.issues}, f, ensure_ascii=False, indent=2)
        print(f"\n日志已保存: {filepath}")


# ============================================================
# 全流程游玩
# ============================================================

def run_full_playthrough():
    logger = PlaythroughLogger()
    random.seed(42)

    print("=" * 60)
    print("  赫拉克勒斯协议 — 全流程游玩测试")
    print("  时间: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)

    # === 初始化 ===
    try:
        gs = create_initial_game_state()
        scheduler = EventScheduler(gs)
        gl = GameLoop(gs, scheduler, chat_fn=mock_chat_fn)
        logger.log_input("INIT", "create_initial_game_state + EventScheduler + GameLoop")
        logger.log_state("初始状态", gs, scheduler)
    except Exception as e:
        logger.log_issue("ERROR", f"初始化失败: {e}", {"traceback": traceback.format_exc()})
        return logger

    # === 启动游戏 ===
    try:
        gl.start("survival")
        logger.log_input("START", "gl.start('survival')")
        logger.log_state("游戏启动", gs, scheduler)
    except Exception as e:
        logger.log_issue("ERROR", f"启动失败: {e}", {"traceback": traceback.format_exc()})

    # === :help ===
    logger.log_input("META", ":help")
    result = gl.handle_meta("help", [])
    logger.log_output(result)

    # === :state ===
    logger.log_input("META", ":state")
    result = gl.handle_meta("state", [])
    logger.log_output(result)

    # === 对话：陈昊 - 氧气 ===
    logger.log_input("PLAYER_INPUT", "陈昊，氧气储备还剩多少？", {"target": "chen_hao"})
    result = gl.tick("陈昊，氧气储备还剩多少？", "chen_hao", "deliberate")
    logger.log_output(result)
    logger.log_state("对话后", gs, scheduler)

    # === 情感指令：安抚陈昊 ===
    logger.log_input("PLAYER_INPUT", "#soothe 你做得很好，别给自己太大压力", {"target": "chen_hao", "emotion": "soothe"})
    result = gl.tick("#soothe 你做得很好，别给自己太大压力", "chen_hao", "deliberate")
    logger.log_output(result)
    logger.log_state("安抚后", gs, scheduler)

    # === 情感指令：命令陈昊 ===
    logger.log_input("PLAYER_INPUT", "#command 立刻给我一份维修方案", {"target": "chen_hao", "emotion": "command"})
    result = gl.tick("#command 立刻给我一份维修方案", "chen_hao", "deliberate")
    logger.log_output(result)

    # === 切换 NPC：索菲亚 ===
    logger.log_input("META", ":npc sophia")
    result = gl.handle_meta("npc", ["sophia"])
    logger.log_output(result)

    # === 对话：索菲亚 - 水 ===
    logger.log_input("PLAYER_INPUT", "水循环系统怎么样？", {"target": "sophia"})
    result = gl.tick("水循环系统怎么样？", "sophia", "deliberate")
    logger.log_output(result)

    # === 情感指令：共情索菲亚 ===
    logger.log_input("PLAYER_INPUT", "#empathize 我知道你压力很大，但你的工作对大家很重要", {"target": "sophia", "emotion": "empathize"})
    result = gl.tick("#empathize 我知道你压力很大，但你的工作对大家很重要", "sophia", "deliberate")
    logger.log_output(result)
    logger.log_state("共情后", gs, scheduler)

    # === 切换 NPC：维克托 ===
    logger.log_input("META", ":npc viktor")
    result = gl.handle_meta("npc", ["viktor"])
    logger.log_output(result)

    # === 对话：维克托 - 修 ===
    logger.log_input("PLAYER_INPUT", "工程舱的设备能修好吗？", {"target": "viktor"})
    result = gl.tick("工程舱的设备能修好吗？", "viktor", "deliberate")
    logger.log_output(result)

    # === 情感指令：责备维克托 ===
    logger.log_input("PLAYER_INPUT", "#blame 你之前为什么没检查备用系统？", {"target": "viktor", "emotion": "blame"})
    result = gl.tick("#blame 你之前为什么没检查备用系统？", "viktor", "deliberate")
    logger.log_output(result)
    logger.log_state("责备后", gs, scheduler)

    # === 切换 NPC：艾莎 ===
    logger.log_input("META", ":npc aisha")
    result = gl.handle_meta("npc", ["aisha"])
    logger.log_output(result)

    # === 对话：艾莎 - 通信 ===
    logger.log_input("PLAYER_INPUT", "还有可能联系上地球吗？", {"target": "aisha"})
    result = gl.tick("还有可能联系上地球吗？", "aisha", "deliberate")
    logger.log_output(result)

    # === 切换 NPC：马库斯 ===
    logger.log_input("META", ":npc marcus")
    result = gl.handle_meta("npc", ["marcus"])
    logger.log_output(result)

    # === 对话：马库斯 - 心理 ===
    logger.log_input("PLAYER_INPUT", "大家的心理状态怎么样？", {"target": "marcus"})
    result = gl.tick("大家的心理状态怎么样？", "marcus", "deliberate")
    logger.log_output(result)

    # === 切换 NPC：林若曦 ===
    logger.log_input("META", ":npc lin_ruoxi")
    result = gl.handle_meta("npc", ["lin_ruoxi"])
    logger.log_output(result)

    # === 对话：林若曦 - 风暴 ===
    logger.log_input("PLAYER_INPUT", "那场风暴...你当时有预感吗？", {"target": "lin_ruoxi"})
    result = gl.tick("那场风暴...你当时有预感吗？", "lin_ruoxi", "deliberate")
    logger.log_output(result)

    # === 情感指令：闲聊 ===
    logger.log_input("PLAYER_INPUT", "#smalltalk 今天天气不错", {"target": "lin_ruoxi", "emotion": "smalltalk"})
    result = gl.tick("#smalltalk 今天天气不错", "lin_ruoxi", "deliberate")
    logger.log_output(result)

    # === :mode 切换 ===
    logger.log_input("META", ":mode reflexive")
    result = gl.handle_meta("mode", ["reflexive"])
    logger.log_output(result)

    logger.log_input("META", ":mode deep")
    result = gl.handle_meta("mode", ["deep"])
    logger.log_output(result)

    logger.log_input("META", ":mode deliberate")
    result = gl.handle_meta("mode", ["deliberate"])
    logger.log_output(result)

    # === :branch 查看 ===
    logger.log_input("META", ":branch")
    result = gl.handle_meta("branch", [])
    logger.log_output(result)

    # === :sol 推进循环（推进 15 个 Sol，触发事件） ===
    for i in range(15):
        logger.log_input("META", f":sol (第 {i+1}/15 次)")
        result = gl.handle_meta("sol", [])
        logger.log_output(result)

        # 检查是否有 story_event 附带
        followup = result.get("_followup_story_events", [])
        if followup:
            logger.log_output(followup)
            logger.log_state(f"Sol推进后(有事件) #{i+1}", gs, scheduler)

            # 处理每个事件：选择第一个选项
            for evt in followup:
                evt_id = evt["payload"]["event_id"]
                options = evt["payload"]["options"]
                if options:
                    opt_id = options[0]["option_id"]
                    logger.log_input("OPTION_SELECT", f"event={evt_id}, option={opt_id} ({options[0].get('label', '')})")
                    opt_result = gl.handle_option_select(evt_id, opt_id)
                    logger.log_output(opt_result)

                    # 检查是否触发结局
                    if opt_result.get("payload", {}).get("ending"):
                        logger.log_issue("INFO", f"结局触发: {opt_result['payload']['ending']}")
                        logger.log_state("结局", gs, scheduler)
                        logger.save_log(os.path.join(os.path.dirname(__file__), "playthrough_log.json"))
                        return logger
        else:
            if i % 5 == 4:
                logger.log_state(f"Sol推进后 #{i+1}", gs, scheduler)

        # 检查结局
        if gl.ending:
            logger.log_issue("INFO", f"游戏结束: {gl.ending}")
            logger.log_state("结局", gs, scheduler)
            break

    # === :skip 测试 ===
    logger.log_input("META", ":skip")
    result = gl.handle_meta("skip", [])
    logger.log_output(result)

    # === 最终状态 ===
    logger.log_input("META", ":state (最终)")
    result = gl.handle_meta("state", [])
    logger.log_output(result)
    logger.log_state("最终状态", gs, scheduler)

    # === :restart 测试 ===
    logger.log_input("META", ":restart")
    result = gl.handle_meta("restart", [])
    logger.log_output(result)
    logger.log_state("重启后", gs, scheduler)

    # === 保存日志 ===
    log_path = os.path.join(os.path.dirname(__file__), "playthrough_log.json")
    logger.save_log(log_path)

    return logger


# ============================================================
# 生成报告
# ============================================================

def generate_report(logger: PlaythroughLogger):
    print("\n" + "=" * 60)
    print("  全流程游玩问题报告")
    print("=" * 60)

    issues = logger.issues
    errors = [i for i in issues if i["severity"] == "ERROR"]
    warns = [i for i in issues if i["severity"] == "WARN"]
    infos = [i for i in issues if i["severity"] == "INFO"]

    print(f"\n总步骤数: {logger.step}")
    print(f"问题统计: {len(errors)} ERROR / {len(warns)} WARN / {len(infos)} INFO")

    if errors:
        print(f"\n--- ERROR ({len(errors)}) ---")
        for i, e in enumerate(errors):
            print(f"  {i+1}. [Step {e['step']}] {e['description']}")

    if warns:
        print(f"\n--- WARN ({len(warns)}) ---")
        for i, w in enumerate(warns):
            print(f"  {i+1}. [Step {w['step']}] {w['description']}")

    if infos:
        print(f"\n--- INFO ({len(infos)}) ---")
        for i, info in enumerate(infos):
            print(f"  {i+1}. [Step {info['step']}] {info['description']}")

    # 分析日志找隐性问题
    print("\n--- 隐性问题分析 ---")
    found_issues = 0

    # 1. 检查是否有 chat_fn 未注入的消息
    for e in logger.entries:
        if e.get("direction") == "OUTPUT":
            content = e.get("content", "")
            if "chat_fn 未注入" in content:
                logger.log_issue("ERROR", "chat_fn 未注入，NPC 无法回复")
                found_issues += 1

    # 2. 检查事件是否被正确触发
    sol_count = sum(1 for e in logger.entries if "Sol推进" in e.get("label", ""))
    event_count = sum(1 for e in logger.entries if e.get("type") == "story_event")
    if sol_count >= 10 and event_count == 0:
        print(f"  ⚠ 推进了 {sol_count} 个 Sol，但未触发任何 story_event")
        found_issues += 1
    else:
        print(f"  ✓ 推进 {sol_count} 个 Sol，触发 {event_count} 个 story_event")

    # 3. 检查结局是否触发
    ending_entries = [e for e in logger.entries if "结局" in e.get("label", "")]
    if not ending_entries:
        print("  ⚠ 15 个 Sol 推进后未触发任何结局（可能需要更多 Sol 或特定条件）")
    else:
        print(f"  ✓ 结局已触发")

    # 4. 检查 NPC 心理状态变化
    state_entries = [e for e in logger.entries if e.get("direction") == "STATE"]
    if len(state_entries) >= 2:
        first = state_entries[0].get("npcs", {})
        last = state_entries[-1].get("npcs", {})
        changes = []
        for nid in first:
            if nid in last:
                stress_diff = last[nid]["stress"] - first[nid]["stress"]
                morale_diff = last[nid]["morale"] - first[nid]["morale"]
                if abs(stress_diff) > 0.01 or abs(morale_diff) > 0.01:
                    changes.append(f"{nid}: stress{stress_diff:+.2f} morale{morale_diff:+.2f}")
        if changes:
            print(f"  ✓ NPC 心理状态变化: {'; '.join(changes)}")
        else:
            print("  ⚠ NPC 心理状态无变化（情感指令可能未生效）")

    # 5. 检查资源衰减
    if len(state_entries) >= 2:
        first_res = state_entries[0].get("resources", {})
        last_res = state_entries[-1].get("resources", {})
        res_changes = []
        for r in first_res:
            if r in last_res:
                diff = last_res[r] - first_res[r]
                if abs(diff) > 0.1:
                    res_changes.append(f"{r}: {first_res[r]}→{last_res[r]} ({diff:+.1f})")
        if res_changes:
            print(f"  ✓ 资源衰减: {'; '.join(res_changes)}")
        else:
            print("  ⚠ 资源无衰减（apply_sol_decay 可能未生效）")

    if found_issues == 0 and not errors:
        print("\n=== 结论: 全流程核心功能正常 ===")
    else:
        print(f"\n=== 结论: 发现 {len(errors) + found_issues} 个需关注的问题 ===")

    # 保存报告
    report_path = os.path.join(os.path.dirname(__file__), "playthrough_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 全流程游玩报告\n\n")
        f.write(f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**总步骤数**: {logger.step}\n")
        f.write(f"**问题统计**: {len(errors)} ERROR / {len(warns)} WARN / {len(infos)} INFO\n\n")
        f.write("## 问题列表\n\n")
        for i in issues:
            f.write(f"- **[{i['severity']}]** Step {i['step']}: {i['description']}\n")
        f.write("\n## 详细日志\n\n")
        f.write("完整日志见 `playthrough_log.json`\n\n")
        f.write("## 步骤摘要\n\n")
        for e in logger.entries:
            direction = e.get("direction", "?")
            etype = e.get("type", e.get("label", "?"))
            content = e.get("content", "")[:120]
            f.write(f"  Step {e['step']} [{direction}/{etype}]: {content}\n")
    print(f"\n报告已保存: {report_path}")


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    logger = run_full_playthrough()
    generate_report(logger)
