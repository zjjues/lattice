# Kubernetes 与 Fast DDS 接入预留

当前演示不要求安装 Kubernetes 或 Fast DDS，但业务模型不直接依赖内存存储和 HTTP。

## 设备统一接入

`lattice_core.mission_scenario.DeviceRegistry` 是设备目录边界。当前场景使用内存目录，真实部署可实现 `KubernetesDeviceRegistry/v1`：

- 用 Kubernetes CustomResourceDefinition 表示无人机、无人艇、传感器和载荷。
- `metadata.uid` 映射为 `platformId`，标签保存装备类型、任务域和能力标签。
- Device Operator 负责注册、心跳、配置下发和设备状态同步。
- 上层场景 API 始终返回统一 `platform/sensors` 模型，不感知设备来自 K8s、文件或仿真器。

## 应用间通信

`lattice_core.mission_scenario.EventTransport` 是消息传输边界。当前实现使用应用内事件与 WebSocket，真实部署可实现 `FastDDS MissionEvent/v1`：

- `platform.telemetry`：位置、姿态、动力和健康状态。
- `sensor.observation`：传感器观测、质量、时间戳和数据来源。
- `mission.task`：协同探测任务、目标、能力要求和执行状态。
- `intelligence.track`：融合航迹、分类、置信度和证据引用。
- `decision.recommendation`：规则/RAG/模型建议和人工审批状态。

建议使用 IDL 定义稳定数据结构，在 Fast DDS Adapter 中完成 IDL 与内部 JSON 模型互转。Web API、Cesium/Omniverse 和大模型服务继续订阅内部统一事件，不直接绑定 DDS Topic。

## 最小迁移顺序

1. 增加 CRD 与 Device Operator，只替换 `DeviceRegistry`。
2. 增加 Fast DDS sidecar/adapter，双写现有 WebSocket 与 DDS。
3. 对遥测和观测 Topic 做回放一致性测试。
4. 稳定后再把应用内事件切换为 DDS 主通道。

该方式可让当前 Fake Lattice 演示继续独立运行，同时保留向真实设备底座迁移的路径。
