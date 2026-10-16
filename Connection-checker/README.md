# Connection-checker

Portable bastion tool that checks TCP connectivity **from source VMs to destination IP:port**.

It reads a hash-separated input file, SSHes to each source host as `Source_User`, runs a **time-bounded telnet** (it will not hang at a Connected prompt), and writes a filterable HTML report.

Version: **1.1.1**

## Requirements

**Bastion** (where you run the script)

- bash 4+
- OpenSSH client (`ssh`)
- Key-based SSH to every source host (BatchMode; no password prompt)
- Write access for the HTML report

**Source VMs** (hosts you SSH into)

- Login shell that can run bash
- `telnet` (preferred)
- GNU `timeout` (preferred; a watchdog is used if it is missing)
- Fallbacks if telnet is missing: `nc` (netcat) or bash `/dev/tcp`

**Network**

- Bastion can reach `Source_IP` on the SSH port (default 22)
- The test itself is whether the **source** can reach `Destination_IP:Destination_Port`

## Quick start

```bash
chmod +x connection-checker.sh
./connection-checker.sh -i sample-input.txt
```

The report is written as `connection-checker-report-YYYYMMDD-HHMMSS.html` in the current directory unless you pass `-o`.

Preview expansion without SSH or telnet:

```bash
./connection-checker.sh -i sample-input.txt --dry-run
```

## Input file

Plain text. Columns separated by `#`. Four columns, in order:

```text
Source_User#Source_IP#Destination_IP#Destination_Port
```

Rules:

- Blank lines are ignored
- Lines whose first non-space character is `#` are comments
- A header row named `Source_User` / `Source_IP` / ... is skipped
- Surrounding whitespace is trimmed
- CRLF (Windows) line endings are accepted
- The same `Source_User` is applied to every address in a `Source_IP` range

A sample file is included: `sample-input.txt`.

### IP format (`Source_IP` and `Destination_IP`)

| Form | Example |
| --- | --- |
| Single IPv4 | `10.17.52.10` |
| Inclusive IPv4 range | `10.17.52.10-10.17.52.239` |

Range expansion is a contiguous 32-bit IPv4 sequence (not only the last octet).

### Port format (`Destination_Port`)

| Form | Example |
| --- | --- |
| Single | `1025` |
| Comma-separated | `1025,1050,22` |
| Inclusive range | `1025-1050` |
| Mixed | `22,80,1025-1030` |

### Sample

```text
# comment
Source_User#Source_IP#Destination_IP#Destination_Port
appuser#10.17.52.10#10.17.60.5#22
appuser#10.17.52.10-10.17.52.12#10.17.60.5#1025,1050
bluser#10.17.52.20#10.17.60.8-10.17.60.9#1025-1027
```

## Usage

```text
connection-checker.sh -i <input.txt> [-o report.html] [options]
```

| Option | Description |
| --- | --- |
| `-i`, `--input FILE` | Input file (required) |
| `-o`, `--output FILE` | HTML report path (default: `connection-checker-report-YYYYMMDD-HHMMSS.html`) |
| `-t`, `--timeout SEC` | Telnet probe timeout in seconds (default: 5) |
| `--ssh-timeout SEC` | SSH connect timeout in seconds (default: 10) |
| `-p`, `--ssh-port PORT` | SSH port on source hosts (default: 22) |
| `-k`, `--identity FILE` | SSH private key (`ssh -i`) |
| `--ssh-strict MODE` | `StrictHostKeyChecking`: `accept-new` (default), `no`, or `yes` |
| `--max-expand N` | Deprecated; ignored. Expansion is unlimited |
| `--dry-run` | Expand and print tuples; do not SSH or telnet |
| `-h`, `--help` | Show help |
| `-V`, `--version` | Show version |

Examples:

```bash
./connection-checker.sh -i hosts.txt
./connection-checker.sh -i hosts.txt -o /tmp/cc-report.html -t 3
./connection-checker.sh -i hosts.txt -k ~/.ssh/id_rsa --ssh-strict no
./connection-checker.sh -i hosts.txt --dry-run
```

## How it works

1. Expand destination IP/port pairs for one input row.
2. Expand source IPs one at a time and start each source worker immediately.
3. Run at most **3** source-IP workers in parallel.
4. SSH once to each source:
   - SSH fail / timeout / auth fail → every dest for that source is **N.A**
   - SSH ok → for each dest:port, run a time-bounded telnet (or fallback)
5. Telnet is forced to exit (`timeout`/watchdog + closed stdin). It does not sit at a Connected prompt.
6. Merge worker results and write the HTML report.

There is **no tuple expansion cap**. Large ranges can produce very large HTML files.

## Report statuses

The HTML report includes a legend, KPI counts, and column filters.

| Status | Color | Meaning |
| --- | --- | --- |
| **PASS** | Green | TCP connect from source to dest:port succeeded |
| **Down** | Grey | Source reachable; dest:port returned `Connection refused` |
| **FAIL** | Orange | Source reachable, but dest:port did not accept (timeout, filtered, or probe unusable) |
| **N.A** | Yellow | Source host not reachable over SSH (or auth/session failed) |

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Completed (report written). Individual FAIL / Down / N.A rows are in the report |
| 1 | Usage / input / expansion error |
| 2 | Runtime error (cannot write report, etc.) |
