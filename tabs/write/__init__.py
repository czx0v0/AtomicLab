"""
Write Tab — UI builder and handlers
====================================
Tab 3: Knowledge tree sidebar + free-form writing area + AI suggest.

v2.0 更新:
- 集成 KeywordSearchService 和 SemanticSearchService
- 支持混合搜索 (HybridSearchService)
- 搜索结果渲染增强

v2.1 更新:
- 添加知识树/知识图谱Tab切换
- 添加文献选择器，支持全局和单文献视图
- 复用整理页面的图谱组件

Exports:
    build_write_tab()      -> dict of Gradio components
    handle_download()      -> Markdown file export handler
    handle_write_search()  -> knowledge tree search handler
    handle_ai_suggest()    -> AI continuation suggestion
    handle_write_doc_select() -> document selector handler
    handle_write_graph_node_select() -> graph node click handler
"""

import os
import tempfile
import gradio as gr

from core.utils import esc
from agents.base import call_llm
from knowledge.search import search_nodes
from ui.echarts_graph import (
    generate_tree_echarts_html,
    generate_empty_graph_html,
    generate_echarts_html,
)
from ui.renderers import render_doc_note_tree

# 尝试导入新版搜索服务
try:
    from services.search import KeywordSearchService, HybridSearchService, SearchResult

    NEW_SEARCH_AVAILABLE = True
except ImportError:
    NEW_SEARCH_AVAILABLE = False


# ══════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════


def _render_tree_sidebar(tree, pid=None):
    """Render knowledge tree as card list for easier browsing."""
    return render_doc_note_tree(tree, pid)


def _render_write_graph(tree, pid=None, highlight_ids=None):
    """Render knowledge graph for write tab."""
    if not tree or not hasattr(tree, "nodes") or not tree.nodes:
        return generate_empty_graph_html("解构笔记后，知识图谱将在此显示")

    # If pid specified, filter to show only that document's nodes
    option = tree.to_echarts_option(highlight_ids)
    return generate_echarts_html(option, container_id="write-graph", height=450)


def _render_search_results(results, tree):
    """Render search results as filtered tree or result list."""
    if not results:
        return "<div class='nc-empty'>未找到相关结果</div>"

    h = f"<div class='search-result'><span class='search-result-count'>找到 {len(results)} 个结果</span></div>"
    for item in results[:15]:
        # 支持新版 SearchResult 和旧版 KnowledgeNode
        if hasattr(item, "node"):
            # 新版 SearchResult
            node = item.node
            score = item.score
            match_type = item.match_type
            highlight = item.highlight
        else:
            # 旧版 KnowledgeNode
            node = item
            score = getattr(node, "weight", 0.5)
            match_type = "keyword"
            highlight = None

        # 获取节点属性
        if hasattr(node, "type"):
            ntype = node.type
        elif isinstance(node, dict):
            ntype = node.get("type", "note")
        else:
            ntype = "note"

        if hasattr(node, "label"):
            label = esc(node.label)
        elif hasattr(node, "get_display_label"):
            label = esc(node.get_display_label())
        elif isinstance(node, dict):
            label = esc(node.get("label", node.get("heading", ""))[:40])
        else:
            label = "..."

        if hasattr(node, "content"):
            content = node.content
        elif isinstance(node, dict):
            content = node.get("content", "")
        else:
            content = ""

        content_preview = highlight or (
            esc(content[:80]) + ("..." if len(content) > 80 else "")
        )

        if hasattr(node, "metadata"):
            cat = node.metadata.get("category", "")
        elif isinstance(node, dict):
            cat = node.get("metadata", {}).get("category", "")
        else:
            cat = ""

        cat_badge = f" <span class='cn-tag'>{esc(cat)}</span>" if cat else ""

        # 匹配类型标记
        type_badge = ""
        if match_type == "semantic":
            type_badge = " <span class='cn-tag' style='background:#e6f0ff'>语义</span>"
        elif match_type == "hybrid":
            type_badge = " <span class='cn-tag' style='background:#f0ffe6'>混合</span>"

        icon = (
            "📄"
            if ntype == "document"
            else (
                "📝"
                if ntype == "note"
                else "🏷" if ntype == "tag" else "📑" if ntype == "annotation" else "🌐"
            )
        )

        h += (
            f"<div class='org-item'>"
            f"<span class='org-icon'>{icon}</span>"
            f"<span class='org-preview'><b>{label}</b>{cat_badge}{type_badge} — {content_preview}</span>"
            f"</div>"
        )
    return f"<div class='org-wrap'>{h}</div>"


# ══════════════════════════════════════════════════════════════
# HANDLERS
# ══════════════════════════════════════════════════════════════


def handle_download(text):
    """Download draft as Markdown file."""
    if not text or not text.strip():
        return None
    path = os.path.join(tempfile.gettempdir(), "atomic_lab_draft.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def handle_write_search(query, tree, lib=None, search_type="keyword"):
    """
    Search knowledge tree AND document full text for write tab.

    v2.0 支持三种搜索模式:
    - keyword: 关键词搜索（默认）
    - semantic: 语义搜索
    - hybrid: 混合搜索

    v2.1: Extended to search full text of documents in library.

    Args:
        query: 搜索词
        tree: KnowledgeTree 实例
        lib: 文献库字典（用于全文搜索）
        search_type: 搜索类型

    Returns:
        HTML 搜索结果
    """
    if not query or not query.strip():
        return _render_tree_sidebar(tree)

    all_results = []
    q_lower = query.lower().strip()

    # 1. Search knowledge tree nodes
    if NEW_SEARCH_AVAILABLE and lib is not None:
        try:
            if search_type == "hybrid":
                service = HybridSearchService(tree=tree, lib=lib)
                node_results = service.search(query, top_k=10)
            else:
                service = KeywordSearchService(tree=tree, lib=lib)
                node_results = service.search(query, top_k=10)
            all_results.extend(node_results)
        except Exception:
            node_results = search_nodes(tree, query)
            all_results.extend(node_results)
    else:
        node_results = search_nodes(tree, query)
        all_results.extend(node_results)

    # 2. Search document full text (extended in v2.1)
    doc_matches = []
    if lib:
        for pid, info in lib.items():
            doc_text = info.get("text", "")
            doc_name = info.get("name", "Unknown")
            if not doc_text:
                continue
            # Find all occurrences
            text_lower = doc_text.lower()
            pos = text_lower.find(q_lower)
            if pos >= 0:
                # Get context around match
                start = max(0, pos - 80)
                end = min(len(doc_text), pos + len(q_lower) + 80)
                snippet = doc_text[start:end]
                doc_matches.append(
                    {
                        "type": "fulltext",
                        "doc_name": doc_name,
                        "pid": pid,
                        "snippet": snippet,
                        "pos": pos,
                    }
                )

    if not all_results and not doc_matches:
        return f"<div class='nc-empty'>未找到与「{esc(query)}」相关的结果</div>"

    # Render combined results
    h = f"<div class='search-result'><span class='search-result-count'>找到 {len(all_results) + len(doc_matches)} 个结果</span></div>"

    # Document full-text matches first
    if doc_matches:
        h += "<div class='search-section'><b>📄 原文匹配</b></div>"
        for dm in doc_matches[:8]:
            snippet = esc(dm["snippet"])
            # Highlight match
            snippet = snippet.replace(q_lower, f"<mark>{q_lower}</mark>")
            h += (
                f"<div class='org-item' onclick=\"jumpToSource('{dm['pid']}', 1)\" style='cursor:pointer' title='点击跳转到原文'>"
                f"<span class='org-icon'>📄</span>"
                f"<span class='org-preview'><b>{esc(dm['doc_name'][:30])}</b> — ...{snippet}...</span>"
                f"</div>"
            )

    # Knowledge node matches
    if all_results:
        h += "<div class='search-section'><b>🔗 知识节点</b></div>"
        h += _render_search_results(all_results[:10], tree)

    return f"<div class='org-wrap'>{h}</div>"


def handle_search(
    query: str,
    search_type: str,
    graph,
    lib: dict = None,
    top_k: int = 10,
):
    """
    搜索文献内容（v2.0 新增 API）

    Args:
        query: 搜索词
        search_type: "keyword" | "semantic" | "hybrid"
        graph: KnowledgeGraph 或 KnowledgeTree 实例
        lib: 文献库字典
        top_k: 结果数量

    Returns:
        SearchResult 列表
    """
    if not query or not query.strip():
        return []

    if not NEW_SEARCH_AVAILABLE:
        # 回退到旧版搜索
        if hasattr(graph, "nodes"):
            return search_nodes(graph, query)[:top_k]
        return []

    try:
        if search_type == "semantic":
            from services.search import SemanticSearchService

            service = SemanticSearchService(graph=graph, tree=graph, lib=lib)
            return service.search(query, top_k=top_k)
        elif search_type == "hybrid":
            service = HybridSearchService(graph=graph, tree=graph, lib=lib)
            return service.search(query, top_k=top_k)
        else:
            service = KeywordSearchService(graph=graph, tree=graph, lib=lib)
            return service.search(query, top_k=top_k)
    except Exception:
        # 回退到旧版搜索
        if hasattr(graph, "nodes"):
            return search_nodes(graph, query)[:top_k]
        return []


def render_search_results(results) -> str:
    """
    渲染搜索结果（v2.0 API）

    Args:
        results: SearchResult 列表或 KnowledgeNode 列表

    Returns:
        HTML 字符串
    """
    return _render_search_results(results, None)


def handle_ai_suggest(draft_text, tree):
    """Generate AI continuation suggestion based on draft + knowledge tree.

    Args:
        draft_text: Current draft content
        tree: KnowledgeTree for context

    Returns:
        Suggestion text (with status prefix for streaming)
    """
    if not draft_text or not draft_text.strip():
        yield "请先在写作区输入一些内容，AI 将基于你的知识库提供续写建议。"
        return

    # Build context from knowledge tree
    context_parts = []
    if tree and hasattr(tree, "nodes") and tree.nodes:
        # Get summaries from domain nodes
        for node in tree.nodes.values():
            if node.type == "domain":
                context_parts.append(f"[领域] {node.content}")
            elif node.type == "note" and node.content:
                context_parts.append(f"[笔记] {node.content[:100]}")
                if len(context_parts) > 10:
                    break

    rag_context = "\n".join(context_parts) if context_parts else "(无知识库内容)"

    # Take last ~500 chars of draft for prompt
    tail = draft_text.strip()[-500:]

    # 发送准备状态
    yield "🔄 正在分析知识库..."

    try:
        # 发送生成状态
        yield "✍️ AI正在生成续写建议..."

        result = call_llm(
            system_prompt=(
                "你是学术写作助手。基于用户的知识库和当前草稿，提供续写建议。\n"
                "规则：\n"
                "1. 续写 2-3 句话，与前文自然衔接\n"
                "2. 如果知识库中有相关内容，优先引用\n"
                "3. 保持学术风格、简洁专业\n"
                "4. 仅输出续写内容，不加前缀说明"
            ),
            user_prompt=f"知识库:\n{rag_context}\n\n当前草稿末尾:\n{tail}\n\n请续写:",
            temperature=0.5,
            max_tokens=300,
        )
        yield result.strip()
    except Exception as e:
        yield f"❌ AI 建议失败: {e}"


def handle_write_doc_select(selected_pid, tree, lib):
    """Handle document selection change in write tab.

    Args:
        selected_pid: Selected document ID ("" or "__all__" for global view)
        tree: KnowledgeTree instance
        lib: Document library

    Returns:
        (tree_html, graph_html)
    """
    pid = None if selected_pid in ("", "__all__") else selected_pid
    tree_html = _render_tree_sidebar(tree, pid)
    graph_html = _render_write_graph(tree, pid)
    return tree_html, graph_html


def handle_write_graph_node_click(node_id, tree, lib):
    """Handle graph node click - if document node, switch to that document.

    Args:
        node_id: Clicked node ID
        tree: KnowledgeTree instance
        lib: Document library

    Returns:
        (new_selected_pid, tree_html, graph_html, node_detail_html)
    """
    if not node_id or not tree:
        return gr.update(), gr.update(), gr.update(), ""

    node = tree.get_node(node_id)
    if not node:
        return gr.update(), gr.update(), gr.update(), ""

    # If it's a document node, switch to that document
    new_pid = None
    if node.type == "document" and node.source_pid:
        new_pid = node.source_pid
    elif node.source_pid:
        # For note nodes, also switch to their parent document
        new_pid = node.source_pid

    # Render node detail
    from tabs.organize import handle_node_select

    node_detail = handle_node_select(node_id, tree)

    if new_pid:
        tree_html = _render_tree_sidebar(tree, new_pid)
        graph_html = _render_write_graph(tree, new_pid, highlight_ids=[node_id])
        return new_pid, tree_html, graph_html, node_detail

    # Just highlight the node without switching
    graph_html = _render_write_graph(tree, None, highlight_ids=[node_id])
    return gr.update(), gr.update(), graph_html, node_detail


def get_doc_choices(lib):
    """Generate document choices for dropdown.

    Args:
        lib: Document library

    Returns:
        List of (display_name, value) tuples
    """
    choices = [("全部文献 (全局视图)", "__all__")]
    if lib:
        for pid, info in lib.items():
            name = info.get("name", "未知文献")[:40]
            choices.append((name, pid))
    return choices


# ══════════════════════════════════════════════════════════════
# UI BUILDER
# ══════════════════════════════════════════════════════════════


_TOOLBAR_HTML = """<div class="write-toolbar">
  <button class="write-toolbar-btn" onclick="writeToolbarAction('bold')" title="粗体"><b>B</b></button>
  <button class="write-toolbar-btn" onclick="writeToolbarAction('italic')" title="斜体"><i>I</i></button>
  <span class="write-toolbar-sep"></span>
  <button class="write-toolbar-btn" onclick="writeToolbarAction('h1')" title="一级标题">H1</button>
  <button class="write-toolbar-btn" onclick="writeToolbarAction('h2')" title="二级标题">H2</button>
  <button class="write-toolbar-btn" onclick="writeToolbarAction('h3')" title="三级标题">H3</button>
  <span class="write-toolbar-sep"></span>
  <button class="write-toolbar-btn" onclick="writeToolbarAction('ul')" title="无序列表">&#8226; 列表</button>
  <button class="write-toolbar-btn" onclick="writeToolbarAction('ol')" title="有序列表">1. 列表</button>
  <button class="write-toolbar-btn" onclick="writeToolbarAction('quote')" title="引用">&gt; 引用</button>
  <span class="write-toolbar-sep"></span>
  <button class="write-toolbar-btn" onclick="writeToolbarAction('code')" title="行内代码">&lt;/&gt;</button>
  <button class="write-toolbar-btn" onclick="writeToolbarAction('codeblock')" title="代码块">代码块</button>
  <button class="write-toolbar-btn" onclick="writeToolbarAction('link')" title="链接">&#128279; 链接</button>
  <button class="write-toolbar-btn" onclick="writeToolbarAction('table')" title="表格">&#9638; 表格</button>
  <button class="write-toolbar-btn" onclick="writeToolbarAction('hr')" title="分割线">&#8212; 分割</button>
</div>"""


def build_write_tab():
    """Build the Write tab UI with formatting toolbar and knowledge panel."""
    gr.HTML(
        "<div class='tip'>左侧浏览知识树/图谱，支持切换文献视图；右侧自由写作，AI 辅助续写</div>"
    )
    with gr.Row():
        # ── Left: Knowledge Panel with Tabs ──
        with gr.Column(scale=3, min_width=300):
            # Document selector
            write_doc_selector = gr.Dropdown(
                choices=[("全部文献 (全局视图)", "__all__")],
                value="__all__",
                label="选择文献",
                interactive=True,
            )

            # Search bar
            with gr.Group():
                write_search = gr.Textbox(
                    label="搜索知识库", placeholder="输入关键词..."
                )
                write_search_btn = gr.Button("搜索", size="sm")

            # Knowledge Tree / Graph Tabs
            with gr.Tabs():
                with gr.Tab("知识树"):
                    ref_tree_html = gr.HTML(
                        "<div class='nc-empty'>解构笔记后，知识树将在此显示</div>"
                    )
                with gr.Tab("知识图谱"):
                    write_graph_html = gr.HTML(
                        generate_empty_graph_html("解构笔记后，知识图谱将在此显示")
                    )
                    # Node detail area
                    write_node_detail = gr.HTML("<div class='node-detail-wrap'></div>")

            # Hidden textbox for graph node click
            write_graph_node_id = gr.Textbox(
                elem_id="write-graph-node-input",
                visible=False,
                show_label=False,
            )

        # ── Right: Writing Area ──
        with gr.Column(scale=6, min_width=400):
            gr.Markdown("### 写作区")
            gr.HTML(_TOOLBAR_HTML)
            draft_text = gr.TextArea(
                label="",
                show_label=False,
                placeholder="在此自由写作，可参考左侧知识树...\n\n支持 Markdown 格式",
                lines=18,
                elem_id="write-draft",
            )
            with gr.Row():
                ai_suggest_btn = gr.Button("AI 续写建议", size="sm", scale=2)
                download_btn = gr.Button("导出 Markdown", variant="primary", scale=2)
            ai_suggest_out = gr.Textbox(
                label="AI 建议",
                lines=3,
                interactive=False,
                placeholder="点击「AI 续写建议」获取基于知识库的续写内容",
            )
            draft_file = gr.File(label="下载草稿", interactive=False)

    return {
        "write_doc_selector": write_doc_selector,
        "write_search": write_search,
        "write_search_btn": write_search_btn,
        "ref_tree_html": ref_tree_html,
        "write_graph_html": write_graph_html,
        "write_node_detail": write_node_detail,
        "write_graph_node_id": write_graph_node_id,
        "draft_text": draft_text,
        "draft_file": draft_file,
        "download_btn": download_btn,
        "ai_suggest_btn": ai_suggest_btn,
        "ai_suggest_out": ai_suggest_out,
    }
