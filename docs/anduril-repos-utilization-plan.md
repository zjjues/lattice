# Anduril 公开仓库利用计划

## 一、总说明

1. `external/` 下的 Anduril 公开仓库只作为公开参考资料，用于理解示例结构、数据模型、任务流程和 UI 表达方式。
2. 当前 fake Lattice-style sandbox 不会调用 Anduril API，所有接口仍然只面向本地 `mock_server.py`。
3. 当前项目不会使用真实 token，也不会要求用户配置真实 Lattice 环境变量。
4. 当前项目不会安装或依赖 Anduril SDK；SDK 仓库只用于字段、接口命名和兼容性审计。
5. `external/` 目录不应该提交进当前项目仓库，应继续由 `.gitignore` 排除。

## 二、仓库清单

| 仓库名 | 本地路径 | 仓库主要用途 | 相关模块 | 应如何利用 | 是否需要运行 | 是否需要改造成本地版本 | 优先级 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `sample-app-ais-integration-rest` | `external/sample-app-ais-integration-rest` | REST 方式接入 AIS/entity 数据的示例 | `generate_entities.py`、Entities API、地图 marker | 对照 AIS 字段、REST 提交流程和示例配置，设计本地 AIS importer | 否 | 是，改造为本地 importer | 高 |
| `sample-app-auto-reconnaissance` | `external/sample-app-auto-reconnaissance` | 自动侦察任务、模拟 asset 和 track 流程示例 | Tasks API、`tools/sim_agent.py`、地图 UI | 参考任务编排、asset 行为和自动任务生成方式，做本地 auto recon | 否 | 是，改造为本地 auto recon | 高 |
| `sample-app-objects` | `external/sample-app-objects` | Objects 上传、查询、下载示例 | Objects API、附件 UI | 对照 object metadata、上传和下载流程，补一个本地 objects CLI | 否 | 是，改造为本地 CLI | 高 |
| `sample-app-thumbnail` | `external/sample-app-thumbnail` | entity/track thumbnail 相关示例 | Objects API、entity popup、附件展示 | 参考 thumbnail 与 object/entity 的关系，在本地 UI 中展示缩略图 | 否 | 是，改造为本地 thumbnail 功能 | 中 |
| `sample-app-entity-visualizer` | `external/sample-app-entity-visualizer` | entity 可视化前端示例 | `static/` 地图 UI、entity list/filter | 参考列表、筛选、选中、定位等 UI 组织方式，增强当前地图 UI | 否 | 是，改造为本地 UI 功能 | 中 |
| `lattice-sdk-python` | `external/lattice-sdk-python` | Python SDK 和 API/schema 参考 | API 兼容性审计、Python 工具脚本 | 只读取字段、endpoint 和类型定义，检查本地 mock 命名是否偏离过大 | 否 | 否，只做审计参考 | 中 |
| `lattice-sdk-javascript` | `external/lattice-sdk-javascript` | JavaScript/TypeScript SDK 和 schema 参考 | 前端 UI、WebSocket 消息、对象/任务字段 | 参考前端侧类型命名，整理本地 JS 数据结构和文档术语 | 否 | 否，只做审计参考 | 中 |
| `lattice-sdk-go` | `external/lattice-sdk-go` | Go SDK，包含 entities、tasks、objects 相关包 | Entities、Tasks、Objects API | 参考 object/task/entity 资源组织和测试覆盖方式，做兼容性对照 | 否 | 否，只做审计参考 | 中 |
| `lattice-sdk-java` | `external/lattice-sdk-java` | Java SDK 和 API 参考 | SDK compatibility audit | 作为低优先级跨语言字段命名参考 | 否 | 否，只做审计参考 | 低 |
| `lattice-sdk-ais-integration-grpc` | `external/lattice-sdk-ais-integration-grpc` | AIS integration gRPC 示例 | 未来 gRPC/AIS importer 对照 | REST importer 稳定后，再参考 gRPC 数据结构和流式接入概念 | 否 | 暂不改造，后续可评估 | 低 |
| `lattice-sdk-cpp` | `external/archived/lattice-sdk-cpp` | 归档 C++ SDK | 历史兼容性参考 | 仅在需要追溯旧字段或旧示例时查阅 | 否 | 否 | 低 |
| `lattice-sdk-rust` | `external/archived/lattice-sdk-rust` | 归档 Rust SDK | 历史兼容性参考 | 仅在需要追溯旧字段或旧示例时查阅 | 否 | 否 | 低 |

## 三、优先级建议

1. `sample-app-ais-integration-rest`：最高优先级。当前项目已经有 entity generator 和 Entities API，最自然的下一步是把公开 REST AIS 示例改造成本地 AIS importer。
2. `sample-app-auto-reconnaissance`：高优先级。当前已经有 Tasks API、任务面板和 `sim_agent.py`，适合继续做本地自动侦察流程。
3. `sample-app-objects`：高优先级。当前 Objects API 和 UI 附件功能已经存在，补一个 CLI 可以让上传、下载、删除更容易验证。
4. `sample-app-thumbnail`：中优先级。适合基于 Objects API 增强 entity popup 的可视化表达。
5. `sample-app-entity-visualizer`：中优先级。当前地图 UI 已经可用，但缺少 entity 列表、过滤和批量查看能力。
6. `lattice-sdk-python`：中优先级。用于 Python 工具和 mock API 的字段兼容性审计，不作为运行依赖。
7. `lattice-sdk-javascript`：中优先级。用于前端字段命名和类型组织参考，不安装 SDK。
8. `lattice-sdk-go`：中优先级。Objects、Tasks、Entities 资源结构可用于对照当前本地 API。
9. `lattice-sdk-java`：低优先级。作为跨语言参考即可。
10. `lattice-sdk-ais-integration-grpc`：低优先级。当前项目优先保持 REST/local mock，gRPC 暂时只读。
11. archived SDK：低优先级。只作为历史参考，不进入当前实现路线。

## 四、后续路线图

| Step | 主题 | 参考仓库 | 目标产出 |
| --- | --- | --- | --- |
| step-12 | `sample-app-ais-integration-rest` → 本地 AIS importer | `external/sample-app-ais-integration-rest` | 从本地 AIS 风格数据导入 mock Entities API |
| step-13 | `sample-app-auto-reconnaissance` → 本地 auto recon | `external/sample-app-auto-reconnaissance` | 自动选择目标、创建任务、交给模拟 agent 处理 |
| step-14 | `sample-app-objects` → 本地 objects CLI | `external/sample-app-objects` | 命令行上传、查询、下载、删除本地 object |
| step-15 | `sample-app-thumbnail` → entity thumbnail | `external/sample-app-thumbnail` | 用 Objects API 管理并展示 entity 缩略图 |
| step-16 | `sample-app-entity-visualizer` → entity list/filter UI | `external/sample-app-entity-visualizer` | 地图旁增加 entity 列表、过滤和定位能力 |
| step-17 | SDK compatibility audit | `external/lattice-sdk-*`、`external/archived/lattice-sdk-*` | 本地 fake API 与公开 SDK/schema 的差异审计 |

## 五、每一步说明

### step-12：本地 AIS importer

- 目标：参考 `sample-app-ais-integration-rest`，新增一个本地 AIS importer，把本地 CSV、JSON 或示例 AIS 数据转换为当前 fake sandbox 的 entity payload，并调用本地 `PUT /api/v1/entities`。
- 输入参考仓库：`external/sample-app-ais-integration-rest`。
- 产出文件：建议新增 `tools/import_ais_entities.py`、`docs/step-12-local-ais-importer.md`，可按需要新增 `examples/ais-import-sample.json` 或 `examples/ais-import-sample.csv`。
- 不做什么：不调用 Anduril API，不读取真实 token，不运行原 sample app，不修改 `external/sample-app-ais-integration-rest`。
- 验证方式：启动 `mock_server.py`，运行 importer，调用 `GET /api/v1/entities` 检查导入结果，并在地图 UI 中确认 marker 出现。

### step-13：本地 auto recon

- 目标：参考 `sample-app-auto-reconnaissance`，实现一个本地自动侦察流程，根据已有 entities 自动创建调查任务，并交给 `tools/sim_agent.py` 模拟处理。
- 输入参考仓库：`external/sample-app-auto-reconnaissance`。
- 产出文件：建议新增 `tools/auto_recon.py`、`docs/step-13-local-auto-recon.md`，必要时新增本地 recon 配置示例。
- 不做什么：不连接真实 Lattice，不控制真实 asset，不实现真实任务规划算法，不运行原 sample app。
- 验证方式：生成并上传 entities，运行本地 auto recon，观察 Tasks API、WebSocket 和 UI 任务面板是否出现新任务，再运行 `sim_agent.py` 观察状态自动流转。

### step-14：本地 objects CLI

- 目标：参考 `sample-app-objects`，为当前 Objects API 增加一个命令行工具，支持 upload、list、get、download、delete。
- 输入参考仓库：`external/sample-app-objects`。
- 产出文件：建议新增 `tools/objects_cli.py`、`docs/step-14-objects-cli.md`，可新增更多 object 示例文件。
- 不做什么：不调用真实 Objects API，不安装 Go sample app 依赖，不实现真实 CDN 或大文件分片上传。
- 验证方式：用 CLI 上传 `examples/object-note.txt`，查询 metadata，下载到本地临时路径，删除 object，并通过 WebSocket 观察 `object.created` 和 `object.deleted`。

### step-15：entity thumbnail

- 目标：参考 `sample-app-thumbnail`，把本地 Objects API 中的图片对象作为 entity thumbnail，在 marker popup 或 entity 详情区域展示。
- 输入参考仓库：`external/sample-app-thumbnail`。
- 产出文件：建议新增 `docs/step-15-entity-thumbnail.md`，并修改 `static/app.js`、`static/style.css` 支持 thumbnail 展示；如需要，可新增 `tools/upload_entity_thumbnail.py`。
- 不做什么：不接入真实 thumbnail 服务，不使用真实 Lattice CDN，不做生产级图片处理或安全扫描。
- 验证方式：上传一张图片 object 并关联 `relatedEntityId`，打开地图 UI，确认对应 marker popup 能显示缩略图并保留下载能力。

### step-16：entity list/filter UI

- 目标：参考 `sample-app-entity-visualizer`，在当前 Leaflet UI 中增加 entity 列表、类型过滤、文本搜索和点击定位 marker 的能力。
- 输入参考仓库：`external/sample-app-entity-visualizer`。
- 产出文件：建议更新 `static/index.html`、`static/app.js`、`static/style.css`，并新增 `docs/step-16-entity-list-filter-ui.md`。
- 不做什么：不把原 React/Vite 项目整体迁入当前项目，不运行原 sample app，不引入 Anduril SDK。
- 验证方式：上传多条 entities，在 UI 中按关键字或类型过滤，点击列表项后地图移动到对应 marker，并确认 WebSocket 更新不会破坏列表状态。

### step-17：SDK compatibility audit

- 目标：只读检查公开 SDK 仓库，整理当前 fake sandbox 的 Entities、Tasks、Objects、WebSocket 字段和真实公开 SDK/schema 的差异。
- 输入参考仓库：`external/lattice-sdk-python`、`external/lattice-sdk-javascript`、`external/lattice-sdk-go`、`external/lattice-sdk-java`、`external/lattice-sdk-ais-integration-grpc`、`external/archived/lattice-sdk-cpp`、`external/archived/lattice-sdk-rust`。
- 产出文件：建议新增 `docs/step-17-sdk-compatibility-audit.md`，列出字段差异、接口差异、当前刻意简化点和后续是否值得兼容。
- 不做什么：不安装 SDK，不生成 SDK client，不调用真实 API，不为了兼容性牺牲当前本地学习版的简单性。
- 验证方式：人工审阅 SDK 的 README、reference 和资源目录，形成对照表，并确认当前项目仍能通过本地 API、UI、WebSocket 和工具脚本验证。

