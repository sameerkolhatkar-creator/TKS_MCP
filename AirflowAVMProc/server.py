#!/usr/bin/env python3
"""AirflowAVMProc MCP Server entry point."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def resolve_config_path() -> str:
    env_path = os.environ.get("UNIX_CONFIG_FILE")
    if env_path:
        return env_path
    return str(
        Path.home()
        / ".cursor"
        / "mcp-servers"
        / "mcp_servers"
        / "unix-mcp-server-main"
        / "config.json"
    )


def setup_logging(config_path: str) -> logging.Logger:
    log_level = "INFO"
    log_file = str(Path(__file__).resolve().parent / "logs" / "airflow_avm_proc.log")
    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            config = json.load(handle)
            logging_config = config.get("logging", {})
            log_level = logging_config.get("level", "INFO")
    except Exception:
        pass
    level = getattr(logging, log_level.upper(), logging.INFO)
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    # File only — stderr INFO from unix-server config dump (~140 hosts) breaks Cursor MCP discovery.
    file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = [file_handler]
    return logging.getLogger("AirflowAVMProc")


async def main(config_path: str, logger: logging.Logger):
    from airflow_avm import AirflowAVMProcServer

    server = AirflowAVMProcServer(config_path)
    logger.info("AirflowAVMProc using unix config: %s", config_path)
    await server.run()


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    cfg = resolve_config_path()
    log = setup_logging(cfg)
    try:
        asyncio.run(main(cfg, log))
    except KeyboardInterrupt:
        log.info("Stopped")
    except Exception:
        log.exception("AirflowAVMProc failed to start")
        raise
