/* ============================================
   MemoryLoadIndicator · 记忆负载指示器
   ------------------------------------------------
   数据源：锐锋 context_summary 字段（WebSocket agent_message payload）
     {
       "context_summary": {
         "history_count": 12,
         "k_limit": 6,
         "compressed_count": 4,
         "mode": "deliberate"
       }
     }
   - history_count = 当前上下文消息数
   - k_limit = 当前模式窗口上限
   - compressed_count = 已压缩的旧消息数
   - mode = reflexive / deliberate / deep

   渲染：负载条 history_count/k_limit 比值
   - < 60%  绿色（安全）
   - 60-85% 橙色（注意）
   - > 85%  红色（紧张）
   ============================================ */

class MemoryLoadIndicator {
  constructor(elementId) {
    this.el = document.getElementById(elementId);
    if (!this.el) throw new Error(`MemoryLoadIndicator 元素 #${elementId} 不存在`);
    this.state = {
      history_count: 0,
      k_limit: 6,
      compressed_count: 0,
      mode: 'deliberate'
    };
    this.visible = false;
  }

  /* === 从 context_summary 更新 === */
  update(contextSummary) {
    if (!contextSummary) return;
    Object.assign(this.state, contextSummary);
    this.visible = true;
    this.render();
  }

  /* === 清空（如切换会话） === */
  reset() {
    this.state = {
      history_count: 0,
      k_limit: 6,
      compressed_count: 0,
      mode: 'deliberate'
    };
    this.visible = false;
    this.render();
  }

  /* === 模式中文标签 === */
  _modeLabel(mode) {
    const map = {
      reflexive: '反射',
      deliberate: '审慎',
      deep: '深思'
    };
    return map[mode] || mode;
  }

  /* === 负载档位 === */
  _getLoadStatus(ratio) {
    if (ratio < 0.6) return 'ok';
    if (ratio <= 0.85) return 'warn';
    return 'danger';
  }

  render() {
    if (!this.visible) {
      this.el.innerHTML = '';
      this.el.style.display = 'none';
      return;
    }

    const s = this.state;
    const ratio = s.k_limit > 0 ? s.history_count / s.k_limit : 0;
    const pct = Math.min(100, Math.round(ratio * 100));
    const status = this._getLoadStatus(ratio);

    this.el.style.display = '';
    this.el.innerHTML = `
      <span class="ml-label">MEM</span>
      <span class="ml-mode mode-${s.mode}">${this._modeLabel(s.mode)}</span>
      <div class="ml-bar-container">
        <div class="ml-bar-fill status-${status}" style="width:${pct}%"></div>
      </div>
      <span class="ml-count">${s.history_count}/${s.k_limit}</span>
      ${s.compressed_count > 0
        ? `<span class="ml-compressed" title="已压缩 ${s.compressed_count} 条旧消息">▽${s.compressed_count}</span>`
        : ''}
    `;
  }
}
