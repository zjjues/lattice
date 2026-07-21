# Step 10: 本地模拟 Agent / Asset

## 本步骤目标

本步骤新增 `tools/sim_agent.py`，用本地脚本模拟一个可接收任务的 agent / asset。脚本会轮询 Tasks API，找到分配给自己的任务，并自动更新任务状态。

本步骤不调用 Anduril API，不使用真实 token，不加入 Anduril SDK，不实现认证，也不修改 `external/sample-app-ais-integration-rest`。

## 为什么需要模拟 agent

前几步已经可以在地图 UI 中创建调查任务、更新状态和观察 WebSocket 事件。模拟 agent 可以补上本地任务执行闭环：

```text
UI 创建任务
  ↓
mock server 保存 task
  ↓
sim_agent.py 发现 assignedAssetId 匹配的 task
  ↓
sim_agent.py 自动更新任务状态
  ↓
WebSocket task.status_updated 同步到 UI
```

这样可以在不接入真实 Lattice 或真实 asset 的情况下，验证任务生命周期和前端同步效果。

## agent 工作流程

`sim_agent.py` 会循环执行：

1. 调用 `GET /api/v1/tasks`。
2. 筛选 `assignedAssetId` 等于当前 `--asset-id` 的任务。
3. 只处理状态为 `CREATED` 或 `ASSIGNED` 的任务。
4. 处理前重新查询单个任务，确认状态和 asset 仍然匹配。
5. 调用 `PATCH /api/v1/tasks/{task_id}/status` 更新状态。
6. 任务完成后记录 taskId，避免本进程重复处理。

## 命令行参数说明

```text
--base-url
  默认 http://127.0.0.1:8000
  mock server 地址。

--asset-id
  默认 SIM_ASSET_001
  当前模拟 agent / asset id。

--poll-interval
  默认 3
  轮询间隔，单位秒。

--work-seconds
  默认 5
  模拟任务执行耗时，单位秒。

--success-rate
  默认 0.9
  最终成功概率，范围 0 到 1。

--once
  只处理一轮后退出。

--verbose
  输出详细轮询日志。
```

## 状态流转说明

对每个候选任务，agent 会执行：

```text
CREATED 或 ASSIGNED
  ↓
ACCEPTED
  ↓
IN_PROGRESS
  ↓
SUCCEEDED 或 FAILED
```

最终状态由 `--success-rate` 控制：

- `random.random() < success_rate`：`SUCCEEDED`
- 否则：`FAILED`

如果任务在处理中被删除、被取消或被其他客户端改成终态，agent 会记录日志并停止处理该任务。

## 测试步骤

启动 mock server：

```bash
uvicorn mock_server:app --reload --port 8000
```

打开地图 UI：

```text
http://127.0.0.1:8000/
```

生成并上传 entities：

```bash
python generate_entities.py --count 5 --format json --output examples/entities.json
curl -X PUT http://127.0.0.1:8000/api/v1/entities \
  -H "Content-Type: application/json" \
  --data-binary @examples/entities.json
```

在地图 marker popup 中点击“创建调查任务”。该任务默认分配给：

```text
SIM_ASSET_001
```

启动模拟 agent：

```bash
python3 tools/sim_agent.py --asset-id SIM_ASSET_001 --verbose
```

只处理一轮：

```bash
python3 tools/sim_agent.py --once --verbose
```

强制失败验证：

```bash
python3 tools/sim_agent.py --success-rate 0 --once --verbose
```

观察 UI 任务面板，状态应通过 WebSocket 自动变化。

## 与真实 Lattice agent/task execution 的区别

当前模拟 agent 只是本地脚本，不代表真实 Lattice agent、真实任务执行器或真实资产。

本地版本不实现：

- 真实 Lattice agent。
- 真实 task claim / leasing。
- 真实任务调度器。
- 真实 asset 注册、能力模型和健康状态。
- 真实任务执行。
- 真实任务结果报告。
- 真实认证和授权。
- 真实审计。
- 多 agent 协调。
- 跨进程互斥。
- heartbeat。
- 重试策略和死信队列。
- 地理约束或传感器能力检查。

## 当前没有实现的内容

- 不调用 Anduril API。
- 不连接 Anduril Sandbox。
- 不使用真实 token。
- 不加入 Anduril SDK。
- 不实现认证、授权或审计。
- 不生成任务报告 object。
- 不自动上传任务附件。
- 不检查 `relatedEntityId` 是否存在。
- 不检查 `assignedAssetId` 是否真实注册。
- 不保证多个相同 `asset-id` agent 同时运行时的互斥。

## 下一步建议

- 增加 Assets API，维护本地 asset 注册和健康状态。
- 增加 agent heartbeat。
- 增加 task claim / lease 语义，避免多个 agent 抢同一任务。
- 任务完成时自动生成 object 报告。
- 在 UI 中显示 agent 处理日志或 asset 状态。
- 增加更完整的重试和错误恢复策略。
