"""
Table Chunker
=============
表格专用分块器
实现双重embedding策略
"""

from typing import List

from models.chunk import TextChunk, ChunkMetadata
from models.parse_result import ParsedTable


class TableChunker:
    """
    表格专用分块器
    
    双重embedding策略:
    1. 语义描述chunk: 用于语义搜索
    2. 行级chunks: 用于精确查询
    3. 结构hash: 用于去重和精确匹配
    """
    
    def create_table_chunks(
        self,
        table: ParsedTable,
        doc_id: str,
        doc_title: str = ""
    ) -> List[TextChunk]:
        """
        为表格创建多个chunks
        
        Returns:
            - 1个语义描述chunk (table_semantic)
            - N个行级chunks (table_row)
        """
        chunks = []
        
        # 1. 语义描述chunk - 用于语义搜索
        semantic_chunk = self._create_semantic_chunk(table, doc_id, doc_title)
        chunks.append(semantic_chunk)
        
        # 2. 行级chunks - 用于精确匹配
        if len(table.rows) <= 20:  # 小表格:每行一个chunk
            for i, row in enumerate(table.rows):
                row_chunk = self._create_row_chunk(table, row, i, doc_id, doc_title)
                chunks.append(row_chunk)
        else:  # 大表格:每5行一个chunk
            for i in range(0, len(table.rows), 5):
                rows_batch = table.rows[i:i+5]
                batch_chunk = self._create_row_batch_chunk(
                    table, rows_batch, i, doc_id, doc_title
                )
                chunks.append(batch_chunk)
        
        return chunks
    
    def _create_semantic_chunk(
        self,
        table: ParsedTable,
        doc_id: str,
        doc_title: str
    ) -> TextChunk:
        """
        创建语义描述chunk
        
        这个chunk包含表格的整体语义描述,
        用于回答"关于这个表格..."类型的查询
        """
        # 使用预生成的语义文本
        content = table.semantic_text
        
        # 如果没有预生成,则构建
        if not content:
            content = self._build_semantic_text(table)
        
        return TextChunk(
            chunk_id=table.table_id,
            doc_id=doc_id,
            content=content,
            chunk_type="table_semantic",
            table_data=table,
            metadata=ChunkMetadata(
                doc_title=doc_title,
                doc_type="table",
                keywords=table.headers,
                source_section=table.caption,
                page_number=table.page_number,
            ),
            quality_score=0.9 if table.headers else 0.5,
        )
    
    def _create_row_chunk(
        self,
        table: ParsedTable,
        row: List[str],
        row_index: int,
        doc_id: str,
        doc_title: str
    ) -> TextChunk:
        """
        创建单行chunk
        
        格式: "列名: 值, 列名: 值..."
        适合精确查询,如"张三的成绩是多少"
        """
        # 构建键值对文本
        kv_pairs = []
        for header, value in zip(table.headers, row):
            kv_pairs.append(f"{header}: {value}")
        
        content = f"{table.caption} | " + " | ".join(kv_pairs)
        
        return TextChunk(
            chunk_id=f"{table.table_id}_r{row_index:03d}",
            doc_id=doc_id,
            content=content,
            chunk_type="table_row",
            table_data=table,
            metadata=ChunkMetadata(
                doc_title=doc_title,
                doc_type="table_row",
                keywords=list(row),  # 行内容作为关键词
                source_section=table.caption,
                page_number=table.page_number,
                parent_table=table.table_id,
            ),
            quality_score=0.95,
        )
    
    def _create_row_batch_chunk(
        self,
        table: ParsedTable,
        rows: List[List[str]],
        start_index: int,
        doc_id: str,
        doc_title: str
    ) -> TextChunk:
        """
        创建行批次chunk (用于大表格)
        """
        # 合并多行
        row_texts = []
        for i, row in enumerate(rows):
            kv_pairs = [f"{h}: {v}" for h, v in zip(table.headers, row)]
            row_texts.append(f"[行{start_index+i+1}] " + " | ".join(kv_pairs))
        
        content = f"{table.caption} (行 {start_index+1}-{start_index+len(rows)}):\n"
        content += "\n".join(row_texts)
        
        # 收集所有关键词
        all_keywords = []
        for row in rows:
            all_keywords.extend(row)
        
        return TextChunk(
            chunk_id=f"{table.table_id}_b{start_index:03d}",
            doc_id=doc_id,
            content=content,
            chunk_type="table_row",
            table_data=table,
            metadata=ChunkMetadata(
                doc_title=doc_title,
                doc_type="table_row",
                keywords=all_keywords,
                source_section=table.caption,
                page_number=table.page_number,
                parent_table=table.table_id,
            ),
            quality_score=0.85,
        )
    
    def _build_semantic_text(self, table: ParsedTable) -> str:
        """
        构建表格的语义描述文本
        
        用于embedding和语义搜索
        """
        parts = []
        
        # 标题
        if table.caption:
            parts.append(f"表格标题: {table.caption}")
        
        # 列信息
        parts.append(f"包含列: {', '.join(table.headers)}")
        
        # 数据概况
        parts.append(f"共{len(table.rows)}行数据")
        
        # 数据样本
        if table.rows:
            sample_texts = []
            for row in table.rows[:3]:  # 前3行
                kv = [f"{h}={v}" for h, v in zip(table.headers, row)]
                sample_texts.append(", ".join(kv))
            parts.append(f"数据示例: {'; '.join(sample_texts)}")
        
        return ". ".join(parts)
    
    def find_table_by_structure(
        self,
        query_table: ParsedTable,
        existing_tables: List[ParsedTable]
    ) -> List[ParsedTable]:
        """
        通过结构hash查找相似表格
        
        用于表格去重和关联
        """
        matches = []
        for table in existing_tables:
            if table.structure_hash == query_table.structure_hash:
                matches.append(table)
        return matches
