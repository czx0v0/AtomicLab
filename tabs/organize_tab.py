"""
Organize Tab
============
Tab 2: Knowledge graph visualization and note organization.
"""

import gradio as gr

from agents.crusher import CrusherAgent
from knowledge.tree_model import KnowledgeTree
from knowledge.search import search_nodes
from ui.renderers import (
    render_notes_for_organize,
    render_cards,
    render_stats,
    render_node_detail,
    render_search_results,
)
from ui.echarts_graph import generate_echarts_html, generate_empty_graph_html
from core.utils import esc


def handle_generate(extra_notes, notes, pid, lib, stats, tree):
    """Execute knowledge deconstruction.
    
    Args:
        extra_notes: Additional notes text
        notes: Notes list
        pid: Current document ID
        lib: Library store
        stats: Statistics
        tree: Knowledge tree
        
    Returns:
        Updated states and UI components
    """
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
            lib,
            stats,
            render_stats(stats),
            "<span class='agent-st'>等待输入...</span>",
            get_all_atom_cards(lib),
            render_notes_for_organize(notes),
            _render_graph(tree),
            tree,
        )

    # Get document context
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
            lib,
            stats,
            render_stats(stats),
            f"<span class='agent-st'>Crusher: {esc(result.error[:40])}</span>",
            get_all_atom_cards(lib),
            render_notes_for_organize(notes),
            _render_graph(tree),
            tree,
        )
    
    data = result.data
    
    # Register atoms in library
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
    
    # Find or create domain node
    domain_node = None
    for node in tree.nodes.values():
        if node.type == "domain" and domain in node.label:
            domain_node = node
            break
    
    if not domain_node:
        domain_node = tree.create_domain_node(domain, pid)
    
    # Add atom nodes
    for atom in data["atoms"]:
        tree.create_atom_node(atom, pid, domain_node.id)
    
    stats["nodes"] = len(tree.nodes)

    status_msg = f"Crusher: {len(notes)} 条笔记 → {len(new_ids)} atoms"
    
    return (
        render_cards(data, new_ids, lib),
        lib,
        stats,
        render_stats(stats),
        f"<span class='agent-st'>{esc(status_msg)}</span>",
        get_all_atom_cards(lib),
        render_notes_for_organize(notes),
        _render_graph(tree),
        tree,
    )


def handle_search(query, tree):
    """Search knowledge tree.
    
    Args:
        query: Search query
        tree: Knowledge tree
        
    Returns:
        Search results HTML and updated graph
    """
    if not query or not query.strip():
        return render_search_results([], ""), _render_graph(tree)
    
    results = search_nodes(tree, query)
    highlight_ids = [n.id for n in results]
    
    return (
        render_search_results(results, query),
        _render_graph(tree, highlight_ids),
    )


def handle_node_select(node_id, tree):
    """Handle node selection from graph.
    
    Args:
        node_id: Selected node ID
        tree: Knowledge tree
        
    Returns:
        Node detail HTML
    """
    if not node_id:
        return render_node_detail(None)
    
    node = tree.get_node(node_id)
    if not node:
        return render_node_detail(None)
    
    return render_node_detail(node.to_dict())


def get_all_atom_cards(lib):
    """Get all atom cards from library.
    
    Args:
        lib: Library store
        
    Returns:
        HTML string for all cards
    """
    from ui.renderers import render_all_cards
    
    all_atoms = []
    for doc in lib.values():
        for a in doc["atoms"]:
            all_atoms.append(a)
    
    if not all_atoms:
        return "<div class='nc-empty'>暂无原子卡片。请先在「整理」页解构笔记。</div>"
    
    return render_all_cards(all_atoms, lib)


def _render_graph(tree, highlight_ids=None):
    """Render knowledge graph.
    
    Args:
        tree: Knowledge tree
        highlight_ids: Node IDs to highlight
        
    Returns:
        Graph HTML
    """
    if not tree.nodes:
        return generate_empty_graph_html("解构笔记后，知识图谱将在此显示")
    
    option = tree.to_echarts_option(highlight_ids)
    return generate_echarts_html(option)


def build_organize_tab(lib_st, stats_st, notes_st, tree_st, stats_html, ref_cards_html):
    """Build the Organize tab UI.
    
    Args:
        lib_st: Library state
        stats_st: Stats state
        notes_st: Notes state
        tree_st: Knowledge tree state
        stats_html: Stats HTML component
        ref_cards_html: Reference cards HTML component (for Tab 3)
        
    Returns:
        Dict of created components
    """
    gr.HTML("<div class='tip'>搜索知识图谱，解构笔记为原子知识</div>")
    
    # Search bar
    with gr.Row():
        search_input = gr.Textbox(
            label="搜索",
            placeholder="输入关键词搜索知识节点...",
            scale=4,
        )
        search_btn = gr.Button("搜索", scale=1)
        refresh_btn = gr.Button("刷新图谱", scale=1)
    
    search_result_html = gr.HTML("")
    
    with gr.Row():
        # Left: Knowledge Graph
        with gr.Column(scale=6, min_width=400):
            gr.Markdown("### 知识图谱")
            graph_html = gr.HTML(
                generate_empty_graph_html("解构笔记后，知识图谱将在此显示")
            )
            # Hidden textbox for node selection
            selected_node_id = gr.Textbox(
                label="",
                visible=False,
                elem_id="selected-node-input"
            )

        # Right: Node Detail + Notes + Generate
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
            
            gr.Markdown("### 原子卡片")
            atom_cards_out = gr.HTML(
                "<div class='nc-empty'>点击「智能解构」将笔记转化为原子知识</div>"
            )
    
    # Get pdf_selector reference - will be set in app.py
    # For now, create a placeholder
    pdf_selector = gr.Textbox(visible=False, value="")
    
    # Event bindings
    def _refresh_and_generate(extra, notes, pid, lib, stats, tree):
        return handle_generate(extra, notes, pid, lib, stats, tree)
    
    gen_btn.click(
        fn=_refresh_and_generate,
        inputs=[extra_notes_in, notes_st, pdf_selector, lib_st, stats_st, tree_st],
        outputs=[
            atom_cards_out,
            lib_st,
            stats_st,
            stats_html,
            agent_status,
            ref_cards_html,
            notes_overview,
            graph_html,
            tree_st,
        ],
    )
    
    search_btn.click(
        fn=handle_search,
        inputs=[search_input, tree_st],
        outputs=[search_result_html, graph_html],
    )
    
    search_input.submit(
        fn=handle_search,
        inputs=[search_input, tree_st],
        outputs=[search_result_html, graph_html],
    )
    
    def _refresh_graph(tree):
        return _render_graph(tree)
    
    refresh_btn.click(
        fn=_refresh_graph,
        inputs=[tree_st],
        outputs=[graph_html],
    )
    
    selected_node_id.change(
        fn=handle_node_select,
        inputs=[selected_node_id, tree_st],
        outputs=[node_detail_html],
    )
    
    return {
        "search_input": search_input,
        "graph_html": graph_html,
        "node_detail_html": node_detail_html,
        "notes_overview": notes_overview,
        "atom_cards_out": atom_cards_out,
        "agent_status": agent_status,
        "pdf_selector_ref": pdf_selector,
    }
