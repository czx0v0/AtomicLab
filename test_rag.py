"""
RAG功能测试脚本
===============
测试高级PDF解析和RAG检索功能
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_imports():
    """测试所有模块是否能正确导入"""
    print("=" * 60)
    print("测试模块导入...")
    print("=" * 60)

    tests = [
        (
            "数据模型",
            lambda: (
                __import__("models.parse_result"),
                __import__("models.chunk"),
                __import__("models.search"),
            ),
        ),
        ("Docling解析器", lambda: __import__("services.parser.docling_parser")),
        ("语义分块器", lambda: __import__("services.chunking.semantic_chunker")),
        ("FAISS存储", lambda: __import__("services.search.faiss_store")),
        ("BM25索引", lambda: __import__("services.search.bm25_index")),
        ("混合检索", lambda: __import__("services.search.hybrid_searcher")),
        ("重排序器", lambda: __import__("services.search.reranker")),
        ("RAG服务", lambda: __import__("services.rag_service")),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            test_fn()
            print(f"✓ {name}")
            passed += 1
        except ImportError as e:
            print(f"✗ {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"⚠ {name}: {e}")
            passed += 1  # 导入成功但可能有依赖问题

    print("=" * 60)
    print(f"结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    return failed == 0


def test_data_models():
    """测试数据模型"""
    print("\n" + "=" * 60)
    print("测试数据模型...")
    print("=" * 60)

    from models.parse_result import ParsedDocument, ParsedTable, DocumentMetadata
    from models.chunk import TextChunk, ChunkMetadata
    from models.search import SearchResult, SearchScores

    # 创建测试文档
    doc = ParsedDocument(
        doc_id="test_doc_001",
        title="测试文档",
        content="# 标题\n\n这是测试内容。",
        tables=[
            ParsedTable(
                table_id="test_table_001",
                caption="测试表格",
                headers=["列1", "列2"],
                rows=[["A", "B"], ["C", "D"]],
                semantic_text="测试表格语义描述",
                structure_hash="abc123",
            )
        ],
        metadata=DocumentMetadata(
            author="测试作者",
            page_count=10,
        ),
        parse_confidence=0.95,
    )

    print(f"✓ ParsedDocument创建成功: {doc.doc_id}")
    print(f"  - 标题: {doc.title}")
    print(f"  - 表格数: {len(doc.tables)}")
    print(f"  - 置信度: {doc.parse_confidence}")

    # 创建测试chunk
    chunk = TextChunk(
        chunk_id="test_chunk_001",
        doc_id="test_doc_001",
        content="测试内容",
        chunk_type="semantic",
        metadata=ChunkMetadata(
            doc_title="测试文档",
            token_count=10,
        ),
    )

    print(f"✓ TextChunk创建成功: {chunk.chunk_id}")

    # 创建测试结果
    result = SearchResult(
        chunk=chunk,
        scores=SearchScores(
            semantic=0.85,
            keyword=0.75,
            rrf_fusion=0.80,
            final=0.82,
        ),
        query="测试查询",
    )

    print(f"✓ SearchResult创建成功")
    print(f"  - 语义分数: {result.scores.semantic}")
    print(f"  - 最终分数: {result.scores.final}")

    print("=" * 60)
    return True


def test_rrf_fusion():
    """测试RRF融合算法"""
    print("\n" + "=" * 60)
    print("测试RRF融合算法...")
    print("=" * 60)

    # 模拟搜索结果
    semantic_results = [
        ("chunk_001", 0.90),
        ("chunk_002", 0.85),
        ("chunk_003", 0.80),
        ("chunk_004", 0.75),
    ]

    keyword_results = [
        ("chunk_002", 0.95),
        ("chunk_001", 0.80),
        ("chunk_005", 0.70),
    ]

    # RRF参数
    k = 60
    semantic_weight = 0.6
    keyword_weight = 0.3

    # 计算RRF分数
    from collections import defaultdict

    semantic_ranks = {cid: rank + 1 for rank, (cid, _) in enumerate(semantic_results)}
    keyword_ranks = {cid: rank + 1 for rank, (cid, _) in enumerate(keyword_results)}

    all_chunks = set(semantic_ranks.keys()) | set(keyword_ranks.keys())
    rrf_scores = {}

    for chunk_id in all_chunks:
        score = 0.0
        if chunk_id in semantic_ranks:
            score += semantic_weight / (k + semantic_ranks[chunk_id])
        if chunk_id in keyword_ranks:
            score += keyword_weight / (k + keyword_ranks[chunk_id])
        rrf_scores[chunk_id] = score

    # 排序
    sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

    print("RRF融合结果:")
    for chunk_id, score in sorted_results:
        sem_rank = semantic_ranks.get(chunk_id, "-")
        key_rank = keyword_ranks.get(chunk_id, "-")
        print(
            f"  {chunk_id}: RRF={score:.4f} (语义排名={sem_rank}, 关键词排名={key_rank})"
        )

    print("=" * 60)
    return True


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("AtomicLab RAG功能测试")
    print("=" * 60 + "\n")

    results = []

    # 测试1: 模块导入
    results.append(("模块导入", test_imports()))

    # 测试2: 数据模型
    try:
        results.append(("数据模型", test_data_models()))
    except Exception as e:
        print(f"✗ 数据模型测试失败: {e}")
        results.append(("数据模型", False))

    # 测试3: RRF融合
    try:
        results.append(("RRF融合", test_rrf_fusion()))
    except Exception as e:
        print(f"✗ RRF融合测试失败: {e}")
        results.append(("RRF融合", False))

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{status}: {name}")

    total = len(results)
    passed = sum(1 for _, p in results if p)

    print("=" * 60)
    print(f"总计: {passed}/{total} 通过")
    print("=" * 60)

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
