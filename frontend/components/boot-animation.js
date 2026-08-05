/* ============================================
   BootAnimation · 启动动画组件
   来源：幻影 v2.0 · 5.1 节
   说明：终端握手动画 + 信号搜索进度条
   实现：xterm.js 逐行打字效果 + CSS 动画
   ============================================ */

class BootAnimation {
  constructor(elementId, options = {}) {
    this.el = document.getElementById(elementId);
    if (!this.el) throw new Error(`BootAnimation 元素 #${elementId} 不存在`);
    this.statusEl = document.getElementById('boot-status');
    this.progressEl = document.getElementById('boot-progress');
    this.onComplete = options.onComplete || (() => {});
    this.completed = false;
  }

  /* === 启动动画序列 === */
  async start() {
    const steps = [
      { text: '[ 初始化信号接收器... ]', delay: 300, progress: 10 },
      { text: '[ 扫描 L 波段 1.4-1.7 GHz... ]', delay: 800, progress: 25 },
      { text: '[ 检测到弱信号源 · 方位 254.7° ]', delay: 600, progress: 40 },
      { text: '[ 信号强度 38% · 噪声比偏高 ]', delay: 500, progress: 55 },
      { text: '[ 正在校准天线阵列... ]', delay: 700, progress: 70 },
      { text: '[ 加密协议握手成功 · AES-256 ]', delay: 400, progress: 85 },
      { text: '[ 已建立与火星基地卫星的连接 ]', delay: 600, progress: 100 },
      { text: '[ 等待用户确认接入... ]', delay: 200, progress: 100 }
    ];

    for (const step of steps) {
      await this._animateStep(step);
    }
    this._showPrompt();
  }

  /* === 单步动画 === */
  _animateStep(step) {
    return new Promise(resolve => {
      setTimeout(() => {
        if (this.statusEl) {
          this.statusEl.textContent = step.text;
        }
        if (this.progressEl) {
          this.progressEl.innerHTML = `<div class="boot-progress-fill" style="width:${step.progress}%"></div>`;
        }
        setTimeout(resolve, 200);
      }, step.delay);
    });
  }

  /* === 显示按 ENTER 提示 === */
  _showPrompt() {
    const promptEl = document.querySelector('.boot-prompt');
    if (promptEl) {
      promptEl.style.display = 'block';
    }
    // 监听 ENTER 键
    const onEnter = (e) => {
      if (e.key === 'Enter' && !this.completed) {
        this.completed = true;
        document.removeEventListener('keydown', onEnter);
        this._fadeOut();
      }
    };
    document.addEventListener('keydown', onEnter);
    // 也支持点击
    this.el.addEventListener('click', () => {
      if (!this.completed) {
        this.completed = true;
        document.removeEventListener('keydown', onEnter);
        this._fadeOut();
      }
    });
  }

  /* === 淡出并触发完成回调 === */
  _fadeOut() {
    this.el.style.transition = 'opacity 0.8s ease-out';
    this.el.style.opacity = '0';
    setTimeout(() => {
      this.el.classList.add('hidden');
      // 显示主应用容器
      const app = document.getElementById('app');
      if (app) app.classList.remove('hidden');
      this.onComplete();
    }, 800);
  }
}
