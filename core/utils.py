"""
Utility Functions
=================
Common utilities for text processing, PDF extraction, and JSON parsing.
"""

import base64
import json
import re
import hashlib
import html as html_lib
from pathlib import Path


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


def get_demo_data_path() -> Path:
    """
    获取 demo_data 目录的绝对路径。

    采用相对 core/utils.py 文件位置的方式定位，兼容 ModelScope 容器环境：
    project_root / "demo_data"
    """
    # core/utils.py -> core/ -> project_root
    project_root = Path(__file__).resolve().parent.parent
    return project_root / "demo_data"


# ── Markdown 图片 Base64 内联（Demo 与阅读区共用）────────────────────────

_IMAGE_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}


def image_path_to_base64_data_url(image_path: Path) -> str | None:
    """读取图片文件并转为 data URL；路径不存在或读失败时返回 None。"""
    if not image_path.is_file():
        return None
    try:
        raw = image_path.read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        ext = image_path.suffix.lower()
        mime = _IMAGE_MIME.get(ext, "image/png")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None


def inline_images_in_markdown(content: str, base_dir: Path | str) -> str:
    """
    将 Markdown 中的图片引用改为 Base64 内联，便于跨平台（ModelScope/本地）100% 加载。

    支持：
    - ](/file=/absolute/path/to/img.png)  （MinerU 解析器产出）
    - ](images/xxx.png) 或 ](./fig/fig1.jpg)  （相对路径，相对 base_dir）
    """
    if not content or not content.strip():
        return content
    base_dir = Path(base_dir).resolve()

    # 1. ](/file=absolute_path) — MinerU 解析器产出
    def repl_file(m: re.Match) -> str:
        path_str = m.group(1).strip()
        path = Path(path_str)
        data_url = image_path_to_base64_data_url(path)
        return f"]({data_url})" if data_url else m.group(0)
    content = re.sub(r"\]\(/file=([^)]+)\)", repl_file, content)

    # 2. ](relative_or_absolute path with image extension)
    def repl_rel(m: re.Match) -> str:
        path_str = m.group(1).strip()
        if path_str.startswith("data:"):
            return m.group(0)
        path = (base_dir / path_str).resolve() if not Path(path_str).is_absolute() else Path(path_str)
        data_url = image_path_to_base64_data_url(path)
        return f"]({data_url})" if data_url else m.group(0)
    content = re.sub(
        r"\]\(([^)]+\.(?:png|jpg|jpeg|gif|webp|svg))\)",
        repl_rel,
        content,
        flags=re.IGNORECASE,
    )
    return content
