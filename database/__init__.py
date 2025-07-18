"""
数据库管理模块 - 通用的SQLite数据库管理系统
支持剧情、角色、知识库等多种数据类型的存储和管理
"""

from .managers.story_manager import StoryManager
from .managers.character_manager import CharacterManager
from .managers.schedule_manager import ScheduleManager
from .managers.base_manager import DatabaseManager

# 全局管理器实例
story_manager = StoryManager()
character_manager = CharacterManager()
schedule_manager = ScheduleManager()
database_manager = DatabaseManager()

__all__ = [
    'StoryManager', 'CharacterManager', 'ScheduleManager', 'DatabaseManager',
    'story_manager', 'character_manager', 'schedule_manager', 'database_manager'
] 