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
import gradio as gr

from agents.router import RouterAgent
from core.utils import esc
from ui.renderers import render_cited_notes

_router = RouterAgent()

_INTENT_LABELS = {
    "translate": "翻译",
    "organize": "整理",
    "synthesize": "综合分析",
    "conversation": "问答",
}


# ══════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════


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
        (updated_history, cleared_input)
    """
    if not message or not message.strip():
        return chat_history, ""

    # Build conversation history for multi-turn
    history_for_agent = []
    for msg in chat_history or []:
        if isinstance(msg, dict):
            history_for_agent.append(msg)
        elif isinstance(msg, (list, tuple)) and len(msg) == 2:
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

    try:
        output = _router.execute(payload, context)
        bot_reply = _format_bot_message(output)
    except Exception as e:
        bot_reply = f"系统异常：{e}"

    chat_history = chat_history or []
    chat_history.append({"role": "user", "content": message.strip()})
    chat_history.append({"role": "assistant", "content": bot_reply})
    return chat_history, ""


def handle_chat_clear():
    """Clear chat history."""
    return [], ""


def handle_ai_ask(text, chat_history, tree, lib, notes):
    """Handle 'ask-ai' from reading page popup — bridge to chat."""
    if not text or not text.strip():
        return chat_history, ""
    # Strip timestamp prefix (format: "timestamp|text")
    if "|" in text:
        text = text.split("|", 1)[1]
    if not text or not text.strip():
        return chat_history, ""
    return handle_chat_send(text.strip(), chat_history, tree, lib, notes)


# ══════════════════════════════════════════════════════════════
# UI BUILDER
# ══════════════════════════════════════════════════════════════


def build_chat_tab():
    """Build the AI Chat tab UI.

    Returns:
        Dict of component references:
            chatbot, msg_input, send_btn, clear_btn
    """
    gr.HTML(
        "<div class='tip'>"
        "AI 助手基于你的文献和笔记回答问题 (RAG)。"
        "支持翻译、知识问答、跨文献分析。"
        "</div>"
    )
    chatbot = gr.Chatbot(
        label="AI 助手",
        height=480,
        elem_id="chat-copilot",
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

    # Hidden textbox for receiving "问AI" from reading page popup
    ai_ask_input = gr.Textbox(
        elem_id="ai-ask-input",
        visible=True,
        show_label=False,
        container=False,
    )

    return {
        "chatbot": chatbot,
        "msg_input": msg_input,
        "send_btn": send_btn,
        "clear_btn": clear_btn,
        "ai_ask_input": ai_ask_input,
    }
