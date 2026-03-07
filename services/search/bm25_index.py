"""
BM25 Index
==========
BM25关键词索引实现
支持中文jieba分词
"""

import pickle
import numpy as np
from typing import List, Optional, Dict, Tuple
from pathlib import Path

try:
    from rank_bm25 import BM25Okapi

    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False

try:
    import jieba

    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False

from models.chunk import TextChunk


class BM25Index:
    """
    BM25关键词索引

    特性:
    - 支持中文jieba分词
    - 增量更新
    - 持久化
    """

    def __init__(self, storage_path: Optional[str] = None):
        if not BM25_AVAILABLE:
            raise ImportError("rank-bm25未安装。请运行: pip install rank-bm25")

        self.corpus: List[str] = []
        self.chunk_ids: List[str] = []
        self.tokenized_corpus: List[List[str]] = []
        self.bm25: Optional[BM25Okapi] = None
        self.metadata: Dict[str, dict] = {}

        self.storage_path = Path(storage_path) if storage_path else None

    def _tokenize(self, text: str) -> List[str]:
        """
        分词
        - 中文使用jieba
        - 英文使用空格分割
        """
        if JIEBA_AVAILABLE:
            # jieba分词,过滤单字和标点
            tokens = list(jieba.cut(text))
            return [
                t.strip().lower()
                for t in tokens
                if len(t.strip()) > 1 and not t.strip().isspace()
            ]
        else:
            # 简单分词
            return text.lower().split()

    def add_documents(self, chunks: List[TextChunk]):
        """
        添加文档到索引

        Args:
            chunks: 文本块列表
        """
        for chunk in chunks:
            self.corpus.append(chunk.content)
            self.chunk_ids.append(chunk.chunk_id)
            self.metadata[chunk.chunk_id] = chunk.metadata.to_dict()

            # 分词
            tokens = self._tokenize(chunk.content)
            self.tokenized_corpus.append(tokens)

        # 重建BM25索引
        if self.tokenized_corpus:
            self.bm25 = BM25Okapi(self.tokenized_corpus)

    def search(
        self, query: str, top_k: int = 10, return_scores: bool = True
    ) -> List[Tuple[str, float]]:
        """
        BM25搜索

        Args:
            query: 查询词
            top_k: 返回结果数量
            return_scores: 是否返回分数

        Returns:
            [(chunk_id, score), ...] 按BM25分数排序
        """
        if not self.bm25 or not self.tokenized_corpus:
            return []

        # 查询分词
        query_tokens = self._tokenize(query)

        if not query_tokens:
            return []

        # 获取BM25分数
        scores = self.bm25.get_scores(query_tokens)

        # 获取top-k索引
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # 只返回有分数的结果
                chunk_id = self.chunk_ids[idx]
                results.append((chunk_id, float(scores[idx])))

        return results

    def search_with_highlight(
        self, query: str, top_k: int = 10
    ) -> List[Tuple[str, float, List[str]]]:
        """
        搜索并返回匹配的关键词

        Returns:
            [(chunk_id, score, matched_keywords), ...]
        """
        query_tokens = set(self._tokenize(query))

        results = self.search(query, top_k)
        highlighted_results = []

        for chunk_id, score in results:
            # 获取chunk内容
            idx = self.chunk_ids.index(chunk_id)
            content = self.corpus[idx]
            content_tokens = self.tokenized_corpus[idx]

            # 找到匹配的词
            matched = [t for t in query_tokens if t in content_tokens]

            highlighted_results.append((chunk_id, score, matched))

        return highlighted_results

    def get_stats(self) -> dict:
        """获取索引统计"""
        return {
            "total_documents": len(self.corpus),
            "avg_doc_length": (
                sum(len(t) for t in self.tokenized_corpus) / len(self.tokenized_corpus)
                if self.tokenized_corpus
                else 0
            ),
        }

    def save(self, path: Optional[str] = None):
        """持久化索引"""
        save_path = Path(path) if path else self.storage_path
        if not save_path:
            raise ValueError("未指定存储路径")

        save_path.parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, "wb") as f:
            pickle.dump(
                {
                    "corpus": self.corpus,
                    "chunk_ids": self.chunk_ids,
                    "tokenized_corpus": self.tokenized_corpus,
                    "metadata": self.metadata,
                },
                f,
            )

        print(f"BM25索引已保存到 {save_path}")

    def load(self, path: Optional[str] = None) -> bool:
        """加载索引"""
        load_path = Path(path) if path else self.storage_path
        if not load_path or not load_path.exists():
            return False

        try:
            with open(load_path, "rb") as f:
                data = pickle.load(f)
                self.corpus = data["corpus"]
                self.chunk_ids = data["chunk_ids"]
                self.tokenized_corpus = data["tokenized_corpus"]
                self.metadata = data.get("metadata", {})

            # 重建BM25索引
            if self.tokenized_corpus:
                self.bm25 = BM25Okapi(self.tokenized_corpus)

            print(f"成功加载BM25索引,包含 {len(self.corpus)} 个文档")
            return True

        except Exception as e:
            print(f"加载BM25索引失败: {e}")
            return False

    def clear(self):
        """清空索引"""
        self.corpus = []
        self.chunk_ids = []
        self.tokenized_corpus = []
        self.bm25 = None
        self.metadata = {}
