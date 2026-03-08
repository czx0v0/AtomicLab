"""
Section Summarizer Service
==========================
章节摘要生成服务 - 为RAG检索提供辅助信息

Features:
- 基于LLM的章节摘要生成
- 缓存机制避免重复生成
- 支持批量生成所有章节摘要
"""

from typing import Dict, Optional, List
from dataclasses import dataclass
import hashlib
import json

from agents.base import call_llm


@dataclass
class SectionSummary:
    """章节摘要数据结构"""

    section_id: str
    heading: str
    summary: str
    key_points: List[str]
    word_count: int

    def to_dict(self) -> dict:
        return {
            "section_id": self.section_id,
            "heading": self.heading,
            "summary": self.summary,
            "key_points": self.key_points,
            "word_count": self.word_count,
        }


class SectionSummarizer:
    """章节摘要生成器

    为文档章节生成简洁摘要，用于RAG检索辅助信息。
    摘要包含：
    - 2-3句话的章节概述
    - 3-5个关键要点
    - 字数统计
    """

    def __init__(self, use_cache: bool = True):
        """初始化摘要生成器

        Args:
            use_cache: 是否启用缓存（避免重复生成）
        """
        self.use_cache = use_cache
        self.cache: Dict[str, SectionSummary] = {}

    def _generate_cache_key(self, section_content: str, section_name: str) -> str:
        """生成缓存键"""
        content_hash = hashlib.md5(
            f"{section_name}:{section_content}".encode()
        ).hexdigest()
        return f"summary_{content_hash}"

    def summarize_section(
        self,
        section_content: str,
        section_name: str,
        section_id: str = "",
        max_content_length: int = 1500,
    ) -> SectionSummary:
        """为章节生成摘要

        Args:
            section_content: 章节内容
            section_name: 章节名称
            section_id: 章节ID（可选）
            max_content_length: 最大内容长度（超过会截断）

        Returns:
            SectionSummary: 章节摘要对象
        """
        # 检查缓存
        if self.use_cache:
            cache_key = self._generate_cache_key(section_content, section_name)
            if cache_key in self.cache:
                return self.cache[cache_key]

        # 截断过长内容
        content = section_content[:max_content_length]
        word_count = len(section_content.split())

        # 构建提示词
        prompt = f"""请为以下学术文献章节生成简洁摘要。

章节名称：{section_name}

章节内容：
{content}

请按照以下格式输出（JSON格式）：
{{
  "summary": "2-3句话的章节概述",
  "key_points": ["要点1", "要点2", "要点3"]
}}

注意：
1. 摘要应简洁明了，突出章节核心内容
2. 关键要点提取3-5个最重要的信息
3. 使用学术性语言，保持客观准确

JSON输出："""

        try:
            # 调用LLM
            response = call_llm(
                system_prompt="你是学术文献摘要生成专家。请为给定的章节内容生成简洁摘要。",
                user_prompt=prompt,
                max_tokens=300,
                temperature=0.3,
            )

            # 解析JSON响应
            summary = self._parse_summary_response(
                response, section_id, section_name, word_count, cache_key
            )

            # 缓存结果
            if self.use_cache and summary:
                self.cache[cache_key] = summary

            return summary

        except Exception as e:
            print(f"[SectionSummarizer] 生成摘要失败: {e}")
            # 返回基础摘要
            return SectionSummary(
                section_id=section_id,
                heading=section_name,
                summary=section_content[:200] + "...",
                key_points=[],
                word_count=word_count,
            )

    def _parse_summary_response(
        self,
        response: str,
        section_id: str,
        section_name: str,
        word_count: int,
        cache_key: str,
    ) -> SectionSummary:
        """解析LLM返回的摘要响应，支持多种格式"""
        import re

        # 尝试提取JSON部分
        json_start = response.find("{")
        json_end = response.rfind("}") + 1

        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]

            try:
                # 尝试直接解析
                data = json.loads(json_str)
                return SectionSummary(
                    section_id=section_id or cache_key if self.use_cache else "",
                    heading=section_name,
                    summary=data.get("summary", ""),
                    key_points=data.get("key_points", []),
                    word_count=word_count,
                )
            except json.JSONDecodeError as e:
                print(f"[SectionSummarizer] JSON解析失败: {e}, 尝试修复...")

                # 尝试修复常见JSON问题
                # 1. 修复单引号
                json_str_fixed = json_str.replace("'", '"')
                # 2. 修复缺少引号的key
                json_str_fixed = re.sub(r"(\w+)\s*:", r'"\1":', json_str_fixed)
                # 3. 修复尾部逗号
                json_str_fixed = re.sub(r",\s*}", "}", json_str_fixed)
                json_str_fixed = re.sub(r",\s*]", "]", json_str_fixed)

                try:
                    data = json.loads(json_str_fixed)
                    return SectionSummary(
                        section_id=section_id or cache_key if self.use_cache else "",
                        heading=section_name,
                        summary=data.get("summary", ""),
                        key_points=data.get("key_points", []),
                        word_count=word_count,
                    )
                except:
                    pass

        # JSON解析完全失败，尝试从文本中提取
        summary_text = ""
        key_points = []

        # 尝试匹配 summary 字段
        summary_match = re.search(
            r'"?summary"?\s*[:：]\s*["\']?([^"\'\n}]+)', response, re.IGNORECASE
        )
        if summary_match:
            summary_text = summary_match.group(1).strip()

        # 尝试匹配 key_points 字段
        points_match = re.search(
            r'"?key_?points"?\s*[:：]\s*\[([^\]]+)\]', response, re.IGNORECASE
        )
        if points_match:
            points_str = points_match.group(1)
            # 提取每个要点
            key_points = re.findall(r'"([^"]+)"', points_str)

        # 如果都没有提取到，使用原始响应
        if not summary_text:
            summary_text = response[:200]

        return SectionSummary(
            section_id=section_id or cache_key if self.use_cache else "",
            heading=section_name,
            summary=summary_text,
            key_points=key_points,
            word_count=word_count,
        )

    def batch_summarize(
        self, sections: List[Dict], progress_callback=None
    ) -> Dict[str, SectionSummary]:
        """批量生成章节摘要

        Args:
            sections: 章节列表，每个章节包含 {id, heading, content}
            progress_callback: 进度回调函数 callback(current, total)

        Returns:
            Dict[section_id, SectionSummary]: 章节ID到摘要的映射
        """
        results = {}
        total = len(sections)

        for i, section in enumerate(sections):
            section_id = section.get("section_id", f"sec-{i}")
            heading = section.get("heading", "")
            content = section.get("content", "")

            if content and heading:
                summary = self.summarize_section(
                    section_content=content,
                    section_name=heading,
                    section_id=section_id,
                )
                results[section_id] = summary

            # 进度回调
            if progress_callback:
                progress_callback(i + 1, total)

        return results

    def get_cached_summaries(self) -> Dict[str, SectionSummary]:
        """获取所有缓存的摘要"""
        return self.cache.copy()

    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
