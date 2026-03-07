"""
Services Module
===============
服务模块，提供搜索、解析、RAG等功能。
"""

# 原有搜索服务(保持兼容)
from .search import (
    KeywordSearchService,
    SemanticSearchService,
    HybridSearchService,
    LegacySearchResult,
    # 新增高级搜索服务
    FAISSVectorStore,
    VectorStoreManager,
    BM25Index,
    HybridSearcher,
    SearchPipeline,
    RerankerService,
    LLMReranker,
)

# 新增RAG服务
from .rag_service import (
    RAGService,
    RAGConfig,
    get_rag_service,
)

# 新增解析服务
from .parser import DoclingParser

__all__ = [
    # 原有搜索服务
    "KeywordSearchService",
    "SemanticSearchService",
    "HybridSearchService",
    "LegacySearchResult",
    # 新增高级搜索服务
    "FAISSVectorStore",
    "VectorStoreManager",
    "BM25Index",
    "HybridSearcher",
    "SearchPipeline",
    "RerankerService",
    "LLMReranker",
    # RAG服务
    "RAGService",
    "RAGConfig",
    "get_rag_service",
    # 解析服务
    "DoclingParser",
]
