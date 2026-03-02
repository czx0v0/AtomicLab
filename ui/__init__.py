"""UI module: styles and renderers."""

from .styles import CSS, HEADER_HTML
from .renderers import (
    render_pdf_text,
    render_note_cards,
    render_notes_for_organize,
    render_classified_notes,
    render_knowledge_tree,
    render_stats,
    render_node_detail,
    render_synth_result,
)

__all__ = [
    "CSS",
    "HEADER_HTML",
    "render_pdf_text",
    "render_note_cards",
    "render_notes_for_organize",
    "render_classified_notes",
    "render_knowledge_tree",
    "render_stats",
    "render_node_detail",
    "render_synth_result",
]
