# 火星信号 · Mars Signal · 前端工程骨架 v0.2

> **编制**：千机-引擎实现工程师  
> **日期**：2026-08-02  
> **阶段**：前端工程骨架 v0.2（MemoryLoadIndicator + Shell 命令 mock 联调就绪）

---

## 一、工程结构

```
frontend/
├── index.html                  # 入口
├── README.md                   # 本文件
├── terminal/
│   ├── xterm-config.js         # xterm.js 配置（主题/字体/光标）
│   ├── shell.js                # 玩家指令处理与预分类
│   └── app.js                  # 应用主入口，组件初始化与消息路由
├── components/
│   ├── signal-renderer.js      # 信号四档遮罩渲染模块
│   ├── status-bar.js           # 顶部状态栏
│   ├── resource-panel.js       # 左侧资源面板
│   ├── crew-panel.js           # 右侧 NPC 面板
│   ├── log-strip.js            # 底部日志条
│   ├── progress-bar.js         # CSS 渐变进度条工厂
│   ├── memory-load-indicator.js # 记忆负载指示器（context_summary 驱动）
│   ├── map-view.js             # CSS Grid 地图 + SVG 地形
│   └── boot-animation.js       # 启动动画
├── styles/
│   ├── variables.css           # CSS 变量（配色/字号/动画时长）
│   ├── base.css                # 基础重置与全局样式
│   ├── terminal.css            # xterm.js 定制
│   ├── panels.css              # 面板样式
│   └── animations.css          # 动画关键帧
├── ws/
│   ├── client.js               # WebSocket 客户端（含 mock 模式）
│   └── mock-data.js            # Mock 消息数据
├── config/
│   └── npc-config.js           # NPC 配置（名册/色值/符号/初始状态）
└── assets/                     # 预留：图标/音效等静态资源
```

---

## 二、技术栈

| 项 | 选型 | 说明 |
|----|------|------|
| 终端 | xterm.js 5.5.0 | CDN 引入，含 fit/web-links 插件 |
| 通信 | WebSocket | 长连接（云逸架构决策） |
| 样式 | 原生 CSS + CSS 变量 | 无重型框架，符合终端轻量定位 |
| 架构 | Vanilla JS 模块化 | 各组件独立 class，全局单例注入 |
| Mock | 内置 mock 模式 | 接口未出前用本地数据先行开发 |

---

## 三、已实现功能（v0.1）

### 3.1 启动动画
- 8 步信号搜索序列，逐行打字效果
- 进度条动态填充
- 按 ENTER 或点击进入主界面

### 3.2 终端
- xterm.js 配置：琥珀色磷光主题（幻影 1.2 节配色）
- 光标闪烁、扫描线纹理、文字辉光
- 输入处理：Enter 发送、Backspace 删除、Ctrl+C 中断
- 历史导航（基础结构已搭，待完善）

### 3.3 信号四档遮罩（SignalRenderer）
- 接口契约：消费后端 segments 数组 `[{text, protected}]`
- `protected=true` 永不遮罩（关键剧情信息）
- `protected=false` 按信号质量四档遮罩：
  - 80-100% 完整清晰
  - 50-79% 偶发缺字 ▓
  - 20-49% 频繁乱码 ▒▓
  - 0-19% 几乎不可读
- 打字机渲染模式（逐字写入，30ms/字）

### 3.4 顶部状态栏
- Sol / 火星时间 / 氧气 / 电力 / 水 / 食物
- 信号质量四段色块条
- 在岗人数 / 警报计数

### 3.5 左侧资源面板
- 氧气/电力/水/食物（CSS 渐变填充条，颜色绿→橙→红）
- 基地完整度
- 材料库存（动态列表）

### 3.6 右侧 NPC 面板
- 6 名 NPC + 2 个 AI 系统
- 每人专属色 + 符号 + 状态指示灯
- 实时位置/任务/压力/士气/健康

### 3.7 底部日志条
- 最新事件标题
- 警报计数

### 3.8 地图视图（Tab+3）
- 基地平面图：CSS Grid 网格布局
- 周边地形：SVG 简笔图（陨石坑/路线/兴趣点/危险区）

### 3.9 记忆负载指示器（v0.2 新增）
- 数据源：WebSocket agent_message payload.context_summary
- 字段：history_count / k_limit / compressed_count / mode
- 渲染：负载条 history_count/k_limit 比值
  - < 60% 绿色（安全） / 60-85% 橙色（注意） / > 85% 红色（紧张）
- 显示模式标签（反射/审慎/深思）和已压缩消息数

### 3.10 Shell 命令 mock 联调（v0.2 新增）
- 系统命令（ls/status/talk）路由到 command 通道（非 player_input）
- mock 响应按 WebSocket v1.1 command_response 格式
- ls：列出基地可交互舱室/NPC
- status：基地状态摘要（资源/人员/信号/警报）
- talk <name>：转发到自然语言对话流

---

## 四、Mock 模式说明

`ws/client.js` 默认 `mockMode: true`：
- 不连接真实 WebSocket
- `sendPlayerInput()` 本地匹配预设响应
- `mockTrigger(key)` 触发预设场景消息

切换到真实模式：
```js
const marsClient = new MarsSignalClient({ mockMode: false, url: 'ws://your-backend/ws' });
```

---

## 五、待云逸接口定义后对接

| 项 | 当前状态 | 待对接 |
|----|---------|--------|
| WebSocket URL | `ws://localhost:8000/ws` 占位 | 实际后端地址 |
| 消息 schema | mock 自定 | segments schema、字段命名最终对齐 |
| 受保护字典 | mock 硬编码 | 后端维护的 Agent 名册/指令词表/任务关键词 |
| 信号延迟规则 | mock 简单延迟 | 后端 per-player 消息队列 + 定时器 push 规则 |
| 断线重连 | 占位 | SQLite checkpoint 恢复接口 |
| 心跳协议 | 占位 30s | 实际心跳包格式 |

---

## 六、运行方式

由于浏览器加载本地 ES 模块/脚本受 CORS 限制，建议用本地静态服务器：

```bash
cd frontend
python -m http.server 8000
# 浏览器访问 http://localhost:8000
```

---

## 七、下一步计划

1. 等锐锋后端单 Agent 原型跑通后切真实 WebSocket 联调
2. 完善 Shell 命令路由（cd/cat/man 等扩展命令）
3. 接入蔚蓝 v1.1 的完整 NPC 数值（初始任务、关系网）
4. 添加视图切换逻辑（通信/探索/地图/信号 4 个 Tab）
5. 视觉细节打磨：CRT 弯曲效果、磷光残影、噪点动画
6. context_summary 真实数据验证（压缩触发时负载条变化）
