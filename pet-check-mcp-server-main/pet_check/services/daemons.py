"""Daemon operations using .Op9DmnMonitor.cfg on PET_RT_ADMIN."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ..constants import DAEMON_CONFIG_PATH, PET_RT_ADMIN


@dataclass
class DaemonEntry:
    common_name: str
    logical_name: str
    actual_daemon_name: str
    start_command: str
    parameters: str
    stop_command: str
    cpu: str
    user: str
    is_auto_load_flag: str
    max_limit: str
    from_time: str
    until_time: str
    check_for_new: str
    group: str
    restart_flag: str


def parse_daemon_config(text: str) -> list[DaemonEntry]:
    entries: list[DaemonEntry] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#COMMON_NAME"):
            continue
        parts = [p.strip() for p in line.split(" # ")]
        if len(parts) < 8:
            continue
        while len(parts) < 15:
            parts.append("")
        entries.append(
            DaemonEntry(
                common_name=parts[0],
                logical_name=parts[1],
                actual_daemon_name=parts[2],
                start_command=parts[3],
                parameters=parts[4],
                stop_command=parts[5],
                cpu=parts[6],
                user=parts[7],
                is_auto_load_flag=parts[8],
                max_limit=parts[9],
                from_time=parts[10],
                until_time=parts[11],
                check_for_new=parts[12],
                group=parts[13],
                restart_flag=parts[14],
            )
        )
    return entries


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def build_daemon_ssh_command(user: str, cpu: str, remote_command: str) -> str:
    return f"ssh -o BatchMode=yes -o ConnectTimeout=15 {_shell_quote(user + '@' + cpu)} {_shell_quote(remote_command)}"


def build_daemon_remote_command(entry: DaemonEntry, action: str) -> str:
    if action == "stop":
        return entry.stop_command
    if action == "start":
        start = entry.start_command.strip()
        params = entry.parameters.strip()
        if params:
            return f"{start} {params}".strip()
        return start
    if action == "check":
        pattern = entry.actual_daemon_name or entry.common_name
        return f"ps -ef | grep {_shell_quote(pattern)} | grep -v grep"
    raise ValueError(f"Unsupported action: {action}")


async def load_daemon_config(executor) -> list[DaemonEntry]:
    results = await executor.execute(f"cat {_shell_quote(DAEMON_CONFIG_PATH)}", PET_RT_ADMIN)
    if not results or not results[0].get("success"):
        stderr = results[0].get("stderr", "") if results else "No response"
        raise RuntimeError(f"Failed to read daemon config: {stderr}")
    return parse_daemon_config(results[0].get("stdout", ""))


def find_daemon(entries: list[DaemonEntry], common_name: str) -> DaemonEntry:
    target = common_name.strip().lower()
    for entry in entries:
        if entry.common_name.lower() == target:
            return entry
    available = ", ".join(sorted(e.common_name for e in entries))
    raise ValueError(f"Daemon '{common_name}' not found. Available: {available}")


async def run_daemon_action(
    executor,
    common_name: str,
    action: str,
    entries: Optional[list[DaemonEntry]] = None,
    command_timeout: int = 180,
) -> tuple[DaemonEntry, list[dict[str, Any]]]:
    daemon_entries = entries or await load_daemon_config(executor)
    entry = find_daemon(daemon_entries, common_name)

    if action == "restart":
        stop_cmd = build_daemon_ssh_command(entry.user, entry.cpu, build_daemon_remote_command(entry, "stop"))
        start_cmd = build_daemon_ssh_command(entry.user, entry.cpu, build_daemon_remote_command(entry, "start"))
        stop_results = await executor.execute(stop_cmd, PET_RT_ADMIN, command_timeout_override=command_timeout)
        start_results = await executor.execute(start_cmd, PET_RT_ADMIN, command_timeout_override=command_timeout)
        return entry, stop_results + start_results

    remote = build_daemon_remote_command(entry, action)
    ssh_cmd = build_daemon_ssh_command(entry.user, entry.cpu, remote)
    results = await executor.execute(ssh_cmd, PET_RT_ADMIN, command_timeout_override=command_timeout)
    return entry, results
