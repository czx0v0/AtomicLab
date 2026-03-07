"""
Keyword Search Service
======================
基于 jieba 分词的关键词搜索服务。
使用字段加权匹配，支持中英文混合搜索。
"""

from typing import List, Dict, Optional, Union
import re

try:
    import jieba

    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False

from .search_result import SearchResult


class KeywordSearchService:
    """
    关键词搜索服务

    使用 jieba 分词处理中文，按字段权重累加分数。
    数据量 <100 时直接遍历所有节点。

    字段权重配置:
        title: 10 (文献标题)
        keywords: 8 (关键词)
        heading: 6 (章节标题)
        abstract: 4 (摘要)
        note: 3 (批注内容)
        content: 1 (正文)
    """

    # 字段权重配置
    FIELD_WEIGHTS = {
        "title": 10,
        "keywords": 8,
        "heading": 6,
        "abstract": 4,
        "note": 3,
        "selected_text": 2,
        "content": 1,
        "caption": 2,
        "tags": 5,
    }

    # 查询扩展映射 - 相关术语自动扩展
    QUERY_EXPANSIONS = {
        # 数据库相关
        "sql": ["mysql", "postgresql", "sqlite", "database", "dbms", "query"],
        "mysql": ["sql", "database", "dbms"],
        "database": ["sql", "dbms", "storage", "data"],
        # 编程语言
        "python": ["programming", "code", "script"],
        "java": ["programming", "code", "jvm"],
        # AI/ML
        "ai": ["artificial intelligence", "machine learning", "ml", "deep learning"],
        "machine learning": ["ml", "ai", "deep learning", "neural network"],
        "llm": ["large language model", "gpt", "transformer", "bert"],
        # 生物信息学
        "metabolite": ["metabolism", "compound", "molecule", "mass spectrometry"],
        "mass spectrometry": ["ms", "lc-ms", "gc-ms", "metabolomics"],
    }

    def __init__(self, graph=None, tree=None, lib: Dict = None):
        """
        初始化

        Args:
            graph: KnowledgeGraph 实例（新版）
            tree: KnowledgeTree 实例（兼容旧版）
            lib: 文献库字典（兼容旧版）
        """
        self.graph = graph
        self.tree = tree
        self.lib = lib or {}

        # 初始化 jieba（如果可用）
        if JIEBA_AVAILABLE:
            jieba.initialize()

    def search(
        self,
        query: str,
        top_k: int = 10,
        include_docs: bool = True,
    ) -> List[SearchResult]:
        """
        关键词搜索

        Args:
            query: 搜索词
            top_k: 返回结果数量
            include_docs: 是否包含文献全文搜索

        Returns:
            SearchResult 列表，按相关度排序
        """
        if not query or not query.strip():
            return []

        tokens = self._tokenize(query.strip())
        if not tokens:
            return []

        results: List[SearchResult] = []

        # 搜索新版 KnowledgeGraph
        if self.graph:
            results.extend(self._search_graph(tokens, include_docs, query))

        # 搜索旧版 KnowledgeTree（兼容）
        if self.tree and hasattr(self.tree, "nodes"):
            results.extend(self._search_tree(tokens, query))

        # 搜索文献库原文
        if include_docs and self.lib:
            results.extend(self._search_lib(tokens, query))

        # 去重（按节点 ID）
        seen = set()
        unique_results = []
        for r in results:
            node_id = r.get_node_id()
            if node_id and node_id not in seen:
                seen.add(node_id)
                unique_results.append(r)
            elif not node_id:
                unique_results.append(r)

        # 按分数排序
        unique_results.sort(key=lambda x: x.score, reverse=True)

        return unique_results[:top_k]

    def _tokenize(self, text: str) -> List[str]:
        """
        分词并扩展查询词

        使用 jieba 进行中文分词，同时保留英文单词。
        自动扩展相关术语（如 sql -> mysql, database 等）

        Args:
            text: 待分词文本

        Returns:
            分词结果列表（包含扩展词）
        """
        if JIEBA_AVAILABLE:
            # 使用 jieba 精确模式分词
            words = list(jieba.cut(text, cut_all=False))
            # 过滤停用词和短词
            tokens = [
                w.strip().lower() for w in words if w.strip() and len(w.strip()) > 1
            ]
        else:
            # 简单分词：按空格和标点分割
            tokens = re.split(r'[\s,，。.!！?？;；:：、\'"()（）\[\]【】]+', text)
            tokens = [
                t.strip().lower() for t in tokens if t.strip() and len(t.strip()) > 1
            ]

        # 去重
        tokens = list(set(tokens))

        # 扩展查询词
        expanded = set(tokens)
        for token in tokens:
            if token in self.QUERY_EXPANSIONS:
                expanded.update(self.QUERY_EXPANSIONS[token])

        return list(expanded)

    def _calculate_score(
        self,
        node: any,
        tokens: List[str],
        doc: any = None,
        query: str = "",
    ) -> tuple[float, str]:
        """
        计算节点匹配分数 - 支持精确匹配和模糊匹配

        Args:
            node: 节点对象或字典
            tokens: 分词列表
            doc: 所属文献（可选）
            query: 原始查询词（用于模糊匹配）

        Returns:
            (分数, 最佳匹配字段)
        """
        total_score = 0.0
        best_field = ""
        best_field_score = 0.0

        # 获取节点字段
        fields = self._extract_fields(node)

        # 如果有文献，也提取文献字段
        if doc:
            doc_fields = self._extract_doc_fields(doc)
            fields.update(doc_fields)

        for field_name, field_value in fields.items():
            if not field_value:
                continue

            weight = self.FIELD_WEIGHTS.get(field_name, 1)
            field_text = (
                field_value.lower()
                if isinstance(field_value, str)
                else " ".join(str(v).lower() for v in field_value)
            )

            # 计算匹配分数
            field_score = 0.0
            for token in tokens:
                # 1. 精确匹配（完整包含）
                if token in field_text:
                    field_score += weight
                    # 精确匹配加分
                    if token == field_text or f" {token} " in f" {field_text} ":
                        field_score += weight * 0.5
                
                # 2. 模糊匹配（前缀匹配）
                elif len(token) >= 3:
                    # 检查字段中的词是否以token开头
                    words = field_text.split()
                    for word in words:
                        if word.startswith(token[:min(4, len(token))]):
                            # 前缀匹配，降权
                            field_score += weight * 0.5
                            break
                    
                    # 检查token是否是字段内容的子串（部分匹配）
                    if token[:min(4, len(token))] in field_text:
                        field_score += weight * 0.3

            # 3. 原始查询的部分匹配（针对用户输入不完整的情况）
            if query and len(query) >= 3:
                query_lower = query.lower()
                # 检查查询前缀
                prefix_len = min(4, len(query))
                if query_lower[:prefix_len] in field_text:
                    field_score += weight * 0.4

            total_score += field_score

            if field_score > best_field_score:
                best_field_score = field_score
                best_field = field_name

        return total_score, best_field

    def _extract_fields(self, node: any) -> Dict[str, any]:
        """从节点提取可搜索字段"""
        if hasattr(node, "to_dict"):
            data = node.to_dict()
        elif isinstance(node, dict):
            data = node
        else:
            return {}

        fields = {}

        # TreeNode 字段
        for key in ["content", "heading", "note", "selected_text", "caption", "tags"]:
            if key in data and data[key]:
                fields[key] = data[key]

        # KnowledgeNode 兼容字段
        if "label" in data:
            fields["heading"] = data["label"]

        # metadata 中的字段
        metadata = data.get("metadata", {})
        if "category" in metadata:
            fields["tags"] = fields.get("tags", []) + [metadata["category"]]

        return fields

    def _extract_doc_fields(self, doc: any) -> Dict[str, any]:
        """从文献提取可搜索字段"""
        if hasattr(doc, "to_dict"):
            data = doc.to_dict()
        elif isinstance(doc, dict):
            data = doc
        else:
            return {}

        fields = {}

        if "title" in data and data["title"]:
            fields["title"] = data["title"]
        if "name" in data and data["name"]:  # 兼容旧版
            fields["title"] = data["name"]
        if "keywords" in data and data["keywords"]:
            fields["keywords"] = data["keywords"]
        if "abstract" in data and data["abstract"]:
            fields["abstract"] = data["abstract"]

        return fields

    def _search_graph(
        self, tokens: List[str], include_docs: bool, query: str = ""
    ) -> List[SearchResult]:
        """搜索 KnowledgeGraph"""
        results = []

        # 搜索树节点
        for node in self.graph.get_all_nodes():
            doc = self.graph.get_document(node.doc_id)
            score, matched_field = self._calculate_score(node, tokens, doc, query)

            if score > 0:
                highlight = self._generate_highlight(node, tokens)
                results.append(
                    SearchResult(
                        node=node,
                        doc=doc,
                        score=score,
                        match_type="keyword",
                        matched_field=matched_field,
                        highlight=highlight,
                    )
                )

        # 搜索文献节点
        if include_docs:
            for doc in self.graph.documents.values():
                score, matched_field = self._calculate_score(doc, tokens, query=query)
                if score > 0:
                    results.append(
                        SearchResult(
                            node=doc,
                            doc=doc,
                            score=score,
                            match_type="keyword",
                            matched_field=matched_field,
                        )
                    )

        return results

    def _search_tree(self, tokens: List[str], query: str = "") -> List[SearchResult]:
        """搜索旧版 KnowledgeTree"""
        results = []

        for node in self.tree.nodes.values():
            doc = None
            if node.source_pid:
                doc = self.lib.get(node.source_pid, {})

            score, matched_field = self._calculate_score(node, tokens, doc, query)

            if score > 0:
                highlight = self._generate_highlight(node, tokens)
                results.append(
                    SearchResult(
                        node=node,
                        doc=doc or {},
                        score=score,
                        match_type="keyword",
                        matched_field=matched_field,
                        highlight=highlight,
                    )
                )

        return results

    def _search_lib(self, tokens: List[str], query: str) -> List[SearchResult]:
        """搜索文献库原文"""
        results = []
        q_lower = query.lower()

        for pid, info in self.lib.items():
            doc_text = info.get("text", "")
            doc_name = info.get("name", "?")

            if not doc_text:
                continue

            # 查找匹配位置
            pos = doc_text.lower().find(q_lower)
            if pos >= 0:
                # 生成高亮片段
                start = max(0, pos - 60)
                end = min(len(doc_text), pos + len(query) + 60)
                snippet = doc_text[start:end]

                # 计算文献匹配分数
                score, _ = self._calculate_score(info, tokens)
                score = max(score, 0.5)  # 原文匹配至少有基础分

                results.append(
                    SearchResult(
                        node={"id": f"lib_{pid}", "content": snippet, "type": "text"},
                        doc=info,
                        score=score,
                        match_type="keyword",
                        matched_field="content",
                        highlight=f"...{snippet}...",
                    )
                )

        return results

    def _generate_highlight(self, node: any, tokens: List[str]) -> str:
        """生成高亮片段"""
        content = ""
        if hasattr(node, "content"):
            content = node.content
        elif isinstance(node, dict):
            content = node.get("content", "")

        if not content:
            return ""

        # 查找第一个匹配词的位置
        content_lower = content.lower()
        best_pos = -1
        for token in tokens:
            pos = content_lower.find(token)
            if pos >= 0:
                best_pos = pos
                break

        if best_pos < 0:
            return content[:100] + ("..." if len(content) > 100 else "")

        # 生成上下文片段
        start = max(0, best_pos - 40)
        end = min(len(content), best_pos + 60)
        snippet = content[start:end]

        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(content) else ""

        return f"{prefix}{snippet}{suffix}"
