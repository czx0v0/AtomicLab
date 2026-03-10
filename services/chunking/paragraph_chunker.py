"""
Paragraph Chunker
=================
段落分块器 - 直接按空行（段落边界）分割，比语义分块更快更自然。
适合 MinerU / Docling 等已保留段落结构的解析结果。
"""

import re
import uuid
from typing import List

from models.chunk import TextChunk, ChunkMetadata


class ParagraphChunker:
    """
    段落分块器

    算法:
    1. 按连续空行（\\n\\n+）分割为原始段落
    2. 过短的段落合并到相邻段落（避免碎片）
    3. 超长段落按句子边界再切分

    优势:
    - 无需加载 embedding 模型，启动快
    - 天然保持段落语义完整性
    - 适合文档结构已由解析器保留的场景
    """

    def __init__(
        self,
        max_chunk_size: int = 900,  # 最大 token 数
        min_chunk_tokens: int = 80,  # 低于此值尝试合并相邻段落
    ):
        self.max_chunk_size = max_chunk_size
        self.min_chunk_tokens = min_chunk_tokens

    # ── Public API ──────────────────────────────────────────────────────

    def chunk(
        self, text: str, doc_id: str, doc_title: str = "", **kwargs
    ) -> List[TextChunk]:
        """按段落分块。

        Args:
            text: 输入文本（Markdown 或纯文本）
            doc_id: 文档 ID
            doc_title: 文档标题
            **kwargs: 透传给 ChunkMetadata（如 doc_type、page_number 等）

        Returns:
            TextChunk 列表
        """
        # 1. 分割原始段落
        raw_paras = re.split(r"\n{2,}", text.strip())
        raw_paras = [p.strip() for p in raw_paras if p.strip()]

        if not raw_paras:
            return []

        # 2. 合并过短段落 & 拆分超长段落
        merged = self._merge_short(raw_paras)
        final_texts: List[str] = []
        for para in merged:
            if self._estimate_tokens(para) > self.max_chunk_size:
                final_texts.extend(self._split_long(para))
            else:
                final_texts.append(para)

        # 3. 转成 TextChunk
        total = len(final_texts)
        chunks: List[TextChunk] = []
        for i, content in enumerate(final_texts):
            chunks.append(
                self._make_chunk(content, doc_id, doc_title, i, total, **kwargs)
            )

        print(f"段落分块完成: {len(raw_paras)} 原始段落 -> {total} 个chunks")
        return chunks

    # ── Internal helpers ────────────────────────────────────────────────

    def _merge_short(self, paras: List[str]) -> List[str]:
        """将过短段落向后合并，直到达到 min_chunk_tokens。"""
        result: List[str] = []
        buf = ""
        for para in paras:
            if buf:
                candidate = buf + "\n\n" + para
                if self._estimate_tokens(buf) < self.min_chunk_tokens:
                    # buf 还太短，继续合并
                    if self._estimate_tokens(candidate) <= self.max_chunk_size:
                        buf = candidate
                        continue
                    else:
                        # 合并后超限，先输出 buf，再处理 para
                        result.append(buf)
                        buf = para
                        continue
                # buf 已够长，输出它，开始新 buf
                result.append(buf)
                buf = para
            else:
                buf = para
        if buf:
            result.append(buf)
        return result

    def _split_long(self, text: str) -> List[str]:
        """将超长段落按句子边界拆分。"""
        sentences = re.split(r"(?<=[。！？.!?])\s*", text)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks: List[str] = []
        current = ""
        for sent in sentences:
            candidate = (current + " " + sent).strip() if current else sent
            if self._estimate_tokens(candidate) <= self.max_chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                # 单句超limit时强制保留
                current = sent
        if current:
            chunks.append(current)
        return chunks if chunks else [text]

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """估算 token 数（中文按字符数，英文按词数的 1.3 倍）。"""
        if not text:
            return 0
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        other_chars = len(text) - chinese_chars
        return chinese_chars + int(other_chars * 0.4)

    def _make_chunk(
        self,
        content: str,
        doc_id: str,
        doc_title: str,
        index: int,
        total: int,
        **kwargs,
    ) -> TextChunk:
        meta = ChunkMetadata(
            doc_title=doc_title,
            chunk_index=index,
            total_chunks=total,
            token_count=self._estimate_tokens(content),
            **{
                k: v
                for k, v in kwargs.items()
                if k in ChunkMetadata.__dataclass_fields__
            },
        )
        return TextChunk(
            chunk_id=f"{doc_id}_p{uuid.uuid4().hex[:8]}",
            doc_id=doc_id,
            content=content,
            chunk_type="paragraph",
            metadata=meta,
            semantic_coherence=1.0,
        )
