"""
Atomic Lab — Read · Organize · Write · Chat
=================================================
基于 Atomic-RAG 的原子化科研工作站

Architecture:
- core/:      Configuration, utilities, state management
- agents/:    AI agents (Crusher, Synthesizer, Translator, Conversation, Router)
- knowledge/: Knowledge tree model and search
- ui/:        Styles, HTML renderers, global JS
- tabs/:      Tab UI builders and handlers (Read, Organize, Write, Chat)
"""

import gradio as gr

from core.config import APP_TITLE, ENABLE_AUTH, AUTH_PASSWORD, MODEL_DISPLAY_NAMES
from core.model_state import cooldown_manager
from ui.styles import CSS, HEADER_HTML
from ui.global_js import ECHARTS_HEAD, GLOBAL_JS
from ui.renderers import render_note_cards
from knowledge.tree_model import KnowledgeTree

from tabs.read import (
    build_read_tab,
    handle_upload,
    handle_select_pdf,
    handle_page_prev,
    handle_page_next,
    handle_mode_switch,
    handle_highlight_action,
    handle_popup_translate,
    handle_read_note_action,
)
from tabs.organize import (
    build_organize_tab,
    handle_refresh_tree,
    handle_generate_summary,
    handle_search,
    handle_note_action,
    handle_node_select,
    handle_org_doc_select,
    _render_graph,
)
from tabs.write import (
    build_write_tab,
    handle_download,
    handle_write_search,
    handle_ai_suggest,
    handle_write_doc_select,
    handle_write_graph_node_click,
    get_doc_choices,
    _render_write_graph,
)
from tabs.chat import build_chat_tab, handle_chat_send, handle_chat_clear, handle_ai_ask

# RAG服务集成
from services.rag_service import get_rag_service
from core.config import RAG_CONFIG

# 初始化RAG服务（使用全局单例）
rag_service = get_rag_service(RAG_CONFIG)
rag_service.load()  # 加载已有索引


# ══════════════════════════════════════════════════════════════
# MODEL SELECTOR HELPERS
# ══════════════════════════════════════════════════════════════


def _get_model_choices():
    """Return dropdown choices for model selector."""
    models = cooldown_manager.get_all_models()
    return [(MODEL_DISPLAY_NAMES.get(m, m), m) for m in models]


def _get_model_status_html():
    """Generate HTML badges showing model status."""
    status = cooldown_manager.get_status()
    available = sum(1 for s in status if not s["in_cooldown"])
    total = len(status)

    badges = []
    for s in status:
        name = s["display_name"]
        if s["in_cooldown"]:
            mins = s["cooldown_remaining_secs"] // 60
            badges.append(f'<span class="model-badge cooldown">{name} ({mins}m)</span>')
        elif s["is_preferred"]:
            badges.append(f'<span class="model-badge preferred">{name} ★</span>')
        else:
            badges.append(f'<span class="model-badge available">{name}</span>')

    return f"""<div class="model-status">
        <span class="model-label">{available}/{total} 可用</span>
        {"".join(badges)}
    </div>"""


def _handle_model_switch(model_id):
    """Handle model preference change."""
    cooldown_manager.set_preferred(model_id if model_id else None)
    return _get_model_status_html()


def _handle_reset_cooldowns():
    """Reset all model cooldowns."""
    cooldown_manager.reset_all()
    return _get_model_status_html()


# ══════════════════════════════════════════════════════════════
# GRADIO APP
# ══════════════════════════════════════════════════════════════

with gr.Blocks(title=APP_TITLE) as demo:
    # ── Shared State ──
    lib_st = gr.State({})
    stats_st = gr.State({"docs": 0, "notes": 0, "nodes": 0})
    notes_st = gr.State([])
    tree_st = gr.State(KnowledgeTree())
    page_st = gr.State(1)  # current reading page

    gr.HTML(HEADER_HTML)

    # ── Model Selector Row ──
    with gr.Row(elem_classes=["model-row"]):
        model_dropdown = gr.Dropdown(
            choices=_get_model_choices(),
            value=cooldown_manager.get_preferred(),
            label="首选模型",
            interactive=True,
            scale=2,
            container=False,
        )
        model_status_html = gr.HTML(_get_model_status_html())
        reset_cooldown_btn = gr.Button("重置冷却", size="sm", scale=0)

    with gr.Tabs():
        with gr.Tab("阅读"):
            read = build_read_tab()
        with gr.Tab("整理"):
            org = build_organize_tab()
        with gr.Tab("写作"):
            wrt = build_write_tab()
        with gr.Tab("AI 助手"):
            chat = build_chat_tab()

    # ═══════════════════════════════════════════════
    # EVENT BINDINGS
    # ═══════════════════════════════════════════════

    # ── Tab 1: Read ──
    read["upload_f"].change(
        fn=lambda files, lib, stats, tree: handle_upload(
            files, lib, stats, tree, rag_service
        ),
        inputs=[read["upload_f"], lib_st, stats_st, tree_st],
        outputs=[
            lib_st,
            stats_st,
            read["pdf_selector"],
            org["stats_html"],
            read["pdf_text_html"],
            page_st,
            read["file_list_html"],
            tree_st,
            read["upload_f"],  # Clear upload area after processing
        ],
    ).then(
        fn=lambda t: _render_graph(t),
        inputs=[tree_st],
        outputs=[org["global_graph_html"]],
    ).then(
        # Update write tab and organize tab document selectors
        fn=lambda lib, tree: (
            gr.update(choices=get_doc_choices(lib)),
            _render_write_graph(tree, None),
            gr.update(choices=get_doc_choices(lib)),
        ),
        inputs=[lib_st, tree_st],
        outputs=[
            wrt["write_doc_selector"],
            wrt["write_graph_html"],
            org["org_doc_selector"],
        ],
    )
    read["pdf_selector"].change(
        fn=handle_select_pdf,
        inputs=[read["pdf_selector"], lib_st, notes_st],
        outputs=[
            page_st,
            read["pdf_text_html"],
            read["file_list_html"],
            read["notes_html"],
        ],
    ).then(
        # Sync to organize tab (convert empty to __all__)
        fn=lambda pid: gr.update(value=pid if pid else "__all__"),
        inputs=[read["pdf_selector"]],
        outputs=[org["org_doc_selector"]],
    ).then(
        # Sync to write tab
        fn=lambda pid: gr.update(value=pid if pid else "__all__"),
        inputs=[read["pdf_selector"]],
        outputs=[wrt["write_doc_selector"]],
    )
    read["prev_btn"].click(
        fn=handle_page_prev,
        inputs=[page_st, read["pdf_selector"], lib_st],
        outputs=[page_st, read["pdf_text_html"]],
    )
    read["next_btn"].click(
        fn=handle_page_next,
        inputs=[page_st, read["pdf_selector"], lib_st],
        outputs=[page_st, read["pdf_text_html"]],
    )
    read["view_mode"].change(
        fn=handle_mode_switch,
        inputs=[read["view_mode"], read["pdf_selector"], lib_st, page_st, notes_st],
        outputs=[read["pdf_text_html"], read["pdf_embed_html"]],
    )
    # Popup: highlight action → auto-save note (v2.0: also creates annotation node + refresh PDF view)
    read["highlight_action_tb"].change(
        fn=handle_highlight_action,
        inputs=[
            read["highlight_action_tb"],
            notes_st,
            read["pdf_selector"],
            tree_st,
            lib_st,
        ],
        outputs=[notes_st, read["notes_html"], tree_st, read["pdf_text_html"], lib_st],
    ).then(
        # Auto-refresh graph after highlight
        fn=lambda t: _render_graph(t),
        inputs=[tree_st],
        outputs=[org["global_graph_html"]],
    )
    # Popup: translate action → return result to hidden textbox
    read["translate_action_tb"].change(
        fn=handle_popup_translate,
        inputs=[read["translate_action_tb"]],
        outputs=[read["translate_result_tb"]],
    )
    # Note card action buttons (translate, tag, annotate) in read tab
    read["note_action_tb"].change(
        fn=handle_read_note_action,
        inputs=[
            read["note_action_tb"],
            notes_st,
            read["pdf_selector"],
            tree_st,
            lib_st,
        ],
        outputs=[org["agent_status"], notes_st, read["notes_html"], tree_st],
    ).then(
        # Refresh organize tab views after read tab action
        fn=lambda t: _render_graph(t),
        inputs=[tree_st],
        outputs=[org["global_graph_html"]],
    )

    # ── Tab 2: Organize ──
    org["refresh_btn"].click(
        fn=handle_refresh_tree,
        inputs=[
            read["pdf_selector"],
            lib_st,
            stats_st,
            tree_st,
        ],
        outputs=[
            org["doc_tree_html"],
            wrt["ref_tree_html"],
            org["global_graph_html"],
            org["stats_html"],
            org["agent_status"],
        ],
    ).then(
        fn=lambda tree: _render_write_graph(tree, None),
        inputs=[tree_st],
        outputs=[wrt["write_graph_html"]],
    )
    org["summary_btn"].click(
        fn=handle_generate_summary,
        inputs=[
            notes_st,
            read["pdf_selector"],
            lib_st,
            stats_st,
            tree_st,
        ],
        outputs=[
            lib_st,
            stats_st,
            org["stats_html"],
            org["agent_status"],
            org["doc_tree_html"],
            tree_st,
            wrt["ref_tree_html"],
            org["global_graph_html"],
        ],
    ).then(
        # Also update write tab graph
        fn=lambda tree: _render_write_graph(tree, None),
        inputs=[tree_st],
        outputs=[wrt["write_graph_html"]],
    )
    # Organize document selector - syncs with other tabs
    org["org_doc_selector"].change(
        fn=handle_org_doc_select,
        inputs=[org["org_doc_selector"], tree_st, lib_st],
        outputs=[org["doc_tree_html"], org["global_graph_html"]],
    ).then(
        # Sync to write tab
        fn=lambda pid: gr.update(value=pid),
        inputs=[org["org_doc_selector"]],
        outputs=[wrt["write_doc_selector"]],
    ).then(
        # Sync to read tab (if not __all__)
        fn=lambda pid: gr.update(value=pid if pid != "__all__" else ""),
        inputs=[org["org_doc_selector"]],
        outputs=[read["pdf_selector"]],
    )
    org["search_btn"].click(
        fn=lambda query, tree, lib: handle_search(query, tree, lib, rag_service),
        inputs=[org["search_input"], tree_st, lib_st],
        outputs=[org["search_result_html"], org["global_graph_html"]],
    )
    org["search_input"].submit(
        fn=lambda query, tree, lib: handle_search(query, tree, lib, rag_service),
        inputs=[org["search_input"], tree_st, lib_st],
        outputs=[org["search_result_html"], org["global_graph_html"]],
    )
    org["note_action_tb"].change(
        fn=handle_note_action,
        inputs=[org["note_action_tb"], tree_st, lib_st, notes_st],
        outputs=[
            org["agent_status"],
            tree_st,
            org["doc_tree_html"],
            org["global_graph_html"],
            org["node_detail_html"],
            notes_st,
        ],
    ).then(
        # Sync read tab notes display after organize actions
        fn=lambda notes, pid: render_note_cards(notes, filter_pid=pid),
        inputs=[notes_st, read["pdf_selector"]],
        outputs=[read["notes_html"]],
    )
    org["selected_node_id"].change(
        fn=handle_node_select,
        inputs=[org["selected_node_id"], tree_st],
        outputs=[org["node_detail_html"]],
    )

    # ── Tab 3: Write ──
    wrt["download_btn"].click(
        fn=handle_download,
        inputs=[wrt["draft_text"]],
        outputs=[wrt["draft_file"]],
    )
    wrt["write_search_btn"].click(
        fn=handle_write_search,
        inputs=[wrt["write_search"], tree_st, lib_st],
        outputs=[wrt["ref_tree_html"]],
    )
    wrt["write_search"].submit(
        fn=handle_write_search,
        inputs=[wrt["write_search"], tree_st, lib_st],
        outputs=[wrt["ref_tree_html"]],
    )
    wrt["ai_suggest_btn"].click(
        fn=handle_ai_suggest,
        inputs=[wrt["draft_text"], tree_st],
        outputs=[wrt["ai_suggest_out"]],
    )
    # Document selector change - update tree and graph view + sync to other tabs
    wrt["write_doc_selector"].change(
        fn=handle_write_doc_select,
        inputs=[wrt["write_doc_selector"], tree_st, lib_st],
        outputs=[wrt["ref_tree_html"], wrt["write_graph_html"]],
    ).then(
        # Sync to organize tab
        fn=lambda pid: gr.update(value=pid),
        inputs=[wrt["write_doc_selector"]],
        outputs=[org["org_doc_selector"]],
    ).then(
        # Sync to read tab (if not __all__)
        fn=lambda pid: gr.update(value=pid if pid != "__all__" else ""),
        inputs=[wrt["write_doc_selector"]],
        outputs=[read["pdf_selector"]],
    )
    # Graph node click - show detail and optionally switch document
    wrt["write_graph_node_id"].change(
        fn=handle_write_graph_node_click,
        inputs=[wrt["write_graph_node_id"], tree_st, lib_st],
        outputs=[
            wrt["write_doc_selector"],
            wrt["ref_tree_html"],
            wrt["write_graph_html"],
            wrt["write_node_detail"],
        ],
    )

    # ── Tab 4: Chat ──
    chat["send_btn"].click(
        fn=handle_chat_send,
        inputs=[chat["msg_input"], chat["chatbot"], tree_st, lib_st, notes_st],
        outputs=[chat["chatbot"], chat["msg_input"]],
    )
    chat["msg_input"].submit(
        fn=handle_chat_send,
        inputs=[chat["msg_input"], chat["chatbot"], tree_st, lib_st, notes_st],
        outputs=[chat["chatbot"], chat["msg_input"]],
    )
    chat["clear_btn"].click(
        fn=handle_chat_clear,
        inputs=[],
        outputs=[chat["chatbot"], chat["msg_input"]],
    )
    # Bridge: "问AI" from reading page popup → auto-send to chat
    chat["ai_ask_input"].change(
        fn=handle_ai_ask,
        inputs=[chat["ai_ask_input"], chat["chatbot"], tree_st, lib_st, notes_st],
        outputs=[chat["chatbot"], chat["msg_input"]],
    )

    # ── Model Selector Events ──
    model_dropdown.change(
        fn=_handle_model_switch,
        inputs=[model_dropdown],
        outputs=[model_status_html],
    )
    reset_cooldown_btn.click(
        fn=_handle_reset_cooldowns,
        inputs=[],
        outputs=[model_status_html],
    )


# ══════════════════════════════════════════════════════════════
# LAUNCH
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    launch_kwargs = {
        "server_name": "0.0.0.0",
        "server_port": 7860,
        "theme": gr.themes.Soft(),
        "css": CSS,
        "js": GLOBAL_JS,
        "head": ECHARTS_HEAD,
    }
    if ENABLE_AUTH:
        launch_kwargs["auth"] = ("admin", AUTH_PASSWORD)
    demo.launch(**launch_kwargs)
