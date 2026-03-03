"""
Tabs Package
=============
UI tabs for Atomic Lab: Read, Organize, Write, Chat.
"""

from .read import (
    build_read_tab,
    handle_upload,
    handle_select_pdf,
    handle_page_prev,
    handle_page_next,
    handle_mode_switch,
    handle_highlight_action,
    handle_popup_translate,
)
from .organize import (
    build_organize_tab,
    handle_refresh_tree,
    handle_generate_summary,
    handle_synthesize,
    handle_search,
    handle_note_action,
    handle_node_select,
)
from .write import (
    build_write_tab,
    handle_download,
    handle_write_search,
    handle_ai_suggest,
)
from .chat import build_chat_tab, handle_chat_send, handle_chat_clear

__all__ = [
    "build_read_tab",
    "handle_upload",
    "handle_select_pdf",
    "handle_page_prev",
    "handle_page_next",
    "handle_mode_switch",
    "handle_highlight_action",
    "handle_popup_translate",
    "build_organize_tab",
    "handle_refresh_tree",
    "handle_generate_summary",
    "handle_synthesize",
    "handle_search",
    "handle_note_action",
    "handle_node_select",
    "build_write_tab",
    "handle_download",
    "handle_write_search",
    "handle_ai_suggest",
    "build_chat_tab",
    "handle_chat_send",
    "handle_chat_clear",
]
