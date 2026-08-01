#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
RUN_DIR="$ROOT_DIR/run"
SERVER_LOG="$LOG_DIR/lattice_server.log"
AGENT_LOG="$LOG_DIR/lattice_agent.log"
SERVER_PID_FILE="$RUN_DIR/lattice_server.pid"
AGENT_PID_FILE="$RUN_DIR/lattice_agent.pid"
CONDA_ENV="${LATTICE_CONDA_ENV:-lattice}"
HOST="${LATTICE_HOST:-127.0.0.1}"
PORT="${LATTICE_PORT:-8000}"
APP_TARGET="app:app"
RESET_FIRST=0
START_AGENT=1
DRY_RUN=0

usage() {
  cat <<'EOF'
用法：bash scripts/start_demo_env.sh [选项]

  --reset         启动前重置 data/*.json 和 objects/（会删除演示数据）
  --legacy        启动旧兼容入口 mock_server:app
  --no-agent      不启动模拟任务 Agent
  --host HOST     监听地址，默认 127.0.0.1
  --port PORT     监听端口，默认 8000
  --dry-run       只打印动作，不启动进程
  -h, --help      显示帮助

环境变量：LATTICE_CONDA_ENV、LATTICE_HOST、LATTICE_PORT
EOF
}

log() { printf '[lattice] %s\n' "$1"; }

find_conda() {
  if [[ -n "${CONDA_EXE:-}" && -x "$CONDA_EXE" ]]; then
    printf '%s\n' "$CONDA_EXE"
  elif command -v conda >/dev/null 2>&1; then
    command -v conda
  elif [[ -x "$HOME/anaconda3/bin/conda" ]]; then
    printf '%s\n' "$HOME/anaconda3/bin/conda"
  elif [[ -x "$HOME/miniconda3/bin/conda" ]]; then
    printf '%s\n' "$HOME/miniconda3/bin/conda"
  else
    return 1
  fi
}

is_running() {
  local pid="${1:-}"
  [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" >/dev/null 2>&1
}

read_running_pid() {
  local pid_file="$1"
  [[ -f "$pid_file" ]] || return 1
  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  is_running "$pid" || return 1
  printf '%s\n' "$pid"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --reset) RESET_FIRST=1; shift ;;
      --legacy) APP_TARGET="mock_server:app"; shift ;;
      --no-agent) START_AGENT=0; shift ;;
      --host) [[ $# -ge 2 ]] || { echo '--host 缺少参数' >&2; exit 2; }; HOST="$2"; shift 2 ;;
      --port) [[ $# -ge 2 ]] || { echo '--port 缺少参数' >&2; exit 2; }; PORT="$2"; shift 2 ;;
      --dry-run) DRY_RUN=1; shift ;;
      -h|--help) usage; exit 0 ;;
      *) printf '未知参数: %s\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
  done
  [[ "$PORT" =~ ^[0-9]+$ ]] && (( PORT >= 1 && PORT <= 65535 )) || {
    printf '无效端口: %s\n' "$PORT" >&2; exit 2;
  }
}

main() {
  parse_args "$@"
  local conda_bin python_bin
  conda_bin="$(find_conda)" || { echo '未找到 Conda。' >&2; exit 1; }
  python_bin="$($conda_bin run -n "$CONDA_ENV" python -c 'import sys; print(sys.executable)' 2>/dev/null)" || {
    printf '无法使用 Conda 环境: %s\n' "$CONDA_ENV" >&2; exit 1;
  }
  [[ -x "$python_bin" ]] || { printf '环境 Python 不可执行: %s\n' "$python_bin" >&2; exit 1; }

  mkdir -p "$LOG_DIR" "$RUN_DIR"
  if [[ -f "$ROOT_DIR/.env.local" ]]; then
    log "加载 $ROOT_DIR/.env.local"
    # shellcheck disable=SC1091
    source "$ROOT_DIR/.env.local"
  fi

  local base_url="http://$HOST:$PORT"
  [[ "$HOST" == "0.0.0.0" || "$HOST" == "::" ]] && base_url="http://127.0.0.1:$PORT"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    [[ "$RESET_FIRST" -eq 1 ]] && log "DRY-RUN: $python_bin tools/reset_demo_state.py"
    log "DRY-RUN: $python_bin -m uvicorn $APP_TARGET --host $HOST --port $PORT"
    [[ "$START_AGENT" -eq 1 ]] && log "DRY-RUN: $python_bin tools/sim_agent.py --base-url $base_url --asset-id SIM_ASSET_001 --poll-interval 1 --work-seconds 3 --success-rate 1.0 --verbose"
    exit 0
  fi

  local existing_pid
  existing_pid="$(read_running_pid "$SERVER_PID_FILE" || true)"
  if [[ -n "$existing_pid" ]]; then
    printf '服务已在运行，PID=%s；请先执行 stop_demo_env.sh。\n' "$existing_pid" >&2
    exit 1
  fi
  rm -f "$SERVER_PID_FILE"

  cd "$ROOT_DIR"
  if [[ "$RESET_FIRST" -eq 1 ]]; then
    log '重置本地演示数据'
    "$python_bin" tools/reset_demo_state.py
  fi

  nohup "$python_bin" -m uvicorn "$APP_TARGET" --host "$HOST" --port "$PORT" >"$SERVER_LOG" 2>&1 &
  local server_pid=$!
  printf '%s\n' "$server_pid" >"$SERVER_PID_FILE"

  local ready=0
  local attempt
  for attempt in {1..40}; do
    is_running "$server_pid" || break
    if python3 -c "import urllib.request; urllib.request.urlopen('$base_url/health', timeout=0.5).read()" >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 0.25
  done
  if [[ "$ready" -ne 1 ]]; then
    rm -f "$SERVER_PID_FILE"
    is_running "$server_pid" && kill "$server_pid" >/dev/null 2>&1 || true
    printf '服务启动失败，查看日志: %s\n' "$SERVER_LOG" >&2
    exit 1
  fi
  log "已启动 $APP_TARGET，PID=$server_pid"

  if [[ "$START_AGENT" -eq 1 ]]; then
    existing_pid="$(read_running_pid "$AGENT_PID_FILE" || true)"
    if [[ -n "$existing_pid" ]]; then
      log "模拟 Agent 已在运行，PID=$existing_pid"
    else
      rm -f "$AGENT_PID_FILE"
      nohup "$python_bin" tools/sim_agent.py --base-url "$base_url" --asset-id SIM_ASSET_001 \
        --poll-interval 1 --work-seconds 3 --success-rate 1.0 --verbose >"$AGENT_LOG" 2>&1 &
      local agent_pid=$!
      printf '%s\n' "$agent_pid" >"$AGENT_PID_FILE"
      log "已启动模拟 Agent，PID=$agent_pid"
    fi
  fi

  log "地图 UI: $base_url/"
  log "健康检查: $base_url/health"
  log "OpenAPI: $base_url/docs"
  log "服务日志: $SERVER_LOG"
  [[ "$START_AGENT" -eq 1 ]] && log "Agent 日志: $AGENT_LOG"
}

main "$@"
