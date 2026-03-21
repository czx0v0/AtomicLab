"""
Docling PDF Renderer
====================
将Docling解析结果渲染为可交互的HTML视图。

支持：
- Markdown/HTML结构化渲染
- 文本高亮和批注
- 表格美化显示
- 公式渲染
- 章节导航
"""

from .docling_renderer import DoclingRenderer, render_docling_view

__all__ = ["DoclingRenderer", "render_docling_view"]
