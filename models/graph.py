"""
KnowledgeGraph Model
====================
文献知识图谱 - 管理多篇文献及其关系。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from .document import DocumentNode
from .tree_node import TreeNode
from .edge import Edge


@dataclass
class KnowledgeGraph:
    """
    文献知识图谱
    
    管理多篇文献之间的关系，提供图结构操作。
    
    Attributes:
        documents: 文献节点字典 {doc_id -> DocumentNode}
        tree_nodes: 树节点字典 {node_id -> TreeNode}
        edges: 关系边列表
    """
    
    documents: Dict[str, DocumentNode] = field(default_factory=dict)
    tree_nodes: Dict[str, TreeNode] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)
    
    def add_document(self, doc: DocumentNode) -> None:
        """添加文献"""
        self.documents[doc.id] = doc
    
    def remove_document(self, doc_id: str) -> None:
        """移除文献及其所有子节点"""
        if doc_id not in self.documents:
            return
        
        # 移除所有相关的树节点
        nodes_to_remove = [
            nid for nid, node in self.tree_nodes.items()
            if node.doc_id == doc_id
        ]
        for nid in nodes_to_remove:
            del self.tree_nodes[nid]
        
        # 移除所有相关的边
        self.edges = [
            e for e in self.edges
            if e.source_id != doc_id and e.target_id != doc_id
            and e.source_id not in nodes_to_remove
            and e.target_id not in nodes_to_remove
        ]
        
        # 移除文献
        del self.documents[doc_id]
    
    def get_document(self, doc_id: str) -> Optional[DocumentNode]:
        """获取文献"""
        return self.documents.get(doc_id)
    
    def add_tree_node(self, node: TreeNode) -> str:
        """添加树节点"""
        self.tree_nodes[node.id] = node
        
        # 更新父节点的 children_ids
        if node.parent_id:
            if node.parent_id in self.tree_nodes:
                self.tree_nodes[node.parent_id].add_child(node.id)
            elif node.parent_id in self.documents:
                self.documents[node.parent_id].add_child(node.id)
        
        return node.id
    
    def get_tree_node(self, node_id: str) -> Optional[TreeNode]:
        """获取树节点"""
        return self.tree_nodes.get(node_id)
    
    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        weight: float = 1.0,
    ) -> None:
        """添加边（文献关系）"""
        edge = Edge(
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            weight=weight,
        )
        self.edges.append(edge)
    
    def get_related_documents(
        self,
        doc_id: str,
        relation: Optional[str] = None,
    ) -> List[DocumentNode]:
        """获取相关文献"""
        related = []
        for edge in self.edges:
            target_id = None
            if edge.source_id == doc_id:
                target_id = edge.target_id
            elif edge.target_id == doc_id:
                target_id = edge.source_id
            
            if target_id and target_id in self.documents:
                if relation is None or edge.relation == relation:
                    related.append(self.documents[target_id])
        
        return related
    
    def get_all_nodes(self) -> List[TreeNode]:
        """获取所有树节点（用于搜索）"""
        return list(self.tree_nodes.values())
    
    def get_document_nodes(self, doc_id: str) -> List[TreeNode]:
        """获取指定文献的所有树节点"""
        return [
            node for node in self.tree_nodes.values()
            if node.doc_id == doc_id
        ]
    
    def get_annotations(self, doc_id: Optional[str] = None) -> List[TreeNode]:
        """获取批注节点"""
        nodes = self.tree_nodes.values()
        if doc_id:
            nodes = [n for n in nodes if n.doc_id == doc_id]
        return [n for n in nodes if n.type == "annotation"]
    
    def get_children(self, parent_id: str) -> List[TreeNode]:
        """获取子节点"""
        parent = self.tree_nodes.get(parent_id) or self.documents.get(parent_id)
        if not parent:
            return []
        
        children_ids = parent.children_ids if hasattr(parent, "children_ids") else []
        return [
            self.tree_nodes[cid]
            for cid in children_ids
            if cid in self.tree_nodes
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "documents": {
                doc_id: doc.to_dict()
                for doc_id, doc in self.documents.items()
            },
            "tree_nodes": {
                node_id: node.to_dict()
                for node_id, node in self.tree_nodes.items()
            },
            "edges": [e.to_dict() for e in self.edges],
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeGraph":
        """从字典反序列化"""
        graph = cls()
        
        for doc_id, doc_data in data.get("documents", {}).items():
            graph.documents[doc_id] = DocumentNode.from_dict(doc_data)
        
        for node_id, node_data in data.get("tree_nodes", {}).items():
            graph.tree_nodes[node_id] = TreeNode.from_dict(node_data)
        
        for edge_data in data.get("edges", []):
            graph.edges.append(Edge.from_dict(edge_data))
        
        return graph
    
    # ══════════════════════════════════════════════════════════════
    # ECharts 可视化支持
    # ══════════════════════════════════════════════════════════════
    
    def to_echarts_option(self, highlight_ids: List[str] = None) -> Dict[str, Any]:
        """生成 ECharts 图谱配置"""
        from core.config import NODE_COLORS, NODE_SIZES, CATEGORY_COLORS
        
        highlight_ids = highlight_ids or []
        
        nodes_data = []
        
        # 添加文献节点
        for doc in self.documents.values():
            size = 40
            color = NODE_COLORS.get("document", "#48bb78")
            tooltip = f"[文献] {doc.title}"
            
            nodes_data.append({
                "id": doc.id,
                "name": doc.title[:24] + ("..." if len(doc.title) > 24 else ""),
                "value": tooltip,
                "symbolSize": size,
                "category": "document",
                "itemStyle": {"color": color},
                "label": {"show": True},
            })
        
        # 添加树节点
        for node in self.tree_nodes.values():
            if node.type == "annotation":
                color = node.color or CATEGORY_COLORS.get("其他", "#a0aec0")
                size = 20 + (node.priority or 3) * 3
            else:
                color = NODE_COLORS.get(node.type, "#ecc94b")
                size = NODE_SIZES.get(node.type, 20) * (0.5 + node.weight)
            
            label = node.get_display_label()
            tooltip_parts = [f"[{node.type}] {label}"]
            if node.content and node.content != label:
                tooltip_parts.append(node.content[:100])
            
            node_data = {
                "id": node.id,
                "name": label[:24] + ("..." if len(label) > 24 else ""),
                "value": "\n".join(tooltip_parts),
                "symbolSize": size,
                "category": node.type,
                "itemStyle": {"color": color},
                "label": {"show": node.type == "section"},
            }
            
            if node.id in highlight_ids:
                node_data["itemStyle"] = {
                    "color": "#f56565",
                    "borderWidth": 3,
                    "borderColor": "#c53030",
                }
                node_data["label"]["show"] = True
            
            nodes_data.append(node_data)
        
        # 生成边
        links_data = [edge.to_echarts_link() for edge in self.edges]
        
        # 添加父子关系边
        for node in self.tree_nodes.values():
            if node.parent_id:
                links_data.append({
                    "source": node.parent_id,
                    "target": node.id,
                    "lineStyle": {
                        "type": "solid",
                        "width": 1,
                        "opacity": 0.4,
                    },
                })
        
        categories = [
            {"name": "document"},
            {"name": "section"},
            {"name": "annotation"},
            {"name": "figure"},
            {"name": "table"},
        ]
        
        return {
            "tooltip": {
                "trigger": "item",
                "formatter": "{c}",
                "textStyle": {"fontSize": 12},
                "extraCssText": "max-width:320px;white-space:pre-wrap;",
            },
            "legend": {
                "data": ["document", "section", "annotation", "figure", "table"],
                "orient": "horizontal",
                "top": 10,
            },
            "series": [
                {
                    "type": "graph",
                    "layout": "force",
                    "data": nodes_data,
                    "links": links_data,
                    "categories": categories,
                    "roam": True,
                    "draggable": True,
                    "force": {
                        "repulsion": 250,
                        "gravity": 0.08,
                        "edgeLength": [60, 180],
                    },
                    "emphasis": {
                        "focus": "adjacency",
                        "lineStyle": {"width": 4},
                    },
                }
            ],
        }
    
    def to_document_graph_option(self) -> Dict[str, Any]:
        """生成文献关系图配置"""
        if not self.documents:
            return {}
        
        nodes_data = []
        for doc in self.documents.values():
            node_count = len([n for n in self.tree_nodes.values() if n.doc_id == doc.id])
            nodes_data.append({
                "id": doc.id,
                "name": doc.title[:20] + ("..." if len(doc.title) > 20 else ""),
                "symbolSize": 30 + node_count * 3,
                "category": 0,
                "itemStyle": {"color": "#48bb78"},
                "label": {"show": True, "fontSize": 11},
            })
        
        links_data = []
        for edge in self.edges:
            if edge.source_id in self.documents and edge.target_id in self.documents:
                links_data.append(edge.to_echarts_link())
        
        return {
            "tooltip": {
                "trigger": "item",
                "formatter": "{c}",
            },
            "series": [
                {
                    "type": "graph",
                    "layout": "force",
                    "data": nodes_data,
                    "links": links_data,
                    "categories": [{"name": "document"}],
                    "roam": True,
                    "draggable": True,
                    "force": {
                        "repulsion": 300,
                        "gravity": 0.1,
                        "edgeLength": [100, 250],
                    },
                    "emphasis": {
                        "focus": "adjacency",
                        "lineStyle": {"width": 5},
                    },
                }
            ],
        }
