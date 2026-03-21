"""
Hybrid Searcher
===============
三路混合检索服务: 语义 + 关键词 + 元数据过滤
使用RRF (Reciprocal Rank Fusion) 融合结果
"""

import os
import time
from typing import List, Optional, Dict, Any, Tuple
from collections import defaultdict

# 设置HuggingFace镜像（中国大陆加速）
if "HF_ENDPOINT" not in os.environ:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

try:
    from sentence_transformers import SentenceTransformer

    ST_AVAILABLE = True
except ImportError:
    ST_AVAILABLE = False

from models.chunk import TextChunk
from models.search import SearchResult, SearchScores, MatchDetails
from .faiss_store import FAISSVectorStore
from .bm25_index import BM25Index


class HybridSearcher:
    """
    混合检索服务

    三路检索:
    1. 语义搜索 (FAISS向量相似度)
    2. 关键词搜索 (BM25)
    3. 元数据过滤

    融合策略: RRF (Reciprocal Rank Fusion)
    score = Σ(weight_i / (k + rank_i))
    """

    def __init__(
        self,
        vector_store: FAISSVectorStore,
        bm25_index: BM25Index,
        embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2",
        device: str = "cpu",
    ):
        if not ST_AVAILABLE:
            raise ImportError(
                "sentence-transformers未安装。请运行: pip install sentence-transformers"
            )

        self.vector_store = vector_store
        self.bm25_index = bm25_index

        # 加载embedding模型
        print(f"加载embedding模型: {embedding_model}")
        try:
            self.embedding_model = SentenceTransformer(embedding_model, device=device)
        except Exception as e:
            print(f"⚠️ 模型加载失败，尝试清理缓存: {e}")
            import shutil
            from pathlib import Path

            cache_dir = Path.home() / ".cache" / "torch" / "sentence_transformers"
            model_cache = cache_dir / embedding_model.replace("/", "_")
            if model_cache.exists():
                shutil.rmtree(model_cache)
            self.embedding_model = SentenceTransformer(embedding_model, device=device)

        # RRF参数
        self.rrf_k = 60  # RRF平滑参数,标准值60
        self.semantic_weight = 0.6
        self.keyword_weight = 0.3
        self.metadata_weight = 0.1

    def search(
        self,
        query: str,
        top_k: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
        return_scores: bool = True,
    ) -> List[SearchResult]:
        """
        混合搜索

        Args:
            query: 查询词
            top_k: 返回结果数量
            metadata_filter: 元数据过滤条件
            return_scores: 是否返回详细分数

        Returns:
            SearchResult列表,按融合分数排序
        """
        start_time = time.time()

        # 1. 生成查询embedding
        query_embedding = self.embedding_model.encode(query)

        # 2. 并行执行语义搜索和关键词搜索
        # 搜索更多结果用于融合
        search_k = max(top_k * 3, 20)

        semantic_results = self.vector_store.search(
            query_embedding, top_k=search_k, metadata_filter=metadata_filter
        )

        keyword_results = self.bm25_index.search(query, top_k=search_k)

        # 3. RRF融合
        fused_results = self._rrf_fusion(semantic_results, keyword_results, top_k)

        elapsed = (time.time() - start_time) * 1000
        print(f"混合搜索完成: {len(fused_results)} 个结果, 耗时 {elapsed:.1f}ms")

        return fused_results

    def _rrf_fusion(
        self,
        semantic_results: List[Tuple[str, float]],
        keyword_results: List[Tuple[str, float]],
        top_k: int,
    ) -> List[SearchResult]:
        """
        RRF (Reciprocal Rank Fusion) 融合算法

        公式: score = Σ(weight_i / (k + rank_i))

        其中:
        - k = 60 (标准平滑参数)
        - rank_i 是文档在第i个结果列表中的排名(从1开始)
        - weight_i 是第i个来源的权重

        Args:
            semantic_results: 语义搜索结果 [(chunk_id, score), ...]
            keyword_results: 关键词搜索结果 [(chunk_id, score), ...]
            top_k: 返回结果数量

        Returns:
            融合后的SearchResult列表
        """
        # 构建chunk_id到排名的映射
        semantic_ranks = {
            chunk_id: rank + 1 for rank, (chunk_id, _) in enumerate(semantic_results)
        }
        keyword_ranks = {
            chunk_id: rank + 1 for rank, (chunk_id, _) in enumerate(keyword_results)
        }

        # 收集所有chunk_id
        all_chunk_ids = set(semantic_ranks.keys()) | set(keyword_ranks.keys())

        # 计算RRF分数
        rrf_scores = {}
        chunk_sources = defaultdict(lambda: {"semantic": 0.0, "keyword": 0.0})

        for chunk_id in all_chunk_ids:
            score = 0.0

            # 语义搜索贡献
            if chunk_id in semantic_ranks:
                rank = semantic_ranks[chunk_id]
                sem_score = self.semantic_weight / (self.rrf_k + rank)
                score += sem_score
                chunk_sources[chunk_id]["semantic"] = sem_score

            # 关键词搜索贡献
            if chunk_id in keyword_ranks:
                rank = keyword_ranks[chunk_id]
                kw_score = self.keyword_weight / (self.rrf_k + rank)
                score += kw_score
                chunk_sources[chunk_id]["keyword"] = kw_score

            rrf_scores[chunk_id] = score

        # 按RRF分数排序
        sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[
            :top_k
        ]

        # 构建SearchResult对象
        search_results = []
        for chunk_id, rrf_score in sorted_results:
            # 获取原始分数
            sem_score = 0.0
            for cid, score in semantic_results:
                if cid == chunk_id:
                    sem_score = score
                    break

            kw_score = 0.0
            for cid, score in keyword_results:
                if cid == chunk_id:
                    kw_score = score
                    break

            # 创建SearchResult
            # 注意: 这里只填充了chunk_id,实际使用时需要从chunk_store获取完整chunk
            result = SearchResult(
                chunk=None,  # 需要后续填充
                scores=SearchScores(
                    semantic=sem_score,
                    keyword=kw_score,
                    rrf_fusion=rrf_score,
                    final=rrf_score,
                ),
                match_details=MatchDetails(
                    matched_fields=["content"] if kw_score > 0 else [],
                ),
            )
            # 临时存储chunk_id用于后续填充
            result._chunk_id = chunk_id
            search_results.append(result)

        return search_results

    def search_with_chunks(
        self,
        query: str,
        chunk_store: Dict[str, TextChunk],
        top_k: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        搜索并返回完整的chunk对象

        Args:
            query: 查询词
            chunk_store: chunk_id到TextChunk的映射
            top_k: 返回结果数量
            metadata_filter: 元数据过滤条件

        Returns:
            完整的SearchResult列表
        """
        results = self.search(query, top_k, metadata_filter)

        # 填充chunk对象
        for result in results:
            chunk_id = getattr(result, "_chunk_id", None)
            if chunk_id and chunk_id in chunk_store:
                result.chunk = chunk_store[chunk_id]

        return results

    def set_weights(
        self, semantic: float = 0.6, keyword: float = 0.3, metadata: float = 0.1
    ):
        """
        设置RRF融合权重

        Args:
            semantic: 语义搜索权重
            keyword: 关键词搜索权重
            metadata: 元数据匹配权重
        """
        total = semantic + keyword + metadata
        self.semantic_weight = semantic / total
        self.keyword_weight = keyword / total
        self.metadata_weight = metadata / total

        print(
            f"权重设置: 语义={self.semantic_weight:.2f}, "
            f"关键词={self.keyword_weight:.2f}, "
            f"元数据={self.metadata_weight:.2f}"
        )


class SearchPipeline:
    """
    完整搜索流水线
    包含: 混合检索 -> 重排序 -> 结果格式化
    """

    def __init__(
        self, hybrid_searcher: HybridSearcher, reranker=None  # 可选的重排序器
    ):
        self.hybrid_searcher = hybrid_searcher
        self.reranker = reranker

    def search(
        self,
        query: str,
        chunk_store: Dict[str, TextChunk],
        top_k: int = 5,
        rerank_top_n: int = 20,
    ) -> List[SearchResult]:
        """
        完整搜索流程

        1. 混合检索 (获取rerank_top_n个候选)
        2. 重排序 (如果有reranker)
        3. 返回top_k结果
        """
        # 1. 混合检索
        candidates = self.hybrid_searcher.search_with_chunks(
            query, chunk_store, top_k=rerank_top_n
        )

        # 2. 重排序
        if self.reranker and len(candidates) > top_k:
            candidates = self.reranker.rerank(query, candidates, top_n=top_k)

        # 3. 返回top_k
        return candidates[:top_k]
