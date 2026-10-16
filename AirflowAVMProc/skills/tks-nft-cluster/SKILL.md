---
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

## SRB NFT (env `SRB_NFT_ADMIN`) - 13 clusters, 106 VMs

| Cluster | IMDG VMs |
|---|---|
| CL1 | r1srbimdgcu101, r1srbimdgcu102, r1srbimdgcu103, r1srbimdgcu104, r1srbimdgcu105, r1srbimdgcu106, r1srbimdgcu107, r1srbimdgcu108, r1srbimdgcu109, r1srbimdgcu110, r1srbimdgpw101, r1srbimdgpw102, r1srbimdgpw103 |
| CL2 | r1srbimdgcu112, r1srbimdgcu113, r1srbimdgcu114, r1srbimdgcu115, r1srbimdgcu116, r1srbimdgcu117, r1srbimdgcu118, r1srbimdgcu119, r1srbimdgcu120, r1srbimdgcu121, r1srbimdgpw104, r1srbimdgpw105, r1srbimdgpw106 |
| CL3 | r1srbimdgcu123, r1srbimdgcu124, r1srbimdgcu125, r1srbimdgcu126, r1srbimdgcu127, r1srbimdgcu128, r1srbimdgcu129, r1srbimdgcu130, r1srbimdgcu131, r1srbimdgcu132, r1srbimdgpw107, r1srbimdgpw108, r1srbimdgpw109 |
| CL4 | r1srbimdgcu134, r1srbimdgcu135, r1srbimdgpw110, r1srbimdgpw111 |
| CL5 | r1srbimdgcu145, r1srbimdgcu146, r1srbimdgpw113, r1srbimdgpw114 |
| CL6 | r1srbimdgcu155, r1srbimdgcu157, r1srbimdgpw116, r1srbimdgpw117 |
| CL7 | r1srbimdgcu167, r1srbimdgcu168, r1srbimdgpw119, r1srbimdgpw120 |
| CL11 | r1srbimdgcu201, r1srbimdgcu202, r1srbimdgcu203, r1srbimdgcu204, r1srbimdgcu205, r1srbimdgcu206, r1srbimdgcu207, r1srbimdgcu208, r1srbimdgcu209, r1srbimdgcu210, r1srbimdgpw201, r1srbimdgpw202, r1srbimdgpw203 |
| CL12 | r1srbimdgcu212, r1srbimdgcu213, r1srbimdgcu214, r1srbimdgcu215, r1srbimdgcu216, r1srbimdgcu217, r1srbimdgcu218, r1srbimdgcu219, r1srbimdgcu220, r1srbimdgcu221, r1srbimdgpw204, r1srbimdgpw205, r1srbimdgpw206 |
| CL13 | r1srbimdgcu223, r1srbimdgcu224, r1srbimdgcu225, r1srbimdgcu226, r1srbimdgcu227, r1srbimdgcu228, r1srbimdgcu229, r1srbimdgcu230, r1srbimdgcu231, r1srbimdgcu232, r1srbimdgpw207, r1srbimdgpw208, r1srbimdgpw209 |
| CL14 | r1srbimdgcu234, r1srbimdgcu235, r1srbimdgpw210, r1srbimdgpw211 |
| CL15 | r1srbimdgcu245, r1srbimdgcu246, r1srbimdgpw213, r1srbimdgpw214 |
| CL16 | r1srbimdgcu256, r1srbimdgcu257, r1srbimdgpw216, r1srbimdgpw217 |

## MKS NFT (env `MKS_NFT_ADMIN`) - 13 clusters, 106 VMs

MKS mirrors SRB with the series swapped: MKS CL1-CL7 use the 200-series, CL11-CL16 the 100-series.

| Cluster | IMDG VMs |
|---|---|
| CL1 | r1mksimdgcu201, r1mksimdgcu202, r1mksimdgcu203, r1mksimdgcu204, r1mksimdgcu205, r1mksimdgcu206, r1mksimdgcu207, r1mksimdgcu208, r1mksimdgcu209, r1mksimdgcu210, r1mksimdgpw201, r1mksimdgpw202, r1mksimdgpw203 |
| CL2 | r1mksimdgcu212, r1mksimdgcu213, r1mksimdgcu214, r1mksimdgcu215, r1mksimdgcu216, r1mksimdgcu217, r1mksimdgcu218, r1mksimdgcu219, r1mksimdgcu220, r1mksimdgcu221, r1mksimdgpw204, r1mksimdgpw205, r1mksimdgpw206 |
| CL3 | r1mksimdgcu223, r1mksimdgcu224, r1mksimdgcu225, r1mksimdgcu226, r1mksimdgcu227, r1mksimdgcu228, r1mksimdgcu229, r1mksimdgcu230, r1mksimdgcu231, r1mksimdgcu232, r1mksimdgpw207, r1mksimdgpw208, r1mksimdgpw209 |
| CL4 | r1mksimdgcu234, r1mksimdgcu235, r1mksimdgpw210, r1mksimdgpw211 |
| CL5 | r1mksimdgcu245, r1mksimdgcu246, r1mksimdgpw213, r1mksimdgpw214 |
| CL6 | r1mksimdgcu256, r1mksimdgcu257, r1mksimdgpw216, r1mksimdgpw217 |
| CL7 | r1mksimdgcu267, r1mksimdgcu268, r1mksimdgpw219, r1mksimdgpw220 |
| CL11 | r1mksimdgcu101, r1mksimdgcu102, r1mksimdgcu103, r1mksimdgcu104, r1mksimdgcu105, r1mksimdgcu106, r1mksimdgcu107, r1mksimdgcu108, r1mksimdgcu109, r1mksimdgcu110, r1mksimdgpw101, r1mksimdgpw102, r1mksimdgpw103 |
| CL12 | r1mksimdgcu112, r1mksimdgcu113, r1mksimdgcu114, r1mksimdgcu115, r1mksimdgcu116, r1mksimdgcu117, r1mksimdgcu118, r1mksimdgcu119, r1mksimdgcu120, r1mksimdgcu121, r1mksimdgpw104, r1mksimdgpw105, r1mksimdgpw106 |
| CL13 | r1mksimdgcu123, r1mksimdgcu124, r1mksimdgcu125, r1mksimdgcu126, r1mksimdgcu127, r1mksimdgcu128, r1mksimdgcu129, r1mksimdgcu130, r1mksimdgcu131, r1mksimdgcu132, r1mksimdgpw107, r1mksimdgpw108, r1mksimdgpw109 |
| CL14 | r1mksimdgcu134, r1mksimdgcu135, r1mksimdgpw110, r1mksimdgpw111 |
| CL15 | r1mksimdgcu145, r1mksimdgcu146, r1mksimdgpw113, r1mksimdgpw114 |
| CL16 | r1mksimdgcu155, r1mksimdgcu157, r1mksimdgpw116, r1mksimdgpw117 |

MKS Airflow URL is not in `environments.json` yet. If the user targets MKS, pass
`unix_machine_name=MKS_NFT_ADMIN` and ask for `airflow_url` unless it has been added.
