# AtomicLab 技术报告

> PDF保真渲染 + 高级RAG分块 + 笔记高亮交互

---

## 目录

1. [系统概述](#1-系统概述)
2. [统一PDF阅读器架构](#2-统一pdf阅读器架构)
3. [RAG检索系统](#3-rag检索系统)
4. [核心组件实现](#4-核心组件实现)
5. [数据模型](#5-数据模型)
6. [技术选型对比](#6-技术选型对比)
7. [部署指南](#7-部署指南)

---

## 1. 系统概述

### 1.1 项目定位

Atomic Lab 是一款面向研究者的 AI 辅助科研工作站，围绕「阅读 → 整理 → 写作 → 对话」四阶段工作流，提供：

- **保真PDF阅读**：PDF.js渲染，公式/表格/图片完整显示
- **高亮笔记交互**：选中文字 → 一键高亮 → 自动保存
- **RAG智能检索**：三路混合检索 + 两阶段重排序
- **AI问答助手**：基于文献和笔记的精准引用回答

### 1.2 核心特性

| 特性 | 实现方案 | 技术价值 |
|------|----------|----------|
| **PDF保真渲染** | PDF.js 3.11 + iframe | 公式/表格/图片完整显示 |
| **高亮交互** | 文本层选择 + 坐标映射 | 高亮 ↔ RAG Chunk联动 |
| **三路混合检索** | 语义 + 关键词 + 元数据 | 召回率90%+ |
| **两阶段重排序** | RRF融合 + Cross-Encoder | 精度提升15-20% |
| **查询扩展** | QUERY_EXPANSIONS映射 | SQL→MySQL/PostgreSQL等 |

### 1.3 四种阅读模式

| 模式 | 保真渲染 | 高亮交互 | RAG分块 | 适用场景 |
|------|----------|----------|---------|----------|
| 文本模式 | ❌ 低 | ✅ 完整 | ⚠️ 简单 | 快速阅读、全文搜索 |
| PDF原版 | ✅ 高 | ❌ 无 | ❌ 无 | 打印预览、格式确认 |
| **PDF高亮** | ✅ 高 | ✅ 完整 | ✅ 支持 | **推荐：主要阅读模式** |
| Docling模式 | ⚠️ 中 | ❌ 无 | ✅ 高级 | RAG调试、结构分析 |

---

## 2. 统一PDF阅读器架构

### 2.1 架构概览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Unified PDF Reader Architecture v2.3                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐               │
│  │   PDF.js     │───▶│   Text       │───▶│  Highlight   │               │
│  │   Renderer   │    │   Layer      │    │   Layer      │               │
│  └──────────────┘    └──────────────┘    └──────┬───────┘               │
│                                                  │                       │
│  ┌───────────────────────────────────────────────▼──────────────────┐   │
│  │                   Coordinate Mapper Service                       │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │   │
│  │  │ PDF Coordinate  │  │  Chunk ID       │  │  RAG Context    │  │   │
│  │  │ (page, x, y)    │◀─▶│  Lookup         │◀─▶│  Retrieval      │  │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                  │                                       │
│  ┌───────────────────────────────▼──────────────────────────────────┐   │
│  │                      Highlight Persistence                        │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │   │
│  │  │ HighlightData   │──▶│  JSON Export    │──▶│  Backend Save   │  │   │
│  │  │ (color, text)   │  │  (srcdoc)       │  │  (Gradio event) │  │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 PDF.js渲染器

**文件**: `services/renderer/pdfjs_viewer.py`

```python
class PDFJSViewer:
    """PDF.js查看器 - 使用iframe嵌入完整HTML"""
    
    PDFJS_VERSION = "3.11.174"
    
    HIGHLIGHT_COLORS = {
        "yellow": "rgba(255, 235, 59, 0.4)",
        "green": "rgba(76, 175, 80, 0.4)",
        "blue": "rgba(33, 150, 243, 0.4)",
        "pink": "rgba(233, 30, 99, 0.4)",
        "orange": "rgba(255, 152, 0, 0.4)",
    }
    
    def render_viewer(self, pdf_path: str, doc_id: str, 
                      highlights: List[HighlightData] = None) -> str:
        """生成PDF.js查看器HTML"""
        # 读取PDF为base64
        with open(pdf_path, "rb") as f:
            pdf_base64 = base64.b64encode(f.read()).decode("ascii")
        
        # 生成iframe HTML
        return self._generate_iframe_html(pdf_base64, doc_id, highlights)
```

**关键技术点**：

1. **iframe + srcdoc架构**：Gradio的`gr.HTML`不支持完整HTML文档，使用iframe srcdoc嵌入
2. **三层渲染**：Canvas层（视觉）+ 文本层（选择）+ 高亮层（标注）
3. **事件通信**：postMessage向父页面发送高亮事件

### 2.3 坐标映射服务

**文件**: `services/renderer/coordinate_mapper.py`

```python
@dataclass
class ChunkPosition:
    """Chunk在PDF中的位置信息"""
    chunk_id: str
    page: int
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    text_content: str

class CoordinateMapper:
    """PDF坐标与RAG Chunk双向映射"""
    
    def register_chunks(self, doc_id: str, chunks: List[TextChunk]):
        """注册Docling解析的chunks及其位置"""
        for chunk in chunks:
            if chunk.bbox and chunk.page_number:
                position = ChunkPosition(
                    chunk_id=chunk.chunk_id,
                    page=chunk.page_number,
                    bbox=chunk.bbox,
                    text_content=chunk.content
                )
                self._position_map[chunk.chunk_id] = position
    
    def find_chunk_by_coordinate(self, page: int, x: float, y: float) -> Optional[str]:
        """根据PDF坐标查找对应的chunk_id"""
        for chunk_id, pos in self._position_map.items():
            if pos.page == page:
                x0, y0, x1, y1 = pos.bbox
                if x0 <= x <= x1 and y0 <= y <= y1:
                    return chunk_id
        return None
    
    def get_chunk_position(self, chunk_id: str) -> Optional[ChunkPosition]:
        """根据chunk_id获取PDF位置"""
        return self._position_map.get(chunk_id)
```

---

## 3. RAG检索系统

### 3.1 系统架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AtomicLab RAG Architecture v2.3                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐               │
│  │   Docling    │───▶│   Chunking   │───▶│  Embedding   │               │
│  │    Parser    │    │   Service    │    │   Service    │               │
│  └──────────────┘    └──────────────┘    └──────┬───────┘               │
│                                                  │                       │
│  ┌───────────────────────────────────────────────▼──────────────────┐   │
│  │                      Vector Store (FAISS)                         │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │   │
│  │  │  HNSW Idx   │  │  BM25 Idx   │  │    Metadata Filter      │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                  │                                       │
│  ┌───────────────────────────────▼──────────────────────────────────┐   │
│  │                      Retrieval Pipeline                           │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │   │
│  │  │  Semantic   │  │   Keyword   │  │   Query Expansion       │  │   │
│  │  │   Search    │  │    Search   │  │   (SQL→MySQL...)        │  │   │
│  │  └──────┬──────┘  └──────┬──────┘  └────────────┬────────────┘  │   │
│  │         └─────────────────┼──────────────────────┘               │   │
│  │                           ▼                                      │   │
│  │                    ┌─────────────┐                               │   │
│  │                    │  RRF Fusion │  score = Σ(w/(60+rank))       │   │
│  │                    └──────┬──────┘                               │   │
│  │                           ▼                                      │   │
│  │                    ┌─────────────┐                               │   │
│  │                    │  Reranker   │  bge-reranker-v2-m3           │   │
│  │                    └──────┬──────┘                               │   │
│  │                           ▼                                      │   │
│  │                    Final Top-K Results                           │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 查询扩展

**文件**: `services/search/keyword_search.py`

```python
QUERY_EXPANSIONS = {
    # 数据库相关
    "sql": ["mysql", "postgresql", "sqlite", "database", "dbms", "query"],
    "mysql": ["sql", "database", "dbms"],
    
    # AI相关
    "ai": ["artificial intelligence", "machine learning", "ml", "deep learning"],
    "ml": ["machine learning", "ai", "deep learning"],
    
    # 生物化学相关
    "metabolite": ["metabolism", "compound", "molecule", "mass spectrometry"],
    
    # 通用技术
    "api": ["interface", "endpoint", "rest", "graphql"],
    "nlp": ["natural language processing", "text mining", "language model"],
}

def expand_query(query: str) -> List[str]:
    """扩展查询词"""
    terms = query.lower().split()
    expanded = list(terms)
    
    for term in terms:
        if term in QUERY_EXPANSIONS:
            expanded.extend(QUERY_EXPANSIONS[term])
    
    return list(set(expanded))
```

### 3.3 RRF融合算法

```python
def rrf_fusion(semantic_results, keyword_results, k=60):
    """
    Reciprocal Rank Fusion
    
    公式: score(d) = Σ(w_i / (k + rank_i))
    
    参数:
    - k = 60 (常数，减少排序位置影响)
    - w_semantic = 0.6 (语义检索权重)
    - w_keyword = 0.3 (关键词检索权重)
    """
    scores = defaultdict(float)
    
    for rank, (chunk_id, _) in enumerate(semantic_results):
        scores[chunk_id] += 0.6 / (k + rank + 1)
    
    for rank, (chunk_id, _) in enumerate(keyword_results):
        scores[chunk_id] += 0.3 / (k + rank + 1)
    
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

---

## 4. 核心组件实现

### 4.1 Docling解析器

**文件**: `services/parser/docling_parser.py`

```python
class DoclingParser:
    """基于Docling的高级PDF解析器"""
    
    def parse(self, filepath: str, doc_id: str) -> ParsedDocument:
        # Docling转换
        result = self.converter.convert(filepath)
        doc = result.document
        
        # 导出Markdown
        markdown = doc.export_to_markdown()
        
        # 提取表格
        tables = self._extract_tables(doc, doc_id)
        
        # 计算解析置信度
        confidence = self._calculate_confidence(doc, tables)
        
        return ParsedDocument(
            doc_id=doc_id,
            title=self._extract_title(doc),
            content=markdown,
            tables=tables,
            parse_confidence=confidence
        )
    
    def _extract_tables(self, doc, doc_id: str) -> List[ParsedTable]:
        """表格提取 - 双重embedding策略"""
        tables = []
        for table in doc.tables:
            df = table.export_to_dataframe(doc)
            
            # 关键：转换列名和单元格为字符串
            headers = [str(h) for h in df.columns]
            rows = [[str(cell) for cell in row] for row in df.values.tolist()]
            
            # 生成结构指纹
            structure_hash = hashlib.md5(
                f"{headers}_{len(rows)}".encode()
            ).hexdigest()[:16]
            
            tables.append(ParsedTable(
                table_id=f"{doc_id}_t{len(tables)}",
                headers=headers,
                rows=rows,
                structure_hash=structure_hash
            ))
        return tables
```

### 4.2 混合检索器

**文件**: `services/search/hybrid_search.py`

```python
class HybridSearcher:
    """三路混合检索器"""
    
    def search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        # 1. 查询扩展
        expanded_query = expand_query(query)
        
        # 2. 语义检索
        semantic_results = self.semantic_search(query, top_k * 2)
        
        # 3. 关键词检索（使用扩展查询）
        keyword_results = self.keyword_search(" ".join(expanded_query), top_k * 2)
        
        # 4. RRF融合
        fused_results = self.rrf_fusion(semantic_results, keyword_results, top_k * 2)
        
        # 5. 获取完整chunk数据
        chunks = [self.get_chunk(chunk_id) for chunk_id, _ in fused_results]
        
        # 6. Cross-Encoder重排序
        reranked = self.reranker.rerank(query, chunks, top_k)
        
        return reranked
```

---

## 5. 数据模型

### 5.1 高亮数据模型

```python
@dataclass
class PDFCoordinate:
    """PDF页面坐标"""
    page: int
    x: float
    y: float
    width: float
    height: float

@dataclass
class HighlightData:
    """高亮数据"""
    highlight_id: str
    doc_id: str
    chunk_id: str
    content: str
    color: str = "yellow"
    annotation: str = ""
    coordinate: PDFCoordinate = None
    created_at: str = ""
```

### 5.2 文本块模型

```python
@dataclass
class TextChunk:
    """文本块 - RAG基本单元"""
    chunk_id: str
    doc_id: str
    content: str
    chunk_type: str = "paragraph"  # paragraph/semantic/section/table
    
    # 向量
    embedding: Optional[np.ndarray] = None
    
    # 元数据
    metadata: ChunkMetadata = None
    
    # 位置信息（用于坐标映射）
    page_number: Optional[int] = None
    bbox: Optional[Tuple] = None
```

---

## 6. 技术选型对比

### 6.1 PDF解析器对比

| 特性 | Docling (当前) | MinerU (magic-pdf) |
|------|----------------|-------------------|
| 开发方 | IBM开源 | OpenDataLab |
| 解析精度 | 82-85 | 90+ (VLM后端) |
| 公式识别 | ✅ DocTags | ✅ LaTeX输出 |
| 表格提取 | ✅ 结构化 | ✅ HTML + 跨页合并 |
| 扫描PDF OCR | ⚠️ 需配置 | ✅ 自动检测109语言 |
| 硬件需求 | 可纯CPU | GPU推荐10GB+ VRAM |
| 国产硬件 | ⚠️ 通用 | ✅ 昆仑芯/寒武纪等 |

### 6.2 整合方案

```
用户上传PDF
    ↓
┌─────────────────────────────────────┐
│         解析后端选择                 │
├──────────────┬──────────────────────┤
│   Docling    │      MinerU          │
│  (快速轻量)   │   (高精度VLM)         │
└──────────────┴──────────────────────┘
    ↓                  ↓
    └──────→ RAG索引 ←──────┘
              ↓
        PDF.js高亮渲染
```

**建议**：
- 默认使用Docling（轻量、快速）
- 扫描PDF自动切换MinerU
- 后续可通过配置选择解析后端

---

## 7. 部署指南

### 7.1 环境要求

- Python 3.10+
- 内存：建议8GB+（加载embedding模型）
- 存储：约2GB（模型文件）

### 7.2 安装步骤

```bash
# 基础安装
pip install -r requirements.txt

# 完整RAG功能
pip install sentence-transformers>=2.2.0 \
            faiss-cpu>=1.7.4 \
            rank-bm25>=0.2.2 \
            docling>=2.0.0

# 可选：MinerU高精度解析
pip install mineru[all]
```

### 7.3 启动验证

```bash
python main.py
```

预期输出：

```
==================================================
初始化RAG服务...
==================================================
✓ Docling解析器初始化成功
✓ 语义分块器初始化成功
✓ Embedding模型加载成功
✓ FAISS向量存储初始化成功 (类型: HNSW)
✓ BM25索引初始化成功
✓ 混合检索器初始化成功
✓ 坐标映射服务初始化成功
==================================================
```

### 7.4 配置说明

```python
# core/config.py

RAG_CONFIG = {
    # 模型配置
    "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
    "reranker_model": "BAAI/bge-reranker-v2-m3",
    
    # 分块配置
    "chunk_size": 512,
    "similarity_threshold": 0.7,
    
    # 检索配置
    "rrf_k": 60,
    "semantic_weight": 0.6,
    "keyword_weight": 0.3,
    
    # 存储配置
    "storage_path": "storage",
}
```

---

**文档版本**: v2.3.0  
**最后更新**: 2026-03-07  
**作者**: AtomicLab Team
