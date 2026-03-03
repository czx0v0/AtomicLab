"""
Semantic Search Service
=======================
基于向量嵌入的语义搜索服务。
支持多种 Embedding 模型，使用余弦相似度匹配。
"""

from typing import List, Dict, Optional, Any
import numpy as np

from .search_result import SearchResult


# 尝试导入 sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


class SemanticSearchService:
    """
    语义搜索服务
    
    使用 Embedding 模型将文本向量化，通过余弦相似度匹配。
    
    支持的模型：
    - BAAI/bge-m3: 多语言、高质量、开源
    - paraphrase-multilingual-MiniLM-L12-v2: 轻量多语言模型（默认）
    
    数据量 <100 时使用 NumPy 内存存储，无需外部向量数据库。
    """
    
    def __init__(
        self,
        graph=None,
        tree=None,
        lib: Dict = None,
        model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
    ):
        """
        初始化
        
        Args:
            graph: KnowledgeGraph 实例（新版）
            tree: KnowledgeTree 实例（兼容旧版）
            lib: 文献库字典（兼容旧版）
            model_name: Embedding 模型名称
        """
        self.graph = graph
        self.tree = tree
        self.lib = lib or {}
        self.model_name = model_name
        
        # 模型实例（延迟加载）
        self._model = None
        
        # 向量索引（内存存储）
        self._embeddings: Optional[np.ndarray] = None
        self._node_ids: List[str] = []
        self._nodes: List[Any] = []
        self._docs: List[Any] = []
        
        self._index_built = False
    
    @property
    def model(self):
        """延迟加载模型"""
        if self._model is None:
            if not SENTENCE_TRANSFORMERS_AVAILABLE:
                raise ImportError(
                    "sentence-transformers 未安装。"
                    "请运行: pip install sentence-transformers"
                )
            self._model = SentenceTransformer(self.model_name)
        return self._model
    
    def build_index(self) -> None:
        """
        构建向量索引
        
        对所有节点进行 embedding，存储在内存中。
        数据量 <100 时，构建速度很快。
        """
        texts = []
        self._node_ids = []
        self._nodes = []
        self._docs = []
        
        # 从 KnowledgeGraph 收集节点
        if self.graph:
            for node in self.graph.get_all_nodes():
                text = self._get_searchable_text(node)
                if text:
                    texts.append(text)
                    self._node_ids.append(node.id)
                    self._nodes.append(node)
                    doc = self.graph.get_document(node.doc_id)
                    self._docs.append(doc)
            
            # 添加文献节点
            for doc in self.graph.documents.values():
                text = self._get_doc_text(doc)
                if text:
                    texts.append(text)
                    self._node_ids.append(doc.id)
                    self._nodes.append(doc)
                    self._docs.append(doc)
        
        # 从旧版 KnowledgeTree 收集节点
        if self.tree and hasattr(self.tree, "nodes"):
            for node in self.tree.nodes.values():
                if node.id in self._node_ids:
                    continue
                text = self._get_searchable_text(node)
                if text:
                    texts.append(text)
                    self._node_ids.append(node.id)
                    self._nodes.append(node)
                    doc = self.lib.get(node.source_pid, {})
                    self._docs.append(doc)
        
        if not texts:
            self._embeddings = np.array([])
            self._index_built = True
            return
        
        # 批量生成 embeddings
        self._embeddings = self._embed_batch(texts)
        self._index_built = True
    
    def search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """
        语义搜索
        
        Args:
            query: 搜索词
            top_k: 返回结果数量
            
        Returns:
            SearchResult 列表，按相似度排序
        """
        if not query or not query.strip():
            return []
        
        # 自动构建索引
        if not self._index_built:
            self.build_index()
        
        if self._embeddings is None or len(self._embeddings) == 0:
            return []
        
        # 生成查询向量
        query_embedding = self._embed(query.strip())
        
        # 计算余弦相似度
        similarities = self._cosine_similarity_batch(
            query_embedding, self._embeddings
        )
        
        # 获取 top-k 结果
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            similarity = similarities[idx]
            if similarity < 0.1:  # 过滤低相似度结果
                continue
            
            results.append(SearchResult(
                node=self._nodes[idx],
                doc=self._docs[idx],
                score=float(similarity),
                match_type="semantic",
            ))
        
        return results
    
    def _embed(self, text: str) -> np.ndarray:
        """文本向量化"""
        return self.model.encode(text, convert_to_numpy=True)
    
    def _embed_batch(self, texts: List[str]) -> np.ndarray:
        """批量文本向量化"""
        return self.model.encode(texts, convert_to_numpy=True)
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算余弦相似度"""
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(vec1, vec2) / (norm1 * norm2))
    
    def _cosine_similarity_batch(
        self, query_vec: np.ndarray, doc_vecs: np.ndarray
    ) -> np.ndarray:
        """批量计算余弦相似度"""
        # 归一化查询向量
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return np.zeros(len(doc_vecs))
        query_normalized = query_vec / query_norm
        
        # 归一化文档向量
        doc_norms = np.linalg.norm(doc_vecs, axis=1, keepdims=True)
        doc_norms[doc_norms == 0] = 1  # 避免除零
        doc_normalized = doc_vecs / doc_norms
        
        # 计算点积
        similarities = np.dot(doc_normalized, query_normalized)
        return similarities
    
    def _get_searchable_text(self, node: Any) -> str:
        """获取节点的可搜索文本"""
        if hasattr(node, "get_searchable_text"):
            return node.get_searchable_text()
        
        parts = []
        
        if hasattr(node, "content") and node.content:
            parts.append(node.content)
        elif isinstance(node, dict) and node.get("content"):
            parts.append(node["content"])
        
        if hasattr(node, "heading") and node.heading:
            parts.append(node.heading)
        if hasattr(node, "note") and node.note:
            parts.append(node.note)
        if hasattr(node, "selected_text") and node.selected_text:
            parts.append(node.selected_text)
        if hasattr(node, "tags") and node.tags:
            parts.extend(node.tags)
        
        # 兼容 KnowledgeNode
        if hasattr(node, "label") and node.label:
            parts.append(node.label)
        
        return " ".join(parts)
    
    def _get_doc_text(self, doc: Any) -> str:
        """获取文献的可搜索文本"""
        parts = []
        
        if hasattr(doc, "title") and doc.title:
            parts.append(doc.title)
        elif isinstance(doc, dict) and doc.get("title"):
            parts.append(doc["title"])
        elif isinstance(doc, dict) and doc.get("name"):
            parts.append(doc["name"])
        
        if hasattr(doc, "abstract") and doc.abstract:
            parts.append(doc.abstract)
        if hasattr(doc, "keywords") and doc.keywords:
            parts.extend(doc.keywords)
        
        return " ".join(parts)
    
    def clear_index(self) -> None:
        """清除索引"""
        self._embeddings = None
        self._node_ids = []
        self._nodes = []
        self._docs = []
        self._index_built = False
