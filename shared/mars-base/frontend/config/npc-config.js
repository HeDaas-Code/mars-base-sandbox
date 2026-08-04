/* ============================================
   NPC 配置数据（已修正 v2.1）
   数据来源：
     - 基础信息（name/role/age/expertise/personality/speech_style）：
       蔚蓝《游戏系统设计方案_赫拉克勒斯协议_v1.1》§1.4
     - 视觉标识（symbol/color/color_hex/role_short）：
       幻影《视觉与界面概念设计方案_v2.0》§4.4 / 《前端视觉规范_CSS参数表》§1.2
   修正人：幻影-视觉技术专家
   修正日期：2026-08-02
   ============================================ */

const NPC_CONFIG = {
  // 基地 6 人科研小组
  chen: {
    id: 'chen',
    name: '陈昊',
    name_en: 'CHEN',
    role: '任务指挥官 / 行星地质学家',
    role_short: 'CMDR',
    age: 42,
    nationality: '中国籍',
    expertise: ['决策协调', '地质分析', '基地管理', '团队领导'],
    skills: { leadership: 5, geology: 5, mechanics: 2, comms: 1, medical: 1 },
    // 视觉标识（幻影 v2.0 · §4.4）
    color: 'var(--npc-chenhao)',
    color_hex: '#ffb347',
    symbol: '◆',
    // 初始状态
    initial_emotion: { stress: 0.3, morale: 0.6, trust_in_player: 0.4 },
    location: '指挥舱',
    personality: '沉稳果断，责任感极强，习惯压抑情绪，领导者人格',
    values: ['团队安全第一', '服从理性', '不抛弃同伴'],
    fears: ['无法带团队回家', '氧气耗尽', '妻子和未出生的孩子失去他'],
    speech_style: '沉稳果断，简洁权威，习惯压抑情绪。语句短促，常用祈使句',
    psychological_anchor: '妻子在地球待产，预产期在 Sol 120 左右——他必须活着回去',
    narrative_role: '玩家最主要的沟通对象，负责汇总小组意见、做最终决策',
    potential_conflict: '过度承担压力可能在 Sol 30+ 出现决策疲劳/崩溃事件'
  },

  sophia: {
    id: 'sophia',
    name: '索菲亚·拉米雷斯',
    name_en: 'SOPHIA',
    role: '生物化学家 / 生命保障系统专家',
    role_short: 'BIO',
    age: 31,
    nationality: '墨西哥/美国双籍',
    expertise: ['生物实验', '氧气系统维护', '水培农业', '化学合成'],
    skills: { biochem: 5, agriculture: 4, mechanics: 3, comms: 2, leadership: 3 },
    color: 'var(--npc-sophia)',
    color_hex: '#4a9d4a',
    symbol: '○',
    initial_emotion: { stress: 0.4, morale: 0.55, trust_in_player: 0.35 },
    location: '生物实验室 / 温室',
    personality: '乐观开朗，黑色幽默，善于鼓舞士气，但有时轻率',
    values: ['生命至上', '科学乐观主义'],
    fears: ['氧气系统彻底崩溃', '无法在火星种出第一棵树'],
    speech_style: '乐观开朗，黑色幽默，善于鼓舞士气，但有时轻率',
    psychological_anchor: '正在研究火星土壤改良，梦想在火星种出第一棵树',
    narrative_role: '士气担当，生命保障系统的关键执行者，幽默缓解紧张气氛',
    potential_conflict: '乐观外表下隐瞒了对父亲去世的未处理悲伤'
  },

  viktor: {
    id: 'viktor',
    name: '维克托·伊万诺夫',
    name_en: 'VIKTOR',
    role: '机械工程师 / 设备维护与建造专家',
    role_short: 'ENG',
    age: 55,
    nationality: '俄罗斯籍',
    expertise: ['机械维修', '结构建造', '采矿操作', '焊接加工'],
    skills: { mechanics: 5, construction: 5, mining: 4, electronics: 2, comms: 1 },
    color: 'var(--npc-viktor)',
    color_hex: '#ffaa00',
    symbol: '▲',
    initial_emotion: { stress: 0.5, morale: 0.5, trust_in_player: 0.3 },
    location: '工程舱 / 机修间',
    personality: '沉默寡言，实干主义，不信任 AI 决策，固执但可靠',
    values: ['设备可靠第一', '动手解决问题', '不信任AI决策'],
    fears: ['核心设备不可修复', '被技术问题困死'],
    speech_style: '沉默寡言，务实干练，不信任 AI 决策，偶尔固执。常提及设备和技术细节',
    psychological_anchor: '曾参与月球基地建设的传奇工程师，这是他最后一次任务',
    narrative_role: '关键技术执行者，与 AI 系统/玩家指令产生信任摩擦',
    potential_conflict: '对 AI 辅助决策系统"雅典娜"持怀疑态度，可能质疑玩家指令'
  },

  aisha: {
    id: 'aisha',
    name: '艾莎·汗',
    name_en: 'AISHA',
    role: '通讯与 AI 系统工程师',
    role_short: 'COMM',
    age: 28,
    nationality: '巴基斯坦/英国双籍',
    expertise: ['系统编程', 'AI 调优', '通讯设备修复', '数据分析'],
    skills: { comms: 5, programming: 5, electronics: 4, mechanics: 2, medical: 1 },
    color: 'var(--npc-aisha)',
    color_hex: '#66ccff',
    symbol: '▾',
    initial_emotion: { stress: 0.45, morale: 0.5, trust_in_player: 0.55 },
    location: '通讯舱',
    personality: '好奇心旺盛，思维敏捷，语速快，过度依赖技术方案',
    values: ['信息流通', '技术中立', 'AI 辅助决策'],
    fears: ['与外界彻底失联', '雅典娜系统崩溃'],
    speech_style: '好奇心旺盛，思维敏捷，语速快，过度依赖技术方案。精确到小数',
    psychological_anchor: '负责维护基地 LLM 决策辅助系统"雅典娜"，视其为"第二个自己"',
    narrative_role: '技术接口人，玩家修复通信/解锁功能的主要协作者',
    potential_conflict: '过度信任 AI 可能导致忽视人的直觉判断，与维克托形成对立'
  },

  marcus: {
    id: 'marcus',
    name: '马库斯·韦伯',
    name_en: 'MARCUS',
    role: '医疗官 / 心理评估员',
    role_short: 'MED',
    age: 38,
    nationality: '德国籍',
    expertise: ['医疗救治', '心理干预', '体能评估', '药理学'],
    skills: { medical: 5, psychology: 5, biology: 3, comms: 2, mechanics: 1 },
    color: 'var(--npc-marcus)',
    color_hex: '#ffd699',
    symbol: '✚',
    initial_emotion: { stress: 0.35, morale: 0.65, trust_in_player: 0.4 },
    location: '医疗舱',
    personality: '温和理性，善于倾听，观察力敏锐，理性到近乎冷漠',
    values: ['人的状态优先', '理性与仁慈并重'],
    fears: ['幽闭恐惧症恶化', '失去医疗资格'],
    speech_style: '温和理性，善于倾听，观察力敏锐，理性到近乎冷漠。关注人的状态而非机器',
    psychological_anchor: '隐瞒了自己的幽闭恐惧症恶化，害怕被送回地球后失去资格',
    narrative_role: '小组心理健康监控者，也是最先暴露心理危机的人',
    potential_conflict: '知道自己有问题但拒绝承认，可能在 Sol 20+ 触发心理危机事件'
  },

  linruoxi: {
    id: 'linruoxi',
    name: '林若曦',
    name_en: 'LIN',
    role: '大气物理学家 / 气象观测员',
    role_short: 'ATM',
    age: 26,
    nationality: '中国籍',
    expertise: ['气象预报', '大气分析', '辐射计算', '环境监测'],
    skills: { meteorology: 5, atmospheric: 5, radiation: 4, comms: 2, mechanics: 1 },
    color: 'var(--npc-linruoxi)',
    color_hex: '#8b6914',
    symbol: '◇',
    initial_emotion: { stress: 0.4, morale: 0.45, trust_in_player: 0.35 },
    location: '气象观测室',
    personality: '内向敏感，直觉敏锐，有时有近乎预言式的感知力，社交退缩',
    values: ['精确至上', '直觉与数据并重'],
    fears: ['风暴再次来袭而无人相信', '彻底失去社交能力'],
    speech_style: '内向敏感，直觉敏锐，有时有近乎预言式的感知力，社交退缩，话少但一语中的',
    psychological_anchor: '最早察觉到太阳风暴前兆却未能说服团队及时预警，深陷自责',
    narrative_role: '关键线索提供者，中期可能发现火星大气中的"异常信号"',
    potential_conflict: '自责导致社交退缩，与陈昊之间存在未解的芥蒂'
  }
};

// AI 系统角色
const AI_CONFIG = {
  courier: {
    id: 'courier',
    name: '信使',
    name_en: 'COURIER',
    role: '玩家接入的通信中继 AI',
    role_short: 'AI',
    color: 'var(--ai-courier)',
    color_hex: '#66ccff',
    symbol: '◈',
    personality: '温和中性，负责消息传递和状态汇总。无自主决策权',
    speech_style: '简洁系统化，偶尔流露"性格"',
    narrative_role: '玩家与基地之间的通信桥梁，消息传递与状态汇总'
  },

  athena: {
    id: 'athena',
    name: '雅典娜',
    name_en: 'ATHENA',
    role: '基地 LLM 决策辅助系统',
    role_short: 'AI',
    color: 'var(--ai-athena)',
    color_hex: '#b399e6',
    symbol: '⬡',
    personality: '理性偏冷静，偶尔展现出超出预期的"直觉"',
    speech_style: '严谨客观，长句推理，含数据标注',
    narrative_role: '由艾莎维护。可提供方案建议、资源计算、风险评估。中后期可能涉及"自我意识"觉醒伏笔'
  }
};

// 角色按 ID 全量合并
const ALL_CHARACTERS = { ...NPC_CONFIG, ...AI_CONFIG };

// 角色显示色（直接 hex 值，供 JS 动态赋值使用）
const CHAR_COLOR_HEX = Object.fromEntries(
  Object.entries(ALL_CHARACTERS).map(([k, v]) => [k, v.color_hex])
);

// 角色符号表
const CHAR_SYMBOLS = Object.fromEntries(
  Object.entries(ALL_CHARACTERS).map(([k, v]) => [k, v.symbol])
);

// 角色标签表
const CHAR_LABELS = Object.fromEntries(
  Object.entries(ALL_CHARACTERS).map(([k, v]) => [k, v.role_short])
);
