# 阶段 1 运行方式

阶段 1 的兼容应用入口为 `app.py`：

```bash
uvicorn app:app --host 127.0.0.1 --port 8000
```

它复用原有全部 HTTP API，只把 ingest 路由切换到 `IngestService`，并在 WebSocket
广播出口补充统一事件信封。原有顶层字段仍然保留，因此当前网页和 watch 客户端无需修改。

迁移期间仍可用 `uvicorn mock_server:app ...` 回退到旧入口。
