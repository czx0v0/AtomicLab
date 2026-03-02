"""
Read Tab — UI builder and handlers
===================================
Tab 1: Upload PDFs, read extracted text, record notes.
       Single-page view with floating popup menu (WeChat Reading style).
       Highlight = auto-save note. Translate inline. Copy to clipboard.
       Dual-mode: text extraction + original PDF rendering.
       Clickable file list instead of dropdown.
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
    render_stats,
    get_total_pages,
)


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


# ══════════════════════════════════════════════════════════════
# HANDLERS
# ══════════════════════════════════════════════════════════════


def handle_upload(files, lib, stats, tree):
    """Handle file upload — also auto-creates knowledge tree nodes."""
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
        )

    for f in files:
        fp = f if isinstance(f, str) else (f.name if hasattr(f, "name") else str(f))
        fn = os.path.basename(fp)
        pid = phash(fn)

        if pid in lib:
            continue

        text = extract_pdf(fp) if fp.lower().endswith(".pdf") else read_txt(fp)
        lib[pid] = {"name": fn, "text": text, "notes": [], "filepath": fp}
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

    choices = [(v["name"], k) for k, v in lib.items()]
    last_pid = choices[-1][1] if choices else None

    return (
        lib,
        stats,
        gr.update(choices=choices, value=last_pid),
        render_stats(stats),
        render_pdf_text(last_pid, lib, 1),
        1,
        _render_file_list(lib, last_pid),
        tree,
    )


def handle_select_pdf(pid, lib):
    """Handle PDF selection — reset to page 1."""
    return 1, render_pdf_text(pid, lib, 1), _render_file_list(lib, pid)


def handle_page_prev(page_st, pid, lib):
    """Go to previous page."""
    new_page = max(1, page_st - 1)
    return new_page, render_pdf_text(pid, lib, new_page)


def handle_page_next(page_st, pid, lib):
    """Go to next page."""
    total = get_total_pages(pid, lib)
    new_page = min(total, page_st + 1)
    return new_page, render_pdf_text(pid, lib, new_page)


def handle_mode_switch(mode, pid, lib, page_st):
    """Switch between text and PDF view modes."""
    if mode == "PDF模式":
        return (
            gr.update(visible=False),
            gr.update(value=_render_pdf_embed(pid, lib), visible=True),
        )
    else:
        return (
            gr.update(visible=True),
            gr.update(visible=False),
        )


def handle_highlight_action(payload_str, notes, pid):
    """Handle highlight / translate-note action from popup — auto-save as note."""
    if not payload_str or not payload_str.strip():
        return notes, render_note_cards(notes)

    try:
        data = json.loads(payload_str)
    except (json.JSONDecodeError, TypeError):
        return notes, render_note_cards(notes)

    action = data.get("action", "")
    text = data.get("text", "")
    page = data.get("page", "1")
    color = data.get("color", "")

    if action == "highlight" and text:
        nid = next_note_id()
        annotation = data.get("annotation", "")
        note = {
            "id": nid,
            "type": "高亮",
            "content": text.strip(),
            "annotation": annotation.strip() if annotation else "",
            "page": int(page) if str(page).isdigit() else 1,
            "color": color,
            "ts": time.strftime("%H:%M"),
            "source_pid": pid or "",
        }
        notes.append(note)
    elif action == "translate_note" and text:
        from urllib.parse import unquote

        orig = unquote(text)
        translation = unquote(data.get("translation", ""))
        # Find existing highlight note for this text and attach translation
        attached = False
        for existing_note in notes:
            if existing_note.get("content", "").strip() == orig.strip() and existing_note.get("type") == "高亮":
                existing_note["translation"] = translation
                attached = True
                break
        if not attached:
            # Create standalone translation note
            nid = next_note_id()
            note = {
                "id": nid,
                "type": "翻译",
                "content": orig,
                "translation": translation,
                "page": int(page) if str(page).isdigit() else 1,
                "ts": time.strftime("%H:%M"),
                "source_pid": pid or "",
            }
            notes.append(note)

    return notes, render_note_cards(notes)


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
            # Hidden selector for programmatic value setting (CSS-hidden, not visible=False)
            pdf_selector = gr.Dropdown(
                choices=[],
                label="",
                visible=True,
                allow_custom_value=True,
                elem_id="pdf-selector-hidden",
            )
            view_mode = gr.Radio(
                choices=["文本模式", "PDF模式"],
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
    }
