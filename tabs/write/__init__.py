"""
Write Tab — UI builder and handlers
====================================
Tab 3: Knowledge tree sidebar + free-form writing area + AI suggest.

v2.0 更新:
- 集成 KeywordSearchService 和 SemanticSearchService
- 支持混合搜索 (HybridSearchService)
- 搜索结果渲染增强

Exports:
    build_write_tab()      -> dict of Gradio components
    handle_download()      -> Markdown file export handler
    handle_write_search()  -> knowledge tree search handler
    handle_ai_suggest()    -> AI continuation suggestion
"""

import os
import tempfile
import gradio as gr

from core.utils import esc
from agents.base import call_llm
from knowledge.search import search_nodes
from ui.echarts_graph import generate_tree_echarts_html, generate_empty_graph_html

# 尝试导入新版搜索服务
try:
    from services.search import KeywordSearchService, HybridSearchService, SearchResult
    NEW_SEARCH_AVAILABLE = True
except ImportError:
    NEW_SEARCH_AVAILABLE = False


# ══════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════


def _render_tree_sidebar(tree):
    """Render knowledge tree as ECharts tree graph for sidebar."""
    if not tree.nodes:
        return generate_empty_graph_html("解构笔记后，知识树将在此显示", height=500)
    option = tree.to_echarts_tree_option()
    if not option:
        return generate_empty_graph_html("解构笔记后，知识树将在此显示", height=500)
    return generate_tree_echarts_html(option, height=500)


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
        
        content_preview = highlight or (esc(content[:80]) + ("..." if len(content) > 80 else ""))
        
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
        
        icon = '📄' if ntype == 'document' else '📝' if ntype == 'note' else '🏷' if ntype == 'tag' else '📑' if ntype == 'annotation' else '🌐'
        
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
    Search knowledge tree for write tab.
    
    v2.0 支持三种搜索模式:
    - keyword: 关键词搜索（默认）
    - semantic: 语义搜索
    - hybrid: 混合搜索
    
    Args:
        query: 搜索词
        tree: KnowledgeTree 实例
        lib: 文献库字典（可选，用于增强搜索）
        search_type: 搜索类型
        
    Returns:
        HTML 搜索结果
    """
    if not query or not query.strip():
        return _render_tree_sidebar(tree)

    # 尝试使用新版搜索服务
    if NEW_SEARCH_AVAILABLE and lib is not None:
        try:
            if search_type == "hybrid":
                service = HybridSearchService(tree=tree, lib=lib)
                results = service.search(query, top_k=15)
            else:
                service = KeywordSearchService(tree=tree, lib=lib)
                results = service.search(query, top_k=15)
            
            if results:
                return _render_search_results(results, tree)
        except Exception:
            pass  # 回退到旧版搜索
    
    # 旧版搜索
    results = search_nodes(tree, query)
    if not results:
        return f"<div class='nc-empty'>未找到与「{esc(query)}」相关的结果</div>"

    return _render_search_results(results, tree)


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
        Suggestion text
    """
    if not draft_text or not draft_text.strip():
        return "请先在写作区输入一些内容，AI 将基于你的知识库提供续写建议。"

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

    try:
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
        return result.strip()
    except Exception as e:
        return f"[AI 建议失败] {e}"


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
    """Build the Write tab UI with formatting toolbar."""
    gr.HTML(
        "<div class='tip'>左侧浏览知识树（文献-笔记-标签），右侧自由写作，AI 辅助续写</div>"
    )
    with gr.Row():
        with gr.Column(scale=3, min_width=280):
            with gr.Group():
                write_search = gr.Textbox(
                    label="搜索知识库", placeholder="输入关键词..."
                )
                write_search_btn = gr.Button("搜索", size="sm")
            gr.Markdown("### 知识树")
            ref_tree_html = gr.HTML(
                "<div class='nc-empty'>解构笔记后，知识树将在此显示</div>"
            )

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
        "write_search": write_search,
        "write_search_btn": write_search_btn,
        "ref_tree_html": ref_tree_html,
        "draft_text": draft_text,
        "draft_file": draft_file,
        "download_btn": download_btn,
        "ai_suggest_btn": ai_suggest_btn,
        "ai_suggest_out": ai_suggest_out,
    }
