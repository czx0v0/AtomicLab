"""
Write Tab
=========
Tab 3: Writing workspace with knowledge reference.
"""

import gradio as gr
import os
import tempfile

from ui.renderers import render_all_cards
from ui.echarts_graph import generate_tree_view_html
from knowledge.tree_model import KnowledgeTree
from knowledge.search import search_nodes, filter_by_type


def handle_download(text):
    """Download draft as Markdown file.
    
    Args:
        text: Draft text content
        
    Returns:
        File path or None
    """
    if not text or not text.strip():
        return None
    
    path = os.path.join(tempfile.gettempdir(), "atomic_lab_draft.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def handle_write_search(query, tree, lib):
    """Search for reference materials.
    
    Args:
        query: Search query
        tree: Knowledge tree
        lib: Library store
        
    Returns:
        Search results as cards HTML
    """
    if not query or not query.strip():
        return get_all_atom_cards(lib)
    
    results = search_nodes(tree, query)
    if not results:
        return f"<div class='nc-empty'>未找到与 \"{query}\" 相关的结果</div>"
    
    # Convert nodes to atoms for display
    atoms = []
    for node in results:
        if node.type == "atom":
            atoms.append({
                "id": node.metadata.get("original_id", node.id),
                "axiom": node.content,
                "methodology": node.metadata.get("methodology", ""),
                "boundary": node.metadata.get("boundary", ""),
                "domain": node.tags[0] if node.tags else "?",
                "source_pid": node.source_pid,
            })
    
    if not atoms:
        return f"<div class='nc-empty'>找到 {len(results)} 个节点，但无原子卡片</div>"
    
    return render_all_cards(atoms, lib)


def get_all_atom_cards(lib):
    """Get all atom cards.
    
    Args:
        lib: Library store
        
    Returns:
        HTML string
    """
    all_atoms = []
    for doc in lib.values():
        for a in doc["atoms"]:
            all_atoms.append(a)
    
    if not all_atoms:
        return "<div class='nc-empty'>暂无原子卡片。请先在「整理」页解构笔记。</div>"
    
    return render_all_cards(all_atoms, lib)


def render_tree_sidebar(tree):
    """Render tree view for sidebar.
    
    Args:
        tree: Knowledge tree
        
    Returns:
        HTML string
    """
    if not tree.nodes:
        return "<div class='nc-empty'>暂无知识树。请先解构笔记。</div>"
    
    # Build hierarchical structure
    roots = []
    for node in tree.nodes.values():
        if node.parent_id is None or node.parent_id not in tree.nodes:
            roots.append(_build_tree_node(node, tree))
    
    return generate_tree_view_html(roots)


def _build_tree_node(node, tree):
    """Build tree node dict with children.
    
    Args:
        node: Knowledge node
        tree: Knowledge tree
        
    Returns:
        Dict with children
    """
    children = []
    for child_id in node.children:
        child = tree.nodes.get(child_id)
        if child:
            children.append(_build_tree_node(child, tree))
    
    return {
        "id": node.id,
        "label": node.label,
        "type": node.type,
        "children": children,
    }


def build_write_tab(lib_st, tree_st, ref_cards_html):
    """Build the Write tab UI.
    
    Args:
        lib_st: Library state
        tree_st: Knowledge tree state
        ref_cards_html: Reference cards HTML component
        
    Returns:
        Dict of created components
    """
    gr.HTML("<div class='tip'>搜索知识库，参考左侧卡片，在右侧自由写作</div>")
    
    with gr.Row():
        # Left: Search + Reference
        with gr.Column(scale=3, min_width=280):
            with gr.Group():
                write_search = gr.Textbox(
                    label="搜索知识库",
                    placeholder="输入关键词搜索原子卡片...",
                )
                write_search_btn = gr.Button("搜索", size="sm")
            
            gr.Markdown("### 知识树")
            tree_view_html = gr.HTML(
                "<div class='nc-empty'>解构笔记后，知识树将在此显示</div>"
            )
            
            gr.Markdown("### 参考卡片")
            # ref_cards_html is passed in from app.py

        # Right: Text Editor
        with gr.Column(scale=6, min_width=400):
            gr.Markdown("### 写作区")
            draft_text = gr.TextArea(
                label="",
                show_label=False,
                placeholder="在此自由写作，可参考左侧原子卡片...\n\n支持 Markdown 格式",
                lines=20,
            )
            
            with gr.Row():
                draft_file = gr.File(label="下载草稿", interactive=False)
                download_btn = gr.Button("生成 Markdown 文件", variant="primary")
    
    # Event bindings
    download_btn.click(
        fn=handle_download,
        inputs=[draft_text],
        outputs=[draft_file],
    )
    
    def _search_and_update(query, tree, lib):
        cards = handle_write_search(query, tree, lib)
        tree_html = render_tree_sidebar(tree)
        return cards, tree_html
    
    write_search_btn.click(
        fn=_search_and_update,
        inputs=[write_search, tree_st, lib_st],
        outputs=[ref_cards_html, tree_view_html],
    )
    
    write_search.submit(
        fn=_search_and_update,
        inputs=[write_search, tree_st, lib_st],
        outputs=[ref_cards_html, tree_view_html],
    )
    
    # Update tree view when tab is selected (via refresh)
    def _refresh_tree_view(tree):
        return render_tree_sidebar(tree)
    
    return {
        "write_search": write_search,
        "tree_view_html": tree_view_html,
        "draft_text": draft_text,
        "draft_file": draft_file,
    }
