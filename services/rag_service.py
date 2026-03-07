"""
RAG Service
===========
RAG统一服务入口
整合: 解析 -> 分块 -> 索引 -> 检索 -> 重排
"""

import os
import time
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

# 设置HuggingFace镜像（中国大陆加速）
if "HF_ENDPOINT" not in os.environ:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

try:
    from sentence_transformers import SentenceTransformer

    ST_AVAILABLE = True
except ImportError:
    ST_AVAILABLE = False

from models.chunk import TextChunk, ChunkCollection
from models.search import RetrievalResult, ProcessingResult, SearchResult
from models.parse_result import ParsedDocument

from services.parser import DoclingParser
from services.chunking import SemanticChunker, TableChunker
from services.search import (
    FAISSVectorStore,
    BM25Index,
    HybridSearcher,
    RerankerService,
)


@dataclass
class RAGConfig:
    """RAG服务配置"""

    # 模型配置
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    device: str = "cpu"

    # 分块配置
    chunk_size: int = 512
    chunk_overlap: int = 50
    similarity_threshold: float = 0.7

    # 检索配置
    vector_index_type: str = "HNSW"
    rrf_k: int = 60
    semantic_weight: float = 0.6
    keyword_weight: float = 0.3

    # 重排序配置
    use_reranker: bool = True
    rerank_top_n: int = 20

    # 质量配置
    min_parse_confidence: float = 0.5

    # 存储配置
    storage_path: str = "storage"


class RAGService:
    """
    RAG统一服务

    完整流程:
    1. 文档解析 (Docling)
    2. 智能分块 (语义分块 + 表格分块)
    3. 向量化 (Embedding)
    4. 索引 (FAISS + BM25)
    5. 检索 (混合检索 + RRF融合)
    6. 重排序 (Cross-Encoder)
    7. 上下文构建
    """

    def __init__(self, config: Optional[Any] = None):
        # 支持字典或RAGConfig对象
        if config is None:
            self.config = RAGConfig()
        elif isinstance(config, dict):
            # 从字典创建RAGConfig对象
            self.config = RAGConfig(
                embedding_model=config.get(
                    "embedding_model", "paraphrase-multilingual-MiniLM-L12-v2"
                ),
                reranker_model=config.get("reranker_model", "BAAI/bge-reranker-v2-m3"),
                device=config.get("device", "cpu"),
                chunk_size=config.get("chunk_size", 512),
                chunk_overlap=config.get("chunk_overlap", 50),
                similarity_threshold=config.get("similarity_threshold", 0.7),
                vector_index_type=config.get("vector_index_type", "HNSW"),
                rrf_k=config.get("rrf_k", 60),
                semantic_weight=config.get("semantic_weight", 0.6),
                keyword_weight=config.get("keyword_weight", 0.3),
                use_reranker=config.get("use_reranker", True),
                rerank_top_n=config.get("rerank_top_n", 20),
                min_parse_confidence=config.get("min_parse_confidence", 0.5),
                storage_path=config.get("storage_path", "storage"),
            )
        else:
            self.config = config

        # 初始化各组件
        self._init_components()

        # Chunk存储 (内存中)
        self.chunk_store: Dict[str, TextChunk] = {}
        self.doc_chunks: Dict[str, List[str]] = {}  # doc_id -> chunk_ids

    def _init_components(self):
        """初始化各组件"""
        print("=" * 50)
        print("初始化RAG服务...")
        print("=" * 50)

        # 1. 文档解析器
        try:
            self.parser = DoclingParser()
            print("✓ Docling解析器初始化成功")
        except ImportError as e:
            print(f"✗ Docling解析器初始化失败: {e}")
            self.parser = None

        # 2. 分块器
        if ST_AVAILABLE:
            self.chunker = SemanticChunker(
                max_chunk_size=self.config.chunk_size,
                overlap=self.config.chunk_overlap,
                similarity_threshold=self.config.similarity_threshold,
                model_name=self.config.embedding_model,
                device=self.config.device,
            )
            self.table_chunker = TableChunker()
            print("✓ 语义分块器初始化成功")
        else:
            self.chunker = None
            self.table_chunker = None
            print("✗ 语义分块器初始化失败: sentence-transformers未安装")

        # 3. Embedding模型
        if ST_AVAILABLE:
            try:
                self.embedding_model = SentenceTransformer(
                    self.config.embedding_model, device=self.config.device
                )
                print(f"✓ Embedding模型加载成功: {self.config.embedding_model}")
            except Exception as e:
                print(f"⚠️ Embedding模型加载失败: {e}")
                print("尝试清理缓存并重新加载...")
                # 清理缓存
                import shutil

                cache_dir = Path.home() / ".cache" / "torch" / "sentence_transformers"
                model_name = self.config.embedding_model.replace("/", "_")
                model_cache = cache_dir / model_name
                if model_cache.exists():
                    shutil.rmtree(model_cache)
                    print(f"已清理缓存: {model_cache}")
                # 重试
                self.embedding_model = SentenceTransformer(
                    self.config.embedding_model, device=self.config.device
                )
                print(f"✓ Embedding模型重新加载成功")
        else:
            self.embedding_model = None

        # 4. 向量存储
        try:
            self.vector_store = FAISSVectorStore(
                dimension=384,  # MiniLM维度
                index_type=self.config.vector_index_type,
                storage_path=f"{self.config.storage_path}/faiss",
            )
            print(f"✓ FAISS向量存储初始化成功 (类型: {self.config.vector_index_type})")
        except ImportError as e:
            print(f"✗ FAISS向量存储初始化失败: {e}")
            self.vector_store = None

        # 5. BM25索引
        try:
            self.bm25_index = BM25Index(
                storage_path=f"{self.config.storage_path}/bm25/index.pkl"
            )
            print("✓ BM25索引初始化成功")
        except ImportError as e:
            print(f"✗ BM25索引初始化失败: {e}")
            self.bm25_index = None

        # 6. 混合检索器
        if self.vector_store and self.bm25_index and self.embedding_model:
            self.hybrid_searcher = HybridSearcher(
                vector_store=self.vector_store,
                bm25_index=self.bm25_index,
                embedding_model=self.config.embedding_model,
                device=self.config.device,
            )
            self.hybrid_searcher.set_weights(
                semantic=self.config.semantic_weight, keyword=self.config.keyword_weight
            )
            print("✓ 混合检索器初始化成功")
        else:
            self.hybrid_searcher = None

        # 7. 重排序器
        if self.config.use_reranker and ST_AVAILABLE:
            try:
                self.reranker = RerankerService(
                    model_name=self.config.reranker_model, device=self.config.device
                )
                print(f"✓ 重排序器初始化成功: {self.config.reranker_model}")
            except Exception as e:
                print(f"✗ 重排序器初始化失败: {e}")
                self.reranker = None
        else:
            self.reranker = None

        print("=" * 50)

    def process_document(
        self, filepath: str, doc_id: Optional[str] = None
    ) -> ProcessingResult:
        """
        处理文档: 解析 -> 分块 -> 索引

        Args:
            filepath: 文件路径
            doc_id: 文档ID(可选)

        Returns:
            ProcessingResult: 处理结果
        """
        start_time = time.time()

        # 检查组件
        if not self.parser:
            return ProcessingResult(success=False, error="Docling解析器未初始化")

        try:
            # 1. 解析文档
            print(f"\n解析文档: {filepath}")
            parsed = self.parser.parse(filepath, doc_id)

            # 2. 质量检查
            if parsed.parse_confidence < self.config.min_parse_confidence:
                return ProcessingResult(
                    success=False,
                    error=f"解析置信度过低: {parsed.parse_confidence:.2f}",
                    confidence=parsed.parse_confidence,
                )

            print(f"解析完成: 置信度={parsed.parse_confidence:.2f}")
            print(f"  - 章节: {len(parsed.sections)}")
            print(f"  - 表格: {len(parsed.tables)}")
            print(f"  - 图片: {len(parsed.figures)}")

            # 3. 分块
            chunks = self._chunk_document(parsed)

            # 4. 生成embeddings
            self._generate_embeddings(chunks)

            # 5. 索引
            self._index_chunks(parsed.doc_id, chunks)

            elapsed = (time.time() - start_time) * 1000

            print(f"\n文档处理完成: {len(chunks)} 个chunks, 耗时 {elapsed:.1f}ms")

            return ProcessingResult(
                success=True,
                doc_id=parsed.doc_id,
                chunk_count=len(chunks),
                confidence=parsed.parse_confidence,
                processing_time_ms=elapsed,
            )

        except Exception as e:
            return ProcessingResult(success=False, error=str(e))

    def _chunk_document(self, parsed: ParsedDocument) -> List[TextChunk]:
        """对文档进行分块"""
        all_chunks = []

        # 1. 文本语义分块
        if self.chunker and parsed.content:
            text_chunks = self.chunker.chunk(
                text=parsed.content,
                doc_id=parsed.doc_id,
                doc_title=parsed.title,
                doc_type="pdf",
            )
            all_chunks.extend(text_chunks)
            print(f"文本分块: {len(text_chunks)} 个chunks")

        # 2. 表格分块 (双重embedding)
        for table in parsed.tables:
            if self.table_chunker:
                table_chunks = self.table_chunker.create_table_chunks(
                    table, parsed.doc_id, parsed.title
                )
                all_chunks.extend(table_chunks)

        if parsed.tables:
            print(
                f"表格分块: {len(parsed.tables)} 个表格 -> {len(all_chunks) - len(text_chunks)} 个chunks"
            )

        return all_chunks

    def _generate_embeddings(self, chunks: List[TextChunk]):
        """为chunks生成embeddings"""
        if not self.embedding_model:
            return

        # 收集需要embedding的chunks
        texts = []
        chunks_to_embed = []

        for chunk in chunks:
            if chunk.embedding is None:
                texts.append(chunk.content)
                chunks_to_embed.append(chunk)

        if not texts:
            return

        print(f"生成embeddings: {len(texts)} 个chunks...")

        # 批量生成embeddings
        embeddings = self.embedding_model.encode(
            texts, show_progress_bar=False, batch_size=32
        )

        # 设置到chunks
        for chunk, embedding in zip(chunks_to_embed, embeddings):
            chunk.set_embedding(embedding, self.config.embedding_model)

    def _index_chunks(self, doc_id: str, chunks: List[TextChunk]):
        """索引chunks"""
        if not chunks:
            return

        # 存储到内存
        chunk_ids = []
        for chunk in chunks:
            self.chunk_store[chunk.chunk_id] = chunk
            chunk_ids.append(chunk.chunk_id)

        self.doc_chunks[doc_id] = chunk_ids

        # 添加到FAISS
        if self.vector_store:
            self.vector_store.add_chunks(chunks)
            self.vector_store.save()

        # 添加到BM25
        if self.bm25_index:
            self.bm25_index.add_documents(chunks)
            self.bm25_index.save()

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        use_reranker: Optional[bool] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> RetrievalResult:
        """
        检索: 混合检索 -> 重排序 -> 构建上下文

        Args:
            query: 查询词
            top_k: 返回结果数量
            use_reranker: 是否使用重排序
            metadata_filter: 元数据过滤条件

        Returns:
            RetrievalResult: 检索结果
        """
        start_time = time.time()

        if not self.hybrid_searcher:
            return RetrievalResult(
                chunks=[], context="", query=query, error="混合检索器未初始化"
            )

        # 1. 混合检索
        print(
            f"\n检索: '{query[:50]}...' " if len(query) > 50 else f"\n检索: '{query}'"
        )

        search_results = self.hybrid_searcher.search(
            query=query,
            top_k=self.config.rerank_top_n if use_reranker else top_k,
            metadata_filter=metadata_filter,
        )

        print(f"混合检索: {len(search_results)} 个候选")

        # 2. 填充chunk对象
        for result in search_results:
            chunk_id = getattr(result, "_chunk_id", None)
            if chunk_id and chunk_id in self.chunk_store:
                result.chunk = self.chunk_store[chunk_id]

        # 3. 重排序
        if (
            use_reranker if use_reranker is not None else self.config.use_reranker
        ) and self.reranker:
            search_results = self.reranker.rerank(query, search_results, top_n=top_k)
            print(f"重排序后: top {len(search_results)}")
        else:
            search_results = search_results[:top_k]

        # 4. 提取chunks
        chunks = [r.chunk for r in search_results if r.chunk]

        # 5. 构建上下文
        context = self._build_context(chunks)

        elapsed = (time.time() - start_time) * 1000

        return RetrievalResult(
            chunks=chunks,
            context=context,
            query=query,
            total_candidates=len(search_results),
            retrieval_time_ms=elapsed,
        )

    def _build_context(self, chunks: List[TextChunk]) -> str:
        """构建LLM上下文"""
        if not chunks:
            return ""

        parts = []
        for i, chunk in enumerate(chunks):
            # 构建来源标注
            source = f"[{i+1}]"
            if chunk.metadata.doc_title:
                source += f" {chunk.metadata.doc_title}"
            if chunk.page_number:
                source += f" (第{chunk.page_number}页)"

            # 根据chunk类型格式化内容
            if chunk.chunk_type in ("table_semantic", "table_row"):
                # 表格内容特殊标记
                parts.append(f"{source} [表格]\n{chunk.content}")
            else:
                parts.append(f"{source}\n{chunk.content}")

        return "\n\n---\n\n".join(parts)

    def get_document_chunks(self, doc_id: str) -> List[TextChunk]:
        """获取文档的所有chunks"""
        chunk_ids = self.doc_chunks.get(doc_id, [])
        return [self.chunk_store[cid] for cid in chunk_ids if cid in self.chunk_store]

    def delete_document(self, doc_id: str) -> bool:
        """删除文档及其chunks"""
        chunk_ids = self.doc_chunks.pop(doc_id, [])

        for cid in chunk_ids:
            self.chunk_store.pop(cid, None)
            if self.vector_store:
                self.vector_store.delete_chunk(cid)

        return len(chunk_ids) > 0

    def get_stats(self) -> dict:
        """获取服务统计信息"""
        return {
            "total_documents": len(self.doc_chunks),
            "total_chunks": len(self.chunk_store),
            "vector_store": (
                self.vector_store.get_stats() if self.vector_store else None
            ),
            "bm25_index": self.bm25_index.get_stats() if self.bm25_index else None,
        }

    def save(self):
        """保存所有索引"""
        if self.vector_store:
            self.vector_store.save()
        if self.bm25_index:
            self.bm25_index.save()
        print("所有索引已保存")

    def load(self):
        """加载所有索引和chunk映射"""
        if self.vector_store:
            self.vector_store.load()
            # 从vector_store恢复chunk_store
            if hasattr(self.vector_store, "chunk_map"):
                for chunk_id, metadata in self.vector_store.chunk_map.items():
                    if chunk_id not in self.chunk_store:
                        # 创建轻量级chunk对象
                        from models.chunk import TextChunk, ChunkMetadata

                        chunk = TextChunk(
                            chunk_id=chunk_id,
                            content=metadata.get("content", ""),
                            chunk_type=metadata.get("chunk_type", "text"),
                            metadata=(
                                ChunkMetadata(
                                    doc_id=metadata.get("doc_id", ""),
                                    doc_title=metadata.get("doc_title", ""),
                                    page_number=metadata.get("page_number"),
                                )
                                if metadata
                                else None
                            ),
                        )
                        self.chunk_store[chunk_id] = chunk

                        # 重建doc_chunks映射
                        doc_id = metadata.get("doc_id", "")
                        if doc_id:
                            if doc_id not in self.doc_chunks:
                                self.doc_chunks[doc_id] = []
                            if chunk_id not in self.doc_chunks[doc_id]:
                                self.doc_chunks[doc_id].append(chunk_id)

        if self.bm25_index:
            self.bm25_index.load()

        print(
            f"✅ 索引已加载: {len(self.chunk_store)} chunks, {len(self.doc_chunks)} 文档"
        )


# 全局RAG服务实例
_rag_service: Optional[RAGService] = None


def get_rag_service(config: Optional[RAGConfig] = None) -> RAGService:
    """获取全局RAG服务实例"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService(config)
    return _rag_service
