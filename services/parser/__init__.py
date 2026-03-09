"""
Parser Services
===============
高级文档解析服务

支持的解析器:
- DoclingParser: IBM开源，轻量级，CPU友好
- MinerUParser: 高精度，支持OCR，GPU加速
"""

from .docling_parser import DoclingParser

# MinerU作为可选解析器
try:
    from .mineru_parser import MinerUParser
    MINERU_AVAILABLE = True
except ImportError:
    MinerUParser = None
    MINERU_AVAILABLE = False

__all__ = ["DoclingParser", "MinerUParser", "MINERU_AVAILABLE"]
