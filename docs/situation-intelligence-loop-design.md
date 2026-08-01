# 态势感知与多源情报处置闭环设计

## 1. 目标与边界

在当前 Cesium 态势监控、统一飞行遥测、规则告警、Embedding RAG 和 DeepSeek 建议能力上，形成以下最小闭环：

`飞机/目标展示 → 传感器状态 → 不完整情报识别 → 追加探测任务 → 多源证据融合 → 规则与 RAG → 大模型方案 → 人工审批 → 仿真执行与复盘`

系统定位为仿真、训练和辅助决策平台。任何会改变真实飞行器状态、影响现实对象或造成不可逆后果的动作必须经过人工审批；最小版本只执行仿真任务，不提供自主武器释放或自主攻击能力。

## 2. 当前能力复用

| 当前模块 | 继续承担的职责 | 最小新增内容 |
|---|---|---|
| Cesium 监控台 | 地图、飞机、航迹、告警、建议 | 传感器图层、情报完整度、探测任务状态 |
| `lattice_core/flight` | 数据集适配与统一遥测 | PX4/ArduPilot/OpenSky/视觉检测适配器 |
| ingest 事件接口 | 接收和广播数据 | 新增 sensor、observation、collection-task 事件 |
| 规则引擎 | 飞行安全和威胁触发 | 情报缺口规则、追加探测策略 |
| BGE RAG | SOP 检索 | 传感器能力、探测规则、证据可靠性知识层 |
| DeepSeek | 结构化处置建议 | 接收融合情报包，不直接接收未经筛选的原始流 |
| recommendation | 建议记录和前端广播 | 增加证据链、缺口、审批与仿真执行状态 |

## 3. 数据源选择

### 3.1 第一优先：飞机自身遥测与传感器健康

1. PX4 ULog：使用 `pyulog` 读取 `sensor_combined`、`vehicle_attitude`、`vehicle_gps_position`、`battery_status`、`vehicle_status`。其中 `sensor_combined` 提供机体系角速度、加速度、采样间隔和 clipping 标志。
2. ArduPilot DataFlash/TLog：读取 GPS、ATT、IMU、BARO、MAG、BAT、ARSP、MODE、EKF 等消息。DataFlash 是自描述格式，适合按少量日志样本逐步扩展。
3. 当前 ALFA/IDF 样本：继续作为故障和姿态规则的回归数据，统一映射到同一个遥测模型。

### 3.2 第二优先：外部目标与载荷感知

1. OpenSky state vectors：用少量 CSV/JSON 样本验证 ADS-B 航迹，字段包括 ICAO24、经纬度、速度、航向、垂直率、高度、呼号和更新时间。
2. EuRoC MAV：用一个短序列验证双目图像、同步 IMU 和真值轨迹的时间对齐与传感器健康展示。
3. VisDrone：只下载验证集中的少量图像/视频和标注，用于验证 EO 相机目标检测结果如何进入态势图，不在本阶段训练大型模型。

### 3.3 暂不纳入最小版本

真实雷达原始回波、电子侦察原始 IQ、现实目标识别与真实任务控制。这些数据成本和安全边界明显高于当前验证目标；先使用结构化模拟量测验证接口。

## 4. 统一数据模型

### 4.1 飞机平台状态 `PlatformState`

```json
{
  "platformId": "aircraft-001",
  "timestamp": "ISO-8601",
  "pose": {"lat": 39.9, "lon": 116.4, "altM": 800, "rollDeg": 2, "pitchDeg": 3, "yawDeg": 90},
  "motion": {"groundSpeedMps": 42, "airSpeedMps": 39, "verticalSpeedMps": 0.5},
  "mode": "AUTO",
  "health": {"overall": "DEGRADED", "faults": ["gps_quality_low"]},
  "source": {"dataset": "px4-ulog", "sampleId": "sample-01"}
}
```

### 4.2 传感器状态 `SensorState`

```json
{
  "sensorId": "aircraft-001/imu-0",
  "platformId": "aircraft-001",
  "type": "IMU",
  "status": "DEGRADED",
  "freshnessMs": 20,
  "quality": 0.76,
  "coverage": {"mode": "ONBOARD", "rangeM": null, "fovDeg": null},
  "metrics": {"accelMps2": [0.1, 0.2, 9.7], "gyroRadps": [0.01, 0.02, 0.03], "clipping": false},
  "provenance": {"adapter": "px4-ulog", "topic": "sensor_combined"}
}
```

传感器类型最小集合：`IMU`、`GNSS`、`BAROMETER`、`MAGNETOMETER`、`AIRSPEED`、`BATTERY`、`ADS_B`、`EO_CAMERA`。后续可增加 `IR_CAMERA`、`RADAR`、`LIDAR`，但统一复用 freshness、quality、coverage 和 provenance。

### 4.3 单次观测 `Observation`

```json
{
  "observationId": "obs-001",
  "sensorId": "sensor-eo-01",
  "observedAt": "ISO-8601",
  "targetRef": "track-unknown-07",
  "measurement": {"kind": "DETECTION", "class": "aircraft", "bearingDeg": 32, "confidence": 0.61},
  "quality": {"confidence": 0.61, "freshness": 0.95, "reliability": 0.8},
  "evidenceUri": "sample://visdrone/frame-001.jpg",
  "provenance": {"dataset": "visdrone", "model": "sample-annotation"}
}
```

### 4.4 融合情报对象 `IntelligenceTrack`

核心字段：目标身份候选、位置与协方差、速度、分类概率、意图假设、威胁等级、证据引用、冲突证据、情报完整度和待补缺口。完整度不能只用一个模型置信度，至少分为：

- `identity`：目标是谁；
- `location`：在哪里以及误差范围；
- `kinematics`：速度、航向和趋势；
- `classification`：目标类别；
- `intent`：行为/意图判断；
- `freshness`：信息是否过期；
- `sourceDiversity`：是否有独立来源交叉确认。

## 5. 不完整情报到追加探测

### 5.1 情报状态机

1. `DETECTED`：单源发现，身份或位置可能不完整。
2. `ASSESSING`：规则计算缺口和可靠性。
3. `COLLECTING`：生成并调度追加探测任务。
4. `FUSING`：关联不同时间、不同传感器的观测。
5. `ACTIONABLE`：达到处置方案最低信息门槛。
6. `STALE`：长时间没有新观测，降低可信度并重新探测。
7. `CLOSED`：人工确认结束或仿真任务完成。

### 5.2 情报缺口规则示例

- 只有 ADS-B 且位置新鲜，但身份可信度低：请求 EO 图像确认，不立即提高威胁等级。
- EO 检出目标但无距离：请求可提供测距的模拟传感器或利用多时刻视线交汇。
- GNSS/ADS-B 与视觉航迹冲突：标记 `CONFLICTED`，请求第二独立来源。
- 威胁概率较高但 freshness 超阈值：先刷新观测，禁止直接生成执行动作。
- 传感器 clipping、延迟或失联：降低该来源权重，同时显示降级原因。

### 5.3 探测能力注册表

每一种探测手段或 skill 注册为 `CollectionCapability`：

```json
{
  "capabilityId": "eo-confirmation",
  "inputs": ["targetRef", "lastKnownPosition"],
  "outputs": ["classification", "bearing", "imageEvidence"],
  "constraints": {"simulationOnly": true, "requiresApproval": false, "timeoutSec": 15},
  "cost": 2,
  "reliability": 0.78
}
```

编排器只能从白名单选择能力，并按照“补足哪个字段、预计增益、时间、成本”排序。skill 输出必须先转换为 Observation 并记录来源，不能直接写入最终情报或直接触发执行。

## 6. 证据融合与大模型职责

### 6.1 确定性层

- 时间窗关联、空间门控、航迹连续性；
- freshness 衰减、来源可靠性、冲突检测；
- 规则风险下限、禁区和人工审批规则；
- 每个结论可以追溯到 observation、sensor 和原始样本。

### 6.2 大模型层

DeepSeek 只接收压缩后的 `DecisionPacket`：融合航迹、明确缺口、规则结果、最多若干条 RAG 依据和允许的处置动作集合。大模型负责解释、比较方案、补充注意事项和生成结构化建议；不能修改原始证据、降低规则风险等级或绕过审批。

输出字段建议固定为：`assessment`、`riskLevel`、`intelligenceGaps`、`options`、`recommendedOption`、`rationale`、`references`、`requiredApprovals`。

## 7. 态势界面设计

保持单一 `/monitor` 页面，在当前地图与左右面板基础上增加：

1. 地图层：飞机三维模型、外部目标、历史/预测航迹、传感器覆盖扇区、观测连线、位置不确定性椭圆。
2. 飞机状态卡：姿态仪、速度/高度、飞行模式、电量、链路、总体健康。
3. 传感器卡：每个传感器显示正常/降级/失联、最近更新时间、质量和关键指标；默认只显示摘要，避免界面过载。
4. 情报卡：完整度雷达图或六项进度条、证据来源、冲突和待补缺口。
5. 探测任务时间线：为什么追加探测、调用了什么能力、返回了什么证据、是否超时。
6. 处置方案卡：规则基线、RAG依据、大模型方案、风险、人工审批和仿真执行结果。

## 8. 开发顺序与最小验收

### 迭代 A：传感器态势

- 扩展统一模型和 ingest 事件；
- 从现有 ALFA/IDF CSV 派生 IMU、姿态、空速和故障状态；
- 加入一个 PX4 ULog 小样本和一个 OpenSky 小样本；
- 在 Cesium 页面显示飞机状态卡、传感器健康和 ADS-B 外部目标。

验收：飞机飞行时，姿态、速度、高度和至少 4 类传感器状态随回放变化，外部目标出现在同一地图。

### 迭代 B：不完整情报与追加探测

- 新增 Observation、IntelligenceTrack、CollectionTask；
- 实现 completeness 和 freshness 规则；
- 创建三个仿真 capability：ADS-B 刷新、EO 确认、位置复核；
- 以 VisDrone 少量标注模拟 EO 检测输出。

验收：单源低置信目标出现后，系统自动产生探测任务，第二来源返回后完整度上升并保留证据链。

### 迭代 C：方案与仿真闭环

- 将融合后的 DecisionPacket 接入现有规则、BGE RAG 和 DeepSeek；
- 增加人工批准、拒绝和退回补充探测；
- 执行结果限定为 Cesium/Omniverse 仿真状态变化；
- 保存全链路事件用于回放和评估。

验收：`发现不完整目标 → 追加探测 → 融合 → 生成方案 → 人工批准 → 仿真执行 → 结果回写` 可在一个页面完成；断开大模型后仍能输出规则方案。

## 9. 推荐的下一步实现

先执行迭代 A，不下载完整数据集：

1. 新增 `SensorState` 和 `Observation` Python 模型；
2. 为当前 CSV 回放补充 IMU、GNSS、空速和发动机/电池虚拟传感器；
3. 下载一个 PX4 ULog 样本、OpenSky 一小时文件中的少量行、EuRoC 一个短序列的少量帧；
4. 在监控台增加可折叠传感器面板与地图覆盖层；
5. 用“ADS-B 单源目标”作为迭代 B 的固定不完整情报场景。

## 10. 调研依据

- PX4 uORB 消息参考：https://docs.px4.io/main/en/msg_docs/index
- PX4 SensorCombined：https://docs.px4.io/main/en/msg_docs/SensorCombined
- PX4 pyulog：https://github.com/PX4/pyulog
- ArduPilot 日志说明：https://ardupilot.org/dev/docs/common-logs.html
- ArduPilot ROS 2 传感器接口：https://ardupilot.org/dev/docs/ros2-interfaces.html
- OpenSky 科研数据集：https://opensky-network.org/data/scientific
- EuRoC MAV：https://projects.asl.ethz.ch/datasets/euroc-mav/
