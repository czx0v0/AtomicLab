"""
Atomic Lab v2.0 — Read · Organize · Write
基于 Atomic-RAG 的原子化科研工作站
"""

import gradio as gr
import os
import json
import re
import time
import hashlib
import tempfile
import html as html_lib
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()  # 本地开发用，魔搭空间通过环境变量配置

# ══════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════
MS_KEY = os.environ.get("MS_KEY", "")
API_BASE = "https://api-inference.modelscope.cn/v1"
MODEL_NAME = "Qwen/Qwen2.5-72B-Instruct"
ATOM_CTR = {"v": 0}
NOTE_CTR = {"v": 0}


# ══════════════════════════════════════════════════════════════
# UTILS
# ══════════════════════════════════════════════════════════════
def esc(t):
    return html_lib.escape(str(t))


def next_atom_id():
    ATOM_CTR["v"] += 1
    return f"ATC-{ATOM_CTR['v']:04d}"


def next_note_id():
    NOTE_CTR["v"] += 1
    return f"NT-{NOTE_CTR['v']:04d}"


def phash(name):
    return "PDF-" + hashlib.md5(name.encode()).hexdigest()[:6].upper()


def call_llm(sys_p, usr_p, temp=0.15, maxt=800):
    c = OpenAI(base_url=API_BASE, api_key=MS_KEY)
    r = c.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": sys_p},
            {"role": "user", "content": usr_p},
        ],
        temperature=temp,
        max_tokens=maxt,
    )
    return r.choices[0].message.content


def pjson(raw):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None


def extract_pdf(fp):
    try:
        from PyPDF2 import PdfReader

        r = PdfReader(fp)
        return "\n".join([p.extract_text() or "" for p in r.pages]).strip()
    except Exception as e:
        return f"[PDF ERROR] {e}"


def extract_pdf_by_page(fp):
    """提取 PDF 文本，按页分段"""
    try:
        from PyPDF2 import PdfReader

        r = PdfReader(fp)
        pages = []
        for i, p in enumerate(r.pages):
            txt = p.extract_text() or ""
            if txt.strip():
                pages.append((i + 1, txt.strip()))
        return pages
    except Exception as e:
        return [(0, f"[PDF ERROR] {e}")]


def _read_txt(fp):
    try:
        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        return f"[READ ERROR] {e}"


# ══════════════════════════════════════════════════════════════
# AGENT A — CRUSHER
# ══════════════════════════════════════════════════════════════
CRUSH_SYS = """你是 Atomic Lab 的知识解构引擎 Crusher。
职责：将学术文本或用户笔记解构为知识原子。

## 输出规则
1. 仅输出 JSON，不带 markdown 标记。
2. 结构：
{
  "atoms": [
    {
      "axiom": "公理化结论，≤30字，纯陈述句",
      "methodology": "实验路径或推导逻辑，≤50字",
      "boundary": "适用边界或实验局限，≤40字"
    }
  ],
  "domain": "学科领域（2-4字）",
  "confidence": 0.0-1.0
}
3. atoms 恰好 3 个。语气冷峻、无修饰。"""

CRUSH_USR = """## 上下文
{context}

## 待解构文本
{text}

执行语义解构。仅输出 JSON。"""


# ══════════════════════════════════════════════════════════════
# HANDLERS — Tab 1: Read
# ══════════════════════════════════════════════════════════════
def handle_upload(files, lib, stats):
    """文献上传 → 入库"""
    if not files:
        return lib, stats, gr.update(), render_stats(stats), render_pdf_text(None, lib)
    for f in files:
        fp = f if isinstance(f, str) else (f.name if hasattr(f, "name") else str(f))
        fn = os.path.basename(fp)
        pid = phash(fn)
        if pid in lib:
            continue
        text = extract_pdf(fp) if fp.lower().endswith(".pdf") else _read_txt(fp)
        lib[pid] = {"name": fn, "text": text, "atoms": [], "filepath": fp}
        stats["docs"] += 1

    choices = [(v["name"], k) for k, v in lib.items()]
    last_pid = choices[-1][1] if choices else None
    return (
        lib,
        stats,
        gr.update(choices=choices, value=last_pid),
        render_stats(stats),
        render_pdf_text(last_pid, lib),
    )


def handle_select_pdf(pid, lib):
    """选择文献 → 文本提取阅读"""
    return render_pdf_text(pid, lib)


def handle_save_note(page, content, notes, pid):
    """保存阅读笔记"""
    if not content or not content.strip():
        return notes, render_note_cards(notes)
    nid = next_note_id()
    note = {
        "id": nid,
        "type": "文字笔记",
        "content": content.strip(),
        "page": int(page) if page else 1,
        "ts": time.strftime("%H:%M"),
        "source_pid": pid or "",
    }
    notes.append(note)
    return notes, render_note_cards(notes)


# ══════════════════════════════════════════════════════════════
# HANDLERS — Tab 2: Organize
# ══════════════════════════════════════════════════════════════
def handle_generate(extra_notes, notes, pid, lib, stats):
    """智能解构：合并笔记 → Crusher"""
    all_text_parts = []
    for n in notes:
        prefix = f"[p.{n['page']}]"
        if n["content"]:
            all_text_parts.append(f"{prefix} {n['content']}")
    if extra_notes and extra_notes.strip():
        all_text_parts.append(extra_notes.strip())

    merged = "\n".join(all_text_parts)
    if not merged.strip():
        return (
            "<div class='nc-empty'>暂无笔记可解构。请先在「阅读」页记录笔记。</div>",
            lib,
            stats,
            render_stats(stats),
            "<span class='agent-st'>等待输入...</span>",
            get_all_atom_cards(lib),
        )

    ctx = lib[pid]["text"][:3000] if pid and pid in lib else "(无文献上下文)"

    try:
        raw = call_llm(CRUSH_SYS, CRUSH_USR.format(context=ctx, text=merged))
        data = pjson(raw)
        if not data or "atoms" not in data:
            return (
                f"<div class='nc-empty'>解析失败: {esc(raw[:120])}</div>",
                lib,
                stats,
                render_stats(stats),
                "<span class='agent-st'>Crusher: 解析失败</span>",
                get_all_atom_cards(lib),
            )

        new_ids = _register_atoms(data, pid, lib, stats)
        stats["notes"] += len(notes)

        status_msg = f"Crusher: {len(notes)} 条笔记 → {len(new_ids)} atoms"
        return (
            render_cards(data, new_ids, lib),
            lib,
            stats,
            render_stats(stats),
            f"<span class='agent-st'>{esc(status_msg)}</span>",
            get_all_atom_cards(lib),
        )
    except Exception as e:
        return (
            f"<div class='nc-empty'>Error: {esc(str(e)[:80])}</div>",
            lib,
            stats,
            render_stats(stats),
            f"<span class='agent-st'>Error: {esc(str(e)[:40])}</span>",
            get_all_atom_cards(lib),
        )


def _register_atoms(data, pid, lib, stats):
    new_ids = []
    for atom in data["atoms"]:
        aid = next_atom_id()
        atom["id"] = aid
        atom["source_pid"] = pid or ""
        atom["domain"] = data.get("domain", "")
        new_ids.append(aid)
        if pid and pid in lib:
            lib[pid]["atoms"].append(atom)
        stats["atoms"] += 1
    return new_ids


# ══════════════════════════════════════════════════════════════
# HANDLERS — Tab 3: Write
# ══════════════════════════════════════════════════════════════
def handle_download(text):
    """下载草稿为 Markdown"""
    if not text or not text.strip():
        return None
    path = os.path.join(tempfile.gettempdir(), "atomic_lab_draft.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def get_all_atom_cards(lib):
    """获取所有原子卡片"""
    all_atoms = []
    for doc in lib.values():
        for a in doc["atoms"]:
            all_atoms.append(a)
    if not all_atoms:
        return "<div class='nc-empty'>暂无原子卡片。请先在「整理」页解构笔记。</div>"
    return render_all_cards(all_atoms, lib)


# ══════════════════════════════════════════════════════════════
# RENDERERS
# ══════════════════════════════════════════════════════════════
def render_pdf_text(pid, lib):
    """渲染 PDF 提取文本（模拟高亮阅读）"""
    if not pid or pid not in lib:
        return "<div class='txt-empty'>选择文献后，文本将在此显示</div>"
    fp = lib[pid].get("filepath", "")
    if not fp or not fp.lower().endswith(".pdf"):
        text = lib[pid].get("text", "")
        if not text:
            return "<div class='txt-empty'>无文本内容</div>"
        paras = [p.strip() for p in text.split("\n") if p.strip()]
        h = "".join(f"<p class='txt-para'>{esc(p)}</p>" for p in paras)
        return f"<div class='txt-reader'>{h}</div>"

    pages = extract_pdf_by_page(fp)
    if not pages:
        return "<div class='txt-empty'>未能提取文本</div>"
    h = ""
    for page_num, text in pages:
        paras = [p.strip() for p in text.split("\n") if p.strip()]
        body = "".join(f"<p class='txt-para'>{esc(p)}</p>" for p in paras)
        h += f"""<div class="txt-page">
  <div class="txt-page-hdr">Page {page_num}</div>
  {body}
</div>"""
    return f"<div class='txt-reader'>{h}</div>"


def render_note_cards(notes):
    """渲染阅读笔记卡片"""
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


def render_notes_for_organize(notes):
    """Tab 2 左栏：笔记概览"""
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


def render_cards(data, ids=None, lib=None):
    """Scrivener-style atom cards"""
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


def render_all_cards(atoms, lib):
    """Tab 3 左栏：所有原子卡片"""
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


def _render_single_card(a, aid, dom, src_name):
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


def render_stats(s):
    items = [
        ("📄", "Docs", s["docs"]),
        ("⚛️", "Atoms", s["atoms"]),
        ("✏️", "Notes", s["notes"]),
    ]
    h = ""
    for icon, label, val in items:
        h += f"<div class='si'><span class='si-i'>{icon}</span><span class='si-l'>{label}</span><span class='si-v'>{val}</span></div>"
    return f"<div class='stats-row'>{h}</div>"


# ══════════════════════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════════════════════
CSS = """
/* ── Global ── */
.gradio-container{
  background:#fafaf8!important;color:#2d3748!important;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans SC',sans-serif!important;
  max-width:100%!important;
}
.dark .gradio-container{background:#fafaf8!important;color:#2d3748!important;}

/* ── Header ── */
.lab-hdr{text-align:center;padding:10px 0 6px;}
.lab-title{font-size:1.2em;font-weight:700;color:#2d3748;letter-spacing:2px;}
.lab-title span{color:#5b8def;}
.lab-sub{font-size:.72em;color:#a0aec0;letter-spacing:1px;margin-top:2px;}

/* ── Tip bar ── */
.tip{font-size:.82em;color:#718096;padding:8px 14px;background:#f7fafc;
  border-radius:6px;margin-bottom:10px;text-align:center;border:1px solid #e2e8f0;}

/* ── Tab labels ── */
button[role="tab"]{color:#2d3748!important;font-weight:600!important;font-size:.95em!important;}
button[role="tab"][aria-selected="true"]{color:#5b8def!important;border-color:#5b8def!important;}

/* ── Gradio Overrides ── */
.gr-group{background:#fff!important;border:1px solid #e2e8f0!important;border-radius:8px!important;box-shadow:0 1px 3px rgba(0,0,0,.04)!important;}
textarea,input[type="text"]{background:#fff!important;border:1px solid #e2e8f0!important;
  color:#2d3748!important;border-radius:6px!important;font-family:inherit!important;}
textarea:focus,input:focus{border-color:#5b8def!important;box-shadow:0 0 0 3px rgba(91,141,239,.12)!important;}
label,.label-wrap span{color:#718096!important;font-weight:500!important;}
button.primary{background:#5b8def!important;border:none!important;color:#fff!important;border-radius:6px!important;font-weight:600!important;}
button.primary:hover{background:#4a7ae0!important;box-shadow:0 2px 8px rgba(91,141,239,.25)!important;}
button.stop{background:#fff!important;border:1px solid #e2e8f0!important;color:#718096!important;border-radius:6px!important;}
button.stop:hover{background:#f7fafc!important;border-color:#cbd5e0!important;}
.prose h3,.markdown h3{color:#2d3748!important;font-size:.9em!important;font-weight:600!important;}
.prose,.markdown{color:#4a5568!important;}

/* ── PDF Text Reader ── */
.txt-reader{max-height:750px;overflow-y:auto;background:#fff;border:1px solid #e2e8f0;
  border-radius:8px;padding:16px 20px;}
.txt-empty{color:#a0aec0;font-size:.84em;padding:20px;text-align:center;}
.txt-page{margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #edf2f7;}
.txt-page:last-child{border-bottom:none;margin-bottom:0;padding-bottom:0;}
.txt-page-hdr{font-size:.75em;font-weight:700;color:#5b8def;text-transform:uppercase;
  letter-spacing:1px;margin-bottom:8px;padding:4px 8px;background:#eef3ff;
  border-radius:4px;display:inline-block;}
.txt-para{font-size:.9em;color:#2d3748;line-height:1.75;margin:0 0 6px;
  font-family:Georgia,'Noto Serif SC','Times New Roman',serif;}

/* ── Note Cards (Tab 1) ── */
.nt-wrap{display:flex;flex-direction:column;gap:8px;max-height:520px;overflow-y:auto;}
.nt{background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:10px 12px;
  transition:box-shadow .2s;}
.nt:hover{box-shadow:0 2px 8px rgba(0,0,0,.06);}
.nt-top{display:flex;align-items:center;gap:8px;margin-bottom:6px;font-size:.8em;}
.nt-badge{font-weight:600;color:#5b8def;background:#eef3ff;padding:2px 8px;border-radius:4px;font-size:.85em;}
.nt-page{color:#a0aec0;font-size:.85em;}
.nt-ts{color:#cbd5e0;font-size:.8em;margin-left:auto;}
.nt-body{font-size:.88em;color:#4a5568;line-height:1.5;}

/* ── Organize summary (Tab 2) ── */
.org-wrap{display:flex;flex-direction:column;gap:4px;}
.org-summary{font-size:.82em;color:#718096;font-weight:600;padding-bottom:6px;border-bottom:1px solid #e2e8f0;margin-bottom:4px;}
.org-item{display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:6px;font-size:.84em;
  background:#fff;border:1px solid #f0f0f0;transition:background .15s;}
.org-item:hover{background:#f7fafc;}
.org-icon{font-size:1em;flex-shrink:0;}
.org-preview{color:#4a5568;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}

/* ── Atom Cards (Scrivener index cards) ── */
.nc-wrap{display:flex;flex-direction:column;gap:10px;}
.nc-meta{font-size:.78em;color:#a0aec0;padding-bottom:4px;}
.nc-empty{color:#a0aec0;font-size:.84em;padding:16px;text-align:center;}
.nc{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px;
  box-shadow:0 1px 4px rgba(0,0,0,.05);transition:box-shadow .2s,transform .15s;}
.nc:hover{box-shadow:0 4px 12px rgba(0,0,0,.08);transform:translateY(-1px);}
.nc-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;}
.nc-tag{font-size:.7em;font-weight:600;color:#5b8def;background:#eef3ff;padding:2px 8px;border-radius:4px;letter-spacing:.5px;}
.nc-code{font-size:.72em;color:#a0aec0;font-family:'SF Mono',Menlo,monospace;}
.nc-axiom{font-size:.95em;font-weight:600;color:#1a202c;line-height:1.45;margin-bottom:6px;}
.nc-detail{font-size:.82em;color:#718096;line-height:1.4;margin-bottom:2px;}
.nc-lbl{font-size:.75em;font-weight:600;color:#a0aec0;text-transform:uppercase;letter-spacing:.5px;margin-right:4px;}
.nc-bnd{font-style:italic;color:#a0aec0;}
.nc-foot{display:flex;align-items:center;gap:8px;margin-top:10px;padding-top:8px;border-top:1px solid #f0f0f0;}
.nc-src{font-size:.75em;color:#a0aec0;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}

/* ── Stats ── */
.stats-row{display:flex;flex-wrap:wrap;gap:6px;}
.si{display:flex;align-items:center;gap:5px;background:#fff;border:1px solid #e2e8f0;
  border-radius:6px;padding:5px 10px;font-size:.82em;flex:1;min-width:70px;}
.si-i{font-size:1em;}
.si-l{color:#a0aec0;font-size:.78em;flex:1;}
.si-v{font-weight:700;color:#2d3748;}

/* ── Agent Status ── */
.agent-st{font-size:.82em;color:#718096;font-family:'SF Mono',Menlo,monospace;}

/* ── Scrollbar ── */
::-webkit-scrollbar{width:5px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:#cbd5e0;border-radius:4px;}
::-webkit-scrollbar-thumb:hover{background:#a0aec0;}
"""


# ══════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════
HEADER_HTML = (
    "<div class='lab-hdr'>"
    "<div class='lab-title'><span>Atomic</span> Lab</div>"
    "<div class='lab-sub'>Read &middot; Organize &middot; Write</div>"
    "</div>"
)


# ══════════════════════════════════════════════════════════════
# GRADIO UI
# ══════════════════════════════════════════════════════════════
with gr.Blocks(title="Atomic Lab v2.0") as demo:
    # ── States ──
    lib_st = gr.State({})
    stats_st = gr.State({"docs": 0, "atoms": 0, "notes": 0})
    notes_st = gr.State([])

    gr.HTML(HEADER_HTML)

    with gr.Tabs():
        # ════════════════════════════════════════════════
        # TAB 1: READ
        # ════════════════════════════════════════════════
        with gr.Tab("📖 阅读"):
            gr.HTML("<div class='tip'>上传 PDF，阅读提取文本并记录笔记</div>")
            with gr.Row():
                # ── LEFT: Upload + Text Reader ──
                with gr.Column(scale=6, min_width=400):
                    with gr.Group():
                        upload_f = gr.File(
                            label="上传文献 (PDF / TXT / MD)",
                            file_types=[".pdf", ".txt", ".md"],
                            file_count="multiple",
                        )
                        pdf_selector = gr.Dropdown(
                            choices=[], label="选择文献", allow_custom_value=False
                        )
                    gr.Markdown("### 文献文本")
                    pdf_text_html = gr.HTML(
                        "<div class='txt-empty'>选择文献后，文本将在此显示</div>"
                    )

                # ── RIGHT: Notes ──
                with gr.Column(scale=3, min_width=240):
                    with gr.Group():
                        note_page = gr.Number(
                            value=1, label="页码", precision=0, minimum=1
                        )
                        note_content = gr.TextArea(
                            label="笔记",
                            placeholder="记录你的思考、摘抄关键段落...",
                            lines=4,
                        )
                        save_note_btn = gr.Button("保存笔记", variant="primary")
                    gr.Markdown("### 阅读笔记")
                    notes_html = gr.HTML(render_note_cards([]))

        # ════════════════════════════════════════════════
        # TAB 2: ORGANIZE
        # ════════════════════════════════════════════════
        with gr.Tab("🧬 整理"):
            gr.HTML("<div class='tip'>基于阅读笔记，一键解构为原子知识</div>")
            with gr.Row():
                # ── LEFT: Notes + Generate ──
                with gr.Column(scale=5, min_width=360):
                    notes_overview = gr.HTML(render_notes_for_organize([]))
                    with gr.Group():
                        extra_notes_in = gr.TextArea(
                            label="补充笔记（可选）",
                            placeholder="额外输入补充内容...",
                            lines=2,
                        )
                        gen_btn = gr.Button("智能解构", variant="primary")

                # ── RIGHT: Atom Cards + Stats ──
                with gr.Column(scale=5, min_width=360):
                    gr.Markdown("### 原子卡片")
                    atom_cards_out = gr.HTML(
                        "<div class='nc-empty'>点击「智能解构」将笔记转化为原子知识</div>"
                    )
                    stats_html = gr.HTML(
                        render_stats({"docs": 0, "atoms": 0, "notes": 0})
                    )
                    agent_status = gr.HTML("<span class='agent-st'>等待操作...</span>")

        # ════════════════════════════════════════════════
        # TAB 3: WRITE
        # ════════════════════════════════════════════════
        with gr.Tab("✍️ 写作"):
            gr.HTML("<div class='tip'>参考左侧原子卡片，在右侧自由写作</div>")
            with gr.Row():
                # ── LEFT: Reference Cards ──
                with gr.Column(scale=3, min_width=280):
                    gr.Markdown("### 参考卡片")
                    ref_cards_html = gr.HTML(
                        "<div class='nc-empty'>解构笔记后，原子卡片将在此显示</div>"
                    )

                # ── RIGHT: Text Editor ──
                with gr.Column(scale=6, min_width=400):
                    gr.Markdown("### 写作区")
                    draft_text = gr.TextArea(
                        label="",
                        show_label=False,
                        placeholder="在此自由写作，可参考左侧原子卡片...\n\n支持 Markdown 格式",
                        lines=20,
                    )
                    draft_file = gr.File(label="下载草稿", interactive=False)
                    download_btn = gr.Button("生成 Markdown 文件", variant="primary")

    # ══════════════════════════════════════════════════════════
    # EVENTS
    # ══════════════════════════════════════════════════════════

    # Tab 1: Upload
    upload_f.change(
        fn=handle_upload,
        inputs=[upload_f, lib_st, stats_st],
        outputs=[lib_st, stats_st, pdf_selector, stats_html, pdf_text_html],
    )

    # Tab 1: Select PDF → text display
    pdf_selector.change(
        fn=handle_select_pdf,
        inputs=[pdf_selector, lib_st],
        outputs=[pdf_text_html],
    )

    # Tab 1: Save note
    save_note_btn.click(
        fn=handle_save_note,
        inputs=[note_page, note_content, notes_st, pdf_selector],
        outputs=[notes_st, notes_html],
    )

    # Tab 2: Generate
    def _refresh_and_generate(extra, notes, pid, lib, stats):
        cards_html, lib, stats, sh, ast, ref = handle_generate(
            extra, notes, pid, lib, stats
        )
        notes_ov = render_notes_for_organize(notes)
        return cards_html, lib, stats, sh, ast, notes_ov, ref

    gen_btn.click(
        fn=_refresh_and_generate,
        inputs=[extra_notes_in, notes_st, pdf_selector, lib_st, stats_st],
        outputs=[
            atom_cards_out,
            lib_st,
            stats_st,
            stats_html,
            agent_status,
            notes_overview,
            ref_cards_html,
        ],
    )

    # Tab 3: Download
    download_btn.click(
        fn=handle_download,
        inputs=[draft_text],
        outputs=[draft_file],
    )


# ══════════════════════════════════════════════════════════════
# LAUNCH
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, css=CSS)
