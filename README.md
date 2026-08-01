# Fake Lattice 本地态势感知与任务闭环演示

这是一个完全在本地运行的 Lattice 风格演示系统，不调用 Anduril API，也不需要 Anduril SDK。工程以 FastAPI 和文件存储模拟实体态势、事件接入、规则告警、处置建议、任务执行、附件管理及 WebSocket 实时同步，并提供浏览器地图界面和模拟 Agent。

## 当前功能

- 地图 UI：显示实体位置、威胁状态、告警、建议、任务和附件。
- Entity：创建、查询、更新和删除实体，保留轨迹历史。
- Ingest：接收模拟传感器/无人机事件，转换实体并执行本地规则。
- Alert：根据禁区、速度、徘徊等规则创建或更新告警。
- Recommendation：结合本地知识库生成处置建议；可选接入 Dify，未配置时使用本地回退逻辑。
- Task：手工创建任务，或从处置建议生成任务。
- Sim Agent：轮询分配给 `SIM_ASSET_001` 的任务并模拟状态流转。
- Object：上传、查询、下载和删除不超过 20 MB 的附件。
- WebSocket：通过 `/api/v1/entities/stream` 实时推送业务事件。

所有运行数据都保存在当前工程的 `data/*.json` 和 `objects/` 中。

## 工程入口

| 入口 | 用途 |
| --- | --- |
| `app:app` | 默认完整入口：模块化 ingest、标准事件信封和全部业务 API |
| `mock_server:app` | 旧单体兼容入口，用于排查或回退 |

启动脚本默认使用 `app:app`。

## 环境准备

```bash
conda activate lattice
cd /home/zhaji/projects/lattice
python -m pip install -r requirements.txt
```

如需接入本地 Dify：

```bash
cp .env.local.example .env.local
```

然后配置 `DIFY_BASE_URL`、`DIFY_API_KEY`、`DIFY_APP_MODE` 和 `DIFY_USER`。`.env.local` 会被启动脚本自动加载，请勿提交真实 API Key。

## 一键启动

```bash
bash scripts/start_demo_env.sh
```

默认使用 Conda 环境 `lattice`，在 `127.0.0.1:8000` 启动 `app:app` 和模拟 Agent。日志位于 `logs/lattice_server.log`、`logs/lattice_agent.log`，PID 位于 `run/lattice_server.pid`、`run/lattice_agent.pid`。

启动完成后访问：

- 地图 UI：<http://127.0.0.1:8000/>
- 健康检查：<http://127.0.0.1:8000/health>
- OpenAPI：<http://127.0.0.1:8000/docs>

常用参数：

```bash
bash scripts/start_demo_env.sh --reset              # 启动前清空演示数据和附件
bash scripts/start_demo_env.sh --no-agent           # 不启动模拟 Agent
bash scripts/start_demo_env.sh --legacy             # 使用 mock_server:app 回退
bash scripts/start_demo_env.sh --host 0.0.0.0 --port 8080
bash scripts/start_demo_env.sh --dry-run
```

`--reset` 会修改 `data/*.json` 并删除 `objects/` 中的附件，需要保留数据时不要使用。


## 停止服务

```bash
bash scripts/stop_demo_env.sh
```

停止脚本只处理 PID 文件记录且命令匹配的本工程进程。

## 演示事件闭环

```bash
conda run -n lattice python tools/replay_sim_events.py \
  --input fixtures/ingest/uav_intrusion.jsonl \
  --interval-seconds 1.5
```

另一个场景为 `fixtures/ingest/uav_loitering.jsonl`。典型流程：

```text
轨迹事件 → ingest → entity 更新 → 本地规则 → alert
       → 本地知识库/Dify → recommendation → task → sim agent 执行
```

## 主要 API

| 能力 | API |
| --- | --- |
| 状态与配置 | `GET /health`、`GET /api/v1/config/map-overlays` |
| Fake OAuth | `POST /api/v1/oauth/token` |
| 事件接入 | `POST /api/v1/ingest/events` |
| 实体和轨迹 | `PUT/GET /api/v1/entities`、`GET/DELETE /api/v1/entities/{id}`、`GET /api/v1/tracks/{id}/history` |
| 告警 | `GET /api/v1/alerts`、`GET/PATCH /api/v1/alerts/{id}` |
| 建议与知识库 | `POST /api/v1/alerts/{id}/recommendation`、`GET /api/v1/recommendations`、`GET/POST /api/v1/kb/search` |
| 任务 | `POST/GET /api/v1/tasks`、`GET/DELETE /api/v1/tasks/{id}`、`PATCH /api/v1/tasks/{id}/status` |
| 附件 | `POST/GET /api/v1/objects`、`GET/DELETE /api/v1/objects/{id}`、`GET /api/v1/objects/{id}/download` |
| 实时事件 | `WS /api/v1/entities/stream` |

完整请求结构可在服务启动后查看 `/docs`。

## 目录

```text
app.py                 模块化 ingest 和标准事件信封入口
mock_server.py         原有 API、规则、文件存储和地图 UI
lattice_core/          领域模型、服务、事件与 Provider
static/                浏览器地图 UI
data/                  JSON 业务数据
objects/               上传附件
kb/raw/                本地知识库
fixtures/ingest/        JSONL 演示场景
tools/                  回放、Agent、重置等工具
scripts/                启停脚本
tests/                  单元和真实入口测试
```

## 测试

```bash
conda run -n lattice python -m unittest discover -s tests -v
```

## 注意事项

- 这是本地演示和架构验证项目，不是 Anduril 官方 SDK 或生产服务。
- 默认只监听 `127.0.0.1`；开放到 `0.0.0.0` 前请确认网络安全策略。
- JSON 文件存储适合单机演示，不适合高并发或多实例部署。
- 日常运行使用 `app:app`；`mock_server:app` 仅作为兼容回退入口。
