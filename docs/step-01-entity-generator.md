# Step 01: 本地 Entity Generator

## 本步骤目标

本步骤创建一个纯本地的 Python 小工具，用于生成 Lattice-style 的模拟 `Surface Vessel` entity JSON。目标是先得到稳定、可重复使用的本地测试数据，而不是连接真实 Lattice 环境。

## 本步骤输入

输入来自命令行参数：

- `--count`：生成 entity 的数量，默认 `1`。
- `--center-lat`：随机位置中心点纬度，默认 `33.69447852698943`。
- `--center-lon`：随机位置中心点经度，默认 `-117.9173785693163`。
- `--radius-deg`：经纬度随机偏移半径，默认 `0.05`。
- `--output`：输出文件路径，默认 `examples/entities.jsonl`。
- `--format`：输出格式，可选 `json` 或 `jsonl`，默认 `jsonl`。

## 本步骤输出

输出是本地文件：

- 当 `--format json` 且 `--count 1` 时，输出单个 JSON 对象。
- 当 `--format json` 且 `--count` 大于 `1` 时，输出 JSON 数组。
- 当 `--format jsonl` 时，输出 JSONL 文件，每行一个 JSON 对象。

程序会在输出目录不存在时自动创建目录。

## 用到的公开 Lattice 概念

本步骤参考公开 Lattice Quickstart 中 surface vessel entity 的数据形状，使用了以下概念：

- `entityId`：entity 的唯一标识。
- `aliases.name`：entity 的可读名称。
- `milView.disposition`：军事视图中的关系属性。
- `milView.environment`：entity 所处环境。
- `location.position`：经纬度和高度位置。
- `ontology.template`：entity 的模板类型。
- `ontology.platformType`：平台类型。
- `ontology.specificType`：具体类型。
- `provenance`：数据来源和更新时间。

这些字段只用于本地模拟，不表示真实 Lattice schema 的完整实现。

## 具体实现了什么

`generate_entities.py` 实现了以下能力：

- 生成模拟的、非敏感的 `Surface Vessel` entity。
- 使用当前 UTC 时间生成 `provenance.sourceUpdateTime`。
- 使用当前 UTC 时间加 1 小时生成 `expiryTime`。
- 在指定中心点和半径范围内随机生成经纬度。
- 支持输出单个 JSON 对象。
- 支持输出 JSON 数组。
- 支持输出 JSONL 文件。
- 自动创建输出目录。
- 校验 `count >= 1`。
- 校验 `center-lat` 在 `-90` 到 `90` 之间。
- 校验 `center-lon` 在 `-180` 到 `180` 之间。
- 校验 `radius-deg >= 0`。

代码只使用 Python 标准库，没有外部依赖。

## 有意不实现什么

本步骤有意不实现以下内容：

- 不调用 Anduril API。
- 不需要 Anduril Sandbox。
- 不需要 token、client id 或 client secret。
- 不依赖 Anduril SDK。
- 不上传 entity。
- 不订阅 entity 更新。
- 不实现认证、授权、审计或真实网络传输。
- 不模拟完整 Lattice 服务端。
- 不处理真实敏感数据。

这样做的目的是把第一阶段限定为本地数据生成，降低联调 sample app 或 fake sandbox 前的复杂度。

## 下一步如何衔接 sample app 或 fake sandbox

下一步可以选择两种衔接方式：

1. sample app 直接读取生成的 `examples/entities.jsonl` 或 `examples/entity.json`，用于前端列表、地图展示或详情页渲染。
2. fake sandbox 读取同样的本地文件，并提供本地 HTTP API，例如 `GET /entities` 或 `GET /entities/{entityId}`。

在这两种方式中，entity generator 都保持为独立工具，只负责生成测试数据。sample app 或 fake sandbox 负责读取、过滤、展示或模拟接口响应。
