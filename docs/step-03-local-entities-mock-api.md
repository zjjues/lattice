# Step 03: 本地 Mock Lattice Entities API

## 本步骤目标

本步骤创建一个本地开发用的 mock Lattice Entities API，用来接收 `generate_entities.py` 生成的 entity payload，并把数据保存到本地 JSON 文件。

本步骤仍然不调用 Anduril API，不依赖 Anduril SDK，不需要 token，也不修改 `external/sample-app-ais-integration-rest`。

## 为什么需要 Mock `/api/v1/entities`

第 1 步和第 2 步已经完成了两件事：

- `generate_entities.py` 可以离线生成接近 AIS sample app 的 Lattice-style entity。
- `external/sample-app-ais-integration-rest` 展示了 AIS 数据如何变成 entity 并发布。

在进入真实 Lattice/Sandbox 联调前，需要一个本地接口来验证：

- entity payload 是否能被 HTTP API 接收。
- `entityId` upsert 逻辑是否稳定。
- 本地生成的 AIS 风格字段是否方便查询和调试。
- 后续 sample app 或 adapter 是否能先对接本地 API，而不是直接访问真实 endpoint。

因此本步骤实现本地 `/api/v1/entities` mock，用文件模拟 entity store。

## 实现文件

- `mock_server.py`：FastAPI mock server。
- `requirements.txt`：本地 mock server 依赖，包含 `fastapi` 和 `uvicorn`。
- `data/entities_store.json`：运行时自动创建的本地 JSON 存储文件。

存储文件结构：

```json
{
  "entities": {
    "ENTITY_ID": {
      "entityId": "ENTITY_ID"
    }
  }
}
```

## 实现了哪些接口

### `GET /health`

返回服务状态：

```json
{
  "status": "ok",
  "service": "local-lattice-entities-mock"
}
```

### `PUT /api/v1/entities`

接收单个 entity JSON 对象，或 entity JSON 数组。

要求每个 entity 都包含 `entityId`。如果缺少 `entityId`，返回 HTTP 400。

服务按 `entityId` upsert 到 `data/entities_store.json`。

成功响应：

```json
{
  "upserted": 1,
  "entityIds": [
    "AIS_SIM_MMSI_366000000"
  ]
}
```

### `GET /api/v1/entities`

返回当前保存的所有 entities：

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

### `GET /api/v1/entities/{entity_id}`

如果 entity 存在，返回该 entity。

如果不存在，返回 HTTP 404。

### `DELETE /api/v1/entities/{entity_id}`

如果 entity 存在，删除并返回：

```json
{
  "deleted": true,
  "entityId": "AIS_SIM_MMSI_366000000"
}
```

如果不存在，返回 HTTP 404。

## 和真实 Lattice API 的区别

这个 mock API 只用于本地开发，与真实 Lattice API 有明确区别：

- 不实现真实 Anduril 认证。
- 不校验 token、client id、client secret。
- 不调用 Anduril endpoint。
- 不依赖 Anduril SDK。
- 不实现真实权限、审计、租户、环境或 sandbox 语义。
- 不保证 URL、字段、错误码和真实 Lattice API 完全一致。
- 不实现 entity stream。
- 不实现 tasks。
- 不实现 objects。
- 不实现复杂 schema 校验。

它的目标是提供一个稳定、可控、离线的本地接收端，方便验证 payload 形状和后续本地 adapter。

## 如何与 `generate_entities.py` 配合

安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

启动 mock server：

```bash
uvicorn mock_server:app --reload --host 127.0.0.1 --port 8000
```

生成单个 entity：

```bash
python3 generate_entities.py --format json --count 1 --output examples/entity.json
```

上传到本地 mock API：

```bash
curl -X PUT http://127.0.0.1:8000/api/v1/entities \
  -H "Content-Type: application/json" \
  --data-binary @examples/entity.json
```

查询所有 entities：

```bash
curl http://127.0.0.1:8000/api/v1/entities
```

查询单个 entity：

```bash
curl http://127.0.0.1:8000/api/v1/entities/AIS_SIM_MMSI_366000000
```

删除单个 entity：

```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/entities/AIS_SIM_MMSI_366000000
```

也可以生成 JSON 数组并一次 upsert 多个 entities：

```bash
python3 generate_entities.py --format json --count 3 --output examples/entities.json
curl -X PUT http://127.0.0.1:8000/api/v1/entities \
  -H "Content-Type: application/json" \
  --data-binary @examples/entities.json
```

## 验证结果

本步骤已经完成以下 13 项验证，结果均为通过：

| 序号 | 验证项 | 结果 |
| --- | --- | --- |
| 1 | `generate_entities.py` 仍然可以生成单个 JSON | 通过 |
| 2 | `generate_entities.py` 仍然可以生成多个 JSONL | 通过 |
| 3 | `mock_server.py` 可以启动 | 通过 |
| 4 | `PUT /api/v1/entities` 支持单个 JSON 对象 | 通过 |
| 5 | `PUT /api/v1/entities` 支持 JSON 数组 | 通过 |
| 6 | entity 缺少 `entityId` 时返回 400 | 通过 |
| 7 | `GET /api/v1/entities` 可以返回所有 entities | 通过 |
| 8 | `GET /api/v1/entities/{entity_id}` 可以返回单个 entity | 通过 |
| 9 | `DELETE /api/v1/entities/{entity_id}` 可以删除 entity | 通过 |
| 10 | 没有调用任何 Anduril API | 通过 |
| 11 | 没有使用任何真实 token | 通过 |
| 12 | 没有修改 `external/sample-app-ais-integration-rest` | 通过 |
| 13 | 代码注释和文档为中文 | 通过 |

验证说明：

- `generate_entities.py` 的 JSON / JSONL 输出使用本地文件验证。
- `mock_server.py` 的启动使用 `uvicorn mock_server:app` 验证。
- 当前工具环境中不同命令会话存在网络命名空间隔离，因此 `curl 127.0.0.1` 不能跨会话访问刚启动的 server；接口行为通过同一 FastAPI app 的本地路由函数验证。
- 验证后已停止测试过程中启动的本地 `uvicorn` / ASGI 测试进程。

## 当前没有实现的能力

当前 mock server 没有实现：

- 认证和授权。
- entity stream。
- WebSocket。
- tasks。
- objects。
- 真实 Lattice 状态同步。
- 真实 schema 验证。
- 与 Anduril API 的任何网络通信。

这些能力应在本地 payload 和 adapter 稳定后再逐步补充。

## 下一步

后续可以沿两个方向推进：

1. 加入 WebSocket stream。
   - 当 `PUT /api/v1/entities` upsert entity 后，向本地 WebSocket 订阅者广播 entity update。
   - 这样可以模拟前端或 sample app 订阅 entity 更新的流程。

2. 改造 sample app 对接本地 mock。
   - 不修改 `external/sample-app-ais-integration-rest` 源码。
   - 在本仓库新增 adapter 或 wrapper，把 sample app 风格 payload 转发到 `PUT /api/v1/entities`。
   - 先验证本地端到端流程，再决定是否进入真实 Lattice/Sandbox 联调。
