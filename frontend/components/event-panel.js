/* ============================================
   EventPanel · 事件呈现 UI 组件 v1.2
   ------------------------------------------------
   设计：幻影-视觉技术专家
   日期：2026-08-03
   规范来源：视觉与界面概念设计方案 v2.0
   依赖：event-panel.css / signal-renderer.js / npc-config.js
   Schema 对齐：云逸《WebSocket接口定义 v1.2 §11 + v1.3 §13-§15》

   v1.3 Schema 字段映射：
     story_event (S→C):
       event_id            → 内部标识
       chapter_id          → 章节 ID（头部显示）
       node_index          → 节点序号显示
       branch              → 分支标记
       sol                 → Sol 天数（头部显示）                    [v1.3 §13]
       narrative_segments  → 事件描述（复用SignalRenderer segments）
       bound_npcs          → 绑定 NPC 标记条（primary 高亮）         [v1.3 §13.4]
       options[]           → 玩家选项列表
       options[].risk      → 选项风险提示（⚠ 行）                   [v1.3 §13]
       options[].followup  → 嵌套二级选项
       ending_determination → 可能结局列表面板（终局节点）           [v1.3 §13.3]
       signal_quality_pct  → 信号质量（遮罩渲染）
       latency_ms          → 调试用，不渲染

     option_select (C→S):
       event_id + option_id + followup_id? → onOptionSelect 回调

     option_result (S→C):
       effects_summary     → 人类可读效果摘要（结果反馈区直接展示）
       effects             → 原始 effects 对象（逐行渲染，§14.4 映射表）[v1.3 §14]
       state_update         → 关键状态变化（path/old/new）
       ending              → 结局命中面板（紫色发光居中）            [v1.3 §14.3]
       leads_to             → 下一事件ID提示
       followup             → 二级选项数据（触发二级渲染）

     sol_advance (S→C):                                    [v1.3 §15]
       sol + delta + chapter_changed + chapter_name → Sol 数字翻转 + 章节切换动画

   五个核心子组件：
     1. 事件弹窗面板 (render)
     2. 玩家选项渲染 (_renderOptions) + 二级选项 (_renderFollowup)
     3. 任务下达面板 (renderTaskBriefing)
     4. 事件结果反馈 (renderOptionResult) — 对齐 option_result payload
     5. Sol 推进通知 (renderSolAdvance) — 对齐 sol_advance 消息
   ============================================ */

class EventPanel {

  constructor() {
    // NPC 配置引用（从全局 npc-config.js）
    this.npcConfig = (typeof NPC_CONFIG !== 'undefined') ? NPC_CONFIG : {};
    this.aiConfig = (typeof AI_CONFIG !== 'undefined') ? AI_CONFIG : {};

    // 信号渲染器引用
    this.signalRenderer = (typeof signalRenderer !== 'undefined') ? signalRenderer : null;

    // 当前活跃事件状态
    this.activeEvent = null;
    this.selectedOption = null;

    // followup（二级选项）状态
    this.followupSelectedOption = null;

    // 回调注册
    this.onOptionSelect = null;  // (optionId) => void
    this.onEventDismiss = null;  // () => void
    this.onFollowupSelect = null; // (followupOptionId) => void
  }

  /* === 主入口：渲染完整事件面板 ===
     v1.2 Schema story_event payload:
       {
         event_id: string,
         chapter_id: string,
         node_index: number,
         branch: string,
         narrative_segments: [{text, protected, tag?}],
         options: [{option_id, label, visible, followup?}],
         signal_quality_pct: number,
         latency_ms: number
       }
     兼容旧格式（description / player_options / signal_quality）用于 Mock 数据
  */
  render(data, targetEl) {
    if (!data || !targetEl) return;

    this.activeEvent = data;
    this.selectedOption = null;

    // 推断事件类型
    const eventType = data.event_type || this._inferEventType(data);

    const container = document.createElement('div');
    container.className = `event-container type-${eventType}`;

    // 信号遮罩等级 class（v1.2: signal_quality_pct，兼容旧: signal_quality）
    const sq = data.signal_quality_pct ?? data.signal_quality ?? 100;
    if (sq < 80) container.classList.add('signal-l2');
    if (sq < 50) container.classList.add('signal-l3');
    if (sq < 20) container.classList.add('signal-l4');

    // 1. 事件头部
    container.appendChild(this._renderHeader(data));

    // 2. 事件描述（v1.2: narrative_segments，兼容旧: description）
    const segments = data.narrative_segments || (data.description
      ? [{text: data.description, protected: false, tag: 'narration'}]
      : []);
    container.appendChild(this._renderDescription(segments, sq));

    // 3. 绑定 NPC 标记条（v1.2 没有显式 bound_npcs，旧格式兼容）
    if (data.bound_npcs) {
      const npcBar = this._renderBoundNpcs(data.bound_npcs);
      if (npcBar) container.appendChild(npcBar);
    }

    // 4. 玩家选项（v1.2: options，兼容旧: player_options）
    const options = data.options || data.player_options;
    if (options && options.length > 0) {
      container.appendChild(this._renderOptions(options));
    }

    // 5. 结局判定（如果有）— v1.3 §13.3 展示性"可能结局列表"
    if (data.ending_determination) {
      container.appendChild(this._renderEnding(data.ending_determination));
    }

    targetEl.appendChild(container);

    // 滚动到视图
    container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    return container;
  }

  /* === 1. 事件头部 === */
  _renderHeader(data) {
    const header = document.createElement('div');
    header.className = 'event-header';

    // 推断事件类型
    const eventType = data.event_type || this._inferEventType(data);

    const typeTag = document.createElement('span');
    typeTag.className = `event-header-tag type-${eventType}`;
    const typeLabels = {
      mainline: '主线',
      crisis: '危机',
      discovery: '发现',
      ending: '结局'
    };
    typeTag.textContent = typeLabels[eventType] || '事件';
    header.appendChild(typeTag);

    // v1.2: chapter_id 显示
    if (data.chapter_id) {
      const chapter = document.createElement('span');
      chapter.className = 'event-header-chapter';
      chapter.textContent = data.chapter_id;
      header.appendChild(chapter);
    }

    const sol = document.createElement('span');
    sol.className = 'event-header-sol';
    sol.innerHTML = `SOL <span class="value">${data.sol ?? '---'}</span>`;
    header.appendChild(sol);

    if (data.branch) {
      const branch = document.createElement('span');
      branch.className = 'event-header-branch';
      branch.textContent = `分支 ${data.branch}`;
      header.appendChild(branch);
    }

    if (data.node_index) {
      const node = document.createElement('span');
      node.className = 'event-header-node';
      node.textContent = `节点 ${data.node_index}`;
      header.appendChild(node);
    }

    return header;
  }

  /* === 推断事件类型（v1.2 没有显式 event_type） === */
  _inferEventType(data) {
    if (data.event_type) return data.event_type;
    const eid = (data.event_id || '').toLowerCase();
    if (eid.includes('ending') || eid.startsWith('e1') || eid.startsWith('e5')) return 'ending';
    if (eid.includes('crisis') || eid.includes('emergency')) return 'crisis';
    if (eid.includes('discovery') || eid.includes('signal')) return 'discovery';
    return 'mainline';
  }

  /* === 2. 事件描述（走信号遮罩）
     v1.2: 接受 narrative_segments 数组 [{text, protected, tag?}]
     兼容旧: 接受字符串（内部转为 segments）
  === */
  _renderDescription(segmentsOrText, signalQuality) {
    const desc = document.createElement('div');
    desc.className = 'event-description';

    // 兼容旧格式：纯字符串转为 segments
    let segments = segmentsOrText;
    if (typeof segmentsOrText === 'string') {
      segments = [{text: segmentsOrText, protected: false, tag: 'narration'}];
    }
    if (!segments || segments.length === 0) return desc;

    // 逐段处理：高亮NPC名 + 信号遮罩
    if (this.signalRenderer && signalQuality < 80) {
      // 用 SignalRenderer 逐段渲染
      segments.forEach(seg => {
        const processedText = this._highlightNpcNames(seg.text);
        const rendered = this.signalRenderer.render(
          [{text: processedText, protected: seg.protected, tag: seg.tag}],
          signalQuality
        );
        if (seg.tag === 'npc_dialogue') {
          const line = document.createElement('div');
          line.className = 'event-desc-npc-line';
          line.innerHTML = rendered;
          desc.appendChild(line);
        } else {
          desc.innerHTML += rendered;
        }
      });
    } else {
      // 信号良好，直接高亮显示
      segments.forEach(seg => {
        const processedText = this._highlightNpcNames(seg.text);
        if (seg.tag === 'npc_dialogue') {
          const line = document.createElement('div');
          line.className = 'event-desc-npc-line';
          line.innerHTML = processedText;
          desc.appendChild(line);
        } else {
          desc.innerHTML += processedText;
        }
      });
    }

    return desc;
  }

  /* === 3. 绑定 NPC 标记条（v1.3 §13.4 bound_npcs 结构变体）=== */
  _renderBoundNpcs(boundNpcs) {
    const bar = document.createElement('div');
    bar.className = 'event-bound-npcs';

    if (boundNpcs.all_crew) {
      const tag = document.createElement('span');
      tag.className = 'event-bound-npc-tag';
      tag.innerHTML = `<span class="symbol">◆</span> 全员`;
      bar.appendChild(tag);
      return bar;
    }

    // v1.3 §13.4 key → role 映射
    const roleLabels = {
      primary: '主导',
      emotional_focus: '情感焦点',
      secondary: '次要',
      advocates: '支持方',
      skeptic: '怀疑方',
      advisor: '顾问',
      advisor_conflict: '冲突顾问',
      special: '特殊角色'
    };

    // 收集所有 NPC id + role
    const entries = [];
    const seen = new Set();

    const collect = (ids, role) => {
      if (!ids) return;
      const idArr = Array.isArray(ids) ? ids : [ids];
      idArr.forEach(id => {
        if (!seen.has(id)) {
          seen.add(id);
          entries.push({ id, role });
        }
      });
    };

    collect(boundNpcs.primary, 'primary');
    collect(boundNpcs.emotional_focus, 'emotional_focus');
    collect(boundNpcs.secondary, 'secondary');
    collect(boundNpcs.advisors, 'advocates');
    collect(boundNpcs.advocates, 'advocates');
    collect(boundNpcs.skeptic, 'skeptic');
    collect(boundNpcs.advisor, 'advisor');
    collect(boundNpcs.advisor_conflict, 'advisor_conflict');
    collect(boundNpcs.special, 'special');

    if (entries.length === 0) return null;

    entries.forEach(({ id, role }) => {
      const npc = this.npcConfig[id] || this.aiConfig[id];
      if (!npc) return;

      const isPrimary = (role === 'primary');
      const tag = document.createElement('span');
      tag.className = `event-bound-npc-tag ${isPrimary ? 'primary' : ''}`;
      if (isPrimary) tag.style.color = npc.color_hex;
      tag.innerHTML = `
        <span class="symbol" style="color: ${npc.color_hex || 'var(--color-text-primary)'}">${npc.symbol || '·'}</span>
        <span>${npc.name || id}</span>
        <span class="role">${roleLabels[role] || role}</span>
      `;
      bar.appendChild(tag);
    });

    return bar;
  }

  /* === 4. 玩家选项列表 === */
  _renderOptions(options) {
    const wrapper = document.createElement('div');
    wrapper.className = 'event-options';

    const label = document.createElement('div');
    label.className = 'event-options-label';
    label.textContent = '指挥官决策';
    wrapper.appendChild(label);

    options.forEach((opt, index) => {
      if (opt.disabled && opt.hidden) return; // 完全隐藏的选项不渲染

      const btn = document.createElement('div');
      btn.className = 'event-option';
      if (opt.recommended) btn.classList.add('recommended');
      if (opt.disabled) btn.classList.add('disabled');
      btn.setAttribute('tabindex', opt.disabled ? '-1' : '0');
      btn.setAttribute('data-option-id', opt.option_id);
      btn.setAttribute('data-index', index);

      const indexEl = document.createElement('span');
      indexEl.className = 'event-option-index';
      indexEl.textContent = index + 1;
      btn.appendChild(indexEl);

      const content = document.createElement('div');
      content.className = 'event-option-content';

      const labelText = document.createElement('div');
      labelText.className = 'event-option-label';
      labelText.textContent = opt.label;
      content.appendChild(labelText);

      if (opt.risk) {
        const risk = document.createElement('div');
        risk.className = 'event-option-risk';
        risk.textContent = `⚠ ${opt.risk}`;
        content.appendChild(risk);
      }

      if (opt.branch_lock) {
        const lock = document.createElement('div');
        lock.className = 'event-option-branch-lock';
        lock.textContent = '选择后将锁定当前分支';
        content.appendChild(lock);
      }

      btn.appendChild(content);

      // 交互事件
      if (!opt.disabled) {
        btn.addEventListener('click', () => this._handleOptionSelect(opt));
        btn.addEventListener('keydown', (e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            this._handleOptionSelect(opt);
          }
        });
      }

      wrapper.appendChild(btn);
    });

    // 键盘快捷选择（1/2/3...）
    this._optionKeyboardHandler = (e) => {
      const num = parseInt(e.key);
      if (num >= 1 && num <= options.length) {
        const opt = options[num - 1];
        if (!opt.disabled) this._handleOptionSelect(opt);
      }
    };
    document.addEventListener('keydown', this._optionKeyboardHandler);

    return wrapper;
  }

  /* === 选项选择处理 === */
  _handleOptionSelect(option) {
    if (this.selectedOption) return; // 已选过

    this.selectedOption = option.option_id;

    // 更新视觉状态
    const optionEls = document.querySelectorAll('.event-option');
    optionEls.forEach(el => {
      if (el.dataset.optionId === option.option_id) {
        el.classList.add('selected');
      } else {
        el.classList.add('disabled');
      }
    });

    // 移除键盘监听
    if (this._optionKeyboardHandler) {
      document.removeEventListener('keydown', this._optionKeyboardHandler);
      this._optionKeyboardHandler = null;
    }

    // 触发回调
    if (this.onOptionSelect) {
      this.onOptionSelect(option.option_id);
    }
  }

  /* === 5. 事件结果反馈 ===
     effectsData 结构（对齐 YAML effects 字段）:
       {
         state_set: { key: value },
         trust_delta: { npc_id: number },
         morale_delta: { npc_id: number | 'all': number },
         branch_progress: string + number,
         risk: string,
         crew_workload: number,
         cross_branch_hint: string
       }
  */
  renderResult(effectsData, targetEl, optionLabel) {
    if (!effectsData || !targetEl) return;

    const panel = document.createElement('div');
    panel.className = 'event-result';

    const header = document.createElement('div');
    header.className = 'event-result-header';
    header.textContent = optionLabel ? `执行结果 · ${optionLabel}` : '执行结果';
    panel.appendChild(header);

    const effectsList = document.createElement('div');
    effectsList.className = 'event-result-effects';

    // state_set
    if (effectsData.state_set) {
      Object.entries(effectsData.state_set).forEach(([key, val]) => {
        const row = document.createElement('div');
        row.className = 'effect-row';
        const isNumeric = typeof val === 'number';
        const isPositive = isNumeric && val > 0;
        row.innerHTML = `
          <span class="effect-icon">⚙</span>
          <span class="effect-label">${this._formatStateKey(key)}</span>
          <span class="effect-value ${isPositive ? 'positive' : (isNumeric && val < 0 ? 'negative' : 'neutral')}">
            ${isPositive ? '+' : ''}${val}
          </span>
        `;
        effectsList.appendChild(row);
      });
    }

    // trust_delta
    if (effectsData.trust_delta) {
      Object.entries(effectsData.trust_delta).forEach(([npcId, delta]) => {
        if (npcId === 'all') {
          this._addDeltaRow(effectsList, '◈', '全员信任', delta);
        } else {
          const npc = this.npcConfig[npcId] || this.aiConfig[npcId];
          const name = npc ? `${npc.symbol} ${npc.name}` : npcId;
          this._addDeltaRow(effectsList, '◈', `${name} 信任`, delta);
        }
      });
    }

    // morale_delta
    if (effectsData.morale_delta) {
      Object.entries(effectsData.morale_delta).forEach(([npcId, delta]) => {
        if (npcId === 'all') {
          this._addDeltaRow(effectsList, '♥', '全员士气', delta);
        } else {
          const npc = this.npcConfig[npcId] || this.aiConfig[npcId];
          const name = npc ? `${npc.symbol} ${npc.name}` : npcId;
          this._addDeltaRow(effectsList, '♥', `${name} 士气`, delta);
        }
      });
    }

    // crew_workload
    if (effectsData.crew_workload) {
      this._addDeltaRow(effectsList, '⚡', '全员工作负荷', effectsData.crew_workload);
    }

    // risk
    if (effectsData.risk) {
      const row = document.createElement('div');
      row.className = 'effect-row';
      row.innerHTML = `
        <span class="effect-icon">⚠</span>
        <span class="effect-risk">${effectsData.risk}</span>
      `;
      effectsList.appendChild(row);
    }

    // branch_progress
    if (effectsData.branch_progress) {
      const [branch, progress] = typeof effectsData.branch_progress === 'string'
        ? effectsData.branch_progress.match(/([A-D])\s*([+-]?\d+)/)?.slice(1) || [effectsData.branch_progress, '']
        : [effectsData.branch_progress.branch, effectsData.branch_progress.progress];

      const row = document.createElement('div');
      row.className = 'effect-row';
      const dots = this._renderProgressDots(branch, parseInt(progress) || 0);
      row.innerHTML = `
        <span class="effect-icon">▸</span>
        <span class="effect-branch-progress">
          <span class="branch-label">分支 ${branch}</span>
          进度
          <span class="progress-dots">${dots}</span>
        </span>
      `;
      effectsList.appendChild(row);
    }

    // cross_branch_hint
    if (effectsData.cross_branch_hint) {
      const row = document.createElement('div');
      row.className = 'effect-row';
      row.innerHTML = `
        <span class="effect-icon">◇</span>
        <span class="effect-state-set">${effectsData.cross_branch_hint}</span>
      `;
      effectsList.appendChild(row);
    }

    panel.appendChild(effectsList);
    targetEl.appendChild(panel);

    return panel;
  }

  /* === 5b. 事件结果反馈（v1.2 option_result payload）===
     v1.2 option_result 结构:
       {
         event_id: string,
         selected_option_id: string,
         effects_summary: string,       // 人类可读效果摘要
         state_update: [{              // 关键状态变化（v1.1 §3.2）
           path: string,               // 如 "resources.oxygen"
           old: any,
           new: any
         }],
         leads_to: string,             // 下一事件ID
         followup: { ... } | null      // 二级选项数据（触发二级渲染）
       }
  */
  renderOptionResult(resultData, targetEl, optionLabel) {
    if (!resultData || !targetEl) return;

    const panel = document.createElement('div');
    panel.className = 'event-result';

    const header = document.createElement('div');
    header.className = 'event-result-header';
    header.textContent = optionLabel
      ? `执行结果 · ${optionLabel}`
      : '执行结果';
    panel.appendChild(header);

    // 1. effects_summary（人类可读摘要，直接展示）
    if (resultData.effects_summary) {
      const summary = document.createElement('div');
      summary.className = 'event-result-summary';
      summary.textContent = resultData.effects_summary;
      panel.appendChild(summary);
    }

    // 2. v1.3 §14 effects 原始结构透传（逐行渲染，对齐 §14.4 映射表）
    //    优先于 state_update 渲染；若两者都有，effects 为主、state_update 作为补充
    if (resultData.effects) {
      this._renderEffectsIntoPanel(resultData.effects, panel);
    } else if (resultData.state_update && resultData.state_update.length > 0) {
      // v1.2 回退：仅 state_update 时渲染 path: old → new
      this._renderStateUpdateIntoPanel(resultData.state_update, panel);
    }

    // 3. leads_to 提示（v1.3: ending 命中时 leads_to 为 null，不渲染跳转提示）
    if (resultData.leads_to && !resultData.ending) {
      const leadsRow = document.createElement('div');
      leadsRow.className = 'effect-row';
      leadsRow.innerHTML = `
        <span class="effect-icon">→</span>
        <span class="effect-leads-to">下一步：${resultData.leads_to}</span>
      `;
      panel.appendChild(leadsRow);
    }

    targetEl.appendChild(panel);

    // 4. 如果有 followup，触发二级选项渲染
    if (resultData.followup) {
      const followupTarget = document.createElement('div');
      followupTarget.className = 'followup-target';
      panel.appendChild(followupTarget);
      this.renderFollowup(resultData.followup, followupTarget);
    }

    // 5. v1.3 §14.3 结局命中面板（ending 非空时渲染）
    if (resultData.ending) {
      this.renderEndingHit(resultData.ending, targetEl);
    }

    return panel;
  }

  /* === v1.2 回退：state_update 逐条渲染到 panel === */
  _renderStateUpdateIntoPanel(stateUpdate, panel) {
    const stateList = document.createElement('div');
    stateList.className = 'event-result-effects';

    const arr = Array.isArray(stateUpdate) ? stateUpdate : [stateUpdate];
    arr.forEach(su => {
      const row = document.createElement('div');
      row.className = 'effect-row';

      const oldValue = su.old;
      const newValue = su.new;
      const isNumeric = typeof newValue === 'number' && typeof oldValue === 'number';
      const delta = isNumeric ? newValue - oldValue : null;
      const isPositive = isNumeric && delta > 0;

      row.innerHTML = `
        <span class="effect-icon">⚙</span>
        <span class="effect-label">${this._formatStatePath(su.path)}</span>
        <span class="effect-value ${isPositive ? 'positive' : (isNumeric && delta < 0 ? 'negative' : 'neutral')}">
          ${isNumeric
            ? `${oldValue} → ${newValue} (${isPositive ? '+' : ''}${delta})`
            : `${oldValue ?? '—'} → ${newValue ?? '—'}`
          }
        </span>
      `;
      stateList.appendChild(row);
    });

    panel.appendChild(stateList);
  }

  /* === v1.3 §14.4 effects 逐行渲染（对齐映射表）=== */
  _renderEffectsIntoPanel(effectsData, panel) {
    const effectsList = document.createElement('div');
    effectsList.className = 'event-result-effects';

    // state_set → ⚙ 行
    if (effectsData.state_set) {
      Object.entries(effectsData.state_set).forEach(([key, val]) => {
        const row = document.createElement('div');
        row.className = 'effect-row';
        const isNumeric = typeof val === 'number';
        const isPositive = isNumeric && val > 0;
        row.innerHTML = `
          <span class="effect-icon">⚙</span>
          <span class="effect-label">${this._formatStateKey(key)}</span>
          <span class="effect-value ${isPositive ? 'positive' : (isNumeric && val < 0 ? 'negative' : 'neutral')}">
            ${isPositive ? '+' : ''}${val}
          </span>
        `;
        effectsList.appendChild(row);
      });
    }

    // trust_delta → ◈ 行
    if (effectsData.trust_delta) {
      Object.entries(effectsData.trust_delta).forEach(([npcId, delta]) => {
        if (npcId === 'all') {
          this._addDeltaRow(effectsList, '◈', '全员信任', delta);
        } else {
          const npc = this.npcConfig[npcId] || this.aiConfig[npcId];
          const name = npc ? `${npc.symbol} ${npc.name}` : npcId;
          this._addDeltaRow(effectsList, '◈', `${name} 信任`, delta);
        }
      });
    }

    // morale_delta → ♥ 行
    if (effectsData.morale_delta) {
      Object.entries(effectsData.morale_delta).forEach(([npcId, delta]) => {
        if (npcId === 'all') {
          this._addDeltaRow(effectsList, '♥', '全员士气', delta);
        } else {
          const npc = this.npcConfig[npcId] || this.aiConfig[npcId];
          const name = npc ? `${npc.symbol} ${npc.name}` : npcId;
          this._addDeltaRow(effectsList, '♥', `${name} 士气`, delta);
        }
      });
    }

    // resource_delta → 📦 行（v1.3 §14.4）
    if (effectsData.resource_delta) {
      Object.entries(effectsData.resource_delta).forEach(([res, delta]) => {
        this._addDeltaRow(effectsList, '📦', this._formatStateKey(res), delta);
      });
    }

    // crew_workload → ⏱ 行（v1.3 §14.4）
    if (effectsData.crew_workload) {
      this._addDeltaRow(effectsList, '⏱', '全员工作负荷', effectsData.crew_workload);
    }

    // branch_progress → ▸ 行
    if (effectsData.branch_progress) {
      const [branch, progress] = typeof effectsData.branch_progress === 'string'
        ? (effectsData.branch_progress.match(/([A-D])\s*([+-]?\d+)/)?.slice(1) || [effectsData.branch_progress, ''])
        : [effectsData.branch_progress.branch, effectsData.branch_progress.progress];

      const row = document.createElement('div');
      row.className = 'effect-row';
      const dots = this._renderProgressDots(branch, parseInt(progress) || 0);
      row.innerHTML = `
        <span class="effect-icon">▸</span>
        <span class="effect-branch-progress">
          <span class="branch-label">分支 ${branch}</span>
          进度
          <span class="progress-dots">${dots}</span>
        </span>
      `;
      effectsList.appendChild(row);
    }

    // risk → ⚠ 行
    if (effectsData.risk) {
      const row = document.createElement('div');
      row.className = 'effect-row';
      row.innerHTML = `
        <span class="effect-icon">⚠</span>
        <span class="effect-risk">${effectsData.risk}</span>
      `;
      effectsList.appendChild(row);
    }

    // narrative_flag → 🚩 行（v1.3 §14.4）
    if (effectsData.narrative_flag) {
      const row = document.createElement('div');
      row.className = 'effect-row';
      const flagVal = typeof effectsData.narrative_flag === 'object'
        ? Object.entries(effectsData.narrative_flag).map(([k,v]) => `${k}=${v}`).join(', ')
        : String(effectsData.narrative_flag);
      row.innerHTML = `
        <span class="effect-icon">🚩</span>
        <span class="effect-narrative-flag">${flagVal}</span>
      `;
      effectsList.appendChild(row);
    }

    // cross_branch_redirect → ⇄ 行（v1.3 §14.4）
    if (effectsData.cross_branch_redirect) {
      const row = document.createElement('div');
      row.className = 'effect-row';
      row.innerHTML = `
        <span class="effect-icon">⇄</span>
        <span class="effect-cross-branch">${effectsData.cross_branch_redirect}</span>
      `;
      effectsList.appendChild(row);
    }

    // 兜底：未在映射表中的 key → ▪ {key}: {value}
    const knownKeys = new Set(['state_set','trust_delta','morale_delta','resource_delta','crew_workload','branch_progress','risk','narrative_flag','cross_branch_redirect']);
    Object.entries(effectsData).forEach(([key, val]) => {
      if (knownKeys.has(key)) return;
      const row = document.createElement('div');
      row.className = 'effect-row';
      const valStr = typeof val === 'object' ? JSON.stringify(val) : String(val);
      row.innerHTML = `
        <span class="effect-icon">▪</span>
        <span class="effect-label">${key}</span>
        <span class="effect-value neutral">${valStr}</span>
      `;
      effectsList.appendChild(row);
    });

    panel.appendChild(effectsList);
  }

  /* === 格式化 state path（如 resources.oxygen → 资源·氧气）=== */
  _formatStatePath(path) {
    const pathMap = {
      'resources': '资源',
      'resources.oxygen': '氧气',
      'resources.water': '水',
      'resources.food': '食物',
      'resources.power': '电力',
      'resources.parts': '备用件',
      'comm_array_main.status': '通信阵列状态',
      'moxie2.status': 'MOXIE-2 状态',
      'crew_fatigue': '全员疲劳度',
      'morale_avg': '平均士气',
    };
    return pathMap[path] || path;
  }

  /* === 6. 任务下达面板 ===
     taskData 结构:
       {
         title: string,
         from: string,           // npc_id
         description: string,
         objectives: [string],
         reward: string
       }
  */
  renderTaskBriefing(taskData, targetEl) {
    if (!taskData || !targetEl) return;

    const panel = document.createElement('div');
    panel.className = 'task-briefing';

    const header = document.createElement('div');
    header.className = 'task-briefing-header';

    const npc = this.npcConfig[taskData.from] || this.aiConfig[taskData.from] || {};
    const icon = document.createElement('span');
    icon.className = 'task-briefing-icon';
    icon.textContent = '▣';
    header.appendChild(icon);

    const title = document.createElement('span');
    title.className = 'task-briefing-title';
    title.textContent = taskData.title || '任务下达';
    header.appendChild(title);

    if (taskData.from) {
      const from = document.createElement('span');
      from.className = 'task-briefing-from';
      from.textContent = `来自 ${npc.symbol || ''} ${npc.name || taskData.from}`;
      header.appendChild(from);
    }

    panel.appendChild(header);

    const body = document.createElement('div');
    body.className = 'task-briefing-body';

    if (taskData.description) {
      const desc = document.createElement('div');
      desc.className = 'task-briefing-desc';
      desc.textContent = taskData.description;
      body.appendChild(desc);
    }

    if (taskData.objectives && taskData.objectives.length > 0) {
      const objList = document.createElement('div');
      objList.className = 'task-briefing-objectives';
      taskData.objectives.forEach((obj, i) => {
        const objEl = document.createElement('div');
        objEl.className = 'task-objective';
        objEl.innerHTML = `
          <span class="obj-marker">[${i + 1}]</span>
          <span class="obj-text">${obj}</span>
        `;
        objList.appendChild(objEl);
      });
      body.appendChild(objList);
    }

    if (taskData.reward) {
      const reward = document.createElement('div');
      reward.className = 'task-briefing-reward';
      reward.innerHTML = `<span class="reward-label">奖励</span> ${taskData.reward}`;
      body.appendChild(reward);
    }

    panel.appendChild(body);
    targetEl.appendChild(panel);

    return panel;
  }

  /* === 7. Sol 推进通知（v1.3 §15 sol_advance 消息）=== */
  renderSolAdvance(solData, targetEl) {
    if (!solData || !targetEl) return;

    // v1.3 §15: chapter_changed=true 时播放章节切换过渡动画
    if (solData.chapter_changed) {
      this._renderChapterTransition(solData, targetEl);
      return;
    }

    const notice = document.createElement('div');
    notice.className = 'sol-advance-notice';

    const label = document.createElement('span');
    label.className = 'sol-label';
    label.textContent = 'SOL ADVANCE';
    notice.appendChild(label);

    const value = document.createElement('span');
    value.className = 'sol-value';
    value.textContent = `Sol ${solData.sol}`;
    notice.appendChild(value);

    if (solData.delta) {
      const delta = document.createElement('span');
      delta.className = 'sol-delta';
      delta.textContent = `+${solData.delta} Sol`;
      notice.appendChild(delta);
    }

    if (solData.chapter_name) {
      const chapter = document.createElement('span');
      chapter.className = 'sol-chapter';
      chapter.textContent = solData.chapter_name;
      notice.appendChild(chapter);
    }

    targetEl.appendChild(notice);
    return notice;
  }

  /* === 7b. 章节切换过渡动画（v1.3 §15 chapter_changed=true）=== */
  _renderChapterTransition(solData, targetEl) {
    // 章节切换全屏过渡
    const overlay = document.createElement('div');
    overlay.className = 'chapter-transition-overlay';

    const content = document.createElement('div');
    content.className = 'chapter-transition-content';

    const chapterLabel = document.createElement('div');
    chapterLabel.className = 'chapter-transition-label';
    chapterLabel.textContent = 'CHAPTER';
    content.appendChild(chapterLabel);

    const chapterName = document.createElement('div');
    chapterName.className = 'chapter-transition-name';
    chapterName.textContent = solData.chapter_name || '';
    content.appendChild(chapterName);

    const solLabel = document.createElement('div');
    solLabel.className = 'chapter-transition-sol';
    solLabel.textContent = `Sol ${solData.sol}`;
    content.appendChild(solLabel);

    overlay.appendChild(content);
    targetEl.appendChild(overlay);

    // 触发入场动画
    requestAnimationFrame(() => {
      overlay.classList.add('visible');
    });

    // 3 秒后淡出并移除
    setTimeout(() => {
      overlay.classList.remove('visible');
      overlay.classList.add('fading');
      setTimeout(() => {
        if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
      }, 800);
    }, 3000);

    return overlay;
  }

  /* === 8. 跟进决策面板（二级选项）===
     调用时机：玩家选完一级选项后，后端调度器检测到该选项带 followup_option 字段，
     不立即 leads_to，而是把 followup_option payload 推给前端。
     玩家在 followup 面板里二次选择，后端再走对应 effects → leads_to。

     接口数据结构（对齐云逸 2026-08-03 Case 1 B 方案 + 结构化字段）:
       {
         source: string,           // NPC/AI id，用于色条着色（如 'athena' / 'chen_hao'）
         prompt: string,           // 跟进提示文本
         options: [{
           option_id: string,      // 如 'B3_opt3a_accept_athena'
           label: string,
           risk: string,           // 可选
           recommended: boolean,   // 可选
           branch_lock: boolean,   // 可选
           disabled: boolean,       // 可选（condition 不满足）
           hidden: boolean,         // 可选（完全不显示）
         }],
         signal_quality: number    // 可选，0-100，复用主事件信号遮罩
       }
     回调：onFollowupSelect(followupOptionId)
  */
  renderFollowup(data, targetEl) {
    if (!data || !targetEl) return;

    this.followupSelectedOption = null;

    const container = document.createElement('div');
    container.className = 'followup-panel';

    // 源 NPC 色条（默认 athena 紫，AI 建议场景）
    const sourceId = data.source || 'athena';
    const sourceConfig = this.npcConfig[sourceId] || this.aiConfig[sourceId] || {};
    const sourceColor = sourceConfig.color_hex || 'var(--ai-athena)';
    container.style.setProperty('--followup-source-color', sourceColor);

    // 信号遮罩等级（与主事件一致）
    const sq = data.signal_quality ?? 100;
    if (sq < 80) container.classList.add('signal-l2');
    if (sq < 50) container.classList.add('signal-l3');
    if (sq < 20) container.classList.add('signal-l4');

    // 1. 头部：FOLLOWUP 标签 + 源
    const header = document.createElement('div');
    header.className = 'followup-header';
    const tag = document.createElement('span');
    tag.className = 'followup-tag';
    tag.textContent = 'FOLLOWUP';
    header.appendChild(tag);
    const sourceLabel = document.createElement('span');
    sourceLabel.className = 'followup-source';
    sourceLabel.innerHTML = sourceConfig.name
      ? `${sourceConfig.symbol || ''} ${sourceConfig.name} 建议`
      : '跟进决策';
    header.appendChild(sourceLabel);
    container.appendChild(header);

    // 2. 跟进提示文本（走信号遮罩，与事件描述同规则）
    if (data.prompt) {
      container.appendChild(this._renderFollowupPrompt(data.prompt, sq));
    }

    // 3. 二级选项列表
    if (data.options && data.options.length > 0) {
      container.appendChild(this._renderFollowupOptions(data.options));
    }

    targetEl.appendChild(container);
    container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    return container;
  }

  /* === followup 提示文本（复用事件描述遮罩逻辑） === */
  _renderFollowupPrompt(text, signalQuality) {
    const prompt = document.createElement('div');
    prompt.className = 'followup-prompt';
    if (!text) return prompt;
    let processedText = this._highlightNpcNames(text);
    if (this.signalRenderer && signalQuality < 80) {
      const segments = this._splitProtectedSegments(processedText);
      processedText = this.signalRenderer.render(segments, signalQuality);
    }
    prompt.innerHTML = processedText;
    return prompt;
  }

  /* === followup 二级选项列表（序号 a/b/c 区分一级 1/2/3） === */
  _renderFollowupOptions(options) {
    const wrapper = document.createElement('div');
    wrapper.className = 'followup-options';

    const label = document.createElement('div');
    label.className = 'followup-options-label';
    label.textContent = '指挥官决断';
    wrapper.appendChild(label);

    const visibleOptions = options.filter(o => !(o.disabled && o.hidden));

    visibleOptions.forEach((opt, index) => {
      const btn = document.createElement('div');
      btn.className = 'followup-option';
      if (opt.recommended) btn.classList.add('recommended');
      if (opt.disabled) btn.classList.add('disabled');
      btn.setAttribute('tabindex', opt.disabled ? '-1' : '0');
      btn.setAttribute('data-option-id', opt.option_id);
      btn.setAttribute('data-index', index);

      const indexEl = document.createElement('span');
      indexEl.className = 'followup-option-index';
      indexEl.textContent = String.fromCharCode(97 + index); // a/b/c...
      btn.appendChild(indexEl);

      const content = document.createElement('div');
      content.className = 'followup-option-content';

      const labelText = document.createElement('div');
      labelText.className = 'followup-option-label';
      labelText.textContent = opt.label;
      content.appendChild(labelText);

      if (opt.risk) {
        const risk = document.createElement('div');
        risk.className = 'followup-option-risk';
        risk.textContent = `⚠ ${opt.risk}`;
        content.appendChild(risk);
      }

      if (opt.branch_lock) {
        const lock = document.createElement('div');
        lock.className = 'followup-option-branch-lock';
        lock.textContent = '选择后将锁定当前分支';
        content.appendChild(lock);
      }

      btn.appendChild(content);

      if (!opt.disabled) {
        btn.addEventListener('click', () => this._handleFollowupSelect(opt));
        btn.addEventListener('keydown', (e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            this._handleFollowupSelect(opt);
          }
        });
      }

      wrapper.appendChild(btn);
    });

    // 键盘快捷键 a/b/c（区分一级选项的 1/2/3）
    this._followupKeyboardHandler = (e) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const ch = e.key.toLowerCase();
      if (/^[a-z]$/.test(ch)) {
        const idx = ch.charCodeAt(0) - 97;
        if (idx >= 0 && idx < visibleOptions.length) {
          const opt = visibleOptions[idx];
          if (!opt.disabled) this._handleFollowupSelect(opt);
        }
      }
    };
    document.addEventListener('keydown', this._followupKeyboardHandler);

    return wrapper;
  }

  /* === followup 选项选择处理 === */
  _handleFollowupSelect(option) {
    if (this.followupSelectedOption) return;

    this.followupSelectedOption = option.option_id;

    const optionEls = document.querySelectorAll('.followup-option');
    optionEls.forEach(el => {
      if (el.dataset.optionId === option.option_id) {
        el.classList.add('selected');
      } else {
        el.classList.add('disabled');
      }
    });

    if (this._followupKeyboardHandler) {
      document.removeEventListener('keydown', this._followupKeyboardHandler);
      this._followupKeyboardHandler = null;
    }

    if (this.onFollowupSelect) {
      this.onFollowupSelect(option.option_id);
    }
  }

  /* === 9. 结局判定面板 ===
     v1.3 §13.3 ending_determination（展示性"可能结局列表"）
     v1.3 §14.3 ending（结局命中面板，紫色发光居中）

     两种调用场景：
     a) story_event.ending_determination 非空 → _renderEnding() 渲染"可能结局列表"
     b) option_result.ending 非空 → renderEndingHit() 渲染"结局命中"面板
  */

  /* 9a. 可能结局列表（story_event 终局节点展示性面板） */
  _renderEnding(endingDetermination) {
    if (!endingDetermination || endingDetermination.length === 0) {
      return document.createDocumentFragment();
    }

    const panel = document.createElement('div');
    panel.className = 'ending-panel ending-list-panel';

    const header = document.createElement('div');
    header.className = 'ending-header';
    const title = document.createElement('div');
    title.className = 'ending-title';
    title.textContent = '可能结局';
    header.appendChild(title);
    panel.appendChild(header);

    endingDetermination.forEach(ending => {
      const item = document.createElement('div');
      item.className = 'ending-list-item';
      item.innerHTML = `
        <span class="ending-id">${ending.ending}</span>
        <span class="ending-desc-text">${ending.description}</span>
        <span class="ending-condition">条件: ${ending.condition}</span>
      `;
      panel.appendChild(item);
    });

    return panel;
  }

  /* 9b. 结局命中面板（option_result.ending 非空时调用） */
  renderEndingHit(ending, targetEl) {
    if (!ending || !targetEl) return;

    const panel = document.createElement('div');
    panel.className = 'ending-panel ending-hit-panel';

    const header = document.createElement('div');
    header.className = 'ending-header';

    const id = document.createElement('div');
    id.className = 'ending-id';
    id.textContent = ending.ending_id;
    header.appendChild(id);

    const title = document.createElement('div');
    title.className = 'ending-title';
    title.textContent = ending.description || '';
    header.appendChild(title);

    panel.appendChild(header);

    const footer = document.createElement('div');
    footer.className = 'ending-hit-footer';
    footer.textContent = '— 事件链终止 —';
    panel.appendChild(footer);

    targetEl.appendChild(panel);

    // 居中滚动
    panel.scrollIntoView({ behavior: 'smooth', block: 'center' });

    return panel;
  }

  /* === 辅助：高亮 NPC 名 === */
  _highlightNpcNames(text) {
    let result = text;
    // 遍历所有 NPC 名，替换为高亮 span
    const allChars = { ...this.npcConfig, ...this.aiConfig };
    Object.values(allChars).forEach(npc => {
      if (npc.name && result.includes(npc.name)) {
        result = result.replaceAll(
          npc.name,
          `<span class="npc-ref" style="color: ${npc.color_hex}">${npc.symbol} ${npc.name}</span>`
        );
      }
    });
    return result;
  }

  /* === 辅助：拆分受保护/非受保护段 === */
  _splitProtectedSegments(text) {
    // NPC 引用和 < > 标签内容为受保护段
    // 其余为非受保护
    const segments = [];
    // 按高亮 span 拆分
    const parts = text.split(/(<span class="npc-ref"[^>]*>.*?<\/span>)/g);
    parts.forEach(part => {
      if (!part) return;
      if (part.startsWith('<span class="npc-ref"')) {
        segments.push({ text: part, protected: true });
      } else {
        segments.push({ text: part, protected: false });
      }
    });
    return segments;
  }

  /* === 辅助：添加数值变化行 === */
  _addDeltaRow(parent, icon, label, delta) {
    const row = document.createElement('div');
    row.className = 'effect-row';
    const isPositive = delta > 0;
    row.innerHTML = `
      <span class="effect-icon">${icon}</span>
      <span class="effect-label">${label}</span>
      <span class="effect-value ${isPositive ? 'positive' : (delta < 0 ? 'negative' : 'neutral')}">
        ${isPositive ? '+' : ''}${delta}
      </span>
    `;
    parent.appendChild(row);
  }

  /* === 辅助：分支进度点 === */
  _renderProgressDots(branch, progress) {
    const maxDots = 5; // 每分支5节点
    let html = '';
    for (let i = 0; i < maxDots; i++) {
      html += `<span class="dot ${i < progress ? 'filled' : ''}"></span>`;
    }
    return html;
  }

  /* === 辅助：格式化状态键名 === */
  _formatStateKey(key) {
    const keyMap = {
      'comm_array_main_status': '通信阵列',
      'moxie2_status': 'MOXIE-2',
      'parts_available': '备用件',
      'earth_contact_confirmed': '地球联络',
      'rescue_eta_sol': '救援预计Sol',
      'strategy': '生存策略',
      'boarding_strategy': '登舱方案',
      'local_crisis_management': '本地危机管理',
      'earth_emergency_request': '紧急请求'
    };
    return keyMap[key] || key.replace(/_/g, ' ');
  }

  /* === 清理当前事件 === */
  cleanup() {
    if (this._optionKeyboardHandler) {
      document.removeEventListener('keydown', this._optionKeyboardHandler);
      this._optionKeyboardHandler = null;
    }
    if (this._followupKeyboardHandler) {
      document.removeEventListener('keydown', this._followupKeyboardHandler);
      this._followupKeyboardHandler = null;
    }
    this.activeEvent = null;
    this.selectedOption = null;
    this.followupSelectedOption = null;
  }
}

/* === Mock 数据（Schema 定稿前驱动预览） ===
   基于蔚蓝 branch_a_earth_rescue.yaml ev_A1 节点结构
*/
const MOCK_EVENT_DATA = {
  event_id: 'ev_A1_comm_array_repair_decision',
  node_index: 1,
  branch: 'A',
  event_type: 'mainline',
  sol: 108,
  sol_range: [105, 120],
  description: `艾莎报告：修复主通信阵列在技术上可行，需要 8 单位备用件 + 5 个 Sol 工期。\n但这意味着从 MOXIE-2 备件中调拨——氧气修复进度将延迟 3 个 Sol。\n陈昊召集小组讨论。维克托反对（备件应优先保命系统），索菲亚中立，艾莎强烈主张修通信。`,
  bound_npcs: {
    primary: 'aisha',
    secondary: ['chen_hao', 'viktor', 'sophia']
  },
  player_options: [
    {
      option_id: 'A1_opt1_repair_comm',
      label: '修复主通信阵列（联系地球优先）',
      effects: { state_set: { comm_array_main_status: 'repairing', parts_available: -8 }, trust_delta: { aisha: +10, viktor: -5, chen_hao: +3 }, branch_progress: 'A +1' },
      leads_to: 'ev_A2_earth_contact'
    },
    {
      option_id: 'A1_opt2_priority_moxie',
      label: '优先修 MOXIE-2（保命系统优先）',
      effects: { state_set: { moxie2_status: 'repairing', parts_available: -5 }, trust_delta: { viktor: +8, aisha: -5, chen_hao: +2 }, branch_progress: 'A 0' },
      leads_to: 'ev_A1b_delayed_comm_attempt'
    },
    {
      option_id: 'A1_opt3_parallel',
      label: '并行修复（人力拆分，风险双倍）',
      risk: '双线作业失误率 15%',
      effects: { state_set: { comm_array_main_status: 'repairing', moxie2_status: 'repairing', crew_fatigue: +0.2 }, trust_delta: { aisha: +5, viktor: +3, chen_hao: +5 }, branch_progress: 'A +1' },
      recommended: true,
      leads_to: 'ev_A2_earth_contact'
    }
  ],
  signal_quality: 65
};

const MOCK_TASK_DATA = {
  title: '通信阵列修复任务',
  from: 'aisha',
  description: '艾莎请求你协助调拨备用件并安排工期。修复完成后可恢复与地球的直接通信。',
  objectives: [
    '调拨 8 单位备用件到通信阵列',
    '安排 5 个 Sol 工期（期间工程效率降低）',
    '确认 MOXIE-2 延迟不影响生存线'
  ],
  reward: '通信阵列修复 + 分支A进度 +1'
};

const MOCK_RESULT_DATA = {
  state_set: { comm_array_main_status: 'repairing', parts_available: -8 },
  trust_delta: { aisha: +10, viktor: -5, chen_hao: +3 },
  branch_progress: 'A +1',
  crew_workload: +0.15
};

/* === v1.2 Schema Mock 数据 === */

const MOCK_V12_STORY_EVENT = {
  event_id: 'ev_A1_comm_array_repair_decision',
  chapter_id: 'CH01_SURVIVAL',
  node_index: 1,
  branch: 'A',
  narrative_segments: [
    { text: '艾莎报告：修复主通信阵列在技术上可行，需要 8 单位备用件 + 5 个 Sol 工期。', protected: false, tag: 'narration' },
    { text: '但这意味着从 MOXIE-2 备件中调拨——氧气修复进度将延迟 3 个 Sol。', protected: false, tag: 'narration' },
    { text: '陈昊召集小组讨论。维克托反对（备件应优先保命系统），索菲亚中立，艾莎强烈主张修通信。', protected: false, tag: 'npc_dialogue' }
  ],
  options: [
    {
      option_id: 'A1_opt1_repair_comm',
      label: '修复主通信阵列（联系地球优先）'
    },
    {
      option_id: 'A1_opt2_priority_moxie',
      label: '优先修 MOXIE-2（保命系统优先）'
    },
    {
      option_id: 'A1_opt3_parallel',
      label: '并行修复（人力拆分，风险双倍）',
      followup: {
        source: 'athena',
        prompt: '雅典娜提示：并行修复需要将工程组拆分为两队。请确认人员分配方案。',
        options: [
          { option_id: 'A1_opt3a_balanced', label: '均衡分配（每队2人）', recommended: true },
          { option_id: 'A1_opt3b_aisha_heavy', label: '偏重通信阵列（艾莎+陈昊）' },
          { option_id: 'A1_opt3c_viktor_heavy', label: '偏重MOXIE-2（维克托+马库斯）' }
        ]
      }
    }
  ],
  signal_quality_pct: 65,
  latency_ms: 120
};

const MOCK_V12_OPTION_RESULT = {
  event_id: 'ev_A1_comm_array_repair_decision',
  selected_option_id: 'A1_opt1_repair_comm',
  effects_summary: '通信阵列开始修复，预计5个Sol后完成。备用件消耗8单位。艾莎信任度提升，维克托略有不满。',
  state_update: [
    { path: 'comm_array_main.status', old: 'damaged', new: 'repairing' },
    { path: 'resources.parts', old: 20, new: 12 },
    { path: 'npc.aisha.trust', old: 50, new: 60 },
    { path: 'npc.viktor.trust', old: 55, new: 50 },
    { path: 'npc.chen_hao.trust', old: 60, new: 63 }
  ],
  leads_to: 'ev_A2_earth_contact',
  followup: null
};

// 全局单例
const eventPanel = new EventPanel();
