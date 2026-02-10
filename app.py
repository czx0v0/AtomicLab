"""
Atomic Lab | 科研驾驶舱 v1.0
沉浸式多智能体科研辅助系统
"""

import gradio as gr
import plotly.graph_objects as go
import os
import json
import re
import random
import time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ══════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════
MODELSCOPE_TOKEN = os.environ.get("MODELSCOPE_TOKEN", "")
API_BASE = "https://api-inference.modelscope.cn/v1"
MODEL_NAME = "Qwen/Qwen2.5-72B-Instruct"


# ══════════════════════════════════════════════════════════════
# SESSION STATE (全局状态容器)
# ══════════════════════════════════════════════════════════════
class SessionState:
    """全局会话状态，跨组件共享"""

    def __init__(self):
        self.mission_log = []  # 航行日志
        self.atomic_storage = []  # 原子知识库
        self.flight_stats = {
            "docs_processed": 0,
            "atoms_generated": 0,
            "focus_minutes": 0,
        }
        self.atom_counter = 0  # 原子编号递增

    def next_atom_id(self):
        self.atom_counter += 1
        return f"ATC-{self.atom_counter:04d}"


SESSION = SessionState()


# ══════════════════════════════════════════════════════════════
# PDF EXTRACTION
# ══════════════════════════════════════════════════════════════
def extract_pdf_text(file_path: str) -> str:
    """从 PDF 提取文本"""
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        return f"[PDF PARSE ERROR] {str(e)}"


# ══════════════════════════════════════════════════════════════
# ENGINEER AGENT (首席工程师 — 语义粉碎引擎)
# ══════════════════════════════════════════════════════════════
ENGINEER_SYSTEM_PROMPT = """你是 Atomic Lab 首席工程师，代号"裂变引擎"。
你的唯一职责：将学术文本解构为知识原子。

## 输出规则（必须严格遵循）
1. 输出且仅输出一个 JSON 对象，不带 ```json 标记，不带任何额外文字。
2. JSON 结构如下：
{
  "atoms": [
    {
      "axiom": "公理化结论，纯陈述句，不超过30字",
      "methodology": "核心实验路径或推导逻辑，不超过50字，可含 LaTeX 如 $E=mc^2$",
      "variable_data": "关键数据指标、公式或边界条件，不超过50字"
    }
  ],
  "domain": "所属学科领域（2-4字）",
  "confidence": 0.0到1.0之间的浮点数
}
3. atoms 数组恰好包含 3 个元素。
4. 语气冷峻、无感情、纯学术，禁止修饰词。"""

ENGINEER_USER_TEMPLATE = """对以下学术文本执行语义粉碎，提取 3 个知识原子。

--- 待处理文本 ---
{text}
--- 文本结束 ---

仅输出 JSON。"""


def call_qwen(text: str) -> str:
    """调用 Qwen 模型执行原子化处理"""
    client = OpenAI(base_url=API_BASE, api_key=MODELSCOPE_TOKEN)
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": ENGINEER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": ENGINEER_USER_TEMPLATE.format(text=text[:4000]),
            },
        ],
        temperature=0.15,
        max_tokens=800,
    )
    return response.choices[0].message.content


def parse_atoms(raw: str) -> dict | None:
    """从 LLM 输出中提取 JSON"""
    # 尝试直接解析
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # 尝试提取 JSON 块
    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def format_atom_cards(atoms_data: dict) -> str:
    """将原子数据渲染为 HUD 风格 HTML 卡片"""
    if not atoms_data or "atoms" not in atoms_data:
        return "<div class='atom-card atom-error'>[PARSE FAILURE] 原子化解析未命中目标结构</div>"

    domain = atoms_data.get("domain", "UNKNOWN")
    confidence = atoms_data.get("confidence", 0)
    conf_pct = (
        f"{confidence * 100:.0f}%"
        if isinstance(confidence, (int, float))
        else str(confidence)
    )

    cards = ""
    for atom in atoms_data["atoms"]:
        atom_id = SESSION.next_atom_id()
        cards += f"""
        <div class="atom-card">
            <div class="atom-card-header">
                <span class="atom-id">#{atom_id}</span>
                <span class="atom-status-dot"></span>
                <span class="atom-status-text">ACTIVE</span>
            </div>
            <div class="atom-field">
                <span class="field-label">[Core Axiom]</span>
                <span class="field-value">{atom.get('axiom', 'N/A')}</span>
            </div>
            <div class="atom-field">
                <span class="field-label">[Methodology]</span>
                <span class="field-value">{atom.get('methodology', 'N/A')}</span>
            </div>
            <div class="atom-field">
                <span class="field-label">[Variable/Data]</span>
                <span class="field-value">{atom.get('variable_data', 'N/A')}</span>
            </div>
            <div class="atom-scanline"></div>
        </div>
        """

    return f"""
    <div class="atom-container">
        <div class="atom-meta">
            DOMAIN: {domain} &nbsp;|&nbsp; CONFIDENCE: {conf_pct}
        </div>
        {cards}
        <div class="atom-footer">
            [Engineer Info] 目标文本已解构，共生成 {len(atoms_data['atoms'])} 个原子。逻辑链路已对齐。
        </div>
    </div>
    """


# ══════════════════════════════════════════════════════════════
# NAVIGATOR AGENT (领航员 — 任务 & 状态管理)
# ══════════════════════════════════════════════════════════════
def navigator_advice(atoms_data: dict) -> str:
    """基于新生成的原子，给出航行建议"""
    if not atoms_data or "atoms" not in atoms_data:
        return ""
    domain = atoms_data.get("domain", "未知领域")
    axiom = atoms_data["atoms"][0].get("axiom", "") if atoms_data["atoms"] else ""
    timestamp = time.strftime("%H:%M:%S")
    return (
        f"[{timestamp}] [Navigator] 新原子已入库 | "
        f"领域 <{domain}> 与当前航线匹配度较高。"
        f"建议围绕「{axiom[:15]}...」展开深度扫描。"
    )


def format_stats_html() -> str:
    """渲染统计面板 HTML"""
    s = SESSION.flight_stats
    return f"""
    <div class="stats-panel">
        <div class="stat-row">
            <span class="stat-label">DOCS SCANNED</span>
            <span class="stat-value">{s['docs_processed']}</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">ATOMS GENERATED</span>
            <span class="stat-value">{s['atoms_generated']}</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">FOCUS TIME</span>
            <span class="stat-value">{s['focus_minutes']} min</span>
        </div>
    </div>
    """


# ══════════════════════════════════════════════════════════════
# RADAR CHART (遥测雷达图)
# ══════════════════════════════════════════════════════════════
def create_radar(atoms_data: dict = None) -> go.Figure:
    """生成科研遥测雷达图"""
    categories = ["理论深度", "方法严谨", "数据密度", "创新性", "可复现性", "应用前景"]

    if atoms_data and "atoms" in atoms_data:
        random.seed(hash(json.dumps(atoms_data, ensure_ascii=False)) % 2**32)
        values = [round(random.uniform(0.55, 0.95), 2) for _ in categories]
    else:
        values = [0.15, 0.10, 0.20, 0.10, 0.15, 0.10]

    # 闭合多边形
    values_closed = values + [values[0]]
    cats_closed = categories + [categories[0]]

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=values_closed,
            theta=cats_closed,
            fill="toself",
            fillcolor="rgba(0, 212, 255, 0.08)",
            line=dict(color="#00d4ff", width=2),
            marker=dict(color="#00d4ff", size=5),
        )
    )
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                gridcolor="rgba(0, 212, 255, 0.12)",
                linecolor="rgba(0, 212, 255, 0.25)",
                tickfont=dict(color="#00d4ff", size=9),
            ),
            angularaxis=dict(
                gridcolor="rgba(0, 212, 255, 0.12)",
                linecolor="rgba(0, 212, 255, 0.25)",
                tickfont=dict(color="#c0c0c0", size=11),
            ),
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#00d4ff", family="Consolas, Courier New, monospace"),
        showlegend=False,
        margin=dict(l=55, r=55, t=30, b=30),
        height=340,
    )
    return fig


# ══════════════════════════════════════════════════════════════
# CORE HANDLER: 原子粉碎主流程
# ══════════════════════════════════════════════════════════════
def crush_handler(file, text_input):
    """
    执行原子粉碎：
    1. 提取文本（PDF 或直接输入）
    2. 调用 Qwen 解构
    3. 渲染卡片 + 雷达图 + 统计 + 航行日志
    """
    # ── 1. 获取文本 ──
    text = ""
    if file is not None:
        file_path = file.name if hasattr(file, "name") else str(file)
        if file_path.lower().endswith(".pdf"):
            text = extract_pdf_text(file_path)
        else:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except Exception as e:
                text = f"[FILE READ ERROR] {e}"

    if text_input and text_input.strip():
        text = (text + "\n" + text_input.strip()) if text else text_input.strip()

    if not text.strip():
        return (
            "<div class='atom-card'>[WARNING] 未检测到输入信号。请载入文献或输入文本。</div>",
            create_radar(),
            format_stats_html(),
            "<div class='nav-log'>[Navigator] 输入信号为空，等待数据载入...</div>",
        )

    # ── 2. 调用 LLM 粉碎 ──
    try:
        raw = call_qwen(text)
        atoms_data = parse_atoms(raw)

        if atoms_data is None:
            return (
                f"<div class='atom-card'>[PARSE ERROR] 模型返回未命中预期结构。<br>原始输出片段: {raw[:300]}...</div>",
                create_radar(),
                format_stats_html(),
                "<div class='nav-log'>[Engineer Info] 解构失败，链路未对齐。</div>",
            )

        # ── 3. 更新全局状态 ──
        SESSION.flight_stats["docs_processed"] += 1
        SESSION.flight_stats["atoms_generated"] += len(atoms_data.get("atoms", []))
        SESSION.atomic_storage.append(atoms_data)

        # ── 4. 渲染输出 ──
        cards_html = format_atom_cards(atoms_data)
        radar = create_radar(atoms_data)
        stats_html = format_stats_html()
        nav_msg = navigator_advice(atoms_data)

        return (
            cards_html,
            radar,
            stats_html,
            f"<div class='nav-log'>{nav_msg}</div>",
        )

    except Exception as e:
        return (
            f"<div class='atom-card atom-error'>[SYSTEM ERROR] {str(e)}</div>",
            create_radar(),
            format_stats_html(),
            f"<div class='nav-log' style='color:#ff6b6b'>[Navigator] 粉碎流程异常: {str(e)[:80]}</div>",
        )


# ══════════════════════════════════════════════════════════════
# CSS — HUD 驾驶舱主题
# ══════════════════════════════════════════════════════════════
CSS = """
/* ═══ 全局基础 ═══ */
.gradio-container {
    background-color: #05070a !important;
    color: #c8d6e5 !important;
    font-family: 'JetBrains Mono', 'Consolas', 'Courier New', monospace !important;
    max-width: 100% !important;
}
.dark .gradio-container { background-color: #05070a !important; }

/* ═══ 标题栏 ═══ */
.hud-title {
    text-align: center;
    padding: 18px 0 10px 0;
    font-size: 1.6em;
    font-weight: 700;
    letter-spacing: 6px;
    color: #00d4ff;
    text-shadow: 0 0 15px rgba(0,212,255,0.6), 0 0 40px rgba(0,212,255,0.2);
    border-bottom: 1px solid rgba(0,212,255,0.15);
    margin-bottom: 8px;
    position: relative;
}
.hud-title::after {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 50%;
    transform: translateX(-50%);
    width: 120px;
    height: 2px;
    background: linear-gradient(90deg, transparent, #00d4ff, transparent);
}
.hud-subtitle {
    text-align: center;
    font-size: 0.75em;
    color: #3a6073;
    letter-spacing: 4px;
    margin-bottom: 12px;
}

/* ═══ 面板通用 ═══ */
.panel-group {
    background: rgba(0, 212, 255, 0.02) !important;
    border: 1px solid rgba(0, 212, 255, 0.12) !important;
    border-radius: 6px !important;
    padding: 12px !important;
    margin-bottom: 8px;
}
.panel-header {
    color: #00d4ff;
    font-size: 0.85em;
    font-weight: 600;
    letter-spacing: 2px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(0,212,255,0.1);
    margin-bottom: 10px;
    text-transform: uppercase;
}

/* ═══ Gradio 组件覆盖 ═══ */
.gr-group {
    background: rgba(0, 212, 255, 0.02) !important;
    border: 1px solid rgba(0, 212, 255, 0.1) !important;
    border-radius: 6px !important;
}
.gr-box, .gr-input, .gr-text-input, textarea, input[type="text"] {
    background: rgba(0, 15, 25, 0.8) !important;
    border: 1px solid rgba(0, 212, 255, 0.2) !important;
    color: #c8d6e5 !important;
    border-radius: 4px !important;
    font-family: 'JetBrains Mono', 'Consolas', monospace !important;
}
textarea:focus, input[type="text"]:focus {
    border-color: #00d4ff !important;
    box-shadow: 0 0 8px rgba(0,212,255,0.15) !important;
}
label, .gr-checkbox-label, .label-wrap span {
    color: #6b8a9e !important;
    font-family: 'JetBrains Mono', 'Consolas', monospace !important;
}
.gr-button {
    font-family: 'JetBrains Mono', 'Consolas', monospace !important;
    letter-spacing: 1px;
}
.gr-button.primary, button.primary {
    background: linear-gradient(135deg, rgba(0,212,255,0.15), rgba(0,212,255,0.05)) !important;
    border: 1px solid #00d4ff !important;
    color: #00d4ff !important;
}
.gr-button.primary:hover, button.primary:hover {
    background: linear-gradient(135deg, rgba(0,212,255,0.25), rgba(0,212,255,0.10)) !important;
    box-shadow: 0 0 15px rgba(0,212,255,0.2) !important;
}
.gr-button.stop, button.stop {
    background: linear-gradient(135deg, rgba(255,60,60,0.12), rgba(255,60,60,0.04)) !important;
    border: 1px solid rgba(255,80,80,0.5) !important;
    color: #ff6b6b !important;
}
.gr-button.stop:hover, button.stop:hover {
    box-shadow: 0 0 15px rgba(255,80,80,0.2) !important;
}

/* Markdown */
.prose h3, .markdown h3, .gr-markdown h3 {
    color: #00d4ff !important;
    font-family: 'JetBrains Mono', 'Consolas', monospace !important;
    font-size: 0.95em !important;
    letter-spacing: 1px;
}
.prose, .markdown, .gr-markdown {
    color: #8899a6 !important;
}
.prose hr, .markdown hr { border-color: rgba(0,212,255,0.1) !important; }

/* Plot 容器透明 */
.plotly .main-svg { background: transparent !important; }
.js-plotly-plot .plotly .main-svg { background: transparent !important; }

/* Label 组件 */
.gr-label, .label-wrap {
    background: transparent !important;
}

/* File upload */
.file-upload, .upload-container {
    border: 1px dashed rgba(0,212,255,0.25) !important;
    background: rgba(0,15,25,0.4) !important;
}

/* ═══ 原子卡片 ═══ */
.atom-container {
    display: flex;
    flex-direction: column;
    gap: 10px;
}
.atom-meta {
    color: #3a6073;
    font-size: 0.75em;
    letter-spacing: 2px;
    padding: 4px 0;
    border-bottom: 1px solid rgba(0,212,255,0.08);
    margin-bottom: 4px;
}
.atom-card {
    border-left: 4px solid #00d4ff;
    background: linear-gradient(135deg, rgba(0,212,255,0.04), rgba(0,20,40,0.6));
    padding: 14px 16px;
    margin: 6px 0;
    border-radius: 0 6px 6px 0;
    position: relative;
    overflow: hidden;
    font-size: 0.88em;
    transition: border-color 0.3s;
}
.atom-card:hover {
    border-left-color: #00ffcc;
    background: linear-gradient(135deg, rgba(0,212,255,0.07), rgba(0,20,40,0.7));
}
.atom-card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
}
.atom-id {
    color: #00d4ff;
    font-weight: 700;
    font-size: 0.9em;
    letter-spacing: 1px;
}
.atom-status-dot {
    width: 6px; height: 6px;
    background: #00ff88;
    border-radius: 50%;
    box-shadow: 0 0 6px #00ff88;
    animation: pulse-dot 2s infinite;
}
@keyframes pulse-dot {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
}
.atom-status-text {
    color: #00ff88;
    font-size: 0.7em;
    letter-spacing: 2px;
}
.atom-field {
    padding: 4px 0;
    line-height: 1.5;
}
.field-label {
    color: #00d4ff;
    font-size: 0.78em;
    font-weight: 600;
    letter-spacing: 1px;
    margin-right: 6px;
}
.field-value {
    color: #c8d6e5;
    font-size: 0.85em;
}
.atom-scanline {
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    background: linear-gradient(
        180deg,
        transparent 0%,
        rgba(0,212,255,0.03) 50%,
        transparent 100%
    );
    background-size: 100% 8px;
    pointer-events: none;
    animation: scanline-move 4s linear infinite;
}
@keyframes scanline-move {
    0% { background-position: 0 0; }
    100% { background-position: 0 100px; }
}
.atom-footer {
    color: #3a6073;
    font-size: 0.72em;
    letter-spacing: 1px;
    padding-top: 8px;
    border-top: 1px solid rgba(0,212,255,0.08);
}
.atom-error {
    border-left-color: #ff6b6b !important;
    color: #ff6b6b;
}

/* ═══ 统计面板 ═══ */
.stats-panel {
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.stat-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    background: rgba(0,212,255,0.03);
    border: 1px solid rgba(0,212,255,0.08);
    border-radius: 4px;
}
.stat-label {
    color: #3a6073;
    font-size: 0.72em;
    letter-spacing: 2px;
}
.stat-value {
    color: #00d4ff;
    font-size: 1.1em;
    font-weight: 700;
    text-shadow: 0 0 8px rgba(0,212,255,0.3);
}

/* ═══ 番茄钟 ═══ */
.timer-container {
    text-align: center;
    padding: 10px;
}
.timer-display {
    font-size: 2.4em;
    font-weight: 700;
    color: #00d4ff;
    text-shadow: 0 0 20px rgba(0,212,255,0.4);
    letter-spacing: 4px;
    margin: 10px 0;
    font-family: 'JetBrains Mono', 'Consolas', monospace;
}
.timer-ring {
    width: 80px; height: 80px;
    border: 3px solid rgba(0,212,255,0.15);
    border-top: 3px solid #00d4ff;
    border-radius: 50%;
    margin: 0 auto 8px auto;
    animation: spin-ring 3s linear infinite;
}
.timer-ring.paused { animation-play-state: paused; border-top-color: #3a6073; }
@keyframes spin-ring {
    100% { transform: rotate(360deg); }
}
.timer-controls {
    display: flex;
    gap: 8px;
    justify-content: center;
    margin-top: 8px;
}
.timer-btn {
    background: rgba(0,212,255,0.08);
    border: 1px solid rgba(0,212,255,0.25);
    color: #00d4ff;
    padding: 5px 14px;
    border-radius: 4px;
    cursor: pointer;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75em;
    letter-spacing: 1px;
    transition: all 0.2s;
}
.timer-btn:hover {
    background: rgba(0,212,255,0.15);
    box-shadow: 0 0 10px rgba(0,212,255,0.15);
}

/* ═══ 航行日志 ═══ */
.nav-log {
    font-size: 0.78em;
    color: #5a8a6e;
    padding: 6px 10px;
    background: rgba(0,255,136,0.03);
    border-left: 2px solid rgba(0,255,136,0.2);
    border-radius: 0 4px 4px 0;
    margin-top: 6px;
    min-height: 24px;
}

/* ═══ 装饰性 HUD 边框 ═══ */
.hud-border-top {
    height: 2px;
    background: linear-gradient(90deg, transparent, rgba(0,212,255,0.3), transparent);
    margin: 4px 0 12px 0;
}
.hud-corner {
    position: relative;
}
.hud-corner::before {
    content: '//';
    position: absolute;
    top: -2px; left: 4px;
    color: rgba(0,212,255,0.2);
    font-size: 0.7em;
}

/* ═══ 滚动条 ═══ */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: #05070a; }
::-webkit-scrollbar-thumb { background: rgba(0,212,255,0.2); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(0,212,255,0.4); }
"""


# ══════════════════════════════════════════════════════════════
# POMODORO TIMER (纯前端 JS 实现)
# ══════════════════════════════════════════════════════════════
TIMER_HTML = """
<div class="timer-container" id="pomodoro-widget">
    <div class="timer-ring" id="timer-ring"></div>
    <div class="timer-display" id="timer-display">25:00</div>
    <div class="timer-controls">
        <button class="timer-btn" onclick="startPomodoro()">START</button>
        <button class="timer-btn" onclick="pausePomodoro()">PAUSE</button>
        <button class="timer-btn" onclick="resetPomodoro()">RESET</button>
    </div>
</div>
<script>
(function() {
    let remaining = 25 * 60;
    let interval = null;
    let running = false;

    function updateDisplay() {
        const m = String(Math.floor(remaining / 60)).padStart(2, '0');
        const s = String(remaining % 60).padStart(2, '0');
        const el = document.getElementById('timer-display');
        if (el) el.textContent = m + ':' + s;
    }

    window.startPomodoro = function() {
        if (running) return;
        running = true;
        const ring = document.getElementById('timer-ring');
        if (ring) ring.classList.remove('paused');
        interval = setInterval(function() {
            if (remaining > 0) {
                remaining--;
                updateDisplay();
            } else {
                clearInterval(interval);
                running = false;
                const el = document.getElementById('timer-display');
                if (el) {
                    el.textContent = 'DONE';
                    el.style.color = '#00ff88';
                }
            }
        }, 1000);
    };

    window.pausePomodoro = function() {
        clearInterval(interval);
        running = false;
        const ring = document.getElementById('timer-ring');
        if (ring) ring.classList.add('paused');
    };

    window.resetPomodoro = function() {
        clearInterval(interval);
        running = false;
        remaining = 25 * 60;
        updateDisplay();
        const ring = document.getElementById('timer-ring');
        if (ring) ring.classList.add('paused');
        const el = document.getElementById('timer-display');
        if (el) el.style.color = '#00d4ff';
    };

    updateDisplay();
    const ring = document.getElementById('timer-ring');
    if (ring) ring.classList.add('paused');
})();
</script>
"""


# ══════════════════════════════════════════════════════════════
# DECORATIVE HUD ELEMENTS
# ══════════════════════════════════════════════════════════════
HEADER_HTML = """
<div class="hud-title">ATOMIC LAB</div>
<div class="hud-subtitle">IMMERSIVE RESEARCH COCKPIT &nbsp; v1.0</div>
<div class="hud-border-top"></div>
"""


# ══════════════════════════════════════════════════════════════
# GRADIO UI 构建
# ══════════════════════════════════════════════════════════════
with gr.Blocks(title="Atomic Lab | 科研驾驶舱") as demo:

    # ── 标题 ──
    gr.HTML(HEADER_HTML)

    with gr.Row():

        # ════════ 左栏：Mission Log ════════
        with gr.Column(scale=1, min_width=260):
            gr.HTML("<div class='panel-header'>// MISSION LOG</div>")

            with gr.Group():
                gr.Markdown("### TASK QUEUE")
                todo_input = gr.Textbox(
                    placeholder="输入新任务后按回车...",
                    label="",
                    show_label=False,
                    lines=1,
                )
                task_list = gr.CheckboxGroup(
                    choices=["分析文献原文", "提取知识原子", "更新知识图谱"],
                    label="当前轨道任务",
                    value=[],
                )

            gr.HTML("<div class='hud-border-top'></div>")

            with gr.Group():
                gr.Markdown("### FOCUS ENGINE")
                gr.HTML(TIMER_HTML)

            gr.HTML("<div class='hud-border-top'></div>")

            with gr.Group():
                gr.Markdown("### NAV LOG")
                nav_log = gr.HTML("<div class='nav-log'>系统待命中，等待指令...</div>")

        # ════════ 中栏：Main Console ════════
        with gr.Column(scale=2, min_width=450):
            gr.HTML(
                "<div class='panel-header'>// MAIN CONSOLE &mdash; ATOMIC CRUSHER</div>"
            )

            with gr.Group():
                gr.Markdown("### DATA INPUT")
                with gr.Row():
                    file_input = gr.File(
                        label="载入文献 (PDF / TXT)",
                        file_types=[".pdf", ".txt", ".md"],
                    )
                text_input = gr.TextArea(
                    label="或直接输入学术文本",
                    placeholder="粘贴论文摘要、段落或实验数据...",
                    lines=7,
                )
                crush_btn = gr.Button(
                    ">>> EXECUTE ATOMIC CRUSH <<<",
                    variant="stop",
                    size="lg",
                )

            gr.HTML("<div class='hud-border-top'></div>")

            with gr.Group():
                gr.Markdown("### TELEMETRY RADAR")
                radar_plot = gr.Plot(
                    value=create_radar(),
                    label="",
                    show_label=False,
                )

        # ════════ 右栏：Atomic Storage ════════
        with gr.Column(scale=1, min_width=300):
            gr.HTML("<div class='panel-header'>// ATOMIC STORAGE</div>")

            with gr.Group():
                gr.Markdown("### PARTICLE STREAM")
                atomic_cards = gr.HTML("<div class='atom-card'>等待粒子注入...</div>")

            gr.HTML("<div class='hud-border-top'></div>")

            with gr.Group():
                gr.Markdown("### FLIGHT STATS")
                stats_display = gr.HTML(format_stats_html())

    # ══════════════════════════════════════════════════════════
    # EVENT BINDINGS
    # ══════════════════════════════════════════════════════════

    # 原子粉碎
    crush_btn.click(
        fn=crush_handler,
        inputs=[file_input, text_input],
        outputs=[atomic_cards, radar_plot, stats_display, nav_log],
    )

    # 添加任务（通过 State 管理 choices 列表）
    task_choices_state = gr.State(["分析文献原文", "提取知识原子", "更新知识图谱"])

    def add_task(new_task, current_choices):
        if not new_task or not new_task.strip():
            return "", current_choices, gr.update()
        task_text = new_task.strip()
        updated_choices = list(current_choices)
        if task_text not in updated_choices:
            updated_choices.append(task_text)
        return "", updated_choices, gr.update(choices=updated_choices)

    todo_input.submit(
        fn=add_task,
        inputs=[todo_input, task_choices_state],
        outputs=[todo_input, task_choices_state, task_list],
    )


# ══════════════════════════════════════════════════════════════
# LAUNCH
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        css=CSS,
    )
