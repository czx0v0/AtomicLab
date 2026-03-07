"""
Chunk Models
============
RAG文本分块数据模型
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
import numpy as np

from .parse_result import ParsedTable


ChunkType = Literal[
    "paragraph",  # 段落分块
    "semantic",  # 语义分块
    "section",  # 章节分块
    "table_semantic",  # 表格语义描述
    "table_row",  # 表格行
    "figure",  # 图片描述
    "formula",  # 公式
]


@dataclass
class ChunkMetadata:
    """块元数据 - 用于过滤和排序"""

    doc_title: str = ""
    doc_type: str = "pdf"  # pdf/docx/md/txt
    author: Optional[str] = None
    created_date: Optional[str] = None
    chunk_index: int = 0  # 在文档中的顺序
    total_chunks: int = 0
    token_count: int = 0

    # 语义标签
    keywords: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)  # 命名实体

    # 章节信息（新增）
    section_name: str = ""  # 章节名称，如 "References", "Introduction"

    # 溯源信息
    source_section: Optional[str] = None
    page_number: Optional[int] = None
    parent_table: Optional[str] = None  # 对于table_row类型

    # 用于混合检索的评分
    bm25_score: Optional[float] = None
    semantic_score: Optional[float] = None

    # 额外元数据
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "doc_title": self.doc_title,
            "doc_type": self.doc_type,
            "author": self.author,
            "created_date": self.created_date,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "token_count": self.token_count,
            "keywords": self.keywords,
            "entities": self.entities,
            "section_name": self.section_name,
            "source_section": self.source_section,
            "page_number": self.page_number,
            "parent_table": self.parent_table,
            "bm25_score": self.bm25_score,
            "semantic_score": self.semantic_score,
        }


@dataclass
class TextChunk:
    """文本块 - RAG基本单元"""

    chunk_id: str
    doc_id: str
    content: str  # 原始文本
    chunk_type: ChunkType = "paragraph"

    # 向量相关
    embedding: Optional[np.ndarray] = None
    embedding_model: str = ""

    # 元数据
    metadata: ChunkMetadata = field(default_factory=ChunkMetadata)

    # 溯源信息
    source_section_id: Optional[str] = None
    page_number: Optional[int] = None
    bbox: Optional[tuple] = None

    # 用于表格的特殊字段
    table_data: Optional[ParsedTable] = None

    # 质量评分
    quality_score: float = 1.0  # 基于解析置信度

    # 语义连贯性评分(仅语义分块)
    semantic_coherence: Optional[float] = None

    # 创建时间
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """确保embedding是numpy数组"""
        if self.embedding is not None and not isinstance(self.embedding, np.ndarray):
            self.embedding = np.array(self.embedding)

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "content": self.content,
            "chunk_type": self.chunk_type,
            "embedding_model": self.embedding_model,
            "metadata": self.metadata.to_dict(),
            "source_section_id": self.source_section_id,
            "page_number": self.page_number,
            "quality_score": self.quality_score,
            "semantic_coherence": self.semantic_coherence,
            "created_at": self.created_at.isoformat(),
        }

    def get_searchable_text(self) -> str:
        """获取可搜索文本（包含章节名称以便可以被检索到）"""
        parts = [self.content]
        if self.metadata.keywords:
            parts.extend(self.metadata.keywords)
        if self.metadata.source_section:
            parts.append(self.metadata.source_section)
        # 添加章节名称到搜索文本
        if self.metadata.section_name:
            parts.append(self.metadata.section_name)
        return " ".join(parts)

    def get_display_text(self, max_length: int = 200) -> str:
        """获取显示文本"""
        text = self.content.replace("\n", " ")
        if len(text) > max_length:
            text = text[:max_length] + "..."
        return text

    def set_embedding(self, embedding: np.ndarray, model_name: str):
        """设置embedding"""
        self.embedding = embedding
        self.embedding_model = model_name

    def get_embedding_dimension(self) -> int:
        """获取embedding维度"""
        if self.embedding is not None:
            return len(self.embedding)
        return 0


@dataclass
class ChunkCollection:
    """文本块集合 - 管理一个文档的所有chunks"""

    doc_id: str
    chunks: List[TextChunk] = field(default_factory=list)

    def add_chunk(self, chunk: TextChunk):
        """添加chunk"""
        self.chunks.append(chunk)

    def get_chunks_by_type(self, chunk_type: ChunkType) -> List[TextChunk]:
        """按类型获取chunks"""
        return [c for c in self.chunks if c.chunk_type == chunk_type]

    def get_chunk_by_id(self, chunk_id: str) -> Optional[TextChunk]:
        """根据ID获取chunk"""
        for chunk in self.chunks:
            if chunk.chunk_id == chunk_id:
                return chunk
        return None

    def get_table_chunks(self) -> List[TextChunk]:
        """获取所有表格相关chunks"""
        return [
            c for c in self.chunks if c.chunk_type in ("table_semantic", "table_row")
        ]

    def to_dict(self) -> dict:
        """序列化"""
        return {
            "doc_id": self.doc_id,
            "chunk_count": len(self.chunks),
            "chunks": [c.to_dict() for c in self.chunks],
        }
