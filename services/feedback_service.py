"""
Feedback Service
================
反馈数据存储服务

功能:
- 保存用户反馈到本地文件
- 加载历史反馈数据
- 导出训练数据集
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from models.feedback import RetrievalFeedback, ChatFeedback, FeedbackCollection
from core.config import FEEDBACK_STORAGE_PATH


class FeedbackService:
    """反馈数据存储服务

    存储结构:
    storage/
    └── feedback/
        ├── retrieval/
        │   ├── feedback_20260307_123456.json
        │   └── ...
        ├── chat/
        │   ├── feedback_20260307_123457.json
        │   └── ...
        └── dataset/
            └── training_data_20260307.json
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.base_dir = Path(FEEDBACK_STORAGE_PATH)
        self.retrieval_dir = self.base_dir / "retrieval"
        self.chat_dir = self.base_dir / "chat"
        self.dataset_dir = self.base_dir / "dataset"

        # 确保目录存在
        self.retrieval_dir.mkdir(parents=True, exist_ok=True)
        self.chat_dir.mkdir(parents=True, exist_ok=True)
        self.dataset_dir.mkdir(parents=True, exist_ok=True)

        self._initialized = True
        print(f"[Feedback] 存储目录: {self.base_dir}")

    def save_retrieval_feedback(self, feedback: RetrievalFeedback) -> str:
        """保存检索反馈

        Args:
            feedback: 检索反馈数据

        Returns:
            保存的文件路径
        """
        filename = f"feedback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.retrieval_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(feedback.to_dict(), f, ensure_ascii=False, indent=2)

        print(f"[Feedback] 保存检索反馈: {filepath}")
        return str(filepath)

    def save_chat_feedback(self, feedback: ChatFeedback) -> str:
        """保存对话反馈

        Args:
            feedback: 对话反馈数据

        Returns:
            保存的文件路径
        """
        filename = f"feedback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.chat_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(feedback.to_dict(), f, ensure_ascii=False, indent=2)

        print(f"[Feedback] 保存对话反馈: {filepath}")
        return str(filepath)

    def load_all_retrieval_feedbacks(self) -> List[RetrievalFeedback]:
        """加载所有检索反馈"""
        feedbacks = []
        for filepath in self.retrieval_dir.glob("feedback_*.json"):
            try:
                with open(filepath, encoding="utf-8") as f:
                    data = json.load(f)
                feedbacks.append(RetrievalFeedback.from_dict(data))
            except Exception as e:
                print(f"[Feedback] 加载失败 {filepath}: {e}")
        return feedbacks

    def load_all_chat_feedbacks(self) -> List[ChatFeedback]:
        """加载所有对话反馈"""
        feedbacks = []
        for filepath in self.chat_dir.glob("feedback_*.json"):
            try:
                with open(filepath, encoding="utf-8") as f:
                    data = json.load(f)
                feedbacks.append(ChatFeedback(
                    query=data.get("query", ""),
                    answer=data.get("answer", ""),
                    context_chunks=data.get("context_chunks", []),
                    user_rating=data.get("user_rating", ""),
                    feedback_text=data.get("feedback_text", ""),
                    timestamp=data.get("timestamp", ""),
                ))
            except Exception as e:
                print(f"[Feedback] 加载失败 {filepath}: {e}")
        return feedbacks

    def export_training_dataset(self) -> str:
        """导出训练数据集

        Returns:
            导出的文件路径
        """
        collection = FeedbackCollection(
            retrieval_feedbacks=self.load_all_retrieval_feedbacks(),
            chat_feedbacks=self.load_all_chat_feedbacks(),
        )

        filename = f"training_data_{datetime.now().strftime('%Y%m%d')}.json"
        filepath = self.dataset_dir / filename

        collection.save(str(filepath))
        print(f"[Feedback] 导出训练数据集: {filepath}")
        print(f"[Feedback] 检索数据: {len(collection.retrieval_feedbacks)} 条")
        print(f"[Feedback] 对话数据: {len(collection.chat_feedbacks)} 条")

        return str(filepath)

    def get_stats(self) -> dict:
        """获取反馈统计"""
        retrieval_count = len(list(self.retrieval_dir.glob("feedback_*.json")))
        chat_count = len(list(self.chat_dir.glob("feedback_*.json")))

        # 计算正反馈比例
        feedbacks = self.load_all_retrieval_feedbacks()
        positive_count = sum(1 for f in feedbacks if f.user_rating == "like")

        return {
            "retrieval_count": retrieval_count,
            "chat_count": chat_count,
            "positive_ratio": positive_count / max(len(feedbacks), 1),
            "storage_path": str(self.base_dir),
        }

    def clear_all(self):
        """清空所有反馈数据"""
        import shutil

        for directory in [self.retrieval_dir, self.chat_dir, self.dataset_dir]:
            if directory.exists():
                shutil.rmtree(directory)
                directory.mkdir(parents=True, exist_ok=True)

        print("[Feedback] 已清空所有反馈数据")


# 全局实例
feedback_service = FeedbackService()


def save_feedback(feedback: RetrievalFeedback) -> str:
    """保存反馈数据的便捷函数"""
    return feedback_service.save_retrieval_feedback(feedback)


def load_feedbacks() -> List[RetrievalFeedback]:
    """加载所有反馈数据"""
    return feedback_service.load_all_retrieval_feedbacks()


def export_training_data() -> str:
    """导出训练数据"""
    return feedback_service.export_training_dataset()


def get_feedback_stats() -> dict:
    """获取反馈统计"""
    return feedback_service.get_stats()
