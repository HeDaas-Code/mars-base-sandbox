/* ============================================
   MapView · 地图视图组件
   来源：幻影 v2.0 · 2.3 节
   规则：CSS Grid 网格布局（基地平面图） + SVG 简笔图（周边地形）
   不走 ASCII
   ============================================ */

class MapView {
  constructor(elementId) {
    this.el = document.getElementById(elementId);
    if (!this.el) throw new Error(`MapView 元素 #${elementId} 不存在`);
    // 基地平面图网格（6x8）
    this.baseGrid = this._initBaseGrid();
    // 周边地形（用 SVG 渲染）
    this.terrainData = {
      craters: [{ x: 100, y: 50, r: 30 }, { x: 300, y: 200, r: 50 }],
      routes: [{ from: 'base', to: 'mines', difficulty: 0.4 }],
      points: [
        { id: 'mines', x: 400, y: 100, name: '矿点 A' },
        { id: 'landing', x: 200, y: 250, name: '着陆点' },
        { id: 'storm', x: 350, y: 180, name: '沙尘区', danger: true }
      ]
    };
  }

  /* === 初始化基地网格 === */
  _initBaseGrid() {
    // 简化版基地平面图
    // B = 基地核心, F = 设施, . = 空地, # = 墙
    const layout = [
      ['#', '#', '#', 'F', 'F', '#', '#', '#'],
      ['#', 'B', 'B', 'B', 'F', 'F', 'F', '#'],
      ['#', 'B', 'B', 'B', 'F', '.', '.', '#'],
      ['#', 'F', 'B', '.', '.', '.', 'F', '#'],
      ['#', 'F', 'F', '.', 'F', 'F', 'F', '#'],
      ['#', '#', '#', '#', '#', '#', '#', '#']
    ];
    // 设施名称映射
    const facilityNames = {
      'B': '核心区',
      'F': '设施区',
      '.': '通道',
      '#': '墙体'
    };
    return { layout, facilityNames };
  }

  /* === 渲染基地平面图（CSS Grid） === */
  _renderBaseGrid() {
    const { layout, facilityNames } = this.baseGrid;
    const cols = layout[0].length;
    const rows = layout.length;

    return `
      <div class="panel-title">基地平面图</div>
      <div class="map-grid" style="grid-template-columns:repeat(${cols}, 1fr)">
        ${layout.flatMap((row, r) => row.map((cell, c) => {
          const cellType = cell === 'B' ? 'base'
                         : cell === 'F' ? 'facility'
                         : cell === '.' ? 'discovered'
                         : 'unexplored';
          const isWall = cell === '#';
          const name = facilityNames[cell] || '';
          return `<div class="map-cell ${cellType}" title="[${r},${c}] ${name}">
            ${isWall ? '' : cell}
          </div>`;
        }).join('')).join('')}
      </div>
      <div style="font-size:10px;color:var(--color-text-secondary);margin-top:4px">
        图例：B=核心区 F=设施区 .=通道 #=墙体
      </div>
    `;
  }

  /* === 渲染周边地形（SVG 简笔图） === */
  _renderTerrainSVG() {
    const { craters, points, routes } = this.terrainData;
    return `
      <div class="panel-title" style="margin-top:8px">周边地形</div>
      <svg viewBox="0 0 500 300" style="width:100%;background:var(--color-bg-primary);border:1px solid var(--color-border)">
        <!-- 基地位置标记 -->
        <rect x="240" y="130" width="20" height="20" fill="var(--color-text-primary)" opacity="0.9">
          <animate attributeName="opacity" values="0.9;0.5;0.9" dur="2s" repeatCount="indefinite"/>
        </rect>
        <text x="250" y="170" text-anchor="middle" fill="var(--color-text-primary)" font-size="10">基地</text>

        <!-- 陨石坑 -->
        ${craters.map(c => `
          <circle cx="${c.x}" cy="${c.y}" r="${c.r}"
                  fill="none" stroke="var(--color-text-secondary)"
                  stroke-width="1" stroke-dasharray="2,2" opacity="0.5"/>
        `).join('')}

        <!-- 探索路线 -->
        ${routes.map(r => `
          <line x1="250" y1="140" x2="${points.find(p => p.id === r.to)?.x || 0}"
                y2="${points.find(p => p.id === r.to)?.y || 0}"
                stroke="${r.danger ? 'var(--color-warning)' : 'var(--color-signal)'}"
                stroke-width="1" stroke-dasharray="3,3" opacity="0.6"/>
        `).join('')}

        <!-- 兴趣点 -->
        ${points.map(p => `
          <g>
            <circle cx="${p.x}" cy="${p.y}" r="4"
                    fill="${p.danger ? 'var(--color-warning)' : 'var(--color-text-secondary)'}"/>
            ${p.danger ? `<animate attributeName="opacity" values="1;0.3;1" dur="1s" repeatCount="indefinite"/>` : ''}
            <text x="${p.x + 8}" y="${p.y + 3}" fill="var(--color-text-secondary)" font-size="9">${p.name}</text>
          </g>
        `).join('')}
      </svg>
    `;
  }

  render() {
    this.el.innerHTML = `
      <div class="map-view">
        ${this._renderBaseGrid()}
        ${this._renderTerrainSVG()}
      </div>
    `;
  }
}
