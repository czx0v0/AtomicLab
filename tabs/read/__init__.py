"""
Read Tab — UI builder and handlers
===================================
Tab 1: Upload PDFs, read extracted text, record notes.
       Single-page view with floating popup menu (WeChat Reading style).
       Highlight = auto-save note with annotation node support.
       Translate inline. Copy to clipboard.

v2.0 更新:
- 批注功能重写，支持 TreeNode(type="annotation")
- 支持 priority (1-5) 和颜色映射
- 批注作为章节/文档的子节点存储

v2.3 更新:
- 添加PDF.js高亮模式（保真渲染 + 高亮交互 + RAG分块）
- 三种阅读模式：文本模式、PDF原版、PDF高亮(RAG增强)
"""

import os
import time
import json
import gradio as gr

from core.utils import phash, extract_pdf, read_txt, esc, get_demo_data_path
from core.state import next_note_id
from agents.base import call_llm
from ui.renderers import (
    render_pdf_text,
    render_note_cards,
    render_annotation_cards,
    render_stats,
    get_total_pages,
)

# v2.2: Docling渲染器
try:
    from services.renderer import DoclingRenderer
    from ui.docling_styles import get_docling_styles
    from ui.docling_interactions import wrap_with_interactions

    DOCLING_RENDERER_AVAILABLE = True
except ImportError as e:
    print(f"[ReadTab] Docling渲染器不可用: {e}")
    DOCLING_RENDERER_AVAILABLE = False

# v2.3: PDF.js高亮渲染器
try:
    from services.renderer.pdfjs_viewer import PDFJSViewer, HighlightData, PDFCoordinate
    from services.renderer.coordinate_mapper import get_coordinate_mapper

    PDFJS_VIEWER_AVAILABLE = True
except ImportError as e:
    print(f"[ReadTab] PDF.js渲染器不可用: {e}")
    PDFJS_VIEWER_AVAILABLE = False

# 颜色到优先级映射
COLOR_PRIORITY_MAP = {
    "red": 5,  # 核心观点
    "orange": 4,  # 重要内容
    "yellow": 3,  # 值得注意
    "green": 2,  # 参考信息
    "purple": 1,  # 一般记录
    "blue": 1,
}


# ══════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════


def _render_file_list(lib: dict, active_pid: str = "") -> str:
    """Render clickable file list with RAG status indicators."""
    if not lib:
        return "<div class='nc-empty'>上传文献后显示</div>"
    h = ""
    for pid, info in lib.items():
        name = esc(info["name"])
        is_pdf = info.get("filepath", "").lower().endswith(".pdf")
        icon = "&#128196;" if is_pdf else "&#128221;"
        active_cls = " active" if pid == active_pid else ""

        # RAG状态指示器
        rag_status = ""
        if is_pdf:
            rag_indexed = info.get("rag_indexed", False)
            rag_processing = info.get("rag_processing", False)
            chunk_count = info.get("chunk_count", 0)
            rag_msg = info.get("rag_status", "")

            if rag_processing:
                rag_status = (
                    f'<span class="rag-status processing" title="{rag_msg}">⏳</span>'
                )
            elif rag_indexed:
                rag_status = f'<span class="rag-status indexed" title="已索引 {chunk_count} 个分块">✓{chunk_count}</span>'
            elif "失败" in rag_msg:
                rag_status = (
                    f'<span class="rag-status failed" title="{rag_msg}">❌</span>'
                )

        # Use JS to set hidden dropdown value
        h += (
            f"<div class='file-item{active_cls}' "
            f"onclick=\"setFileSelection('{pid}')\">"
            f"<span class='file-item-icon'>{icon}</span>"
            f"<span class='file-item-name'>{name}</span>"
            f"{rag_status}"
            f"</div>"
        )
    return f"<div class='file-list'>{h}</div>"


def _render_pdf_embed(pid: str, lib: dict) -> str:
    """Render original PDF via base64 data URL (avoids Gradio download header)."""
    if not pid or pid not in lib:
        return "<div class='txt-empty'>选择文献后，PDF 将在此显示</div>"
    fp = lib[pid].get("filepath", "")
    if not fp or not fp.lower().endswith(".pdf"):
        return "<div class='txt-empty'>非 PDF 文件，请切换到文本模式</div>"
    try:
        file_size_mb = os.path.getsize(fp) / (1024 * 1024)
    except OSError:
        file_size_mb = 0

    if file_size_mb > 20:
        return (
            f"<div class='txt-empty'>PDF 文件过大 ({file_size_mb:.1f} MB)，"
            f"建议使用文本模式阅读</div>"
        )

    import base64

    try:
        with open(fp, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
    except Exception as e:
        return f"<div class='txt-empty'>PDF 读取失败: {esc(str(e)[:80])}</div>"

    name = esc(lib[pid]["name"])
    data_url = f"data:application/pdf;base64,{b64}"
    return (
        f"<div style='text-align:center;padding:8px;'>"
        f"<p style='color:#718096;font-size:.82em;margin-bottom:6px;'>"
        f"{name} ({file_size_mb:.1f} MB)"
        f" &mdash; <em>高亮笔记请切换到文本模式</em></p>"
        f"<object data='{data_url}' type='application/pdf' "
        f"style='width:100%;height:700px;border:1px solid #e2e8f0;border-radius:8px;'>"
        f"<p style='padding:20px;color:#718096;'>浏览器无法预览 PDF，请切换到文本模式</p>"
        f"</object></div>"
    )


def _render_pdfjs_highlight_view(
    pid: str, lib: dict, notes: list = None, initial_page: int = 1
) -> str:
    """
    Render PDF with PDF.js - supports highlighting and RAG integration.

    v2.3: 统一的保真渲染 + 高亮交互模式
    initial_page: 打开时定位到的页码（用于跳转联动）
    """
    if not pid or pid not in lib:
        return "<div class='txt-empty'>选择文献后，PDF 将在此显示</div>"

    if not PDFJS_VIEWER_AVAILABLE:
        return "<div class='txt-empty'>PDF.js渲染器未安装，请使用文本模式或PDF原版模式</div>"

    doc_info = lib[pid]
    fp = doc_info.get("filepath", "")

    if not fp or not fp.lower().endswith(".pdf"):
        return "<div class='txt-empty'>非 PDF 文件，请切换到文本模式</div>"

    # 检查文件大小
    try:
        file_size_mb = os.path.getsize(fp) / (1024 * 1024)
    except OSError:
        file_size_mb = 0

    if file_size_mb > 30:
        return f"<div class='txt-empty'>PDF过大 ({file_size_mb:.1f}MB)，建议使用文本模式</div>"

    # 获取已有高亮笔记
    highlights = []
    if notes:
        for note in notes:
            if note.get("source_pid") == pid and note.get("type") in (
                "高亮",
                "highlight",
            ):
                coord_data = note.get("coordinate", {})
                rects_data = note.get("rects", [])

                # 构建coordinate对象
                coord = None
                if coord_data:
                    coord = PDFCoordinate(
                        page=coord_data.get("page", 1),
                        x=coord_data.get("x", 0),
                        y=coord_data.get("y", 0),
                        width=coord_data.get("width", 100),
                        height=coord_data.get("height", 20),
                    )

                highlights.append(
                    HighlightData(
                        highlight_id=note.get("id", ""),
                        doc_id=pid,
                        chunk_id=note.get("chunk_id", ""),
                        content=note.get("content", ""),
                        color=note.get("color", "yellow"),
                        annotation=note.get("annotation", ""),
                        coordinate=coord,
                        rects=rects_data if rects_data else None,
                    )
                )

    # 使用PDF.js渲染器（支持 initial_page 供全局跳转）
    viewer = PDFJSViewer()
    return viewer.render_viewer(
        pdf_path=fp,
        doc_id=pid,
        highlights=highlights,
        doc_name=doc_info.get("name", "未命名文档"),
        initial_page=max(1, initial_page),
    )


def _render_docling_view(pid: str, lib: dict, notes: list = None) -> str:
    """Render Docling parsed document view with interactive highlighting.

    v2.2: 使用Docling解析结果渲染结构化文档视图
    """
    if not pid or pid not in lib:
        return "<div class='txt-empty'>选择文献后，Docling视图将在此显示</div>"

    if not DOCLING_RENDERER_AVAILABLE:
        return "<div class='txt-empty'>Docling渲染器未安装</div>"

    # 检查是否有RAG解析结果
    doc_info = lib[pid]

    # 检查处理状态
    is_indexed = doc_info.get("rag_indexed", False)
    is_processing = doc_info.get("rag_processing", False)
    chunk_count = doc_info.get("chunk_count", 0)
    rag_status = doc_info.get("rag_status", "")

    # 如果正在处理中
    if is_processing:
        return f"""
        <div class='docling-status' style='padding: 40px; text-align: center; background: #f0f9ff; border-radius: 8px; margin: 20px;'>
            <div style='font-size: 48px; margin-bottom: 20px;'>⏳</div>
            <h3 style='color: #0369a1;'>Docling解析中...</h3>
            <p style='color: #4b5563;'>状态: {rag_status}</p>
            <p style='color: #718096; font-size: 14px;'>请稍后再试，或切换到"文本模式"查看</p>
            <div style='margin-top: 20px; padding: 10px; background: white; border-radius: 4px; font-size: 12px; color: #6b7280;'>
                💡 提示: 解析过程包括PDF提取→语义分块→向量索引，可能需要30-60秒
            </div>
        </div>
        """

    # 如果有状态但失败了（不全屏阅覆，展示警告条并回进基础文本）
    if rag_status and "失败" in rag_status:
        # 尝试展示基础文本内容而不是全屏错误
        basic_text = doc_info.get("text", "")
        warn_bar = f"""
        <div style='background:#fef3c7;border:1px solid #f59e0b;border-radius:6px;
          padding:8px 12px;margin-bottom:12px;font-size:.82em;color:#92400e;'>
          ⚠️ RAG解析失败（{rag_status.replace('❌ ','')})，以下显示基础文本。切换到“PDF高亮”模式可查看原始 PDF。
        </div>
        """
        if basic_text.strip():
            import html as _html

            paras = [p for p in basic_text.split("\n") if p.strip()]
            content_html = "".join(
                f"<p class='txt-para'>{_html.escape(p)}</p>" for p in paras[:200]
            )
            return f"<div class='txt-reader'>{warn_bar}{content_html}</div>"
        return f"""
        <div class='docling-status' style='padding:20px;text-align:center;background:#fef2f2;
          border-radius:8px;margin:20px;'>
          <div style='font-size:36px;margin-bottom:10px;'>⚠️</div>
          <p style='color:#dc2626;font-weight:600;'>{rag_status}</p>
          <p style='color:#6b7280;font-size:.84em;'>请切换到“PDF高亮”模式查看原始PDF。</p>
        </div>
        """
    if chunk_count > 0 and not is_indexed:
        return f"""
        <div class='docling-status' style='padding: 40px; text-align: center; background: #f0f9ff; border-radius: 8px; margin: 20px;'>
            <div style='font-size: 48px; margin-bottom: 20px;'>⏳</div>
            <h3 style='color: #0369a1;'>Docling索引中...</h3>
            <p style='color: #4b5563;'>已生成 {chunk_count} 个文本块，正在建立索引</p>
            <p style='color: #718096; font-size: 14px;'>请稍后再试，或切换到"文本模式"查看</p>
        </div>
        """

    # 尝试从RAG服务获取解析结果
    try:
        from services.rag_service import get_rag_service
        from core.config import RAG_CONFIG

        # 使用全局RAG服务实例
        rag_service = get_rag_service(RAG_CONFIG)

        # 如果文档已索引，尝试获取chunks
        if is_indexed:
            # 获取文档的chunks
            chunks = []
            if hasattr(rag_service, "doc_chunks") and pid in rag_service.doc_chunks:
                chunk_ids = rag_service.doc_chunks[pid]
                for chunk_id in chunk_ids:
                    if chunk_id in rag_service.chunk_store:
                        chunks.append(rag_service.chunk_store[chunk_id])

            if not chunks:
                # 已标记为indexed但chunks不在内存中，可能是重启后
                return f"""
                <div class='docling-status' style='padding: 40px; text-align: center;'>
                    <div style='font-size: 48px; margin-bottom: 20px;'>🔄</div>
                    <h3>索引需要重新加载</h3>
                    <p>文档已解析（{chunk_count} chunks），但索引不在内存中</p>
                    <p style='color: #718096; font-size: 14px;'>请重新上传PDF或切换到"文本模式"</p>
                </div>
                """

            # 构建ParsedDocument-like结构
            if chunks:
                # 按chunk_index排序，保持文档顺序
                sorted_chunks = sorted(
                    chunks,
                    key=lambda c: (
                        c.metadata.chunk_index
                        if c.metadata and hasattr(c.metadata, "chunk_index")
                        else 0
                    ),
                )

                # 构建内容，保留段落结构
                content_parts = []
                for chunk in sorted_chunks:
                    if chunk.chunk_type in ("paragraph", "semantic", "section", "text"):
                        content_parts.append(chunk.content)

                parsed_data = {
                    "title": doc_info.get("name", "未命名文档"),
                    "content": "\n\n".join(content_parts),
                    "tables": [],
                    "metadata": {
                        "page_count": doc_info.get("chunk_count", 0),
                        "parse_confidence": doc_info.get("parse_confidence", 0.8),
                    },
                }

                # 收集表格 - 从所有chunks中找表格数据
                for chunk in sorted_chunks:
                    if chunk.chunk_type in ("table_semantic", "table_row"):
                        if hasattr(chunk, "table_data") and chunk.table_data:
                            parsed_data["tables"].append(
                                {
                                    "html": (
                                        chunk.content
                                        if chunk.content.startswith("<table")
                                        else f"<table><tr><td>{chunk.content}</td></tr></table>"
                                    ),
                                    "caption": (
                                        f"Table from page {chunk.page_number}"
                                        if chunk.page_number
                                        else "Table"
                                    ),
                                }
                            )
                        elif hasattr(chunk, "metadata") and chunk.metadata:
                            table_data = getattr(chunk.metadata, "table_data", None)
                            if table_data:
                                parsed_data["tables"].append(table_data)

                # 准备高亮
                highlights = []
                if notes:
                    for note in notes:
                        if note.get("source_pid") == pid and note.get("type") == "高亮":
                            highlights.append(
                                {
                                    "id": note.get("id", ""),
                                    "content": note.get("content", ""),
                                    "color": note.get("color", "yellow"),
                                    "annotation": note.get("annotation", ""),
                                    "page": note.get("page", 1),
                                }
                            )

                # 渲染
                renderer = DoclingRenderer()
                renderer.set_highlights(highlights)
                html_content = renderer.render(parsed_data)

                # 包装交互功能
                return wrap_with_interactions(html_content)

    except Exception as e:
        print(f"[DoclingView] 渲染失败: {e}")

    # 降级到普通文本
    return (
        "<div class='txt-empty'>Docling解析结果不可用，请先上传PDF并等待解析完成</div>"
    )


def _render_docling_structure_view(pid: str, lib: dict, notes: list = None) -> str:
    """Render parser structure view showing hierarchical sections.

    v2.5: 优先使用解析器原生章节（MinerU/Docling），避免模糊匹配章节。
    """
    if not pid or pid not in lib:
        return "<div class='txt-empty'>选择文献后，Docling结构将在此显示</div>"

    doc_info = lib[pid]

    # 检查处理状态
    is_indexed = doc_info.get("rag_indexed", False)
    is_processing = doc_info.get("rag_processing", False)
    chunk_count = doc_info.get("chunk_count", 0)
    rag_status = doc_info.get("rag_status", "")

    # 如果正在处理中
    if is_processing:
        return f"""
        <div class='docling-status' style='padding: 40px; text-align: center; background: #f0f9ff; border-radius: 8px; margin: 20px;'>
            <div style='font-size: 48px; margin-bottom: 20px;'>⏳</div>
            <h3 style='color: #0369a1;'>Docling解析中...</h3>
            <p style='color: #4b5563;'>状态: {rag_status}</p>
            <p style='color: #718096; font-size: 14px;'>请稍后再试，或切换到"文本模式"查看</p>
        </div>
        """

    # 如果有状态但失败了
    if rag_status and "失败" in rag_status:
        return f"""
        <div class='docling-status' style='padding: 20px; text-align: center; background: #fef2f2;
          border-radius: 8px; margin: 20px;'>
          <div style='font-size: 36px; margin-bottom: 10px;'>⚠️</div>
          <p style='color: #dc2626; font-weight:600;'>{rag_status}</p>
          <p style='color: #718096; font-size: .84em;'>切换到“PDF高亮”模式可查看原始PDF</p>
        </div>
        """
    try:
        from services.rag_service import get_rag_service
        from core.config import RAG_CONFIG
        from ui.renderers import render_docling_structure

        # 使用全局RAG服务实例
        rag_service = get_rag_service(RAG_CONFIG)

        # 优先使用解析器原生结果（避免基于chunk的模糊章节推断）
        parsed_doc = None
        if hasattr(rag_service, "get_parsed_document"):
            parsed_doc = rag_service.get_parsed_document(pid)

        chunks = []
        if hasattr(rag_service, "doc_chunks") and pid in rag_service.doc_chunks:
            chunk_ids = rag_service.doc_chunks[pid]
            for chunk_id in chunk_ids:
                if chunk_id in rag_service.chunk_store:
                    chunks.append(rag_service.chunk_store[chunk_id])

        if parsed_doc:
            parsed_data = {
                "title": parsed_doc.title or doc_info.get("name", "未命名文档"),
                "content": parsed_doc.content,
                "sections": [s.to_dict() for s in parsed_doc.sections],
                "metadata": {
                    "page_count": parsed_doc.metadata.page_count,
                    "parse_confidence": parsed_doc.parse_confidence,
                    "parser": parsed_doc.metadata.extra.get("parser", "unknown"),
                },
            }
            return render_docling_structure(
                parsed_data=parsed_data,
                chunks=chunks,
                doc_name=doc_info.get("name", ""),
            )

        if is_indexed and chunks:
            # 降级：无解析缓存时，按chunk元数据构造最小结构
            parsed_data = {
                "title": doc_info.get("name", "未命名文档"),
                "content": "\n\n".join(
                    c.content for c in chunks if hasattr(c, "content")
                ),
                "sections": [],
                "metadata": {
                    "page_count": chunk_count,
                    "parse_confidence": doc_info.get("parse_confidence", 0.8),
                },
            }
            return render_docling_structure(
                parsed_data=parsed_data,
                chunks=chunks,
                doc_name=doc_info.get("name", ""),
            )

        if is_indexed:
            return f"""
            <div class='docling-status' style='padding: 40px; text-align: center;'>
                <div style='font-size: 48px; margin-bottom: 20px;'>🔄</div>
                <h3>索引需要重新加载</h3>
                <p>文档已解析（{chunk_count} chunks），但索引不在内存中</p>
                <p style='color: #718096; font-size: 14px;'>请重新上传PDF或切换到"文本模式"</p>
            </div>
            """

    except Exception as e:
        print(f"[DoclingStructureView] 渲染失败: {e}")
        import traceback

        traceback.print_exc()

    # 降级提示
    return (
        "<div class='txt-empty'>Docling结构视图不可用，请先上传PDF并等待解析完成</div>"
    )


def _render_mineru_markdown_view(pid: str, lib: dict) -> str:
    """Render MinerU Markdown view.

    直接显示MinerU解析得到的Markdown，避免回退到旧文本模式观感。
    """
    if not pid or pid not in lib:
        return "<div class='txt-empty'>选择文献后，MinerU Markdown将在此显示</div>"

    doc_info = lib[pid]
    is_processing = doc_info.get("rag_processing", False)
    rag_status = doc_info.get("rag_status", "")

    if is_processing:
        return f"""
        <div class='docling-status' style='padding: 40px; text-align: center; background: #f0f9ff; border-radius: 8px; margin: 20px;'>
            <div style='font-size: 48px; margin-bottom: 20px;'>⏳</div>
            <h3 style='color: #0369a1;'>MinerU解析中...</h3>
            <p style='color: #4b5563;'>状态: {rag_status}</p>
            <p style='color: #718096; font-size: 14px;'>请稍后再试</p>
        </div>
        """

    try:
        from services.rag_service import get_rag_service
        from core.config import RAG_CONFIG

        rag_service = get_rag_service(RAG_CONFIG)
        parsed_doc = None
        if hasattr(rag_service, "get_parsed_document"):
            parsed_doc = rag_service.get_parsed_document(pid)

        if not parsed_doc:
            return "<div class='txt-empty'>当前会话未找到MinerU解析缓存，请重新上传该PDF后查看Markdown模式</div>"

        parser_name = parsed_doc.metadata.extra.get("parser", "unknown")
        markdown_text = parsed_doc.content or ""
        if not markdown_text.strip():
            return "<div class='txt-empty'>MinerU未返回Markdown内容</div>"

        # 轻量Markdown显示：保留换行与标题语义，避免依赖额外库
        import re as _re

        _img_re = _re.compile(r"!\[([^\]]*)\]\([^\)]*\)")

        def _render_line(raw_line: str) -> str:
            """将单行Markdown渲染为HTML片段（含图片占位符）。"""
            stripped = raw_line.lstrip()
            # 图片语法 ![alt](path) — 渲染为行内占位符（本地路径浏览器无法访问）
            if _img_re.search(stripped):
                parts = []
                last = 0
                for m in _img_re.finditer(stripped):
                    if m.start() > last:
                        parts.append(esc(stripped[last : m.start()]))
                    alt = esc(m.group(1)) if m.group(1) else "图片"
                    parts.append(
                        f'<span style="display:inline-block;background:#f3f4f6;'
                        f"border:1px solid #d1d5db;border-radius:6px;padding:2px 10px;"
                        f'color:#6b7280;font-size:13px;">🖼 {alt}</span>'
                    )
                    last = m.end()
                if last < len(stripped):
                    parts.append(esc(stripped[last:]))
                return f"<p>{''.join(parts)}</p>"
            line = esc(raw_line)
            if stripped.startswith("###### "):
                return f"<h6>{esc(stripped[7:])}</h6>"
            elif stripped.startswith("##### "):
                return f"<h5>{esc(stripped[6:])}</h5>"
            elif stripped.startswith("#### "):
                return f"<h4>{esc(stripped[5:])}</h4>"
            elif stripped.startswith("### "):
                return f"<h3>{esc(stripped[4:])}</h3>"
            elif stripped.startswith("## "):
                return f"<h2>{esc(stripped[3:])}</h2>"
            elif stripped.startswith("# "):
                return f"<h1>{esc(stripped[2:])}</h1>"
            elif stripped == "":
                return "<div style='height:10px;'></div>"
            else:
                return f"<p>{line}</p>"

        body_html = "\n".join(_render_line(ln) for ln in markdown_text.splitlines())
        return f"""
        <div class='mineru-md-wrap' style='padding:16px 20px;'>
            <div style='margin-bottom:12px;color:#4b5563;font-size:13px;'>
                解析器: <b>{esc(parser_name)}</b> | 置信度: <b>{parsed_doc.parse_confidence:.2f}</b>
            </div>
            <div class='mineru-md-body' style='line-height:1.8;font-size:15px;'>
                {body_html}
            </div>
        </div>
        """
    except Exception as e:
        print(f"[MinerUMarkdownView] 渲染失败: {e}")
        return "<div class='txt-empty'>MinerU Markdown视图渲染失败，请查看日志</div>"


def _get_mineru_raw_markdown(pid: str, lib: dict) -> str:
    """返回当前文献的 MinerU 原始 Markdown，供 gr.Markdown 渲染（含 LaTeX）。"""
    if not pid or pid not in lib:
        return ""
    try:
        from services.rag_service import get_rag_service
        from core.config import RAG_CONFIG

        rag_service = get_rag_service(RAG_CONFIG)
        parsed_doc = None
        if hasattr(rag_service, "get_parsed_document"):
            parsed_doc = rag_service.get_parsed_document(pid)
        if not parsed_doc or not (parsed_doc.content or "").strip():
            return ""
        return (parsed_doc.content or "").strip()
    except Exception:
        return ""


def _render_chunk_database_view(pid: str, lib: dict) -> str:
    """Render chunk database view showing text chunks.

    v2.4: 分块数据库显示模式
    - 显示文本分块数据库
    - 展示分块层级关系
    - 按章节分组显示
    """
    if not pid or pid not in lib:
        return "<div class='txt-empty'>选择文献后，分块数据库将在此显示</div>"

    doc_info = lib[pid]

    # 检查处理状态
    is_indexed = doc_info.get("rag_indexed", False)
    is_processing = doc_info.get("rag_processing", False)
    chunk_count = doc_info.get("chunk_count", 0)
    rag_status = doc_info.get("rag_status", "")

    # 如果正在处理中
    if is_processing:
        return f"""
        <div class='docling-status' style='padding: 40px; text-align: center; background: #f0f9ff; border-radius: 8px; margin: 20px;'>
            <div style='font-size: 48px; margin-bottom: 20px;'>⏳</div>
            <h3 style='color: #0369a1;'>文本分块处理中...</h3>
            <p style='color: #4b5563;'>状态: {rag_status}</p>
            <p style='color: #718096; font-size: 14px;'>请稍后再试</p>
        </div>
        """

    # 如果有状态但失败了
    if rag_status and "失败" in rag_status:
        return f"""
        <div class='docling-status' style='padding: 40px; text-align: center; background: #fef2f2; border-radius: 8px; margin: 20px;'>
            <div style='font-size: 48px; margin-bottom: 20px;'>❌</div>
            <h3 style='color: #dc2626;'>分块处理失败</h3>
            <p style='color: #4b5563;'>{rag_status}</p>
            <p style='color: #718096; font-size: 14px;'>请重新上传PDF</p>
        </div>
        """

    # 尝试从RAG服务获取chunks
    try:
        from services.rag_service import get_rag_service
        from core.config import RAG_CONFIG
        from ui.renderers import render_chunk_database_tree

        # 使用全局RAG服务实例
        rag_service = get_rag_service(RAG_CONFIG)

        # 如果文档已索引，尝试获取chunks
        if is_indexed:
            # 获取文档的chunks
            chunks = []
            if hasattr(rag_service, "doc_chunks") and pid in rag_service.doc_chunks:
                chunk_ids = rag_service.doc_chunks[pid]
                for chunk_id in chunk_ids:
                    if chunk_id in rag_service.chunk_store:
                        chunks.append(rag_service.chunk_store[chunk_id])

            if not chunks:
                # 已标记为indexed但chunks不在内存中
                return f"""
                <div class='docling-status' style='padding: 40px; text-align: center;'>
                    <div style='font-size: 48px; margin-bottom: 20px;'>🔄</div>
                    <h3>索引需要重新加载</h3>
                    <p>文档已解析（{chunk_count} chunks），但索引不在内存中</p>
                    <p style='color: #718096; font-size: 14px;'>请重新上传PDF</p>
                </div>
                """

            # 渲染分块数据库视图
            return render_chunk_database_tree(
                chunks=chunks,
                doc_name=doc_info.get("name", ""),
            )

    except Exception as e:
        print(f"[ChunkDatabaseView] 渲染失败: {e}")
        import traceback

        traceback.print_exc()

    # 降级提示
    return (
        "<div class='txt-empty'>分块数据库视图不可用，请先上传PDF并等待解析完成</div>"
    )


# ══════════════════════════════════════════════════════════════
# HANDLERS
# ══════════════════════════════════════════════════════════════


def handle_upload(files, lib, stats, tree, rag_service=None):
    """Handle file upload — also auto-creates knowledge tree nodes.

    v2.1: 集成RAG服务，自动进行高级PDF解析和向量化索引

    Returns tuple including gr.update(value=None) for upload_f to clear it after processing.
    """
    if not files:
        return (
            lib,
            stats,
            gr.update(),
            render_stats(stats),
            render_pdf_text(None, lib),
            1,
            _render_file_list(lib),
            tree,
            gr.update(),  # Don't clear upload_f if no files
        )

    for f in files:
        fp = f if isinstance(f, str) else (f.name if hasattr(f, "name") else str(f))
        fn = os.path.basename(fp)
        pid = phash(fn)

        if pid in lib:
            continue

        text = extract_pdf(fp) if fp.lower().endswith(".pdf") else read_txt(fp)
        lib[pid] = {
            "name": fn,
            "text": text,
            "notes": [],
            "annotations": [],  # v2.0: 存储批注节点数据
            "filepath": fp,
            "rag_indexed": False,  # v2.1: RAG索引状态
        }
        stats["docs"] += 1

        # Auto-create knowledge tree: domain → document node
        domain_label = "研究文献"
        domain_node = tree.find_domain_node(domain_label)
        if not domain_node:
            domain_node = tree.create_domain_node(domain_label, pid)
        doc_node = tree.find_document_node(pid)
        if not doc_node:
            tree.create_document_node(fn, pid, domain_node.id)
        stats["nodes"] = len(tree.nodes)

        # v2.1: RAG高级解析和索引 (异步处理，不阻塞UI)
        if rag_service and fp.lower().endswith(".pdf"):
            # 先标记为处理中状态
            lib[pid]["rag_processing"] = True
            lib[pid]["rag_status"] = "📋 解析中..."
            lib[pid]["rag_progress"] = 0  # 进度百分比

            try:
                import threading

                def process_with_rag():
                    try:
                        print(f"[RAG] 开始处理: {fn}")
                        lib[pid]["rag_status"] = "📄 PDF提取中..."
                        lib[pid]["rag_progress"] = 10

                        result = rag_service.process_document(fp, pid)

                        if result.success:
                            lib[pid]["rag_progress"] = 90
                            lib[pid]["rag_status"] = "🔍 建立索引中..."

                            lib[pid]["rag_indexed"] = True
                            lib[pid]["rag_processing"] = False
                            lib[pid]["rag_status"] = "✅ 已完成"
                            lib[pid]["chunk_count"] = result.chunk_count
                            lib[pid]["parse_confidence"] = result.confidence
                            lib[pid]["rag_progress"] = 100
                            print(f"[RAG] 完成: {fn} ({result.chunk_count} chunks)")

                            # 创建section节点（章节信息同步到知识树）
                            if result.sections:
                                doc_node = tree.find_document_node(pid)
                                if doc_node:
                                    for sec_data in result.sections:
                                        section_node = tree.create_section_node(
                                            section_heading=sec_data.get(
                                                "heading", "未知章节"
                                            ),
                                            source_pid=pid,
                                            doc_node_id=doc_node.id,
                                            level=sec_data.get("level", 2),
                                            page_start=sec_data.get("page_start"),
                                            page_end=sec_data.get("page_end"),
                                        )
                                        # 添加章节摘要到metadata
                                        if sec_data.get("summary"):
                                            section_node.metadata["summary"] = sec_data[
                                                "summary"
                                            ]
                                    print(
                                        f"[RAG] 创建 {len(result.sections)} 个章节节点"
                                    )
                        else:
                            lib[pid]["rag_processing"] = False
                            lib[pid]["rag_status"] = f"❌ 失败: {result.error[:30]}"
                            lib[pid]["rag_progress"] = 0
                            print(f"[RAG] 失败: {fn} - {result.error}")
                    except Exception as e:
                        lib[pid]["rag_processing"] = False
                        lib[pid]["rag_status"] = f"❌ 异常: {str(e)[:30]}"
                        lib[pid]["rag_progress"] = 0
                        print(f"[RAG] 异常: {fn} - {e}")

                # 在后台线程中处理，避免阻塞UI
                thread = threading.Thread(target=process_with_rag)
                thread.daemon = True
                thread.start()
            except Exception as e:
                lib[pid]["rag_processing"] = False
                lib[pid]["rag_status"] = f"❌ 启动失败: {str(e)[:30]}"
                lib[pid]["rag_progress"] = 0
                print(f"[RAG] 启动失败: {fn} - {e}")

    last_pid = list(lib.keys())[-1] if lib else None

    return (
        lib,
        stats,
        gr.update(value=last_pid or ""),
        render_stats(stats),
        render_pdf_text(last_pid, lib, 1),
        1,
        _render_file_list(lib, last_pid),
        tree,
        gr.update(value=None),  # Clear upload_f after processing
    )


def handle_load_demo(lib, stats, notes, tree, rag_service=None, view_mode=None):
    """
    加载静态 Demo 数据（秒开体验）。

    行为：
    - 从 demo_data/ 目录读取:
      - demo_paper.pdf (原始文档，仅供渲染使用)
      - mock_library.json (lib / stats 等状态)
      - mock_notes.json (notes 状态)
    - 绝不调用 RAG 解析或 embedding，仅通知 rag_service
      从 demo_data/faiss_index/ 加载现有索引
    - view_mode: 当前阅读模式，用于全量刷新 pdf_text/html、pdf_embed、mineru_markdown 三块视图
    """
    try:
        demo_dir = get_demo_data_path()
        lib_path = demo_dir / "mock_library.json"
        notes_path = demo_dir / "mock_notes.json"

        if not lib_path.exists():
            print(f"[Demo] mock_library.json 不存在于 {lib_path}，使用内存 Mock 数据。")
            # 最小化内存 Mock，防止 UI 崩溃，同时不触发任何解析。
            mock_lib = {
                "DEMO-MOCK": {
                    "name": "Demo (No Data)",
                    "text": "Mock 数据未生成，请先在本地运行 scripts/generate_demo_mock.py。",
                    "notes": [],
                    "annotations": [],
                    "filepath": "",
                    "rag_indexed": False,
                }
            }
            mock_stats = {
                "docs": 1,
                "notes": 0,
                "nodes": len(tree.nodes) if tree else 0,
            }
            active_pid = "DEMO-MOCK"
            page = 1
            file_list_html = _render_file_list(mock_lib, active_pid)
            txt_upd, embed_upd, mineru_upd = handle_mode_switch(
                view_mode or "PDF高亮", active_pid, mock_lib, page, []
            )
            if txt_upd.get("visible", False):
                txt_upd = gr.update(value=render_pdf_text(active_pid, mock_lib, page), visible=True)
            return (
                mock_lib,
                mock_stats,
                [],  # notes
                tree,
                gr.update(value=active_pid),
                render_stats(mock_stats),
                txt_upd,
                page,
                file_list_html,
                gr.update(),  # upload_f
                embed_upd,
                mineru_upd,
            )

        with open(lib_path, "r", encoding="utf-8") as f:
            lib_data = json.load(f)

        if notes_path.exists():
            with open(notes_path, "r", encoding="utf-8") as f:
                notes_data = json.load(f)
        else:
            notes_data = []

        new_lib = lib_data.get("lib", lib_data if isinstance(lib_data, dict) else {})
        new_stats = lib_data.get("stats", stats or {"docs": 0, "notes": 0, "nodes": 0})
        new_notes = notes_data if isinstance(notes_data, list) else notes

        # 规范化 filepath，避免 mock 数据中残留 Windows 绝对路径在 Linux 环境下失效
        for doc_id, info in new_lib.items():
            fp = info.get("filepath", "")
            name = info.get("name", "")
            # 如果 filepath 不存在或是明显的 Windows 盘符路径，则尝试用 demo_data 目录重建
            if (isinstance(fp, str) and fp and not os.path.exists(fp)) or (
                isinstance(fp, str) and len(fp) >= 2 and fp[1] == ":"
            ):
                candidate = demo_dir / name if name else demo_dir / "demo_paper.pdf"
                if candidate.exists():
                    info["filepath"] = str(candidate.resolve())

        # 若 stats 中未包含 docs/notes 统计，可基于数据补全
        if isinstance(new_stats, dict):
            new_stats.setdefault("docs", len(new_lib))
            new_stats.setdefault("notes", len(new_notes))

        # 选取第一个文献作为当前激活文献
        active_pid = next(iter(new_lib.keys())) if new_lib else ""
        page = 1
        file_list_html = _render_file_list(new_lib, active_pid)
        # 按当前 view_mode 全量刷新三块视图（文本/PDF嵌入/分块数据库/MinerU Markdown）
        txt_upd, embed_upd, mineru_upd = handle_mode_switch(
            view_mode or "PDF高亮", active_pid, new_lib, page, new_notes
        )
        if txt_upd.get("visible", False):
            txt_upd = gr.update(value=render_pdf_text(active_pid or None, new_lib, page), visible=True)

        # 尝试让 RAG 服务从 demo_data/faiss_index 目录加载现成索引，
        # 并将 ParsedDocument 恢复到 RAGService 的内存缓存中，避免“索引不在内存中”提示。
        try:
            from services.rag_service import load_demo_index_from_path, get_rag_service
            from core.config import RAG_CONFIG
            from models.parse_result import (
                ParsedDocument,
                ParsedSection,
                ParsedTable,
                ParsedFigure,
                ParsedFormula,
                DocumentMetadata,
            )

            # 加载向量索引
            load_demo_index_from_path(str(demo_dir / "faiss_index"))

            # 恢复 ParsedDocument 到全局 RAG 服务
            service = rag_service or get_rag_service(RAG_CONFIG)
            if service is not None:
                for doc_id, info in new_lib.items():
                    pd_data = info.get("parsed_document")
                    if not pd_data:
                        continue

                    meta_raw = pd_data.get("metadata", {}) or {}
                    metadata = DocumentMetadata(
                        page_count=meta_raw.get("page_count", 0),
                        keywords=meta_raw.get("keywords", []),
                        extra={
                            "title": info.get(
                                "name", meta_raw.get("title", doc_id)
                            ),
                            "parser": "mineru_cloud_demo",
                        },
                    )

                    sections = [
                        ParsedSection(**s_dict)
                        for s_dict in pd_data.get("sections", []) or []
                    ]
                    tables = [
                        ParsedTable(**t_dict)
                        for t_dict in pd_data.get("tables", []) or []
                    ]
                    figures = [
                        ParsedFigure(**f_dict)
                        for f_dict in pd_data.get("figures", []) or []
                    ]
                    formulas = [
                        ParsedFormula(**fo_dict)
                        for fo_dict in pd_data.get("formulas", []) or []
                    ]

                    parsed_doc = ParsedDocument(
                        doc_id=pd_data.get("doc_id", doc_id),
                        title=pd_data.get(
                            "title", info.get("name", meta_raw.get("title", doc_id))
                        ),
                        content=pd_data.get("content", ""),
                        sections=sections,
                        tables=tables,
                        figures=figures,
                        formulas=formulas,
                        metadata=metadata,
                        parse_confidence=pd_data.get("parse_confidence", 1.0),
                    )
                    service.parsed_docs[parsed_doc.doc_id] = parsed_doc
                # 上下文切换：使分块显示等前端能在内存中找到当前文档
                if active_pid and active_pid == parsed_doc.doc_id:
                    service.set_active_document(active_pid)
            if service is not None and active_pid:
                service.set_active_document(active_pid)
            # Heuristic：为每个 Document 下的 Section 补 Summary 并将 Note 挂到 Summary 下
            if tree:
                for node in list(getattr(tree, "nodes", {}).values()):
                    if getattr(node, "type", None) == "document":
                        getattr(tree, "ensure_section_summary_heuristic", lambda _: 0)(node.id)
        except Exception as e:  # pragma: no cover - demo 辅助逻辑
            print(f"[Demo] 加载 Demo 索引或恢复解析缓存失败: {e}")

        return (
            new_lib,
            new_stats,
            new_notes,
            tree,
            gr.update(value=active_pid or ""),
            render_stats(new_stats),
            txt_upd,
            page,
            file_list_html,
            gr.update(value=None),  # upload_f
            embed_upd,
            mineru_upd,
        )
    except Exception as e:
        print(f"[Demo] 加载 Demo 数据异常: {e}")
        txt_upd, embed_upd, mineru_upd = (
            gr.update(value=render_pdf_text(None, lib)),
            gr.update(),
            gr.update(),
        )
        return (
            lib,
            stats,
            notes,
            tree,
            gr.update(),
            render_stats(stats),
            txt_upd,
            1,
            _render_file_list(lib),
            gr.update(),
            embed_upd,
            mineru_upd,
        )


def jump_to_pdf_context(
    pid: str,
    page: int,
    text_to_highlight: str = "",
    lib: dict = None,
    notes: list = None,
) -> tuple:
    """
    通用 PDF 跳转：更新页码与阅读区视图，供搜索、笔记卡片、RAG 引用等复用。

    Args:
        pid: 文档 ID
        page: 目标页码（1-based）
        text_to_highlight: 预留，当前无 BBox 时仅做页码跳转
        lib: 文献库
        notes: 笔记列表（用于高亮视图）

    Returns:
        (page_st, pdf_text_html, pdf_embed_html)
        用于更新 page_st、pdf_text_html、pdf_embed_html 三个组件。
    """
    lib = lib or {}
    notes = notes or []
    page = max(1, int(page) if page else 1)
    if not pid or pid not in lib:
        return (
            1,
            render_pdf_text(None, lib, 1),
            gr.update(),  # 不破坏当前 embed 视图
        )
    return (
        page,
        render_pdf_text(pid, lib, page),
        gr.update(
            value=_render_pdfjs_highlight_view(pid, lib, notes, initial_page=page),
            visible=True,
        ),
    )


def handle_jump_request(payload: str, lib: dict, notes: list) -> tuple:
    """
    处理「跳转到 PDF 上下文」请求（由隐藏输入 jump_request_tb 触发）。
    payload 格式: "pid|page" 或 "pid|page|text_to_highlight"。
    返回 (page_st, pdf_text_html, pdf_embed_html)。
    """
    if not payload or "|" not in payload:
        return 1, gr.update(), gr.update()
    parts = payload.strip().split("|", 2)
    pid = (parts[0] or "").strip()
    page = int(parts[1]) if len(parts) > 1 and parts[1].strip().isdigit() else 1
    text = (parts[2] or "").strip() if len(parts) > 2 else ""
    return jump_to_pdf_context(pid, page, text, lib, notes)


def handle_select_pdf(pid, lib, notes):
    """Handle PDF selection — reset to page 1 and filter notes.

    Args:
        pid: Document ID
        lib: Document library
        notes: All notes list

    Returns:
        (page, pdf_html, file_list_html, notes_html)
    """
    return (
        1,
        render_pdf_text(pid, lib, 1),
        _render_file_list(lib, pid),
        render_note_cards(notes, filter_pid=pid),
    )


def handle_page_prev(page_st, pid, lib):
    """Go to previous page."""
    new_page = max(1, page_st - 1)
    return new_page, render_pdf_text(pid, lib, new_page)


def handle_page_next(page_st, pid, lib):
    """Go to next page."""
    total = get_total_pages(pid, lib)
    new_page = min(total, page_st + 1)
    return new_page, render_pdf_text(pid, lib, new_page)


def handle_mode_switch(mode, pid, lib, page_st, notes=None):
    """Switch between text, PDF, and PDF highlight view modes.

    v2.3: PDF高亮模式为默认，移除了Docling模式（解析功能已整合到RAG服务中）
    v2.4: 新增Docling结构模式和分块数据库模式
    v2.5: MinerU Markdown 使用 gr.Markdown + latex_delimiters 以支持 LaTeX 渲染
    """
    _hide_mineru_md = gr.update(visible=False)
    if mode == "PDF原版":
        return (
            gr.update(visible=False),
            gr.update(value=_render_pdf_embed(pid, lib), visible=True),
            _hide_mineru_md,
        )
    elif mode == "PDF高亮":
        pdfjs_html = _render_pdfjs_highlight_view(pid, lib, notes or [])
        return (
            gr.update(visible=False),
            gr.update(value=pdfjs_html, visible=True),
            _hide_mineru_md,
        )
    elif mode == "Docling结构":
        docling_html = _render_docling_structure_view(pid, lib, notes or [])
        return (
            gr.update(visible=False),
            gr.update(value=docling_html, visible=True),
            _hide_mineru_md,
        )
    elif mode == "分块数据库":
        chunk_db_html = _render_chunk_database_view(pid, lib)
        return (
            gr.update(visible=False),
            gr.update(value=chunk_db_html, visible=True),
            _hide_mineru_md,
        )
    elif mode == "MinerU Markdown":
        raw_md = _get_mineru_raw_markdown(pid, lib)
        return (
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(value=raw_md or "选择文献后，MinerU Markdown 将在此显示（支持 LaTeX 公式）", visible=True),
        )
    else:
        # 文本模式
        return (
            gr.update(visible=True),
            gr.update(visible=False),
            _hide_mineru_md,
        )


def handle_highlight_action(payload_str, notes, pid, tree, lib):
    """
    Handle highlight / translate-note action from popup.

    v2.0 更新:
    - 创建 annotation TreeNode 存储批注
    - 支持 priority 和 color 映射
    - 批注作为文档的子节点
    - **高亮笔记存储到 lib[pid]["notes"] 以支持持久化显示**

    v3.0 更新:
    - **立即创建 KnowledgeNode 到 tree**，实现笔记实时可见
    - 不依赖 AI 处理即可在知识树/图谱中显示

    v3.1 更新:
    - **检查RAG处理状态，处理中时显示警告**
    - 处理中时仍然允许高亮，但显示提示

    Args:
        payload_str: JSON 格式的操作数据
        notes: 现有笔记列表
        pid: 当前文献 ID
        tree: 知识树实例
        lib: 文献库

    Returns:
        (notes, notes_html, tree, pdf_text_html, lib)
    """
    if not payload_str or not payload_str.strip():
        return notes, render_note_cards(notes, filter_pid=pid), tree, gr.update(), lib

    # 检查RAG处理状态
    rag_warning = ""
    if pid and pid in lib:
        is_processing = lib[pid].get("rag_processing", False)
        rag_status = lib[pid].get("rag_status", "")
        if is_processing:
            rag_warning = f"<div class='tip' style='background:#fef3c7;border-color:#fcd34d;'>⚠️ 文档正在解析中: {rag_status}<br>建议等待解析完成后再标注，否则章节信息可能不准确。</div>"

    try:
        data = json.loads(payload_str)
    except (json.JSONDecodeError, TypeError):
        return notes, render_note_cards(notes, filter_pid=pid), tree, gr.update(), lib

    action = data.get("action", "")
    text = data.get("text", "")
    page = data.get("page", "1")
    color = data.get("color", "yellow")  # 默认黄色

    if action == "highlight" and text:
        text_content = text.strip()
        annotation_text = data.get("annotation", "")

        # 检查是否已存在相同内容的笔记（防重复）
        existing_note = None
        for n in notes:
            if (
                n.get("content", "").strip() == text_content
                and n.get("source_pid") == pid
            ):
                existing_note = n
                break

        if existing_note:
            # 更新已有笔记的批注（如果有新批注）
            if annotation_text:
                existing_note["annotation"] = annotation_text
                # 同步到 tree
                if tree:
                    tree_node = tree.find_note_by_original_id(
                        existing_note.get("id", "")
                    )
                    if tree_node:
                        tree_node.metadata["annotation"] = annotation_text
                # 同步到 lib
                if pid and pid in lib:
                    for ln in lib[pid].get("notes", []):
                        if ln.get("id") == existing_note.get("id"):
                            ln["annotation"] = annotation_text
                            break
            current_page = int(page) if str(page).isdigit() else 1
            pdf_html = render_pdf_text(pid, lib, current_page)
            return notes, render_note_cards(notes, filter_pid=pid), tree, pdf_html, lib

        # 创建新笔记
        nid = next_note_id()
        priority = COLOR_PRIORITY_MAP.get(color, 3)

        note = {
            "id": nid,
            "type": "高亮",
            "content": text_content,
            "annotation": annotation_text.strip() if annotation_text else "",
            "translation": "",
            "tags": [],
            "page": int(page) if str(page).isdigit() else 1,
            "color": color,
            "priority": priority,
            "ts": time.strftime("%H:%M"),
            "source_pid": pid or "",
            # PDF.js特有字段（跨行高亮支持）
            "rects": data.get("rects", []),
            "coordinate": data.get("coordinate"),
            "pdfjs": data.get("pdfjs", False),
        }
        notes.append(note)

        # 同时保存到 lib 以支持持久化高亮显示
        if pid and pid in lib:
            if "notes" not in lib[pid]:
                lib[pid]["notes"] = []
            lib[pid]["notes"].append(note)

        # v3.0: 立即创建 KnowledgeNode 到 tree（不依赖AI）
        if tree and pid and pid in lib:
            # 确保文档节点存在
            doc_node = tree.find_document_node(pid)
            if not doc_node:
                # 创建默认 domain 和 document 节点
                domain_node = tree.find_domain_node("未分类")
                if not domain_node:
                    domain_node = tree.create_domain_node("未分类", pid)
                doc_name = lib[pid].get("name", "未知文献")
                doc_node = tree.create_document_node(doc_name, pid, domain_node.id)

            # 查找对应的section节点（如果已有章节信息）
            section_node_id = None
            current_page = int(page) if str(page).isdigit() else 1
            section_node = tree.get_sections_by_page(doc_node.id, current_page)
            if section_node:
                section_node_id = section_node.id

            # 创建 note 节点（category 暂时为空，等AI分类后更新）
            # 如果找到section，则放在section下，否则放在document下
            tree.create_note_node(
                note=note,
                category="",  # 初始无分类
                doc_node_id=doc_node.id,
                section_node_id=section_node_id,  # 传递section ID
            )

        # 重新渲染 PDF 文本以显示持久化高亮
        current_page = int(page) if str(page).isdigit() else 1
        pdf_html = render_pdf_text(pid, lib, current_page)
        notes_html = render_note_cards(notes, filter_pid=pid)
        if rag_warning:
            notes_html = rag_warning + notes_html
        return notes, notes_html, tree, pdf_html, lib

    elif action == "translate_note" and text:
        from urllib.parse import unquote

        orig = unquote(text)
        translation = unquote(data.get("translation", ""))
        color = data.get("color", "yellow")  # 默认黄色

        # Find existing highlight note for this text and attach translation
        attached = False
        for existing_note in notes:
            if (
                existing_note.get("content", "").strip() == orig.strip()
                and existing_note.get("type") == "高亮"
            ):
                existing_note["translation"] = translation
                attached = True
                # Also update tree node if exists
                if tree:
                    tree_node = tree.find_note_by_original_id(
                        existing_note.get("id", "")
                    )
                    if tree_node:
                        tree_node.metadata["translation"] = translation
                # Also update lib
                if pid and pid in lib:
                    for ln in lib[pid].get("notes", []):
                        if ln.get("id") == existing_note.get("id"):
                            ln["translation"] = translation
                            break
                break

        if not attached:
            # Create new highlight note WITH translation (not standalone translation)
            nid = next_note_id()
            priority = COLOR_PRIORITY_MAP.get(color, 3)
            note = {
                "id": nid,
                "type": "高亮",
                "content": orig,
                "translation": translation,
                "annotation": "",
                "page": int(page) if str(page).isdigit() else 1,
                "color": color,
                "priority": priority,
                "ts": time.strftime("%H:%M"),
                "source_pid": pid or "",
            }
            notes.append(note)

            # Save to lib
            if pid and pid in lib:
                if "notes" not in lib[pid]:
                    lib[pid]["notes"] = []
                lib[pid]["notes"].append(note)

            # Create tree node
            if tree and pid and pid in lib:
                doc_node = tree.find_document_node(pid)
                if not doc_node:
                    domain_node = tree.find_domain_node("未分类")
                    if not domain_node:
                        domain_node = tree.create_domain_node("未分类", pid)
                    doc_name = lib[pid].get("name", "未知文献")
                    doc_node = tree.create_document_node(doc_name, pid, domain_node.id)
                tree.create_note_node(note=note, category="", doc_node_id=doc_node.id)

        current_page = int(page) if str(page).isdigit() else 1
        pdf_html = render_pdf_text(pid, lib, current_page)
        return notes, render_note_cards(notes, filter_pid=pid), tree, pdf_html, lib

    elif action == "screenshot":
        # v2.3: 截图笔记保存
        image_data = data.get("image", "")
        screenshot_page = data.get("page", "1")
        annotation_text = data.get("annotation", "")
        doc_id = data.get("doc_id", pid)
        ocr_text = data.get("ocr_text", "")  # OCR识别的文字

        if not image_data:
            return (
                notes,
                render_note_cards(notes, filter_pid=pid),
                tree,
                gr.update(),
                lib,
            )

        # 创建截图笔记
        nid = next_note_id()
        # 如果有OCR文字，使用OCR文字作为content
        content_text = (
            ocr_text.strip() if ocr_text.strip() else f"[截图] 第{screenshot_page}页"
        )
        note = {
            "id": nid,
            "type": "截图",  # 截图类型
            "content": content_text,  # OCR文字或默认文本
            "annotation": annotation_text.strip() if annotation_text else "",
            "image": image_data,  # base64图片数据
            "page": int(screenshot_page) if str(screenshot_page).isdigit() else 1,
            "color": "blue",  # 截图默认蓝色
            "priority": 3,
            "ts": time.strftime("%H:%M"),
            "source_pid": doc_id or pid or "",
            "ocr": bool(ocr_text.strip()),  # 标记是否有OCR
        }
        notes.append(note)

        # 保存到 lib
        if pid and pid in lib:
            if "notes" not in lib[pid]:
                lib[pid]["notes"] = []
            lib[pid]["notes"].append(note)

        # 创建知识树节点
        if tree and pid and pid in lib:
            doc_node = tree.find_document_node(pid)
            if not doc_node:
                domain_node = tree.find_domain_node("未分类")
                if not domain_node:
                    domain_node = tree.create_domain_node("未分类", pid)
                doc_name = lib[pid].get("name", "未知文献")
                doc_node = tree.create_document_node(doc_name, pid, domain_node.id)
            tree.create_note_node(note=note, category="图像", doc_node_id=doc_node.id)

        return notes, render_note_cards(notes, filter_pid=pid), tree, gr.update(), lib

    return notes, render_note_cards(notes, filter_pid=pid), tree, gr.update(), lib


def handle_read_note_action(action_data, notes, pid, tree, lib):
    """Handle action button click on note card in read tab.

    action_data format: "action:note_id" or "annotate:note_id:annotation_text"
    Actions: translate, tag, annotate, ask

    Returns: (status_message, notes, notes_html, tree)
    """
    if not action_data or ":" not in action_data:
        return "<span class='agent-st'>等待操作...</span>", notes, gr.update(), tree

    parts = action_data.split(":", 2)
    action = parts[0]
    note_id = parts[1] if len(parts) > 1 else ""

    # Find the note
    note = None
    for n in notes:
        if n.get("id") == note_id:
            note = n
            break

    if not note:
        return (
            f"<span class='agent-st'>笔记未找到: {note_id[:20]}</span>",
            notes,
            gr.update(),
            tree,
        )

    content = note.get("content", "")

    if action == "translate":
        from agents.translator import TranslatorAgent

        translator = TranslatorAgent()
        result = translator.execute(
            payload={"text": content}, context={"target_lang": "zh"}
        )
        if result.status == "success":
            translated = result.data.get("translation", "")
            # Update note
            note["translation"] = translated
            # Sync to tree
            if tree:
                tree_node = tree.find_note_by_original_id(note_id)
                if tree_node:
                    tree_node.metadata["translation"] = translated
            # Sync to lib
            if pid and pid in lib:
                for ln in lib[pid].get("notes", []):
                    if ln.get("id") == note_id:
                        ln["translation"] = translated
                        break
            return (
                "<span class='agent-st'>翻译完成</span>",
                notes,
                render_note_cards(notes, filter_pid=pid),
                tree,
            )
        return (
            f"<span class='agent-st'>翻译失败: {esc(str(result.error)[:40])}</span>",
            notes,
            gr.update(),
            tree,
        )

    elif action == "tag":
        from agents.crusher import CrusherAgent

        crusher = CrusherAgent()
        result = crusher.execute(
            payload={"notes": [{"content": content, "page": 0}]},
            context={"doc_context": ""},
        )
        if result.status == "success":
            data = result.data
            new_tags = data.get("notes", [{}])[0].get("tags", [])
            # Update note (use ai_tags field)
            if "ai_tags" not in note:
                note["ai_tags"] = []
            note["ai_tags"].extend([t for t in new_tags if t not in note["ai_tags"]])
            # Sync to tree
            if tree:
                tree_node = tree.find_note_by_original_id(note_id)
                if tree_node:
                    for tag_text in new_tags:
                        if not any(
                            c.label == tag_text
                            for c in tree.get_children(tree_node.id)
                            if c.type == "tag"
                        ):
                            tree.create_tag_node(tag_text, tree_node.id)
            # Sync to lib
            if pid and pid in lib:
                for ln in lib[pid].get("notes", []):
                    if ln.get("id") == note_id:
                        if "ai_tags" not in ln:
                            ln["ai_tags"] = []
                        ln["ai_tags"].extend(
                            [t for t in new_tags if t not in ln["ai_tags"]]
                        )
                        break
            return (
                f"<span class='agent-st'>已添加标签: {', '.join(new_tags[:3])}</span>",
                notes,
                render_note_cards(notes, filter_pid=pid),
                tree,
            )
        return (
            "<span class='agent-st'>标签生成失败</span>",
            notes,
            gr.update(),
            tree,
        )

    elif action == "annotate":
        annotation_text = parts[2].strip() if len(parts) > 2 else ""
        if not annotation_text:
            return (
                "<span class='agent-st'>请输入批注内容</span>",
                notes,
                gr.update(),
                tree,
            )
        # Update note
        note["annotation"] = annotation_text
        # Sync to tree
        if tree:
            tree_node = tree.find_note_by_original_id(note_id)
            if tree_node:
                tree_node.metadata["annotation"] = annotation_text
        # Sync to lib
        if pid and pid in lib:
            for ln in lib[pid].get("notes", []):
                if ln.get("id") == note_id:
                    ln["annotation"] = annotation_text
                    break
        return (
            "<span class='agent-st'>已添加批注</span>",
            notes,
            render_note_cards(notes, filter_pid=pid),
            tree,
        )

    elif action == "manual_tag":
        tag_text = parts[2].strip() if len(parts) > 2 else ""
        if not tag_text:
            return (
                "<span class='agent-st'>请输入标签文本</span>",
                notes,
                gr.update(),
                tree,
            )
        # Update note (use manual_tags field)
        if "manual_tags" not in note:
            note["manual_tags"] = []
        if tag_text not in note["manual_tags"]:
            note["manual_tags"].append(tag_text)
        # Sync to tree
        if tree:
            tree_node = tree.find_note_by_original_id(note_id)
            if tree_node:
                if not any(
                    c.label == tag_text
                    for c in tree.get_children(tree_node.id)
                    if c.type == "tag"
                ):
                    tree.create_tag_node(tag_text, tree_node.id)
        # Sync to lib
        if pid and pid in lib:
            for ln in lib[pid].get("notes", []):
                if ln.get("id") == note_id:
                    if "manual_tags" not in ln:
                        ln["manual_tags"] = []
                    if tag_text not in ln["manual_tags"]:
                        ln["manual_tags"].append(tag_text)
                    break
        return (
            f"<span class='agent-st'>已添加标签: {tag_text}</span>",
            notes,
            render_note_cards(notes, filter_pid=pid),
            tree,
        )

    elif action == "ask":
        return (
            "<span class='agent-st'>已发送到AI助手</span>",
            notes,
            gr.update(),
            tree,
        )

    return (
        f"<span class='agent-st'>未知操作: {action}</span>",
        notes,
        gr.update(),
        tree,
    )


def handle_save_annotation(
    doc_id: str,
    section_id: str,
    selected_text: str,
    note: str,
    priority: int,
    tree,
    lib,
):
    """
    保存批注到章节 (API 接口)

    Args:
        doc_id: 文献 ID
        section_id: 章节节点 ID（可选，为空则挂到文档下）
        selected_text: 选中的原文
        note: 用户批注内容
        priority: 重要性 (1-5)
        tree: 知识树实例
        lib: 文献库

    Returns:
        创建的 annotation TreeNode 或 None
    """
    if not selected_text or not doc_id:
        return None

    try:
        from models.tree_node import TreeNode, PRIORITY_COLORS

        # 确定父节点
        parent_id = section_id
        if not parent_id and tree:
            doc_node = tree.find_document_node(doc_id)
            parent_id = doc_node.id if doc_node else None

        # 获取颜色
        color = PRIORITY_COLORS.get(priority, "#FFE66D")

        # 创建批注节点
        annotation_node = TreeNode.create_annotation(
            doc_id=doc_id,
            parent_id=parent_id,
            selected_text=selected_text,
            note=note,
            priority=priority,
            color=color,
        )

        # 存储到 lib
        if doc_id in lib:
            if "annotations" not in lib[doc_id]:
                lib[doc_id]["annotations"] = []
            lib[doc_id]["annotations"].append(annotation_node.to_dict())

        return annotation_node

    except ImportError:
        return None


def handle_popup_translate(text):
    """Translate text from popup (strips timestamp prefix)."""
    if not text or not text.strip():
        return ""
    if "|" in text:
        text = text.split("|", 1)[1]

    if not text or not text.strip():
        return ""
    try:
        result = call_llm(
            "你是翻译引擎。如果输入是中文则翻译为英文，如果输入是英文则翻译为中文。"
            "仅输出翻译结果，不加解释、不加引号。",
            text.strip(),
            temperature=0.1,
            max_tokens=500,
        )
        return result.strip()
    except Exception as e:
        return f"[翻译失败] {e}"


# ══════════════════════════════════════════════════════════════
# UI BUILDER
# ══════════════════════════════════════════════════════════════


def build_read_tab():
    """Build the Read tab UI — file list + reader + visible notes.

    v2.3: PDF高亮模式为默认显示模式
    """
    # 上传提示
    gr.HTML(
        """
    <div class='upload-notice' style='background:#fef3c7;border:1px solid #f59e0b;border-radius:6px;padding:8px 12px;margin-bottom:12px;font-size:0.85em;color:#92400e;'>
    ⚠️ <strong>提示：</strong>上传的文件仅在当前会话中使用，不会永久保存。刷新页面后需要重新上传。
    </div>
    """
    )

    gr.HTML(
        "<div class='tip'>"
        "PDF高亮模式：选择文字弹出工具栏，或切换到截图模式框选区域 | 支持高亮·翻译·批注保存到知识图谱"
        "</div>"
    )

    with gr.Row():
        # ── Left: File list ──
        with gr.Column(scale=2, min_width=200):
            with gr.Row():
                upload_f = gr.File(
                    label="上传文献",
                    file_types=[".pdf", ".txt", ".md"],
                    file_count="multiple",
                    scale=4,
                )
                # Demo 按钮：加载官方架构白皮书的预置体验数据（高且醒目）
                demo_btn = gr.Button(
                    "🎁 体验: 加载官方架构白皮书",
                    scale=2,
                    size="lg",
                    variant="secondary",
                    elem_id="read-demo-btn",
                )
                # 重置按钮 - 清空所有状态
                reset_btn = gr.Button(
                    "🔄 重置", scale=1, size="sm", variant="secondary"
                )
            gr.Markdown(
                "### 文献列表",
                latex_delimiters=[
                    {"left": "$$", "right": "$$", "display": True},
                    {"left": "$", "right": "$", "display": False},
                ],
            )
            file_list_html = gr.HTML("<div class='nc-empty'>上传文献后显示</div>")
            # Hidden textbox for programmatic value setting
            # visible=True but CSS-hidden to ensure DOM is rendered
            pdf_selector = gr.Textbox(
                value="",
                label="选择文献",
                elem_id="pdf-selector-hidden",
                show_label=False,
            )
            view_mode = gr.Radio(
                choices=[
                    "PDF高亮",
                    "文本模式",
                    "PDF原版",
                    "Docling结构",
                    "MinerU Markdown",
                    "分块数据库",
                ],
                value="PDF高亮",  # v2.3: PDF高亮模式为默认
                label="查看模式",
                info="PDF高亮:保真+高亮+截图 | 文本:可高亮 | PDF原版:保真 | Docling:章节结构 | MinerU Markdown:解析原文 | 分块:数据库视图",
            )
            chunk_granularity = gr.Radio(
                choices=["细", "中", "粗"],
                value="中",
                label="RAG分块粒度",
                info="细:更精细召回 | 中:平衡 | 粗:减少碎片。切换后对后续上传/重建索引生效",
            )
            chunk_mode = gr.Radio(
                choices=["语义", "段落"],
                value="语义",
                label="分块模式",
                info="语义:基于embedding相似度切割(精准) | 段落:按空行分块(快速/不调用 embedding 模型)",
            )

        # ── Center: Reader ──
        with gr.Column(scale=5, min_width=400):
            with gr.Row():
                prev_btn = gr.Button("◀ 上一页", scale=1, size="sm")
                next_btn = gr.Button("下一页 ▶", scale=1, size="sm")
            # v2.3: PDF高亮模式为默认，所以pdf_text_html初始隐藏，pdf_embed_html初始显示
            pdf_text_html = gr.HTML(
                "<div class='txt-empty'>选择文献后，文本将在此显示</div>",
                visible=False,  # 默认隐藏，因为PDF高亮模式是默认
            )
            pdf_embed_html = gr.HTML(
                "<div class='txt-empty'>选择文献后，PDF 将在此显示</div>",
                visible=True,  # 默认显示，PDF高亮模式
            )
            # MinerU Markdown 专用：gr.Markdown 支持 LaTeX 公式渲染（$...$ / $$...$$）
            mineru_markdown = gr.Markdown(
                value="",
                visible=False,
                latex_delimiters=[
                    {"left": "$$", "right": "$$", "display": True},
                    {"left": "$", "right": "$", "display": False},
                ],
            )

        # ── Right: Notes (always visible) ──
        with gr.Column(scale=3, min_width=240):
            gr.Markdown(
                "### 阅读笔记",
                latex_delimiters=[
                    {"left": "$$", "right": "$$", "display": True},
                    {"left": "$", "right": "$", "display": False},
                ],
            )
            notes_html = gr.HTML(render_note_cards([]))

    # Hidden textboxes for JS ↔ Python communication
    # visible=True but hidden via CSS (visible=False prevents DOM rendering in Gradio 6.5.1)
    highlight_action_tb = gr.Textbox(
        elem_id="highlight-action-input",
        visible=True,
        container=False,
    )
    translate_action_tb = gr.Textbox(
        elem_id="translate-action-input",
        visible=True,
        container=False,
    )
    translate_result_tb = gr.Textbox(
        elem_id="translate-result-input",
        visible=True,
        container=False,
    )
    # Hidden textbox for note card action buttons (translate, tag, annotate)
    note_action_tb = gr.Textbox(
        elem_id="note-action-input",
        visible=True,
        container=False,
    )
    # 全局跳转：搜索/笔记/RAG 引用点击时传入 "pid|page" 或 "pid|page|text"
    jump_request_tb = gr.Textbox(
        elem_id="jump-request-input",
        value="",
        visible=True,
        container=False,
    )

    return {
        "upload_f": upload_f,
        "file_list_html": file_list_html,
        "pdf_selector": pdf_selector,
        "view_mode": view_mode,
        "chunk_granularity": chunk_granularity,
        "chunk_mode": chunk_mode,
        "pdf_text_html": pdf_text_html,
        "pdf_embed_html": pdf_embed_html,
        "mineru_markdown": mineru_markdown,
        "notes_html": notes_html,
        "prev_btn": prev_btn,
        "next_btn": next_btn,
        "highlight_action_tb": highlight_action_tb,
        "translate_action_tb": translate_action_tb,
        "translate_result_tb": translate_result_tb,
        "note_action_tb": note_action_tb,
        "jump_request_tb": jump_request_tb,
        "reset_btn": reset_btn,
        "demo_btn": demo_btn,
    }
