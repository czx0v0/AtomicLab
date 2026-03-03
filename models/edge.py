"""
Edge Model
==========
文献间边关系 - 表示文献之间的引用、相似、扩展关系。
"""

from dataclasses import dataclass
from typing import Dict, Any, Literal


@dataclass
class Edge:
    """
    文献间边
    
    Attributes:
        source_id: 源文献/节点 ID
        target_id: 目标文献/节点 ID
        relation: 关系类型
        weight: 关系权重 (0-1)
    """
    
    source_id: str
    target_id: str
    relation: Literal["cites", "similar", "extends", "contains", "tagged_with", "references"]
    weight: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation,
            "weight": self.weight,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Edge":
        """从字典反序列化"""
        # 兼容旧版字段名
        source_id = data.get("source_id") or data.get("source", "")
        target_id = data.get("target_id") or data.get("target", "")
        
        return cls(
            source_id=source_id,
            target_id=target_id,
            relation=data.get("relation", "references"),
            weight=data.get("weight", 1.0),
        )
    
    def to_echarts_link(self) -> Dict[str, Any]:
        """转换为 ECharts link 格式"""
        line_styles = {
            "cites": "solid",
            "similar": "dashed",
            "extends": "dotted",
            "contains": "solid",
            "tagged_with": "dashed",
            "references": "dotted",
        }
        return {
            "source": self.source_id,
            "target": self.target_id,
            "lineStyle": {
                "type": line_styles.get(self.relation, "solid"),
                "width": 1 + self.weight * 2,
                "opacity": 0.5,
            },
        }
