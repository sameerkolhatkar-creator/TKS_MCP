"""Main PET Check MCP Server class."""

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

# Reuse unix-server SSH stack (sibling package).
_UNIX_SERVER_ROOT = Path(__file__).resolve().parents[2] / "unix-mcp-server-main"
if str(_UNIX_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(_UNIX_SERVER_ROOT))

from src.config import load_config  # noqa: E402
from src.connection.manager import PoolManager  # noqa: E402
from src.execution.executor import CommandExecutor  # noqa: E402
from src.logging.audit import AuditLogger  # noqa: E402

from .tools.handlers import ToolHandler, get_tool_definitions

logger = logging.getLogger(__name__)


class PetCheckMCPServer:
    """MCP server for PET environment checks and operations."""

    def __init__(self, config_path: Optional[str] = None):
        self.config = load_config(config_path)

        if config_path and self.config.get("audit", {}).get("file"):
            audit_file = self.config["audit"]["file"]
            config_dir = Path(config_path).resolve().parent
            audit_path = Path(audit_file)
            if not audit_path.is_absolute():
                audit_path = config_dir / audit_path
                audit_path.parent.mkdir(parents=True, exist_ok=True)
                self.config["audit"]["file"] = str(audit_path)

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

        self.server = Server("pet-check")
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
            servers = self.config.get("servers", [])
            if servers:
                drain_timeout = servers[0].get("timing", {}).get(
                    "shutdown_drain_timeout_seconds", drain_timeout
                )

        if self._shutting_down:
            return

        self._shutting_down = True
        logger.info("Initiating graceful shutdown...")

        self.pool_manager.stop_accepting()
        await self.pool_manager.wait_for_drain(timeout=drain_timeout)
        await self.pool_manager.close_all()

        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)

        self._shutdown_event.set()
        logger.info("Graceful shutdown complete")

    def request_shutdown(self):
        if not self._shutting_down:
            asyncio.create_task(self.shutdown())

    async def run(self):
        try:
            cleanup_interval = self.config.get("cleanup_interval", 60.0)
            await self.pool_manager.start_cleanup_task(interval=cleanup_interval)
            await self.pool_manager.pre_warm(self.config)

            async with stdio_server() as (read_stream, write_stream):
                notification_options = SimpleNamespace()
                notification_options.tools_changed = False
                notification_options.resources_changed = False
                notification_options.prompts_changed = False

                await self.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="pet-check",
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
