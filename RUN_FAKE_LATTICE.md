# Fake Lattice 演示 Runbook

这份 runbook 面向现场演示，不是开发备忘。目标是用最少的窗口和最顺的讲解顺序，把当前这套本地 fake Lattice 系统讲清楚。

如果现场只想看最短版本，直接看：

- [演示前最终检查清单](./docs/demo-final-checklist.md)
- [演示速查命令](./docs/demo-cheatsheet.md)

系统定位：

- 不是 Anduril 官方 Lattice
- 不依赖真实 endpoint、token、client id、client secret
- 所有数据都保存在本地 `data/` 和 `objects/`
- 当前演示主线是：
  `模拟目标上报 -> 平台显示 -> 告警 -> 建议 -> 任务 -> 执行回流`

---

## 1. 演示前准备

进入工程目录：

```bash
cd /home/cring/lattice/entity-generator
```

首次运行安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

可选：如果要让建议走 Dify，而不是本地回退逻辑，先复制并编辑本地环境文件：

```bash
cp .env.local.example .env.local
```

把 `.env.local` 里的 `DIFY_BASE_URL` 和 `DIFY_API_KEY` 改成你本地 Dify 的实际值。

如果不配 Dify：

- 系统仍可完整演示
- recommendation provider 会显示为 `local-fallback`
- 本地知识库仍会参与建议生成

---

## 2. 需要打开的窗口

建议只开 4 个窗口。

如果想先一键拉起后端和模拟 agent，可以直接执行：

```bash
cd /home/cring/lattice/entity-generator
bash scripts/start_demo_env.sh --reset
```

这个脚本会：

- 可选先重置演示数据
- 启动 `mock_server`
- 启动 `sim_agent`
- 打印浏览器地址和两条主演示命令

如果只想检查脚本会做什么，不真正启动：

```bash
cd /home/cring/lattice/entity-generator
bash scripts/start_demo_env.sh --reset --dry-run
```

演示结束后，可以一键停止环境：

```bash
cd /home/cring/lattice/entity-generator
bash scripts/stop_demo_env.sh
```

如果只想看它会停哪些进程：

```bash
cd /home/cring/lattice/entity-generator
bash scripts/stop_demo_env.sh --dry-run
```

### 窗口 1：后端服务

```bash
cd /home/cring/lattice/entity-generator
uvicorn mock_server:app --reload --host 127.0.0.1 --port 8000
```

### 窗口 2：模拟执行 agent

```bash
cd /home/cring/lattice/entity-generator
python3 tools/sim_agent.py --asset-id SIM_ASSET_001 --poll-interval 1 --work-seconds 3 --success-rate 1.0 --verbose
```

### 窗口 3：演示触发窗口

后面用这个窗口发送单条事件或回放轨迹。

### 窗口 4：浏览器

推荐直接打开上海视角：

```text
http://127.0.0.1:8000/?lat=31.2304&lon=121.4737&zoom=12
```

---

## 3. 页面上应该看到什么

打开浏览器后，页面结构应该是：

- 顶部：态势摘要
  - 当前目标
  - 开放告警
  - 高风险告警
  - 已生成建议
  - 执行中任务
- 左侧地图：
  - 目标点
  - 轨迹线
  - 警戒区
  - 图例
  - 选中目标的状态标签
- 右侧指控面板：
  - 告警面板
  - 建议面板
  - 任务面板
  - 威胁目标

如果页面打不开，先检查：

```bash
curl http://127.0.0.1:8000/health
```

---

## 4. 演示场景 A：目标进入警戒区

这是最推荐的主演示场景。

### 4.1 触发命令

在窗口 3 执行：

```bash
cd /home/cring/lattice/entity-generator
python3 tools/replay_sim_events.py \
  --input fixtures/ingest/uav_intrusion.jsonl \
  --interval-seconds 1.5
```

### 4.2 你应该看到

浏览器里会逐步出现：

1. 目标在地图上移动
2. 轨迹逐步逼近警戒区
3. 进入警戒区后出现高风险告警
4. 点击告警后可生成建议
5. 建议面板展示：
   - 触发原因
   - 触发证据
   - 处置理由
   - 建议动作
   - 参考依据
6. 点击“采纳并创建任务”
7. `sim_agent.py` 自动推进任务到完成
8. 任务卡显示来源告警、来源建议、执行动作

### 4.3 讲解话术

可以按这个顺序讲：

1. 这里模拟的是外部无人机/传感器持续上报目标位置。
2. 平台先把数据统一成一个目标实体，而不是直接展示原始设备协议。
3. 当目标进入警戒区时，规则引擎触发高风险告警。
4. 告警不是终点，系统会进一步结合知识库和建议逻辑给出处置建议。
5. 操作员确认建议后，再把它转成任务，而不是直接自动执行。
6. 任务交给模拟 agent 执行，最后把状态和结果回流到平台。

一句话概括：

`发现目标 -> 告警 -> 建议 -> 任务 -> 回流`

---

## 5. 演示场景 B：目标盘旋滞留

这个场景适合说明：不是所有风险都来自“高速闯入”，也可能是“持续观察”。

### 5.1 触发命令

在窗口 3 执行：

```bash
cd /home/cring/lattice/entity-generator
python3 tools/replay_sim_events.py \
  --input fixtures/ingest/uav_loitering.jsonl \
  --interval-seconds 1.5
```

### 5.2 你应该看到

1. 目标在小范围内来回活动
2. 轨迹不是直线接近，而是局部盘旋
3. 系统触发 `loitering` 类型告警
4. 建议更偏向持续观察和补充识别，而不是立即强处置

### 5.3 讲解重点

这个场景的重点不是“入侵”，而是：

- 平台能区分不同异常模式
- 告警和建议不是一套固定模板
- 同样是一个目标，不同轨迹行为会引出不同处置思路

---

## 6. 最小操作顺序

如果现场时间很短，只做下面 6 步：

1. 打开浏览器，展示地图、警戒区、右侧指控台
2. 回放 `uav_intrusion.jsonl`
3. 点开一条告警
4. 点击“生成建议”
5. 点击“采纳并创建任务”
6. 等待 agent 自动把任务推进到完成

这已经足够讲清楚系统价值。

---

## 7. 常见问题

### 7.1 为什么地图不是标准在线地图

因为当前演示使用的是本地离线态势图，不依赖外部瓦片服务。  
重点是展示目标、轨迹、区域、告警和任务关系，不是做 GIS 产品。

### 7.2 为什么 recommendation provider 显示 `local-fallback`

说明当前没有接 Dify，或者 Dify 调用失败。  
这不影响主流程演示，只是建议来自本地逻辑而不是外部模型。

### 7.3 为什么能演示任务闭环

因为 `tools/sim_agent.py` 会轮询任务，并把任务状态从 `ASSIGNED / IN_PROGRESS` 推到完成。

### 7.4 为什么这不是 Anduril 官方 Lattice

因为：

- 没有真实 Lattice 后端
- 没有真实认证和权限体系
- 没有真实硬件接入
- 没有官方 UI 和运行环境

当前系统只是一个本地教学版 fake Lattice。

---

## 8. 附录：常用命令

### 8.1 一键清空当前演示数据

每次正式演示前，建议先执行一次：

```bash
cd /home/cring/lattice/entity-generator
python3 tools/reset_demo_state.py
```

如果只想清空 store，不删除 `objects/` 里的附件文件：

```bash
cd /home/cring/lattice/entity-generator
python3 tools/reset_demo_state.py --keep-objects
```

### 8.2 单条模拟事件注入

```bash
cd /home/cring/lattice/entity-generator
python3 tools/send_sim_event.py
```

### 8.3 查看本地知识库搜索结果

```bash
curl 'http://127.0.0.1:8000/api/v1/kb/search?q=restricted_area_intrusion%20uav'
```

### 8.4 查询 tasks

```bash
curl http://127.0.0.1:8000/api/v1/tasks
```

### 8.5 查询 alerts

```bash
curl http://127.0.0.1:8000/api/v1/alerts
```

### 8.6 查询 recommendations

```bash
curl http://127.0.0.1:8000/api/v1/recommendations
```

### 8.7 查询 objects

```bash
curl http://127.0.0.1:8000/api/v1/objects
```

### 8.8 监听 WebSocket

```bash
cd /home/cring/lattice/entity-generator
python3 tools/watch_entities.py
```

### 8.9 旧的一键 demo workflow

这个脚本还在，但现在不再是主演示路径：

```bash
cd /home/cring/lattice/entity-generator
python3 tools/demo_workflow.py \
  --lat 31.2304 \
  --lon 121.4737 \
  --place-name "Shanghai port" \
  --anomaly-type "高速接近港区" \
  --threat-level HIGH \
  --asset-id SIM_ASSET_001 \
  --use-external-agent
```
