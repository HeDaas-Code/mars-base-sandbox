# 前端视觉规范 — CSS 参数表

> 供千机-引擎实现工程师直接引用  
> 来源：《视觉与界面概念设计方案 v2.0》+ terra-faction-ui 设计语言修订  
> 编制：幻影-视觉技术专家  
> 修订日期：2026-08-09

---

## 一、设计原则

本前端采用 **terra-faction-ui** 设计语言，核心原则：

- **平面/标尺/蒙版优先于圆角卡片 chrome**
- **全直角**：`--radius: 0`，所有面板、按钮、指示灯均不使用圆角
- **右上切角**：`clip-path` 45° 切角作为"气闸门"隐喻，仅用于关键标题/入口
- **表格数字**：所有数值使用 `font-variant-numeric: tabular-nums`
- **克制元数据**：移除 CRT 扫描线、文字辉光等装饰性 HUD 噪声；技术可信度来自真实状态
- **语义化变量**：使用 `--field`/`--ink`/`--surface`/`--rule`/`--signal` 等命名，而非旧式 `--bg-primary`

---

## 二、CSS 语义变量

### 2.1 核心语义变量

```css
:root {
  /* === terra-faction-ui 语义变量 ===
     --field      主背景场（深空/火星表土）
     --ink        主前景文字（暖琥珀）
     --surface    表面/面板（略浅于 field）
     --surface-2  次级表面/标题背景
     --rule       分隔线/边框
     --signal     默认信号/选中（琥珀铜）
     --signal-ink 信号上的深色文字
     --signal-text 信号上的浅色文字
     --critical   临界/危险
     --cultural   次要文化色（基地结构） */
  --field: #0a0805;
  --ink: #d9b779;
  --surface: #14100a;
  --surface-2: #1c1610;
  --rule: #3d2b1f;
  --signal: #c89249;
  --signal-ink: #5a3d18;
  --signal-text: #14100a;
  --critical: #c84a3a;
  --cultural: #2e5c4a;

  /* 状态色 */
  --status-ok: #4a8d5a;
  --status-warn: #c89249;
  --status-danger: #c84a3a;
  --status-offline: #4a4035;

  /* 功能色 */
  --color-signal-blue: #5b9eb8;  /* 通信信号 */
  --color-athena: #9a7fb8;       /* 雅典娜 AI */

  /* 几何 */
  --radius: 0;                   /* 全直角 */
  --chamfer-size: 12px;          /* 右上切角大小 */
  --chamfer-top-right: polygon(
    0 0,
    calc(100% - var(--chamfer-size)) 0,
    100% var(--chamfer-size),
    100% 100%,
    0 100%
  );

  /* 焦点 */
  --focus-outline: 2px solid var(--signal);
  --focus-offset: 2px;

  /* 动画 */
  --anim-feedback: 200ms;    /* 直接反馈 160-280ms */
  --anim-commit: 500ms;      /* 主承诺 360-680ms */
  --anim-pulse: 2s;          /* 状态注意循环 1.6-2.4s */
}
```

### 2.2 向后兼容别名

旧变量名保留，映射到新语义变量，避免破坏现有 JS/CSS 引用：

```css
:root {
  --color-bg-primary: var(--field);
  --color-bg-secondary: var(--surface);
  --color-text-primary: var(--ink);
  --color-text-highlight: var(--signal);
  --color-text-secondary: #7a6440;
  --color-warning: var(--critical);
  --color-attention: var(--status-warn);
  --color-safe: var(--status-ok);
  --color-border: var(--rule);
}
```

---

## 三、NPC 视觉标识 CSS 色值表

### 3.1 NPC 专属色

| 角色 | 符号 | CSS 变量 | HEX | 标签 | CSS 类名 |
|------|------|---------|-----|------|---------|
| 陈昊 | ◆ | `--npc-chenhao` | `#c89249` | CMDR | `.npc-chenhao` |
| 索菲亚 | ○ | `--npc-sophia` | `#4a8d5a` | BIO | `.npc-sophia` |
| 维克托 | ▲ | `--npc-viktor` | `#d4a042` | ENG | `.npc-viktor` |
| 艾莎 | ▾ | `--npc-aisha` | `#5b9eb8` | COMM | `.npc-aisha` |
| 马库斯 | ✚ | `--npc-marcus` | `#c4a87a` | MED | `.npc-marcus` |
| 林若曦 | ◇ | `--npc-linruoxi` | `#8a6d3b` | ATM | `.npc-linruoxi` |
| 信使 | ◈ | `--ai-courier` | `#5b9eb8` | COURIER | `.ai-courier` |
| 雅典娜 | ⬡ | `--ai-athena` | `#9a7fb8` | ATHENA | `.ai-athena` |

### 3.2 NPC 消息样式类

```css
.npc-msg {
  color: var(--ink);
  font-family: var(--font-mono);
  margin: 4px 0;
  padding-left: 8px;
  border-left: 2px solid var(--rule);  /* 标尺式分隔，非圆角卡片 */
}

.npc-chenhao   { color: var(--npc-chenhao); }
.npc-sophia    { color: var(--npc-sophia); }
.npc-viktor    { color: var(--npc-viktor); }
.npc-aisha     { color: var(--npc-aisha); }
.npc-marcus    { color: var(--npc-marcus); }
.npc-linruoxi  { color: var(--npc-linruoxi); }
.ai-courier    { color: var(--ai-courier); }
.ai-athena     { color: var(--ai-athena); }
```

---

## 四、几何规范

### 4.1 全直角

所有容器、按钮、输入框、指示灯、进度条均使用 `--radius: 0`：

```css
.panel,
.button,
.input,
.progress-bar-container,
.status-dot,
.map-cell,
.tab {
  border-radius: var(--radius);  /* = 0 */
}
```

### 4.2 右上切角（气闸门隐喻）

仅用于**面板标题**、**启动标题**、**关键入口标识**，不得泛化到所有元素：

```css
.panel-title,
.resource-panel-title,
.crew-panel-title,
.boot-title {
  clip-path: var(--chamfer-top-right);
}
```

### 4.3 通用面板

```css
.panel {
  background-color: var(--surface);
  border: 1px solid var(--rule);
  padding: 8px;
}

.panel-title {
  font-family: var(--font-mono);
  font-size: var(--font-size-status);
  color: var(--signal-ink);
  text-transform: uppercase;
  letter-spacing: 1px;
  border-bottom: 1px solid var(--rule);
  padding: 4px 8px;
  margin-bottom: 6px;
  background-color: var(--surface-2);
  clip-path: var(--chamfer-top-right);
  border-left: 2px solid var(--signal);
}
```

---

## 五、信号四档遮罩 CSS 参数规范

### 5.1 四档信号等级定义

| 档位 | 信号质量 | 遮罩字符 | 替换比例 | 透明度 | CSS 类名 |
|------|---------|---------|---------|--------|---------|
| L1 正常 | 80-100% | 无 | 0% | 1.0 | `.signal-l1` |
| L2 轻度 | 50-79% | `▓` U+2593 | ~15% 字符 | 0.85 | `.signal-l2` |
| L3 重度 | 20-49% | `▒▓` 混合 | ~45% 字符 | 0.6 | `.signal-l3` |
| L4 极差 | 0-19% | `▒▓█` 混合 | ~75% 字符 | 0.35 | `.signal-l4` |

### 5.2 CSS 样式定义

```css
/* L1: 正常 — 无遮罩 */
.signal-l1 {
  opacity: 1;
  animation: none;
}

/* L2: 轻度干扰 — 偶发缺字 */
.signal-l2 {
  opacity: 0.85;
  animation: signal-jitter 0.3s ease-in-out infinite;
}

/* L3: 重度干扰 — 频繁乱码 */
.signal-l3 {
  opacity: 0.6;
  animation: signal-jitter 0.2s ease-in-out infinite alternate;
}

/* L4: 极差 — 几乎不可读 */
.signal-l4 {
  opacity: 0.35;
  animation: signal-jitter 100ms infinite alternate;
}

/* 受保护内容 — 任何档位都不遮罩 */
.signal-protected {
  opacity: 1 !important;
  animation: none !important;
}

/* 字符抖动：1px 随机偏移（功能性：真实信号降级） */
@keyframes signal-jitter {
  0% { transform: translateX(0); }
  25% { transform: translateX(-1px); }
  75% { transform: translateX(1px); }
  100% { transform: translateX(0); }
}
```

> **氛围层说明**：CRT 扫描线与文字辉光已恢复，但**服务于"远程终端/孤独感"叙事任务**，强度由 `--crt-scanline-opacity` / `--glow-intensity` 控制，并随 `signal-lost` / `alert-mode` 状态变化。信号遮罩仍承载真实 `signal_quality_pct` 值，氛围层不覆盖数据层。

---

## 五（附）. 氛围层：CRT 扫描线与文字辉光

### 5.1 设计原则

氛围层装饰恢复，但遵循 terra-faction-ui「装饰不得脱离任务」原则：

- **CRT 扫描线**：慢定向循环（10s），极淡（opacity 0.04），强化老式远程终端感
- **屏幕暗角**：边缘渐黑，强化聚焦与孤独感
- **文字辉光**：仅用于标题/关键信号/危险文字，不全局泛化
- **状态联动**：`signal-lost` 时扫描线加重、辉光减弱；`alert-mode` 时暗角泛入临界色

### 5.2 CSS 变量

```css
:root {
  --crt-scanline-opacity: 0.04;
  --crt-scanline-height: 2px;
  --crt-scanline-gap: 4px;
  --crt-scanline-speed: 10s;
  --crt-vignette-opacity: 0.25;
  --glow-intensity: 0.18;
  --glow-color: var(--signal);
}
```

### 5.3 动态扫描线元素

```html
<!-- 放在 body 开头，pointer-events: none -->
<div class="crt-scanline" aria-hidden="true"></div>
```

```css
.crt-scanline {
  position: fixed;
  left: 0;
  right: 0;
  height: var(--crt-scanline-height);
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(200, 146, 73, 0.08) 50%,
    transparent 100%
  );
  opacity: 0.5;
  pointer-events: none;
  z-index: 997;
  animation: crt-scan var(--anim-crt-scan) linear infinite;
}

@keyframes crt-scan {
  0% { transform: translateY(-100vh); }
  100% { transform: translateY(100vh); }
}
```

### 5.4 辉光工具类

```css
.glow-breathe    { animation: text-glow-breathe 8s ease-in-out infinite; }
.glow-strong     { text-shadow: 0 0 2px rgba(217,183,121,var(--glow-intensity)), 0 0 8px rgba(217,183,121,calc(var(--glow-intensity)*0.5)); }
.glow-signal     { text-shadow: 0 0 2px rgba(91,158,184,var(--glow-intensity)), 0 0 6px rgba(91,158,184,calc(var(--glow-intensity)*0.4)); }
.glow-critical   { text-shadow: 0 0 2px rgba(200,74,58,var(--glow-intensity)), 0 0 6px rgba(200,74,58,calc(var(--glow-intensity)*0.4)); }
```

### 5.5 可访问性降级

```css
@media (prefers-reduced-motion: reduce) {
  body { background-image: none; text-shadow: none; }
  body::before { content: none; }
  .crt-scanline { display: none; }
}
```

---

## 六、进度条 CSS 参数

```css
.progress-bar-container {
  height: 10px;
  background-color: var(--field);
  border: 1px solid var(--rule);
  overflow: hidden;
  position: relative;
  border-radius: var(--radius);
}

.progress-bar-fill {
  height: 100%;
  transition: width var(--anim-feedback) ease-out,
              background-color var(--anim-feedback) ease-out;
}

/* 进度条刻度标尺（terra-faction-ui: 标尺承载真实信息） */
.progress-bar-tick-marks {
  position: absolute;
  inset: 0;
  display: flex;
  pointer-events: none;
}

.progress-bar-tick-marks span {
  flex: 1;
  border-right: 1px solid rgba(0, 0, 0, 0.4);
}

.progress-bar-fill.status-ok    { background-color: var(--status-ok); }
.progress-bar-fill.status-warn  { background-color: var(--status-warn); }
.progress-bar-fill.status-danger {
  background-color: var(--critical);
  animation: pulse-danger var(--anim-pulse) infinite;  /* 状态注意循环 */
}

@keyframes pulse-danger {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.5; }
}
```

---

## 七、状态指示灯与信号强度条

### 7.1 状态指示灯（直角方块，非圆形）

```css
.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: var(--radius);  /* 0 = 方块 */
  margin-right: 4px;
  vertical-align: middle;
}

.status-dot.ok       { background-color: var(--status-ok); }
.status-dot.warn     { background-color: var(--status-warn); }
.status-dot.danger   { background-color: var(--critical); animation: pulse-danger var(--anim-pulse) infinite; }
.status-dot.offline  { background-color: var(--status-offline); }
.status-dot.unknown  { background-color: var(--status-offline); animation: blink-unknown 1.5s infinite; }
.status-dot.emergency { background-color: var(--critical); animation: blink-fast 0.5s infinite; }
```

### 7.2 信号强度四段色块条（直角）

```css
.signal-bars {
  display: inline-flex;
  gap: 2px;
  align-items: flex-end;
  height: 12px;
}

.signal-bar {
  width: 4px;
  background-color: var(--rule);
  transition: background-color var(--anim-feedback);
  border-radius: var(--radius);  /* 0 */
}

.signal-bar:nth-child(1) { height: 25%; }
.signal-bar:nth-child(2) { height: 50%; }
.signal-bar:nth-child(3) { height: 75%; }
.signal-bar:nth-child(4) { height: 100%; }

.signal-bar.lit        { background-color: var(--status-ok); }
.signal-bar.lit-warn   { background-color: var(--status-warn); }
.signal-bar.lit-danger { background-color: var(--critical); }
```

---

## 八、面板组件样式

### 8.1 资源面板标题

```css
.resource-panel-title {
  font-family: var(--font-mono);
  font-size: var(--font-size-status);
  color: var(--signal-ink);
  text-transform: uppercase;
  letter-spacing: 1px;
  padding: 4px 8px;
  margin-bottom: 8px;
  background-color: var(--surface-2);
  clip-path: var(--chamfer-top-right);
  border-left: 2px solid var(--signal);
}
```

### 8.2 NPC 条目（平面 + 左侧归属色条）

```css
.crew-item {
  margin-bottom: 6px;
  padding: 6px 8px;
  background-color: var(--field);
  border-left: 3px solid var(--rule);
  border-radius: var(--radius);
  transition: border-color var(--anim-feedback);
}

.crew-item:hover   { border-left-color: var(--signal); }
.crew-item.active  { border-left-color: var(--signal); background-color: var(--surface-2); }
```

### 8.3 警报状态

```css
.app-container.alert-mode {
  animation: alert-pulse var(--anim-pulse) infinite;
}

@keyframes alert-pulse {
  0%, 100% { box-shadow: inset 0 0 80px rgba(200, 74, 58, 0); }
  50%      { box-shadow: inset 0 0 80px rgba(200, 74, 58, 0.35); }
}
```

> **terra-faction-ui 说明**：警报只使用屏幕边缘内发光，不使用全局扫描线或文字辉光。

---

## 九、动画规范

遵循 terra-faction-ui motion-grammar：

| 类型 | 时长 | 用途 |
|------|------|------|
| 直接反馈 | 160-280ms | hover、选择、状态切换 |
| 主承诺 | 360-680ms | 事件到场、结局命中、章节切换 |
| 状态注意循环 | 1.6-2.4s | 危险脉冲、离线闪烁 |
| 慢定向循环 | 6-14s | 扫描线、待机指示 |

**禁止**：用动画暗示实时遥测，当底层值实际为静态。

### 9.1 到场动画

```css
@keyframes fade-in {
  from { opacity: 0; transform: translateY(4px); }
  to   { opacity: 1; transform: translateY(0); }
}

.fade-in { animation: fade-in 0.4s ease-out; }
```

### 9.2 结局承诺动画

```css
.ending-panel {
  margin: 8px 0;
  border: 2px solid var(--ai-athena);
  background-color: var(--surface);
  border-radius: var(--radius);
  animation: ending-commit 0.6s ease-out;  /* 单次，非无限 */
}

@keyframes ending-commit {
  from { opacity: 0; transform: scale(0.98); }
  to   { opacity: 1; transform: scale(1); }
}
```

---

## 十、可访问性

### 10.1 焦点轮廓

```css
button:focus-visible,
[tabindex]:focus-visible {
  outline: var(--focus-outline);
  outline-offset: var(--focus-offset);
}
```

### 10.2 点击目标

```css
.tab,
.event-option,
.followup-option {
  min-height: 40px;  /* 至少 40px 点击区域 */
}
```

### 10.3 减少动效降级

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## 十一、借鉴 terra-faction-ui 的优化

### 11.1 提交反馈（commit feedback）

选项/命令触发后，目标元素播放一次性背景闪光，提供跨模块确认：

```css
.commit-feedback {
  animation: commit-flash 0.5s ease-out;
}

@keyframes commit-flash {
  0% { background-color: rgba(200, 146, 73, 0.25); }
  100% { background-color: transparent; }
}
```

### 11.2 按压态（active state）

按钮/选项/条目按下时有 1px 微位移 + 背景加深，提供机械按压感：

```css
.event-option:active,
.crew-item:active {
  transform: translateY(1px);
  background-color: rgba(200, 146, 73, 0.12);
}
```

### 11.3 状态链 / 第二仪器

资源面板显示"当前值 → 变化率 → 预估续航"链式信息，作为第二仪器：

```css
.resource-chain {
  display: flex;
  gap: 4px;
  font-size: 10px;
  font-family: var(--font-mono);
  color: var(--color-text-secondary);
}
```

### 11.4 焦点承诺（focus commit）

焦点状态除轮廓外，增加柔和脉冲阴影，强化键盘导航可见性：

```css
.focus-commit {
  animation: focus-pulse 2s ease-in-out infinite;
}

@keyframes focus-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(200, 146, 73, 0.3); }
  50% { box-shadow: 0 0 0 3px rgba(200, 146, 73, 0.1); }
}
```

---

## 十二、实现检查清单

- [ ] 所有 `border-radius` 使用 `var(--radius)`（0）
- [ ] 面板标题使用 `clip-path: var(--chamfer-top-right)` + 左侧信号条
- [ ] 数值使用 `font-variant-numeric: tabular-nums`
- [ ] CRT 扫描线/辉光强度可控，服务于叙事任务，不覆盖数据层
- [ ] 状态指示灯为直角方块，非圆形
- [ ] 信号强度条为直角分段色块
- [ ] 进度条使用纯色填充 + 刻度标尺，不使用渐变 chrome
- [ ] 结局/事件使用单次承诺动画，不使用无限辉光
- [ ] 选项/条目提供 `:active` 按压态
- [ ] 资源面板提供状态链/第二仪器
- [ ] 所有焦点元素有可见 `2px` 轮廓 + offset
- [ ] 提供 `prefers-reduced-motion` 降级
