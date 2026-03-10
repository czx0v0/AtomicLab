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
from pathlib import Path

# HuggingFace镜像配置由core/config.py统一管理
# ModelScope创空间环境检测和镜像设置在config.py中
from core.config import IN_MODELSCOPE_SPACE, MODEL_CACHE_DIR

# ══════════════════════════════════════════════════════════════
# SentenceTransformers缓存目录配置
# ══════════════════════════════════════════════════════════════

# 关键：本地开发完全使用默认缓存，不干预HuggingFace行为
if IN_MODELSCOPE_SPACE and MODEL_CACHE_DIR:
    # ModelScope创空间: 使用持久化存储目录
    SENTENCE_TRANSFORMERS_CACHE = os.path.join(MODEL_CACHE_DIR, "sentence_transformers")

    # 确保目录存在
    os.makedirs(SENTENCE_TRANSFORMERS_CACHE, exist_ok=True)

    # 设置环境变量（仅在创空间）
    os.environ["SENTENCE_TRANSFORMERS_HOME"] = SENTENCE_TRANSFORMERS_CACHE

    print(f"[RAG] ModelScope创空间模式")
    print(f"[RAG] 模型缓存目录: {SENTENCE_TRANSFORMERS_CACHE}")
else:
    # 本地开发: 完全使用默认缓存位置，不设置任何环境变量
    SENTENCE_TRANSFORMERS_CACHE = None
    # 不打印，避免干扰

try:
    from sentence_transformers import SentenceTransformer

    ST_AVAILABLE = True
except ImportError:
    ST_AVAILABLE = False

from models.chunk import TextChunk, ChunkCollection
from models.search import RetrievalResult, ProcessingResult, SearchResult
from models.parse_result import ParsedDocument, ParsedSection, DocumentMetadata

from services.chunking import SemanticChunker, TableChunker, ParagraphChunker
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

    # 解析器配置
    parser_backend: str = "docling"  # "docling" 或 "mineru"
    mineru_parse_method: str = "auto"  # auto/ocr/txt
    # 分块模式
    chunk_mode: str = "semantic"  # semantic | paragraph


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
                parser_backend=config.get("parser_backend", "docling"),
                mineru_parse_method=config.get("mineru_parse_method", "auto"),
                chunk_mode=config.get("chunk_mode", "semantic"),
            )
        else:
            self.config = config

        # 初始化各组件
        self._init_components()

        # Chunk存储 (内存中)
        self.chunk_store: Dict[str, TextChunk] = {}
        self.doc_chunks: Dict[str, List[str]] = {}  # doc_id -> chunk_ids
        # 解析结果缓存（会话内）
        self.parsed_docs: Dict[str, ParsedDocument] = {}

    def _init_components(self):
        """初始化各组件"""
        print("=" * 50)
        print("初始化RAG服务...")
        print("=" * 50)

        # 1. 文档解析器 - 支持MinerU和Docling
        parser_backend = getattr(self.config, "parser_backend", "docling")
        self.parser = None

        if parser_backend == "mineru":
            try:
                from services.parser.mineru_parser import (
                    MinerUParser,
                    MINERU_AVAILABLE,
                    MINERU_IMPORT_ERROR,
                )

                if MINERU_AVAILABLE:
                    self.parser = MinerUParser(
                        parse_method=self.config.mineru_parse_method
                    )
                    print("✓ MinerU解析器初始化成功 (高精度模式)")
                else:
                    raise ImportError(
                        f"MinerU不可用: {MINERU_IMPORT_ERROR or 'unknown reason'}"
                    )
            except ImportError as e:
                print(f"⚠️ MinerU解析器不可用: {e}")
                print("  回退到Docling解析器...")
                parser_backend = "docling"

        if parser_backend == "docling" or self.parser is None:
            try:
                from services.parser.docling_parser import DoclingParser

                self.parser = DoclingParser()
                print("✓ Docling解析器初始化成功")
            except ImportError as e:
                print(f"✗ Docling解析器初始化失败: {e}")
                self.parser = None

        # 2. 分块器
        chunk_mode = getattr(self.config, "chunk_mode", "semantic")
        if chunk_mode == "paragraph":
            self.chunker = ParagraphChunker(
                max_chunk_size=self.config.chunk_size,
            )
            self.table_chunker = TableChunker()
            print("✓ 段落分块器初始化成功")
        elif ST_AVAILABLE:
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
                # 根据环境选择缓存目录
                cache_folder = (
                    SENTENCE_TRANSFORMERS_CACHE if IN_MODELSCOPE_SPACE else None
                )

                self.embedding_model = SentenceTransformer(
                    self.config.embedding_model,
                    device=self.config.device,
                    cache_folder=cache_folder,
                )
                print(f"✓ Embedding模型加载成功: {self.config.embedding_model}")
                if cache_folder:
                    print(f"  模型缓存位置: {cache_folder}")
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

        # 7. 章节摘要生成器
        try:
            from services.summarizer import SectionSummarizer

            self.summarizer = SectionSummarizer(use_cache=True)
            print("✓ 章节摘要生成器初始化成功")
        except ImportError as e:
            print(f"⚠️ 章节摘要生成器初始化失败: {e}")
            self.summarizer = None

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
            try:
                parsed = self.parser.parse(filepath, doc_id)
            except Exception as parse_error:
                if self._is_windows_privilege_error(parse_error):
                    print("⚠️ 检测到Windows缓存链接权限问题，回退到纯文本解析模式")
                    parsed = self._fallback_parse_document(filepath, doc_id)
                else:
                    raise

            # 2. 质量检查
            if parsed.parse_confidence < self.config.min_parse_confidence:
                return ProcessingResult(
                    success=False,
                    error=f"解析置信度过低: {parsed.parse_confidence:.2f}",
                    confidence=parsed.parse_confidence,
                )

            # 缓存解析结果，供前端结构化渲染使用（如MinerU Markdown/章节视图）
            self.parsed_docs[parsed.doc_id] = parsed

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

            # 6. 生成章节摘要（可选）
            if self.summarizer and parsed.sections:
                print("\n生成章节摘要...")
                sections_data = [
                    {
                        "section_id": s.section_id,
                        "heading": s.heading,
                        "content": s.content,
                    }
                    for s in parsed.sections
                ]
                summaries = self.summarizer.batch_summarize(sections_data)

                # 更新ParsedSection的summary字段
                for section in parsed.sections:
                    if section.section_id in summaries:
                        summary_obj = summaries[section.section_id]
                        section.summary = summary_obj.summary
                        section.key_points = summary_obj.key_points

                print(f"章节摘要生成完成: {len(summaries)} 个章节")

            elapsed = (time.time() - start_time) * 1000

            print(f"\n文档处理完成: {len(chunks)} 个chunks, 耗时 {elapsed:.1f}ms")

            # 构建章节信息列表（用于知识树构建）
            sections_data = None
            if parsed.sections:
                sections_data = [
                    {
                        "section_id": s.section_id,
                        "heading": s.heading,
                        "level": s.level,
                        "summary": s.summary,
                        "page_start": s.page_start,
                        "page_end": s.page_end,
                    }
                    for s in parsed.sections
                ]

            return ProcessingResult(
                success=True,
                doc_id=parsed.doc_id,
                chunk_count=len(chunks),
                confidence=parsed.parse_confidence,
                processing_time_ms=elapsed,
                sections=sections_data,
            )

        except Exception as e:
            return ProcessingResult(success=False, error=str(e))

    def _is_windows_privilege_error(self, error: Exception) -> bool:
        """检测Windows下HF缓存链接权限错误(WinError 1314)。"""
        msg = str(error)
        return (
            "WinError 1314" in msg
            or "客户端没有所需的特权" in msg
            or "required privilege is not held by the client" in msg.lower()
        )

    def _fallback_parse_document(
        self, filepath: str, doc_id: Optional[str] = None
    ) -> ParsedDocument:
        """Docling失败时回退为PyPDF2纯文本解析，保证RAG流程可继续。"""
        if doc_id is None:
            filename = os.path.basename(filepath)
            doc_id = (
                "doc-" + filename.encode("utf-8", errors="ignore").hex()[:8].upper()
            )

        text = ""
        page_count = 0
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(filepath)
            page_count = len(reader.pages)
            chunks = []
            for page in reader.pages:
                chunks.append(page.extract_text() or "")
            text = "\n\n".join(chunks).strip()
        except Exception as e:
            raise RuntimeError(f"回退解析失败: {e}") from e

        if not text:
            raise RuntimeError("回退解析失败: PDF未提取到文本")

        title = Path(filepath).stem
        section = ParsedSection(
            section_id=f"{doc_id}_s000",
            heading="Document",
            level=1,
            content=text[:3000],
            page_start=1,
            page_end=max(page_count, 1),
        )
        metadata = DocumentMetadata(page_count=page_count, extra={"title": title})

        return ParsedDocument(
            doc_id=doc_id,
            title=title,
            content=text,
            sections=[section],
            metadata=metadata,
            parse_confidence=0.56,
        )

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
            return RetrievalResult(chunks=[], context="", query=query)

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

    def update_chunking_profile(self, profile: str = "中") -> Dict[str, Any]:
        """更新分块粒度档位（细/中/粗）。

        注意：仅影响后续解析与分块，已入库文档不会自动重建。
        """
        mapping = {
            "细": {
                "chunk_size": 720,
                "chunk_overlap": 100,
                "similarity_threshold": 0.62,
            },
            "中": {
                "chunk_size": 900,
                "chunk_overlap": 120,
                "similarity_threshold": 0.58,
            },
            "粗": {
                "chunk_size": 1200,
                "chunk_overlap": 180,
                "similarity_threshold": 0.52,
            },
        }

        settings = mapping.get(profile, mapping["中"])
        self.config.chunk_size = settings["chunk_size"]
        self.config.chunk_overlap = settings["chunk_overlap"]
        self.config.similarity_threshold = settings["similarity_threshold"]

        if self.chunker:
            self.chunker.max_chunk_size = settings["chunk_size"]
            if isinstance(self.chunker, SemanticChunker):
                self.chunker.overlap = settings["chunk_overlap"]
                self.chunker.similarity_threshold = settings["similarity_threshold"]

        return {
            "profile": profile if profile in mapping else "中",
            **settings,
        }

    def update_chunk_mode(self, mode: str) -> dict:
        """切换分块模式（semantic / paragraph），立即替换 self.chunker。"""
        if mode not in ("semantic", "paragraph"):
            mode = "semantic"

        self.config.chunk_mode = mode

        if mode == "paragraph":
            self.chunker = ParagraphChunker(max_chunk_size=self.config.chunk_size)
            label = "段落分块"
        else:
            # 切回语义分块（需要 ST）
            try:
                self.chunker = SemanticChunker(
                    max_chunk_size=self.config.chunk_size,
                    overlap=self.config.chunk_overlap,
                    similarity_threshold=self.config.similarity_threshold,
                    model_name=self.config.embedding_model,
                    device=self.config.device,
                )
                label = "语义分块"
            except Exception as e:
                print(f"[RAGService] 语义分块器切换失败: {e}，保持段落模式")
                self.chunker = ParagraphChunker(max_chunk_size=self.config.chunk_size)
                label = "段落分块（语义模型不可用）"

        print(f"[RAGService] 分块模式切换 -> {label}")
        return {"mode": mode, "label": label}

    def get_parsed_document(self, doc_id: str) -> Optional[ParsedDocument]:
        """获取已缓存的解析结果（会话内）。"""
        return self.parsed_docs.get(doc_id)

    def delete_document(self, doc_id: str) -> bool:
        """删除文档及其chunks"""
        chunk_ids = self.doc_chunks.pop(doc_id, [])
        self.parsed_docs.pop(doc_id, None)

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

    def load(self, clear_existing: bool = False):
        """加载所有索引和chunk映射

        Args:
            clear_existing: 是否清空现有索引重新加载
        """
        if clear_existing:
            self.chunk_store.clear()
            self.doc_chunks.clear()
            self.parsed_docs.clear()
            print("🗑️ 已清空现有索引缓存")

        if self.vector_store:
            self.vector_store.load()
            # 从vector_store恢复chunk_store
            # chunk_map: Dict[int, str] = faiss_id -> chunk_id
            # metadata_store: Dict[str, dict] = chunk_id -> metadata
            if hasattr(self.vector_store, "metadata_store"):
                loaded_count = 0
                for chunk_id, metadata in self.vector_store.metadata_store.items():
                    if chunk_id not in self.chunk_store:
                        # 确保metadata是字典
                        if not isinstance(metadata, dict):
                            print(
                                f"⚠️ chunk {chunk_id} 的metadata格式不正确({type(metadata)})，跳过"
                            )
                            continue

                        try:
                            # 创建轻量级chunk对象
                            from models.chunk import TextChunk, ChunkMetadata

                            chunk = TextChunk(
                                chunk_id=chunk_id,
                                doc_id=metadata.get("doc_id", ""),
                                content=metadata.get("content", ""),
                                chunk_type=metadata.get("chunk_type", "paragraph"),
                                page_number=metadata.get("page_number"),
                                metadata=(
                                    ChunkMetadata(
                                        doc_title=metadata.get("doc_title", ""),
                                        page_number=metadata.get("page_number"),
                                    )
                                    if metadata
                                    else ChunkMetadata()
                                ),
                            )
                            self.chunk_store[chunk_id] = chunk
                            loaded_count += 1

                            # 重建doc_chunks映射
                            doc_id = metadata.get("doc_id", "")
                            if doc_id:
                                if doc_id not in self.doc_chunks:
                                    self.doc_chunks[doc_id] = []
                                if chunk_id not in self.doc_chunks[doc_id]:
                                    self.doc_chunks[doc_id].append(chunk_id)
                        except Exception as e:
                            print(f"⚠️ 加载chunk {chunk_id} 失败: {e}")
                            continue

                print(f"✅ 从索引加载了 {loaded_count} 个chunks")

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
