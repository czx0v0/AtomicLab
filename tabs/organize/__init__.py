"""
Organize Tab — UI builder and handlers
=======================================
Tab 2: Knowledge graph + AI note analysis (Crusher) + Synthesizer.
       Two graph views: note tree graph + document relation graph.
       Streamlined layout: graph dominant, controls compact.

Exports:
    build_organize_tab()   -> dict of Gradio components
    handle_generate()      -> Crusher execution handler
    handle_synthesize()    -> Synthesizer execution handler
    handle_search()        -> search handler
    handle_node_select()   -> node click handler
"""

import time
import gradio as gr

from core.utils import esc
from agents.crusher import CrusherAgent
from agents.synthesizer import SynthesizerAgent
from knowledge.tree_model import KnowledgeTree
from knowledge.search import search_nodes
from ui.renderers import (
    render_notes_for_organize,
    render_classified_notes,
    render_stats,
    render_node_detail,
    render_synth_result,
)
from ui.echarts_graph import (
    generate_echarts_html,
    generate_empty_graph_html,
    generate_tree_echarts_html,
)


# ══════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════


def _render_graph(tree, highlight_ids=None):
    if not tree.nodes:
        return generate_empty_graph_html("解构笔记后，知识图谱将在此显示")
    option = tree.to_echarts_option(highlight_ids)
    return generate_echarts_html(option)


def _render_doc_graph(tree):
    if not tree.nodes:
        return generate_empty_graph_html("上传多篇文献后，文献关系图将在此显示")
    option = tree.to_document_graph_option()
    if not option:
        return generate_empty_graph_html("上传多篇文献后，文献关系图将在此显示")
    return generate_echarts_html(option, container_id="doc-graph", height=400)


def _render_tree_sidebar(tree):
    if not tree.nodes:
        return generate_empty_graph_html("解构笔记后，知识树将在此显示", height=400)
    option = tree.to_echarts_tree_option()
    if not option:
        return generate_empty_graph_html("解构笔记后，知识树将在此显示", height=400)
    return generate_tree_echarts_html(option, container_id="organize-tree", height=400)


# ══════════════════════════════════════════════════════════════
# HANDLERS
# ══════════════════════════════════════════════════════════════


def handle_generate(notes, pid, lib, stats, tree):
    """Execute Crusher: classify + tag + summarize notes. Auto-refresh graph."""
    if not notes:
        # No notes — just refresh the graph
        return (
            "<div class='nc-empty'>暂无笔记可解构。请先在「阅读」页记录笔记。</div>",
            lib,
            stats,
            render_stats(stats),
            "<span class='agent-st'>等待输入...</span>",
            render_notes_for_organize(notes),
            _render_graph(tree),
            tree,
            _render_tree_sidebar(tree),
            _render_doc_graph(tree),
        )

    all_notes = list(notes)

    ctx = lib[pid]["text"][:3000] if pid and pid in lib else "(无文献上下文)"

    crusher = CrusherAgent()
    result = crusher.execute(
        payload={"notes": all_notes},
        context={"doc_context": ctx},
    )

    if result.status != "success":
        return (
            f"<div class='nc-empty'>解析失败: {esc(result.error[:120])}</div>",
            lib,
            stats,
            render_stats(stats),
            f"<span class='agent-st'>Crusher: {esc(result.error[:40])}</span>",
            render_notes_for_organize(notes),
            _render_graph(tree),
            tree,
            _render_tree_sidebar(tree),
            _render_doc_graph(tree),
        )

    data = result.data
    domain = data.get("domain", "未知")
    classified_notes = data.get("notes", [])

    # Build tree: domain -> document -> note -> tags
    domain_node = tree.find_domain_node(domain)
    if not domain_node:
        domain_node = tree.create_domain_node(domain, pid)

    doc_node = None
    if pid and pid in lib:
        doc_node = tree.find_document_node(pid)
        if not doc_node:
            doc_name = lib[pid]["name"]
            doc_node = tree.create_document_node(doc_name, pid, domain_node.id)

    for cn in classified_notes:
        idx = cn.get("index", 0)
        cat = cn.get("category", "其他")
        ai_tags = cn.get("tags", [])

        original_note = (
            all_notes[idx]
            if idx < len(all_notes)
            else (
                all_notes[-1]
                if all_notes
                else {"content": "", "page": 0, "source_pid": pid or ""}
            )
        )

        note_node = tree.create_note_node(
            note=original_note,
            category=cat,
            doc_node_id=doc_node.id if doc_node else domain_node.id,
        )
        for tag_text in ai_tags:
            tree.create_tag_node(tag_text, note_node.id)

    stats["notes"] += len(notes)
    stats["nodes"] = len(tree.nodes)

    status_msg = f"Crusher: {len(all_notes)} 条笔记 → {len(classified_notes)} 分类 · {len(tree.nodes)} 节点"

    return (
        render_classified_notes(data, lib, all_notes),
        lib,
        stats,
        render_stats(stats),
        f"<span class='agent-st'>{esc(status_msg)}</span>",
        render_notes_for_organize(notes),
        _render_graph(tree),
        tree,
        _render_tree_sidebar(tree),
        _render_doc_graph(tree),
    )


def handle_synthesize(tree, lib):
    """Execute Synthesizer: cross-document analysis."""
    note_nodes = [n for n in tree.nodes.values() if n.type == "note"]
    if len(note_nodes) < 2:
        return (
            "<div class='nc-empty'>至少需要 2 条已分类笔记才能进行跨文献合成</div>",
            tree,
        )

    synth_notes = []
    for nn in note_nodes:
        doc_name = "?"
        if nn.parent_id:
            parent = tree.get_node(nn.parent_id)
            if parent and parent.type == "document":
                doc_name = parent.label
        tags = [c.label for c in tree.get_children(nn.id) if c.type == "tag"]
        synth_notes.append(
            {
                "content": nn.content,
                "category": nn.metadata.get("category", "其他"),
                "tags": tags,
                "doc_name": doc_name,
                "node_id": nn.id,
            }
        )

    doc_list = [n.label for n in tree.nodes.values() if n.type == "document"]

    synth = SynthesizerAgent()
    result = synth.execute(
        payload={"notes": synth_notes},
        context={"doc_list": doc_list},
    )

    if result.status != "success":
        return f"<div class='nc-empty'>合成失败: {esc(result.error[:120])}</div>", tree

    data = result.data

    # Apply cross-references to tree
    cross_refs = data.get("cross_refs", [])
    for cr in cross_refs:
        from_idx = cr.get("from_idx", -1)
        to_idx = cr.get("to_idx", -1)
        if 0 <= from_idx < len(synth_notes) and 0 <= to_idx < len(synth_notes):
            tree.add_cross_reference(
                synth_notes[from_idx]["node_id"],
                synth_notes[to_idx]["node_id"],
            )

    return render_synth_result(data), tree


def handle_search(query, tree, lib):
    if not query or not query.strip():
        return "", _render_graph(tree)
    results = search_nodes(tree, query)
    highlight_ids = [n.id for n in results]

    # Also search document full text
    doc_matches = []
    q_lower = query.lower().strip()
    for pid, info in lib.items():
        doc_text = info.get("text", "")
        doc_name = info.get("name", "?")
        if not doc_text:
            continue
        pos = doc_text.lower().find(q_lower)
        if pos >= 0:
            start = max(0, pos - 60)
            end = min(len(doc_text), pos + len(q_lower) + 60)
            snippet = doc_text[start:end]
            doc_matches.append((doc_name, snippet))

    total = len(results) + len(doc_matches)
    if total == 0:
        return "<div class='search-result'><span>未找到结果</span></div>", _render_graph(tree)

    parts = []
    if results:
        parts.append(f"知识节点 {len(results)} 条")
    if doc_matches:
        parts.append(f"原文 {len(doc_matches)} 处")

    h = f"<div class='search-result'><span class='search-result-count'>找到 {total} 个结果（{' · '.join(parts)}）</span>"
    for name, snippet in doc_matches[:5]:
        h += f"<div class='search-doc-match'><b>{esc(name)}</b>: ...{esc(snippet)}...</div>"
    h += "</div>"
    return h, _render_graph(tree, highlight_ids)


def handle_node_select(node_id, tree):
    if not node_id:
        return render_node_detail(None), "", ""
    node = tree.get_node(node_id)
    if not node:
        return render_node_detail(None), "", ""
    detail = render_node_detail(node.to_dict())
    tags_str = ", ".join(node.tags) if node.tags else ""
    return detail, node.content, tags_str


def handle_node_edit(node_id, new_content, new_tags, tree):
    """Save edits to a knowledge node."""
    if not node_id:
        return tree, _render_graph(tree), render_node_detail(None), _render_doc_graph(tree), _render_tree_sidebar(tree)

    node = tree.get_node(node_id)
    if not node:
        return tree, _render_graph(tree), render_node_detail(None), _render_doc_graph(tree), _render_tree_sidebar(tree)

    # Update node
    if new_content and new_content.strip():
        node.content = new_content.strip()
        node.label = new_content.strip()[:20] + ("..." if len(new_content.strip()) > 20 else "")
    if new_tags is not None:
        node.tags = [t.strip() for t in new_tags.split(",") if t.strip()]

    detail = render_node_detail(node.to_dict())
    return tree, _render_graph(tree), detail, _render_doc_graph(tree), _render_tree_sidebar(tree)


# ══════════════════════════════════════════════════════════════
# UI BUILDER
# ══════════════════════════════════════════════════════════════


def build_organize_tab():
    """Build the Organize/Knowledge-Graph tab UI — simplified layout."""
    gr.HTML(
        "<div class='tip'>AI 自动分类笔记、打标签、生成摘要，构建文献-笔记-标签知识树</div>"
    )

    # ── Top action bar (simplified) ──
    with gr.Row():
        search_input = gr.Textbox(label="搜索", placeholder="搜索知识节点和原文...", scale=4)
        search_btn = gr.Button("搜索", scale=1, size="sm")
        gen_btn = gr.Button("刷新图谱", variant="primary", scale=1, size="sm")

    agent_status = gr.HTML("<span class='agent-st'>等待操作...</span>")
    stats_html = gr.HTML(render_stats({"docs": 0, "notes": 0, "nodes": 0}))
    search_result_html = gr.HTML("")

    # ── Main area: graph + details side by side ──
    with gr.Row():
        with gr.Column(scale=6, min_width=400):
            with gr.Tabs():
                with gr.Tab("笔记知识图谱"):
                    graph_html = gr.HTML(
                        generate_empty_graph_html("解构笔记后，知识图谱将在此显示")
                    )
                with gr.Tab("文献关系图"):
                    doc_graph_html = gr.HTML(
                        generate_empty_graph_html(
                            "上传多篇文献后，文献关系图将在此显示"
                        )
                    )
            selected_node_id = gr.Textbox(
                elem_id="selected-node-input",
                visible=True,
                show_label=False,
                container=False,
            )

        with gr.Column(scale=4, min_width=300):
            gr.Markdown("### 节点详情")
            node_detail_html = gr.HTML(render_node_detail(None))
            edit_content = gr.TextArea(
                label="编辑内容",
                placeholder="点击图谱节点后可在此编辑...",
                lines=2,
                interactive=True,
            )
            edit_tags = gr.Textbox(
                label="编辑标签（逗号分隔）",
                placeholder="tag1, tag2, ...",
                interactive=True,
            )
            save_node_btn = gr.Button("保存修改", size="sm")

            gr.Markdown("### 笔记概览")
            notes_overview = gr.HTML(render_notes_for_organize([]))

    # ── Results below (always visible) ──
    gr.Markdown("### 分析结果")
    classified_cards_out = gr.HTML(
        "<div class='nc-empty'>点击「刷新图谱」将笔记自动解构为分类知识</div>"
    )

    return {
        "search_input": search_input,
        "search_btn": search_btn,
        "search_result_html": search_result_html,
        "graph_html": graph_html,
        "doc_graph_html": doc_graph_html,
        "selected_node_id": selected_node_id,
        "node_detail_html": node_detail_html,
        "edit_content": edit_content,
        "edit_tags": edit_tags,
        "save_node_btn": save_node_btn,
        "notes_overview": notes_overview,
        "gen_btn": gen_btn,
        "agent_status": agent_status,
        "stats_html": stats_html,
        "classified_cards_out": classified_cards_out,
    }
