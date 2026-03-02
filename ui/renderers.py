"""
HTML Renderers
==============
Functions for rendering UI components as HTML strings.
"""

from core.utils import esc, extract_pdf_by_page


def render_pdf_text(pid: str, lib: dict) -> str:
    """Render PDF text with clickable paragraphs.
    
    Args:
        pid: Document ID
        lib: Library store
        
    Returns:
        HTML string for text display
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
            h += f"<p class='txt-para' data-para-id='{i}'>{esc(p)}</p>"
        return f"<div class='txt-reader'>{h}</div>"

    pages = extract_pdf_by_page(fp)
    if not pages:
        return "<div class='txt-empty'>未能提取文本</div>"
    
    h = ""
    para_idx = 0
    for page_num, text in pages:
        paras = [p.strip() for p in text.split("\n") if p.strip()]
        body = ""
        for p in paras:
            body += f"<p class='txt-para' data-para-id='{para_idx}' data-page='{page_num}'>{esc(p)}</p>"
            para_idx += 1
        h += f"""<div class="txt-page">
  <div class="txt-page-hdr">Page {page_num}</div>
  {body}
</div>"""
    return f"<div class='txt-reader'>{h}</div>"


def render_note_cards(notes: list) -> str:
    """Render note cards for Tab 1.
    
    Args:
        notes: List of note dicts
        
    Returns:
        HTML string for note cards
    """
    if not notes:
        return "<div class='nc-empty'>暂无笔记</div>"
    
    h = ""
    for n in reversed(notes):
        h += f"""<div class="nt">
  <div class="nt-top">
    <span class="nt-badge">📝 笔记</span>
    <span class="nt-page">p.{n['page']}</span>
    <span class="nt-ts">{esc(n['ts'])}</span>
  </div>
  <div class="nt-body">{esc(n['content'])}</div>
</div>"""
    return f"<div class='nt-wrap'>{h}</div>"


def render_notes_for_organize(notes: list) -> str:
    """Render notes overview for Tab 2.
    
    Args:
        notes: List of note dicts
        
    Returns:
        HTML string for notes summary
    """
    if not notes:
        return "<div class='nc-empty'>暂无笔记。请先在「阅读」页记录。</div>"
    
    h = f"<div class='org-summary'>共 {len(notes)} 条笔记</div>"
    for n in notes:
        preview = esc(n["content"][:60]) + ("..." if len(n["content"]) > 60 else "")
        h += f"""<div class="org-item">
  <span class="org-icon">📝</span>
  <span class="org-preview">{preview}</span>
  <span class="nt-page">p.{n['page']}</span>
</div>"""
    return f"<div class='org-wrap'>{h}</div>"


def render_cards(data: dict, ids: list = None, lib: dict = None) -> str:
    """Render atom cards from Crusher output.
    
    Args:
        data: Crusher output dict with 'atoms' key
        ids: Optional list of atom IDs
        lib: Library store for source names
        
    Returns:
        HTML string for atom cards
    """
    if not data or "atoms" not in data:
        return "<div class='nc-empty'>无数据</div>"
    
    dom = esc(data.get("domain", "?"))
    c = data.get("confidence", 0)
    cs = f"{c * 100:.0f}%" if isinstance(c, (int, float)) else str(c)
    h = f"<div class='nc-meta'>{dom} · confidence {cs}</div>"
    
    for a in data["atoms"]:
        aid = a.get("id", "???")
        src_pid = a.get("source_pid", "")
        src_name = ""
        if lib and src_pid and src_pid in lib:
            src_name = lib[src_pid]["name"][:20]
        h += _render_single_card(a, aid, dom, src_name)
    return f"<div class='nc-wrap'>{h}</div>"


def render_all_cards(atoms: list, lib: dict) -> str:
    """Render all atom cards for Tab 3.
    
    Args:
        atoms: List of atom dicts
        lib: Library store for source names
        
    Returns:
        HTML string for all atom cards
    """
    h = ""
    for a in atoms:
        aid = a.get("id", "???")
        dom = esc(a.get("domain", "?"))
        src_pid = a.get("source_pid", "")
        src_name = ""
        if lib and src_pid and src_pid in lib:
            src_name = lib[src_pid]["name"][:20]
        h += _render_single_card(a, aid, dom, src_name)
    return f"<div class='nc-wrap'>{h}</div>"


def _render_single_card(a: dict, aid: str, dom: str, src_name: str) -> str:
    """Render a single atom card.
    
    Args:
        a: Atom dict
        aid: Atom ID
        dom: Domain string (already escaped)
        src_name: Source document name
        
    Returns:
        HTML string for single card
    """
    return f"""<div class="nc">
  <div class="nc-top">
    <span class="nc-tag">{dom}</span>
    <span class="nc-code">{esc(aid)}</span>
  </div>
  <div class="nc-axiom">{esc(a.get('axiom',''))}</div>
  <div class="nc-detail">
    <span class="nc-lbl">Method</span> {esc(a.get('methodology',''))}
  </div>
  <div class="nc-detail nc-bnd">
    <span class="nc-lbl">Boundary</span> {esc(a.get('boundary',''))}
  </div>
  <div class="nc-foot">
    <span class="nc-src">{esc(src_name)}</span>
  </div>
</div>"""


def render_stats(s: dict) -> str:
    """Render statistics bar.
    
    Args:
        s: Stats dict with docs, atoms, notes counts
        
    Returns:
        HTML string for stats display
    """
    items = [
        ("📄", "Docs", s.get("docs", 0)),
        ("⚛️", "Atoms", s.get("atoms", 0)),
        ("✏️", "Notes", s.get("notes", 0)),
        ("🌳", "Nodes", s.get("nodes", 0)),
    ]
    h = ""
    for icon, label, val in items:
        h += f"<div class='si'><span class='si-i'>{icon}</span><span class='si-l'>{label}</span><span class='si-v'>{val}</span></div>"
    return f"<div class='stats-row'>{h}</div>"


def render_node_detail(node: dict = None) -> str:
    """Render knowledge node detail panel.
    
    Args:
        node: Knowledge node dict
        
    Returns:
        HTML string for node detail
    """
    if not node:
        return "<div class='node-detail'><div class='nc-empty'>点击图谱节点查看详情</div></div>"
    
    node_type = node.get("type", "unknown")
    h = f"""<div class='node-detail'>
  <div class='node-detail-header'>
    <span class='node-detail-type {node_type}'>{node_type.upper()}</span>
    <span class='node-detail-id'>{esc(node.get('id', '???'))}</span>
  </div>
  <div class='node-detail-content'>{esc(node.get('content', node.get('label', '')))}</div>"""
    
    # Render annotations if any
    annotations = node.get("annotations", [])
    if annotations:
        h += "<div class='node-annotations'>"
        for ann in annotations:
            h += f"""<div class='node-annotation'>
  <div class='node-annotation-agent'>🤖 {esc(ann.get('agent', 'AI'))}</div>
  <div>{esc(ann.get('content', ''))}</div>
</div>"""
        h += "</div>"
    
    h += "</div>"
    return h


def render_search_results(nodes: list, query: str) -> str:
    """Render search results summary.
    
    Args:
        nodes: List of matching nodes
        query: Search query
        
    Returns:
        HTML string for search results
    """
    if not nodes:
        return f"<div class='search-result'><span class='search-result-count'>未找到与 \"{esc(query)}\" 相关的结果</span></div>"
    
    return f"<div class='search-result'><span class='search-result-count'>找到 {len(nodes)} 个与 \"{esc(query)}\" 相关的节点</span></div>"
