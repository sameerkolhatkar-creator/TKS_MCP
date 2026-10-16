"""Format AVM results as markdown tables."""

from __future__ import annotations

from typing import Any, Optional, Tuple

from .constants import TABLE_COLUMNS


def format_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No processes matched."
    header = " | ".join(TABLE_COLUMNS)
    sep = " | ".join("---" for _ in TABLE_COLUMNS)
    lines = [header, sep]
    for row in rows:
        lines.append(
            " | ".join(
                str(row.get(col, "") if col != "host" else row.get("host") or row.get("hostName") or "")
                for col in TABLE_COLUMNS
            )
        )
    return "\n".join(lines)


def format_pod_check(pod_check: dict[str, Any]) -> str:
    if not pod_check:
        return "Pod check was not run."
    lines = [
        "Airflow / avmrest deployment check (oc):",
        "- oc available: %s" % pod_check.get("oc_available"),
        "- namespace: %s" % pod_check.get("namespace"),
        "- airflow deployed: %s  up/Running: %s" % (pod_check.get("airflow_deployed"), pod_check.get("airflow_up")),
        "- avmrest deployed: %s  up/Running: %s" % (pod_check.get("avmrest_deployed"), pod_check.get("avmrest_up")),
        "",
        "Matching pods:",
    ]
    pods = pod_check.get("pods") or []
    if pods:
        lines.extend(["  " + p for p in pods])
    else:
        lines.append("  (none)")
    deps = pod_check.get("deployments") or []
    lines.append("Matching deployments:")
    if deps:
        lines.extend(["  " + d for d in deps])
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def format_notify(action: str, environment: str, airflow_url: str, username: str) -> str:
    return (
        "NOTIFY: will perform **%s** on **%s** with Airflow URL **%s**, "
        "username **%s** (password defaulted unless overridden)."
        % (action, environment, airflow_url, username)
    )


def format_unix_result(results: list[dict[str, Any]]) -> Tuple[bool, str, Optional[dict[str, Any]]]:
    if not results:
        return False, "unix-server returned no results.", None
    result = results[0]
    stdout = (result.get("stdout") or "").strip()
    stderr = (result.get("stderr") or "").strip()
    if not result.get("success"):
        return False, "unix-server command failed (exit %s).\n%s\n%s" % (
            result.get("exit_status"),
            stdout,
            stderr,
        ), None
    # last JSON object in stdout
    parsed = None
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                parsed = __import__("json").loads(line)
                break
            except Exception:
                continue
    if parsed is None:
        try:
            parsed = __import__("json").loads(stdout)
        except Exception:
            return False, "Could not parse JSON from remote curl output:\n%s\n%s" % (stdout, stderr), None
    return True, stdout, parsed
