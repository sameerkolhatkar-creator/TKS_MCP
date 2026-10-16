#!/usr/bin/env python3
"""PET Check MCP Server entry point."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(config_path: str) -> logging.Logger:
    log_level = "INFO"
    log_file = None
    max_size_mb = 10
    backup_count = 5

    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            config = json.load(handle)
            logging_config = config.get("logging", {})
            log_level = logging_config.get("level", "INFO")
            log_file = logging_config.get("file")
            max_size_mb = logging_config.get("max_size_mb", 10)
            backup_count = logging_config.get("backup_count", 5)
    except Exception:
        pass

    level = getattr(logging, log_level.upper(), logging.INFO)
    handlers = [logging.StreamHandler(sys.stderr)]

    if log_file:
        config_dir = Path(config_path).resolve().parent
        log_path = Path(log_file)
        if not log_path.is_absolute():
            log_path = config_dir / log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            str(log_path),
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding="utf-8",
        )
        handlers.append(file_handler)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for handler in handlers:
        handler.setLevel(level)
        if not handler.formatter:
            handler.setFormatter(
                logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            )
        root_logger.addHandler(handler)

    return logging.getLogger(__name__)


def resolve_config_path() -> str:
    env_path = os.environ.get("UNIX_CONFIG_FILE")
    if env_path:
        return env_path
    unix_default = (
        Path(__file__).resolve().parents[1]
        / "unix-mcp-server-main"
        / "config.json"
    )
    return str(unix_default)


async def main(config_path: str, logger: logging.Logger):
    server = None
    try:
        from pet_check import PetCheckMCPServer

        server = PetCheckMCPServer(config_path)
        await server.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        if server and not server._shutting_down:
            await server.shutdown()
    except Exception as exc:
        logger.error("Server error: %s", exc)
        import traceback

        logger.error(traceback.format_exc())
        if server and not server._shutting_down:
            try:
                await server.shutdown(drain_timeout=5.0)
            except Exception:
                pass
        sys.exit(1)


if __name__ == "__main__":
    config_path = resolve_config_path()
    logger = setup_logging(config_path)
    logger.info("PET Check MCP using config: %s", config_path)
    try:
        asyncio.run(main(config_path, logger))
    except KeyboardInterrupt:
        logger.info("Server shutdown complete.")
