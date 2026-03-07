"""
Reranker Service
================
Cross-Encoder重排序服务
两阶段检索的第二阶段
"""

import os
import time
from typing import List, Tuple, Optional

# 设置HuggingFace镜像（中国大陆加速）
if "HF_ENDPOINT" not in os.environ:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

try:
    from sentence_transformers import CrossEncoder

    ST_AVAILABLE = True
except ImportError:
    ST_AVAILABLE = False

from models.chunk import TextChunk
from models.search import SearchResult, RerankInfo


class RerankerService:
    """
    Cross-Encoder重排序服务

    工作流程:
    1. 第一阶段: Bi-Encoder(embedding模型)快速召回top-k候选
    2. 第二阶段: Cross-Encoder精确计算query-chunk相关性

    优势:
    - Cross-Encoder同时编码query和document,捕获更细粒度的交互
    - 精度显著高于Bi-Encoder,但计算成本更高
    - 适合对少量候选进行精确排序

    常用模型:
    - BAAI/bge-reranker-v2-m3 (推荐,多语言)
    - cross-encoder/ms-marco-MiniLM-L-6-v2
    - cross-encoder/ms-marco-MiniLM-L-12-v2
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-v2-m3",
        device: str = "cpu",
        batch_size: int = 16,
        max_length: int = 512,
    ):
        if not ST_AVAILABLE:
            raise ImportError(
                "sentence-transformers未安装。请运行: pip install sentence-transformers"
            )

        print(f"加载重排序模型: {model_name}")
        self.model = CrossEncoder(model_name, device=device, max_length=max_length)
        self.model_name = model_name
        self.batch_size = batch_size

    def rerank(
        self, query: str, results: List[SearchResult], top_n: int = 5
    ) -> List[SearchResult]:
        """
        重排序搜索结果

        Args:
            query: 查询词
            results: 候选结果列表(来自第一阶段检索)
            top_n: 返回结果数量

        Returns:
            重排序后的SearchResult列表
        """
        if not results:
            return []

        start_time = time.time()

        # 构建query-chunk pairs
        pairs = []
        for result in results:
            if result.chunk:
                pairs.append([query, result.chunk.content])
            else:
                pairs.append([query, ""])

        # 批量预测相关性分数
        scores = self.model.predict(
            pairs, batch_size=self.batch_size, show_progress_bar=False
        )

        # 更新结果分数
        for i, (result, score) in enumerate(zip(results, scores)):
            result.scores.rerank = float(score)
            # 综合分数: RRF分数 * 0.4 + 重排序分数 * 0.6
            result.scores.final = result.scores.rrf_fusion * 0.4 + float(score) * 0.6

            # 记录重排序信息
            result.rerank_info = RerankInfo(
                original_rank=i,
                rerank_score=float(score),
                rerank_model=self.model_name,
                latency_ms=(time.time() - start_time) * 1000 / len(results),
            )

        # 按重排序分数排序
        results.sort(key=lambda x: x.scores.rerank, reverse=True)

        elapsed = (time.time() - start_time) * 1000
        print(f"重排序完成: {len(results)} 个候选 -> top {top_n}, 耗时 {elapsed:.1f}ms")

        return results[:top_n]

    def rerank_chunks(
        self, query: str, chunks: List[TextChunk], top_n: int = 5
    ) -> List[Tuple[TextChunk, float]]:
        """
        直接重排序chunks

        Args:
            query: 查询词
            chunks: 候选chunk列表
            top_n: 返回结果数量

        Returns:
            [(chunk, score), ...] 按分数排序
        """
        if not chunks:
            return []

        # 构建pairs
        pairs = [[query, chunk.content] for chunk in chunks]

        # 预测
        scores = self.model.predict(pairs, batch_size=self.batch_size)

        # 排序
        scored_chunks = list(zip(chunks, scores))
        scored_chunks.sort(key=lambda x: x[1], reverse=True)

        return scored_chunks[:top_n]

    def compute_score(self, query: str, text: str) -> float:
        """
        计算单个query-text对的相关性分数

        Args:
            query: 查询词
            text: 文档文本

        Returns:
            相关性分数 (0-1)
        """
        score = self.model.predict([[query, text]])[0]
        return float(score)


class LLMReranker:
    """
    基于LLM的重排序器

    使用LLM判断query和document的相关性
    适合需要复杂推理的场景,但成本和延迟更高

    提示词策略:
    - 要求LLM输出相关性分数(0-10)
    - 提供评分标准和示例
    """

    def __init__(self, llm_client):
        self.llm = llm_client

    def rerank(
        self, query: str, chunks: List[TextChunk], top_n: int = 5
    ) -> List[Tuple[TextChunk, float]]:
        """
        使用LLM重排序

        注意: 这个方法成本较高,建议只用于少量候选(<10)
        """
        scored_chunks = []

        for chunk in chunks:
            score = self._llm_score(query, chunk.content)
            scored_chunks.append((chunk, score))

        # 排序
        scored_chunks.sort(key=lambda x: x[1], reverse=True)

        return scored_chunks[:top_n]

    def _llm_score(self, query: str, document: str) -> float:
        """使用LLM评分"""
        prompt = f"""评估以下文档与查询的相关性:

查询: {query}

文档: {document[:500]}...

请输出相关性分数(0-10):
- 10: 完全相关,直接回答问题
- 7-9: 高度相关,包含关键信息
- 4-6: 部分相关,包含一些有用信息
- 1-3: 低度相关,仅提及相关内容
- 0: 完全不相关

只输出数字分数:"""

        try:
            response = self.llm.generate(prompt, max_tokens=5)
            score = float(response.strip()) / 10.0  # 归一化到0-1
            return min(max(score, 0.0), 1.0)  # 确保在范围内
        except:
            return 0.0
