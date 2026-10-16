"""WebLogic server operations on CM hosts."""

from __future__ import annotations

import re
from typing import Any, Optional

from ..constants import (
    CM_TYPE_SUFFIX,
    CM_WL_BY_MACHINE,
    CM_WL_INSTANCES,
    WL_SCRIPTS_DIR,
    WL_SERVER_CACHE_DIR,
)


def normalize_cm_type(cm_type: str) -> str:
    key = cm_type.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "preaid": "prepaid",
        "pospaid": "postpaid",
        "internalapi": "internal_api",
        "collectionscanner": "collection_scanner",
        "cm_webservices": "webservices",
        "cm_prepaid": "prepaid",
        "cm_postpaid": "postpaid",
        "cm_internal_api": "internal_api",
        "lockserver": "lock_server",
        "lock": "lock_server",
        "cm_lock_server": "lock_server",
    }
    key = aliases.get(key, key)
    if key not in CM_TYPE_SUFFIX:
        valid = ", ".join(sorted(CM_TYPE_SUFFIX))
        raise ValueError(f"Invalid cm_type '{cm_type}'. Valid types: {valid}")
    return key


def build_cm_machine_name(cm_server: str, cm_type: Optional[str] = None) -> str:
    name = cm_server.strip()
    if re.match(r"^CM\d+-Server_", name, re.IGNORECASE):
        return name

    match = re.match(r"^(CM\d+)$", name, re.IGNORECASE)
    if match:
        if not cm_type:
            raise ValueError("cm_type is required when cm_server is a CM number (e.g. CM31)")
        suffix = CM_TYPE_SUFFIX[normalize_cm_type(cm_type)]
        return f"{match.group(1).upper()}-{suffix}"

    if cm_type and not name.upper().startswith("CM"):
        suffix = CM_TYPE_SUFFIX[normalize_cm_type(cm_type)]
        return f"{name}-{suffix}"

    return name


def get_cm_wl_instance(machine_name: str) -> Optional[dict[str, str]]:
    """Return CM WL definition (machine_name, user, host, cm_type) or None."""
    return CM_WL_BY_MACHINE.get(machine_name)


def list_cm_wl_instances(cm_type: Optional[str] = None) -> list[dict[str, str]]:
    """Return CM WL definitions, optionally filtered by cm_type."""
    if not cm_type:
        return list(CM_WL_INSTANCES)
    normalized = normalize_cm_type(cm_type)
    return [item for item in CM_WL_INSTANCES if item["cm_type"] == normalized]


def format_user_at_host(instance: dict[str, str]) -> str:
    return f"{instance['user']}@{instance['host']}"


def build_weblogic_commands(action: str, clean_cache: bool = False) -> list[str]:
    scripts = WL_SCRIPTS_DIR
    cache_dir = WL_SERVER_CACHE_DIR

    if action == "check":
        return [f"cd {scripts} && ./ping-Server.sh"]

    if action == "stop":
        return [f"cd {scripts} && ./forceStop-Server.sh"]

    if action == "start":
        commands = []
        if clean_cache:
            commands.append(
                f"rm -rf {cache_dir}/stage {cache_dir}/cache {cache_dir}/tmp"
            )
        commands.append(f"cd {scripts} && ./start-Server.sh")
        return commands

    if action == "restart":
        commands = [f"cd {scripts} && ./forceStop-Server.sh"]
        if clean_cache:
            commands.append(
                f"rm -rf {cache_dir}/stage {cache_dir}/cache {cache_dir}/tmp"
            )
        commands.append(f"cd {scripts} && ./start-Server.sh")
        return commands

    raise ValueError(f"Unsupported action: {action}")


async def run_weblogic_action(
    executor,
    machine_name: str,
    action: str,
    clean_cache: bool = False,
    command_timeout: int = 600,
) -> list[dict[str, Any]]:
    commands = build_weblogic_commands(action, clean_cache)
    all_results: list[dict[str, Any]] = []
    for command in commands:
        results = await executor.execute(
            command,
            machine_name,
            command_timeout_override=command_timeout,
        )
        all_results.extend(results)
        if results and not all(r.get("success") for r in results):
            break
    return all_results
