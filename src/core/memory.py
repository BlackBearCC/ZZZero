"""
记忆系统 - 为Agent提供记忆能力
支持短期记忆缓冲、LLM压缩、长期存储和智能检索
"""
import json
import sqlite3
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import asyncio
import logging

from .types import Message, MessageRole

# 尝试相对导入，失败则使用绝对导入
try:
    from ..llm.base import BaseLLMProvider
except ImportError:
    from llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """记忆条目"""
    id: str
    content: str
    timestamp: datetime
    memory_type: str  # 'conversation', 'fact', 'compressed'
    importance: float  # 0.0-1.0 重要性评分
    session_id: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'memory_type': self.memory_type,
            'importance': self.importance,
            'session_id': self.session_id,
            'metadata': json.dumps(self.metadata)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryEntry':
        """从字典创建"""
        return cls(
            id=data['id'],
            content=data['content'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            memory_type=data['memory_type'],
            importance=data['importance'],
            session_id=data['session_id'],
            metadata=json.loads(data['metadata']) if data['metadata'] else {}
        )


class BaseMemoryStore(ABC):
    """记忆存储抽象基类"""
    
    @abstractmethod
    async def save(self, entry: MemoryEntry) -> bool:
        """保存记忆条目"""
        pass
    
    @abstractmethod
    async def get_by_id(self, entry_id: str) -> Optional[MemoryEntry]:
        """根据ID获取记忆条目"""
        pass
    
    @abstractmethod
    async def search(self, query: str, session_id: str, limit: int = 10) -> List[MemoryEntry]:
        """搜索相关记忆"""
        pass
    
    @abstractmethod
    async def get_session_memories(self, session_id: str, limit: int = 50) -> List[MemoryEntry]:
        """获取会话记忆"""
        pass
    
    @abstractmethod
    async def delete_session(self, session_id: str) -> bool:
        """删除会话记忆"""
        pass
    
    @abstractmethod
    async def get_stats(self, session_id: str) -> Dict[str, Any]:
        """获取记忆统计"""
        pass


class SQLiteMemoryStore(BaseMemoryStore):
    """SQLite记忆存储实现"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    importance REAL NOT NULL,
                    session_id TEXT NOT NULL,
                    metadata TEXT
                )
            """)
            
            # 创建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON memories(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance)")
            conn.commit()
    
    async def save(self, entry: MemoryEntry) -> bool:
        """保存记忆条目"""
        try:
            data = entry.to_dict()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO memories 
                    (id, content, timestamp, memory_type, importance, session_id, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    data['id'], data['content'], data['timestamp'],
                    data['memory_type'], data['importance'], 
                    data['session_id'], data['metadata']
                ))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"保存记忆失败: {e}")
            return False
    
    async def get_by_id(self, entry_id: str) -> Optional[MemoryEntry]:
        """根据ID获取记忆条目"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM memories WHERE id = ?", (entry_id,)
                )
                row = cursor.fetchone()
                if row:
                    return MemoryEntry.from_dict(dict(row))
            return None
        except Exception as e:
            logger.error(f"获取记忆失败: {e}")
            return None
    
    async def search(self, query: str, session_id: str, limit: int = 10) -> List[MemoryEntry]:
        """搜索相关记忆（简单文本匹配）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM memories 
                    WHERE session_id = ? AND content LIKE ?
                    ORDER BY importance DESC, timestamp DESC
                    LIMIT ?
                """, (session_id, f"%{query}%", limit))
                
                rows = cursor.fetchall()
                return [MemoryEntry.from_dict(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"搜索记忆失败: {e}")
            return []
    
    async def get_session_memories(self, session_id: str, limit: int = 50) -> List[MemoryEntry]:
        """获取会话记忆"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM memories 
                    WHERE session_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (session_id, limit))
                
                rows = cursor.fetchall()
                return [MemoryEntry.from_dict(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"获取会话记忆失败: {e}")
            return []
    
    async def delete_session(self, session_id: str) -> bool:
        """删除会话记忆"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM memories WHERE session_id = ?", (session_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"删除会话记忆失败: {e}")
            return False
    
    async def get_stats(self, session_id: str) -> Dict[str, Any]:
        """获取记忆统计"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_count,
                        SUM(LENGTH(content)) as total_chars,
                        AVG(importance) as avg_importance,
                        COUNT(CASE WHEN memory_type = 'conversation' THEN 1 END) as conversation_count,
                        COUNT(CASE WHEN memory_type = 'fact' THEN 1 END) as fact_count,
                        COUNT(CASE WHEN memory_type = 'compressed' THEN 1 END) as compressed_count
                    FROM memories WHERE session_id = ?
                """, (session_id,))
                
                row = cursor.fetchone()
                return {
                    'total_memories': row[0] or 0,
                    'total_characters': row[1] or 0,
                    'average_importance': row[2] or 0.0,
                    'conversation_memories': row[3] or 0,
                    'fact_memories': row[4] or 0,
                    'compressed_memories': row[5] or 0
                }
        except Exception as e:
            logger.error(f"获取记忆统计失败: {e}")
            return {}


class MemoryCompressor:
    """记忆压缩器 - 使用LLM压缩和提取记忆"""
    
    def __init__(self, llm: BaseLLMProvider):
        self.llm = llm
    
    async def compress_conversations(self, conversations: List[str], target_ratio: float = 0.3) -> Tuple[str, List[str]]:
        """
        压缩对话历史
        
        Args:
            conversations: 对话列表
            target_ratio: 目标压缩比例（保留30%）
            
        Returns:
            (压缩后的摘要, 提取的事实列表)
        """
        if not conversations:
            return "", []
        
        # 构建压缩提示
        conversations_text = "\n\n".join(conversations)
        
        compress_prompt = f"""
请分析以下对话内容，并完成两个任务：

1. 生成一个简洁的对话摘要，保留关键信息和上下文
2. 提取重要的事实信息，每个事实一行

对话内容：
{conversations_text}

请按以下格式输出：

=== 对话摘要 ===
[简洁的对话摘要，保留关键信息]

=== 重要事实 ===
- [事实1]
- [事实2]
- [事实3]
...

要求：
- 摘要长度约为原文的30%
- 保留所有重要决策、结论和关键信息
- 事实应该是具体、可验证的信息
- 使用中文输出
"""
        
        try:
            # 调用LLM进行压缩
            messages = [Message(role=MessageRole.USER, content=compress_prompt)]
            response = await self.llm.generate(messages)
            
            # 解析响应
            summary, facts = self._parse_compression_response(response.content)
            
            logger.info(f"压缩完成: 原文{len(conversations_text)}字符 -> 摘要{len(summary)}字符")
            return summary, facts
            
        except Exception as e:
            logger.error(f"记忆压缩失败: {e}")
            # 降级处理：简单截取
            fallback_summary = conversations_text[:int(len(conversations_text) * target_ratio)]
            return fallback_summary, []
    
    def _parse_compression_response(self, response: str) -> Tuple[str, List[str]]:
        """解析压缩响应"""
        summary = ""
        facts = []
        
        try:
            # 分割响应
            parts = response.split("=== 重要事实 ===")
            
            if len(parts) >= 2:
                # 提取摘要
                summary_part = parts[0].replace("=== 对话摘要 ===", "").strip()
                summary = summary_part
                
                # 提取事实
                facts_part = parts[1].strip()
                for line in facts_part.split('\n'):
                    line = line.strip()
                    if line.startswith('- '):
                        facts.append(line[2:])  # 移除 "- " 前缀
            else:
                # 如果格式不正确，将整个响应作为摘要
                summary = response.strip()
                
        except Exception as e:
            logger.error(f"解析压缩响应失败: {e}")
            summary = response.strip()
        
        return summary, facts
    
    def calculate_importance(self, content: str, memory_type: str) -> float:
        """计算记忆重要性评分"""
        # 简单的启发式规则
        importance = 0.5  # 基础分数
        
        # 根据类型调整
        if memory_type == 'fact':
            importance += 0.2
        elif memory_type == 'compressed':
            importance += 0.3
        
        # 根据内容长度调整
        if len(content) > 500:
            importance += 0.1
        
        # 根据关键词调整
        important_keywords = ['重要', '关键', '注意', '记住', '总结', '结论']
        for keyword in important_keywords:
            if keyword in content:
                importance += 0.1
                break
        
        return min(1.0, importance)


class ShortTermMemory:
    """短期记忆 - 缓冲区管理"""
    
    def __init__(self, limit: int = 3000):
        self.limit = limit
        self.buffer: List[str] = []
        self.current_size = 0
    
    def add(self, content: str) -> bool:
        """添加内容到缓冲区"""
        content_size = len(content)
        
        # 检查是否会超出限制
        if self.current_size + content_size > self.limit:
            return False  # 需要压缩
        
        self.buffer.append(content)
        self.current_size += content_size
        return True
    
    def get_all(self) -> List[str]:
        """获取所有缓冲内容"""
        return self.buffer.copy()
    
    def clear(self):
        """清空缓冲区"""
        self.buffer.clear()
        self.current_size = 0
    
    def is_full(self) -> bool:
        """检查是否接近满"""
        return self.current_size >= self.limit * 0.8  # 80%时认为接近满
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓冲区统计"""
        return {
            'current_size': self.current_size,
            'limit': self.limit,
            'usage_ratio': self.current_size / self.limit,
            'item_count': len(self.buffer)
        }


class LongTermMemory:
    """长期记忆 - 持久化存储管理"""
    
    def __init__(self, store: BaseMemoryStore):
        self.store = store
    
    async def save_conversation(self, content: str, session_id: str, importance: float = 0.5) -> str:
        """保存对话记忆"""
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            content=content,
            timestamp=datetime.now(),
            memory_type='conversation',
            importance=importance,
            session_id=session_id,
            metadata={}
        )
        
        success = await self.store.save(entry)
        return entry.id if success else ""
    
    async def save_compressed(self, content: str, session_id: str, original_count: int) -> str:
        """保存压缩记忆"""
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            content=content,
            timestamp=datetime.now(),
            memory_type='compressed',
            importance=0.8,  # 压缩记忆通常比较重要
            session_id=session_id,
            metadata={'original_count': original_count}
        )
        
        success = await self.store.save(entry)
        return entry.id if success else ""
    
    async def save_facts(self, facts: List[str], session_id: str) -> List[str]:
        """保存事实记忆"""
        saved_ids = []
        
        for fact in facts:
            entry = MemoryEntry(
                id=str(uuid.uuid4()),
                content=fact,
                timestamp=datetime.now(),
                memory_type='fact',
                importance=0.7,  # 事实记忆重要性较高
                session_id=session_id,
                metadata={}
            )
            
            success = await self.store.save(entry)
            if success:
                saved_ids.append(entry.id)
        
        return saved_ids
    
    async def retrieve_relevant(self, query: str, session_id: str, limit: int = 5) -> List[MemoryEntry]:
        """检索相关记忆"""
        return await self.store.search(query, session_id, limit)
    
    async def get_recent(self, session_id: str, limit: int = 10) -> List[MemoryEntry]:
        """获取最近记忆"""
        return await self.store.get_session_memories(session_id, limit)


class MemoryManager:
    """记忆管理器 - 统一管理短期和长期记忆"""
    
    def __init__(self, 
                 llm: BaseLLMProvider,
                 store: BaseMemoryStore,
                 short_term_limit: int = 3000,
                 session_id: str = None):
        self.llm = llm
        self.session_id = session_id or str(uuid.uuid4())
        
        # 初始化各组件
        self.compressor = MemoryCompressor(llm)
        self.short_term = ShortTermMemory(short_term_limit)
        self.long_term = LongTermMemory(store)
        
        logger.info(f"记忆管理器初始化完成，会话ID: {self.session_id}")
    
    async def add_conversation(self, user_message: str, agent_response: str) -> bool:
        """添加对话到记忆"""
        # 格式化对话
        conversation = f"用户: {user_message}\n助手: {agent_response}"
        
        # 尝试添加到短期记忆
        if self.short_term.add(conversation):
            logger.debug(f"对话已添加到短期记忆，当前大小: {self.short_term.current_size}")
            return True
        else:
            # 短期记忆满了，需要压缩
            logger.info("短期记忆已满，开始压缩...")
            await self._compress_and_store()
            
            # 压缩后再次尝试添加
            if self.short_term.add(conversation):
                logger.info("压缩后成功添加新对话")
                return True
            else:
                logger.error("压缩后仍无法添加对话")
                return False
    
    async def _compress_and_store(self):
        """压缩短期记忆并存储到长期记忆"""
        try:
            # 获取所有短期记忆
            conversations = self.short_term.get_all()
            if not conversations:
                return
            
            # 使用LLM压缩
            compressed_summary, facts = await self.compressor.compress_conversations(conversations)
            
            # 保存压缩摘要
            if compressed_summary:
                await self.long_term.save_compressed(
                    compressed_summary, 
                    self.session_id, 
                    len(conversations)
                )
                logger.info(f"已保存压缩摘要: {len(compressed_summary)}字符")
            
            # 保存提取的事实
            if facts:
                saved_facts = await self.long_term.save_facts(facts, self.session_id)
                logger.info(f"已保存{len(saved_facts)}个事实")
            
            # 清空短期记忆
            self.short_term.clear()
            logger.info("短期记忆已清空")
            
        except Exception as e:
            logger.error(f"压缩和存储失败: {e}")
    
    async def get_context_for_query(self, query: str, max_entries: int = 5) -> str:
        """为查询获取相关上下文"""
        try:
            # 从长期记忆检索相关内容
            relevant_memories = await self.long_term.retrieve_relevant(query, self.session_id, max_entries)
            
            # 获取短期记忆
            short_term_conversations = self.short_term.get_all()
            
            # 构建上下文
            context_parts = []
            
            # 添加相关长期记忆
            if relevant_memories:
                context_parts.append("=== 相关记忆 ===")
                for memory in relevant_memories:
                    context_parts.append(f"[{memory.memory_type}] {memory.content}")
            
            # 添加短期记忆
            if short_term_conversations:
                context_parts.append("\n=== 最近对话 ===")
                # 只取最后几个对话
                recent_conversations = short_term_conversations[-3:]
                context_parts.extend(recent_conversations)
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"获取上下文失败: {e}")
            return ""
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        try:
            # 获取长期记忆统计
            long_term_stats = await self.long_term.store.get_stats(self.session_id)
            
            # 获取短期记忆统计
            short_term_stats = self.short_term.get_stats()
            
            return {
                'session_id': self.session_id,
                'short_term': short_term_stats,
                'long_term': long_term_stats,
                'total_characters': short_term_stats['current_size'] + long_term_stats.get('total_characters', 0)
            }
        except Exception as e:
            logger.error(f"获取记忆统计失败: {e}")
            return {}
    
    async def clear_all(self) -> bool:
        """清空所有记忆"""
        try:
            # 清空短期记忆
            self.short_term.clear()
            
            # 清空长期记忆
            success = await self.long_term.store.delete_session(self.session_id)
            
            logger.info(f"记忆清空{'成功' if success else '失败'}")
            return success
        except Exception as e:
            logger.error(f"清空记忆失败: {e}")
            return False
    
    async def export_data(self) -> Dict[str, Any]:
        """导出记忆数据"""
        try:
            # 获取所有长期记忆
            memories = await self.long_term.get_recent(self.session_id, 1000)
            
            # 获取短期记忆
            short_term_data = self.short_term.get_all()
            
            # 获取统计信息
            stats = await self.get_stats()
            
            return {
                'session_id': self.session_id,
                'export_time': datetime.now().isoformat(),
                'statistics': stats,
                'short_term_memory': short_term_data,
                'long_term_memory': [
                    {
                        'id': memory.id,
                        'content': memory.content,
                        'timestamp': memory.timestamp.isoformat(),
                        'type': memory.memory_type,
                        'importance': memory.importance,
                        'metadata': memory.metadata
                    }
                    for memory in memories
                ]
            }
        except Exception as e:
            logger.error(f"导出记忆数据失败: {e}")
            return {} 