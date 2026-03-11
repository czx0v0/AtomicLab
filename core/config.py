"""
Atomic Lab Configuration
========================
API settings, model configuration, and global constants.
"""

import os
from dotenv import load_dotenv

load_dotenv()  # 本地开发用，魔搭空间通过环境变量配置

# Windows下默认关闭HF symlink提示，避免日志噪音影响排障。
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# ══════════════════════════════════════════════════════════════
# HuggingFace镜像配置 - 中国大陆加速
# ══════════════════════════════════════════════════════════════

# 检测是否运行在ModelScope创空间环境
# 关键：只有明确的创空间特征才触发，本地开发不应受影响
# 本地设置MS_KEY只是用于API调用，不代表是创空间环境
import sys

IN_MODELSCOPE_SPACE = False  # 默认为本地环境

# 检测方法1: Linux系统 + /mnt/workspace目录存在（创空间特有）
if sys.platform.startswith("linux") and os.path.exists("/mnt/workspace"):
    IN_MODELSCOPE_SPACE = True
    print("[Config] 检测方式1: /mnt/workspace目录存在")

# 检测方法2: 明确的创空间环境变量
if os.environ.get("MODELSCOPE_ENVIRONMENT", "").lower() == "studio":
    IN_MODELSCOPE_SPACE = True
    print("[Config] 检测方式2: MODELSCOPE_ENVIRONMENT=studio")

# HuggingFace镜像配置
# ModelScope创空间无法访问HuggingFace，需要特殊处理
if IN_MODELSCOPE_SPACE:
    # 创空间：使用ModelScope模型源
    # 设置ModelScope缓存目录（持久化）
    os.environ["MODELSCOPE_CACHE"] = "/mnt/workspace/.cache/modelscope"

    # 尝试从ModelScope下载sentence-transformers模型
    # ModelScope镜像了常用的embedding模型
    print("[Config] 创空间环境，配置ModelScope模型源")

    # 设置使用ModelScope的HF镜像（部分可用）
    if "HF_ENDPOINT" not in os.environ:
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        print("[Config] 尝试HuggingFace镜像: hf-mirror.com")
else:
    # 本地开发：统一启用镜像加速
    if "HF_ENDPOINT" not in os.environ:
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        print("[Config] 已启用HuggingFace镜像加速: hf-mirror.com")

# ══════════════════════════════════════════════════════════════
# 模型缓存目录 - 仅ModelScope创空间需要特殊设置
# ══════════════════════════════════════════════════════════════

# 重要：本地开发不设置任何缓存目录，完全使用HuggingFace默认行为
# 这样不会影响已有的本地缓存
if IN_MODELSCOPE_SPACE:
    # 创空间专用模型缓存目录（持久化存储）
    MODEL_CACHE_DIR = "/mnt/workspace/.cache/huggingface"
    # 注意：不要覆盖已有的缓存设置，只在需要时设置
    if "TRANSFORMERS_CACHE" not in os.environ:
        os.environ["TRANSFORMERS_CACHE"] = MODEL_CACHE_DIR
    if "HF_HOME" not in os.environ:
        os.environ["HF_HOME"] = MODEL_CACHE_DIR
    print(f"[Config] ModelScope创空间环境")
    print(f"[Config] 模型缓存目录: {MODEL_CACHE_DIR}")

    # ══════════════════════════════════════════════════════════════
    # MinerU 自动初始化（创空间无终端访问权限时）
    # ══════════════════════════════════════════════════════════════
    MINERU_CONFIG_FILE = "/mnt/workspace/.magic-pdf.json"
    MODELSCOPE_CACHE_DIR = "/mnt/workspace/.cache/modelscope"

    # 设置 MinerU 环境变量（先于配置文件生成，让 mineru 知道模型缓存路径）
    os.environ.setdefault("MINERU_TOOLS_CONFIG_JSON", MINERU_CONFIG_FILE)
    os.environ.setdefault("MODELSCOPE_CACHE", MODELSCOPE_CACHE_DIR)

    # 自动创建/更新 MinerU 配置文件
    # 关键：不再硬编码 models-dir，让 mineru 使用自身默认路径
    # mineru-models-download 默认下到 ~/.cache/magic-pdf/ 或 MODELSCOPE_CACHE
    # 若 models-dir 路径不存在，magic-pdf 会静默退出(exit 0)不产生任何输出
    try:
        import json

        _need_write = True
        if os.path.exists(MINERU_CONFIG_FILE):
            try:
                with open(MINERU_CONFIG_FILE, "r") as _f:
                    _existing = json.load(_f)
                # 如果旧配置包含不存在的 models-dir，需要更新
                _old_models_dir = _existing.get("models-dir", "")
                if _old_models_dir and os.path.isdir(_old_models_dir):
                    _need_write = False  # 路径存在，保留旧配置
                    print(
                        f"[Config] MinerU 配置文件有效，models-dir: {_old_models_dir}"
                    )
                else:
                    print(
                        f"[Config] MinerU 配置文件中 models-dir 不存在: {_old_models_dir}，将更新"
                    )
            except Exception:
                pass

        if _need_write:
            # 不设置 models-dir，让 mineru 自动查找
            config_content = {"device-mode": "cpu"}
            with open(MINERU_CONFIG_FILE, "w") as f:
                json.dump(config_content, f, indent=2)
            print(
                f"[Config] 已更新 MinerU 配置文件: {MINERU_CONFIG_FILE} (不指定models-dir，使用默认路径)"
            )
    except Exception as e:
        print(f"[Config] 创建 MinerU 配置文件失败: {e}")

    # 打印 magic-pdf 模型可能存在的路径（方便排查）
    _possible_model_dirs = [
        "/root/.cache/magic-pdf/models",
        f"{MODELSCOPE_CACHE_DIR}/models",
        os.path.expanduser("~/.cache/magic-pdf/models"),
    ]
    for _d in _possible_model_dirs:
        if os.path.exists(_d):
            _files = os.listdir(_d)
            print(f"[Config] MinerU 模型目录已找到: {_d} ({len(_files)} 个文件)")
            break
    else:
        print("[Config] 未找到 MinerU 模型目录，首次解析将触发自动下载")
else:
    MODEL_CACHE_DIR = None  # 使用默认

# 本地环境如果显式设置了HF_HOME，同步到hub/cache相关变量
# 避免部分依赖仍回落到C盘默认缓存路径。
if not IN_MODELSCOPE_SPACE:
    _hf_home = os.environ.get("HF_HOME", "").strip()
    if _hf_home:
        _hf_home = os.path.normpath(_hf_home)
        os.environ["HF_HOME"] = _hf_home
        os.environ.setdefault("TRANSFORMERS_CACHE", _hf_home)
        os.environ.setdefault("HF_HUB_CACHE", os.path.join(_hf_home, "hub"))
        os.environ.setdefault("HUGGINGFACE_HUB_CACHE", os.path.join(_hf_home, "hub"))
        # 仅关闭警告，不影响功能；用于减少Windows链接提示噪音。
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        print(f"[Config] 本地HF_HOME: {os.environ.get('HF_HOME')}")
        print(f"[Config] 本地HF_HUB_CACHE: {os.environ.get('HF_HUB_CACHE')}")

# ══════════════════════════════════════════════════════════════
# API Configuration
# ══════════════════════════════════════════════════════════════
MS_KEY = os.environ.get("MS_KEY", "")
API_BASE = os.environ.get("API_BASE", "https://api-inference.modelscope.cn/v1")

# DeepSeek direct API (fallback when ModelScope is rate-limited)
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_BASE = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")

# Primary model (user-configurable via env)
MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen3.5-35B-A3B")

# Fallback models (user-configurable via env, comma-separated)
_default_fallbacks = "deepseek-ai/DeepSeek-V3.2,Qwen/Qwen3-235B-A22B,Qwen/Qwen3-32B,MiniMax/MiniMax-M2.5,ZhipuAI/GLM-4.7-Flash"
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

# ══════════════════════════════════════════════════════════════
# RAG Configuration
# ══════════════════════════════════════════════════════════════

# RAG服务配置
RAG_CONFIG = {
    # 模型配置
    "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
    "reranker_model": "BAAI/bge-reranker-v2-m3",
    "device": "cpu",
    # 分块配置
    "chunk_size": int(os.environ.get("RAG_CHUNK_SIZE", "900")),
    "chunk_overlap": int(os.environ.get("RAG_CHUNK_OVERLAP", "120")),
    "similarity_threshold": float(os.environ.get("RAG_SIMILARITY_THRESHOLD", "0.58")),
    # 分块模式: semantic(语义分块) | paragraph(段落分块)
    "chunk_mode": os.environ.get("CHUNK_MODE", "paragraph"),
    # 检索配置
    "vector_index_type": "HNSW",  # Flat, IVF, HNSW
    "rrf_k": 60,
    "semantic_weight": 0.6,
    "keyword_weight": 0.3,
    "metadata_weight": 0.1,
    # 重排序配置
    "use_reranker": True,
    "rerank_top_n": 20,
    # 质量配置
    "min_parse_confidence": 0.5,
    "enable_quality_check": True,
    # 解析器配置
    "parser_backend": os.environ.get("PARSER_BACKEND", "docling"),
    "mineru_parse_method": os.environ.get("MINERU_PARSE_METHOD", "auto"),
}

# 存储路径配置
STORAGE_PATHS = {
    "faiss_index": "storage/faiss/index.faiss",
    "bm25_index": "storage/bm25/index.pkl",
    "documents": "storage/documents",
    "chunks": "storage/chunks",
}

# Chunk类型配置
CHUNK_TYPES = [
    "paragraph",  # 段落分块
    "semantic",  # 语义分块
    "section",  # 章节分块
    "table_semantic",  # 表格语义描述
    "table_row",  # 表格行
    "figure",  # 图片描述
    "formula",  # 公式
]

# ══════════════════════════════════════════════════════════════
# Parser Configuration
# ══════════════════════════════════════════════════════════════

# PDF解析后端选择
# - "docling": IBM开源，轻量级，CPU友好 (默认)
# - "mineru": 高精度，支持OCR，GPU加速
PARSER_BACKEND = os.environ.get("PARSER_BACKEND", "docling")

# ══════════════════════════════════════════════════════════════
# Feedback Configuration
# ══════════════════════════════════════════════════════════════

# 反馈数据存储路径 (用于RAG模型微调)
FEEDBACK_STORAGE_PATH = os.environ.get(
    "FEEDBACK_STORAGE_PATH",
    "/mnt/workspace/storage/feedback" if IN_MODELSCOPE_SPACE else "storage/feedback",
)
