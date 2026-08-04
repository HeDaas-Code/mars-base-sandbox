/* ============================================
   xterm.js 配置 · 终端实例初始化
   来源：幻影 v2.0 · 1.1 / 1.2 节
   主题：复古工业科幻 / 琥珀色磷光屏
   ============================================ */

const TERMINAL_CONFIG = {
  // 基础选项
  cols: 80,
  rows: 24,
  cursorBlink: true,
  cursorStyle: 'bar',
  cursorWidth: 2,

  // 字体（幻影 1.3 节）
  fontFamily: "'JetBrains Mono', 'Fira Code', 'Source Code Pro', 'Sarasa Mono SC', monospace",
  fontSize: 14,
  lineHeight: 1.4,
  fontWeight: 'normal',
  fontWeightBold: 'bold',
  letterSpacing: 0,

  // 主题（幻影 1.2 节配色）
  theme: {
    background: '#0a0805',
    foreground: '#ffb347',
    cursor: '#ffd699',
    cursorAccent: '#0a0805',
    selectionBackground: 'rgba(255, 179, 71, 0.25)',
    black: '#0a0805',
    red: '#ff4444',
    green: '#4a9d4a',
    yellow: '#ffaa00',
    blue: '#66ccff',
    magenta: '#b399e6',
    cyan: '#66ccff',
    white: '#ffd699',
    brightBlack: '#3d2b1f',
    brightRed: '#ff6666',
    brightGreen: '#6abd6a',
    brightYellow: '#ffcc44',
    brightBlue: '#88ddff',
    brightMagenta: '#c7a9f0',
    brightCyan: '#88ddff',
    brightWhite: '#fff5d6'
  },

  // 滚动条
  scrollback: 1000,
  scrollbar: {
    vertical: 'auto',
    horizontal: 'hidden'
  },

  // 行为
  allowProposedApi: true,
  allowTransparency: true,
  bellStyle: 'none',
  drawBoldText: true,
  fastScrollModifier: 'shift',
  fastScrollSensitivity: 5,
  logLevel: 'warn',
  macOptionIsMeta: true,
  minimumContrastRatio: 1,
  screenReaderMode: false,
  smoothScrollDuration: 200,
  tabStopWidth: 4,
  wordSeparator: ' ()[]{}\',"`'
};

/* === 创建终端实例 === */
function createTerminal() {
  const term = new Terminal(TERMINAL_CONFIG);
  const fitAddon = new FitAddon.FitAddon();
  const webLinksAddon = new WebLinksAddon.WebLinksAddon();

  term.loadAddon(fitAddon);
  term.loadAddon(webLinksAddon);

  // 打开终端到容器
  const container = document.getElementById('terminal');
  term.open(container);
  fitAddon.fit();

  // 响应窗口大小
  window.addEventListener('resize', () => {
    try { fitAddon.fit(); } catch (e) { /* ignore */ }
  });

  return { term, fitAddon };
}
