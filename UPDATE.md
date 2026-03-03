# AtomicLab — 原子化科研工作站

> 基于图+树数据结构的文献管理与智能写作系统

---

## 目录

1. [项目简介](#1-项目简介)
2. [核心理念](#2-核心理念)
3. [系统建模](#3-系统建模)
4. [技术选型](#4-技术选型)
5. [文件结构](#5-文件结构)
6. [接口规范](#6-接口规范)
7. [实现状态](#7-实现状态)
8. [快速启动](#8-快速启动)
9. [开发路线图](#9-开发路线图)

---

## 1. 项目简介

AtomicLab 是一款专注于「读写闭环」的科研工作站。系统将文献建模为**图+树**混合数据结构：

- **图结构**：管理文献之间的引用关系、相似度关系
- **树结构**：管理单篇文献内部的章节层次、批注、图表

通过三段式工作流 **Read → Organize → Write**，帮助科研人员完成从阅读到写作的全流程。

---

## 2. 核心理念

### 2.1 设计哲学

| 理念 | 说明 |
|------|------|
| **读写闭环** | 阅读中的批注自动成为写作的参考素材 |
| **章节块为核心** | 以章节块（而非原子知识）作为最小内容单元 |
| **批注即子节点** | 用户批注作为章节块的子节点，统一管理 |
| **轻量优先** | 数据量 <100 条，追求简洁实现 |

### 2.2 工作流概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        AtomicLab 工作流                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   📖 READ          🧬 ORGANIZE         ✍️ WRITE                 │
│   ┌─────────┐      ┌─────────┐        ┌─────────┐              │
│   │ PDF阅读 │ ───► │ 智能解构 │ ────► │ 参考写作 │              │
│   │ 章节批注 │      │ 结构提取 │        │ 搜索匹配 │              │
│   └─────────┘      └─────────┘        └─────────┘              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 系统建模

### 3.1 数据结构总览

```
                    ┌────────────────────────────────────┐
                    │         KnowledgeGraph             │
                    │      (文献间关系 - 图结构)           │
                    └────────────────────────────────────┘
                                    │
                                    │ contains
                                    ▼
         ┌──────────────────────────────────────────────────────┐
         │                    DocumentNode                       │
         │              (文献根节点 - 树的根)                      │
         │  id: "doc001"                                         │
         │  title: "论文标题"                                     │
         │  keywords: ["关键词1", "关键词2"]                       │
         │  abstract: "摘要内容..."                               │
         │  filepath: "/path/to/file.pdf"                        │
         └──────────────────────────────────────────────────────┘
                                    │
                                    │ children
                                    ▼
         ┌──────────────────────────────────────────────────────┐
         │                     TreeNode                          │
         │              (章节块/批注 - 统一模型)                   │
         │  type: "section" | "annotation" | "figure" | "table"  │
         └──────────────────────────────────────────────────────┘
```

### 3.2 文献图结构 (KnowledgeGraph)

管理多篇文献之间的关系。

```python
@dataclass
class KnowledgeGraph:
    """文献知识图谱"""
    documents: Dict[str, DocumentNode]  # doc_id -> DocumentNode
    edges: List[Edge]                   # 文献间关系

@dataclass
class Edge:
    """文献间边"""
    source_id: str          # 源文献 ID
    target_id: str          # 目标文献 ID
    relation: str           # 关系类型: "cites" | "similar" | "extends"
    weight: float = 1.0     # 关系权重 (0-1)
```

**边类型说明**：

| 类型 | 含义 | 示例场景 |
|------|------|----------|
| `cites` | 引用关系 | A 文献引用了 B 文献 |
| `similar` | 相似关系 | 基于语义相似度计算 |
| `extends` | 扩展关系 | A 是 B 的后续研究 |

### 3.3 文献树结构 (DocumentNode + TreeNode)

单篇文献内部采用树结构组织。

```python
@dataclass
class DocumentNode:
    """文献根节点"""
    id: str                     # 唯一标识: "doc001"
    title: str                  # 文献标题
    keywords: List[str]         # 关键词列表
    abstract: str               # 摘要
    filepath: str               # 文件路径
    filetype: str               # 文件类型: "pdf" | "txt" | "md"
    created_at: datetime        # 创建时间
    children_ids: List[str]     # 顶级章节 ID 列表

@dataclass
class TreeNode:
    """
    树节点 - 统一模型
    
    通过 type 字段区分不同类型的节点：
    - section: 章节块
    - annotation: 用户批注
    - figure: 图片
    - table: 表格
    """
    id: str                     # 唯一标识: "doc001_n001"
    doc_id: str                 # 所属文献 ID
    parent_id: Optional[str]    # 父节点 ID (顶级节点为 None)
    children_ids: List[str]     # 子节点 ID 列表
    type: str                   # 节点类型
    
    # 通用字段
    content: str                # 主要内容
    created_at: datetime        # 创建时间
    
    # section 专用字段
    heading: Optional[str]      # 章节标题: "2.1 研究方法"
    level: Optional[int]        # 层级: 1=H1, 2=H2, 3=H3
    page_start: Optional[int]   # 起始页码
    page_end: Optional[int]     # 结束页码
    
    # annotation 专用字段
    selected_text: Optional[str]    # 选中的原文
    note: Optional[str]             # 用户批注内容
    priority: Optional[int]         # 重要性 (1-5)
    color: Optional[str]            # 高亮颜色 (代表重要程度)
    
    # figure/table 专用字段
    caption: Optional[str]          # 图表标题
    ref_id: Optional[str]           # 引用编号: "Fig.1" | "Table.2"
```

### 3.4 树结构示例

```
doc001 (DocumentNode: "深度学习综述")
│
├── doc001_n001 (section: "1. Introduction", level=1)
│   ├── doc001_n002 (section: "1.1 Background", level=2)
│   │   └── doc001_a001 (annotation: 用户批注, priority=5, color="#FF6B6B")
│   └── doc001_n003 (section: "1.2 Motivation", level=2)
│
├── doc001_n004 (section: "2. Methods", level=1)
│   ├── doc001_n005 (section: "2.1 Model Architecture", level=2)
│   │   ├── doc001_f001 (figure: "Fig.1 模型架构图")
│   │   └── doc001_a002 (annotation: 用户批注, priority=3, color="#FFE66D")
│   └── doc001_n006 (section: "2.2 Training", level=2)
│       └── doc001_t001 (table: "Table.1 超参数配置")
│
└── doc001_n007 (section: "3. Experiments", level=1)
```

### 3.5 批注颜色与重要性映射

| Priority | 颜色 | 色值 | 含义 |
|----------|------|------|------|
| 5 | 🔴 红色 | `#FF6B6B` | 核心观点 |
| 4 | 🟠 橙色 | `#FFA500` | 重要内容 |
| 3 | 🟡 黄色 | `#FFE66D` | 值得注意 |
| 2 | 🟢 绿色 | `#4ECDC4` | 参考信息 |
| 1 | 🔵 蓝色 | `#45B7D1` | 一般记录 |

---

## 4. 技术选型

### 4.1 当前技术栈

| 层级 | 技术 | 版本 | 用途 |
|------|------|------|------|
| **Runtime** | Python | 3.10+ | 主运行时 |
| **UI Framework** | Gradio | 4.44+ | Web 界面 |
| **LLM** | Qwen2.5-72B-Instruct | - | 智能解构 (ModelScope API) |
| **PDF 解析** | PyPDF2 | 3.0+ | PDF 文本提取 |
| **分词** | jieba | 0.42+ | 中文分词 (关键词搜索) |

### 4.2 搜索技术方案

#### 关键词搜索 (已规划)

```
┌─────────────────────────────────────────────────────────────┐
│                    关键词搜索流程                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  输入Query ──► jieba分词 ──► 遍历节点 ──► 字段加权匹配 ──► 排序  │
│                                                              │
│  字段权重:                                                    │
│    title    : 10  (文献标题)                                  │
│    keywords : 8   (关键词)                                    │
│    heading  : 6   (章节标题)                                  │
│    abstract : 4   (摘要)                                      │
│    note     : 3   (批注内容)                                  │
│    content  : 1   (正文)                                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**实现方案** (MVP - 简单遍历)：
- 数据量 <100，直接遍历所有节点
- 使用 jieba 分词处理中文
- 按字段权重累加分数
- 返回 Top-K 结果

#### 语义搜索 (已规划)

```
┌─────────────────────────────────────────────────────────────┐
│                    语义搜索流程                               │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  输入Query ──► Embedding模型 ──► 向量相似度 ──► Top-K结果     │
│                        │                                     │
│                        ▼                                     │
│  预处理: 所有节点内容 ──► Embedding ──► 向量存储              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Embedding 模型选择**：

| 模型 | 来源 | 维度 | 特点 |
|------|------|------|------|
| `BGE-M3` | HuggingFace | 1024 | 多语言、高质量、开源 |
| `text-embedding-3-small` | OpenAI | 1536 | 商业 API、简单接入 |
| `GTE-Qwen2` | 阿里云 | 768 | 中文优化 |

**向量存储**（数据量 <100，内存存储即可）：
- NumPy 数组 + 余弦相似度计算
- 或使用 FAISS (IndexFlatIP) 简化实现

### 4.3 未来扩展技术栈

| 技术 | 用途 | 引入时机 |
|------|------|----------|
| **FAISS** | 向量索引 | 语义搜索实现时 |
| **sentence-transformers** | Embedding 生成 | 语义搜索实现时 |
| **NetworkX** | 图结构操作 | 文献关系可视化时 |
| **pdfplumber** | PDF 结构解析 | 章节自动提取时 |

---

## 5. 文件结构

```
AtomicLab/
│
├── app.py                      # 🚀 主入口 - 委托给 main.py
├── main.py                     # 🚀 实际入口 - UI 组装与事件绑定
├── requirements.txt            # 📦 依赖清单
├── README.md                   # 📖 项目文档
├── UPDATE.md                   # 📖 v2.0 更新说明
│
├── core/                       # 🧱 核心模块
│   ├── __init__.py
│   ├── config.py              # ⚙️ 配置常量、API 设置
│   ├── state.py               # 状态管理、ID 生成器
│   └── utils.py               # 通用工具函数（PDF提取、JSON解析）
│
├── models/                     # 📊 数据模型（v2.0 新增）
│   ├── __init__.py
│   ├── document.py            # DocumentNode 文献节点
│   ├── tree_node.py           # TreeNode 统一树节点（section/annotation/figure/table）
│   ├── edge.py                # Edge 关系边
│   └── graph.py               # KnowledgeGraph 知识图谱
│
├── agents/                     # 🤖 AI Agent
│   ├── __init__.py
│   ├── base.py                # Agent 基类 + LLM 调用封装
│   ├── crusher.py             # Crusher 解构 Agent（笔记分析）
│   ├── synthesizer.py         # Synthesizer 合成 Agent（跨文献分析）
│   ├── translator.py          # Translator 翻译 Agent
│   ├── conversation.py        # Conversation Agent（RAG问答）
│   └── router.py              # Router Agent（意图路由）
│
├── knowledge/                  # 📚 知识管理
│   ├── __init__.py
│   ├── tree_model.py          # KnowledgeTree 知识树（原有）
│   └── search.py              # 基础搜索功能
│
├── services/                   # 🔧 业务服务（v2.0 新增）
│   ├── __init__.py
│   └── search/                # 搜索服务
│       ├── __init__.py
│       ├── keyword_search.py  # 关键词搜索（jieba分词+字段加权）
│       ├── semantic_search.py # 语义搜索（Embedding+余弦相似度）
│       ├── hybrid_search.py   # 混合搜索（RRF融合）
│       └── search_result.py   # SearchResult 统一结果类
│
├── tabs/                       # 📑 Tab UI 模块
│   ├── __init__.py
│   ├── read/                  # 📖 阅读模块（v2.0 批注功能重写）
│   │   └── __init__.py        # 上传、阅读、高亮批注
│   ├── organize/              # 🧬 整理模块
│   │   └── __init__.py        # 智能解构、知识图谱
│   ├── write/                 # ✍️ 写作模块（v2.0 搜索增强）
│   │   └── __init__.py        # 搜索、写作、AI续写
│   └── chat/                  # 💬 AI助手模块
│       └── __init__.py        # RAG问答
│
└── ui/                         # 🎨 UI 组件
    ├── __init__.py
    ├── styles.py              # CSS 样式
    ├── renderers.py           # HTML 渲染函数（v2.0 批注渲染）
    ├── echarts_graph.py       # ECharts 图表生成
    └── global_js.py           # 全局 JavaScript
```

---

## 6. 接口规范

### 6.1 数据模型接口

#### DocumentNode

```python
class DocumentNode:
    """文献节点"""
    
    @classmethod
    def create(cls, filepath: str) -> "DocumentNode":
        """从文件创建文献节点"""
        pass
    
    def add_child(self, node: "TreeNode") -> None:
        """添加子节点"""
        pass
    
    def get_all_nodes(self) -> List["TreeNode"]:
        """获取所有子节点（深度优先遍历）"""
        pass
    
    def to_dict(self) -> Dict:
        """序列化为字典"""
        pass
    
    @classmethod
    def from_dict(cls, data: Dict) -> "DocumentNode":
        """从字典反序列化"""
        pass
```

#### TreeNode

```python
class TreeNode:
    """树节点"""
    
    @classmethod
    def create_section(cls, doc_id: str, heading: str, level: int, 
                       content: str, parent_id: Optional[str] = None) -> "TreeNode":
        """创建章节节点"""
        pass
    
    @classmethod
    def create_annotation(cls, doc_id: str, parent_id: str,
                          selected_text: str, note: str, 
                          priority: int = 3) -> "TreeNode":
        """创建批注节点"""
        pass
    
    @classmethod
    def create_figure(cls, doc_id: str, parent_id: str,
                      caption: str, ref_id: str) -> "TreeNode":
        """创建图片节点"""
        pass
    
    @classmethod
    def create_table(cls, doc_id: str, parent_id: str,
                     caption: str, ref_id: str, content: str) -> "TreeNode":
        """创建表格节点"""
        pass
    
    def add_child(self, node: "TreeNode") -> None:
        """添加子节点"""
        pass
    
    def get_searchable_text(self) -> str:
        """获取可搜索文本（用于检索）"""
        pass
    
    def to_dict(self) -> Dict:
        """序列化"""
        pass
```

#### KnowledgeGraph

```python
class KnowledgeGraph:
    """知识图谱"""
    
    def add_document(self, doc: DocumentNode) -> None:
        """添加文献"""
        pass
    
    def remove_document(self, doc_id: str) -> None:
        """移除文献"""
        pass
    
    def add_edge(self, source_id: str, target_id: str, 
                 relation: str, weight: float = 1.0) -> None:
        """添加边（文献关系）"""
        pass
    
    def get_related_documents(self, doc_id: str, 
                              relation: Optional[str] = None) -> List[DocumentNode]:
        """获取相关文献"""
        pass
    
    def get_all_nodes(self) -> List[TreeNode]:
        """获取所有树节点（用于搜索）"""
        pass
```

### 6.2 搜索服务接口

#### KeywordSearchService

```python
class KeywordSearchService:
    """关键词搜索服务"""
    
    # 字段权重配置
    FIELD_WEIGHTS = {
        "title": 10,
        "keywords": 8,
        "heading": 6,
        "abstract": 4,
        "note": 3,
        "content": 1,
    }
    
    def __init__(self, graph: KnowledgeGraph):
        """初始化，传入知识图谱"""
        pass
    
    def search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """
        关键词搜索
        
        Args:
            query: 搜索词
            top_k: 返回结果数量
            
        Returns:
            SearchResult 列表，按相关度排序
        """
        pass
    
    def _tokenize(self, text: str) -> List[str]:
        """分词（使用 jieba）"""
        pass
    
    def _calculate_score(self, node: TreeNode, tokens: List[str]) -> float:
        """计算节点匹配分数"""
        pass
```

#### SemanticSearchService

```python
class SemanticSearchService:
    """语义搜索服务"""
    
    def __init__(self, graph: KnowledgeGraph, model_name: str = "BAAI/bge-m3"):
        """
        初始化
        
        Args:
            graph: 知识图谱
            model_name: Embedding 模型名称
        """
        pass
    
    def build_index(self) -> None:
        """构建向量索引（对所有节点进行 embedding）"""
        pass
    
    def search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """
        语义搜索
        
        Args:
            query: 搜索词
            top_k: 返回结果数量
            
        Returns:
            SearchResult 列表，按相似度排序
        """
        pass
    
    def _embed(self, text: str) -> np.ndarray:
        """文本向量化"""
        pass
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算余弦相似度"""
        pass
```

#### HybridSearchService (可选扩展)

```python
class HybridSearchService:
    """混合搜索服务 - RRF 融合"""
    
    def __init__(self, keyword_service: KeywordSearchService,
                 semantic_service: SemanticSearchService):
        pass
    
    def search(self, query: str, top_k: int = 10, 
               keyword_weight: float = 0.5) -> List[SearchResult]:
        """
        混合搜索 - 使用 RRF (Reciprocal Rank Fusion) 融合结果
        
        Args:
            query: 搜索词
            top_k: 返回结果数量
            keyword_weight: 关键词搜索权重 (0-1)
            
        Returns:
            融合后的 SearchResult 列表
        """
        pass
    
    def _rrf_fusion(self, keyword_results: List, semantic_results: List,
                    k: int = 60) -> List[SearchResult]:
        """RRF 融合算法"""
        pass
```

#### SearchResult

```python
@dataclass
class SearchResult:
    """搜索结果"""
    node: TreeNode              # 匹配的节点
    doc: DocumentNode           # 所属文献
    score: float                # 相关度/相似度分数
    match_type: str             # 匹配类型: "keyword" | "semantic" | "hybrid"
    matched_field: Optional[str]  # 匹配字段 (关键词搜索时)
    highlight: Optional[str]    # 高亮片段
```

### 6.3 功能模块接口

#### READ 模块

```python
# features/read/handlers.py

def handle_upload(files, lib_st, stats_st) -> Tuple:
    """
    处理文件上传
    
    Args:
        files: 上传的文件列表
        lib_st: 文献库状态
        stats_st: 统计状态
        
    Returns:
        (更新后的lib_st, stats_st, pdf_selector_choices, stats_html, text_html)
    """
    pass

def handle_select_pdf(selected: str, lib_st: Dict) -> str:
    """
    处理文献选择
    
    Returns:
        文献文本 HTML
    """
    pass

def handle_save_note(page: int, content: str, notes_st: List, 
                     current_pdf: str) -> Tuple:
    """
    保存笔记
    
    Returns:
        (更新后的notes_st, notes_html)
    """
    pass

def handle_save_annotation(doc_id: str, section_id: str, 
                           selected_text: str, note: str,
                           priority: int) -> TreeNode:
    """
    保存批注到章节 [待实现]
    
    Returns:
        创建的 annotation TreeNode
    """
    pass
```

#### ORGANIZE 模块

```python
# features/organize/handlers.py

def refresh_and_generate(extra_notes, notes_st, current_pdf, 
                         lib_st, stats_st) -> Tuple:
    """
    智能解构 - 将笔记转化为结构化知识
    
    Returns:
        (atom_cards_html, lib_st, stats_st, stats_html, 
         agent_status, notes_overview, ref_cards_html)
    """
    pass

def extract_document_structure(doc: DocumentNode) -> List[TreeNode]:
    """
    提取文档结构 - 自动识别章节 [待实现]
    
    Returns:
        章节 TreeNode 列表
    """
    pass
```

#### WRITE 模块

```python
# features/write/handlers.py

def handle_download(text: str) -> Optional[str]:
    """
    下载草稿为 Markdown 文件
    
    Returns:
        临时文件路径
    """
    pass

def handle_search(query: str, search_type: str, graph: KnowledgeGraph,
                  top_k: int = 10) -> List[SearchResult]:
    """
    搜索文献内容 [待实现]
    
    Args:
        query: 搜索词
        search_type: "keyword" | "semantic" | "hybrid"
        graph: 知识图谱
        top_k: 结果数量
        
    Returns:
        SearchResult 列表
    """
    pass

def render_search_results(results: List[SearchResult]) -> str:
    """
    渲染搜索结果 [待实现]
    
    Returns:
        HTML 字符串
    """
    pass
```

---

## 7. 实现状态

### 7.1 已实现 ✅

| 模块 | 功能 | 状态 |
|------|------|------|
| **core/config.py** | API 配置、模型设置 | ✅ 完成 |
| **core/state.py** | ID 生成器、状态管理 | ✅ 完成 |
| **core/utils.py** | 工具函数（PDF提取、JSON解析） | ✅ 完成 |
| **models/** | 数据模型（DocumentNode, TreeNode, Edge, KnowledgeGraph） | ✅ v2.0 完成 |
| **agents/base.py** | Agent 基类 + LLM 调用封装 | ✅ 完成 |
| **agents/crusher.py** | Crusher 解构 Agent | ✅ 完成 |
| **agents/synthesizer.py** | Synthesizer 合成 Agent | ✅ 完成 |
| **agents/translator.py** | Translator 翻译 Agent | ✅ 完成 |
| **agents/conversation.py** | Conversation RAG Agent | ✅ 完成 |
| **agents/router.py** | Router 意图路由 Agent | ✅ 完成 |
| **knowledge/tree_model.py** | KnowledgeTree 知识树 | ✅ 完成 |
| **knowledge/search.py** | 基础搜索 | ✅ 完成 |
| **services/search/** | 搜索服务（关键词/语义/混合） | ✅ v2.0 完成 |
| **tabs/read/** | PDF 上传、文本提取、批注功能 | ✅ v2.0 重写 |
| **tabs/organize/** | 智能解构、知识图谱 | ✅ 完成 |
| **tabs/write/** | 写作、搜索、AI续写 | ✅ v2.0 增强 |
| **tabs/chat/** | AI 助手 RAG 问答 | ✅ 完成 |
| **ui/** | 样式、渲染、全局JS | ✅ 完成 |
| **main.py** | 主入口、事件绑定 | ✅ 完成 |

### 7.2 待实现 🚧

| 模块 | 功能 | 优先级 | 说明 |
|------|------|--------|------|
| **services/parser/** | PDF 结构解析 | 🟡 中 | 自动识别章节层级 |
| **services/graph/** | 文献关系管理 | 🟢 低 | 引用关系、相似度计算 |
| **语义搜索** | Embedding 向量化 | 🟡 中 | 需要安装 sentence-transformers |

### 7.3 v2.0 更新说明

**新增功能：**

1. **数据模型重构** (`models/`)
   - `DocumentNode`: 文献根节点，包含元信息
   - `TreeNode`: 统一树节点，支持 section/annotation/figure/table
   - `Edge`: 文献间关系边
   - `KnowledgeGraph`: 知识图谱管理

2. **搜索服务** (`services/search/`)
   - `KeywordSearchService`: jieba 分词 + 字段加权搜索
   - `SemanticSearchService`: Embedding 向量化语义搜索
   - `HybridSearchService`: RRF 融合混合搜索
   - `SearchResult`: 统一搜索结果类

3. **批注功能重写** (`tabs/read/`)
   - 支持 annotation TreeNode 创建
   - 支持 priority (1-5) 重要性级别
   - 颜色与重要性自动映射
   - 批注作为文档子节点存储

4. **写作搜索增强** (`tabs/write/`)
   - 支持关键词/语义/混合三种搜索模式
   - 搜索结果渲染增强，显示匹配类型

**兼容性：**
- 保持与原有 `KnowledgeTree` 的兼容
- 新旧模型可并行使用
- 搜索服务自动降级到旧版实现

---

## 8. 快速启动

### 8.1 环境要求

- Python 3.10+
- 网络连接（调用 ModelScope API）

### 8.2 安装步骤

```bash
# 1. 克隆项目
git clone <repo-url>
cd AtomicLab-main

# 2. 创建虚拟环境 (可选)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
.\venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量 (可选)
# 创建 .env 文件
DASHSCOPE_API_KEY=your_api_key_here

# 5. 启动应用
python app.py
```

### 8.3 访问应用

浏览器打开: `http://127.0.0.1:7860`

### 8.4 依赖清单

```txt
# requirements.txt
gradio>=4.44.0
openai>=1.30.0
PyPDF2>=3.0.0
python-dotenv>=1.0.0

# v2.0 搜索功能依赖
jieba>=0.42.0
numpy>=1.24.0

# 语义搜索（可选 - 如需语义搜索功能）
# sentence-transformers>=2.2.0
```

---

## 9. 开发路线图

### v1.0 (原有)
- [x] 三段式工作流 (Read → Organize → Write)
- [x] PDF 上传与文本提取
- [x] 笔记记录与管理
- [x] Crusher Agent 智能解构
- [x] Markdown 导出

### v2.0 (当前版本) ✅
- [x] 图+树数据结构重构（DocumentNode, TreeNode, Edge, KnowledgeGraph）
- [x] 关键词搜索（jieba 分词 + 字段加权）
- [x] 语义搜索接口（需安装 sentence-transformers）
- [x] 混合搜索（RRF 融合）
- [x] 章节批注功能重写（支持 annotation 节点）
- [x] 批注颜色/重要性系统（priority 1-5）

### v3.0 (规划中)
- [ ] PDF 章节自动识别
- [ ] 文献关系图谱
- [ ] 知识图谱可视化增强
- [ ] AI 辅助写作增强

---

## 许可证

MIT License

---

## 联系方式

如有问题或建议，请提交 Issue。
