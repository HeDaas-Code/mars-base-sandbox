/* ============================================
   StatusBar · 顶部状态栏组件
   来源：云逸 v2.0 · 3.3 节 + 幻影 v2.0 · 2.1 节
   内容：Sol/火星时间 + 核心资源 + 信号质量 + 紧急状态
   ============================================ */

class StatusBar {
  constructor(elementId) {
    this.el = document.getElementById(elementId);
    if (!this.el) throw new Error(`StatusBar 元素 #${elementId} 不存在`);
    this.state = {
      sol: 1,
      mars_time: '00:00',
      oxygen: 100,
      power: 100,
      water: 100,
      food: 100,
      signal_quality: 1.0,
      agent_count: 6,
      alert_count: 0,
      is_emergency: false
    };
  }

  /* === 更新状态 === */
  update(state) {
    Object.assign(this.state, state);
    this.render();
  }

  /* === 从后端 status_update 消息更新 === */
  applyServerStatus(msg) {
    const p = msg.payload;
    if (p.world) {
      this.state.sol = p.world.sol;
      const date = new Date(p.world.mars_time);
      this.state.mars_time = date.toTimeString().slice(0, 5);
    }
    if (p.base && p.base.resources) {
      const r = p.base.resources;
      this.state.oxygen = r.oxygen?.current ?? this.state.oxygen;
      this.state.power = r.power?.current ?? this.state.power;
      this.state.water = r.water?.current ?? this.state.water;
      this.state.food = r.food?.current ?? this.state.food;
    }
    if (p.agents) {
      this.state.agent_count = p.agents.length;
    }
    this.render();
  }

  render() {
    const s = this.state;
    // 资源状态判定
    const resourceStatus = (val) => {
      if (val >= 60) return 'ok';
      if (val >= 30) return 'warn';
      return 'danger';
    };

    // 信号强度档位
    const signalLabel = (sq) => {
      if (sq >= 0.8) return '良好';
      if (sq >= 0.5) return '一般';
      if (sq >= 0.2) return '差';
      return '极差';
    };

    // 警报模式：氧气或电力低于 30%
    const isAlert = s.oxygen < 30 || s.power < 30;
    document.querySelector('.app-container').classList.toggle('alert-mode', isAlert);

    this.el.innerHTML = `
      <div class="status-bar-section">
        <span class="label">Sol</span>
        <span class="value">${s.sol}</span>
      </div>
      <div class="status-bar-section">
        <span class="label">时间</span>
        <span class="value">${s.mars_time}</span>
      </div>
      <div class="status-bar-section ${resourceStatus(s.oxygen) === 'danger' ? 'alert' : ''}">
        <span class="label">O₂</span>
        <span class="value">${s.oxygen}%</span>
      </div>
      <div class="status-bar-section ${resourceStatus(s.power) === 'danger' ? 'alert' : ''}">
        <span class="label">PWR</span>
        <span class="value">${s.power}%</span>
      </div>
      <div class="status-bar-section ${resourceStatus(s.water) === 'danger' ? 'alert' : ''}">
        <span class="label">H₂O</span>
        <span class="value">${s.water}%</span>
      </div>
      <div class="status-bar-section ${resourceStatus(s.food) === 'danger' ? 'alert' : ''}">
        <span class="label">食物</span>
        <span class="value">${s.food}%</span>
      </div>
      <div class="status-bar-spacer"></div>
      <div class="status-bar-section">
        <span class="label">信号</span>
        <span class="value">${signalLabel(s.signal_quality)}</span>
        ${this._renderSignalBars(s.signal_quality)}
      </div>
      <div class="status-bar-section">
        <span class="label">在岗</span>
        <span class="value">${s.agent_count}/6</span>
      </div>
      ${s.alert_count > 0 ? `
      <div class="status-bar-section alert">
        <span class="label">警报</span>
        <span class="value">${s.alert_count}</span>
      </div>` : ''}
    `;
  }

  /* === 信号强度四段色块条（幻影 1.4 节） === */
  _renderSignalBars(sq) {
    const litCount = sq >= 0.8 ? 4 : (sq >= 0.5 ? 3 : (sq >= 0.2 ? 2 : 1));
    const cls = sq >= 0.5 ? 'lit' : (sq >= 0.2 ? 'lit-warn' : 'lit-danger');
    return `<span class="signal-bars">
      ${[1,2,3,4].map(i => `<span class="signal-bar ${i <= litCount ? cls : ''}"></span>`).join('')}
    </span>`;
  }
}
