"""
Knowledge Tree Model
====================
Data structures for document -> note -> tag hierarchical knowledge graph.

Tree structure:
    domain (学科领域)
    └── document (文献)
        └── note (笔记, with category: 方法/公式/图像/定义/观点/数据/其他)
            └── tag (AI 标签关键词)
"""

from dataclasses import dataclass, field
from typing import Literal, Optional
from datetime import datetime
import json

from core.state import next_node_id
from core.config import NODE_COLORS, NODE_SIZES, CATEGORY_COLORS


@dataclass
class KnowledgeNode:
    """A node in the knowledge graph.

    Attributes:
        id: Unique identifier (NK-XXXX format)
        type: Node type (domain/document/note/tag)
        label: Short display label
        content: Full content text
        source_pid: Source document ID
        parent_id: Parent node ID (for tree structure)
        children: List of child node IDs
        weight: Importance weight (0-1)
        tags: Searchable tags
        ts: Creation timestamp
        metadata: Additional metadata (category, comment, etc.)
    """

    id: str
    type: Literal["domain", "document", "note", "tag"]
    label: str
    content: str = ""
    source_pid: str = ""
    parent_id: Optional[str] = None
    children: list[str] = field(default_factory=list)
    weight: float = 0.5
    tags: list[str] = field(default_factory=list)
    ts: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "label": self.label,
            "content": self.content,
            "source_pid": self.source_pid,
            "parent_id": self.parent_id,
            "children": self.children,
            "weight": self.weight,
            "tags": self.tags,
            "ts": self.ts,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "KnowledgeNode":
        return cls(
            id=d["id"],
            type=d["type"],
            label=d["label"],
            content=d.get("content", ""),
            source_pid=d.get("source_pid", ""),
            parent_id=d.get("parent_id"),
            children=d.get("children", []),
            weight=d.get("weight", 0.5),
            tags=d.get("tags", []),
            ts=d.get("ts", ""),
            metadata=d.get("metadata", {}),
        )

    def to_echarts_node(self, highlight: bool = False) -> dict:
        """Convert to ECharts node format."""
        color = NODE_COLORS.get(self.type, "#888")
        # Notes get category-specific color
        if self.type == "note":
            cat = self.metadata.get("category", "")
            color = CATEGORY_COLORS.get(cat, color)

        size = NODE_SIZES.get(self.type, 20) * (0.5 + self.weight)
        # Tooltip content: type + full content preview
        tooltip_lines = [f"[{self.type}] {self.label}"]
        if self.content and self.content != self.label:
            tooltip_lines.append(self.content[:120])
        if self.tags:
            tooltip_lines.append("标签: " + ", ".join(self.tags[:5]))
        cat = self.metadata.get("category", "")
        if cat:
            tooltip_lines.append(f"分类: {cat}")

        node = {
            "id": self.id,
            "name": self.label[:24] + ("..." if len(self.label) > 24 else ""),
            "value": "\n".join(tooltip_lines),
            "symbolSize": size,
            "category": self.type,
            "itemStyle": {"color": color},
            "label": {"show": self.type in ("domain", "document")},
        }
        if highlight:
            node["itemStyle"] = {
                "color": "#f56565",
                "borderWidth": 3,
                "borderColor": "#c53030",
            }
            node["label"]["show"] = True
        return node


@dataclass
class KnowledgeEdge:
    """An edge connecting two knowledge nodes.

    Attributes:
        source: Source node ID
        target: Target node ID
        relation: Relationship type (contains / tagged_with / references)
        weight: Edge weight
    """

    source: str
    target: str
    relation: Literal["contains", "tagged_with", "references"]
    weight: float = 0.5

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "weight": self.weight,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "KnowledgeEdge":
        return cls(
            source=d["source"],
            target=d["target"],
            relation=d["relation"],
            weight=d.get("weight", 0.5),
        )

    def to_echarts_link(self) -> dict:
        line_styles = {
            "contains": "solid",
            "tagged_with": "dashed",
            "references": "dotted",
        }
        return {
            "source": self.source,
            "target": self.target,
            "lineStyle": {
                "type": line_styles.get(self.relation, "solid"),
                "width": 1 + self.weight * 2,
                "opacity": 0.5,
            },
        }


class KnowledgeTree:
    """Hierarchical knowledge tree: domain -> document -> note -> tag."""

    def __init__(self):
        self.nodes: dict[str, KnowledgeNode] = {}
        self.edges: list[KnowledgeEdge] = []

    # ── node creation helpers ──────────────────────────────────

    def add_node(self, node: KnowledgeNode) -> str:
        self.nodes[node.id] = node
        return node.id

    def add_edge(self, edge: KnowledgeEdge):
        self.edges.append(edge)

    def _link_parent_child(self, parent_id: str, child_id: str, relation: str):
        """Create parent-child link + edge."""
        parent = self.nodes.get(parent_id)
        if parent:
            parent.children.append(child_id)
        self.add_edge(
            KnowledgeEdge(
                source=parent_id,
                target=child_id,
                relation=relation,
            )
        )

    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        return self.nodes.get(node_id)

    def get_children(self, node_id: str) -> list[KnowledgeNode]:
        node = self.nodes.get(node_id)
        if not node:
            return []
        return [self.nodes[cid] for cid in node.children if cid in self.nodes]

    def get_connected(self, node_id: str) -> list[tuple[KnowledgeNode, str]]:
        """Get all nodes connected to *node_id* via edges (both directions).

        Returns:
            List of (connected_node, relation) tuples.
        """
        results: list[tuple[KnowledgeNode, str]] = []
        for edge in self.edges:
            if edge.source == node_id:
                tgt = self.nodes.get(edge.target)
                if tgt:
                    results.append((tgt, edge.relation))
            elif edge.target == node_id:
                src = self.nodes.get(edge.source)
                if src:
                    results.append((src, edge.relation))
        return results

    # ── domain ─────────────────────────────────────────────────

    def create_domain_node(self, domain: str, source_pid: str = "") -> KnowledgeNode:
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

    def find_domain_node(self, domain: str) -> Optional[KnowledgeNode]:
        for n in self.nodes.values():
            if n.type == "domain" and domain in n.label:
                return n
        return None

    # ── document ───────────────────────────────────────────────

    def create_document_node(
        self,
        doc_name: str,
        source_pid: str,
        domain_node_id: str = None,
    ) -> KnowledgeNode:
        """Create a document node under a domain."""
        node = KnowledgeNode(
            id=next_node_id(),
            type="document",
            label=doc_name[:30],
            content=doc_name,
            source_pid=source_pid,
            parent_id=domain_node_id,
            weight=0.8,
            tags=[],
        )
        self.add_node(node)
        if domain_node_id:
            self._link_parent_child(domain_node_id, node.id, "contains")
        return node

    def find_document_node(self, source_pid: str) -> Optional[KnowledgeNode]:
        for n in self.nodes.values():
            if n.type == "document" and n.source_pid == source_pid:
                return n
        return None

    # ── note ───────────────────────────────────────────────────

    def create_note_node(
        self,
        note: dict,
        category: str = "其他",
        doc_node_id: str = None,
    ) -> KnowledgeNode:
        """Create a note node under a document.

        Args:
            note: Original note dict {id, content, page, ...}
            category: AI classification (方法/公式/图像/定义/观点/数据/其他)
            doc_node_id: Parent document node ID
        """
        content = note.get("content", "")
        node = KnowledgeNode(
            id=next_node_id(),
            type="note",
            label=content[:20] + ("..." if len(content) > 20 else ""),
            content=content,
            source_pid=note.get("source_pid", ""),
            parent_id=doc_node_id,
            weight=0.6,
            metadata={
                "page": note.get("page", 1),
                "category": category,
                "original_id": note.get("id", ""),
            },
        )
        self.add_node(node)
        if doc_node_id:
            self._link_parent_child(doc_node_id, node.id, "contains")
        return node

    # ── tag ────────────────────────────────────────────────────

    def create_tag_node(self, tag_text: str, note_node_id: str = None) -> KnowledgeNode:
        """Create a tag node under a note."""
        node = KnowledgeNode(
            id=next_node_id(),
            type="tag",
            label=tag_text,
            content=tag_text,
            parent_id=note_node_id,
            weight=0.3,
            tags=[tag_text],
        )
        self.add_node(node)
        if note_node_id:
            self._link_parent_child(note_node_id, node.id, "tagged_with")
        return node

    # ── ECharts serialization ──────────────────────────────────

    def to_echarts_option(self, highlight_ids: list[str] = None) -> dict:
        highlight_ids = highlight_ids or []

        categories = [
            {"name": "domain"},
            {"name": "document"},
            {"name": "note"},
            {"name": "tag"},
        ]

        nodes_data = [
            node.to_echarts_node(highlight=node.id in highlight_ids)
            for node in self.nodes.values()
        ]
        links_data = [edge.to_echarts_link() for edge in self.edges]

        return {
            "tooltip": {
                "trigger": "item",
                "formatter": "{c}",
                "textStyle": {"fontSize": 12},
                "extraCssText": "max-width:320px;white-space:pre-wrap;",
            },
            "legend": {
                "data": ["domain", "document", "note", "tag"],
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

    # ── tree view helpers (for write tab sidebar) ──────────────

    def build_tree_data(self) -> list[dict]:
        """Build hierarchical tree data for rendering.

        Returns list of root-level dicts, each with nested 'children'.
        """
        roots = [n for n in self.nodes.values() if n.parent_id is None]
        roots.sort(key=lambda n: n.ts)

        def _build(node: KnowledgeNode) -> dict:
            children = self.get_children(node.id)
            children.sort(key=lambda c: c.ts)
            return {
                "id": node.id,
                "type": node.type,
                "label": node.label,
                "content": node.content,
                "metadata": node.metadata,
                "tags": node.tags,
                "children": [_build(c) for c in children],
            }

        return [_build(r) for r in roots]

    # ── ECharts tree layout (for write tab) ──────────────────────

    def to_echarts_tree_option(self) -> dict:
        """Generate ECharts option for tree layout visualization.

        Returns orthogonal LR tree with expandable nodes, suitable for
        the Write tab sidebar.
        """
        roots = [n for n in self.nodes.values() if n.parent_id is None]
        roots.sort(key=lambda n: n.ts)

        def _convert(node: KnowledgeNode) -> dict:
            color = NODE_COLORS.get(node.type, "#888")
            if node.type == "note":
                cat = node.metadata.get("category", "")
                color = CATEGORY_COLORS.get(cat, color)

            children = self.get_children(node.id)
            children.sort(key=lambda c: c.ts)

            return {
                "name": node.label[:24] + ("..." if len(node.label) > 24 else ""),
                "value": node.content,
                "itemStyle": {"color": color},
                "children": [_convert(c) for c in children],
            }

        if len(roots) == 1:
            tree_data = [_convert(roots[0])]
        elif len(roots) > 1:
            tree_data = [
                {
                    "name": "Knowledge Base",
                    "value": "",
                    "itemStyle": {"color": "#5b8def"},
                    "children": [_convert(r) for r in roots],
                }
            ]
        else:
            return {}

        return {
            "tooltip": {
                "trigger": "item",
                "formatter": "{b}<br/>{c}",
            },
            "series": [
                {
                    "type": "tree",
                    "layout": "orthogonal",
                    "orient": "LR",
                    "roam": True,
                    "expandAndCollapse": True,
                    "initialTreeDepth": 3,
                    "data": tree_data,
                    "label": {
                        "show": True,
                        "fontSize": 11,
                        "position": "right",
                        "verticalAlign": "middle",
                    },
                    "leaves": {
                        "label": {"position": "right", "verticalAlign": "middle"},
                    },
                    "animationDurationUpdate": 750,
                }
            ],
        }

    # ── cross-document references (from Synthesizer) ────────────

    def add_cross_reference(self, node_id_a: str, node_id_b: str):
        """Add a cross-document reference edge between two nodes."""
        if node_id_a in self.nodes and node_id_b in self.nodes:
            self.add_edge(
                KnowledgeEdge(
                    source=node_id_a,
                    target=node_id_b,
                    relation="references",
                    weight=0.6,
                )
            )

    # ── Document relation graph (paper-level) ──────────────────

    def to_document_graph_option(self) -> dict:
        """Generate ECharts option showing only document-level relationships.

        Documents are connected when they share tags or have cross-references.
        """
        doc_nodes = [n for n in self.nodes.values() if n.type == "document"]
        if not doc_nodes:
            return {}

        # Collect tags per document
        doc_tags: dict[str, set[str]] = {}
        for dn in doc_nodes:
            tags = set()
            for child in self.get_children(dn.id):
                if child.type == "note":
                    for tag_child in self.get_children(child.id):
                        if tag_child.type == "tag":
                            tags.add(tag_child.label.lower())
            doc_tags[dn.id] = tags

        # Build nodes
        nodes_data = []
        for dn in doc_nodes:
            tag_count = len(doc_tags.get(dn.id, set()))
            note_count = sum(1 for c in self.get_children(dn.id) if c.type == "note")
            nodes_data.append(
                {
                    "id": dn.id,
                    "name": dn.label[:20] + ("..." if len(dn.label) > 20 else ""),
                    "symbolSize": 30 + note_count * 5,
                    "category": 0,
                    "itemStyle": {"color": "#48bb78"},
                    "label": {"show": True, "fontSize": 11},
                }
            )

        # Build edges: shared tags
        links_data = []
        doc_list = list(doc_tags.keys())
        for i in range(len(doc_list)):
            for j in range(i + 1, len(doc_list)):
                shared = doc_tags[doc_list[i]] & doc_tags[doc_list[j]]
                if shared:
                    links_data.append(
                        {
                            "source": doc_list[i],
                            "target": doc_list[j],
                            "lineStyle": {
                                "width": 1 + len(shared) * 1.5,
                                "opacity": 0.6,
                                "type": "solid",
                            },
                        }
                    )

        # Also include explicit cross-reference edges between documents
        for edge in self.edges:
            if edge.relation == "references":
                src = self.nodes.get(edge.source)
                tgt = self.nodes.get(edge.target)
                if src and tgt and src.type == "document" and tgt.type == "document":
                    links_data.append(
                        {
                            "source": edge.source,
                            "target": edge.target,
                            "lineStyle": {"width": 3, "opacity": 0.8, "type": "dashed"},
                        }
                    )

        return {
            "tooltip": {
                "trigger": "item",
                "formatter": "{c}",
                "textStyle": {"fontSize": 12},
                "extraCssText": "max-width:320px;white-space:pre-wrap;",
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

    # ── serialization ──────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "KnowledgeTree":
        tree = cls()
        for nid, ndata in d.get("nodes", {}).items():
            tree.nodes[nid] = KnowledgeNode.from_dict(ndata)
        for edata in d.get("edges", []):
            tree.edges.append(KnowledgeEdge.from_dict(edata))
        return tree
