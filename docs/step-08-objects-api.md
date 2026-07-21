# Step 08: 本地 Objects API

## 本步骤目标

本步骤给本地 fake Lattice sandbox 增加 Objects API，用本地文件夹模拟对象上传、metadata 查询、原始文件下载、删除和 WebSocket 事件广播。

本步骤不调用 Anduril API，不使用真实 token，不实现认证，不依赖 Anduril SDK，也不修改 `external/sample-app-ais-integration-rest`。

## 为什么需要 Objects API

Objects 可以用来表示单个文件或一段数据。在本地学习版中，它适合模拟：

- track thumbnail。
- vessel manifest。
- 任务附件。
- 图片。
- 文本报告。
- entity 或 task 的备注文件。

当前实现只服务于本地开发和 curl 验证，不模拟真实 Lattice CDN、mesh 分发、权限控制或生产对象存储。

## object 数据模型

每个 object metadata 包含：

```json
{
  "objectId": "OBJ_20260529_120000_ABC123",
  "filename": "object-note.txt",
  "storedFilename": "OBJ_20260529_120000_ABC123_object-note.txt",
  "contentType": "text/plain",
  "sizeBytes": 123,
  "sha256": "...",
  "relatedEntityId": "AIS_SIM_MMSI_366000000",
  "relatedTaskId": "TASK_20260529_120000_ABC123",
  "description": "本地 Objects API 示例文件",
  "metadata": {
    "createdFrom": "curl"
  },
  "createdAt": "2026-05-29T12:00:00Z",
  "updatedAt": "2026-05-29T12:00:00Z"
}
```

`objectId` 由服务端生成。上传文件名会先做安全处理，避免路径穿越；本地实际保存文件名使用 `objectId` 加安全文件名。

## API 说明

### 上传 object

```text
POST /api/v1/objects
```

使用 `multipart/form-data`。

表单字段：

- `file`：必填，上传文件。
- `relatedEntityId`：可选，关联 entity。
- `relatedTaskId`：可选，关联 task。
- `description`：可选，描述。
- `metadata`：可选，JSON 字符串，必须解析为 JSON 对象。

限制：

- 文件大小不能超过 20MB。
- 不限制文件类型。
- `contentType` 来自上传表单中的 content type，缺失时使用 `application/octet-stream`。
- 客户端不能指定 `objectId`、`storedFilename` 或本地保存路径。

### 查询 objects

```text
GET /api/v1/objects
```

返回：

```json
{
  "count": 1,
  "objects": []
}
```

支持 query 参数：

- `relatedEntityId`
- `relatedTaskId`
- `contentType`

### 查询单个 object metadata

```text
GET /api/v1/objects/{object_id}
```

如果 object 不存在，返回 `404`。

### 下载 object

```text
GET /api/v1/objects/{object_id}/download
```

返回本地保存的原始文件。如果 metadata 存在但本地文件丢失，返回 `404`。

### 删除 object

```text
DELETE /api/v1/objects/{object_id}
```

删除 metadata 和 `objects/` 下的本地文件。返回：

```json
{
  "deleted": true,
  "objectId": "OBJ_20260529_120000_ABC123"
}
```

## 本地存储说明

新增本地存储：

```text
data/objects_store.json
objects/
```

`data/objects_store.json` 结构：

```json
{
  "objects": {
    "OBJ_20260529_120000_ABC123": {
      "objectId": "OBJ_20260529_120000_ABC123"
    }
  }
}
```

`objects/` 保存真实上传文件，例如：

```text
objects/OBJ_20260529_120000_ABC123_object-note.txt
```

服务启动时会自动创建 `data/`、`data/objects_store.json` 和 `objects/`。

## WebSocket 事件说明

Objects API 复用现有 stream：

```text
WS /api/v1/entities/stream
```

新增事件：

```text
object.created
object.deleted
```

创建事件：

```json
{
  "type": "object.created",
  "objectId": "OBJ_20260529_120000_ABC123",
  "object": {
    "objectId": "OBJ_20260529_120000_ABC123"
  },
  "timestamp": "2026-05-29T12:00:00Z"
}
```

删除事件：

```json
{
  "type": "object.deleted",
  "objectId": "OBJ_20260529_120000_ABC123",
  "timestamp": "2026-05-29T12:00:00Z"
}
```

已有事件保持不变：

- `stream.connected`
- `entity.upserted`
- `entity.deleted`
- `task.created`
- `task.status_updated`
- `task.deleted`

## curl 测试步骤

启动 mock server：

```bash
uvicorn mock_server:app --reload --port 8000
```

可选：启动 WebSocket watch：

```bash
python3 tools/watch_entities.py
```

创建并上传 entities，方便关联 `relatedEntityId`：

```bash
python generate_entities.py --count 5 --format json --output examples/entities.json
curl -X PUT http://127.0.0.1:8000/api/v1/entities \
  -H "Content-Type: application/json" \
  --data-binary @examples/entities.json
```

上传 object，并关联 entity：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/objects \
  -F "file=@examples/object-note.txt;type=text/plain" \
  -F "relatedEntityId=AIS_SIM_MMSI_366000000" \
  -F "description=本地 Objects API 示例文件" \
  -F 'metadata={"createdFrom":"curl","kind":"note"}'
```

上传 object，并关联 task：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/objects \
  -F "file=@examples/object-note.txt;type=text/plain" \
  -F "relatedTaskId=TASK_20260529_120000_ABC123" \
  -F "description=本地 task 附件" \
  -F 'metadata={"createdFrom":"curl","kind":"task_attachment"}'
```

查询 objects：

```bash
curl http://127.0.0.1:8000/api/v1/objects
curl "http://127.0.0.1:8000/api/v1/objects?relatedEntityId=AIS_SIM_MMSI_366000000"
curl "http://127.0.0.1:8000/api/v1/objects?contentType=text/plain"
```

查询单个 object metadata：

```bash
curl http://127.0.0.1:8000/api/v1/objects/OBJ_20260529_120000_ABC123
```

下载 object：

```bash
curl -L http://127.0.0.1:8000/api/v1/objects/OBJ_20260529_120000_ABC123/download \
  -o /tmp/downloaded-object-note.txt
```

删除 object：

```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/objects/OBJ_20260529_120000_ABC123
```

WebSocket watch 应看到 `object.created` 和 `object.deleted`。

## 当前实现和真实 Lattice Objects 的区别

当前实现是本地文件系统 mock，只用于学习和开发验证。它不代表真实 Lattice Objects 的协议、SDK、权限模型或存储实现。

真实系统可能涉及对象 CDN、mesh 分发、对象生命周期、访问控制、审计、加密、跨节点索引和更严格的数据治理；这些都不在本步骤范围内。

## 当前没有实现的内容

- 不调用 Anduril API。
- 不连接 Anduril Sandbox。
- 不使用真实 token。
- 不实现认证、授权或审计。
- 不依赖 Anduril SDK。
- 不实现真实 Lattice CDN。
- 不实现 mesh 分发。
- 不实现 TTL 生命周期管理。
- 不实现真实 SDK 兼容。
- 不实现大文件分片上传。
- 不实现跨节点查找。
- 不实现生产级安全扫描。
- 不实现对象 metadata 更新接口。
- 不实现对象列表分页、排序和全文搜索。

## 下一步建议

- 在任务面板中增加附件上传和附件列表。
- 在 entity marker popup 中增加 object 上传入口。
- 增加 object metadata 更新接口。
- 增加对象大小和 content type 的 UI 提示。
- 增加浏览器端测试，覆盖上传、下载和删除流程。
- 如果后续接入真实系统，应先明确真实 API schema、认证、权限和审计要求。
