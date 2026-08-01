# Embedding RAG 外挂知识库

管理界面：`/static/rag-knowledge.html`

当前最小闭环支持 TXT、Markdown、JSON 和 CSV 文档：

1. 浏览器上传文档。
2. 后端按字符长度、自然段和句末边界分段，并保留可配置重叠区。
3. Embedding Provider 批量生成向量。
4. 文档、分段和向量保存在 SQLite。
5. 界面可以查看全部分段，并输入问题执行向量相似度检索。

## 正式 Embedding 模型

系统支持 OpenAI 兼容的 `/embeddings` API。复制 `.env.local.example` 为
`.env.local`，然后配置：

```bash
export EMBEDDING_BASE_URL=http://127.0.0.1:模型服务端口/v1
export EMBEDDING_API_KEY=可选密钥
export EMBEDDING_MODEL=模型名称
export EMBEDDING_DIMENSION=模型向量维度
```

没有配置模型服务时使用 `local-hash-v1` 离线回退。它用于验证上传、分段、索引和检索链路，
不应作为正式语义检索质量基线。切换模型后，旧文档应重新上传并生成新向量。

## D 盘存储

较大知识库建议将数据库放到 D 盘：

```bash
export RAG_DATA_DIR=/mnt/d/lattice-data/rag
```

模型服务的权重目录也应单独配置到 `/mnt/d/lattice-data/models`。当前仓库不会自动下载大型模型。

## API

- `GET /api/v1/rag/documents`：文档列表和当前 Embedding Provider。
- `POST /api/v1/rag/documents`：上传、分段并生成向量。
- `GET /api/v1/rag/documents/{id}/chunks`：查看分段内容。
- `GET /api/v1/rag/search?q=问题&limit=5`：返回可直接放入大模型上下文的相关分段。
