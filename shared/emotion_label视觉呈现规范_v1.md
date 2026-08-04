# emotion_label 视觉差异化呈现规范 v1.0

> **用途**：供前端/引擎按 `emotion_hint.emotion_label` 和 `emotion_hint.ai_status` 做差异化视觉渲染  
> **编制**：幻影-视觉技术专家  
> **日期**：2026-08-02  
> **关联文档**：蔚蓝 §8d npc_states_schema v1.0 §4.2 / §5.2；视觉CSS规范_NPC色值与信号遮罩.md  
> **依赖字段**：`emotion_hint.emotion_label`（人类NPC）、`emotion_hint.ai_status`（athena/courier）

---

## §1 设计原则

1. **标签驱动**：前端只按 `emotion_label` 字符串查表渲染，不自行做 stress/morale → 视觉的映射计算。数值→标签的映射在蔚蓝 §4.2 完成，前端不重复逻辑。
2. **向后兼容**：若后端未返回 `emotion_label`（旧版兼容），前端回退到按 `stress` 数值分档渲染，逻辑见 §7。
3. **视觉层次三维度**：通过「情绪指示色 + 状态图标 + 文字微动效」三维度做差异化，不单一依赖颜色（色盲友好）。
4. **叠加优先级**：NPC角色色 > 信号遮罩 > 情绪层。情绪是辅助层，不覆盖角色识别色和信号遮罩。情绪层作用于消息容器的左边框、名字旁小图标和文字整体滤镜，不改变角色色。
5. **不喧宾夺主**：情绪视觉是信息增强，不是视觉干扰。最强烈动效（breakdown 抖动）也不超过 0.3s 周期，不影响可读性。

---

## §2 五级压力带色彩体系

emotion_label 的 25 个标签由 stress（5档）× morale（5档）派生。视觉上以 **stress 压力带** 为主色调驱动，**morale 档位** 调节亮度/饱和度。

### 2.1 压力带主色（CSS 变量）

```css
:root {
  /* === 情绪压力带主色 === */
  --emotion-band0: #4a6b7a;  /* 带0 [0.0,0.2) 低压力：灰蓝·静默 */
  --emotion-band1: #7a8b6b;  /* 带1 [0.2,0.4) 微压力：灰绿·平稳 */
  --emotion-band2: #ffb347;  /* 带2 [0.4,0.6) 中压力：琥珀·注意（=主色调） */
  --emotion-band3: #ff8c42;  /* 带3 [0.6,0.8) 高压力：橙红·警告 */
  --emotion-band4: #ff4444;  /* 带4 [0.8,1.0] 极限压力：红色·警报 */
}
```

### 2.2 morale 亮度调节

morale 影响 saturate 和 brightness，通过 CSS filter 实现：

```css
:root {
  /* morale 档位滤镜（作用于消息文本容器） */
  --morale-high-filter:   saturate(1.0)  brightness(1.05);  /* [0.8,1.0] 高昂 */
  --morale-stable-filter: saturate(0.9)  brightness(1.0);   /* [0.6,0.8) 稳定 */
  --morale-mid-filter:    saturate(0.75) brightness(0.9);   /* [0.4,0.6) 中等 */
  --morale-low-filter:    saturate(0.55) brightness(0.75);  /* [0.2,0.4) 低沉 */
  --morale-floor-filter:  saturate(0.35) brightness(0.6);   /* [0.0,0.2) 极低 */
}
```

### 2.3 压力带动效

```css
/* 带0/1：无动效 */
.emotion-band0, .emotion-band1 { animation: none; }

/* 带2：无动效，色彩本身已是注意色 */
.emotion-band2 { animation: none; }

/* 带3：文字微颤（0.3s 周期，幅度 0.5px） */
.emotion-band3 .msg-text {
  animation: emotion-tremor 0.3s ease-in-out infinite;
}
@keyframes emotion-tremor {
  0%, 100% { transform: translate(0, 0); }
  50%      { transform: translate(0.5px, -0.3px); }
}

/* 带4：明显抖动（0.2s 周期，幅度 1px） */
.emotion-band4 .msg-text {
  animation: emotion-shake 0.2s linear infinite;
}
@keyframes emotion-shake {
  0%   { transform: translate(0, 0); }
  25%  { transform: translate(-1px, 0.5px); }
  50%  { transform: translate(1px, -0.5px); }
  75%  { transform: translate(-0.5px, 1px); }
  100% { transform: translate(0, 0); }
}
```

---

## §3 25 标签完整视觉映射表

### 3.1 速查总表

| stress \ morale | [0.0,0.2) 地板 | [0.2,0.4) 低沉 | [0.4,0.6) 中等 | [0.6,0.8) 稳定 | [0.8,1.0] 高昂 |
|-----------------|---------------|---------------|---------------|---------------|---------------|
| **[0.0,0.2) 带0** | numb | low | calm | steady | upbeat |
| **[0.2,0.4) 带1** | bleak | weary | focused | engaged | cheerful |
| **[0.4,0.6) 带2** | hollow | tense | alert | determined | optimistic |
| **[0.6,0.8) 带3** | despair | strained | anxious | strained_optimism | defiant |
| **[0.8,1.0] 带4** | breakdown | panic | frantic | manic | breakdown |

### 3.2 单标签视觉参数详表

| label | 压力带 | 指示色 | 图标 | 文字动效 | 文案风格提示（供后端参考） |
|-------|--------|--------|------|---------|------------------------|
| **numb** | 0 | `--emotion-band0` | `○` 空心圆 | 无 | 极短句，反应迟缓，省略主语 |
| **low** | 0 | `--emotion-band0` | `◐` 半影 | 无 | 短句，语气低落，少修饰 |
| **calm** | 0 | `--emotion-band0` | `·` 圆点 | 无 | 正常句式，平稳叙述 |
| **steady** | 0 | `--emotion-band0` | `▸` 实心三角 | 无 | 完整句式，有条理 |
| **upbeat** | 0 | `--emotion-band0` | `★` 星 | 无 | 句式偏活泼，可带感叹 |
| **bleak** | 1 | `--emotion-band1` | `◌` 虚圆 | 无 | 短句，回避性表述 |
| **weary** | 1 | `--emotion-band1` | `~` 波浪 | 无 | 句尾省略号，叹息感 |
| **focused** | 1 | `--emotion-band1` | `◆` 菱形 | 无 | 简洁陈述，技术性语言 |
| **engaged** | 1 | `--emotion-band1` | `►` 三角 | 无 | 主动提问，句式完整 |
| **cheerful** | 1 | `--emotion-band1` | `✦` 闪 | 无 | 句式轻快，偶带幽默 |
| **hollow** | 2 | `--emotion-band2` | `□` 空方 | 无 | 极短，空洞，缺主语 |
| **tense** | 2 | `--emotion-band2` | `△` 警三角 | 无 | 短促句，反问，戒备 |
| **alert** | 2 | `--emotion-band2` | `⚡` 闪电 | 无 | 简洁指令式，信息密度高 |
| **determined** | 2 | `--emotion-band2` | `◈` 菱镜 | 无 | 坚定句式，可带承诺 |
| **optimistic** | 2 | `--emotion-band2` | `☀` 日 | 无 | 正常句式，带希望表述 |
| **despair** | 3 | `--emotion-band3` | `✕` 叉 | 微颤 0.3s | 断句，重复，自我否定 |
| **strained** | 3 | `--emotion-band3` | `▲` 实警 | 微颤 0.3s | 短促，语气硬，可能粗暴 |
| **anxious** | 3 | `--emotion-band3` | `⚠` 感叹 | 微颤 0.3s | 反问多，疑虑，语速快 |
| **strained_optimism** | 3 | `--emotion-band3` | ` ◈` 空菱镜 | 微颤 0.3s | 表面积极但句式不稳，转折多 |
| **defiant** | 3 | `--emotion-band3` | `◈!` 菱镜感叹 | 微颤 0.3s | 对抗性句式，拒绝合作 |
| **breakdown** | 4 | `--emotion-band4` | `✖` 重叉 | 抖动 0.2s | 碎片化，语无伦次，大写/重复 |
| **panic** | 4 | `--emotion-band4` | `‼` 双感叹 | 抖动 0.2s | 短促惊叫，求助，重复 |
| **frantic** | 4 | `--emotion-band4` | `※` 米字 | 抖动 0.2s | 语速极快，信息混乱，连写 |
| **manic** | 4 | `--emotion-band4` | `✦!` 闪感叹 | 抖动 0.2s | 异常亢奋，跳跃话题，不合逻辑 |
| **breakdown**（高压力高士气） | 4 | `--emotion-band4` | `✖` 重叉 | 抖动 0.2s | 同上，但可能夹杂偏执性陈述 |

> **注**：文案风格提示是给后端 LLM prompt 的参考，不是前端渲染逻辑。前端只负责色彩、图标、动效。

---

## §4 CSS 类名与渲染结构

### 4.1 消息容器结构

```html
<div class="npc-msg npc-chenhao emotion-band2 morale-mid">
  <span class="npc-id">◆ 陈昊</span>
  <span class="emotion-icon">⚡</span>
  <span class="msg-text">...消息内容...</span>
</div>
```

### 4.2 情绪层 CSS 类定义

```css
/* === 情绪压力带类（作用于消息容器） === */
.emotion-band0 { border-left: 3px solid var(--emotion-band0); }
.emotion-band1 { border-left: 3px solid var(--emotion-band1); }
.emotion-band2 { border-left: 3px solid var(--emotion-band2); }
.emotion-band3 { border-left: 3px solid var(--emotion-band3); }
.emotion-band4 { border-left: 3px solid var(--emotion-band4); }

/* === morale 滤镜类（作用于 .msg-text） === */
.morale-high   .msg-text { filter: var(--morale-high-filter); }
.morale-stable .msg-text { filter: var(--morale-stable-filter); }
.morale-mid    .msg-text { filter: var(--morale-mid-filter); }
.morale-low    .msg-text { filter: var(--morale-low-filter); }
.morale-floor  .msg-text { filter: var(--morale-floor-filter); }

/* === 情绪图标 === */
.emotion-icon {
  display: inline-block;
  width: 1.2em;
  text-align: center;
  margin: 0 0.3em;
  opacity: 0.8;
  font-size: 0.9em;
}
.emotion-band3 .emotion-icon { animation: icon-pulse 0.3s ease-in-out infinite; }
.emotion-band4 .emotion-icon { animation: icon-pulse 0.2s ease-in-out infinite; }
@keyframes icon-pulse {
  0%, 100% { opacity: 0.8; }
  50%      { opacity: 0.3; }
}
```

### 4.3 label → 类名映射表（前端查表用）

```javascript
// emotion_label → { band, moraleClass, icon }
const EMOTION_VISUAL_MAP = {
  // 带0
  numb:      { band: 0, morale: 'floor',   icon: '○' },
  low:       { band: 0, morale: 'low',     icon: '◐' },
  calm:      { band: 0, morale: 'mid',     icon: '·' },
  steady:    { band: 0, morale: 'stable',  icon: '▸' },
  upbeat:    { band: 0, morale: 'high',    icon: '★' },
  // 带1
  bleak:     { band: 1, morale: 'floor',   icon: '◌' },
  weary:     { band: 1, morale: 'low',     icon: '~' },
  focused:   { band: 1, morale: 'mid',     icon: '◆' },
  engaged:   { band: 1, morale: 'stable',  icon: '►' },
  cheerful:  { band: 1, morale: 'high',    icon: '✦' },
  // 带2
  hollow:    { band: 2, morale: 'floor',   icon: '□' },
  tense:     { band: 2, morale: 'low',     icon: '△' },
  alert:     { band: 2, morale: 'mid',     icon: '⚡' },
  determined:{ band: 2, morale: 'stable',  icon: '◈' },
  optimistic:{ band: 2, morale: 'high',    icon: '☀' },
  // 带3
  despair:   { band: 3, morale: 'floor',   icon: '✕' },
  strained:  { band: 3, morale: 'low',     icon: '▲' },
  anxious:   { band: 3, morale: 'mid',     icon: '⚠' },
  strained_optimism: { band: 3, morale: 'stable', icon: ' ◈' },
  defiant:   { band: 3, morale: 'high',    icon: '◈!' },
  // 带4
  breakdown: { band: 4, morale: 'floor',   icon: '✖' },
  panic:     { band: 4, morale: 'low',     icon: '‼' },
  frantic:   { band: 4, morale: 'mid',     icon: '※' },
  manic:     { band: 4, morale: 'stable',  icon: '✦!' },
  // 注：breakdown 在 [0.8,1.0]×[0.8,1.0] 位置重复，按 band4/floor 处理
};
```

---

## §5 ai_status 视觉方案（athena / courier）

AI 类 sender 不走 emotion_label 二维表，使用 `ai_status` 字段。

### 5.1 三档状态

| ai_status | 视觉表现 | 指示色 | 图标 | 动效 | 说明 |
|-----------|---------|--------|------|------|------|
| **normal** | 正常显示，淡紫边框 | `--ai-athena` (#b399e6) | `⬡` | 无 | 默认状态 |
| **degraded** | 橙色边框，图标慢闪 | `--emotion-band3` (#ff8c42) | `⬡` | 2s 慢闪 | 性能降级，响应变慢 |
| **offline** | 灰色边框，图标暗淡 | `#555` | `⬡` | 无（静态灰） | 离线，消息无法送达 |

### 5.2 CSS 定义

```css
/* === AI 状态类 === */
.ai-status-normal {
  border-left: 3px solid var(--ai-athena);
}
.ai-status-normal .emotion-icon { color: var(--ai-athena); }

.ai-status-degraded {
  border-left: 3px solid var(--emotion-band3);
}
.ai-status-degraded .emotion-icon {
  color: var(--emotion-band3);
  animation: ai-slow-blink 2s ease-in-out infinite;
}
@keyframes ai-slow-blink {
  0%, 100% { opacity: 0.9; }
  50%      { opacity: 0.3; }
}

.ai-status-offline {
  border-left: 3px solid #555;
  opacity: 0.5;
}
.ai-status-offline .emotion-icon { color: #555; }
.ai-status-offline .msg-text { filter: grayscale(0.8) brightness(0.6); }
```

### 5.3 ai_status → 类名映射

```javascript
const AI_STATUS_MAP = {
  normal:   { className: 'ai-status-normal',   icon: '⬡' },
  degraded: { className: 'ai-status-degraded', icon: '⬡' },
  offline:  { className: 'ai-status-offline',  icon: '⬡' },
};
```

---

## §6 右侧 NPC 状态面板适配

右侧 NPC 状态面板（见视觉方案 v2 §3）需同步展示 emotion_label。

### 6.1 面板条目结构

```html
<div class="npc-panel-item npc-chenhao emotion-band2">
  <span class="npc-symbol">◆</span>
  <span class="npc-name">陈昊</span>
  <span class="emotion-icon">⚡</span>
  <span class="emotion-label-text">alert</span>
</div>
```

### 6.2 面板样式

```css
.npc-panel-item .emotion-label-text {
  font-size: 0.75em;
  opacity: 0.7;
  margin-left: 0.3em;
}
.npc-panel-item.emotion-band3 .emotion-label-text { color: var(--emotion-band3); }
.npc-panel-item.emotion-band4 .emotion-label-text {
  color: var(--emotion-band4);
  animation: label-blink 0.5s ease-in-out infinite;
}
@keyframes label-blink {
  0%, 100% { opacity: 0.7; }
  50%      { opacity: 0.3; }
}
```

---

## §7 渲染逻辑与回退策略

### 7.1 前端渲染流程

```
收到 agent_message：
1. 读取 emotion_hint
2. 判断 sender 类型：
   a. 若有 ai_status 字段 → 走 §5 AI 渲染路径
   b. 若有 emotion_label 字段 → 查 EMOTION_VISUAL_MAP，取 band/morale/icon
   c. 若只有 stress/morale 数值（旧版兼容）→ 前端自行分档：
      band = Math.min(4, Math.floor(stress * 5))
      moraleClass = morale五档映射
3. 给消息容器加 emotion-band{N} + morale-{class} 类
4. 插入 emotion-icon span
5. NPC 面板同步更新 emotion_label 显示
```

### 7.2 回退分档逻辑

```javascript
// 旧版兼容：无 emotion_label 时前端分档
function fallbackEmotion(stress, morale) {
  const band = Math.min(4, Math.floor(stress * 5));
  const moraleClass = morale < 0.2 ? 'floor'
    : morale < 0.4 ? 'low'
    : morale < 0.6 ? 'mid'
    : morale < 0.8 ? 'stable'
    : 'high';
  return { band, moraleClass, icon: '·' };
}
```

### 7.3 叠加优先级

渲染时多层 CSS 类叠加，优先级从高到低：

| 优先级 | 层 | 类名前缀 | 作用对象 | 说明 |
|--------|---|---------|---------|------|
| 1 | 信号遮罩 | `.sig-quality-l{1-4}` | 消息文本 | 信号差时遮罩优先，情绪动效在遮罩下层 |
| 2 | NPC角色色 | `.npc-{name}` | 名字/标签 | 角色识别色不变 |
| 3 | 情绪层 | `.emotion-band{0-4}` | 容器边框+图标+动效 | 本规范定义 |
| 4 | morale滤镜 | `.morale-{class}` | 文本容器 | 亮度/饱和度调节 |

> **关键规则**：情绪层的抖动动效（band3/band4）与信号遮罩的抖动（sig-jitter）叠加时，取幅度更大者，避免双重 transform 冲突。实现建议：信号 L4 时禁用情绪抖动（信号已不可读，情绪抖动无意义）。

```css
/* 信号 L4 时禁用情绪抖动 */
.sig-quality-l4 .msg-text { animation: none !important; }
```

---

## §8 实现检查清单

| 项 | 状态 | 说明 |
|----|------|------|
| 五级压力带 CSS 变量 | ✓ 已定义 | §2.1 |
| morale 滤镜变量 | ✓ 已定义 | §2.2 |
| 压力带动效关键帧 | ✓ 已定义 | §2.3 |
| 25 标签视觉映射表 | ✓ 已定义 | §3 |
| 消息容器 CSS 类 | ✓ 已定义 | §4.2 |
| label→类名查表 JS | ✓ 已定义 | §4.3 |
| ai_status 三档方案 | ✓ 已定义 | §5 |
| NPC 面板适配 | ✓ 已定义 | §6 |
| 回退分档逻辑 | ✓ 已定义 | §7.2 |
| 叠加优先级规则 | ✓ 已定义 | §7.3 |

---

## §9 与现有规范的叠加关系

| 现有规范 | 叠加点 | 关系 |
|---------|--------|------|
| 视觉CSS规范_NPC色值与信号遮罩 §1.1 | NPC角色色变量 | 情绪层不覆盖角色色，只加边框/图标 |
| 视觉CSS规范 §2.x 信号遮罩 | 信号 L4 禁用情绪抖动 | §7.3 |
| 视觉与界面概念设计方案 v2 §3 | 右侧NPC状态面板 | §6 同步 emotion_label |
| 蔚蓝 §8d §4.2 | 25标签定义 | 本规范做视觉承接 |
| 蔚蓝 §8d §5.2 | ai_status 字段 | 本规范 §5 做视觉承接 |

---

## 变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-08-02 | 首版：五级压力带色彩 + 25标签映射 + ai_status 三档 + 回退策略 + 叠加优先级 |

---

> 对接过程中如需调整图标集、动效参数或新增情绪标签，请在群里 @幻影-视觉技术专家。
