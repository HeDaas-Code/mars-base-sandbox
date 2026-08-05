# 前端视觉规范 — CSS 参数表

> 供千机-引擎实现工程师直接引用  
> 来源：《视觉与界面概念设计方案 v2.0》  
> 编制：幻影-视觉技术专家

---

## 一、NPC 视觉标识 CSS 色值表

### 1.1 CSS 变量定义

```css
:root {
  /* 基础色板 */
  --bg-primary: #0a0805;
  --bg-secondary: #15100a;
  --text-primary: #ffb347;
  --text-highlight: #ffd699;
  --text-secondary: #8b6914;
  --color-warning: #ff4444;
  --color-caution: #ffaa00;
  --color-safe: #4a9d4a;
  --color-signal: #66ccff;
  --border-color: #3d2b1f;

  /* NPC 专属色 */
  --npc-chenhao: #ffb347;      /* 陈昊 - 深琥珀 */
  --npc-sophia: #4a9d4a;       /* 索菲亚 - 安全绿 */
  --npc-viktor: #ffaa00;       /* 维克托 - 橙色 */
  --npc-aisha: #66ccff;        /* 艾莎 - 冷蓝 */
  --npc-marcus: #ffd699;       /* 马库斯 - 暖白 */
  --npc-linruoxi: #8b6914;     /* 林若曦 - 暗琥珀 */
  --ai-courier: #66ccff;       /* 信使 - 冷蓝 */
  --ai-athena: #b399e6;        /* 雅典娜 - 淡紫 */
}
```

### 1.2 NPC 标识对照表

| 角色 | 符号 | CSS 变量 | HEX | 标签 | CSS 类名 |
|------|------|---------|-----|------|---------|
| 陈昊 | ◆ | `--npc-chenhao` | `#ffb347` | CMDR | `.npc-chenhao` |
| 索菲亚 | ○ | `--npc-sophia` | `#4a9d4a` | BIO | `.npc-sophia` |
| 维克托 | ▲ | `--npc-viktor` | `#ffaa00` | ENG | `.npc-viktor` |
| 艾莎 | ▾ | `--npc-aisha` | `#66ccff` | COMM | `.npc-aisha` |
| 马库斯 | ✚ | `--npc-marcus` | `#ffd699` | MED | `.npc-marcus` |
| 林若曦 | ◇ | `--npc-linruoxi` | `#8b6914` | ATM | `.npc-linruoxi` |
| 信使 | ◈ | `--ai-courier` | `#66ccff` | COURIER | `.ai-courier` |
| 雅典娜 | ⬡ | `--ai-athena` | `#b399e6` | ATHENA | `.ai-athena` |

### 1.3 NPC 消息样式类

```css
.npc-msg {
  color: var(--text-primary);
  font-family: "JetBrains Mono", "Sarasa Mono SC", monospace;
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

## 二、信号四档遮罩 CSS 参数规范

### 2.1 四档信号等级定义

| 档位 | 信号质量 | 遮罩字符 | 替换比例 | 透明度 | 动画时长 | CSS 类名 |
|------|---------|---------|---------|--------|---------|---------|
| L1 正常 | 80-100% | 无 | 0% | 1.0 | 无 | `.signal-l1` |
| L2 轻度 | 50-79% | `▓` U+2593 | ~15% 字符 | 0.85 | 0.3s | `.signal-l2` |
| L3 重度 | 20-49% | `▒▓` 混合 | ~45% 字符 | 0.6 | 0.2s | `.signal-l3` |
| L4 极差 | 0-19% | `▒▓█` 混合 | ~75% 字符 | 0.35 | 0.15s | `.signal-l4` |

### 2.2 遮罩字符说明

| 字符 | Unicode | 名称 | 用途 |
|------|---------|------|------|
| `░` | U+2591 | 浅色块 | L4 边缘噪声 |
| `▒` | U+2592 | 中色块 | L3 主要遮罩 |
| `▓` | U+2593 | 深色块 | L2/L3 缺字替换 |
| `█` | U+2588 | 实心块 | L4 大面积遮挡 |

### 2.3 CSS 样式定义

```css
/* === 信号遮罩基础类 === */

/* L1: 正常 — 无遮罩 */
.signal-l1 {
  opacity: 1;
  text-shadow: 0 0 2px var(--text-primary);
  animation: none;
}

/* L2: 轻度干扰 — 偶发缺字 */
.signal-l2 {
  opacity: 0.85;
  text-shadow: 0 0 1px var(--text-primary);
  animation: signal-jitter 0.3s ease-in-out infinite;
}

/* L3: 重度干扰 — 频繁乱码 */
.signal-l3 {
  opacity: 0.6;
  text-shadow: none;
  animation: signal-jitter 0.2s ease-in-out infinite,
             signal-flicker 0.5s steps(2) infinite;
}

/* L4: 极差 — 几乎不可读 */
.signal-l4 {
  opacity: 0.35;
  text-shadow: none;
  animation: signal-jitter 0.15s ease-in-out infinite,
             signal-flicker 0.3s steps(3) infinite;
  letter-spacing: 0.5px;
}

/* 受保护内容 — 任何档位都不遮罩 */
.signal-protected {
  opacity: 1 !important;
  text-shadow: 0 0 2px currentColor;
  animation: none !important;
}

/* === 关键帧动画 === */

/* 字符抖动：1-2px 随机偏移 */
@keyframes signal-jitter {
  0%, 100% { transform: translate(0, 0); }
  25%      { transform: translate(1px, 0); }
  50%      { transform: translate(-1px, 1px); }
  75%      { transform: translate(0, -1px); }
}

/* 闪烁：模拟信号不稳 */
@keyframes signal-flicker {
  0%, 100% { opacity: var(--flicker-base, 0.6); }
  50%      { opacity: calc(var(--flicker-base, 0.6) * 0.5); }
}

/* === 信号噪点叠加层 === */
.signal-noise-overlay {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  pointer-events: none;
  background-image: radial-gradient(
    circle at 50% 50%,
    transparent 0%,
    rgba(255, 179, 71, 0.03) 100%
  );
  mix-blend-mode: screen;
}
```

### 2.4 SignalRenderer 渲染逻辑建议

```typescript
// 前端渲染伪代码
interface Segment {
  text: string;
  protected: boolean;
}

function renderSegments(segments: Segment[], signalQuality: number): string {
  const level = getSignalLevel(signalQuality); // L1-L4
  const maskChars = getMaskChars(level);       // 对应档位的遮罩字符集
  const maskRatio = getMaskRatio(level);       // 对应档位的替换比例

  return segments.map(seg => {
    if (seg.protected) {
      return `<span class="signal-protected">${seg.text}</span>`;
    }
    // 对未保护文本按比例随机替换字符
    const masked = applyMask(seg.text, maskChars, maskRatio);
    return `<span class="signal-${level}">${masked}</span>`;
  }).join('');
}
```

### 2.5 信号档位映射函数

```typescript
function getSignalLevel(quality: number): string {
  if (quality >= 80) return 'l1';
  if (quality >= 50) return 'l2';
  if (quality >= 20) return 'l3';
  return 'l4';
}
```

---

## 三、进度条 CSS 参数

```css
.progress-bar {
  width: 100%;
  height: 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 0;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  transition: width 0.3s ease, background-color 0.3s ease;
}

/* 状态色：绿 → 橙 → 红 */
.progress-fill.status-safe    { background: linear-gradient(90deg, #3a7d3a, var(--color-safe)); }
.progress-fill.status-caution { background: linear-gradient(90deg, #cc8800, var(--color-caution)); }
.progress-fill.status-warning { background: linear-gradient(90deg, #cc3333, var(--color-warning)); }

/* 危险闪烁 */
.progress-fill.status-warning.critical {
  animation: progress-blink 0.8s ease-in-out infinite;
}

@keyframes progress-blink {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.4; }
}
```

---

## 四、面板边框通用样式

```css
.panel {
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  padding: 8px 12px;
}

.panel-title {
  font-family: "Share Tech Mono", monospace;
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 1px;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 4px;
  margin-bottom: 8px;
}

/* 警报状态：边框红色脉冲 */
.panel.alert {
  border-color: var(--color-warning);
  box-shadow: 0 0 8px rgba(255, 68, 68, 0.3);
  animation: alert-pulse 1s ease-in-out infinite;
}

@keyframes alert-pulse {
  0%, 100% { box-shadow: 0 0 8px rgba(255, 68, 68, 0.3); }
  50%      { box-shadow: 0 0 16px rgba(255, 68, 68, 0.6); }
}
```

---

> 如需补充图标集（状态指示灯、信号强度条等）的 CSS 参数，随时找我。
