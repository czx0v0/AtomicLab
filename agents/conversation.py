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
    from services.rag_service import get_rag_service
    from core.config import RAG_CONFIG

    # 使用全局RAG服务实例（与main.py共享）
    _rag_service = get_rag_service(RAG_CONFIG)
    # 不重复加载，使用main.py已加载的索引
    RAG_AVAILABLE = True
    print("✅ ConversationAgent: RAG服务已连接")
except Exception as e:
    print(f"⚠️ RAG服务初始化失败，将使用传统搜索: {e}")
    _rag_service = None
    RAG_AVAILABLE = False


RAG_SYSTEM_PROMPT = """你是 Atomic Lab 的 AI 研究助手。基于提供的知识库上下文回答问题。

【强制规则】
1. 必须基于下面提供的"知识库内容"回答，禁止说"未找到""未提及"
2. 如果上下文中有任何相关信息，即使不完整，也必须基于现有信息回答
3. 只有当下方知识库内容完全为空时，才可以说没有相关信息
4. 回答中用 [来源: 文献名 p.页码] 标注引用来源
5. 用中文回答（除非用户用英文提问）
6. 简洁、专业、有条理

【回答策略】
- 主动整合多个片段的信息，给出综合回答
- 如果信息不完整，说明"基于现有信息..."然后给出最佳回答
- 不要过度保守，用户看到检索到了内容，期望你基于这些内容回答

用户问题通常与提供的文献内容直接相关，请认真分析上下文后给出答案。"""


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
        search_debug_info = []  # 检索调试信息

        # 0) 优先使用RAG服务进行语义检索（如果可用）
        if RAG_AVAILABLE and _rag_service:
            # 检查hybrid_searcher是否可用
            if not _rag_service.hybrid_searcher:
                search_debug_info.append("⚠️ RAG混合检索器未初始化")
                print("[RAG Debug] hybrid_searcher is None")
            else:
                try:
                    print(f"[RAG Debug] 开始检索: '{question[:50]}...'")
                    retrieval_result = _rag_service.retrieve(
                        query=question, top_k=10, use_reranker=True
                    )

                    chunk_count = (
                        len(retrieval_result.chunks)
                        if retrieval_result and retrieval_result.chunks
                        else 0
                    )
                    search_debug_info.append(
                        f"🔍 RAG检索: 找到 {chunk_count} 个相关片段"
                    )
                    print(f"[RAG Debug] 检索完成: {chunk_count} chunks")

                    if retrieval_result and retrieval_result.chunks:
                        rag_chunks_used = True

                        # 按页码分组chunks，重组上下文
                        chunks_by_page = {}
                        for chunk in retrieval_result.chunks[:10]:
                            doc_title = (
                                chunk.metadata.doc_title
                                if chunk.metadata
                                else "未知文献"
                            )
                            page_num = chunk.page_number if chunk.page_number else "?"
                            key = (doc_title, page_num)
                            if key not in chunks_by_page:
                                chunks_by_page[key] = []
                            chunks_by_page[key].append(chunk)

                        # 合并同一页的chunks，避免内容被分割
                        # TODO: one chapter's chunks
                        for (
                            doc_title,
                            page_num,
                        ), page_chunks in chunks_by_page.items():
                            # 合并同一页的所有chunk内容
                            combined_content = "\n".join(
                                [c.content for c in page_chunks]
                            )
                            chunk_type = (
                                page_chunks[0].chunk_type
                                if page_chunks[0].chunk_type
                                else "text"
                            )

                            # 构建上下文
                            source_label = f"[文献: {doc_title} p.{page_num}]"
                            context_parts.append(
                                f"{source_label} ({chunk_type})\n{combined_content}"
                            )

                            # 收集引用信息
                            if doc_title not in cited_docs:
                                cited_docs.append(doc_title)

                        search_debug_info.append(
                            f"✅ 使用RAG检索结果: {len(context_parts)} 条上下文"
                        )
                    else:
                        search_debug_info.append("⚠️ RAG检索无结果")
                except Exception as e:
                    error_msg = f"❌ RAG检索失败: {str(e)[:100]}"
                    search_debug_info.append(error_msg)
                    print(f"[RAG Debug] {error_msg}")
                    rag_chunks_used = False
        else:
            search_debug_info.append("⚠️ RAG服务不可用")
            print("[RAG Debug] RAG服务未初始化")

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
                                "source_pid": node.source_pid
                                or "",  # 添加source_pid用于跳转
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
                                "source_pid": n.get("source_pid", ""),  # 添加source_pid用于跳转
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

        # 记录传统搜索结果
        if not rag_chunks_used:
            if context_parts:
                search_debug_info.append(
                    f"📚 传统搜索: 找到 {len(context_parts)} 条相关内容"
                )
            else:
                search_debug_info.append("📚 传统搜索: 无结果")

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

            # 构建调试信息展示
            debug_summary = (
                " | ".join(search_debug_info) if search_debug_info else "无检索信息"
            )

            # 在回答前添加检索状态（仅当检索有问题时）
            answer = result.strip()
            if not context_parts:
                answer = f"⚠️ **检索提示**: 未找到相关内容\n\n{answer}"

            return AgentOutput(
                agent_id=self.agent_id,
                status="success",
                data={
                    "answer": answer,
                    "notes_count": len(cited_notes),
                    "docs_count": len(cited_docs),
                    "cited_notes": cited_notes[:6],  # Limit to 6 for display
                    "cited_docs": cited_docs[:3],  # Limit to 3 for display
                    "search_debug": debug_summary,  # 检索调试信息
                    "context_count": len(context_parts),  # 上下文数量
                    "rag_used": rag_chunks_used,  # 是否使用RAG
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
