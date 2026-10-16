"""Main AirflowAVMProc MCP Server — reuses unix-server SSH stack."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

_UNIX_SERVER_ROOT = Path(
    os.environ.get(
        "UNIX_MCP_ROOT",
        str(Path.home() / ".cursor" / "mcp-servers" / "mcp_servers" / "unix-mcp-server-main"),
    )
)
if str(_UNIX_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(_UNIX_SERVER_ROOT))

from src.config import load_config  # noqa: E402
from src.connection.manager import PoolManager  # noqa: E402
from src.execution.executor import CommandExecutor  # noqa: E402
from src.logging.audit import AuditLogger  # noqa: E402

from .handlers import ToolHandler, get_tool_definitions

logger = logging.getLogger(__name__)


def _resolve_relative_log_path(config: dict, config_path: Optional[str], section: str, key: str = "file") -> None:
    """Make unix-server log paths absolute vs config.json, and create the directory.

    unix-server CWD is its own folder, so relative `logs/command_audit.log` works there.
    This MCP starts from mcps/AirflowAVMProc, which resolved to %USERPROFILE%\\logs\\ and crashed.
    """
    if not config_path:
        return
    block = config.get(section) or {}
    log_file = block.get(key)
    if not log_file:
        return
    path = Path(log_file)
    if not path.is_absolute():
        path = Path(config_path).resolve().parent / path
    path.parent.mkdir(parents=True, exist_ok=True)
    block[key] = str(path)
    config[section] = block


class AirflowAVMProcServer:
    def __init__(self, config_path: Optional[str] = None):
        self.config = load_config(config_path)
        _resolve_relative_log_path(self.config, config_path, "audit")
        _resolve_relative_log_path(self.config, config_path, "logging")
        self._shutting_down = False
        self._shutdown_event = asyncio.Event()
        max_workers = self.config.get("thread_pool_max_workers", 50)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self.audit_logger = AuditLogger(self.config)
        self.pool_manager = PoolManager(self._executor)
        self.command_executor = CommandExecutor(
            self.config, self.pool_manager, self._executor, self.audit_logger
        )
        self.tool_handler = ToolHandler(self.command_executor, self.config)
        self.server = Server("AirflowAVMProc")
        self._setup_tools()

    def _setup_tools(self):
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return get_tool_definitions()

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            return await self.tool_handler.handle(name, arguments)

    async def shutdown(self, drain_timeout: float | None = None):
        if drain_timeout is None:
            global_timing = self.config.get("timing", {})
            drain_timeout = global_timing.get("shutdown_drain_timeout_seconds", 30.0)
        if self._shutting_down:
            return
        self._shutting_down = True
        self.pool_manager.stop_accepting()
        await self.pool_manager.wait_for_drain(timeout=drain_timeout)
        await self.pool_manager.close_all()
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
        self._shutdown_event.set()

    async def run(self):
        try:
            cleanup_interval = self.config.get("cleanup_interval", 60.0)
            await self.pool_manager.start_cleanup_task(interval=cleanup_interval)
            # Do not pre-warm 140 unix-server pools; JUMP is opened on first AVM command.
            async with stdio_server() as (read_stream, write_stream):
                notification_options = SimpleNamespace()
                notification_options.tools_changed = False
                notification_options.resources_changed = False
                notification_options.prompts_changed = False
                await self.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="AirflowAVMProc",
                        server_version="1.0.0",
                        capabilities=self.server.get_capabilities(
                            notification_options=notification_options,
                            experimental_capabilities={},
                        ),
                    ),
                )
        finally:
            if not self._shutting_down:
                await self.shutdown()
