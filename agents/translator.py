"""
Translator Agent
================
Dedicated translation agent following BaseAgent protocol.
"""

from agents.base import BaseAgent, AgentOutput, call_llm


class TranslatorAgent(BaseAgent):
    """Bi-directional translation agent (Chinese <-> English)."""

    agent_id = "translator"
    name = "Translator"
    description = "Auto-detect language and translate between Chinese and English"

    def execute(self, payload: dict, context: dict = None) -> AgentOutput:
        text = payload.get("text", "")
        if not text or not text.strip():
            return AgentOutput(
                agent_id=self.agent_id, status="error", error="Empty text"
            )

        try:
            result = call_llm(
                system_prompt=(
                    "你是翻译引擎。如果输入是中文则翻译为英文，如果输入是英文则翻译为中文。"
                    "仅输出翻译结果，不加解释、不加引号。"
                ),
                user_prompt=text.strip(),
                temperature=0.1,
                max_tokens=500,
            )
            return AgentOutput(
                agent_id=self.agent_id,
                status="success",
                data={"translation": result.strip(), "original": text.strip()},
                confidence=0.9,
            )
        except Exception as e:
            return AgentOutput(agent_id=self.agent_id, status="error", error=str(e))
