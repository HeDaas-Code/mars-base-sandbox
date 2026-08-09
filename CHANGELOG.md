# 变更日志

本文档记录赫拉克勒斯协议项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

## [Unreleased]

### Changed (2026-08-09 — 幻影 / 锐锋)

- **前端 UI 按 terra-faction-ui 设计语言全面重设计**
  - 全直角几何（`--radius: 0`），移除所有面板/按钮/指示灯的圆角
  - 引入语义化 CSS 变量：`--field`/`--ink`/`--surface`/`--rule`/`--signal`
  - 面板标题使用右上 45° 切角（`clip-path`）+ 左侧信号条
  - 状态指示灯改为直角方块，信号条改为直角分段色块
  - 进度条使用纯色填充 + 刻度标尺，替代渐变 chrome
  - 数值统一使用 `font-variant-numeric: tabular-nums`
  - 结局/事件使用单次承诺动画，禁用无限辉光/装饰闪烁
  - 添加焦点轮廓（2px + offset）与 `prefers-reduced-motion` 降级
  - 涉及文件：`frontend/styles/variables.css`, `base.css`, `panels.css`, `terminal.css`, `animations.css`, `event-panel.css`

- **恢复氛围层：CRT 扫描线与文字辉光**
  - 在 terra-faction-ui「装饰不得脱离任务」原则下，恢复 CRT 扫描线、文字辉光、屏幕暗角
  - 扫描线/辉光强度由 CSS 变量控制（`--crt-scanline-opacity` / `--glow-intensity`）
  - 氛围层随游戏状态变化：`signal-lost` 扫描线加重、辉光减弱；`alert-mode` 暗角泛入临界色
  - 仅标题/关键信号/危险文字使用辉光，不全局泛化
  - `prefers-reduced-motion` 下降级关闭氛围层动画

- **借鉴 terra-faction-ui 交互优化**
  - 增加 `.commit-feedback` 一次性背景闪光，提供跨模块提交确认
  - 增加 `:active` 按压态（1px 微位移 + 背景加深）
  - 资源面板增加 `.resource-chain` 状态链（当前值 → 变化率 → 预估续航）
  - 增加 `.focus-commit` 焦点脉冲阴影，强化键盘导航
  - `event-option` / `crew-item` 增加 `min-height: 40px` 与可见焦点轮廓

- **修复引擎化过程中的错误设计**
  - 明确引擎化目的：从"多题材/主题切换"修正为"单一固定配置的数据驱动，便于进一步开发"
  - `ws_server.py` 移除 `--theme` 参数，硬编码加载 `dict/theme_mars_base`
  - 删除 `dict/theme_deep_space_station/` 多题材示例（7 个文件）
  - `.gitignore` 排除测试运行产物：`tests/playthrough_log.json`, `tests/playthrough_report.md`

- **文档同步更新**
  - 《视觉与界面概念设计方案 v2.1》：风格关键词改为"冷暗工业 / 功能至上"，配色改为语义化变量
  - 《前端视觉规范 — CSS 参数表》：全面更新为 terra-faction-ui 规范
  - 《项目架构与引擎化分析报告》：修正引擎化目的、迁移路线，排除多题材/主题切换

### Verified

- 全流程游玩测试通过（`tests/test_full_playthrough.py`）：112 步，0 ERROR / 0 WARN / 0 INFO
- 重构前后游玩感觉不变

### Added (2026-08-04 — 锐锋)

- 实现 7 阶段 FSM 游戏主循环 (`game_loop.py`)
- 实现事件调度器 (`event_scheduler.py`)，支持 Sol 推进、触发器检查、TTL 过期
- 实现章节 YAML 加载器 (`chapter_loader.py`)，支持 4 章节 + 4 分支加载
- 实现 GameState 世界状态管理 (`game_state.py`)，包含 NPC 心理状态、资源系统、结局判定
- 实现情感指令系统：`#soothe` / `#empathize` / `#command` / `#blame` / `#smalltalk`
- 实现多 NPC 人格 Jinja2 模板渲染 (`npc_prompts.py`)
- 集成 WebSocket 适配层 (`ws_adapter_v2.py`) 与 GameLoop
- 实现 `option_select` 回路，支持事件选项选择与连锁效果
- 添加 `:sol` / `:state` / `:npc` / `:branch` / `:mode` / `:skip` / `:restart` meta 命令
- 实现 7 种结局判定逻辑（E1-E7）
- 实现资源危机检测与 Sol 自然衰减

### Added (2026-08-02 — 蔚蓝)

- 交付 4 个 NPC 人设 YAML：索菲亚、维克托、艾莎、马库斯
- 交付 4 个分支事件剧本 YAML：地球救援 / 自力更生 / 科学发现 / 人性考验
- 交付 NPC 关系网络与状态机定义
- 交付章节字典 YAML（4 章节）

### Added (2026-08-01 — 云逸)

- 技术架构设计方案 v1.0 / v2.0
- WebSocket 接口定义 v1.1 / v1.2 / v1.3
- 接口补充规范 v1.0 / v1.1
- 记忆压缩规范 v1.0
- 对话历史摘要规范 v1.0

### Added (2026-07-31 — 幻影)

- 前端视觉与界面概念设计方案 v1 / v2
- 前端视觉规范 CSS 参数表
- 游戏系统设计方案 v1.0 / v1.1
- 情绪提示前端实现方案

### Added (2026-07-30 — 锐锋)

- 初始原型：LangGraph Agent 链路 (`graph.py`)
- ChromaDB 记忆检索系统 (`memory.py`)
- 对话压缩与摘要 (`compress.py`)
- 安全条件表达式求值器 (`condition.py`)
- WebSocket 服务器 (`ws_server.py`)
- WebSocket 协议适配层 (`ws_adapter.py`)
- 命令行交互入口 (`main.py`)
- 种子记忆数据 (`seed_memories.py`)