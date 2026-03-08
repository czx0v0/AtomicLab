"""
Atomic Knowledge Models
=======================
原子知识解构数据模型

实现Atomic-RAG驱动的知识解构，将每条原子知识拆分为：
- Axiom（公理）：核心概念或事实
- Methodology（方法）：技术路径或方法
- Boundary（边界）：适用范围和限制

Categories:
- Method: 方法论（技术方法、算法、流程）
- Definition: 定义（概念定义、术语解释）
- Formula: 公式（数学公式、计算方法）
- Context: 背景（研究背景、历史上下文）
- Data: 数据（实验数据、统计结果）
- Result: 结果（研究发现、实验结论）
- Insight: 洞察（观点、见解、推论）
"""

from dataclasses import dataclass, field
from typing import List, Optional, Literal
from datetime import datetime


# 知识分类枚举
KnowledgeCategory = Literal[
    "Method",  # 方法论
    "Definition",  # 定义
    "Formula",  # 公式
    "Context",  # 背景
    "Data",  # 数据
    "Result",  # 结果
    "Insight",  # 洞察
]


@dataclass
class AtomicKnowledge:
    """原子知识结构

    将一条笔记解构为三层结构：
    - Axiom: 公理层，核心概念
    - Methodology: 方法层，技术路径
    - Boundary: 边界层，适用范围
    """

    # 基本信息
    knowledge_id: str
    original_note_id: str  # 原始笔记ID
    doc_id: str  # 文献ID

    # 三层解构
    axiom: str  # 公理：核心概念或事实
    methodology: str  # 方法：技术路径或方法
    boundary: str  # 边界：适用范围和限制

    # 分类
    category: KnowledgeCategory

    # 元数据
    confidence: float = 1.0  # 解构置信度 (0-1)
    tags: List[str] = field(default_factory=list)

    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "knowledge_id": self.knowledge_id,
            "original_note_id": self.original_note_id,
            "doc_id": self.doc_id,
            "axiom": self.axiom,
            "methodology": self.methodology,
            "boundary": self.boundary,
            "category": self.category,
            "confidence": self.confidence,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
        }

    def to_rag_text(self) -> str:
        """转换为RAG检索文本

        将三层结构合并为一段文本，用于向量检索
        """
        return f"""【{self.category}】
核心概念：{self.axiom}
方法路径：{self.methodology}
适用范围：{self.boundary}
标签：{', '.join(self.tags) if self.tags else '无'}
置信度：{self.confidence:.2f}
"""


@dataclass
class AtomicDecomposition:
    """原子解构结果

    一条笔记可能被解构为多个原子知识
    """

    note_id: str
    doc_id: str

    # 解构结果
    atoms: List[AtomicKnowledge] = field(default_factory=list)

    # 解构质量
    overall_confidence: float = 0.0
    decomposition_time_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "note_id": self.note_id,
            "doc_id": self.doc_id,
            "atoms": [a.to_dict() for a in self.atoms],
            "overall_confidence": self.overall_confidence,
            "decomposition_time_ms": self.decomposition_time_ms,
        }


# 分类描述映射
CATEGORY_DESCRIPTIONS = {
    "Method": "方法论：描述技术方法、算法、实验流程等",
    "Definition": "定义：解释概念、术语、定义等",
    "Formula": "公式：数学公式、计算方法、方程等",
    "Context": "背景：研究背景、历史上下文、相关工作等",
    "Data": "数据：实验数据、统计结果、数据集等",
    "Result": "结果：研究发现、实验结论、性能指标等",
    "Insight": "洞察：观点、见解、推论、未来方向等",
}

# 分类提示词映射（用于LLM）
CATEGORY_PROMPTS = {
    "Method": "如果内容描述了具体的技术方法、算法或实验流程",
    "Definition": "如果内容定义了概念、解释了术语或提供了定义",
    "Formula": "如果内容包含数学公式、计算方法或方程",
    "Context": "如果内容提供了研究背景、历史或相关工作",
    "Data": "如果内容包含实验数据、统计结果或数据集描述",
    "Result": "如果内容报告了研究发现、实验结论或性能指标",
    "Insight": "如果内容表达了观点、见解、推论或未来方向",
}
