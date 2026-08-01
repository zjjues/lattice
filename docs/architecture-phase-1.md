# 阶段 1：核心边界与兼容迁移

阶段 1 的目标是在不改变现有 HTTP API 和 JSON store 的前提下，把稳定业务边界从
`mock_server.py` 中抽离，便于后续接入 Cesium、MAVLink、ROS 2、本地模型和独立知识库。

## 新增核心模块

- `lattice_core.models`：共享的 ingest、entity、alert、recommendation、task 类型。
- `lattice_core.events`：带 `eventId`、`schemaVersion`、`source`、`subject` 和 `data` 的统一事件信封。
- `lattice_core.services`：与 FastAPI 和文件路径无关的 ingest 应用服务。
- `lattice_core.providers`：大模型、知识检索和建议生成的 Provider 契约。

## 兼容原则

1. 现有 `/api/v1/*` 路径和响应字段保持不变。
2. 现有 JSON store 暂不迁移，由服务依赖注入继续使用。
3. WebSocket 标准信封以增量字段加入，并保留原有顶层业务字段。
4. Dify 后续实现 `RecommendationProvider`，不会再成为业务核心的直接依赖。

## 后续适配器

MAVLink、ROS 2、JSBSim 和回放文件都应先转换成 `IngestEvent`，再调用 `IngestService`；
Cesium 只消费 entity 和领域事件，不直接依赖仿真平台协议。
