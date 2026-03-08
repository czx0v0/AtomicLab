"""
Citation Extractor Service
==========================
引用关系提取服务 - 从文献中提取引用关系

Features:
- 多格式引用解析（IEEE/APA/GB/T 7714）
- CrossRef/Semantic Scholar/OpenAlex API集成
- 引用关系图谱构建
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
import re
import hashlib
import time
import os

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


@dataclass
class Citation:
    """引用文献数据结构"""

    citation_id: str  # 引用ID
    raw_text: str  # 原始引用文本

    # 解析后的字段
    authors: List[str] = field(default_factory=list)
    title: str = ""
    journal: str = ""
    year: Optional[int] = None
    volume: str = ""
    issue: str = ""
    pages: str = ""
    doi: str = ""

    # 元数据
    citation_type: str = "journal"  # journal/conference/book/thesis
    format: str = "unknown"  # IEEE/APA/GB/T7714
    confidence: float = 0.0

    # 外部API补充的信息
    abstract: str = ""
    citation_count: int = 0
    source_api: str = ""  # crossref/semantic_scholar/openalex

    def to_dict(self) -> dict:
        return {
            "citation_id": self.citation_id,
            "raw_text": self.raw_text,
            "authors": self.authors,
            "title": self.title,
            "journal": self.journal,
            "year": self.year,
            "doi": self.doi,
            "citation_type": self.citation_type,
            "format": self.format,
            "confidence": self.confidence,
            "citation_count": self.citation_count,
            "source_api": self.source_api,
        }

    def to_search_query(self) -> str:
        """生成搜索查询字符串"""
        parts = []
        if self.title:
            parts.append(self.title)
        if self.authors:
            parts.append(self.authors[0])
        if self.year:
            parts.append(str(self.year))
        return " ".join(parts)


@dataclass
class CitationExtractionResult:
    """引用提取结果"""

    doc_id: str
    citations: List[Citation]
    reference_section_found: bool
    extraction_time_ms: float
    total_citations: int
    parsed_citations: int

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "total_citations": self.total_citations,
            "parsed_citations": self.parsed_citations,
            "reference_section_found": self.reference_section_found,
            "extraction_time_ms": self.extraction_time_ms,
            "citations": [c.to_dict() for c in self.citations],
        }


class CitationExtractor:
    """引用文献提取器

    支持的引用格式：
    - IEEE: [1] Author, Title, Journal, Year.
    - APA: Author (Year). Title. Journal.
    - GB/T 7714: [序号] 作者. 题名[J]. 刊名, 年, 卷(期): 页码.
    """

    # IEEE格式: [1] Author, Title, Journal, Year.
    IEEE_PATTERN = re.compile(r"\[(\d+)\]\s+([^,]+),\s+([^,]+),\s+([^,]+),\s+(\d{4})")

    # APA格式: Author (Year). Title. Journal.
    APA_PATTERN = re.compile(
        r"([A-Z][a-z]+(?:,?\s+[A-Z][a-z]+)*)\s+\((\d{4})\)\.\s+([^\.]+)\.\s+([^,]+)"
    )

    # GB/T 7714格式: [序号] 作者. 题名[J]. 刊名, 年, 卷(期): 页码.
    GB_PATTERN = re.compile(
        r"\[(\d+)\]\s+([^\.]+)\.\s+([^\[]+)\[J\]\.\s+([^,]+),\s+(\d{4})"
    )

    # 参考文献章节标识
    REFERENCE_HEADERS = [
        "references",
        "bibliography",
        "参考文献",
        "引用文献",
        "reference",
    ]

    def __init__(
        self,
        enable_crossref: bool = True,
        enable_semantic_scholar: bool = False,
        enable_openalex: bool = False,
        cache_dir: str = "storage/citations",
    ):
        """初始化引用提取器

        Args:
            enable_crossref: 启用CrossRef API
            enable_semantic_scholar: 启用Semantic Scholar API
            enable_openalex: 启用OpenAlex API
            cache_dir: 缓存目录
        """
        self.enable_crossref = enable_crossref and REQUESTS_AVAILABLE
        self.enable_semantic_scholar = enable_semantic_scholar and REQUESTS_AVAILABLE
        self.enable_openalex = enable_openalex and REQUESTS_AVAILABLE
        self.cache_dir = cache_dir
        self.cache: Dict[str, Citation] = {}

        # API配置
        self.crossref_url = "https://api.crossref.org/works"
        self.semantic_scholar_url = "https://api.semanticscholar.org/graph/v1"
        self.openalex_url = "https://api.openalex.org"

        # 创建缓存目录
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

    def extract_from_text(
        self,
        text: str,
        doc_id: str = "",
    ) -> CitationExtractionResult:
        """从文本中提取引用

        Args:
            text: 文档文本（Markdown或纯文本）
            doc_id: 文档ID

        Returns:
            CitationExtractionResult: 提取结果
        """
        start_time = time.time()

        # 1. 定位参考文献部分
        ref_section, ref_found = self._find_reference_section(text)

        # 2. 提取引用条目
        raw_citations = self._extract_raw_citations(ref_section)

        # 3. 解析每个引用
        citations = []
        for i, raw in enumerate(raw_citations):
            citation = self._parse_citation(raw, f"{doc_id}_cite_{i}")
            if citation and citation.title:
                citations.append(citation)

        # 4. 通过API补充元数据（可选）
        if self.enable_crossref or self.enable_semantic_scholar:
            citations = self._enrich_citations(citations)

        extraction_time = (time.time() - start_time) * 1000

        return CitationExtractionResult(
            doc_id=doc_id,
            citations=citations,
            reference_section_found=ref_found,
            extraction_time_ms=extraction_time,
            total_citations=len(raw_citations),
            parsed_citations=len(citations),
        )

    def _find_reference_section(self, text: str) -> Tuple[str, bool]:
        """定位参考文献部分"""
        lines = text.split("\n")
        ref_start = -1
        ref_end = len(lines)

        # 查找参考文献标题
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            for header in self.REFERENCE_HEADERS:
                if header in line_lower and len(line_lower) < 30:
                    ref_start = i
                    break
            if ref_start >= 0:
                break

        if ref_start < 0:
            return "", False

        # 查找参考文献结束位置（下一个标题或文档末尾）
        for i in range(ref_start + 1, len(lines)):
            line = lines[i].strip()
            # 遇到新的一级标题，认为参考文献部分结束
            if line.startswith("# ") and "reference" not in line.lower():
                ref_end = i
                break

        ref_text = "\n".join(lines[ref_start:ref_end])
        return ref_text, True

    def _extract_raw_citations(self, ref_section: str) -> List[str]:
        """提取原始引用条目"""
        if not ref_section:
            return []

        # 按换行分割，合并多行引用
        lines = ref_section.split("\n")
        citations = []
        current_citation = ""

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检测新引用开始（以数字或方括号开头）
            is_new_citation = bool(
                re.match(r"^\[\d+\]", line)  # [1] 格式
                or re.match(r"^\d+\.", line)  # 1. 格式
                or re.match(r"^[A-Z][a-z]+,", line)  # Author, 格式
            )

            if is_new_citation and current_citation:
                citations.append(current_citation.strip())
                current_citation = line
            else:
                current_citation += " " + line

        # 添加最后一个引用
        if current_citation.strip():
            citations.append(current_citation.strip())

        return citations

    def _parse_citation(self, raw_text: str, citation_id: str) -> Optional[Citation]:
        """解析单个引用"""

        # 尝试IEEE格式
        match = self.IEEE_PATTERN.search(raw_text)
        if match:
            return Citation(
                citation_id=citation_id,
                raw_text=raw_text,
                authors=[match.group(2).strip()],
                title=match.group(3).strip(),
                journal=match.group(4).strip(),
                year=int(match.group(5)),
                format="IEEE",
                confidence=0.85,
            )

        # 尝试APA格式
        match = self.APA_PATTERN.search(raw_text)
        if match:
            return Citation(
                citation_id=citation_id,
                raw_text=raw_text,
                authors=[match.group(1).strip()],
                title=match.group(3).strip(),
                journal=match.group(4).strip(),
                year=int(match.group(2)),
                format="APA",
                confidence=0.80,
            )

        # 尝试GB/T 7714格式
        match = self.GB_PATTERN.search(raw_text)
        if match:
            return Citation(
                citation_id=citation_id,
                raw_text=raw_text,
                authors=[match.group(2).strip()],
                title=match.group(3).strip(),
                journal=match.group(4).strip(),
                year=int(match.group(5)),
                format="GB/T7714",
                confidence=0.85,
            )

        # 无法解析，返回基础信息
        # 尝试提取年份
        year_match = re.search(r"\b(19|20)\d{2}\b", raw_text)
        year = int(year_match.group()) if year_match else None

        return Citation(
            citation_id=citation_id,
            raw_text=raw_text,
            year=year,
            format="unknown",
            confidence=0.3,
        )

    def _enrich_citations(self, citations: List[Citation]) -> List[Citation]:
        """通过外部API补充引用信息"""
        enriched = []

        for citation in citations:
            if citation.confidence < 0.5 and citation.title:
                # 尝试CrossRef
                if self.enable_crossref:
                    citation = self._enrich_from_crossref(citation)

                # 如果CrossRef失败，尝试Semantic Scholar
                if citation.confidence < 0.7 and self.enable_semantic_scholar:
                    citation = self._enrich_from_semantic_scholar(citation)

            enriched.append(citation)

        return enriched

    def _enrich_from_crossref(self, citation: Citation) -> Citation:
        """从CrossRef API补充信息"""
        if not REQUESTS_AVAILABLE:
            return citation

        try:
            params = {
                "query": citation.to_search_query(),
                "rows": 1,
            }

            response = requests.get(
                self.crossref_url,
                params=params,
                timeout=5,
            )

            if response.ok:
                data = response.json()
                items = data.get("message", {}).get("items", [])

                if items:
                    item = items[0]

                    if not citation.doi:
                        citation.doi = item.get("DOI", "")
                    if not citation.journal:
                        citation.journal = item.get("container-title", [""])[0]
                    if not citation.year:
                        published = item.get("published-print", {})
                        date_parts = published.get("date-parts", [[None]])
                        citation.year = date_parts[0][0] if date_parts else None
                    if not citation.title:
                        titles = item.get("title", [])
                        citation.title = titles[0] if titles else ""

                    citation.citation_count = item.get("is-referenced-by-count", 0)
                    citation.source_api = "crossref"
                    citation.confidence = min(citation.confidence + 0.3, 1.0)

        except Exception as e:
            print(f"[CitationExtractor] CrossRef查询失败: {e}")

        return citation

    def _enrich_from_semantic_scholar(self, citation: Citation) -> Citation:
        """从Semantic Scholar API补充信息"""
        if not REQUESTS_AVAILABLE:
            return citation

        try:
            # 搜索论文
            search_url = f"{self.semantic_scholar_url}/paper/search"
            params = {
                "query": citation.to_search_query(),
                "limit": 1,
                "fields": "title,authors,year,abstract,citationCount",
            }

            response = requests.get(search_url, params=params, timeout=5)

            if response.ok:
                data = response.json()
                papers = data.get("data", [])

                if papers:
                    paper = papers[0]

                    if not citation.title:
                        citation.title = paper.get("title", "")
                    if not citation.year:
                        citation.year = paper.get("year")
                    if not citation.abstract:
                        citation.abstract = paper.get("abstract", "")[:500]

                    citation.citation_count = paper.get("citationCount", 0)
                    citation.source_api = "semantic_scholar"
                    citation.confidence = min(citation.confidence + 0.2, 1.0)

        except Exception as e:
            print(f"[CitationExtractor] Semantic Scholar查询失败: {e}")

        return citation

    def build_citation_graph(
        self,
        extractions: List[CitationExtractionResult],
    ) -> Dict[str, List[str]]:
        """构建引用关系图

        Args:
            extractions: 多个文档的引用提取结果

        Returns:
            Dict[doc_id, List[cited_doi]]: 文档ID到引用DOI列表的映射
        """
        graph = {}

        for extraction in extractions:
            cited_dois = []
            for citation in extraction.citations:
                if citation.doi:
                    cited_dois.append(citation.doi)
                elif citation.title:
                    # 使用标题作为唯一标识
                    title_hash = hashlib.md5(citation.title.encode()).hexdigest()[:12]
                    cited_dois.append(f"title:{title_hash}")

            graph[extraction.doc_id] = cited_dois

        return graph

    def find_co_citations(
        self,
        doc_id: str,
        graph: Dict[str, List[str]],
    ) -> List[str]:
        """查找共引文献（引用了相同文献的其他文档）

        Args:
            doc_id: 当前文档ID
            graph: 引用关系图

        Returns:
            List[doc_id]: 共引文档列表
        """
        if doc_id not in graph:
            return []

        current_refs = set(graph[doc_id])
        co_cited_docs = []

        for other_id, other_refs in graph.items():
            if other_id == doc_id:
                continue

            # 计算共引比例
            common_refs = current_refs & set(other_refs)
            if common_refs:
                similarity = len(common_refs) / max(len(current_refs), 1)
                if similarity >= 0.1:  # 至少10%共引
                    co_cited_docs.append(other_id)

        return co_cited_docs


# 模块级函数（便捷调用）
def extract_citations(text: str, doc_id: str = "") -> CitationExtractionResult:
    """从文本中提取引用（便捷函数）"""
    extractor = CitationExtractor()
    return extractor.extract_from_text(text, doc_id)


if __name__ == "__main__":
    # 测试代码
    test_text = """
    # References
    
    [1] Vaswani, A., Shazeer, N., Parmar, N., et al., Attention Is All You Need, Advances in Neural Information Processing Systems, 2017.
    
    [2] Devlin, J., Chang, M. W., Lee, K., et al., BERT: Pre-training of Deep Bidirectional Transformers, NAACL, 2019.
    
    [3] Brown, T. B., Mann, B., Ryder, N., et al., Language Models are Few-Shot Learners, NeurIPS, 2020.
    """

    extractor = CitationExtractor(enable_crossref=False)
    result = extractor.extract_from_text(test_text, "test_doc")

    print(f"提取到 {result.parsed_citations} 条引用")
    for citation in result.citations:
        print(f"- [{citation.format}] {citation.title} ({citation.year})")
