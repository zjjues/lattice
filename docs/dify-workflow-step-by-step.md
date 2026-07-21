# Dify Workflow 接入 fake lattice 的手把手步骤

这份说明对应本地 Dify 1.13.3。
目标是把 Dify 作为 recommendation 生成适配层，不让它接管实体、任务和告警状态。

## 第 1 步：准备知识库文件

先把下面目录里的 4 个文件导入 Dify Dataset：

```text
kb/dify_samples/
```

文件分别是：

- `uav_intrusion_sop.md`
- `fast_approach_guide.md`
- `loitering_sop.md`
- `multi_sensor_case.md`

如果你只想先跑最小版本，也可以只导入前 3 个。

## 第 2 步：在 Dify 创建 Dataset

1. 打开 Dify 控制台。
2. 进入 `Knowledge` 或 `Dataset` 页面。
3. 点击 `Create Dataset`。
4. 输入名称，例如 `fake-lattice-sop`。
5. 保存。

## 第 3 步：导入文档

1. 打开刚建好的 Dataset。
2. 点击 `Add file` 或 `Import`。
3. 选择 `kb/dify_samples/` 下的 Markdown 文件。
4. 等待解析完成。
5. 用关键词检索确认能搜到内容。

建议先搜：

- `警戒区`
- `高速接近`
- `盘旋`
- `多传感器`

## 第 4 步：创建 Workflow App

1. 回到 Dify 首页。
2. 点击 `Create App`。
3. 选择 `Workflow`。
4. 命名，例如 `Fake Lattice Advisor`。
5. 保存并进入工作流编辑器。

## 第 5 步：配置 Start 节点输入

你现在这套 fake lattice 最小接入只需要一个输入：

```text
context_json
```

操作方法：

1. 点击工作流里的 `Start` 节点。
2. 找到 `Input Variables` 或 `Inputs`。
3. 点击 `Add Variable`。
4. 变量名填：`context_json`
5. 类型选：`Text` 或 `String`
6. 说明可写：`告警上下文 JSON 字符串`

如果你想一步到位，也可以再加：

- `alert_json`
- `entity_json`
- `knowledge_json`
- `threat_json`
- `state_signature`

但第一轮只加 `context_json` 就够。

## 第 6 步：填写输入变量时怎么操作

这里最容易出错，所以单独说。

### 方式 A：在 Dify 预览里直接粘贴 JSON

如果你在测试面板看到一个文本框，直接把整段 JSON 粘进去即可。

例如：

```json
{
  "alert": {
    "alertId": "ALERT_001",
    "alertType": "restricted_area_intrusion",
    "riskLevel": "HIGH",
    "title": "疑似目标进入警戒区",
    "summary": "目标进入预设警戒区域，建议立即关注并确认身份。",
    "evidence": [
      "来源: uav / SIM_UAV_001",
      "位置: 31.23040, 121.47370"
    ]
  },
  "entity": {
    "entityId": "TRACK_UAV_001",
    "platformType": "UAV",
    "speedMps": 21.5,
    "headingDegrees": 72,
    "location": {
      "latitudeDegrees": 31.2304,
      "longitudeDegrees": 121.4737
    }
  }
}
```

注意：
- 不要写成 `"{...}"`。
- 不要自己再加一层引号。
- 直接粘原始 JSON。

### 方式 B：在 Workflow 里引用变量

在后续节点里，你一般不用手敲 JSON，只需要从变量面板里点选：

1. 点击输入框。
2. 打开变量选择器。
3. 选 `Start.context_json`。
4. 或选 `Start.alert_json`、`Start.entity_json`。

如果界面里没显示变量选择器，就手动输入变量名，格式通常是平台提示的那种占位符。

## 第 7 步：配置 Knowledge Retrieval 节点

如果你先做最小版本，可以跳过这一节点。  
如果你要用 Dify 自己的知识库检索，就这样做：

1. 在 `Start` 后面加一个 `Knowledge Retrieval` 节点。
2. 选择刚才建好的 Dataset。
3. 检索 query 优先用：
   - `context_json`
   - 或者从 JSON 中提取的 `alert.alertType`
   - `alert.title`
   - `alert.evidence`

如果节点支持变量映射，优先点选变量，不要手工拼一大段字符串。

## 第 8 步：配置 LLM 节点

1. 在检索节点后面加一个 `LLM` 节点。
2. 在提示词里写死输出格式。
3. 系统提示词建议用下面这段：

```text
你是一个安防/低空监控指挥辅助系统。
请根据输入的告警上下文、目标状态和知识库检索结果，输出结构化处置建议。
输出必须是 JSON 对象，且只包含 summary, riskLevel, actions, recommendedAssetTypes, confidence, references 这 6 个字段。
不要输出额外解释，不要输出 markdown。
```

4. 把模型输出类型设成尽量稳定的文本输出。

## 第 9 步：配置 End 节点

1. 在最后加一个 `End` 节点。
2. 把 LLM 的输出直接作为最终输出。
3. 确认输出是 JSON 字符串，而不是富文本。

## 第 10 步：发布 Workflow App

1. 保存工作流。
2. 点击 `Publish`。
3. 找到 `API Access` 或 `API Key`。
4. 复制这个 Key。

## 第 11 步：把 fake lattice 指向本地 Dify

在 fake lattice 启动前，先设置环境变量：

```bash
export DIFY_BASE_URL=http://127.0.0.1:5001
export DIFY_API_KEY=你的Dify应用APIKey
export DIFY_APP_MODE=workflow
export DIFY_USER=fake-lattice-local
```

然后启动 fake lattice：

```bash
cd /home/cring/lattice/entity-generator
uvicorn mock_server:app --reload --host 127.0.0.1 --port 8000
```

## 第 12 步：验证链路

1. 打开 fake lattice 页面。
2. 用回放脚本注入一个目标。
3. 在告警卡上点 `生成建议`。
4. 看 recommendation 是否出现。
5. 再点 `采纳并创建任务`。

如果成功，说明 Dify 已经接通。

## 第 13 步：先单独验证 Dify Workflow

在接 fake lattice 之前，先确认 Dify 自己能返回 JSON。

### 13.1 用 Dify 控制台测试

1. 打开 Workflow App。
2. 找到测试 / run / preview 面板。
3. 给 `context_json` 粘贴一段测试 JSON。
4. 直接运行。
5. 看输出是否是合法 JSON。

### 13.2 通过后应该看到

- 返回内容可被复制为纯 JSON。
- 包含 `summary`、`riskLevel`、`actions`、`recommendedAssetTypes`、`confidence`、`references`。
- 没有额外解释文字。

### 13.3 如果这里不通，先修 Dify

先不要碰 fake lattice。  
先把 Dify 的输出改到稳定 JSON，再继续下一步。

## 第 14 步：再验证 fake lattice 接入

1. 设置环境变量。
2. 重启 fake lattice。
3. 打开页面。
4. 回放目标。
5. 点 `生成建议`。
6. 看 recommendation 是否来自 Dify。

### 14.1 通过后应该看到

- recommendation 面板有新建议或复用建议。
- recommendation 的 provider 显示为 `dify`。
- 点击 `采纳并创建任务` 后，任务正常创建。

## 第 15 步：如果没有接通，先看这几项

1. `DIFY_BASE_URL` 是否正确。
2. `DIFY_API_KEY` 是否复制对了。
3. Workflow App 是否已经发布。
4. 输出是否仍然是纯 JSON。
5. Dataset 是否已经导入并能检索。
