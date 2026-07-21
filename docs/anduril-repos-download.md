# Anduril 公开仓库下载说明

## 为什么放在 external/

本项目是本地 fake Lattice sandbox。`external/` 用来保存 Anduril 公开 GitHub 仓库，作为阅读、对照和学习资料。把这些仓库放在 `external/` 下，可以把第三方参考代码和当前项目功能代码隔离开，避免混入本地 mock server、地图 UI 和脚本实现。

本项目不会创建 `external/anduril/`。主要仓库直接放在 `external/` 下，归档 SDK 放在 `external/archived/` 下。

## 使用边界

这些仓库只作为公开参考资料：

- 不运行真实 Anduril API。
- 不安装 Anduril SDK。
- 不使用真实 token。
- 不把 `external/` 提交进当前项目。
- 不修改 external 仓库内部代码。

`.gitignore` 已忽略 `external/`，避免把第三方仓库提交到当前项目。

## 当前目录结构

```text
external/
  sample-app-ais-integration-rest/
  sample-app-auto-reconnaissance/
  sample-app-objects/
  sample-app-thumbnail/
  sample-app-entity-visualizer/
  lattice-sdk-python/
  lattice-sdk-javascript/
  lattice-sdk-go/
  lattice-sdk-java/
  lattice-sdk-ais-integration-grpc/
  archived/
    lattice-sdk-cpp/
    lattice-sdk-rust/
```

## 仓库用途简要说明

- `sample-app-ais-integration-rest`：REST 风格 AIS entity integration 示例，可用于理解 AIS 数据到 Lattice-style entity 的转换。
- `sample-app-auto-reconnaissance`：自动侦察 sample app，可作为任务流、侦察场景和 agent 行为建模参考。
- `sample-app-objects`：Objects sample app，可用于对照本地 Objects API 的上传、metadata 和下载概念。
- `sample-app-thumbnail`：thumbnail 示例，可用于后续为 entity 或 object 增加缩略图能力时参考。
- `sample-app-entity-visualizer`：entity 可视化示例，可用于改进当前 Leaflet 地图 UI。
- `lattice-sdk-ais-integration-grpc`：gRPC AIS integration 示例，可用于理解非 REST 的 integration 形态。
- `lattice-sdk-python`：Python SDK 公开仓库，仅作 schema 和 API 使用方式参考。
- `lattice-sdk-javascript`：JavaScript SDK 公开仓库，仅作前端或 Node 使用方式参考。
- `lattice-sdk-go`：Go SDK 公开仓库，仅作 Go 客户端实现参考。
- `lattice-sdk-java`：Java SDK 公开仓库，仅作 Java 客户端实现参考。
- `archived/lattice-sdk-cpp`：归档 C++ SDK，仅作历史参考。
- `archived/lattice-sdk-rust`：归档 Rust SDK，仅作历史参考。

## 下载方式

从项目根目录运行：

```bash
bash scripts/download_anduril_repos.sh
```

脚本会自动创建：

```text
external/
external/archived/
```

如果目标目录已经是 git 仓库，脚本会输出“已存在，跳过”。如果目标目录存在但不是 git 仓库，脚本会提示并跳过，避免覆盖用户文件。

## 后续如何利用这些仓库

后续可以逐步阅读这些公开仓库，并用它们改进当前 fake sandbox：

- 对照 sample app 的 entity 字段，完善 `generate_entities.py` 的本地模拟数据。
- 对照 Objects sample，完善本地 Objects API 和 UI 附件面板。
- 对照 thumbnail sample，为地图 marker 或 object 增加缩略图展示。
- 对照 entity visualizer，改进当前 Leaflet 地图 UI 的实体显示和筛选。
- 对照 auto reconnaissance 示例，改进 `tools/sim_agent.py`、Tasks API 和任务状态机。
- 对照 SDK 仓库的公开 schema 和调用习惯，改进本地 mock API 的字段命名和文档。

这些改进仍应保持本地 fake sandbox 边界：不调用 Anduril API，不使用真实 token，不安装 Anduril SDK，不实现真实认证。
