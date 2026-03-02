"""Core module: configuration, utilities, and state management."""

from .config import MS_KEY, API_BASE, MODEL_NAME
from .utils import esc, pjson, phash, extract_pdf, extract_pdf_by_page, read_txt
from .state import next_atom_id, next_note_id, next_node_id

__all__ = [
    "MS_KEY",
    "API_BASE",
    "MODEL_NAME",
    "esc",
    "pjson",
    "phash",
    "extract_pdf",
    "extract_pdf_by_page",
    "read_txt",
    "next_atom_id",
    "next_note_id",
    "next_node_id",
]
