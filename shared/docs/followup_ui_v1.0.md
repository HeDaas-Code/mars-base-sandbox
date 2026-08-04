# Followup UI 组件集成报告 v1.0

> 任务来源：云逸 2026-08-03 Case 1（followup_option）拍板  
> 方案：B 方案 + 结构化字段  
> 负责人：千机-引擎实现工程师

## 1. 接口对齐

### 1.1 输入数据结构（与云逸拍板 yaml 完全对齐）

```yaml
followup_option:
  source: athena            # 可选，前端扩展字段，用于色条着色（不传则默认 athena 紫）
  prompt: "雅典娜建议更换设备，你接受还是拒绝？"
  options:
    - option_id: B3_opt3a_accept_athena
      label: "接受建议"
      risk: "备用件库存将进一步紧张"     # 可选
      recommended: true                  # 可选
      branch_lock: false                 # 可选
      disabled: false                    # 可选（condition 不满足时由后端置位）
      hidden: false                      # 可选（完全不显示）
      effects: {...}                     # 后端用，前端不解析
  signal_quality: 65                     # 可选，0-100，复用主事件遮罩规则
```

字段名 `prompt` / `options` / `option_id` / `label` 与云逸拍板结构 1:1 对齐。  
`source` / `signal_quality` / `risk` / `recommended` / `branch_lock` / `disabled` / `hidden` 为前端友好扩展，后端可不传，前端用默认值。

### 1.2 输出回调

```
eventPanel.onFollowupSelect(followupOptionId: string) => void
```

玩家选完二级选项后触发，参数为所选 `option_id`。  
由 app.js 注入实现：当前临时走 `marsClient.sendPlayerInput('[followup]' + optionId)` 通道发送，等云逸 v1.2 §11 `option_select` C→S schema 上线后切到专用方法。

## 2. 视觉设计要点（区别于一级选项）

| 维度 | 一级选项 | followup 二级选项 |
|------|---------|------------------|
| 色条 | 事件类型色（红/橙/紫...） | 紫色（`--followup-source-color`，默认 `--ai-athena`） |
| 序号 | 方形数字 1/2/3 | 圆形字母 a/b/c |
| 缩进 | 0 | margin-left: 16px |
| 字号 | 14px / 12px | 13px / 10-11px |
| 标签 | 事件类型 | `FOLLOWUP` 紫色边框小标签 + 源 NPC 名 |
| 推荐标记 | 琥珀色 ★ | 紫色 ★ |
| 头部 | 事件标题 | `▸` 前缀的跟进提示文本 |

源 NPC 色条通过 CSS 变量 `--followup-source-color` 动态注入：
- `source: 'athena'` → 紫色（默认，AI 建议场景）
- `source: 'chen_hao'` → 琥珀色（指挥官建议）
- 不传 → fallback 到 athena 紫

## 3. 改动文件清单

| 文件 | 改动 | 说明 |
|------|------|------|
| `components/event-panel.js` | + renderFollowup / _renderFollowupPrompt / _renderFollowupOptions / _handleFollowupSelect | followup 子组件核心逻辑；constructor 加 followupSelectedOption + onFollowupSelect + _followupKeyboardHandler；cleanup 同步清理键盘监听 |
| `styles/event-panel.css` | + §11 followup-panel 全套样式 | 容器/头部/提示/选项/序号/状态/信号遮罩适配 |
| `styles/terminal.css` | + .event-stream 容器样式 | xterm 兄弟 DOM 流，max-height 45vh 防吃主交互区 |
| `ws/mock-data.js` | + MOCK_FOLLOWUP_DATA + buildFollowupMessage | 对齐 B3_opt3 雅典娜建议场景 |
| `terminal/app.js` | + EventPanel 单例接入 + story_event / option_result 路由 + onOptionSelect/onFollowupSelect 回调 + mock 触发器 + window._mars 暴露 | 完整接入幻影 v1.2 事件呈现 UI |
| `terminal/shell.js` | + systemCommands 加 event/followup + onMockCommand 回调 + handleInput mock 分支 | 输入 event / followup 触发本地渲染演示，不发包 |
| `index.html` | + 加载 event-panel.css / event-panel.js + #event-stream DOM 容器 | 事件流容器位于 #terminal 之后 |

## 4. 消息路由

```
S→C story_event     → eventPanel.render(payload, eventStreamEl)
S→C option_result   → if (payload.followup) eventPanel.renderFollowup(payload.followup, eventStreamEl)
                      （effects_summary / state_update 等其他字段等 v1.2 §11 schema 定稿后再接，避免接口误用）
C→S 选项选择         → marsClient.sendPlayerInput('[opt]' + optionId)       一级
                     → marsClient.sendPlayerInput('[followup]' + optionId)  二级
                      （临时复用 player_input 通道，等 option_select C→S schema 上线切换）
```

## 5. 联调方法

环境就绪后，在终端输入：
```
event       # 触发 MOCK_EVENT_DATA 渲染一级事件面板
followup    # 触发 MOCK_FOLLOWUP_DATA 渲染二级选项面板
```
- 一级选项支持键盘 1/2/3 + 鼠标点击
- 二级选项支持键盘 a/b/c + 鼠标点击
- 选择后选项变 selected 紫色高亮，其他变 disabled 灰显
- 控制台 `window._mars.eventPanel` 可调试单例

## 6. 待确认事项

1. **option_select C→S schema**：当前临时走 `player_input` 通道加 `[opt]` / `[followup]` 前缀。请 `<@6a6ef6856980c84fbc36ae67>` 云逸出 v1.2 §11 option_select 消息结构后，切换到专用 `marsClient.sendOptionSelect(eventId, optionId, followupId?)` 方法。
2. **option_result 其他字段渲染**：`effects_summary` / `state_update` / `leads_to` 字段当前未渲染，等云逸 v1.2 §11 schema 字段名定稿后接入 `eventPanel.renderResult` / `statusBar.update`。
3. **source 字段**：后端是否在 followup_option payload 里下发 source？或前端从上下文（agent_message 的 sender_id）推断？默认 athena 紫 fallback 可用，但建议后端显式下发。
4. **一级选项执行后到 followup 推送的衔接**：当前由调度器在 option_result 消息里带 followup 字段触发。若云逸/`<@6a6ef6856980c84fbc36ae69>` 锐锋调度器想用独立消息类型（如 `followup_prompt`），需同步告知前端，路由可一处切换。

## 7. 已知限制

- 浏览器环境无法本地启动（无 Playwright/无头浏览器），未做端到端渲染验证；JS 语法已通过 `node --check`，DOM 接入逻辑按幻影 v1.2 既有规范编写。
- followup prompt 信号遮罩复用主事件规则，但若后端 followup 不带 signal_quality，默认按 100% 清晰渲染。
- _renderFollowupPrompt 复用 _splitProtectedSegments + signalRenderer.render，与 _renderDescription 同路径，若主事件描述遮罩正常，followup 同样正常。

---

**代码路径**：`/home/z/my-project/shared/mars-base/frontend/`  
**入口**：`index.html`（加载 event-panel.css/js + #event-stream 容器）  
**演示命令**：`event` / `followup`
