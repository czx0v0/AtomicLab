"""
Atomic Knowledge Decomposition Service
======================================
原子知识解构服务 - 基于LLM的知识解构

Features:
- Atomic-RAG驱动的知识解构
- 三层结构：Axiom + Methodology + Boundary
- 七分类：Method/Definition/Formula/Context/Data/Result/Insight
- 使用Qwen2.5-72B-Instruct进行高阶逻辑推理
"""

from typing import List, Dict, Optional
import json
import time
import hashlib

from models.atomic_knowledge import (
    AtomicKnowledge,
    AtomicDecomposition,
    KnowledgeCategory,
    CATEGORY_PROMPTS,
)
from agents.base import call_llm
from core.state import next_node_id


class AtomicDecomposer:
    """原子知识解构器

    将笔记解构为原子知识的三层结构：
    - Axiom（公理）：核心概念或事实
    - Methodology（方法）：技术路径或方法
    - Boundary（边界）：适用范围和限制
    """

    def __init__(self, model: str = "deepseek-chat"):
        """初始化解构器
            
        Args:
            model: LLM模型名称（默认DeepSeek V2，兼容call_llm默认配置）
        """
        self.model = model
        self.cache: Dict[str, AtomicDecomposition] = {}

    def _generate_cache_key(self, note_content: str) -> str:
        """生成缓存键"""
        return hashlib.md5(note_content.encode()).hexdigest()

    def decompose(
        self,
        note_content: str,
        note_id: str,
        doc_id: str,
        use_cache: bool = True,
    ) -> AtomicDecomposition:
        """解构单条笔记

        Args:
            note_content: 笔记内容
            note_id: 笔记ID
            doc_id: 文献ID
            use_cache: 是否使用缓存

        Returns:
            AtomicDecomposition: 解构结果
        """
        start_time = time.time()

        # 检查缓存
        if use_cache:
            cache_key = self._generate_cache_key(note_content)
            if cache_key in self.cache:
                return self.cache[cache_key]

        # 构建提示词
        prompt = self._build_decomposition_prompt(note_content)

        try:
            # 调用LLM
            response = call_llm(
                system_prompt="你是学术知识解构专家。请将给定的学术笔记解构为原子知识的三层结构。",
                user_prompt=prompt,
                max_tokens=800,
                temperature=0.3,
            )

            # 解析响应
            atoms = self._parse_decomposition_response(response, note_id, doc_id)

            # 计算置信度
            overall_confidence = (
                sum(a.confidence for a in atoms) / len(atoms) if atoms else 0.0
            )

            # 创建解构结果
            decomposition = AtomicDecomposition(
                note_id=note_id,
                doc_id=doc_id,
                atoms=atoms,
                overall_confidence=overall_confidence,
                decomposition_time_ms=(time.time() - start_time) * 1000,
            )

            # 缓存结果
            if use_cache:
                self.cache[cache_key] = decomposition

            return decomposition

        except Exception as e:
            print(f"[AtomicDecomposer] 解构失败: {e}")
            # 返回空解构
            return AtomicDecomposition(
                note_id=note_id,
                doc_id=doc_id,
                atoms=[],
                overall_confidence=0.0,
                decomposition_time_ms=(time.time() - start_time) * 1000,
            )

    def _build_decomposition_prompt(self, note_content: str) -> str:
        """构建解构提示词"""

        # 截断过长内容
        content = note_content[:800] if len(note_content) > 800 else note_content

        prompt = f"""请对以下学术笔记进行原子知识解构，提取核心知识的三层结构。

笔记内容：
{content}

解构要求：
1. 将内容分解为1-3个原子知识
2. 每个原子知识包含三层：
   - Axiom（公理）：核心概念或事实（一句话）
   - Methodology（方法）：技术路径或方法（一句话）
   - Boundary（边界）：适用范围和限制（一句话）

3. 分类为以下类别之一：
   - Method: 方法论（技术方法、算法、流程）
   - Definition: 定义（概念定义、术语解释）
   - Formula: 公式（数学公式、计算方法）
   - Context: 背景（研究背景、历史上下文）
   - Data: 数据（实验数据、统计结果）
   - Result: 结果（研究发现、实验结论）
   - Insight: 洞察（观点、见解、推论）

请按以下JSON格式输出：
{{
  "atoms": [
    {{
      "axiom": "核心概念或事实",
      "methodology": "技术路径或方法",
      "boundary": "适用范围和限制",
      "category": "Method|Definition|Formula|Context|Data|Result|Insight",
      "confidence": 0.95,
      "tags": ["标签1", "标签2"]
    }}
  ]
}}

JSON输出："""

        return prompt

    def _parse_decomposition_response(
        self,
        response: str,
        note_id: str,
        doc_id: str,
    ) -> List[AtomicKnowledge]:
        """解析解构响应"""

        atoms = []

        try:
            # 提取JSON部分
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)

                # 解析atoms数组
                for i, atom_data in enumerate(data.get("atoms", [])):
                    atom = AtomicKnowledge(
                        knowledge_id=f"{note_id}_atom_{i}",
                        original_note_id=note_id,
                        doc_id=doc_id,
                        axiom=atom_data.get("axiom", ""),
                        methodology=atom_data.get("methodology", ""),
                        boundary=atom_data.get("boundary", ""),
                        category=atom_data.get("category", "Insight"),
                        confidence=atom_data.get("confidence", 0.8),
                        tags=atom_data.get("tags", []),
                    )
                    atoms.append(atom)

        except (json.JSONDecodeError, KeyError) as e:
            print(f"[AtomicDecomposer] JSON解析失败: {e}")
            # 创建默认原子知识
            atoms = [
                AtomicKnowledge(
                    knowledge_id=f"{note_id}_atom_0",
                    original_note_id=note_id,
                    doc_id=doc_id,
                    axiom=response[:100],
                    methodology="",
                    boundary="",
                    category="Insight",
                    confidence=0.5,
                    tags=[],
                )
            ]

        return atoms

    def batch_decompose(
        self,
        notes: List[Dict],
        progress_callback=None,
    ) -> List[AtomicDecomposition]:
        """批量解构笔记

        Args:
            notes: 笔记列表，每个包含 {id, content, doc_id}
            progress_callback: 进度回调

        Returns:
            List[AtomicDecomposition]: 解构结果列表
        """
        results = []
        total = len(notes)

        for i, note in enumerate(notes):
            note_id = note.get("id", f"note_{i}")
            content = note.get("content", "")
            doc_id = note.get("doc_id", "")

            if content:
                decomposition = self.decompose(content, note_id, doc_id)
                results.append(decomposition)

            # 进度回调
            if progress_callback:
                progress_callback(i + 1, total)

        return results

    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        return {
            "cache_size": len(self.cache),
            "cached_notes": list(self.cache.keys()),
        }

    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
