"""
Docling Renderer Service
========================
将Docling解析的PDF转换为可交互的HTML视图。

Features:
- 结构化文档渲染（章节、段落、表格）
- 文本高亮和笔记集成
- 页码映射和导航
- 优雅降级（无Docling结果时显示原始文本）
"""

import re
import html
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path

# 尝试导入Docling模型
try:
    from models.parse_result import ParsedDocument, ParsedTable
    from models.chunk import TextChunk
    DOCLING_MODELS_AVAILABLE = True
except ImportError:
    DOCLING_MODELS_AVAILABLE = False


@dataclass
class RenderOptions:
    """渲染选项"""
    show_page_numbers: bool = True
    enable_highlighting: bool = True
    table_style: str = "grid"  # grid, simple, striped
    max_table_width: str = "100%"
    font_size: str = "14px"
    line_height: str = "1.8"


class DoclingRenderer:
    """
    Docling文档渲染器
    
    将ParsedDocument转换为交互式HTML，支持：
    - 章节层次结构
    - 表格渲染
    - 文本高亮
    - 页码导航
    """
    
    def __init__(self, options: Optional[RenderOptions] = None):
        self.options = options or RenderOptions()
        self.highlights: List[Dict] = []  # 当前高亮列表
    
    def set_highlights(self, highlights: List[Dict]):
        """设置要高亮显示的笔记/批注"""
        self.highlights = highlights
    
    def render(self, parsed_doc: Any, chunks: Optional[List] = None) -> str:
        """
        将ParsedDocument渲染为HTML
        
        Args:
            parsed_doc: ParsedDocument对象或包含解析结果的字典
            chunks: 可选的TextChunk列表，用于高亮映射
            
        Returns:
            HTML字符串
        """
        if not parsed_doc:
            return self._render_empty()
        
        # 处理字典类型的解析结果（从存储加载）
        if isinstance(parsed_doc, dict):
            return self._render_from_dict(parsed_doc)
        
        # 处理ParsedDocument对象
        if DOCLING_MODELS_AVAILABLE and hasattr(parsed_doc, 'title'):
            return self._render_parsed_document(parsed_doc)
        
        return self._render_empty()
    
    def _render_parsed_document(self, doc: Any) -> str:
        """渲染ParsedDocument对象"""
        html_parts = []
        
        # 文档头部
        html_parts.append(self._render_header(doc))
        
        # 章节内容
        if hasattr(doc, 'sections') and doc.sections:
            for section in doc.sections:
                html_parts.append(self._render_section(section))
        
        # 主内容（如果没有章节）
        elif hasattr(doc, 'content') and doc.content:
            html_parts.append(self._render_content_with_highlights(doc.content))
        
        # 表格
        if hasattr(doc, 'tables') and doc.tables:
            html_parts.append(self._render_tables_section(doc.tables))
        
        # 图片
        if hasattr(doc, 'figures') and doc.figures:
            html_parts.append(self._render_figures_section(doc.figures))
        
        # 页脚
        html_parts.append(self._render_footer(doc))
        
        return self._wrap_document("\n".join(html_parts))
    
    def _render_from_dict(self, data: Dict) -> str:
        """从字典渲染（用于存储的解析结果）"""
        html_parts = []
        
        # 标题
        title = data.get('title', '未命名文档')
        html_parts.append(f'<h1 class="doc-title">{html.escape(title)}</h1>')
        
        # 元数据
        if 'metadata' in data:
            html_parts.append(self._render_metadata(data['metadata']))
        
        # 内容
        content = data.get('content', '')
        if content:
            html_parts.append(self._render_content_with_highlights(content))
        
        # 表格
        tables = data.get('tables', [])
        if tables:
            html_parts.append('<h2>表格</h2>')
            for i, table in enumerate(tables):
                html_parts.append(self._render_table_from_dict(table, i))
        
        return self._wrap_document("\n".join(html_parts))
    
    def _render_header(self, doc: Any) -> str:
        """渲染文档头部"""
        title = getattr(doc, 'title', '未命名文档')
        
        header_html = f'''
        <div class="doc-header">
            <h1 class="doc-title">{html.escape(title)}</h1>
            {self._render_metadata(getattr(doc, 'metadata', None))}
        </div>
        '''
        return header_html
    
    def _render_metadata(self, metadata: Optional[Dict]) -> str:
        """渲染元数据信息"""
        if not metadata:
            return ''
        
        meta_items = []
        if 'authors' in metadata:
            meta_items.append(f'<span class="meta-item">作者: {html.escape(str(metadata["authors"]))}</span>')
        if 'doi' in metadata:
            meta_items.append(f'<span class="meta-item">DOI: {html.escape(str(metadata["doi"]))}</span>')
        if 'page_count' in metadata:
            meta_items.append(f'<span class="meta-item">页数: {metadata["page_count"]}</span>')
        
        if meta_items:
            return f'<div class="doc-metadata">{" | ".join(meta_items)}</div>'
        return ''
    
    def _render_section(self, section: Any) -> str:
        """渲染章节"""
        level = getattr(section, 'level', 1)
        heading = getattr(section, 'heading', '')
        content = getattr(section, 'content', '')
        page_num = getattr(section, 'page_number', None)
        
        # 限制标题级别
        level = max(1, min(6, level))
        
        section_html = f'''
        <section class="doc-section" data-page="{page_num or ''}">
            <h{level} class="section-heading">{html.escape(heading)}</h{level}>
            {self._render_content_with_highlights(content)}
        </section>
        '''
        return section_html
    
    def _render_content_with_highlights(self, content: str) -> str:
        """渲染内容并应用高亮"""
        if not content:
            return ''
        
        # 转义HTML
        escaped_content = html.escape(content)
        
        # 应用高亮
        if self.options.enable_highlighting and self.highlights:
            escaped_content = self._apply_highlights(escaped_content)
        
        # 将换行转换为段落
        paragraphs = escaped_content.split('\n\n')
        para_html = []
        for para in paragraphs:
            if para.strip():
                # 处理列表项
                if para.strip().startswith(('- ', '* ', '1. ', '2. ')):
                    para_html.append(self._render_list(para))
                else:
                    para_html.append(f'<p class="doc-paragraph">{para}</p>')
        
        return '\n'.join(para_html)
    
    def _render_list(self, text: str) -> str:
        """渲染列表"""
        lines = text.strip().split('\n')
        items = []
        
        for line in lines:
            line = line.strip()
            if line.startswith(('- ', '* ')):
                items.append(f'<li>{line[2:]}</li>')
            elif re.match(r'^\d+\.\s', line):
                items.append(f'<li>{re.sub(r"^\d+\.\s", "", line)}</li>')
        
        if items:
            return f'<ul class="doc-list">{ "".join(items) }</ul>'
        return f'<p>{text}</p>'
    
    def _apply_highlights(self, text: str) -> str:
        """应用高亮标记"""
        result = text
        
        # 按内容长度降序排序，避免重叠问题
        sorted_highlights = sorted(
            self.highlights,
            key=lambda h: len(h.get('content', '')),
            reverse=True
        )
        
        for hl in sorted_highlights:
            content = hl.get('content', '')
            color = hl.get('color', 'yellow')
            note_id = hl.get('id', '')
            
            if content and content in result:
                # 创建高亮标记
                mark_html = (
                    f'<mark class="hl-{color}" '
                    f'data-note-id="{note_id}" '
                    f'title="{html.escape(hl.get("annotation", ""))}"'
                    f'>{html.escape(content)}</mark>'
                )
                result = result.replace(html.escape(content), mark_html, 1)
        
        return result
    
    def _render_tables_section(self, tables: List) -> str:
        """渲染表格区域"""
        html_parts = ['<div class="tables-section"><h2>表格</h2>']
        
        for i, table in enumerate(tables):
            html_parts.append(self._render_table(table, i))
        
        html_parts.append('</div>')
        return '\n'.join(html_parts)
    
    def _render_table(self, table: Any, index: int) -> str:
        """渲染单个表格"""
        if hasattr(table, 'html') and table.html:
            # 使用Docling生成的HTML
            return self._clean_table_html(table.html, index)
        
        # 从DataFrame渲染
        headers = getattr(table, 'headers', [])
        rows = getattr(table, 'rows', [])
        caption = getattr(table, 'caption', f'Table {index + 1}')
        
        return self._build_table_html(headers, rows, caption)
    
    def _render_table_from_dict(self, table: Dict, index: int) -> str:
        """从字典渲染表格"""
        html_content = table.get('html', '')
        if html_content:
            return self._clean_table_html(html_content, index)
        
        headers = table.get('headers', [])
        rows = table.get('rows', [])
        caption = table.get('caption', f'Table {index + 1}')
        
        return self._build_table_html(headers, rows, caption)
    
    def _build_table_html(self, headers: List, rows: List, caption: str) -> str:
        """构建表格HTML"""
        # 表头
        header_html = ''
        if headers:
            header_cells = ''.join([f'<th>{html.escape(str(h))}</th>' for h in headers])
            header_html = f'<thead><tr>{header_cells}</tr></thead>'
        
        # 表体
        rows_html = ''
        for row in rows:
            cells = ''.join([f'<td>{html.escape(str(c))}</td>' for c in row])
            rows_html += f'<tr>{cells}</tr>'
        
        body_html = f'<tbody>{rows_html}</tbody>'
        
        return f'''
        <div class="table-wrapper">
            <div class="table-caption">{html.escape(str(caption))}</div>
            <table class="doc-table {self.options.table_style}">
                {header_html}
                {body_html}
            </table>
        </div>
        '''
    
    def _clean_table_html(self, html: str, index: int) -> str:
        """清理和美化Docling生成的表格HTML"""
        # 添加样式类
        html = html.replace('<table>', f'<table class="doc-table {self.options.table_style}">')
        return f'<div class="table-wrapper">{html}</div>'
    
    def _render_figures_section(self, figures: List) -> str:
        """渲染图片区域"""
        # 当前版本仅显示占位符
        return f'''
        <div class="figures-section">
            <h2>图片 ({len(figures)}个)</h2>
            <p class="text-muted">图片查看功能开发中...</p>
        </div>
        '''
    
    def _render_footer(self, doc: Any) -> str:
        """渲染文档页脚"""
        confidence = getattr(doc, 'parse_confidence', None)
        
        if confidence:
            return f'''
            <div class="doc-footer">
                <span class="parse-confidence">解析置信度: {confidence:.2%}</span>
            </div>
            '''
        return ''
    
    def _render_empty(self) -> str:
        """渲染空状态"""
        return self._wrap_document('''
        <div class="doc-empty">
            <p>暂无解析内容</p>
        </div>
        ''')
    
    def _wrap_document(self, content: str) -> str:
        """包装文档HTML"""
        return f'''
        <div class="docling-viewer" style="
            font-size: {self.options.font_size};
            line-height: {self.options.line_height};
        ">
            {content}
        </div>
        '''


def render_docling_view(
    parsed_doc: Any,
    highlights: Optional[List[Dict]] = None,
    chunks: Optional[List] = None,
    options: Optional[RenderOptions] = None
) -> str:
    """
    便捷函数：渲染Docling视图
    
    Args:
        parsed_doc: 解析后的文档对象
        highlights: 要高亮的笔记列表
        chunks: 文档chunks（可选）
        options: 渲染选项
        
    Returns:
        HTML字符串
    """
    renderer = DoclingRenderer(options)
    if highlights:
        renderer.set_highlights(highlights)
    return renderer.render(parsed_doc, chunks)
