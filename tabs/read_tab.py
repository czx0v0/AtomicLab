"""
Read Tab
========
Tab 1: PDF reading and note-taking interface.
"""

import gradio as gr
import os
import time

from core.utils import phash, extract_pdf, read_txt
from core.state import next_note_id
from ui.renderers import render_pdf_text, render_note_cards, render_stats


def handle_upload(files, lib, stats):
    """Handle file upload.
    
    Args:
        files: Uploaded files
        lib: Library store state
        stats: Statistics state
        
    Returns:
        Updated states and UI components
    """
    if not files:
        return lib, stats, gr.update(), render_stats(stats), render_pdf_text(None, lib)
    
    for f in files:
        fp = f if isinstance(f, str) else (f.name if hasattr(f, "name") else str(f))
        fn = os.path.basename(fp)
        pid = phash(fn)
        
        if pid in lib:
            continue
        
        text = extract_pdf(fp) if fp.lower().endswith(".pdf") else read_txt(fp)
        lib[pid] = {"name": fn, "text": text, "atoms": [], "filepath": fp}
        stats["docs"] += 1

    choices = [(v["name"], k) for k, v in lib.items()]
    last_pid = choices[-1][1] if choices else None
    
    return (
        lib,
        stats,
        gr.update(choices=choices, value=last_pid),
        render_stats(stats),
        render_pdf_text(last_pid, lib),
    )


def handle_select_pdf(pid, lib):
    """Handle PDF selection.
    
    Args:
        pid: Document ID
        lib: Library store
        
    Returns:
        Rendered PDF text HTML
    """
    return render_pdf_text(pid, lib)


def handle_save_note(page, content, notes, pid):
    """Save a reading note.
    
    Args:
        page: Page number
        content: Note content
        notes: Notes state
        pid: Current document ID
        
    Returns:
        Updated notes and rendered cards
    """
    if not content or not content.strip():
        return notes, render_note_cards(notes)
    
    nid = next_note_id()
    note = {
        "id": nid,
        "type": "文字笔记",
        "content": content.strip(),
        "page": int(page) if page else 1,
        "ts": time.strftime("%H:%M"),
        "source_pid": pid or "",
    }
    notes.append(note)
    return notes, render_note_cards(notes)


def build_read_tab(lib_st, stats_st, notes_st, stats_html):
    """Build the Read tab UI.
    
    Args:
        lib_st: Library state
        stats_st: Stats state  
        notes_st: Notes state
        stats_html: Stats HTML component reference
        
    Returns:
        Dict of created components for event binding
    """
    gr.HTML("<div class='tip'>上传 PDF，阅读提取文本并记录笔记</div>")
    
    with gr.Row():
        # Left: Upload + Text Reader
        with gr.Column(scale=6, min_width=400):
            with gr.Group():
                upload_f = gr.File(
                    label="上传文献 (PDF / TXT / MD)",
                    file_types=[".pdf", ".txt", ".md"],
                    file_count="multiple",
                )
                pdf_selector = gr.Dropdown(
                    choices=[], 
                    label="选择文献", 
                    allow_custom_value=False
                )
            gr.Markdown("### 文献文本")
            pdf_text_html = gr.HTML(
                "<div class='txt-empty'>选择文献后，文本将在此显示</div>"
            )

        # Right: Notes
        with gr.Column(scale=3, min_width=240):
            with gr.Group():
                note_page = gr.Number(
                    value=1, 
                    label="页码", 
                    precision=0, 
                    minimum=1
                )
                note_content = gr.TextArea(
                    label="笔记",
                    placeholder="记录你的思考、摘抄关键段落...",
                    lines=4,
                )
                save_note_btn = gr.Button("保存笔记", variant="primary")
            gr.Markdown("### 阅读笔记")
            notes_html = gr.HTML(render_note_cards([]))
    
    # Event bindings
    upload_f.change(
        fn=handle_upload,
        inputs=[upload_f, lib_st, stats_st],
        outputs=[lib_st, stats_st, pdf_selector, stats_html, pdf_text_html],
    )
    
    pdf_selector.change(
        fn=handle_select_pdf,
        inputs=[pdf_selector, lib_st],
        outputs=[pdf_text_html],
    )
    
    save_note_btn.click(
        fn=handle_save_note,
        inputs=[note_page, note_content, notes_st, pdf_selector],
        outputs=[notes_st, notes_html],
    )
    
    return {
        "upload_f": upload_f,
        "pdf_selector": pdf_selector,
        "pdf_text_html": pdf_text_html,
        "note_page": note_page,
        "note_content": note_content,
        "notes_html": notes_html,
    }
