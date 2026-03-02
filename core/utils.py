"""
Utility Functions
=================
Common utilities for text processing, PDF extraction, and JSON parsing.
"""

import json
import re
import hashlib
import html as html_lib


def esc(text: str) -> str:
    """Escape HTML special characters.
    
    Args:
        text: Raw text to escape
        
    Returns:
        HTML-escaped string
    """
    return html_lib.escape(str(text))


def phash(name: str) -> str:
    """Generate a short hash ID for a document.
    
    Args:
        name: Document filename
        
    Returns:
        Hash ID in format 'PDF-XXXXXX'
    """
    return "PDF-" + hashlib.md5(name.encode()).hexdigest()[:6].upper()


def pjson(raw: str) -> dict | None:
    """Parse JSON with fallback for malformed responses.
    
    Attempts strict JSON parsing first, then tries to extract
    JSON object from within markdown or other text.
    
    Args:
        raw: Raw string potentially containing JSON
        
    Returns:
        Parsed dict or None if parsing fails
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON object from text
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None


def extract_pdf(filepath: str) -> str:
    """Extract all text from a PDF file.
    
    Args:
        filepath: Path to PDF file
        
    Returns:
        Extracted text or error message
    """
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(filepath)
        return "\n".join([p.extract_text() or "" for p in reader.pages]).strip()
    except Exception as e:
        return f"[PDF ERROR] {e}"


def extract_pdf_by_page(filepath: str) -> list[tuple[int, str]]:
    """Extract PDF text page by page.
    
    Args:
        filepath: Path to PDF file
        
    Returns:
        List of (page_number, text) tuples
    """
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(filepath)
        pages = []
        for i, page in enumerate(reader.pages):
            txt = page.extract_text() or ""
            if txt.strip():
                pages.append((i + 1, txt.strip()))
        return pages
    except Exception as e:
        return [(0, f"[PDF ERROR] {e}")]


def read_txt(filepath: str) -> str:
    """Read text from a file.
    
    Args:
        filepath: Path to text file
        
    Returns:
        File contents or error message
    """
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        return f"[READ ERROR] {e}"
