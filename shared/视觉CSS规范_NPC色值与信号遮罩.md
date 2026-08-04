# 视觉 CSS 规范：NPC 色值表 + 信号遮罩参数

> **用途**：供前端/引擎直接引用的 CSS 变量与类名规范  
> **编制**：幻影-视觉技术专家  
> **日期**：2026-08-02  
> **对应方案**：《视觉与界面概念设计方案 v2.0》第四节、第 4.5 节

---

## 一、NPC 视觉标识 CSS 色值表

### 1.1 CSS 变量定义

```css
:root {
  /* === 科研小组成员代表色 === */
  --npc-chenhao:   #ffb347;  /* 陈昊 ◆  深琥珀 */
  --npc-sophia:    #4a9d4a;  /* 索菲亚 ○  安全绿 */
  --npc-viktor:    #ffaa00;  /* 维克托 ▲  橙色 */
  --npc-aisha:     #66ccff;  /* 艾莎 ▾   冷蓝 */
  --npc-marcus:    #ffd699;  /* 马库斯 ✚  暖白 */
  --npc-linruoxi:  #8b6914;  /* 林若曦 ◇  暗琥珀 */

  /* === AI 系统代表色 === */
  --ai-courier:    #66ccff;  /* 信使 ◈   冷蓝 */
  --ai-athena:     #b399e6;  /* 雅典娜 ⬡  淡紫 */

  /* === 通用色（摘自 v2 方案 §1.2） === */
  --bg-primary:    #0a0805;  /* 主背景 */
  --bg-secondary:  #15100a;  /* 次背景/面板底 */
  --text-primary:  #ffb347;  /* 主文字 */
  --text-highlight:#ffd699;  /* 高亮文字 */
  --text-muted:    #8b6914;  /* 次要文字 */
  --color-warn:    #ff4444;  /* 警告色 */
  --color-notice:  #ffaa00;  /* 注意色 */
  --color-safe:    #4a9d4a;  /* 安全色 */
  --color-signal:  #66ccff;  /* 信号蓝 */
  --border-color:  #3d2b1f;  /* 边框线 */
}
```

### 1.2 NPC 标识符与类名映射

| 角色 | 符号 | 标签 | CSS 类名 | 代表色变量 | 说明 |
|------|------|------|---------|-----------|------|
| 陈昊 | `◆` | `[CMDR]` | `.npc-chenhao` | `--npc-chenhao` | 指挥官，双线边框暗示权威 |
| 索菲亚 | `○` | `[BIO]` | `.npc-sophia` | `--npc-sophia` | 生命保障，绿色系 |
| 维克托 | `▲` | `[ENG]` | `.npc-viktor` | `--npc-viktor` | 机械工程，橙色系 |
| 艾莎 | `▾` | `[COMM]` | `.npc-aisha` | `--npc-aisha` | 通信/AI，唯一冷色角色 |
| 马库斯 | `✚` | `[MED]` | `.npc-marcus` | `--npc-marcus` | 医疗，暖白 |
| 林若曦 | `◇` | `[ATM]` | `.npc-linruoxi` | `--npc-linruoxi` | 大气物理，暗琥珀 |
| 信使 | `◈` | `[COURIER]` | `.ai-courier` | `--ai-courier` | 通信中继 AI，系统消息风格 |
| 雅典娜 | `⬡` | `[ATHENA]` | `.ai-athena` | `--ai-athena` | 基地决策 AI，数据分析风格 |

### 1.3 NPC 消息样式类（建议）

```css
/* NPC 消息容器，按角色加修饰类 */
.npc-msg { font-family: 'JetBrains Mono', 'Sarasa Mono SC', monospace; }
.npc-msg .npc-id { font-weight: bold; margin-right: 0.5em; }
.npc-msg .npc-tag { font-size: 0.85em; opacity: 0.7; margin-right: 0.3em; }

/* 各角色标识符着色 */
.npc-chenhao  .npc-id { color: var(--npc-chenhao); }
.npc-sophia   .npc-id { color: var(--npc-sophia); }
.npc-viktor   .npc-id { color: var(--npc-viktor); }
.npc-aisha    .npc-id { color: var(--npc-aisha); }
.npc-marcus   .npc-id { color: var(--npc-marcus); }
.npc-linruoxi .npc-id { color: var(--npc-linruoxi); }
.ai-courier   .npc-id { color: var(--ai-courier); }
.ai-athena    .npc-id { color: var(--ai-athena); }

/* 指挥官特殊：双线边框（暗示军衔权威） */
.npc-chenhao .npc-card { border: 2px double var(--npc-chenhao); }

/* AI 系统特殊：无边框、纯系统消息风格 */
.ai-courier .npc-card, .ai-athena .npc-card { border: 1px dashed var(--border-color); }
```

### 1.4 通信状态色点

```css
/* NPC 通信状态指示灯（小圆点） */
.status-online   { background: var(--color-safe); }   /* 在线/活跃 */
.status-silent   { background: var(--color-notice); }  /* 静默 */
.status-offline  { background: #555; }                /* 离线 */
.status-unknown  { background: #555; animation: blink 1s infinite; } /* 未知 */
.status-emergency{ background: var(--color-warn); animation: blink 0.5s infinite; } /* 紧急 */

@keyframes blink {
  0%, 49% { opacity: 1; }
  50%, 100% { opacity: 0.2; }
}
```

---

## 二、信号四档遮罩 CSS 参数规范

### 2.1 四档信号质量分级

| 档位 | 信号质量 | 视觉表现 | 遮罩字符 | 字符透明度 | 动画时长 |
|------|---------|---------|---------|-----------|---------|
| L1 清晰 | 80-100% | 完整显示，无遮罩 | 无 | 1.0 | 无动画 |
| L2 轻微 | 50-79% | 偶发缺字，个别字符替换 | `▓` | 0.7 | 2s 闪烁 |
| L3 严重 | 20-49% | 频繁乱码，多处替换，句子断裂 | `▒` + `▓` 混合 | 0.5 | 1s 闪烁 |
| L4 极差 | 0-19% | 大面积乱码，仅偶有可辨识片段 | `▒` 为主 | 0.3 | 0.5s 抖动 |

### 2.2 遮罩字符 CSS 类定义

```css
/* === 信号遮罩字符样式 === */

/* L1 清晰：无处理 */
.sig-clear { /* 无遮罩，正常显示 */ }

/* L2 轻微缺字：单字符替换为 ▓ */
.sig-loss-l2 {
  display: inline-block;
  color: var(--text-muted);
  opacity: 0.7;
  animation: sig-flicker 2s ease-in-out infinite;
}

/* L3 严重乱码：▒▓ 混合，更低透明度 */
.sig-loss-l3 {
  display: inline-block;
  color: var(--text-muted);
  opacity: 0.5;
  animation: sig-flicker 1s ease-in-out infinite;
}

/* L4 极差：大面积 ▒，几乎不可读 */
.sig-loss-l4 {
  display: inline-block;
  color: var(--text-muted);
  opacity: 0.3;
  animation: sig-jitter 0.5s linear infinite;
}

/* === 关键帧动画 === */

/* L2/L3 闪烁：模拟信号不稳定 */
@keyframes sig-flicker {
  0%, 100% { opacity: var(--base-opacity, 0.7); }
  50%      { opacity: calc(var(--base-opacity, 0.7) * 0.6); }
}

/* L4 抖动：字符随机偏移 */
@keyframes sig-jitter {
  0%   { transform: translate(0, 0); }
  25%  { transform: translate(1px, -1px); }
  50%  { transform: translate(-1px, 1px); }
  75%  { transform: translate(1px, 1px); }
  100% { transform: translate(0, 0); }
}
```

### 2.3 信号噪点叠加层（全局）

信号差时在整个消息容器上叠加噪点效果：

```css
/* 信号噪点叠加层 */
.sig-noise-overlay {
  position: relative;
}
.sig-noise-overlay::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image: 
    repeating-linear-gradient(
      0deg,
      transparent 0px,
      transparent 2px,
      rgba(255, 179, 71, 0.03) 2px,
      rgba(255, 179, 71, 0.03) 3px
    );
  opacity: var(--noise-intensity, 0);
  transition: opacity 0.3s ease;
}

/* 按信号档位调整噪点强度 */
.sig-quality-l1 .sig-noise-overlay::after { --noise-intensity: 0; }
.sig-quality-l2 .sig-noise-overlay::after { --noise-intensity: 0.15; }
.sig-quality-l3 .sig-noise-overlay::after { --noise-intensity: 0.35; }
.sig-quality-l4 .sig-noise-overlay::after { --noise-intensity: 0.6; }
```

### 2.4 受保护内容标记

后端用标记区分受保护片段，前端对受保护内容不执行遮罩：

```css
/* 受保护内容：始终清晰显示，不受信号遮罩影响 */
.sig-protected {
  opacity: 1 !important;
  animation: none !important;
  color: var(--text-primary);
  font-weight: 500;
}

/* 受保护内容类型建议标记：
   - NPC 姓名/标签 → .sig-protected-name
   - 指令/任务关键 → .sig-protected-cmd
   - 数值数据      → .sig-protected-data
   - 系统消息/警报 → .sig-protected-alert
   以上均继承 .sig-protected 基础样式 */
```

### 2.5 前端渲染逻辑说明

```
渲染流程：
1. 后端返回消息文本 + 信号质量百分比 + 受保护片段标记
2. 前端根据信号质量选择档位 class（sig-quality-l1 ~ l4）
3. 遍历文本：
   a. 受保护片段 → 包裹 <span class="sig-protected">，不遮罩
   b. 未标记片段 → 按档位概率执行字符遮罩：
      - L2: ~15% 字符替换为 ▓
      - L3: ~45% 字符替换为 ▒/▓ 混合，随机插入断句符 //
      - L4: ~75% 字符替换为 ▒，仅保留少量可读片段
4. 在消息容器上叠加对应强度的噪点层
```

---

## 三、快速接入检查清单

| 项 | 状态 |
|----|------|
| NPC 色值 CSS 变量 | 已定义（§1.1） |
| NPC 标识符→类名映射 | 已定义（§1.2） |
| 通信状态色点 | 已定义（§1.4） |
| 四档遮罩字符与透明度 | 已定义（§2.1） |
| 遮罩动画关键帧 | 已定义（§2.2） |
| 噪点叠加层 | 已定义（§2.3） |
| 受保护内容样式 | 已定义（§2.4） |
| 前端渲染逻辑说明 | 已定义（§2.5） |

---

> 如需补充图标集、边框装饰等细节，随时找我。
