"""
Atomic Lab Configuration
========================
API settings, model configuration, and global constants.
"""

import os
from dotenv import load_dotenv

load_dotenv()  # 本地开发用，魔搭空间通过环境变量配置

# ══════════════════════════════════════════════════════════════
# API Configuration
# ══════════════════════════════════════════════════════════════
MS_KEY = os.environ.get("MS_KEY", "")
API_BASE = os.environ.get("API_BASE", "https://api-inference.modelscope.cn/v1")

# Primary model (user-configurable via env)
MODEL_NAME = os.environ.get("MODEL_NAME", "deepseek-ai/DeepSeek-V3.2")

# Fallback models (user-configurable via env, comma-separated)
_default_fallbacks = (
    "Qwen/Qwen3-235B-A22B,Qwen/Qwen3-32B,MiniMax/MiniMax-M2.5,ZhipuAI/GLM-4.7-Flash"
)
FALLBACK_MODELS = [
    m.strip()
    for m in os.environ.get("FALLBACK_MODELS", _default_fallbacks).split(",")
    if m.strip()
]

# Cooldown duration (hours) when a model hits rate limit
COOLDOWN_HOURS = float(os.environ.get("COOLDOWN_HOURS", "1.0"))


def _make_display_name(model_id: str) -> str:
    """Generate display name from model ID (e.g. 'Qwen/Qwen3-32B' -> 'Qwen3 32B')."""
    name = model_id.split("/")[-1]  # Take part after /
    return name.replace("-", " ").replace("_", " ")


def _is_thinking_model(model_id: str) -> bool:
    """Check if model requires enable_thinking=false (Qwen3 series)."""
    return "Qwen3" in model_id or "qwen3" in model_id.lower()


# Display names for UI (auto-generated, can override via code)
MODEL_DISPLAY_NAMES = {m: _make_display_name(m) for m in [MODEL_NAME] + FALLBACK_MODELS}

# Models requiring thinking mode disabled for non-streaming (auto-detected)
THINKING_MODELS = {m for m in [MODEL_NAME] + FALLBACK_MODELS if _is_thinking_model(m)}

# ══════════════════════════════════════════════════════════════
# Access Control
# ══════════════════════════════════════════════════════════════
ENABLE_AUTH = os.environ.get("ENABLE_AUTH", "true").lower() == "true"
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "")  # Set in .env, never hardcode

# ══════════════════════════════════════════════════════════════
# Application Constants
# ══════════════════════════════════════════════════════════════
APP_TITLE = "Atomic Lab"
APP_SUBTITLE = "Read · Organize · Write"

# Knowledge Node Types
NODE_TYPES = ["domain", "document", "note", "tag"]

# Note Categories
NOTE_CATEGORIES = ["方法", "公式", "图像", "定义", "观点", "数据", "其他"]

# Category Badge Colors
CATEGORY_COLORS = {
    "方法": "#5b8def",
    "公式": "#48bb78",
    "图像": "#ed8936",
    "定义": "#9f7aea",
    "观点": "#e53e3e",
    "数据": "#38b2ac",
    "其他": "#a0aec0",
}

# Edge Relation Types
EDGE_RELATIONS = ["contains", "tagged_with", "references"]

# ECharts Node Colors
NODE_COLORS = {
    "domain": "#5b8def",  # Blue
    "document": "#48bb78",  # Green
    "note": "#ecc94b",  # Yellow
    "tag": "#9f7aea",  # Purple
}

# ECharts Node Sizes
NODE_SIZES = {
    "domain": 50,
    "document": 40,
    "note": 25,
    "tag": 15,
}
