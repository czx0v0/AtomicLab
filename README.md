# Atomic Lab — 沉浸式科研工作站

> Read · Organize · Write

## 项目简介

Atomic Lab 是一款面向研究者的 AI 辅助科研工作站。围绕「阅读 → 整理 → 写作 」三阶段工作流，将文献阅读和笔记管理流程与大语言模型结合，自动完成笔记分类、关键词标注和知识图谱构建。

**核心理念**：每一条笔记都是知识原子，AI 为其赋予分类和标签，最终形成可检索、可视化的知识树。

## 功能亮点

### 核心功能

- **沉浸式阅读**：三种阅读模式（PDF高亮/文本模式/PDF原版），选中文字自动弹出浮动工具栏（高亮 · 翻译 · 复制 · 问AI）
- **PDF高亮交互**：PDF.js保真渲染 + 文本选择高亮 + 坐标映射RAG分块
- **高亮笔记**：点击颜色按钮自动保存为笔记卡片，支持黄/绿/蓝/粉四色标记
- **一键翻译**：弹出菜单内中英互译，可保存翻译结果为笔记
- **AI 笔记分类**：Crusher Agent 自动分为「方法 / 公式 / 图像 / 定义 / 观点 / 数据 / 其他」七类
- **自动打标签**：每条笔记 1-3 个关键词标签 + 一句话 AI 批注
- **双图谱视图**：
  - 笔记知识图谱：文献 → 笔记 → 标签 树形结构（ECharts 力导向图）
  - 文献关系图：论文级关联（共享标签自动连边）
- **跨文献合成**：Synthesizer Agent 发现跨论文主题关联和宏观洞察
- **写作辅助**：Markdown 格式工具栏 + 侧栏知识树浏览 + AI 建议 + 导出
- **RAG 对话**：AI 助手基于文献和笔记回答问题，支持翻译、知识问答、跨文献分析
- **Agentic RAG 流水线**：Reviewer 规划（意图识别 + 中英关键词）→ Seeker 多路召回（FAISS / 图 / ArXiv）→ Reviewer 评估 → Synthesizer 流式生成并标注引用
- **引用来源 UI**：当前回答的本地文献与 ArXiv 卡片独立展示，点击本地卡片跳转 PDF 原文，点击 ArXiv 卡片新窗口打开
- **可点击卡片**：AI回答中的引用笔记、搜索结果均支持点击跳转到原文位置
- **实时状态反馈**：Chat/Organize/Write Tab 操作进度实时显示
- **密码保护**：默认开启，通过环境变量 `ENABLE_AUTH` 和 `AUTH_PASSWORD` 控制

### RAG系统 (v2.3)

**六种阅读模式**：

| 模式                    | 保真渲染 | 高亮交互 | RAG分块   | 适用场景                            |
| ----------------------- | -------- | -------- | --------- | ----------------------------------- |
| **PDF高亮**       | ✅ 高    | ✅ 完整  | ✅ 支持   | **推荐：主要阅读模式**        |
| **MinerU Markdown** | ✅ 中   | ❌ 无    | ✅ 高级   | 查看MinerU解析原文与章节结构        |
| **Docling结构**   | ✅ 中    | ❌ 无    | ✅ 高级   | 章节层级可视化，RAG调试             |
| **分块数据库**    | ❌ 低    | ❌ 无    | ✅ 高级   | 文本分块查看，章节组织              |
| 文本模式                | ❌ 低    | ✅ 完整  | ⚠️ 简单 | 快速阅读、全文搜索                  |
| PDF原版                 | ✅ 高    | ❌ 无    | ❌ 无     | 打印预览、格式确认                  |

**MinerU Markdown 模式** (v2.3新增)：

- 直接展示 MinerU 解析生成的原始 Markdown，不再经过二次推断
- 展示解析器名称与置信度评分
- 标题层级（h1–h6）轻量渲染，保留完整内容结构

**Docling结构显示模式**：

- 优先读取缓存的 `ParsedDocument.sections`，直接映射原始章节，**不再进行模糊关键词匹配**
- 章节层级可视化：正确渲染 Markdown 标题层级（#, ##, ###）
- 参考文献过滤：自动识别并过滤参考文献条目

**分块数据库显示模式**：

- 按章节组织分块：显示文本分块的章节归属关系
- 层级结构展示：树状结构显示章节-分块关系
- 分块类型标注：语义分块、表格分块等类型标识

**PDF.js高亮模式** (v2.3新增)：

- 基于PDF.js 3.11的保真渲染（公式、表格、图片完整显示）
- 文本层选择 → 一键高亮（黄/绿/蓝/粉四色）
- 坐标映射服务：PDF位置 ↔ RAG Chunk ID双向映射
- iframe嵌入架构：完整HTML文档通过srcdoc安全加载

**高级PDF解析**：

- **Docling解析器**：IBM开源高保真PDF解析，支持表格结构化提取、公式识别、图表描述
- **MinerU解析器**：高精度VLM后端，支持扫描PDF OCR；解析结果缓存至 `parsed_docs`，供结构视图直接读取，消除二次推断误差
- **多版本兼容**：自动检测 MinerU Python API（UNIPipe）或 CLI（`magic-pdf`）并择优使用
- **解析质量评估**：自动计算文档解析置信度，低质量文档预警

**智能文本分块**：

- **语义分块**（默认）：基于 sentence-transformers 计算句子相似度动态分割，保持语义完整性；最小句子数 4、最小 token 阈值限制过碎分块
- **段落分块**（新增）：按空行直接切割，无需加载 embedding 模型，启动快、适合结构完整的解析结果；自动合并过短段落、拆分超长段落
- **表格专用分块**：双重 embedding 策略（结构hash + 语义文本）
- **坐标映射服务**：`services/renderer/coordinate_mapper.py` - PDF位置 ↔ Chunk ID双向映射
- **运行时热切换**：阅读页「分块模式」Radio（语义/段落）+ 「分块粒度」Radio（细/中/粗），切换后即时生效

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
- **多路召回**：本地 FAISS + 知识图谱(Mock) + ArXiv 兜底（本地结果少于 2 条时触发）
- **精准引用**：回答中标注文献来源和页码，支持参考文献检索；Chat 页下方「当前回答引用来源」可点击跳转 PDF 或打开 ArXiv
- **实时状态反馈**：规划 → 召回 → 评估 → 合成各阶段进度可视化
- **优雅降级**：RAG服务不可用时自动回退到传统搜索

## AI 架构

### Multi-Agent 系统

采用 Router + 专家 Agent 架构，统一 `BaseAgent` 接口：

| Agent                  | 职责            | 说明                                         |
| ---------------------- | --------------- | -------------------------------------------- |
| **Router**       | 意图识别 + 分发 | 关键词检测 + LLM 分类，路由到对应专家 Agent  |
| **Crusher**      | 笔记分类引擎    | 七分类 + 标签 + 摘要 + 学科识别              |
| **Synthesizer**  | 跨文献合成      | 主题发现 + 关联分析 + 重要性排序 + 洞察      |
| **Translator**   | 翻译引擎        | 中英自动检测 + 互译                          |
| **Conversation** | RAG 问答        | 检索知识树 → 提取片段 → LLM 生成带引用回答 |
| **Reviewer（规划/评估）** | 意图与检索规划 | 意图识别、中英关键词提取、多路召回规划、检索质量评估 |
| **Seeker**       | 多路召回执行    | 按规划执行 FAISS / 知识图谱(Mock) / ArXiv 检索 |
| **Synthesizer（对话）** | 回答合成        | 基于高分上下文流式生成，标注 [Doc_Page] / [ArXiv_ID] 引用 |

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
├── main.py              # 入口：组装 UI + 事件绑定 + RAG服务初始化
├── core/
│   ├── config.py        # API、模型、RAG配置
│   ├── utils.py         # PDF 提取、JSON 解析、HTML 转义
│   └── state.py         # ID 生成器、状态工厂
├── models/              # 🆕 v2.1 数据模型
│   ├── parse_result.py  # Docling解析结果模型
│   ├── chunk.py         # 文本块模型
│   └── search.py        # 搜索结果模型
├── agents/
│   ├── base.py          # BaseAgent 协议 + call_llm()
│   ├── crusher.py       # Crusher 笔记分类引擎
│   ├── synthesizer.py   # Synthesizer 跨文献合成引擎
│   ├── router.py        # Router 意图识别 + 分发
│   ├── translator.py    # Translator 中英互译
│   └── conversation.py  # Conversation RAG 问答
├── services/            # 🆕 v2.1 RAG服务
│   ├── rag_service.py   # RAG统一服务入口（含 parsed_docs 缓存 + 热切换分块器）
│   ├── parser/          # 文档解析
│   │   ├── docling_parser.py
│   │   └── mineru_parser.py  # MinerU 多版本兼容解析器
│   ├── chunking/        # 智能分块
│   │   ├── semantic_chunker.py   # 语义分块（embedding相似度）
│   │   ├── paragraph_chunker.py  # 段落分块（空行切割，无需embedding）
│   │   └── table_chunker.py
│   └── search/          # 检索服务
│       ├── faiss_store.py
│       ├── bm25_index.py
│       ├── hybrid_searcher.py
│       └── reranker.py
├── knowledge/
│   ├── tree_model.py    # KnowledgeTree / Node / Edge + 双图谱
│   └── search.py        # 搜索、过滤、层级路径查询
├── ui/
│   ├── styles.py        # CSS 样式（浅色主题）+ Header HTML
│   ├── global_js.py     # 全局 JS（ECharts 初始化 + 浮动弹出菜单 + 通信）
│   ├── renderers.py     # HTML 渲染（分类卡片、知识树、合成结果）
│   └── echarts_graph.py # ECharts 图谱生成
├── tabs/
│   ├── read/            # 阅读 Tab：上传 + 双模式阅读 + 高亮笔记 + RAG索引
│   ├── organize/        # 知识图谱 Tab：Crusher + Synthesizer + RAG检索
│   ├── write/           # 写作 Tab：Markdown 工具栏 + 知识树 + 编辑器
│   └── chat/            # AI 助手 Tab：RAG 对话
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

### 密码保护

默认开启密码认证（用户名 `admin`，密码通过环境变量 `AUTH_PASSWORD` 设置）。

```bash
# 自定义密码
export AUTH_PASSWORD=your_password

# 关闭密码保护
export ENABLE_AUTH=false
```

### 环境变量

| 变量                    | 默认值                           | 说明                                           |
| ----------------------- | -------------------------------- | ---------------------------------------------- |
| `MS_KEY`              | (无)                             | ModelScope API Key（主要 LLM 来源）            |
| `DEEPSEEK_API_KEY`    | (无)                             | DeepSeek 官方 API Key（ModelScope 限额后降级） |
| `DEEPSEEK_API_BASE`   | `https://api.deepseek.com/v1`  | DeepSeek API 端点                              |
| `ENABLE_AUTH`         | `true`                         | 是否开启密码认证                               |
| `AUTH_PASSWORD`       | (无)                             | 登录密码（必须通过环境变量设置）               |
| `PARSER_BACKEND`      | `docling`                      | 解析后端：`docling` 或 `mineru`              |
| `CHUNK_MODE`          | `semantic`                     | 分块模式：`semantic` 或 `paragraph`          |
| `RAG_CHUNK_SIZE`      | `900`                          | 分块最大 token 数                              |
| `RAG_CHUNK_OVERLAP`   | `120`                          | 相邻分块重叠 token 数                          |
| `RAG_SIMILARITY_THRESHOLD` | `0.58`                    | 语义分割相似度阈值（越低=块越大）              |
| `HF_HOME`             | (系统默认)                       | HuggingFace 模型缓存目录                       |

## 技术要点

### RAG混合检索

三路检索 + 两阶段重排序：

1. **语义检索**：FAISS HNSW索引，余弦相似度
2. **关键词检索**：BM25 + jieba分词
3. **元数据过滤**：按文档属性预过滤
4. **RRF融合**：`score = Σ(weight_i / (60 + rank_i))`
5. **Cross-Encoder重排序**：精确计算query-document相关性

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

当你更新解析算法或 RAG 配置时，可以在本地运行离线脚本，重新生成 Demo 所需的静态数据：

```bash
python -m scripts.generate_demo_mock
```

脚本会执行以下步骤：

1. 使用 `demo_data/demo_paper.pdf` 作为输入文档；
2. 调用真实 `RAGService` 与 `handle_upload()`，走完解析 → 分块 → 向量化 → 索引全流程；
3. 将向量索引保存到 `demo_data/faiss_index/`，同时将文献库与笔记状态写入：
   - `demo_data/mock_library.json`
   - `demo_data/mock_notes.json`
4. 将 Markdown 中的图片引用转为 Base64 内联并写入 `mock_library.json`，确保 ModelScope / 本地跨平台 100% 加载图片。

生成完成后，重新启动应用并点击 Demo 按钮，即可在任意环境中获得与真实流程一致的 Demo 体验。RAG 回答中的引用 [1][2] 可点击，通过全局 `jumpToPdf` 跳转阅读页并定位到对应 PDF 页码。