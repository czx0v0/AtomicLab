#!/usr/bin/env python
"""
Build SFT dataset for ms-swift via a full Teacher-Student distillation workflow.

Pipeline:
1) Search and download arXiv PDFs with mandatory download interval (>= 3 seconds).
2) Parse PDFs to Markdown via local MinerU CLI (magic-pdf).
3) Split Markdown into sections and call teacher LLM to extract AtomicNote JSON.
4) Enforce schema constraints (knowledge_type/page_num/bbox).
5) Convert to ShareGPT JSONL and append to data/train.jsonl.

Usage example:
python scripts/build_sft_dataset.py \
  --keywords "Retrieval Augmented Generation" "Knowledge Graph" \
  --max-papers 50 \
  --teacher-model deepseek-ai/DeepSeek-V3.2

Note: When redirecting output to a file, use:
  python scripts/build_sft_dataset.py ... > logs/output.log 2>&1
to capture both stdout and stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from dataclasses import field

try:
    import requests
except Exception as e:  # pragma: no cover - runtime dependency guard
    raise RuntimeError(
        "Missing dependency 'requests'. Install it with: pip install requests"
    ) from e

try:
    from tenacity import (
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )
except Exception as e:  # pragma: no cover - runtime dependency guard
    raise RuntimeError(
        "Missing dependency 'tenacity'. Install it with: pip install tenacity"
    ) from e


# Ensure project root is importable so we can reuse core.config
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency guard
    load_dotenv = None

try:
    import arxiv
except Exception as e:  # pragma: no cover - runtime dependency guard
    raise RuntimeError(
        "Missing dependency 'arxiv'. Install it with: pip install arxiv"
    ) from e

try:
    from openai import OpenAI
except Exception as e:  # pragma: no cover - runtime dependency guard
    raise RuntimeError(
        "Missing dependency 'openai'. Install it with: pip install openai"
    ) from e


if load_dotenv:
    load_dotenv()

# Reuse project config when available; otherwise fall back to env defaults.
try:
    from core.config import API_BASE, MS_KEY, FALLBACK_MODELS
except Exception:
    API_BASE = os.environ.get("API_BASE", "https://api-inference.modelscope.cn/v1")
    MS_KEY = os.environ.get("MS_KEY", "")
    raw_fallbacks = os.environ.get(
        "FALLBACK_MODELS",
        "deepseek-ai/DeepSeek-V3.2,Qwen/Qwen3-235B-A22B,Qwen/Qwen3-32B",
    )
    FALLBACK_MODELS = [m.strip() for m in raw_fallbacks.split(",") if m.strip()]

# DeepSeek API support (alternative to ModelScope for users with DeepSeek credits)
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_BASE = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com")
SEMANTIC_SCHOLAR_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")


ALLOWED_KNOWLEDGE_TYPES = {"方法", "公式", "图像", "定义", "观点", "数据", "其他"}
DEFAULT_KEYWORDS = ["Retrieval Augmented Generation", "Knowledge Graph"]
DEFAULT_TEACHER_MODEL = "deepseek-ai/DeepSeek-V3.2"
DEFAULT_DEEPSEEK_MODELS = ["deepseek-chat", "deepseek-reasoner"]
SYSTEM_PROMPT = (
    "你是学术结构化提取专家。"
    "你必须输出严格 json 格式。"
    "请将给定章节文本提炼为 AtomicNote，并以 JSON 对象输出。"
    "输出必须是一个包含 notes 键的 json 对象，不要输出任何额外说明。"
    '当章节没有可提取价值时，返回 {"notes": []}，不要报错。'
)

USER_PROMPT_TEMPLATE = """
请基于以下章节内容与 MinerU 证据，提取 AtomicNote。

严格要求：
1) 输出必须是 JSON 对象，不允许输出 JSON 数组。
2) 你只能输出以下结构：
    {{"notes": [{{...}}, {{...}}]}}
3) notes 数组中的每个元素必须包含字段：
   - knowledge_type: 必须是 {allowed_types} 之一
   - title: 字符串
   - content: 字符串
   - page_num: 整数（必须来自 MinerU 证据）
   - bbox: [x1, y1, x2, y2] 数字数组（必须来自 MinerU 证据）
   - bibtex_citation: 字符串（当前论文的 BibTeX 引用格式，见下方）
4) 不允许新增知识类型。
5) page_num 与 bbox 必须精准引用证据中的值，禁止编造。
6) bibtex_citation 必须使用下方提供的真实引用信息，不可编造。
7) 如果章节没有可用证据，或属于无价值段落（如纯标题、目录、版权声明），返回 {{"notes": []}}。

文档信息：
- arxiv_id: {arxiv_id}
- title: {title}
- section: {section_title}

当前论文 BibTeX 引用（所有笔记的 bibtex_citation 字段都应填入此值）：
{bibtex}

当前论文引用的核心文献（供参考，可在 content 中提及）：
{citations_info}

章节文本：
{section_text}

MinerU证据（可引用的 page_num/bbox 候选）：
{evidence_json}
""".strip()


@dataclass
class PaperRecord:
    arxiv_id: str
    title: str
    pdf_url: str
    published: str
    keywords: List[str]
    bibtex: str = ""  # BibTeX citation from Semantic Scholar
    citations: List[Dict[str, str]] = field(default_factory=list)  # Referenced papers


@dataclass
class SectionChunk:
    title: str
    text: str
    order: int


def log(msg: str) -> None:
    print(f"[build_sft_dataset] {msg}", flush=True)


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", name)
    return cleaned.strip("_")[:180] or "paper"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build ShareGPT SFT dataset from arXiv papers"
    )
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=DEFAULT_KEYWORDS,
        help="Search keywords used on arXiv",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=50,
        help="Maximum number of unique papers to download",
    )
    parser.add_argument(
        "--per-query",
        type=int,
        default=80,
        help="Max arXiv results fetched per keyword before dedup",
    )
    parser.add_argument(
        "--download-interval",
        type=float,
        default=3.0,
        help="Sleep interval (seconds) between each arXiv download, enforced >= 3",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "raw" / "arxiv_pdf",
        help="Directory to store downloaded PDFs",
    )
    parser.add_argument(
        "--parse-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "raw" / "mineru_out",
        help="Directory for MinerU output",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=PROJECT_ROOT / "data" / "train.jsonl",
        help="ShareGPT JSONL output path",
    )
    parser.add_argument(
        "--teacher-model",
        type=str,
        default=None,
        help="Teacher model id (supports comma-separated fallback list)",
    )
    parser.add_argument(
        "--max-sections-per-paper",
        type=int,
        default=20,
        help="Safety cap for number of sections processed per paper",
    )
    parser.add_argument(
        "--max-section-chars",
        type=int,
        default=12000,
        help="Max characters sent to teacher for one section",
    )
    parser.add_argument(
        "--teacher-timeout",
        type=int,
        default=120,
        help="Teacher API timeout in seconds",
    )
    parser.add_argument(
        "--teacher-retries",
        type=int,
        default=3,
        help="Teacher API retries per section",
    )
    parser.add_argument(
        "--mineru-bin",
        type=str,
        default=os.environ.get("MINERU_BIN", "magic-pdf"),
        help="MinerU CLI executable (default: magic-pdf)",
    )
    parser.add_argument(
        "--mineru-method",
        type=str,
        default="auto",
        choices=["auto", "txt", "ocr"],
        help="MinerU parse method",
    )
    parser.add_argument(
        "--mineru-timeout",
        type=int,
        default=900,
        help="MinerU subprocess timeout per PDF in seconds",
    )
    parser.add_argument(
        "--use-deepseek",
        action="store_true",
        help="Use DeepSeek API instead of ModelScope (requires DEEPSEEK_API_KEY in .env)",
    )
    parser.add_argument(
        "--enable-semantic-scholar",
        action="store_true",
        help="Fetch BibTeX and citation metadata from Semantic Scholar API",
    )
    parser.add_argument(
        "--test-split-ratio",
        type=float,
        default=0.0,
        help="Test split ratio (0.0-0.5). If > 0, writes test records to separate file",
    )
    return parser.parse_args()


def search_arxiv_papers(
    keywords: Sequence[str], max_papers: int, per_query: int
) -> List[PaperRecord]:
    seen_ids: set[str] = set()
    records: List[PaperRecord] = []
    search_retries = 4

    for kw in keywords:
        query = f'all:"{kw}"'
        search = arxiv.Search(
            query=query,
            max_results=per_query,
            sort_by=arxiv.SortCriterion.Relevance,
            sort_order=arxiv.SortOrder.Descending,
        )

        log(f"Searching arXiv for keyword: {kw}")
        last_error: Optional[Exception] = None

        for attempt in range(1, search_retries + 1):
            # Recreate client each retry to avoid stale/broken connections.
            client = arxiv.Client(page_size=50, delay_seconds=3.0, num_retries=3)
            try:
                for result in client.results(search):
                    pid = result.get_short_id()
                    if pid in seen_ids:
                        continue
                    seen_ids.add(pid)

                    records.append(
                        PaperRecord(
                            arxiv_id=pid,
                            title=result.title.replace("\n", " ").strip(),
                            pdf_url=result.pdf_url or "",
                            published=str(getattr(result, "published", "")),
                            keywords=[kw],
                        )
                    )
                    if len(records) >= max_papers:
                        break

                # Success for current keyword.
                last_error = None
                break
            except Exception as e:
                last_error = e
                wait_sec = min(2**attempt, 12)
                log(
                    f"Search error for '{kw}' (attempt {attempt}/{search_retries}): {e}"
                )
                if attempt < search_retries:
                    log(f"Retrying arXiv search in {wait_sec}s...")
                    time.sleep(wait_sec)

        if last_error is not None:
            log(f"Search failed for '{kw}' after {search_retries} attempts; continue")

        if len(records) >= max_papers:
            break

    return records[:max_papers]


class TransientSemanticScholarError(RuntimeError):
    """Retryable API errors, e.g. 429/503 and transient 5xx."""


class SemanticScholarClient:
    """Robust Semantic Scholar batch client.

    Features:
    - Optional x-api-key injection via SEMANTIC_SCHOLAR_API_KEY
    - Tenacity exponential backoff retry for 429/503/5xx
    - Batch POST endpoint usage
    - 1.2s rate limiting between requests to stay <= 1 RPS
    """

    BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"

    def __init__(self, api_key: str = "", timeout_sec: int = 20, batch_size: int = 20):
        self.api_key = (api_key or "").strip()
        self.timeout_sec = timeout_sec
        self.batch_size = max(1, min(batch_size, 500))
        self.session = requests.Session()

    @staticmethod
    def _normalize_arxiv_id(arxiv_id: str) -> str:
        # Strip arXiv version suffix (e.g. 2411.18583v1 -> 2411.18583)
        return re.sub(r"v\d+$", "", (arxiv_id or "").strip(), flags=re.IGNORECASE)

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": "AtomicLab-Dataset-Builder/1.0",
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def _build_ids(self, papers: Sequence[PaperRecord]) -> List[str]:
        # Use ARXIV:<id> so we can directly map each paper in batch mode.
        return [f"ARXIV:{self._normalize_arxiv_id(p.arxiv_id)}" for p in papers]

    @retry(
        wait=wait_exponential(min=2, max=20),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(TransientSemanticScholarError),
        reraise=True,
    )
    def _post_batch(self, ids: Sequence[str]) -> List[Dict[str, Any]]:
        resp = self.session.post(
            self.BASE_URL,
            params={
                "fields": "citationStyles,citations,references,title,year,externalIds"
            },
            json={"ids": list(ids)},
            headers=self._build_headers(),
            timeout=self.timeout_sec,
        )

        if resp.status_code in (429, 503):
            raise TransientSemanticScholarError(
                f"Semantic Scholar transient error {resp.status_code}: {resp.text[:200]}"
            )

        if 500 <= resp.status_code < 600:
            raise TransientSemanticScholarError(
                f"Semantic Scholar server error {resp.status_code}: {resp.text[:200]}"
            )

        if resp.status_code >= 400:
            raise RuntimeError(
                f"Semantic Scholar non-retryable error {resp.status_code}: {resp.text[:300]}"
            )

        payload = resp.json()
        if not isinstance(payload, list):
            raise RuntimeError("Unexpected Semantic Scholar batch response format")
        return payload

    @staticmethod
    def _extract_citations(
        item: Dict[str, Any], top_k: int = 15
    ) -> List[Dict[str, str]]:
        refs = item.get("references") or []
        citations: List[Dict[str, str]] = []
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            # Compatible with multiple response layouts
            title = ref.get("title")
            year = ref.get("year")
            if not title and isinstance(ref.get("citedPaper"), dict):
                title = ref["citedPaper"].get("title")
                year = ref["citedPaper"].get("year", year)
            if title:
                citations.append({"title": str(title), "year": str(year or "N/A")})
            if len(citations) >= top_k:
                break
        return citations

    def enrich_papers(self, papers: Sequence[PaperRecord]) -> int:
        if not papers:
            return 0

        if not self.api_key:
            log(
                "Semantic Scholar API key not set (SEMANTIC_SCHOLAR_API_KEY). Using unauthenticated mode."
            )

        success_count = 0
        total = len(papers)
        for start in range(0, total, self.batch_size):
            end = min(start + self.batch_size, total)
            chunk = list(papers[start:end])
            ids = self._build_ids(chunk)

            log(f"Semantic Scholar batch {start + 1}-{end}/{total}, size={len(ids)}")
            try:
                rows = self._post_batch(ids)
            except Exception as e:
                log(f"  ✗ Batch failed: {e}")
                # Continue with next batch rather than stopping the full pipeline.
                if end < total:
                    time.sleep(1.2)
                continue

            # Rows are aligned with ids order in batch response.
            for idx, paper in enumerate(chunk):
                item = rows[idx] if idx < len(rows) else None
                if not isinstance(item, dict) or not item:
                    continue

                citation_styles = item.get("citationStyles") or {}
                paper.bibtex = (
                    citation_styles.get("bibtex", "")
                    if isinstance(citation_styles, dict)
                    else ""
                )
                paper.citations = self._extract_citations(item, top_k=15)
                success_count += 1

            # Strict throttle: keep <= 1 request per second.
            if end < total:
                time.sleep(1.2)

        return success_count


def download_paper_pdf(
    paper: PaperRecord,
    raw_dir: Path,
    download_interval: float,
) -> Optional[Path]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{safe_filename(paper.arxiv_id)}__{safe_filename(paper.title)}.pdf"
    pdf_path = raw_dir / filename

    if pdf_path.exists() and pdf_path.stat().st_size > 0:
        log(f"PDF exists, skip download: {pdf_path.name}")
        time.sleep(max(3.0, download_interval))
        return pdf_path

    url = paper.pdf_url
    if not url:
        log(f"No PDF URL for {paper.arxiv_id}, skip")
        return None

    import urllib.request

    try:
        log(f"Downloading {paper.arxiv_id} from {url}")
        with urllib.request.urlopen(url, timeout=60) as resp:
            data = resp.read()
        if not data:
            log(f"Empty PDF data for {paper.arxiv_id}")
            return None
        pdf_path.write_bytes(data)
        log(f"Downloaded: {pdf_path.name} ({len(data)} bytes)")
        return pdf_path
    except Exception as e:
        log(f"Download failed for {paper.arxiv_id}: {e}")
        return None
    finally:
        # arXiv policy guard: mandatory delay to reduce request pressure.
        delay = max(3.0, float(download_interval))
        log(f"Sleeping {delay:.1f}s to respect arXiv rate policy")
        time.sleep(delay)


def run_mineru(
    pdf_path: Path,
    parse_dir: Path,
    mineru_bin: str,
    mineru_method: str,
    timeout_sec: int,
) -> Optional[Path]:
    parse_dir.mkdir(parents=True, exist_ok=True)
    out_dir = parse_dir / pdf_path.stem

    # Reuse parsed output if markdown already exists.
    md_exists = list(out_dir.rglob("*.md")) if out_dir.exists() else []
    if md_exists:
        log(f"MinerU output exists, reuse: {out_dir}")
        return out_dir

    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        mineru_bin,
        "-p",
        str(pdf_path),
        "-o",
        str(out_dir),
        "-m",
        mineru_method,
    ]

    log(f"Running MinerU: {' '.join(cmd)}")
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            check=False,
        )
        if proc.returncode != 0:
            log(f"MinerU failed ({proc.returncode}) for {pdf_path.name}")
            if proc.stdout:
                log(proc.stdout[-1200:])
            return None

        md_files = list(out_dir.rglob("*.md"))
        if not md_files:
            log(f"MinerU produced no markdown for {pdf_path.name}")
            return None
        return out_dir
    except subprocess.TimeoutExpired:
        log(f"MinerU timeout for {pdf_path.name}")
        return None
    except FileNotFoundError:
        log(f"MinerU executable not found: {mineru_bin}")
        return None
    except Exception as e:
        log(f"MinerU error for {pdf_path.name}: {e}")
        return None


def pick_primary_markdown(parse_out_dir: Path) -> Optional[Path]:
    md_files = list(parse_out_dir.rglob("*.md"))
    if not md_files:
        return None
    md_files.sort(key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)
    return md_files[0]


def load_mineru_evidence(
    parse_out_dir: Path, max_items: int = 400, debug: bool = False
) -> List[Dict[str, Any]]:
    """Extract text+page_num+bbox candidates from MinerU json outputs.

    This function is intentionally permissive because MinerU output formats vary by version.
    """
    candidates: List[Dict[str, Any]] = []

    json_files = [
        p
        for p in parse_out_dir.rglob("*.json")
        if any(k in p.name.lower() for k in ("middle", "content", "model"))
    ]

    if debug:
        log(
            f"  load_mineru_evidence: Found {len(json_files)} JSON files: {[jf.name for jf in json_files]}"
        )

    for jf in json_files:
        try:
            obj = json.loads(jf.read_text(encoding="utf-8", errors="replace"))
        except Exception as e:
            if debug:
                log(f"  Failed to parse {jf.name}: {e}")
            continue

        scanned_nodes = 0
        nodes_with_text = 0
        nodes_with_page = 0
        nodes_with_bbox = 0
        nodes_added = 0

        def collect_text(node: Any) -> str:
            """Recursively collect all text/content from a node and its children."""
            texts = []

            if isinstance(node, dict):
                # Direct text field
                txt = node.get("text") or node.get("content") or node.get("raw_text")
                if txt and isinstance(txt, str):
                    texts.append(txt.strip())

                # Recurse into children
                for v in node.values():
                    if isinstance(v, (dict, list)):
                        child_text = collect_text(v)
                        if child_text:
                            texts.append(child_text)
            elif isinstance(node, list):
                for item in node:
                    child_text = collect_text(item)
                    if child_text:
                        texts.append(child_text)

            return " ".join(texts)

        def walk(
            node: Any,
            inherited_page: Optional[int] = None,
            parent_key: Optional[str] = None,
        ) -> None:
            nonlocal scanned_nodes, nodes_with_text, nodes_with_page, nodes_with_bbox, nodes_added

            if isinstance(node, dict):
                scanned_nodes += 1
                page = node.get("page_num", node.get("page", node.get("page_idx")))
                if page is None:
                    page = inherited_page

                if page is not None:
                    nodes_with_page += 1

                bbox = node.get("bbox")
                if bbox is None:
                    # Common alternatives in layout outputs
                    poly = node.get("poly") or node.get("position") or node.get("box")
                    if isinstance(poly, list) and len(poly) >= 4:
                        # Convert potential polygon to bounding rect.
                        nums = [float(x) for x in poly if isinstance(x, (int, float))]
                        if len(nums) >= 4:
                            xs = nums[0::2]
                            ys = nums[1::2]
                            if xs and ys:
                                bbox = [min(xs), min(ys), max(xs), max(ys)]

                if bbox is not None:
                    nodes_with_bbox += 1

                # If this node has both page and bbox, collect all text from it and children
                if page is not None and isinstance(bbox, list) and len(bbox) >= 4:
                    txt = collect_text(node)

                    if txt:
                        nodes_with_text += 1

                        try:
                            page_num = int(page)
                            box4 = [
                                float(bbox[0]),
                                float(bbox[1]),
                                float(bbox[2]),
                                float(bbox[3]),
                            ]
                        except Exception:
                            page_num = None
                            box4 = None

                        if page_num is not None and box4 is not None:
                            nodes_added += 1
                            candidates.append(
                                {
                                    "text": str(txt)[:600],
                                    "page_num": page_num,
                                    "bbox": box4,
                                    "source": jf.name,
                                }
                            )
                            # Don't recurse into children since we already collected their text
                            return

                # Recurse into children
                for k, v in node.items():
                    walk(v, inherited_page=page, parent_key=k)
            elif isinstance(node, list):
                for idx, item in enumerate(node):
                    next_page = inherited_page
                    # MinerU middle.json often stores per-page data under pdf_info list
                    # where page number is represented by list index.
                    if parent_key == "pdf_info" and inherited_page is None:
                        next_page = idx
                    walk(item, inherited_page=next_page, parent_key=parent_key)

        walk(obj)

        if debug:
            log(
                f"  {jf.name}: scanned={scanned_nodes}, text={nodes_with_text}, page={nodes_with_page}, bbox={nodes_with_bbox}, added={nodes_added}"
            )

    # Deduplicate by page+bbox+prefix text
    dedup: Dict[Tuple[int, str, str], Dict[str, Any]] = {}
    for c in candidates:
        key = (
            c["page_num"],
            json.dumps(c["bbox"], ensure_ascii=False),
            c["text"][:100],
        )
        dedup[key] = c

    unique = list(dedup.values())
    unique.sort(key=lambda x: (x["page_num"], len(x.get("text", ""))), reverse=False)

    if debug:
        log(
            f"  load_mineru_evidence: {len(candidates)} raw candidates -> {len(unique)} unique items (returning {min(len(unique), max_items)})"
        )

    return unique[:max_items]


def split_markdown_sections(md_text: str) -> List[SectionChunk]:
    lines = md_text.splitlines()
    sections: List[SectionChunk] = []

    cur_title = "Introduction"
    cur_buf: List[str] = []
    order = 0

    heading_re = re.compile(r"^(#{1,2})\s+(.+?)\s*$")

    for line in lines:
        m = heading_re.match(line)
        if m:
            if cur_buf:
                txt = "\n".join(cur_buf).strip()
                if txt:
                    sections.append(
                        SectionChunk(title=cur_title, text=txt, order=order)
                    )
                    order += 1
            cur_title = m.group(2).strip()
            cur_buf = []
        else:
            cur_buf.append(line)

    if cur_buf:
        txt = "\n".join(cur_buf).strip()
        if txt:
            sections.append(SectionChunk(title=cur_title, text=txt, order=order))

    return sections


def select_section_evidence(
    section_text: str, evidence: List[Dict[str, Any]], k: int = 40
) -> List[Dict[str, Any]]:
    words = set(re.findall(r"[A-Za-z]{3,}|[\u4e00-\u9fff]{2,}", section_text.lower()))
    if not words:
        return evidence[:k]

    scored: List[Tuple[int, Dict[str, Any]]] = []
    for ev in evidence:
        t = ev.get("text", "").lower()
        score = sum(1 for w in words if w in t)
        scored.append((score, ev))

    scored.sort(key=lambda x: x[0], reverse=True)
    picked = [ev for s, ev in scored if s > 0][:k]
    if len(picked) < min(8, k):
        picked.extend(evidence[: max(0, k - len(picked))])
    return picked[:k]


def extract_json_array(text: str) -> List[Any]:
    if not text:
        return []

    cleaned = text.strip()

    # Remove fenced code block wrappers if present.
    fenced = re.match(
        r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL | re.IGNORECASE
    )
    if fenced:
        cleaned = fenced.group(1).strip()

    try:
        obj = json.loads(cleaned)
        return obj if isinstance(obj, list) else []
    except Exception:
        pass

    # Fallback: first array-like region
    m = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if not m:
        return []

    frag = m.group(0)
    try:
        obj = json.loads(frag)
        return obj if isinstance(obj, list) else []
    except Exception:
        return []


def clean_json_string(text: str) -> str:
    """Clean model output and keep only the JSON object body.

    DeepSeek responses may contain <think>...</think> or markdown wrappers.
    We keep content between the first '{' and the last '}'.
    """
    if not text:
        return "{}"

    cleaned = text.strip()

    # Remove optional reasoning tags.
    cleaned = re.sub(
        r"<think>.*?</think>", "", cleaned, flags=re.DOTALL | re.IGNORECASE
    )

    # Remove fenced markdown block wrappers if present.
    fenced = re.match(
        r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL | re.IGNORECASE
    )
    if fenced:
        cleaned = fenced.group(1).strip()

    # If model returns bare empty list, normalize to expected object schema.
    if cleaned == "[]":
        return '{"notes": []}'

    first = cleaned.find("{")
    last = cleaned.rfind("}")
    if first == -1 or last == -1 or first > last:
        return "{}"

    return cleaned[first : last + 1]


def validate_atomic_notes(
    items: Iterable[Any], debug: bool = False
) -> List[Dict[str, Any]]:
    valid: List[Dict[str, Any]] = []
    rejected_reasons: Dict[str, int] = {}

    for it in items:
        if not isinstance(it, dict):
            rejected_reasons["not_dict"] = rejected_reasons.get("not_dict", 0) + 1
            continue

        ktype = str(it.get("knowledge_type", "")).strip()
        title = str(it.get("title", "")).strip()
        content = str(it.get("content", "")).strip()
        page_num = it.get("page_num")
        bbox = it.get("bbox")
        bibtex_citation = str(it.get("bibtex_citation", "")).strip()

        if ktype not in ALLOWED_KNOWLEDGE_TYPES:
            rejected_reasons["invalid_knowledge_type"] = (
                rejected_reasons.get("invalid_knowledge_type", 0) + 1
            )
            continue
        if not title or not content:
            rejected_reasons["missing_title_or_content"] = (
                rejected_reasons.get("missing_title_or_content", 0) + 1
            )
            continue
        if page_num is None:
            rejected_reasons["missing_page_num"] = (
                rejected_reasons.get("missing_page_num", 0) + 1
            )
            continue

        try:
            page_num = int(page_num)
        except Exception:
            rejected_reasons["invalid_page_num_format"] = (
                rejected_reasons.get("invalid_page_num_format", 0) + 1
            )
            continue

        if isinstance(bbox, list) and len(bbox) == 4:
            try:
                bbox4 = [
                    float(bbox[0]),
                    float(bbox[1]),
                    float(bbox[2]),
                    float(bbox[3]),
                ]
            except Exception:
                rejected_reasons["bbox_conversion_failed_use_default"] = (
                    rejected_reasons.get("bbox_conversion_failed_use_default", 0) + 1
                )
                bbox4 = [0.0, 0.0, 0.0, 0.0]
        else:
            rejected_reasons["missing_or_invalid_bbox_use_default"] = (
                rejected_reasons.get("missing_or_invalid_bbox_use_default", 0) + 1
            )
            bbox4 = [0.0, 0.0, 0.0, 0.0]

        valid.append(
            {
                "knowledge_type": ktype,
                "title": title,
                "content": content,
                "page_num": page_num,
                "bbox": bbox4,
                "bibtex_citation": bibtex_citation,
            }
        )

    if debug and rejected_reasons:
        log(f"  Validation rejected: {rejected_reasons}")

    return valid


def build_teacher_client(timeout_sec: int, use_deepseek: bool = False) -> OpenAI:
    """Build OpenAI client for teacher model calls.

    Supports two API backends:
    - ModelScope (default): MS_KEY + API_BASE
    - DeepSeek (if use_deepseek=True): DEEPSEEK_API_KEY + DEEPSEEK_API_BASE
    """
    if use_deepseek:
        if not DEEPSEEK_API_KEY:
            raise RuntimeError(
                "DEEPSEEK_API_KEY is empty. Please set it in .env or environment variables."
            )
        log(f"Using DeepSeek API: {DEEPSEEK_API_BASE}")
        return OpenAI(
            base_url=DEEPSEEK_API_BASE,
            api_key=DEEPSEEK_API_KEY,
            timeout=timeout_sec,
            max_retries=0,
        )
    else:
        if not MS_KEY:
            raise RuntimeError(
                "MS_KEY is empty. Please set MS_KEY in .env or environment variables."
            )
        log(f"Using ModelScope API: {API_BASE}")
        return OpenAI(
            base_url=API_BASE, api_key=MS_KEY, timeout=timeout_sec, max_retries=0
        )


def _is_model_not_exist_error(err: Exception) -> bool:
    text = str(err).lower()
    return "model not exist" in text or "model_not_exist" in text


def choose_teacher_models(cli_model: Optional[str], use_deepseek: bool) -> List[str]:
    """Choose ordered candidate teacher models for current provider."""
    env_model = os.environ.get("TEACHER_MODEL", "")
    raw = (cli_model or env_model or "").strip()

    # Support comma-separated candidate list from CLI/env.
    models = [m.strip() for m in raw.split(",") if m.strip()] if raw else []

    if use_deepseek:
        # DeepSeek endpoint requires native model IDs.
        # Keep explicit models first, then append native fallbacks.
        normalized: List[str] = []
        for m in models:
            # Common mistaken provider-specific IDs from ModelScope.
            if m.lower().startswith("deepseek-ai/"):
                continue
            if m not in normalized:
                normalized.append(m)

        for m in DEFAULT_DEEPSEEK_MODELS:
            if m not in normalized:
                normalized.append(m)

        return normalized

    if models:
        return models

    # For ModelScope endpoint, prefer configured fallback list then default.
    models = FALLBACK_MODELS.copy() if FALLBACK_MODELS else []
    if DEFAULT_TEACHER_MODEL not in models:
        models.insert(0, DEFAULT_TEACHER_MODEL)
    return models


def teacher_extract_atomic_notes(
    client: OpenAI,
    teacher_models: List[str],
    paper: PaperRecord,
    section: SectionChunk,
    evidence: List[Dict[str, Any]],
    max_section_chars: int,
    retries: int,
) -> List[Dict[str, Any]]:
    section_text = section.text[:max_section_chars]
    evidence_json = json.dumps(evidence, ensure_ascii=False, indent=2)

    # Format citations for prompt
    citations_info = (
        "\n".join(
            f"- {c.get('title', 'N/A')} ({c.get('year', 'N/A')})"
            for c in (paper.citations[:10] if paper.citations else [])
        )
        or "暂无引用信息"
    )

    user_prompt = USER_PROMPT_TEMPLATE.format(
        allowed_types="/".join(sorted(ALLOWED_KNOWLEDGE_TYPES)),
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        section_title=section.title,
        bibtex=paper.bibtex or "（未获取）",
        citations_info=citations_info,
        section_text=section_text,
        evidence_json=evidence_json,
    )

    for model in teacher_models:
        for attempt in range(1, retries + 1):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=2000,
                )
                text = (resp.choices[0].message.content or "").strip()
                cleaned_text = clean_json_string(text)
                raw_obj = json.loads(cleaned_text)
                if not isinstance(raw_obj, dict):
                    raise ValueError("Teacher response is not a JSON object")

                raw_items = raw_obj.get("notes", [])
                if not isinstance(raw_items, list):
                    raise ValueError("Teacher response 'notes' is not a JSON array")

                if raw_items:
                    log(f"  Teacher responded with {len(raw_items)} raw note items")
                    sample_str = json.dumps(raw_items[0], ensure_ascii=False)
                    log(f"  Sample raw item: {sample_str[:200]}...")
                else:
                    log("  Teacher returned empty notes array")

                notes = validate_atomic_notes(raw_items, debug=True)

                if not notes and raw_items:
                    log(
                        f"  WARNING: Teacher returned {len(raw_items)} items but ALL were rejected by validation"
                    )

                return notes
            except Exception as e:
                # Fast-fail current model when endpoint says this model does not exist.
                if _is_model_not_exist_error(e):
                    log(
                        f"Teacher model unavailable: {model}. "
                        f"Trying next candidate..."
                    )
                    break

                wait = min(2**attempt, 12)
                log(
                    f"Teacher call failed ({model}, attempt {attempt}/{retries}) for "
                    f"{paper.arxiv_id} sec#{section.order}: {e}"
                )
                if attempt < retries:
                    time.sleep(wait)

    return []


def append_sharegpt_records(output_jsonl: Path, records: List[Dict[str, Any]]) -> int:
    if not records:
        return 0
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)

    with output_jsonl.open("a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return len(records)


def to_sharegpt_record(
    paper: PaperRecord,
    section: SectionChunk,
    notes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    user_inst = (
        "请将以下学术章节提炼为 AtomicNote JSON 数组，"
        "每个元素包含 knowledge_type/title/content/page_num/bbox，"
        f"knowledge_type 必须属于: {sorted(ALLOWED_KNOWLEDGE_TYPES)}。\n\n"
        f"章节标题: {section.title}\n"
        f"章节文本:\n{section.text}"
    )

    assistant_out = json.dumps(notes, ensure_ascii=False)

    return {
        "messages": [
            {"role": "user", "content": user_inst},
            {"role": "assistant", "content": assistant_out},
        ],
        "meta": {
            "source": "arxiv+mineru+teacher",
            "arxiv_id": paper.arxiv_id,
            "paper_title": paper.title,
            "section_title": section.title,
            "section_order": section.order,
            "keywords": paper.keywords,
        },
    }


def main() -> None:
    args = parse_args()

    if args.max_papers <= 0:
        raise ValueError("--max-papers must be > 0")

    if args.download_interval < 3.0:
        log("download interval < 3 detected, auto-adjust to 3.0 seconds")
        args.download_interval = 3.0

    teacher_models = choose_teacher_models(args.teacher_model, args.use_deepseek)

    log(f"API_BASE={API_BASE}")
    log(f"Teacher models={teacher_models}")
    log(f"Keywords={args.keywords}")

    papers = search_arxiv_papers(
        keywords=args.keywords,
        max_papers=args.max_papers,
        per_query=args.per_query,
    )
    if not papers:
        log("No papers found. Exit.")
        return

    log(f"Collected {len(papers)} unique arXiv papers")

    # Fetch Semantic Scholar metadata (BibTeX + citations) if enabled
    if args.enable_semantic_scholar:
        log("=" * 72)
        log("Fetching Semantic Scholar metadata (BibTeX + citations)...")
        log("Rate limit: <= 1 RPS with mandatory 1.2s throttle")
        log(
            "This will take approximately {:.1f} minutes".format(
                max(0.0, ((len(papers) - 1) * 1.2) / 60)
            )
        )
        log("=" * 72)

        s2_client = SemanticScholarClient(
            api_key=SEMANTIC_SCHOLAR_API_KEY,
            timeout_sec=20,
            batch_size=20,
        )
        success_count = s2_client.enrich_papers(papers)

        log("=" * 72)
        log(
            f"Semantic Scholar fetch completed: {success_count}/{len(papers)} successful"
        )
        log("=" * 72)

    client = build_teacher_client(
        timeout_sec=args.teacher_timeout, use_deepseek=args.use_deepseek
    )

    total_records = 0
    total_notes = 0
    total_processed_papers = 0

    # Collect all records first for potential train/test split
    all_paper_records: List[Tuple[PaperRecord, Dict[str, Any]]] = []

    for idx, paper in enumerate(papers, start=1):
        log(f"[{idx}/{len(papers)}] Processing {paper.arxiv_id} - {paper.title}")

        pdf_path = download_paper_pdf(
            paper=paper,
            raw_dir=args.raw_dir,
            download_interval=args.download_interval,
        )
        if not pdf_path:
            continue

        parse_out = run_mineru(
            pdf_path=pdf_path,
            parse_dir=args.parse_dir,
            mineru_bin=args.mineru_bin,
            mineru_method=args.mineru_method,
            timeout_sec=args.mineru_timeout,
        )
        if not parse_out:
            continue

        md_path = pick_primary_markdown(parse_out)
        if not md_path:
            log(f"No markdown found for {paper.arxiv_id}")
            continue

        try:
            md_text = md_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            log(f"Read markdown failed for {paper.arxiv_id}: {e}")
            continue

        sections = split_markdown_sections(md_text)
        if not sections:
            log(f"No sections from markdown for {paper.arxiv_id}")
            continue

        sections = sections[: args.max_sections_per_paper]
        evidence = load_mineru_evidence(parse_out, debug=True)

        log(f"  Found {len(sections)} sections, {len(evidence)} evidence items")

        paper_records: List[Dict[str, Any]] = []
        paper_note_count = 0

        for sec in sections:
            try:
                sec_evidence = select_section_evidence(sec.text, evidence, k=40)

                log(
                    f"  Processing section #{sec.order} '{sec.title}' ({len(sec.text)} chars, {len(sec_evidence)} evidence)"
                )

                notes = teacher_extract_atomic_notes(
                    client=client,
                    teacher_models=teacher_models,
                    paper=paper,
                    section=sec,
                    evidence=sec_evidence,
                    max_section_chars=args.max_section_chars,
                    retries=args.teacher_retries,
                )
                if not notes:
                    continue

                paper_note_count += len(notes)
                paper_records.append(
                    to_sharegpt_record(paper=paper, section=sec, notes=notes)
                )
            except Exception as e:
                log(f"Section failed ({paper.arxiv_id}#{sec.order}): {e}; continue")
                continue

        # Store records with paper metadata for later split
        for rec in paper_records:
            all_paper_records.append((paper, rec))

        paper_note_count = sum(len(rec["messages"]) for rec in paper_records)
        total_notes += paper_note_count
        total_processed_papers += 1

        log(
            f"Paper done: {paper.arxiv_id}, records={len(paper_records)}, notes_extracted={paper_note_count}"
        )

    # Train/test split logic
    if args.test_split_ratio > 0 and all_paper_records:
        import random

        random.seed(42)  # Reproducible split

        test_ratio = min(args.test_split_ratio, 0.5)  # Cap at 50%
        test_size = int(len(all_paper_records) * test_ratio)

        random.shuffle(all_paper_records)
        test_records = [rec for _, rec in all_paper_records[:test_size]]
        train_records = [rec for _, rec in all_paper_records[test_size:]]

        # Write train set
        written_train = append_sharegpt_records(args.output_jsonl, train_records)

        # Write test set
        test_jsonl = args.output_jsonl.parent / f"test_{args.output_jsonl.name}"
        written_test = append_sharegpt_records(test_jsonl, test_records)

        total_records = written_train + written_test

        log("=" * 72)
        log("Build completed with train/test split")
        log(f"Train records: {written_train} -> {args.output_jsonl}")
        log(f"Test records: {written_test} -> {test_jsonl}")
    else:
        # Write all to single file
        all_records = [rec for _, rec in all_paper_records]
        written = append_sharegpt_records(args.output_jsonl, all_records)
        total_records = written

        log("=" * 72)
        log("Build completed")
        log(f"Total records written: {total_records}")

    log(f"Processed papers: {total_processed_papers}")
    log(f"AtomicNote count: {total_notes}")
    log(f"Output pathpers: {total_processed_papers}")
    log(f"ShareGPT records written: {total_records}")
    log(f"AtomicNote count: {total_notes}")
    log(f"Output JSONL: {args.output_jsonl}")


if __name__ == "__main__":
    main()
