/* ============================================
   LogStrip · 底部日志条
   来源：云逸 v2.0 · 3.3 节 L4
   内容：自动事件 + 告警 + 最近事件流
   渲染：滚动文本 + 警报计数
   ============================================ */

class LogStrip {
  constructor(elementId) {
    this.el = document.getElementById(elementId);
    if (!this.el) throw new Error(`LogStrip 元素 #${elementId} 不存在`);
    this.events = [];
    this.alertCount = 0;
    this.maxEvents = 20;
  }

  /* === 添加事件 === */
  addEvent(event) {
    this.events.unshift(event);
    if (this.events.length > this.maxEvents) {
      this.events.pop();
    }
    if (event.category === 'crisis' || event.severity === 'alert') {
      this.alertCount++;
    }
    this.render();
  }

  /* === 从后端 event 消息更新 === */
  applyServerEvent(msg) {
    const p = msg.payload;
    this.addEvent({
      time: msg.mars_time || '',
      title: p.title,
      description: p.description,
      category: msg.category
    });
  }

  /* === 清除警报 === */
  clearAlerts() {
    this.alertCount = 0;
    this.render();
  }

  render() {
    const latest = this.events[0];
    const latestText = latest
      ? `[${latest.time}] ${latest.title}`
      : '无事件';

    this.el.innerHTML = `
      <span class="log-strip-label">日志</span>
      <span class="log-strip-content">${latestText}</span>
      ${this.alertCount > 0 ? `
        <span class="log-strip-alert-count">
          ⚠ ${this.alertCount}
        </span>
      ` : ''}
    `;
  }
}
