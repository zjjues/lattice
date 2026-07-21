# Lattice-style 本地模拟实体生成器

> 工程已经从最初的实体生成器扩展为一套本地 Fake Lattice 闭环演示系统。若要了解当前系统全貌、环境要求、目录职责和在另一台机器上的完整复刻步骤，请先阅读 [工程总览与环境复刻指南](./SYSTEM_OVERVIEW.md)。本文后续内容保留各功能的详细 API 和操作示例。

这个项目用于在本地生成 Lattice-style 的模拟 entity JSON。当前阶段只生成非敏感的 `Surface Vessel` 示例数据，适合用于 sample app、假数据管线、前端原型或 fake sandbox 的早期联调。

项目不会调用 Anduril API，不需要 Anduril Sandbox，不需要 token、client id、client secret，也不依赖 Anduril SDK。`generate_entities.py` 只使用 Python 标准库；本地 mock server 和 watch 客户端使用 FastAPI、Uvicorn 和 WebSockets，依赖写在 `requirements.txt` 中。

## 为什么不需要 Anduril SDK

本项目只生成本地 JSON 或 JSONL 文件，不负责把数据发送到 Lattice，也不实现认证、传输、订阅、状态同步或真实集成。因此没有必要引入 Anduril SDK。

换句话说，它模拟的是公开 Quickstart 中 entity 数据的大致形状，而不是模拟真实 Lattice 服务端行为。

## 和 Lattice Quickstart 的关系

Lattice Quickstart 中展示了 surface vessel entity 的公开示例形状。本项目参考这种 entity 的字段组织方式，生成结构相近的本地测试数据，包括：

- entity 标识
- 描述和存活状态
- 过期时间
- 名称 alias
- MMSI alternate id
- 军事视图中的 disposition 和 environment
- 经纬度位置
- ontology 分类
- provenance 来源信息
- AIS 风格 metadata 扩展字段

这些数据是本地模拟数据，不代表真实目标、真实资产或真实任务。

## 生成单个 entity.json

```bash
python3 generate_entities.py --format json --count 1 --output examples/entity.json
```

当 `--format json` 且 `--count 1` 时，输出文件是单个 JSON 对象。

## 生成多个 entities.jsonl

```bash
python3 generate_entities.py --format jsonl --count 10 --output examples/entities.jsonl
```

当 `--format jsonl` 时，输出文件每一行是一个 JSON 对象，适合流式读取或批量导入测试。

也可以输出 JSON 数组：

```bash
python3 generate_entities.py --format json --count 10 --output examples/entities.json
```

当 `--format json` 且 `--count` 大于 1 时，输出文件是 JSON 数组。

## 生成 AIS 风格模拟 entity

默认输出会生成 AIS 风格字段，包括稳定 MMSI、船名、MMSI alternate id、AIS 来源名称，以及 `metadata.ais` 扩展信息：

```bash
python3 generate_entities.py \
  --format jsonl \
  --count 3 \
  --start-mmsi 366000100 \
  --source-name local_ais_simulator \
  --output examples/ais_entities.jsonl
```

如果只想保留核心 entity 字段，可以关闭 AIS metadata：

```bash
python3 generate_entities.py \
  --format json \
  --count 1 \
  --no-include-ais-metadata \
  --output examples/entity_without_ais_metadata.json
```

## 命令行参数

```text
--count       生成 entity 数量，默认 1
--center-lat  随机位置中心点纬度，默认 33.69447852698943
--center-lon  随机位置中心点经度，默认 -117.9173785693163
--radius-deg  经纬度随机偏移半径，默认 0.05
--output      输出文件路径，默认 examples/entities.jsonl
--format      输出格式，可选 json 或 jsonl，默认 jsonl
--source-name 模拟 AIS 数据来源名称，默认 local_ais_simulator
--start-mmsi  模拟 MMSI 起始值，默认 366000000
--include-ais-metadata / --no-include-ais-metadata
              是否输出 metadata.ais 扩展字段，默认开启
```

程序会校验：

- `count >= 1`
- `center-lat` 在 `-90` 到 `90` 之间
- `center-lon` 在 `-180` 到 `180` 之间
- `radius-deg >= 0`
- `start-mmsi >= 0`
- `source-name` 非空

如果输出目录不存在，程序会自动创建。

## 本地 Mock Entities API

本仓库提供一个仅用于本地开发的 FastAPI mock server，用来接收 `generate_entities.py` 生成的 entity payload。它不会调用 Anduril API，不实现真实认证，也不依赖 Anduril SDK。

### 安装依赖

```bash
python3 -m pip install -r requirements.txt
```

### 启动 mock server

```bash
uvicorn mock_server:app --reload --host 127.0.0.1 --port 8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

### 生成并上传单个 entity

```bash
python3 generate_entities.py --format json --count 1 --output examples/entity.json
curl -X PUT http://127.0.0.1:8000/api/v1/entities \
  -H "Content-Type: application/json" \
  --data-binary @examples/entity.json
```

成功响应示例：

```json
{
  "upserted": 1,
  "entityIds": [
    "AIS_SIM_MMSI_366000000"
  ]
}
```

### 查询所有 entities

```bash
curl http://127.0.0.1:8000/api/v1/entities
```

返回格式：

```json
{
  "count": 1,
  "entities": [
    {
      "entityId": "AIS_SIM_MMSI_366000000"
    }
  ]
}
```

### 查询单个 entity

```bash
curl http://127.0.0.1:8000/api/v1/entities/AIS_SIM_MMSI_366000000
```

### 删除单个 entity

```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/entities/AIS_SIM_MMSI_366000000
```

本地 mock server 会把数据保存到 `data/entities_store.json`。如果该文件不存在，服务会自动创建。

## 本地 Entity Stream / Watch

mock server 还提供本地 WebSocket stream，用于观察 entity upsert 和 delete 事件。该能力只用于本地开发，不实现真实 Lattice stream/watch 协议，不需要 token，也不会调用 Anduril API。

### 启动 mock server

```bash
uvicorn mock_server:app --reload --host 127.0.0.1 --port 8000
```

### 启动 watch 客户端

在另一个终端启动监听：

```bash
python3 tools/watch_entities.py
```

默认连接：

```text
ws://127.0.0.1:8000/api/v1/entities/stream
```

也可以指定 URL：

```bash
python3 tools/watch_entities.py --url ws://127.0.0.1:8000/api/v1/entities/stream
```

连接成功后，watch 客户端会先收到：

```json
{
  "type": "stream.connected",
  "message": "已连接到本地 entity stream",
  "timestamp": "2026-05-29T00:00:00Z"
}
```

### 生成并 PUT entity

```bash
python3 generate_entities.py --format json --count 1 --output examples/entity.json
curl -X PUT http://127.0.0.1:8000/api/v1/entities \
  -H "Content-Type: application/json" \
  --data-binary @examples/entity.json
```

watch 客户端应该看到类似消息：

```json
{
  "type": "entity.upserted",
  "entityId": "AIS_SIM_MMSI_366000000",
  "entity": {
    "entityId": "AIS_SIM_MMSI_366000000"
  },
  "timestamp": "2026-05-29T00:00:00Z"
}
```

如果 PUT 的请求体是 entity 数组，每个 entity 会单独广播一条 `entity.upserted` 消息。

### 测试 DELETE 广播

```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/entities/AIS_SIM_MMSI_366000000
```

watch 客户端应该看到类似消息：

```json
{
  "type": "entity.deleted",
  "entityId": "AIS_SIM_MMSI_366000000",
  "timestamp": "2026-05-29T00:00:00Z"
}
```

## 本地地图 UI

mock server 提供一个最小浏览器监控 UI，用本地态势图显示 entities。页面打开时会调用 `GET /api/v1/entities` 加载已有 entities，并连接 `WS /api/v1/entities/stream` 实时接收 upsert 和 delete 事件。

态势图不依赖 Leaflet、OpenStreetMap 或外部 CDN。它根据 entity 经纬度在本地画布上渲染目标点、坐标网格和弹窗，适合离线演示。默认中心在 Orange County 附近，也可以通过 URL 指定初始地点：

```text
http://127.0.0.1:8000/?lat=31.2304&lon=121.4737&zoom=12
```

`demo_workflow.py` 也可以指定威胁事件的位置。只要创建的 entity 经纬度在指定地点附近，地图会自动缩放到 marker：

```bash
python3 tools/demo_workflow.py \
  --lat 31.2304 \
  --lon 121.4737 \
  --place-name "Shanghai port" \
  --anomaly-type "高速接近港区" \
  --threat-level HIGH
```

该 UI 不需要登录，不需要 token，不调用 Anduril API，也不依赖 Anduril SDK。态势图完全本地渲染，即使环境离线也能显示目标和任务流程。

### 启动 mock server

```bash
uvicorn mock_server:app --reload --host 127.0.0.1 --port 8000
```

### 打开地图页面

在浏览器打开：

```text
http://127.0.0.1:8000/
```

页面会显示：

- WebSocket 连接状态
- 当前 entity 数量
- 最近一条 stream 事件
- 本地态势图和 entity markers
- 右侧“威胁目标”列表：显示威胁等级、异常类型、传感器来源、处置建议
- 右侧“任务面板”：显示任务状态、处置建议、执行结果和附件

### 生成并 PUT entities

```bash
python3 generate_entities.py --format json --count 5 --output examples/entities.json
curl -X PUT http://127.0.0.1:8000/api/v1/entities \
  -H "Content-Type: application/json" \
  --data-binary @examples/entities.json
```

地图会为每个有合法经纬度的 entity 新增或更新 marker。marker popup 会显示：

- `entityId`
- `aliases.name`
- `mmsi`
- `speedKnots`
- `courseDegrees`
- `threatLevel`
- `anomalyType`
- `sensorSources`
- `recommendation`
- `provenance.sourceUpdateTime`
- “创建处置任务”按钮

### 测试删除 marker

```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/entities/AIS_SIM_MMSI_366000000
```

地图收到 `entity.deleted` stream 消息后，会移除对应 marker。

## 本地地图 UI 任务面板

地图 UI 右侧提供本地任务面板，用来查看、创建、更新和删除 `mock_server.py` 中已有的模拟 tasks。页面加载时会同时调用 `GET /api/v1/entities` 和 `GET /api/v1/tasks`，并通过同一个 WebSocket stream 同步 entity 和 task 事件。

该任务面板只用于本地开发演示，不调用 Anduril API，不使用真实 token，不实现认证，也不依赖 Anduril SDK。

### 打开地图 UI

启动 mock server：

```bash
uvicorn mock_server:app --reload --host 127.0.0.1 --port 8000
```

在浏览器打开：

```text
http://127.0.0.1:8000/
```

页面顶部显示 WebSocket 状态、entity 数量和最近事件；左侧是本地态势图，右侧是威胁目标列表和任务面板。态势图不依赖在线地图瓦片，演示时可以稳定显示目标点。

### 创建 entity

生成并上传一批 AIS 风格模拟 entities：

```bash
python3 generate_entities.py --format json --count 5 --output examples/entities.json
curl -X PUT http://127.0.0.1:8000/api/v1/entities \
  -H "Content-Type: application/json" \
  --data-binary @examples/entities.json
```

上传成功后，地图会显示对应 marker。后续 `entity.upserted` 和 `entity.deleted` 会通过 WebSocket 自动更新地图。

### 从 marker popup 或威胁目标列表创建处置任务

点击地图上的 entity marker，popup 中会显示“创建处置任务”按钮。也可以直接在右侧“威胁目标”列表中点击“创建处置任务”。点击后前端会调用：

```text
POST /api/v1/tasks
```

请求体固定为：

```json
{
  "taskType": "RESPOND_TO_THREAT",
  "title": "处置疑似威胁目标",
  "description": "<处置建议>",
  "priority": "NORMAL",
  "relatedEntityId": "<当前 entityId>",
  "assignedAssetId": "SIM_ASSET_001",
  "metadata": {
    "createdFrom": "map_popup",
    "threatAnalysis": {
      "threatLevel": "HIGH",
      "anomalyType": "高速接近限制区域",
      "sensorSources": ["AIS", "岸基雷达", "光电观察哨"],
      "recommendation": "<建议动作>"
    }
  }
}
```

创建成功后，顶部最近事件会显示创建结果。WebSocket 可用时，任务面板通过 `task.created` 自动新增任务；WebSocket 不可用时，前端会使用 `POST` 返回的 task 直接更新任务面板。

### 查看任务面板

任务面板显示：

- `taskId`
- `title`
- `status`
- `relatedEntityId`
- `assignedAssetId`
- `recommend`
- `result`
- `createdAt`
- `updatedAt`

点击“刷新任务”会重新调用 `GET /api/v1/tasks`，并按 `createdAt` 倒序刷新右侧列表。

`relatedEntityId` 会显示为可点击按钮。点击后，如果地图上存在对应 marker，前端会移动地图并打开 marker popup；如果 marker 不存在，顶部最近事件会提示找不到对应 entity marker。

### 更新任务状态

每个任务卡片提供以下状态按钮：

```text
ASSIGNED
IN_PROGRESS
SUCCEEDED
FAILED
CANCELED
```

点击状态按钮会调用：

```text
PATCH /api/v1/tasks/{task_id}/status
```

请求体格式：

```json
{"status": "<目标状态>"}
```

更新成功后，顶部最近事件会显示状态更新结果。WebSocket 可用时，任务面板通过 `task.status_updated` 自动更新；WebSocket 不可用时，前端会使用 `PATCH` 返回的 task 直接更新任务面板。

### 删除任务

每个任务卡片都有“删除任务”按钮。点击后会调用：

```text
DELETE /api/v1/tasks/{task_id}
```

删除成功后，顶部最近事件会显示删除结果。WebSocket 可用时，任务面板通过 `task.deleted` 自动移除任务；WebSocket 不可用时，前端会直接调用本地 `deleteTask(taskId)` 作为兜底。

### WebSocket 同步任务事件

任务面板复用当前 stream：

```text
WS /api/v1/entities/stream
```

前端同时处理：

- `entity.upserted`
- `entity.deleted`
- `task.created`
- `task.status_updated`
- `task.deleted`

收到 `task.created` 或 `task.status_updated` 时，前端会新增或更新任务卡片。收到 `task.deleted` 时，前端会从任务面板移除对应任务。

## 本地 Tasks API

mock server 提供最小本地 Tasks API，用于创建、查询、更新和删除模拟任务。任务保存在 `data/tasks_store.json`。该能力只用于本地开发，不实现真实 Lattice Tasks 协议，不需要 token，也不会调用 Anduril API。

### 创建任务

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  --data-binary @examples/task.json
```

响应是完整 task，例如：

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

### 查询所有任务

```bash
curl http://127.0.0.1:8000/api/v1/tasks
```

返回格式：

```json
{
  "count": 1,
  "tasks": []
}
```

### 按状态查询任务

```bash
curl "http://127.0.0.1:8000/api/v1/tasks?status=CREATED"
```

### 按 relatedEntityId 查询任务

```bash
curl "http://127.0.0.1:8000/api/v1/tasks?relatedEntityId=AIS_SIM_MMSI_366000000"
```

### 查询单个任务

```bash
curl http://127.0.0.1:8000/api/v1/tasks/TASK_20260529_120000_ABC123
```

### 更新任务状态

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

更新示例：

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/tasks/TASK_20260529_120000_ABC123/status \
  -H "Content-Type: application/json" \
  -d '{"status": "IN_PROGRESS"}'
```

### 删除任务

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

### WebSocket task 事件

Tasks API 复用现有 stream：

```text
ws://127.0.0.1:8000/api/v1/entities/stream
```

创建、更新状态、删除任务时，watch 客户端会分别看到：

```text
task.created
task.status_updated
task.deleted
```

## 本地 Objects API

mock server 提供本地 Objects API，用 `objects/` 目录保存真实上传文件，用 `data/objects_store.json` 保存 object metadata。该能力只用于本地 fake sandbox 学习和联调，不调用 Anduril API，不使用真实 token，不实现认证，也不依赖 Anduril SDK。

Objects 可用于模拟 track thumbnail、vessel manifest、任务附件、图片、文本报告或 entity 备注文件。

### 安装依赖

Objects API 使用 `multipart/form-data` 上传文件，需要安装 `requirements.txt` 中的 `python-multipart`：

```bash
python3 -m pip install -r requirements.txt
```

### 启动 mock server

```bash
uvicorn mock_server:app --reload --host 127.0.0.1 --port 8000
```

服务启动时会自动创建：

```text
data/objects_store.json
objects/
```

### 上传 object

上传 `examples/object-note.txt`：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/objects \
  -F "file=@examples/object-note.txt;type=text/plain" \
  -F "description=本地 Objects API 示例文件" \
  -F 'metadata={"createdFrom":"curl","kind":"note"}'
```

返回完整 object metadata：

```json
{
  "objectId": "OBJ_20260529_120000_ABC123",
  "filename": "object-note.txt",
  "storedFilename": "OBJ_20260529_120000_ABC123_object-note.txt",
  "contentType": "text/plain",
  "sizeBytes": 123,
  "sha256": "...",
  "relatedEntityId": null,
  "relatedTaskId": null,
  "description": "本地 Objects API 示例文件",
  "metadata": {
    "createdFrom": "curl",
    "kind": "note"
  },
  "createdAt": "2026-05-29T12:00:00Z",
  "updatedAt": "2026-05-29T12:00:00Z"
}
```

第一版限制：

- 最大文件大小 20MB。
- 不限制文件类型。
- 服务端记录 `contentType`。
- 服务端生成 `objectId`。
- 上传文件名会做安全处理，避免路径穿越。
- 客户端不能指定本地存储路径。

### 关联 relatedEntityId

先创建并上传 entities：

```bash
python generate_entities.py --count 5 --format json --output examples/entities.json
curl -X PUT http://127.0.0.1:8000/api/v1/entities \
  -H "Content-Type: application/json" \
  --data-binary @examples/entities.json
```

上传 object 时关联 entity：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/objects \
  -F "file=@examples/object-note.txt;type=text/plain" \
  -F "relatedEntityId=AIS_SIM_MMSI_366000000" \
  -F "description=关联 entity 的本地附件" \
  -F 'metadata={"createdFrom":"curl","kind":"entity_note"}'
```

### 关联 relatedTaskId

上传 object 时关联已有 task：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/objects \
  -F "file=@examples/object-note.txt;type=text/plain" \
  -F "relatedTaskId=TASK_20260529_120000_ABC123" \
  -F "description=关联 task 的本地附件" \
  -F 'metadata={"createdFrom":"curl","kind":"task_attachment"}'
```

### 查询 objects

查询所有 objects：

```bash
curl http://127.0.0.1:8000/api/v1/objects
```

按 `relatedEntityId` 查询：

```bash
curl "http://127.0.0.1:8000/api/v1/objects?relatedEntityId=AIS_SIM_MMSI_366000000"
```

按 `relatedTaskId` 查询：

```bash
curl "http://127.0.0.1:8000/api/v1/objects?relatedTaskId=TASK_20260529_120000_ABC123"
```

按 `contentType` 查询：

```bash
curl "http://127.0.0.1:8000/api/v1/objects?contentType=text/plain"
```

查询单个 object metadata：

```bash
curl http://127.0.0.1:8000/api/v1/objects/OBJ_20260529_120000_ABC123
```

### 下载 object

```bash
curl -L http://127.0.0.1:8000/api/v1/objects/OBJ_20260529_120000_ABC123/download \
  -o /tmp/downloaded-object-note.txt
```

### 删除 object

```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/objects/OBJ_20260529_120000_ABC123
```

成功响应：

```json
{
  "deleted": true,
  "objectId": "OBJ_20260529_120000_ABC123"
}
```

### WebSocket object 事件

Objects API 复用现有 stream：

```text
ws://127.0.0.1:8000/api/v1/entities/stream
```

创建和删除 object 时，watch 客户端会分别看到：

```text
object.created
object.deleted
```

当前本地版本不实现真实 Lattice CDN、mesh 分发、TTL 生命周期管理、权限控制、真实 SDK 兼容、大文件分片上传、跨节点查找或生产级安全扫描。

## 本地地图 UI Objects 附件

地图 UI 已经把本地 Objects API 接入 entity marker popup 和任务面板。页面加载时会调用 `GET /api/v1/objects`，前端用 `objects Map` 保存 object metadata，并通过 WebSocket 同步 `object.created` 和 `object.deleted`。

该 UI 只用于本地 fake sandbox，不调用 Anduril API，不使用真实 token，不实现认证，也不依赖 Anduril SDK。

### 打开 UI

安装依赖并启动 mock server：

```bash
python3 -m pip install -r requirements.txt
uvicorn mock_server:app --reload --host 127.0.0.1 --port 8000
```

生成并上传 entities：

```bash
python generate_entities.py --count 5 --format json --output examples/entities.json
curl -X PUT http://127.0.0.1:8000/api/v1/entities \
  -H "Content-Type: application/json" \
  --data-binary @examples/entities.json
```

在浏览器打开：

```text
http://127.0.0.1:8000/
```

### 给 entity 上传附件

点击地图上的 entity marker，popup 中会显示“关联附件”区域。选择文件、填写可选描述，然后点击“上传附件”。

前端会调用：

```text
POST /api/v1/objects
```

上传表单包含：

```text
file=<选择的文件>
relatedEntityId=<当前 entityId>
description=<附件描述>
metadata={"createdFrom":"entity_popup"}
```

上传成功后，附件会显示在该 marker popup 的“关联附件”列表中。

### 给 task 上传附件

任务面板中的每个 task card 都有“任务附件”区域。选择文件、填写可选描述，然后点击“上传附件”。

前端会调用：

```text
POST /api/v1/objects
```

上传表单包含：

```text
file=<选择的文件>
relatedTaskId=<当前 taskId>
description=<附件描述>
metadata={"createdFrom":"task_panel"}
```

上传成功后，附件会显示在该 task card 的“任务附件”列表中。

### 附件显示字段

每个附件显示：

- `objectId`
- `filename`
- `contentType`
- `sizeBytes`
- `description`
- `createdAt`

### 下载附件

点击附件的“下载”按钮，前端会打开：

```text
GET /api/v1/objects/{object_id}/download
```

### 删除附件

点击附件的“删除”按钮，前端会调用：

```text
DELETE /api/v1/objects/{object_id}
```

删除成功后，附件会从相关 entity popup 或 task card 中移除。WebSocket 不可用时，前端会使用 HTTP 删除结果做本地兜底更新。

### WebSocket object 同步

地图 UI 复用现有 stream：

```text
WS /api/v1/entities/stream
```

前端新增处理：

```text
object.created
object.deleted
```

收到 `object.created` 时，前端会更新 `objects Map` 并刷新 marker popup 与任务面板。收到 `object.deleted` 时，前端会从 `objects Map` 删除对应 object 并刷新 UI。

当前 UI 没有实现全局对象管理器、附件预览、上传进度条、断点续传、权限控制、真实 Lattice Objects UI 或真实 CDN 下载地址。

## 本地模拟 Agent / Asset

`tools/sim_agent.py` 可以模拟一个本地 taskable agent / asset，例如 `SIM_ASSET_001`。它会定期查询 Tasks API，找到分配给自己的任务，并自动把任务状态从 `CREATED` 或 `ASSIGNED` 推进到 `ACCEPTED`、`IN_PROGRESS`，最后变成 `SUCCEEDED` 或 `FAILED`。

该脚本只调用本地 mock server，不调用 Anduril API，不使用真实 token，不实现认证，也不依赖 Anduril SDK。

### 启动 mock server

```bash
uvicorn mock_server:app --reload --host 127.0.0.1 --port 8000
```

### 打开地图 UI

```text
http://127.0.0.1:8000/
```

### 生成并上传 entity

```bash
python generate_entities.py --count 5 --format json --output examples/entities.json
curl -X PUT http://127.0.0.1:8000/api/v1/entities \
  -H "Content-Type: application/json" \
  --data-binary @examples/entities.json
```

### 创建威胁响应任务

在地图 UI 中点击任意 entity marker，然后点击 popup 里的“创建处置任务”；或者在右侧“威胁目标”列表点击“创建处置任务”。前端创建的任务默认包含：

```text
assignedAssetId=SIM_ASSET_001
taskType=RESPOND_TO_THREAT
```

### 启动 sim_agent.py

```bash
python3 tools/sim_agent.py --asset-id SIM_ASSET_001 --verbose
```

任务面板会通过 WebSocket 看到状态自动变化：

```text
CREATED 或 ASSIGNED
  → ACCEPTED
  → IN_PROGRESS
  → SUCCEEDED 或 FAILED
```

### 使用 --once

只处理当前轮询看到的一轮任务，然后退出：

```bash
python3 tools/sim_agent.py --once --verbose
```

### 指定 --asset-id

只处理 `assignedAssetId` 匹配的任务：

```bash
python3 tools/sim_agent.py --asset-id SIM_ASSET_002 --verbose
```

如果没有任务分配给 `SIM_ASSET_002`，脚本会继续等待，或在 `--once` 模式下处理一轮后退出。

### 调整 --success-rate

默认成功率是 `0.9`：

```bash
python3 tools/sim_agent.py --success-rate 0.9
```

强制成功：

```bash
python3 tools/sim_agent.py --success-rate 1 --once --verbose
```

强制失败：

```bash
python3 tools/sim_agent.py --success-rate 0 --once --verbose
```

### 常用参数

```text
--base-url       mock server 地址，默认 http://127.0.0.1:8000
--asset-id       当前模拟 asset id，默认 SIM_ASSET_001
--poll-interval  轮询间隔秒数，默认 3
--work-seconds   模拟执行秒数，默认 5
--success-rate   成功概率，默认 0.9
--once           只处理一轮后退出
--verbose        输出详细日志
```

当前模拟 agent 不实现真实任务调度、task claim / lease、agent heartbeat、跨进程互斥、真实任务执行、真实审计或真实 Lattice agent 协议。

## 一键演示工作流

`tools/demo_workflow.py` 用来把 fake Lattice 后端的最小闭环封装成一条命令，适合给 Codex、Claude Code 或命令行演示调用。

默认模式会在脚本内部推进任务状态：

```bash
uvicorn mock_server:app --host 127.0.0.1 --port 8000
python3 tools/demo_workflow.py
```

它会依次完成：

```text
fake OAuth -> 创建 AIS entity -> 创建 Investigation task -> 推进任务状态 -> 上传任务报告 object
```

默认演示现在按“监控发现威胁”的故事组织：

```text
监控界面接收 AIS / 雷达 / 光电观察哨数据
  -> 发现一个疑似威胁目标 entity
  -> 根据规则生成处置建议
  -> 创建威胁响应 task
  -> agent 执行 task
  -> 状态和处置结果回流
  -> 上传 task report object
```

任务完成时会写入 `resultSummary`。地图右侧任务面板会显示这段处置结论，任务附件区域会出现自动上传的 `demo-task-report.txt`。演示时可以重点指给别人看：

```text
任务状态：SUCCEEDED
recommend：建议派遣 SIM_ASSET_001...
result：处置完成...
任务附件：demo-task-report.txt
```

输出示例：

```text
[1] fake auth ok
[2] entity created: AIS_DEMO_MMSI_366123456
[3] response task created: TASK_20260625_010000_ABC123
[3] recommendation: 建议派遣 SIM_ASSET_001...
[4] advancing task inline
[5] task status -> ACCEPTED
[5] task status -> IN_PROGRESS
[5] task status -> SUCCEEDED
[6] report object uploaded: OBJ_20260625_010001_DEF456
[7] workflow complete: entity=AIS_DEMO_MMSI_366123456 task=TASK_... status=SUCCEEDED
```

也可以让外部模拟 agent 处理任务。先启动 server，再启动 agent，最后运行 workflow：

```bash
uvicorn mock_server:app --host 127.0.0.1 --port 8000
python3 tools/sim_agent.py --asset-id SIM_ASSET_001 --verbose
python3 tools/demo_workflow.py --use-external-agent
```

这个模式会创建任务后等待 `tools/sim_agent.py` 把任务推进到终态。

### fake OAuth

mock server 提供最小 OAuth 端点：

```text
POST /api/v1/oauth/token
```

它接受 JSON 或表单请求，并返回固定的 fake token：

```json
{
  "access_token": "fake_lattice_token",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

这个 token 只用于演示“先认证、再调用 API”的流程。当前后端接受 `Authorization: Bearer fake_lattice_token`，但不做真实身份认证、权限校验或租户隔离。

## 输出字段含义

- `entityId`：本地模拟 entity 的唯一标识，格式为 `AIS_SIM_MMSI_<mmsi>`。
- `description`：模拟实体的简短描述。
- `createdTime`：entity 创建时间，使用当前 UTC 时间。
- `isLive`：表示 entity 当前是否被视为 live。
- `expiryTime`：过期时间，使用当前 UTC 时间加 1 小时。
- `aliases.name`：entity 的显示名称，使用模拟船名。
- `aliases.alternateIds`：模拟 MMSI alternate id，类型为 `ALT_ID_TYPE_MMSI_ID`。
- `milView.disposition`：模拟军事视图中的关系属性。
- `milView.environment`：模拟实体所在环境，此处为 `ENVIRONMENT_SURFACE`。
- `location.position.latitudeDegrees`：纬度。
- `location.position.longitudeDegrees`：经度。
- `location.position.altitudeHaeMeters`：HAE 高度，水面舰船示例中固定为 `0`。
- `ontology.template`：模拟 ontology 模板。
- `ontology.platformType`：平台类型，此处为 `Surface Vessel`。
- `ontology.specificType`：具体类型，此处为 `SURFACE_VESSEL`。
- `provenance.integrationName`：本地模拟集成名称。
- `provenance.dataType`：本地模拟数据类型。
- `provenance.sourceName`：模拟 AIS 数据来源名称。
- `provenance.sourceId`：模拟 AIS 数据来源标识。
- `provenance.sourceUpdateTime`：来源更新时间，使用当前 UTC 时间。
- `metadata.ais.mmsi`：模拟 MMSI。
- `metadata.ais.vesselName`：模拟船名。
- `metadata.ais.speedKnots`：模拟航速，单位为节。
- `metadata.ais.courseDegrees`：模拟对地航向角。
- `metadata.ais.headingDegrees`：模拟船首向。
- `metadata.ais.navigationStatus`：模拟 AIS 航行状态。
- `dataClassification.default.level`：本地非敏感分类标记，固定为 `CLASSIFICATION_LEVELS_UNCLASSIFIED`。

## 当前阶段没有实现的内容

本阶段只负责生成本地测试数据和本地 mock API，没有实现以下内容：

- 不调用 Anduril API。
- 不连接 Anduril Sandbox。
- 只提供 fake OAuth token，不处理真实 token、client id 或 client secret。
- 不依赖 Anduril SDK。
- 不向真实 Lattice 上传、订阅或同步 entity。
- 不实现真实身份认证、授权或审计。
- 不模拟完整 Lattice 后端。
- 不保证字段集合覆盖真实生产 schema。

下一阶段可以把这些本地 JSON 或 JSONL 文件接入 sample app，或者由 fake sandbox 读取后提供本地 HTTP API。
