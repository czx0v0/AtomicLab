"""
Knowledge Search
================
Search functionality for knowledge tree.
"""

from typing import Optional
from .tree_model import KnowledgeTree, KnowledgeNode


def search_nodes(
    tree: KnowledgeTree,
    query: str,
    mode: str = "exact",
) -> list[KnowledgeNode]:
    """Search for nodes matching query.

    Searches in: label, content, tags, annotation, translation

    Args:
        tree: Knowledge tree to search
        query: Search query string
        mode: Search mode ('exact' or 'fuzzy')

    Returns:
        List of matching nodes
    """
    if not query or not query.strip():
        return []

    query = query.lower().strip()
    results = []

    for node in tree.nodes.values():
        # Search in label
        if query in node.label.lower():
            results.append(node)
            continue

        # Search in content
        if query in node.content.lower():
            results.append(node)
            continue

        # Search in tags
        for tag in node.tags:
            if query in tag.lower():
                results.append(node)
                break
        else:
            # Search in metadata (annotation, translation)
            annotation = node.metadata.get("annotation", "")
            translation = node.metadata.get("translation", "")
            if annotation and query in annotation.lower():
                results.append(node)
                continue
            if translation and query in translation.lower():
                results.append(node)
                continue

    # Sort by relevance (weight)
    results.sort(key=lambda n: n.weight, reverse=True)
    return results


def filter_by_type(
    tree: KnowledgeTree,
    node_type: str,
) -> list[KnowledgeNode]:
    """Filter nodes by type.

    Args:
        tree: Knowledge tree
        node_type: Type to filter ('domain', 'document', 'note', 'tag')

    Returns:
        List of nodes matching type
    """
    return [n for n in tree.nodes.values() if n.type == node_type]


def filter_by_domain(
    tree: KnowledgeTree,
    domain: str,
) -> list[KnowledgeNode]:
    """Filter nodes by domain tag.

    Args:
        tree: Knowledge tree
        domain: Domain string

    Returns:
        List of nodes in domain
    """
    domain = domain.lower()
    return [n for n in tree.nodes.values() if any(domain in t.lower() for t in n.tags)]


def get_node_hierarchy(
    tree: KnowledgeTree,
    node_id: str,
) -> list[KnowledgeNode]:
    """Get hierarchy path from root to node.

    Args:
        tree: Knowledge tree
        node_id: Target node ID

    Returns:
        List of nodes from root to target
    """
    node = tree.get_node(node_id)
    if not node:
        return []

    path = [node]
    current = node

    while current.parent_id:
        parent = tree.get_node(current.parent_id)
        if not parent:
            break
        path.insert(0, parent)
        current = parent

    return path


def get_related_nodes(
    tree: KnowledgeTree,
    node_id: str,
    relation: Optional[str] = None,
) -> list[tuple[KnowledgeNode, str]]:
    """Get nodes related via edges.

    Args:
        tree: Knowledge tree
        node_id: Source node ID
        relation: Optional filter by relation type

    Returns:
        List of (node, relation) tuples
    """
    connected = tree.get_connected(node_id)
    if relation:
        connected = [(n, r) for n, r in connected if r == relation]
    return connected
