# Step 05: 本地地图 UI

## 本步骤目标

本步骤给本地 fake Lattice sandbox 增加一个最小浏览器地图 UI，用 Leaflet 显示保存在本地 mock API 中的 entities。

页面打开后会先调用 `GET /api/v1/entities` 加载当前已保存的 entities，然后连接 `WS /api/v1/entities/stream`。后续收到 `entity.upserted` 时新增或更新 marker，收到 `entity.deleted` 时删除 marker。

本步骤不调用 Anduril API，不使用真实 token，不依赖 Anduril SDK，不实现认证，也不修改 `external/sample-app-ais-integration-rest`。

## 为什么选择 Leaflet

Leaflet 是轻量的浏览器地图库，适合当前本地 mock 阶段：

- 不需要前端构建工具。
- 可以直接用 HTML、CSS 和 JavaScript 引入。
- 能快速显示 marker、popup 和 OpenStreetMap 底图。
- 与当前 FastAPI 静态文件服务配合简单。

当前实现通过 CDN 加载 Leaflet，并使用 OpenStreetMap tile layer。它不是 Anduril 地图服务，也不代表真实 Lattice UI。

## 新增文件说明

- `static/index.html`：地图 UI 页面。
- `static/app.js`：地图初始化、初始加载、WebSocket 连接、marker 管理逻辑。
- `static/style.css`：页面布局、状态栏和 popup 样式。
- `docs/step-05-map-ui.md`：本步骤说明文档。

同时 `mock_server.py` 增加：

- `app.mount("/static", StaticFiles(...))`：提供静态文件。
- `GET /`：返回 `static/index.html`。

现有 REST 和 WebSocket API 保持不变。

## 数据流说明

```text
浏览器打开 /
  ↓
加载 static/index.html / static/style.css / static/app.js
  ↓
GET /api/v1/entities
  ↓
对已有 entities 创建 markers
  ↓
连接 WS /api/v1/entities/stream
  ↓
PUT /api/v1/entities 触发 entity.upserted
  ↓
地图新增或更新 marker
  ↓
DELETE /api/v1/entities/{entity_id} 触发 entity.deleted
  ↓
地图删除 marker
```

## 初始加载说明

页面初始化后会调用：

```text
GET /api/v1/entities
```

期望响应格式：

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

前端会遍历 `entities`，对每个 entity 调用 `upsertMarker(entity)`。

如果 entity 缺少合法位置：

- `location.position.latitudeDegrees`
- `location.position.longitudeDegrees`

则该 entity 不会显示 marker，并会在浏览器 console 中输出 `console.warn`。

## WebSocket 实时更新说明

页面会根据当前访问协议自动选择 WebSocket 协议：

- `http:` 页面使用 `ws:`
- `https:` 页面使用 `wss:`

连接地址：

```text
ws://当前 host/api/v1/entities/stream
```

支持的消息：

```json
{
  "type": "stream.connected",
  "message": "已连接到本地 entity stream",
  "timestamp": "2026-05-29T00:00:00Z"
}
```

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

```json
{
  "type": "entity.deleted",
  "entityId": "AIS_SIM_MMSI_366000000",
  "timestamp": "2026-05-29T00:00:00Z"
}
```

## Marker 更新和删除逻辑

前端使用 JavaScript `Map` 保存 marker：

```text
entityId -> Leaflet marker
```

### Upsert

收到 `entity.upserted` 后：

1. 从 `entity.location.position` 读取经纬度。
2. 如果 marker 不存在，创建 marker。
3. 如果 marker 已存在，更新位置。
4. 更新 popup。
5. 更新页面上的 entity 数量和最近事件。

### Delete

收到 `entity.deleted` 后：

1. 根据 `entityId` 查找 marker。
2. 如果存在，从地图移除并从 `Map` 删除。
3. 更新页面上的 entity 数量和最近事件。
4. 如果 marker 不存在，只在 console 中提示，不影响页面运行。

## Popup 字段说明

marker popup 显示：

- `entityId`
- `aliases.name`
- `mmsi`
- `speedKnots`
- `courseDegrees`
- `provenance.sourceUpdateTime`

AIS 扩展字段会兼容以下位置：

- `metadata.ais`
- `metadata`
- `extensions.ais`
- `extensions`

## 测试步骤

安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

启动 mock server：

```bash
uvicorn mock_server:app --reload --host 127.0.0.1 --port 8000
```

打开地图页面：

```text
http://127.0.0.1:8000/
```

生成 entities：

```bash
python3 generate_entities.py --format json --count 5 --output examples/entities.json
```

PUT entities：

```bash
curl -X PUT http://127.0.0.1:8000/api/v1/entities \
  -H "Content-Type: application/json" \
  --data-binary @examples/entities.json
```

预期结果：

- 地图出现或更新 5 个 markers。
- 页面 entity 数量更新。
- 最近事件显示最新 `upsert`。
- marker popup 可查看 entity 字段。

测试删除：

```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/entities/AIS_SIM_MMSI_366000000
```

预期结果：

- 对应 marker 从地图移除。
- 页面 entity 数量减少。
- 最近事件显示 `delete AIS_SIM_MMSI_366000000`。

## 当前 UI 和真实 Lattice UI 的区别

当前地图 UI 只是本地开发 mock：

- 不实现真实 Lattice 登录。
- 不实现认证、授权或租户隔离。
- 不调用 Anduril API。
- 不依赖 Anduril SDK。
- 不实现真实 Lattice 协议。
- 不实现真实图层、任务、对象、告警、审计或权限。
- 不实现 track history。
- 不实现高级筛选、搜索、聚合或态势展示。
- 使用 Leaflet 和 OpenStreetMap 底图，不是 Anduril 地图服务。

## 下一步建议

后续可以按需要增加：

1. marker 航向箭头，用 `courseDegrees` 或 `headingDegrees` 表达方向。
2. entity 列表侧栏，用于搜索、定位和删除本地 entity。
3. marker clustering，支持更多 entities。
4. 历史轨迹，把同一 entity 的位置更新保存为 polyline。
5. 完全离线地图资源，将 Leaflet 和地图瓦片改成本地资源。
6. 简单过滤器，例如只显示特定 `sourceName` 或 MMSI 范围。
