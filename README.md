# 赫拉克勒斯协议 (Heracles Protocol)

> 火星基地多智能体文字剧情沙盒游戏

**赫拉克勒斯协议** 是一款基于 LLM（大语言模型）驱动的多智能体交互式叙事游戏。玩家作为地球观察者，通过 WebSocket 终端与火星基地「赫拉克勒斯-7号」的 6 名被困宇航员进行实时对话，在超级太阳风暴后的生存危机中做出决策，影响基地命运与成员心理。

---

## 核心特性

- **多 NPC 人格系统**：6 名宇航员各自拥有独立的人格模板、记忆库、心理状态机（Stress/Morale/Trust），对话风格随心理状态动态变化
- **事件驱动游戏循环**：7 阶段 FSM 主循环，支持 Sol 推进、资源衰减、章节切换、结局判定
- **情感指令系统**：`#soothe` / `#empathize` / `#command` / `#blame` / `#smalltalk` 前缀影响 NPC 心理状态
- **4 分支 × 19 事件节点**：地球救援 / 自力更生 / 科学发现 / 人性考验，多结局叙事
- **WebSocket 实时通信**：终端式前端，支持 `agent_message` / `story_event` / `option_result` / `command_response` 消息协议
- **terra-faction-ui 视觉风格**：冷暗工业风，全直角 + 右上切角 + 平面/标尺分隔，移除 CRT 辉光/扫描线装饰
- **ChromaDB 向量记忆**：NPC 种子记忆 + 对话记忆压缩 + 语义检索召回

---

## 项目结构

```
/
├── README.md                   # 项目说明（本文件）
├── LICENSE                     # 开源协议
├── CONTRIBUTING.md             # 贡献指南
├── CHANGELOG.md                # 变更日志
├── .gitignore
├── backend/                    # 后端核心代码
│   ├── agent/                  # Agent 引擎
│   │   ├── game_loop.py        # 7 阶段主循环 FSM
│   │   ├── game_state.py       # 游戏世界状态（NPC 心理 + 资源 + 结局判定）
│   │   ├── event_scheduler.py  # 事件调度器
│   │   ├── chapter_loader.py   # 章节 YAML 加载器
│   │   ├── graph.py            # LangGraph Agent 链路
│   │   ├── prompt.py           # NPC 人格 Prompt 统一入口
│   │   ├── npc_prompts.py      # Jinja2 人格模板
│   │   ├── memory.py           # ChromaDB 记忆检索
│   │   ├── compress.py         # 对话压缩与摘要
│   │   ├── condition.py        # 安全条件表达式求值器
│   │   ├── config.py           # 全局配置
│   │   └── state.py            # Agent 对话状态
│   ├── ws_server.py            # WebSocket 服务器
│   ├── ws_adapter_v2.py        # WS 协议适配层（GameLoop 集成）
│   ├── ws_adapter.py           # WS 协议适配层（旧版兼容）
│   ├── main.py                 # 命令行交互入口
│   ├── seed_memories.py        # NPC 种子记忆
│   ├── benchmark.py            # 性能基准测试
│   └── data/                   # 运行时数据（不入库）
├── frontend/                   # 前端终端界面
│   ├── index.html              # 主页面
│   ├── components/             # UI 组件
│   ├── config/                 # 前端配置
│   ├── styles/                 # CSS 样式
│   ├── terminal/               # 终端逻辑
│   ├── ws/                     # WebSocket 客户端
│   └── preview/                # 预览页面
├── dict/                       # 游戏数据（YAML）
│   └── theme_mars_base/        # 项目固定配置包（单一题材，不支持主题切换）
│       ├── SCHEMA.md           # 数据格式说明
│       ├── chapters/           # 章节字典（4 章）
│       ├── events/mainline/    # 主线事件分支（4 分支）
│       └── npcs/               # NPC 人设（6 个）
├── tests/                      # 测试文件
├── prototype/                  # 历史原型代码
└── docs/                       # 项目文档
```

---

## 快速开始

### 环境要求

- Python 3.10+
- pip

### 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 配置 API Key

```bash
export LLM_API_KEY="your-api-key"
export LLM_BASE_URL="http://your-api-endpoint/v1"  # 可选，默认 MiniMax 兼容
```

### 启动 WebSocket 服务器

```bash
cd backend
python ws_server.py --port 8000
```

> 注：`ws_server.py` 已移除 `--theme` 参数，启动时自动加载固定配置 `dict/theme_mars_base`。引擎化是为了单一项目的数据驱动开发，不支持主题切换。

### 启动前端

用浏览器打开 `frontend/index.html`，或通过 HTTP 服务器托管：

```bash
cd frontend
python -m http.server 3000
```

### 命令行模式（无需前端）

```bash
cd backend
python main.py
```

---

## 游戏机制

| 机制 | 说明 |
|------|------|
| **Sol 推进** | 输入 `:sol` 推进一个火星日，触发资源衰减、事件检查、章节切换 |
| **NPC 对话** | 输入 `talk <name>` 或直接输入文字与当前 NPC 对话 |
| **情感指令** | `#soothe` / `#empathize` / `#command` / `#blame` / `#smalltalk` 前缀 |
| **事件选择** | 事件面板显示选项，点击后触发 `option_select` 回路 |
| **结局判定** | 7 种结局：E1 归航 / E2 火星之子 / E5 最后信号 / E6 守墓人 / E7 雅典娜觉醒 等 |

---

## 技术栈

- **后端**：Python 3.10+, LangGraph, LangChain, ChromaDB, WebSockets
- **前端**：原生 JavaScript, CSS, WebSocket API, xterm.js
- **数据**：YAML（章节/事件/NPC）, Jinja2（人格模板）
- **LLM**：OpenAI 兼容接口（MiniMax-M3 / GPT-4o 等）

---

## 文档

详细文档请参阅 [docs/](./docs/) 目录：

- [架构设计](./docs/architecture/) - 技术架构设计方案
- [API 接口](./docs/api/) - WebSocket 协议定义
- [游戏设计](./docs/design/) - 游戏系统设计、视觉概念
- [数据格式](./docs/data-format/) - 章节字典与事件 YAML 格式
- [开发指南](./docs/DEVELOPMENT.md) - 开发环境搭建与贡献指南

---

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](./LICENSE)。