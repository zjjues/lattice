# Fake Lattice 工程总览与环境复刻指南

本文以当前仓库的代码、脚本和数据为准，说明系统用途、组成、依赖和迁移方法。目标是在另一台 Linux/macOS 机器上仅凭本仓库即可复现核心演示环境。

## 1. 系统要做什么

这是一个完全本地运行的 **Lattice-style 态势感知与任务闭环演示系统**，用于原型验证、接口联调和现场演示。它把模拟传感器事件转成统一目标实体，在浏览器中展示位置和轨迹，用本地规则产生告警，再由操作员生成处置建议、创建任务，并由模拟 agent 执行任务和回传结果。

主流程是：

```text
模拟传感器/AIS 数据
        ↓
统一事件接入与实体更新
        ↓
离线态势图、轨迹与 WebSocket 实时同步
        ↓
规则告警（进入警戒区 / 高速接近 / 盘旋滞留）
        ↓
本地知识库或可选 Dify 生成处置建议
        ↓
操作员采纳建议并创建任务
        ↓
模拟 agent 执行，状态和结果回流
```

它不是 Anduril 官方 Lattice，不连接真实 Lattice endpoint，不需要 Anduril token、client id、client secret 或 SDK。API 和数据结构只用于本地模拟，不保证与真实 Lattice 协议完全兼容。

## 2. 当前能力

- 生成 AIS 风格的 Surface Vessel entity JSON/JSONL。
- 接收统一格式的 UAV/传感器事件，维护实体和轨迹历史。
- 根据上海演示区域内置规则生成侵入、高速接近和盘旋滞留告警。
- 查询、确认、解决或忽略告警。
- 使用本地知识库生成建议；配置 Dify 后可优先调用 Dify，失败时回退到本地逻辑。
- 从建议创建任务，或直接对实体创建任务；支持完整任务状态流转。
- 通过模拟 agent 自动领取和完成分配给指定 asset 的任务。
- 上传、查询、下载和删除与 entity/task 关联的本地附件（单文件上限 20 MiB）。
- 通过一个 WebSocket 通道实时广播 entity、task、object、alert 和 recommendation 变化。
- 提供不依赖在线地图瓦片的浏览器 UI，因此核心演示可离线运行。
- 提供两条现成轨迹：无人机进入警戒区、无人机盘旋滞留。

所有业务数据都保存在本机文件中，没有数据库和消息队列。

## 3. 技术结构

| 层次 | 实现 | 说明 |
| --- | --- | --- |
| 后端 | `mock_server.py`、FastAPI、Uvicorn | HTTP API、WebSocket、规则、知识库、文件存储和静态页面 |
| 前端 | `static/index.html`、`app.js`、`style.css` | 原生 HTML/CSS/JavaScript，无 npm 构建步骤、无在线瓦片依赖 |
| 数据生成 | `generate_entities.py` | 仅用 Python 标准库生成 AIS 风格数据 |
| 事件模拟 | `tools/send_sim_event.py`、`replay_sim_events.py` | 注入单条事件或回放 JSONL 轨迹 |
| 执行模拟 | `tools/sim_agent.py` | 轮询任务并模拟 ACCEPTED → IN_PROGRESS → SUCCEEDED/FAILED |
| 本地持久化 | `data/*.json`、`objects/` | JSON store 和附件目录；仅适合单机演示，不是并发数据库 |
| 知识与建议 | `kb/`、可选 Dify | 本地 SOP 检索与建议；Dify 是增强项而非必需项 |

默认服务地址为 `http://127.0.0.1:8000`，入口页面是 `/`，健康检查是 `/health`，实时流是 `/api/v1/entities/stream`。完整 API 示例见 [README.md](./README.md)，演示流程见 [RUN_FAKE_LATTICE.md](./RUN_FAKE_LATTICE.md)。

## 4. 目录和文件职责

### 核心运行文件

| 路径 | 是否必需 | 用途 |
| --- | --- | --- |
| `mock_server.py` | 是 | 核心服务及全部本地 API |
| `static/` | 是 | 浏览器态势图和操作面板 |
| `requirements.txt` | 是 | 核心 Python 第三方依赖 |
| `data/` | 是 | 六类 JSON store；缺失文件可由服务或重置脚本创建 |
| `objects/` | 运行时创建 | 上传附件的实际文件；当前可为空 |
| `kb/raw/` | 建议保留 | 本地建议检索使用的结构化知识库 |
| `fixtures/ingest/` | 演示需要 | 两个 JSONL 演示场景 |
| `tools/sim_agent.py` | 闭环演示需要 | 模拟任务执行端 |
| `tools/send_sim_event.py` | 可选 | 发送单条测试事件 |
| `tools/replay_sim_events.py` | 演示需要 | 回放轨迹场景 |
| `tools/reset_demo_state.py` | 建议保留 | 重置全部本地 store 和附件 |
| `scripts/start_demo_env.sh` / `stop_demo_env.sh` | 建议保留 | 一键启动和停止服务、agent |

### 文档、样例和辅助内容

- `README.md`：各 API 与功能的详细使用说明。
- `RUN_FAKE_LATTICE.md`、`DEMO_COMMANDS.md`、`docs/demo-*`：现场演示手册和速查表。
- `docs/step-*`：功能逐步实现记录；用于理解演进过程，不参与运行。
- `docs/dify-*`、`kb/dify_samples/`：Dify 接入说明及可导入材料。
- `examples/`：entity、task、object 的请求/输出示例。
- `tools/demo_workflow.py`：用 HTTP 串联完整演示流程的命令行工具。
- `tools/watch_entities.py`：终端 WebSocket 监听器。
- `external/`：下载的 Anduril SDK、样例仓库、演示文档和其他参考材料。**核心系统不导入、编译或运行这里的项目，复刻核心演示时可不复制。** 如需重新下载公开参考仓库，可运行 `scripts/download_anduril_repos.sh`（需要 Git 和互联网）。
- `tools/build_fake_lattice_doc.py`、`retheme_anduril_ppt.py`、`manual_layout_fix_anduril_ppt.py`：文档/PPT 生成或排版工具，不参与服务运行。
- `logs/`、`run/*.pid`、`__pycache__/`、`downloaded-object*.txt`：运行日志、进程号、缓存或下载测试产物，迁移时无需保留。

## 5. 环境要求

### 核心必需

- Linux 或 macOS。Windows 建议使用 WSL2；一键脚本依赖 Bash 和 POSIX 进程工具。
- Python **3.9 或更高版本**。代码使用了 `dict[...]`、`set[...]` 等 Python 3.9 语法；当前工程曾在 Python 3.11 环境运行。
- `pip` 和创建虚拟环境所需的 `venv` 模块。
- 核心 Python 包（来自 `requirements.txt`）：
  - `fastapi`
  - `uvicorn`
  - `websockets`
  - `python-multipart`
- 现代浏览器（Chrome、Edge、Firefox 或 Safari）。前端无 Node.js/npm 构建要求。
- 端口 `8000` 可用。

### 脚本和验证建议安装

- Bash、`pgrep`/`kill`（一键启停脚本使用；Linux 通常由 `procps` 提供）。
- `curl`（手工调用和健康检查；不是 Python 服务的依赖）。
- Git（复制/拉取仓库及下载 `external/` 参考项目时使用）。

### 可选功能

- Dify：需要一个可访问的 Dify workflow 或 chatflow 服务，以及 `DIFY_BASE_URL`、`DIFY_API_KEY`；不配置仍可使用完整本地回退流程。
- 文档/PPT 辅助脚本：分别需要 `python-docx` 和 `python-pptx`。它们当前没有写入核心 `requirements.txt`，仅在运行对应工具时安装。
- `external/` 中各参考项目拥有各自的 Go、Java、Node.js、Rust、Nix 等环境要求；这些都不属于本系统核心运行环境。

> `requirements.txt` 当前未锁定版本。它适合快速搭建；若要求长期、逐字节一致的复现，应在已验证环境中额外保存 `python -m pip freeze` 输出或构建容器镜像。

## 6. 在另一台机器上复刻

### 6.1 复制工程

推荐通过 Git 克隆；也可以打包复制，但应至少包括第 4 节“核心运行文件”。不要复制 `.env.local`、`logs/`、`run/` 和 `__pycache__/`。若要连当前业务状态一起迁移，则额外复制 `data/` 与 `objects/`；若只要干净环境，保留代码后执行重置即可。

```bash
git clone <本工程仓库地址> entity-generator
cd entity-generator
```

### 6.2 创建隔离的 Python 环境

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Windows/WSL2 请在 WSL 的 Bash 中执行上述命令。原生 Windows PowerShell 可以手动启动 Python 进程，但现有 `.sh` 启停脚本不能直接使用。

### 6.3 可选配置 Dify

```bash
cp .env.local.example .env.local
```

编辑 `.env.local`：

```bash
export DIFY_BASE_URL=http://你的-dify-地址
export DIFY_API_KEY=你的-api-key
export DIFY_APP_MODE=workflow
export DIFY_USER=fake-lattice-local
```

`.env.local` 由 `scripts/start_demo_env.sh` 加载；直接运行 `uvicorn` 时，需先执行 `source .env.local`。请勿把真实 API key 提交到版本库。

### 6.4 启动完整演示环境

```bash
bash scripts/start_demo_env.sh --reset
```

该命令会重置本地数据、后台启动 Uvicorn 和模拟 agent，并将日志写入 `logs/`、PID 写入 `run/`。然后打开：

```text
http://127.0.0.1:8000/?lat=31.2304&lon=121.4737&zoom=12
```

检查服务：

```bash
curl http://127.0.0.1:8000/health
```

### 6.5 触发演示场景

进入警戒区：

```bash
python3 tools/replay_sim_events.py \
  --input fixtures/ingest/uav_intrusion.jsonl \
  --interval-seconds 1.5
```

盘旋滞留：

```bash
python3 tools/replay_sim_events.py \
  --input fixtures/ingest/uav_loitering.jsonl \
  --interval-seconds 1.5
```

在 UI 中选择告警、生成建议并“采纳并创建任务”；模拟 agent 会自动推进任务。更完整的讲解顺序见 [RUN_FAKE_LATTICE.md](./RUN_FAKE_LATTICE.md)。

### 6.6 停止环境

```bash
bash scripts/stop_demo_env.sh
```

也可以不用后台脚本，分别在两个终端前台运行，便于观察错误：

```bash
uvicorn mock_server:app --host 127.0.0.1 --port 8000
```

```bash
python3 tools/sim_agent.py \
  --asset-id SIM_ASSET_001 \
  --poll-interval 1 \
  --work-seconds 3 \
  --success-rate 1.0 \
  --verbose
```

## 7. 复刻完成后的验收

按以下顺序检查：

1. `python3 -m compileall generate_entities.py mock_server.py tools` 无语法错误。
2. `bash scripts/start_demo_env.sh --dry-run` 能正确打印启动动作。
3. 启动后 `GET /health` 返回健康状态。
4. 浏览器页面能显示地图、警戒区和右侧面板，WebSocket 显示已连接。
5. 回放 `uav_intrusion.jsonl` 后目标移动并产生告警。
6. 告警可以生成建议，建议可以创建任务。
7. `sim_agent.py` 能把分配给 `SIM_ASSET_001` 的任务推进到终态。
8. 重启服务后 `data/*.json` 中的状态仍然存在。

若启动失败，优先查看 `logs/mock_server.log` 和 `logs/sim_agent.log`；若端口占用，可用 `ss -ltnp | grep 8000` 或 `lsof -i :8000` 检查。

## 8. 数据、状态和安全边界

- `data/*.json` 是运行状态，不是只读 fixture；多人或多进程同时写入可能互相覆盖。
- `objects/` 保存用户上传文件，迁移真实状态时必须与 `data/objects_store.json` 一起复制。
- `tools/reset_demo_state.py` 会重置 JSON store，并默认清理 `objects/` 附件；需要保留附件时使用 `--keep-objects`。
- 服务默认只绑定 `127.0.0.1`，没有真实鉴权、TLS、权限隔离、数据库事务或生产级并发保护。不要直接暴露到公网或用于生产环境。
- `/api/v1/oauth/token` 只是演示用 fake OAuth，不提供真实安全性。
- Dify 是系统唯一可选的外部运行时调用；不配置时核心演示可完全离线。

## 9. 当前限制

- 规则、警戒区和速度阈值直接定义在 `mock_server.py`，尚未配置化。
- JSON 文件存储适合单机演示，不适合高并发、多实例或大数据量。
- Python 依赖未锁版本，也没有容器、数据库迁移或自动化测试套件。
- 前后端集中在少量大文件中，当前更偏演示原型而非生产架构。
- 与真实 Lattice 的认证、协议、订阅、状态同步和部署方式均未实现。

因此，最可靠的复刻目标是“在另一台机器上恢复相同的本地功能闭环”，而不是搭建真实 Lattice 或生产服务。
