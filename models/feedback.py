"""
Feedback Models
===============
用户反馈数据模型 - 用于RAG模型微调

收集用户对AI回答的反馈，用于后续模型微调:
- Embedding模型微调: 提升语义检索精度
- Reranker模型微调: 提升重排序准确性
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
import json


@dataclass
class RetrievalFeedback:
    """检索反馈数据

    记录用户对检索结果的反馈，用于训练更好的检索模型。

    Attributes:
        query: 用户查询
        retrieved_chunk_ids: 检索到的chunk ID列表
        retrieved_contents: 检索到的chunk内容列表
        user_rating: 用户评分 ("like" / "dislike")
        timestamp: 时间戳
        correct_chunk_id: 用户选择的正确chunk (可选)
        session_id: 会话ID
        doc_ids: 相关文档ID列表
    """

    query: str
    retrieved_chunk_ids: List[str] = field(default_factory=list)
    retrieved_contents: List[str] = field(default_factory=list)
    user_rating: str = ""  # "like" / "dislike"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # 可选字段
    correct_chunk_id: Optional[str] = None
    session_id: str = ""
    doc_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "query": self.query,
            "retrieved_chunk_ids": self.retrieved_chunk_ids,
            "retrieved_contents": self.retrieved_contents,
            "user_rating": self.user_rating,
            "timestamp": self.timestamp,
            "correct_chunk_id": self.correct_chunk_id,
            "session_id": self.session_id,
            "doc_ids": self.doc_ids,
        }

    def to_training_pair(self) -> dict:
        """转换为训练数据格式

        用于sentence-transformers微调:
        - positive: 正样本 (用户满意的chunk)
        - negatives: 负样本 (用户不满意的chunk)
        - label: 标签 (1=满意, 0=不满意)
        """
        # 确定正样本
        if self.correct_chunk_id:
            positive = self.correct_chunk_id
        elif self.retrieved_chunk_ids:
            positive = self.retrieved_chunk_ids[0]
        else:
            positive = ""

        # 确定负样本
        negatives = [
            cid for cid in self.retrieved_chunk_ids[1:]
            if cid != self.correct_chunk_id
        ]

        return {
            "query": self.query,
            "positive": positive,
            "positives": [positive] if positive else [],
            "negatives": negatives,
            "label": 1 if self.user_rating == "like" else 0,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RetrievalFeedback":
        """从字典创建"""
        return cls(
            query=d.get("query", ""),
            retrieved_chunk_ids=d.get("retrieved_chunk_ids", []),
            retrieved_contents=d.get("retrieved_contents", []),
            user_rating=d.get("user_rating", ""),
            timestamp=d.get("timestamp", datetime.now().isoformat()),
            correct_chunk_id=d.get("correct_chunk_id"),
            session_id=d.get("session_id", ""),
            doc_ids=d.get("doc_ids", []),
        )


@dataclass
class ChatFeedback:
    """对话反馈数据

    记录用户对AI回答的完整反馈，包括:
    - 问题
    - AI回答
    - 用户评分
    - 检索上下文
    """

    query: str
    answer: str
    context_chunks: List[str] = field(default_factory=list)
    user_rating: str = ""
    feedback_text: str = ""  # 用户文字反馈
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # 检索元信息
    retrieval_method: str = ""  # "semantic" / "keyword" / "hybrid"
    reranked: bool = False
    context_count: int = 0

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "answer": self.answer,
            "context_chunks": self.context_chunks,
            "user_rating": self.user_rating,
            "feedback_text": self.feedback_text,
            "timestamp": self.timestamp,
            "retrieval_method": self.retrieval_method,
            "reranked": self.reranked,
            "context_count": self.context_count,
        }

    def to_training_format(self) -> dict:
        """转换为RLHF/DPO训练格式"""
        return {
            "prompt": self.query,
            "response": self.answer,
            "context": "\n".join(self.context_chunks),
            "rating": self.user_rating,
            "feedback": self.feedback_text,
        }


@dataclass
class FeedbackCollection:
    """反馈数据集合"""

    retrieval_feedbacks: List[RetrievalFeedback] = field(default_factory=list)
    chat_feedbacks: List[ChatFeedback] = field(default_factory=list)

    def add_retrieval_feedback(self, feedback: RetrievalFeedback):
        """添加检索反馈"""
        self.retrieval_feedbacks.append(feedback)

    def add_chat_feedback(self, feedback: ChatFeedback):
        """添加对话反馈"""
        self.chat_feedbacks.append(feedback)

    def to_training_dataset(self) -> dict:
        """导出为训练数据集"""
        return {
            "retrieval_data": [f.to_training_pair() for f in self.retrieval_feedbacks],
            "chat_data": [f.to_training_format() for f in self.chat_feedbacks],
            "stats": {
                "total_retrieval": len(self.retrieval_feedbacks),
                "total_chat": len(self.chat_feedbacks),
                "positive_ratio": sum(1 for f in self.retrieval_feedbacks if f.user_rating == "like") / max(len(self.retrieval_feedbacks), 1),
            },
        }

    def save(self, filepath: str):
        """保存到文件"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_training_dataset(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, filepath: str) -> "FeedbackCollection":
        """从文件加载"""
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        collection = cls()
        for item in data.get("retrieval_data", []):
            collection.add_retrieval_feedback(RetrievalFeedback.from_dict(item))

        return collection
