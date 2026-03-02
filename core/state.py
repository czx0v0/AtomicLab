"""
State Management
================
ID generators and global state utilities.
"""

# ══════════════════════════════════════════════════════════════
# ID Counters (module-level singletons)
# ══════════════════════════════════════════════════════════════
_ATOM_CTR = {"v": 0}
_NOTE_CTR = {"v": 0}
_NODE_CTR = {"v": 0}


def next_atom_id() -> str:
    """Generate next atom ID.

    Returns:
        ID in format 'ATC-0001'
    """
    _ATOM_CTR["v"] += 1
    return f"ATC-{_ATOM_CTR['v']:04d}"


def next_note_id() -> str:
    """Generate next note ID.

    Returns:
        ID in format 'NT-0001'
    """
    _NOTE_CTR["v"] += 1
    return f"NT-{_NOTE_CTR['v']:04d}"


def next_node_id() -> str:
    """Generate next knowledge node ID.

    Returns:
        ID in format 'NK-0001'
    """
    _NODE_CTR["v"] += 1
    return f"NK-{_NODE_CTR['v']:04d}"


def reset_counters():
    """Reset all counters (for testing)."""
    _ATOM_CTR["v"] = 0
    _NOTE_CTR["v"] = 0
    _NODE_CTR["v"] = 0


# ══════════════════════════════════════════════════════════════
# Initial State Factories
# ══════════════════════════════════════════════════════════════
def create_initial_library() -> dict:
    """Create empty library store.

    Returns:
        Empty dict for library_store
    """
    return {}


def create_initial_stats() -> dict:
    """Create initial statistics.

    Returns:
        Stats dict with zero counts
    """
    return {"docs": 0, "atoms": 0, "notes": 0, "nodes": 0}


def create_initial_tree() -> dict:
    """Create empty knowledge tree.

    Returns:
        Empty tree structure
    """
    return {
        "root_id": None,
        "nodes": {},
        "edges": [],
        "metadata": {
            "doc_count": 0,
            "node_count": 0,
            "last_updated": None,
        },
    }
