"""
EngineCore：引擎核心统一 API

将 GameState + EventScheduler + GameLoop + 各注册表包装为统一的 EngineCore，
提供 init(theme) / tick() / handle_meta() / handle_option_select() 单一入口。

设计原则：
- 渐进式迁移：EngineCore 作为 wrapper 包装现有 GameLoop，不破坏原 API
- 题材无关：所有题材特定数据通过 theme bundle 注入，引擎核心不含硬编码
- 注册表聚合：EndingRegistry / CommandRegistry / PersonaRegistry / StateSchema 统一管理

作者：锐锋-核心开发工程师  日期：2026-08-09
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from ..game_state import GameState, create_initial_game_state
from ..event_scheduler import EventScheduler
from ..game_loop import GameLoop
from .ending_registry import EndingRegistry, create_default_ending_registry
from .command_registry import CommandRegistry
from .persona_registry import PersonaRegistry, create_default_persona_registry
from .state_schema import StateSchema, ResourceSchema, NpcSchema
from .data_loader import DataLoader, ThemeBundle

logger = logging.getLogger(__name__)


class EngineCore:
    """引擎核心

    用法（典型流程）：
        # 1. 加载题材包
        loader = DataLoader()
        bundle = loader.load_theme("dict/theme_mars_base")

        # 2. 初始化引擎
        engine = EngineCore()
        engine.load_theme(bundle)
        engine.init(start_stage="survival")

        # 3. 运行游戏
        msgs = engine.tick("陈昊，氧气还能撑多久？", agent_id="chen_hao")
        msg = engine.handle_meta("sol", [])

    也可不加载题材包，直接用默认注册表（向后兼容）：
        engine = EngineCore()
        engine.init()  # 使用默认火星基地题材
    """

    def __init__(self) -> None:
        # 注册表
        self.ending_registry: EndingRegistry = EndingRegistry()
        self.command_registry: CommandRegistry = CommandRegistry()
        self.persona_registry: PersonaRegistry = PersonaRegistry()
        self.state_schema: StateSchema = StateSchema()
        self.resource_schema: ResourceSchema = ResourceSchema()
        self.npc_schema: NpcSchema = NpcSchema()
        self.data_loader: DataLoader = DataLoader()

        # 运行时组件
        self.game_state: Optional[GameState] = None
        self.scheduler: Optional[EventScheduler] = None
        self.game_loop: Optional[GameLoop] = None
        self.chat_fn: Optional[Callable] = None

        # 题材包
        self.theme_bundle: Optional[ThemeBundle] = None
        self._initialized = False

    # --------------------------------------------------------
    # 题材包加载
    # --------------------------------------------------------

    def load_theme(self, bundle: ThemeBundle) -> None:
        """从 ThemeBundle 加载注册表

        将题材包 config.yaml 中的 endings / commands / state_schema / resources
        注册到对应注册表。人格模板从 NPC YAML 加载。
        """
        self.theme_bundle = bundle

        if bundle.errors:
            logger.warning(f"题材包 {bundle.theme_id} 有 {len(bundle.errors)} 个错误，继续加载但可能不完整")

        config = bundle.config or {}

        # 1. 结局注册表
        endings = config.get("endings", [])
        if endings:
            self.ending_registry.register_from_list(endings)
            logger.info(f"题材包注册 {len(endings)} 个结局")

        # 2. 命令注册表（仅记录元数据，handler 由 bind_command_handlers 绑定）
        commands = config.get("commands", [])
        if commands:
            self.command_registry.register_from_list(commands)
            logger.info(f"题材包注册 {len(commands)} 个命令（待绑定 handler）")

        # 3. 状态字段 schema
        state_fields = config.get("state_schema", {}).get("fields", [])
        if state_fields:
            self.state_schema.register_from_list(state_fields)
            logger.info(f"题材包注册 {len(state_fields)} 个状态字段")

        # 4. 资源 schema
        resources = config.get("resources", [])
        if resources:
            self.resource_schema.register_from_list(resources)
            logger.info(f"题材包注册 {len(resources)} 个资源")

        # 5. 人格模板 + NPC schema（从 NPC YAML 加载）
        if bundle.npcs_dir:
            npc_ids = self.data_loader.list_npcs_from(bundle.npcs_dir)
            for npc_id in npc_ids:
                npc_data = self.data_loader.load_npc_from(bundle.npcs_dir, npc_id)
                if npc_data:
                    self.persona_registry.register_from_yaml(npc_id, npc_data)
                    self.npc_schema.register_from_yaml(npc_id, npc_data)
            logger.info(f"题材包加载 {len(npc_ids)} 个 NPC（人格模板 + 初始状态 schema）")

    def load_default_theme(self) -> None:
        """加载默认题材（火星基地，向后兼容）

        不依赖题材包文件，直接用硬编码的默认注册表。
        """
        self.ending_registry = create_default_ending_registry()
        self.persona_registry = create_default_persona_registry()
        logger.info("已加载默认火星基地题材（硬编码）")

    def bind_command_handlers(self, resolver: Callable[[str], Callable]) -> None:
        """绑定命令 handler（将题材包中的字符串 handler 名解析为实际函数）

        Args:
            resolver: handler_name → handler 函数 的解析器
        """
        self.command_registry.bind_handlers(resolver)

    # --------------------------------------------------------
    # 初始化与启动
    # --------------------------------------------------------

    def init(
        self,
        start_stage: str = "survival",
        chat_fn: Optional[Callable] = None,
        use_default_theme: bool = False,
    ) -> None:
        """初始化引擎运行时

        Args:
            start_stage: 起始章节 ID
            chat_fn: Agent.chat 回调（由 ws_adapter 注入）
            use_default_theme: True 则强制使用默认题材（忽略已加载的 theme bundle）
        """
        if use_default_theme or self.theme_bundle is None:
            if not self.ending_registry._entries:
                self.load_default_theme()

        # 初始化 GameState（Phase 4：题材包有 NPC schema 时动态创建 NPC）
        if self.npc_schema and len(self.npc_schema) > 0:
            self.game_state = create_initial_game_state(npc_schema=self.npc_schema)
        else:
            self.game_state = create_initial_game_state()

        # 应用题材包状态字段（custom_fields）
        if self.state_schema:
            self.game_state.custom_fields = self.state_schema.init_fields()

        # 应用题材包资源 schema（覆盖默认 resources）
        if self.resource_schema and len(self.resource_schema) > 0:
            new_resources = self.resource_schema.init_resources()
            # 保留既有资源，合并新资源
            for name, rdef in new_resources.items():
                self.game_state.resources[name] = rdef

        # 初始化 EventScheduler
        self.scheduler = EventScheduler(self.game_state)

        # 初始化 GameLoop
        self.chat_fn = chat_fn
        self.game_loop = GameLoop(
            game_state=self.game_state,
            scheduler=self.scheduler,
            chat_fn=chat_fn,
        )

        # 将 EndingRegistry 注入 GameLoop（替换硬编码 _ENDING_TABLE）
        self.game_loop.ending_registry = self.ending_registry

        # 将 PersonaRegistry 注入 GameLoop（供 NPC prompt 渲染）
        self.game_loop.persona_registry = self.persona_registry

        # 将 PersonaRegistry 注入 prompt 模块（供 graph.py 的 get_system_prompt 使用）
        try:
            from ..prompt import set_persona_registry
            set_persona_registry(self.persona_registry)
        except ImportError as e:
            logger.warning(f"无法注入 PersonaRegistry 到 prompt 模块: {e}")

        # 注册默认 meta 命令（向后兼容 game_loop 的硬编码命令）
        self._register_default_commands()

        # 启动
        self.game_loop.start(start_stage)
        self._initialized = True
        logger.info(f"EngineCore 初始化完成: stage={start_stage}, Sol={self.game_state.sol}")

    def _register_default_commands(self) -> None:
        """注册默认 meta 命令（绑定到 GameLoop 的现有 handler 方法）

        GameLoop 的 _cmd_* 方法签名是 (self) 或 (self, args)，需用 lambda 适配
        CommandRegistry 的 handler(loop, args) 签名。
        """
        gl = self.game_loop
        if gl is None:
            return

        # 带 args 参数的命令
        self.command_registry.register(
            "npc", lambda loop, args: loop._cmd_npc(args),
            "切换对话目标", aliases=["talk"])
        self.command_registry.register(
            "mode", lambda loop, args: loop._cmd_mode(args),
            "切换响应模式")

        # 不带 args 的命令
        self.command_registry.register(
            "sol", lambda loop, args: loop._cmd_advance_sol(),
            "推进一个 Sol（触发事件检查 + 资源衰减）")
        self.command_registry.register(
            "state", lambda loop, args: loop._cmd_state(),
            "查看基地与成员状态")
        self.command_registry.register(
            "branch", lambda loop, args: loop._cmd_branch(),
            "查看章节进度与触发器")
        self.command_registry.register(
            "skip", lambda loop, args: loop._cmd_skip(),
            "跳过所有待处理事件")
        self.command_registry.register(
            "restart", lambda loop, args: loop._cmd_restart(),
            "重置游戏")
        self.command_registry.register(
            "help", lambda loop, args: loop._cmd_help(),
            "显示此帮助", aliases=["?"])

    # --------------------------------------------------------
    # 运行时 API
    # --------------------------------------------------------

    def tick(
        self,
        player_input: str,
        agent_id: Optional[str] = None,
        response_mode: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """处理一回合玩家自然语言输入"""
        self._ensure_initialized()
        return self.game_loop.tick(player_input, agent_id, response_mode)

    def handle_meta(self, command: str, args: List[str]) -> Dict[str, Any]:
        """处理 meta 命令

        优先走 CommandRegistry（题材包可扩展），未注册的命令回退到 GameLoop.handle_meta。
        """
        self._ensure_initialized()

        # 结局后只允许 restart / help
        if self.game_loop.ending is not None and command not in ("restart", "help", "?"):
            from ..protocol import build_command_response, seg
            return build_command_response(
                [seg("游戏已结束。输入 :restart 重新开始。\n")], None
            )

        # 优先走注册表
        if self.command_registry.has(command):
            return self.command_registry.dispatch(self.game_loop, command, args)

        # 回退到 GameLoop 默认（含未知命令提示）
        return self.game_loop.handle_meta(command, args)

    def handle_option_select(
        self,
        event_id: str,
        option_id: str,
        followup_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """处理玩家选项选择"""
        self._ensure_initialized()
        return self.game_loop.handle_option_select(event_id, option_id, followup_id)

    def restart(self, stage_id: str = "survival") -> None:
        """重置游戏"""
        self._ensure_initialized()
        self.game_loop._cmd_restart()

    # --------------------------------------------------------
    # 状态查询
    # --------------------------------------------------------

    def get_state_snapshot(self) -> Dict[str, Any]:
        """获取当前游戏状态快照（供 session_init.world_snapshot 使用）"""
        self._ensure_initialized()
        gs = self.game_state
        return {
            "sol": gs.sol,
            "stage_id": self.scheduler.chapter.stage_id,
            "signal_quality": gs.signal_quality,
            "athena_status": gs.athena_status,
            "resources": {k: v.get("current", 0) for k, v in gs.resources.items()},
            "npcs": {
                nid: {
                    "stress": ns.stress,
                    "morale": ns.morale,
                    "trust": ns.trust_in_player,
                    "energy": ns.energy,
                    "current_state": ns.current_state,
                }
                for nid, ns in gs.npc_states.items()
            },
            "active_npc": self.game_loop.active_npc,
            "response_mode": self.game_loop.response_mode,
            "ending": self.game_loop.ending,
        }

    def get_npc_list(self) -> List[Dict[str, Any]]:
        """获取 NPC 列表（供前端动态渲染）"""
        self._ensure_initialized()
        result = []
        for nid, ns in self.game_state.npc_states.items():
            result.append({
                "npc_id": nid,
                "stress": ns.stress,
                "morale": ns.morale,
                "current_state": ns.current_state,
            })
        return result

    def get_theme_meta(self) -> Dict[str, Any]:
        """获取主题元信息（供 session_init.world_snapshot 动态渲染）

        返回主题 ID / 名称 / 引擎版本 / 资源 schema / 状态字段 schema 等，
        前端可据此动态渲染 UI（资源条、状态字段标签、主题色等）。
        """
        bundle = self.theme_bundle
        if bundle is None:
            return {
                "theme_id": "default",
                "theme_name": "默认题材",
                "engine_version": "",
                "has_bundle": False,
            }
        return {
            "theme_id": bundle.theme_id,
            "theme_name": bundle.theme_name,
            "engine_version": bundle.engine_version,
            "has_bundle": True,
            "resource_schema": self.resource_schema.list_resources(),
            "state_fields": self.state_schema.list_fields(),
            "npc_schema": self.npc_schema.list_npcs(),
            "endings": [
                {
                    "id": e.ending_id,
                    "display_name": e.display_name,
                    "priority": e.priority,
                }
                for e in self.ending_registry._entries
            ],
            "commands": [
                {
                    "name": c.name,
                    "help_text": c.help_text,
                    "aliases": c.aliases,
                }
                for c in self.command_registry._entries.values()
            ],
            "npcs": self.persona_registry.list_personas(),
        }

    # --------------------------------------------------------
    # 内部工具
    # --------------------------------------------------------

    def _ensure_initialized(self) -> None:
        if not self._initialized or self.game_loop is None:
            raise RuntimeError("EngineCore 未初始化，请先调用 init()")

    @property
    def is_initialized(self) -> bool:
        return self._initialized
