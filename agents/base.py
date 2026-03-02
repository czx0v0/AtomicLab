"""
Base Agent Protocol
===================
Unified interface for all Atomic Lab agents.
"""

from dataclasses import dataclass, field
from typing import Literal, Any
from datetime import datetime
from openai import OpenAI

from core.config import API_BASE, MS_KEY, MODEL_NAME, FALLBACK_MODELS


@dataclass
class AgentOutput:
    """Standardized output from any agent.

    Attributes:
        agent_id: Identifier of the agent that produced this output
        status: Execution status
        data: Agent-specific output data
        confidence: Confidence score (0.0-1.0)
        tokens_used: Number of tokens consumed
        ts: Timestamp of execution
        error: Error message if status is 'error'
    """

    agent_id: str
    status: Literal["success", "error", "partial"]
    data: dict = field(default_factory=dict)
    confidence: float = 0.0
    tokens_used: int = 0
    ts: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    error: str = ""


class BaseAgent:
    """Base class for all Atomic Lab agents.

    All agents should inherit from this class and implement
    the execute() method.

    Attributes:
        agent_id: Unique identifier for this agent
        name: Human-readable name
        description: Brief description of agent's purpose
    """

    agent_id: str = "base"
    name: str = "Base Agent"
    description: str = "Base agent class"

    def __init__(self):
        """Initialize the agent."""
        pass

    def execute(self, payload: dict, context: dict = None) -> AgentOutput:
        """Execute the agent's main task.

        Args:
            payload: Input data for the agent
            context: Optional context (tree, lib, etc.)

        Returns:
            AgentOutput with results
        """
        raise NotImplementedError("Subclasses must implement execute()")

    def validate_payload(self, payload: dict) -> tuple[bool, str]:
        """Validate input payload.

        Args:
            payload: Input to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        return True, ""


def _is_rate_limit_error(e: Exception) -> bool:
    """Check if an exception is a rate limit / quota error."""
    # Check status_code attribute (openai library sets this)
    if getattr(e, "status_code", None) == 429:
        return True
    err_str = str(e).lower()
    return any(kw in err_str for kw in ("429", "quota", "rate limit", "exceeded"))


def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.15,
    max_tokens: int = 800,
) -> str:
    """Call the LLM API with automatic fallback on rate limit (429).

    Tries MODEL_NAME first, then each FALLBACK_MODELS in order.
    Disables built-in retries since quota errors won't resolve with retries.

    Args:
        system_prompt: System message
        user_prompt: User message
        temperature: Sampling temperature
        max_tokens: Maximum tokens in response

    Returns:
        Generated text response

    Raises:
        Exception: If all models fail
    """
    client = OpenAI(base_url=API_BASE, api_key=MS_KEY, max_retries=0)
    models = [MODEL_NAME] + list(FALLBACK_MODELS)
    last_error = None

    for model in models:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            last_error = e
            if _is_rate_limit_error(e):
                print(f"[call_llm] {model} rate-limited, trying next...")
                continue
            # Other errors: raise immediately
            raise

    # All models exhausted
    raise last_error
