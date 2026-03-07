"""
Semantic Chunker
================
语义分块器 - 基于embedding相似度动态分割
"""

import os
import uuid
from typing import List, Optional
import numpy as np

# 设置HuggingFace镜像（中国大陆加速）
if "HF_ENDPOINT" not in os.environ:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity

    ST_AVAILABLE = True
except ImportError:
    ST_AVAILABLE = False

try:
    import spacy

    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

from models.chunk import TextChunk, ChunkMetadata


class SemanticChunker:
    """
    语义分块器

    核心算法:
    1. 句子分割 (使用spaCy)
    2. 计算相邻句子embedding相似度
    3. 相似度低于阈值时在边界分割

    优势:
    - 保持语义完整性,避免在句子中间切断
    - 动态调整块大小,语义连贯的内容保持在一起
    - 适合长文档和复杂内容
    """

    def __init__(
        self,
        max_chunk_size: int = 512,  # 最大token数
        overlap: int = 50,  # 重叠token数
        similarity_threshold: float = 0.7,  # 相似度阈值
        model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
        device: str = "cpu",
    ):
        if not ST_AVAILABLE:
            raise ImportError(
                "sentence-transformers未安装。请运行: pip install sentence-transformers scikit-learn"
            )

        self.max_chunk_size = max_chunk_size
        self.overlap = overlap
        self.similarity_threshold = similarity_threshold

        print(f"加载语义分块模型: {model_name}")
        try:
            self.model = SentenceTransformer(model_name, device=device)
        except Exception as e:
            print(f"⚠️ 模型加载失败，尝试重新下载: {e}")
            # 清除缓存并重新下载
            import shutil
            from pathlib import Path
            cache_dir = Path.home() / ".cache" / "torch" / "sentence_transformers"
            model_cache = cache_dir / model_name.replace("/", "_")
            if model_cache.exists():
                print(f"清理缓存: {model_cache}")
                shutil.rmtree(model_cache)
            # 重新加载
            self.model = SentenceTransformer(model_name, device=device)

        self.nlp = None
        self._init_nlp()

    def _init_nlp(self):
        """初始化spaCy NLP模型"""
        if SPACY_AVAILABLE:
            try:
                # 尝试加载中文模型
                self.nlp = spacy.load("zh_core_web_sm")
            except:
                try:
                    # 回退到英文模型
                    self.nlp = spacy.load("en_core_web_sm")
                except:
                    print("警告: spaCy模型未安装,使用简单分句")
                    self.nlp = None

    def chunk(
        self, text: str, doc_id: str, doc_title: str = "", **kwargs
    ) -> List[TextChunk]:
        """
        语义分块

        Args:
            text: 输入文本
            doc_id: 文档ID
            doc_title: 文档标题
            **kwargs: 额外元数据

        Returns:
            TextChunk列表
        """
        # 1. 句子分割
        sentences = self._split_sentences(text)
        if len(sentences) <= 1:
            # 文本太短,直接作为一个chunk
            return [self._create_chunk(text, doc_id, doc_title, 1.0, **kwargs)]

        # 2. 计算句子embeddings
        print(f"计算 {len(sentences)} 个句子的embeddings...")
        embeddings = self.model.encode(sentences, show_progress_bar=False)

        # 3. 计算相邻句子相似度
        similarities = []
        for i in range(len(embeddings) - 1):
            sim = cosine_similarity([embeddings[i]], [embeddings[i + 1]])[0][0]
            similarities.append(sim)

        # 4. 确定分割点
        split_points = self._find_split_points(sentences, similarities)

        # 5. 生成chunks
        chunks = []
        for i in range(len(split_points) - 1):
            start = split_points[i]
            end = split_points[i + 1]

            # 合并句子
            chunk_sentences = sentences[start:end]
            chunk_text = "".join(chunk_sentences)

            # 检查大小限制
            if self._estimate_tokens(chunk_text) > self.max_chunk_size:
                # 进一步分割
                sub_chunks = self._split_by_token_limit(
                    chunk_sentences, doc_id, doc_title, **kwargs
                )
                chunks.extend(sub_chunks)
            else:
                # 计算该chunk的平均语义连贯性
                chunk_sims = similarities[start : end - 1] if start < end - 1 else [1.0]
                coherence = sum(chunk_sims) / len(chunk_sims)

                chunk = self._create_chunk(
                    chunk_text, doc_id, doc_title, coherence, chunk_index=i, **kwargs
                )
                chunks.append(chunk)

        # 更新总chunk数
        for i, chunk in enumerate(chunks):
            chunk.metadata.total_chunks = len(chunks)
            chunk.metadata.chunk_index = i

        print(f"语义分块完成: {len(sentences)} 个句子 -> {len(chunks)} 个chunks")
        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        """
        句子分割

        优先使用spaCy,回退到简单规则
        """
        if self.nlp:
            doc = self.nlp(text)
            sentences = []
            for sent in doc.sents:
                sent_text = sent.text.strip()
                if sent_text:
                    sentences.append(sent_text)
            return sentences
        else:
            # 简单分句: 按句号、问号、感叹号分割
            import re

            sentences = re.split(r"([。！？.!?])", text)
            # 合并标点
            result = []
            for i in range(0, len(sentences) - 1, 2):
                if i + 1 < len(sentences):
                    result.append(sentences[i] + sentences[i + 1])
                else:
                    result.append(sentences[i])
            return [s.strip() for s in result if s.strip()]

    def _find_split_points(
        self, sentences: List[str], similarities: List[float]
    ) -> List[int]:
        """
        找到最佳分割点

        策略:
        1. 相似度低于阈值时分割
        2. 避免产生过小的chunks
        """
        min_chunk_sentences = 2  # 最少句子数

        split_points = [0]
        current_chunk_start = 0

        for i, sim in enumerate(similarities):
            current_chunk_size = i - current_chunk_start + 1

            # 检查是否应该分割
            should_split = (
                sim < self.similarity_threshold
                and current_chunk_size >= min_chunk_sentences
            )

            if should_split:
                split_points.append(i + 1)
                current_chunk_start = i + 1

        # 确保最后一个chunk不会太小
        if (
            len(sentences) - split_points[-1] < min_chunk_sentences
            and len(split_points) > 1
        ):
            # 合并到最后一个chunk
            split_points.pop()

        split_points.append(len(sentences))
        return split_points

    def _split_by_token_limit(
        self, sentences: List[str], doc_id: str, doc_title: str, **kwargs
    ) -> List[TextChunk]:
        """
        按token限制分割(备用方案)
        """
        chunks = []
        current_text = ""

        for sent in sentences:
            if self._estimate_tokens(current_text + sent) > self.max_chunk_size:
                if current_text:
                    chunks.append(
                        self._create_chunk(
                            current_text, doc_id, doc_title, 0.5, **kwargs
                        )
                    )
                current_text = sent
            else:
                current_text += sent

        if current_text:
            chunks.append(
                self._create_chunk(current_text, doc_id, doc_title, 0.5, **kwargs)
            )

        return chunks

    def _create_chunk(
        self,
        content: str,
        doc_id: str,
        doc_title: str,
        coherence: float,
        chunk_index: int = 0,
        **kwargs,
    ) -> TextChunk:
        """创建TextChunk"""
        return TextChunk(
            chunk_id=f"{doc_id}_c{uuid.uuid4().hex[:8]}",
            doc_id=doc_id,
            content=content.strip(),
            chunk_type="semantic",
            metadata=ChunkMetadata(
                doc_title=doc_title,
                doc_type=kwargs.get("doc_type", "pdf"),
                chunk_index=chunk_index,
                token_count=self._estimate_tokens(content),
                keywords=kwargs.get("keywords", []),
            ),
            semantic_coherence=coherence,
            quality_score=coherence,  # 用连贯性作为质量分
        )

    def _estimate_tokens(self, text: str) -> int:
        """
        估算token数量

        中文: 1字 ≈ 1 token
        英文: 1词 ≈ 1.3 tokens
        简单估算: 字符数 / 2
        """
        return len(text) // 2


class ParagraphChunker:
    """
    段落分块器

    简单的段落级分块,适合格式良好的文档
    """

    def __init__(self, max_chunk_size: int = 512, overlap: int = 50):
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap

    def chunk(
        self, text: str, doc_id: str, doc_title: str = "", **kwargs
    ) -> List[TextChunk]:
        """按段落分块"""
        # 按空行分割段落
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        chunks = []
        current_text = ""

        for para in paragraphs:
            if len(current_text) + len(para) > self.max_chunk_size * 2:  # 中文字符估算
                if current_text:
                    chunks.append(
                        self._create_chunk(current_text, doc_id, doc_title, **kwargs)
                    )
                current_text = para
            else:
                current_text += "\n\n" + para if current_text else para

        if current_text:
            chunks.append(self._create_chunk(current_text, doc_id, doc_title, **kwargs))

        return chunks

    def _create_chunk(
        self, content: str, doc_id: str, doc_title: str, **kwargs
    ) -> TextChunk:
        return TextChunk(
            chunk_id=f"{doc_id}_c{uuid.uuid4().hex[:8]}",
            doc_id=doc_id,
            content=content.strip(),
            chunk_type="paragraph",
            metadata=ChunkMetadata(
                doc_title=doc_title,
                doc_type=kwargs.get("doc_type", "pdf"),
                token_count=len(content) // 2,
            ),
        )
