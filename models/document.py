"""
DocumentNode Model
==================
文献根节点 - 表示一篇完整的文献文档。
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

from core.state import next_node_id


@dataclass
class DocumentNode:
    """
    文献节点 - 树的根节点
    
    每篇文献对应一个 DocumentNode，包含文献元信息。
    子节点为章节(section)、批注(annotation)等 TreeNode。
    
    Attributes:
        id: 唯一标识，格式 "doc001"
        title: 文献标题
        keywords: 关键词列表
        abstract: 摘要内容
        filepath: 文件路径
        filetype: 文件类型 ("pdf" | "txt" | "md")
        created_at: 创建时间
        children_ids: 顶级子节点 ID 列表
        metadata: 额外元数据（作者、年份等）
    """
    
    id: str
    title: str
    keywords: List[str] = field(default_factory=list)
    abstract: str = ""
    filepath: str = ""
    filetype: str = "pdf"
    created_at: datetime = field(default_factory=datetime.now)
    children_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 兼容旧版 KnowledgeNode 属性
    source_pid: str = ""  # 用于兼容性
    
    @classmethod
    def create(cls, filepath: str, title: str = "") -> "DocumentNode":
        """从文件创建文献节点
        
        Args:
            filepath: 文件路径
            title: 文献标题（可选，默认使用文件名）
            
        Returns:
            新创建的 DocumentNode
        """
        import os
        import hashlib
        
        filename = os.path.basename(filepath)
        doc_id = "doc-" + hashlib.md5(filename.encode()).hexdigest()[:6].upper()
        
        # 推断文件类型
        ext = os.path.splitext(filepath)[1].lower()
        filetype_map = {".pdf": "pdf", ".txt": "txt", ".md": "md"}
        filetype = filetype_map.get(ext, "txt")
        
        return cls(
            id=doc_id,
            title=title or filename,
            filepath=filepath,
            filetype=filetype,
            source_pid=doc_id,
        )
    
    def add_child(self, node_id: str) -> None:
        """添加子节点 ID"""
        if node_id not in self.children_ids:
            self.children_ids.append(node_id)
    
    def remove_child(self, node_id: str) -> None:
        """移除子节点 ID"""
        if node_id in self.children_ids:
            self.children_ids.remove(node_id)
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "keywords": self.keywords,
            "abstract": self.abstract,
            "filepath": self.filepath,
            "filetype": self.filetype,
            "created_at": self.created_at.isoformat(),
            "children_ids": self.children_ids,
            "metadata": self.metadata,
            "source_pid": self.source_pid,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentNode":
        """从字典反序列化"""
        created_at = data.get("created_at", "")
        if isinstance(created_at, str) and created_at:
            try:
                created_at = datetime.fromisoformat(created_at)
            except ValueError:
                created_at = datetime.now()
        else:
            created_at = datetime.now()
            
        return cls(
            id=data["id"],
            title=data.get("title", ""),
            keywords=data.get("keywords", []),
            abstract=data.get("abstract", ""),
            filepath=data.get("filepath", ""),
            filetype=data.get("filetype", "pdf"),
            created_at=created_at,
            children_ids=data.get("children_ids", []),
            metadata=data.get("metadata", {}),
            source_pid=data.get("source_pid", data["id"]),
        )
