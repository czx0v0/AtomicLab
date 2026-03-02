"""
Crusher Agent — Simplified
===========================
Analyzes user notes: auto-classify, tag, and summarize.

Input:  User notes + document context
Output: Per-note classification/tags + overall summary
"""

from .base import BaseAgent, AgentOutput, call_llm
from core.utils import pjson


CLASSIFY_SYS = """你是 Atomic Lab 的笔记分析引擎。
职责：对用户的阅读笔记进行自动分类、打标签，并生成一段综合摘要。

## 输出规则
1. 仅输出 JSON，不带 markdown 标记。
2. 结构：
{
  "notes": [
    {
      "index": 0,
      "category": "方法|公式|图像|定义|观点|数据|其他",
      "tags": ["关键词1", "关键词2"]
    }
  ],
  "summary": "综合摘要（50-150字，概括所有笔记的核心要点和关联）",
  "domain": "学科领域（2-4字）"
}
3. category 从以下选择：方法、公式、图像、定义、观点、数据、其他。
4. tags 每条笔记 1-3 个关键词。
5. summary 是对全部笔记的综合总结，不是逐条复述。"""

CLASSIFY_USR = """## 文献上下文（供参考）
{context}

## 用户笔记（请逐条分析）
{notes}

请分析以上笔记，输出 JSON。"""


class CrusherAgent(BaseAgent):
    """Note analysis agent: classify, tag, and summarize.

    Takes user notes + document context, produces per-note
    classification with tags and an overall summary.
    """

    agent_id = "crusher"
    name = "Crusher"
    description = "笔记分析引擎"

    def execute(self, payload: dict, context: dict = None) -> AgentOutput:
        """Analyze notes.

        Args:
            payload: Dict with 'notes' (list of note dicts)
            context: Optional dict with 'doc_context'

        Returns:
            AgentOutput with classified notes + summary
        """
        notes = payload.get("notes", [])
        if not notes:
            return AgentOutput(
                agent_id=self.agent_id,
                status="error",
                error="无笔记可分析",
            )

        # Format notes for LLM
        notes_text = ""
        for i, n in enumerate(notes):
            page = n.get("page", "?")
            content = n.get("content", "")
            notes_text += f"[{i}] (p.{page}) {content}\n"

        doc_ctx = ""
        if context:
            doc_ctx = context.get("doc_context", "")[:3000]
        if not doc_ctx:
            doc_ctx = "(无文献上下文)"

        try:
            raw = call_llm(
                CLASSIFY_SYS,
                CLASSIFY_USR.format(context=doc_ctx, notes=notes_text),
                max_tokens=1000,
            )
            data = pjson(raw)

            if not data or "notes" not in data:
                return AgentOutput(
                    agent_id=self.agent_id,
                    status="error",
                    error=f"解析失败: {raw[:100]}",
                )

            return AgentOutput(
                agent_id=self.agent_id,
                status="success",
                data=data,
                confidence=0.85,
            )

        except Exception as e:
            return AgentOutput(
                agent_id=self.agent_id,
                status="error",
                error=str(e),
            )
