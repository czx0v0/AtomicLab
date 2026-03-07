"""
Docling Parser
==============
基于Docling的高级PDF解析器
支持表格、图片、公式的提取和双重embedding策略
"""

import hashlib
import os
from typing import List, Optional
from pathlib import Path

try:
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.document import TableItem, PictureItem

    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False

from models.parse_result import (
    ParsedDocument,
    ParsedSection,
    ParsedTable,
    ParsedFigure,
    ParsedFormula,
    DocumentMetadata,
)


class DoclingParser:
    """
    基于Docling的高级PDF解析器

    特性:
    - Markdown格式导出
    - 表格结构化提取(支持双重embedding)
    - 图片和公式识别
    - 解析质量评估
    """

    def __init__(self):
        if not DOCLING_AVAILABLE:
            raise ImportError("Docling未安装。请运行: pip install docling>=2.0.0")

        self.converter = DocumentConverter()

    def parse(self, filepath: str, doc_id: Optional[str] = None) -> ParsedDocument:
        """
        解析文档

        Args:
            filepath: 文件路径
            doc_id: 文档ID(可选,默认从文件名生成)

        Returns:
            ParsedDocument: 解析后的文档结构
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"文件不存在: {filepath}")

        # 生成doc_id
        if doc_id is None:
            doc_id = self._generate_doc_id(filepath)

        # Docling转换
        result = self.converter.convert(filepath)
        doc = result.document

        # 导出Markdown
        markdown = doc.export_to_markdown()

        # 提取各元素
        sections = self._extract_sections(doc, doc_id)
        tables = self._extract_tables(doc, doc_id)
        figures = self._extract_figures(doc, doc_id)
        formulas = self._extract_formulas(doc, doc_id)

        # 提取元数据
        metadata = self._extract_metadata(doc, filepath)

        # 计算解析置信度
        confidence = self._calculate_confidence(doc, tables)

        return ParsedDocument(
            doc_id=doc_id,
            title=metadata.extra.get("title", Path(filepath).stem),
            content=markdown,
            sections=sections,
            tables=tables,
            figures=figures,
            formulas=formulas,
            metadata=metadata,
            parse_confidence=confidence,
        )

    def parse_to_markdown(self, filepath: str) -> str:
        """快速转换为Markdown"""
        result = self.converter.convert(filepath)
        return result.document.export_to_markdown()

    def _generate_doc_id(self, filepath: str) -> str:
        """从文件路径生成文档ID"""
        filename = os.path.basename(filepath)
        return "doc-" + hashlib.md5(filename.encode()).hexdigest()[:8].upper()

    def _extract_sections(self, doc, doc_id: str) -> List[ParsedSection]:
        """提取章节结构"""
        sections = []

        # 从文档结构中提取标题
        headings = []
        for item in doc.texts:
            if hasattr(item, "label") and item.label in [
                "section_header",
                "page_header",
            ]:
                headings.append(
                    {
                        "text": item.text,
                        "level": getattr(item, "level", 1),
                        "page": getattr(item, "page_number", 0),
                    }
                )

        # 构建章节结构
        for i, heading in enumerate(headings):
            section_id = f"{doc_id}_s{i:03d}"
            sections.append(
                ParsedSection(
                    section_id=section_id,
                    heading=heading["text"],
                    level=heading["level"],
                    content=heading["text"],  # 简化处理
                    page_start=heading["page"],
                    page_end=heading["page"],
                )
            )

        return sections

    def _extract_tables(self, doc, doc_id: str) -> List[ParsedTable]:
        """
        提取表格 - 实现双重embedding策略

        1. 结构hash用于精确匹配
        2. 语义文本用于相似性搜索
        """
        tables = []

        table_items = [item for item in doc.tables] if hasattr(doc, "tables") else []

        for i, table in enumerate(table_items):
            try:
                # 导出DataFrame (传入doc参数避免弃用警告)
                df = table.export_to_dataframe(doc=doc)

                # 导出Markdown和HTML
                markdown = table.export_to_markdown(doc=doc)
                html = table.export_to_html(doc=doc)

                # 生成语义描述文本
                semantic_text = self._generate_table_description(df, table)

                # 生成结构指纹
                structure_hash = self._hash_table_structure(df)

                tables.append(
                    ParsedTable(
                        table_id=f"{doc_id}_t{i:03d}",
                        caption=getattr(table, "caption", f"Table {i+1}"),
                        headers=list(df.columns),
                        rows=df.values.tolist(),
                        markdown=markdown,
                        html=html,
                        page_number=getattr(table, "page_number", 0),
                        semantic_text=semantic_text,
                        structure_hash=structure_hash,
                    )
                )
            except Exception as e:
                # 表格解析失败,记录但继续
                print(f"警告: 表格 {i} 解析失败: {e}")
                continue

        return tables

    def _extract_figures(self, doc, doc_id: str) -> List[ParsedFigure]:
        """提取图片"""
        figures = []

        picture_items = (
            [item for item in doc.pictures] if hasattr(doc, "pictures") else []
        )

        for i, pic in enumerate(picture_items):
            figures.append(
                ParsedFigure(
                    figure_id=f"{doc_id}_f{i:03d}",
                    caption=getattr(pic, "caption", f"Figure {i+1}"),
                    page_number=getattr(pic, "page_number", 0),
                )
            )

        return figures

    def _extract_formulas(self, doc, doc_id: str) -> List[ParsedFormula]:
        """提取公式"""
        formulas = []

        # Docling对公式的支持还在发展中
        # 这里预留接口

        return formulas

    def _extract_metadata(self, doc, filepath: str) -> DocumentMetadata:
        """提取文档元数据"""
        meta = DocumentMetadata()

        # 文件信息
        path = Path(filepath)
        if path.exists():
            meta.file_size = path.stat().st_size

        # 尝试从文档中提取
        if hasattr(doc, "metadata"):
            doc_meta = doc.metadata
            meta.author = getattr(doc_meta, "author", None)
            meta.page_count = getattr(doc_meta, "page_count", 0)
            meta.extra["title"] = getattr(doc_meta, "title", path.stem)

        return meta

    def _generate_table_description(self, df, table) -> str:
        """
        生成表格的语义描述用于embedding

        这是双重embedding策略的关键:
        - 结构hash用于精确匹配
        - 这段描述用于语义搜索
        """
        parts = []

        # 标题
        caption = getattr(table, "caption", "")
        if caption:
            parts.append(f"表格: {caption}")

        # 列描述
        headers = list(df.columns)
        parts.append(f"包含列: {', '.join(headers)}")

        # 数据概况
        parts.append(f"共{len(df)}行数据")

        # 数据样本(前3行)
        if len(df) > 0:
            sample_rows = []
            for idx, row in df.head(3).iterrows():
                row_desc = ", ".join(f"{k}={v}" for k, v in row.items())
                sample_rows.append(row_desc)
            parts.append(f"数据示例: {'; '.join(sample_rows)}")

        return ". ".join(parts)

    def _hash_table_structure(self, df) -> str:
        """
        生成表格结构指纹

        用于:
        1. 表格去重
        2. 精确匹配查询
        """
        # 使用列名和数据类型作为指纹
        cols = list(df.columns)
        dtypes = [str(dt) for dt in df.dtypes]
        row_count = len(df)

        fingerprint = f"{'|'.join(cols)}_{'|'.join(dtypes)}_{row_count}"
        return hashlib.md5(fingerprint.encode()).hexdigest()[:16]

    def _calculate_confidence(self, doc, tables: List[ParsedTable]) -> float:
        """
        计算文档解析置信度

        评估维度:
        - 文本提取质量
        - 表格解析成功率
        - 结构识别完整性
        """
        scores = []

        # 基础文本质量
        text_content = doc.export_to_markdown()
        if len(text_content) > 100:
            scores.append(0.9)
        else:
            scores.append(0.3)

        # 表格解析质量
        for table in tables:
            if table.headers and len(table.rows) > 0:
                # 检查表格完整性
                expected_cols = len(table.headers)
                consistent_rows = sum(
                    1 for row in table.rows if len(row) == expected_cols
                )
                if consistent_rows == len(table.rows):
                    scores.append(0.95)
                else:
                    scores.append(0.6)
            else:
                scores.append(0.2)

        return sum(scores) / len(scores) if scores else 0.5


# 兼容性函数 - 保持与旧版extract_pdf接口一致
def extract_pdf_advanced(filepath: str, doc_id: Optional[str] = None) -> ParsedDocument:
    """
    高级PDF提取函数

    这是core/utils.py中extract_pdf的高级版本
    保持兼容性的同时提供更强大的功能
    """
    parser = DoclingParser()
    return parser.parse(filepath, doc_id)
