"""
Meta 命令注册表

将 game_loop.GameLoop.handle_meta 中的硬编码 if-elif 链升级为可注册的
CommandRegistry，支持题材包动态注册自定义 meta 命令。

handler 签名：
    handler(loop: GameLoop, args: List[str]) -> Dict[str, Any]

返回值：command_response 信封（由 protocol.build_command_response 构造）

作者：锐锋-核心开发工程师  日期：2026-08-09
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# handler 类型：接收 GameLoop 实例和参数列表，返回信封字典
CommandHandler = Callable[["Any", List[str]], Dict[str, Any]]


@dataclass
class CommandEntry:
    """命令注册项"""
    name: str                       # 命令名（不含 : 前缀）
    handler: CommandHandler         # 处理函数
    help_text: str = ""             # 帮助文本
    aliases: List[str] = None       # 别名列表

    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []


class CommandRegistry:
    """Meta 命令注册表

    用法：
        reg = CommandRegistry()
        reg.register("sol", _cmd_sol, "推进一个 Sol")
        reg.register("help", _cmd_help, "显示帮助", aliases=["?"])

        msg = reg.dispatch(loop, "sol", [])
    """

    def __init__(self) -> None:
        self._entries: Dict[str, CommandEntry] = {}
        self._alias_to_name: Dict[str, str] = {}

    def register(
        self,
        name: str,
        handler: CommandHandler,
        help_text: str = "",
        aliases: Optional[List[str]] = None,
    ) -> None:
        """注册一个 meta 命令

        Args:
            name: 命令名（不含 : 前缀）
            handler: 处理函数，签名 handler(loop, args) -> dict
            help_text: 帮助文本
            aliases: 命令别名列表
        """
        if name in self._entries:
            logger.debug(f"CommandRegistry 覆盖注册: {name}")
        self._entries[name] = CommandEntry(
            name=name,
            handler=handler,
            help_text=help_text,
            aliases=aliases or [],
        )
        for alias in (aliases or []):
            self._alias_to_name[alias] = name
        logger.debug(f"CommandRegistry 注册: {name} (aliases={aliases or []})")

    def register_from_list(self, commands: List[Dict[str, Any]]) -> None:
        """从列表批量注册（题材包 YAML 结构）

        YAML 格式：
            commands:
              - name: sol
                handler: advance_sol   # 函数名，需通过 handler_resolver 解析
                help: 推进一个 Sol
                aliases: [next]
        注：handler_resolver 由 EngineCore 提供，将字符串名映射到实际函数。
        """
        # 此方法仅记录元数据，实际 handler 绑定由 EngineCore 完成
        self._pending_registers = getattr(self, "_pending_registers", [])
        for cmd in commands or []:
            self._pending_registers.append(cmd)

    def bind_handlers(self, resolver: Callable[[str], CommandHandler]) -> None:
        """将 register_from_list 中暂存的字符串 handler 名解析为实际函数

        Args:
            resolver: 函数名 → handler 函数的解析器（由 EngineCore 提供）
        """
        pending = getattr(self, "_pending_registers", [])
        for cmd in pending:
            handler_name = cmd.get("handler", "")
            handler = resolver(handler_name)
            if handler is None:
                logger.warning(f"CommandRegistry: 无法解析 handler '{handler_name}' for '{cmd.get('name')}'")
                continue
            self.register(
                name=cmd.get("name", ""),
                handler=handler,
                help_text=cmd.get("help", ""),
                aliases=cmd.get("aliases"),
            )
        self._pending_registers = []

    def unregister(self, name: str) -> bool:
        """注销一个命令"""
        if name in self._entries:
            entry = self._entries.pop(name)
            for alias in entry.aliases:
                self._alias_to_name.pop(alias, None)
            return True
        return False

    def dispatch(self, loop: Any, name: str, args: List[str]) -> Optional[Dict[str, Any]]:
        """分发命令到 handler

        Args:
            loop: GameLoop 实例（传给 handler）
            name: 命令名（已去除 : 前缀）
            args: 命令参数

        Returns:
            handler 返回的信封字典，或 None（命令未注册）
        """
        # 别名解析
        canonical = self._alias_to_name.get(name, name)
        entry = self._entries.get(canonical)
        if entry is None:
            return None
        try:
            return entry.handler(loop, args)
        except Exception as e:
            logger.error(f"CommandRegistry dispatch '{name}' 失败: {e}", exc_info=True)
            from ..protocol import build_command_response, seg
            return build_command_response(
                [seg(f"命令执行失败: {name} ({e})\n", protected=True)],
                None,
            )

    def list_commands(self) -> List[Dict[str, Any]]:
        """列出所有已注册命令（用于 :help）"""
        return [
            {
                "name": e.name,
                "help": e.help_text,
                "aliases": e.aliases,
            }
            for e in self._entries.values()
        ]

    def has(self, name: str) -> bool:
        """判断命令是否已注册（含别名）"""
        canonical = self._alias_to_name.get(name, name)
        return canonical in self._entries

    def __len__(self) -> int:
        return len(self._entries)
