"""Build and wrap the remote curl/python payload run via unix-server."""

from __future__ import annotations

import base64
import json
from typing import Any, Optional

from .constants import COOKIE_JAR, DEFAULT_PAGE_SIZE


def shell_quote(value: str) -> str:
    return "'" + str(value).replace("'", "'\\''") + "'"


def build_filter_field(
    host_name: Optional[str] = None,
    host_names: Optional[list[str]] = None,
    process_type: Optional[str] = None,
    process_types: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    types: list[str] = []
    if process_types:
        types.extend([t.strip() for t in process_types if t and str(t).strip()])
    if process_type and str(process_type).strip():
        types.append(str(process_type).strip())
    seen = set()
    unique_types = []
    for item in types:
        if item not in seen:
            seen.add(item)
            unique_types.append(item)
    if unique_types:
        filters.append({"filterKey": "processType", "filterValue": unique_types})
    hosts: list[str] = []
    host_seen: set[str] = set()
    for item in list(host_names or []) + ([host_name] if host_name else []):
        value = str(item).strip()
        if value and value not in host_seen:
            host_seen.add(value)
            hosts.append(value)
    if hosts:
        filters.append({"filterKey": "hostName", "filterValue": hosts})
    return filters


def build_list_body(
    host_name: Optional[str] = None,
    host_names: Optional[list[str]] = None,
    process_type: Optional[str] = None,
    process_types: Optional[list[str]] = None,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    return {
        "pageNumber": 1,
        "pageSize": page_size or DEFAULT_PAGE_SIZE,
        "sortField": None,
        "filterField": build_filter_field(host_name, host_names, process_type, process_types),
    }


def _remote_python_script() -> str:
    return r'''
import json
import os
import re
import subprocess
import sys
import time

spec = json.loads(sys.stdin.read())
vip = spec["airflow_url"].rstrip("/")
user = spec.get("username") or "admin"
password = spec.get("password") or "admin"
cj = spec.get("cookie_jar") or "/tmp/airflow.cj"
action = spec["action"]
body = spec.get("body") or {}
sids = spec.get("sids") or []
wait_seconds = int(spec.get("wait_seconds") or 0)
process_name = (spec.get("process_name") or "").strip()
process_names = spec.get("process_names") or []
wanted_names = set([n for n in ([process_name] + list(process_names)) if n])

def run(args, timeout=45):
    try:
        proc = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True
        )
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except Exception:
            pass
        raise RuntimeError("curl timeout after %ss: %s" % (timeout, " ".join(args[:6])))
    if proc.returncode != 0:
        raise RuntimeError("cmd failed rc=%s: %s\n%s" % (proc.returncode, " ".join(args), (out or "")[:800]))
    return out or ""

def diagnose_pods():
    ns = (spec.get("oc_namespace") or "").strip()
    needles = ("airflow", "avmrest", "avm-rest", "avm_rest")
    info = {"oc_available": False, "namespace": ns or "(all namespaces)", "pods": [], "deployments": [], "raw": ""}
    oc = "oc"
    try:
        which = subprocess.Popen(["which", "oc"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        wout, _ = which.communicate()
        if which.returncode != 0 or not (wout or "").strip():
            info["raw"] = "oc not found in PATH"
            return info
        info["oc_available"] = True
    except Exception as exc:
        info["raw"] = "oc lookup failed: %s" % exc
        return info
    def oc_get(kind):
        args = [oc, "get", kind, "--no-headers"]
        if ns:
            args.extend(["-n", ns])
        else:
            args.append("-A")
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        out, _ = p.communicate()
        rows = []
        for line in (out or "").splitlines():
            low = line.lower()
            if any(n in low for n in needles):
                rows.append(line.strip())
        return p.returncode, out or "", rows
    rc1, raw1, pods = oc_get("pods")
    rc2, raw2, deps = oc_get("deploy")
    info["pods"] = pods
    info["deployments"] = deps
    info["raw"] = (("pods rc=%s\n" % rc1) + "\n".join(pods or ["(none matching airflow/avmrest)"]) +
                   "\n\ndeploy rc=%s\n" % rc2 + "\n".join(deps or ["(none matching airflow/avmrest)"]))
    def is_up(line):
        low = line.lower()
        return ("running" in low) or ("/" in line and " 0/" not in line and "running" in low)
    airflow_pods = [p for p in pods if "airflow" in p.lower() and "avm" not in p.lower()]
    avm_pods = [p for p in pods if "avmrest" in p.lower() or "avm-rest" in p.lower() or "avm_rest" in p.lower()]
    if not avm_pods:
        avm_pods = [p for p in pods if "avm" in p.lower()]
    info["airflow_up"] = any("running" in p.lower() for p in airflow_pods)
    info["avmrest_up"] = any("running" in p.lower() for p in avm_pods)
    info["airflow_deployed"] = bool(airflow_pods) or any("airflow" in d.lower() for d in deps)
    info["avmrest_deployed"] = bool(avm_pods) or any(("avmrest" in d.lower() or "avm-rest" in d.lower() or "avm" in d.lower()) for d in deps)
    return info


def csrf_from_html(html, attr="value"):
    if attr == "content":
        m = re.search(r'csrf_token"\s+content="([^"]+)"', html)
        if m:
            return m.group(1)
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    if m:
        return m.group(1)
    m = re.search(r'csrf_token"\s+value="([^"]+)"', html)
    if m:
        return m.group(1)
    return ""

def login():
    try:
        os.remove(cj)
    except OSError:
        pass
    html = run(["curl", "-k", "-sS", "--connect-timeout", "20", "--max-time", "45", "-c", cj, vip + "/login/"])
    if not (html or "").strip():
        raise RuntimeError("empty response from %s/login/" % vip)
    token = csrf_from_html(html, "value")
    if not token:
        raise RuntimeError("Could not parse login CSRF token")
    run([
        "curl", "-k", "-sS", "--connect-timeout", "20", "--max-time", "45", "-b", cj, "-c", cj, "-X", "POST", vip + "/login/",
        "-H", "Referer: %s/login/" % vip,
        "-d", "csrf_token=" + token,
        "-d", "username=" + user,
        "-d", "password=" + password,
        "-o", "/dev/null",
    ])
    home = run(["curl", "-k", "-sS", "--connect-timeout", "20", "--max-time", "45", "-b", cj, "-c", cj, vip + "/home"])
    if not (home or "").strip():
        raise RuntimeError("empty response from %s/home" % vip)
    xtoken = csrf_from_html(home, "content") or csrf_from_html(home, "value")
    if not xtoken:
        raise RuntimeError("Could not parse X-CSRFToken from /home (login may have failed)")
    return xtoken

def avm_post(xtoken, path, referer, payload, expect_json=True):
    data = json.dumps(payload)
    out = run([
        "curl", "-k", "-sS", "--connect-timeout", "20", "--max-time", "45", "-b", cj, "-c", cj, "-X", "POST",
        vip + path,
        "-H", "Content-Type: application/json",
        "-H", "X-CSRFToken: " + xtoken,
        "-H", "Referer: " + vip + referer,
        "-d", data,
        "-w", "\n__HTTP__%{http_code}",
    ])
    marker = "\n__HTTP__"
    http_code = 0
    body_text = out
    if marker in out:
        body_text, tail = out.rsplit(marker, 1)
        try:
            http_code = int(tail.strip())
        except ValueError:
            http_code = 0
    if not expect_json:
        return {"http_code": http_code, "raw": body_text}
    body_text = body_text.strip()
    if not body_text:
        return {"http_code": http_code, "empty": True}
    try:
        return json.loads(body_text)
    except ValueError:
        raise RuntimeError("Non-JSON AVM response HTTP=%s: %s" % (http_code, body_text[:500]))

def rows_from(payload):
    rows = payload.get("avmProcList") or []
    if wanted_names:
        rows = [p for p in rows if p.get("processName") in wanted_names]
    return rows

def table(rows):
    out = []
    for p in rows:
        out.append({
            "sid": p.get("sid"),
            "processType": p.get("processType"),
            "processName": p.get("processName"),
            "status": p.get("status"),
            "host": p.get("hostName") or p.get("host"),
            "agentStatus": p.get("agentStatus"),
            "state": p.get("state"),
        })
    return out

try:
    xtoken = login()
    result = {
        "ok": True,
        "action": action,
        "airflow_url": vip,
        "username": user,
    }
    if action in ("list_up", "list_down"):
        path = "/avm/v1/collectUpProcessList" if action == "list_up" else "/avm/v1/collectDownProcessList"
        referer = "/charging-control/stop-processes" if action == "list_up" else "/charging-control/start-processes"
        payload = avm_post(xtoken, path, referer, body)
        if isinstance(payload, dict) and payload.get("empty"):
            raise RuntimeError("empty AVM response HTTP=%s for %s" % (payload.get("http_code"), path))
        rows = table(rows_from(payload if isinstance(payload, dict) else {}))
        result["rows"] = rows
        result["total"] = len(rows)
        result["filterField"] = body.get("filterField") or []
    elif action in ("start", "stop"):
        if not sids:
            raise RuntimeError("No SIDs provided")
        path = "/avm/v1/sendStartProcessCommand" if action == "start" else "/avm/v1/sendStopProcessCommand"
        referer = "/charging-control/start-processes" if action == "start" else "/charging-control/stop-processes"
        cmd_result = avm_post(xtoken, path, referer, [{"sid": int(s)} for s in sids], expect_json=False)
        result["command_http_code"] = cmd_result.get("http_code")
        result["command_body"] = cmd_result.get("raw") or ""
        result["sids"] = sids
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        verify_path = "/avm/v1/collectUpProcessList" if action == "start" else "/avm/v1/collectDownProcessList"
        verify_ref = "/charging-control/stop-processes" if action == "start" else "/charging-control/start-processes"
        payload = avm_post(xtoken, verify_path, verify_ref, {
            "pageNumber": 1, "pageSize": 500, "sortField": None, "filterField": [],
        })
        wanted = set(int(s) for s in sids)
        rows = [r for r in table(rows_from(payload if isinstance(payload, dict) else {})) if int(r.get("sid") or 0) in wanted]
        result["verified_rows"] = rows
        result["verified_sids_found"] = [r["sid"] for r in rows]
        result["missing_sids"] = [s for s in sids if int(s) not in set(int(r["sid"]) for r in rows)]
        result["wait_seconds"] = wait_seconds
        result["verify_list"] = "UP" if action == "start" else "DOWN"
    else:
        raise RuntimeError("Unknown action: %s" % action)
except Exception as err:
    result = {
        "ok": False,
        "action": action,
        "airflow_url": vip,
        "error": str(err),
        "pod_check": diagnose_pods(),
    }

print(json.dumps(result))
'''


def wrap_remote_command(python_script: str, payload: dict[str, Any], hop_user_host: Optional[str]) -> str:
    script_b64 = base64.b64encode(python_script.encode("utf-8")).decode("ascii")
    spec_b64 = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    inner = (
        "python3 -c 'import base64,sys,io; "
        "script=base64.b64decode(\"%s\").decode(); spec=base64.b64decode(\"%s\").decode(); "
        "sys.stdin=io.StringIO(spec); exec(compile(script, \"<avm>\", \"exec\"))'"
        % (script_b64, spec_b64)
    )
    if hop_user_host:
        return "ssh -o BatchMode=yes -o ConnectTimeout=15 %s %s" % (
            shell_quote(hop_user_host),
            shell_quote(inner),
        )
    return inner


def build_unix_command(payload: dict[str, Any], hop_user_host: Optional[str]) -> str:
    return wrap_remote_command(_remote_python_script(), payload, hop_user_host)
