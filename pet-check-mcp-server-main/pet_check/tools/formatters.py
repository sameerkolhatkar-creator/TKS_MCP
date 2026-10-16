"""Format remote command results for MCP responses."""

from typing import Any


def format_results(
    title: str,
    results: list[dict[str, Any]],
    extra: str = "",
) -> str:
    lines = [title]
    if extra:
        lines.append(extra)
    lines.append("")

    if not results:
        lines.append("No results returned.")
        return "\n".join(lines)

    if len(results) == 1:
        result = results[0]
        lines.extend(_format_single(result))
        return "\n".join(lines)

    for index, result in enumerate(results, start=1):
        lines.append(f"--- Step {index}: {result.get('server', 'unknown')} ---")
        lines.extend(_format_single(result, indent="  "))
        lines.append("")

    return "\n".join(lines).rstrip()


def _format_single(result: dict[str, Any], indent: str = "") -> list[str]:
    lines = [
        f"{indent}Machine: {result.get('module', 'unknown')}",
        f"{indent}Server: {result.get('server', 'unknown')}",
        f"{indent}Exit Status: {result.get('exit_status')}",
        f"{indent}Success: {result.get('success')}",
    ]
    stdout = result.get("stdout", "")
    stderr = result.get("stderr", "")
    if stdout:
        lines.append(f"{indent}STDOUT:\n{stdout.rstrip()}")
    if stderr:
        lines.append(f"{indent}STDERR:\n{stderr.rstrip()}")
    return lines
