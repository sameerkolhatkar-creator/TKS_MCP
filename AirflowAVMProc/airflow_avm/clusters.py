"""TKS NFT cluster → IMDG VM mapping (SRB / MKS)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

_CLUSTER_FILE = Path(__file__).resolve().parents[1] / "tks_nft_clusters.json"

_CLUSTER_RE = re.compile(r"^(?:CL|CLUSTER)?\s*[-_ ]*(\d+)$", re.IGNORECASE)


def load_cluster_config() -> dict[str, Any]:
    if _CLUSTER_FILE.exists():
        return json.loads(_CLUSTER_FILE.read_text(encoding="utf-8"))
    return {"fqdn_suffix": ".r1.telkomsel.co.id", "sites": {}}


def normalize_cluster_id(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Empty cluster id")
    match = _CLUSTER_RE.match(raw.replace(" ", ""))
    if match:
        return "CL%s" % int(match.group(1))
    upper = raw.upper()
    if upper.startswith("CL") and upper[2:].isdigit():
        return "CL%s" % int(upper[2:])
    raise ValueError("Unknown cluster id: %s (expected CL1..CL19)" % value)


def _alias_key(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def resolve_site(site: Optional[str] = None, environment: Optional[str] = None) -> str:
    cfg = load_cluster_config()
    sites = cfg.get("sites") or {}
    for candidate in (site, environment):
        key = _alias_key(candidate or "")
        if not key:
            continue
        for name, data in sites.items():
            aliases = [_alias_key(name)] + [_alias_key(a) for a in (data.get("aliases") or [])]
            env_alias = _alias_key(data.get("environment") or "")
            if key in aliases or (env_alias and env_alias in key) or key in env_alias:
                return name
            if key.startswith(name) or name in key:
                return name
    raise ValueError(
        "NFT site is required to expand clusters. Pass site=SRB or site=MKS "
        "(or use environment SRB_NFT_ADMIN / MKS_NFT_ADMIN). Known sites: %s"
        % ", ".join(sorted(sites))
    )


def cluster_ids_from_args(arguments: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("clusters", "cluster"):
        raw = arguments.get(key)
        if raw is None:
            continue
        if isinstance(raw, str):
            parts = re.split(r"[,;\s]+", raw)
            values.extend([p for p in parts if p])
        elif isinstance(raw, (list, tuple)):
            values.extend([str(p) for p in raw if p])
    seen: set[str] = set()
    out: list[str] = []
    for item in values:
        cid = normalize_cluster_id(item)
        if cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out


def expand_clusters(
    cluster_ids: list[str],
    site: Optional[str] = None,
    environment: Optional[str] = None,
    include_fqdn: bool = False,
) -> dict[str, Any]:
    cfg = load_cluster_config()
    site_name = resolve_site(site, environment)
    site_data = (cfg.get("sites") or {}).get(site_name) or {}
    mapping = site_data.get("clusters") or {}
    suffix = cfg.get("fqdn_suffix") or ""
    unknown: list[str] = []
    hosts: list[str] = []
    per_cluster: dict[str, list[str]] = {}
    seen: set[str] = set()
    normalized: list[str] = []
    seen_c: set[str] = set()
    for raw_id in cluster_ids:
        cid = normalize_cluster_id(raw_id)
        if cid not in seen_c:
            seen_c.add(cid)
            normalized.append(cid)
    cluster_ids = normalized
    for cid in cluster_ids:
        vms = mapping.get(cid)
        if not vms:
            unknown.append(cid)
            continue
        per_cluster[cid] = list(vms)
        for host in vms:
            variants = [host]
            if include_fqdn and suffix and not host.endswith(suffix):
                variants.append(host + suffix)
            for item in variants:
                if item not in seen:
                    seen.add(item)
                    hosts.append(item)
    if unknown:
        known = ", ".join(sorted(mapping, key=lambda x: int(x[2:])))
        raise ValueError(
            "Unknown cluster(s) for %s: %s. Known: %s" % (site_name, ", ".join(unknown), known)
        )
    return {
        "site": site_name,
        "display_name": site_data.get("display_name") or site_name,
        "environment": site_data.get("environment") or "",
        "clusters": cluster_ids,
        "hosts": hosts,
        "per_cluster": per_cluster,
    }


def format_cluster_catalog(site: Optional[str] = None) -> str:
    cfg = load_cluster_config()
    lines = ["TKS NFT cluster → IMDG VM mapping", ""]
    wanted = resolve_site(site) if site else None
    for site_name, data in (cfg.get("sites") or {}).items():
        if wanted and site_name != wanted:
            continue
        lines.append("## %s" % (data.get("display_name") or site_name))
        lines.append("environment: `%s`" % (data.get("environment") or ""))
        lines.append("")
        lines.append("| Cluster | IMDG VMs |")
        lines.append("|---|---|")
        clusters = data.get("clusters") or {}
        for cid in sorted(clusters, key=lambda x: int(x[2:])):
            lines.append("| %s | %s |" % (cid, ", ".join(clusters[cid])))
        lines.append("")
    return "\n".join(lines)
