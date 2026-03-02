"""
Knowledge Tree Model
====================
Data structures for representing knowledge as a graph/tree.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional
from datetime import datetime
import json

from core.state import next_node_id
from core.config import NODE_COLORS, NODE_SIZES


@dataclass
class Annotation:
    """AI-generated annotation on a knowledge node.
    
    Attributes:
        agent: Agent that created this annotation
        content: Annotation text
        confidence: Confidence score
        ts: Timestamp
    """
    agent: str
    content: str
    confidence: float = 0.8
    ts: str = field(default_factory=lambda: datetime.now().strftime("%H:%M"))


@dataclass
class KnowledgeNode:
    """A node in the knowledge graph.
    
    Attributes:
        id: Unique identifier (NK-XXXX format)
        type: Node type (domain/atom/note/concept)
        label: Short display label
        content: Full content text
        source_pid: Source document ID
        parent_id: Parent node ID (for tree structure)
        children: List of child node IDs
        annotations: AI annotations
        weight: Importance weight (0-1)
        tags: Searchable tags
        ts: Creation timestamp
        metadata: Additional metadata
    """
    id: str
    type: Literal["domain", "atom", "note", "concept"]
    label: str
    content: str = ""
    source_pid: str = ""
    parent_id: Optional[str] = None
    children: list[str] = field(default_factory=list)
    annotations: list[Annotation] = field(default_factory=list)
    weight: float = 0.5
    tags: list[str] = field(default_factory=list)
    ts: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "label": self.label,
            "content": self.content,
            "source_pid": self.source_pid,
            "parent_id": self.parent_id,
            "children": self.children,
            "annotations": [
                {"agent": a.agent, "content": a.content, "confidence": a.confidence, "ts": a.ts}
                for a in self.annotations
            ],
            "weight": self.weight,
            "tags": self.tags,
            "ts": self.ts,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "KnowledgeNode":
        """Create from dictionary."""
        annotations = [
            Annotation(**a) for a in d.get("annotations", [])
        ]
        return cls(
            id=d["id"],
            type=d["type"],
            label=d["label"],
            content=d.get("content", ""),
            source_pid=d.get("source_pid", ""),
            parent_id=d.get("parent_id"),
            children=d.get("children", []),
            annotations=annotations,
            weight=d.get("weight", 0.5),
            tags=d.get("tags", []),
            ts=d.get("ts", ""),
            metadata=d.get("metadata", {}),
        )
    
    def to_echarts_node(self) -> dict:
        """Convert to ECharts node format."""
        return {
            "id": self.id,
            "name": self.label[:20] + ("..." if len(self.label) > 20 else ""),
            "symbolSize": NODE_SIZES.get(self.type, 20) * (0.5 + self.weight),
            "category": self.type,
            "itemStyle": {"color": NODE_COLORS.get(self.type, "#888")},
            "label": {"show": True},
        }


@dataclass
class KnowledgeEdge:
    """An edge connecting two knowledge nodes.
    
    Attributes:
        source: Source node ID
        target: Target node ID
        relation: Relationship type
        weight: Edge weight (affects display)
    """
    source: str
    target: str
    relation: Literal["derives_from", "contradicts", "extends", "references"]
    weight: float = 0.5
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "weight": self.weight,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "KnowledgeEdge":
        """Create from dictionary."""
        return cls(
            source=d["source"],
            target=d["target"],
            relation=d["relation"],
            weight=d.get("weight", 0.5),
        )
    
    def to_echarts_link(self) -> dict:
        """Convert to ECharts link format."""
        line_styles = {
            "derives_from": "solid",
            "contradicts": "dashed",
            "extends": "dotted",
            "references": "solid",
        }
        return {
            "source": self.source,
            "target": self.target,
            "lineStyle": {
                "type": line_styles.get(self.relation, "solid"),
                "width": 1 + self.weight * 2,
                "opacity": 0.6,
            },
        }


class KnowledgeTree:
    """A knowledge graph/tree structure.
    
    Supports both hierarchical (tree) and associative (graph) relationships.
    """
    
    def __init__(self):
        """Initialize empty tree."""
        self.nodes: dict[str, KnowledgeNode] = {}
        self.edges: list[KnowledgeEdge] = []
        self.metadata = {
            "doc_count": 0,
            "node_count": 0,
            "last_updated": None,
        }
    
    def add_node(self, node: KnowledgeNode) -> str:
        """Add a node to the tree.
        
        Args:
            node: Node to add
            
        Returns:
            Node ID
        """
        self.nodes[node.id] = node
        self.metadata["node_count"] = len(self.nodes)
        self.metadata["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        return node.id
    
    def add_edge(self, edge: KnowledgeEdge):
        """Add an edge to the tree.
        
        Args:
            edge: Edge to add
        """
        self.edges.append(edge)
    
    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        """Get a node by ID.
        
        Args:
            node_id: Node identifier
            
        Returns:
            Node or None if not found
        """
        return self.nodes.get(node_id)
    
    def get_children(self, node_id: str) -> list[KnowledgeNode]:
        """Get child nodes.
        
        Args:
            node_id: Parent node ID
            
        Returns:
            List of child nodes
        """
        node = self.nodes.get(node_id)
        if not node:
            return []
        return [self.nodes[cid] for cid in node.children if cid in self.nodes]
    
    def get_connected(self, node_id: str) -> list[tuple[KnowledgeNode, str]]:
        """Get nodes connected via edges.
        
        Args:
            node_id: Node ID
            
        Returns:
            List of (node, relation) tuples
        """
        result = []
        for edge in self.edges:
            if edge.source == node_id and edge.target in self.nodes:
                result.append((self.nodes[edge.target], edge.relation))
            elif edge.target == node_id and edge.source in self.nodes:
                result.append((self.nodes[edge.source], edge.relation))
        return result
    
    def create_domain_node(self, domain: str, source_pid: str = "") -> KnowledgeNode:
        """Create a domain node.
        
        Args:
            domain: Domain name
            source_pid: Optional source document ID
            
        Returns:
            Created node
        """
        node = KnowledgeNode(
            id=next_node_id(),
            type="domain",
            label=domain,
            content=f"学科领域：{domain}",
            source_pid=source_pid,
            weight=1.0,
            tags=[domain],
        )
        self.add_node(node)
        return node
    
    def create_atom_node(
        self, 
        atom: dict, 
        source_pid: str = "",
        parent_id: str = None,
    ) -> KnowledgeNode:
        """Create an atom node from Crusher output.
        
        Args:
            atom: Atom dict with axiom/methodology/boundary
            source_pid: Source document ID
            parent_id: Optional parent (domain) node ID
            
        Returns:
            Created node
        """
        axiom = atom.get("axiom", "")
        node = KnowledgeNode(
            id=next_node_id(),
            type="atom",
            label=axiom[:30] if axiom else "Atom",
            content=axiom,
            source_pid=source_pid,
            parent_id=parent_id,
            weight=0.8,
            tags=[atom.get("domain", "")],
            metadata={
                "methodology": atom.get("methodology", ""),
                "boundary": atom.get("boundary", ""),
                "original_id": atom.get("id", ""),
            }
        )
        self.add_node(node)
        
        # Link to parent
        if parent_id and parent_id in self.nodes:
            self.nodes[parent_id].children.append(node.id)
            self.add_edge(KnowledgeEdge(
                source=parent_id,
                target=node.id,
                relation="derives_from",
            ))
        
        return node
    
    def create_note_node(
        self,
        note: dict,
        parent_id: str = None,
    ) -> KnowledgeNode:
        """Create a note node.
        
        Args:
            note: Note dict
            parent_id: Optional parent node ID
            
        Returns:
            Created node
        """
        content = note.get("content", "")
        node = KnowledgeNode(
            id=next_node_id(),
            type="note",
            label=content[:20] + ("..." if len(content) > 20 else ""),
            content=content,
            source_pid=note.get("source_pid", ""),
            parent_id=parent_id,
            weight=0.4,
            metadata={
                "page": note.get("page", 1),
                "original_id": note.get("id", ""),
            }
        )
        self.add_node(node)
        return node
    
    def to_echarts_option(self, highlight_ids: list[str] = None) -> dict:
        """Convert to ECharts graph option.
        
        Args:
            highlight_ids: Node IDs to highlight
            
        Returns:
            ECharts option dict
        """
        highlight_ids = highlight_ids or []
        
        categories = [
            {"name": "domain"},
            {"name": "atom"},
            {"name": "note"},
            {"name": "concept"},
        ]
        
        nodes_data = []
        for node in self.nodes.values():
            n = node.to_echarts_node()
            if node.id in highlight_ids:
                n["itemStyle"] = {"color": "#f56565", "borderWidth": 3, "borderColor": "#c53030"}
            nodes_data.append(n)
        
        links_data = [edge.to_echarts_link() for edge in self.edges]
        
        return {
            "tooltip": {"trigger": "item"},
            "legend": {
                "data": ["domain", "atom", "note", "concept"],
                "orient": "horizontal",
                "top": 10,
            },
            "series": [{
                "type": "graph",
                "layout": "force",
                "data": nodes_data,
                "links": links_data,
                "categories": categories,
                "roam": True,
                "draggable": True,
                "force": {
                    "repulsion": 200,
                    "gravity": 0.1,
                    "edgeLength": [80, 200],
                },
                "emphasis": {
                    "focus": "adjacency",
                    "lineStyle": {"width": 4},
                },
            }],
        }
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "KnowledgeTree":
        """Deserialize from dictionary."""
        tree = cls()
        for nid, ndata in d.get("nodes", {}).items():
            tree.nodes[nid] = KnowledgeNode.from_dict(ndata)
        for edata in d.get("edges", []):
            tree.edges.append(KnowledgeEdge.from_dict(edata))
        tree.metadata = d.get("metadata", tree.metadata)
        return tree
