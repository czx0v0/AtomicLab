"""
Hybrid Search Service
=====================
混合搜索服务 - 使用 RRF (Reciprocal Rank Fusion) 融合关键词和语义搜索结果。
"""

from typing import List, Dict, Optional

from .keyword_search import KeywordSearchService
from .semantic_search import SemanticSearchService
from .search_result import SearchResult


class HybridSearchService:
    """
    混合搜索服务
    
    结合关键词搜索和语义搜索，使用 RRF 算法融合结果。
    RRF 公式: score = sum(1 / (k + rank_i))
    
    Attributes:
        keyword_service: 关键词搜索服务
        semantic_service: 语义搜索服务
    """
    
    def __init__(
        self,
        keyword_service: Optional[KeywordSearchService] = None,
        semantic_service: Optional[SemanticSearchService] = None,
        graph=None,
        tree=None,
        lib: Dict = None,
    ):
        """
        初始化
        
        Args:
            keyword_service: 关键词搜索服务（可选，会自动创建）
            semantic_service: 语义搜索服务（可选，会自动创建）
            graph: KnowledgeGraph 实例
            tree: KnowledgeTree 实例
            lib: 文献库字典
        """
        self.keyword_service = keyword_service or KeywordSearchService(
            graph=graph, tree=tree, lib=lib
        )
        
        # 语义搜索可能不可用（需要安装额外依赖）
        self._semantic_service = semantic_service
        self._semantic_available = True
        
        if semantic_service is None:
            try:
                self._semantic_service = SemanticSearchService(
                    graph=graph, tree=tree, lib=lib
                )
                # 测试是否可用
                _ = self._semantic_service.model
            except ImportError:
                self._semantic_available = False
                self._semantic_service = None
    
    @property
    def semantic_service(self) -> Optional[SemanticSearchService]:
        return self._semantic_service
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        keyword_weight: float = 0.5,
        rrf_k: int = 60,
    ) -> List[SearchResult]:
        """
        混合搜索
        
        Args:
            query: 搜索词
            top_k: 返回结果数量
            keyword_weight: 关键词搜索权重 (0-1)
                - 0: 仅语义搜索
                - 1: 仅关键词搜索
                - 0.5: 均衡融合
            rrf_k: RRF 算法参数 k，控制排名衰减速度
            
        Returns:
            融合后的 SearchResult 列表
        """
        if not query or not query.strip():
            return []
        
        # 关键词搜索
        keyword_results = self.keyword_service.search(query, top_k=top_k * 2)
        
        # 语义搜索（如果可用）
        semantic_results = []
        if self._semantic_available and self._semantic_service:
            try:
                semantic_results = self._semantic_service.search(query, top_k=top_k * 2)
            except Exception:
                # 语义搜索失败，回退到仅关键词搜索
                pass
        
        # 如果只有一种搜索可用
        if not semantic_results:
            return keyword_results[:top_k]
        if not keyword_results:
            return semantic_results[:top_k]
        
        # RRF 融合
        fused_results = self._rrf_fusion(
            keyword_results,
            semantic_results,
            k=rrf_k,
            keyword_weight=keyword_weight,
        )
        
        return fused_results[:top_k]
    
    def _rrf_fusion(
        self,
        keyword_results: List[SearchResult],
        semantic_results: List[SearchResult],
        k: int = 60,
        keyword_weight: float = 0.5,
    ) -> List[SearchResult]:
        """
        RRF 融合算法
        
        Reciprocal Rank Fusion 公式:
            RRF_score = weight_kw * (1/(k + rank_kw)) + weight_sem * (1/(k + rank_sem))
        
        Args:
            keyword_results: 关键词搜索结果
            semantic_results: 语义搜索结果
            k: RRF 参数，控制排名重要性衰减
            keyword_weight: 关键词搜索权重
            
        Returns:
            融合后的结果列表
        """
        semantic_weight = 1.0 - keyword_weight
        
        # 构建节点 ID -> 结果的映射
        result_map: Dict[str, SearchResult] = {}
        score_map: Dict[str, float] = {}
        
        # 处理关键词搜索结果
        for rank, result in enumerate(keyword_results):
            node_id = result.get_node_id()
            rrf_score = keyword_weight * (1.0 / (k + rank + 1))
            
            if node_id in score_map:
                score_map[node_id] += rrf_score
            else:
                score_map[node_id] = rrf_score
                result_map[node_id] = result
        
        # 处理语义搜索结果
        for rank, result in enumerate(semantic_results):
            node_id = result.get_node_id()
            rrf_score = semantic_weight * (1.0 / (k + rank + 1))
            
            if node_id in score_map:
                score_map[node_id] += rrf_score
            else:
                score_map[node_id] = rrf_score
                result_map[node_id] = result
        
        # 创建融合结果
        fused_results = []
        for node_id, score in score_map.items():
            original_result = result_map[node_id]
            fused_result = SearchResult(
                node=original_result.node,
                doc=original_result.doc,
                score=score,
                match_type="hybrid",
                matched_field=original_result.matched_field,
                highlight=original_result.highlight,
            )
            fused_results.append(fused_result)
        
        # 按融合分数排序
        fused_results.sort(key=lambda x: x.score, reverse=True)
        
        return fused_results
    
    def build_index(self) -> None:
        """构建语义搜索索引"""
        if self._semantic_available and self._semantic_service:
            self._semantic_service.build_index()
    
    def clear_index(self) -> None:
        """清除语义搜索索引"""
        if self._semantic_service:
            self._semantic_service.clear_index()
