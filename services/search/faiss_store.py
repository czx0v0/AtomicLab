"""
FAISS Vector Store
==================
FAISS向量存储管理器
支持多索引类型、增量更新、元数据过滤、持久化
"""

import os
import pickle
import numpy as np
from pathlib import Path
from typing import List, Optional, Dict, Tuple, Any

try:
    import faiss

    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

from models.chunk import TextChunk


class FAISSVectorStore:
    """
    FAISS向量存储管理器

    特性:
    - 多索引类型支持 (Flat/IVF/HNSW)
    - 增量更新
    - 元数据过滤
    - 持久化到本地文件
    """

    def __init__(
        self,
        dimension: int = 384,  # MiniLM默认维度
        index_type: str = "HNSW",
        storage_path: str = "storage/faiss",
    ):
        if not FAISS_AVAILABLE:
            raise ImportError("FAISS未安装。请运行: pip install faiss-cpu>=1.7.4")

        self.dimension = dimension
        self.index_type = index_type.upper()
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 索引和映射
        self.index: Optional[faiss.Index] = None
        self.chunk_map: Dict[int, str] = {}  # faiss_id -> chunk_id
        self.metadata_store: Dict[str, dict] = {}  # chunk_id -> metadata

        self._init_index()

    def _init_index(self):
        """初始化FAISS索引"""
        if self.index_type == "FLAT":
            # 精确搜索 - 适合小规模数据(<10k)
            self.index = faiss.IndexFlatIP(self.dimension)

        elif self.index_type == "HNSW":
            # HNSW图索引 - 适合中等规模,速度快
            self.index = faiss.IndexHNSWFlat(self.dimension, 32)
            self.index.hnsw.efConstruction = 200
            self.index.hnsw.efSearch = 128

        elif self.index_type == "IVF":
            # IVF倒排索引 - 适合大规模数据
            quantizer = faiss.IndexFlatIP(self.dimension)
            self.index = faiss.IndexIVFFlat(quantizer, self.dimension, 100)
            self.index.nprobe = 10  # 搜索时检查的聚类数

        else:
            raise ValueError(f"不支持的索引类型: {self.index_type}")

    def add_chunks(self, chunks: List[TextChunk]):
        """
        批量添加chunks到索引

        Args:
            chunks: 文本块列表,每个chunk需要有embedding
        """
        if not chunks:
            return

        # 提取embeddings
        embeddings = []
        valid_chunks = []

        for chunk in chunks:
            if chunk.embedding is not None:
                # 确保维度匹配
                if len(chunk.embedding) == self.dimension:
                    embeddings.append(chunk.embedding)
                    valid_chunks.append(chunk)
                    self.metadata_store[chunk.chunk_id] = chunk.metadata.to_dict()
                else:
                    print(f"警告: chunk {chunk.chunk_id} 维度不匹配,跳过")

        if not embeddings:
            print("警告: 没有有效的embeddings可添加")
            return

        # 转换为numpy数组并归一化
        embeddings = np.array(embeddings).astype("float32")
        faiss.normalize_L2(embeddings)  # 归一化以使用内积作为余弦相似度

        # 添加到索引
        start_id = len(self.chunk_map)
        self.index.add(embeddings)

        # 更新映射
        for i, chunk in enumerate(valid_chunks):
            self.chunk_map[start_id + i] = chunk.chunk_id

        print(f"成功添加 {len(valid_chunks)} 个chunks到索引")

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, float]]:
        """
        向量搜索 + 元数据过滤

        Args:
            query_embedding: 查询向量
            top_k: 返回结果数量
            metadata_filter: 元数据过滤条件,如 {"doc_type": "pdf"}

        Returns:
            [(chunk_id, score), ...] 按相似度排序
        """
        if self.index is None or self.index.ntotal == 0:
            return []

        # 准备查询向量
        query = query_embedding.reshape(1, -1).astype("float32")
        faiss.normalize_L2(query)

        # 搜索更多结果用于过滤
        search_k = (
            min(top_k * 3, self.index.ntotal)
            if metadata_filter
            else min(top_k, self.index.ntotal)
        )

        # 执行搜索
        scores, indices = self.index.search(query, search_k)

        results = []
        for idx, score in zip(indices[0], scores[0]):
            if idx == -1:
                continue

            chunk_id = self.chunk_map.get(int(idx))
            if not chunk_id:
                continue

            # 元数据过滤
            if metadata_filter:
                meta = self.metadata_store.get(chunk_id, {})
                if not self._match_filter(meta, metadata_filter):
                    continue

            results.append((chunk_id, float(score)))

            if len(results) >= top_k:
                break

        return results

    def _match_filter(self, metadata: dict, filter_dict: dict) -> bool:
        """检查元数据是否匹配过滤条件"""
        for key, value in filter_dict.items():
            if key not in metadata:
                return False
            meta_value = metadata[key]
            # 支持列表包含检查
            if isinstance(value, list):
                if not any(v in meta_value for v in value):
                    return False
            elif meta_value != value:
                return False
        return True

    def get_stats(self) -> dict:
        """获取索引统计信息"""
        return {
            "total_vectors": self.index.ntotal if self.index else 0,
            "dimension": self.dimension,
            "index_type": self.index_type,
            "storage_path": str(self.storage_path),
        }

    def save(self):
        """持久化索引和元数据"""
        if self.index is None:
            return

        # 保存FAISS索引
        index_file = self.storage_path / "index.faiss"
        faiss.write_index(self.index, str(index_file))

        # 保存元数据和映射
        meta_file = self.storage_path / "metadata.pkl"
        with open(meta_file, "wb") as f:
            pickle.dump(
                {
                    "chunk_map": self.chunk_map,
                    "metadata_store": self.metadata_store,
                    "dimension": self.dimension,
                    "index_type": self.index_type,
                },
                f,
            )

        print(f"索引已保存到 {self.storage_path}")

    def load(self) -> bool:
        """
        加载索引和元数据

        Returns:
            是否成功加载
        """
        index_file = self.storage_path / "index.faiss"
        meta_file = self.storage_path / "metadata.pkl"

        if not index_file.exists() or not meta_file.exists():
            print(f"索引文件不存在于 {self.storage_path}")
            return False

        try:
            # 加载FAISS索引
            self.index = faiss.read_index(str(index_file))

            # 加载元数据
            with open(meta_file, "rb") as f:
                data = pickle.load(f)
                self.chunk_map = data["chunk_map"]
                self.metadata_store = data["metadata_store"]
                # 验证维度
                saved_dim = data.get("dimension", self.dimension)
                if saved_dim != self.dimension:
                    print(
                        f"警告: 保存的维度({saved_dim})与当前({self.dimension})不匹配"
                    )

            print(f"成功加载索引,包含 {self.index.ntotal} 个向量")
            return True

        except Exception as e:
            print(f"加载索引失败: {e}")
            return False

    def delete_chunk(self, chunk_id: str) -> bool:
        """
        删除指定chunk(标记删除,实际重建索引)

        Note: FAISS不支持直接删除,这里标记为无效
        实际删除需要在重建索引时处理
        """
        if chunk_id in self.metadata_store:
            self.metadata_store[chunk_id]["_deleted"] = True
            return True
        return False

    def clear(self):
        """清空索引"""
        self._init_index()
        self.chunk_map = {}
        self.metadata_store = {}
        print("索引已清空")


class VectorStoreManager:
    """
    向量存储管理器
    管理多个集合(如不同文档类型)
    """

    def __init__(self, base_path: str = "storage/faiss"):
        self.base_path = Path(base_path)
        self.stores: Dict[str, FAISSVectorStore] = {}

    def get_store(self, name: str, **kwargs) -> FAISSVectorStore:
        """获取或创建存储"""
        if name not in self.stores:
            store_path = self.base_path / name
            self.stores[name] = FAISSVectorStore(storage_path=str(store_path), **kwargs)
        return self.stores[name]

    def save_all(self):
        """保存所有存储"""
        for name, store in self.stores.items():
            print(f"保存存储: {name}")
            store.save()

    def load_all(self) -> List[str]:
        """加载所有存储,返回成功加载的名称列表"""
        loaded = []
        for store_dir in self.base_path.iterdir():
            if store_dir.is_dir():
                name = store_dir.name
                store = self.get_store(name)
                if store.load():
                    loaded.append(name)
        return loaded
