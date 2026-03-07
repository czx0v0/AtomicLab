"""
Organize Tab — UI builder and handlers
=======================================
Tab 2: Knowledge tree + global graph + AI note analysis (Crusher).
       New layout: upper-lower tabs for single-doc tree vs global graph.

Exports:
    build_organize_tab()       -> dict of Gradio components
    handle_refresh_tree()      -> refresh display without AI
    handle_generate_summary()  -> Crusher AI execution handler
    handle_synthesize()        -> Synthesizer execution handler
    handle_search()            -> search handler
    handle_note_action()       -> note card action button handler
"""

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
    render_doc_note_tree,
)
from ui.echarts_graph import (
    generate_echarts_html,
    generate_empty_graph_html,
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


# ══════════════════════════════════════════════════════════════
# HANDLERS
# ══════════════════════════════════════════════════════════════


def handle_refresh_tree(pid, lib, stats, tree):
    """Refresh tree display without calling AI.

    Simply re-renders the current tree state.
    Returns: (doc_tree_html, ref_tree_html, global_graph_html, stats_html, agent_status)
    """
    return (
        render_doc_note_tree(tree, pid),
        render_doc_note_tree(tree, None),  # For write tab ref_tree_html
        _render_graph(tree),
        render_stats(stats),
        "<span class='agent-st'>已刷新显示</span>",
    )


def handle_generate_summary(notes, pid, lib, stats, tree):
    """Execute Crusher AI: classify + tag + summarize notes for current document.

    Now filters notes by current document (pid) and generates per-document summary.
    Returns: (lib, stats, stats_html, agent_status, doc_tree_html, tree, ref_tree_html, global_graph_html)
    """
    if not notes:
        yield (
            lib,
            stats,
            render_stats(stats),
            "<span class='agent-st'>暂无笔记可解构。请先在「阅读」页记录笔记。</span>",
            render_doc_note_tree(tree, pid),
            tree,
            render_doc_note_tree(tree, None),
            _render_graph(tree),
        )
        return

    # 发送开始状态
    yield (
        lib,
        stats,
        render_stats(stats),
        "<span class='agent-st'>🔄 正在准备笔记...</span>",
        render_doc_note_tree(tree, pid),
        tree,
        render_doc_note_tree(tree, None),
        _render_graph(tree),
    )

    # Filter notes for current document only
    if pid:
        doc_notes = [n for n in notes if n.get("source_pid") == pid]
    else:
        doc_notes = list(notes)

    if not doc_notes:
        yield (
            lib,
            stats,
            render_stats(stats),
            "<span class='agent-st'>当前文献暂无笔记。请先在「阅读」页为此文献记录笔记。</span>",
            render_doc_note_tree(tree, pid),
            tree,
            render_doc_note_tree(tree, None),
            _render_graph(tree),
        )
        return

    ctx = lib[pid]["text"][:3000] if pid and pid in lib else "(无文献上下文)"

    # 发送AI处理状态
    yield (
        lib,
        stats,
        render_stats(stats),
        f"<span class='agent-st'>🤖 AI正在分析 {len(doc_notes)} 条笔记...</span>",
        render_doc_note_tree(tree, pid),
        tree,
        render_doc_note_tree(tree, None),
        _render_graph(tree),
    )

    crusher = CrusherAgent()
    result = crusher.execute(
        payload={"notes": doc_notes},
        context={"doc_context": ctx},
    )

    if result.status != "success":
        yield (
            lib,
            stats,
            render_stats(stats),
            f"<span class='agent-st'>❌ Crusher 失败: {esc(result.error[:60])}</span>",
            render_doc_note_tree(tree, pid),
            tree,
            render_doc_note_tree(tree, None),
            _render_graph(tree),
        )
        return

    data = result.data
    domain = data.get("domain", "未知")
    summary = data.get("summary", "")
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
        # Store per-document summary in document node metadata
        if doc_node and summary:
            doc_node.metadata["summary"] = summary

    for cn in classified_notes:
        idx = cn.get("index", 0)
        cat = cn.get("category", "其他")
        ai_tags = cn.get("tags", [])

        original_note = (
            doc_notes[idx]
            if idx < len(doc_notes)
            else (
                doc_notes[-1]
                if doc_notes
                else {"content": "", "page": 0, "source_pid": pid or ""}
            )
        )

        # 查找已存在的 note 节点（v3.0 高亮时创建的）
        original_id = original_note.get("id", "")
        existing_node = (
            tree.find_note_by_original_id(original_id) if original_id else None
        )

        if existing_node:
            # 更新现有节点的 category（不创建新节点）
            existing_node.metadata["category"] = cat
            note_node = existing_node
        else:
            # 创建新节点（兼容旧数据）
            note_node = tree.create_note_node(
                note=original_note,
                category=cat,
                doc_node_id=doc_node.id if doc_node else domain_node.id,
            )

        # Note: AI标签不在此处自动添加，用户可通过卡片上的"AI标签"按钮单独生成

    stats["notes"] += len(doc_notes)
    stats["nodes"] = len(tree.nodes)

    doc_name = lib[pid]["name"][:30] if pid and pid in lib else "文献"
    status_msg = f"✅ Crusher: {doc_name} · {len(doc_notes)} 条笔记 → {len(classified_notes)} 分类"

    yield (
        lib,
        stats,
        render_stats(stats),
        f"<span class='agent-st'>{esc(status_msg)}</span>",
        render_doc_note_tree(tree, pid),
        tree,
        render_doc_note_tree(tree, None),
        _render_graph(tree),
    )


def handle_synthesize(tree, lib):
    """Execute Synthesizer: cross-document analysis."""
    note_nodes = [n for n in tree.nodes.values() if n.type == "note"]
    if len(note_nodes) < 2:
        yield (
            "<div class='nc-empty'>至少需要 2 条已分类笔记才能进行跨文献合成</div>",
            tree,
        )
        return

    # 发送准备状态
    yield (
        f"<div style='padding:20px;text-align:center'><span class='agent-st'>🔄 正在准备 {len(note_nodes)} 条笔记...</span></div>",
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

    # 发送AI处理状态
    yield (
        f"<div style='padding:20px;text-align:center'><span class='agent-st'>🤖 AI正在跨文献分析 {len(synth_notes)} 条笔记...</span></div>",
        tree,
    )

    synth = SynthesizerAgent()
    result = synth.execute(
        payload={"notes": synth_notes},
        context={"doc_list": doc_list},
    )

    if result.status != "success":
        yield f"<div class='nc-empty'>❌ 合成失败: {esc(result.error[:120])}</div>", tree
        return

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

    yield render_synth_result(data), tree


def handle_org_doc_select(selected_pid, tree, lib):
    """Handle document selection change in organize tab.

    Args:
        selected_pid: Selected document ID ("" or "__all__" for global view)
        tree: KnowledgeTree instance
        lib: Document library

    Returns:
        (doc_tree_html, global_graph_html)
    """
    pid = None if selected_pid in ("", "__all__") else selected_pid
    tree_html = render_doc_note_tree(tree, pid)
    graph_html = _render_graph(tree)
    return tree_html, graph_html


def handle_search(query, tree, lib, rag_service=None):
    """搜索处理 - v2.1集成RAG混合检索

    优先使用RAG服务进行语义+关键词混合检索，
    如RAG不可用则回退到原有搜索方式
    """
    if not query or not query.strip():
        return "", _render_graph(tree)

    # v2.1: 尝试使用RAG服务进行高级检索
    rag_results = []
    if rag_service:
        try:
            retrieval_result = rag_service.retrieve(query, top_k=10, use_reranker=True)
            if retrieval_result and retrieval_result.chunks:
                rag_results = retrieval_result.chunks
        except Exception as e:
            print(f"RAG检索失败，回退到传统搜索: {e}")

    # 传统知识树搜索
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
            doc_matches.append((doc_name, snippet, pid))

    total = len(results) + len(doc_matches) + len(rag_results)
    if total == 0:
        return (
            "<div class='search-result'><span>未找到结果</span></div>",
            _render_graph(tree),
        )

    parts = []
    if rag_results:
        parts.append(f"RAG语义检索 {len(rag_results)} 条")
    if results:
        parts.append(f"知识节点 {len(results)} 条")
    if doc_matches:
        parts.append(f"原文 {len(doc_matches)} 处")

    h = f"<div class='search-result'><span class='search-result-count'>找到 {total} 个结果（{' · '.join(parts)}）</span></div>"

    # v2.1: 优先显示RAG检索结果
    if rag_results:
        h += "<div class='search-rag-results'>"
        h += "<div style='font-size:12px;color:#3182ce;margin-bottom:8px;font-weight:500'>🎯 RAG智能检索结果</div>"
        for chunk in rag_results[:8]:
            content = esc(chunk.content[:200]) + (
                "..." if len(chunk.content) > 200 else ""
            )
            doc_title = esc(chunk.metadata.doc_title) if chunk.metadata else "未知文档"
            page_num = chunk.page_number if chunk.page_number else "?"
            chunk_type = chunk.chunk_type if chunk.chunk_type else "text"

            # 类型标签样式
            type_colors = {
                "table_semantic": "#e53e3e",
                "table_row": "#dd6b20",
                "semantic": "#3182ce",
                "paragraph": "#38a169",
            }
            type_color = type_colors.get(chunk_type, "#718096")

            h += f"""<div class="search-rag-card" style="margin-bottom:10px;padding:12px;background:#f7fafc;border-radius:8px;border-left:3px solid {type_color}">
  <div style="font-size:11px;color:#4a5568;margin-bottom:4px;display:flex;justify-content:space-between">
    <span><b>{doc_title}</b> (p.{page_num})</span>
    <span style="color:{type_color};font-size:10px">{chunk_type}</span>
  </div>
  <div style="font-size:13px;color:#2d3748;line-height:1.5">{content}</div>
</div>"""
        h += "</div>"

    # Render knowledge node results as detailed cards
    if results:
        h += "<div class='search-nodes'>"
        for node in results[:10]:
            content = esc(node.content[:150]) + (
                "..." if len(node.content) > 150 else ""
            )
            cat = node.metadata.get("category", "")
            page = node.metadata.get("page", "")
            translation = node.metadata.get("translation", "")
            annotation = node.metadata.get("annotation", "")

            # Category badge
            from core.config import CATEGORY_COLORS

            cat_badge = ""
            if cat:
                cat_color = CATEGORY_COLORS.get(cat, "#a0aec0")
                cat_badge = f'<span class="cn-cat" style="background:{cat_color}20;color:{cat_color};border:1px solid {cat_color}40">{esc(cat)}</span>'

            # Tags
            tags = [esc(c.label) for c in tree.get_children(node.id) if c.type == "tag"]
            tags_html = ""
            if tags:
                tags_html = (
                    '<div class="cn-tags" style="margin-top:6px">'
                    + "".join(f'<span class="cn-tag">{t}</span>' for t in tags[:5])
                    + "</div>"
                )

            # Page info
            page_html = f'<span class="nt-page">p.{page}</span>' if page else ""

            # Translation & annotation
            trans_html = (
                f'<div class="nt-translation"><b>译:</b> {esc(translation[:80])}{"..." if len(translation) > 80 else ""}</div>'
                if translation
                else ""
            )
            ann_html = (
                f'<div class="nt-annotation"><b>批注:</b> {esc(annotation[:80])}{"..." if len(annotation) > 80 else ""}</div>'
                if annotation
                else ""
            )

            h += f"""<div class="search-node-card" onclick="setGradioValue('#selected-node-input', '{node.id}')" style="cursor:pointer">
  <div class="nt-top">{cat_badge}<span class="nt-type">{node.type}</span>{page_html}</div>
  <div class="nt-body">{content}</div>
  {ann_html}{trans_html}{tags_html}
</div>"""
        h += "</div>"

    # Render document matches
    if doc_matches:
        h += "<div class='search-doc-matches'>"
        for name, snippet, pid in doc_matches[:5]:
            h += f"<div class='search-doc-match' onclick=\"jumpToSource('{pid}', 1)\" style='cursor:pointer'><b>{esc(name)}</b>: ...{esc(snippet)}...</div>"
        h += "</div>"

    return h, _render_graph(tree, highlight_ids)


def handle_note_action(action_data, tree, lib, notes):
    """Handle action button click on note card.

    action_data format: "action:node_id" or "manual_tag:node_id:tag_text"
    node_id can be either a tree node ID (KN-xxx) or original note ID (NT-xxx)
    Actions: translate, tag, search, ask, annotate, manual_tag

    Returns: (status_message, updated_tree, doc_tree_html, global_graph_html, node_detail_html, notes)
    """
    empty_detail = "<div class='node-detail-wrap'></div>"

    if not action_data or ":" not in action_data:
        return (
            "<span class='agent-st'>等待操作...</span>",
            tree,
            gr.update(),
            gr.update(),
            empty_detail,
            notes,
        )

    parts = action_data.split(":", 2)  # Allow 3 parts for manual_tag:node_id:tag_text
    action = parts[0]
    node_id = parts[1] if len(parts) > 1 else ""

    # Find node - support both tree node ID (KN-xxx) and original note ID (NT-xxx)
    node = tree.get_node(node_id)
    if not node and node_id.startswith("NT-"):
        # Try to find by original_id
        node = tree.find_note_by_original_id(node_id)
        if node:
            node_id = node.id  # Update to actual tree node ID

    # If still not found, try to create from notes_st
    if not node and node_id.startswith("NT-") and notes:
        original_note = next((n for n in notes if n.get("id") == node_id), None)
        if original_note:
            pid = original_note.get("source_pid", "")
            if pid and pid in lib:
                # Ensure document node exists
                doc_node = tree.find_document_node(pid)
                if not doc_node:
                    domain_node = tree.find_domain_node("未分类")
                    if not domain_node:
                        domain_node = tree.create_domain_node("未分类", pid)
                    doc_name = lib[pid].get("name", "未知文献")
                    doc_node = tree.create_document_node(doc_name, pid, domain_node.id)

                # Create node from original note
                node = tree.create_note_node(
                    note=original_note,
                    category="",
                    doc_node_id=doc_node.id,
                )
                node_id = node.id

    if not node:
        return (
            f"<span class='agent-st'>节点未找到: {node_id[:20]}</span>",
            tree,
            gr.update(),
            gr.update(),
            empty_detail,
            notes,
        )

    content = node.content[:100] if node.content else ""
    original_id = node.metadata.get("original_id", "")

    if action == "translate":
        from agents.translator import TranslatorAgent

        translator = TranslatorAgent()
        result = translator.execute(
            payload={"text": node.content}, context={"target_lang": "zh"}
        )
        if result.status == "success":
            translated = result.data.get("translation", "")
            # Store translation in node metadata
            node.metadata["translation"] = translated
            # Also update original note in notes_st for sync
            if original_id and notes:
                for n in notes:
                    if n.get("id") == original_id:
                        n["translation"] = translated
                        break
            pid = node.source_pid
            return (
                f"<span class='agent-st'>翻译完成</span>",
                tree,
                render_doc_note_tree(tree, pid),
                _render_graph(tree),
                handle_node_select(node_id, tree),
                notes,
            )
        return (
            f"<span class='agent-st'>翻译失败: {esc(result.error[:40])}</span>",
            tree,
            gr.update(),
            gr.update(),
            empty_detail,
            notes,
        )

    elif action == "tag":
        # Auto-tag using Crusher for single note
        from agents.crusher import CrusherAgent

        crusher = CrusherAgent()
        result = crusher.execute(
            payload={"notes": [{"content": node.content, "page": 0}]},
            context={"doc_context": ""},
        )
        if result.status == "success":
            data = result.data
            new_tags = data.get("notes", [{}])[0].get("tags", [])
            for tag_text in new_tags:
                if not any(
                    c.label == tag_text
                    for c in tree.get_children(node_id)
                    if c.type == "tag"
                ):
                    tree.create_tag_node(tag_text, node_id)
            # Sync to notes_st (use ai_tags field)
            if original_id and notes:
                for n in notes:
                    if n.get("id") == original_id:
                        if "ai_tags" not in n:
                            n["ai_tags"] = []
                        n["ai_tags"].extend(
                            [t for t in new_tags if t not in n["ai_tags"]]
                        )
                        break
            pid = node.source_pid
            return (
                f"<span class='agent-st'>已添加标签: {', '.join(new_tags[:3])}</span>",
                tree,
                render_doc_note_tree(tree, pid),
                _render_graph(tree),
                handle_node_select(node_id, tree),
                notes,
            )
        return (
            f"<span class='agent-st'>标签生成失败</span>",
            tree,
            gr.update(),
            gr.update(),
            empty_detail,
            notes,
        )

    elif action == "ask":
        # This should trigger chat - return a signal
        return (
            f"<span class='agent-st'>已发送到AI助手</span>",
            tree,
            gr.update(),
            gr.update(),
            empty_detail,
            notes,
        )

    elif action == "annotate":
        # Annotate: action_data = "annotate:node_id:annotation_text"
        annotation_text = parts[2].strip() if len(parts) > 2 else ""
        if not annotation_text:
            return (
                f"<span class='agent-st'>请输入批注内容</span>",
                tree,
                gr.update(),
                gr.update(),
                empty_detail,
                notes,
            )
        # Store annotation in node metadata
        node.metadata["annotation"] = annotation_text
        # Sync to notes_st
        if original_id and notes:
            for n in notes:
                if n.get("id") == original_id:
                    n["annotation"] = annotation_text
                    break
        pid = node.source_pid
        return (
            f"<span class='agent-st'>已添加批注</span>",
            tree,
            render_doc_note_tree(tree, pid),
            _render_graph(tree),
            handle_node_select(node_id, tree),
            notes,
        )

    elif action == "manual_tag":
        # Manual tag: action_data = "manual_tag:node_id:tag_text"
        tag_text = parts[2].strip() if len(parts) > 2 else ""
        if not tag_text:
            return (
                f"<span class='agent-st'>请输入标签文本</span>",
                tree,
                gr.update(),
                gr.update(),
                empty_detail,
                notes,
            )
        # Check if tag already exists
        if not any(
            c.label == tag_text for c in tree.get_children(node_id) if c.type == "tag"
        ):
            tree.create_tag_node(tag_text, node_id)
        # Sync to notes_st (use manual_tags field)
        if original_id and notes:
            for n in notes:
                if n.get("id") == original_id:
                    if "manual_tags" not in n:
                        n["manual_tags"] = []
                    if tag_text not in n["manual_tags"]:
                        n["manual_tags"].append(tag_text)
                    break
        pid = node.source_pid
        return (
            f"<span class='agent-st'>已添加标签: {tag_text}</span>",
            tree,
            render_doc_note_tree(tree, pid),
            _render_graph(tree),
            handle_node_select(node_id, tree),
            notes,
        )

    return (
        f"<span class='agent-st'>未知操作: {action}</span>",
        tree,
        gr.update(),
        gr.update(),
        empty_detail,
        notes,
    )


def handle_node_select(node_id, tree):
    """Handle graph node click - show node detail card with actions."""
    if not node_id or not tree:
        return "<div class='node-detail-wrap'></div>"

    node = tree.get_node(node_id)
    if not node:
        return "<div class='node-detail-wrap'></div>"

    # Build card HTML with action buttons
    content = esc(node.content) if node.content else ""
    cat = node.metadata.get("category", "")
    page = node.metadata.get("page", "")
    translation = node.metadata.get("translation", "")
    annotation = node.metadata.get("annotation", "")

    # Category badge
    cat_badge = ""
    if cat:
        from core.config import CATEGORY_COLORS

        cat_color = CATEGORY_COLORS.get(cat, "#a0aec0")
        cat_badge = f'<span class="cn-cat" style="background:{cat_color}20;color:{cat_color}">{esc(cat)}</span>'

    page_html = f'<span class="nt-page">p.{page}</span>' if page else ""

    # Collect tags
    tags = []
    for child in tree.get_children(node_id):
        if child.type == "tag":
            tags.append(esc(child.label))
    tags_html = ""
    if tags:
        tags_html = (
            '<div class="cn-tags">'
            + "".join(f'<span class="cn-tag">{t}</span>' for t in tags)
            + "</div>"
        )

    # Annotation display
    ann_html = ""
    if annotation:
        ann_html = f'<div class="nt-annotation"><b>批注:</b> {esc(annotation)}</div>'

    # Translation display
    trans_html = ""
    if translation:
        trans_html = (
            f'<div class="nt-translation"><b>翻译:</b> {esc(translation)}</div>'
        )

    # Action buttons + manual tag input (unified)
    actions_html = f"""<div class="nt-actions">
  <span class="nt-action-btn" onclick="noteAction('translate', '{node_id}')">翻译</span>
  <span class="nt-action-btn" onclick="noteAction('tag', '{node_id}')">AI标签</span>
  <span class="nt-action-btn" onclick="showAnnotatePopup('{node_id}')">添加批注</span>
  <span class="nt-action-btn" onclick="noteAction('ask', '{node_id}')">问AI</span>
</div>
<div class="nt-manual-tag">
  <input type="text" id="manual-tag-input" placeholder="输入标签..." onkeydown="if(event.key==='Enter')manualTag('{node_id}', this)" />
  <span class="nt-action-btn" onclick="manualTag('{node_id}', this.previousElementSibling)">添加</span>
</div>"""

    return f"""<div class="node-detail-wrap">
  <div class="nt node-detail-card">
    <div class="nt-top">{cat_badge}{page_html}<span class="nt-type">{node.type}</span></div>
    <div class="nt-body">{content}</div>
    {ann_html}
    {trans_html}
    {tags_html}
    {actions_html}
  </div>
</div>"""


# ══════════════════════════════════════════════════════════════
# UI BUILDER
# ══════════════════════════════════════════════════════════════


def build_organize_tab():
    """Build the Organize tab UI — new layout with upper-lower tabs."""
    gr.HTML("<div class='tip'>整理笔记、构建知识树、查看文献关系</div>")

    # ── Top action bar ──
    with gr.Row():
        # Document selector (synced with other tabs)
        org_doc_selector = gr.Dropdown(
            choices=[("全部文献 (全局视图)", "__all__")],
            value="__all__",
            label="选择文献",
            interactive=True,
            scale=2,
        )
        search_input = gr.Textbox(
            label="搜索", placeholder="搜索知识节点和原文...", scale=3
        )
        search_btn = gr.Button("搜索", scale=1, size="sm")
        refresh_btn = gr.Button("刷新显示", scale=1, size="sm")
        summary_btn = gr.Button("生成摘要(AI)", variant="primary", scale=1, size="sm")

    agent_status = gr.HTML("<span class='agent-st'>等待操作...</span>")
    stats_html = gr.HTML(render_stats({"docs": 0, "notes": 0, "nodes": 0}))
    search_result_html = gr.HTML("")

    # ── Main area: upper-lower tab switching ──
    with gr.Tabs():
        with gr.Tab("单文献知识树"):
            doc_tree_html = gr.HTML(
                "<div class='nc-empty'>上传文献并记录笔记后，知识树将在此显示</div>"
            )
        with gr.Tab("全局知识图谱"):
            global_graph_html = gr.HTML(
                generate_empty_graph_html("解构笔记后，知识图谱将在此显示")
            )
            # Node detail display area (shows when clicking graph node)
            node_detail_html = gr.HTML("<div class='node-detail-wrap'></div>")

    # ── Hidden bridge textboxes ──
    selected_node_id = gr.Textbox(
        elem_id="selected-node-input",
        visible=False,
        show_label=False,
    )
    note_action_tb = gr.Textbox(
        elem_id="note-action-input",
        visible=False,
        show_label=False,
    )

    return {
        "org_doc_selector": org_doc_selector,
        "search_input": search_input,
        "search_btn": search_btn,
        "search_result_html": search_result_html,
        "doc_tree_html": doc_tree_html,
        "global_graph_html": global_graph_html,
        "node_detail_html": node_detail_html,
        "selected_node_id": selected_node_id,
        "note_action_tb": note_action_tb,
        "refresh_btn": refresh_btn,
        "summary_btn": summary_btn,
        "agent_status": agent_status,
        "stats_html": stats_html,
    }
