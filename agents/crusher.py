"""
Crusher Agent
=============
Knowledge deconstruction engine that converts notes into atomic knowledge.
"""

from .base import BaseAgent, AgentOutput, call_llm
from core.utils import pjson
from core.state import next_atom_id


# ══════════════════════════════════════════════════════════════
# System Prompts
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


class CrusherAgent(BaseAgent):
    """Agent for deconstructing text into atomic knowledge.
    
    Takes notes and context, produces structured atoms with
    axiom, methodology, and boundary components.
    """
    
    agent_id = "crusher"
    name = "Crusher"
    description = "知识解构引擎"
    
    def execute(self, payload: dict, context: dict = None) -> AgentOutput:
        """Deconstruct text into atoms.
        
        Args:
            payload: Dict with 'text' key containing text to deconstruct
            context: Optional dict with 'doc_context' for reference
            
        Returns:
            AgentOutput with atoms data
        """
        text = payload.get("text", "")
        if not text or not text.strip():
            return AgentOutput(
                agent_id=self.agent_id,
                status="error",
                error="No text provided for deconstruction",
            )
        
        doc_context = ""
        if context:
            doc_context = context.get("doc_context", "")[:3000]
        if not doc_context:
            doc_context = "(无文献上下文)"
        
        try:
            raw = call_llm(
                CRUSH_SYS,
                CRUSH_USR.format(context=doc_context, text=text)
            )
            data = pjson(raw)
            
            if not data or "atoms" not in data:
                return AgentOutput(
                    agent_id=self.agent_id,
                    status="error",
                    error=f"Failed to parse response: {raw[:100]}",
                )
            
            # Assign IDs to atoms
            for atom in data["atoms"]:
                atom["id"] = next_atom_id()
            
            return AgentOutput(
                agent_id=self.agent_id,
                status="success",
                data=data,
                confidence=data.get("confidence", 0.8),
            )
            
        except Exception as e:
            return AgentOutput(
                agent_id=self.agent_id,
                status="error",
                error=str(e),
            )
    
    def validate_payload(self, payload: dict) -> tuple[bool, str]:
        """Validate crusher payload.
        
        Args:
            payload: Input to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not payload.get("text"):
            return False, "Missing 'text' field"
        return True, ""
