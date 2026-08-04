/* ============================================
   Mock 数据 · 模拟后端 WebSocket 推送 v2.0
   ------------------------------------------------
   数据源：云逸《WebSocket接口定义 v1.1》§4.1 segments 示例
   说明：云逸接口定义已出，但仍用 mock 先行开发
        所有字段已对齐 v1.1 协议（snake_case / signal_quality_pct 0-100 整数）

   消息信封结构（云逸 v1.1 §2.1）：
     { msg_id, type, ts_tick, payload }

   agent_message payload 结构（云逸 v1.1 §4.1）：
     { sender_id, sender_label, segments[], signal_quality_pct, latency_ms, emotion_hint? }
   ============================================ */

// === Mock WebSocket 推送消息 ===
const MOCK_MESSAGES = {
  // === 启动握手成功后的 session_init 消息 ===
  // 云逸 v1.1 §3.2 session_init
  session_init: {
    msg_id: 'mock-001',
    type: 'session_init',
    ts_tick: 0,
    payload: {
      session_id: 'mock-session-001',
      resume_mode: 'cold',  // 全新连接
      player_state: {
        player_id: 'earth_observer_01',
        player_name: '观察者',
        established_at: '2087-04-15T08:00:00Z',
        signal_quality_pct: 62
      },
      world_snapshot: {
        sol: 1,
        mars_time: '08:00',
        base: {
          name: '赫拉克勒斯-7号基地',
          integrity: 0.78,
          resources: {
            oxygen: { current: 78, max: 100, rate: -0.3 },
            power: { current: 85, max: 100, rate: 0.5 },
            water: { current: 65, max: 100, rate: -0.1 },
            food: { current: 90, max: 100, rate: -0.5 }
          },
          materials: {
            iron: 24,
            silicon: 12,
            carbon: 5
          }
        },
        agents: [
          {
            agent_id: 'chen_hao',
            label: 'CMDR',
            name: '陈昊',
            location: '指挥舱',
            health: 1.0,
            stress: 0.45,
            morale: 0.55,
            current_task: '评估基地损害'
          },
          {
            agent_id: 'sophia_ramirez',
            label: 'BIO',
            name: '索菲亚',
            location: '生物实验室',
            health: 1.0,
            stress: 0.30,
            morale: 0.60,
            current_task: '盘点生命保障系统'
          },
          {
            agent_id: 'viktor_ivanov',
            label: 'ENG',
            name: '维克托',
            location: '工程舱',
            health: 0.9,
            stress: 0.55,
            morale: 0.50,
            current_task: '修复电力系统'
          },
          {
            agent_id: 'aisha_khan',
            label: 'COMM',
            name: '艾莎',
            location: '通信舱',
            health: 1.0,
            stress: 0.40,
            morale: 0.65,
            current_task: '校准主通信阵列'
          },
          {
            agent_id: 'marcus_weber',
            label: 'MED',
            name: '马库斯',
            location: '医疗舱',
            health: 1.0,
            stress: 0.35,
            morale: 0.60,
            current_task: '医疗物资盘点'
          },
          {
            agent_id: 'lin_ruoxi',
            label: 'ATM',
            name: '林若曦',
            location: '气象观测站',
            health: 1.0,
            stress: 0.40,
            morale: 0.55,
            current_task: '监测沙尘暴动向'
          }
        ]
      },
      signal_quality_pct: 62
    }
  },

  // === 握手后的首条 agent_message（信使 AI 引导） ===
  courier_intro: {
    msg_id: 'mock-002',
    type: 'agent_message',
    ts_tick: 1,
    payload: {
      sender_id: 'courier',
      sender_label: 'AI',
      segments: [
        { text: '[COURIER]> ', protected: true, tag: 'speaker_label' },
        { text: '检测到外部信号接入，正在建立加密信道...\n', protected: false, tag: 'smalltalk' },
        { text: '信道建立成功。信号源：未知地球终端。\n', protected: true, tag: 'command_response' },
        { text: '已通知基地指挥官', protected: false, tag: 'narration' },
        { text: '陈昊', protected: true, tag: 'npc_name' },
        { text: '。请稍候。\n', protected: false, tag: 'narration' }
      ],
      signal_quality_pct: 85,
      latency_ms: 800,
      emotion_hint: { ai_status: 'normal' }
    }
  },

  // === 陈昊首条响应（云逸 §4.1 示例，作为低信号质量样本） ===
  // stress 0.55 / morale 0.50 → 落 [0.4,0.6)×[0.4,0.6) → alert（带2 mid）
  chen_low_signal: {
    msg_id: 'mock-003',
    type: 'agent_message',
    ts_tick: 5,
    payload: {
      sender_id: 'chen_hao',
      sender_label: 'CMDR',
      segments: [
        { text: '[CMDR]> ', protected: true, tag: 'speaker_label' },
        { text: '信号有点弱……外面的', protected: false, tag: 'narration' },
        { text: '气闸舱', protected: true, tag: 'mission_keyword' },
        { text: '温度还在下降', protected: false, tag: 'speech' }
      ],
      signal_quality_pct: 45,  // L3 重度档
      latency_ms: 2300,
      emotion_hint: {
        stress: 0.55,
        morale: 0.50,
        emotion_label: 'alert'
      }
    }
  },

  // === 中等信号质量样本（L2 轻度档） ===
  // stress 0.30 / morale 0.60 → 落 [0.2,0.4)×[0.6,0.8) → engaged（带1 stable）
  sophia_medium_signal: {
    msg_id: 'mock-004',
    type: 'agent_message',
    ts_tick: 8,
    payload: {
      sender_id: 'sophia_ramirez',
      sender_label: 'BIO',
      segments: [
        { text: '[BIO]> ', protected: true, tag: 'speaker_label' },
        { text: '生命保障系统循环还算稳定，但', protected: false, tag: 'speech' },
        { text: '氧气', protected: true, tag: 'mission_keyword' },
        { text: '的消耗速度比预期快了百分之十五', protected: false, tag: 'speech' }
      ],
      signal_quality_pct: 65,  // L2 轻度档
      latency_ms: 1500,
      emotion_hint: {
        stress: 0.30,
        morale: 0.60,
        emotion_label: 'engaged'
      }
    }
  },

  // === 高信号质量样本（L1 正常档） ===
  // stress 0.40 / morale 0.70 → 落 [0.4,0.6)×[0.6,0.8) → determined（带2 stable）
  viktor_clear: {
    msg_id: 'mock-005',
    type: 'agent_message',
    ts_tick: 12,
    payload: {
      sender_id: 'viktor_ivanov',
      sender_label: 'ENG',
      segments: [
        { text: '[ENG]> ', protected: true, tag: 'speaker_label' },
        { text: '电力系统修好了。', protected: false, tag: 'speech' },
        { text: '太阳能阵列', protected: true, tag: 'mission_keyword' },
        { text: '重新连上主线了，输出稳定在百分之八十五。', protected: false, tag: 'speech' }
      ],
      signal_quality_pct: 92,  // L1 正常档
      latency_ms: 600,
      emotion_hint: {
        stress: 0.40,
        morale: 0.70,
        emotion_label: 'determined'
      }
    }
  },

  // === 极差信号样本（L4 不可读档）+ band3 strained ===
  // stress 0.75 / morale 0.30 → 落 [0.6,0.8)×[0.2,0.4) → strained（带3 low）
  // 注：L4 时情绪抖动应被禁用（信号遮罩优先），仅保留色彩
  aisha_lost: {
    msg_id: 'mock-006',
    type: 'agent_message',
    ts_tick: 15,
    payload: {
      sender_id: 'aisha_khan',
      sender_label: 'COMM',
      segments: [
        { text: '[COMM]> ', protected: true, tag: 'speaker_label' },
        { text: '信号……还在吗……干扰……太强……', protected: false, tag: 'speech' },
        { text: '主通信阵列', protected: true, tag: 'mission_keyword' },
        { text: '……阵……风……', protected: false, tag: 'speech' }
      ],
      signal_quality_pct: 12,  // L4 极差档
      latency_ms: 3500,
      emotion_hint: {
        stress: 0.75,
        morale: 0.30,
        emotion_label: 'strained'
      }
    }
  },

  // === 高压力崩溃样本（band4 breakdown，验证抖动+红色）===
  // stress 0.85 / morale 0.10 → 落 [0.8,1.0]×[0.0,0.2) → breakdown
  chen_breakdown: {
    msg_id: 'mock-007',
    type: 'agent_message',
    ts_tick: 18,
    payload: {
      sender_id: 'chen_hao',
      sender_label: 'CMDR',
      segments: [
        { text: '[CMDR]> ', protected: true, tag: 'speaker_label' },
        { text: '不行了不行了，氧气掉得太快，我们撑不过今晚', protected: false, tag: 'speech' }
      ],
      signal_quality_pct: 70,  // L2 轻度档（保证抖动可见）
      latency_ms: 1800,
      emotion_hint: {
        stress: 0.85,
        morale: 0.10,
        emotion_label: 'breakdown'
      }
    }
  },

  // === 雅典娜 AI 状态降级样本 ===
  athena_degraded: {
    msg_id: 'mock-008',
    type: 'agent_message',
    ts_tick: 22,
    payload: {
      sender_id: 'athena',
      sender_label: 'AI',
      segments: [
        { text: '[ATHENA]> ', protected: true, tag: 'speaker_label' },
        { text: '检测到推理节点响应延迟超过阈值。已切换至降级模式，部分决策路径暂时不可用。', protected: false, tag: 'speech' }
      ],
      signal_quality_pct: 88,
      latency_ms: 2500,
      emotion_hint: { ai_status: 'degraded' }
    }
  },

  // === 玩家未知指令的 command_response ===
  unknown_command: {
    msg_id: 'mock-err',
    type: 'command_response',
    ts_tick: 0,
    payload: {
      output_segments: [
        { text: 'command not found. 输入 help 查看可用指令。', protected: true, tag: 'command_response' }
      ],
      data: null
    }
  },

  // === system_event 沙尘暴来袭 ===
  dust_storm: {
    msg_id: 'mock-evt-001',
    type: 'system_event',
    ts_tick: 20,
    payload: {
      event_id: 'evt_dust_storm_001',
      category: 'crisis',
      severity: 'alert',
      text: '沙尘暴警报：基地外风速达 28 m/s，能见度不足 10 米。所有舱外活动暂停。'
    }
  },

  // === alert 氧气告急 ===
  oxygen_alert: {
    msg_id: 'mock-alert-001',
    type: 'alert',
    ts_tick: 25,
    payload: {
      level: 'danger',
      code: 'OXYGEN_LOW',
      text: '氧气储量跌破 30%，请立即指导基地采取应对措施。'
    }
  }
};

// === Shell 命令 mock 响应（锐锋后端 ls/status/talk 已跑通，格式按 WebSocket v1.1） ===
// command_response payload: { output_segments[], data }
const MOCK_COMMAND_RESPONSES = {
  // ls: 列出基地当前可交互的舱室/NPC
  ls: {
    msg_id: 'mock-cmd-ls',
    type: 'command_response',
    ts_tick: 0,
    payload: {
      output_segments: [
        { text: '指挥舱    chen_hao     [CMDR]  在线\n', protected: true, tag: 'command_response' },
        { text: '生物实验室 sophia_ramirez [BIO]   在线\n', protected: true, tag: 'command_response' },
        { text: '工程舱    viktor_ivanov [ENG]   在线\n', protected: true, tag: 'command_response' },
        { text: '通信舱    aisha_khan   [COMM]  在线\n', protected: true, tag: 'command_response' },
        { text: '医疗舱    marcus_weber  [MED]   在线\n', protected: true, tag: 'command_response' },
        { text: '气象站    lin_ruoxi    [ATM]   在线\n', protected: true, tag: 'command_response' }
      ],
      data: {
        entries: [
          { location: '指挥舱', agent_id: 'chen_hao', label: 'CMDR', online: true },
          { location: '生物实验室', agent_id: 'sophia_ramirez', label: 'BIO', online: true },
          { location: '工程舱', agent_id: 'viktor_ivanov', label: 'ENG', online: true },
          { location: '通信舱', agent_id: 'aisha_khan', label: 'COMM', online: true },
          { location: '医疗舱', agent_id: 'marcus_weber', label: 'MED', online: true },
          { location: '气象站', agent_id: 'lin_ruoxi', label: 'ATM', online: true }
        ]
      }
    }
  },

  // status: 基地状态摘要
  status: {
    msg_id: 'mock-cmd-status',
    type: 'command_response',
    ts_tick: 0,
    payload: {
      output_segments: [
        { text: '═══ 赫拉克勒斯-7号基地 状态报告 ═══\n', protected: true, tag: 'command_response' },
        { text: `Sol 1  火星时间 08:00  基地完整度 78%\n`, protected: true, tag: 'command_response' },
        { text: '───────────────────────────\n', protected: false, tag: 'command_response' },
        { text: '氧气  78%  电力  85%  水  65%  食物  90%\n', protected: true, tag: 'command_response' },
        { text: '───────────────────────────\n', protected: false, tag: 'command_response' },
        { text: '在岗人员 6/6  信号质量 62%  警报 0\n', protected: true, tag: 'command_response' },
        { text: '───────────────────────────\n', protected: false, tag: 'command_response' },
        { text: '当前任务：评估基地损害\n', protected: false, tag: 'command_response' }
      ],
      data: {
        sol: 1,
        mars_time: '08:00',
        integrity: 0.78,
        resources: {
          oxygen: { current: 78, max: 100 },
          power: { current: 85, max: 100 },
          water: { current: 65, max: 100 },
          food: { current: 90, max: 100 }
        },
        agent_count: 6,
        signal_quality_pct: 62,
        alert_count: 0
      }
    }
  },

  // talk <name>: 触发 NPC 对话（返回 agent_message）
  // 使用 buildAgentMessage 动态构造，见 client.js mock 处理
};

// === context_summary mock 生成器（模拟锐锋后端压缩中间件输出） ===
// 随着对话轮次递增 history_count，达到 k_limit 后触发压缩 → compressed_count 增长
function genContextSummary(mode) {
  const kMap = { reflexive: 0, deliberate: 6, deep: 10 };
  const k = kMap[mode] || 6;
  // 模拟递增的上下文（每次调用取当前 mockRound）
  const round = (typeof globalThis !== 'undefined' && globalThis._mockRound) || 1;
  const history = Math.min(round * 2, k + 4); // 超过 k 后开始压缩
  const compressed = history > k ? Math.floor((history - k) / 2) * 2 : 0;
  return {
    history_count: history,
    k_limit: k,
    compressed_count: compressed,
    mode: mode
  };
}

// === 工具函数：生成 mock msg_id ===
function genMockMsgId() {
  return 'mock-' + Math.random().toString(36).slice(2, 10);
}

// === 工具函数：构造 agent_message（用于自然语言响应） ===
function buildAgentMessage(senderId, senderLabel, segments, sqPct, latencyMs, emotion) {
  return {
    msg_id: genMockMsgId(),
    type: 'agent_message',
    ts_tick: Math.floor(Date.now() / 1000),
    payload: {
      sender_id: senderId,
      sender_label: senderLabel,
      segments,
      signal_quality_pct: sqPct,
      latency_ms: latencyMs,
      emotion_hint: emotion || null
    }
  };
}

// === Mock followup_option（Case 1 B 方案 · 二级选项）===
// 数据源：云逸 2026-08-03 群聊拍板的接口结构
// 触发场景：B3_opt3 一级选项被选后，调度器不立即 leads_to，
//          而是推 followup_option 给前端，玩家二次选择后再走 effects → leads_to
const MOCK_FOLLOWUP_DATA = {
  source: 'athena',  // 雅典娜建议，紫色色条
  prompt: '雅典娜建议立即更换通信阵列主控模块（消耗备用件 +3，但可缩短工期 2 Sol）。你接受还是拒绝？',
  options: [
    {
      option_id: 'B3_opt3a_accept_athena',
      label: '接受建议（缩短工期，消耗备用件）',
      risk: '备用件库存将进一步紧张',
      recommended: true,
      effects: {
        state_set: { comm_array_main_status: 'repairing', parts_available: -3, repair_eta_sol: -2 },
        trust_delta: { aisha: +2, viktor: -2, chen_hao: +1 }
      }
    },
    {
      option_id: 'B3_opt3b_reject_athena',
      label: '拒绝建议（按原计划 5 Sol 工期推进）',
      effects: {
        state_set: { comm_array_main_status: 'repairing' },
        trust_delta: { aisha: 0, viktor: +1, chen_hao: 0 }
      }
    }
  ],
  signal_quality: 65
};

// === 工具函数：构造 followup_option 消息信封 ===
// 对齐 option_result payload.followup 字段（云逸 v1.2 §11）
function buildFollowupMessage(followupData, sqPct) {
  return {
    msg_id: genMockMsgId(),
    type: 'option_result',
    ts_tick: Math.floor(Date.now() / 1000),
    payload: {
      effects_summary: '一级选项已执行，等待跟进决断',
      state_update: [],
      leads_to: null,
      followup: followupData || MOCK_FOLLOWUP_DATA,
      signal_quality_pct: sqPct || 65
    }
  };
}

// === v1.3 §13 story_event mock（含 bound_npcs / sol / options[].risk / ending_determination）===
const MOCK_V13_STORY_EVENT = {
  event_id: 'ev_B3_oxygen_crisis_decision',
  chapter_id: 'chapter_2',
  node_index: 7,
  branch: 'B',
  sol: 42,
  narrative_segments: [
    { content: '基地氧气循环系统主控模块故障，当前储备氧气仅够维持 72 小时。', protected: true },
    { content: '维克托建议立即拆解 MOXIE-2 备用件进行更换，但艾莎担心备用件库存已不足。', protected: true },
    { content: '空气里弥漫着淡淡的铁锈味，每个人都屏住了呼吸。', protected: false }
  ],
  bound_npcs: {
    primary: 'viktor',
    emotional_focus: 'aisha',
    advocates: ['viktor', 'marcus'],
    skeptic: 'aisha',
    advisor: 'athena'
  },
  options: [
    {
      option_id: 'B3_opt1_repair_moxie',
      label: '立即拆解 MOXIE-2 备用件更换主控模块',
      risk: '备用件库存降至临界水平（剩余 2 单位）'
    },
    {
      option_id: 'B3_opt2_emergency_rationing',
      label: '启动紧急氧气配给方案，全员减少活动',
      risk: '士气大幅下降，工作效率降低 48 小时'
    },
    {
      option_id: 'B3_opt3_athena_protocol',
      label: '请求雅典娜计算最优修复路径'
    }
  ],
  ending_determination: null,
  signal_quality_pct: 78,
  latency_ms: 100
};

// === v1.3 §13.3 终局节点 story_event mock（含 ending_determination）===
const MOCK_V13_ENDING_EVENT = {
  event_id: 'ev_final_signal_decode',
  chapter_id: 'chapter_3',
  node_index: 15,
  branch: 'D',
  sol: 98,
  narrative_segments: [
    { content: '信号完全解码。地面控制中心确认救援船已在轨道，但只能接载 4 人。', protected: true }
  ],
  bound_npcs: { all_crew: true },
  options: [
    {
      option_id: 'D15_opt1_draw_lots',
      label: '全员抽签决定登船顺序',
      risk: '可能导致团队分裂'
    },
    {
      option_id: 'D15_opt2_mission_critical',
      label: '按任务关键性排序（陈昊+维克托+艾莎+马库斯）',
      risk: '林若曦和索菲亚将被留下'
    }
  ],
  ending_determination: [
    { ending: 'ENDING_A', description: '全员获救', condition: 'branch_progress.D >= 3 且 oxygen > 20%' },
    { ending: 'ENDING_B', description: '部分牺牲', condition: 'branch_progress.D >= 2' },
    { ending: 'ENDING_C', description: '信号中断', condition: 'signal_quality < 30%' }
  ],
  signal_quality_pct: 85,
  latency_ms: 90
};

// === v1.3 §14 option_result mock（含 effects 原始结构 + ending）===
const MOCK_V13_OPTION_RESULT = {
  event_id: 'ev_final_signal_decode',
  selected_option_id: 'D15_opt2_mission_critical',
  effects_summary: '按任务关键性排序登船名单已确认。救援船将在 6 小时后抵达。',
  effects: {
    state_set: { evacuation_list: ['chen_hao','viktor','aisha','marcus'], rescue_eta_hours: 6 },
    trust_delta: { chen_hao: +2, viktor: +1, aisha: 0, marcus: +1, lin_ruoxi: -3, sophia: -2 },
    morale_delta: { lin_ruoxi: -20, sophia: -15, all: -5 },
    resource_delta: { oxygen: -2, power: -1 },
    branch_progress: 'D+1',
    risk: '被留下的成员可能拒绝执行后续指令',
    narrative_flag: { evacuation_decided: true, sacrifice_accepted: true }
  },
  state_update: null,
  ending: {
    ending_id: 'ENDING_B',
    description: '部分牺牲'
  },
  leads_to: null
};

// === v1.3 §15 sol_advance mock（含 chapter_changed / chapter_name）===
const MOCK_V13_SOL_ADVANCE = {
  sol: 43,
  delta: 1,
  chapter_changed: false,
  chapter_name: null
};

// === v1.3 §15 sol_advance mock（章节切换）===
const MOCK_V13_CHAPTER_CHANGE = {
  sol: 50,
  delta: 7,
  chapter_changed: true,
  chapter_name: '第二章 · 风暴前夜'
};

