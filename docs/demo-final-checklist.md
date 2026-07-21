# 演示前最终检查清单

这份清单只服务现场演示。目标是把“能不能稳定讲出来”这件事提前确认完。

---

## 1. 环境检查

在工程目录执行：

```bash
cd /home/cring/lattice/entity-generator
bash scripts/start_demo_env.sh --reset
```

确认输出里有：

- 浏览器地址
- 健康检查地址
- 场景 A 命令
- 场景 B 命令

---

## 2. 页面检查

打开：

```text
http://127.0.0.1:8000/?lat=31.2304&lon=121.4737&zoom=12
```

确认页面初始状态正确：

- 顶部 5 个摘要指标都显示为 0
- 左侧能看到警戒区和图例
- 右侧有 4 个面板：
  - 告警
  - 建议
  - 任务
  - 威胁目标

如果一开始就有旧数据，说明没有先重置成功。

---

## 3. 主场景彩排

在触发窗口执行：

```bash
cd /home/cring/lattice/entity-generator
python3 tools/replay_sim_events.py \
  --input fixtures/ingest/uav_intrusion.jsonl \
  --interval-seconds 1.5
```

确认以下链路完整：

1. 地图上出现目标和轨迹
2. 目标进入警戒区后触发告警
3. 点击一条告警，可以生成建议
4. 建议卡里能看到：
   - 触发原因
   - 触发证据
   - 处置理由
   - 建议动作
   - 参考依据
5. 采纳建议后生成任务
6. `sim_agent` 自动推进任务状态
7. 任务卡能看到：
   - 来源告警
   - 来源建议
   - 执行动作
8. 点击地图上的选中目标，旁边状态标签会同步更新

只要这 8 步成立，主演示就可以开始。

---

## 4. 备选场景彩排

在触发窗口执行：

```bash
cd /home/cring/lattice/entity-generator
python3 tools/replay_sim_events.py \
  --input fixtures/ingest/uav_loitering.jsonl \
  --interval-seconds 1.5
```

确认：

- 轨迹是小范围盘旋，不是直线闯入
- 告警类型是 `loitering`
- 建议偏向持续观察和补充识别

这个场景的作用是说明系统不是只会处理一种风险模式。

---

## 5. 现场讲解时要主动说明的边界

建议主动讲清楚下面 4 点，避免被追问时被动解释：

1. 这是本地 fake Lattice，不是官方 Lattice
2. 当前地图是离线态势图，不是标准 GIS 瓦片地图
3. 如果没接 Dify，建议会走 `local-fallback`
4. 当前数据接入是模拟事件/轨迹回放，不是真实硬件

---

## 6. 演示结束

结束后执行：

```bash
cd /home/cring/lattice/entity-generator
bash scripts/stop_demo_env.sh
```

如果要清掉这轮残留数据，再执行：

```bash
cd /home/cring/lattice/entity-generator
python3 tools/reset_demo_state.py
```
