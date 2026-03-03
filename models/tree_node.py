"""
TreeNode Model
==============
统一树节点模型 - 支持章节/批注/图片/表格等多种类型。
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime

from core.state import next_node_id


# 批注颜色与重要性映射
PRIORITY_COLORS = {
    5: "#FF6B6B",  # 红色 - 核心观点
    4: "#FFA500",  # 橙色 - 重要内容
    3: "#FFE66D",  # 黄色 - 值得注意
    2: "#4ECDC4",  # 绿色 - 参考信息
    1: "#45B7D1",  # 蓝色 - 一般记录
}

COLOR_PRIORITY = {
    "red": 5,
    "#FF6B6B": 5,
    "orange": 4,
    "#FFA500": 4,
    "yellow": 3,
    "#FFE66D": 3,
    "green": 2,
    "#4ECDC4": 2,
    "blue": 1,
    "#45B7D1": 1,
}

# 旧版颜色到新版的映射
LEGACY_COLOR_MAP = {
    "red": "#FF6B6B",
    "yellow": "#FFE66D",
    "green": "#4ECDC4",
    "purple": "#9f7aea",
}


@dataclass
class TreeNode:
    """
    树节点 - 统一模型
    
    通过 type 字段区分不同类型的节点：
    - section: 章节块
    - annotation: 用户批注
    - figure: 图片
    - table: 表格
    
    Attributes:
        id: 唯一标识，格式 "doc001_n001"
        doc_id: 所属文献 ID
        parent_id: 父节点 ID（顶级节点为 None）
        children_ids: 子节点 ID 列表
        type: 节点类型
        content: 主要内容
        created_at: 创建时间
        
        # section 专用字段
        heading: 章节标题
        level: 层级 (1=H1, 2=H2, 3=H3)
        page_start: 起始页码
        page_end: 结束页码
        
        # annotation 专用字段
        selected_text: 选中的原文
        note: 用户批注内容
        priority: 重要性 (1-5)
        color: 高亮颜色
        
        # figure/table 专用字段
        caption: 图表标题
        ref_id: 引用编号
        
        # 兼容旧版字段
        tags: 标签列表
        metadata: 额外元数据
    """
    
    id: str
    doc_id: str
    type: Literal["section", "annotation", "figure", "table"]
    content: str = ""
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    
    # section 专用
    heading: Optional[str] = None
    level: Optional[int] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    
    # annotation 专用
    selected_text: Optional[str] = None
    note: Optional[str] = None
    priority: Optional[int] = 3
    color: Optional[str] = None
    
    # figure/table 专用
    caption: Optional[str] = None
    ref_id: Optional[str] = None
    
    # 兼容旧版
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    weight: float = 0.5  # 兼容 KnowledgeNode
    
    @classmethod
    def create_section(
        cls,
        doc_id: str,
        heading: str,
        level: int,
        content: str,
        parent_id: Optional[str] = None,
        page_start: Optional[int] = None,
        page_end: Optional[int] = None,
    ) -> "TreeNode":
        """创建章节节点"""
        node_id = f"{doc_id}_s{next_node_id().split('-')[1]}"
        return cls(
            id=node_id,
            doc_id=doc_id,
            parent_id=parent_id,
            type="section",
            content=content,
            heading=heading,
            level=level,
            page_start=page_start,
            page_end=page_end,
            weight=0.6,
        )
    
    @classmethod
    def create_annotation(
        cls,
        doc_id: str,
        parent_id: str,
        selected_text: str,
        note: str,
        priority: int = 3,
        color: Optional[str] = None,
        page: Optional[int] = None,
    ) -> "TreeNode":
        """创建批注节点
        
        Args:
            doc_id: 所属文献 ID
            parent_id: 父节点 ID（通常是章节或文档）
            selected_text: 选中的原文
            note: 用户批注内容
            priority: 重要性 (1-5)，默认 3
            color: 高亮颜色（可选，会自动根据 priority 设置）
            page: 页码
            
        Returns:
            创建的 annotation TreeNode
        """
        node_id = f"{doc_id}_a{next_node_id().split('-')[1]}"
        
        # 如果没有指定颜色，根据 priority 设置
        if color is None:
            color = PRIORITY_COLORS.get(priority, "#FFE66D")
        elif color in LEGACY_COLOR_MAP:
            # 转换旧版颜色
            color = LEGACY_COLOR_MAP[color]
        
        # 如果通过颜色推断 priority
        if priority == 3 and color in COLOR_PRIORITY:
            priority = COLOR_PRIORITY[color]
        
        return cls(
            id=node_id,
            doc_id=doc_id,
            parent_id=parent_id,
            type="annotation",
            content=note,
            selected_text=selected_text,
            note=note,
            priority=priority,
            color=color,
            page_start=page,
            weight=0.4 + priority * 0.1,  # 优先级越高权重越大
            metadata={"page": page} if page else {},
        )
    
    @classmethod
    def create_figure(
        cls,
        doc_id: str,
        parent_id: str,
        caption: str,
        ref_id: str,
        content: str = "",
    ) -> "TreeNode":
        """创建图片节点"""
        node_id = f"{doc_id}_f{next_node_id().split('-')[1]}"
        return cls(
            id=node_id,
            doc_id=doc_id,
            parent_id=parent_id,
            type="figure",
            content=content,
            caption=caption,
            ref_id=ref_id,
            weight=0.5,
        )
    
    @classmethod
    def create_table(
        cls,
        doc_id: str,
        parent_id: str,
        caption: str,
        ref_id: str,
        content: str = "",
    ) -> "TreeNode":
        """创建表格节点"""
        node_id = f"{doc_id}_t{next_node_id().split('-')[1]}"
        return cls(
            id=node_id,
            doc_id=doc_id,
            parent_id=parent_id,
            type="table",
            content=content,
            caption=caption,
            ref_id=ref_id,
            weight=0.5,
        )
    
    def add_child(self, node_id: str) -> None:
        """添加子节点 ID"""
        if node_id not in self.children_ids:
            self.children_ids.append(node_id)
    
    def remove_child(self, node_id: str) -> None:
        """移除子节点 ID"""
        if node_id in self.children_ids:
            self.children_ids.remove(node_id)
    
    def get_searchable_text(self) -> str:
        """获取可搜索文本（用于检索）"""
        parts = []
        
        if self.heading:
            parts.append(self.heading)
        if self.content:
            parts.append(self.content)
        if self.selected_text:
            parts.append(self.selected_text)
        if self.note:
            parts.append(self.note)
        if self.caption:
            parts.append(self.caption)
        if self.tags:
            parts.extend(self.tags)
            
        return " ".join(parts)
    
    def get_display_label(self) -> str:
        """获取显示标签"""
        if self.type == "section" and self.heading:
            return self.heading
        if self.type == "annotation":
            text = self.note or self.selected_text or ""
            return text[:30] + ("..." if len(text) > 30 else "")
        if self.caption:
            return self.caption
        return self.content[:30] + ("..." if len(self.content) > 30 else "")
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "id": self.id,
            "doc_id": self.doc_id,
            "type": self.type,
            "content": self.content,
            "parent_id": self.parent_id,
            "children_ids": self.children_ids,
            "created_at": self.created_at.isoformat(),
            "heading": self.heading,
            "level": self.level,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "selected_text": self.selected_text,
            "note": self.note,
            "priority": self.priority,
            "color": self.color,
            "caption": self.caption,
            "ref_id": self.ref_id,
            "tags": self.tags,
            "metadata": self.metadata,
            "weight": self.weight,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TreeNode":
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
            doc_id=data.get("doc_id", ""),
            type=data.get("type", "section"),
            content=data.get("content", ""),
            parent_id=data.get("parent_id"),
            children_ids=data.get("children_ids", []),
            created_at=created_at,
            heading=data.get("heading"),
            level=data.get("level"),
            page_start=data.get("page_start"),
            page_end=data.get("page_end"),
            selected_text=data.get("selected_text"),
            note=data.get("note"),
            priority=data.get("priority", 3),
            color=data.get("color"),
            caption=data.get("caption"),
            ref_id=data.get("ref_id"),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            weight=data.get("weight", 0.5),
        )
