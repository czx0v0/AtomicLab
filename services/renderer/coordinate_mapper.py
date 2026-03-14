"""
Coordinate Mapper Service
=========================
PDF坐标 ↔ Chunk ID 双向映射器。

核心功能：
1. 存储Docling解析结果中的chunk位置信息
2. 根据PDF页面坐标查找对应chunk
3. 根据chunk_id获取PDF渲染位置
4. 支持高亮数据的精确关联

数据流：
    PDF文件 → Docling解析 → chunks(含bbox) → CoordinateMapper
                                        ↓
    PDF.js渲染 → 用户选择 → 页面坐标 → find_chunk() → chunk_id
                                        ↓
    高亮存储 ← coordinate ← get_highlight_position()
"""

import json
import os
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ChunkPosition:
    """Chunk在PDF中的位置信息。支持 bbox 与 character_offset 双轨，移动端 bbox 穿透时用 offset fallback。"""

    chunk_id: str
    doc_id: str
    page: int
    x: float
    y: float
    width: float
    height: float
    text_content: str = ""  # 用于文本匹配验证
    char_offset_start: int = -1  # 在全文中的字符偏移，用于无 bbox 时 scrollTo 定位
    char_offset_end: int = -1

    def to_dict(self) -> dict:
        d = {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "page": self.page,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }
        if self.char_offset_start >= 0:
            d["char_offset_start"] = self.char_offset_start
        if self.char_offset_end >= 0:
            d["char_offset_end"] = self.char_offset_end
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "ChunkPosition":
        return cls(
            chunk_id=data.get("chunk_id", ""),
            doc_id=data.get("doc_id", ""),
            page=data.get("page", 1),
            x=data.get("x", 0),
            y=data.get("y", 0),
            width=data.get("width", 0),
            height=data.get("height", 0),
            char_offset_start=data.get("char_offset_start", -1),
            char_offset_end=data.get("char_offset_end", -1),
        )

    def contains(self, x: float, y: float) -> bool:
        """检查点是否在此chunk区域内"""
        return (
            self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height
        )

    def overlaps(self, x: float, y: float, w: float, h: float) -> bool:
        """检查矩形是否与此chunk重叠"""
        return not (
            x > self.x + self.width
            or x + w < self.x
            or y > self.y + self.height
            or y + h < self.y
        )


class CoordinateMapper:
    """
    坐标映射器

    管理PDF页面坐标与RAG chunk之间的映射关系。

    Usage:
        mapper = CoordinateMapper()

        # 注册chunk位置
        mapper.register_chunks(doc_id, chunks_from_docling)

        # 根据PDF坐标查找chunk
        chunk_id = mapper.find_chunk_by_coordinate(doc_id, page=1, x=100, y=200)

        # 根据chunk_id获取渲染位置
        position = mapper.get_chunk_position(chunk_id)
    """

    def __init__(self):
        # doc_id -> List[ChunkPosition]
        self._doc_chunks: Dict[str, List[ChunkPosition]] = {}

        # chunk_id -> ChunkPosition (全局索引)
        self._chunk_index: Dict[str, ChunkPosition] = {}

        # page -> List[ChunkPosition] (按页面索引，加速查找)
        self._page_index: Dict[str, Dict[int, List[ChunkPosition]]] = {}

    def register_chunks(self, doc_id: str, chunks: List[Any]):
        """
        注册文档的chunk位置信息

        Args:
            doc_id: 文档ID
            chunks: TextChunk列表（来自Docling解析）
        """
        positions = []

        for chunk in chunks:
            # 提取位置信息
            page = getattr(chunk, "page_number", 1) or 1
            content = getattr(chunk, "content", "")

            # 尝试从不同位置获取bbox
            bbox = None
            if hasattr(chunk, "bbox"):
                bbox = chunk.bbox
            elif hasattr(chunk, "metadata") and chunk.metadata:
                bbox = getattr(chunk.metadata, "bbox", None)

            # 解析bbox
            if bbox:
                if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                    x, y, w, h = bbox[0], bbox[1], bbox[2], bbox[3]
                elif isinstance(bbox, dict):
                    x = bbox.get("x", 0)
                    y = bbox.get("y", 0)
                    w = bbox.get("width", bbox.get("w", 100))
                    h = bbox.get("height", bbox.get("h", 20))
                else:
                    x, y, w, h = 0, 0, 100, 20
            else:
                # 无 bbox 时使用估算位置；同时尝试从 metadata 取 character_offset 供前端 fallback
                x, y, w, h = 50, 50 + len(positions) * 25, 500, 20

            char_start = char_end = -1
            if hasattr(chunk, "metadata") and chunk.metadata:
                char_start = getattr(chunk.metadata, "char_offset_start", -1)
                char_end = getattr(chunk.metadata, "char_offset_end", -1)
            if isinstance(getattr(chunk, "metadata", None), dict):
                char_start = chunk.metadata.get("char_offset_start", -1)
                char_end = chunk.metadata.get("char_offset_end", -1)

            pos = ChunkPosition(
                chunk_id=chunk.chunk_id,
                doc_id=doc_id,
                page=page,
                x=x,
                y=y,
                width=w,
                height=h,
                text_content=content[:200],
                char_offset_start=char_start if isinstance(char_start, int) else -1,
                char_offset_end=char_end if isinstance(char_end, int) else -1,
            )

            positions.append(pos)
            self._chunk_index[chunk.chunk_id] = pos

        self._doc_chunks[doc_id] = positions

        # 构建页面索引
        if doc_id not in self._page_index:
            self._page_index[doc_id] = {}

        for pos in positions:
            if pos.page not in self._page_index[doc_id]:
                self._page_index[doc_id][pos.page] = []
            self._page_index[doc_id][pos.page].append(pos)

    def find_chunk_by_coordinate(
        self, doc_id: str, page: int, x: float, y: float
    ) -> Optional[str]:
        """
        根据PDF坐标查找chunk_id

        Args:
            doc_id: 文档ID
            page: 页码
            x, y: PDF坐标点

        Returns:
            chunk_id 或 None
        """
        if doc_id not in self._page_index:
            return None

        page_chunks = self._page_index[doc_id].get(page, [])

        for pos in page_chunks:
            if pos.contains(x, y):
                return pos.chunk_id

        return None

    def find_chunks_in_region(
        self, doc_id: str, page: int, x: float, y: float, width: float, height: float
    ) -> List[str]:
        """
        查找区域内的所有chunk_id

        Args:
            doc_id: 文档ID
            page: 页码
            x, y, width, height: 选择区域

        Returns:
            chunk_id列表
        """
        if doc_id not in self._page_index:
            return []

        page_chunks = self._page_index[doc_id].get(page, [])

        return [
            pos.chunk_id for pos in page_chunks if pos.overlaps(x, y, width, height)
        ]

    def get_chunk_position(self, chunk_id: str) -> Optional[ChunkPosition]:
        """
        根据chunk_id获取位置信息

        Args:
            chunk_id: Chunk ID

        Returns:
            ChunkPosition 或 None
        """
        return self._chunk_index.get(chunk_id)

    def get_doc_chunks(self, doc_id: str) -> List[ChunkPosition]:
        """
        获取文档的所有chunk位置

        Args:
            doc_id: 文档ID

        Returns:
            ChunkPosition列表
        """
        return self._doc_chunks.get(doc_id, [])

    def find_chunks_by_text(
        self, doc_id: str, text: str, page: int = None
    ) -> List[str]:
        """
        根据文本内容查找chunk（用于文本匹配验证）

        Args:
            doc_id: 文档ID
            text: 要匹配的文本
            page: 可选，限定页码

        Returns:
            匹配的chunk_id列表
        """
        if doc_id not in self._doc_chunks:
            return []

        text_lower = text.lower()
        matches = []

        chunks = (
            self._page_index[doc_id].get(page, [])
            if page and doc_id in self._page_index
            else self._doc_chunks[doc_id]
        )

        for pos in chunks:
            if text_lower in pos.text_content.lower():
                matches.append(pos.chunk_id)

        return matches

    def to_json(self, doc_id: str) -> str:
        """
        导出文档的坐标映射为JSON（用于前端）

        Args:
            doc_id: 文档ID

        Returns:
            JSON字符串
        """
        chunks = self._doc_chunks.get(doc_id, [])
        return json.dumps([c.to_dict() for c in chunks])

    def from_json(self, doc_id: str, json_str: str):
        """
        从JSON导入坐标映射

        Args:
            doc_id: 文档ID
            json_str: JSON字符串
        """
        data = json.loads(json_str)
        positions = [ChunkPosition.from_dict(d) for d in data]

        self._doc_chunks[doc_id] = positions

        for pos in positions:
            self._chunk_index[pos.chunk_id] = pos

            if doc_id not in self._page_index:
                self._page_index[doc_id] = {}
            if pos.page not in self._page_index[doc_id]:
                self._page_index[doc_id][pos.page] = []
            self._page_index[doc_id][pos.page].append(pos)

    def clear_doc(self, doc_id: str):
        """
        清除文档的坐标映射

        Args:
            doc_id: 文档ID
        """
        if doc_id in self._doc_chunks:
            for pos in self._doc_chunks[doc_id]:
                self._chunk_index.pop(pos.chunk_id, None)
            del self._doc_chunks[doc_id]

        if doc_id in self._page_index:
            del self._page_index[doc_id]


# 全局坐标映射器实例
_mapper: Optional[CoordinateMapper] = None


def get_coordinate_mapper() -> CoordinateMapper:
    """获取全局坐标映射器实例"""
    global _mapper
    if _mapper is None:
        _mapper = CoordinateMapper()
    return _mapper
