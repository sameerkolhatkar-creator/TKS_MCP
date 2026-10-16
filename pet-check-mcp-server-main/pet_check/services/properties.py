"""CM WebLogic application property file operations."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from ..constants import WL_PROPERTIES_DIR


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def _property_file_path(file_name: str) -> str:
    name = file_name.strip().lstrip("/")
    if not name or "/" in name or ".." in name:
        raise ValueError("file_name must be a simple file name (no path separators)")
    return f"{WL_PROPERTIES_DIR}/{name}"


def _parse_property_key(line: str) -> Optional[str]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("!"):
        return None
    if "=" in stripped:
        return stripped.split("=", 1)[0].strip()
    if ":" in stripped and not stripped.startswith("http"):
        return stripped.split(":", 1)[0].strip()
    return None


@dataclass
class PropertyChange:
    key: str
    value: str = ""
    action: str = "set"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PropertyChange":
        key = str(data.get("key", "")).strip()
        if not key:
            raise ValueError("Each change requires a non-empty key")
        action = str(data.get("action", "set")).strip().lower()
        if action not in ("set", "delete"):
            raise ValueError(f"Invalid change action '{action}'. Use set or delete.")
        return cls(key=key, value=str(data.get("value", "")), action=action)


def parse_changes(changes: Optional[list[dict[str, Any]]]) -> list[PropertyChange]:
    if not changes:
        raise ValueError("changes is required for preview/apply actions")
    return [PropertyChange.from_dict(item) for item in changes]


def apply_changes_to_content(content: str, changes: list[PropertyChange]) -> tuple[str, list[str]]:
    """Return updated content and a human-readable list of modifications."""
    lines = content.splitlines()
    keys_to_change = {change.key: change for change in changes}
    seen_keys: set[str] = set()
    output_lines: list[str] = []
    modifications: list[str] = []

    for line in lines:
        key = _parse_property_key(line)
        if key is None or key not in keys_to_change:
            output_lines.append(line)
            continue

        seen_keys.add(key)
        change = keys_to_change[key]
        if change.action == "delete":
            modifications.append(f"- {key}: deleted")
            continue

        old_value = line.split("=", 1)[1].strip() if "=" in line else ""
        output_lines.append(f"{key}={change.value}")
        modifications.append(f"- {key}: {old_value!r} -> {change.value!r}")

    for change in changes:
        if change.key in seen_keys:
            continue
        if change.action == "delete":
            modifications.append(f"- {change.key}: (not found, no-op)")
            continue
        output_lines.append(f"{change.key}={change.value}")
        modifications.append(f"- {change.key}: (added) -> {change.value!r}")

    trailing_newline = content.endswith("\n")
    updated = "\n".join(output_lines)
    if trailing_newline:
        updated += "\n"
    return updated, modifications


def build_backup_command(file_path: str, timestamp: str) -> tuple[str, str]:
    backup_path = f"{file_path}.bak.{timestamp}"
    command = f"cp -p {_shell_quote(file_path)} {_shell_quote(backup_path)}"
    return command, backup_path


def build_read_command(file_path: str) -> str:
    return f"cat {_shell_quote(file_path)}"


def build_list_command() -> str:
    return f"ls -1 {_shell_quote(WL_PROPERTIES_DIR)} 2>/dev/null || echo ''"


def build_write_command(file_path: str, content: str) -> str:
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    quoted_path = _shell_quote(file_path)
    return f"echo {_shell_quote(encoded)} | base64 -d > {quoted_path}"


def format_backup_notice(backup_path: str) -> str:
    return f">>> BACKUP CREATED: {backup_path} <<<"


async def list_property_files(executor, machine_name: str) -> list[dict[str, Any]]:
    return await executor.execute(build_list_command(), machine_name)


async def read_property_file(
    executor,
    machine_name: str,
    file_name: str,
) -> tuple[str, list[dict[str, Any]]]:
    file_path = _property_file_path(file_name)
    results = await executor.execute(build_read_command(file_path), machine_name)
    if not results or not results[0].get("success"):
        return "", results

    content = results[0].get("stdout", "")
    if content.startswith("cat:") or "No such file" in content:
        raise ValueError(f"Property file not found: {file_name}")
    return content, results


async def preview_property_changes(
    executor,
    machine_name: str,
    file_name: str,
    changes: list[PropertyChange],
) -> str:
    current, _ = await read_property_file(executor, machine_name, file_name)
    updated, modifications = apply_changes_to_content(current, changes)

    lines = [
        f"Preview changes for {file_name} on {machine_name}",
        f"Path: {_property_file_path(file_name)}",
        "",
        "Proposed modifications:",
    ]
    lines.extend(modifications or ["- (no changes)"])
    lines.extend(["", "--- Current content ---", current.rstrip(), "", "--- Updated content ---", updated.rstrip()])
    lines.extend([
        "",
        "Approval required: present these changes to the user and obtain explicit approval "
        f"for {file_name} before calling apply with approved=true.",
    ])
    return "\n".join(lines)


async def apply_property_changes(
    executor,
    machine_name: str,
    file_name: str,
    changes: list[PropertyChange],
    approved: bool,
) -> tuple[str, list[dict[str, Any]]]:
    if not approved:
        raise ValueError(
            f"User approval is required before applying changes to {file_name}. "
            "Present the preview to the user, obtain explicit approval per file, "
            "then call apply with approved=true."
        )

    file_path = _property_file_path(file_name)
    current, read_results = await read_property_file(executor, machine_name, file_name)
    if not read_results or not read_results[0].get("success"):
        return "", read_results

    updated, modifications = apply_changes_to_content(current, changes)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_cmd, backup_path = build_backup_command(file_path, timestamp)

    all_results: list[dict[str, Any]] = []
    backup_results = await executor.execute(backup_cmd, machine_name)
    all_results.extend(backup_results)
    if backup_results and not all(r.get("success") for r in backup_results):
        return "", all_results

    write_results = await executor.execute(build_write_command(file_path, updated), machine_name)
    all_results.extend(write_results)

    lines = [
        f"Applied property changes to {file_name} on {machine_name}",
        f"Path: {file_path}",
        "",
        format_backup_notice(backup_path),
        "",
        "Modifications:",
    ]
    lines.extend(modifications or ["- (no changes)"])
    if write_results and all(r.get("success") for r in write_results):
        lines.append("")
        lines.append("Status: SUCCESS — file updated.")
    else:
        lines.append("")
        lines.append("Status: FAILED — see command output below.")

    return "\n".join(lines), all_results
