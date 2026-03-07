"""
Knowledge Search
================
Search functionality for knowledge tree.

支持三种匹配模式:
- exact: 精确匹配（完整包含）
- fuzzy: 模糊匹配（部分匹配、前缀匹配）
- mixed: 混合模式（精确优先，模糊备选）
"""

from typing import Optional, List, Tuple
from .tree_model import KnowledgeTree, KnowledgeNode


def search_nodes(
    tree: KnowledgeTree,
    query: str,
    mode: str = "mixed",
    min_fuzzy_score: float = 0.3,
) -> List[KnowledgeNode]:
    """Search for nodes matching query.

    Searches in: label, content, tags, annotation, translation

    Args:
        tree: Knowledge tree to search
        query: Search query string
        mode: Search mode ('exact', 'fuzzy', 'mixed')
        min_fuzzy_score: 模糊匹配最低分数阈值 (0-1)

    Returns:
        List of matching nodes (with fuzzy match score in node._search_score)
    """
    if not query or not query.strip():
        return []

    query = query.lower().strip()
    query_len = len(query)
    
    # 分词（支持中英文）
    tokens = _tokenize(query)
    
    results = []  # [(node, score, match_type)]

    for node in tree.nodes.values():
        score, match_type = _calculate_node_match(node, query, tokens)
        
        if score > 0:
            # 精确匹配
            if match_type == "exact":
                results.append((node, score + 1.0, "exact"))  # 精确匹配加分
            # 模糊匹配
            elif mode in ("fuzzy", "mixed") and score >= min_fuzzy_score:
                results.append((node, score * 0.6, "fuzzy"))  # 模糊匹配降权

    # 去重（保留最高分）
    node_scores = {}
    for node, score, match_type in results:
        if node.id not in node_scores or node_scores[node.id][1] < score:
            node_scores[node.id] = (node, score, match_type)
    
    # 排序：精确匹配优先，然后按分数排序
    sorted_results = sorted(
        node_scores.values(),
        key=lambda x: (0 if x[2] == "exact" else 1, -x[1], -x[0].weight)
    )
    
    # 返回节点列表
    return [item[0] for item in sorted_results]


def _tokenize(text: str) -> List[str]:
    """
    分词：支持中英文混合
    
    Args:
        text: 待分词文本
        
    Returns:
        分词列表
    """
    import re
    
    # 英文单词
    english_words = re.findall(r'[a-zA-Z]+', text.lower())
    
    # 中文字符（单字和双字组合）
    chinese_chars = re.findall(r'[\u4e00-\u9fff]+', text)
    chinese_ngrams = []
    for seq in chinese_chars:
        # 单字
        chinese_ngrams.extend(list(seq))
        # 双字组合
        for i in range(len(seq) - 1):
            chinese_ngrams.append(seq[i:i+2])
    
    return list(set(english_words + chinese_ngrams))


def _calculate_node_match(
    node: KnowledgeNode,
    query: str,
    tokens: List[str]
) -> Tuple[float, str]:
    """
    计算节点与查询的匹配分数
    
    Args:
        node: 知识节点
        query: 查询词
        tokens: 分词列表
        
    Returns:
        (分数, 匹配类型) - 匹配类型: 'exact' 或 'fuzzy'
    """
    query_len = len(query)
    best_score = 0.0
    match_type = "none"
    
    # 搜索字段列表 (字段, 权重)
    fields = [
        (node.label, 2.0),
        (node.content, 1.0),
        (" ".join(node.tags), 1.5),
        (node.metadata.get("annotation", ""), 1.2),
        (node.metadata.get("translation", ""), 1.2),
        (node.metadata.get("category", ""), 1.3),
    ]
    
    for field_text, weight in fields:
        if not field_text:
            continue
            
        field_lower = field_text.lower()
        
        # 1. 精确匹配（完整包含）
        if query in field_lower:
            return 1.0 * weight, "exact"
        
        # 2. Token 匹配
        token_match_count = 0
        for token in tokens:
            if token in field_lower:
                token_match_count += 1
        
        if token_match_count > 0:
            token_score = token_match_count / len(tokens) * weight
            if token_score > best_score:
                best_score = token_score
                match_type = "fuzzy"
        
        # 3. 部分匹配（前缀、后缀、子串）
        # 检查查询的前缀是否匹配
        for prefix_len in range(min(4, query_len), query_len // 2, -1):
            prefix = query[:prefix_len]
            if prefix in field_lower:
                partial_score = prefix_len / query_len * weight * 0.8
                if partial_score > best_score:
                    best_score = partial_score
                    match_type = "fuzzy"
                break
        
        # 检查字段中是否有词以查询开头
        words = field_lower.split()
        for word in words:
            if word.startswith(query):
                prefix_score = 0.9 * weight
                if prefix_score > best_score:
                    best_score = prefix_score
                    match_type = "fuzzy"
                break
            
            # 检查查询是否是词的前缀
            if query_len >= 3 and word.startswith(query[:min(4, query_len)]):
                prefix_score = min(4, query_len) / query_len * weight * 0.7
                if prefix_score > best_score:
                    best_score = prefix_score
                    match_type = "fuzzy"
    
    return best_score, match_type


def filter_by_type(
    tree: KnowledgeTree,
    node_type: str,
) -> List[KnowledgeNode]:
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
) -> List[KnowledgeNode]:
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
) -> List[KnowledgeNode]:
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
) -> List[Tuple[KnowledgeNode, str]]:
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
