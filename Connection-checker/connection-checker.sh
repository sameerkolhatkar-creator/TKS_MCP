#!/usr/bin/env bash
# Connection-checker
# Run from a bastion VM: SSH to each source host and probe destination:port with a
# time-bounded telnet (never hangs waiting for input).
#Created By Sameer K 
###############################
set -u

CC_WORK_DIR=""
cleanup() {
	if [[ -n "${CC_WORK_DIR-}" && -d "$CC_WORK_DIR" ]]; then
		rm -rf "$CC_WORK_DIR"
	fi
}
trap cleanup EXIT

TOOL_NAME="Connection-checker"
TOOL_VERSION="1.1.1"

INPUT_FILE=""
OUTPUT_FILE=""
TELNET_TIMEOUT=5
SSH_CONNECT_TIMEOUT=10
SSH_PORT=22
SSH_IDENTITY=""
SSH_STRICT="accept-new"
MAX_PARALLEL_SOURCES=3
DRY_RUN=0

usage() {
	cat <<'EOF'
Connection-checker  v1.1.1
==========================
Portable bastion tool. Reads a hash-separated input file, SSHes to each
source VM as Source_User, and runs a time-bounded telnet from that source
to every Destination_IP:Destination_Port combination. Writes a filterable
HTML report.

REQUIREMENTS
  Bastion (where this script runs)
    - bash 4+ (associative arrays)
    - OpenSSH client (ssh)
    - Key-based SSH from the bastion to every source host
      (BatchMode; no interactive password prompt)
    - Write access for the HTML report

  Source VMs (the hosts you SSH into)
    - Login shell that can run bash
    - telnet client (preferred)
    - timeout from GNU coreutils (preferred; a watchdog fallback is used
      if timeout is missing)
    - Optional fallbacks if telnet is missing: nc (netcat) or bash /dev/tcp

  Network
    - Bastion can reach Source_IP on the SSH port (default 22)
    - Source can reach Destination_IP:Destination_Port (this is what is tested)

INPUT FILE
  Plain text. Columns separated by '#' (hash). Four columns, in order:

    Source_User # Source_IP # Destination_IP # Destination_Port

  Rules
    - Blank lines are ignored
    - Lines whose first non-space character is '#' are comments
    - A header row named Source_User / Source_IP / ... is skipped
    - Surrounding whitespace is trimmed
    - CRLF (Windows) line endings are accepted
    - The same Source_User is applied to every address in a Source_IP range

  IP format (Source_IP and Destination_IP)
    - Single IPv4:           10.17.52.10
    - Inclusive IPv4 range:  10.17.52.10-10.17.52.239
    Range is expanded as a contiguous 32-bit IPv4 sequence (not only the
    last octet). Same user is used for every source address in the range.

  Port format (Destination_Port)
    - Single:           1025
    - Comma-separated:  1025,1050,22
    - Inclusive range:  1025-1050
    - Mixed:            22,80,1025-1030

FLOW
  1. Expand the destination IP/port mapping for one input row
  2. Expand source IPs one at a time and immediately start each source worker
  3. Run at most 3 source-IP workers in parallel
  4. SSH once to each source
       - SSH fail / timeout / auth fail  -> every dest for that source is N.A
       - SSH ok -> for each dest:port, run telnet with a hard timeout
  5. Telnet is forced to exit (timeout/watchdog + closed stdin). It will
     not sit at a Connected prompt.
  6. Merge worker results and write the HTML report

  Expansion has no tuple limit. Large runs can create very large HTML files.

TELNET STATUS (report)
  PASS   GREEN    TCP connect from source to dest:port succeeded
  Down   GREY     Source reachable; dest:port returned Connection refused
  FAIL   ORANGE   Source reachable, but dest:port did not accept the connect
                  (filtered, timeout, or telnet missing/unusable)
  N.A    YELLOW   Source host not reachable over SSH (or auth/session failed)

USAGE
  connection-checker.sh -i <input.txt> [-o report.html] [options]

OPTIONS
  -i, --input FILE         Input file (required)
  -o, --output FILE        HTML report path
                           default: connection-checker-report-YYYYMMDD-HHMMSS.html
  -t, --timeout SEC        Telnet probe timeout in seconds (default: 5)
      --ssh-timeout SEC    SSH connect timeout in seconds (default: 10)
  -p, --ssh-port PORT      SSH port on source hosts (default: 22)
  -k, --identity FILE      SSH private key (passed as ssh -i)
      --ssh-strict MODE    StrictHostKeyChecking: accept-new|no|yes
                           (default: accept-new)
      --max-expand N       Deprecated compatibility option; N is ignored
                           because expansion is unlimited
      --dry-run            Expand and print tuples; do not SSH or telnet
  -h, --help               Show this help
  -V, --version            Show version

EXAMPLES
  ./connection-checker.sh -i hosts.txt
  ./connection-checker.sh -i hosts.txt -o /tmp/cc-report.html -t 3
  ./connection-checker.sh -i hosts.txt -k ~/.ssh/id_rsa --ssh-strict no
  ./connection-checker.sh -i hosts.txt --dry-run

SAMPLE INPUT
  # comment
  Source_User#Source_IP#Destination_IP#Destination_Port
  appuser#10.17.52.10#10.17.60.5#22
  appuser#10.17.52.10-10.17.52.12#10.17.60.5#1025,1050
  bluser#10.17.52.20#10.17.60.8-10.17.60.9#1025-1027

EXIT CODES
  0  Completed (report written). Individual FAIL/Down/N.A rows are in the report.
  1  Usage / input / expansion error
  2  Runtime error (cannot write report, etc.)
EOF
}

log()  { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*" >&2; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

trim() {
	local s="${1-}"
	s="${s#"${s%%[![:space:]]*}"}"
	s="${s%"${s##*[![:space:]]}"}"
	printf '%s' "$s"
}

html_escape() {
	local s="${1-}"
	s="${s//&/&amp;}"
	s="${s//</&lt;}"
	s="${s//>/&gt;}"
	s="${s//\"/&quot;}"
	s="${s//\'/&#39;}"
	printf '%s' "$s"
}

valid_ipv4() {
	local ip="$1"
	local a b c d
	[[ "$ip" =~ ^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$ ]] || return 1
	a="${BASH_REMATCH[1]}"; b="${BASH_REMATCH[2]}"
	c="${BASH_REMATCH[3]}"; d="${BASH_REMATCH[4]}"
	(( a <= 255 && b <= 255 && c <= 255 && d <= 255 ))
}

ip_to_int() {
	local ip="$1"
	local a b c d
	IFS=. read -r a b c d <<< "$ip"
	printf '%s' "$(( a * 16777216 + b * 65536 + c * 256 + d ))"
}

int_to_ip() {
	local n="$1"
	printf '%s.%s.%s.%s' \
		"$(( (n >> 24) & 255 ))" \
		"$(( (n >> 16) & 255 ))" \
		"$(( (n >> 8) & 255 ))" \
		"$(( n & 255 ))"
}

expand_ips() {
	local spec="$1"
	local start_ip end_ip start_n end_n n tmp
	if [[ "$spec" == *-* ]]; then
		start_ip="$(trim "${spec%%-*}")"
		end_ip="$(trim "${spec#*-}")"
		valid_ipv4 "$start_ip" || die "Invalid start IP: $spec"
		valid_ipv4 "$end_ip"   || die "Invalid end IP: $spec"
		start_n="$(ip_to_int "$start_ip")"
		end_n="$(ip_to_int "$end_ip")"
		if (( start_n > end_n )); then
			tmp=$start_n; start_n=$end_n; end_n=$tmp
		fi
		for (( n = start_n; n <= end_n; n++ )); do
			int_to_ip "$n"
			printf '\n'
		done
	else
		valid_ipv4 "$spec" || die "Invalid IP: $spec"
		printf '%s\n' "$spec"
	fi
}

expand_ports() {
	local spec="$1"
	local token start end p
	IFS=',' read -ra tokens <<< "$spec"
	for token in "${tokens[@]}"; do
		token="$(trim "$token")"
		[[ -z "$token" ]] && continue
		if [[ "$token" == *-* ]]; then
			start="$(trim "${token%%-*}")"
			end="$(trim "${token#*-}")"
			[[ "$start" =~ ^[0-9]+$ && "$end" =~ ^[0-9]+$ ]] || die "Invalid port range: $token"
			(( start >= 1 && start <= 65535 && end >= 1 && end <= 65535 )) || die "Port out of range: $token"
			if (( start > end )); then
				p=$start; start=$end; end=$p
			fi
			for (( p = start; p <= end; p++ )); do
				printf '%s\n' "$p"
			done
		else
			[[ "$token" =~ ^[0-9]+$ ]] || die "Invalid port: $token"
			(( token >= 1 && token <= 65535 )) || die "Port out of range: $token"
			printf '%s\n' "$token"
		fi
	done
}

parse_args() {
	while [[ $# -gt 0 ]]; do
		case "$1" in
			-h|--help) usage; exit 0 ;;
			-V|--version) printf '%s %s\n' "$TOOL_NAME" "$TOOL_VERSION"; exit 0 ;;
			-i|--input)
				[[ $# -ge 2 ]] || die "$1 requires a value"
				INPUT_FILE="$2"; shift 2 ;;
			-o|--output)
				[[ $# -ge 2 ]] || die "$1 requires a value"
				OUTPUT_FILE="$2"; shift 2 ;;
			-t|--timeout)
				[[ $# -ge 2 ]] || die "$1 requires a value"
				TELNET_TIMEOUT="$2"; shift 2 ;;
			--ssh-timeout)
				[[ $# -ge 2 ]] || die "$1 requires a value"
				SSH_CONNECT_TIMEOUT="$2"; shift 2 ;;
			-p|--ssh-port)
				[[ $# -ge 2 ]] || die "$1 requires a value"
				SSH_PORT="$2"; shift 2 ;;
			-k|--identity)
				[[ $# -ge 2 ]] || die "$1 requires a value"
				SSH_IDENTITY="$2"; shift 2 ;;
			--ssh-strict)
				[[ $# -ge 2 ]] || die "$1 requires a value"
				SSH_STRICT="$2"; shift 2 ;;
			--max-expand)
				[[ $# -ge 2 ]] || die "$1 requires a value"
				log "WARN: --max-expand is deprecated and ignored; expansion is unlimited"
				shift 2 ;;
			--dry-run) DRY_RUN=1; shift ;;
			--) shift; break ;;
			-*) die "Unknown option: $1 (try --help)" ;;
			*) die "Unexpected argument: $1 (try --help)" ;;
		esac
	done
	[[ -n "$INPUT_FILE" ]] || die "Input file is required. Use -i FILE or --help"
	[[ -f "$INPUT_FILE" ]] || die "Input file not found: $INPUT_FILE"
	[[ "$TELNET_TIMEOUT" =~ ^[0-9]+$ && "$TELNET_TIMEOUT" -ge 1 ]] || die "Invalid --timeout"
	[[ "$SSH_CONNECT_TIMEOUT" =~ ^[0-9]+$ && "$SSH_CONNECT_TIMEOUT" -ge 1 ]] || die "Invalid --ssh-timeout"
	[[ "$SSH_PORT" =~ ^[0-9]+$ && "$SSH_PORT" -ge 1 && "$SSH_PORT" -le 65535 ]] || die "Invalid --ssh-port"
	case "$SSH_STRICT" in accept-new|no|yes) ;; *) die "Invalid --ssh-strict (accept-new|no|yes)" ;; esac
	if [[ -z "$OUTPUT_FILE" ]]; then
		OUTPUT_FILE="connection-checker-report-$(date '+%Y%m%d-%H%M%S').html"
	fi
}

build_ssh_opts() {
	SSH_OPTS=(
		-n
		-o "BatchMode=yes"
		-o "ConnectTimeout=${SSH_CONNECT_TIMEOUT}"
		-o "ConnectionAttempts=1"
		-o "ServerAliveInterval=2"
		-o "ServerAliveCountMax=2"
		-o "StrictHostKeyChecking=${SSH_STRICT}"
		-o "LogLevel=ERROR"
		-o "PreferredAuthentications=publickey"
		-p "$SSH_PORT"
	)
	if [[ -n "$SSH_IDENTITY" ]]; then
		[[ -f "$SSH_IDENTITY" ]] || die "SSH identity file not found: $SSH_IDENTITY"
		SSH_OPTS+=(-i "$SSH_IDENTITY")
	fi
}

# Remote probe script: always exits. Prefers timeout+telnet.
# Args: timeout dest port
# Prints PASS, Down, or FAIL
remote_probe_fn='
probe() {
  t="$1"; dest="$2"; port="$3"
  out=""
  if command -v timeout >/dev/null 2>&1 && command -v telnet >/dev/null 2>&1; then
    out=$(timeout -s KILL "$t" telnet "$dest" "$port" </dev/null 2>&1 || true)
  elif command -v telnet >/dev/null 2>&1; then
    out=$(telnet "$dest" "$port" </dev/null 2>&1 &
      _pid=$!
      (sleep "$t"; kill -KILL "$_pid" >/dev/null 2>&1) &
      _w=$!
      wait "$_pid" >/dev/null 2>&1 || true
      kill -KILL "$_w" >/dev/null 2>&1 || true
      wait "$_w" >/dev/null 2>&1 || true
    )
  elif command -v nc >/dev/null 2>&1; then
    out=$(nc -z -w "$t" "$dest" "$port" 2>&1) && { echo PASS; return; }
  elif command -v bash >/dev/null 2>&1; then
    out=$(bash -c "exec 3<>/dev/tcp/$dest/$port" 2>&1) && { echo PASS; return; }
  else
    echo FAIL; return
  fi
  if printf "%s\n" "$out" | grep -qiE "Connected to|Escape character|Connected"; then
    echo PASS
  elif printf "%s\n" "$out" | grep -qiE "Connection refused"; then
    echo Down
  else
    echo FAIL
  fi
}
'

# Wait for the oldest worker when all three source slots are occupied.
wait_for_source_slot() {
	local pid
	if (( ${#ACTIVE_PIDS[@]} < MAX_PARALLEL_SOURCES )); then
		return 0
	fi
	pid="${ACTIVE_PIDS[0]}"
	if ! wait "$pid"; then
		log "WARN: source worker PID $pid exited unexpectedly"
	fi
	ACTIVE_PIDS=("${ACTIVE_PIDS[@]:1}")
}

wait_for_all_sources() {
	local pid
	for pid in "${ACTIVE_PIDS[@]}"; do
		if ! wait "$pid"; then
			log "WARN: source worker PID $pid exited unexpectedly"
		fi
	done
	ACTIVE_PIDS=()
}

# Stream input by source IP. A worker starts as soon as its source IP and
# destination mapping are ready; input expansion continues while it runs.
process_input() {
	local line raw user sip dip dport extra lineno=0
	local src_ip dest_ip port pair_count total=0 source_count=0 job_id=0
	local pairs_file result_file
	while IFS= read -r raw || [[ -n "$raw" ]]; do
		lineno=$((lineno + 1))
		line="${raw%$'\r'}"
		line="$(trim "$line")"
		[[ -z "$line" ]] && continue
		[[ "$line" == \#* ]] && continue
		IFS='#' read -r user sip dip dport extra <<< "$line"
		user="$(trim "${user-}")"
		sip="$(trim "${sip-}")"
		dip="$(trim "${dip-}")"
		dport="$(trim "${dport-}")"
		if [[ "${user,,}" == "source_user" ]]; then
			continue
		fi
		[[ -n "$user" && -n "$sip" && -n "$dip" && -n "$dport" ]] \
			|| die "Line $lineno: expected 4 hash-separated columns (got: $line)"
		[[ -z "${extra-}" ]] || log "WARN line $lineno: extra columns ignored"

		# Destination mappings are read-only and shared by every source worker
		# generated from this input row.
		pairs_file="${CC_WORK_DIR}/pairs-line-${lineno}.txt"
		: > "$pairs_file"
		pair_count=0
		while IFS= read -r dest_ip; do
			[[ -z "$dest_ip" ]] && continue
			while IFS= read -r port; do
				[[ -z "$port" ]] && continue
				printf '%s|%s\n' "$dest_ip" "$port" >> "$pairs_file"
				pair_count=$((pair_count + 1))
			done < <(expand_ports "$dport")
		done < <(expand_ips "$dip")
		(( pair_count > 0 )) || die "Line $lineno produced no destination/port pairs"

		while IFS= read -r src_ip; do
			[[ -z "$src_ip" ]] && continue
			source_count=$((source_count + 1))
			total=$((total + pair_count))
			if [[ "$DRY_RUN" -eq 1 ]]; then
				while IFS='|' read -r dest_ip port; do
					printf '%s|%s|%s|%s\n' "$user" "$src_ip" "$dest_ip" "$port"
				done < "$pairs_file"
				continue
			fi

			wait_for_source_slot
			job_id=$((job_id + 1))
			result_file="${CC_WORK_DIR}/result-$(printf '%08d' "$job_id").txt"
			RESULT_FILES+=("$result_file")
			run_source_batch "$user" "$src_ip" "$pairs_file" > "$result_file" &
			ACTIVE_PIDS+=("$!")
		done < <(expand_ips "$sip")
	done < "$INPUT_FILE"
	(( total > 0 )) || die "No probe tuples produced from $INPUT_FILE"
	log "Mapped $total probe tuple(s) across $source_count source IP execution(s)"
}

ssh_probe_source() {
	local user="$1" src="$2"
	local rc=0
	ssh "${SSH_OPTS[@]}" "${user}@${src}" "echo __CC_OK__" >/dev/null 2>&1 || rc=$?
	if [[ $rc -eq 0 ]]; then
		printf '1'
	else
		printf '0'
	fi
}

# Run all dest:port probes for one source in a single SSH session.
run_source_batch() {
	local user="$1" src="$2"
	local pairs_file="$3"
	local reachable
	reachable="$(ssh_probe_source "$user" "$src")"
	if [[ "$reachable" != "1" ]]; then
		log "Source not reachable: ${user}@${src} -> N.A for all destinations"
		while IFS='|' read -r dest port; do
			[[ -z "${dest-}" ]] && continue
			printf '%s|%s|%s|%s|N.A\n' "$user" "$src" "$dest" "$port"
		done < "$pairs_file"
		return 0
	fi
	log "Probing from ${user}@${src} ($(wc -l < "$pairs_file" | tr -d ' ') dest/port pair(s))"
	local ssh_run_opts=()
	local opt
	for opt in "${SSH_OPTS[@]}"; do
		[[ "$opt" == "-n" ]] && continue
		ssh_run_opts+=("$opt")
	done

	local remote_out rc=0
	remote_out="$(
		{
			printf '%s\n' "$remote_probe_fn"
			printf 'T=%s\n' "$TELNET_TIMEOUT"
			cat <<'REMOTE_LOOP'
while IFS= read -r line || [ -n "$line" ]; do
  [ -z "$line" ] && continue
  dest=${line%%|*}
  port=${line#*|}
  st=$(probe "$T" "$dest" "$port")
  printf "%s|%s|%s\n" "$dest" "$port" "$st"
done <<'PAIRS'
REMOTE_LOOP
			cat "$pairs_file"
			printf '%s\n' 'PAIRS'
		} | ssh "${ssh_run_opts[@]}" "${user}@${src}" "bash -s"
	)" || rc=$?
	if [[ $rc -ne 0 ]]; then
		log "SSH session failed mid-run for ${user}@${src}; marking remaining as N.A"
		while IFS='|' read -r dest port; do
			[[ -z "${dest-}" ]] && continue
			printf '%s|%s|%s|%s|N.A\n' "$user" "$src" "$dest" "$port"
		done < "$pairs_file"
		return 0
	fi

	declare -A got=()
	while IFS='|' read -r dest port st || [[ -n "${dest-}" ]]; do
		[[ -z "${dest-}" ]] && continue
		st="$(trim "$st")"
		case "$st" in PASS|FAIL|Down) ;; *) st="FAIL" ;; esac
		got["${dest}|${port}"]=1
		printf '%s|%s|%s|%s|%s\n' "$user" "$src" "$dest" "$port" "$st"
	done <<< "$remote_out"

	while IFS='|' read -r dest port; do
		[[ -z "${dest-}" ]] && continue
		if [[ -z "${got[${dest}|${port}]+x}" ]]; then
			printf '%s|%s|%s|%s|FAIL\n' "$user" "$src" "$dest" "$port"
		fi
	done < "$pairs_file"
}

write_html() {
	local results="$1"
	local out="$2"
	local generated total pass fail down na
	generated="$(date '+%Y-%m-%d %H:%M:%S %Z')"
	total=$(grep -c . "$results" 2>/dev/null || true)
	pass=$(grep -c '|PASS$' "$results" 2>/dev/null || true)
	fail=$(grep -c '|FAIL$' "$results" 2>/dev/null || true)
	down=$(grep -c '|Down$' "$results" 2>/dev/null || true)
	na=$(grep -c '|N\.A$' "$results" 2>/dev/null || true)
	total=${total:-0}; pass=${pass:-0}; fail=${fail:-0}; down=${down:-0}; na=${na:-0}

	{
		cat <<EOF
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${TOOL_NAME} report</title>
<style>
  :root { --bg:#0f172a; --card:#1e293b; --text:#e2e8f0; --muted:#94a3b8; --line:#334155; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: Segoe UI, Tahoma, sans-serif; background:var(--bg); color:var(--text); }
  header { padding:20px 24px 8px; }
  h1 { margin:0 0 6px; font-size:22px; }
  .meta { color:var(--muted); font-size:13px; }
  .kpis { display:flex; gap:12px; padding:12px 24px 16px; flex-wrap:wrap; }
  .kpi { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 16px; min-width:110px; }
  .kpi b { display:block; font-size:22px; }
  .kpi span { color:var(--muted); font-size:12px; }
  .kpi.pass b { color:#4ade80; }
  .kpi.fail b { color:#fb923c; }
  .kpi.down b { color:#9ca3af; }
  .kpi.na b { color:#facc15; }
  .wrap { padding:0 24px 32px; }
  table { width:100%; border-collapse:collapse; background:var(--card); border-radius:10px; overflow:hidden; }
  th, td { padding:8px 10px; text-align:left; border-bottom:1px solid var(--line); font-size:13px; }
  th { background:#0b1220; position:sticky; top:0; z-index:2; }
  tr.filters th { background:#111827; position:sticky; top:34px; z-index:1; font-weight:normal; }
  .filters input, .filters select {
    width:100%; background:#0f172a; color:var(--text); border:1px solid var(--line);
    border-radius:6px; padding:6px 8px;
  }
  .st { display:inline-block; min-width:64px; text-align:center; font-weight:700; border-radius:999px; padding:3px 10px; color:#111; }
  .st-PASS { background:#4ade80; }
  .st-FAIL { background:#fb923c; }
  .st-Down { background:#9ca3af; }
  .st-NA  { background:#facc15; }
  .legend { display:flex; gap:16px 24px; flex-wrap:wrap; padding:10px 24px 4px; align-items:flex-start; }
  .legend-item { display:flex; gap:10px; align-items:flex-start; max-width:360px; font-size:12px; color:var(--muted); line-height:1.4; }
  .legend-item .st { margin-top:1px; flex-shrink:0; }
  tr.hide { display:none; }
  .count { color:var(--muted); font-size:12px; padding:8px 0 0; }
</style>
</head>
<body>
<header>
  <h1>${TOOL_NAME} report</h1>
  <div class="meta">Generated ${generated} &nbsp;|&nbsp; Input $(html_escape "$INPUT_FILE") &nbsp;|&nbsp; Telnet timeout ${TELNET_TIMEOUT}s</div>
</header>
<div class="legend">
  <div class="legend-item"><span class="st st-PASS">PASS</span><span>TCP connect from source to dest:port succeeded</span></div>
  <div class="legend-item"><span class="st st-FAIL">FAIL</span><span>Source reachable, but dest:port did not accept (timeout, filtered, or probe unusable)</span></div>
  <div class="legend-item"><span class="st st-Down">Down</span><span>Source reachable; dest:port returned Connection refused</span></div>
  <div class="legend-item"><span class="st st-NA">N.A</span><span>Source host not reachable over SSH (or auth/session failed)</span></div>
</div>
<div class="kpis">
  <div class="kpi"><b id="kpi-total">${total}</b><span>Total</span></div>
  <div class="kpi pass"><b id="kpi-pass">${pass}</b><span>PASS</span></div>
  <div class="kpi fail"><b id="kpi-fail">${fail}</b><span>FAIL</span></div>
  <div class="kpi down"><b id="kpi-down">${down}</b><span>Down</span></div>
  <div class="kpi na"><b id="kpi-na">${na}</b><span>N.A</span></div>
</div>
<div class="wrap">
<table id="rpt">
<thead>
<tr>
  <th>Source_User</th>
  <th>Source_IP</th>
  <th>Destination_IP</th>
  <th>Destination_Port</th>
  <th>Telnet_Status</th>
</tr>
<tr class="filters">
  <th><input data-col="0" placeholder="Filter user"></th>
  <th><input data-col="1" placeholder="Filter source IP"></th>
  <th><input data-col="2" placeholder="Filter dest IP"></th>
  <th><input data-col="3" placeholder="Filter port"></th>
  <th>
    <select data-col="4">
      <option value="">All statuses</option>
      <option value="PASS">PASS</option>
      <option value="FAIL">FAIL</option>
      <option value="Down">Down</option>
      <option value="N.A">N.A</option>
    </select>
  </th>
</tr>
</thead>
<tbody>
EOF
		local user src dest port st cls
		while IFS='|' read -r user src dest port st; do
			[[ -z "${user-}" ]] && continue
			cls="$st"
			[[ "$st" == "N.A" ]] && cls="NA"
			printf '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td><span class="st st-%s">%s</span></td></tr>\n' \
				"$(html_escape "$user")" \
				"$(html_escape "$src")" \
				"$(html_escape "$dest")" \
				"$(html_escape "$port")" \
				"$cls" \
				"$(html_escape "$st")"
		done < "$results"
		cat <<'EOF'
</tbody>
</table>
<div class="count" id="vis">Showing all rows</div>
</div>
<script>
(function () {
  var table = document.getElementById("rpt");
  var tbody = table.tBodies[0];
  var filters = table.querySelectorAll(".filters input, .filters select");
  function val(row, i) { return (row.cells[i] ? row.cells[i].innerText : "").trim(); }
  function apply() {
    var shown = 0, p = 0, f = 0, d = 0, n = 0;
    var rows = tbody.rows;
    for (var r = 0; r < rows.length; r++) {
      var row = rows[r], ok = true;
      for (var i = 0; i < filters.length; i++) {
        var col = +filters[i].getAttribute("data-col");
        var q = (filters[i].value || "").trim().toLowerCase();
        if (!q) continue;
        if (val(row, col).toLowerCase().indexOf(q) === -1) { ok = false; break; }
      }
      row.classList.toggle("hide", !ok);
      if (ok) {
        shown++;
        var st = val(row, 4);
        if (st === "PASS") p++;
        else if (st === "FAIL") f++;
        else if (st === "Down") d++;
        else n++;
      }
    }
    document.getElementById("vis").textContent = "Showing " + shown + " of " + rows.length + " rows";
    document.getElementById("kpi-total").textContent = shown;
    document.getElementById("kpi-pass").textContent = p;
    document.getElementById("kpi-fail").textContent = f;
    document.getElementById("kpi-down").textContent = d;
    document.getElementById("kpi-na").textContent = n;
  }
  for (var i = 0; i < filters.length; i++) {
    filters[i].addEventListener("input", apply);
    filters[i].addEventListener("change", apply);
  }
})();
</script>
</body>
</html>
EOF
	} > "$out"
}

main() {
	parse_args "$@"
	build_ssh_opts

	CC_WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/connection-checker.XXXXXX")"

	if [[ "$DRY_RUN" -eq 1 ]]; then
		printf 'Source_User|Source_IP|Destination_IP|Destination_Port\n'
		ACTIVE_PIDS=()
		RESULT_FILES=()
		process_input
		log "Dry-run complete. No SSH/telnet performed."
		exit 0
	fi

	local results_file="${CC_WORK_DIR}/results.txt"
	local result_file
	ACTIVE_PIDS=()
	RESULT_FILES=()
	process_input
	wait_for_all_sources

	: > "$results_file"
	for result_file in "${RESULT_FILES[@]}"; do
		cat "$result_file" >> "$results_file"
	done

	write_html "$results_file" "$OUTPUT_FILE"
	log "Report written: $OUTPUT_FILE"
	log "Summary: $(grep -c . "$results_file" || true) rows, PASS=$(grep -c '|PASS$' "$results_file" || true) FAIL=$(grep -c '|FAIL$' "$results_file" || true) Down=$(grep -c '|Down$' "$results_file" || true) N.A=$(grep -c '|N\.A$' "$results_file" || true)"
}

main "$@"
