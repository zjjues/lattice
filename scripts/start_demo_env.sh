#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
RUN_DIR="$ROOT_DIR/run"
SERVER_LOG="$LOG_DIR/mock_server.log"
AGENT_LOG="$LOG_DIR/sim_agent.log"
SERVER_PID_FILE="$RUN_DIR/mock_server.pid"
AGENT_PID_FILE="$RUN_DIR/sim_agent.pid"
BASE_URL="http://127.0.0.1:8000"
MAP_URL="http://127.0.0.1:8000/?lat=31.2304&lon=121.4737&zoom=12"
RESET_FIRST=0
DRY_RUN=0
ENV_FILE="$ROOT_DIR/.env.local"

usage() {
  cat <<'EOF'
用法：
  bash scripts/start_demo_env.sh [--reset] [--dry-run]

参数：
  --reset    启动前先执行 tools/reset_demo_state.py
  --dry-run  只打印将要执行的动作，不真正启动进程
EOF
}

log() {
  printf '[start-demo] %s\n' "$1"
}

load_env_file() {
  if [[ -f "$ENV_FILE" ]]; then
    log "加载本地环境文件：$ENV_FILE"
    # shellcheck disable=SC1090
    source "$ENV_FILE"
  fi
}

run_cmd() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: $*"
    return 0
  fi
  "$@"
}

is_pid_running() {
  local pid="$1"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" >/dev/null 2>&1
}

find_existing_server_pid() {
  pgrep -f "uvicorn mock_server:app --reload --host 127.0.0.1 --port 8000" | head -n 1 || true
}

find_existing_agent_pid() {
  pgrep -f "python3 tools/sim_agent.py --asset-id SIM_ASSET_001" | head -n 1 || true
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --reset)
        RESET_FIRST=1
        shift
        ;;
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

start_server() {
  local pid=""
  if [[ -f "$SERVER_PID_FILE" ]]; then
    pid="$(cat "$SERVER_PID_FILE" 2>/dev/null || true)"
    if is_pid_running "$pid"; then
      log "mock server 已在运行，PID=$pid"
      return 0
    fi
  fi

  pid="$(find_existing_server_pid)"
  if [[ -n "$pid" ]]; then
    printf '%s\n' "$pid" >"$SERVER_PID_FILE"
    log "检测到已有 mock server 进程，PID=$pid"
    return 0
  fi

  mkdir -p "$LOG_DIR" "$RUN_DIR"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: 启动 mock server -> uvicorn mock_server:app --reload --host 127.0.0.1 --port 8000"
    return 0
  fi

  (
    cd "$ROOT_DIR"
    nohup uvicorn mock_server:app --reload --host 127.0.0.1 --port 8000 >"$SERVER_LOG" 2>&1 &
    echo $! >"$SERVER_PID_FILE"
  )
  log "已启动 mock server，PID=$(cat "$SERVER_PID_FILE")，日志：$SERVER_LOG"
}

start_agent() {
  local pid=""
  if [[ -f "$AGENT_PID_FILE" ]]; then
    pid="$(cat "$AGENT_PID_FILE" 2>/dev/null || true)"
    if is_pid_running "$pid"; then
      log "sim_agent 已在运行，PID=$pid"
      return 0
    fi
  fi

  pid="$(find_existing_agent_pid)"
  if [[ -n "$pid" ]]; then
    printf '%s\n' "$pid" >"$AGENT_PID_FILE"
    log "检测到已有 sim_agent 进程，PID=$pid"
    return 0
  fi

  mkdir -p "$LOG_DIR" "$RUN_DIR"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log "DRY-RUN: 启动 sim_agent -> python3 tools/sim_agent.py --asset-id SIM_ASSET_001 --poll-interval 1 --work-seconds 3 --success-rate 1.0 --verbose"
    return 0
  fi

  (
    cd "$ROOT_DIR"
    nohup python3 tools/sim_agent.py --asset-id SIM_ASSET_001 --poll-interval 1 --work-seconds 3 --success-rate 1.0 --verbose >"$AGENT_LOG" 2>&1 &
    echo $! >"$AGENT_PID_FILE"
  )
  log "已启动 sim_agent，PID=$(cat "$AGENT_PID_FILE")，日志：$AGENT_LOG"
}

main() {
  parse_args "$@"
  mkdir -p "$LOG_DIR" "$RUN_DIR"
  load_env_file

  if [[ "$RESET_FIRST" -eq 1 ]]; then
    log "先重置演示数据"
    run_cmd python3 "$ROOT_DIR/tools/reset_demo_state.py"
  fi

  start_server
  start_agent

  log "演示环境已准备完成"
  log "浏览器地址：$MAP_URL"
  log "健康检查：$BASE_URL/health"
  log "主演示命令（场景 A）：python3 tools/replay_sim_events.py --input fixtures/ingest/uav_intrusion.jsonl --interval-seconds 1.5"
  log "第二场景命令（场景 B）：python3 tools/replay_sim_events.py --input fixtures/ingest/uav_loitering.jsonl --interval-seconds 1.5"
}

main "$@"
