"""
Knowledge Tree Model
====================
五级联动：Domain -> Document -> Section -> Summary/Note -> Atomic Knowledge.

Tree structure:
    domain (领域，如 AI)
    └── document (论文)
        └── section (章节标题，由 Markdown # 生成)
            └── summary (章节摘要，虚拟节点) / note (原子卡片)
                └── (原子知识点块)
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
    type: Literal["domain", "document", "section", "summary", "note", "atomic"]
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
        t = d.get("type", "note")
        if t == "tag":
            t = "note"
        if t not in ("domain", "document", "section", "summary", "note", "atomic"):
            t = "note"
        return cls(
            id=d["id"],
            type=t,
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
        """Convert to ECharts node format. Atomic 节点使用小方块(symbol=rect)与 Note 圆点区分。"""
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

        page = self.metadata.get("page_start") or self.metadata.get("page")
        node = {
            "id": self.id,
            "name": self.label[:24] + ("..." if len(self.label) > 24 else ""),
            "value": "\n".join(tooltip_lines),
            "symbolSize": size,
            "category": self.type,
            "itemStyle": {"color": color},
            "label": {"show": self.type in ("domain", "document", "section")},
            "source_pid": self.source_pid or "",
            "page": page if page is not None else 1,
        }
        # Atomic Knowledge：小方块样式，与 Note 圆点区分
        if self.type == "atomic":
            node["symbol"] = "rect"
            node["symbolSize"] = [size * 0.9, size * 0.9]
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
    """五级联动: Domain -> Document -> Section -> Summary/Note -> Atomic."""

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

    # ── section ─────────────────────────────────────────────────

    def create_section_node(
        self,
        section_heading: str,
        source_pid: str,
        doc_node_id: str,
        level: int = 2,
        page_start: int = None,
        page_end: int = None,
    ) -> KnowledgeNode:
        """Create a section node under a document.

        Args:
            section_heading: Section heading text
            source_pid: Document PID
            doc_node_id: Parent document node ID
            level: Heading level (1=H1, 2=H2, etc.)
            page_start: Starting page number
            page_end: Ending page number
        """
        node = KnowledgeNode(
            id=next_node_id(),
            type="section",
            label=section_heading[:50],
            content=section_heading,
            source_pid=source_pid,
            parent_id=doc_node_id,
            weight=0.7,
            metadata={
                "level": level,
                "page_start": page_start,
                "page_end": page_end,
            },
        )
        self.add_node(node)
        if doc_node_id:
            self._link_parent_child(doc_node_id, node.id, "contains")
        return node

    def find_section_node(self, doc_node_id: str, section_heading: str) -> Optional[KnowledgeNode]:
        """Find a section node by heading under a specific document."""
        for n in self.nodes.values():
            if (
                n.type == "section"
                and n.parent_id == doc_node_id
                and section_heading.lower() in n.label.lower()
            ):
                return n
        return None

    def get_sections_by_page(self, doc_node_id: str, page: int) -> Optional[KnowledgeNode]:
        """Find the section node that contains a given page."""
        for n in self.nodes.values():
            if n.type == "section" and n.parent_id == doc_node_id:
                start = n.metadata.get("page_start", 0)
                end = n.metadata.get("page_end", 9999)
                if start and end and start <= page <= end:
                    return n
        return None

    def _reparent_note_to_section(
        self, note_node_id: str, new_section_id: str
    ) -> None:
        """将笔记节点从当前父节点移动到指定 section 下（更新 parent_id、children、edges）。"""
        note = self.nodes.get(note_node_id)
        if not note or note.type != "note":
            return
        old_parent_id = note.parent_id
        if old_parent_id == new_section_id:
            return
        old_parent = self.nodes.get(old_parent_id)
        if old_parent and note_node_id in old_parent.children:
            old_parent.children.remove(note_node_id)
        self.edges[:] = [
            e
            for e in self.edges
            if not (e.source == old_parent_id and e.target == note_node_id)
        ]
        note.parent_id = new_section_id
        new_parent = self.nodes.get(new_section_id)
        if new_parent and note_node_id not in new_parent.children:
            new_parent.children.append(note_node_id)
        self.add_edge(
            KnowledgeEdge(source=new_section_id, target=note_node_id, relation="contains")
        )

    def bind_notes_to_sections_heuristic(self, doc_node_id: str) -> int:
        """
        将直接挂在 document 下的 note 软绑定到最相关的 section 下（Document -> Section -> Note）。
        启发式：优先按页码归属（note.page 落在 section 的 page_start~page_end），
        其次按文本包含（note.content 与 section.label/content 重叠）。
        返回被重新挂载的 note 数量。
        """
        doc = self.nodes.get(doc_node_id)
        if not doc or doc.type != "document":
            return 0
        sections = [
            n
            for n in self.nodes.values()
            if n.type == "section" and n.parent_id == doc_node_id
        ]
        notes_direct = [
            n
            for n in self.nodes.values()
            if n.type == "note" and n.parent_id == doc_node_id
        ]
        if not sections or not notes_direct:
            return 0
        moved = 0
        for note in notes_direct:
            page = note.metadata.get("page") or note.metadata.get("page_start") or 1
            if not isinstance(page, int):
                try:
                    page = int(page)
                except (TypeError, ValueError):
                    page = 1
            best = self.get_sections_by_page(doc_node_id, page)
            if not best:
                for sec in sections:
                    if note.content and sec.content and (
                        (note.content[:50] in sec.content or sec.label in note.content)
                    ):
                        best = sec
                        break
            if not best:
                for sec in sections:
                    s = sec.metadata.get("page_start", 0) or 0
                    e = sec.metadata.get("page_end", 9999) or 9999
                    if s <= page <= e:
                        best = sec
                        break
            if best:
                self._reparent_note_to_section(note.id, best.id)
                moved += 1
        return moved

    def find_note_by_original_id(self, original_id: str) -> "KnowledgeNode":
        """Find a note node by its original note ID (from notes_st).

        Args:
            original_id: The original note ID (e.g., NT-XXXX)

        Returns:
            KnowledgeNode if found, None otherwise
        """
        for n in self.nodes.values():
            if n.type == "note" and n.metadata.get("original_id") == original_id:
                return n
        return None

    # ── note ───────────────────────────────────────────────────

    def create_note_node(
        self,
        note: dict,
        category: str = "其他",
        doc_node_id: str = None,
        section_node_id: str = None,
    ) -> KnowledgeNode:
        """Create a note node under a document or section.

        Args:
            note: Original note dict {id, content, page, annotation, translation, ...}
            category: AI classification (方法/公式/图像/定义/观点/数据/其他)
            doc_node_id: Parent document node ID (used if no section)
            section_node_id: Parent section node ID (preferred if provided)
        """
        content = note.get("content", "")
        
        # Prefer section as parent if provided, otherwise use document
        parent_id = section_node_id if section_node_id else doc_node_id
        
        node = KnowledgeNode(
            id=next_node_id(),
            type="note",
            label=content[:20] + ("..." if len(content) > 20 else ""),
            content=content,
            source_pid=note.get("source_pid", ""),
            parent_id=parent_id,
            weight=0.6,
            metadata={
                "page": note.get("page", 1),
                "category": category,
                "original_id": note.get("id", ""),
                "annotation": note.get("annotation", ""),
                "translation": note.get("translation", ""),
                "color": note.get("color", ""),
            },
        )
        self.add_node(node)
        if parent_id:
            self._link_parent_child(parent_id, node.id, "contains")
        return node

    # ── summary（章节摘要，虚拟节点）────────────────────────────

    def create_summary_node(
        self,
        section_node_id: str,
        title: str = "本章摘要",
        content: str = "",
        source_pid: str = "",
    ) -> KnowledgeNode:
        """在 Section 下创建 Summary 节点，用于挂载该章节下的所有 Note。"""
        section = self.nodes.get(section_node_id)
        if not section or section.type != "section":
            raise ValueError("section_node_id 必须指向 section 节点")
        node = KnowledgeNode(
            id=next_node_id(),
            type="summary",
            label=title[:50],
            content=content,
            source_pid=source_pid or section.source_pid,
            parent_id=section_node_id,
            weight=0.65,
            metadata={"virtual": True},
        )
        self.add_node(node)
        self._link_parent_child(section_node_id, node.id, "contains")
        return node

    # ── atomic（原子知识，挂在 Note 下）────────────────────────────

    def create_atomic_knowledge_node(
        self,
        note_node_id: str,
        label: str,
        content: str = "",
        category: str = "Insight",
        source_pid: str = "",
        metadata: dict = None,
    ) -> KnowledgeNode:
        """在 Note 下创建 Atomic Knowledge 节点（公理/边界/方法论等解构卡片）。"""
        note = self.nodes.get(note_node_id)
        if not note or note.type != "note":
            raise ValueError("note_node_id 必须指向 note 节点")
        meta = dict(metadata or {})
        meta.setdefault("category", category)
        node = KnowledgeNode(
            id=next_node_id(),
            type="atomic",
            label=label[:80],
            content=content,
            source_pid=source_pid or note.source_pid,
            parent_id=note_node_id,
            weight=0.6,
            metadata=meta,
        )
        self.add_node(node)
        self._link_parent_child(note_node_id, node.id, "contains")
        return node

    def ensure_section_summary_heuristic(self, doc_node_id: str) -> int:
        """
        为每个 Section 若无 Summary 子节点则创建虚拟 Summary，并将该 Section 下所有直接 Note 挂到 Summary 下。
        形成 Section -> Summary -> Notes 闭环。返回创建的 Summary 数量。
        """
        doc = self.nodes.get(doc_node_id)
        if not doc or doc.type != "document":
            return 0
        sections = [
            n
            for n in self.nodes.values()
            if n.type == "section" and n.parent_id == doc_node_id
        ]
        created = 0
        for sec in sections:
            children = self.get_children(sec.id)
            has_summary = any(c.type == "summary" for c in children)
            notes_direct = [c for c in children if c.type == "note"]
            if not has_summary and notes_direct:
                summary_node = self.create_summary_node(
                    sec.id,
                    title=sec.label or "本章摘要",
                    content=sec.metadata.get("summary", "") or "",
                    source_pid=sec.source_pid,
                )
                created += 1
                for note in notes_direct:
                    self._reparent_note_to_section(note.id, summary_node.id)
            elif has_summary and notes_direct:
                summary_node = next(c for c in children if c.type == "summary")
                for note in notes_direct:
                    self._reparent_note_to_section(note.id, summary_node.id)
        return created

    def create_tag_node(self, tag_text: str, note_node_id: str = None) -> Optional["KnowledgeNode"]:
        """已剔除 Tag 层级：不再创建 tag 节点，仅将标签写入 note 的 metadata.tags。保留接口兼容。"""
        if not note_node_id or not tag_text:
            return None
        note = self.nodes.get(note_node_id)
        if note and note.type == "note":
            if "tags" not in note.metadata:
                note.metadata["tags"] = []
            if tag_text not in note.metadata["tags"]:
                note.metadata["tags"].append(tag_text)
            if tag_text not in note.tags:
                note.tags.append(tag_text)
        return None

    # ── ECharts serialization ──────────────────────────────────

    def to_echarts_option(self, highlight_ids: list[str] = None) -> dict:
        highlight_ids = highlight_ids or []
        # 五级联动：先绑定 Note 到 Section，再为 Section 补 Summary 并挂载 Note -> Summary
        for n in list(self.nodes.values()):
            if n.type == "document":
                self.bind_notes_to_sections_heuristic(n.id)
                self.ensure_section_summary_heuristic(n.id)

        categories = [
            {"name": "domain"},
            {"name": "document"},
            {"name": "section"},
            {"name": "summary"},
            {"name": "note"},
            {"name": "atomic"},
        ]

        valid_types = ("domain", "document", "section", "summary", "note", "atomic")
        valid_ids = {n.id for n in self.nodes.values() if n.type in valid_types}
        nodes_data = [
            node.to_echarts_node(highlight=node.id in highlight_ids)
            for node in self.nodes.values()
            if node.type in valid_types
        ]
        links_data = [
            edge.to_echarts_link()
            for edge in self.edges
            if edge.source in valid_ids and edge.target in valid_ids
        ]

        return {
            "tooltip": {
                "trigger": "item",
                "formatter": "{c}",
                "textStyle": {"fontSize": 12},
                "extraCssText": "max-width:320px;white-space:pre-wrap;",
            },
            "legend": {
                "data": ["domain", "document", "section", "summary", "note", "atomic"],
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
                "source_pid": node.source_pid,
                "ts": node.ts,
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

        Documents are connected by cross-references (Tag 层级已剔除，不再按标签连边).
        """
        doc_nodes = [n for n in self.nodes.values() if n.type == "document"]
        if not doc_nodes:
            return {}

        # Build nodes
        nodes_data = []
        for dn in doc_nodes:
            note_count = sum(
                1 for c in self.get_children(dn.id) if c.type in ("note", "section", "summary")
            )
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

        links_data = []
        # Cross-reference edges between documents
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
