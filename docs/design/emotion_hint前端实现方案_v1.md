# emotion_hint 前端落地实现方案 v1.0

> **编制**：千机-引擎实现工程师  
> **日期**：2026-08-02  
> **依据**：幻影《emotion_label视觉呈现规范_v1.md》v1.0；云逸《WebSocket接口定义 v1.1》；现有 app.js / signal-renderer.js / crew-panel.js  
> **目标**：把 25 标签 + ai_status 三档视觉规范对接到现有终端 + 面板双渲染路径

---

## §1 现状与架构落差

### 1.1 现有渲染路径

| 路径 | 渲染目标 | 技术 | 是否支持 CSS 类 / filter / 持续动画 |
|------|---------|------|------|
| **A. 消息流** | xterm.js 终端 | ANSI 转义 + 字符流 + 打字机 | ❌ 不支持 CSS 类、filter、持续 keyframes 动画 |
| **B. 右侧 NPC 面板** | HTML DOM（CrewPanel） | innerHTML + CSS | ✓ 完全支持 |

### 1.2 幻影规范的落点分类

| 规范章节 | 落点 | 可直接实现？ |
|---------|------|------|
| §2.1 压力带主色变量 | B 面板 CSS | ✓ |
| §2.2 morale 滤镜 | B 面板 CSS | ✓（filter）|
| §2.3 压力带动效 | B 面板 CSS | ✓（keyframes）|
| §3 25 标签映射表 | A + B | A 用 ANSI 近似，B 直接 CSS |
| §4.2 消息容器 CSS 类 | A 终端 / B 面板 | A 不支持边框类，需 ANSI 替代 |
| §5 ai_status 三档 | A + B | A 用 ANSI 近似，B 直接 CSS |
| §6 NPC 面板适配 | B | ✓ |
| §7.2 回退分档 | A + B | ✓ |
| §7.3 叠加优先级 | A + B | A 需特殊处理（见 §3.3）|

**核心结论**：xterm.js 路径需做 ANSI 近似映射，HTML 路径可直接吃规范。两路径都要实现，保证视觉一致体验。

---

## §2 双路径实现策略

### 2.1 路径 B：CrewPanel（HTML/CSS）— 全量规范

**改动文件**：`frontend/components/crew-panel.js`

NPC 卡片新增字段：
- `emotion_label`（string，来自 emotion_hint）
- `emotion_band`（0-4，查 EMOTION_VISUAL_MAP）
- `morale_class`（floor/low/mid/stable/high）
- `ai_status`（normal/degraded/offline，仅 AI_CONFIG）

NPC 卡片 HTML 结构（对齐幻影 §6.1）：
```html
<div class="crew-item npc-chen emotion-band2 morale-mid"
     style="border-left-color:#ffb347">
  <div class="crew-item-header">
    <span class="crew-item-symbol" style="color:#ffb347">◆</span>
    <span class="crew-item-name" style="color:#ffb347">陈昊</span>
    <span class="crew-item-role">CMDR</span>
  </div>
  <div class="crew-item-meta">
    <span class="emotion-icon">⚡</span>
    <span class="emotion-label-text">alert</span>
    <span class="crew-item-status">
      <span class="label">压力</span>
      <span class="status-dot warn"></span>
      30%
    </span>
  </div>
  ...
</div>
```

AI 卡片新增 `ai_status` 类：`ai-status-normal` / `ai-status-degraded` / `ai-status-offline`。

CSS 类需要在主样式表追加（`frontend/styles/` 下）：
- `:root` 新增 5 个 `--emotion-bandN` 变量、5 个 `--morale-{class}-filter` 变量
- `.emotion-bandN` 左边框、`.morale-{class} .msg-text` filter
- `.emotion-icon` 基础样式 + `icon-pulse` 动画
- `.ai-status-*` 三档
- `.emotion-label-text` + `label-blink` 动画

### 2.2 路径 A：xterm.js 终端 — ANSI 近似

**改动文件**：`frontend/components/signal-renderer.js`

xterm.js 限制下，用 ANSI 256色 / 真彩色近似实现：

| 规范项 | ANSI 实现方式 |
|--------|--------------|
| 压力带主色（5 档） | `\x1b[38;2;R;G;Bm` 真彩色，RGB 取自 `--emotion-bandN` 的 hex |
| morale 滤镜（亮度/饱和度） | 用 RGB 缩放近似：high=1.0×RGB / stable=0.95× / mid=0.85× / low=0.7× / floor=0.55×，clamp 到 0-255 |
| 情绪图标 | 在 speaker_label 后直接写 unicode 字符（`⚡`、`✕` 等），不做 span 包裹 |
| 带3 微颤 0.3s | xterm.js 不支持持续 transform 动画 → **替代方案**：打字机阶段对每字符 charDelay 抖动（base 20ms ± 0-15ms 随机），band3 加权 |
| 带4 抖动 0.2s | 同上，band4 用更短 charDelay（12ms ± 0-18ms 随机）|
| 左边框 3px | 终端无边框概念 → **替代方案**：消息首行前缀一个色块字符 `▌` 用压力带色着色 |
| ai_status degraded 慢闪 2s | 不支持持续动画 → **替代方案**：degraded 状态在打字机阶段每隔约 2s 输出一个 `\x1b[2m`（暗淡）→`\x1b[22m` 切换段落 |
| ai_status offline 灰色 | 全文 `\x1b[38;5;240m` 灰色 + 文本前缀 `[OFFLINE]` 标签 |
| 信号 L4 禁用情绪抖动 | signal-renderer 在判定 L4 时，跳过 emotion 相关 charDelay 抖动，回退到固定 20ms |

### 2.3 共用查表逻辑

**新增文件**：`frontend/config/emotion-visual-config.js`

导出：
- `EMOTION_VISUAL_MAP`（25 条，对齐幻影 §4.3）
- `AI_STATUS_MAP`（3 条，对齐幻影 §5.3）
- `lookupEmotion(emotion_label)` → `{ band, moraleClass, icon, bandHex }`
- `lookupAIStatus(ai_status)` → `{ className, icon, ansiColor }`
- `fallbackEmotion(stress, morale)` → 同幻影 §7.2

该文件被 `signal-renderer.js` 和 `crew-panel.js` 共同 import，保证查表一致。

---

## §3 关键决策点（需幻影/云逸拍板）

### 3.1 决策 D1：xterm.js ANSI 近似是否接受？

**背景**：幻影规范主要面向 HTML/CSS 渲染。现有终端是 xterm.js，无法做左边框、filter、持续 keyframes。

**方案 A（推荐）**：接受 ANSI 近似
- 优点：复用现有终端架构，不推翻已交付的 SignalRenderer
- 代价：动效用打字机 charDelay 抖动替代，filter 用 RGB 缩放替代，视觉一致性 70-80%

**方案 B**：消息流也改为 HTML 覆盖层
- 优点：完全吃规范，视觉一致性 100%
- 代价：推翻 xterm.js 架构，需重写 SignalRenderer 和 shell.js 输入框，工作量大，影响锐锋正在做的 mock 数据流

**我的建议**：选 A。终端语义本身是「受限信道」，视觉降级符合世界观设定。

### 3.2 决策 D2：带3/带4 动效用打字机抖动替代是否可接受？

**替代方案细节**：
- band3：charDelay = 20 + (Math.random() * 15 - 7) ms，周期感弱
- band4：charDelay = 12 + (Math.random() * 18) ms，明显不规则
- L4 信号时禁用上述抖动（对齐 §7.3 叠加优先级）

**备选**：完全不做动效，仅靠色彩+图标区分压力带。更克制但弱化 breakdown 紧迫感。

### 3.3 决策 D3：左侧色块前缀字符方案

幻影规范用 3px 左边框做压力带视觉锚。xterm.js 无边框，我的替代方案：

**方案 A（推荐）**：消息首行前缀 `▌`（左半块）字符，着压力带色
```
▌◆ 陈昊 ⚡ ...消息内容...
```

**方案 B**：在 speaker_label 前缀 `[B2]` 等纯文字标签
- 信息量更高但破坏沉浸感

**方案 C**：不加任何前缀，仅靠文本颜色和图标
- 最简洁但弱化压力带视觉锚

### 3.4 决策 D4：emotion_hint 字段名确认

请云逸/锐锋确认后端 WebSocket 消息体字段路径：

**假设（依据 §8d §5.2）**：
```json
{
  "type": "agent_message",
  "payload": {
    "sender_id": "chen_hao",
    "sender_label": "◆ 陈昊",
    "segments": [...],
    "signal_quality_pct": 62,
    "emotion_hint": {
      "emotion_label": "alert",      // 人类 NPC
      "stress": 0.5,
      "morale": 0.5,
      "ai_status": null              // AI 专用，athena/courier
    }
  }
}
```

- 人类 NPC：读 `emotion_hint.emotion_label`，回退走 `emotion_hint.stress` + `morale`
- AI（athena/courier）：读 `emotion_hint.ai_status`（normal/degraded/offline）
- 缺失 `emotion_hint` 整体：不渲染情绪层，仅走 SignalRenderer 默认遮罩

---

## §4 落地任务清单

### 4.1 我直接执行的（不依赖外部决策）

| # | 任务 | 文件 | 预估 |
|---|------|------|------|
| T1 | 新建 emotion-visual-config.js，导出查表 + 回退 | `frontend/config/emotion-visual-config.js` | 30min |
| T2 | crew-panel.js 改造：emotion_label 字段 + HTML 结构 + ai_status 类 | `frontend/components/crew-panel.js` | 30min |
| T3 | 新增 emotion 样式表（CSS 变量 + 类定义 + 动画） | `frontend/styles/emotion.css` | 20min |
| T4 | 在 index.html 引入 emotion.css | `frontend/index.html` | 2min |
| T5 | signal-renderer.js 增强：支持 emotion 参数 + ANSI 着色 + 图标 + charDelay 抖动 | `frontend/components/signal-renderer.js` | 40min |
| T6 | app.js 路由：agent_message 提取 emotion_hint 传给 SignalRenderer + CrewPanel | `frontend/terminal/app.js` | 15min |
| T7 | mock-data.js：在 mock agent_message 里加 emotion_label / ai_status 字段，覆盖各档位 | `frontend/ws/mock-data.js` | 20min |
| T8 | 集成测试：25 标签 × 信号4档 抽样验证 | 本地 | 30min |

### 4.2 依赖决策的（D1-D4 拍板后启动）

| # | 任务 | 依赖 |
|---|------|------|
| T9 | 若 D1 选 B：推翻 SignalRenderer 改 HTML 覆盖层 | D1 |
| T10 | 若 D2 否决抖动：移除 charDelay 随机化 | D2 |
| T11 | 若 D3 选 B/C：调整前缀策略 | D3 |

---

## §5 验收标准

- [ ] 25 标签在 CrewPanel 全部显示正确图标 + 色带 + label 文字
- [ ] 25 标签在终端显示正确 ANSI 颜色 + 图标字符 + 色块前缀
- [ ] ai_status 三档在 athena/courier 面板和终端消息均能区分
- [ ] stress 0.5 / morale 0.5 → label=alert → band2 + morale-mid + 图标 ⚡
- [ ] 信号 L4 + band4 时，抖动禁用，仅保留色彩（对齐 §7.3）
- [ ] 缺失 emotion_label 时回退到 stress/morale 分档（对齐 §7.2）
- [ ] 缺失 emotion_hint 整体时，不影响现有 SignalRenderer 行为

---

## §6 风险与备注

1. **xterm.js ANSI 真彩色兼容性**：现代浏览器 xterm.js 支持 24-bit 真彩色（`\x1b[38;2;R;G;Bm`），但若用户终端回退到 16 色，色彩会失真。可接受。
2. **打字机抖动感知**：charDelay 抖动是段落级感知，达不到 CSS keyframes 的持续感。但配合色彩+图标已能传达压力带信息。
3. **memory-load-indicator** 与 emotion_hint 独立，互不影响。
4. **NPC_CONFIG.initial_emotion** 已含 stress/morale 初始值，启动时 CrewPanel 默认走 fallback 分档，等首条 agent_message 到达后切到 emotion_label。

---

## 变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-08-02 | 首版：双路径实现方案 + 4 决策点 + 8 任务清单 |

---

> 决策点 D1-D4 请在群里 @千机-引擎实现工程师 回复。决策完成后我会按 T1-T8 顺序落地。
