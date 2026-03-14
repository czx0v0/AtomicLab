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


# ModelScope创空间：使用ModelScope下载embedding模型
def _download_embedding_model_from_modelscope(model_name: str) -> Optional[str]:
    """从ModelScope下载embedding模型，返回本地路径"""
    if not IN_MODELSCOPE_SPACE:
        return None

    try:
        from modelscope import snapshot_download

        # ModelScope上的sentence-transformers镜像模型
        # 映射 HuggingFace 模型名到 ModelScope 模型名
        # 注意：ModelScope上直接使用相同的模型名
        modelscope_mapping = {
            "paraphrase-multilingual-MiniLM-L12-v2": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            "BAAI/bge-reranker-v2-m3": "BAAI/bge-reranker-v2-m3",
        }

        ms_model_name = modelscope_mapping.get(model_name)
        if not ms_model_name:
            # 尝试直接使用原模型名
            ms_model_name = model_name

        print(f"[RAG] 从ModelScope下载模型: {ms_model_name}")

        cache_dir = "/mnt/workspace/.cache/modelscope"
        local_path = snapshot_download(
            ms_model_name,
            cache_dir=cache_dir,
        )
        print(f"[RAG] 模型下载完成: {local_path}")
        return local_path
    except ImportError:
        print("[RAG] modelscope库未安装，无法从ModelScope下载模型")
        return None
    except Exception as e:
        print(f"[RAG] ModelScope下载模型失败: {e}")
        return None


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

from models.chunk import TextChunk, ChunkCollection, ChunkMetadata
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
        # 当前激活文档（Demo/分块显示时前端切换用）
        self._active_doc_id: Optional[str] = None

    def set_active_document(self, doc_id: str) -> None:
        """设置当前激活文档，供分块显示等前端逻辑在内存中定位数据。"""
        self._active_doc_id = doc_id

    def get_active_document(self) -> Optional[str]:
        """返回当前激活文档 ID。"""
        return self._active_doc_id

    def _init_components(self):
        """初始化各组件"""
        print("=" * 50)
        print("初始化RAG服务...")
        print("=" * 50)

        # 1. 文档解析器 - 支持MinerU和Docling
        parser_backend = getattr(self.config, "parser_backend", "docling")
        self.parser = None

        if parser_backend == "mineru":
            # 仅使用 MinerU Cloud，不再调用本地 CLI 解析器
            from core.config import MINERU_API_KEY

            try:
                if not (MINERU_API_KEY or "").strip():
                    raise RuntimeError(
                        "MinerU Cloud API 未配置：MINERU_API_KEY 为空，无法使用 mineru 解析后端"
                    )

                from services.parser.mineru_cloud_parser import MinerUCloudParser

                # 当前 MinerUCloudParser 自身管理解析策略，不接受额外参数
                self.parser = MinerUCloudParser()
                print("✓ MinerU Cloud 解析器初始化成功 (HTTP API)")
            except Exception as e:
                print(f"⚠️ MinerU Cloud 解析器不可用: {e}")
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
                # ModelScope创空间：先尝试从ModelScope下载模型
                model_path = self.config.embedding_model
                if IN_MODELSCOPE_SPACE:
                    print("[RAG] 检测到ModelScope创空间环境")
                    local_model_path = _download_embedding_model_from_modelscope(
                        self.config.embedding_model
                    )
                    if local_model_path:
                        model_path = local_model_path
                        print(f"[RAG] 使用ModelScope本地模型: {model_path}")

                # 根据环境选择缓存目录
                cache_folder = (
                    SENTENCE_TRANSFORMERS_CACHE if IN_MODELSCOPE_SPACE else None
                )

                self.embedding_model = SentenceTransformer(
                    model_path,
                    device=self.config.device,
                    cache_folder=cache_folder,
                )
                print(f"✓ Embedding模型加载成功: {self.config.embedding_model}")
                if cache_folder:
                    print(f"  模型缓存位置: {cache_folder}")
            except Exception as e:
                error_msg = str(e)
                print(f"⚠️ Embedding模型加载失败: {error_msg}")

                # 检测是否是网络不可达错误（ModelScope创空间常见）
                if (
                    "Network is unreachable" in error_msg
                    or "Cannot send a request" in error_msg
                ):
                    print("⚠️ 检测到网络不可达，RAG语义搜索将不可用")
                    print("  将使用BM25关键词搜索作为降级方案")
                    if IN_MODELSCOPE_SPACE:
                        print("  提示: ModelScope创空间无法访问HuggingFace")
                        print("  如需RAG语义搜索，请预先下载模型到持久化目录")
                    self.embedding_model = None
                else:
                    print("尝试清理缓存并重新加载...")
                    # 清理缓存
                    import shutil

                    cache_dir = (
                        Path.home() / ".cache" / "torch" / "sentence_transformers"
                    )
                    model_name = self.config.embedding_model.replace("/", "_")
                    model_cache = cache_dir / model_name
                    if model_cache.exists():
                        shutil.rmtree(model_cache)
                        print(f"已清理缓存: {model_cache}")
                    # 重试
                    try:
                        self.embedding_model = SentenceTransformer(
                            self.config.embedding_model, device=self.config.device
                        )
                        print(f"✓ Embedding模型重新加载成功")
                    except Exception as retry_error:
                        print(f"⚠️ 重试失败: {retry_error}")
                        print("  RAG语义搜索将不可用，使用BM25关键词搜索")
                        self.embedding_model = None
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
                embedding_model=self.embedding_model,  # 传递已加载的模型对象
                device=self.config.device,
            )
            self.hybrid_searcher.set_weights(
                semantic=self.config.semantic_weight, keyword=self.config.keyword_weight
            )
            print("✓ 混合检索器初始化成功")
        else:
            self.hybrid_searcher = None
            if not self.embedding_model:
                print("⚠️ 混合检索器不可用（缺少Embedding模型），将使用BM25关键词搜索")

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
                    # MinerU 解析失败时自动降级到 Docling，再失败则用 PyPDF2 基础提取
                    parser_backend = getattr(self.config, "parser_backend", "docling")
                    if parser_backend == "mineru":
                        print(f"⚠️ MinerU解析失败: {parse_error}")
                        print("  自动降级到Docling解析器...")
                        try:
                            from services.parser.docling_parser import DoclingParser

                            fallback_parser = DoclingParser()
                            parsed = fallback_parser.parse(filepath, doc_id)
                            print("✓ Docling降级解析成功")
                        except Exception as fallback_err:
                            print(f"⚠️ Docling降级也失败: {fallback_err}")
                            print("  最终降级到PyPDF2基础提取...")
                            parsed = self._fallback_parse_document(filepath, doc_id)
                            print("✓ PyPDF2基础提取完成")
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

            # 4. 生成章节摘要（可选）；标题降级：若全文仅一个一级标题，则将 ## 视作独立 Section
            if self.summarizer and parsed.sections:
                h1_count = sum(1 for s in parsed.sections if s.level == 1)
                use_h2_as_section = h1_count <= 1
                if use_h2_as_section:
                    print("\n生成章节摘要 (一级+二级标题，因仅一个一级标题)...")
                else:
                    print("\n生成章节摘要 (仅一级标题)...")
                level1_sections = [
                    s for s in parsed.sections
                    if (s.level == 1 or (use_h2_as_section and s.level == 2))
                    and s.content.strip()
                ]
                if level1_sections:
                    sections_data = [
                        {
                            "section_id": s.section_id,
                            "heading": s.heading,
                            "content": s.content,
                        }
                        for s in level1_sections
                    ]
                    summaries = self.summarizer.batch_summarize(sections_data)

                    # 更新ParsedSection的summary字段，并创建摘要chunk加入索引
                    summary_chunks = []
                    for section in level1_sections:
                        if section.section_id in summaries:
                            summary_obj = summaries[section.section_id]
                            section.summary = summary_obj.summary
                            section.key_points = summary_obj.key_points
                            # 将摘要文本作为可检索chunk加入RAG索引
                            summary_text = (
                                f"[章节摘要] {section.heading}: {summary_obj.summary}"
                            )
                            summary_chunk = TextChunk(
                                chunk_id=f"{section.section_id}-SUMMARY",
                                doc_id=parsed.doc_id,
                                content=summary_text,
                                chunk_type="section",
                                metadata=ChunkMetadata(
                                    doc_title=parsed.title,
                                    section_name=section.heading,
                                    extra={
                                        "is_summary": True,
                                        "section_id": section.section_id,
                                    },
                                ),
                            )
                            summary_chunks.append(summary_chunk)

                    chunks.extend(summary_chunks)
                    print(
                        f"章节摘要生成完成: {len(summaries)} 个章节, "
                        f"新增 {len(summary_chunks)} 个摘要chunks"
                    )

            # 4b. 轻量级图抽取：从 chunk 文本中提取主-谓-宾关系
            self._extract_relation_edges(parsed, chunks)

            # 5. 生成embeddings（含摘要chunk）
            self._generate_embeddings(chunks)

            # 6. 索引
            self._index_chunks(parsed.doc_id, chunks)

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
        """对文档进行分块。有 sections 且含 page_start 时按章节分块并写入 page_number，避免全为 p.1。"""
        all_chunks = []

        # 1. 文本分块（有实质内容的章节时按节分块并写入 page_number，否则全文分块并设 page_number=1）
        if self.chunker and parsed.content:
            sections_with_page = [
                s for s in (parsed.sections or [])
                if getattr(s, "content", None) and len((s.content or "").strip()) > 50
                and (getattr(s, "page_start", None) or getattr(s, "page_end", None))
            ]
            if sections_with_page:
                for section in sections_with_page:
                    page_num = getattr(section, "page_start", None) or getattr(section, "page_end", None) or 1
                    text_chunks = self.chunker.chunk(
                        text=section.content.strip(),
                        doc_id=parsed.doc_id,
                        doc_title=parsed.title,
                        doc_type="pdf",
                        page_number=page_num,
                    )
                    all_chunks.extend(text_chunks)
                print(f"文本分块(按章节): {len(sections_with_page)} 节 -> {len(all_chunks)} 个chunks")
            else:
                text_chunks = self.chunker.chunk(
                    text=parsed.content,
                    doc_id=parsed.doc_id,
                    doc_title=parsed.title,
                    doc_type="pdf",
                    page_number=1,
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

    def _extract_relation_edges(self, parsed: ParsedDocument, chunks: List[TextChunk]):
        """从 chunk 文本中轻量级抽取主-谓-宾关系，写入 parsed.edges / edge_chunk_ids。"""
        if not chunks:
            return
        try:
            from agents.base import call_llm
        except ImportError:
            return
        prompt = """从下面这段学术文本中抽取知识关系三元组，格式为：主词 | 谓语 | 宾语。每行一个三元组，仅输出三元组，不要解释。
例如：Transformer | 包含 | 自注意力机制
文本：
"""
        # 限制处理数量，避免耗时过长
        max_chunks = min(30, len(chunks))
        for i, chunk in enumerate(chunks[:max_chunks]):
            if not (chunk.content and chunk.content.strip()):
                continue
            text = (chunk.content or "").strip()[:600]
            try:
                out = call_llm(
                    system_prompt="你是知识图谱抽取器。仅输出「主词|谓语|宾语」形式的三元组，每行一个，无则输出空。",
                    user_prompt=prompt + text,
                    temperature=0.1,
                    max_tokens=150,
                )
                for line in (out or "").strip().splitlines():
                    line = line.strip()
                    if "|" not in line:
                        continue
                    parts = [p.strip() for p in line.split("|", 2)]
                    if len(parts) >= 3 and parts[0] and parts[1] and parts[2]:
                        parsed.edges.append((parts[0], parts[1], parts[2]))
                        parsed.edge_chunk_ids.append(chunk.chunk_id)
            except Exception:
                continue
        if parsed.edges:
            print(f"图抽取: {len(parsed.edges)} 条边 (来自 {max_chunks} 个chunks)")

    def retrieve(
        self,
        query: str,
        top_k: int = 15,
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

        # 降级：使用BM25关键词搜索
        if not self.hybrid_searcher:
            if self.bm25_index and self.chunk_store:
                print(
                    f"\n使用BM25关键词搜索: '{query[:50]}'"
                    if len(query) > 50
                    else f"\n使用BM25关键词搜索: '{query}'"
                )
                return self._bm25_search(query, top_k)
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

        # 4. 提取 chunks：第一路向量 Top5，第二路图一度扩展
        vector_chunks = [r.chunk for r in search_results if r.chunk][:5]
        graph_chunks = self._graph_expand_chunks(vector_chunks)
        chunks = vector_chunks + graph_chunks

        # 5. 构建上下文：区分 [1]-[5] 向量匹配 与 [G1]-[Gk] 图谱扩展
        context = self._build_context_with_refs(vector_chunks, graph_chunks)

        elapsed = (time.time() - start_time) * 1000

        return RetrievalResult(
            chunks=chunks,
            context=context,
            query=query,
            total_candidates=len(search_results),
            retrieval_time_ms=elapsed,
        )

    def _graph_expand_chunks(self, vector_chunks: List[TextChunk], max_expand: int = 5) -> List[TextChunk]:
        """基于 edges 一度关联扩展：从向量结果中的 chunk 出发，找到关联的其它 chunk。"""
        if not vector_chunks or not getattr(self, "parsed_docs", None):
            return []
        vector_cids = {c.chunk_id for c in vector_chunks}
        all_edges = []
        for parsed in (self.parsed_docs or {}).values():
            if not getattr(parsed, "edges", None) or not getattr(parsed, "edge_chunk_ids", None):
                continue
            for idx, (s, p, o) in enumerate(parsed.edges):
                cid = parsed.edge_chunk_ids[idx] if idx < len(parsed.edge_chunk_ids) else ""
                if cid:
                    all_edges.append((s, p, o, cid))
        entities_from_vector = set()
        for s, p, o, cid in all_edges:
            if cid in vector_cids:
                entities_from_vector.add(s)
                entities_from_vector.add(o)
        related_cids = set()
        for s, p, o, cid in all_edges:
            if cid in vector_cids:
                continue
            if s in entities_from_vector or o in entities_from_vector:
                related_cids.add(cid)
        out = []
        for cid in list(related_cids)[:max_expand]:
            if cid in self.chunk_store:
                out.append(self.chunk_store[cid])
        return out

    def _build_context_with_refs(
        self,
        vector_chunks: List[TextChunk],
        graph_chunks: List[TextChunk],
    ) -> str:
        """构建带 [1]/[G1] 区分的上下文。"""
        parts = []
        for i, chunk in enumerate(vector_chunks):
            source = f"[{i+1}]"
            if chunk.metadata.doc_title:
                source += f" {chunk.metadata.doc_title}"
            if chunk.page_number:
                source += f" (第{chunk.page_number}页)"
            if chunk.chunk_type in ("table_semantic", "table_row"):
                parts.append(f"{source} [表格]\n{chunk.content}")
            else:
                parts.append(f"{source}\n{chunk.content}")
        for i, chunk in enumerate(graph_chunks):
            source = f"[G{i+1}]"
            if chunk.metadata.doc_title:
                source += f" {chunk.metadata.doc_title}"
            if chunk.page_number:
                source += f" (第{chunk.page_number}页)"
            if chunk.chunk_type in ("table_semantic", "table_row"):
                parts.append(f"{source} [图谱扩展-表格]\n{chunk.content}")
            else:
                parts.append(f"{source} [图谱扩展]\n{chunk.content}")
        return "\n\n---\n\n".join(parts) if parts else ""

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

    def _bm25_search(self, query: str, top_k: int = 5) -> RetrievalResult:
        """BM25关键词搜索（降级方案）"""
        import time as time_module

        start_time = time_module.time()

        # 使用BM25搜索
        results = self.bm25_index.search(query, top_k=top_k * 2)

        # 转换为SearchResult并填充chunk
        search_results = []
        for chunk_id, score in results[:top_k]:
            if chunk_id in self.chunk_store:
                chunk = self.chunk_store[chunk_id]
                from models.search import SearchResult as SR

                search_results.append(SR(chunk=chunk, score=score, _chunk_id=chunk_id))

        # 提取chunks
        chunks = [r.chunk for r in search_results if r.chunk]

        # 构建上下文
        context = self._build_context(chunks)

        elapsed = (time_module.time() - start_time) * 1000

        return RetrievalResult(
            chunks=chunks,
            context=context,
            query=query,
            total_candidates=len(search_results),
            retrieval_time_ms=elapsed,
        )

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

    def _recover_chunk_store_from_vector_store(self) -> int:
        """从 vector_store.metadata_store 恢复 chunk_store 与 doc_chunks。用于 load() 与 Demo 加载。"""
        loaded_count = 0
        if not self.vector_store or not hasattr(self.vector_store, "metadata_store"):
            return loaded_count
        for chunk_id, metadata in self.vector_store.metadata_store.items():
            if chunk_id in self.chunk_store:
                continue
            if not isinstance(metadata, dict):
                continue
            try:
                from models.chunk import TextChunk, ChunkMetadata

                page_num = metadata.get("page_number")
                meta = (
                    ChunkMetadata(
                        doc_title=metadata.get("doc_title", ""),
                        page_number=page_num,
                    )
                    if metadata
                    else ChunkMetadata()
                )
                chunk = TextChunk(
                    chunk_id=chunk_id,
                    doc_id=metadata.get("doc_id", ""),
                    content=metadata.get("content", ""),
                    chunk_type=metadata.get("chunk_type", "paragraph"),
                    page_number=page_num,
                    metadata=meta,
                )
                self.chunk_store[chunk_id] = chunk
                loaded_count += 1
                doc_id = metadata.get("doc_id", "")
                if doc_id:
                    if doc_id not in self.doc_chunks:
                        self.doc_chunks[doc_id] = []
                    if chunk_id not in self.doc_chunks[doc_id]:
                        self.doc_chunks[doc_id].append(chunk_id)
            except Exception as e:
                print(f"⚠️ 加载chunk {chunk_id} 失败: {e}")
        if loaded_count:
            print(f"✅ 从索引恢复 {loaded_count} 个 chunks 到内存")
        return loaded_count

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
            self._recover_chunk_store_from_vector_store()

        if self.bm25_index:
            self.bm25_index.load()

        print(
            f"✅ 索引已加载: {len(self.chunk_store)} chunks, {len(self.doc_chunks)} 文档"
        )

    def clear(self):
        """清空当前会话的所有数据（内存 + 磁盘）"""
        self.chunk_store.clear()
        self.doc_chunks.clear()
        self.parsed_docs.clear()

        if self.vector_store:
            self.vector_store.clear()
        if self.bm25_index:
            self.bm25_index.clear()

        # 清理存储目录
        if hasattr(self.config, "storage_path") and self.config.storage_path:
            import shutil

            storage_path = Path(self.config.storage_path)
            if storage_path.exists():
                shutil.rmtree(storage_path, ignore_errors=True)

        print(
            f"[Session] 已清理 RAG 数据: {getattr(self.config, 'storage_path', '未知')}"
        )


# ══════════════════════════════════════════════════════════════
# 会话级 RAG 服务管理（对接 core.session_store）
# ══════════════════════════════════════════════════════════════
import uuid
from threading import Lock
from typing import Dict

_session_rag_services: Dict[str, RAGService] = {}
_session_rag_lock = Lock()

# 全局共享服务（本地开发 / 无 session_id 场景）
_shared_rag_service: Optional[RAGService] = None

# 查询重写 System Prompt：意图识别 + 中英学术关键词
_QUERY_REWRITE_SYSTEM = """你是一个学术查询优化器。用户的输入可能是一段中文提问或闲聊。
任务 1 (意图识别)：如果这是普通的日常聊天、打招呼，或如"帮我翻译"等指令，请直接输出 "NONE"。
任务 2 (中英翻译)：如果这是一个学术问题，请提取核心实体，并将其翻译为标准的英文学术搜索关键词。
只输出最终的英文关键词字符串，不要包含任何解释、引号或多余的话语。例如，输入"什么是原子知识？"，输出"Atomic Knowledge"。
"""


def optimize_search_query(user_query: str) -> str:
    """
    大模型查询重写：意图识别 + 中英学术关键词提取。
    - 闲聊/打招呼/纯指令（如「帮我翻译」）→ 返回 "NONE"，调用方应跳过检索。
    - 学术问题 → 返回英文学术搜索关键词，用于 ArXiv 等检索。
    """
    if not user_query or not user_query.strip():
        return "NONE"
    try:
        from agents.base import call_llm

        out = call_llm(
            system_prompt=_QUERY_REWRITE_SYSTEM,
            user_prompt=user_query.strip(),
            temperature=0.1,
            max_tokens=120,
        )
        s = (out or "").strip()
        if s.upper() == "NONE":
            return "NONE"
        return s
    except Exception as e:
        print(f"[RAG] optimize_search_query 失败: {e}")
        return user_query.strip()


def get_rag_service(
    config: Optional[RAGConfig] = None, session_id: Optional[str] = None
) -> RAGService:
    """
    获取 RAG 服务实例

    - session_id=None：返回全局共享服务（本地开发）
    - session_id 指定：返回会话独立服务（多用户 Demo）
    """
    global _shared_rag_service

    if session_id is None:
        if _shared_rag_service is None:
            _shared_rag_service = RAGService(config)
        return _shared_rag_service

    with _session_rag_lock:
        if session_id not in _session_rag_services:
            # 通过 session_store 初始化会话目录
            try:
                from core.session_store import init_session, touch_session

                session_dir = init_session(session_id)
                session_storage = str(session_dir)
            except ImportError:
                session_storage = f"storage/sessions/{session_id}"

            if config is None:
                session_config = RAGConfig(storage_path=session_storage)
            elif isinstance(config, dict):
                session_config = RAGConfig(
                    **{**config, "storage_path": session_storage}
                )
            else:
                session_config = config
                session_config.storage_path = session_storage

            _session_rag_services[session_id] = RAGService(session_config)
        else:
            # 更新会话活跃时间
            try:
                from core.session_store import touch_session

                touch_session(session_id)
            except ImportError:
                pass

        return _session_rag_services[session_id]


def create_session() -> str:
    """创建新会话，返回 session_id"""
    return str(uuid.uuid4())[:8]


def clear_session(session_id: str) -> bool:
    """清理指定会话的所有数据（RAG + 文件）"""
    cleared = False

    with _session_rag_lock:
        if session_id in _session_rag_services:
            service = _session_rag_services.pop(session_id)
            service.clear()
            cleared = True

    # 同步清理 session_store
    try:
        from core.session_store import SessionDataStore, get_session_dir
        import shutil

        SessionDataStore.cleanup_session(session_id)
        session_dir = get_session_dir(session_id)
        if session_dir.exists():
            shutil.rmtree(session_dir, ignore_errors=True)
    except Exception as e:
        print(f"[Session] session_store 清理失败: {e}")

    print(f"[Session] 已清理会话: {session_id}")
    return cleared


def get_active_sessions() -> list:
    """获取所有活跃会话ID"""
    with _session_rag_lock:
        return list(_session_rag_services.keys())


def load_demo_index_from_path(index_dir: str) -> bool:
    """
    从指定目录加载 Demo 向量索引，而不重新进行 embedding。
    同时将 chunk_store / doc_chunks 从 metadata_store 恢复到内存，避免「索引不在内存中」。

    设计用于 Demo 场景：index_dir 通常为 demo_data/faiss_index。
    """
    service = get_rag_service()
    if not getattr(service, "vector_store", None):
        print("[RAG] Demo 索引加载失败：vector_store 不可用")
        return False

    path = Path(index_dir)
    service.vector_store.storage_path = path
    print(f"[RAG] 正在从 Demo 索引目录加载 FAISS: {path}")
    ok = service.vector_store.load()
    if ok:
        service._recover_chunk_store_from_vector_store()
        # 若 Demo 目录下存在 bm25 索引，则一并加载以启用混合检索（传入 path 避免覆盖 storage_path 为 str 导致 .exists() 报错）
        base = path.parent
        bm25_path = base / "bm25" / "index.pkl"
        if getattr(service, "bm25_index", None):
            try:
                if Path(bm25_path).exists():
                    service.bm25_index.load(str(bm25_path))
                    print(f"[RAG] 已加载 Demo BM25 索引: {bm25_path}")
            except Exception as e:
                print(f"[RAG] Demo BM25 加载跳过: {e}")
        # 加载完 Demo 后立即把写入路径改回默认，确保后续上传触发的 save() 只写 storage/faiss，不写 demo_data
        service.vector_store.storage_path = Path(f"{service.config.storage_path}/faiss")
    return ok


def start_session_cleanup():
    """启动会话清理调度器（委托给 session_store）"""
    try:
        from core.session_store import start_cleanup_scheduler

        start_cleanup_scheduler(interval_seconds=300)
    except ImportError:
        print("[Session] session_store 未可用，跳过清理调度器")
