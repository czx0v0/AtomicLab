"""
Parse Result Models
===================
Docling解析后的文档结构数据模型
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime


@dataclass
class DocumentMetadata:
    """文档元数据"""

    author: Optional[str] = None
    created_date: Optional[str] = None
    modified_date: Optional[str] = None
    page_count: int = 0
    file_size: int = 0
    language: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedSection:
    """文档章节"""

    section_id: str
    heading: str
    level: int  # H1=1, H2=2, etc.
    content: str
    word_count: int = 0
    page_start: int = 0
    page_end: int = 0
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "section_id": self.section_id,
            "heading": self.heading,
            "level": self.level,
            "content": self.content,
            "word_count": self.word_count,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "parent_id": self.parent_id,
            "children_ids": self.children_ids,
        }


@dataclass
class ParsedTable:
    """表格结构 - 支持双重embedding策略"""

    table_id: str
    caption: str
    headers: List[str]
    rows: List[List[str]]
    markdown: str = ""  # Markdown格式
    html: str = ""  # HTML格式
    page_number: int = 0
    bbox: Optional[Tuple[float, float, float, float]] = None  # 边界框 (x1, y1, x2, y2)

    # 双重embedding支持
    semantic_text: str = ""  # 用于语义检索的文本描述
    structure_hash: str = ""  # 结构指纹用于去重

    def to_dict(self) -> dict:
        return {
            "table_id": self.table_id,
            "caption": self.caption,
            "headers": self.headers,
            "rows": self.rows,
            "markdown": self.markdown,
            "html": self.html,
            "page_number": self.page_number,
            "bbox": self.bbox,
            "semantic_text": self.semantic_text,
            "structure_hash": self.structure_hash,
        }


@dataclass
class ParsedFigure:
    """图片及描述"""

    figure_id: str
    caption: str
    image_path: Optional[str] = None  # 提取的图片本地路径
    page_number: int = 0
    bbox: Optional[Tuple[float, float, float, float]] = None

    def to_dict(self) -> dict:
        return {
            "figure_id": self.figure_id,
            "caption": self.caption,
            "image_path": self.image_path,
            "page_number": self.page_number,
            "bbox": self.bbox,
        }


@dataclass
class ParsedFormula:
    """公式"""

    formula_id: str
    content: str  # LaTeX格式
    page_number: int = 0
    bbox: Optional[Tuple[float, float, float, float]] = None

    def to_dict(self) -> dict:
        return {
            "formula_id": self.formula_id,
            "content": self.content,
            "page_number": self.page_number,
            "bbox": self.bbox,
        }


@dataclass
class ParsedDocument:
    """Docling解析后的完整文档结构"""

    doc_id: str
    title: str
    content: str  # Markdown格式全文
    sections: List[ParsedSection] = field(default_factory=list)
    tables: List[ParsedTable] = field(default_factory=list)
    figures: List[ParsedFigure] = field(default_factory=list)
    formulas: List[ParsedFormula] = field(default_factory=list)
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    parse_confidence: float = 1.0  # 解析置信度 0-1
    parse_time: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "content": self.content,
            "sections": [s.to_dict() for s in self.sections],
            "tables": [t.to_dict() for t in self.tables],
            "figures": [f.to_dict() for f in self.figures],
            "formulas": [f.to_dict() for f in self.formulas],
            "metadata": {
                "author": self.metadata.author,
                "created_date": self.metadata.created_date,
                "page_count": self.metadata.page_count,
                "keywords": self.metadata.keywords,
            },
            "parse_confidence": self.parse_confidence,
            "parse_time": self.parse_time.isoformat(),
        }

    def get_table_by_id(self, table_id: str) -> Optional[ParsedTable]:
        """根据ID获取表格"""
        for table in self.tables:
            if table.table_id == table_id:
                return table
        return None

    def get_section_by_heading(self, heading: str) -> Optional[ParsedSection]:
        """根据标题获取章节"""
        for section in self.sections:
            if section.heading == heading:
                return section
        return None
