"""
HTML Renderers
==============
Functions for rendering UI components as HTML strings.

Supports the new Crusher output format:
  - Per-note classification (方法/公式/图像/定义/观点/数据/其他)
  - AI tags + one-line comment
  - Overall summary
"""

from core.utils import esc, extract_pdf_by_page
from core.config import CATEGORY_COLORS


# ══════════════════════════════════════════════════════════════
# Tab 1: PDF Reader
# ══════════════════════════════════════════════════════════════


def get_total_pages(pid: str, lib: dict) -> int:
    """Get total page count for a document."""
    if not pid or pid not in lib:
        return 1
    fp = lib[pid].get("filepath", "")
    if not fp or not fp.lower().endswith(".pdf"):
        return 1
    pages = extract_pdf_by_page(fp)
    return max(len(pages), 1)


def render_pdf_text(pid: str, lib: dict, current_page: int = 1) -> str:
    """Render single page of PDF text with floating popup menu.

    Single-page view (WeChat Reading style):
    - Renders only one page at a time
    - Shows page indicator
    - Embeds popup JS for highlight/translate/copy
    """
    if not pid or pid not in lib:
        return "<div class='txt-empty'>选择文献后，文本将在此显示</div>"

    fp = lib[pid].get("filepath", "")
    if not fp or not fp.lower().endswith(".pdf"):
        text = lib[pid].get("text", "")
        if not text:
            return "<div class='txt-empty'>无文本内容</div>"
        paras = [p.strip() for p in text.split("\n") if p.strip()]
        h = ""
        for i, p in enumerate(paras):
            h += f"<p class='txt-para' data-para-id='{i}' data-page='1'>{esc(p)}</p>"
        indicator = "<div class='page-nav'><span class='page-indicator'>第 1 页 / 共 1 页</span></div>"
        return f"{indicator}<div class='txt-reader' data-current-page='1' data-total-pages='1'>{h}</div>"

    pages = extract_pdf_by_page(fp)
    if not pages:
        return "<div class='txt-empty'>未能提取文本</div>"

    total = len(pages)
    current_page = max(1, min(current_page, total))

    page_num, text = pages[current_page - 1]
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    h = ""
    for i, p in enumerate(paras):
        h += f"<p class='txt-para' data-para-id='{i}' data-page='{page_num}'>{esc(p)}</p>"

    indicator = f"<div class='page-nav'><span class='page-indicator'>第 {current_page} 页 / 共 {total} 页</span></div>"
    return f"{indicator}<div class='txt-reader' data-current-page='{current_page}' data-total-pages='{total}'>{h}</div>"


# ══════════════════════════════════════════════════════════════
# Tab 1: Note cards (reading notes)
# ══════════════════════════════════════════════════════════════


def render_note_cards(notes: list) -> str:
    """Render note cards for Tab 1 (supports highlight color badges)."""
    if not notes:
        return "<div class='nc-empty'>暂无笔记</div>"

    h = ""
    for n in reversed(notes):
        ntype = n.get("type", "笔记")
        color = n.get("color", "")
        annotation = n.get("annotation", "")
        translation = n.get("translation", "")
        badge_cls = f"nt-badge hl-{color}" if color else "nt-badge"
        badge_text = esc(ntype)
        # Color bar indicator
        color_bar = ""
        if color:
            color_map = {"red": "#fc8181", "yellow": "#fbd38d", "green": "#9ae6b4", "purple": "#d6bcfa"}
            bar_color = color_map.get(color, "#e2e8f0")
            color_bar = f" style='border-left:3px solid {bar_color}'"
        annotation_html = ""
        if annotation:
            annotation_html = f"\n  <div class=\"nt-annotation\">批注: {esc(annotation)}</div>"
        translation_html = ""
        if translation:
            translation_html = f"\n  <div class=\"nt-annotation\" style=\"border-left-color:var(--accent-green);\">译: {esc(translation)}</div>"
        h += f"""<div class="nt"{color_bar}>
  <div class="nt-top">
    <span class="{badge_cls}">{badge_text}</span>
    <span class="nt-page">p.{n['page']}</span>
    <span class="nt-ts">{esc(n['ts'])}</span>
  </div>
  <div class="nt-body">{esc(n['content'])}</div>{annotation_html}{translation_html}
</div>"""
    return f"<div class='nt-wrap'>{h}</div>"


# ══════════════════════════════════════════════════════════════
# Tab 2: Notes overview
# ══════════════════════════════════════════════════════════════


def render_notes_for_organize(notes: list) -> str:
    """Render notes summary for Tab 2 sidebar."""
    if not notes:
        return "<div class='nc-empty'>暂无笔记。请先在「阅读」页记录。</div>"

    h = f"<div class='org-summary'>共 {len(notes)} 条笔记</div>"
    for n in notes:
        preview = esc(n["content"][:60]) + ("..." if len(n["content"]) > 60 else "")
        h += f"""<div class="org-item">
  <span class="org-icon">&#9998;</span>
  <span class="org-preview">{preview}</span>
  <span class="nt-page">p.{n['page']}</span>
</div>"""
    return f"<div class='org-wrap'>{h}</div>"


# ══════════════════════════════════════════════════════════════
# Tab 2: Classified note cards (Crusher output)
# ══════════════════════════════════════════════════════════════


def render_classified_notes(
    data: dict, lib: dict = None, original_notes: list = None
) -> str:
    """Render Crusher output as classified note cards.

    Args:
        data: Crusher result {notes: [...], summary, domain}
        lib: Library for doc name lookup
        original_notes: Original note list for displaying original text
    """
    if not data or "notes" not in data:
        return "<div class='nc-empty'>无分析结果</div>"

    domain = esc(data.get("domain", ""))
    summary = esc(data.get("summary", ""))
    classified = data.get("notes", [])

    h = ""
    # Summary card
    if summary:
        h += f"""<div class="summary-card">
  <div class="summary-hdr"><span class="summary-badge">AI 摘要</span><span class="summary-domain">{domain}</span></div>
  <div class="summary-body">{summary}</div>
</div>"""

    # Per-note classification cards
    for cn in classified:
        idx = cn.get("index", 0)
        cat = cn.get("category", "其他")
        tags = cn.get("tags", [])
        color = CATEGORY_COLORS.get(cat, "#a0aec0")

        # Get original note text
        original_text = ""
        original_page = ""
        if original_notes and isinstance(idx, int) and 0 <= idx < len(original_notes):
            original_text = esc(original_notes[idx].get("content", ""))
            original_page = original_notes[idx].get("page", "")

        tags_html = "".join(f"<span class='cn-tag'>{esc(t)}</span>" for t in tags)
        page_html = (
            f"<div class='cn-page'>p.{original_page}</div>" if original_page else ""
        )
        h += f"""<div class="cn-card">
  <div class="cn-top">
    <span class="cn-cat" style="background:{color}20;color:{color};border:1px solid {color}40">{esc(cat)}</span>
    <span class="cn-idx">#{idx}</span>
  </div>
  <div class="cn-body">{original_text}</div>
  {page_html}
  <div class="cn-tags">{tags_html}</div>
</div>"""

    return f"<div class='cn-wrap'>{h}</div>"


# ══════════════════════════════════════════════════════════════
# Tab 3: Knowledge tree (sidebar)
# ══════════════════════════════════════════════════════════════

_TYPE_ICONS = {
    "domain": "&#127760;",  # globe
    "document": "&#128196;",  # page
    "note": "&#128221;",  # memo
    "tag": "&#127991;",  # label
}

_TYPE_COLORS = {
    "domain": "#5b8def",
    "document": "#48bb78",
    "note": "#ecc94b",
    "tag": "#9f7aea",
}


def render_knowledge_tree(tree_data: list) -> str:
    """Render hierarchical knowledge tree with full note details.

    Args:
        tree_data: Output of KnowledgeTree.build_tree_data()
    """
    if not tree_data:
        return "<div class='nc-empty'>暂无知识树。请先在「知识图谱」页解构笔记。</div>"

    def _render(node: dict, level: int = 0) -> str:
        ntype = node.get("type", "")
        label = esc(node.get("label", ""))
        content = node.get("content", "")
        icon = _TYPE_ICONS.get(ntype, "")
        color = _TYPE_COLORS.get(ntype, "#888")
        children = node.get("children", [])
        meta = node.get("metadata", {})
        cat = meta.get("category", "")
        tags = node.get("tags", [])

        indent = level * 18
        cat_badge = ""
        if cat and ntype == "note":
            cat_color = CATEGORY_COLORS.get(cat, "#a0aec0")
            cat_badge = f"<span class='kt-cat' style='background:{cat_color}20;color:{cat_color}'>{esc(cat)}</span>"

        # Show full content for notes, not just label
        detail_html = ""
        if ntype == "note" and content and content != label:
            detail_html = f"<div class='kt-detail'>{esc(content)}</div>"

        # Show tags
        tags_html = ""
        if tags and ntype in ("note", "document"):
            tags_html = (
                "<div class='kt-tags'>"
                + "".join(f"<span class='kt-tag-item'>{esc(t)}</span>" for t in tags)
                + "</div>"
            )

        html = f"""<div class="kt-node" style="--kt-indent:{indent}px;padding-left:{indent}px">
  <div class="kt-node-header">
    <span class="kt-icon" style="color:{color}">{icon}</span>
    {cat_badge}
    <span class="kt-label">{label}</span>
  </div>
  {detail_html}
  {tags_html}
</div>"""
        for child in children:
            html += _render(child, level + 1)
        return html

    h = ""
    for root in tree_data:
        h += _render(root)
    return f"<div class='kt-wrap'>{h}</div>"


# ══════════════════════════════════════════════════════════════
# Stats bar
# ══════════════════════════════════════════════════════════════


def render_stats(s: dict) -> str:
    """Render statistics bar."""
    items = [
        ("Docs", s.get("docs", 0)),
        ("Notes", s.get("notes", 0)),
        ("Nodes", s.get("nodes", 0)),
    ]
    h = ""
    for label, val in items:
        h += f"<div class='si'><span class='si-l'>{label}</span><span class='si-v'>{val}</span></div>"
    return f"<div class='stats-row'>{h}</div>"


# ══════════════════════════════════════════════════════════════
# Node detail panel
# ══════════════════════════════════════════════════════════════


def render_node_detail(node: dict = None) -> str:
    """Render knowledge node detail panel — full card view with all info."""
    if not node:
        return "<div class='node-detail'><div class='nc-empty'>点击图谱节点查看详情</div></div>"

    ntype = node.get("type", "unknown")
    nid = esc(node.get("id", ""))
    label = esc(node.get("label", ""))
    content = esc(node.get("content", label))
    source_pid = node.get("source_pid", "")
    parent_id = esc(node.get("parent_id", "") or "")
    weight = node.get("weight", 0)
    ts = esc(node.get("ts", ""))
    meta = node.get("metadata", {})
    cat = meta.get("category", "")
    comment = meta.get("comment", "")
    page = meta.get("page", "")
    children = node.get("children", [])
    tags = node.get("tags", [])

    h = f"""<div class='node-detail'>
  <div class='node-detail-header'>
    <span class='node-detail-type {ntype}'>{ntype.upper()}</span>
    <span class='node-detail-id'>{nid}</span>
    <span class='nt-ts' style='margin-left:auto'>{ts}</span>
  </div>
  <div class='node-detail-content'>{content}</div>"""

    # Category badge
    if cat:
        cat_color = CATEGORY_COLORS.get(cat, "#a0aec0")
        h += f"<div class='node-cat-row'><span class='cn-cat' style='background:{cat_color}20;color:{cat_color};border:1px solid {cat_color}40'>{esc(cat)}</span></div>"

    # Page info
    if page:
        h += f"<div style='font-size:.78em;color:#718096;margin-bottom:4px;'>页码: p.{page}</div>"

    # AI comment
    if comment:
        h += f"<div class='node-comment'>AI: {esc(comment)}</div>"

    # Tags
    if tags:
        tags_html = "".join(f"<span class='cn-tag'>{esc(t)}</span>" for t in tags)
        h += f"<div class='cn-tags' style='margin-bottom:8px'>{tags_html}</div>"

    # Children count
    if children:
        h += f"<div style='font-size:.78em;color:#718096;'>子节点: {len(children)} 个</div>"

    # Parent
    if parent_id:
        h += f"<div style='font-size:.78em;color:#718096;'>父节点: {parent_id}</div>"

    h += "</div>"
    return h


# ══════════════════════════════════════════════════════════════
# Synthesizer result (cross-document analysis)
# ══════════════════════════════════════════════════════════════


def render_synth_result(data: dict) -> str:
    """Render Synthesizer output: themes, cross-refs, insight."""
    if not data:
        return "<div class='nc-empty'>无合成结果</div>"

    h = ""
    # Insight card
    insight = data.get("insight", "")
    if insight:
        h += f"""<div class="summary-card">
  <div class="summary-hdr"><span class="summary-badge">跨文献洞察</span></div>
  <div class="summary-body">{esc(insight)}</div>
</div>"""

    # Theme groups
    themes = data.get("themes", [])
    for t in themes:
        name = esc(t.get("name", ""))
        desc = esc(t.get("description", ""))
        indices = t.get("note_indices", [])
        idx_str = ", ".join(f"#{i}" for i in indices)
        h += f"""<div class="cn-card">
  <div class="cn-top">
    <span class="cn-cat" style="background:#5b8def20;color:#5b8def;border:1px solid #5b8def40">{name}</span>
    <span class="cn-idx">{idx_str}</span>
  </div>
  <div class="cn-comment">{desc}</div>
</div>"""

    # Cross-references
    cross_refs = data.get("cross_refs", [])
    if cross_refs:
        refs_html = ""
        for cr in cross_refs:
            refs_html += f"<div class='org-item'><span class='org-icon'>&#128279;</span><span class='org-preview'>#{cr.get('from_idx','')} &#8596; #{cr.get('to_idx','')} : {esc(cr.get('reason',''))}</span></div>"
        h += f"<div class='org-wrap' style='margin-top:8px'>{refs_html}</div>"

    return (
        f"<div class='cn-wrap'>{h}</div>"
        if h
        else "<div class='nc-empty'>无合成结果</div>"
    )
