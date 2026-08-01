# Fake Lattice 演进实施计划

## 1. 目标

在保留当前实体、事件接入、告警、建议、任务、附件和 WebSocket 能力的基础上，将工程演进为支持真实飞行数据、三维物理空间仿真、可替换大模型、分层知识库以及“规则 + 大模型”混合决策的平台。

本计划覆盖：

1. 接入 Cesium、Omniverse 等仿真或三维平台。
2. 接入包含位置、速度、姿态和 IMU 参数的开源飞机/无人机数据。
3. 接入可替换的大模型 API。
4. 创建脱离 Dify 的轻量分层知识库。
5. 使用规则与大模型共同生成可解释、可追溯的处置建议。

## 2. 设计原则

- 核心业务不直接依赖 Cesium、Omniverse、Dify 或特定模型厂商。
- 所有外部数据先转换为统一飞行遥测模型。
- 仿真平台、数据集、模型和知识库均通过 Adapter 或 Provider 接入。
- 规则决定安全底线，大模型只能补充分析和建议，不能绕过硬规则。
- 所有建议必须保留规则证据、知识来源、模型信息和审批记录。
- 大模型或知识库不可用时，系统应回退到纯规则建议。

## 3. 目标架构

```text
真实数据集 / PX4 / MAVLink / 仿真平台
                 ↓
        Telemetry Adapter
                 ↓
统一遥测模型 + 坐标/时间/单位转换
                 ↓
 Entity / Track / Alert / Event Store
        ↓                       ↓
Cesium/Omniverse Adapter      规则引擎
                                 ↓
                       分层知识库检索
                                 ↓
                          LLM Provider
                                 ↓
                       建议校验与风险控制
                                 ↓
                    Recommendation / Task
```

## 4. 统一飞行遥测模型

优先在 `lattice_core` 中建立统一的 `FlightTelemetry`，作为数据集、实时飞控、仿真器和前端之间的稳定边界。

建议字段：

- `schemaVersion`、`timestamp`、`vehicleId`、`source`
- WGS84 经纬度和高度
- NED/ENU 位置与速度
- 四元数及 roll、pitch、yaw
- 角速度和线加速度
- 空速、地速、航向、爬升率
- 飞行模式、解锁状态、电量
- GPS、姿态和传感器质量标记
- 原始消息引用和数据置信度

必须统一处理：

- WGS84、ECEF、ENU、NED 坐标转换。
- 度、弧度、米、秒等单位转换。
- UTC、仿真时间和数据集相对时间。
- 欧拉角与四元数互转。
- 数据乱序、重复、缺失、插值和降采样。

建议目录：

```text
lattice_core/
  telemetry.py
  coordinates.py
  timebase.py

adapters/
  base.py
  px4_ulog.py
  mavlink.py
  euroc.py
  jsbsim.py
  cesium.py
  omniverse.py
```

## 5. 三维展示与物理仿真

### 5.1 Cesium

Cesium 首先作为地理空间三维展示端，不承担飞行动力学计算。

实现内容：

- 将现有二维地图扩展或替换为 CesiumJS 三维地球。
- 加载飞机和无人机 glTF/GLB 模型。
- 根据统一遥测更新位置和四元数姿态。
- 显示历史轨迹、预测轨迹、禁飞区和传感器覆盖区。
- 支持历史回放、暂停、倍速和时间轴拖动。
- 继续通过 WebSocket 接收实时事件。

### 5.2 物理仿真

建议按以下顺序接入：

1. PX4 SITL + Gazebo：无人机飞控、MAVLink 和控制闭环。
2. JSBSim：固定翼飞机动力学。
3. Omniverse/Isaac Sim：高质量三维场景、传感器、碰撞和数字孪生。

仿真 Adapter 只负责：

- 创建和更新仿真实体。
- 交换位置、姿态、速度和传感器状态。
- 同步仿真时钟。
- 将碰撞、故障和传感器事件转换为统一事件。
- 通过受控接口接收已审批的任务或控制指令。

## 6. 开源飞行数据

### 6.1 PX4 ULog

作为第一优先数据源，解析：

- `vehicle_attitude`
- `vehicle_local_position`
- `vehicle_global_position`
- `sensor_combined`
- `vehicle_status`
- `battery_status`

使用 `pyulog` 完成 ULog 解析，并转换为统一遥测事件。

### 6.2 EuRoC MAV

用于验证：

- IMU 和六自由度姿态。
- 坐标系转换。
- 时间同步和插值。
- 轨迹回放与误差计算。

### 6.3 仿真生成数据

使用 PX4 SITL、JSBSim 或 Omniverse 生成可控场景：

- 正常巡航。
- 禁区入侵。
- GPS 漂移或丢失。
- 姿态异常和急转。
- 超速、失速和低电量。
- 通信中断。
- 多机接近或碰撞风险。

### 6.4 数据存储

高频遥测不再写入单个 JSON Store。建议第一版使用：

- Parquet：保存标准化历史遥测。
- DuckDB：本地查询和分析。
- JSON Store：继续保存当前业务实体、告警、建议和任务。
- 后续需要多实例时迁移到 PostgreSQL/TimescaleDB。

建议目录：

```text
datasets/
  raw/
  normalized/
  manifests/

data_lake/
  telemetry/
  events/
```

## 7. 大模型 API 解耦

定义独立的 `LLMProvider`：

```python
class LLMProvider(Protocol):
    async def generate_structured(self, messages, response_schema):
        ...
```

建议实现：

```text
providers/llm/
  base.py
  openai_compatible.py
  ollama.py
  vllm.py
  dify_compat.py
  mock.py
```

运行配置：

```text
LLM_PROVIDER
LLM_BASE_URL
LLM_API_KEY
LLM_MODEL
LLM_TIMEOUT_SECONDS
```

要求：

- 强制结构化 JSON 输出并进行 Pydantic 校验。
- 实现超时、重试、并发限制和熔断。
- 记录模型、提示词版本、耗时和 token。
- 敏感字段进入模型前进行脱敏。
- 模型不可用时回退到规则模板。
- 模型不得直接执行任务或控制飞行器。

Dify 保留为临时兼容 Provider，核心流程不再依赖 Dify 工作流。

## 8. 分层知识库

| 层级 | 内容 | 典型示例 |
| --- | --- | --- |
| L0 规则层 | 强制约束、阈值和法规 | 禁飞区、最低电量、碰撞距离 |
| L1 平台层 | 飞机、传感器和飞控知识 | 机型手册、故障码、性能边界 |
| L2 SOP 层 | 处置流程和应急预案 | GPS 丢失、入侵、失速处置 |
| L3 案例层 | 历史事件和执行结果 | 告警、建议、任务和复盘记录 |

知识条目至少包含：

- `documentId`、`layer`、`title`、`content`
- 适用机型、风险类型和区域
- 版本、生效时间、来源和权威度
- 标签、关联规则和引用关系

轻量化实现：

- Markdown/JSON 保存原始文档。
- SQLite 保存元数据、版本和审计信息。
- SQLite FTS5/BM25 提供关键词检索。
- FAISS 或 Qdrant 提供向量检索。
- 本地 Sentence Transformers 生成 Embedding。
- 由工程内部 `KnowledgeRetriever` 提供统一检索接口。
- Dify 知识库改为可选 Adapter。

检索顺序：元数据过滤 → 关键词检索 → 向量检索 → 重排 → 权威度与版本校验。

## 9. 规则与大模型混合建议

```text
遥测标准化
  → 硬规则检测
  → 风险和置信度计算
  → 根据规则、机型和区域检索知识库
  → LLM 生成结构化建议
  → 硬约束和来源校验
  → 人工审批或输出最终建议
```

建议结果应包含：

- 风险等级和摘要。
- 命中的规则及证据。
- 推荐动作、优先级和审批要求。
- 引用的知识条目及版本。
- 模型置信度和已知限制。
- 模型、提示词和生成时间。

安全约束：

- 硬规则决定风险下限，大模型不能降低。
- 大模型不能覆盖禁飞、碰撞、电池等安全规则。
- 没有有效知识来源时不得输出高置信度建议。
- 高风险动作必须人工批准。
- LLM 失败时输出规则模板建议。
- 执行结果可进入 L3 案例层，但不能自动成为权威 SOP。

## 10. 实施阶段

### 阶段 A：遥测基础

- 建立 `FlightTelemetry`。
- 完成坐标、单位、时间和姿态转换。
- 将当前 ingest 映射到统一模型。
- 增加高频遥测存储与回放接口。

验收：同一轨迹可稳定回放，姿态、坐标和时间转换测试通过。

### 阶段 B：数据集接入

- 实现 PX4 ULog Adapter。
- 实现 EuRoC Adapter。
- 建立 Parquet 数据目录和数据集清单。
- 支持暂停、倍速、循环和时间范围回放。

验收：真实位置、速度和姿态可进入 Entity/WebSocket 流程。

### 阶段 C：Cesium 三维展示

- 集成 CesiumJS。
- 加载飞机/无人机三维模型。
- 实现位置、姿态、轨迹和时间轴。
- 显示告警区、预测轨迹和传感器范围。

验收：历史数据和实时数据均可驱动三维模型。

### 阶段 D：物理仿真

- 接入 PX4 SITL 或 JSBSim。
- 定义仿真控制与遥测接口。
- 实现仿真时间同步。
- 后续实现 Omniverse Adapter。

验收：仿真状态实时进入系统，已审批任务可通过受控接口返回仿真器。

### 阶段 E：LLM 与知识库解绑

- 实现通用 `LLMProvider`。
- 实现本地分层知识库。
- 将 Dify 改为可选 Adapter。
- 加入模型超时和规则回退。

验收：关闭 Dify 后，知识检索和建议流程仍能运行。

### 阶段 F：混合建议系统

- 规则引擎输出结构化证据。
- 知识库按规则、机型和区域检索。
- LLM 生成结构化建议。
- 增加安全校验、人工审批和审计。

验收：建议可解释、可追溯、可回退，模型不能绕过硬规则。

## 11. 第一轮开发范围

第一轮建议只完成以下六项：

1. `FlightTelemetry` 统一模型。
2. PX4 ULog 数据解析与回放。
3. CesiumJS 三维位置、姿态和轨迹展示。
4. `LLMProvider` 和一个 OpenAI-compatible 实现。
5. SQLite FTS5 + FAISS/Qdrant 轻量知识库。
6. 规则证据 + 知识检索 + 结构化建议闭环。

第一轮暂不实现：

- 复杂 Omniverse 场景。
- 多模型协作或智能体编排。
- 自动控制真实飞行器。
- 分布式消息队列和多实例部署。
- 大规模在线训练。

## 12. 第一轮完成标准

- 至少一个 PX4 ULog 文件可转换并回放。
- Cesium 中可正确显示飞机位置、roll、pitch、yaw 和历史轨迹。
- 当前 Entity、Alert、Recommendation 和 Task API 保持兼容。
- 不配置 Dify 时仍可完成知识检索和建议生成。
- 大模型不可用时自动回退到规则建议。
- 每条建议可追溯到规则、知识条目、模型和提示词版本。
- 新模块具备单元测试、入口测试和最小运行文档。
