# Step 06: 本地 Tasks API

## 本步骤目标

本步骤给本地 fake Lattice sandbox 增加最小 Tasks API，用于创建、查询、更新和删除模拟任务。

任务数据保存到 `data/tasks_store.json`。任务事件复用现有 `WS /api/v1/entities/stream` 广播，新增事件类型包括 `task.created`、`task.status_updated` 和 `task.deleted`。

本步骤不调用 Anduril API，不使用真实 token，不依赖 Anduril SDK，不实现认证，也不修改 `external/sample-app-ais-integration-rest`。

## 为什么需要 Tasks API

前几个步骤已经完成了本地 entity 生成、REST mock、WebSocket stream 和地图 UI。Tasks API 用来模拟围绕 entity 的任务工作流，例如对某个 AIS 模拟目标创建调查任务、更新任务状态、删除任务。

这个能力可以帮助后续验证：

- 本地任务 payload 结构。
- 任务和 entity 的关联字段。
- 任务状态更新流程。
- WebSocket 中 task 事件的消费方式。

## Task 数据模型

本地 task 包含以下字段：

| 字段 | 说明 |
| --- | --- |
| `taskId` | 服务端自动生成的任务 ID，例如 `TASK_20260529_120000_ABC123` |
| `taskType` | 任务类型，创建时必填 |
| `title` | 任务标题，创建时必填 |
| `description` | 任务描述，默认空字符串 |
| `status` | 任务状态，创建时默认为 `CREATED` |
| `priority` | 任务优先级，默认 `NORMAL` |
| `relatedEntityId` | 关联 entity id，可为空 |
| `assignedAssetId` | 分配资产 id，可为空 |
| `createdAt` | 创建时间，服务端生成 |
| `updatedAt` | 更新时间，服务端生成 |
| `metadata` | 扩展字段，必须是 JSON 对象，默认 `{}` |

创建请求示例见 `examples/task.json`：

```json
{
  "taskType": "INVESTIGATE_ENTITY",
  "title": "调查目标",
  "description": "对指定 entity 进行模拟调查任务",
  "priority": "NORMAL",
  "relatedEntityId": "AIS_SIM_MMSI_366000000",
  "assignedAssetId": "SIM_ASSET_001",
  "metadata": {
    "reason": "local test"
  }
}
```

## Task 状态机

允许状态：

```text
CREATED
ASSIGNED
ACCEPTED
IN_PROGRESS
SUCCEEDED
FAILED
CANCELED
```

当前实现采用宽松状态机：

- 只校验状态值是否属于允许集合。
- 不强制状态流转顺序。

推荐流转可以按以下方式理解：

```text
CREATED -> ASSIGNED -> ACCEPTED -> IN_PROGRESS -> SUCCEEDED
CREATED -> CANCELED
IN_PROGRESS -> FAILED
IN_PROGRESS -> CANCELED
```

## API 说明

### `POST /api/v1/tasks`

创建任务。

请求：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  --data-binary @examples/task.json
```

响应是完整 task：

```json
{
  "taskId": "TASK_20260529_120000_ABC123",
  "taskType": "INVESTIGATE_ENTITY",
  "title": "调查目标",
  "description": "对指定 entity 进行模拟调查任务",
  "status": "CREATED",
  "priority": "NORMAL",
  "relatedEntityId": "AIS_SIM_MMSI_366000000",
  "assignedAssetId": "SIM_ASSET_001",
  "createdAt": "2026-05-29T12:00:00Z",
  "updatedAt": "2026-05-29T12:00:00Z",
  "metadata": {
    "reason": "local test"
  }
}
```

### `GET /api/v1/tasks`

查询所有任务。

```bash
curl http://127.0.0.1:8000/api/v1/tasks
```

支持过滤：

```bash
curl "http://127.0.0.1:8000/api/v1/tasks?status=CREATED"
curl "http://127.0.0.1:8000/api/v1/tasks?relatedEntityId=AIS_SIM_MMSI_366000000"
```

响应：

```json
{
  "count": 1,
  "tasks": []
}
```

### `GET /api/v1/tasks/{task_id}`

查询单个任务。

```bash
curl http://127.0.0.1:8000/api/v1/tasks/TASK_20260529_120000_ABC123
```

如果不存在，返回 404。

### `PATCH /api/v1/tasks/{task_id}/status`

更新任务状态。

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/tasks/TASK_20260529_120000_ABC123/status \
  -H "Content-Type: application/json" \
  -d '{"status": "IN_PROGRESS"}'
```

如果 task 不存在，返回 404。如果状态不在允许集合中，返回 400。

### `DELETE /api/v1/tasks/{task_id}`

删除任务。

```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/tasks/TASK_20260529_120000_ABC123
```

成功响应：

```json
{
  "deleted": true,
  "taskId": "TASK_20260529_120000_ABC123"
}
```

如果 task 不存在，返回 404。

## 数据存储说明

任务保存到：

```text
data/tasks_store.json
```

文件不存在时自动创建。

结构：

```json
{
  "tasks": {
    "TASK_ID": {
      "taskId": "TASK_ID"
    }
  }
}
```

该文件是本地开发存储，不是数据库，不提供事务保证。

## WebSocket 事件说明

Tasks API 复用现有 WebSocket：

```text
WS /api/v1/entities/stream
```

连接后仍会收到原有欢迎消息：

```json
{
  "type": "stream.connected",
  "message": "已连接到本地 entity stream",
  "timestamp": "2026-05-29T12:00:00Z"
}
```

创建任务后广播：

```json
{
  "type": "task.created",
  "taskId": "TASK_20260529_120000_ABC123",
  "task": {},
  "timestamp": "2026-05-29T12:00:00Z"
}
```

状态更新后广播：

```json
{
  "type": "task.status_updated",
  "taskId": "TASK_20260529_120000_ABC123",
  "status": "IN_PROGRESS",
  "task": {},
  "timestamp": "2026-05-29T12:05:00Z"
}
```

删除任务后广播：

```json
{
  "type": "task.deleted",
  "taskId": "TASK_20260529_120000_ABC123",
  "timestamp": "2026-05-29T12:10:00Z"
}
```

## curl 测试步骤

启动服务：

```bash
uvicorn mock_server:app --reload --host 127.0.0.1 --port 8000
```

创建任务：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  --data-binary @examples/task.json
```

查询所有任务：

```bash
curl http://127.0.0.1:8000/api/v1/tasks
```

按状态查询：

```bash
curl "http://127.0.0.1:8000/api/v1/tasks?status=CREATED"
```

按关联 entity 查询：

```bash
curl "http://127.0.0.1:8000/api/v1/tasks?relatedEntityId=AIS_SIM_MMSI_366000000"
```

更新状态：

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/tasks/<TASK_ID>/status \
  -H "Content-Type: application/json" \
  -d '{"status": "IN_PROGRESS"}'
```

删除任务：

```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/tasks/<TASK_ID>
```

观察 WebSocket 事件：

```bash
python3 tools/watch_entities.py
```

## 当前实现和真实 Lattice Tasks API 的区别

当前实现只是本地 mock：

- 不实现真实 Lattice Tasks 协议。
- 不调用 Anduril API。
- 不使用 Anduril SDK。
- 不实现认证、授权或租户隔离。
- 不保证字段名、状态名、URL 与真实 Lattice 一致。
- 不实现真实任务分配、执行、确认、回执或审计。
- 不实现多用户、多角色。
- 不实现数据库事务。
- 不实现跨进程 stream。
- 不校验 `relatedEntityId` 是否真实存在。

## 当前没有实现的内容

当前 Tasks API 没有实现：

- 认证和授权。
- 严格状态流转。
- task 评论、附件、对象或子任务。
- 任务指派确认。
- 任务历史记录。
- 多用户协作。
- 并发写入保护。
- 与 Anduril API 的任何网络通信。

## 下一步建议

后续可以按需要增加：

1. 在地图 UI 中展示与当前 entity 相关的 tasks。
2. 增加任务列表页面，用于创建、过滤和更新任务。
3. 增加严格状态流转规则。
4. 增加 `relatedEntityId` 存在性校验。
5. 增加任务历史事件记录。
