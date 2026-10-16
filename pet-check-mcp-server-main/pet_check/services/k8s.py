"""Kubernetes / OCP pod operations on PET_RT_ADMIN."""

from __future__ import annotations

from typing import Any, Optional

from ..constants import KUBECTL, PET_RT_ADMIN, TCK8S_NAMESPACE, TCMS_NAMESPACE


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def build_k8s_command(
    namespace: str,
    resource_name: str,
    action: str,
    replicas: Optional[int] = None,
) -> str:
    name = resource_name.strip()
    if not name:
        raise ValueError("resource_name is required")

    ns = _shell_quote(namespace)
    quoted = _shell_quote(name)

    if action == "check":
        return (
            f"{KUBECTL} get deploy,sts,pods -n {ns} -o wide 2>&1 "
            f"| grep -E '^{name}[^a-zA-Z0-9_-]|NAME|/{name}[^a-zA-Z0-9_-]'"
        )

    if action == "stop":
        return (
            f"if {KUBECTL} get deployment {quoted} -n {ns} >/dev/null 2>&1; then "
            f"{KUBECTL} scale deployment/{quoted} --replicas=0 -n {ns}; "
            f"elif {KUBECTL} get statefulset {quoted} -n {ns} >/dev/null 2>&1; then "
            f"{KUBECTL} scale statefulset/{quoted} --replicas=0 -n {ns}; "
            f"else echo 'No deployment or statefulset named {name} in {namespace}'; exit 1; fi"
        )

    if action == "start":
        count = replicas if replicas is not None else 1
        if count < 0:
            raise ValueError("replicas must be >= 0")
        return (
            f"if {KUBECTL} get deployment {quoted} -n {ns} >/dev/null 2>&1; then "
            f"{KUBECTL} scale deployment/{quoted} --replicas={count} -n {ns}; "
            f"elif {KUBECTL} get statefulset {quoted} -n {ns} >/dev/null 2>&1; then "
            f"{KUBECTL} scale statefulset/{quoted} --replicas={count} -n {ns}; "
            f"else echo 'No deployment or statefulset named {name} in {namespace}'; exit 1; fi"
        )

    if action == "restart":
        return (
            f"if {KUBECTL} get deployment {quoted} -n {ns} >/dev/null 2>&1; then "
            f"{KUBECTL} rollout restart deployment/{quoted} -n {ns} && "
            f"{KUBECTL} rollout status deployment/{quoted} -n {ns} --timeout=300s; "
            f"elif {KUBECTL} get statefulset {quoted} -n {ns} >/dev/null 2>&1; then "
            f"{KUBECTL} rollout restart statefulset/{quoted} -n {ns} && "
            f"{KUBECTL} rollout status statefulset/{quoted} -n {ns} --timeout=300s; "
            f"else {KUBECTL} delete pod -n {ns} -l app={quoted} --ignore-not-found; "
            f"{KUBECTL} get pods -n {ns} | grep '^{name}'; fi"
        )

    raise ValueError(f"Unsupported action: {action}")


async def run_k8s_action(
    executor,
    namespace: str,
    resource_name: str,
    action: str,
    replicas: Optional[int] = None,
    command_timeout: int = 360,
) -> list[dict[str, Any]]:
    command = build_k8s_command(namespace, resource_name, action, replicas)
    return await executor.execute(
        command,
        PET_RT_ADMIN,
        command_timeout_override=command_timeout,
    )


async def tck8s_action(executor, resource_name: str, action: str, replicas: Optional[int] = None):
    return await run_k8s_action(executor, TCK8S_NAMESPACE, resource_name, action, replicas)


async def tcms_action(executor, resource_name: str, action: str, replicas: Optional[int] = None):
    return await run_k8s_action(executor, TCMS_NAMESPACE, resource_name, action, replicas)
