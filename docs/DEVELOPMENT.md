# 开发指南

> 赫拉克勒斯协议 — 开发环境搭建与运行指南

## 环境要求

- Python 3.10+
- pip
- Git

## 本地开发环境搭建

### 1. 克隆仓库

```bash
git clone <repo-url>
cd <repo-name>
```

### 2. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows
```

### 3. 安装依赖

```bash
pip install langchain langchain-openai langgraph chromadb websockets pyyaml jinja2
```

### 4. 配置 API Key

```bash
export LLM_API_KEY="your-api-key"
# 可选：自定义 API 端点
export LLM_BASE_URL="http://your-api-endpoint/v1"
```

### 5. 启动后端服务

```bash
cd backend
python ws_server.py --port 8000
```

### 6. 启动前端（可选）

```bash
cd frontend
python -m http.server 3000
# 浏览器打开 http://localhost:3000
```

### 7. 命令行模式（无需前端）

```bash
cd backend
python main.py
```

## 项目模块说明

### 后端模块

| 文件 | 职责 |
|------|------|
| `ws_server.py` | WebSocket 服务器，处理连接与消息分发 |
| `ws_adapter_v2.py` | 协议适配层，集成 GameLoop |
| `agent/game_loop.py` | 7 阶段 FSM 游戏主循环 |
| `agent/game_state.py` | 游戏世界状态管理 |
| `agent/event_scheduler.py` | 事件调度器 |
| `agent/chapter_loader.py` | 章节 YAML 加载器 |
| `agent/graph.py` | LangGraph Agent 链路 |
| `agent/prompt.py` | NPC 人格 Prompt 入口 |
| `agent/npc_prompts.py` | Jinja2 人格模板 |
| `agent/memory.py` | ChromaDB 记忆检索 |
| `agent/compress.py` | 对话压缩与摘要 |
| `agent/condition.py` | 安全条件表达式求值器 |
| `agent/config.py` | 全局配置 |
| `agent/state.py` | Agent 对话状态 |
| `main.py` | 命令行交互入口 |
| `seed_memories.py` | NPC 种子记忆数据 |
| `benchmark.py` | 性能基准测试 |

### 前端模块

| 文件 | 职责 |
|------|------|
| `index.html` | 主页面 |
| `components/crew-panel.js` | 成员面板 |
| `components/event-panel.js` | 事件面板 |
| `components/resource-panel.js` | 资源面板 |
| `components/log-strip.js` | 日志条 |
| `components/status-bar.js` | 状态栏 |
| `terminal/app.js` | 终端主逻辑 |
| `terminal/shell.js` | Shell 命令处理 |
| `ws/client.js` | WebSocket 客户端 |
| `styles/` | CSS 样式 |

## 运行测试

```bash
cd backend
python -m pytest ../tests/ -v

# 运行特定测试
python -m pytest ../tests/test_integration.py -v
python -m pytest ../tests/test_phase1.py -v
```

## 模块自测

部分模块可直接运行进行自测：

```bash
cd backend
python -m agent.game_state     # GameState 自测
python -m agent.chapter_loader # 章节加载自测
```

## 常见问题

### Q: 启动时报 "websockets 库未安装"

```bash
pip install websockets
```

### Q: 启动时报 "LLM_API_KEY 未设置"

设置环境变量或使用 Mock 模式（无 API Key 时自动降级为规则匹配）。

### Q: 前端连接不上 WebSocket

- 确认后端已启动：`python ws_server.py --port 8000`
- 检查防火墙是否允许 8000 端口
- 检查前端 WebSocket 连接地址是否正确

### Q: ChromaDB 数据损坏

```bash
rm -rf backend/data/chroma_db/
# 重新启动后会自动重建
```

## 目录约定

- `backend/` — 后端 Python 代码
- `frontend/` — 前端 JS/CSS/HTML
- `dict/` — 游戏数据 YAML（策划编辑）
- `docs/` — 项目文档
- `tests/` — 测试文件
- `prototype/` — 历史原型代码（参考用）