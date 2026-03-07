"""
Conversation Agent (RAG)
========================
RAG-based conversational agent for document Q&A.
Retrieves relevant knowledge tree nodes + document text,
builds context, and generates grounded answers with citations.
"""

from agents.base import BaseAgent, AgentOutput, call_llm
from knowledge.search import search_nodes

# 尝试导入RAG服务
try:
    from services.rag_service import RAGService
    from core.config import RAG_CONFIG

    _rag_service = RAGService(RAG_CONFIG)
    RAG_AVAILABLE = True
except Exception as e:
    print(f"RAG服务初始化失败，将使用传统搜索: {e}")
    _rag_service = None
    RAG_AVAILABLE = False


RAG_SYSTEM_PROMPT = """你是 Atomic Lab 的 AI 研究助手。基于用户的笔记和文献库回答问题。

规则：
1. 仅基于提供的知识库内容回答，不编造信息
2. 如果知识库中没有相关内容，诚实说明
3. 回答中用 [来源: 笔记/文献名] 标注引用来源
4. 用中文回答（除非用户用英文提问）
5. 简洁、专业、有条理"""


class ConversationAgent(BaseAgent):
    """RAG-powered conversational agent for research Q&A."""

    agent_id = "conversation"
    name = "Conversation Agent"
    description = (
        "Answer questions based on uploaded documents and notes via RAG retrieval"
    )

    def execute(self, payload: dict, context: dict = None) -> AgentOutput:
        question = payload.get("question", "")
        history = payload.get("history", [])

        if not question or not question.strip():
            return AgentOutput(
                agent_id=self.agent_id, status="error", error="Empty question"
            )

        context = context or {}
        tree = context.get("tree")
        lib = context.get("lib", {})
        notes = context.get("notes", [])

        # ── RAG Retrieval Pipeline ──
        context_parts = []
        cited_notes = []  # Track cited notes for display
        cited_docs = []  # Track cited documents for display
        rag_chunks_used = False

        # 0) 优先使用RAG服务进行语义检索（如果可用）
        if RAG_AVAILABLE and _rag_service and _rag_service.hybrid_searcher:
            try:
                retrieval_result = _rag_service.retrieve(
                    query=question, top_k=10, use_reranker=True
                )
                if retrieval_result and retrieval_result.chunks:
                    print(f"RAG检索: 找到 {len(retrieval_result.chunks)} 个相关chunks")
                    rag_chunks_used = True
                    for chunk in retrieval_result.chunks[:8]:
                        doc_title = (
                            chunk.metadata.doc_title if chunk.metadata else "未知文献"
                        )
                        page_num = chunk.page_number if chunk.page_number else "?"
                        chunk_type = chunk.chunk_type if chunk.chunk_type else "text"

                        # 构建上下文
                        source_label = f"[文献: {doc_title} p.{page_num}]"
                        context_parts.append(
                            f"{source_label} ({chunk_type})\n{chunk.content}"
                        )

                        # 收集引用信息
                        if doc_title not in cited_docs:
                            cited_docs.append(doc_title)
            except Exception as e:
                print(f"RAG检索失败，回退到传统搜索: {e}")
                rag_chunks_used = False

        # 1) 如果没有RAG结果，使用传统知识树搜索
        if not rag_chunks_used:
            if tree and hasattr(tree, "nodes") and tree.nodes:
                matches = search_nodes(tree, question)
                for node in matches[:8]:
                    source_label = ""
                    source_name = ""
                    if node.parent_id and tree.get_node(node.parent_id):
                        parent = tree.get_node(node.parent_id)
                        source_label = f" (来自: {parent.label})"
                        source_name = parent.label
                    context_parts.append(f"[{node.type}]{source_label} {node.content}")

                    # Collect note info for cited display
                    if node.type == "note":
                        cited_notes.append(
                            {
                                "content": node.content,
                                "page": node.metadata.get("page", ""),
                                "category": node.metadata.get("category", ""),
                                "source_name": source_name,
                            }
                        )

            # 2) Search raw notes (including annotations)
            q_lower = question.lower()
            for n in notes:
                content = n.get("content", "")
                annotation = n.get("annotation", "")
                search_text = content + " " + annotation
                if any(
                    kw in search_text.lower() for kw in q_lower.split() if len(kw) > 1
                ):
                    note_str = f"[笔记 p.{n.get('page', '?')}] {content}"
                    if annotation:
                        note_str += f" (批注: {annotation})"
                    context_parts.append(note_str)

                    # Also collect for cited display (avoid duplicates)
                    if not any(c.get("content") == content for c in cited_notes):
                        cited_notes.append(
                            {
                                "content": content,
                                "page": n.get("page", ""),
                                "category": n.get("category", ""),
                                "source_name": n.get("source_name", ""),
                            }
                        )

                    if len(context_parts) > 12:
                        break

            # 3) Always search document text — include more context for better RAG
            for pid, info in lib.items():
                doc_text = info.get("text", "")
                doc_name = info.get("name", "?")
                if not doc_text:
                    continue
                # Try multiple keyword snippets for broader coverage
                snippets_added = 0
                for kw in [kw for kw in q_lower.split() if len(kw) > 1]:
                    snippet = self._find_relevant_snippet(doc_text, kw, window=800)
                    if snippet:
                        context_parts.append(f"[文献: {doc_name}] {snippet}")
                        snippets_added += 1
                        if snippets_added >= 2:
                            break
                # Fallback: add abstract if no keyword match
                if snippets_added == 0 and doc_text:
                    context_parts.append(f"[文献摘要: {doc_name}] {doc_text[:800]}")
                    snippets_added = 1

                # Track cited documents
                if snippets_added > 0 and doc_name not in cited_docs:
                    cited_docs.append(doc_name)

        # Build prompt
        if context_parts:
            rag_context = "\n---\n".join(context_parts[:20])
            user_prompt = f"知识库内容:\n{rag_context}\n\n用户问题: {question}"
        else:
            user_prompt = (
                f"（当前知识库为空，无检索结果）\n\n"
                f"用户问题: {question}\n\n"
                f"请提示用户先上传文献并记录笔记。"
            )

        # Include recent history for multi-turn
        history_text = ""
        if history:
            recent = history[-3:]  # last 3 turns
            for turn in recent:
                role = turn.get("role", "")
                content = turn.get("content", "")
                if role == "user":
                    history_text += f"用户: {content}\n"
                elif role == "assistant":
                    history_text += f"助手: {content[:200]}\n"

        full_prompt = history_text + user_prompt if history_text else user_prompt

        try:
            result = call_llm(
                system_prompt=RAG_SYSTEM_PROMPT,
                user_prompt=full_prompt,
                temperature=0.3,
                max_tokens=1200,
            )

            return AgentOutput(
                agent_id=self.agent_id,
                status="success",
                data={
                    "answer": result.strip(),
                    "notes_count": len(cited_notes),
                    "docs_count": len(cited_docs),
                    "cited_notes": cited_notes[:6],  # Limit to 6 for display
                    "cited_docs": cited_docs[:3],  # Limit to 3 for display
                },
                confidence=0.8 if context_parts else 0.3,
            )
        except Exception as e:
            return AgentOutput(agent_id=self.agent_id, status="error", error=str(e))

    @staticmethod
    def _find_relevant_snippet(text: str, query: str, window: int = 400) -> str:
        """Find the most relevant text snippet around query keywords."""
        if not text:
            return ""
        text_lower = text.lower()
        keywords = [kw for kw in query.lower().split() if len(kw) > 1]

        best_pos = -1
        for kw in keywords:
            pos = text_lower.find(kw)
            if pos >= 0:
                best_pos = pos
                break

        if best_pos < 0:
            return text[:window] if len(text) > window else text

        start = max(0, best_pos - window // 2)
        end = min(len(text), best_pos + window // 2)
        return text[start:end]
