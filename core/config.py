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

# ══════════════════════════════════════════════════════════════
# Application Constants
# ══════════════════════════════════════════════════════════════
APP_TITLE = "Atomic Lab v3.0"
APP_SUBTITLE = "Read · Organize · Write"

# Knowledge Node Types
NODE_TYPES = ["domain", "atom", "note", "concept"]

# Edge Relation Types
EDGE_RELATIONS = ["derives_from", "contradicts", "extends", "references"]

# ECharts Node Colors
NODE_COLORS = {
    "domain": "#5b8def",   # Blue
    "atom": "#48bb78",     # Green
    "note": "#ecc94b",     # Yellow
    "concept": "#9f7aea",  # Purple
}

# ECharts Node Sizes
NODE_SIZES = {
    "domain": 50,
    "atom": 30,
    "note": 15,
    "concept": 22,
}
