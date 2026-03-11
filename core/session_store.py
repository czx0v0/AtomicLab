"""
会话隔离存储模块
================
支持多用户 Demo 场景，数据按 session_id 隔离，默认30分钟后自动清理
参考 AtomicLab/modelspace-deploy/aether_engine/core/session_store.py 改进版
"""
import os
import time
import shutil
import threading
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger("atomic_lab.session")

# ModelScope 创空间使用持久化路径，本地使用项目相对路径
try:
    from core.config import IN_MODELSCOPE_SPACE
except ImportError:
    IN_MODELSCOPE_SPACE = False

if IN_MODELSCOPE_SPACE:
    SESSION_ROOT = Path("/mnt/workspace/sessions")
else:
    SESSION_ROOT = Path("storage/sessions")

SESSION_ROOT.mkdir(parents=True, exist_ok=True)

# 会话过期时间（秒）- 支持环境变量配置
SESSION_EXPIRE_SECONDS = int(os.environ.get("SESSION_TIMEOUT", "1800"))  # 默认30分钟

# 内存中的会话元数据
_session_metadata: Dict[str, dict] = {}
_lock = threading.Lock()


def get_session_dir(session_id: str) -> Path:
    """获取会话数据目录"""
    return SESSION_ROOT / session_id


def init_session(session_id: str) -> Path:
    """
    初始化会话目录，记录活跃时间
    
    Returns:
        会话目录路径
    """
    with _lock:
        session_dir = get_session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # 预创建子目录
        (session_dir / "faiss").mkdir(exist_ok=True)
        (session_dir / "bm25").mkdir(exist_ok=True)
        
        _session_metadata[session_id] = {
            "created_at": datetime.utcnow(),
            "last_active": datetime.utcnow(),
            "dir": str(session_dir),
        }
        logger.info(f"[Session] 初始化会话: {session_id} -> {session_dir}")
        return session_dir


def touch_session(session_id: str):
    """更新会话活跃时间"""
    with _lock:
        if session_id in _session_metadata:
            _session_metadata[session_id]["last_active"] = datetime.utcnow()


def get_session_path(session_id: str, *paths: str) -> Path:
    """获取会话内的文件路径，同时更新活跃时间"""
    touch_session(session_id)
    return get_session_dir(session_id).joinpath(*paths)


def is_session_valid(session_id: str) -> bool:
    """检查会话是否有效（未过期）"""
    with _lock:
        if session_id not in _session_metadata:
            # 检查目录是否存在（可能是服务重启后的旧会话）
            session_dir = get_session_dir(session_id)
            if session_dir.exists():
                # 恢复会话元数据
                _session_metadata[session_id] = {
                    "created_at": datetime.utcnow(),
                    "last_active": datetime.utcnow(),
                    "dir": str(session_dir),
                }
                return True
            return False
        
        last_active = _session_metadata[session_id]["last_active"]
        return datetime.utcnow() - last_active <= timedelta(seconds=SESSION_EXPIRE_SECONDS)


def get_active_session_ids() -> list:
    """获取所有活跃会话ID"""
    with _lock:
        return [
            sid for sid, meta in _session_metadata.items()
            if datetime.utcnow() - meta["last_active"] <= timedelta(seconds=SESSION_EXPIRE_SECONDS)
        ]


def cleanup_expired_sessions():
    """清理过期会话数据"""
    with _lock:
        now = datetime.utcnow()
        expired = [
            sid for sid, meta in list(_session_metadata.items())
            if now - meta["last_active"] > timedelta(seconds=SESSION_EXPIRE_SECONDS)
        ]
        
        for session_id in expired:
            try:
                session_dir = get_session_dir(session_id)
                if session_dir.exists():
                    shutil.rmtree(session_dir)
                del _session_metadata[session_id]
                logger.info(f"[Session] 已清理过期会话: {session_id}")
            except Exception as e:
                logger.error(f"[Session] 清理会话失败 {session_id}: {e}")
    
    if expired:
        logger.info(f"[Session] 共清理 {len(expired)} 个过期会话")


def cleanup_all_sessions():
    """清理所有会话数据（服务重启时调用）"""
    try:
        for session_dir in SESSION_ROOT.iterdir():
            if session_dir.is_dir():
                shutil.rmtree(session_dir)
                logger.info(f"[Session] 清理旧会话: {session_dir.name}")
        _session_metadata.clear()
        logger.info("[Session] 所有旧会话已清理")
    except Exception as e:
        logger.error(f"[Session] 清理所有会话失败: {e}")


def start_cleanup_scheduler(interval_seconds: int = 300):
    """
    启动定时清理任务
    
    Args:
        interval_seconds: 检查间隔（默认5分钟）
    """
    def cleanup_loop():
        while True:
            time.sleep(interval_seconds)
            try:
                cleanup_expired_sessions()
            except Exception as e:
                logger.error(f"[Session] 清理任务出错: {e}")
    
    thread = threading.Thread(target=cleanup_loop, daemon=True)
    thread.start()
    logger.info(f"[Session] 清理调度器已启动，间隔 {interval_seconds}s，超时 {SESSION_EXPIRE_SECONDS}s")


class SessionDataStore:
    """
    会话内存数据存储
    用于保存笔记、文档元数据等轻量级数据
    """
    
    _memory_store: Dict[str, Dict[str, Any]] = {}
    
    @classmethod
    def get(cls, session_id: str, key: str, default=None):
        """获取会话数据"""
        touch_session(session_id)
        return cls._memory_store.get(session_id, {}).get(key, default)
    
    @classmethod
    def set(cls, session_id: str, key: str, value: Any):
        """设置会话数据"""
        touch_session(session_id)
        if session_id not in cls._memory_store:
            cls._memory_store[session_id] = {}
        cls._memory_store[session_id][key] = value
    
    @classmethod
    def delete(cls, session_id: str, key: str):
        """删除指定键"""
        touch_session(session_id)
        if session_id in cls._memory_store:
            cls._memory_store[session_id].pop(key, None)
    
    @classmethod
    def cleanup_session(cls, session_id: str):
        """清理会话内存数据"""
        cls._memory_store.pop(session_id, None)
