"""Tabs module: Gradio tab builders."""

from .read_tab import build_read_tab
from .organize_tab import build_organize_tab
from .write_tab import build_write_tab

__all__ = [
    "build_read_tab",
    "build_organize_tab",
    "build_write_tab",
]
