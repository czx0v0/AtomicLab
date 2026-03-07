"""
Search Result Models
====================
搜索结果数据模型
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

from .chunk import TextChunk


@dataclass
class SearchScores:
    """多维度评分"""

    semantic: float = 0.0  # 语义相似度
    keyword: float = 0.0  # 关键词匹配度
    metadata_match: float = 0.0  # 元数据匹配度
    rrf_fusion: float = 0.0  # RRF融合分
    rerank: Optional[float] = None  # 重排序分
    final: float = 0.0  # 最终综合分

    def to_dict(self) -> dict:
        return {
            "semantic": self.semantic,
            "keyword": self.keyword,
            "metadata_match": self.metadata_match,
            "rrf_fusion": self.rrf_fusion,
            "rerank": self.rerank,
            "final": self.final,
        }


@dataclass
class MatchDetails:
    """匹配详情"""

    matched_fields: List[str] = field(default_factory=list)  # 匹配的字段
    highlight_spans: List[Tuple[int, int]] = field(default_factory=list)  # 高亮位置
    query_expansion: List[str] = field(default_factory=list)  # 查询扩展词
    matched_keywords: List[str] = field(default_factory=list)  # 匹配的关键词

    def to_dict(self) -> dict:
        return {
            "matched_fields": self.matched_fields,
            "highlight_spans": self.highlight_spans,
            "query_expansion": self.query_expansion,
            "matched_keywords": self.matched_keywords,
        }


@dataclass
class RerankInfo:
    """重排序信息"""

    original_rank: int  # 重排前的排名
    rerank_score: float  # 重排序分数
    rerank_model: str  # 使用的模型
    latency_ms: float  # 重排序耗时

    def to_dict(self) -> dict:
        return {
            "original_rank": self.original_rank,
            "rerank_score": self.rerank_score,
            "rerank_model": self.rerank_model,
            "latency_ms": self.latency_ms,
        }


@dataclass
class SearchResult:
    """统一搜索结果"""

    chunk: TextChunk
    scores: SearchScores = field(default_factory=SearchScores)
    match_details: MatchDetails = field(default_factory=MatchDetails)
    rerank_info: Optional[RerankInfo] = None

    # 搜索上下文
    query: str = ""
    search_time: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "chunk": self.chunk.to_dict(),
            "scores": self.scores.to_dict(),
            "match_details": self.match_details.to_dict(),
            "rerank_info": self.rerank_info.to_dict() if self.rerank_info else None,
            "query": self.query,
            "search_time": self.search_time.isoformat(),
        }

    def get_highlighted_content(self) -> str:
        """获取带高亮的内容"""
        content = self.chunk.content
        if not self.match_details.highlight_spans:
            return content

        # 按位置排序并添加高亮标记
        result = []
        last_end = 0
        for start, end in sorted(self.match_details.highlight_spans):
            result.append(content[last_end:start])
            result.append(f"**{content[start:end]}**")
            last_end = end
        result.append(content[last_end:])

        return "".join(result)


@dataclass
class RetrievalResult:
    """检索结果集合"""

    chunks: List[TextChunk] = field(default_factory=list)
    context: str = ""  # 构建好的上下文
    query: str = ""

    # 检索统计
    total_candidates: int = 0  # 候选数量
    retrieval_time_ms: float = 0.0

    # Agentic信息
    agentic_iterations: int = 0
    rewritten_query: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "chunks": [c.to_dict() for c in self.chunks],
            "context": self.context,
            "query": self.query,
            "total_candidates": self.total_candidates,
            "retrieval_time_ms": self.retrieval_time_ms,
            "agentic_iterations": self.agentic_iterations,
            "rewritten_query": self.rewritten_query,
        }

    def get_context_with_citations(self) -> str:
        """获取带引用的上下文"""
        parts = []
        for i, chunk in enumerate(self.chunks):
            source = f"[{i+1}]"
            if chunk.metadata.doc_title:
                source += f" {chunk.metadata.doc_title}"
            if chunk.page_number:
                source += f" (第{chunk.page_number}页)"

            parts.append(f"{source}\n{chunk.content}")

        return "\n\n---\n\n".join(parts)


@dataclass
class ProcessingResult:
    """文档处理结果"""

    success: bool
    doc_id: str = ""
    chunk_count: int = 0
    confidence: float = 0.0
    error: Optional[str] = None
    processing_time_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "doc_id": self.doc_id,
            "chunk_count": self.chunk_count,
            "confidence": self.confidence,
            "error": self.error,
            "processing_time_ms": self.processing_time_ms,
        }
