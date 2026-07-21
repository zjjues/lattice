#!/usr/bin/env bash
set -euo pipefail

mkdir -p external
mkdir -p external/archived

RESULTS=()

clone_repo() {
  local url="$1"
  local target_path="$2"
  local repo_name
  repo_name="$(basename "${target_path}")"

  if [[ -d "${target_path}/.git" ]]; then
    echo "${repo_name}: 已存在，跳过 (${target_path})"
    RESULTS+=("${repo_name}|${target_path}|已存在跳过|")
    return 0
  fi

  if [[ -e "${target_path}" ]]; then
    echo "${repo_name}: 目标目录已存在但不是 git 仓库，跳过以避免覆盖 (${target_path})"
    RESULTS+=("${repo_name}|${target_path}|已存在跳过|目标目录已存在但不是 git 仓库")
    return 0
  fi

  echo "${repo_name}: clone ${url} -> ${target_path}"
  if git clone --depth 1 "${url}" "${target_path}"; then
    RESULTS+=("${repo_name}|${target_path}|已 clone|")
  else
    RESULTS+=("${repo_name}|${target_path}|失败|git clone 失败")
  fi
}

clone_repo "https://github.com/anduril/sample-app-ais-integration-rest.git" "external/sample-app-ais-integration-rest"
clone_repo "https://github.com/anduril/sample-app-auto-reconnaissance.git" "external/sample-app-auto-reconnaissance"
clone_repo "https://github.com/anduril/sample-app-objects.git" "external/sample-app-objects"
clone_repo "https://github.com/anduril/sample-app-thumbnail.git" "external/sample-app-thumbnail"
clone_repo "https://github.com/anduril/sample-app-entity-visualizer.git" "external/sample-app-entity-visualizer"
clone_repo "https://github.com/anduril/sample-app-ais-integration-grpc.git" "external/lattice-sdk-ais-integration-grpc"
clone_repo "https://github.com/anduril/lattice-sdk-python.git" "external/lattice-sdk-python"
clone_repo "https://github.com/anduril/lattice-sdk-javascript.git" "external/lattice-sdk-javascript"
clone_repo "https://github.com/anduril/lattice-sdk-go.git" "external/lattice-sdk-go"
clone_repo "https://github.com/anduril/lattice-sdk-java.git" "external/lattice-sdk-java"
clone_repo "https://github.com/anduril/lattice-sdk-cpp.git" "external/archived/lattice-sdk-cpp"
clone_repo "https://github.com/anduril/lattice-sdk-rust.git" "external/archived/lattice-sdk-rust"

echo
echo "目标目录："
printf '%s\n' \
  "external/sample-app-ais-integration-rest" \
  "external/sample-app-auto-reconnaissance" \
  "external/sample-app-objects" \
  "external/sample-app-thumbnail" \
  "external/sample-app-entity-visualizer" \
  "external/lattice-sdk-ais-integration-grpc" \
  "external/lattice-sdk-python" \
  "external/lattice-sdk-javascript" \
  "external/lattice-sdk-go" \
  "external/lattice-sdk-java" \
  "external/archived/lattice-sdk-cpp" \
  "external/archived/lattice-sdk-rust"

echo
echo "下载结果："
printf '%-36s | %-48s | %-14s | %s\n' "仓库名" "本地路径" "状态" "失败原因"
printf '%-36s-+-%-48s-+-%-14s-+-%s\n' "------------------------------------" "------------------------------------------------" "--------------" "----------------"
for item in "${RESULTS[@]}"; do
  IFS='|' read -r repo_name target_path status reason <<<"${item}"
  printf '%-36s | %-48s | %-14s | %s\n' "${repo_name}" "${target_path}" "${status}" "${reason}"
done
