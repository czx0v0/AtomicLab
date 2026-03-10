"""
Services Module
===============
服务模块，提供搜索、解析、RAG等功能。
"""

# 原有搜索服务(保持兼容)
try:
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
except Exception:
    KeywordSearchService = None
    SemanticSearchService = None
    HybridSearchService = None
    LegacySearchResult = None
    FAISSVectorStore = None
    VectorStoreManager = None
    BM25Index = None
    HybridSearcher = None
    SearchPipeline = None
    RerankerService = None
    LLMReranker = None

# 新增RAG服务
from .rag_service import RAGService, RAGConfig, get_rag_service

# 新增解析服务
try:
    from .parser import DoclingParser, MinerUParser
except Exception:
    DoclingParser = None
    MinerUParser = None

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
    "MinerUParser",
]
