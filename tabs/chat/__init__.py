"""
Chat Tab -- AI Assistant (Copilot)
===================================
RAG-powered AI assistant for document Q&A.
Routes messages through the multi-agent router.

Exports:
    build_chat_tab()    -> dict of Gradio components
    handle_chat_send()  -> process user message via Router
    handle_chat_clear() -> clear conversation history
"""

import time
import inspect
import gradio as gr

from agents.router import RouterAgent
from agents.base import call_llm
from core.utils import esc
from ui.renderers import render_cited_notes

_router = RouterAgent()

_INTENT_LABELS = {
    "translate": "翻译",
    "organize": "整理",
    "synthesize": "综合分析",
    "conversation": "问答",
}


def _build_status(status_type: str, message: str, context_count: int = 0) -> str:
    """Build status HTML for real-time feedback."""
    status_icons = {
        "retrieving": "🔍",
        "generating": "✍️",
        "no_results": "⚠️",
        "complete": "✅",
        "error": "❌",
    }
    icon = status_icons.get(status_type, "⏳")

    # 进度条样式
    progress_style = ""
    if status_type == "retrieving":
        progress_style = "background: linear-gradient(90deg, #3182ce 0%, #63b3ed 50%, #3182ce 100%); background-size: 200% 100%; animation: progress-move 1.5s ease-in-out infinite;"
    elif status_type == "generating":
        progress_style = "background: linear-gradient(90deg, #38a169 0%, #68d391 50%, #38a169 100%); background-size: 200% 100%; animation: progress-move 1.5s ease-in-out infinite;"
    elif status_type == "complete":
        progress_style = "background: #38a169;"
    elif status_type == "error":
        progress_style = "background: #e53e3e;"

    progress_html = f"""
    <div style="height: 3px; width: 100%; margin-top: 8px; border-radius: 2px; {progress_style}"></div>
    <style>
    @keyframes progress-move {{
        0% {{ background-position: 100% 0; }}
        100% {{ background-position: -100% 0; }}
    }}
    </style>
    """

    return f"""
    <div style="padding: 8px 12px; background: #f7fafc; border-radius: 6px; border-left: 3px solid {'#3182ce' if status_type in ['retrieving', 'generating'] else '#38a169' if status_type == 'complete' else '#e53e3e'}; font-size: 13px; color: #4a5568;">
        <span style="font-weight: 500;">{icon} {message}</span>
        {progress_html if status_type in ['retrieving', 'generating'] else ''}
    </div>
    """


# ══════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════


def format_agent_msg(agent_name: str, icon: str, content: str) -> str:
    """Format a single agent bubble using Markdown quote block.

    形如：
    > **🔍 SEEKER_BOT**
    >
    > 正在检索...
    """
    # 注意换行格式：\n> \n> 可在 Gradio 6.2 中渲染出独立引用块
    return f"> **{icon} {agent_name}**\n> \n> {content}\n\n"


def _render_citation_bar(citation_items: list) -> str:
    """渲染 RAG 引用跳转按钮栏。citation_items: [{"pid", "page", "label"}, ...]。"""
    if not citation_items:
        return ""
    parts = [
        '<div class="chat-citation-bar" style="margin-top:10px;padding:8px 0;border-top:1px solid #e2e8f0;display:flex;flex-wrap:wrap;gap:8px;align-items:center;">',
        '<span style="font-size:12px;color:#718096;margin-right:6px;">📑 跳转引用:</span>',
    ]
    for item in citation_items:
        pid = item.get("pid", "") or ""
        page = item.get("page", 1)
        label = item.get("label", "") or f"p.{page}"
        if not pid:
            continue
        safe_label = esc(label[:30] + ("..." if len(label) > 30 else ""))
        parts.append(
            f'<button type="button" class="citation-jump-btn" '
            f'onclick="jumpToSource(\'{esc(pid)}\', {int(page)})" '
            f'style="font-size:12px;padding:4px 10px;border-radius:6px;border:1px solid #cbd5e0;background:#f7fafc;cursor:pointer;color:#2d3748;">'
            f'📑 {safe_label}</button>'
        )
    parts.append("</div>")
    return "\n".join(parts)


def _render_references_ui(
    citation_items: list, arxiv_refs: list
) -> str:
    """渲染「当前回答引用来源」卡片列表，供点击跳转 PDF 或打开 ArXiv。
    citation_items: [{"pid", "page", "label"}, ...]；arxiv_refs: ["1908.123", ...]。
    本地卡片点击触发 jumpToSource(pid, page)；ArXiv 卡片点击在新窗口打开链接。
    """
    parts = [
        '<div class="current-references-ui" style="margin-top:12px;padding:12px;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;">',
        '<div style="font-size:12px;color:#718096;margin-bottom:8px;font-weight:500;">📑 当前回答引用来源（点击跳转）</div>',
        '<div style="display:flex;flex-direction:column;gap:8px;">',
    ]
    for item in citation_items or []:
        pid = item.get("pid", "") or ""
        page = item.get("page", 1) or 1
        label = item.get("label", "") or f"p.{page}"
        if not pid:
            continue
        safe_label = esc(label[:50] + ("..." if len(label) > 50 else ""))
        parts.append(
            '<div class="ref-card ref-card-local" style="padding:8px 12px;background:#fff;border-radius:6px;border:1px solid #e2e8f0;cursor:pointer;" '
            f'onclick="jumpToSource(\'{esc(pid)}\', {int(page)})" '
            'title="点击跳转到 PDF 原文">'
            f'<span style="color:#2d3748;">📄 {safe_label}</span>'
            '</div>'
        )
    for aid in arxiv_refs or []:
        url = f"https://arxiv.org/abs/{aid}"
        safe_aid = esc(aid)
        parts.append(
            '<div class="ref-card ref-card-arxiv" style="padding:8px 12px;background:#fff;border-radius:6px;border:1px solid #e2e8f0;cursor:pointer;" '
            f'onclick="window.open(\'{esc(url)}\', \'_blank\')" '
            'title="在新窗口打开 ArXiv">'
            f'<span style="color:#2d3748;">📎 ArXiv {safe_aid}</span>'
            '</div>'
        )
    if not (citation_items or arxiv_refs):
        parts.append('<div style="font-size:12px;color:#a0aec0;">暂无引用来源</div>')
    parts.append("</div></div>")
    return "\n".join(parts)


def _format_bot_message(output) -> str:
    """Format AgentOutput into display HTML."""
    if output.status == "error":
        return f"抱歉，处理时出错：{esc(output.error)}"

    data = output.data or {}
    intent = data.get("intent", "conversation")
    label = _INTENT_LABELS.get(intent, intent)

    if intent == "translate":
        translation = data.get("translation", "")
        original = data.get("original", "")
        return (
            f"**[{label}]**\n\n"
            f"{esc(translation)}\n\n"
            f"---\n*原文: {esc(original[:200])}*"
        )

    # conversation / organize / synthesize
    answer = data.get("answer", "无回复")
    notes_count = data.get("notes_count", 0)
    docs_count = data.get("docs_count", 0)
    cited_notes = data.get("cited_notes", [])
    cited_docs = data.get("cited_docs", [])
    note = data.get("note", "")

    # v2.2: 检索调试信息
    search_debug = data.get("search_debug", "")
    context_count = data.get("context_count", 0)
    rag_used = data.get("rag_used", False)

    result = answer

    # Render cited notes as cards if available
    if cited_notes:
        cited_html = render_cited_notes(cited_notes)
        if cited_html:
            result += f"\n\n{cited_html}"

    # Show reference summary (only if we have actual references)
    ref_parts = []
    if notes_count > 0:
        ref_parts.append(f"{notes_count} 条笔记")
    if docs_count > 0:
        doc_names = ", ".join(cited_docs[:2])
        if len(cited_docs) > 2:
            doc_names += f" 等{docs_count}篇"
        ref_parts.append(f"文献: {doc_names}")

    if ref_parts and not cited_notes:
        # Only show text summary if no card display
        result += f"\n\n---\n*参考来源: {' · '.join(ref_parts)}*"

    # v2.2: 添加检索调试信息（折叠显示）
    if search_debug:
        rag_status = "🟢 RAG" if rag_used else "📚 传统"
        result += f"\n\n<details><summary>🔍 检索详情 ({rag_status} | {context_count}条上下文)</summary>\n\n{search_debug}\n</details>"

    if note:
        result += f"\n\n> {esc(note)}"
    return result


# ══════════════════════════════════════════════════════════════
# CHAT HISTORY FORMAT HELPERS (Gradio 6.2 默认 messages 格式)
# ══════════════════════════════════════════════════════════════


def _chat_history_to_messages(pairs):
    """将内部 [[user, bot], ...] 转为 Gradio messages 格式 [{role, content}, ...]。"""
    out = []
    for u, b in pairs:
        out.append({"role": "user", "content": u if u is not None else ""})
        out.append({"role": "assistant", "content": b if b is not None else ""})
    return out


def _normalize_chat_history_to_pairs(chat_history):
    """兼容入参：messages 或 元组列表，统一为 [[user, bot], ...]。"""
    if not chat_history:
        return []
    first = chat_history[0]
    if isinstance(first, dict):
        pairs = []
        i = 0
        while i < len(chat_history):
            u = (
                chat_history[i].get("content", "")
                if isinstance(chat_history[i], dict)
                else str(chat_history[i])
            )
            if i + 1 < len(chat_history) and isinstance(chat_history[i + 1], dict):
                b = chat_history[i + 1].get("content", "")
                pairs.append([u, b])
                i += 2
            else:
                pairs.append([u, ""])
                i += 1
        return pairs
    return [list(p) if isinstance(p, (list, tuple)) else [str(p), ""] for p in chat_history]


# ══════════════════════════════════════════════════════════════
# HANDLERS
# ══════════════════════════════════════════════════════════════


def handle_chat_send(message, chat_history, tree, lib, notes):
    """Process user message through the Router agent.

    Args:
        message: User text input
        chat_history: List of (user, assistant) tuples
        tree: KnowledgeTree instance
        lib: Document library dict
        notes: List of note dicts

    Returns:
        (updated_history, cleared_input, status_html)
    """
    if not message or not message.strip():
        return chat_history, "", ""

    # 统一为内部 [[user, bot]]，输出时再转为 messages
    chat_history = _normalize_chat_history_to_pairs(chat_history or [])
    chat_history.append([message.strip(), "🔍 正在分析意图..."])

    # Build conversation history for multi-turn
    history_for_agent = []
    for msg in chat_history[:-1] or []:  # 排除刚添加的临时消息
        if isinstance(msg, (list, tuple)) and len(msg) == 2:
            history_for_agent.append({"role": "user", "content": msg[0]})
            history_for_agent.append({"role": "assistant", "content": msg[1]})

    payload = {
        "message": message.strip(),
        "history": history_for_agent,
    }
    context = {
        "tree": tree,
        "lib": lib,
        "notes": notes,
    }

    # 更新状态：正在检索
    chat_history[-1][1] = "🔍 正在检索相关文档..."
    yield _chat_history_to_messages(chat_history), "", _build_status("retrieving", "正在检索知识库...")

    try:
        output = _router.execute(payload, context)

        # 更新状态：已找到结果
        data = output.data or {}
        context_count = data.get("context_count", 0)
        rag_used = data.get("rag_used", False)

        if context_count > 0:
            search_type = "RAG语义检索" if rag_used else "传统搜索"
            chat_history[-1][1] = (
                f"✅ 找到 {context_count} 个相关片段，正在生成答案..."
            )
            yield _chat_history_to_messages(chat_history), "", _build_status(
                "generating", f"{search_type}: {context_count} 条上下文", context_count
            )
        else:
            chat_history[-1][1] = "⚠️ 未找到相关内容，基于一般知识回答..."
            yield _chat_history_to_messages(chat_history), "", _build_status("no_results", "知识库无匹配结果")

        # 生成最终回答
        bot_reply = _format_bot_message(output)
        chat_history[-1][1] = bot_reply
        status_msg = (
            f"✅ 完成 | {'RAG' if rag_used else '传统'}检索 | {context_count} 条上下文"
        )
        yield _chat_history_to_messages(chat_history), "", _build_status(
            "complete", status_msg, context_count
        )

    except Exception as e:
        import traceback

        error_detail = traceback.format_exc()
        print(f"[Chat] AI处理异常: {e}")
        print(f"[Chat] 错误堆栈:\n{error_detail}")

        # 在回复中显示错误详情（开发模式）
        error_msg = f"❌ 系统异常：{e}\n\n<details><summary>📝 错误详情（开发者信息）</summary>\n\n```\n{error_detail[:500]}\n```\n</details>"
        chat_history[-1][1] = error_msg
        yield _chat_history_to_messages(chat_history), "", _build_status("error", f"处理失败: {str(e)[:50]}")


def handle_chat_stream(message, messages, tree, lib, notes):
    """
    Multi-agent style streaming handler using gr.Chatbot(type="messages").
    含意图拦截与 ArXiv 查询清洗，与 handle_chat_stream_legacy 对齐。
    """
    from services.rag_service import get_rag_service, optimize_search_query
    from core.config import RAG_CONFIG
    import requests
    import re as _re

    if not message or not message.strip():
        yield messages, "", ""
        return

    messages = messages or []
    question = message.strip()
    messages.append({"role": "user", "content": question})

    optimized_query = optimize_search_query(question)
    retrieval = None
    doc_summaries = []
    arxiv_context = ""
    arxiv_refs = []

    if optimized_query.strip().upper() == "NONE":
        seeker_msg = {
            "role": "assistant",
            "content": "识别到闲聊/非学术指令，跳过知识库检索。",
            "metadata": {"title": "🔍 SEEKER"},
        }
        messages.append(seeker_msg)
        yield messages, "", _build_status("retrieving", "跳过检索，直接执行指令...")
        reviewer_msg = {
            "role": "assistant",
            "content": "准备直接执行用户指令。",
            "metadata": {"title": "⚖️ REVIEWER"},
        }
        messages.append(reviewer_msg)
        yield messages, "", _build_status("generating", "评估完成，准备合成答案...")
    else:
        seeker_msg = {
            "role": "assistant",
            "content": f"提取检索关键词: [{optimized_query}]… 正在多源检索知识库 (文档 + 笔记 + BM25)...",
            "metadata": {"title": "🔍 SEEKER"},
        }
        messages.append(seeker_msg)
        yield messages, "", _build_status(
            "retrieving", f"提取检索关键词: [{optimized_query}]… 正在查询 ArXiv / 本地..."
        )

        rag_service = get_rag_service(RAG_CONFIG)
        try:
            retrieval = rag_service.retrieve(question, top_k=5)
            for idx, chunk in enumerate(retrieval.chunks[:3], start=1):
                title = getattr(chunk.metadata, "doc_title", "") or "未知文献"
                preview = (chunk.content or "").replace("\n", " ")[:80]
                doc_summaries.append(f"[{idx}] {title}: {preview}...")
        except Exception as e:
            print(f"[ChatStream] RAG 检索失败: {e}")

        if retrieval and retrieval.chunks:
            seeker_msg["content"] = (
                "正在检索多源知识库 (文档 + 笔记 + BM25)...\n\n"
                "已找到以下相关内容：\n" + "\n".join(doc_summaries)
            )
        else:
            seeker_msg["content"] = (
                "未在本地知识库中检索到高质量结果，将尝试 ArXiv 备选检索。"
            )
        yield messages, "", _build_status(
            "retrieving",
            "本地检索完成" if retrieval and retrieval.chunks else "本地无匹配结果",
        )

        reviewer_msg = {
            "role": "assistant",
            "content": "正在评估检索质量...",
            "metadata": {"title": "⚖️ REVIEWER"},
        }
        messages.append(reviewer_msg)
        yield messages, "", _build_status("generating", "评估检索质量...")

        if not (retrieval and retrieval.chunks):
            arxiv_query = optimized_query
            try:
                q = requests.utils.quote(arxiv_query)
                url = f"https://export.arxiv.org/api/query?search_query=all:{q}&max_results=3"
                resp = requests.get(url, timeout=20)
                if resp.ok:
                    arxiv_context = resp.text[:4000]
                    reviewer_msg["content"] = "本地无匹配结果，已优化检索词并从 ArXiv 抓取若干相关文章作为补充。"
                    arxiv_refs = list(dict.fromkeys(_re.findall(r"arxiv\.org\/abs\/([0-9\.]+)", arxiv_context)))[:3]
                else:
                    reviewer_msg["content"] = "本地无匹配结果，ArXiv 备选检索失败，请稍后重试。"
            except Exception as e:
                print(f"[ChatStream] ArXiv 检索失败: {e}")
                reviewer_msg["content"] = "本地无匹配结果，ArXiv 备选检索失败，请稍后重试。"
        else:
            score = min(10, max(1, len(retrieval.chunks)))
            reviewer_msg["content"] = f"已评估检索质量，综合评分约为 {score}/10。"

    yield messages, "", _build_status("generating", "评估完成，准备合成答案...")

    # ── Step 3: Synthesizer 合成（模拟流式输出） ──
    synth_msg = {
        "role": "assistant",
        "content": "",
        "metadata": {"title": "🧠 SYNTHESIZER"},
    }
    messages.append(synth_msg)
    yield messages, "", _build_status("generating", "正在合成最终答案...")

    # 构造上下文给 LLM
    rag_context = ""
    internal_refs = []
    if retrieval and retrieval.chunks:
        parts = []
        seen_docs = set()
        for idx, chunk in enumerate(retrieval.chunks[:5], start=1):
            title = getattr(chunk.metadata, "doc_title", "") or "未知文献"
            page = getattr(chunk, "page_number", None) or "?"
            preview = (chunk.content or "").strip()
            parts.append(f"[{idx}] {title} p.{page}\n{preview}")
            if title not in seen_docs:
                internal_refs.append(f"{idx}. {title} p.{page}")
                seen_docs.add(title)
        rag_context = "\n\n".join(parts)

    full_context = ""
    if rag_context:
        full_context += f"[本地知识库片段]\n{rag_context}\n\n"
    if arxiv_context:
        full_context += f"[ArXiv 结果片段]\n{arxiv_context}\n\n"
    if not full_context:
        full_context = (
            "（当前知识库与 ArXiv 检索均未找到高质量上下文，仅能基于一般常识简要回答）"
        )

    system_prompt = """你是一个智能学术助手。请遵循以下回答原则：

如果提供的上下文中包含有用的信息，请优先使用上下文回答，并标注引用来源。

如果上下文为空，或者只包含 API 报错/XML 元数据（如 totalResults: 0），绝对不要向用户解释 API 结果或 XML 结构！请直接使用你自身的常识和内部知识来回答用户的问题。

如果用户的输入是明确的指令（如“翻译”、“总结”、“润色”），请直接对上文或当前输入执行该任务，不要说“上下文中找不到可供翻译的内容”。"""
    user_prompt = f"用户问题：{question}\n\n可用上下文：\n{full_context}"

    try:
        # 当前 call_llm 不支持原生流式，先一次性拿到结果，再手动切片模拟“打字机效果”
        answer_full = call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=1200,
        ).strip()

        # 附加引用列表
        ref_lines = []
        if internal_refs:
            ref_lines.append("本地文献：")
            ref_lines.extend([f"[{i}] {txt}" for i, txt in enumerate(internal_refs, 1)])
        if arxiv_refs:
            ref_lines.append("ArXiv 补充：")
            ref_lines.extend(
                [f"[arXiv-{i}] arxiv:{aid}" for i, aid in enumerate(arxiv_refs, 1)]
            )
        if ref_lines:
            answer_full += "\n\n---\n参考来源：\n" + "\n".join(ref_lines)

        # 模拟流式：按固定长度切片逐步输出
        chunk_size = 80
        for i in range(0, len(answer_full), chunk_size):
            synth_msg["content"] = answer_full[: i + chunk_size]
            yield messages, "", _build_status("generating", "正在合成最终答案...")
            time.sleep(0.05)

        yield messages, "", _build_status("complete", "多智能体合成完成", 0)
    except Exception as e:
        synth_msg["content"] = f"合成答案时发生错误：{e}"
        yield messages, "", _build_status("error", "合成失败")


def handle_chat_stream_legacy(message, chat_history, tree, lib, notes):
    """
    Agentic RAG 流水线：Reviewer 规划 → Seeker 多路召回 → Reviewer 评估 → Synthesizer 合成。
    经典 [[user, bot]] 历史结构，yield 5 输出：chatbot, msg_input, chat_status, citation_bar, current_references_ui。
    """
    from services.rag_service import get_rag_service, optimize_search_query
    from core.config import RAG_CONFIG
    import requests
    import re as _re

    def _yield(hist, status_msg, status_ctx=0, citation_html="", refs_ui=""):
        st = "retrieving" if "检索" in status_msg or "召回" in status_msg else "generating" if "评估" in status_msg or "合成" in status_msg else "complete" if "完成" in status_msg else "retrieving"
        return (
            _chat_history_to_messages(hist),
            "",
            _build_status(st, status_msg, status_ctx),
            citation_html,
            refs_ui,
        )

    if not message or not message.strip():
        out = _normalize_chat_history_to_pairs(chat_history or [])
        yield _chat_history_to_messages(out), "", "", "", ""
        return

    chat_history = _normalize_chat_history_to_pairs(chat_history or [])
    question = message.strip()
    chat_history.append([question, ""])

    def _set_bot_reply(text: str):
        chat_history[-1][1] = text

    # ── Phase 1: Reviewer 规划 ──
    reviewer_plan = format_agent_msg(
        "REVIEWER_BOT", "⚖️", "正在分析意图并规划检索路线..."
    )
    _set_bot_reply(reviewer_plan)
    t = _yield(chat_history, "正在分析意图并规划检索路线...")
    yield t[0], t[1], t[2], t[3], t[4]

    optimized_query = optimize_search_query(question)
    retrieval = None
    doc_summaries: list[str] = []
    arxiv_context = ""
    arxiv_refs: list[str] = []
    citation_items: list[dict] = []
    is_skip = optimized_query.strip().upper() == "NONE"

    if is_skip:
        reviewer_plan = format_agent_msg(
            "REVIEWER_BOT", "⚖️", "意图: 闲聊/任务 | 跳过检索，直接合成"
        )
    else:
        reviewer_plan = format_agent_msg(
            "REVIEWER_BOT",
            "⚖️",
            f"意图: 学术问答 | 提取实体: [{optimized_query}] | 规划路线: 多路召回 (Vector, Graph, ArXiv)",
        )
    _set_bot_reply(reviewer_plan)
    t = _yield(chat_history, "规划完成，进入多路召回..." if not is_skip else "跳过检索，直接合成...")
    yield t[0], t[1], t[2], t[3], t[4]

    # ── Phase 2: Seeker 多路执行 ──
    if is_skip:
        seeker_text = format_agent_msg(
            "SEEKER_BOT", "🔍", "已跳过检索（闲聊/任务模式）。"
        )
    else:
        seeker_text = format_agent_msg(
            "SEEKER_BOT", "🔍", "正在执行多路检索..."
        )
    _set_bot_reply(reviewer_plan + seeker_text)
    t = _yield(chat_history, "正在执行多路检索...")
    yield t[0], t[1], t[2], t[3], t[4]

    n_local, n_graph, n_arxiv = 0, 0, 0
    if not is_skip:
        rag_service = get_rag_service(RAG_CONFIG)
        try:
            retrieval = rag_service.retrieve(question, top_k=5)
            n_local = len(retrieval.chunks) if retrieval and retrieval.chunks else 0
            for idx, chunk in enumerate((retrieval.chunks or [])[:3], start=1):
                title = getattr(chunk.metadata, "doc_title", "") or "未知文献"
                preview = (chunk.content or "").replace("\n", " ")[:80]
                doc_summaries.append(f"[{idx}] {title}: {preview}...")
        except Exception as e:
            print(f"[ChatStreamLegacy] RAG 检索失败: {e}")
        graph_results = []  # Mock: 图检索待接入
        n_graph = len(graph_results)

        if n_local < 2:
            arxiv_query = optimized_query
            q_encoded = requests.utils.quote(arxiv_query)
            try:
                url = f"https://export.arxiv.org/api/query?search_query=all:{q_encoded}&max_results=3"
                resp = requests.get(url, timeout=20)
                if resp.ok:
                    arxiv_context = resp.text[:4000]
                    arxiv_refs = list(
                        dict.fromkeys(
                            _re.findall(r"arxiv\.org\/abs\/([0-9\.]+)", arxiv_context)
                        )
                    )[:3]
                    n_arxiv = len(arxiv_refs)
            except Exception as e:
                print(f"[ChatStreamLegacy] ArXiv 检索失败: {e}")

        seeker_text = format_agent_msg(
            "SEEKER_BOT",
            "🔍",
            f"召回完毕：本地原子卡片 ({n_local}条) | 知识图谱 ({n_graph}条) | ArXiv ({n_arxiv}条)",
        )
    else:
        seeker_text = format_agent_msg(
            "SEEKER_BOT", "🔍", "召回完毕：本地原子卡片 (0条) | 知识图谱 (0条) | ArXiv (0条)"
        )
    _set_bot_reply(reviewer_plan + seeker_text)
    t = _yield(chat_history, "多路召回完成")
    yield t[0], t[1], t[2], t[3], t[4]

    # ── Phase 3: Reviewer 评估 ──
    if is_skip or not (retrieval and retrieval.chunks) and not arxiv_refs:
        score = 0
        eval_msg = "质量评估: N/A，无检索结果，交由合成器。"
    else:
        n_ctx = (len(retrieval.chunks) if retrieval else 0) + len(arxiv_refs)
        score = min(100, 50 + min(50, n_ctx * 12))
        eval_msg = "质量评估: %d/100，上下文充足，已过滤低质片段，交由合成器。" % score
    reviewer_eval = format_agent_msg("REVIEWER_BOT", "⚖️", eval_msg)
    _set_bot_reply(reviewer_plan + seeker_text + reviewer_eval)
    t = _yield(chat_history, "评估完成，准备合成答案...")
    yield t[0], t[1], t[2], t[3], t[4]

    # 构造 RAG 上下文与引用元数据
    rag_context = ""
    internal_refs: list[str] = []
    if retrieval and retrieval.chunks:
        parts = []
        seen_docs: set[str] = set()
        for idx, chunk in enumerate(retrieval.chunks[:5], start=1):
            title = getattr(chunk.metadata, "doc_title", "") or "未知文献"
            page = getattr(chunk, "page_number", None) or 1
            if page is None:
                page = 1
            preview = (chunk.content or "").strip()
            parts.append(f"[{idx}] {title} p.{page}\n{preview}")
            pid = getattr(chunk, "doc_id", "") or ""
            if pid:
                citation_items.append({
                    "pid": pid,
                    "page": page,
                    "label": f"引用 {idx}: {title} p.{page}",
                })
            if title not in seen_docs:
                internal_refs.append(f"{idx}. {title} p.{page}")
                seen_docs.add(title)
        rag_context = "\n\n".join(parts)

    full_context = ""
    if rag_context:
        full_context += f"[本地知识库片段]\n{rag_context}\n\n"
    if arxiv_context:
        full_context += f"[ArXiv 结果片段]\n{arxiv_context}\n\n"
    if not full_context:
        full_context = "（当前知识库与 ArXiv 检索均未找到高质量上下文，仅能基于一般常识简要回答）"

    system_prompt = """你是一个智能学术助手。请遵循以下回答原则：

如果提供的上下文中包含有用的信息，请优先使用上下文回答，并在句中或句末标注引用，格式如 [Doc_1_Page_5] 或 [ArXiv_1908.123]。

如果上下文为空，或只包含 API 报错/XML 元数据（如 totalResults: 0），不要解释 API 结果或 XML 结构，直接基于常识回答。

如果用户的输入是明确指令（如“翻译”、“总结”、“润色”），请直接执行该任务。"""
    user_prompt = f"用户问题：{question}\n\n可用上下文：\n{full_context}"

    synth_header = "> **🧠 SYNTHESIZER_BOT**\n> \n> "
    base_text = reviewer_plan + seeker_text + reviewer_eval + synth_header

    try:
        answer_full = call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=1200,
        ).strip()

        ref_lines: list[str] = []
        if internal_refs:
            ref_lines.append("本地文献：")
            ref_lines.extend([f"[{i}] {txt}" for i, txt in enumerate(internal_refs, 1)])
        if arxiv_refs:
            ref_lines.append("ArXiv 补充：")
            ref_lines.extend([f"[arXiv-{i}] arxiv:{aid}" for i, aid in enumerate(arxiv_refs, 1)])
        if ref_lines:
            answer_full += "\n\n---\n参考来源：\n" + "\n".join(ref_lines)

        chunk_size = 80
        for i in range(0, len(answer_full), chunk_size):
            current = answer_full[: i + chunk_size]
            _set_bot_reply(base_text + current)
            t = _yield(chat_history, "正在合成最终答案...")
            yield t[0], t[1], t[2], t[3], t[4]
            time.sleep(0.05)

        _set_bot_reply(base_text + answer_full)
        citation_html = _render_citation_bar(citation_items)
        refs_ui = _render_references_ui(citation_items, arxiv_refs)
        yield _chat_history_to_messages(chat_history), "", _build_status(
            "complete", "多智能体合成完成", len(retrieval.chunks) if retrieval else 0
        ), citation_html, refs_ui
    except Exception as e:
        error_msg = format_agent_msg(
            "SYNTHESIZER_BOT", "🧠", f"合成答案时发生错误：{e}"
        )
        _set_bot_reply(reviewer_plan + seeker_text + reviewer_eval + error_msg)
        yield _chat_history_to_messages(chat_history), "", _build_status("error", "合成失败"), "", ""


def handle_chat_clear():
    """Clear chat history, citation bar, and current references UI."""
    return [], "", "", ""


def handle_feedback(feedback_data):
    """Handle user feedback on AI responses.

    在 Gradio 6.x 中，Chatbot.like 会自动注入 LikeData/EventData，
    因此这里只接收一个参数，避免 inputs=[] 覆盖默认事件数据。
    """
    if not feedback_data:
        return ""

    try:
        # 兼容 Gradio 不同版本的 LikeData 结构
        if hasattr(feedback_data, "value"):
            action = feedback_data.value
            index = getattr(feedback_data, "index", "?")
        elif isinstance(feedback_data, dict):
            action = feedback_data.get("value", "")
            index = feedback_data.get("index", "?")
        else:
            action = str(feedback_data)
            index = "?"

        # 保存反馈数据用于模型微调（当前无法直接拿到完整 chat_history，因此传入 None）
        _save_feedback_for_training(action, index, None)

        if action == "like":
            print(f"[Chat] 用户对第 {index} 条回答点赞")
            return "<span class='agent-st success'>✓ 感谢反馈！这将帮助我们改进AI回答质量。</span>"
        elif action == "dislike":
            print(f"[Chat] 用户对第 {index} 条回答点踩")
            return "<span class='agent-st error'>✓ 感谢反馈！我们会持续改进AI回答质量。</span>"
        else:
            print(f"[Chat] 收到反馈: {action}")
    except Exception as e:
        print(f"[Chat] 反馈处理异常: {e}")

    return ""


def _save_feedback_for_training(action: str, index: int, chat_history):
    """保存反馈数据用于RAG模型微调"""
    if not chat_history or len(chat_history) < 2:
        return

    try:
        from models.feedback import RetrievalFeedback
        from services.feedback_service import save_feedback

        # 找到对应的用户问题和AI回答
        # chat_history格式: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        target_idx = int(index) * 2 if str(index).isdigit() else -2

        if target_idx >= 0 and target_idx < len(chat_history):
            user_msg = chat_history[target_idx]
            ai_msg = (
                chat_history[target_idx + 1]
                if target_idx + 1 < len(chat_history)
                else None
            )
        else:
            # 默认取最后一条
            user_msg = chat_history[-2] if len(chat_history) >= 2 else None
            ai_msg = chat_history[-1] if chat_history else None

        if not user_msg or not ai_msg:
            return

        query = (
            user_msg.get("content", "") if isinstance(user_msg, dict) else str(user_msg)
        )

        # 创建反馈对象
        feedback = RetrievalFeedback(
            query=query,
            retrieved_chunk_ids=[],  # TODO: 从上下文中提取chunk IDs
            retrieved_contents=[],
            user_rating=action,
        )

        # 保存反馈
        save_feedback(feedback)
        print(f"[Chat] 反馈已保存: {action}")

    except Exception as e:
        print(f"[Chat] 保存反馈失败: {e}")


def handle_ai_ask(text, chat_history, tree, lib, notes):
    """Handle 'ask-ai' from reading page popup — bridge to chat."""
    if not text or not text.strip():
        yield chat_history, ""
        return
    # Strip timestamp prefix (format: "timestamp|text")
    if "|" in text:
        text = text.split("|", 1)[1]
    if not text or not text.strip():
        yield chat_history, ""
        return
    # handle_chat_send 是生成器，使用 yield from 传递
    yield from handle_chat_send(text.strip(), chat_history, tree, lib, notes)


# ══════════════════════════════════════════════════════════════
# UI BUILDER
# ══════════════════════════════════════════════════════════════


def build_chat_tab():
    """Build the AI Chat tab UI.

    Returns:
        Dict of component references:
            chatbot, msg_input, send_btn, clear_btn, status_html
    """
    gr.HTML(
        "<div class='tip'>"
        "AI 助手基于你的文献和笔记回答问题 (RAG)。"
        "支持翻译、知识问答、跨文献分析。"
        "</div>"
    )

    # 状态显示区域
    chat_status = gr.HTML(
        value="",
        elem_id="chat-status",
    )

    # 统一使用经典 [[user, bot]] 历史结构，避免 messages 模式在旧版 Gradio 中的兼容性问题
    chatbot = gr.Chatbot(
        label="AI 助手",
        height=480,
        elem_id="chat-copilot",
        latex_delimiters=[
            {"left": "$$", "right": "$$", "display": True},
            {"left": "$", "right": "$", "display": False},
        ],
    )
    citation_bar = gr.HTML(
        value="",
        elem_id="chat-citation-bar",
        elem_classes=["chat-citation-bar-wrap"],
    )
    current_references_ui = gr.HTML(
        value="",
        elem_id="chat-current-references",
        elem_classes=["chat-references-wrap"],
    )
    with gr.Row():
        msg_input = gr.Textbox(
            label="",
            show_label=False,
            placeholder="输入问题，例如：「这篇论文的核心方法是什么？」「翻译：摘要」",
            lines=1,
            scale=8,
            elem_id="chat-input",
        )
        send_btn = gr.Button("发送", variant="primary", scale=1, size="sm")
        clear_btn = gr.Button("清空", scale=1, size="sm")

    # ── 左下角工具栏：模型选择 + 文献选择 ──
    with gr.Row(elem_classes=["chat-toolbar"]):
        # 模型选择器 - 初始化默认值
        from core.model_state import cooldown_manager
        from core.config import MODEL_DISPLAY_NAMES

        _models = cooldown_manager.get_all_models()
        _model_choices = [(MODEL_DISPLAY_NAMES.get(m, m), m) for m in _models]
        _preferred = cooldown_manager.get_preferred() or (_models[0] if _models else "")

        model_selector = gr.Dropdown(
            choices=_model_choices,
            value=_preferred,
            label="模型",
            scale=2,
            container=False,
            elem_id="chat-model-selector",
            allow_custom_value=True,
        )
        # 当前文献选择器
        doc_selector = gr.Dropdown(
            choices=[("全部文献", "__all__")],
            value="__all__",
            label="发送文献",
            scale=2,
            container=False,
            elem_id="chat-doc-selector",
            allow_custom_value=True,
        )
        # 模型状态指示
        model_status = gr.HTML("", elem_id="chat-model-status")

    # Hidden textbox for receiving "问AI" from reading page popup
    ai_ask_input = gr.Textbox(
        elem_id="ai-ask-input",
        visible=True,
        container=False,
    )

    return {
        "chatbot": chatbot,
        "citation_bar": citation_bar,
        "current_references_ui": current_references_ui,
        "msg_input": msg_input,
        "send_btn": send_btn,
        "clear_btn": clear_btn,
        "ai_ask_input": ai_ask_input,
        "chat_status": chat_status,
        "model_selector": model_selector,
        "doc_selector": doc_selector,
        "model_status": model_status,
    }
