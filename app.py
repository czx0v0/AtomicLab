"""
Atomic Lab v3.0 — Read · Organize · Write
=========================================
基于 Atomic-RAG 的原子化科研工作站

Architecture:
- core/: Configuration, utilities, state management
- agents/: AI agents (Crusher, Annotator, Synthesizer)
- tabs/: Gradio tab builders
- knowledge/: Knowledge tree model and search
- ui/: Styles and HTML renderers
"""

import gradio as gr
import os
import time
import tempfile

# Core imports
from core.config import APP_TITLE
from core.utils import phash, extract_pdf, read_txt, esc
from core.state import next_note_id, create_initial_stats

# UI imports
from ui.styles import CSS, HEADER_HTML
from ui.renderers import (
    render_pdf_text,
    render_note_cards,
    render_notes_for_organize,
    render_cards,
    render_all_cards,
    render_stats,
    render_node_detail,
)
from ui.echarts_graph import generate_echarts_html, generate_empty_graph_html

# Agent imports
from agents.crusher import CrusherAgent

# Knowledge imports
from knowledge.tree_model import KnowledgeTree
from knowledge.search import search_nodes


# ══════════════════════════════════════════════════════════════
# HANDLERS
# ══════════════════════════════════════════════════════════════

def handle_upload(files, lib, stats):
    """Handle file upload."""
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
    """Handle PDF selection."""
    return render_pdf_text(pid, lib)


def handle_save_note(page, content, notes, pid):
    """Save a reading note."""
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


def handle_generate(extra_notes, notes, pid, lib, stats, tree):
    """Execute knowledge deconstruction."""
    # Merge all notes
    all_text_parts = []
    for n in notes:
        prefix = f"[p.{n['page']}]"
        if n["content"]:
            all_text_parts.append(f"{prefix} {n['content']}")
    if extra_notes and extra_notes.strip():
        all_text_parts.append(extra_notes.strip())

    merged = "\n".join(all_text_parts)
    if not merged.strip():
        return (
            "<div class='nc-empty'>暂无笔记可解构。请先在「阅读」页记录笔记。</div>",
            lib, stats, render_stats(stats),
            "<span class='agent-st'>等待输入...</span>",
            get_all_atom_cards(lib),
            render_notes_for_organize(notes),
            _render_graph(tree),
            tree,
        )

    ctx = lib[pid]["text"][:3000] if pid and pid in lib else "(无文献上下文)"

    # Execute Crusher agent
    crusher = CrusherAgent()
    result = crusher.execute(
        payload={"text": merged},
        context={"doc_context": ctx}
    )
    
    if result.status != "success":
        return (
            f"<div class='nc-empty'>解析失败: {esc(result.error[:120])}</div>",
            lib, stats, render_stats(stats),
            f"<span class='agent-st'>Crusher: {esc(result.error[:40])}</span>",
            get_all_atom_cards(lib),
            render_notes_for_organize(notes),
            _render_graph(tree),
            tree,
        )
    
    data = result.data
    
    # Register atoms
    new_ids = []
    for atom in data["atoms"]:
        atom["source_pid"] = pid or ""
        atom["domain"] = data.get("domain", "")
        new_ids.append(atom["id"])
        if pid and pid in lib:
            lib[pid]["atoms"].append(atom)
        stats["atoms"] += 1
    
    stats["notes"] += len(notes)
    
    # Update knowledge tree
    domain = data.get("domain", "未知")
    domain_node = None
    for node in tree.nodes.values():
        if node.type == "domain" and domain in node.label:
            domain_node = node
            break
    
    if not domain_node:
        domain_node = tree.create_domain_node(domain, pid)
    
    for atom in data["atoms"]:
        tree.create_atom_node(atom, pid, domain_node.id)
    
    stats["nodes"] = len(tree.nodes)

    status_msg = f"Crusher: {len(notes)} 条笔记 → {len(new_ids)} atoms"
    
    return (
        render_cards(data, new_ids, lib),
        lib, stats, render_stats(stats),
        f"<span class='agent-st'>{esc(status_msg)}</span>",
        get_all_atom_cards(lib),
        render_notes_for_organize(notes),
        _render_graph(tree),
        tree,
    )


def handle_search(query, tree):
    """Search knowledge tree."""
    if not query or not query.strip():
        return "", _render_graph(tree)
    
    results = search_nodes(tree, query)
    highlight_ids = [n.id for n in results]
    count_html = f"<div class='search-result'><span class='search-result-count'>找到 {len(results)} 个结果</span></div>" if results else ""
    
    return count_html, _render_graph(tree, highlight_ids)


def handle_node_select(node_id, tree):
    """Handle node selection."""
    if not node_id:
        return render_node_detail(None)
    node = tree.get_node(node_id)
    return render_node_detail(node.to_dict() if node else None)


def handle_download(text):
    """Download draft as Markdown."""
    if not text or not text.strip():
        return None
    path = os.path.join(tempfile.gettempdir(), "atomic_lab_draft.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def get_all_atom_cards(lib):
    """Get all atom cards."""
    all_atoms = []
    for doc in lib.values():
        for a in doc["atoms"]:
            all_atoms.append(a)
    if not all_atoms:
        return "<div class='nc-empty'>暂无原子卡片。请先在「整理」页解构笔记。</div>"
    return render_all_cards(all_atoms, lib)


def _render_graph(tree, highlight_ids=None):
    """Render knowledge graph."""
    if not tree.nodes:
        return generate_empty_graph_html("解构笔记后，知识图谱将在此显示")
    option = tree.to_echarts_option(highlight_ids)
    return generate_echarts_html(option)


# ══════════════════════════════════════════════════════════════
# GRADIO UI
# ══════════════════════════════════════════════════════════════

with gr.Blocks(title=APP_TITLE) as demo:
    # States
    lib_st = gr.State({})
    stats_st = gr.State({"docs": 0, "atoms": 0, "notes": 0, "nodes": 0})
    notes_st = gr.State([])
    tree_st = gr.State(KnowledgeTree())

    gr.HTML(HEADER_HTML)

    with gr.Tabs():
        # ═══════════════════════════════════════════════
        # TAB 1: READ
        # ═══════════════════════════════════════════════
        with gr.Tab("📖 阅读"):
            gr.HTML("<div class='tip'>上传 PDF，阅读提取文本并记录笔记</div>")
            with gr.Row():
                with gr.Column(scale=6, min_width=400):
                    with gr.Group():
                        upload_f = gr.File(
                            label="上传文献 (PDF / TXT / MD)",
                            file_types=[".pdf", ".txt", ".md"],
                            file_count="multiple",
                        )
                        pdf_selector = gr.Dropdown(
                            choices=[], label="选择文献", allow_custom_value=False
                        )
                    gr.Markdown("### 文献文本")
                    pdf_text_html = gr.HTML(
                        "<div class='txt-empty'>选择文献后，文本将在此显示</div>"
                    )

                with gr.Column(scale=3, min_width=240):
                    with gr.Group():
                        note_page = gr.Number(value=1, label="页码", precision=0, minimum=1)
                        note_content = gr.TextArea(
                            label="笔记",
                            placeholder="记录你的思考、摘抄关键段落...",
                            lines=4,
                        )
                        save_note_btn = gr.Button("保存笔记", variant="primary")
                    gr.Markdown("### 阅读笔记")
                    notes_html = gr.HTML(render_note_cards([]))

        # ═══════════════════════════════════════════════
        # TAB 2: ORGANIZE (Knowledge Graph)
        # ═══════════════════════════════════════════════
        with gr.Tab("🌳 知识图谱"):
            gr.HTML("<div class='tip'>搜索知识图谱，解构笔记为原子知识</div>")
            
            with gr.Row():
                search_input = gr.Textbox(label="搜索", placeholder="输入关键词...", scale=4)
                search_btn = gr.Button("搜索", scale=1)
                refresh_btn = gr.Button("刷新图谱", scale=1)
            
            search_result_html = gr.HTML("")
            
            with gr.Row():
                with gr.Column(scale=6, min_width=400):
                    gr.Markdown("### 知识图谱")
                    graph_html = gr.HTML(generate_empty_graph_html("解构笔记后，知识图谱将在此显示"))
                    selected_node_id = gr.Textbox(label="", visible=False, elem_id="selected-node-input")

                with gr.Column(scale=4, min_width=300):
                    gr.Markdown("### 节点详情")
                    node_detail_html = gr.HTML(render_node_detail(None))
                    
                    gr.Markdown("### 笔记概览")
                    notes_overview = gr.HTML(render_notes_for_organize([]))
                    
                    with gr.Group():
                        extra_notes_in = gr.TextArea(
                            label="补充笔记（可选）",
                            placeholder="额外输入补充内容...",
                            lines=2,
                        )
                        gen_btn = gr.Button("智能解构", variant="primary")
                    
                    agent_status = gr.HTML("<span class='agent-st'>等待操作...</span>")
                    stats_html = gr.HTML(render_stats({"docs": 0, "atoms": 0, "notes": 0, "nodes": 0}))
                    
                    gr.Markdown("### 原子卡片")
                    atom_cards_out = gr.HTML("<div class='nc-empty'>点击「智能解构」将笔记转化为原子知识</div>")

        # ═══════════════════════════════════════════════
        # TAB 3: WRITE
        # ═══════════════════════════════════════════════
        with gr.Tab("✍️ 写作"):
            gr.HTML("<div class='tip'>搜索知识库，参考左侧卡片，在右侧自由写作</div>")
            with gr.Row():
                with gr.Column(scale=3, min_width=280):
                    with gr.Group():
                        write_search = gr.Textbox(label="搜索知识库", placeholder="输入关键词...")
                        write_search_btn = gr.Button("搜索", size="sm")
                    gr.Markdown("### 参考卡片")
                    ref_cards_html = gr.HTML("<div class='nc-empty'>解构笔记后，原子卡片将在此显示</div>")

                with gr.Column(scale=6, min_width=400):
                    gr.Markdown("### 写作区")
                    draft_text = gr.TextArea(
                        label="", show_label=False,
                        placeholder="在此自由写作，可参考左侧原子卡片...\n\n支持 Markdown 格式",
                        lines=20,
                    )
                    with gr.Row():
                        draft_file = gr.File(label="下载草稿", interactive=False)
                        download_btn = gr.Button("生成 Markdown 文件", variant="primary")

    # ═══════════════════════════════════════════════
    # EVENTS
    # ═══════════════════════════════════════════════
    
    # Tab 1
    upload_f.change(
        fn=handle_upload,
        inputs=[upload_f, lib_st, stats_st],
        outputs=[lib_st, stats_st, pdf_selector, stats_html, pdf_text_html],
    )
    pdf_selector.change(fn=handle_select_pdf, inputs=[pdf_selector, lib_st], outputs=[pdf_text_html])
    save_note_btn.click(
        fn=handle_save_note,
        inputs=[note_page, note_content, notes_st, pdf_selector],
        outputs=[notes_st, notes_html],
    )

    # Tab 2
    gen_btn.click(
        fn=handle_generate,
        inputs=[extra_notes_in, notes_st, pdf_selector, lib_st, stats_st, tree_st],
        outputs=[atom_cards_out, lib_st, stats_st, stats_html, agent_status, ref_cards_html, notes_overview, graph_html, tree_st],
    )
    search_btn.click(fn=handle_search, inputs=[search_input, tree_st], outputs=[search_result_html, graph_html])
    search_input.submit(fn=handle_search, inputs=[search_input, tree_st], outputs=[search_result_html, graph_html])
    refresh_btn.click(fn=lambda t: _render_graph(t), inputs=[tree_st], outputs=[graph_html])
    selected_node_id.change(fn=handle_node_select, inputs=[selected_node_id, tree_st], outputs=[node_detail_html])

    # Tab 3
    download_btn.click(fn=handle_download, inputs=[draft_text], outputs=[draft_file])
    
    def _write_search(query, tree, lib):
        if not query.strip():
            return get_all_atom_cards(lib)
        results = search_nodes(tree, query)
        if not results:
            return f"<div class='nc-empty'>未找到与 \"{query}\" 相关的结果</div>"
        atoms = [{"id": n.metadata.get("original_id", n.id), "axiom": n.content,
                  "methodology": n.metadata.get("methodology", ""), "boundary": n.metadata.get("boundary", ""),
                  "domain": n.tags[0] if n.tags else "?", "source_pid": n.source_pid}
                 for n in results if n.type == "atom"]
        return render_all_cards(atoms, lib) if atoms else f"<div class='nc-empty'>找到 {len(results)} 个节点</div>"
    
    write_search_btn.click(fn=_write_search, inputs=[write_search, tree_st, lib_st], outputs=[ref_cards_html])
    write_search.submit(fn=_write_search, inputs=[write_search, tree_st, lib_st], outputs=[ref_cards_html])


# ══════════════════════════════════════════════════════════════
# LAUNCH
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, css=CSS)
