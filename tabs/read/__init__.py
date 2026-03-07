"""
Read Tab — UI builder and handlers
===================================
Tab 1: Upload PDFs, read extracted text, record notes.
       Single-page view with floating popup menu (WeChat Reading style).
       Highlight = auto-save note with annotation node support.
       Translate inline. Copy to clipboard.
       Dual-mode: text extraction + original PDF rendering.
       Clickable file list instead of dropdown.

v2.0 更新:
- 批注功能重写，支持 TreeNode(type="annotation")
- 支持 priority (1-5) 和颜色映射
- 批注作为章节/文档的子节点存储
"""

import os
import time
import json
import gradio as gr

from core.utils import phash, extract_pdf, read_txt, esc
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
    """Render clickable file list."""
    if not lib:
        return "<div class='nc-empty'>上传文献后显示</div>"
    h = ""
    for pid, info in lib.items():
        name = esc(info["name"])
        is_pdf = info.get("filepath", "").lower().endswith(".pdf")
        icon = "&#128196;" if is_pdf else "&#128221;"
        active_cls = " active" if pid == active_pid else ""
        # Use JS to set hidden dropdown value
        h += (
            f"<div class='file-item{active_cls}' "
            f"onclick=\"setFileSelection('{pid}')\">"
            f"<span class='file-item-icon'>{icon}</span>"
            f"<span class='file-item-name'>{name}</span>"
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

    # 尝试从RAG服务获取解析结果
    try:
        from services.rag_service import RAGService
        from core.config import RAG_CONFIG

        rag_service = RAGService(RAG_CONFIG)

        # 如果文档已索引，尝试获取chunks
        if doc_info.get("rag_indexed"):
            # 获取文档的chunks
            chunks = []
            if hasattr(rag_service, "doc_chunks") and pid in rag_service.doc_chunks:
                chunk_ids = rag_service.doc_chunks[pid]
                for chunk_id in chunk_ids:
                    if chunk_id in rag_service.chunk_store:
                        chunks.append(rag_service.chunk_store[chunk_id])

            # 构建ParsedDocument-like结构
            if chunks:
                parsed_data = {
                    "title": doc_info.get("name", "未命名文档"),
                    "content": "\n\n".join(
                        [c.content for c in chunks if c.chunk_type == "text"]
                    ),
                    "tables": [],
                    "metadata": {
                        "page_count": doc_info.get("chunk_count", 0),
                        "parse_confidence": doc_info.get("parse_confidence", 0.8),
                    },
                }

                # 收集表格
                for chunk in chunks:
                    if chunk.chunk_type == "table" and hasattr(chunk, "metadata"):
                        table_meta = chunk.metadata
                        if hasattr(table_meta, "table_data"):
                            parsed_data["tables"].append(table_meta.table_data)

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
            try:
                import threading

                def process_with_rag():
                    try:
                        result = rag_service.process_document(fp, pid)
                        if result.success:
                            lib[pid]["rag_indexed"] = True
                            lib[pid]["chunk_count"] = result.chunk_count
                            lib[pid]["parse_confidence"] = result.confidence
                    except Exception as e:
                        print(f"RAG处理文档失败 {fn}: {e}")

                # 在后台线程中处理，避免阻塞UI
                thread = threading.Thread(target=process_with_rag)
                thread.daemon = True
                thread.start()
            except Exception as e:
                print(f"启动RAG处理失败: {e}")

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
    """Switch between text, PDF, and Docling view modes.

    v2.2: 新增Docling模式支持
    """
    if mode == "PDF模式":
        return (
            gr.update(visible=False),
            gr.update(value=_render_pdf_embed(pid, lib), visible=True),
        )
    elif mode == "Docling模式":
        # Docling模式：使用结构化渲染
        docling_html = _render_docling_view(pid, lib, notes or [])
        return (
            gr.update(visible=False),
            gr.update(value=docling_html, visible=True),
        )
    else:
        # 文本模式
        return (
            gr.update(visible=True),
            gr.update(visible=False),
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

            # 创建 note 节点（category 暂时为空，等AI分类后更新）
            tree.create_note_node(
                note=note,
                category="",  # 初始无分类
                doc_node_id=doc_node.id,
            )

        # 重新渲染 PDF 文本以显示持久化高亮
        current_page = int(page) if str(page).isdigit() else 1
        pdf_html = render_pdf_text(pid, lib, current_page)
        return notes, render_note_cards(notes, filter_pid=pid), tree, pdf_html, lib

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
    """Build the Read tab UI — file list + reader + visible notes."""
    gr.HTML(
        "<div class='tip'>"
        "选中文字自动弹出工具栏：高亮标记 · 一键翻译 · 复制 · 问AI | 左右翻页浏览"
        "</div>"
    )

    with gr.Row():
        # ── Left: File list ──
        with gr.Column(scale=2, min_width=200):
            upload_f = gr.File(
                label="上传文献",
                file_types=[".pdf", ".txt", ".md"],
                file_count="multiple",
            )
            gr.Markdown("### 文献列表")
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
                choices=["文本模式", "PDF模式", "Docling模式"],
                value="文本模式",
                label="查看模式",
            )

        # ── Center: Reader ──
        with gr.Column(scale=5, min_width=400):
            with gr.Row():
                prev_btn = gr.Button("◀ 上一页", scale=1, size="sm")
                next_btn = gr.Button("下一页 ▶", scale=1, size="sm")
            pdf_text_html = gr.HTML(
                "<div class='txt-empty'>选择文献后，文本将在此显示</div>"
            )
            pdf_embed_html = gr.HTML(visible=False)

        # ── Right: Notes (always visible) ──
        with gr.Column(scale=3, min_width=240):
            gr.Markdown("### 阅读笔记")
            notes_html = gr.HTML(render_note_cards([]))

    # Hidden textboxes for JS ↔ Python communication
    # visible=True but hidden via CSS (visible=False prevents DOM rendering in Gradio 6.5.1)
    highlight_action_tb = gr.Textbox(
        elem_id="highlight-action-input",
        visible=True,
        show_label=False,
        container=False,
    )
    translate_action_tb = gr.Textbox(
        elem_id="translate-action-input",
        visible=True,
        show_label=False,
        container=False,
    )
    translate_result_tb = gr.Textbox(
        elem_id="translate-result-input",
        visible=True,
        show_label=False,
        container=False,
    )
    # Hidden textbox for note card action buttons (translate, tag, annotate)
    note_action_tb = gr.Textbox(
        elem_id="note-action-input",
        visible=True,
        show_label=False,
        container=False,
    )

    return {
        "upload_f": upload_f,
        "file_list_html": file_list_html,
        "pdf_selector": pdf_selector,
        "view_mode": view_mode,
        "pdf_text_html": pdf_text_html,
        "pdf_embed_html": pdf_embed_html,
        "notes_html": notes_html,
        "prev_btn": prev_btn,
        "next_btn": next_btn,
        "highlight_action_tb": highlight_action_tb,
        "translate_action_tb": translate_action_tb,
        "translate_result_tb": translate_result_tb,
        "note_action_tb": note_action_tb,
    }
