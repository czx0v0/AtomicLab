"""
MinerU Parser
=============
基于MinerU (magic-pdf) 的高精度PDF解析器

特性:
- 90%+ 解析精度
- 自动OCR (84+语言)
- LaTeX公式输出
- 跨页表格合并
- 支持扫描PDF
"""

import hashlib
import os
from typing import List, Optional
from pathlib import Path

try:
    from magic_pdf.pipe.UNIPipe import UNIPipe

    MINERU_AVAILABLE = True
except ImportError:
    MINERU_AVAILABLE = False

from models.parse_result import (
    ParsedDocument,
    ParsedSection,
    ParsedTable,
    ParsedFigure,
    ParsedFormula,
    DocumentMetadata,
)


class MinerUParser:
    """基于MinerU的高精度PDF解析器

    相比Docling的优势:
    - 更高的解析精度 (90%+ vs 82-85%)
    - 自动OCR支持扫描PDF
    - 更好的公式识别 (LaTeX输出)
    - 跨页表格合并
    - 支持国产硬件 (昆仑芯/寒武纪)

    硬件需求:
    - CPU模式: 可运行但较慢
    - GPU模式: 推荐10GB+ VRAM
    """

    def __init__(self, parse_method: str = "auto"):
        """初始化MinerU解析器

        Args:
            parse_method: 解析方法
                - "auto": 自动选择OCR或文本提取
                - "ocr": 强制使用OCR
                - "txt": 强制使用文本提取
        """
        if not MINERU_AVAILABLE:
            raise ImportError(
                "MinerU未安装。请运行: pip install magic-pdf[full]\n"
                "GPU版本: pip install magic-pdf[full-gpu]"
            )
        self.parse_method = parse_method

    def parse(self, filepath: str, doc_id: Optional[str] = None) -> ParsedDocument:
        """解析PDF文档

        Args:
            filepath: PDF文件路径
            doc_id: 文档ID (可选)

        Returns:
            ParsedDocument: 解析后的文档结构
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"文件不存在: {filepath}")

        # 生成doc_id
        if doc_id is None:
            doc_id = self._generate_doc_id(filepath)

        print(f"[MinerU] 开始解析: {filepath}")

        # MinerU解析
        pipe = UNIPipe(filepath, parse_method=self.parse_method)

        # 获取Markdown内容
        md_content = pipe.get_markdown()

        # 获取结构化内容列表
        content_list = pipe.get_content_list()

        # 提取各元素
        sections = self._extract_sections(content_list, doc_id)
        tables = self._extract_tables(content_list, doc_id)
        figures = self._extract_figures(content_list, doc_id)
        formulas = self._extract_formulas(content_list, doc_id)

        # 提取元数据
        metadata = self._extract_metadata(filepath, content_list)

        # 计算解析置信度 (MinerU通常较高)
        confidence = self._calculate_confidence(content_list, tables)

        print(
            f"[MinerU] 解析完成: {len(sections)} 章节, {len(tables)} 表格, 置信度 {confidence:.2f}"
        )

        return ParsedDocument(
            doc_id=doc_id,
            title=metadata.extra.get("title", Path(filepath).stem),
            content=md_content,
            sections=sections,
            tables=tables,
            figures=figures,
            formulas=formulas,
            metadata=metadata,
            parse_confidence=confidence,
        )

    def parse_to_markdown(self, filepath: str) -> str:
        """快速转换为Markdown

        Args:
            filepath: PDF文件路径

        Returns:
            Markdown格式的内容
        """
        pipe = UNIPipe(filepath, parse_method=self.parse_method)
        return pipe.get_markdown()

    def _generate_doc_id(self, filepath: str) -> str:
        """生成文档ID"""
        return "DOC-" + hashlib.md5(filepath.encode()).hexdigest()[:8].upper()

    def _extract_sections(self, content_list: list, doc_id: str) -> List[ParsedSection]:
        """从MinerU内容列表提取章节"""
        sections = []

        for i, item in enumerate(content_list):
            if item.get("type") in ("text", "title", "header"):
                text = item.get("text", "")
                if not text.strip():
                    continue

                # 判断标题级别
                level = 2  # 默认H2
                if item.get("type") == "title":
                    level = 1
                elif item.get("type") == "header":
                    level = item.get("level", 2)

                section = ParsedSection(
                    section_id=f"{doc_id}-SEC-{i:03d}",
                    heading=text[:100] if level <= 2 else text[:50],
                    level=level,
                    content=text,
                    word_count=len(text.split()),
                    page_start=item.get("page", 0),
                    page_end=item.get("page", 0),
                )
                sections.append(section)

        return sections

    def _extract_tables(self, content_list: list, doc_id: str) -> List[ParsedTable]:
        """从MinerU内容列表提取表格"""
        tables = []

        for i, item in enumerate(content_list):
            if item.get("type") == "table":
                table_data = item.get("table_body", [])
                caption = item.get("caption", "")

                # 提取表头和行
                headers = table_data[0] if table_data else []
                rows = table_data[1:] if len(table_data) > 1 else []

                # 生成Markdown格式
                md_lines = []
                if headers:
                    md_lines.append("| " + " | ".join(str(h) for h in headers) + " |")
                    md_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
                for row in rows:
                    md_lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
                markdown = "\n".join(md_lines)

                table = ParsedTable(
                    table_id=f"{doc_id}-TBL-{i:03d}",
                    caption=caption,
                    headers=headers,
                    rows=rows,
                    markdown=markdown,
                    html=item.get("html", ""),
                    page_number=item.get("page", 0),
                    semantic_text=caption or f"表格: {markdown[:100]}",
                )
                tables.append(table)

        return tables

    def _extract_figures(self, content_list: list, doc_id: str) -> List[ParsedFigure]:
        """从MinerU内容列表提取图片"""
        figures = []

        for i, item in enumerate(content_list):
            if item.get("type") == "image":
                figure = ParsedFigure(
                    figure_id=f"{doc_id}-FIG-{i:03d}",
                    caption=item.get("caption", ""),
                    page_number=item.get("page", 0),
                    image_path=item.get("image_path", ""),
                )
                figures.append(figure)

        return figures

    def _extract_formulas(self, content_list: list, doc_id: str) -> List[ParsedFormula]:
        """从MinerU内容列表提取公式"""
        formulas = []

        for i, item in enumerate(content_list):
            if item.get("type") == "equation":
                formula = ParsedFormula(
                    formula_id=f"{doc_id}-EQ-{i:03d}",
                    content=item.get("latex", item.get("text", "")),
                    page_number=item.get("page", 0),
                )
                formulas.append(formula)

        return formulas

    def _extract_metadata(self, filepath: str, content_list: list) -> DocumentMetadata:
        """提取文档元数据"""
        stat = os.stat(filepath) if os.path.exists(filepath) else None

        return DocumentMetadata(
            page_count=(
                max(item.get("page", 0) for item in content_list) if content_list else 0
            ),
            file_size=stat.st_size if stat else 0,
            extra={
                "title": Path(filepath).stem,
                "parser": "mineru",
                "parse_method": self.parse_method,
            },
        )

    def _calculate_confidence(self, content_list: list, tables: list) -> float:
        """计算解析置信度

        MinerU通常有较高的置信度
        """
        if not content_list:
            return 0.5

        # 基于内容类型和数量估算
        text_items = sum(1 for item in content_list if item.get("type") == "text")
        table_items = len(tables)

        # 有表格说明解析较好
        if table_items > 0:
            return 0.92

        # 文本内容丰富
        if text_items > 10:
            return 0.90

        return 0.85
