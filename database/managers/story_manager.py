"""
剧情数据库管理器 - 专门处理剧情、小节、角色关联等数据
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from .base_manager import DatabaseManager

logger = logging.getLogger(__name__)

class StoryManager(DatabaseManager):
    """剧情数据库管理器"""
    
    def __init__(self, db_path: str = "workspace/databases/story.db"):
        """初始化剧情数据库"""
        super().__init__(db_path)
    
    def _init_database(self):
        """初始化剧情相关表结构"""
        super()._init_database()
        
        # 创建剧情主表
        self.create_table_if_not_exists("stories", """(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT UNIQUE NOT NULL,
            story_name TEXT NOT NULL,
            story_type TEXT DEFAULT 'daily_life',
            story_length TEXT DEFAULT 'medium',
            relationship_depth TEXT DEFAULT 'casual',
            protagonist TEXT DEFAULT '方知衡',
            selected_characters TEXT,  -- JSON格式存储角色列表
            selected_locations TEXT,   -- JSON格式存储地点列表
            story_summary TEXT,        -- JSON格式存储剧情总结
            main_conflict TEXT,
            emotional_development TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        
        # 创建小节详情表
        self.create_table_if_not_exists("scenes", """(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT NOT NULL,
            scene_id TEXT NOT NULL,
            scene_title TEXT NOT NULL,
            scene_content TEXT NOT NULL,
            location TEXT,
            participants TEXT,  -- JSON格式存储参与角色
            scene_order INTEGER DEFAULT 0,
            scene_metadata TEXT,  -- JSON格式存储额外元数据
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (story_id) REFERENCES stories(story_id) ON DELETE CASCADE,
            UNIQUE(story_id, scene_id)
        )""")
        
        # 创建角色剧情关联表
        self.create_table_if_not_exists("character_stories", """(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_name TEXT NOT NULL,
            story_id TEXT NOT NULL,
            relationship_type TEXT,
            importance_level INTEGER DEFAULT 1,  -- 1-5级重要程度
            character_role TEXT,  -- 在剧情中的角色定位
            interaction_count INTEGER DEFAULT 0,  -- 互动次数
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (story_id) REFERENCES stories(story_id) ON DELETE CASCADE,
            UNIQUE(character_name, story_id)
        )""")
        
        # 创建剧情标签表（用于分类和搜索）
        self.create_table_if_not_exists("story_tags", """(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id TEXT NOT NULL,
            tag_name TEXT NOT NULL,
            tag_category TEXT DEFAULT 'general',  -- 标签分类：theme, mood, genre等
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (story_id) REFERENCES stories(story_id) ON DELETE CASCADE,
            UNIQUE(story_id, tag_name)
        )""")
        
        # 创建索引提高查询性能
        self._create_indexes()
        
        logger.info("剧情数据库表结构初始化完成")
    
    def _create_indexes(self):
        """创建数据库索引"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_stories_protagonist ON stories(protagonist)",
            "CREATE INDEX IF NOT EXISTS idx_stories_type ON stories(story_type)",
            "CREATE INDEX IF NOT EXISTS idx_stories_created_at ON stories(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_scenes_story_id ON scenes(story_id)",
            "CREATE INDEX IF NOT EXISTS idx_scenes_order ON scenes(scene_order)",
            "CREATE INDEX IF NOT EXISTS idx_character_stories_character ON character_stories(character_name)",
            "CREATE INDEX IF NOT EXISTS idx_character_stories_story ON character_stories(story_id)",
            "CREATE INDEX IF NOT EXISTS idx_story_tags_story_id ON story_tags(story_id)",
            "CREATE INDEX IF NOT EXISTS idx_story_tags_category ON story_tags(tag_category)"
        ]
        
        for index_sql in indexes:
            try:
                self.execute_query(index_sql)
            except Exception as e:
                logger.warning(f"创建索引失败: {index_sql} | 错误: {e}")
    
    def save_story_data(self, story_data: Dict[str, Any], config: Dict[str, Any]) -> bool:
        """保存完整的剧情数据到数据库"""
        try:
            # 解析剧情数据
            if isinstance(story_data, dict) and '剧情列表' in story_data:
                story_list = story_data['剧情列表']
            else:
                logger.error("无效的剧情数据格式")
                return False
            
            for story in story_list:
                story_id = story.get('剧情ID', '')
                story_name = story.get('剧情名称', '未命名剧情')
                scenes = story.get('剧情小节', [])
                story_summary_data = story.get('剧情总结', {})
                
                # 插入或更新剧情主表
                story_record = {
                    'story_id': story_id,
                    'story_name': story_name,
                    'story_type': config.get('story_type', 'daily_life'),
                    'story_length': config.get('story_length', 'medium'),
                    'relationship_depth': config.get('relationship_depth', 'casual'),
                    'protagonist': config.get('protagonist', '方知衡'),
                    'selected_characters': json.dumps(config.get('selected_characters', []), ensure_ascii=False),
                    'selected_locations': json.dumps(config.get('selected_locations', []), ensure_ascii=False),
                    'story_summary': json.dumps(story_summary_data, ensure_ascii=False),
                    'main_conflict': story_summary_data.get('主要冲突', ''),
                    'emotional_development': story_summary_data.get('情感发展', ''),
                    'updated_at': datetime.now().isoformat()
                }
                
                # 检查记录是否存在
                existing = self.execute_query(
                    "SELECT id FROM stories WHERE story_id = ?", 
                    (story_id,), 
                    fetch_all=False
                )
                
                if existing:
                    # 更新现有记录
                    self.update_record('stories', story_record, 'story_id = ?', (story_id,))
                else:
                    # 插入新记录
                    self.insert_record('stories', story_record)
                
                # 删除旧的小节数据
                self.delete_record('scenes', 'story_id = ?', (story_id,))
                
                # 插入小节数据
                for idx, scene in enumerate(scenes):
                    scene_id = scene.get('小节ID', f'SCENE_{idx+1:03d}')
                    participants = scene.get('参与角色', [])
                    
                    scene_record = {
                        'story_id': story_id,
                        'scene_id': scene_id,
                        'scene_title': scene.get('小节标题', ''),
                        'scene_content': scene.get('小节内容', ''),
                        'location': scene.get('地点', ''),
                        'participants': json.dumps(participants, ensure_ascii=False),
                        'scene_order': idx + 1,
                        'scene_metadata': json.dumps({
                            'original_index': idx,
                            'content_length': len(scene.get('小节内容', '')),
                            'participant_count': len(participants)
                        }, ensure_ascii=False)
                    }
                    
                    self.insert_record('scenes', scene_record)
                
                # 删除旧的角色关联
                self.delete_record('character_stories', 'story_id = ?', (story_id,))
                
                # 插入角色关联数据
                all_characters = set()
                for scene in scenes:
                    participants = scene.get('参与角色', [])
                    all_characters.update(participants)
                
                for character in all_characters:
                    if character and character.strip():
                        # 计算该角色的出现次数
                        interaction_count = sum(
                            1 for scene in scenes 
                            if character in scene.get('参与角色', [])
                        )
                        
                        # 判断重要程度：主角为5，其他角色根据出现频率
                        if character == config.get('protagonist', '方知衡'):
                            importance = 5
                            character_role = '主角'
                        else:
                            importance = min(5, max(1, interaction_count))
                            character_role = '配角' if interaction_count > 1 else '次要角色'
                        
                        character_story_record = {
                            'character_name': character,
                            'story_id': story_id,
                            'relationship_type': config.get('relationship_depth', 'casual'),
                            'importance_level': importance,
                            'character_role': character_role,
                            'interaction_count': interaction_count
                        }
                        
                        self.insert_record('character_stories', character_story_record)
                
                # 自动生成标签
                self._generate_story_tags(story_id, story, config)
            
            logger.info(f"成功保存 {len(story_list)} 个剧情到数据库")
            return True
            
        except Exception as e:
            logger.error(f"保存剧情数据到数据库失败: {e}", exc_info=True)
            return False
    
    def _generate_story_tags(self, story_id: str, story_data: Dict[str, Any], config: Dict[str, Any]):
        """自动生成剧情标签"""
        try:
            # 删除旧标签
            self.delete_record('story_tags', 'story_id = ?', (story_id,))
            
            tags = []
            
            # 基于配置生成标签
            tags.append({
                'story_id': story_id,
                'tag_name': config.get('story_type', 'daily_life'),
                'tag_category': 'genre'
            })
            
            tags.append({
                'story_id': story_id,
                'tag_name': config.get('story_length', 'medium'),
                'tag_category': 'length'
            })
            
            tags.append({
                'story_id': story_id,
                'tag_name': config.get('relationship_depth', 'casual'),
                'tag_category': 'relationship'
            })
            
            # 基于角色生成标签
            for character in config.get('selected_characters', []):
                tags.append({
                    'story_id': story_id,
                    'tag_name': character,
                    'tag_category': 'character'
                })
            
            # 基于地点生成标签
            for location in config.get('selected_locations', []):
                tags.append({
                    'story_id': story_id,
                    'tag_name': location,
                    'tag_category': 'location'
                })
            
            # 批量插入标签
            for tag in tags:
                try:
                    self.insert_record('story_tags', tag)
                except Exception as e:
                    # 忽略重复标签错误
                    pass
                    
        except Exception as e:
            logger.warning(f"生成剧情标签失败: {e}")
    
    def get_character_stories(self, character_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取指定角色的所有剧情"""
        try:
            sql = """
                SELECT 
                    s.story_id, s.story_name, s.story_type, s.story_length,
                    s.relationship_depth, s.protagonist, s.selected_characters,
                    s.selected_locations, s.main_conflict, s.emotional_development,
                    s.created_at, cs.importance_level, cs.character_role, cs.interaction_count
                FROM stories s
                JOIN character_stories cs ON s.story_id = cs.story_id
                WHERE cs.character_name = ?
                ORDER BY s.created_at DESC
                LIMIT ?
            """
            
            stories = self.execute_query(sql, (character_name, limit))
            
            # 解析JSON字段
            for story in stories:
                story['selected_characters'] = json.loads(story['selected_characters'] or '[]')
                story['selected_locations'] = json.loads(story['selected_locations'] or '[]')
            
            return stories
            
        except Exception as e:
            logger.error(f"获取角色剧情失败: {e}")
            return []
    
    def get_story_scenes(self, story_id: str) -> List[Dict[str, Any]]:
        """获取指定剧情的所有小节"""
        try:
            sql = """
                SELECT 
                    scene_id, scene_title, scene_content, location, 
                    participants, scene_order, scene_metadata, created_at
                FROM scenes
                WHERE story_id = ?
                ORDER BY scene_order ASC
            """
            
            scenes = self.execute_query(sql, (story_id,))
            
            # 解析JSON字段
            for scene in scenes:
                scene['participants'] = json.loads(scene['participants'] or '[]')
                scene['scene_metadata'] = json.loads(scene['scene_metadata'] or '{}')
            
            return scenes
            
        except Exception as e:
            logger.error(f"获取剧情小节失败: {e}")
            return []
    
    def get_all_characters(self) -> List[Dict[str, Any]]:
        """获取数据库中所有角色及其统计信息"""
        try:
            sql = """
                SELECT 
                    character_name,
                    COUNT(DISTINCT story_id) as story_count,
                    SUM(interaction_count) as total_interactions,
                    AVG(importance_level) as avg_importance,
                    GROUP_CONCAT(DISTINCT character_role) as roles
                FROM character_stories 
                GROUP BY character_name
                ORDER BY story_count DESC, total_interactions DESC
            """
            
            characters = self.execute_query(sql)
            
            # 处理结果
            for char in characters:
                char['roles'] = char['roles'].split(',') if char['roles'] else []
                char['avg_importance'] = round(char['avg_importance'], 2)
            
            return characters
            
        except Exception as e:
            logger.error(f"获取角色列表失败: {e}")
            return []
    
    def get_stories_by_filter(self, filters: Dict[str, Any], limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """按条件筛选剧情"""
        try:
            where_clauses = []
            params = []
            
            # 构建WHERE条件
            if filters.get('story_type'):
                where_clauses.append("s.story_type = ?")
                params.append(filters['story_type'])
            
            if filters.get('protagonist'):
                where_clauses.append("s.protagonist = ?")
                params.append(filters['protagonist'])
            
            if filters.get('character_name'):
                where_clauses.append("EXISTS (SELECT 1 FROM character_stories cs WHERE cs.story_id = s.story_id AND cs.character_name = ?)")
                params.append(filters['character_name'])
            
            if filters.get('tag_name'):
                where_clauses.append("EXISTS (SELECT 1 FROM story_tags st WHERE st.story_id = s.story_id AND st.tag_name = ?)")
                params.append(filters['tag_name'])
            
            if filters.get('created_after'):
                where_clauses.append("s.created_at >= ?")
                params.append(filters['created_after'])
            
            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            sql = f"""
                SELECT 
                    s.story_id, s.story_name, s.story_type, s.story_length,
                    s.protagonist, s.main_conflict, s.created_at,
                    (SELECT COUNT(*) FROM scenes sc WHERE sc.story_id = s.story_id) as scene_count,
                    (SELECT GROUP_CONCAT(character_name) FROM character_stories cs WHERE cs.story_id = s.story_id) as characters
                FROM stories s
                WHERE {where_clause}
                ORDER BY s.created_at DESC
                LIMIT ? OFFSET ?
            """
            
            params.extend([limit, offset])
            stories = self.execute_query(sql, tuple(params))
            
            # 处理字符串字段
            for story in stories:
                story['characters'] = story['characters'].split(',') if story['characters'] else []
            
            return stories
            
        except Exception as e:
            logger.error(f"筛选剧情失败: {e}")
            return []
    
    def delete_story(self, story_id: str) -> bool:
        """删除指定剧情（级联删除相关数据）"""
        try:
            affected_rows = self.delete_record('stories', 'story_id = ?', (story_id,))
            
            if affected_rows > 0:
                logger.info(f"成功删除剧情: {story_id}")
                return True
            else:
                logger.warning(f"剧情不存在: {story_id}")
                return False
                
        except Exception as e:
            logger.error(f"删除剧情失败: {e}")
            return False
    
    def update_scene(self, story_id: str, scene_id: str, updates: Dict[str, Any]) -> bool:
        """更新指定小节的信息"""
        try:
            # 处理特殊字段
            if 'participants' in updates:
                updates['participants'] = json.dumps(updates['participants'], ensure_ascii=False)
            
            updates['updated_at'] = datetime.now().isoformat()
            
            affected_rows = self.update_record(
                'scenes', 
                updates, 
                'story_id = ? AND scene_id = ?', 
                (story_id, scene_id)
            )
            
            if affected_rows > 0:
                logger.info(f"成功更新小节: {story_id}/{scene_id}")
                return True
            else:
                logger.warning(f"小节不存在: {story_id}/{scene_id}")
                return False
                
        except Exception as e:
            logger.error(f"更新小节失败: {e}")
            return False
    
    def get_story_statistics(self) -> Dict[str, Any]:
        """获取剧情数据库统计信息"""
        try:
            stats = {}
            
            # 基础统计
            stats['total_stories'] = self.get_record_count('stories')
            stats['total_scenes'] = self.get_record_count('scenes')
            stats['total_characters'] = self.get_record_count('character_stories', 'character_name IS NOT NULL')
            stats['unique_characters'] = len(self.execute_query("SELECT DISTINCT character_name FROM character_stories"))
            
            # 按类型统计
            type_stats = self.execute_query("""
                SELECT story_type, COUNT(*) as count 
                FROM stories 
                GROUP BY story_type
                ORDER BY count DESC
            """)
            stats['by_story_type'] = {row['story_type']: row['count'] for row in type_stats}
            
            # 按主角统计
            protagonist_stats = self.execute_query("""
                SELECT protagonist, COUNT(*) as count 
                FROM stories 
                GROUP BY protagonist
                ORDER BY count DESC
            """)
            stats['by_protagonist'] = {row['protagonist']: row['count'] for row in protagonist_stats}
            
            # 最活跃角色
            active_characters = self.execute_query("""
                SELECT character_name, COUNT(*) as story_count
                FROM character_stories
                GROUP BY character_name
                ORDER BY story_count DESC
                LIMIT 10
            """)
            stats['most_active_characters'] = active_characters
            
            # 最新创建时间
            latest = self.execute_query("SELECT MAX(created_at) as latest FROM stories", fetch_all=False)
            stats['latest_creation'] = latest['latest'] if latest else None
            
            return stats
            
        except Exception as e:
            logger.error(f"获取剧情统计失败: {e}")
            return {}
    
    def export_story_data(self, story_id: str = None, format: str = 'csv') -> str:
        """导出剧情数据"""
        try:
            if story_id:
                # 导出单个剧情
                where_clause = "s.story_id = ?"
                where_params = (story_id,)
                filename_suffix = f"_{story_id}"
            else:
                # 导出所有剧情
                where_clause = "1=1"
                where_params = ()
                filename_suffix = "_all"
            
            if format.lower() == 'csv':
                # CSV格式导出
                sql = f"""
                    SELECT 
                        s.story_name, sc.scene_id, sc.scene_title, sc.scene_content,
                        sc.location, sc.participants, s.story_type, s.protagonist,
                        s.created_at, sc.scene_order
                    FROM stories s
                    JOIN scenes sc ON s.story_id = sc.story_id
                    WHERE {where_clause}
                    ORDER BY s.created_at DESC, sc.scene_order ASC
                """
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"workspace/exports/story_export{filename_suffix}_{timestamp}.csv"
                
                return self.export_table_to_csv(
                    'stories',  # 这里实际会被SQL覆盖
                    output_path,
                    where_clause,
                    where_params
                )
            
            else:
                # JSON格式导出
                stories_data = self.get_stories_by_filter({} if not story_id else {'story_id': story_id})
                
                export_data = {
                    'export_time': datetime.now().isoformat(),
                    'export_type': 'story_data',
                    'stories': []
                }
                
                for story in stories_data:
                    story_detail = {
                        'story_info': story,
                        'scenes': self.get_story_scenes(story['story_id'])
                    }
                    export_data['stories'].append(story_detail)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"workspace/exports/story_export{filename_suffix}_{timestamp}.json"
                
                # 确保目录存在
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
                
                logger.info(f"JSON导出完成: {output_path}")
                return output_path
                
        except Exception as e:
            logger.error(f"导出剧情数据失败: {e}")
            return "" 