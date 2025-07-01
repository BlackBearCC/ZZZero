"""
角色数据库管理器 - 专门处理角色信息、关系网络等数据
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from .base_manager import DatabaseManager

logger = logging.getLogger(__name__)

class CharacterManager(DatabaseManager):
    """角色数据库管理器"""
    
    def __init__(self, db_path: str = "workspace/databases/character.db"):
        """初始化角色数据库"""
        super().__init__(db_path)
    
    def _init_database(self):
        """初始化角色相关表结构"""
        super()._init_database()
        
        # 创建角色基础信息表
        self.create_table_if_not_exists("characters", """(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id TEXT UNIQUE NOT NULL,
            character_name TEXT NOT NULL,
            age TEXT,
            personality TEXT,
            description TEXT,
            backstory TEXT,
            appearance TEXT,
            skills TEXT,  -- JSON格式存储技能列表
            habits TEXT,  -- JSON格式存储习惯列表
            dialogue_style TEXT,
            motivations TEXT,  -- JSON格式存储动机目标
            locations TEXT,  -- JSON格式存储活动地点
            plots TEXT,  -- JSON格式存储可触发剧情
            relationships TEXT,  -- JSON格式存储人际关系
            extra_data TEXT,  -- JSON格式存储额外数据
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        
        # 创建角色关系表
        self.create_table_if_not_exists("character_relationships", """(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_a TEXT NOT NULL,
            character_b TEXT NOT NULL,
            relationship_type TEXT NOT NULL,
            relationship_description TEXT,
            intimacy_level INTEGER DEFAULT 1,  -- 1-5级亲密度
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (character_a) REFERENCES characters(character_id),
            FOREIGN KEY (character_b) REFERENCES characters(character_id),
            UNIQUE(character_a, character_b, relationship_type)
        )""")
        
        # 创建索引
        self._create_indexes()
        
        logger.info("角色数据库表结构初始化完成")
    
    def _create_indexes(self):
        """创建数据库索引"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_characters_name ON characters(character_name)",
            "CREATE INDEX IF NOT EXISTS idx_relationships_a ON character_relationships(character_a)",
            "CREATE INDEX IF NOT EXISTS idx_relationships_b ON character_relationships(character_b)",
        ]
        
        for index_sql in indexes:
            try:
                self.execute_query(index_sql)
            except Exception as e:
                logger.warning(f"创建索引失败: {index_sql} | 错误: {e}")
    
    def save_character(self, character_data: Dict[str, Any]) -> bool:
        """保存角色信息"""
        try:
            character_id = character_data.get('character_id') or character_data.get('character_name', '')
            
            if not character_id:
                raise ValueError("角色ID或名称不能为空")
            
            # 处理JSON字段
            record = {
                'character_id': character_id,
                'character_name': character_data.get('character_name', character_id),
                'age': character_data.get('age', ''),
                'personality': character_data.get('personality', ''),
                'description': character_data.get('description', ''),
                'backstory': character_data.get('backstory', ''),
                'appearance': character_data.get('appearance', ''),
                'skills': json.dumps(character_data.get('skills', []), ensure_ascii=False),
                'habits': json.dumps(character_data.get('habits', []), ensure_ascii=False),
                'dialogue_style': character_data.get('dialogue_style', ''),
                'motivations': json.dumps(character_data.get('motivations', []), ensure_ascii=False),
                'locations': json.dumps(character_data.get('locations', []), ensure_ascii=False),
                'plots': json.dumps(character_data.get('plots', []), ensure_ascii=False),
                'relationships': json.dumps(character_data.get('relationships', {}), ensure_ascii=False),
                'extra_data': json.dumps(character_data.get('extra_data', {}), ensure_ascii=False),
                'updated_at': datetime.now().isoformat()
            }
            
            # 检查角色是否存在
            existing = self.execute_query(
                "SELECT id FROM characters WHERE character_id = ?",
                (character_id,),
                fetch_all=False
            )
            
            if existing:
                # 更新现有角色
                self.update_record('characters', record, 'character_id = ?', (character_id,))
            else:
                # 插入新角色
                self.insert_record('characters', record)
            
            logger.info(f"成功保存角色: {character_id}")
            return True
            
        except Exception as e:
            logger.error(f"保存角色失败: {e}")
            return False
    
    def get_character(self, character_id: str) -> Dict[str, Any]:
        """获取角色详细信息"""
        try:
            sql = "SELECT * FROM characters WHERE character_id = ? OR character_name = ?"
            result = self.execute_query(sql, (character_id, character_id), fetch_all=False)
            
            if result:
                # 解析JSON字段
                for field in ['skills', 'habits', 'motivations', 'locations', 'plots', 'relationships', 'extra_data']:
                    if result[field]:
                        result[field] = json.loads(result[field])
                    else:
                        result[field] = [] if field in ['skills', 'habits', 'motivations', 'locations', 'plots'] else {}
            
            return result or {}
            
        except Exception as e:
            logger.error(f"获取角色信息失败: {e}")
            return {}
    
    def get_all_characters(self) -> List[Dict[str, Any]]:
        """获取所有角色信息"""
        try:
            sql = "SELECT * FROM characters ORDER BY character_name"
            results = self.execute_query(sql)
            
            for result in results:
                # 解析JSON字段
                for field in ['skills', 'habits', 'motivations', 'locations', 'plots', 'relationships', 'extra_data']:
                    if result[field]:
                        result[field] = json.loads(result[field])
                    else:
                        result[field] = [] if field in ['skills', 'habits', 'motivations', 'locations', 'plots'] else {}
            
            return results
            
        except Exception as e:
            logger.error(f"获取角色列表失败: {e}")
            return [] 