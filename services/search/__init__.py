"""
Search Services
===============
搜索服务模块
"""

# 原有搜索服务
from .keyword_search import KeywordSearchService
from .semantic_search import SemanticSearchService
from .hybrid_search import HybridSearchService
from .search_result import SearchResult as LegacySearchResult

# 新增高级搜索服务
from .faiss_store import FAISSVectorStore, VectorStoreManager
from .bm25_index import BM25Index
from .hybrid_searcher import HybridSearcher, SearchPipeline
from .reranker import RerankerService, LLMReranker

__all__ = [
    # 原有服务(保持兼容)
    "KeywordSearchService",
    "SemanticSearchService",
    "HybridSearchService",
    "LegacySearchResult",
    # 新增服务
    "FAISSVectorStore",
    "VectorStoreManager",
    "BM25Index",
    "HybridSearcher",
    "SearchPipeline",
    "RerankerService",
    "LLMReranker",
]
