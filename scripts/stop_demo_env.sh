#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/run"
DRY_RUN=0

usage() { echo '用法：bash scripts/stop_demo_env.sh [--dry-run]'; }
log() { printf '[lattice] %s\n' "$1"; }
is_running() { local pid="${1:-}"; [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" >/dev/null 2>&1; }

stop_process() {
  local pid_file="$1" label="$2" expected="$3"
  [[ -f "$pid_file" ]] || { log "$label 未记录 PID"; return 0; }
  local pid command_line
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if ! is_running "$pid"; then
    log "$label 未运行，清理过期 PID 文件"
    [[ "$DRY_RUN" -eq 1 ]] || rm -f "$pid_file"
    return 0
  fi
  command_line="$(ps -p "$pid" -o args= 2>/dev/null || true)"
  if [[ "$command_line" != *"$expected"* ]]; then
    printf '%s PID=%s 与本工程命令不匹配，拒绝停止：%s\n' "$label" "$pid" "$command_line" >&2
    return 1
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: kill $pid ($label)"
    return 0
  fi
  kill "$pid"
  local attempt
  for attempt in {1..20}; do is_running "$pid" || break; sleep 0.1; done
  if is_running "$pid"; then
    printf '%s PID=%s 未在超时时间内退出\n' "$label" "$pid" >&2
    return 1
  fi
  rm -f "$pid_file"
  log "已停止 $label，PID=$pid"
}

main() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) DRY_RUN=1; shift ;;
      -h|--help) usage; exit 0 ;;
      *) printf '未知参数: %s\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
  done
  local failed=0
  stop_process "$RUN_DIR/lattice_agent.pid" '模拟 Agent' 'tools/sim_agent.py' || failed=1
  stop_process "$RUN_DIR/lattice_server.pid" 'Lattice 服务' 'uvicorn' || failed=1
  [[ "$failed" -eq 0 ]]
}

main "$@"
