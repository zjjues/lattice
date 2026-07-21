# 本地知识库说明

当前 fake Lattice 已加入一个最小本地知识库层，用于给 recommendation 提供可检索的依据。

## 目录

知识库原始文件位于：

```text
kb/raw/
```

当前样例文件：

```text
kb/raw/security_sops.json
kb/dify_samples/
```

## 文档格式

每条文档是一个 JSON 对象，推荐包含：

- `docId`
- `docType`
- `title`
- `tags`
- `summary`
- `content`

## 接口

GET 搜索：

```bash
curl 'http://127.0.0.1:8000/api/v1/kb/search?q=restricted_area_intrusion%20uav'
```

POST 搜索：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/kb/search \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "restricted_area_intrusion uav",
    "limit": 3
  }'
```

## 当前实现边界

当前不是向量检索，而是本地轻量关键词检索，目标是：

1. 先把知识库作为系统资产留存下来。
2. 让 recommendation 不再只是纯模板或纯黑盒模型输出。
3. 后续可以无缝替换成 Dify Dataset、SQLite FTS、向量库或自建 RAG。

## Dify 导入样本

如果你想把知识库导入本地 Dify，可以直接使用：

```text
kb/dify_samples/
```

手把手步骤见：

```text
docs/dify-workflow-step-by-step.md
```

## 与 recommendation 的关系

系统在生成 recommendation 前，会先根据：

- alert 类型
- alert 标题
- entity 类型
- evidence

拼接检索 query，再把命中的 1-3 条结果放进 recommendation 上下文。

因此即使没有配置 Dify，`local-fallback` 生成的建议也会带上本地知识库 references。
