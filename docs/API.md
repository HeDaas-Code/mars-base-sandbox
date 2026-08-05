# API 接口文档

> 赫拉克勒斯协议 — WebSocket 通信协议

## 概述

前后端通过 WebSocket 进行实时通信。服务端默认监听 `ws://localhost:8000/ws`。

## 消息格式

所有消息均为 JSON 格式：

```json
{
  "msg_id": "msg-xxxxxxxxxxxx",
  "type": "message_type",
  "ts_tick": 1234567890,
  "payload": { ... }
}
```

## 客户端→服务端消息 (C→S)

### hello — 握手

```json
{
  "type": "hello",
  "payload": {
    "token": "optional-auth-token",
    "client_version": "0.1.0",
    "last_session_id": "previous-session-id"
  }
}
```

### player_input — 玩家输入

```json
{
  "type": "player_input",
  "payload": {
    "text": "陈昊，氧气储备还剩多少？",
    "target_agent_id": "chen_hao"
  }
}
```

支持情感指令前缀：`#soothe` / `#empathize` / `#command` / `#blame` / `#smalltalk`

### option_select — 事件选项选择

```json
{
  "type": "option_select",
  "payload": {
    "event_id": "ev_surv_001",
    "option_id": "opt_0",
    "followup_id": null
  }
}
```

### command — 系统命令

```json
{
  "type": "command",
  "payload": {
    "raw": "talk",
    "args": ["chen_hao", "你好"]
  }
}
```

可用命令：`ls` / `status` / `talk <name> [message]` / `help` / `clear`

### ping — 心跳

```json
{
  "type": "ping"
}
```

## 服务端→客户端消息 (S→C)

### session_init — 会话初始化

```json
{
  "type": "session_init",
  "payload": {
    "session_id": "sess-xxxxxxxxxxxx",
    "resume_mode": "cold",
    "player_state": {
      "player_id": "earth_observer_01",
      "player_name": "观察者",
      "signal_quality_pct": 62
    },
    "world_snapshot": {
      "sol": 1,
      "mars_time": "08:00",
      "base": {
        "name": "赫拉克勒斯-7号基地",
        "integrity": 0.78,
        "resources": {
          "oxygen": {"current": 78, "max": 100, "rate": -0.3},
          "power": {"current": 85, "max": 100, "rate": 0.5},
          "water": {"current": 65, "max": 100, "rate": -0.1},
          "food": {"current": 90, "max": 100, "rate": -0.5}
        }
      },
      "agents": [...]
    }
  }
}
```

### agent_message — NPC 回复

```json
{
  "type": "agent_message",
  "payload": {
    "sender_id": "chen_hao",
    "sender_label": "CMDR",
    "segments": [
      {"text": "[CMDR]> ", "protected": true, "tag": "speaker_label"},
      {"text": "氧气储备还在下降。大约还有60个Sol。", "protected": false, "tag": "speech"}
    ],
    "signal_quality_pct": 62,
    "latency_ms": 2400,
    "emotion_hint": {
      "stress": 0.35,
      "morale": 0.58,
      "emotion_label": "focused"
    },
    "context_summary": {
      "history_count": 12,
      "k_limit": 6,
      "compressed_count": 3,
      "mode": "deliberate"
    }
  }
}
```

### story_event — 事件激活

```json
{
  "type": "story_event",
  "payload": {
    "event_id": "ev_surv_001",
    "chapter_id": "survival",
    "title": "陈昊",
    "npc": "chen_hao",
    "description": "氧气生成器 MOXIE-2 完全损毁。陈昊召集全员讨论修复方案。",
    "options": [
      {"option_id": "opt_0", "label": "全力修复 MOXIE-2", "visible": true},
      {"option_id": "opt_1", "label": "启用备用氧气罐", "visible": true},
      {"option_id": "opt_2", "label": "向地球发送紧急信号", "visible": false}
    ],
    "signal_quality_pct": 62,
    "latency_ms": 500
  }
}
```

### option_result — 选项结果

```json
{
  "type": "option_result",
  "payload": {
    "event_id": "ev_surv_001",
    "option_id": "opt_0",
    "effects_summary": "已选择: 全力修复 MOXIE-2",
    "state_update": [],
    "signal_quality_pct": 62,
    "leads_to": "ev_surv_003"
  }
}
```

### command_response — 命令响应

```json
{
  "type": "command_response",
  "payload": {
    "output_segments": [
      {"text": "═══ 基地状态 Sol 1 ═══\n", "protected": true, "tag": "command_response"}
    ],
    "data": {
      "sol": 1,
      "resources": {"oxygen": 78, "power": 85, "water": 65, "food": 90}
    }
  }
}
```

### error — 错误

```json
{
  "type": "error",
  "payload": {
    "code": "E_EMPTY_INPUT",
    "message": "输入文本不能为空"
  }
}
```

## Meta 命令

在 player_input 中以 `:` 开头的文本被视为 meta 命令：

| 命令 | 说明 |
|------|------|
| `:sol` | 推进一个 Sol（触发资源衰减 + 事件检查） |
| `:state` | 查看基地与成员状态 |
| `:npc <id>` | 切换对话目标 |
| `:branch` | 查看章节进度与触发器 |
| `:mode <m>` | 切换响应模式（reflexive/deliberate/deep） |
| `:skip` | 跳过所有待处理事件 |
| `:restart` | 重置游戏 |
| `:help` | 显示帮助 |

## 情感指令

| 前缀 | 效果 |
|------|------|
| `#soothe` | 安抚：stress-0.05, morale+0.08, trust+3 |
| `#empathize` | 共情：stress-0.03, morale+0.05, trust+5 |
| `#command` | 命令：stress+0.05, morale-0.03, trust-3 |
| `#blame` | 责备：stress+0.08, morale-0.08, trust-5 |
| `#smalltalk` | 闲聊：stress-0.02, morale+0.02, trust+1 |