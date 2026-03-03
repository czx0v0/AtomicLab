"""
Data Models
===========
Core data structures for AtomicLab v2.0:
- DocumentNode: 文献根节点
- TreeNode: 统一树节点模型 (section/annotation/figure/table)
- Edge: 文献间关系
- KnowledgeGraph: 文献知识图谱
"""

from .document import DocumentNode
from .tree_node import TreeNode
from .edge import Edge
from .graph import KnowledgeGraph

__all__ = [
    "DocumentNode",
    "TreeNode",
    "Edge",
    "KnowledgeGraph",
]
