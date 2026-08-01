# 阶段 1 正式入口与回退

阶段 1 完整入口为：

```bash
uvicorn stage1_app:app --host 127.0.0.1 --port 8000
```

一键启动：

```bash
bash scripts/start_phase1_env.sh --reset
```

显式使用原有回退入口：

```bash
bash scripts/start_phase1_env.sh --legacy
```

也可以直接启动原入口：

```bash
uvicorn mock_server:app --host 127.0.0.1 --port 8000
```

`stage1_app:app` 启用统一事件信封、`IngestService`、`RecommendationService`、
`KnowledgeRetriever` 和 `RecommendationProvider`。当前 Provider 适配原有 Dify + 本地回退实现，
因此业务行为不变，但核心服务已不再直接依赖 Dify 调用方式。

原有 `scripts/start_demo_env.sh` 和 `mock_server:app` 保持未修改，作为完全回退路径。
新旧入口共享正式运行时的 `data/*.json`；进程级测试则使用临时目录，不接触正式业务数据。
