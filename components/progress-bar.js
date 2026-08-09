/* ============================================
   ProgressBar · 进度条组件工厂
   来源：幻影 v2.0 · 1.4 节
   规则：CSS 渐变填充条，颜色随状态绿→橙→红
   不用 ASCII 方块
   ============================================ */

class ProgressBar {
  /* 静态方法：返回进度条 HTML */
  static render(value, max, options = {}) {
    const {
      showTicks = false,
      tickCount = 10,
      height = '12px',
      label = ''
    } = options;

    const pct = Math.max(0, Math.min(100, (value / max) * 100));
    let status = 'ok';
    if (pct < 30) status = 'danger';
    else if (pct < 60) status = 'warn';

    const ticks = showTicks
      ? `<div class="progress-bar-tick-marks">
          ${Array(tickCount).fill('<span></span>').join('')}
        </div>`
      : '';

    return `
      <div class="progress-bar-container" style="height:${height}">
        <div class="progress-bar-fill status-${status}" style="width:${pct}%"></div>
        ${ticks}
      </div>
    `;
  }

  /* 动态更新：在指定容器内渲染 */
  static mount(containerId, value, max, options = {}) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = ProgressBar.render(value, max, options);
  }

  /* 平滑更新已有进度条 */
  static update(barSelector, value, max) {
    const fill = document.querySelector(`${barSelector} .progress-bar-fill`);
    if (!fill) return;
    const pct = Math.max(0, Math.min(100, (value / max) * 100));
    fill.style.width = `${pct}%`;

    let status = 'ok';
    if (pct < 30) status = 'danger';
    else if (pct < 60) status = 'warn';

    fill.className = `progress-bar-fill status-${status}`;
  }
}
