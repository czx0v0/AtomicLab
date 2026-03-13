"""
MinerU Cloud Parser
===================
基于 MinerU 云端 API 的 PDF 解析器。

职责：
- 通过 HTTP 上传 PDF 到 MinerU Cloud，获取 Markdown 及结构化信息
- 构造 ParsedDocument，尽量保留图片链接、表格和公式信息

注意：
- 实际 API 路径/字段需根据 MinerU 官方文档调整
- 通过环境变量控制：
  - MINERU_API_KEY       : 必填，云端 API Key
  - MINERU_API_BASE      : 可选，基础地址
  - MINERU_API_ENDPOINT  : 可选，完整解析端点，若设置则优先使用
"""

from __future__ import annotations

import io
import os
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from core.config import MINERU_API_BASE, MINERU_API_ENDPOINT, MINERU_API_KEY
from models.parse_result import (
    DocumentMetadata,
    ParsedDocument,
    ParsedFigure,
    ParsedFormula,
    ParsedSection,
    ParsedTable,
)


@dataclass
class MinerUCloudConfig:
    api_key: str
    endpoint: str
    timeout: int = 120


def _build_default_endpoint() -> Optional[str]:
    """
    根据环境变量构造默认解析端点。

    优先级：
    1. MINERU_API_ENDPOINT
    2. MINERU_API_BASE + /v1/parse
    """
    if MINERU_API_ENDPOINT:
        return MINERU_API_ENDPOINT
    if MINERU_API_BASE:
        return f"{MINERU_API_BASE.rstrip('/')}/v1/parse"
    return None


class MinerUCloudParser:
    """基于 MinerU Cloud API 的高精度 PDF 解析器。

    仅负责解析，不做分块和索引。
    """

    def __init__(self):
        # 强制使用官网 v4 基础路径
        self.api_base = (
            os.environ.get("MINERU_API_BASE") or "https://mineru.net/api/v4"
        ).rstrip("/")
        self.api_key = (os.environ.get("MINERU_API_KEY") or "").strip()
        if not self.api_key:
            raise RuntimeError(
                "MinerU Cloud API 未配置：环境变量 MINERU_API_KEY 为空。"
            )
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def parse(self, filepath: str, doc_id: Optional[str] = None) -> ParsedDocument:
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"文件不存在: {filepath}")

        if doc_id is None:
            doc_id = self._default_doc_id(str(filepath))

        print(f"🚀 开始向 MinerU Cloud 提交解析任务: {filepath.name}")
        batch_payload = {
            "files": [{"name": filepath.name, "data_id": doc_id or "demo_doc"}],
            "model_version": "vlm",
        }

        url_resp = requests.post(
            f"{self.api_base}/file-urls/batch",
            headers=self.headers,
            json=batch_payload,
        )
        url_resp.raise_for_status()
        url_data = url_resp.json()

        if url_data.get("code") != 0:
            raise RuntimeError(f"申请上传链接失败: {url_data.get('msg')}")

        data_block = url_data.get("data") or {}
        batch_id = data_block.get("batch_id")
        file_urls = data_block.get("file_urls") or []
        if not batch_id or not file_urls:
            raise RuntimeError("MinerU 返回的数据中缺少 batch_id 或 file_urls")

        upload_url = file_urls[0]

        print("⬆️ 正在直传文件流...")
        with open(filepath, "rb") as f:
            put_resp = requests.put(upload_url, data=f)
            put_resp.raise_for_status()

        print(f"⏳ 文件上传成功。等待云端处理 (Batch ID: {batch_id})...")
        poll_headers = {"Authorization": f"Bearer {self.api_key}"}

        import time

        for _ in range(60):
            time.sleep(10)
            status_resp = requests.get(
                f"{self.api_base}/extract-results/batch/{batch_id}",
                headers=poll_headers,
            )
            status_resp.raise_for_status()
            status_data = status_resp.json()

            if status_data.get("code") != 0:
                continue

            extract_results = (
                status_data.get("data", {}).get("extract_result", []) or []
            )
            if not extract_results:
                continue

            file_result = extract_results[0]
            state = file_result.get("state")

            if state == "done":
                zip_url = file_result.get("full_zip_url")
                if not zip_url:
                    raise RuntimeError("MinerU 返回的结果中缺少 full_zip_url")
                print(f"✅ 解析完成！下载地址: {zip_url}")
                return self._download_and_extract_zip(zip_url, doc_id)
            elif state == "failed" or file_result.get("err_msg"):
                raise RuntimeError(
                    f"MinerU 云端解析失败: {file_result.get('err_msg', '未知错误')}"
                )

            print(f"   ...当前状态: {state}，请耐心等待...")

        raise TimeoutError("MinerU 解析超时。")

    def parse_to_markdown(self, filepath: str) -> str:
        """仅返回 Markdown 内容的快捷方法。"""
        doc = self.parse(filepath)
        return doc.content

    def _download_and_extract_zip(self, zip_url: str, doc_id: str) -> ParsedDocument:
        """
        下载 MinerU Cloud 返回的 ZIP 结果，解压并构建 ParsedDocument。

        步骤：
        1. 将 ZIP 下载到内存并解压到本地缓存目录 parsed_docs/{doc_id}/
        2. 搜索主 Markdown 文件（*.md）
        3. 修复 Markdown 中的图片相对路径为本地可访问路径
        4. 使用处理后的 Markdown 构造 ParsedDocument

        若未找到 .md 文件，则抛出 ValueError。
        """
        print(f"[MinerUCloud] ⬇️ 正在下载并解压云端解析结果 (doc_id={doc_id})...")

        # 1. 本地缓存目录：.cache/parsed_docs/{doc_id}
        cache_dir = Path(".cache") / "parsed_docs" / doc_id
        if cache_dir.exists():
            shutil.rmtree(cache_dir, ignore_errors=True)
        cache_dir.mkdir(parents=True, exist_ok=True)

        # 2. 下载 ZIP 到内存并解压（使用固定超时时间，避免依赖已移除的 config）
        resp = requests.get(zip_url, timeout=120)
        resp.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            zf.extractall(path=cache_dir)

        # 3. 寻找 Markdown 文件
        md_files = list(cache_dir.rglob("*.md"))
        if not md_files:
            raise ValueError(
                f"解析失败：在 MinerU 返回的压缩包中未找到 Markdown 文件（doc_id={doc_id}）"
            )

        # 简单策略：取第一个 .md 作为主文件（通常位于 auto/xxx.md）
        main_md_file = md_files[0]
        md_content = main_md_file.read_text(encoding="utf-8", errors="ignore")
        md_dir = main_md_file.parent  # 图片通常与 md 同级或子目录

        # 4. 修复 Markdown 中的图片路径
        # 处理 markdown 语法: ![alt](images/xxx.png)
        def _replace_markdown_img(match: re.Match) -> str:
            original_path = match.group(1)
            absolute_path = (md_dir / original_path).resolve()
            return f"](/file={absolute_path})"

        img_pattern = re.compile(
            r"\]\(([^)]+\.(?:png|jpg|jpeg|svg|gif|webp))\)", flags=re.IGNORECASE
        )
        fixed_md_content = img_pattern.sub(_replace_markdown_img, md_content)

        # 处理 HTML 语法: <img src="images/xxx.png" ...>
        def _replace_html_img(match: re.Match) -> str:
            original_path = match.group(1)
            absolute_path = (md_dir / original_path).resolve()
            return f'src="/file={absolute_path}"'

        html_img_pattern = re.compile(
            r'src="([^"]+\.(?:png|jpg|jpeg|svg|gif|webp))"', flags=re.IGNORECASE
        )
        fixed_md_content = html_img_pattern.sub(_replace_html_img, fixed_md_content)

        print(f"[MinerUCloud] 🎉 解析结果落盘完成 (缓存路径: {cache_dir})")

        # 5. 构建 ParsedDocument
        # 使用修复后的 Markdown 构建简要章节信息（可供后续结构视图使用）
        content_list = self._build_content_list_from_markdown(fixed_md_content)
        sections = self._extract_sections(content_list, doc_id)

        metadata = DocumentMetadata(
            page_count=0,
            file_size=0,
            extra={
                "title": main_md_file.stem,
                "parser": "mineru_cloud",
                "api": "cloud_zip",
                "cache_dir": str(cache_dir),
            },
        )

        return ParsedDocument(
            doc_id=doc_id,
            title=main_md_file.stem,
            content=fixed_md_content,
            sections=sections,
            tables=[],
            figures=[],
            formulas=[],
            metadata=metadata,
            parse_confidence=0.95,
        )

    # ── helpers ──────────────────────────────────────────────────
    def _default_doc_id(self, filepath: str) -> str:
        name = Path(filepath).name.encode("utf-8", errors="ignore").hex()[:8].upper()
        return f"DOC-{name}"

    def _build_content_list_from_markdown(self, markdown: str) -> List[Dict[str, Any]]:
        """与本地 MinerUParser 保持风格一致的粗粒度内容列表。"""
        content_list: List[Dict[str, Any]] = []

        for line in markdown.splitlines():
            s = line.strip()
            if not s:
                continue
            if s.startswith("#"):
                level = len(s) - len(s.lstrip("#"))
                text = s[level:].strip()
                if text:
                    content_list.append({"type": "title", "text": text, "level": level})
            else:
                content_list.append({"type": "text", "text": s})

        return content_list

    def _extract_sections(
        self, content_list: List[Dict[str, Any]], doc_id: str
    ) -> List[ParsedSection]:
        """从粗粒度内容列表提取章节。"""
        sections: List[ParsedSection] = []
        current_heading = ""
        current_level = 1
        current_content_parts: List[str] = []
        section_index = 0

        def _flush():
            nonlocal section_index, current_heading, current_content_parts
            if not current_heading:
                return
            content = "\n\n".join(current_content_parts)
            sections.append(
                ParsedSection(
                    section_id=f"{doc_id}-SEC-{section_index:03d}",
                    heading=current_heading[:100],
                    level=current_level,
                    content=content,
                    word_count=len(content.split()),
                    page_start=0,
                    page_end=0,
                )
            )
            section_index += 1
            current_content_parts = []

        for item in content_list:
            item_type = item.get("type", "")
            text = (item.get("text") or "").strip()
            if not text:
                continue
            if item_type in ("title", "header"):
                _flush()
                current_heading = text
                current_level = int(item.get("level") or 1)
            else:
                current_content_parts.append(text)

        _flush()
        return sections

    def _extract_tables_from_api(
        self, tables_data: List[Dict[str, Any]], doc_id: str
    ) -> List[ParsedTable]:
        tables: List[ParsedTable] = []
        for i, item in enumerate(tables_data):
            markdown = item.get("markdown") or ""
            headers = item.get("headers") or []
            rows = item.get("rows") or []
            caption = item.get("caption") or ""
            html = item.get("html") or ""
            page = item.get("page") or 0

            # 如果没有显式 headers/rows，但有 markdown，可简单回退
            if (not headers or not rows) and markdown:
                # 不尝试完整 Markdown 表格解析，保留原始 markdown 即可
                headers = []
                rows = []

            tables.append(
                ParsedTable(
                    table_id=f"{doc_id}-TBL-{i:03d}",
                    caption=caption,
                    headers=[str(h) for h in headers],
                    rows=[[str(c) for c in r] for r in rows],
                    markdown=markdown,
                    html=html,
                    page_number=int(page),
                    semantic_text=caption or (markdown[:100] if markdown else ""),
                )
            )
        return tables

    def _extract_tables_from_markdown(
        self, content_list: List[Dict[str, Any]], markdown: str, doc_id: str
    ) -> List[ParsedTable]:
        """在缺少结构化表格字段时，从 Markdown 粗略提取表格。"""
        from services.parser.mineru_parser import MinerUParser  # 复用现有实现

        helper = MinerUParser(parse_method=self.parse_method)  # type: ignore[arg-type]
        # 仅使用其 Markdown → content_list → table 的逻辑
        return helper._extract_tables(  # type: ignore[attr-defined]
            helper._build_content_list_from_markdown(markdown),  # type: ignore[attr-defined]
            doc_id,
        )

    def _extract_figures_from_api(
        self, images: List[Dict[str, Any]], doc_id: str
    ) -> List[ParsedFigure]:
        figures: List[ParsedFigure] = []
        for i, img in enumerate(images):
            figures.append(
                ParsedFigure(
                    figure_id=f"{doc_id}-FIG-{i:03d}",
                    caption=img.get("caption", ""),
                    page_number=int(img.get("page") or 0),
                    image_path=img.get("url") or img.get("path") or "",
                )
            )
        return figures

    def _extract_formulas_from_api(
        self, equations: List[Dict[str, Any]], doc_id: str
    ) -> List[ParsedFormula]:
        formulas: List[ParsedFormula] = []
        for i, eq in enumerate(equations):
            latex = eq.get("latex") or eq.get("content") or eq.get("text") or ""
            if not latex:
                continue
            formulas.append(
                ParsedFormula(
                    formula_id=f"{doc_id}-EQ-{i:03d}",
                    content=latex,
                    page_number=int(eq.get("page") or 0),
                )
            )
        return formulas

    def _build_metadata(
        self,
        filepath: str,
        api_data: Dict[str, Any],
        content_list: List[Dict[str, Any]],
    ) -> DocumentMetadata:
        stat = os.stat(filepath) if os.path.exists(filepath) else None
        page_count = int(
            api_data.get(
                "page_count",
                (
                    max((item.get("page") or 0) for item in content_list)
                    if content_list
                    else 0
                ),
            )
        )
        title = api_data.get("title") or Path(filepath).stem

        extra: Dict[str, Any] = {
            "title": title,
            "parser": "mineru_cloud",
            "api": "cloud",
            "endpoint": self.config.endpoint,
        }
        if "parser_name" in api_data:
            extra["parser_name"] = api_data["parser_name"]

        return DocumentMetadata(
            page_count=page_count,
            file_size=stat.st_size if stat else 0,
            extra=extra,
        )
