# Step 07: 地图 UI 任务面板

## 本步骤目标

本步骤在本地地图 UI 中增加任务面板，并支持从 entity marker popup 创建“调查任务”。前端可以查看任务、更新任务状态、删除任务，通过 WebSocket 同步 task 事件，并通过 `relatedEntityId` 定位对应 marker。

本步骤不调用 Anduril API，不使用真实 token，不依赖 Anduril SDK，不实现认证，也不修改 `external/sample-app-ais-integration-rest`。

## UI 新增内容

页面布局为：

```text
顶部状态栏
  ↓
主体区域
  ├─ 左侧 Leaflet 地图
  └─ 右侧任务面板
```

右侧任务面板包含：

- 标题“任务面板”。
- “刷新任务”按钮。
- 当前任务数量。
- `task-list` 任务列表容器。

每个任务卡片显示：

- `taskId`
- `title`
- `status`
- `relatedEntityId`
- `assignedAssetId`
- `createdAt`
- `updatedAt`

每个任务卡片还包含状态更新按钮和删除按钮。`relatedEntityId` 显示为可点击按钮，用于定位地图上的对应 marker。

## 数据流说明

```text
浏览器打开 /
  ↓
加载 static/index.html / static/style.css / static/app.js
  ↓
初始化 Leaflet 地图
  ↓
GET /api/v1/entities
  ↓
创建或更新 markers
  ↓
GET /api/v1/tasks
  ↓
写入 tasks Map 并调用 renderTaskPanel()
  ↓
连接 WS /api/v1/entities/stream
  ↓
根据 entity 和 task 事件更新地图与任务面板
```

前端状态包括：

```text
markers: Map<entityId, LeafletMarker>
tasks: Map<taskId, task>
```

`tasks` 使用 `taskId` 作为 key。渲染时会按 `createdAt` 倒序显示。

## 任务创建流程

每个 entity marker popup 中都有“创建调查任务”按钮。按钮通过 DOM 事件绑定调用：

```text
createTaskForEntity(entityId)
```

前端随后调用：

```text
POST /api/v1/tasks
```

请求体为：

```json
{
  "taskType": "INVESTIGATE_ENTITY",
  "title": "调查目标",
  "description": "对指定 entity 进行模拟调查任务",
  "priority": "NORMAL",
  "relatedEntityId": "<当前 entityId>",
  "assignedAssetId": "SIM_ASSET_001",
  "metadata": {
    "createdFrom": "map_popup"
  }
}
```

创建成功后，顶部最近事件会更新。WebSocket 可用时，任务面板通过 `task.created` 更新；WebSocket 不可用时，前端使用 `POST` 返回的 task 调用 `upsertTask(task)` 作为兜底。

## 任务状态更新流程

每个任务卡片提供以下状态按钮：

```text
ASSIGNED
IN_PROGRESS
SUCCEEDED
FAILED
CANCELED
```

点击按钮后，前端调用：

```text
PATCH /api/v1/tasks/{task_id}/status
```

请求体格式为：

```json
{"status": "<目标状态>"}
```

更新成功后，顶部最近事件会更新。WebSocket 可用时，任务面板通过 `task.status_updated` 更新；WebSocket 不可用时，前端使用 `PATCH` 返回的 task 调用 `upsertTask(task)` 作为兜底。

## 任务删除流程

每个任务卡片都有“删除任务”按钮。点击后，前端调用：

```text
DELETE /api/v1/tasks/{task_id}
```

删除成功后，顶部最近事件会更新。WebSocket 可用时，任务面板通过 `task.deleted` 移除任务；WebSocket 不可用时，前端调用 `deleteTask(taskId)` 作为兜底。

## WebSocket 同步说明

地图 UI 复用现有 stream：

```text
WS /api/v1/entities/stream
```

前端处理以下事件：

```text
stream.connected
entity.upserted
entity.deleted
task.created
task.status_updated
task.deleted
```

entity 事件更新地图 marker：

- `entity.upserted`：新增或更新 marker。
- `entity.deleted`：删除 marker。

task 事件更新任务面板：

- `task.created`：调用 `upsertTask(message.task)`。
- `task.status_updated`：调用 `upsertTask(message.task)`。
- `task.deleted`：调用 `deleteTask(message.taskId)`。

顶部“最近事件”会显示最近一次 entity 或 task 事件。

## relatedEntityId 定位 marker

任务卡片中的 `relatedEntityId` 是可点击按钮。点击后调用：

```text
focusEntity(entityId)
```

如果 `markers` Map 中存在对应 marker，地图会移动到该 marker 并打开 popup。如果不存在，顶部最近事件会提示找不到对应 entity marker。

## 当前实现和真实 Lattice tasking UI 的区别

当前实现是本地 mock UI，只演示任务交互的数据流。它使用本地 `mock_server.py` 和本地 JSON 存储，不实现真实 Lattice tasking UI 的权限、任务编排、资产分配、审计、地理约束、协作流程或生产级状态机。

当前 task schema 也是本地模拟形状，不代表真实 Lattice Tasks API schema。

## 当前没有实现的内容

- 不调用 Anduril API。
- 不连接 Anduril Sandbox。
- 不处理真实 token、client id 或 client secret。
- 不依赖 Anduril SDK。
- 不实现真实身份认证、授权、审计或权限控制。
- 不实现完整 Lattice tasking workflow。
- 不实现复杂任务过滤、搜索、分页和批量操作。
- 不保证字段集合覆盖真实生产 schema。

## 下一步建议

- 增加任务筛选和搜索。
- 增加任务详情抽屉或详情页。
- 为任务操作增加错误提示和加载状态。
- 增加浏览器端自动化测试，覆盖创建、更新、删除和定位 marker。
- 如果后续接入真实系统，应先明确真实 API schema、认证方式、权限模型和审计要求。

## 验证方法

启动服务：

```bash
uvicorn mock_server:app --reload --port 8000
```

生成并上传 entities：

```bash
python generate_entities.py --count 5 --format json --output examples/entities.json
curl -X PUT http://127.0.0.1:8000/api/v1/entities \
  -H "Content-Type: application/json" \
  --data-binary @examples/entities.json
```

打开页面：

```text
http://127.0.0.1:8000/
```

在浏览器中点击 marker popup 的“创建调查任务”按钮。随后可以用 curl 查询任务：

```bash
curl http://127.0.0.1:8000/api/v1/tasks
```

在 UI 中更新任务状态、删除任务，并点击 `relatedEntityId` 定位对应 marker。
