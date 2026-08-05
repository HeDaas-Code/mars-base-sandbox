/* ============================================
   CrewPanel · 右侧 NPC 面板
   来源：云逸 v2.0 · 3.3 节 + 幻影 v2.0 · 2.2 节 + 4.4 节
        + 幻影《emotion_label视觉呈现规范_v1.md》§6 NPC 面板适配
   内容：6 名 NPC + 2 个 AI 系统的实时状态
   渲染：NPC 专属色 + 符号 + 状态指示灯 + 情绪层（emotion_band / ai_status）
   ============================================ */

class CrewPanel {
  constructor(elementId) {
    this.el = document.getElementById(elementId);
    if (!this.el) throw new Error(`CrewPanel 元素 #${elementId} 不存在`);
    this.agents = {};
    // 初始化 6 个 NPC 状态
    for (const [id, cfg] of Object.entries(NPC_CONFIG)) {
      // 用 fallbackEmotion 计算初始 emotion 字段（首屏展示）
      const initEmotion = fallbackEmotion(
        cfg.initial_emotion.stress,
        cfg.initial_emotion.morale
      );
      this.agents[id] = {
        ...cfg,
        location: cfg.location,
        stress: cfg.initial_emotion.stress,
        morale: cfg.initial_emotion.morale,
        health: 1.0,
        current_task: '待命',
        // 情绪层字段
        emotion_label: null,             // 后端无明确 label 时为 null（走 fallback）
        emotion_band: initEmotion.band,
        morale_class: initEmotion.moraleClass,
        emotion_icon: initEmotion.icon
      };
    }
    // 初始化 AI 系统
    this.aiSystems = {};
    for (const [id, cfg] of Object.entries(AI_CONFIG)) {
      this.aiSystems[id] = {
        ...cfg,
        ai_status: 'normal'  // 默认在线
      };
    }
  }

  /* === 从后端 status_update 更新 NPC 状态 === */
  applyServerStatus(msg) {
    if (!msg.payload.agents) return;
    for (const agentState of msg.payload.agents) {
      const id = agentState.agent_id;
      if (this.agents[id]) {
        Object.assign(this.agents[id], {
          location: agentState.location,
          stress: agentState.stress,
          morale: agentState.morale,
          health: agentState.health,
          current_task: agentState.current_task
        });
        // 若后端未带 emotion_label，按 stress/morale 重算 fallback
        if (!agentState.emotion_label) {
          const fb = fallbackEmotion(agentState.stress, agentState.morale);
          Object.assign(this.agents[id], {
            emotion_label: null,
            emotion_band: fb.band,
            morale_class: fb.moraleClass,
            emotion_icon: fb.icon
          });
        }
      }
    }
    this.render();
  }

  /* === 从 agent_message.emotion_hint 更新 NPC 情绪状态 ===
     由 app.js 在 agent_message 路由里调用
     参数：configKey（NPC_CONFIG 的 key），emotionHint（emotion_hint 对象）
  */
  applyEmotionHint(configKey, emotionHint) {
    const agent = this.agents[configKey];
    if (!agent || !emotionHint) return;

    // 更新 stress/morale 数值（用于显示进度）
    if (typeof emotionHint.stress === 'number') {
      agent.stress = emotionHint.stress;
    }
    if (typeof emotionHint.morale === 'number') {
      agent.morale = emotionHint.morale;
    }

    // AI 状态分支
    if (emotionHint.ai_status) {
      agent.ai_status = emotionHint.ai_status;
    }

    // 优先使用 emotion_label（人类 NPC）
    if (emotionHint.emotion_label) {
      const v = lookupEmotion(emotionHint.emotion_label);
      if (v) {
        agent.emotion_label = emotionHint.emotion_label;
        agent.emotion_band = v.band;
        agent.morale_class = v.moraleClass;
        agent.emotion_icon = v.icon;
      }
    } else if (typeof emotionHint.stress === 'number') {
      // 回退：用 stress/morale 分档
      const fb = fallbackEmotion(emotionHint.stress, emotionHint.morale);
      agent.emotion_label = null;
      agent.emotion_band = fb.band;
      agent.morale_class = fb.moraleClass;
      agent.emotion_icon = fb.icon;
    }
  }

  /* === 状态判定 === */
  _healthStatus(h) {
    if (h >= 0.8) return 'ok';
    if (h >= 0.4) return 'warn';
    return 'danger';
  }

  _stressStatus(s) {
    if (s <= 0.4) return 'ok';
    if (s <= 0.7) return 'warn';
    return 'danger';
  }

  /* === NPC 卡片渲染（含情绪层）=== */
  _renderAgent(agent) {
    const healthStatus = this._healthStatus(agent.health);
    const stressStatus = this._stressStatus(agent.stress);

    // 情绪层 CSS 类
    const emotionBandClass = `emotion-band${agent.emotion_band}`;
    const moraleClass = `morale-${agent.morale_class}`;
    // 显示 label 文字（fallback 时为空，避免暴露内部档位）
    const labelText = agent.emotion_label
      ? `<span class="emotion-label-text">${agent.emotion_label}</span>`
      : '';

    return `
      <div class="crew-item ${emotionBandClass} ${moraleClass}" style="border-left-color:${agent.color_hex}">
        <div class="crew-item-header">
          <span class="crew-item-symbol" style="color:${agent.color_hex}">${agent.symbol}</span>
          <span class="crew-item-name" style="color:${agent.color_hex}">${agent.name}</span>
          <span class="crew-item-role">${agent.role_short}</span>
        </div>
        <div class="crew-item-meta">
          <span class="emotion-icon">${agent.emotion_icon || '·'}</span>
          ${labelText}
          <span class="crew-item-status">
            <span class="status-dot ${healthStatus}"></span>
            ${Math.round(agent.health * 100)}%
          </span>
          <span class="crew-item-status">
            <span class="label">压力</span>
            <span class="status-dot ${stressStatus}"></span>
            ${Math.round(agent.stress * 100)}%
          </span>
        </div>
        <div class="crew-item-meta">
          <span>${agent.location}</span>
        </div>
        <div class="crew-item-task">${agent.current_task}</div>
      </div>
    `;
  }

  /* === AI 系统卡片渲染（含 ai_status 三档）=== */
  _renderAI(ai) {
    const statusClass = `ai-status-${ai.ai_status || 'normal'}`;
    const statusText = ai.ai_status === 'offline' ? '离线'
      : ai.ai_status === 'degraded' ? '降级'
      : '在线';
    const statusDotClass = ai.ai_status === 'offline' ? 'danger'
      : ai.ai_status === 'degraded' ? 'warn'
      : 'ok';

    return `
      <div class="crew-item ${statusClass}" style="border-left-color:${ai.color_hex};opacity:0.8">
        <div class="crew-item-header">
          <span class="crew-item-symbol" style="color:${ai.color_hex}">${ai.symbol}</span>
          <span class="crew-item-name" style="color:${ai.color_hex}">${ai.name}</span>
          <span class="crew-item-role">${ai.role_short}</span>
        </div>
        <div class="crew-item-meta">
          <span class="emotion-icon">${(lookupAIStatus(ai.ai_status) || {}).icon || ai.symbol}</span>
          <span class="emotion-label-text">${ai.ai_status || 'normal'}</span>
          <span class="crew-item-status">
            <span class="status-dot ${statusDotClass}"></span>
            ${statusText}
          </span>
          <span>${ai.role}</span>
        </div>
      </div>
    `;
  }

  render() {
    const npcHtml = Object.values(this.agents)
      .map(a => this._renderAgent(a))
      .join('');
    const aiHtml = Object.values(this.aiSystems)
      .map(a => this._renderAI(a))
      .join('');

    this.el.innerHTML = `
      <div class="panel-title">基地成员</div>
      ${npcHtml}
      <div class="panel-title" style="margin-top:8px">AI 系统</div>
      ${aiHtml}
    `;
  }
}

