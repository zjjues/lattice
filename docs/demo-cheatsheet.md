# 演示速查命令

只保留现场最常用的几条命令。

---

## 1. 一键启动

```bash
cd /home/cring/lattice/entity-generator
bash scripts/start_demo_env.sh --reset
```

---

## 2. 浏览器地址

```text
http://127.0.0.1:8000/?lat=31.2304&lon=121.4737&zoom=12
```

---

## 3. 主演示场景

```bash
cd /home/cring/lattice/entity-generator
python3 tools/replay_sim_events.py \
  --input fixtures/ingest/uav_intrusion.jsonl \
  --interval-seconds 1.5
```

---

## 4. 备选场景

```bash
cd /home/cring/lattice/entity-generator
python3 tools/replay_sim_events.py \
  --input fixtures/ingest/uav_loitering.jsonl \
  --interval-seconds 1.5
```

---

## 5. 一键停止

```bash
cd /home/cring/lattice/entity-generator
bash scripts/stop_demo_env.sh
```

---

## 6. 单独重置数据

```bash
cd /home/cring/lattice/entity-generator
python3 tools/reset_demo_state.py
```
