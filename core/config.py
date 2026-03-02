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
API_BASE = "https://api-inference.modelscope.cn/v1"
MODEL_NAME = "deepseek-ai/DeepSeek-V3.2"

# Fallback models when primary model hits rate limit (429)
FALLBACK_MODELS = [
    "Qwen/Qwen2.5-72B-Instruct",
    "Qwen/Qwen2.5-Coder-32B-Instruct",
    "deepseek-ai/DeepSeek-V3",
]

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
