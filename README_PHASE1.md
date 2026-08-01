# Fake Lattice 阶段 1 架构说明

本文记录阶段 1 模块化改造后的目录、运行方式、兼容范围和回退方法。项目原有 API、网页、JSON 数据文件和演示流程均继续保留。

## 推荐启动入口

阶段 1 推荐使用新的兼容应用入口：

```bash
uvicorn app:app --host 127.0.0.1 --port 8000
```

Windows PowerShell 示例：

```powershell
conda activate lattice
uvicorn app:app --host 127.0.0.1 --port 8000
```

浏览器入口和健康检查保持不变：

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/health
```

## 原有回退入口

阶段 1 没有删除或覆盖原来的应用入口。如果新服务接线出现问题，或者需要对比改造前行为，可以停止新入口，然后启动：

```bash
uvicorn mock_server:app --host 127.0.0.1 --port 8000
```

需要注意：

- `app:app` 和 `mock_server:app` 不能同时占用端口 `8000`。
- 两个入口使用相同的 `data/*.json` 和 `objects/`，切换时不需要迁移业务数据。
- 回退入口继续使用原来的单体 ingest 路由。
- 回退入口发送原始 WebSocket 消息，不包含阶段 1 新增的标准事件信封字段。
- 回退不会删除或修改新核心模块；恢复新入口时重新运行 `uvicorn app:app ...` 即可。

## 阶段 1 修改内容

### `app.py`

新的兼容应用入口。它导入并复用 `mock_server.py` 中现有的 FastAPI 应用、HTTP API、静态页面、规则和本地存储能力，然后只在边界处完成阶段 1 接线：

1. 用独立 `IngestService` 替换 `/api/v1/ingest/events` 的编排实现。
2. 在 WebSocket 的统一广播出口补充标准事件信封。
3. 完整保留旧消息字段，保证当前网页和 `tools/watch_entities.py` 继续工作。

### `lattice_core/models.py`

定义跨组件共享的领域类型：

- `IngestEvent`
- `Entity`
- `Alert`
- `Recommendation`
- `Task`
- 位置、姿态和运动学字段

这些类型是后续 MAVLink、ROS 2、JSBSim、Cesium 和本地智能服务之间的稳定边界。当前 JSON store 不需要立即迁移。

### `lattice_core/events.py`

定义统一领域事件信封。新入口广播的事件包含：

```json
{
  "eventId": "EVT_...",
  "schemaVersion": "1.0",
  "type": "entity.upserted",
  "timestamp": "2026-07-28T00:00:00Z",
  "source": "fake-lattice-core",
  "subject": {
    "entityId": "UAV_001"
  },
  "data": {
    "entity": {}
  }
}
```

为保持兼容，`entityId`、`entity`、`alertId`、`task` 等原有字段仍会出现在消息顶层。

### `lattice_core/services.py`

新增与 FastAPI、具体文件路径和仿真平台无关的 `IngestService`，负责：

```text
事件标准化
  → 事件存储
  → 实体构建与存储
  → 规则求值
  → 告警创建或更新
  → WebSocket 广播
```

存储、规则、时钟和广播都通过依赖注入提供，后续可以替换为数据库、消息队列或外部适配器。

### `lattice_core/providers.py`

定义三个独立能力接口：

- `LLMProvider`：调用本地 vLLM、Ollama 或其他模型服务。
- `KnowledgeRetriever`：调用本地文件索引、Qdrant 或其他知识库。
- `RecommendationProvider`：根据告警和实体上下文生成处置建议。

Dify 后续作为其中一种 Provider 实现保留，不再作为核心业务的固定依赖。

## API 兼容范围

阶段 1 不修改：

- `/health`
- `/api/v1/entities`
- `/api/v1/alerts`
- `/api/v1/recommendations`
- `/api/v1/tasks`
- `/api/v1/objects`
- `/api/v1/kb/search`
- `/api/v1/entities/stream`
- 现有网页资源和 JSON store 格式

新入口加载后仍有 35 条 FastAPI 路由，`POST /api/v1/ingest/events` 只注册一次。

## 验证

使用 `lattice` Conda 环境运行：

```powershell
python -m unittest discover -s tests -v
```

当前阶段 1 测试覆盖：

- 统一事件信封及旧字段兼容
- 事件 ID 唯一性
- ingest 服务的存储、规则和广播编排
- 新入口保留关键原有 API
- ingest 路由只注册一次

当前 5 项测试均已通过。

## 相关文档

- `README.md`：原有功能和 API 使用说明。
- `SYSTEM_OVERVIEW.md`：系统总览和环境复刻。
- `docs/architecture-phase-1.md`：阶段 1 核心边界和迁移原则。
- `docs/phase-1-run.md`：阶段 1 简明运行方式。

## 后续迁移建议

后续应继续按兼容迁移方式进行：

1. 把 Dify 和本地建议逻辑实现为 `RecommendationProvider`。
2. 把 JSON 文件读写抽成 repository 接口。
3. 将 MAVLink、ROS 2 和 JSBSim 数据转换为统一 `IngestEvent`。
4. 让 Cesium 只消费统一 entity 和领域事件，不依赖具体仿真协议。
5. 每一步保留旧入口，确认行为一致后再逐步缩小回退代码范围。
