/* ============================================
   ResourcePanel · 左侧资源面板
   来源：云逸 v2.0 · 3.3 节 L1 + 幻影 v2.0 · 2.2 节
   内容：氧气/电力/水/食物/材料/基地完整度
   渲染：CSS 渐变填充条（幻影 1.4 节）
   ============================================ */

class ResourcePanel {
  constructor(elementId) {
    this.el = document.getElementById(elementId);
    if (!this.el) throw new Error(`ResourcePanel 元素 #${elementId} 不存在`);
    this.state = {
      oxygen: { current: 100, max: 100, rate: 0 },
      power: { current: 100, max: 100, rate: 0 },
      water: { current: 100, max: 100, rate: 0 },
      food: { current: 100, max: 100, rate: 0 },
      materials: {},
      integrity: 1.0
    };
  }

  update(state) {
    Object.assign(this.state, state);
    this.render();
  }

  applyServerStatus(msg) {
    const p = msg.payload;
    if (p.base) {
      if (p.base.resources) Object.assign(this.state, p.base.resources);
      if (p.base.integrity !== undefined) this.state.integrity = p.base.integrity;
    }
    this.render();
  }

  /* === 状态档位判定 === */
  _getStatus(val, max) {
    const pct = val / max;
    if (pct >= 0.6) return 'ok';
    if (pct >= 0.3) return 'warn';
    return 'danger';
  }

  /* === 速率格式化 === */
  _formatRate(rate) {
    if (rate === 0 || rate === undefined) return '稳定';
    return `${rate > 0 ? '+' : ''}${rate.toFixed(2)}/tick`;
  }

  render() {
    const s = this.state;

    const renderResource = (key, label, symbol, data) => {
      const pct = Math.round((data.current / data.max) * 100);
      const status = this._getStatus(data.current, data.max);
      return `
        <div class="resource-item">
          <div class="resource-item-header">
            <span class="resource-item-name">${symbol} ${label}</span>
            <span class="resource-item-value">${pct}%</span>
          </div>
          <div class="progress-bar-container">
            <div class="progress-bar-fill status-${status}" style="width:${pct}%"></div>
          </div>
          <div class="resource-item-header">
            <span style="font-size:10px;color:var(--color-text-secondary);opacity:0.7">
              ${data.current.toFixed(0)}/${data.max}
            </span>
            <span style="font-size:10px;color:var(--color-text-secondary);opacity:0.7">
              ${this._formatRate(data.rate)}
            </span>
          </div>
        </div>
      `;
    };

    const integrityPct = Math.round(s.integrity * 100);
    const integrityStatus = this._getStatus(s.integrity, 1.0);

    this.el.innerHTML = `
      <div class="panel-title">基地资源</div>
      ${renderResource('oxygen', '氧气', 'O₂', s.oxygen)}
      ${renderResource('power', '电力', 'PWR', s.power)}
      ${renderResource('water', '水', 'H₂O', s.water)}
      ${renderResource('food', '食物', 'FD', s.food)}

      <div class="resource-item">
        <div class="resource-item-header">
          <span class="resource-item-name">完整度</span>
          <span class="resource-item-value">${integrityPct}%</span>
        </div>
        <div class="progress-bar-container">
          <div class="progress-bar-fill status-${integrityStatus}" style="width:${integrityPct}%"></div>
        </div>
      </div>

      ${Object.keys(s.materials).length > 0 ? `
        <div class="panel-title" style="margin-top:8px">材料库存</div>
        ${Object.entries(s.materials).map(([k, v]) => `
          <div class="resource-item-header">
            <span class="resource-item-name" style="font-size:10px">${k}</span>
            <span class="resource-item-value" style="font-size:10px">${v}</span>
          </div>
        `).join('')}
      ` : ''}
    `;
  }
}
