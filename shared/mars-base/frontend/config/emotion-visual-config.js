/* ============================================
   emotion-visual-config · 情绪视觉映射查表模块 v1.0
   ------------------------------------------------
   数据源：
     - 幻影《emotion_label视觉呈现规范_v1.md》§2-§5
     - 蔚蓝 §8d §4.2 emotion_label 25 标签表 / §5.2 ai_status 三档
   用途：
     - 供 CrewPanel（HTML/CSS）查 band/moraleClass/icon
     - 供 SignalRenderer（xterm.js ANSI）查 ANSI 颜色 + 图标 + charDelay 抖动参数
   导出：
     - EMOTION_VISUAL_MAP   25 标签查表（幻影 §4.3）
     - AI_STATUS_MAP        3 档状态查表（幻影 §5.3）
     - EMOTION_BAND_HEX     5 档压力带主色 hex
     - MORALE_FILTER_FACT  5 档 morale 滤镜 RGB 缩放系数（ANSI 近似用）
     - lookupEmotion(label)          → { band, moraleClass, icon, bandHex }
     - lookupAIStatus(status)        → { className, icon, ansiColor, hex }
     - fallbackEmotion(stress,morale)→ { band, moraleClass, icon, bandHex }
     - hexToAnsi24(hex)              → '\x1b[38;2;R;G;Bm'
     - applyMoraleFilter(hex, moraleClass) → 经亮度缩放的 hex
   ============================================ */

// === §2.1 五级压力带主色 hex ===
const EMOTION_BAND_HEX = {
  0: '#4a6b7a',  // 灰蓝·静默
  1: '#7a8b6b',  // 灰绿·平稳
  2: '#ffb347',  // 琥珀·注意
  3: '#ff8c42',  // 橙红·警告
  4: '#ff4444'  // 红色·警报
};

// === §2.2 morale 滤镜系数（ANSI 近似用 RGB 缩放）===
// 原 CSS filter 是 saturate+brightness，ANSI 不支持 filter，
// 用 RGB × scale 近似：数值越小越暗
const MORALE_FILTER_FACT = {
  high:   1.00,  // [0.8,1.0] 高昂
  stable: 0.95,  // [0.6,0.8) 稳定
  mid:    0.85,  // [0.4,0.6) 中等
  low:    0.70,  // [0.2,0.4) 低沉
  floor:  0.55   // [0.0,0.2) 极低
};

// === §4.3 25 标签 → 视觉映射表 ===
// 与幻影规范完全对齐
const EMOTION_VISUAL_MAP = {
  // 带0 [0.0,0.2) 灰蓝·静默
  numb:      { band: 0, morale: 'floor',   icon: '○' },
  low:       { band: 0, morale: 'low',     icon: '◐' },
  calm:      { band: 0, morale: 'mid',     icon: '·' },
  steady:    { band: 0, morale: 'stable',  icon: '▸' },
  upbeat:    { band: 0, morale: 'high',    icon: '★' },
  // 带1 [0.2,0.4) 灰绿·平稳
  bleak:     { band: 1, morale: 'floor',   icon: '◌' },
  weary:     { band: 1, morale: 'low',     icon: '~' },
  focused:   { band: 1, morale: 'mid',     icon: '◆' },
  engaged:   { band: 1, morale: 'stable',  icon: '►' },
  cheerful:  { band: 1, morale: 'high',    icon: '✦' },
  // 带2 [0.4,0.6) 琥珀·注意
  hollow:    { band: 2, morale: 'floor',   icon: '□' },
  tense:     { band: 2, morale: 'low',     icon: '△' },
  alert:     { band: 2, morale: 'mid',     icon: '⚡' },
  determined:{ band: 2, morale: 'stable',  icon: '◈' },
  optimistic:{ band: 2, morale: 'high',    icon: '☀' },
  // 带3 [0.6,0.8) 橙红·警告
  despair:              { band: 3, morale: 'floor',  icon: '✕' },
  strained:             { band: 3, morale: 'low',     icon: '▲' },
  anxious:              { band: 3, morale: 'mid',     icon: '⚠' },
  strained_optimism:    { band: 3, morale: 'stable',  icon: ' ◈' },
  defiant:              { band: 3, morale: 'high',    icon: '◈!' },
  // 带4 [0.8,1.0] 红色·警报
  // 注：[0.8,1.0]×[0.8,1.0] 位置的 breakdown 与左上角 breakdown 同名，
  // 按幻影 §4.3 注，统一按 band4/floor 处理
  breakdown: { band: 4, morale: 'floor', icon: '✖' },
  panic:     { band: 4, morale: 'low',   icon: '‼' },
  frantic:   { band: 4, morale: 'mid',    icon: '※' },
  manic:     { band: 4, morale: 'stable', icon: '✦!' }
  // 注：[0.8,1.0]×[0.8,1.0] 的第 25 格 label = breakdown（高压力高士气）
  // 不单独建条目，与 band4/floor 共用
};

// === §5.3 ai_status → 视觉映射表 ===
const AI_STATUS_MAP = {
  normal:   { className: 'ai-status-normal',   icon: '⬡', hex: '#b399e6', ansi: null },
  degraded: { className: 'ai-status-degraded', icon: '⬡', hex: '#ff8c42', ansi: null },
  offline:  { className: 'ai-status-offline',  icon: '⬡', hex: '#555555', ansi: null }
};

// 启动时把 ansi 字段填充好
for (const v of Object.values(AI_STATUS_MAP)) {
  v.ansi = hexToAnsi24(v.hex);
}

// === §4.3 lookupEmotion：label → 视觉参数 ===
// 返回 { band, moraleClass, icon, bandHex } 或 null（label 未登记）
function lookupEmotion(label) {
  if (!label) return null;
  const entry = EMOTION_VISUAL_MAP[label];
  if (!entry) {
    console.warn('[emotion] 未知 emotion_label:', label);
    return null;
  }
  return {
    band: entry.band,
    moraleClass: entry.morale,
    icon: entry.icon,
    bandHex: EMOTION_BAND_HEX[entry.band]
  };
}

// === lookupAIStatus：ai_status → 视觉参数 ===
function lookupAIStatus(status) {
  if (!status) return null;
  const entry = AI_STATUS_MAP[status];
  if (!entry) {
    console.warn('[emotion] 未知 ai_status:', status);
    return null;
  }
  return {
    className: entry.className,
    icon: entry.icon,
    hex: entry.hex,
    ansi: entry.ansi
  };
}

// === §7.2 fallbackEmotion：缺 emotion_label 时前端分档 ===
// 输入 stress/morale 0-1 数值，返回与 lookupEmotion 同结构
function fallbackEmotion(stress, morale) {
  const s = Math.max(0, Math.min(1, stress || 0));
  const m = Math.max(0, Math.min(1, morale || 0));
  const band = Math.min(4, Math.floor(s * 5));
  const moraleClass = m < 0.2 ? 'floor'
    : m < 0.4 ? 'low'
    : m < 0.6 ? 'mid'
    : m < 0.8 ? 'stable'
    : 'high';
  // 回退时图标用通用圆点
  return { band, moraleClass, icon: '·', bandHex: EMOTION_BAND_HEX[band] };
}

// === 工具：hex → ANSI 24-bit 真彩色前缀 ===
// 例：'#ffb347' → '\x1b[38;2;255;179;71m'
function hexToAnsi24(hex) {
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `\x1b[38;2;${r};${g};${b}m`;
}

// === 工具：hex × morale 滤镜系数 → 经亮度缩放的 hex ===
// 用于 ANSI 近似 morale 滤镜（CSS 的 saturate+brightness）
function applyMoraleFilter(hex, moraleClass) {
  const factor = MORALE_FILTER_FACT[moraleClass] || 1.0;
  const h = hex.replace('#', '');
  const r = Math.min(255, Math.round(parseInt(h.slice(0, 2), 16) * factor));
  const g = Math.min(255, Math.round(parseInt(h.slice(2, 4), 16) * factor));
  const b = Math.min(255, Math.round(parseInt(h.slice(4, 6), 16) * factor));
  const toHex2 = (n) => n.toString(16).padStart(2, '0');
  return '#' + toHex2(r) + toHex2(g) + toHex2(b);
}

// === 工具：从 emotion_hint 提取视觉参数（统一入口）===
// 输入 emotion_hint 对象，返回统一结构：
//   { type: 'emotion'|'ai'|'none', band?, moraleClass?, icon?, bandHex?, ansi?, className? }
function resolveEmotionHint(emotionHint, senderId) {
  if (!emotionHint) return { type: 'none' };

  // AI 路径：senderId 是 athena/courier 或 emotion_hint.ai_status 存在
  if (emotionHint.ai_status) {
    const r = lookupAIStatus(emotionHint.ai_status);
    if (r) return { type: 'ai', ...r };
  }

  // 人类 NPC 路径：优先 emotion_label，回退 stress/morale
  if (emotionHint.emotion_label) {
    const r = lookupEmotion(emotionHint.emotion_label);
    if (r) {
      return {
        type: 'emotion',
        ...r,
        ansi: hexToAnsi24(applyMoraleFilter(r.bandHex, r.moraleClass))
      };
    }
  }

  // 回退：用 stress/morale 分档
  if (typeof emotionHint.stress === 'number') {
    const r = fallbackEmotion(emotionHint.stress, emotionHint.morale);
    return {
      type: 'emotion',
      ...r,
      ansi: hexToAnsi24(applyMoraleFilter(r.bandHex, r.moraleClass))
    };
  }

  return { type: 'none' };
}

// === 工具：从 emotion_hint 提取用于 CrewPanel 的字段 ===
// 返回 { emotion_label, stress, morale, ai_status }，缺失字段保留 undefined
// CrewPanel 调用此方法把字段合并到 agents[key] 里
function extractForCrewPanel(emotionHint) {
  if (!emotionHint) return {};
  return {
    emotion_label: emotionHint.emotion_label,
    stress: emotionHint.stress,
    morale: emotionHint.morale,
    ai_status: emotionHint.ai_status
  };
}

// === ANSI 重置码 ===
const ANSI_RESET = '\x1b[0m';

// === 信号 L4 时禁用情绪抖动的判断（对齐幻影 §7.3）===
// 输入 signal_quality_pct（0-100），返回 true 表示应禁用情绪抖动
function shouldSuppressEmotionMotion(sqPct) {
  return sqPct < 20;  // L4 阈值
}

// === charDelay 抖动参数（用于 SignalRenderer 打字机阶段）===
// 对齐幻影 §2.3：带3 微颤 0.3s / 带4 抖动 0.2s
// ANSI 无 keyframes，用 charDelay 抖动近似
const EMOTION_CHARDELAY = {
  0: { base: 20, jitter: 0 },     // 静默：稳定
  1: { base: 20, jitter: 0 },     // 平稳：稳定
  2: { base: 20, jitter: 0 },     // 注意：稳定
  3: { base: 20, jitter: 7 },     // 警告：±7ms 微颤
  4: { base: 15, jitter: 18 }     // 警报：base 15ms ±18ms 明显不规则（幻影建议 12→15 兼顾可读性）
};

// 暴露到全局（非 module 环境）
if (typeof window !== 'undefined') {
  window.EMOTION_VISUAL_MAP = EMOTION_VISUAL_MAP;
  window.AI_STATUS_MAP = AI_STATUS_MAP;
  window.EMOTION_BAND_HEX = EMOTION_BAND_HEX;
  window.MORALE_FILTER_FACT = MORALE_FILTER_FACT;
  window.lookupEmotion = lookupEmotion;
  window.lookupAIStatus = lookupAIStatus;
  window.fallbackEmotion = fallbackEmotion;
  window.hexToAnsi24 = hexToAnsi24;
  window.applyMoraleFilter = applyMoraleFilter;
  window.resolveEmotionHint = resolveEmotionHint;
  window.extractForCrewPanel = extractForCrewPanel;
  window.shouldSuppressEmotionMotion = shouldSuppressEmotionMotion;
  window.EMOTION_CHARDELAY = EMOTION_CHARDELAY;
  window.ANSI_RESET = ANSI_RESET;
}
