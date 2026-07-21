# Step 09: 地图 UI Objects 附件

## 本步骤目标

本步骤把本地 Objects API 接入地图 UI 和任务面板。页面会加载 object metadata，并在 entity marker popup 与 task card 中展示、上传、下载和删除附件。

本步骤不调用 Anduril API，不使用真实 token，不加入 Anduril SDK，不实现认证，也不修改 `external/sample-app-ais-integration-rest`。

## UI 新增内容

地图 UI 新增：

- 页面加载时调用 `GET /api/v1/objects`。
- 前端维护 `objects: Map<objectId, objectMetadata>`。
- entity marker popup 新增“关联附件”区域。
- task card 新增“任务附件”区域。
- entity 和 task 附件区都包含文件选择、描述输入、上传按钮、附件列表。
- 每个附件提供“下载”和“删除”按钮。

每个附件显示：

- `objectId`
- `filename`
- `contentType`
- `sizeBytes`
- `description`
- `createdAt`

## object 数据如何加载

页面初始化流程：

```text
DOMContentLoaded
  ↓
初始化 Leaflet 地图
  ↓
GET /api/v1/entities
  ↓
GET /api/v1/tasks
  ↓
GET /api/v1/objects
  ↓
连接 WS /api/v1/entities/stream
```

前端状态：

```text
entities: Map<entityId, entity>
markers: Map<entityId, LeafletMarker>
tasks: Map<taskId, task>
objects: Map<objectId, objectMetadata>
```

`objects` 更新后会刷新 marker popup 和任务面板。entity popup 根据 `relatedEntityId` 过滤附件，task card 根据 `relatedTaskId` 过滤附件。

## entity 附件流程

打开 entity marker popup 后，用户可以在“关联附件”区域选择文件并填写描述。

上传时前端调用：

```text
POST /api/v1/objects
```

表单内容：

```text
file=<选择的文件>
relatedEntityId=<当前 entityId>
description=<附件描述>
metadata={"createdFrom":"entity_popup"}
```

上传成功后：

- 顶部最近事件显示上传结果。
- WebSocket 正常时，UI 通过 `object.created` 刷新。
- WebSocket 不可用时，前端使用 POST 返回的 object 调用 `upsertObject(object)` 兜底。

## task 附件流程

每个 task card 都显示“任务附件”区域。用户可以选择文件并填写描述。

上传时前端调用：

```text
POST /api/v1/objects
```

表单内容：

```text
file=<选择的文件>
relatedTaskId=<当前 taskId>
description=<附件描述>
metadata={"createdFrom":"task_panel"}
```

上传成功后：

- 顶部最近事件显示上传结果。
- WebSocket 正常时，UI 通过 `object.created` 刷新。
- WebSocket 不可用时，前端使用 POST 返回的 object 调用 `upsertObject(object)` 兜底。

## 下载流程

每个附件都有“下载”按钮。点击后前端打开：

```text
GET /api/v1/objects/{object_id}/download
```

当前实现使用浏览器新窗口或新标签打开下载 URL。

## 删除流程

每个附件都有“删除”按钮。点击后前端调用：

```text
DELETE /api/v1/objects/{object_id}
```

删除成功后：

- 顶部最近事件显示删除结果。
- WebSocket 正常时，UI 通过 `object.deleted` 刷新。
- WebSocket 不可用时，前端调用 `deleteObject(objectId)` 兜底。

## WebSocket 同步说明

地图 UI 复用现有 stream：

```text
WS /api/v1/entities/stream
```

新增处理：

```text
object.created
object.deleted
```

收到 `object.created`：

```text
upsertObject(message.object)
```

收到 `object.deleted`：

```text
deleteObject(message.objectId)
```

已有事件保持不变：

- `stream.connected`
- `entity.upserted`
- `entity.deleted`
- `task.created`
- `task.status_updated`
- `task.deleted`

## 当前实现和真实 Lattice Objects UI 的区别

当前实现是本地 fake sandbox UI，只把 object metadata 和下载 URL 展示到地图 popup 与任务卡片中。它不代表真实 Lattice Objects UI、真实 CDN、mesh 分发状态、权限模型或生产对象治理能力。

真实系统可能包含认证、授权、审计、对象预览、缩略图、上传进度、断点续传、病毒扫描、生命周期策略、跨节点查找和更复杂的对象搜索能力。当前实现都不包含这些内容。

## 当前没有实现的内容

- 不调用 Anduril API。
- 不连接 Anduril Sandbox。
- 不使用真实 token。
- 不依赖 Anduril SDK。
- 不实现认证、授权或审计。
- 不实现全局 objects 面板。
- 不实现附件预览或图片缩略图。
- 不实现上传进度条。
- 不实现断点续传。
- 不实现大文件分片上传。
- 不实现对象 metadata 编辑。
- 不实现对象分页、排序、搜索和标签过滤。
- 不在删除 task 时级联删除 relatedTaskId 对象。

## 下一步建议

- 增加全局对象管理面板。
- 在任务面板中按附件数量显示更紧凑的摘要。
- 为图片对象增加缩略图预览。
- 增加上传进度和 20MB 限制提示。
- 增加 object metadata 编辑接口和 UI。
- 增加浏览器端自动化测试，覆盖 entity 附件和 task 附件流程。
