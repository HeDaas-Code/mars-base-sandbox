/* ============================================
   SignalRenderer · 信号四档遮罩渲染模块 v2.0
   ------------------------------------------------
   数据源与规范：
     - 云逸《WebSocket接口定义 v1.1》§4.1 segments schema
     - 云逸《WebSocket接口定义 v1.1》§4.4 渲染规则映射
     - 幻影《前端视觉规范_CSS参数表》§2 信号四档遮罩
     - 蔚蓝 Q3 补充：关键剧情信息受保护，不纯随机遮罩

   接口约定：
     - signal_quality_pct: 0-100 整数（不是 0-1 小数）
     - segments: [{text, protected, tag?}]
       - protected=true 永不遮罩（关键剧情信息）
       - protected=false 按 signal_quality_pct 走四档渲染
       - tag 可选，仅供调试，前端可忽略

   四档渲染规则（与幻影参数表对齐）：
     80-100% L1 正常  原样
     50-79%  L2 轻度  ~15% 字符替换为 ▓，opacity 0.85，0.3s 抖动
     20-49%  L3 重度  ~45% 字符替换为 ▒▓，opacity 0.6，0.2s 抖动 + 闪烁
     0-19%   L4 极差  ~75% 字符替换为 ▒▓█，opacity 0.35，0.15s 抖动 + 闪烁
   ============================================ */

class SignalRenderer {
  constructor() {
    // 信号质量分档阈值（pct 0-100）
    this.THRESHOLDS = {
      L1_CLEAR: 80,
      L2_LIGHT_MASK: 50,
      L3_HEAVY_MASK: 20,
      L4_UNREADABLE: 0
    };

    // 遮罩字符集（按档位递进）
    this.MASK_CHARS = {
      L2: ['▓'],
      L3: ['▒', '▓'],
      L4: ['▒', '▓', '█']
    };

    // 遮罩比例
    this.MASK_RATIO = {
      L2: 0.15,
      L3: 0.45,
      L4: 0.75
    };

    // 渲染抖动状态（同一文本渲染时遮罩位置应稳定）
    // key: text+quality hash → value: 遮罩位置数组
    // 注：预留缓存槽，当前 _maskText 走确定性哈希实时计算，未实际写入此 Map
    //     后续若引入跨渲染遮罩稳定性优化时启用，避免重复哈希开销
    this.maskCache = new Map();

    // 不可读时的全遮罩串
    this.UNREADABLE_BLOCK = '▒▓█▒▓█▒▓█';
  }

  /* === 入口：渲染消息 segments ===
     输入：
       segments: [{text, protected, tag?}]
       signal_quality_pct: 0-100 整数
     输出：
       ANSI 字符串，可直接写入 xterm.js
  */
  render(segments, signal_quality_pct) {
    if (!segments || !Array.isArray(segments)) return '';
    const sq = Math.max(0, Math.min(100, signal_quality_pct));
    const level = this._getLevel(sq);

    // L1：直接拼接所有 text
    if (level === 'L1') {
      return segments.map(s => s.text).join('');
    }

    // L2/L3/L4：按 protected 分流
    return segments.map(seg => {
      if (seg.protected) {
        // 受保护段：原样输出（含 speaker_label/npc_name/command_response/mission_keyword）
        return seg.text;
      }
      // 未保护段：按档位遮罩
      return this._maskText(seg.text, level, sq);
    }).join('');
  }

  /* === 档位判定 === */
  _getLevel(sq) {
    if (sq >= this.THRESHOLDS.L1_CLEAR) return 'L1';
    if (sq >= this.THRESHOLDS.L2_LIGHT_MASK) return 'L2';
    if (sq >= this.THRESHOLDS.L3_HEAVY_MASK) return 'L3';
    return 'L4';
  }

  /* === 文本遮罩 ===
     按档位替换一定比例的字符为遮罩字符
     使用确定性哈希保证同一文本+档位的遮罩位置稳定
  */
  _maskText(text, level, sq) {
    if (!text) return '';

    // 空白字符不遮罩
    const chars = [...text];
    const maskableIndices = [];
    for (let i = 0; i < chars.length; i++) {
      if (!/\s/.test(chars[i]) && chars[i].length > 0) {
        maskableIndices.push(i);
      }
    }

    if (maskableIndices.length === 0) return text;

    // 计算遮罩数量
    const ratio = this.MASK_RATIO[level];
    const maskCount = Math.max(1, Math.floor(maskableIndices.length * ratio));

    // 确定性选择遮罩位置（基于文本内容+sq 的哈希）
    const seed = this._hash(text + level + sq);
    const maskPositions = this._selectPositions(maskableIndices, maskCount, seed);

    // 替换字符
    const maskChars = this.MASK_CHARS[level];
    for (let i = 0; i < maskPositions.length; i++) {
      const idx = maskPositions[i];
      // 在遮罩字符集中循环选择
      chars[idx] = maskChars[i % maskChars.length];
    }

    return chars.join('');
  }

  /* === 简单确定性哈希 === */
  _hash(str) {
    let h = 5381;
    for (let i = 0; i < str.length; i++) {
      h = ((h << 5) + h) + str.charCodeAt(i);
      h = h & 0xffffffff;
    }
    return Math.abs(h);
  }

  /* === 从候选位置中确定性选择 N 个 === */
  _selectPositions(candidates, count, seed) {
    // 使用线性同余生成器（LCG）做确定性洗牌
    let state = seed || 1;
    const arr = [...candidates];
    const result = [];

    for (let i = 0; i < count && arr.length > 0; i++) {
      // LCG: state = state * 1103515245 + 12345
      state = (state * 1103515245 + 12345) & 0x7fffffff;
      const idx = state % arr.length;
      result.push(arr.splice(idx, 1)[0]);
    }
    return result;
  }

  /* === 写入 xterm.js 终端（含打字机效果） ===
     options:
       typewriter: bool       是否逐字写入
       charDelay: ms          每字符延迟（typewriter=true 时生效，emotion 抖动优先）
       onComplete: fn         完成回调
       emotionPrefix: string  含 ANSI 的情绪前缀（色块+图标），非空时写在消息开头
       emotionProfile: { base, jitter }  charDelay 抖动参数（band3/4 抖动用）
         - base: 基础延迟 ms
         - jitter: ±jitter 随机偏移 ms
         - 当 signal_quality_pct < 20 (L4) 时自动禁用抖动，回退到 charDelay
     信号 L4 时禁用情绪抖动（对齐幻影 §7.3 叠加优先级）
  */
  renderToTerminal(segments, signal_quality_pct, xterm, options = {}) {
    const {
      typewriter = true,
      charDelay = 20,
      onComplete = null,
      emotionPrefix = '',
      emotionProfile = null
    } = options;

    const sq = Math.max(0, Math.min(100, signal_quality_pct));
    // 信号 L4 时禁用情绪抖动（信号遮罩优先级高于情绪层）
    const suppressMotion = (typeof shouldSuppressEmotionMotion === 'function')
      ? shouldSuppressEmotionMotion(sq)
      : sq < 20;

    // 组装最终文本：前缀 + segments 渲染结果
    const fullText = (emotionPrefix || '') + this.render(segments, sq);

    // 计算实际使用的 charDelay 配置
    // 优先级：emotion 抖动 > 默认 charDelay
    let baseDelay = charDelay;
    let jitter = 0;
    if (emotionProfile && !suppressMotion) {
      baseDelay = emotionProfile.base || charDelay;
      jitter = emotionProfile.jitter || 0;
    }

    if (!typewriter) {
      xterm.write(fullText);
      if (onComplete) onComplete();
      return;
    }

    // 打字机逐字写入
    let i = 0;
    const writeNext = () => {
      if (i >= fullText.length) {
        if (onComplete) onComplete();
        return;
      }
      // 处理 ANSI 转义序列（整段写入）
      const ch = fullText[i];
      if (ch === '\x1b') {
        let end = i + 1;
        while (end < fullText.length && end < i + 20) {
          const c = fullText.charCodeAt(end);
          if (c >= 0x40 && c <= 0x7e) { end++; break; }
          end++;
        }
        xterm.write(fullText.slice(i, end));
        i = end;
        // ANSI 转义段不延迟
        setTimeout(writeNext, 0);
      } else {
        xterm.write(ch);
        i++;
        // 情绪抖动：base ± jitter，clamp 到 >= 5ms
        const delay = jitter > 0
          ? Math.max(5, baseDelay + (Math.random() * 2 - 1) * jitter)
          : baseDelay;
        setTimeout(writeNext, delay);
      }
    };
    writeNext();
  }

  /* === 获取档位描述（调试用） === */
  getLevelInfo(sq) {
    const level = this._getLevel(sq);
    const info = {
      L1: { name: '正常', desc: '完整清晰', opacity: 1.0 },
      L2: { name: '轻度', desc: '偶发缺字 ▓', opacity: 0.85 },
      L3: { name: '重度', desc: '频繁乱码 ▒▓', opacity: 0.6 },
      L4: { name: '极差', desc: '几乎不可读 ▒▓█', opacity: 0.35 }
    };
    return { level, ...info[level] };
  }

  /* === 清理缓存 === */
  clearCache() {
    this.maskCache.clear();
  }
}

// 全局单例
const signalRenderer = new SignalRenderer();
