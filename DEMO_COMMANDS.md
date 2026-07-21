# 演示命令速查

这份文件只放演示时真正需要执行的命令。

## 1. 进入目录

```bash
cd /home/cring/lattice/entity-generator
```

## 2. 一键启动演示环境

会先重置数据，再启动 `mock_server` 和 `sim_agent`。

```bash
cd /home/cring/lattice/entity-generator
bash scripts/start_demo_env.sh --reset
```

## 3. 浏览器打开地址

```text
http://127.0.0.1:8000/?lat=31.2304&lon=121.4737&zoom=12
```

## 4. 主演示场景：目标进入警戒区

```bash
cd /home/cring/lattice/entity-generator
python3 tools/replay_sim_events.py \
  --input fixtures/ingest/uav_intrusion.jsonl \
  --interval-seconds 1.5
```

## 5. 备选场景：目标盘旋滞留

```bash
cd /home/cring/lattice/entity-generator
python3 tools/replay_sim_events.py \
  --input fixtures/ingest/uav_loitering.jsonl \
  --interval-seconds 1.5
```

## 6. 单独重置数据

```bash
cd /home/cring/lattice/entity-generator
python3 tools/reset_demo_state.py
```

## 7. 一键停止演示环境

```bash
cd /home/cring/lattice/entity-generator
bash scripts/stop_demo_env.sh
```

## 8. 只检查启动/停止脚本会做什么

```bash
cd /home/cring/lattice/entity-generator
bash scripts/start_demo_env.sh --reset --dry-run
```

```bash
cd /home/cring/lattice/entity-generator
bash scripts/stop_demo_env.sh --dry-run
```
