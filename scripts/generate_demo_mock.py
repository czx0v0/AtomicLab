"""
Generate Demo Mock Data
=======================

离线脚本：基于真实 RAG 流程生成 Demo 所需的静态数据：
- demo_data/demo_paper.pdf (需提前放好真实 PDF)
- demo_data/mock_library.json
- demo_data/mock_notes.json
- demo_data/faiss_index/{index.faiss, metadata.pkl}

使用方式（在项目根目录）::

    python -m scripts.generate_demo_mock

注意：
- 该脚本仅用于本地/开发环境，不能在只读容器内写入。
- 运行前请确保 RAG 相关依赖已安装，且 demo_paper.pdf.pdf 已替换为真实白皮书，
  并在环境中正确配置 MINERU_API_KEY 以启用 MinerU Cloud 解析。
"""

from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path

from core.config import RAG_CONFIG
from core.utils import get_demo_data_path
from services.rag_service import RAGService


# 图片扩展名 -> data URL MIME
_IMAGE_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}


def _image_path_to_base64_data_url(image_path: Path) -> str | None:
    """读取图片文件并转为 data URL；路径不存在或读失败时返回 None。"""
    if not image_path.is_file():
        return None
    try:
        raw = image_path.read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        ext = image_path.suffix.lower()
        mime = _IMAGE_MIME.get(ext, "image/png")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None


def inline_images_in_markdown(
    content: str,
    base_dir: Path,
) -> str:
    """
    将 Markdown 中的图片引用改为 Base64 内联，便于跨平台（ModelScope/本地）100% 加载。

    支持：
    - ](/file=/absolute/path/to/img.png)  （MinerU 解析器产出）
    - ](images/xxx.png) 或 ](./fig/fig1.jpg)  （相对路径，相对 base_dir）
    """
    if not content or not content.strip():
        return content

    base_dir = Path(base_dir).resolve()

    # 1. ](/file=absolute_path) — MinerU 解析器产出
    def repl_file(m: re.Match) -> str:
        path_str = m.group(1).strip()
        path = Path(path_str)
        data_url = _image_path_to_base64_data_url(path)
        return f"]({data_url})" if data_url else m.group(0)
    content = re.sub(r"\]\(/file=([^)]+)\)", repl_file, content)

    # 2. ](relative_or_absolute path with image extension)
    def repl_rel(m: re.Match) -> str:
        path_str = m.group(1).strip()
        if path_str.startswith("data:"):
            return m.group(0)
        path = (base_dir / path_str).resolve() if not Path(path_str).is_absolute() else Path(path_str)
        data_url = _image_path_to_base64_data_url(path)
        return f"]({data_url})" if data_url else m.group(0)
    content = re.sub(
        r"\]\(([^)]+\.(?:png|jpg|jpeg|gif|webp|svg))\)",
        repl_rel,
        content,
        flags=re.IGNORECASE,
    )

    return content


def main() -> None:
    demo_dir = get_demo_data_path()
    demo_pdf = demo_dir / "demo_paper.pdf"

    if not demo_pdf.exists():
        raise FileNotFoundError(
            f"atomic_lab_manual.pdf 不存在，请先放入真实 Demo 文档: {demo_pdf}"
        )

    print(f"[DemoMock] 使用 Demo 文档: {demo_pdf}")

    # 初始化 RAG 服务，单独使用 demo_data 目录作为存储，并强制使用 MinerU Cloud 解析后端
    # 注意：RAGService 会在 storage_path 下创建 \"faiss\" / \"bm25\" 子目录。
    # 我们后面会把 \"faiss\" 重命名为 \"faiss_index\"，与在线 Demo 加载逻辑保持一致。
    rag_cfg = {**RAG_CONFIG, "storage_path": str(demo_dir), "parser_backend": "mineru"}
    rag = RAGService(rag_cfg)

    print("[DemoMock] 调用 RAGService.process_document() 开始处理 Demo 文档...")
    result = rag.process_document(str(demo_pdf))
    if not result.success:
        raise RuntimeError(f"Demo 文档处理失败: {result.error}")

    print(
        f"[DemoMock] 处理完成: doc_id={result.doc_id}, "
        f"chunks={result.chunk_count}, confidence={result.confidence:.2f}"
    )

    # 从 RAG 服务中获取解析后的 ParsedDocument
    parsed = rag.get_parsed_document(result.doc_id)
    if not parsed:
        raise RuntimeError("未在 RAGService 中找到对应的 ParsedDocument 缓存。")

    # 将 Markdown 中的图片路径改为 Base64 内联，确保跨平台（ModelScope/本地）100% 加载
    extra = getattr(parsed.metadata, "extra", None) or {}
    cache_dir_str = extra.get("cache_dir", "")
    content_base = Path(cache_dir_str) if cache_dir_str and Path(cache_dir_str).is_dir() else demo_dir
    inlined_content = inline_images_in_markdown(parsed.content, content_base)
    parsed_dict = parsed.to_dict()
    parsed_dict["content"] = inlined_content

    # 构造 lib/stats 状态，兼容在线 Demo 加载逻辑
    lib: dict = {
        result.doc_id: {
            "name": demo_pdf.name,
            "text": inlined_content,
            "notes": [],
            "annotations": [],
            "filepath": str(demo_pdf),
            "rag_indexed": True,
            "rag_processing": False,
            "rag_status": "✅ 已完成",
            "rag_progress": 100,
            "chunk_count": result.chunk_count,
            "parse_confidence": result.confidence,
            "parsed_document": parsed_dict,
        }
    }
    stats = {"docs": 1, "notes": 0, "nodes": 0}

    # 保存向量索引到 demo_data/faiss 下
    print("[DemoMock] 正在保存向量索引到 demo_data/faiss ...")
    rag.save()

    # 将 demo_data/faiss 重命名为 demo_data/faiss_index，便于在线 Demo 直接加载
    faiss_src = demo_dir / "faiss"
    faiss_dst = demo_dir / "faiss_index"
    if faiss_dst.exists():
        print(f"[DemoMock] 清理旧的 {faiss_dst} 目录...")
        import shutil as _shutil

        _shutil.rmtree(faiss_dst, ignore_errors=True)
    if faiss_src.exists():
        import shutil as _shutil

        _shutil.move(str(faiss_src), str(faiss_dst))
        print(f"[DemoMock] 已将索引目录从 {faiss_src} 移动到 {faiss_dst}")
    else:
        print(f"[DemoMock] 警告：未找到 {faiss_src}，请检查 RAG 保存逻辑。")

    # 根据 lib 构造简单的 notes 列表占位（真实环境可结合 Crusher 等生成）
    notes = []
    for pid, info in lib.items():
        sample_note = {
            "id": f"NOTE-{pid}-0001",
            "type": "高亮",
            "content": f"示例笔记来自文献 {info.get('name', '')}",
            "annotation": "",
            "translation": "",
            "page": 1,
            "color": "yellow",
            "priority": 3,
            "ts": "00:00",
            "source_pid": pid,
        }
        notes.append(sample_note)

    stats["notes"] = len(notes)
    # Demo 场景下不持久化知识树结构，这里节点数固定为 0
    stats["nodes"] = 0

    # 保存 mock_library.json
    lib_out = {
        "lib": lib,
        "stats": stats,
    }
    with open(demo_dir / "mock_library.json", "w", encoding="utf-8") as f:
        json.dump(lib_out, f, ensure_ascii=False, indent=2)
    print(f"[DemoMock] 已写入 {demo_dir / 'mock_library.json'}")

    # 保存 mock_notes.json
    with open(demo_dir / "mock_notes.json", "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)
    print(f"[DemoMock] 已写入 {demo_dir / 'mock_notes.json'}")

    print("[DemoMock] 生成完成")


if __name__ == "__main__":
    main()
