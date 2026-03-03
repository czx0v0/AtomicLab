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

from core.config import APP_TITLE, ENABLE_AUTH, AUTH_PASSWORD
from ui.styles import CSS, HEADER_HTML
from ui.global_js import ECHARTS_HEAD, GLOBAL_JS
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
)
from tabs.organize import (
    build_organize_tab,
    handle_generate,
    handle_search,
    handle_node_select,
    handle_node_edit,
    _render_graph,
    _render_doc_graph,
)
from tabs.write import (
    build_write_tab,
    handle_download,
    handle_write_search,
    handle_ai_suggest,
)
from tabs.chat import build_chat_tab, handle_chat_send, handle_chat_clear, handle_ai_ask


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

    with gr.Tabs():
        with gr.Tab("阅读"):
            read = build_read_tab()
        with gr.Tab("知识图谱"):
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
        fn=handle_upload,
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
        ],
    ).then(
        fn=lambda t: (_render_graph(t), _render_doc_graph(t)),
        inputs=[tree_st],
        outputs=[org["graph_html"], org["doc_graph_html"]],
    )
    read["pdf_selector"].change(
        fn=handle_select_pdf,
        inputs=[read["pdf_selector"], lib_st],
        outputs=[page_st, read["pdf_text_html"], read["file_list_html"]],
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
        inputs=[read["view_mode"], read["pdf_selector"], lib_st, page_st],
        outputs=[read["pdf_text_html"], read["pdf_embed_html"]],
    )
    # Popup: highlight action → auto-save note (v2.0: also creates annotation node + refresh PDF view)
    read["highlight_action_tb"].change(
        fn=handle_highlight_action,
        inputs=[read["highlight_action_tb"], notes_st, read["pdf_selector"], tree_st, lib_st],
        outputs=[notes_st, read["notes_html"], tree_st, read["pdf_text_html"]],
    )
    # Popup: translate action → return result to hidden textbox
    read["translate_action_tb"].change(
        fn=handle_popup_translate,
        inputs=[read["translate_action_tb"]],
        outputs=[read["translate_result_tb"]],
    )

    # ── Tab 2: Organize ──
    org["gen_btn"].click(
        fn=handle_generate,
        inputs=[
            notes_st,
            read["pdf_selector"],
            lib_st,
            stats_st,
            tree_st,
        ],
        outputs=[
            org["classified_cards_out"],
            lib_st,
            stats_st,
            org["stats_html"],
            org["agent_status"],
            org["notes_overview"],
            org["graph_html"],
            tree_st,
            wrt["ref_tree_html"],
            org["doc_graph_html"],
        ],
    )
    org["search_btn"].click(
        fn=handle_search,
        inputs=[org["search_input"], tree_st, lib_st],
        outputs=[org["search_result_html"], org["graph_html"]],
    )
    org["search_input"].submit(
        fn=handle_search,
        inputs=[org["search_input"], tree_st, lib_st],
        outputs=[org["search_result_html"], org["graph_html"]],
    )
    org["selected_node_id"].change(
        fn=handle_node_select,
        inputs=[org["selected_node_id"], tree_st],
        outputs=[org["node_detail_html"], org["edit_content"], org["edit_tags"]],
    )
    org["save_node_btn"].click(
        fn=handle_node_edit,
        inputs=[org["selected_node_id"], org["edit_content"], org["edit_tags"], tree_st],
        outputs=[tree_st, org["graph_html"], org["node_detail_html"], org["doc_graph_html"], wrt["ref_tree_html"]],
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
