/* ============================================
   WebSocket 客户端 v2.0
   ------------------------------------------------
   实现规范：云逸《WebSocket接口定义 v1.1》
     - §1 连接生命周期：Connecting → Hello → Active → Reconnect
     - §2 统一信封 {msg_id, type, ts_tick, payload}
     - §3.1 C→S 消息：hello/resume/ping/player_input/command/ack
     - §3.2 S→C 消息：session_init/pong/agent_message/command_response/state_update/system_event/alert/error/ack
     - §7 断线重连：localStorage 持久化 last_msg_id，支持 hot/warm/cold resume
     - §8 错误码与异常处理（含 HTTP 轮询兜底）
   ============================================ */

class MarsSignalClient {
  constructor(options = {}) {
    // WebSocket URL（云逸 v1.1 §1.1：URL 不带 player_id/token）
    // 生产环境：GitHub Actions 部署时会替换 wss://BACKEND_URL/ws 为实际后端地址
    const defaultUrl = (typeof window !== 'undefined' && window.location.hostname.includes('github.io'))
      ? 'wss://BACKEND_URL/ws'
      : 'ws://localhost:8000/ws';
    this.url = options.url || defaultUrl;
    // mock 模式：不连真实后端，用本地 mock 数据
    this.mockMode = options.mockMode !== undefined ? options.mockMode : true;
    // 鉴权 token
    this.token = options.token || null;
    // 客户端版本（用于版本兼容性检查，云逸 §8.1 close code 4029）
    this.clientVersion = options.clientVersion || '0.1.0';
    // 事件监听器：type -> Set<handler>
    this.listeners = new Map();
    // 连接状态
    this.ws = null;
    this.connected = false;
    this.sessionId = null;
    this.resumeMode = null;
    // 重连
    this.reconnectAttempts = 0;
    this.maxReconnect = 5;
    this.reconnectDelay = 2000;
    // 心跳（云逸 v1.1 §1.3：30s 间隔，90s 超时）
    this.heartbeatInterval = 30 * 1000;
    this.heartbeatTimeout = 90 * 1000;
    this.heartbeatTimer = null;
    this.lastServerFrameTs = 0;
    // 消息去重（云逸 v1.1 §7.2：hot resume 时按 msg_id 去重）
    this.processedMsgIds = new Set();
    this.lastMsgId = this._loadLastMsgId();
    // 兜底模式（云逸 v1.1 §8.3：HTTP 轮询）
    this.fallbackMode = false;
    this.fallbackPollTimer = null;
    // mock 定时器
    this.pendingTimers = new Set();
  }

  /* ============================================
     连接管理
     ============================================ */

  /* === 建立连接 === */
  connect() {
    if (this.mockMode) {
      console.log('[Mock] mock 模式，跳过真实 WebSocket 连接');
      this._mockConnect();
      return;
    }
    try {
      this.ws = new WebSocket(this.url);
      this._bindWsEvents();
    } catch (e) {
      console.error('[WS] 连接失败，切换兜底模式', e);
      this._startFallback();
    }
  }

  _bindWsEvents() {
    this.ws.onopen = () => {
      this.connected = true;
      this.reconnectAttempts = 0;
      this.lastServerFrameTs = Date.now();
      // 建连后发 hello（云逸 v1.1 §3.1）
      this._sendHello();
      this._startHeartbeat();
    };
    this.ws.onclose = (e) => this._onClose(e);
    this.ws.onerror = () => { /* onclose 会处理 */ };
    this.ws.onmessage = (e) => this._onMessage(e);
  }

  /* === 发送 hello（云逸 v1.1 §3.1） === */
  _sendHello() {
    const hello = {
      msg_id: this._genMsgId(),
      type: 'hello',
      ts_tick: 0,
      payload: {
        token: this.token,
        client_version: this.clientVersion,
        last_session_id: this.sessionId || null
      }
    };
    this._send(hello);
  }

  /* === 发送 resume（云逸 v1.1 §3.1，短断线重连） === */
  _sendResume() {
    if (!this.sessionId || !this.lastMsgId) return;
    const resume = {
      msg_id: this._genMsgId(),
      type: 'resume',
      ts_tick: 0,
      payload: {
        session_id: this.sessionId,
        last_msg_id: this.lastMsgId
      }
    };
    this._send(resume);
  }

  /* === 心跳（云逸 v1.1 §1.3：30s 间隔） === */
  _startHeartbeat() {
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
    this.heartbeatTimer = setInterval(() => {
      if (Date.now() - this.lastServerFrameTs > this.heartbeatTimeout) {
        console.warn('[WS] 心跳超时，主动断开');
        this.ws.close(4000, 'heartbeat timeout');
        return;
      }
      this._send({
        msg_id: this._genMsgId(),
        type: 'ping',
        ts_tick: 0,
        payload: {}
      });
    }, this.heartbeatInterval);
  }

  /* === 断线处理 === */
  _onClose(e) {
    this.connected = false;
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
    // 按 close code 分类处理（云逸 v1.1 §8.1）
    if (e.code === 4000) {
      console.log('[WS] 服务端空闲超时，立即 resume');
      this.connect();
      setTimeout(() => this._sendResume(), 500);
    } else if (e.code === 4029) {
      console.error('[WS] 版本不兼容，请升级');
      this.emit('error', { code: 'E_VERSION_MISMATCH', message: '客户端版本不兼容' });
      return;
    } else if (e.code === 4003) {
      console.error('[WS] 鉴权失败');
      this.emit('error', { code: 'E_AUTH_FAILED', message: '鉴权失败' });
      return;
    }
    // 通用重连
    this._scheduleReconnect();
  }

  _scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnect) {
      console.warn('[WS] 重连次数达上限，切兜底模式');
      this._startFallback();
      return;
    }
    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1);
    setTimeout(() => {
      console.log(`[WS] 第 ${this.reconnectAttempts} 次重连...`);
      this.connect();
    }, delay);
  }

  /* === 兜底模式：HTTP 轮询（云逸 v1.1 §8.3） === */
  _startFallback() {
    if (this.fallbackMode) return;
    this.fallbackMode = true;
    this.emit('fallback_mode', { poll_interval_ms: 2000 });
    this.fallbackPollTimer = setInterval(() => {
      // GET /api/poll?session_id=xxx&since=msg_id
      // 此处简化：仅触发事件，实际由后端实现
    }, 2000);
  }

  _stopFallback() {
    if (!this.fallbackMode) return;
    this.fallbackMode = false;
    if (this.fallbackPollTimer) clearInterval(this.fallbackPollTimer);
  }

  /* ============================================
     消息收发
     ============================================ */

  /* === 接收消息 === */
  _onMessage(e) {
    try {
      const msg = JSON.parse(e.data);
      this.lastServerFrameTs = Date.now();
      // 心跳响应
      if (msg.type === 'pong') return;
      // 消息去重
      if (msg.msg_id && this.processedMsgIds.has(msg.msg_id)) return;
      if (msg.msg_id) {
        this.processedMsgIds.add(msg.msg_id);
        this._saveLastMsgId(msg.msg_id);
      }
      // session_init 处理
      if (msg.type === 'session_init') {
        this.sessionId = msg.payload.session_id;
        this.resumeMode = msg.payload.resume_mode;
      }
      // 分发
      this.emit(msg.type, msg);
    } catch (err) {
      console.error('[WS] 消息解析失败', err, e.data);
    }
  }

  /* === 发送消息（统一信封） === */
  _send(msg) {
    if (!this.connected || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify(msg));
  }

  /* === 玩家自然语言输入（云逸 v1.1 §3.1 player_input） === */
  sendPlayerInput(text, targetAgentId = null) {
    if (this.mockMode) {
      this._mockHandlePlayerInput(text);
      return;
    }
    const msg = {
      msg_id: this._genMsgId(),
      type: 'player_input',
      ts_tick: 0,
      payload: { text, target_agent_id: targetAgentId }
    };
    this._send(msg);
  }

  /* === 剧情事件选项选择（云逸 v1.2 §11.4 option_select C→S）===
     一级选项：eventId + optionId
     二级选项（followup）：eventId + optionId + followupId（父选项 ID）
     后端 event_scheduler 收到后走 effects → leads_to / 推 option_result
  */
  sendOptionSelect(eventId, optionId, followupId = null) {
    if (this.mockMode) {
      this._mockHandleOptionSelect(eventId, optionId, followupId);
      return;
    }
    const payload = { event_id: eventId, option_id: optionId };
    if (followupId) payload.followup_id = followupId;
    this._send({
      msg_id: this._genMsgId(),
      type: 'option_select',
      ts_tick: 0,
      payload
    });
  }

  /* === 终端系统命令（云逸 v1.1 §3.1 command） === */
  sendCommand(raw, args = []) {
    if (this.mockMode) {
      this._mockHandleCommand(raw, args);
      return;
    }
    const msg = {
      msg_id: this._genMsgId(),
      type: 'command',
      ts_tick: 0,
      payload: { raw, args }
    };
    this._send(msg);
  }

  /* === 发送 ack（可选） === */
  sendAck(ackedMsgId) {
    if (this.mockMode) return;
    this._send({
      msg_id: this._genMsgId(),
      type: 'ack',
      ts_tick: 0,
      payload: { acked_msg_id: ackedMsgId }
    });
  }

  /* ============================================
     事件订阅
     ============================================ */
  on(type, handler) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type).add(handler);
  }
  off(type, handler) {
    this.listeners.get(type)?.delete(handler);
  }
  emit(type, data) {
    this.listeners.get(type)?.forEach(h => {
      try { h(data); } catch (e) { console.error(`[WS] handler 异常 (${type})`, e); }
    });
    // 总监听
    this.listeners.get('*')?.forEach(h => {
      try { h({ type, data }); } catch (e) { console.error('[WS] wildcard handler 异常', e); }
    });
  }

  /* ============================================
     工具方法
     ============================================ */
  _genMsgId() {
    if (crypto.randomUUID) return crypto.randomUUID();
    return 'msg-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8);
  }
  _loadLastMsgId() {
    try { return localStorage.getItem('mars_last_msg_id') || null; }
    catch (e) { return null; }
  }
  _saveLastMsgId(id) {
    try { localStorage.setItem('mars_last_msg_id', id); } catch (e) {}
  }

  /* ============================================
     Mock 模式实现
     ============================================ */
  _mockConnect() {
    // 模拟 session_init
    setTimeout(() => {
      const msg = MOCK_MESSAGES.session_init;
      this.sessionId = msg.payload.session_id;
      this.resumeMode = msg.payload.resume_mode;
      this.emit('session_init', msg);
    }, 800);
  }

  _mockHandlePlayerInput(text) {
    // 模拟轮次递增（用于 context_summary 演示）
    globalThis._mockRound = (globalThis._mockRound || 0) + 1;
    const mode = 'deliberate'; // mock 默认审慎模式
    const ctxSummary = genContextSummary(mode);

    // 简单关键词匹配
    if (/你好|hello|嗨/i.test(text)) {
      const msg = { ...MOCK_MESSAGES.courier_intro };
      msg.payload.context_summary = ctxSummary;
      setTimeout(() => this.emit('agent_message', msg), msg.payload.latency_ms);
      return;
    }
    if (/陈|chen|指挥/i.test(text)) {
      const msg = { ...MOCK_MESSAGES.chen_low_signal };
      msg.payload.context_summary = genContextSummary(mode);
      setTimeout(() => this.emit('agent_message', msg), msg.payload.latency_ms);
      return;
    }
    if (/索菲亚|sophia|生物/i.test(text)) {
      const msg = { ...MOCK_MESSAGES.sophia_medium_signal };
      msg.payload.context_summary = genContextSummary(mode);
      setTimeout(() => this.emit('agent_message', msg), msg.payload.latency_ms);
      return;
    }
    if (/维克托|viktor|工程|电力/i.test(text)) {
      const msg = { ...MOCK_MESSAGES.viktor_clear };
      msg.payload.context_summary = genContextSummary(mode);
      setTimeout(() => this.emit('agent_message', msg), msg.payload.latency_ms);
      return;
    }
    if (/艾莎|aisha|通信|信号/i.test(text)) {
      const msg = { ...MOCK_MESSAGES.aisha_lost };
      msg.payload.context_summary = genContextSummary(mode);
      setTimeout(() => this.emit('agent_message', msg), msg.payload.latency_ms);
      return;
    }
    // 默认陈昊响应
    const reply = buildAgentMessage(
      'chen_hao', 'CMDR',
      [
        { text: '[CMDR]> ', protected: true, tag: 'speaker_label' },
        { text: '收到你的消息：「' + text + '」\n', protected: false, tag: 'speech' },
        { text: '我会考虑的。', protected: true, tag: 'command_response' }
      ],
      72, 1500,
      { stress: 0.45, morale: 0.55 }
    );
    reply.payload.context_summary = genContextSummary(mode);
    setTimeout(() => this.emit('agent_message', reply), 1500);
  }

  _mockHandleCommand(raw, args) {
    // ls / status: 返回预定义 command_response
    if (raw === 'ls' || raw === 'status') {
      const msg = MOCK_COMMAND_RESPONSES[raw];
      setTimeout(() => this.emit('command_response', msg), 100);
      return;
    }
    // talk <name>: 解析目标 NPC，返回 agent_message
    if (raw === 'talk' && args.length > 0) {
      this._mockHandlePlayerInput(args.join(' '));
      return;
    }
    if (raw === 'help') {
      this.emit('command_response', {
        msg_id: this._genMsgId(),
        type: 'command_response',
        ts_tick: 0,
        payload: {
          output_segments: [
            { text: '可用指令：\n', protected: true, tag: 'command_response' },
            { text: '  status    查看基地状态\n', protected: false, tag: 'command_response' },
            { text: '  map       查看基地地图\n', protected: false, tag: 'command_response' },
            { text: '  talk <名字>  与 NPC 对话\n', protected: false, tag: 'command_response' },
            { text: '  scan      扫描周边环境\n', protected: false, tag: 'command_response' },
            { text: '  help      显示本帮助\n', protected: false, tag: 'command_response' }
          ],
          data: null
        }
      });
      return;
    }
    // 未知命令
    this.emit('command_response', MOCK_MESSAGES.unknown_command);
  }

  /* === Mock 模式：处理 option_select（前端独立联调用）===
     模拟后端 event_scheduler 收到选项后的响应：
     - 查找 MOCK_V12_STORY_EVENT 的 option_id
     - 若该 option 带 followup → 推 option_result（含 followup 字段，触发二级面板）
     - 否则 → 推 option_result（含 effects_summary/state_update/leads_to）
  */
  _mockHandleOptionSelect(eventId, optionId, followupId) {
    // 引用 event-panel.js 中的 Mock v1.2 数据（前端联调时全局可见）
    const storyEvent = (typeof MOCK_V12_STORY_EVENT !== 'undefined') ? MOCK_V12_STORY_EVENT : null;
    if (!storyEvent) {
      console.warn('[Mock] MOCK_V12_STORY_EVENT 未定义，无法模拟 option_select 响应');
      return;
    }

    // 二级选项回传：直接构造成功结果
    if (followupId) {
      const followupOpt = storyEvent.options
        .find(o => o.followup)?.followup?.options
        ?.find(fo => fo.option_id === optionId);
      const label = followupOpt ? followupOpt.label : optionId;
      const resultMsg = {
        msg_id: this._genMsgId(),
        type: 'option_result',
        ts_tick: Date.now(),
        payload: {
          event_id: eventId,
          option_id: optionId,
          effects_summary: `二级决策已执行：${label}`,
          state_update: [],
          leads_to: 'ev_A2_earth_contact',
          followup: null
        }
      };
      const t = setTimeout(() => this.emit('option_result', resultMsg), 600);
      this.pendingTimers.add(t);
      return;
    }

    // 一级选项：查找对应的 option 定义
    const opt = storyEvent.options.find(o => o.option_id === optionId);
    if (!opt) {
      console.warn('[Mock] 未知 option_id:', optionId);
      return;
    }

    // 若带 followup → 推 followup 触发的 option_result（不立即 leads_to）
    if (opt.followup) {
      const resultMsg = {
        msg_id: this._genMsgId(),
        type: 'option_result',
        ts_tick: Date.now(),
        payload: {
          event_id: eventId,
          option_id: optionId,
          effects_summary: null,
          state_update: null,
          leads_to: null,
          followup: opt.followup
        }
      };
      const t = setTimeout(() => this.emit('option_result', resultMsg), 400);
      this.pendingTimers.add(t);
      return;
    }

    // 普通一级选项：推完整 option_result（含 effects_summary/state_update/leads_to）
    const resultMsg = {
      msg_id: this._genMsgId(),
      type: 'option_result',
      ts_tick: Date.now(),
      payload: {
        event_id: eventId,
        option_id: optionId,
        effects_summary: '通信阵列开始修复，预计5个Sol后完成。备用件消耗8单位。艾莎信任度提升，维克托略有不满。',
        state_update: [
          { path: 'comm_array_main.status', old: 'offline', new: 'repairing' },
          { path: 'resources.parts', old: 24, new: 16 },
          { path: 'npc_states.aisha.trust', old: 32, new: 42 }
        ],
        leads_to: 'ev_A2_earth_contact',
        followup: null
      }
    };
    const t = setTimeout(() => this.emit('option_result', resultMsg), 600);
    this.pendingTimers.add(t);
  }

  /* === Mock 模式：触发预设场景消息 === */
  mockTrigger(messageKey) {
    if (!this.mockMode) return;
    const msg = MOCK_MESSAGES[messageKey];
    if (!msg) {
      console.warn('[Mock] 未知消息 key:', messageKey);
      return;
    }
    // agent_message 按 latency_ms 延迟推送
    const delay = msg.payload.latency_ms || 0;
    const timer = setTimeout(() => {
      this.emit(msg.type, msg);
      this.pendingTimers.delete(timer);
    }, delay);
    this.pendingTimers.add(timer);
  }

  /* === 主动断开 === */
  disconnect() {
    if (this.heartbeatTimer) clearInterval(this.heartbeatTimer);
    this._stopFallback();
    if (this.ws) {
      this.ws.onclose = null;
      try { this.ws.close(1000, 'client disconnect'); } catch (e) {}
    }
    this.connected = false;
  }
}

// 全局单例（默认连真实后端；URL ?mock=1 切回 mock 模式用于前端独立开发）
// 锐锋 ws_server 已就位（监听 ws://localhost:8000/ws，PID 6717，13/13 测试通过）
// 协议验证：hello→session_init(6 NPCs) / ping→pong / status→command_response 均通
const _useMock = (typeof URLSearchParams !== 'undefined'
  && typeof location !== 'undefined'
  && new URLSearchParams(location.search).has('mock'));
const marsClient = new MarsSignalClient({ mockMode: _useMock });
