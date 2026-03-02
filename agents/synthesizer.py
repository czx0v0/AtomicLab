"""
Synthesizer Agent
=================
Analyzes all notes across documents and suggests:
  1. Cross-document references (which notes relate across papers)
  2. High-level themes grouping multiple notes
  3. Suggested reading order / importance ranking

Input:  All notes with their classifications + document list
Output: Suggested edges + theme groups
"""

from .base import BaseAgent, AgentOutput, call_llm
from core.utils import pjson


SYNTH_SYS = """你是 Atomic Lab 的知识合成引擎。
职责：分析来自多篇文献的所有已分类笔记，发现跨文献关联，生成知识结构建议。

## 输出规则
1. 仅输出 JSON，不带 markdown 标记。
2. 结构：
{
  "themes": [
    {
      "name": "主题名称（2-6字）",
      "description": "主题描述（一句话）",
      "note_indices": [0, 3, 5]
    }
  ],
  "cross_refs": [
    {
      "from_idx": 0,
      "to_idx": 3,
      "reason": "关联原因（一句话）"
    }
  ],
  "importance_order": [2, 0, 5, 3, 1, 4],
  "insight": "综合洞察（50-100字，跨文献的宏观发现）"
}
3. themes: 将笔记按主题分组（一条笔记可属于多个主题）。
4. cross_refs: 跨文献笔记之间的关联（仅当确实存在逻辑关联时）。
5. importance_order: 按重要性排序的笔记索引。
6. insight: 跨文献的宏观洞察。"""

SYNTH_USR = """## 文献列表
{doc_list}

## 所有笔记（已分类）
{notes_text}

请分析以上笔记，输出 JSON。"""


class SynthesizerAgent(BaseAgent):
    """Knowledge synthesis agent: cross-document analysis.

    Takes all classified notes across documents, discovers
    themes, cross-references, and importance ranking.
    """

    agent_id = "synthesizer"
    name = "Synthesizer"
    description = "知识合成引擎"

    def execute(self, payload: dict, context: dict = None) -> AgentOutput:
        """Synthesize knowledge across documents.

        Args:
            payload: Dict with 'notes' (list of classified note dicts)
            context: Optional dict with 'doc_list' (list of doc names)

        Returns:
            AgentOutput with themes, cross_refs, importance, insight
        """
        notes = payload.get("notes", [])
        if len(notes) < 2:
            return AgentOutput(
                agent_id=self.agent_id,
                status="error",
                error="至少需要 2 条笔记才能进行合成分析",
            )

        # Format notes
        notes_text = ""
        for i, n in enumerate(notes):
            cat = n.get("category", "其他")
            tags = ", ".join(n.get("tags", []))
            content = n.get("content", "")[:100]
            doc = n.get("doc_name", "?")
            notes_text += f"[{i}] [{cat}] [{doc}] {content} (tags: {tags})\n"

        doc_list = ""
        if context and context.get("doc_list"):
            for d in context["doc_list"]:
                doc_list += f"- {d}\n"
        else:
            doc_list = "(未知)"

        try:
            raw = call_llm(
                SYNTH_SYS,
                SYNTH_USR.format(doc_list=doc_list, notes_text=notes_text),
                max_tokens=1500,
            )
            data = pjson(raw)

            if not data or "themes" not in data:
                return AgentOutput(
                    agent_id=self.agent_id,
                    status="error",
                    error=f"解析失败: {raw[:100]}",
                )

            return AgentOutput(
                agent_id=self.agent_id,
                status="success",
                data=data,
                confidence=0.8,
            )

        except Exception as e:
            return AgentOutput(
                agent_id=self.agent_id,
                status="error",
                error=str(e),
            )
