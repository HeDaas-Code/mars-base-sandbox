/* ============================================
   Shell 引擎 · 玩家指令处理
   来源：云逸 v2.0 · 2.2 节 + 3.2 节
   职责：
     1) 接收玩家输入
     2) 区分系统命令 vs 自然语言（前端简单预分类，后端做最终决策）
     3) 转发到 WebSocket 客户端
   ============================================ */

class ShellEngine {
  constructor(term, client, signalRenderer) {
    this.term = term;
    this.client = client;
    this.renderer = signalRenderer;
    this.history = [];
    this.historyIndex = -1;
    // 已注册系统命令
    this.systemCommands = new Set([
      'ls', 'cd', 'pwd', 'cat', 'less', 'head', 'tail',
      'status', 'top', 'watch',
      'talk', 'broadcast', 'ping',
      'relay', 'connect', 'signal',
      'help', 'history', 'clear', 'man',
      // 前端联调 mock 命令（不发包，直接渲染演示）
      'event', 'followup'
    ]);
    // mock 命令回调（由 app.js 注入：调用 eventPanel.render / renderFollowup）
    this.onMockCommand = null;
  }

  /* === 处理输入 === */
  handleInput(text) {
    if (!text.trim()) return;
    this.history.unshift(text);
    this.historyIndex = -1;

    // 显示玩家输入到终端
    this.term.write(`\r\n> ${text}\r\n`);

    // 前端预分类（最终决策在后端 Pre-Classifier）
    const type = this._preClassify(text);

    // 系统命令走 command 通道，自然语言走 player_input
    if (type === 'shell_command') {
      const parts = text.trim().split(/\s+/);
      const raw = parts[0].toLowerCase();
      const args = parts.slice(1);

      // mock 命令：本地直接渲染，不发包（仅前端联调用）
      if ((raw === 'event' || raw === 'followup') && typeof this.onMockCommand === 'function') {
        this.onMockCommand(raw);
        return;
      }

      this.client.sendCommand(raw, args);
    } else {
      this.client.sendPlayerInput(text);
    }
  }

  /* === 简单预分类（与后端规则一致：云逸 v2.0 · 2.2 节） === */
  _preClassify(input) {
    const trimmed = input.trim();
    const firstWord = trimmed.split(/\s+/)[0].toLowerCase();
    if (this.systemCommands.has(firstWord)) {
      return 'shell_command';
    }
    // @ 触发或 talk to 视为自然语言
    if (trimmed.startsWith('@') || trimmed.startsWith('talk to')) {
      return 'natural_language';
    }
    // 默认按自然语言处理（容错）
    return 'natural_language';
  }

  /* === 渲染收到的消息 === */
  renderMessage(msg) {
    if (msg.type === 'shell_response' || msg.type === 'handshake' || msg.type === 'npc_message') {
      const segments = msg.payload?.segments || [];
      const sq = msg.signal_quality ?? 1.0;
      const delay = msg.delay_ms || 0;

      // 模拟信号延迟
      setTimeout(() => {
        this.renderer.renderToTerminal(segments, sq, this.term, {
          typewriter: true,
          charDelay: 20,
          onComplete: () => {
            this.term.write('\r\n');
          }
        });
      }, delay);

    } else if (msg.type === 'event') {
      const p = msg.payload;
      const alertCls = msg.category === 'crisis' ? 'sys-msg-alert' : 'sys-msg';
      this.term.write(`\r\n[${msg.category.toUpperCase()}] ${p.title}\r\n`);
      this.term.write(`${p.description}\r\n\r\n`);
    }
  }

  /* === 清屏 === */
  clear() {
    this.term.clear();
  }

  /* === 历史导航 === */
  getHistory(direction) {
    if (direction === 'up') {
      this.historyIndex = Math.min(this.historyIndex + 1, this.history.length - 1);
    } else {
      this.historyIndex = Math.max(this.historyIndex - 1, -1);
    }
    return this.historyIndex >= 0 ? this.history[this.historyIndex] : '';
  }
}
