# AirflowAVMProc MCP

List, start, and stop Airflow AVM charging-control processes by running the documented `curl` login + AVM calls on a remote host through **unix-server** SSH.

## Tools

| Tool | AVM API | Page |
|------|---------|------|
| `list_environments` | — | Map env → unix-server `machine_name` + Airflow URL |
| `list_nft_clusters` | — | TKS_NFT_Cluster map: NFT site → CL1–CL19 → IMDG VMs (SRB, MKS) |
| `list_up_processes` | `POST /avm/v1/collectUpProcessList` | `/charging-control/stop-processes` |
| `list_down_processes` | `POST /avm/v1/collectDownProcessList` | `/charging-control/start-processes` |
| `stop_processes` | `POST /avm/v1/sendStopProcessCommand` | then wait and list DOWN for those SIDs |
| `start_processes` | `POST /avm/v1/sendStartProcessCommand` | then wait and list UP for those SIDs |

## Agent flow

1. Understand the environment (`list_environments`) or ask for the Airflow URL + unix-server machine name.
2. Notify: will perform **ACTION** on **ENVIRONMENT** with **Airflow URL**, username (default `admin`).
3. **Always ask for filters** (`hostName`, `clusters`+`site`, `processType`, `processName`) before listing. The list tools refuse the call until filters are passed or `no_filters=true`. NFT cluster names expand to every IMDG VM in those clusters (`tks_nft_clusters.json`). When using this MCP, load skill **TKS_NFT_Cluster** (`skills/tks-nft-cluster/SKILL.md`). Example: start IMDG_LOCATOR on CL1 and CL2 → start that process on all VMs in CL1 and CL2 where it is present.
4. Run the matching tool. Show table: `sid | processType | processName | status | host`.
5. For start/stop, get approval, then call with `confirm=true` and `sids` (or `all_matching=true`).
6. Start/stop wait 30 seconds, then verify against the opposite list.

If curl times out or returns empty, the MCP runs `oc get pods/deploy` for **airflow** and **avmrest** and reports whether they are deployed and Running.

Valid `processType`: `AGENT`, `IMDG_LOCATOR`, `IMDG_PWINFO`, `IMDG_RTN`, `IMDG_SERVER`, `HB_IMDG_LOADER`, `HB_FETCHER_LAZY`, `RCND`, `IMDG_VIEWER`, `MASD`, `AEM_CM`, `UHI`, `JAP`, `APP_SERVER`, `AC`, `IMDG_DELTA`, `IMDG_ALL`.

`sendStartProcessCommand` / `sendStopProcessCommand` return HTTP 200 with an empty body. That is success. Processes boot asynchronously.

Do not stop `AGENT` unless the user names that SID. Host AGENT must be Up before other processes will start.

## Default environment

`environments.json` → `TKS_IN08_ENV12`:

- unix-server machine: `JUMP`
- hop: `admin@incetks173`
- Airflow: `https://10.77.156.62:1031`
- user/password: `admin` / `admin`

## Cursor registration

Same Python + `UNIX_CONFIG_FILE` / `MCP_SECRETS_AES_KEY` as unix-server. Fragment: `mcp-d.json`.

Add to `%USERPROFILE%\.cursor\mcp.json`:

```json
"AirflowAVMProc": {
  "command": "C:\\Users\\sameerk\\AppData\\Local\\Microsoft\\WindowsApps\\python.exe",
  "args": ["C:\\GenAI\\Cursor\\mcps\\AirflowAVMProc\\server.py"],
  "env": {
    "UNIX_CONFIG_FILE": "C:\\Users\\sameerk\\.cursor\\mcp-servers\\mcp_servers\\unix-mcp-server-main\\config.json",
    "MCP_SECRETS_AES_KEY": "<same-as-unix-server>"
  }
}
```

Restart Cursor after registration. The server appears as `user-AirflowAVMProc`.
