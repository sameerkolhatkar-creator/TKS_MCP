# PET Check MCP Server
#Developed by - Sameer Kolhatkar
##################################

MCP server for PET environment operations. Uses the **unix-server** SSH stack to connect to PET hosts and run OCP, WebLogic, and daemon commands.

## Tools

| Tool | Description |
|------|-------------|
| `tck8s_pods` | Stop/start/restart/check K8S pods in `tks-in02-pet1-tc` via PET_RT_ADMIN |
| `tcms_pods` | Stop/start/restart/check TCMS microservice pods in `tc-product-k8s-tks-in02-pet1` |
| `weblogic_server` | Stop/start/restart/check WebLogic ABP-FULL on CM servers |
| `daemon` | Stop/start/restart/check daemons from `.Op9DmnMonitor.cfg` |
| `list_pet_daemons` | List daemon COMMON_NAME entries |
| `list_cm_servers` | List PET CM WL instances with `machine_name`, `user@host`, and `cm_type` |
| `cm_wl_properties` | List/read/preview/apply CM WebLogic application property files |

## TCK8S Helm charts

On **PET_RT_ADMIN**, charts live at `${HOME}/helm-charts`:

| Path | Contents |
|------|----------|
| `helm-charts/global` | Global values — charts, configs, krb5, certificates |
| `helm-charts/deployments` | TCK8S deployments |
| `helm-charts/services` | TCK8S service configurations |

## TCMS pods

All TCMS pods are microservices.

## CM WebLogic instances

Canonical inventory is `CM_WL_INSTANCES` in `pet_check/constants.py` (45 instances).  
`list_cm_servers` returns `machine_name`, `user@host`, and `cm_type`.

| cm_type | hosts |
|---------|-------|
| prepaid | tcslocwleapp1–4 |
| internal_api | tcslocwleapp5–6 |
| webservices | tcslocwleapp7–8 |
| lock_server / collection_scanner / srm | tcslocwleapp9–11 |
| postpaid | tcsloswleapp1–2, tcsloawleapp1–2 |

Examples:

| machine_name | user@host |
|--------------|-----------|
| CM31-Server_CM_Prepaid | ptcmwl11@tcslocwleapp1 |
| CM122-Server_Collection_Scanner | ptcmwl102@tcslocwleapp10 |
| CM141-Server_CM_Postpaid | ptsrwl11@tcsloswleapp1 |

CM WebLogic Scripts/properties paths (per user home):

- Properties: `${HOME}/JEE/ABPProduct/config_files/ABP-FULL/ABPServer`
- Scripts / setenv: `${HOME}/JEE/ABPProduct/scripts/ABP-FULL`

## CM WebLogic property files

Application properties live at:

`${HOME}/JEE/ABPProduct/config_files/ABP-FULL/ABPServer`

When updating property files:

1. **Preview per file** — call `cm_wl_properties` with `action=preview` and show the user the proposed diff for each file.
2. **Obtain approval** — get explicit user approval for each file before applying.
3. **Apply with backup** — call `action=apply` with `approved=true`. A timestamped backup is created automatically; backup paths are highlighted in the response (`>>> BACKUP CREATED: ... <<<`).
4. **One file at a time** — repeat preview/approve/apply for each property file being changed.

## Setup

Uses the same `UNIX_CONFIG_FILE` and `MCP_SECRETS_AES_KEY` as unix-server.

Add to `~/.cursor/mcp.json`:

```json
"pet-check": {
  "command": "C:\\Users\\sameerk\\AppData\\Local\\Microsoft\\WindowsApps\\python.exe",
  "args": [
    "C:\\Users\\sameerk\\.cursor\\mcp-servers\\mcp_servers\\pet-check-mcp-server-main\\server.py"
  ],
  "env": {
    "UNIX_CONFIG_FILE": "C:\\Users\\sameerk\\.cursor\\mcp-servers\\mcp_servers\\unix-mcp-server-main\\config.json",
    "MCP_SECRETS_AES_KEY": "<same-as-unix-server>"
  }
}
```

## Examples

- Check CR pods: `tck8s_pods` action=`check`, resource_name=`cr1`
- Restart TCMS deployment: `tcms_pods` action=`restart`, resource_name=`usage-management`
- Ping WebLogic: `weblogic_server` action=`check`, cm_server=`CM31`, cm_type=`prepaid`
- Clean restart WL: `weblogic_server` action=`restart`, machine_name=`CM31-Server_CM_Prepaid`, clean_cache=`true`
- Check daemon: `daemon` action=`check`, common_name=`MY_DAEMON`
- List CM property files: `cm_wl_properties` action=`list`, cm_server=`CM31`, cm_type=`prepaid`
- Preview property change: `cm_wl_properties` action=`preview`, file_name=`application.properties`, changes=`[{key: foo, value: bar}]`
- Apply after approval: `cm_wl_properties` action=`apply`, file_name=`application.properties`, changes=`[...]`, approved=`true`
