# 开源传感器样本

大文件和可更新的外部数据保存在 D 盘，工程只保留适配器、测试和来源说明。

## 当前文件

| 数据 | D 盘路径 | 用途 |
|---|---|---|
| PX4 pyulog `sample.ulg` | `/mnt/d/lattice-data/datasets/px4/sample.ulg` | IMU、气压高度、姿态和飞控状态 |
| OpenSky 北京状态向量 | `/mnt/d/lattice-data/datasets/opensky/beijing-states.json` | 外部 ADS-B 航迹 |

PX4 样本来自官方 `PX4/pyulog` 仓库：

https://raw.githubusercontent.com/PX4/pyulog/main/test/sample.ulg

OpenSky 样本来自公开 state vectors API，北京范围为：

https://opensky-network.org/api/states/all?lamin=39.0&lomin=115.0&lamax=41.0&lomax=117.5

## 配置

默认路径已经内置，也可以在 `.env.local` 中覆盖：

```bash
SENSOR_DATA_ROOT=/mnt/d/lattice-data/datasets
PX4_SAMPLE_PATH=/mnt/d/lattice-data/datasets/px4/sample.ulg
OPENSKY_SAMPLE_PATH=/mnt/d/lattice-data/datasets/opensky/beijing-states.json
```

## 验证接口

- `GET /api/v1/situation/{entity_id}`：当前飞机传感器和 OpenSky 外部目标。
- `GET /api/v1/situation-samples`：PX4 样本解析结果与文件可用性。

当前 OpenSky 文件是下载时刻的快照，不代表实时航空管制信息；系统仅用于仿真和开发验证。
