"""MCP tool definitions and handlers for PET Check."""

from __future__ import annotations

import logging
from typing import Any

from mcp.types import TextContent, Tool

from ..constants import (
    CM_TYPE_SUFFIX,
    CM_WL_PROPERTIES_GUIDELINES,
    DAEMON_ACTIONS,
    K8S_ACTIONS,
    PET_RT_ADMIN,
    TCK8S_HELM_GUIDELINES,
    TCK8S_NAMESPACE,
    TCMS_NAMESPACE,
    TCMS_PODS_GUIDELINES,
    WL_ACTIONS,
    WL_PROPERTIES_ACTIONS,
    WL_PROPERTIES_DIR,
)
from ..services.daemons import load_daemon_config, run_daemon_action
from ..services.k8s import tck8s_action, tcms_action
from ..services.properties import (
    apply_property_changes,
    list_property_files,
    parse_changes,
    preview_property_changes,
    read_property_file,
)
from ..services.weblogic import (
    build_cm_machine_name,
    format_user_at_host,
    get_cm_wl_instance,
    list_cm_wl_instances,
    normalize_cm_type,
    run_weblogic_action,
)
from .formatters import format_results

logger = logging.getLogger(__name__)

_ACTION_SCHEMA = {
    "type": "string",
    "enum": list(K8S_ACTIONS),
    "description": "Operation: check (status), stop (scale to 0), start (scale up), restart (rollout restart).",
}


def get_tool_definitions() -> list[Tool]:
    cm_types = ", ".join(sorted(CM_TYPE_SUFFIX))
    return [
        Tool(
            name="tck8s_pods",
            description=(
                "Stop, start, restart, or check TCK8S/K8S pods on PET_RT_ADMIN using OCP/kubectl "
                f"in namespace {TCK8S_NAMESPACE}. "
                f"{TCK8S_HELM_GUIDELINES}"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": _ACTION_SCHEMA,
                    "resource_name": {
                        "type": "string",
                        "description": "Deployment, statefulset, or pod name prefix (e.g. cr1, cr1-5g, ela2).",
                    },
                    "replicas": {
                        "type": "integer",
                        "description": "Replica count for start action (default: 1).",
                        "minimum": 0,
                    },
                },
                "required": ["action", "resource_name"],
            },
        ),
        Tool(
            name="tcms_pods",
            description=(
                "Stop, start, restart, or check TCMS pods on PET_RT_ADMIN using OCP/kubectl "
                f"in namespace {TCMS_NAMESPACE}. "
                f"{TCMS_PODS_GUIDELINES}"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": _ACTION_SCHEMA,
                    "resource_name": {
                        "type": "string",
                        "description": "Deployment, statefulset, or pod name prefix (microservice).",
                    },
                    "replicas": {
                        "type": "integer",
                        "description": "Replica count for start action (default: 1).",
                        "minimum": 0,
                    },
                },
                "required": ["action", "resource_name"],
            },
        ),
        Tool(
            name="weblogic_server",
            description=(
                "Stop, start, restart, or check WebLogic (ABP-FULL) on CM servers via unix-server. "
                "Connects to CM*-Server_CM_{Type} hosts. Scripts: start-Server.sh, forceStop-Server.sh, ping-Server.sh."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": list(WL_ACTIONS),
                        "description": "Operation: check, stop, start, restart.",
                    },
                    "machine_name": {
                        "type": "string",
                        "description": "Full unix-server machine name (e.g. CM31-Server_CM_Prepaid).",
                    },
                    "cm_server": {
                        "type": "string",
                        "description": "CM id or full machine name (e.g. CM31). Requires cm_type if not full name.",
                    },
                    "cm_type": {
                        "type": "string",
                        "description": f"CM server type when cm_server is a number. One of: {cm_types}.",
                    },
                    "clean_cache": {
                        "type": "boolean",
                        "description": "For start/restart: delete stage, cache, tmp under ABPServer before starting.",
                        "default": False,
                    },
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="daemon",
            description=(
                "Stop, start, restart, or check a PET daemon using .Op9DmnMonitor.cfg on PET_RT_ADMIN. "
                "Runs SSH to USER@CPU with START_COMMAND/STOP_COMMAND or ps -ef check."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": list(DAEMON_ACTIONS),
                        "description": "Operation: check, stop, start, restart.",
                    },
                    "common_name": {
                        "type": "string",
                        "description": "Daemon COMMON_NAME from .Op9DmnMonitor.cfg.",
                    },
                },
                "required": ["action", "common_name"],
            },
        ),
        Tool(
            name="list_pet_daemons",
            description="List daemon COMMON_NAME entries from .Op9DmnMonitor.cfg on PET_RT_ADMIN.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="list_cm_servers",
            description=(
                "List PET CM WebLogic instances with machine_name, user@host, and cm_type. "
                "Uses pet-check CM_WL_INSTANCES definitions (45 instances)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "cm_type": {
                        "type": "string",
                        "description": f"Optional filter by type: {cm_types}.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="cm_wl_properties",
            description=(
                "List, read, preview, or apply CM WebLogic application property files on CM servers. "
                f"Properties directory: {WL_PROPERTIES_DIR}. "
                f"{CM_WL_PROPERTIES_GUIDELINES} "
                "Workflow: use preview to show per-file diffs, obtain user approval for each file, "
                "then call apply with approved=true (backup is created automatically before write)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": list(WL_PROPERTIES_ACTIONS),
                        "description": (
                            "list: files in properties dir; read: file contents; "
                            "preview: show proposed changes (requires changes); "
                            "apply: backup then write (requires changes and approved=true)."
                        ),
                    },
                    "machine_name": {
                        "type": "string",
                        "description": "Full unix-server machine name (e.g. CM31-Server_CM_Prepaid).",
                    },
                    "cm_server": {
                        "type": "string",
                        "description": "CM id or full machine name (e.g. CM31). Requires cm_type if not full name.",
                    },
                    "cm_type": {
                        "type": "string",
                        "description": f"CM server type when cm_server is a number. One of: {cm_types}.",
                    },
                    "file_name": {
                        "type": "string",
                        "description": "Property file name (required for read, preview, apply).",
                    },
                    "changes": {
                        "type": "array",
                        "description": (
                            "Property updates for preview/apply. Each item: "
                            "{key, value, action?} where action is set (default) or delete."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string"},
                                "value": {"type": "string"},
                                "action": {
                                    "type": "string",
                                    "enum": ["set", "delete"],
                                    "description": "set (default) or delete.",
                                },
                            },
                            "required": ["key"],
                        },
                    },
                    "approved": {
                        "type": "boolean",
                        "description": (
                            "Required for apply. Must be true only after the user has explicitly "
                            "approved the previewed changes for this file."
                        ),
                        "default": False,
                    },
                },
                "required": ["action"],
            },
        ),
    ]


class ToolHandler:
    """Routes pet-check MCP tool calls."""

    def __init__(self, executor, config: dict):
        self.executor = executor
        self.config = config

    async def handle(self, name: str, arguments: dict[str, Any]) -> list[TextContent]:
        try:
            if name == "tck8s_pods":
                return await self._handle_tck8s(arguments)
            if name == "tcms_pods":
                return await self._handle_tcms(arguments)
            if name == "weblogic_server":
                return await self._handle_weblogic(arguments)
            if name == "daemon":
                return await self._handle_daemon(arguments)
            if name == "list_pet_daemons":
                return await self._handle_list_daemons(arguments)
            if name == "list_cm_servers":
                return await self._handle_list_cm_servers(arguments)
            if name == "cm_wl_properties":
                return await self._handle_cm_wl_properties(arguments)
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        except Exception as exc:
            logger.exception("Tool %s failed", name)
            return [TextContent(type="text", text=f"Error: {exc}")]

    async def _handle_tck8s(self, arguments: dict) -> list[TextContent]:
        action = arguments.get("action", "").lower()
        resource_name = arguments.get("resource_name", "")
        replicas = arguments.get("replicas")
        results = await tck8s_action(self.executor, resource_name, action, replicas)
        text = format_results(
            f"TCK8S {action.upper()}: {resource_name}",
            results,
            extra=f"Host: {PET_RT_ADMIN} | Namespace: {TCK8S_NAMESPACE}",
        )
        return [TextContent(type="text", text=text)]

    async def _handle_tcms(self, arguments: dict) -> list[TextContent]:
        action = arguments.get("action", "").lower()
        resource_name = arguments.get("resource_name", "")
        replicas = arguments.get("replicas")
        results = await tcms_action(self.executor, resource_name, action, replicas)
        text = format_results(
            f"TCMS {action.upper()}: {resource_name}",
            results,
            extra=f"Host: {PET_RT_ADMIN} | Namespace: {TCMS_NAMESPACE}",
        )
        return [TextContent(type="text", text=text)]

    async def _handle_weblogic(self, arguments: dict) -> list[TextContent]:
        action = arguments.get("action", "").lower()
        machine_name = arguments.get("machine_name") or arguments.get("cm_server")
        if not machine_name:
            return [TextContent(type="text", text="Error: machine_name or cm_server is required.")]

        cm_type = arguments.get("cm_type")
        if not arguments.get("machine_name"):
            machine_name = build_cm_machine_name(machine_name, cm_type)
        clean_cache = bool(arguments.get("clean_cache", False))

        results = await run_weblogic_action(
            self.executor,
            machine_name,
            action,
            clean_cache=clean_cache,
        )
        instance = get_cm_wl_instance(machine_name)
        target = format_user_at_host(instance) if instance else machine_name
        text = format_results(
            f"WebLogic {action.upper()}: {machine_name}",
            results,
            extra=f"target={target} | clean_cache={clean_cache}",
        )
        return [TextContent(type="text", text=text)]

    async def _handle_daemon(self, arguments: dict) -> list[TextContent]:
        action = arguments.get("action", "").lower()
        common_name = arguments.get("common_name", "")
        entry, results = await run_daemon_action(self.executor, common_name, action)
        text = format_results(
            f"Daemon {action.upper()}: {entry.common_name}",
            results,
            extra=(
                f"logical={entry.logical_name} | user={entry.user}@{entry.cpu} | "
                f"actual={entry.actual_daemon_name}"
            ),
        )
        return [TextContent(type="text", text=text)]

    async def _handle_list_daemons(self, arguments: dict) -> list[TextContent]:
        entries = await load_daemon_config(self.executor)
        if not entries:
            return [TextContent(type="text", text="No daemons found in config.")]
        lines = [
            f"Daemons ({len(entries)}) from .Op9DmnMonitor.cfg:",
            "",
        ]
        for entry in entries:
            lines.append(
                f"- {entry.common_name} | {entry.logical_name} | "
                f"{entry.user}@{entry.cpu} | {entry.actual_daemon_name}"
            )
        return [TextContent(type="text", text="\n".join(lines))]

    async def _handle_list_cm_servers(self, arguments: dict) -> list[TextContent]:
        cm_type_filter = arguments.get("cm_type")
        try:
            instances = list_cm_wl_instances(cm_type_filter)
        except ValueError as exc:
            return [TextContent(type="text", text=f"Error: {exc}")]

        if not instances:
            return [TextContent(type="text", text="No CM servers found.")]

        lines = [
            f"PET CM WL instances ({len(instances)}):",
            "",
            f"{'machine_name':<40} {'user@host':<32} cm_type",
            f"{'-' * 40} {'-' * 32} {'-' * 18}",
        ]
        for item in instances:
            lines.append(
                f"{item['machine_name']:<40} "
                f"{format_user_at_host(item):<32} "
                f"{item['cm_type']}"
            )
        return [TextContent(type="text", text="\n".join(lines))]

    def _resolve_cm_machine(self, arguments: dict) -> str | list[TextContent]:
        machine_name = arguments.get("machine_name") or arguments.get("cm_server")
        if not machine_name:
            return [TextContent(type="text", text="Error: machine_name or cm_server is required.")]
        if not arguments.get("machine_name"):
            try:
                return build_cm_machine_name(machine_name, arguments.get("cm_type"))
            except ValueError as exc:
                return [TextContent(type="text", text=f"Error: {exc}")]
        return machine_name

    async def _handle_cm_wl_properties(self, arguments: dict) -> list[TextContent]:
        action = arguments.get("action", "").lower()
        resolved = self._resolve_cm_machine(arguments)
        if isinstance(resolved, list):
            return resolved
        machine_name = resolved

        if action == "list":
            results = await list_property_files(self.executor, machine_name)
            text = format_results(
                f"CM WL properties: {machine_name}",
                results,
                extra=f"Directory: {WL_PROPERTIES_DIR}",
            )
            return [TextContent(type="text", text=text)]

        file_name = arguments.get("file_name", "").strip()
        if not file_name:
            return [TextContent(type="text", text="Error: file_name is required for this action.")]

        if action == "read":
            content, results = await read_property_file(self.executor, machine_name, file_name)
            if not results or not results[0].get("success"):
                text = format_results(
                    f"Read property file: {file_name}",
                    results,
                    extra=f"Machine: {machine_name}",
                )
                return [TextContent(type="text", text=text)]
            header = (
                f"Property file: {file_name}\n"
                f"Machine: {machine_name}\n"
                f"Path: {WL_PROPERTIES_DIR}/{file_name}\n\n"
                f"{content.rstrip()}"
            )
            return [TextContent(type="text", text=header)]

        try:
            changes = parse_changes(arguments.get("changes"))
        except ValueError as exc:
            return [TextContent(type="text", text=f"Error: {exc}")]

        if action == "preview":
            text = await preview_property_changes(
                self.executor, machine_name, file_name, changes
            )
            return [TextContent(type="text", text=text)]

        if action == "apply":
            try:
                text, results = await apply_property_changes(
                    self.executor,
                    machine_name,
                    file_name,
                    changes,
                    approved=bool(arguments.get("approved", False)),
                )
            except ValueError as exc:
                return [TextContent(type="text", text=f"Error: {exc}")]

            if results and not all(r.get("success") for r in results):
                detail = format_results(
                    f"Apply failed: {file_name}",
                    results,
                    extra=f"Machine: {machine_name}",
                )
                return [TextContent(type="text", text=f"{text}\n\n{detail}")]
            return [TextContent(type="text", text=text)]

        return [TextContent(type="text", text=f"Error: unsupported action '{action}'.")]
