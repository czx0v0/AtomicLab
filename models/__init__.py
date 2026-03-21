"""
Data Models
===========
Core data structures for AtomicLab v2.0:
- DocumentNode: 文献根节点
- TreeNode: 统一树节点模型 (section/annotation/figure/table)
- Edge: 文献间关系
- KnowledgeGraph: 文献知识图谱
- ParsedDocument: Docling解析结果
- TextChunk: RAG文本块
- SearchResult: 搜索结果
"""

from .document import DocumentNode
from .tree_node import TreeNode
from .edge import Edge
from .graph import KnowledgeGraph
from .parse_result import (
    ParsedDocument,
    ParsedSection,
    ParsedTable,
    ParsedFigure,
    ParsedFormula,
    DocumentMetadata,
)
from .chunk import TextChunk, ChunkMetadata, ChunkCollection, ChunkType
from .search import SearchResult, SearchScores, RetrievalResult, ProcessingResult

__all__ = [
    "DocumentNode",
    "TreeNode",
    "Edge",
    "KnowledgeGraph",
    "ParsedDocument",
    "ParsedSection",
    "ParsedTable",
    "ParsedFigure",
    "ParsedFormula",
    "DocumentMetadata",
    "TextChunk",
    "ChunkMetadata",
    "ChunkCollection",
    "ChunkType",
    "SearchResult",
    "SearchScores",
    "RetrievalResult",
    "ProcessingResult",
]
