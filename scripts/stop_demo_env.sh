#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/run"
SERVER_PID_FILE="$RUN_DIR/mock_server.pid"
AGENT_PID_FILE="$RUN_DIR/sim_agent.pid"
DRY_RUN=0

usage() {
  cat <<'EOF'
用法：
  bash scripts/stop_demo_env.sh [--dry-run]

参数：
  --dry-run  只打印将要停止的进程，不真正发送 kill
EOF
}

log() {
  printf '[stop-demo] %s\n' "$1"
}

is_pid_running() {
  local pid="$1"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" >/dev/null 2>&1
}

find_existing_server_pids() {
  pgrep -f "uvicorn mock_server:app --reload --host 127.0.0.1 --port 8000" || true
}

find_existing_agent_pids() {
  pgrep -f "python3 tools/sim_agent.py --asset-id SIM_ASSET_001" || true
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run)
        DRY_RUN=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        printf '未知参数: %s\n' "$1" >&2
        usage >&2
        exit 1
        ;;
    esac
  done
}

stop_pid() {
  local pid="$1"
  local label="$2"
  if ! is_pid_running "$pid"; then
    log "$label PID=$pid 不在运行"
    return 0
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: kill $pid ($label)"
    return 0
  fi

  kill "$pid"
  log "已停止 $label，PID=$pid"
}

stop_from_pid_file() {
  local pid_file="$1"
  local label="$2"
  if [[ ! -f "$pid_file" ]]; then
    return 1
  fi

  local pid=""
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  [[ -n "$pid" ]] || return 1
  stop_pid "$pid" "$label"
  if [[ "$DRY_RUN" -eq 0 ]]; then
    rm -f "$pid_file"
  fi
  return 0
}

stop_by_pattern() {
  local label="$1"
  shift
  local pids
  pids="$("$@")"
  if [[ -z "$pids" ]]; then
    log "未发现正在运行的 $label"
    return 0
  fi

  while IFS= read -r pid; do
    [[ -n "$pid" ]] || continue
    stop_pid "$pid" "$label"
  done <<<"$pids"
}

main() {
  parse_args "$@"

  local handled_server=0
  local handled_agent=0

  if stop_from_pid_file "$SERVER_PID_FILE" "mock server"; then
    handled_server=1
  fi
  if stop_from_pid_file "$AGENT_PID_FILE" "sim_agent"; then
    handled_agent=1
  fi

  if [[ "$handled_server" -eq 0 ]]; then
    stop_by_pattern "mock server" find_existing_server_pids
  fi
  if [[ "$handled_agent" -eq 0 ]]; then
    stop_by_pattern "sim_agent" find_existing_agent_pids
  fi

  log "演示环境停止流程已完成"
}

main "$@"
