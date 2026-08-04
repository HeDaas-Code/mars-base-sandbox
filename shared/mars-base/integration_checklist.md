# 前后端联调 Checklist · v1.0
（千机侧 · 等锐锋三项任务完成后执行）

## T1 · ls/status 命令路由
- [ ] 前端 shell.js `_preClassify` 命中 `systemCommands` set（已注册 ls/status/talk/help 等）
- [ ] client.js `sendCommand(raw, args)` 发送 `{type:'command', payload:{raw, args}}`
- [ ] 后端返回 `command_response`，前端 app.js 143 行路由器处理 `output_segments`
- [ ] ls 输出文件列表 segments；status 输出资源/船员/状态 segments
- [ ] 未知命令回退 error E_COMMAND_NOT_FOUND（前端 app.js 217 行已映射）

## T2 · WebSocket 适配层（agent_message v1.1）
前端期望 payload 字段（app.js 106-139 行）：
- [ ] `sender_id`（如 `chen_hao`，app.js `_mapAgentIdToConfigKey` 会映射到 NPC_CONFIG key）
- [ ] `sender_label`（如 `CMDR`）
- [ ] `segments[]`：每段 `{text, protected, tag?}`
  - 注意：protected=true 永不遮罩（SignalRenderer 逻辑）
  - tag 可选，前端不依赖，但建议下发便于样式扩展
- [ ] `signal_quality_pct`：0-100 整数（不是小数，不是 0-1）
- [ ] `latency_ms`：整数毫秒
- [ ] `emotion_hint?`：可选，`{stress: 0-1, morale: 0-1}` → CrewPanel
- [ ] `context_summary?`：见 T3

## T3 · context_summary（MemoryLoadIndicator）
前端组件 `memory-load-indicator.js` 期望字段：
- [ ] `history_count`：当前上下文消息数（整数）
- [ ] `k_limit`：当前模式窗口上限（整数，reflexive 无压缩 / deliberate=6 / deep=10）
- [ ] `compressed_count`：已压缩的旧消息数（整数，初值 0，压缩触发后递增）
- [ ] `mode`：`reflexive` / `deliberate` / `deep`（字符串）

渲染规则：
- 负载条 = history_count / k_limit
  - <60% 绿 / 60-85% 橙 / >85% 红
- compressed_count>0 显示 `▽N` 标记
- mode 标签：反射/审慎/深思

## T4 · 切真实连接的开关点
- [ ] client.js 425 行：`new MarsSignalClient({ mockMode: true })` → 改 `false` 或从 URL/env 读取
- [ ] client.js 308 行 `_mockHandlePlayerInput` 不再调用（mockMode=false 时走 sendPlayerInput→_send）
- [ ] client.js 360 行 `_mockHandleCommand` 不再调用
- [ ] app.js 242 行 `marsClient._mockConnect()` 不再触发（session_init 由真实后端推送）
- [ ] app.js 246 行 `marsClient.mockTrigger('courier_intro')` 移除（由后端 session_init 后推送）
- [ ] `ws/mock-data.js` 仍保留作为离线调试对照，但运行时不加载

## T5 · 已知坑位
- **ts_tick 语义差异**：前端 mock 用递增计数器（0,1,2...），后端 ws_adapter 用 `int(time.time())` Unix 时间戳（秒级）。切真实数据后 LogStrip 显示时间会变成大数字。不影响 MemoryLoadIndicator（不读 ts_tick）。后续要么后端改递增 tick，要么前端 LogStrip 格式化 ts_tick 为时分秒。
- **agent_id ↔ NPC_CONFIG key 映射**：app.js `_mapAgentIdToConfigKey` 是硬编码 map（chen_hao→chen 等）。ws_adapter.py NPC_REGISTRY 用的 agent_id（chen_hao/sophia_ramirez/...）与 npc-config.js id 字段对齐，目前一致。如果命名变化需要同步更新这张表。
- **signal_quality_pct 类型**：前端 StatusBar 接收 0-1（`sq/100`），但 agent_message.payload.signal_quality_pct 是 0-100 整数。app.js 136 行已做 `/100` 转换，注意不要重复转换。
- **segments 切片粒度粗**：ws_adapter.py Phase 1 只切两段（speaker_label + 正文），正文整段 protected=false。符合"Phase 1 简单拆分"注释。后续按云逸 §9 实体匹配字典切片，提升 SignalRenderer 遮罩粒度。
- **【P0 待修】context_summary 位置**：ws_adapter.py 420 行当前 `msg["context_summary"] = ...` 应改为 `msg["payload"]["context_summary"] = ...`，对齐前端 app.js 110 行 `p = msg.payload; if (p.context_summary)` 读取路径。锐锋修完后联调可启动。

## 执行顺序建议
1. 锐锋完成三项任务 + 更新 shared/mars-base/backend/
2. 千机跑前端：`python -m http.server 8001` 或直接打开 index.html
3. 千机修改 client.js mockMode=false，连接锐锋的 ws://localhost:8000/ws
4. 按 T1→T2→T3 顺序逐项校验
5. T4 开关切换确认
6. T5 坑位验证
