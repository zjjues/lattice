# Step 04: 本地 Entity Stream / Watch

## 本步骤目标

本步骤给本地 mock Lattice Entities API 增加 entity stream/watch 能力。

客户端连接 `WS /api/v1/entities/stream` 后，只要本地 `PUT /api/v1/entities` 成功 upsert entity，mock server 就会向所有已连接客户端广播 entity update。`DELETE /api/v1/entities/{entity_id}` 成功删除 entity 后，也会广播 delete 事件。

本步骤不调用 Anduril API，不使用真实 token，不依赖 Anduril SDK，不实现认证，也不修改 `external/sample-app-ais-integration-rest`。

## 为什么需要 Entity Stream / Watch

REST API 可以保存和查询当前 entity 状态，但不能让客户端实时知道 entity 何时发生变化。

本地 stream/watch 的目标是补齐一个最小开发闭环：

```text
generate_entities.py
  ↓
PUT /api/v1/entities
  ↓
data/entities_store.json
  ↓
WS /api/v1/entities/stream
  ↓
本地 watch 客户端或前端原型
```

这样可以先验证本地 entity payload、upsert、删除和实时通知流程，再考虑是否需要对接更复杂的 sample app 或真实环境。

## 新增接口说明

### `WS /api/v1/entities/stream`

WebSocket 地址：

```text
ws://127.0.0.1:8000/api/v1/entities/stream
```

连接建立后，服务端会发送一条欢迎消息：

```json
{
  "type": "stream.connected",
  "message": "已连接到本地 entity stream",
  "timestamp": "2026-05-29T00:00:00Z"
}
```

连接会保持打开，直到客户端主动断开或网络断开。

## 消息格式说明

### Entity Upsert 消息

当 `PUT /api/v1/entities` 成功保存 entity 后，每个 entity 会广播一条消息：

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

字段说明：

- `type`：事件类型，upsert 事件固定为 `entity.upserted`。
- `entityId`：被新增或更新的 entity id。
- `entity`：完整 entity payload。
- `timestamp`：mock server 广播时间，使用 UTC ISO 8601 字符串。

如果 PUT 请求体是 entity 数组，服务端会为每个 entity 单独广播一条 `entity.upserted` 消息。

### Entity Delete 消息

当 `DELETE /api/v1/entities/{entity_id}` 成功删除 entity 后，服务端会广播：

```json
{
  "type": "entity.deleted",
  "entityId": "AIS_SIM_MMSI_366000000",
  "timestamp": "2026-05-29T00:00:00Z"
}
```

## 数据流说明

### Upsert 数据流

```text
客户端 PUT 单个 entity 或 entity 数组
  ↓
mock_server.py 校验 entityId
  ↓
按 entityId upsert 到 data/entities_store.json
  ↓
对每个成功保存的 entity 构造 entity.upserted 消息
  ↓
ConnectionManager.broadcast(...)
  ↓
所有已连接 WebSocket 客户端收到消息
```

### Delete 数据流

```text
客户端 DELETE /api/v1/entities/{entity_id}
  ↓
mock_server.py 从 data/entities_store.json 删除 entity
  ↓
构造 entity.deleted 消息
  ↓
ConnectionManager.broadcast(...)
  ↓
所有已连接 WebSocket 客户端收到消息
```

广播失败不会影响 PUT 或 DELETE 的正常返回。失败或已经断开的 WebSocket 连接会从连接集合中移除。

## 测试步骤

安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

启动 mock server：

```bash
uvicorn mock_server:app --reload --host 127.0.0.1 --port 8000
```

启动 watch 客户端：

```bash
python3 tools/watch_entities.py
```

生成单个 entity：

```bash
python3 generate_entities.py --format json --count 1 --output examples/entity.json
```

PUT entity：

```bash
curl -X PUT http://127.0.0.1:8000/api/v1/entities \
  -H "Content-Type: application/json" \
  --data-binary @examples/entity.json
```

watch 客户端应收到一条 `entity.upserted` 消息。

生成 entity 数组：

```bash
python3 generate_entities.py --format json --count 3 --output examples/entities.json
```

PUT entity 数组：

```bash
curl -X PUT http://127.0.0.1:8000/api/v1/entities \
  -H "Content-Type: application/json" \
  --data-binary @examples/entities.json
```

watch 客户端应收到 3 条 `entity.upserted` 消息。

测试 DELETE 广播：

```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/entities/AIS_SIM_MMSI_366000000
```

watch 客户端应收到一条 `entity.deleted` 消息。

## 与真实 Lattice Stream / Watch 的区别

当前实现只是本地 mock，不是现实中的 Lattice stream/watch 协议：

- 不实现真实 Anduril 认证。
- 不校验 token、client id、client secret。
- 不调用 Anduril endpoint。
- 不依赖 Anduril SDK。
- 不保证消息 envelope、路径、事件类型与真实 Lattice 一致。
- 不支持 replay。
- 不支持 cursor、offset 或 sequence number。
- 不支持订阅过滤条件。
- 不支持权限、租户或 sandbox 隔离。
- 不支持跨进程、跨 worker 或跨机器广播。
- 不保证生产级顺序、重试或 backpressure 语义。

## 当前没有实现的内容

当前 stream/watch 没有实现：

- 认证和授权。
- 真实 Lattice 协议。
- 历史消息 replay。
- cursor / offset。
- 订阅过滤。
- heartbeat。
- 客户端慢消费保护。
- 跨进程广播。
- 与 Anduril API 的任何网络通信。

## 下一步建议

后续可以按需要逐步增加：

1. Heartbeat / ping 消息，用于更快发现断开的客户端。
2. 简单订阅过滤，例如只订阅某个 `entityId` 前缀。
3. 本地 sequence number，方便调试消息顺序。
4. 前端原型页面，用地图或列表实时展示 stream 消息。
5. 本地 adapter，把 sample app 风格数据发送到 mock REST API，再通过 stream 观察变化。
