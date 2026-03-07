"""
HTML Renderers
==============
Functions for rendering UI components as HTML strings.

Supports the new Crusher output format:
  - Per-note classification (方法/公式/图像/定义/观点/数据/其他)
  - AI tags + one-line comment
  - Overall summary

v2.0 更新:
  - 支持 annotation 节点渲染
  - 支持 priority/color 显示
"""

from core.utils import esc, extract_pdf_by_page
from core.config import CATEGORY_COLORS

# 优先级颜色映射
PRIORITY_COLORS = {
    5: "#FF6B6B",  # 红色 - 核心观点
    4: "#FFA500",  # 橙色 - 重要内容
    3: "#FFE66D",  # 黄色 - 值得注意
    2: "#4ECDC4",  # 绿色 - 参考信息
    1: "#45B7D1",  # 蓝色 - 一般记录
}

PRIORITY_LABELS = {
    5: "核心观点",
    4: "重要内容",
    3: "值得注意",
    2: "参考信息",
    1: "一般记录",
}


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


def _apply_highlights_to_text(text: str, highlights: list, page: int) -> str:
    """Apply stored highlights to text content.

    Args:
        text: Original text
        highlights: List of highlight dicts with 'content', 'page', 'color'
        page: Current page number

    Returns:
        Text with <mark> tags applied for matching highlights
    """
    if not highlights:
        return esc(text)

    # Filter highlights for current page
    page_highlights = [h for h in highlights if h.get("page") == page]
    if not page_highlights:
        return esc(text)

    result = text
    # Sort by content length descending to handle overlapping matches
    page_highlights.sort(key=lambda h: len(h.get("content", "")), reverse=True)

    for hl in page_highlights:
        content = hl.get("content", "")
        color = hl.get("color", "yellow")
        if content and content in result:
            # Replace first occurrence only to avoid duplicates
            mark_html = f'<mark class="hl-{color}" data-note-id="{hl.get("id", "")}">{esc(content)}</mark>'
            result = result.replace(content, f"__HL_MARK_{hl.get('id', '')}__", 1)
            result = result.replace(f"__HL_MARK_{hl.get('id', '')}__", mark_html)

    # Escape any remaining unprocessed text parts
    # Since we already escaped in mark_html, we need to be careful
    return result


def render_pdf_text(pid: str, lib: dict, current_page: int = 1) -> str:
    """Render single page of PDF text with floating popup menu.

    Single-page view (WeChat Reading style):
    - Renders only one page at a time
    - Shows page indicator
    - Embeds popup JS for highlight/translate/copy
    - **v2.0: Persists highlights from stored notes**
    """
    if not pid or pid not in lib:
        return "<div class='txt-empty'>选择文献后，文本将在此显示</div>"

    # Get stored notes for this document to apply highlights
    doc_notes = lib[pid].get("notes", [])
    highlight_notes = [n for n in doc_notes if n.get("type") == "高亮"]

    fp = lib[pid].get("filepath", "")
    if not fp or not fp.lower().endswith(".pdf"):
        text = lib[pid].get("text", "")
        if not text:
            return "<div class='txt-empty'>无文本内容</div>"
        paras = [p.strip() for p in text.split("\n") if p.strip()]
        h = ""
        for i, p in enumerate(paras):
            # Apply stored highlights to this paragraph
            para_html = _apply_highlights_to_paragraph(p, highlight_notes, 1)
            h += f"<p class='txt-para' data-para-id='{i}' data-page='1'>{para_html}</p>"
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
        # Apply stored highlights to this paragraph
        para_html = _apply_highlights_to_paragraph(p, highlight_notes, page_num)
        h += f"<p class='txt-para' data-para-id='{i}' data-page='{page_num}'>{para_html}</p>"

    indicator = f"<div class='page-nav'><span class='page-indicator'>第 {current_page} 页 / 共 {total} 页</span></div>"
    return f"{indicator}<div class='txt-reader' data-current-page='{current_page}' data-total-pages='{total}'>{h}</div>"


def _apply_highlights_to_paragraph(para_text: str, notes: list, page: int) -> str:
    """Apply stored highlights to a paragraph.

    Supports multi-line highlights by matching partial content.

    Args:
        para_text: Paragraph text
        notes: List of note dicts
        page: Current page number

    Returns:
        HTML string with highlights applied
    """
    # Filter notes for current page
    page_notes = [n for n in notes if n.get("page") == page and n.get("content")]

    if not page_notes:
        return esc(para_text)

    # Sort by content length descending for better matching
    page_notes.sort(key=lambda n: len(n.get("content", "")), reverse=True)

    result = para_text
    applied_marks = []

    for note in page_notes:
        content = note.get("content", "").strip()
        color = note.get("color", "yellow")
        note_id = note.get("id", "")

        if not content:
            continue

        # Try exact match first
        if content in result:
            placeholder = f"__HLMARK_{len(applied_marks)}__"
            result = result.replace(content, placeholder, 1)
            applied_marks.append(
                {
                    "placeholder": placeholder,
                    "content": content,
                    "color": color,
                    "note_id": note_id,
                }
            )
        else:
            # Multi-line content: try matching each line/segment
            # Split by common whitespace patterns
            segments = [
                s.strip()
                for s in content.replace("\r\n", "\n").split("\n")
                if s.strip()
            ]
            for segment in segments:
                if len(segment) > 10 and segment in result:
                    placeholder = f"__HLMARK_{len(applied_marks)}__"
                    result = result.replace(segment, placeholder, 1)
                    applied_marks.append(
                        {
                            "placeholder": placeholder,
                            "content": segment,
                            "color": color,
                            "note_id": note_id,
                        }
                    )

    # Escape the remaining text
    result = esc(result)

    # Replace placeholders with actual mark tags
    for mark in applied_marks:
        mark_html = f'<mark class="hl-{mark["color"]}" data-note-id="{mark["note_id"]}">{esc(mark["content"])}</mark>'
        result = result.replace(esc(mark["placeholder"]), mark_html)

    return result


# ══════════════════════════════════════════════════════════════
# Tab 1: Note cards (reading notes)
# ══════════════════════════════════════════════════════════════


def render_note_cards(
    notes: list, collapsible: bool = True, filter_pid: str = None
) -> str:
    """Render note cards for Tab 1 (supports highlight color badges, priority, and expand/collapse).

    Args:
        notes: List of note dicts
        collapsible: Whether to enable expand/collapse functionality
        filter_pid: If provided, only show notes for this document

    Returns:
        HTML string for note cards
    """
    if not notes:
        return "<div class='nc-empty'>暂无笔记</div>"

    # Filter by source_pid if provided
    if filter_pid:
        notes = [n for n in notes if n.get("source_pid") == filter_pid]
        if not notes:
            return "<div class='nc-empty'>当前文献暂无笔记</div>"

    h = ""
    for idx, n in enumerate(reversed(notes)):
        ntype = n.get("type", "笔记")
        color = n.get("color", "")
        annotation = n.get("annotation", "")
        translation = n.get("translation", "")
        priority = n.get("priority", 3)
        note_id = n.get("id", f"note-{idx}")
        content = n.get("content", "")

        badge_cls = f"nt-badge hl-{color}" if color else "nt-badge"
        badge_text = esc(ntype)

        # Priority indicator
        priority_label = PRIORITY_LABELS.get(priority, "")
        priority_html = ""
        if priority and priority_label:
            priority_color = PRIORITY_COLORS.get(priority, "#FFE66D")
            priority_html = f" <span style='font-size:.7em;color:{priority_color};'>●{priority_label}</span>"

        # Color bar indicator
        color_bar = ""
        if color:
            color_map = {
                "red": "#fc8181",
                "yellow": "#fbd38d",
                "green": "#9ae6b4",
                "purple": "#d6bcfa",
                "orange": "#FFA500",
                "blue": "#45B7D1",
            }
            bar_color = color_map.get(color, "#e2e8f0")
            color_bar = f" style='border-left:3px solid {bar_color}'"

        annotation_html = ""
        if annotation:
            annotation_html = (
                f'\n  <div class="nt-annotation"><b>批注:</b> {esc(annotation)}</div>'
            )
        translation_html = ""
        if translation:
            translation_html = (
                f'\n  <div class="nt-translation"><b>译:</b> {esc(translation)}</div>'
            )

        # 截图图片显示
        image_html = ""
        image_data = n.get("image", "")
        source_pid = n.get("source_pid", "")
        page_num = n.get("page", 1)
        if image_data:
            # 截图类型：显示图片缩略图，点击跳转到原文位置
            image_html = f'\n  <div class="nt-image"><img src="{image_data}" style="max-width:100%;border-radius:4px;cursor:pointer" onclick="jumpToSource(\'{source_pid}\', {page_num})" title="点击跳转到原文位置" /></div>'

        # Tags display (AI tags + manual tags with different colors)
        ai_tags = n.get("ai_tags", [])
        manual_tags = n.get("manual_tags", [])
        # Fallback: old "tags" field treated as AI tags
        if not ai_tags and not manual_tags:
            ai_tags = n.get("tags", [])

        tags_html = ""
        if ai_tags or manual_tags:
            tags_parts = []
            for t in ai_tags:
                tags_parts.append(f'<span class="cn-tag ai-tag">{esc(t)}</span>')
            for t in manual_tags:
                tags_parts.append(f'<span class="cn-tag manual-tag">{esc(t)}</span>')
            tags_html = '<div class="cn-tags">' + "".join(tags_parts) + "</div>"

        # Action buttons (no similar search)
        actions_html = f"""<div class="nt-actions">
  <span class="nt-action-btn" onclick="noteAction('translate', '{note_id}')">翻译</span>
  <span class="nt-action-btn" onclick="noteAction('tag', '{note_id}')">AI标签</span>
  <span class="nt-action-btn" onclick="showAnnotatePopup('{note_id}')">添加批注</span>
  <span class="nt-action-btn" onclick="noteAction('ask', '{note_id}')">问AI</span>
</div>
<div class="nt-manual-tag">
  <input type="text" class="manual-tag-input" placeholder="输入标签..." onkeydown="if(event.key==='Enter')manualTag('{note_id}', this)" />
  <span class="nt-action-btn" onclick="manualTag('{note_id}', this.previousElementSibling)">添加</span>
</div>"""

        # Expand/collapse for long content
        is_long = len(content) > 100
        collapsed_class = "nt-collapsed" if is_long and collapsible else ""
        expand_btn = ""
        if is_long and collapsible:
            expand_btn = f'<span class="nt-expand-btn" onclick="toggleNoteExpand(this)" data-note-id="{note_id}">展开 ▼</span>'

        h += f"""<div class="nt {collapsed_class}" data-note-id="{note_id}"{color_bar}>
  <div class="nt-top">
    <span class="{badge_cls}">{badge_text}</span>{priority_html}
    <span class="nt-page" onclick="scrollToHighlight('{note_id}')" style="cursor:pointer" title="点击定位">p.{n.get('page', '?')}</span>
    <span class="nt-ts">{esc(n.get('ts', ''))}</span>
    {expand_btn}
  </div>
  <div class="nt-body">{esc(content)}</div>{image_html}{annotation_html}{translation_html}{tags_html}
  {actions_html}
</div>"""
    return f"<div class='nt-wrap'>{h}</div>"


def render_annotation_cards(annotations: list) -> str:
    """
    渲染批注卡片（v2.0 新增）

    Args:
        annotations: 批注节点列表（TreeNode 格式的 dict）

    Returns:
        HTML 字符串
    """
    if not annotations:
        return "<div class='nc-empty'>暂无批注</div>"

    h = ""
    for ann in reversed(annotations):
        priority = ann.get("priority", 3)
        color = ann.get("color") or PRIORITY_COLORS.get(priority, "#FFE66D")
        selected_text = ann.get("selected_text", "")
        note = ann.get("note", "")
        page = ann.get("page_start") or ann.get("metadata", {}).get("page", "")

        priority_label = PRIORITY_LABELS.get(priority, "一般")

        h += f"""<div class="nt" style="border-left:4px solid {color}">
  <div class="nt-top">
    <span class="nt-badge" style="background:{color}20;color:{color}">●{esc(priority_label)}</span>
    {f"<span class='nt-page'>p.{page}</span>" if page else ""}
  </div>
  <div class="nt-body">{esc(selected_text)}</div>
  {f'<div class="nt-annotation">{esc(note)}</div>' if note else ''}
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


def render_knowledge_cards(tree_data: list, show_hierarchy: bool = True) -> str:
    """Render knowledge nodes as full cards with all details.

    This is an alternative to render_knowledge_tree that displays each node
    as a complete card similar to .cn-card style.

    Args:
        tree_data: Output of KnowledgeTree.build_tree_data()
        show_hierarchy: Whether to show hierarchical indentation

    Returns:
        HTML string with card-style node display
    """
    if not tree_data:
        return (
            "<div class='nc-empty'>暂无知识节点。请先在「知识图谱」页解构笔记。</div>"
        )

    def _render_card(node: dict, level: int = 0) -> str:
        ntype = node.get("type", "")
        label = esc(node.get("label", ""))
        content = node.get("content", "")
        node_id = node.get("id", "")
        icon = _TYPE_ICONS.get(ntype, "")
        color = _TYPE_COLORS.get(ntype, "#888")
        children = node.get("children", [])
        meta = node.get("metadata", {})
        cat = meta.get("category", "")
        comment = meta.get("comment", "")
        page = meta.get("page", "")
        tags = node.get("tags", [])

        indent = level * 16 if show_hierarchy else 0

        # Type badge
        type_badge = f"""<span class="cn-cat" style="background:{color}20;color:{color};border:1px solid {color}40">
            {icon} {ntype.upper()}
        </span>"""

        # Category badge for notes
        cat_badge = ""
        if cat and ntype == "note":
            cat_color = CATEGORY_COLORS.get(cat, "#a0aec0")
            cat_badge = f"""<span class="cn-cat" style="background:{cat_color}20;color:{cat_color};border:1px solid {cat_color}40">
                {esc(cat)}
            </span>"""

        # Page info
        page_html = f"<span class='cn-idx'>p.{page}</span>" if page else ""

        # Content - show full content, not truncated
        content_html = ""
        if content:
            content_html = f"<div class='cn-body'>{esc(content)}</div>"
        elif label:
            content_html = f"<div class='cn-body'>{label}</div>"

        # AI comment
        comment_html = ""
        if comment:
            comment_html = f"<div class='cn-comment'>AI: {esc(comment)}</div>"

        # Tags
        tags_html = ""
        if tags:
            tags_html = (
                "<div class='cn-tags'>"
                + "".join(f"<span class='cn-tag'>{esc(t)}</span>" for t in tags)
                + "</div>"
            )

        html = f"""<div class="cn-card" style="margin-left:{indent}px" data-node-id="{node_id}">
  <div class="cn-top">
    {type_badge}
    {cat_badge}
    {page_html}
  </div>
  {content_html}
  {comment_html}
  {tags_html}
</div>"""

        # Render children recursively
        for child in children:
            html += _render_card(child, level + 1)
        return html

    h = ""
    for root in tree_data:
        h += _render_card(root)
    return f"<div class='cn-wrap'>{h}</div>"


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


# ══════════════════════════════════════════════════════════════
# Tab 2 (Organize): Document-Note Tree with inline tags
# ══════════════════════════════════════════════════════════════


def render_doc_note_tree(tree, pid: str = None) -> str:
    """Render knowledge tree for a single document.

    - Domain/Document: collapsible text rows
    - Note: card style with inline tags and action buttons
    - Tag: embedded in Note card (not separate nodes)

    Args:
        tree: KnowledgeTree instance
        pid: Document ID to filter (if None, show all)

    Returns:
        HTML string
    """
    if not tree or not hasattr(tree, "nodes") or not tree.nodes:
        return "<div class='nc-empty'>解构笔记后，知识树将在此显示</div>"

    # Build tree data
    tree_data = tree.build_tree_data()
    if not tree_data:
        return "<div class='nc-empty'>解构笔记后，知识树将在此显示</div>"

    def _render_domain(domain: dict, idx: int) -> str:
        """Render domain as collapsible text row."""
        domain_id = f"domain-{idx}"
        label = esc(domain.get("label", "未知领域"))
        children = domain.get("children", [])

        # Filter documents by pid if specified
        if pid:
            children = [
                c
                for c in children
                if c.get("type") == "document" and c.get("source_pid") == pid
            ]

        if not children:
            return ""

        h = f"""<div class="org-domain-row" onclick="toggleOrgTree(this, '{domain_id}-content')">
  <span class="org-toggle">▼</span>
  <span class="org-icon">🌐</span>
  <span class="org-label">{label}</span>
  <span class="org-count">({len(children)} 文献)</span>
</div>
<div id="{domain_id}-content" class="org-domain-content">"""

        for doc_idx, doc in enumerate(children):
            h += _render_document(doc, f"{domain_id}-doc-{doc_idx}")

        h += "</div>"
        return h

    def _render_document(doc: dict, doc_id: str) -> str:
        """Render document as collapsible text row with summary."""
        label = esc(doc.get("label", "未知文献"))
        summary = esc(doc.get("metadata", {}).get("summary", ""))
        children = [c for c in doc.get("children", []) if c.get("type") == "note"]
        source_pid = doc.get("source_pid", "")

        h = f"""<div class="org-doc-row" onclick="toggleOrgTree(this, '{doc_id}-content')">
  <span class="org-toggle">▼</span>
  <span class="org-icon">📄</span>
  <span class="org-label">{label}</span>
  <span class="org-count">({len(children)} 笔记)</span>
</div>
<div id="{doc_id}-content" class="org-doc-content">"""

        if summary:
            h += f'<div class="org-doc-summary">{summary}</div>'

        for note_idx, note in enumerate(children):
            h += _render_note_card(note, f"{doc_id}-note-{note_idx}", source_pid)

        h += "</div>"
        return h

    def _render_note_card(note: dict, note_id: str, source_pid: str) -> str:
        """Render note as card with inline tags and action buttons."""
        content = esc(note.get("content", ""))
        node_id = note.get("id", note_id)
        meta = note.get("metadata", {})
        cat = meta.get("category", "")
        page = meta.get("page", "")
        ts = note.get("ts", "")
        annotation = meta.get("annotation", "")
        translation = meta.get("translation", "")

        # Collect AI tags from tree children and ai_tags field
        tag_children = [c for c in note.get("children", []) if c.get("type") == "tag"]
        ai_tags = [esc(t.get("label", "")) for t in tag_children]
        # Also include ai_tags from metadata/note
        for t in note.get("ai_tags", []):
            if esc(t) not in ai_tags:
                ai_tags.append(esc(t))
        # Fallback: old "tags" field treated as AI tags if no ai_tags
        if not ai_tags:
            for t in note.get("tags", []):
                ai_tags.append(esc(t))

        # Collect manual tags
        manual_tags = [esc(t) for t in note.get("manual_tags", [])]

        # Category badge
        cat_badge = ""
        if cat:
            cat_color = CATEGORY_COLORS.get(cat, "#a0aec0")
            cat_badge = f'<span class="cn-cat" style="background:{cat_color}20;color:{cat_color};border:1px solid {cat_color}40">{esc(cat)}</span>'

        # Page info
        page_html = f'<span class="nt-page">p.{page}</span>' if page else ""

        # Timestamp
        ts_html = f'<span class="nt-ts">{esc(ts)}</span>' if ts else ""

        # Inline tags (AI tags + manual tags with different colors)
        tags_html = ""
        if ai_tags or manual_tags:
            tags_parts = []
            for t in ai_tags:
                tags_parts.append(f'<span class="cn-tag ai-tag">{t}</span>')
            for t in manual_tags:
                tags_parts.append(f'<span class="cn-tag manual-tag">{t}</span>')
            tags_html = '<div class="cn-tags">' + "".join(tags_parts) + "</div>"

        # Annotation display
        annotation_html = ""
        if annotation:
            annotation_html = (
                f'<div class="nt-annotation"><b>批注:</b> {esc(annotation)}</div>'
            )

        # Translation display
        translation_html = ""
        if translation:
            translation_html = (
                f'<div class="nt-translation"><b>翻译:</b> {esc(translation)}</div>'
            )

        # Action buttons (unified with read tab)
        actions_html = f"""<div class="nt-actions">
  <span class="nt-action-btn" onclick="noteAction('translate', '{node_id}')">翻译</span>
  <span class="nt-action-btn" onclick="noteAction('tag', '{node_id}')">AI标签</span>
  <span class="nt-action-btn" onclick="showAnnotatePopup('{node_id}')">添加批注</span>
  <span class="nt-action-btn" onclick="noteAction('ask', '{node_id}')">问AI</span>
</div>
<div class="nt-manual-tag">
  <input type="text" class="manual-tag-input" placeholder="输入标签..." onkeydown="if(event.key==='Enter')manualTag('{node_id}', this)" />
  <span class="nt-action-btn" onclick="manualTag('{node_id}', this.previousElementSibling)">添加</span>
</div>"""

        return f"""<div class="nt org-note-card" data-note-id="{node_id}" data-source-pid="{source_pid}">
  <div class="nt-top">
    {cat_badge}
    {page_html}
    {ts_html}
  </div>
  <div class="nt-body">{content}</div>
  {annotation_html}
  {translation_html}
  {tags_html}
  {actions_html}
</div>"""

    h = ""
    for idx, domain in enumerate(tree_data):
        h += _render_domain(domain, idx)

    if not h.strip():
        return "<div class='nc-empty'>当前文献暂无已解构的笔记</div>"

    return f"<div class='org-tree-wrap'>{h}</div>"


def render_cited_notes(notes_data: list) -> str:
    """Render AI-cited notes as compact horizontal scrolling cards.

    Args:
        notes_data: List of note dicts with content, page, category, etc.

    Returns:
        HTML string of note cards in horizontal scroll container
    """
    if not notes_data:
        return ""

    h = ""
    for note in notes_data[:6]:  # Limit to 6
        content = esc(note.get("content", "")[:120])
        if len(note.get("content", "")) > 120:
            content += "..."
        page = note.get("page", "")
        cat = note.get("category", "")
        source = esc(note.get("source_name", "")[:20])
        source_pid = note.get("source_pid", "")

        cat_badge = ""
        if cat:
            cat_color = CATEGORY_COLORS.get(cat, "#a0aec0")
            cat_badge = f'<span class="cn-cat" style="background:{cat_color}20;color:{cat_color};font-size:.7em;padding:1px 4px">{esc(cat)}</span>'

        page_html = f'<span class="nt-page">p.{page}</span>' if page else ""
        source_html = f'<span class="nt-source">{source}</span>' if source else ""

        # 添加点击跳转功能
        onclick = f"onclick=\"jumpToSource('{source_pid}', {page})\"" if source_pid and page else ""

        h += f"""<div class="nt nt-cited" {onclick} style="cursor:pointer" title="点击跳转到原文">
  <div class="nt-top">{cat_badge}{page_html}{source_html}</div>
  <div class="nt-body">{content}</div>
</div>"""

    return f"""<div class="nt-cited-header" style="font-size:.75em;color:var(--text-muted);margin-top:8px">📎 引用来源 ({len(notes_data)}) - 点击跳转</div>
<div class='nt-cited-wrap'>{h}</div>"""
