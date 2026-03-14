# Atomic Lab — 沉浸式科研工作站

> Read · Organize · Write

## 项目简介

Atomic Lab 是一款面向研究者的 AI 辅助科研工作站。围绕「阅读 → 整理 → 写作 」三阶段工作流，将文献阅读和笔记管理流程与大语言模型结合，自动完成笔记分类、关键词标注和知识图谱构建。

**核心理念**：每一条笔记都是知识的原子。

## 功能亮点

### Tab 1：阅读

- **多种查看模式**：PDF高亮（推荐）、文本模式、PDF原版、文档结构、MinerU Markdown（见下方阅读模式表）
- **PDF 高亮交互**：PDF.js 保真渲染 + 文本选择高亮 + 坐标映射 RAG 分块
- **高亮笔记**：选中文字弹出浮动工具栏（高亮 · 翻译 · 复制 · 问AI），点击颜色自动保存为笔记卡片（黄/绿/蓝/粉）
- **一键翻译**：弹出菜单内中英互译，可保存翻译结果为笔记
- **RAG 索引**：上传 PDF 后自动解析、分块、向量化，支持 Docling / MinerU Cloud 解析后端

### Tab 2：整理

- **双图谱视图**：笔记知识图谱（ECharts 力导向图）+ 文献关系图（共享标签连边）
- **AI 笔记分类**：Crusher Agent 七分类（方法/公式/图像/定义/观点/数据/其他）+ 自动打标签与批注
- **原子解构**：将笔记解构为公理/边界/方法论等 Atomic Knowledge，挂载在知识树 Note 下
- **RAG 检索与搜索**：关键词/语义检索、节点跳转原文、提取引用

### Tab 3：写作

- **Markdown 写作区**：格式工具栏 + 侧栏知识树/图谱浏览 + 文献切换
- **AI 续写建议**：基于当前草稿与知识库生成续写内容
- **检查**：本地正则检测常见错别字与学术病句，结果输出到 AI 建议框
- **一键语病/润色**：对全文做语病检查与润色后写回草稿
- **Zen 模式**：外圈变灰、写作区磨砂玻璃，不改变尺寸，便于专注写作
- **导出**：导出 Markdown 草稿

### Tab 4：AI 助手

- **Agentic RAG 流水线**：Reviewer 规划（意图识别 + 中英关键词）→ Seeker 多路召回（FAISS 向量 Top5 + 知识图谱一度扩展 + ArXiv）→ Reviewer 评估 → Synthesizer 流式生成并标注引用
- **引用区分**：[1]-[5] 为向量直接匹配，[G1]-[Gk] 为知识图谱关联扩展；引用来源 UI 与回答末尾同步标注
- **阅读 Tab 上下文**：在阅读页提问时自动注入当前打开文档内容，优先参考；「翻译摘要」直接翻译当前文档摘要或前 500 字
- **概念解释**：问 RAG/知识图谱等学术名词时走「本地检索 + 常识」，严禁仅回复「未在本地找到」
- **引用来源 UI**：当前回答的本地文献与 ArXiv 卡片在「多路召回完成」后即渲染，与 [1]-[5]/[G1] 一致；点击本地卡片触发 `jumpToSource` 跳转阅读 Tab 并定位 PDF 页码。
- **可点击引用**：回答内 [1][G1] 等与引用栏、引用面板卡片均支持一键跳转 PDF 对应页。
- **实时状态反馈**：规划 → 召回 → 评估 → 合成各阶段进度可视化

### RAG 与阅读模式 (v2.3+)

**五种阅读模式**：

| 模式                | 保真渲染 | 高亮交互 | RAG分块   | 适用场景                     |
| ------------------- | -------- | -------- | --------- | ---------------------------- |
| **PDF高亮**         | ✅ 高    | ✅ 完整  | ✅ 支持   | **推荐：主要阅读模式**       |
| **MinerU Markdown** | ✅ 中    | ❌ 无    | ✅ 高级   | MinerU 解析原文与章节结构    |
| **文档结构**        | ✅ 中    | ❌ 无    | ✅ 高级   | 章节层级可视化、RAG 调试     |
| 文本模式            | ❌ 低    | ✅ 完整  | ⚠️ 简单  | 快速阅读、全文搜索           |
| PDF原版             | ✅ 高    | ❌ 无    | ❌ 无     | 打印预览、格式确认           |

**MinerU Markdown 模式** (v2.3新增)：

- 直接展示 MinerU 解析生成的原始 Markdown，不再经过二次推断
- 展示解析器名称与置信度评分
- 标题层级（h1–h6）轻量渲染，保留完整内容结构
- 新上传文档的图片在展示时自动 Base64 内联（与 Demo 一致），跨环境可加载

**文档结构显示模式**（原 Docling 结构）：

- 优先读取缓存的 `ParsedDocument.sections`，直接映射原始章节
- 章节层级可视化：正确渲染 Markdown 标题层级（#, ##, ###）
- 参考文献过滤：自动识别并过滤参考文献条目

**PDF.js 高亮模式** (v2.3)：

- 基于PDF.js 3.11的保真渲染（公式、表格、图片完整显示）
- 文本层选择 → 一键高亮（黄/绿/蓝/粉四色）
- 坐标映射服务：PDF位置 ↔ RAG Chunk ID双向映射
- iframe嵌入架构：完整HTML文档通过srcdoc安全加载

**高级PDF解析**：

- **Docling 解析器**：IBM 开源高保真 PDF 解析，支持表格结构化提取、公式识别、图表描述
- **MinerU Cloud 解析器**：高精度 VLM 云端解析（`PARSER_BACKEND=mineru` + `MINERU_API_KEY`），支持扫描 PDF OCR；解析结果缓存至 `parsed_docs`，供文档结构/MinerU Markdown 视图直接读取
- **解析质量评估**：自动计算文档解析置信度，低质量文档预警

**智能文本分块**：

- **语义分块**（默认）：基于 sentence-transformers 计算句子相似度动态分割，保持语义完整性；最小句子数 4、最小 token 阈值限制过碎分块
- **段落分块**（新增）：按空行直接切割，无需加载 embedding 模型，启动快、适合结构完整的解析结果；自动合并过短段落、拆分超长段落
- **表格专用分块**：双重 embedding 策略（结构hash + 语义文本）
- **坐标映射服务**：`services/renderer/coordinate_mapper.py` - PDF 位置 ↔ Chunk ID 双向映射
- **分块配置**：分块模式（语义/段落）、分块粒度（细/中/粗）可通过环境变量配置（阅读页控件已隐藏）

**三路混合检索**：

- **语义检索**：FAISS向量存储 + HNSW索引，支持高维向量快速检索
- **关键词检索**：BM25算法 + jieba中文分词，精准匹配专业术语
- **模糊匹配检索**：支持部分匹配、前缀匹配，精确匹配优先、模糊备选
- **查询扩展**：自动扩展相关术语（如SQL→MySQL/PostgreSQL/SQLite/Database）
- **元数据过滤**：按文档类型、日期、作者、章节等维度预过滤
- **章节检索**：自动识别章节标题（References、Introduction等），支持按章节搜索

**两阶段重排序**：

- **RRF融合**：Reciprocal Rank Fusion算法融合多路检索结果
- **Cross-Encoder重排序**：bge-reranker-v2-m3模型精确计算相关性

**智能问答集成**：

- **RAG优先检索**：AI助手优先使用语义检索获取相关文档片段
- **查询重写**：`optimize_search_query()` 做意图识别（闲聊/任务 → 跳过检索）与中英学术关键词提取，ArXiv 使用英文关键词避免 0 结果
- **多路召回**：本地 FAISS 向量 Top5 + 知识图谱一度扩展（edges 主-谓-宾关联）+ ArXiv 兜底（本地结果少于 2 条时触发）
- **精准引用**：回答中区分 [1]-[5]（向量）与 [G1] 等（图谱扩展），标注 [参考本地文献: 第X页] / [扩展知识]；引用栏可点击跳转 PDF 或打开 ArXiv
- **实时状态反馈**：规划 → 召回 → 评估 → 合成各阶段进度可视化
- **优雅降级**：RAG服务不可用时自动回退到传统搜索

## AI 架构

### Multi-Agent 系统

**整理 / 写作侧**（BaseAgent 协议）：

| Agent         | 职责           | 说明                                      |
| ------------- | -------------- | ----------------------------------------- |
| **Router**    | 意图识别 + 分发 | 关键词检测 + LLM 分类，路由到对应专家     |
| **Crusher**   | 笔记分类引擎   | 七分类 + 标签 + 摘要 + 学科识别            |
| **Synthesizer** | 跨文献合成   | 主题发现 + 关联分析 + 重要性排序 + 洞察    |
| **Translator** | 翻译引擎     | 中英自动检测 + 互译                        |

**AI 助手（对话）RAG 流水线**（四阶段串行）：

| 阶段        | 职责           | 说明                                                       |
| ----------- | -------------- | ---------------------------------------------------------- |
| **Reviewer 规划** | 意图与检索规划 | 意图识别、中英关键词提取、多路召回规划                     |
| **Seeker 执行**  | 多路召回       | 按规划执行 FAISS / 知识图谱(Mock) / ArXiv 检索             |
| **Reviewer 评估** | 质量评估       | 对召回上下文打分，过滤低质片段                             |
| **Synthesizer 合成** | 回答生成     | 基于高分上下文流式生成，标注 [1][2] 引用，可点击跳转 PDF   |

### LLM 多模型容错

`call_llm()` 采用三级降级策略，保障服务高可用：

1. **ModelScope 主模型**（`MODEL_NAME`，默认 Qwen3.5-35B-A3B）
2. **ModelScope 备用模型**（`FALLBACK_MODELS` 列表，依次尝试）
3. **DeepSeek 官方 API**（当所有 ModelScope 模型限额时，使用 `DEEPSEEK_API_KEY`）

触发限额（HTTP 429）后模型进入 1 小时冷却，次日午夜自动重置。

### Atomic-RAG

以单条笔记为检索粒度，AI 在分类阶段介入（而非生成阶段），用户保留写作控制权。对话模式下采用 3 步 RAG 管线：搜索节点 → 提取上下文 → 生成回答。

### RAG服务架构

```
┌─────────────────────────────────────────────────────────────┐
│                    RAG Service Pipeline                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐                │
│  │ Docling  │──▶│ Chunking │──▶│ Embedding│                │
│  │  Parser  │   │ Service  │   │  Model   │                │
│  └──────────┘   └──────────┘   └────┬─────┘                │
│                                      │                       │
│  ┌───────────────────────────────────▼──────────────────┐   │
│  │                   Vector Store (FAISS)                │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────────────────┐  │   │
│  │  │HNSW Idx │  │BM25 Idx │  │  Metadata Filter    │  │   │
│  │  └─────────┘  └─────────┘  └─────────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                      │                       │
│  ┌───────────────────────────────────▼──────────────────┐   │
│  │                 Retrieval Pipeline                    │   │
│  │  Semantic ──┬── Keyword ──┬── Metadata ──▶ RRF Fusion │   │
│  └───────────────────────────────────┬──────────────────┘   │
│                                      ▼                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Cross-Encoder Reranker                   │   │
│  │              (bge-reranker-v2-m3)                     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 知识树结构

五级层级：`Domain → Document → Section → Note/Summary → Atomic Knowledge`（Atomic 为原子解构后的知识卡片，挂在 Note 下）。支持 `contains`、`tagged_with`、`references` 三种边关系。

## 技术栈

| 层         | 技术                                                              |
| ---------- | ----------------------------------------------------------------- |
| 前端框架   | Gradio 6.5+（Python 原生 Web UI）                                 |
| 主题       | Gradio Soft 浅色主题 + 自定义 CSS                                 |
| 大语言模型 | ModelScope Inference API（主）→ DeepSeek 官方 API（降级）        |
| 可视化     | ECharts 5（MutationObserver 自动初始化）                          |
| PDF 解析   | PyPDF2（基础）+ Docling / MinerU（高级解析，可切换）              |
| 向量存储   | FAISS (HNSW索引)                                                  |
| 语义模型   | sentence-transformers (MiniLM)                                    |
| 重排序模型 | bge-reranker-v2-m3                                                |
| 关键词检索 | rank-bm25 + jieba                                                 |
| 语言       | Python 3.10+                                                      |

## 项目结构

```
atomic-lab/
├── main.py              # 入口：组装 UI + 事件绑定 + RAG 服务初始化
├── core/
│   ├── config.py        # API、模型、RAG、MinerU 配置
│   ├── utils.py         # PDF 提取、JSON 解析、HTML 转义、Markdown 图片 Base64 内联
│   └── state.py         # ID 生成器、状态工厂
├── models/
│   ├── parse_result.py  # 解析结果模型（ParsedDocument / Section / Figure 等）
│   ├── chunk.py         # 文本块模型
│   ├── search.py        # 搜索结果模型
│   └── atomic_knowledge.py  # 原子知识解构模型
├── agents/
│   ├── base.py          # BaseAgent 协议 + call_llm()
│   ├── crusher.py       # Crusher 笔记分类引擎
│   ├── synthesizer.py   # Synthesizer 跨文献合成引擎
│   ├── router.py        # Router 意图识别 + 分发
│   ├── translator.py    # Translator 中英互译
│   └── conversation.py  # Conversation RAG 问答
├── services/
│   ├── rag_service.py   # RAG 统一服务（解析、分块、索引、检索、重排序）
│   ├── parser/          # 文档解析
│   │   ├── docling_parser.py      # Docling 本地解析
│   │   └── mineru_cloud_parser.py # MinerU Cloud API 解析
│   ├── chunking/        # 智能分块
│   │   ├── semantic_chunker.py   # 语义分块
│   │   ├── paragraph_chunker.py  # 段落分块
│   │   └── table_chunker.py
│   └── search/          # 检索
│       ├── faiss_store.py
│       ├── bm25_index.py
│       ├── hybrid_searcher.py
│       └── reranker.py
├── knowledge/
│   ├── tree_model.py    # KnowledgeTree / 五级层级 / ECharts 序列化
│   └── search.py        # 搜索、过滤、层级路径查询
├── ui/
│   ├── styles.py        # CSS（浅色主题、Zen 模式、高亮等）
│   ├── global_js.py     # 全局 JS（ECharts、jumpToSource、引用可点击）
│   ├── renderers.py     # HTML 渲染（卡片、知识树、合成结果）
│   └── echarts_graph.py # ECharts 图谱
├── tabs/
│   ├── read/            # 阅读：上传、多模式阅读、高亮笔记、MinerU Markdown、RAG 索引
│   ├── organize/        # 整理：双图谱、Crusher、原子解构、RAG 检索
│   ├── write/           # 写作：Markdown、知识树、AI 续写、语病润色、Zen 模式
│   └── chat/            # AI 助手：Agentic RAG 流水线、引用跳转
├── scripts/
│   └── generate_demo_mock.py  # Demo 静态数据与 Base64 内联图片生成
└── requirements.txt
```

## Tab 布局

| Tab      | 左栏                | 中栏                      | 右栏                |
| -------- | ------------------- | ------------------------- | ------------------- |
| 阅读     | 文献列表 + 查看模式 | 文本/PDF双模式阅读 + 翻页 | 阅读笔记卡片        |
| 知识图谱 | 搜索 + RAG检索      | 笔记图谱 + 文献关系图     | 节点详情 + 分析结果 |
| 写作     | 搜索 + 知识树浏览   | Markdown 编辑器 + 工具栏  | AI 建议 + 导出      |
| AI 助手  | —                  | 对话界面（RAG 问答）      | —                  |

## 快速启动

### 基础安装

```bash
pip install -r requirements.txt
python main.py
```

### 完整RAG功能安装

```bash
# 安装所有依赖（包括RAG组件）
pip install -r requirements.txt

# 或单独安装RAG核心组件
pip install sentence-transformers>=2.2.0 faiss-cpu>=1.7.4 rank-bm25>=0.2.2 docling>=2.0.0
```

浏览器访问 `http://127.0.0.1:7860`

### RAG服务使用示例

```python
from services.rag_service import RAGService
from core.config import RAG_CONFIG

# 初始化RAG服务
rag = RAGService(RAG_CONFIG)

# 处理文档（自动解析、分块、索引）
result = rag.process_document("/path/to/paper.pdf", doc_id="paper_001")
print(f"处理完成: {result.chunk_count} 个文本块")

# 混合检索
retrieval = rag.retrieve("深度学习在NLP中的应用", top_k=5)
for chunk in retrieval.chunks:
    print(f"[{chunk.metadata.doc_title}] {chunk.content[:100]}...")
```

### 环境变量

| 变量                         | 默认值                           | 说明                                           |
| ---------------------------- | -------------------------------- | ---------------------------------------------- |
| `MS_KEY`                     | (无)                             | ModelScope API Key（主要 LLM 来源）            |
| `DEEPSEEK_API_KEY`           | (无)                             | DeepSeek 官方 API Key（ModelScope 限额后降级） |
| `DEEPSEEK_API_BASE`          | `https://api.deepseek.com/v1`   | DeepSeek API 端点                              |
| **MinerU 云端解析**          |                                  |                                                |
| `MINERU_API_KEY`             | (无)                             | MinerU Cloud API Key（必填才可用 mineru 后端）  |
| `MINERU_API_BASE`            | (空)                             | MinerU API 基础地址，未设时用官方 v4            |
| `MINERU_API_ENDPOINT`        | (空)                             | 完整解析端点，若设置则优先于 MINERU_API_BASE   |
| `MINERU_PARSE_METHOD`        | `auto`                           | 解析策略：auto / ocr / txt 等                  |
| **解析与分块**               |                                  |                                                |
| `PARSER_BACKEND`             | `docling`                        | 解析后端：`docling` 或 `mineru`                 |
| `CHUNK_MODE`                 | `semantic`                       | 分块模式：`semantic` 或 `paragraph`             |
| `RAG_CHUNK_SIZE`             | `900`                            | 分块最大 token 数                              |
| `RAG_CHUNK_OVERLAP`          | `120`                            | 相邻分块重叠 token 数                          |
| `RAG_SIMILARITY_THRESHOLD`   | `0.58`                           | 语义分割相似度阈值（越低=块越大）              |
| `HF_HOME`                    | (系统默认)                       | HuggingFace 模型缓存目录                       |

## 技术要点

### RAG混合检索与 Graph RAG

三路检索 + 两阶段重排序：

1. **语义检索**：FAISS HNSW索引，余弦相似度
2. **关键词检索**：BM25 + jieba分词
3. **元数据过滤**：按文档属性预过滤
4. **RRF融合**：`score = Σ(weight_i / (60 + rank_i))`
5. **Cross-Encoder重排序**：精确计算 query-document 相关性

**Graph RAG（一度扩展）**：解析阶段从 chunk 文本抽取主-谓-宾三元组存入 `ParsedDocument.edges`；检索时取向量 Top5 后，根据 edges 做一度关联扩展，将关联 chunk 并入上下文并标注为 [G1]、[G2] 等，与向量直接匹配 [1]-[5] 区分。

### 表格双重Embedding

- **结构Hash**：用于精确匹配，识别相同结构的表格
- **语义文本**：用于相似搜索，理解表格内容含义

### JS ↔ Python 通信

Gradio 6.5.1 的 `gr.HTML()` 使用 innerHTML 赋值，会自动过滤 `<script>` 标签。解决方案：

1. 全局 JS 通过 `launch(js=...)` 注入，在页面加载时执行一次
2. ECharts 配置通过 `data-option` 属性传递，MutationObserver 监测 DOM 变化自动初始化
3. JS → Python 通过隐藏 Textbox 的 `change` 事件触发 Gradio 回调
4. Python → JS 通过更新 `gr.HTML()` 组件内容实现

### PDF 双模式

- **文本模式**：PyPDF2 逐页提取文本，渲染为可选中的段落（支持高亮弹出菜单）
- **PDF 模式**：Base64 编码嵌入 `<object>` 标签，20MB 以内直接渲染，超大文件提示切换文本模式

## 依赖清单

```txt
# requirements.txt
gradio>=6.0.0
openai>=1.30.0
PyPDF2>=3.0.0
python-dotenv>=1.0.0

# 搜索功能
jieba>=0.42.0
numpy>=1.24.0

# RAG语义搜索
sentence-transformers>=2.2.0

# 高级PDF解析
docling>=2.0.0

# 向量数据库
faiss-cpu>=1.7.4

# 关键词检索
rank-bm25>=0.2.2
```

## 声明

### 第三方模型声明

本项目使用以下预训练模型，其版权归各自作者所有：

| 模型                                      | 用途     | 许可证     | 来源                                                               |
| ----------------------------------------- | -------- | ---------- | ------------------------------------------------------------------ |
| `paraphrase-multilingual-MiniLM-L12-v2` | 文本嵌入 | Apache 2.0 | [Sentence-Transformers](https://huggingface.co/sentence-transformers) |
| `BAAI/bge-reranker-v2-m3`               | 重排序   | Apache 2.0 | [BAAI](https://huggingface.co/BAAI)                                   |

**注意**：模型文件在首次运行时自动从 HuggingFace Hub 下载并缓存到本地持久化目录，无需手动下载。

### 第三方库声明

本项目依赖以下开源库（详见 requirements.txt）：

- [Gradio](https://gradio.app/) - Apache 2.0
- [Docling](https://github.com/DS4SD/docling) - MIT
- [FAISS](https://github.com/facebookresearch/faiss) - MIT
- [Sentence-Transformers](https://www.sbert.net/) - Apache 2.0


## Demo 体验与 MinerU Cloud 集成

### Demo 静态数据（秒开体验）

为了在本地和 ModelScope 创空间中提供「秒开级」体验，本项目在根目录下约定了 `demo_data/` 目录，用于存放预生成的 Demo 数据：

- `demo_data/demo_paper.pdf`：官方架构白皮书或示例论文 PDF；
- `demo_data/mock_library.json`：预计算好的文献库状态（对应 `lib_st` + `stats_st`）；
- `demo_data/mock_notes.json`：预置的原子知识卡片列表（对应 `notes_st`）；
- `demo_data/faiss_index/`：预构建好的向量索引（`index.faiss` + `metadata.pkl`）。

阅读页左侧上传区域提供按钮：

- `🎁 体验: 加载官方架构白皮书`

点击后，系统**只会加载上述静态数据**，不会触发任何新的解析或 embedding，保证在只读或资源受限环境中也能即时体验完整 RAG 流程。

### 生成 Demo 数据（离线脚本）

**怎么运行**：在**项目根目录**执行：

```bash
python -m scripts.generate_demo_mock
```

前置条件：将白皮书或示例 PDF 放入 `demo_data/demo_paper.pdf`，安装 RAG 依赖（见上方「完整RAG功能安装」）；使用 MinerU 解析时需配置 `MINERU_API_KEY`。脚本仅适合本地/开发环境（会写入 `demo_data/`），只读或容器内勿用。

当你更新解析算法或 RAG 配置时，运行上述命令可重新生成 Demo 所需的静态数据。脚本会执行以下步骤：

1. 使用 `demo_data/demo_paper.pdf` 作为输入文档；
2. 调用真实 `RAGService` 与 `handle_upload()`，走完解析 → 分块 → 向量化 → 索引全流程；
3. 将向量索引保存到 `demo_data/faiss_index/`，同时将文献库与笔记状态写入：
   - `demo_data/mock_library.json`
   - `demo_data/mock_notes.json`
4. 将 Markdown 中的图片引用转为 Base64 内联并写入 `mock_library.json`，确保 ModelScope / 本地跨平台 100% 加载图片。

生成完成后，重新启动应用并点击 Demo 按钮，即可在任意环境中获得与真实流程一致的 Demo 体验。RAG 回答中的引用 [1][2] 可点击，通过全局 `jumpToPdf` 跳转阅读页并定位到对应 PDF 页码。