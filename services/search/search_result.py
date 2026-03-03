"""
SearchResult Model
==================
统一搜索结果数据结构
"""

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from models.tree_node import TreeNode
    from models.document import DocumentNode


@dataclass
class SearchResult:
    """
    搜索结果
    
    Attributes:
        node: 匹配的节点（TreeNode 或可转换为 dict）
        doc: 所属文献（DocumentNode 或可转换为 dict）
        score: 相关度/相似度分数
        match_type: 匹配类型 ("keyword" | "semantic" | "hybrid")
        matched_field: 匹配字段（关键词搜索时）
        highlight: 高亮片段
    """
    
    node: any  # TreeNode or dict
    doc: any   # DocumentNode or dict  
    score: float
    match_type: str = "keyword"
    matched_field: Optional[str] = None
    highlight: Optional[str] = None
    
    def to_dict(self) -> dict:
        """序列化为字典"""
        node_dict = self.node.to_dict() if hasattr(self.node, "to_dict") else self.node
        doc_dict = self.doc.to_dict() if hasattr(self.doc, "to_dict") else self.doc
        
        return {
            "node": node_dict,
            "doc": doc_dict,
            "score": self.score,
            "match_type": self.match_type,
            "matched_field": self.matched_field,
            "highlight": self.highlight,
        }
    
    def get_node_id(self) -> str:
        """获取节点 ID"""
        if hasattr(self.node, "id"):
            return self.node.id
        return self.node.get("id", "") if isinstance(self.node, dict) else ""
    
    def get_content_preview(self, max_len: int = 100) -> str:
        """获取内容预览"""
        if self.highlight:
            return self.highlight[:max_len]
        
        content = ""
        if hasattr(self.node, "content"):
            content = self.node.content
        elif isinstance(self.node, dict):
            content = self.node.get("content", "")
        
        if len(content) > max_len:
            return content[:max_len] + "..."
        return content
