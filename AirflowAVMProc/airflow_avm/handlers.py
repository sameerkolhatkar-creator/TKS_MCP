"""MCP tool definitions and handlers for Airflow AVM processes."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from mcp.types import TextContent, Tool

from .clusters import (
    cluster_ids_from_args,
    expand_clusters,
    format_cluster_catalog,
    load_cluster_config,
    resolve_site,
)
from .constants import DEFAULT_WAIT_SECONDS, PROCESS_TYPES
from .formatters import format_notify, format_pod_check, format_table, format_unix_result
from .remote import build_list_body, build_unix_command

logger = logging.getLogger(__name__)

_ENV_FILE = Path(__file__).resolve().parents[1] / "environments.json"

_FILTER_PROPS = {
    "environment": {
        "type": "string",
        "description": "Named environment from environments.json (e.g. TKS_IN08_ENV12). Map this to a unix-server machine_name.",
    },
    "unix_machine_name": {
        "type": "string",
        "description": "unix-server machine_name override (e.g. JUMP). Ask the user if the environment mapping is unclear.",
    },
    "airflow_url": {
        "type": "string",
        "description": "Airflow base URL override, e.g. https://10.77.156.62:1031",
    },
    "hop_user_host": {
        "type": "string",
        "description": "Optional extra SSH hop from the unix-server host, e.g. admin@incetks173",
    },
    "username": {"type": "string", "description": "Airflow UI username. Default admin."},
    "password": {"type": "string", "description": "Airflow UI password. Default admin."},
    "hostName": {
        "type": "string",
        "description": "Optional AVM hostName filter, e.g. incetks173.corp.amdocs.com",
    },
    "hostNames": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Optional list of AVM hostName values (OR).",
    },
    "site": {
        "type": "string",
        "description": "TKS NFT site for cluster expansion: SRB or MKS.",
    },
    "cluster": {
        "type": "string",
        "description": "Single NFT cluster id, e.g. CL1. Expanded to all IMDG VMs in that cluster.",
    },
    "clusters": {
        "type": "array",
        "items": {"type": "string"},
        "description": "NFT cluster ids, e.g. [\"CL1\", \"CL2\"]. Action applies to every IMDG VM in those clusters.",
    },
    "processType": {
        "type": "string",
        "description": "Optional processType filter. Valid: " + ", ".join(PROCESS_TYPES),
    },
    "processTypes": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Optional list of processType values (OR). Includes IMDG_ALL.",
    },
    "processName": {
        "type": "string",
        "description": "Optional processName filter (applied after the AVM response), e.g. IMDG_SERVER4021",
    },
    "processNames": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Optional list of processName values.",
    },
    "no_filters": {
        "type": "boolean",
        "description": (
            "Set true only after the user was asked for filters and chose an unfiltered list. "
            "Do NOT set this on the first call."
        ),
    },
}

FILTERS_REQUIRED = (
    "FILTERS_REQUIRED: Do not fetch the process list yet.\n"
    "Ask the user whether to add filters before calling this tool again:\n"
    "- hostName / hostNames\n"
    "- clusters / cluster + site (TKS NFT CL1–CL19 on SRB or MKS; expands to all IMDG VMs)\n"
    "- processType (AGENT, IMDG_LOCATOR, IMDG_PWINFO, IMDG_RTN, IMDG_SERVER, "
    "HB_IMDG_LOADER, HB_FETCHER_LAZY, RCND, IMDG_VIEWER, MASD, AEM_CM, UHI, JAP, "
    "APP_SERVER, AC, IMDG_DELTA, or IMDG_ALL)\n"
    "- processName (e.g. IMDG_SERVER4021)\n"
    "If they want all processes with no filters, call again with no_filters=true."
)


def load_env_config() -> dict[str, Any]:
    if _ENV_FILE.exists():
        return json.loads(_ENV_FILE.read_text(encoding="utf-8"))
    return {"default_environment": "", "environments": {}}


def list_unix_machine_names(unix_config: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for server in unix_config.get("servers") or []:
        names = server.get("machine_names") or []
        host = server.get("host", "")
        user = server.get("username", "")
        for name in names:
            rows.append({"machine_name": name, "user_host": "%s@%s" % (user, host)})
    return rows


def resolve_target(arguments: dict[str, Any], unix_config: dict[str, Any]) -> dict[str, Any]:
    cfg = load_env_config()
    environments = cfg.get("environments") or {}
    env_name = (arguments.get("environment") or "").strip()
    if not env_name and arguments.get("site"):
        try:
            site_name = resolve_site(arguments.get("site"))
            env_name = ((load_cluster_config().get("sites") or {}).get(site_name) or {}).get(
                "environment"
            ) or ""
        except ValueError:
            env_name = ""
    env_name = env_name or (cfg.get("default_environment") or "")
    env_name = env_name.strip()
    env = environments.get(env_name) or {}
    unix_machine = (
        arguments.get("unix_machine_name")
        or env.get("unix_machine_name")
        or ""
    ).strip()
    airflow_url = (arguments.get("airflow_url") or env.get("airflow_url") or "").strip()
    hop = (arguments.get("hop_user_host") or env.get("hop_user_host") or "").strip() or None
    username = (arguments.get("username") or env.get("username") or "admin").strip()
    password = arguments.get("password") or env.get("password") or "admin"
    if not airflow_url:
        raise ValueError(
            "Airflow URL is missing. Pass airflow_url or choose a known environment. "
            "Known: %s" % ", ".join(sorted(environments))
        )
    if not unix_machine:
        machines = list_unix_machine_names(unix_config)
        sample = ", ".join(sorted({m["machine_name"] for m in machines})[:20])
        raise ValueError(
            "unix_machine_name is missing. Map the environment to a unix-server machine "
            "(list_environments) or pass unix_machine_name. Known samples: %s" % sample
        )
    return {
        "environment": env_name or "(adhoc)",
        "unix_machine_name": unix_machine,
        "airflow_url": airflow_url.rstrip("/"),
        "hop_user_host": hop,
        "username": username,
        "password": password,
        "description": env.get("description") or "",
        "oc_namespace": (arguments.get("oc_namespace") or env.get("oc_namespace") or "").strip(),
    }


def _filters_from_args(arguments: dict[str, Any]) -> dict[str, Any]:
    names = arguments.get("processNames") or []
    if arguments.get("processName"):
        names = list(names) + [arguments["processName"]]
    types = arguments.get("processTypes") or []
    if arguments.get("processType"):
        types = list(types) + [arguments["processType"]]
    hosts: list[str] = []
    host_seen: set[str] = set()
    for item in list(arguments.get("hostNames") or []) + (
        [arguments["hostName"]] if arguments.get("hostName") else []
    ):
        value = str(item).strip()
        if value and value not in host_seen:
            host_seen.add(value)
            hosts.append(value)
    expansion = None
    cluster_ids = cluster_ids_from_args(arguments)
    if cluster_ids:
        expansion = expand_clusters(
            cluster_ids,
            site=arguments.get("site"),
            environment=arguments.get("environment"),
        )
        for host in expansion.get("hosts") or []:
            if host not in host_seen:
                host_seen.add(host)
                hosts.append(host)
    return {
        "host_name": hosts[0] if len(hosts) == 1 else None,
        "host_names": hosts,
        "process_types": types,
        "process_names": names,
        "cluster_expansion": expansion,
    }


def _has_list_filters(arguments: dict[str, Any]) -> bool:
    filters = _filters_from_args(arguments)
    return bool(
        filters["host_names"]
        or filters["process_types"]
        or filters["process_names"]
        or filters["cluster_expansion"]
    )


def _filters_confirmed(arguments: dict[str, Any]) -> bool:
    return _has_list_filters(arguments) or arguments.get("no_filters") is True


def get_tool_definitions() -> list[Tool]:
    types_help = ", ".join(PROCESS_TYPES)
    list_flow = (
        "AGENT FLOW: 1) Resolve environment from unix-server machine names or ask for Airflow URL. "
        "2) Notify the user of ACTION / ENVIRONMENT / Airflow URL / username. "
        "3) ALWAYS ask for filters first (hostName, clusters+site, processType, processName). Do not call this tool "
        "until the user answers. Then pass those filters, or no_filters=true if they declined. "
        "If the user names NFT clusters (CL1, CL2, ...), pass clusters and site; the MCP expands to all IMDG VMs. "
        "The tool refuses the first unfiltered call. "
        "4) Show the returned table (sid, processType, processName, status, host). "
        "Valid processType: " + types_help + "."
    )
    return [
        Tool(
            name="list_environments",
            description=(
                "List configured Airflow AVM environments and unix-server machine_name mappings. "
                "Use this first to understand which environment the user means."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="list_nft_clusters",
            description=(
                "Show TKS_NFT_Cluster map: NFT site (SRB, MKS) → CL1–CL19 → IMDG VM hostnames. "
                "Use when the user names clusters so list/start/stop can target every VM in those clusters."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "site": {
                        "type": "string",
                        "description": "Optional site filter: SRB or MKS.",
                    }
                },
            },
        ),
        Tool(
            name="list_up_processes",
            description=(
                "Get AVM UP processes (Stop Processes page / collectUpProcessList) via unix-server remote curl. "
                + list_flow
                + " After displaying the table, ask if the Stop processes routine should be initiated."
            ),
            inputSchema={"type": "object", "properties": _FILTER_PROPS},
        ),
        Tool(
            name="list_down_processes",
            description=(
                "Get AVM DOWN processes (Start Processes page / collectDownProcessList) via unix-server remote curl. "
                + list_flow
                + " After displaying the table, ask if the Start processes routine should be initiated."
            ),
            inputSchema={"type": "object", "properties": _FILTER_PROPS},
        ),
        Tool(
            name="stop_processes",
            description=(
                "Stop AVM processes via /avm/v1/sendStopProcessCommand. "
                "AGENT FLOW: list UP processes first (re-run with extra filters if the user asks). "
                "If the user names NFT clusters, pass clusters+site+processType so all matching IMDG VMs are included. "
                "If the user gives SIDs, stop those. If they want all currently listed rows stopped, "
                "pass those SIDs with all_matching=false. confirm=true is required. "
                "Do not stop AGENT unless the user explicitly includes that SID. "
                "Waits wait_seconds (default 30) then lists DOWN processes for those SIDs."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    **_FILTER_PROPS,
                    "sids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Process SIDs to stop, e.g. [4009, 4021]",
                    },
                    "all_matching": {
                        "type": "boolean",
                        "description": "If true, list UP with the given filters and stop every returned SID.",
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Must be true after the user approved the stop.",
                    },
                    "wait_seconds": {
                        "type": "integer",
                        "description": "Seconds to wait before verification (default 30).",
                    },
                },
            },
        ),
        Tool(
            name="start_processes",
            description=(
                "Start AVM processes via /avm/v1/sendStartProcessCommand. "
                "AGENT FLOW: list DOWN processes first (re-run with extra filters if the user asks). "
                "If the user names NFT clusters, pass clusters+site+processType so all matching IMDG VMs are included. "
                "If the user gives SIDs, start those. If they want all currently listed rows started, "
                "pass those SIDs. confirm=true is required. "
                "Warn if AGENT on the host is Down. HTTP 200 with empty body is success. "
                "Waits wait_seconds (default 30) then lists UP processes for those SIDs."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    **_FILTER_PROPS,
                    "sids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Process SIDs to start, e.g. [4021, 4022]",
                    },
                    "all_matching": {
                        "type": "boolean",
                        "description": "If true, list DOWN with the given filters and start every returned SID.",
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Must be true after the user approved the start.",
                    },
                    "wait_seconds": {
                        "type": "integer",
                        "description": "Seconds to wait before verification (default 30).",
                    },
                },
            },
        ),
    ]


class ToolHandler:
    def __init__(self, command_executor, unix_config: dict[str, Any]):
        self.executor = command_executor
        self.unix_config = unix_config

    async def handle(self, name: str, arguments: dict[str, Any]) -> list[TextContent]:
        arguments = arguments or {}
        try:
            if name == "list_environments":
                text = self._list_environments()
            elif name == "list_nft_clusters":
                text = self._list_nft_clusters(arguments)
            elif name == "list_up_processes":
                text = await self._list_processes("list_up", arguments)
            elif name == "list_down_processes":
                text = await self._list_processes("list_down", arguments)
            elif name == "stop_processes":
                text = await self._mutate("stop", arguments)
            elif name == "start_processes":
                text = await self._mutate("start", arguments)
            else:
                text = "Unknown tool: %s" % name
        except Exception as exc:
            logger.exception("AirflowAVMProc tool %s failed", name)
            text = "Error: %s" % exc
        return [TextContent(type="text", text=text)]

    def _list_environments(self) -> str:
        cfg = load_env_config()
        lines = ["Configured Airflow AVM environments", ""]
        for name, env in (cfg.get("environments") or {}).items():
            default_mark = " (default)" if name == cfg.get("default_environment") else ""
            lines.append("- **%s**%s" % (name, default_mark))
            lines.append("  - %s" % (env.get("description") or ""))
            lines.append("  - unix-server machine_name: `%s`" % env.get("unix_machine_name"))
            lines.append("  - hop: `%s`" % (env.get("hop_user_host") or "(none)"))
            lines.append("  - Airflow URL: %s" % env.get("airflow_url"))
            lines.append("  - username: %s" % (env.get("username") or "admin"))
            lines.append("")
        lines.append("unix-server machine names (from UNIX_CONFIG_FILE):")
        for row in list_unix_machine_names(self.unix_config):
            lines.append("- `%s` → %s" % (row["machine_name"], row["user_host"]))
        lines.append("")
        lines.append("If the environment is not listed, ask the user for Airflow URL + unix-server machine_name.")
        lines.append("NFT clusters: use list_nft_clusters (TKS_NFT_Cluster skill). Pass clusters+site on list/start/stop.")
        return "\n".join(lines)

    def _list_nft_clusters(self, arguments: dict[str, Any]) -> str:
        return format_cluster_catalog(arguments.get("site"))

    async def _run(self, target: dict[str, Any], payload: dict[str, Any], timeout: int = 180) -> dict[str, Any]:
        payload = dict(payload)
        payload["airflow_url"] = target["airflow_url"]
        payload["username"] = target["username"]
        payload["password"] = target["password"]
        payload["cookie_jar"] = "/tmp/airflow.cj"
        payload["oc_namespace"] = target.get("oc_namespace") or ""
        cmd = build_unix_command(payload, target.get("hop_user_host"))
        results = await self.executor.execute(
            cmd, target["unix_machine_name"], command_timeout_override=timeout
        )
        ok, raw, parsed = format_unix_result(results)
        if not ok or parsed is None:
            raise RuntimeError(raw)
        parsed["_unix_raw"] = raw
        parsed["_target"] = target
        return parsed

    def _format_curl_failure(self, parsed: dict[str, Any], target: dict[str, Any]) -> str:
        lines = [
            format_notify(
                parsed.get("action") or "AVM call",
                target["environment"],
                target["airflow_url"],
                target.get("username") or "",
            ),
            "Airflow/AVM curl returned no usable response: %s" % parsed.get("error"),
            "",
            format_pod_check(parsed.get("pod_check") or {}),
        ]
        return "\n".join(lines)

    async def _list_processes(self, action: str, arguments: dict[str, Any]) -> str:
        if not _filters_confirmed(arguments):
            return FILTERS_REQUIRED
        target = resolve_target(arguments, self.unix_config)
        filters = _filters_from_args(arguments)
        body = build_list_body(
            host_name=filters["host_name"],
            host_names=filters["host_names"],
            process_types=filters["process_types"],
        )
        payload = {
            "action": action,
            "body": body,
            "process_names": filters["process_names"],
        }
        parsed = await self._run(target, payload, timeout=120)
        if parsed.get("ok") is False:
            return self._format_curl_failure(parsed, target)
        label = "UP" if action == "list_up" else "DOWN"
        follow = (
            "Ask the user if the Stop processes routine should be initiated."
            if action == "list_up"
            else "Ask the user if the Start processes routine should be initiated."
        )
        lines = [
            format_notify("list %s processes" % label, target["environment"], target["airflow_url"], target["username"]),
            "unix-server machine: `%s` hop: `%s`" % (target["unix_machine_name"], target.get("hop_user_host") or "none"),
            "AVM filters: `%s`" % json.dumps(body.get("filterField") or []),
        ]
        expansion = filters.get("cluster_expansion")
        if expansion:
            lines.append(
                "TKS_NFT_Cluster %s %s → hosts: %s"
                % (expansion.get("display_name"), expansion.get("clusters"), ", ".join(expansion.get("hosts") or []))
            )
        lines.extend(
            [
                "",
                format_table(parsed.get("rows") or []),
                "",
                "Total: %s" % parsed.get("total", 0),
                follow,
            ]
        )
        return "\n".join(lines)

    async def _mutate(self, action: str, arguments: dict[str, Any]) -> str:
        if not arguments.get("confirm"):
            return (
                "Refused: confirm=true is required. Show the process table, get explicit approval, "
                "then call again with confirm=true and the SID list."
            )
        target = resolve_target(arguments, self.unix_config)
        sids = [int(s) for s in (arguments.get("sids") or [])]
        filters = _filters_from_args(arguments)
        wait_seconds = int(arguments.get("wait_seconds") if arguments.get("wait_seconds") is not None else DEFAULT_WAIT_SECONDS)
        if arguments.get("all_matching") or not sids:
            list_action = "list_up" if action == "stop" else "list_down"
            body = build_list_body(
                host_name=filters["host_name"],
                host_names=filters["host_names"],
                process_types=filters["process_types"],
            )
            listed = await self._run(
                target,
                {"action": list_action, "body": body, "process_names": filters["process_names"]},
                timeout=120,
            )
            if listed.get("ok") is False:
                return self._format_curl_failure(listed, target)
            sids = [int(r["sid"]) for r in (listed.get("rows") or []) if r.get("sid") is not None]
            if not arguments.get("all_matching") and not arguments.get("sids"):
                return (
                    "No SIDs provided. Current matching %s processes:\n\n%s\n\n"
                    "Re-call with sids=[...] and confirm=true, or all_matching=true after approval."
                    % ("UP" if action == "stop" else "DOWN", format_table(listed.get("rows") or []))
                )
        if not sids:
            return "No matching SIDs to %s." % action
        if action == "stop" and not arguments.get("all_matching"):
            pass
        parsed = await self._run(
            target,
            {
                "action": action,
                "sids": sids,
                "wait_seconds": wait_seconds,
                "body": {},
            },
            timeout=max(90, wait_seconds + 60),
        )
        if parsed.get("ok") is False:
            return self._format_curl_failure(parsed, target)
        http_code = parsed.get("command_http_code")
        lines = [
            format_notify(
                "%s processes %s" % (action, sids),
                target["environment"],
                target["airflow_url"],
                target["username"],
            ),
            "Command HTTP: %s (empty body + 200 is success)" % http_code,
            "Waited %s seconds, then listed %s processes for those SIDs."
            % (parsed.get("wait_seconds"), parsed.get("verify_list")),
            "",
            format_table(parsed.get("verified_rows") or []),
            "",
            "SIDs found on verify list: %s" % parsed.get("verified_sids_found"),
            "SIDs not found on verify list: %s" % parsed.get("missing_sids"),
        ]
        if action == "start" and parsed.get("missing_sids"):
            lines.append(
                "Note: missing SIDs may still be booting, or AGENT on that host may be Down. "
                "Re-list after another wait."
            )
        return "\n".join(lines)
