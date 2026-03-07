# 更新日志

### 2026-03-07 v2.1.0 (advanced-pdf-parsing)

#### 🚀 新功能

**1. RAG系统**

- 实现三路混合检索架构（语义 + 关键词 + 元数据过滤）
- 两阶段重排序：RRF融合 + Cross-Encoder重排序
- 支持bge-reranker-v2-m3模型精确计算相关性

**2. 高级PDF解析 (Docling)**

- 集成IBM开源Docling解析器
- 支持表格结构化提取和Markdown导出
- 支持公式识别和图表描述
- 自动计算文档解析置信度

**3. 智能文本分块**

- 语义分块：基于sentence-transformers计算句子相似度动态分割
- 表格专用分块：双重embedding策略（结构hash + 语义文本）
- 支持中英文混合文本分块

**4. 向量存储与检索**

- FAISS向量存储，支持HNSW索引
- BM25关键词索引，支持jieba中文分词
- 元数据过滤和持久化存储

**5. RAG统一服务**

- 整合解析→分块→索引→检索→重排全流程
- 异步文档处理，不阻塞UI
- 优雅降级，依赖缺失时自动回退

#### 📦 新增文件

| 文件路径                                  | 功能描述                |
| ----------------------------------------- | ----------------------- |
| `models/parse_result.py`                | Docling解析结果数据模型 |
| `models/chunk.py`                       | 文本块数据模型          |
| `models/search.py`                      | 搜索结果数据模型        |
| `services/rag_service.py`               | RAG统一服务入口         |
| `services/parser/docling_parser.py`     | Docling解析器实现       |
| `services/chunking/semantic_chunker.py` | 语义分块器              |
| `services/chunking/table_chunker.py`    | 表格分块器              |
| `services/search/faiss_store.py`        | FAISS向量存储           |
| `services/search/bm25_index.py`         | BM25关键词索引          |
| `services/search/hybrid_searcher.py`    | 混合检索服务            |
| `services/search/reranker.py`           | Cross-Encoder重排序器   |
| `test_rag.py`                           | RAG功能测试脚本         |

#### 🔧 修改文件

| 文件路径                      | 变更说明                                |
| ----------------------------- | --------------------------------------- |
| `main.py`                   | 集成RAG服务初始化，更新事件绑定         |
| `core/config.py`            | 添加RAG_CONFIG配置项                    |
| `tabs/read/__init__.py`     | 上传时触发RAG文档处理                   |
| `tabs/organize/__init__.py` | 搜索时优先使用RAG检索                   |
| `agents/conversation.py`    | 集成RAG检索到AI问答，支持精准引用       |
| `services/parser/docling_parser.py` | 修复Docling API弃用警告         |
| `requirements.txt`          | 添加docling、faiss-cpu、rank-bm25等依赖 |

#### 📊 核心算法

**RRF融合算法**：

```
score = Σ(weight_i / (k + rank_i))
其中 k=60, weight_semantic=0.6, weight_keyword=0.3
```

**表格双重Embedding**：

- 结构Hash：MD5(列名+行数) 用于精确匹配
- 语义文本：表格描述 + 前500字符 用于相似搜索

#### 🧪 测试验证

- ✅ 模块导入测试（8/8通过）
- ✅ 数据模型测试
- ✅ RRF融合算法测试
- ✅ 主程序启动测试
- ✅ RAG检索集成到AI问答

#### 🐛 Bug修复

| 问题 | 解决方案 |
|------|----------|
| Docling API弃用警告 | 添加`doc`参数到`export_to_dataframe()`等方法 |
| RAG检索未生效 | ConversationAgent优先使用RAG服务检索 |
| 参考文献检索失败 | 语义检索支持全文检索，不再只搜索开头 |

---

### 2026-03-03 v2.0.1 (gradio6-ui)

1. **Gradio 6 适配** - 适配 Gradio 6.5+ 新版 API
2. **UI/UX 增强**
   - 卡片按钮功能修复（翻译、AI标签、批注、手动标签）
   - 全局文献选择同步（阅读/整理/写作三页面联动）
   - AI标签与手动标签分色显示（紫/绿）
   - 模态弹窗替代 prompt() 原生对话框
   - 按钮状态反馈（loading/success/error 动画）
3. **数据流优化**
   - 笔记元数据正确同步到知识树（notes_st ↔ tree_st ↔ lib_st）
   - AI摘要与AI标签功能分离
