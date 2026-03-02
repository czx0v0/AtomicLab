"""
Router Agent
============
Multi-intent router that dispatches user messages to the appropriate
specialist agent based on keyword rules + LLM intent classification.

Routing logic:
    user input -> intent detection -> dispatch -> AgentOutput

Supported intents:
    - translate:      keywords like "翻译", "translate"
    - organize:       keywords like "分类", "整理", "归纳"
    - synthesize:     keywords like "关联", "跨文", "综合"
    - conversation:   (default) RAG-based Q&A
"""

import re
from .base import BaseAgent, AgentOutput, call_llm
from .translator import TranslatorAgent
from .conversation import ConversationAgent

# Keyword patterns for fast intent detection (avoids LLM call for obvious cases)
# NOTE: conversation patterns checked FIRST to prevent misclassification
_INTENT_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("conversation", re.compile(
        r"是什么|什么是|解释|如何|怎[样么]|为什么|why|what\s+is|how\s+|"
        r"原理|概念|方法|定义|区别|介绍|总结|概括|分析|流程|步骤|"
        r"能.{0,4}(帮|生成|画|做)|请.{0,2}(解释|说明|描述|分析|介绍)",
        re.I,
    )),
    ("translate", re.compile(r"^翻译|^translate|请翻译|帮我翻译|译.{0,2}(为|成|到)", re.I)),
    ("organize", re.compile(r"分类|整理|归纳|标签|classify|categorize", re.I)),
    ("synthesize", re.compile(r"关联|跨文|综合|对比|compare|synthesize|cross", re.I)),
]

_CLASSIFY_PROMPT = """判断用户消息的意图，仅输出一个英文单词：
- translate（用户明确要求翻译某段文字，如"翻译：xxx"或"translate this"）
- organize（分类/整理/打标签）
- synthesize（跨文献分析/关联/对比）
- conversation（提问/讨论/知识问答/解释概念/其他所有情况）

重要：如果用户是在提问、讨论概念或请求解释（即使消息包含英文单词），应该选择 conversation。
只有用户明确要求"翻译某段文字"时才选择 translate。

用户消息: {msg}

意图:"""


class RouterAgent(BaseAgent):
    """Multi-agent router: detects intent and dispatches to specialists."""

    agent_id = "router"
    name = "Router"
    description = "Route user messages to the correct specialist agent"

    def __init__(self):
        super().__init__()
        self._translator = TranslatorAgent()
        self._conversation = ConversationAgent()

    def _detect_intent(self, message: str) -> str:
        """Detect user intent via keyword matching, fall back to LLM."""
        msg = message.strip()

        # Fast path: keyword rules
        for intent, pattern in _INTENT_PATTERNS:
            if pattern.search(msg):
                return intent

        # Short messages are almost always conversation
        if len(msg) < 12:
            return "conversation"

        # LLM classification for ambiguous messages
        try:
            raw = call_llm(
                system_prompt="你是意图分类器。仅输出一个英文单词。",
                user_prompt=_CLASSIFY_PROMPT.format(msg=msg[:300]),
                temperature=0.0,
                max_tokens=20,
            )
            intent = raw.strip().lower().rstrip(".")
            if intent in ("translate", "organize", "synthesize", "conversation"):
                return intent
        except Exception:
            pass

        return "conversation"

    def execute(self, payload: dict, context: dict = None) -> AgentOutput:
        """Route message to the appropriate agent.

        Args:
            payload: Dict with 'message' (user text), optional 'history'
            context: Dict with 'tree', 'lib', 'notes' for RAG

        Returns:
            AgentOutput from the dispatched specialist agent
        """
        message = payload.get("message", "")
        if not message or not message.strip():
            return AgentOutput(
                agent_id=self.agent_id, status="error", error="Empty message"
            )

        intent = self._detect_intent(message)

        if intent == "translate":
            result = self._translator.execute({"text": message}, context)
            result.data["intent"] = "translate"
            return result

        if intent in ("organize", "synthesize"):
            # These intents need notes in the payload; fall back to
            # conversation if we don't have them.
            notes = (context or {}).get("notes", [])
            if not notes:
                result = self._conversation.execute(
                    {"question": message, "history": payload.get("history", [])},
                    context,
                )
                result.data["intent"] = "conversation"
                result.data["note"] = "需要先上传文献并记录笔记才能进行整理/合成分析。"
                return result

            # For organize/synthesize, redirect to conversation with
            # a hint so it can answer about the user's request.
            result = self._conversation.execute(
                {"question": message, "history": payload.get("history", [])},
                context,
            )
            result.data["intent"] = intent
            return result

        # Default: conversation (RAG Q&A)
        result = self._conversation.execute(
            {"question": message, "history": payload.get("history", [])},
            context,
        )
        result.data["intent"] = "conversation"
        return result
