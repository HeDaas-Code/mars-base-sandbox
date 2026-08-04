/* ============================================
   应用主入口 v2.0
   ------------------------------------------------
   职责：
     1) 初始化所有组件
     2) 注册消息路由（对齐云逸《WebSocket接口定义 v1.1》§3.2 S→C 消息）
     3) 启动 BootAnimation → 终端就绪
     4) 路由到各面板：
        - session_init → 全量初始化
        - agent_message → SignalRenderer → xterm.js
        - command_response → xterm.js（命令输出）
        - state_update → StatusBar + ResourcePanel + CrewPanel
        - system_event → LogStrip
        - alert → 屏幕警报 + LogStrip
        - error → 错误提示
   ============================================ */

(function() {
  // === 初始化各组件 ===
  const statusBar = new StatusBar('status-bar');
  const resourcePanel = new ResourcePanel('resource-panel');
  const crewPanel = new CrewPanel('crew-panel');
  const logStrip = new LogStrip('log-strip');
  const mapView = new MapView('map-panel');
  const memoryLoad = new MemoryLoadIndicator('memory-load');

  // === 初始化终端与 Shell ===
  const { term, fitAddon } = createTerminal();
  const shell = new ShellEngine(term, marsClient, signalRenderer);

  // === 事件流容器（嵌入终端流下方，event-panel.js 渲染于此） ===
  const eventStreamEl = document.getElementById('event-stream');

  // === EventPanel 单例接入（幻影 v1.2 事件呈现 UI）===
  // v1.2 §11.4 option_select C→S 路由：
  //   - 一级选项：sendOptionSelect(eventId, optionId)
  //   - 二级选项：sendOptionSelect(eventId, followupOptionId, parentOptionId)
  // eventPanel.activeEvent.event_id 提供当前事件上下文
  if (typeof eventPanel !== 'undefined') {
    eventPanel.onOptionSelect = (optionId) => {
      const eventId = eventPanel.activeEvent?.event_id;
      console.log('[App] option_select:', eventId, optionId);
      marsClient.sendOptionSelect(eventId, optionId);
    };
    eventPanel.onFollowupSelect = (followupOptionId) => {
      const eventId = eventPanel.activeEvent?.event_id;
      // followupSelectedOption 是父选项 ID（v1.2 §11.4 followup_id）
      const parentOptionId = eventPanel.selectedOption;
      console.log('[App] followup_select:', eventId, followupOptionId, 'parent=', parentOptionId);
      marsClient.sendOptionSelect(eventId, followupOptionId, parentOptionId);
    };
  }

  // === Mock 触发器（前端独立联调用，shell 命令 event / result 触发）===
  // v1.2 Mock 数据切到 MOCK_V12_STORY_EVENT / MOCK_V12_OPTION_RESULT
  function triggerMockEvent() {
    if (eventPanel && eventStreamEl && typeof MOCK_V12_STORY_EVENT !== 'undefined') {
      eventPanel.render(MOCK_V12_STORY_EVENT, eventStreamEl);
    }
  }
  function triggerMockOptionResult() {
    if (eventPanel && eventStreamEl && typeof MOCK_V12_OPTION_RESULT !== 'undefined') {
      // 模拟收到 option_result 后的渲染（含 effects_summary/state_update/leads_to）
      eventPanel.renderOptionResult(MOCK_V12_OPTION_RESULT, eventStreamEl, '修复主通信阵列');
    }
  }
  function triggerMockFollowup() {
    // 直接从 MOCK_V12_STORY_EVENT 取 opt3 的 followup 字段做演示
    if (eventPanel && eventStreamEl && typeof MOCK_V12_STORY_EVENT !== 'undefined') {
      const opt3 = MOCK_V12_STORY_EVENT.options.find(o => o.followup);
      if (opt3 && opt3.followup) {
        eventPanel.renderFollowup(opt3.followup, eventStreamEl);
      }
    }
  }

  // Shell mock 命令路由（输入 event / result / followup 触发本地渲染演示）
  shell.onMockCommand = (kind) => {
    if (kind === 'event') triggerMockEvent();
    else if (kind === 'result') triggerMockOptionResult();
    else if (kind === 'followup') triggerMockFollowup();
  };

  // === 默认 Mock 状态（在 session_init 到来前展示） ===
  statusBar.update({
    sol: 1,
    mars_time: '08:00',
    oxygen: 78,
    power: 85,
    water: 65,
    food: 90,
    signal_quality: 0.62,
    agent_count: 6,
    alert_count: 0,
    is_emergency: false
  });
  resourcePanel.update({
    oxygen: { current: 78, max: 100, rate: -0.3 },
    power: { current: 85, max: 100, rate: 0.5 },
    water: { current: 65, max: 100, rate: -0.1 },
    food: { current: 90, max: 100, rate: -0.5 },
    materials: { iron: 24, silicon: 12, carbon: 5 },
    integrity: 0.78
  });
  crewPanel.render();
  mapView.render();

  // === 消息路由 ===

  // session_init：会话建立，全量初始化状态
  marsClient.on('session_init', (msg) => {
    const p = msg.payload;
    console.log('[App] session_init resume_mode=', p.resume_mode);

    // 初始化状态栏
    if (p.player_state) {
      const sq = p.player_state.signal_quality_pct || 0;
      statusBar.update({
        signal_quality: sq / 100,  // 转换为 0-1
      });
    }
    // world_snapshot 初始化各面板
    if (p.world_snapshot) {
      const ws = p.world_snapshot;
      statusBar.update({
        sol: ws.sol,
        mars_time: ws.mars_time,
        agent_count: ws.agents ? ws.agents.length : 6,
      });
      if (ws.base) {
        if (ws.base.resources) {
          resourcePanel.update(ws.base.resources);
        }
        if (ws.base.integrity !== undefined) {
          resourcePanel.update({ integrity: ws.base.integrity });
        }
      }
      if (ws.agents) {
        // 转换后端 agent 状态到 CrewPanel 格式
        for (const a of ws.agents) {
          // agent_id 形如 'chen_hao'，要映射到 NPC_CONFIG key 'chen'
          const configKey = _mapAgentIdToConfigKey(a.agent_id);
          if (crewPanel.agents[configKey]) {
            Object.assign(crewPanel.agents[configKey], {
              location: a.location,
              stress: a.stress,
              morale: a.morale,
              health: a.health,
              current_task: a.current_task
            });
          }
        }
        crewPanel.render();
      }
    }
  });

  // agent_message：NPC 消息，通过 SignalRenderer 写入终端
  marsClient.on('agent_message', (msg) => {
    const p = msg.payload;
    const sq = p.signal_quality_pct || 100;
    // 更新记忆负载指示器（锐锋 context_summary 字段）
    if (p.context_summary) {
      memoryLoad.update(p.context_summary);
    }
    // 渲染角色标签前缀
    const label = p.sender_label || '';
    const segments = p.segments || [];

    // === 情绪层处理（千机 §6 实现）===
    // 解析 emotion_hint → 视觉参数
    const emotion = (typeof resolveEmotionHint === 'function')
      ? resolveEmotionHint(p.emotion_hint, p.sender_id)
      : { type: 'none' };

    // 组装情绪前缀：色块 ▌ + 图标 + 空格
    // - emotion 路径：用压力带色（已 morale 滤镜缩放）
    // - ai 路径：用 ai_status 色
    let emotionPrefix = '';
    let emotionProfile = null;
    if (emotion.type === 'emotion') {
      emotionPrefix = `${emotion.ansi}▌${emotion.icon} ${ANSI_RESET}`;
      emotionProfile = (typeof EMOTION_CHARDELAY !== 'undefined')
        ? EMOTION_CHARDELAY[emotion.band] : null;
    } else if (emotion.type === 'ai') {
      emotionPrefix = `${emotion.ansi}▌${emotion.icon} ${ANSI_RESET}`;
      // ai_status 暂不加打字机抖动（幻影规范未指定）
    }

    // 写入换行
    term.write('\r\n');
    // 渲染 segments（含遮罩 + 情绪前缀 + 抖动）
    signalRenderer.renderToTerminal(segments, sq, term, {
      typewriter: true,
      charDelay: 20,
      emotionPrefix,
      emotionProfile,
      onComplete: () => {
        term.write('\r\n');
        // 更新 NPC 面板的情绪状态
        if (p.emotion_hint) {
          const configKey = _mapAgentIdToConfigKey(p.sender_id);
          // NPC 路径
          if (crewPanel.agents[configKey]) {
            crewPanel.applyEmotionHint(configKey, p.emotion_hint);
            crewPanel.render();
          }
          // AI 路径
          else if (crewPanel.aiSystems && crewPanel.aiSystems[configKey]) {
            if (p.emotion_hint.ai_status) {
              crewPanel.aiSystems[configKey].ai_status = p.emotion_hint.ai_status;
              crewPanel.render();
            }
          }
        }
        // 更新状态栏信号质量
        statusBar.update({ signal_quality: sq / 100 });
      }
    });
  });

  // command_response：终端命令输出
  marsClient.on('command_response', (msg) => {
    const p = msg.payload;
    const segments = p.output_segments || [];
    term.write('\r\n');
    for (const seg of segments) {
      term.write(seg.text);
    }
    term.write('\r\n');
  });

  // state_update：增量状态更新
  marsClient.on('state_update', (msg) => {
    const p = msg.payload;
    if (p.world) {
      statusBar.update({
        sol: p.world.sol,
        mars_time: p.world.mars_time,
      });
    }
    if (p.base) {
      if (p.base.resources) resourcePanel.update(p.base.resources);
      if (p.base.integrity !== undefined) resourcePanel.update({ integrity: p.base.integrity });
    }
    if (p.signal_quality_pct !== undefined) {
      statusBar.update({ signal_quality: p.signal_quality_pct / 100 });
    }
    if (p.agents) {
      for (const a of p.agents) {
        const key = _mapAgentIdToConfigKey(a.agent_id);
        if (crewPanel.agents[key]) {
          Object.assign(crewPanel.agents[key], a);
          crewPanel.render();
        }
      }
    }
  });

  // system_event：事件，添加到日志条
  marsClient.on('system_event', (msg) => {
    const p = msg.payload;
    logStrip.addEvent({
      time: msg.ts_tick,
      title: p.text || p.title,
      description: p.description || '',
      category: p.category
    });
  });

  // story_event：剧情事件（云逸 v1.2 §11 S→C）
  // 渲染完整事件面板（含一级选项）到 #event-stream
  marsClient.on('story_event', (msg) => {
    const p = msg.payload;
    if (eventPanel && eventStreamEl) {
      eventPanel.render(p, eventStreamEl);
    }
  });

  // option_result：选项执行结果（云逸 v1.2 §11 S→C）
  // payload 字段：effects_summary / state_update / leads_to / followup / signal_quality_pct
  // v1.2 §11.6 路由逻辑：
  //   - 若 followup 字段非空：调用 renderFollowup 触发二级选项面板（不立即 leads_to）
  //   - 否则：调用 renderOptionResult 渲染 effects_summary + state_update + leads_to 反馈条
  //   - leads_to 非空时：渲染结果条后由后端继续推下一条 story_event，前端无需主动拉取
  marsClient.on('option_result', (msg) => {
    const p = msg.payload;
    if (!eventPanel || !eventStreamEl) return;

    if (p.followup) {
      // Case 1 B：含二级选项，渲染 followup 面板（不立即 leads_to）
      eventPanel.renderFollowup(p.followup, eventStreamEl);
    } else {
      // 普通一级选项结果：渲染 effects_summary + state_update + leads_to 反馈条
      // optionLabel 取 activeEvent 中已选 option 的 label 用于结果条标题
      const selectedOpt = eventPanel.activeEvent?.options
        ?.find(o => o.option_id === p.option_id || o.option_id === p.selected_option_id);
      const optionLabel = selectedOpt ? selectedOpt.label : '已选选项';
      eventPanel.renderOptionResult(p, eventStreamEl, optionLabel);
    }
  });

  // alert：警报，触发屏幕警报
  marsClient.on('alert', (msg) => {
    const p = msg.payload;
    logStrip.addEvent({
      time: msg.ts_tick,
      title: `[${p.code}] ${p.text}`,
      description: '',
      category: 'crisis'
    });
    // 触发屏幕红色脉冲
    const container = document.querySelector('.app-container');
    if (container && p.level === 'danger') {
      container.classList.add('alert-mode');
    }
    // 屏幕震动
    if (p.level === 'danger') {
      container?.classList.add('shake');
      setTimeout(() => container?.classList.remove('shake'), 500);
    }
  });

  // error：错误处理
  marsClient.on('error', (msg) => {
    const p = msg.payload || msg;
    const codeMap = {
      E_AGENT_BUSY: '正在思考...',
      E_AGENT_UNREACHABLE: '信号丢失',
      E_COMMAND_NOT_FOUND: 'command not found',
      E_RATE_LIMIT: '信噪过大，请稍候',
      E_INTERNAL: '服务异常'
    };
    const text = codeMap[p.code] || p.message || '未知错误';
    term.write(`\r\n\x1b[31m[ERROR] ${text}\x1b[0m\r\n`);
  });

  // fallback_mode：兜底模式提示
  marsClient.on('fallback_mode', (msg) => {
    term.write('\r\n\x1b[33m[ 信号不稳，切换至备用信道 ]\x1b[0m\r\n');
  });

  // === 启动 BootAnimation ===
  const boot = new BootAnimation('boot-screen', {
    onComplete: () => {
      // 启动动画完成后，写入欢迎信息并触发 session_init
      term.write('\x1b[33m');
      term.write('Mars Signal Terminal v0.1\r\n');
      term.write('赫拉克勒斯-7号基地 · 通信终端\r\n');
      term.write('\x1b[0m');
      term.write('\r\n');
      term.write('> ');

      // 触发 mock session_init
      marsClient._mockConnect();

      // 短延迟后推送信使引导
      setTimeout(() => {
        marsClient.mockTrigger('courier_intro');
      }, 1200);

      // 绑定终端输入
      let inputBuffer = '';
      term.onData((e) => {
        switch (e) {
          case '\r':  // Enter
            term.write('\r\n');
            shell.handleInput(inputBuffer);
            inputBuffer = '';
            setTimeout(() => term.write('> '), 100);
            break;
          case '\u007F':  // Backspace
            if (inputBuffer.length > 0) {
              inputBuffer = inputBuffer.slice(0, -1);
              term.write('\b \b');
            }
            break;
          case '\u001b[A':  // Up arrow
            // 历史
            break;
          case '\u001b[B':  // Down arrow
            break;
          case '\u0003':  // Ctrl+C
            inputBuffer = '';
            term.write('^C\r\n> ');
            break;
          default:
            if (e.charCodeAt(0) >= 32) {
              inputBuffer += e;
              term.write(e);
            }
        }
      });
    }
  });

  // 启动动画自动开始
  boot.start();

  // === 工具：后端 agent_id → NPC_CONFIG key 映射 ===
  // 后端用全名 ID（chen_hao/sophia_ramirez/...），前端 NPC_CONFIG key 是短名（chen/sophia/...）
  function _mapAgentIdToConfigKey(agentId) {
    if (!agentId) return null;
    // 去掉 _hao/_ramirez 等后缀
    const map = {
      'chen_hao': 'chen',
      'sophia_ramirez': 'sophia',
      'viktor_ivanov': 'viktor',
      'aisha_khan': 'aisha',
      'marcus_weber': 'marcus',
      'lin_ruoxi': 'linruoxi',
      'courier': 'courier',
      'athena': 'athena'
    };
    return map[agentId] || agentId.split('_')[0];
  }

  // 暴露到全局便于调试
  window._mars = {
    term, shell, marsClient,
    statusBar, resourcePanel, crewPanel,
    logStrip, mapView, memoryLoad, signalRenderer,
    eventPanel, eventStreamEl,
    triggerMockEvent, triggerMockFollowup
  };
})();
