import json
import shutil

DATA = r"C:\GenAI\Cursor\mcps\AirflowAVMProc\tks_nft_clusters.json"
TARGETS = [
    r"C:\GenAI\Cursor\mcps\AirflowAVMProc\skills\tks-nft-cluster\SKILL.md",
    r"C:\Users\sameerk\.cursor\skills\tks-nft-cluster\SKILL.md",
    r"C:\GenAI\Cursor\.cursor\skills\tks-nft-cluster\SKILL.md",
]

cfg = json.loads(open(DATA, encoding="utf-8").read())


def table(site):
    clusters = cfg["sites"][site]["clusters"]
    rows = ["| Cluster | IMDG VMs |", "|---|---|"]
    for cid in sorted(clusters, key=lambda x: int(x[2:])):
        rows.append("| %s | %s |" % (cid, ", ".join(clusters[cid])))
    return "\n".join(rows)


def count(site):
    clusters = cfg["sites"][site]["clusters"]
    return len(clusters), sum(len(v) for v in clusters.values())


srb_n, srb_vms = count("SRB")
mks_n, mks_vms = count("MKS")

body = """---
name: tks-nft-cluster
description: >-
  TKS_NFT_Cluster - maps Telkomsel NFT clusters (CL1-CL7, CL11-CL16) to IMDG VMs for SRB and
  MKS NFT sites. Load this skill whenever using the AirflowAVMProc MCP. Use when the user names
  NFT clusters, CL1/CL2, SRB NFT, MKS NFT, or asks to list/start/stop AVM processes by cluster.
---

# TKS_NFT_Cluster

Mandatory companion skill for **AirflowAVMProc**. Read this before any list/start/stop on an NFT site.

Canonical data: `mcps/AirflowAVMProc/tks_nft_clusters.json` (the MCP expands `clusters` itself).

Clusters are **CL1-CL7 and CL11-CL16**. There is no CL8, CL9, CL10 or CL17+. Each cluster holds
`imdgcu` and `imdgpw` VMs.

## When the user names clusters

1. Resolve **site**: SRB NFT -> `SRB` / env `SRB_NFT_ADMIN`. MKS NFT -> `MKS` / env `MKS_NFT_ADMIN`.
2. Expand each `CLn` to **all IMDG VMs** in that cluster (tables below).
3. Apply the requested action on **every host in those clusters**, wherever that process type exists.
   Do not stop at the first VM.
4. Pass MCP args: `environment`, `site`, `clusters` (e.g. `["CL1","CL2"]`), plus `processType`
   (e.g. `IMDG_LOCATOR`). Do not require the user to list VMs.
5. Show the expanded host list, then the AVM table (sid / processType / processName / status / host),
   grouped by cluster then host.

**Example:** start `IMDG_LOCATOR` on CL1 and CL2 -> start `IMDG_LOCATOR` on every VM in those clusters
that has that process (DOWN list -> start matching SIDs with `confirm=true` after approval).

Skip VMs where the process type is not present. Do not start/stop `AGENT` unless the user names those SIDs.

## MCP arguments

| Arg | Use |
|---|---|
| `site` | `SRB` or `MKS` |
| `clusters` | `["CL1","CL2"]` (also `cluster`, `CL-1`, `1`) |
| `hostNames` | optional extra hosts |
| `processType` | e.g. `IMDG_LOCATOR` |

`clusters` counts as a list filter. Call `list_nft_clusters` to dump the map.

## SRB NFT (env `SRB_NFT_ADMIN`) - {srb_n} clusters, {srb_vms} VMs

{srb_table}

## MKS NFT (env `MKS_NFT_ADMIN`) - {mks_n} clusters, {mks_vms} VMs

MKS mirrors SRB with the series swapped: MKS CL1-CL7 use the 200-series, CL11-CL16 the 100-series.

{mks_table}

MKS Airflow URL is not in `environments.json` yet. If the user targets MKS, pass
`unix_machine_name=MKS_NFT_ADMIN` and ask for `airflow_url` unless it has been added.
""".format(
    srb_n=srb_n,
    srb_vms=srb_vms,
    mks_n=mks_n,
    mks_vms=mks_vms,
    srb_table=table("SRB"),
    mks_table=table("MKS"),
)

primary = TARGETS[0]
open(primary, "w", encoding="utf-8").write(body)
for target in TARGETS[1:]:
    shutil.copyfile(primary, target)
    shutil.copyfile(DATA, target.replace("SKILL.md", "tks_nft_clusters.json"))
shutil.copyfile(DATA, primary.replace("SKILL.md", "tks_nft_clusters.json"))
print("written:", *TARGETS, sep="\n  ")
