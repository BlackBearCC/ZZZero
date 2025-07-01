"""日程数据库管理器 - 专门处理日程、时间段、角色安排等数据"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from calendar import monthrange
import re

from .base_manager import DatabaseManager

logger = logging.getLogger(__name__)

class ScheduleManager(DatabaseManager):
    """日程数据库管理器"""
    
    def __init__(self, db_path: str = "workspace/databases/schedule.db"):
        """初始化日程数据库"""
        super().__init__(db_path)
    
    def _init_database(self):
        """初始化日程相关表结构"""
        super()._init_database()
        
        # 创建日程主表
        self.create_table_if_not_exists("schedules", """(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id TEXT UNIQUE NOT NULL,
            schedule_name TEXT NOT NULL,
            schedule_type TEXT DEFAULT 'weekly',  -- weekly, daily, monthly
            protagonist TEXT DEFAULT '方知衡',
            start_date TEXT NOT NULL,  -- YYYY-MM-DD格式
            end_date TEXT NOT NULL,    -- YYYY-MM-DD格式
            total_days INTEGER NOT NULL,
            description TEXT,
            weekly_plan TEXT,  -- 周期计划
            config_data TEXT,  -- JSON格式存储配置信息
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        
        # 创建日程详情表（每日安排）
        self.create_table_if_not_exists("schedule_days", """(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id TEXT NOT NULL,
            day_date TEXT NOT NULL,     -- YYYY-MM-DD格式
            day_number INTEGER NOT NULL, -- 第几天（1开始）
            weekday INTEGER NOT NULL,    -- 星期几（0=周一，6=周日）
            is_holiday INTEGER DEFAULT 0, -- 是否节假日
            holiday_name TEXT,           -- 节假日名称
            lunar_date TEXT,             -- 农历日期
            weather_info TEXT,           -- 天气信息（可选）
            daily_theme TEXT,            -- 当日主题
            daily_plan TEXT,             -- 每日计划（角色预计要做什么）
            daily_summary TEXT,          -- 当日总结（实际发生的事情）
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (schedule_id) REFERENCES schedules(schedule_id)
        )""")
        
        # 创建时间段表（每日5个时间段）
        self.create_table_if_not_exists("time_slots", """(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id TEXT NOT NULL,
            day_date TEXT NOT NULL,
            slot_number INTEGER NOT NULL,  -- 时间段编号（1-5）
            slot_name TEXT NOT NULL,       -- 时间段名称（早晨、上午、下午、傍晚、夜晚）
            start_time TEXT NOT NULL,      -- 开始时间（HH:MM格式）
            end_time TEXT NOT NULL,        -- 结束时间（HH:MM格式）
            assigned_character TEXT,       -- 安排的角色
            activity_type TEXT,            -- 活动类型
            location TEXT,                 -- 活动地点
            story_content TEXT,            -- 故事内容
            story_id TEXT,                 -- 关联的剧情ID（可选）
            importance_level INTEGER DEFAULT 3, -- 重要程度（1-5）
            mood_tone TEXT DEFAULT 'neutral',   -- 情感基调
            interaction_level TEXT DEFAULT 'normal', -- 互动程度
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (schedule_id) REFERENCES schedules(schedule_id)
        )""")
        
        # 创建角色安排统计表
        self.create_table_if_not_exists("character_assignments", """(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id TEXT NOT NULL,
            character_name TEXT NOT NULL,
            total_slots INTEGER DEFAULT 0,     -- 总安排次数
            night_slots INTEGER DEFAULT 0,     -- 夜间时段次数
            morning_slots INTEGER DEFAULT 0,   -- 上午时段次数
            noon_slots INTEGER DEFAULT 0,      -- 中午时段次数
            afternoon_slots INTEGER DEFAULT 0, -- 下午时段次数
            evening_slots INTEGER DEFAULT 0,   -- 晚上时段次数
            avg_importance REAL DEFAULT 3.0,   -- 平均重要程度
            last_assigned_date TEXT,           -- 最后安排日期
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (schedule_id) REFERENCES schedules(schedule_id)
        )""")
        
        # 创建节假日表
        self.create_table_if_not_exists("holidays", """(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            holiday_date TEXT NOT NULL,    -- YYYY-MM-DD格式
            holiday_name TEXT NOT NULL,    -- 节假日名称
            holiday_type TEXT NOT NULL,    -- 节假日类型（national, traditional, international）
            is_lunar INTEGER DEFAULT 0,   -- 是否农历节日
            lunar_date TEXT,               -- 农历日期（如果是农历节日）
            description TEXT,              -- 节假日描述
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        
        # 创建索引
        self.execute_query("CREATE INDEX IF NOT EXISTS idx_schedule_days_date ON schedule_days(day_date)")
        self.execute_query("CREATE INDEX IF NOT EXISTS idx_time_slots_date ON time_slots(day_date)")
        self.execute_query("CREATE INDEX IF NOT EXISTS idx_time_slots_character ON time_slots(assigned_character)")
        self.execute_query("CREATE INDEX IF NOT EXISTS idx_holidays_date ON holidays(holiday_date)")
        
        # 添加新字段（如果不存在）
        self._add_missing_columns()
        
        logger.info("日程数据库表结构初始化完成")
    
    def _add_missing_columns(self):
        """添加缺失的列（用于数据库升级）"""
        try:
            # 添加weekly_plan字段到schedules表
            try:
                self.execute_query("ALTER TABLE schedules ADD COLUMN weekly_plan TEXT")
                logger.info("已添加weekly_plan字段到schedules表")
            except Exception:
                # 字段可能已存在，忽略错误
                pass
            
            # 添加daily_plan字段到schedule_days表
            try:
                self.execute_query("ALTER TABLE schedule_days ADD COLUMN daily_plan TEXT")
                logger.info("已添加daily_plan字段到schedule_days表")
            except Exception:
                # 字段可能已存在，忽略错误
                pass
                
        except Exception as e:
            logger.warning(f"添加新字段时出现问题（可能字段已存在）: {e}")
    
    def save_schedule_data(self, schedule_data: Dict[str, Any], config: Dict[str, Any]) -> bool:
        """保存完整的日程数据到数据库"""
        try:
            schedule_id = schedule_data.get('schedule_id', '')
            schedule_name = schedule_data.get('schedule_name', '未命名日程')
            start_date = schedule_data.get('start_date', '')
            end_date = schedule_data.get('end_date', '')
            total_days = schedule_data.get('total_days', 0)
            
            # 保存主日程记录
            schedule_record = {
                'schedule_id': schedule_id,
                'schedule_name': schedule_name,
                'schedule_type': config.get('schedule_type', 'weekly'),
                'protagonist': config.get('protagonist', '方知衡'),
                'start_date': start_date,
                'end_date': end_date,
                'total_days': total_days,
                'description': schedule_data.get('description', ''),
                'weekly_plan': schedule_data.get('weekly_plan', ''),
                'config_data': json.dumps(config, ensure_ascii=False),
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            self.insert_record('schedules', schedule_record)
            logger.info(f"保存日程主记录: {schedule_id}")
            
            # 保存每日安排
            daily_schedules = schedule_data.get('daily_schedules', [])
            for day_data in daily_schedules:
                self._save_daily_schedule(schedule_id, day_data)
            
            # 更新角色安排统计
            self._update_character_assignments(schedule_id)
            
            logger.info(f"成功保存日程数据: {schedule_id}，包含 {len(daily_schedules)} 天的安排")
            return True
            
        except Exception as e:
            logger.error(f"保存日程数据失败: {e}")
            return False
    
    def _save_daily_schedule(self, schedule_id: str, day_data: Dict[str, Any]):
        """保存单日安排数据"""
        try:
            # 计算weekday（如果没有提供）
            weekday = day_data.get('weekday', 0)
            if weekday == 0 and day_data.get('date'):
                try:
                    date_obj = datetime.strptime(day_data['date'], '%Y-%m-%d')
                    weekday = date_obj.weekday()  # 0=周一，6=周日
                except:
                    weekday = 0
            
            # 保存日程详情
            day_record = {
                'schedule_id': schedule_id,
                'day_date': day_data.get('date', ''),
                'day_number': day_data.get('day_number', 0),
                'weekday': weekday,
                'is_holiday': 1 if day_data.get('is_holiday', False) else 0,
                'holiday_name': day_data.get('holiday_name', ''),
                'lunar_date': day_data.get('lunar_date', ''),
                'weather_info': day_data.get('weather', ''),  # 注意：可能是'weather'而不是'weather_info'
                'daily_theme': day_data.get('daily_theme', ''),
                'daily_plan': day_data.get('daily_plan', ''),
                'daily_summary': day_data.get('daily_summary', ''),
                'created_at': datetime.now().isoformat()
            }
            
            self.insert_record('schedule_days', day_record)
            
            # 保存时间段安排
            time_slots = day_data.get('time_slots', [])
            for i, slot_data in enumerate(time_slots):
                # 自动计算slot_number（如果没有提供）
                slot_number = slot_data.get('slot_number', i + 1)
                
                slot_record = {
                    'schedule_id': schedule_id,
                    'day_date': day_data.get('date', ''),
                    'slot_number': slot_number,
                    'slot_name': slot_data.get('slot_name', ''),
                    'start_time': slot_data.get('start_time', ''),
                    'end_time': slot_data.get('end_time', ''),
                    'assigned_character': slot_data.get('assigned_character', ''),
                    'activity_type': slot_data.get('activity_type', ''),
                    'location': slot_data.get('location', ''),
                    'story_content': slot_data.get('story_content', ''),
                    'story_id': slot_data.get('story_id', ''),
                    'importance_level': slot_data.get('importance_level', 3),
                    'mood_tone': slot_data.get('mood_tone', 'neutral'),
                    'interaction_level': slot_data.get('interaction_level', 'normal'),
                    'created_at': datetime.now().isoformat()
                }
                
                self.insert_record('time_slots', slot_record)
                
        except Exception as e:
            logger.error(f"保存单日安排失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _update_character_assignments(self, schedule_id: str):
        """更新角色安排统计"""
        try:
            # 删除旧统计
            self.delete_record('character_assignments', 'schedule_id = ?', (schedule_id,))
            
            # 重新计算统计
            sql = """
                SELECT 
                    assigned_character,
                    COUNT(*) as total_slots,
                    SUM(CASE WHEN slot_name = '夜间' THEN 1 ELSE 0 END) as night_slots,
                    SUM(CASE WHEN slot_name = '上午' THEN 1 ELSE 0 END) as morning_slots,
                    SUM(CASE WHEN slot_name = '中午' THEN 1 ELSE 0 END) as noon_slots,
                    SUM(CASE WHEN slot_name = '下午' THEN 1 ELSE 0 END) as afternoon_slots,
                    SUM(CASE WHEN slot_name = '晚上' THEN 1 ELSE 0 END) as evening_slots,
                    AVG(importance_level) as avg_importance,
                    MAX(day_date) as last_assigned_date
                FROM time_slots 
                WHERE schedule_id = ? AND assigned_character != ''
                GROUP BY assigned_character
            """
            
            stats = self.execute_query(sql, (schedule_id,))
            
            for stat in stats:
                assignment_record = {
                    'schedule_id': schedule_id,
                    'character_name': stat['assigned_character'],
                    'total_slots': stat['total_slots'],
                    'morning_slots': stat['morning_slots'],
                    'afternoon_slots': stat['afternoon_slots'],
                    'evening_slots': stat['evening_slots'],
                    'night_slots': stat['night_slots'],
                    'avg_importance': round(stat['avg_importance'], 2),
                    'last_assigned_date': stat['last_assigned_date'],
                    'created_at': datetime.now().isoformat()
                }
                
                self.insert_record('character_assignments', assignment_record)
                
        except Exception as e:
            logger.error(f"更新角色安排统计失败: {e}")
    
    def get_schedule_by_id(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取完整日程信息"""
        try:
            # 获取主日程信息
            schedule = self.get_record('schedules', 'schedule_id = ?', (schedule_id,))
            if not schedule:
                return None
            
            # 获取每日安排
            daily_schedules = self.get_daily_schedules(schedule_id)
            
            # 获取角色统计
            character_stats = self.get_character_assignments(schedule_id)
            
            result = dict(schedule)
            result['daily_schedules'] = daily_schedules
            result['character_assignments'] = character_stats
            
            # 解析配置数据
            if result.get('config_data'):
                result['config'] = json.loads(result['config_data'])
            
            return result
            
        except Exception as e:
            logger.error(f"获取日程失败: {e}")
            return None
    
    def get_daily_schedules(self, schedule_id: str) -> List[Dict[str, Any]]:
        """获取指定日程的所有每日安排"""
        try:
            sql = """
                SELECT * FROM schedule_days 
                WHERE schedule_id = ? 
                ORDER BY day_date
            """
            
            days = self.execute_query(sql, (schedule_id,))
            
            for day in days:
                # 获取该日的时间段安排
                time_slots = self.get_time_slots(schedule_id, day['day_date'])
                day['time_slots'] = time_slots
            
            return days
            
        except Exception as e:
            logger.error(f"获取每日安排失败: {e}")
            return []
    
    def get_time_slots(self, schedule_id: str, day_date: str) -> List[Dict[str, Any]]:
        """获取指定日期的时间段安排"""
        try:
            sql = """
                SELECT * FROM time_slots 
                WHERE schedule_id = ? AND day_date = ? 
                ORDER BY slot_number
            """
            
            return self.execute_query(sql, (schedule_id, day_date))
            
        except Exception as e:
            logger.error(f"获取时间段安排失败: {e}")
            return []
    
    def get_character_assignments(self, schedule_id: str) -> List[Dict[str, Any]]:
        """获取角色安排统计"""
        try:
            sql = """
                SELECT * FROM character_assignments 
                WHERE schedule_id = ? 
                ORDER BY total_slots DESC
            """
            
            return self.execute_query(sql, (schedule_id,))
            
        except Exception as e:
            logger.error(f"获取角色安排统计失败: {e}")
            return []
    
    def get_schedules_by_filter(self, filters: Dict[str, Any], limit: int = 50) -> List[Dict[str, Any]]:
        """根据条件筛选日程"""
        try:
            where_conditions = []
            params = []
            
            # 基础条件筛选
            if filters.get('protagonist'):
                where_conditions.append('protagonist = ?')
                params.append(filters['protagonist'])
            
            if filters.get('schedule_type'):
                where_conditions.append('schedule_type = ?')
                params.append(filters['schedule_type'])
            
            if filters.get('start_date'):
                where_conditions.append('start_date >= ?')
                params.append(filters['start_date'])
            
            if filters.get('end_date'):
                where_conditions.append('end_date <= ?')
                params.append(filters['end_date'])
            
            # 处理单个日期筛选
            if filters.get('date'):
                where_conditions.append('(start_date <= ? AND end_date >= ?)')
                params.extend([filters['date'], filters['date']])
            
            # 处理日期范围筛选
            if filters.get('date_range'):
                date_range = filters['date_range']
                where_conditions.append('(start_date <= ? AND end_date >= ?)')
                params.extend([date_range['end'], date_range['start']])
            
            where_clause = ' AND '.join(where_conditions) if where_conditions else '1=1'
            
            # 主查询，获取基本信息和统计
            sql = f"""
                SELECT s.*, 
                    (SELECT COUNT(DISTINCT day_date) FROM schedule_days WHERE schedule_id = s.schedule_id) as actual_days,
                    (SELECT COUNT(*) FROM time_slots WHERE schedule_id = s.schedule_id) as slot_count,
                    (SELECT GROUP_CONCAT(DISTINCT assigned_character) FROM time_slots 
                     WHERE schedule_id = s.schedule_id AND assigned_character != '') as characters,
                    (SELECT COUNT(DISTINCT assigned_character) FROM time_slots 
                     WHERE schedule_id = s.schedule_id AND assigned_character != '') as character_count
                FROM schedules s
                WHERE {where_clause}
                ORDER BY created_at DESC 
                LIMIT ?
            """
            
            params.append(limit)
            schedules = self.execute_query(sql, params)
            result = []
            
            for schedule in schedules:
                # 解析角色列表
                characters = []
                if schedule.get('characters'):
                    characters = schedule['characters'].split(',')
                
                # 处理按角色筛选（如果有）
                if filters.get('character'):
                    character_filter = filters['character'].strip()
                    # 检查是否包含指定角色
                    if not any(character_filter.lower() in char.lower() for char in characters):
                        continue
                
                # 构建返回记录
                result.append({
                    'schedule_id': schedule['schedule_id'],
                    'schedule_name': schedule['schedule_name'],
                    'start_date': schedule['start_date'],
                    'end_date': schedule['end_date'],
                    'protagonist': schedule['protagonist'],
                    'schedule_type': schedule['schedule_type'],
                    'total_days': schedule['total_days'],
                    'actual_days': schedule['actual_days'],
                    'time_slots': schedule['slot_count'],
                    'characters': characters,
                    'character_count': schedule['character_count'],
                    'description': schedule.get('description', ''),
                    'weekly_plan': schedule.get('weekly_plan', ''),
                    'created_at': schedule['created_at']
                })
            
            return result
            
        except Exception as e:
            logger.error(f"筛选日程失败: {e}")
            return []
    
    def delete_schedule(self, schedule_id: str) -> bool:
        """删除指定日程（级联删除相关数据）"""
        try:
            # 删除时间段
            self.delete_record('time_slots', 'schedule_id = ?', (schedule_id,))
            
            # 删除每日安排
            self.delete_record('schedule_days', 'schedule_id = ?', (schedule_id,))
            
            # 删除角色统计
            self.delete_record('character_assignments', 'schedule_id = ?', (schedule_id,))
            
            # 删除主记录
            affected_rows = self.delete_record('schedules', 'schedule_id = ?', (schedule_id,))
            
            if affected_rows > 0:
                logger.info(f"成功删除日程: {schedule_id}")
                return True
            else:
                logger.warning(f"日程不存在: {schedule_id}")
                return False
                
        except Exception as e:
            logger.error(f"删除日程失败: {e}")
            return False
    
    def get_schedule_statistics(self) -> Dict[str, Any]:
        """获取日程数据库统计信息"""
        try:
            stats = {}
            
            # 基础统计
            stats['total_schedules'] = self.get_record_count('schedules')
            stats['total_days'] = self.get_record_count('schedule_days')
            stats['total_time_slots'] = self.get_record_count('time_slots')
            stats['unique_characters'] = len(self.execute_query("SELECT DISTINCT assigned_character FROM time_slots WHERE assigned_character != ''"))
            
            # 按类型统计
            type_stats = self.execute_query("""
                SELECT schedule_type, COUNT(*) as count 
                FROM schedules 
                GROUP BY schedule_type
                ORDER BY count DESC
            """)
            stats['by_schedule_type'] = {row['schedule_type']: row['count'] for row in type_stats}
            
            # 按主角统计
            protagonist_stats = self.execute_query("""
                SELECT protagonist, COUNT(*) as count 
                FROM schedules 
                GROUP BY protagonist
                ORDER BY count DESC
            """)
            stats['by_protagonist'] = {row['protagonist']: row['count'] for row in protagonist_stats}
            
            # 最活跃角色
            character_stats = self.execute_query("""
                SELECT assigned_character, COUNT(*) as slot_count 
                FROM time_slots 
                WHERE assigned_character != ''
                GROUP BY assigned_character
                ORDER BY slot_count DESC
                LIMIT 10
            """)
            stats['most_active_characters'] = [
                {'character': row['assigned_character'], 'slots': row['slot_count']} 
                for row in character_stats
            ]
            
            return stats
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
    
    def add_holiday(self, holiday_date: str, holiday_name: str, holiday_type: str = 'national', 
                   is_lunar: bool = False, lunar_date: str = '', description: str = '') -> bool:
        """添加节假日信息"""
        try:
            holiday_record = {
                'holiday_date': holiday_date,
                'holiday_name': holiday_name,
                'holiday_type': holiday_type,
                'is_lunar': 1 if is_lunar else 0,
                'lunar_date': lunar_date,
                'description': description,
                'created_at': datetime.now().isoformat()
            }
            
            self.insert_record('holidays', holiday_record)
            logger.info(f"添加节假日: {holiday_date} - {holiday_name}")
            return True
            
        except Exception as e:
            logger.error(f"添加节假日失败: {e}")
            return False
    
    def get_holidays_in_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """获取指定日期范围内的节假日"""
        try:
            sql = """
                SELECT * FROM holidays 
                WHERE holiday_date >= ? AND holiday_date <= ?
                ORDER BY holiday_date
            """
            
            return self.execute_query(sql, (start_date, end_date))
            
        except Exception as e:
            logger.error(f"获取节假日失败: {e}")
            return []
    
    def export_schedule_data(self, schedule_id: str = None, format: str = 'csv') -> str:
        """导出日程数据"""
        try:
            if schedule_id:
                # 导出指定日程
                schedule_data = self.get_schedule_by_id(schedule_id)
                if not schedule_data:
                    return f"日程 {schedule_id} 不存在"
                
                if format == 'csv':
                    return self._export_schedule_to_csv(schedule_data)
                elif format == 'json':
                    return json.dumps(schedule_data, ensure_ascii=False, indent=2)
            else:
                # 导出所有日程
                all_schedules = self.get_schedules_by_filter({}, limit=1000)
                if format == 'csv':
                    return self._export_all_schedules_to_csv(all_schedules)
                elif format == 'json':
                    return json.dumps(all_schedules, ensure_ascii=False, indent=2)
            
            return "不支持的导出格式"
            
        except Exception as e:
            logger.error(f"导出日程数据失败: {e}")
            return f"导出失败: {str(e)}"
    
    def _export_schedule_to_csv(self, schedule_data: Dict[str, Any]) -> str:
        """将单个日程导出为CSV格式"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 写入表头
        writer.writerow([
            '日程ID', '日程名称', '日期', '星期', '是否节假日', '节假日名称',
            '时间段', '开始时间', '结束时间', '安排角色', '活动类型', '地点',
            '故事内容', '重要程度', '情感基调'
        ])
        
        # 写入数据
        for day in schedule_data.get('daily_schedules', []):
            for slot in day.get('time_slots', []):
                writer.writerow([
                    schedule_data['schedule_id'],
                    schedule_data['schedule_name'],
                    day['day_date'],
                    day['weekday'],
                    '是' if day['is_holiday'] else '否',
                    day.get('holiday_name', ''),
                    slot['slot_name'],
                    slot['start_time'],
                    slot['end_time'],
                    slot['assigned_character'],
                    slot['activity_type'],
                    slot['location'],
                    slot['story_content'],
                    slot['importance_level'],
                    slot['mood_tone']
                ])
        
        return output.getvalue()
    
    def _export_all_schedules_to_csv(self, schedules: List[Dict[str, Any]]) -> str:
        """将所有日程导出为CSV格式"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # 写入表头
        writer.writerow([
            '日程ID', '日程名称', '日程类型', '主角', '开始日期', '结束日期',
            '总天数', '描述', '创建时间'
        ])
        
        # 写入数据
        for schedule in schedules:
            writer.writerow([
                schedule['schedule_id'],
                schedule['schedule_name'],
                schedule['schedule_type'],
                schedule['protagonist'],
                schedule['start_date'],
                schedule['end_date'],
                schedule['total_days'],
                schedule.get('description', ''),
                schedule['created_at']
            ])
        
        return output.getvalue()

    def get_all_schedules(self) -> List[Dict[str, Any]]:
        """获取所有日程的基本信息"""
        try:
            sql = """
                SELECT s.*, 
                    (SELECT COUNT(DISTINCT day_date) FROM schedule_days WHERE schedule_id = s.schedule_id) as actual_days,
                    (SELECT COUNT(*) FROM time_slots WHERE schedule_id = s.schedule_id) as slot_count,
                    (SELECT GROUP_CONCAT(DISTINCT assigned_character) FROM time_slots 
                     WHERE schedule_id = s.schedule_id AND assigned_character != '') as characters,
                    (SELECT COUNT(DISTINCT assigned_character) FROM time_slots 
                     WHERE schedule_id = s.schedule_id AND assigned_character != '') as character_count
                FROM schedules s
                ORDER BY created_at DESC
                LIMIT 100
            """
            
            schedules = self.execute_query(sql)
            result = []
            
            for schedule in schedules:
                # 解析角色列表
                characters = []
                if schedule.get('characters'):
                    characters = schedule['characters'].split(',')
                
                # 构建简化的返回记录
                result.append({
                    'schedule_id': schedule['schedule_id'],
                    'schedule_name': schedule['schedule_name'],
                    'start_date': schedule['start_date'],
                    'end_date': schedule['end_date'],
                    'protagonist': schedule['protagonist'],
                    'schedule_type': schedule['schedule_type'],
                    'total_days': schedule['total_days'],
                    'actual_days': schedule['actual_days'],
                    'time_slots': schedule['slot_count'],
                    'characters': characters,
                    'character_count': schedule['character_count'],
                    'description': schedule.get('description', ''),
                    'created_at': schedule['created_at']
                })
            
            return result
            
        except Exception as e:
            logger.error(f"获取所有日程失败: {e}")
            return []

    def get_schedule_activities(self, schedule_id: str) -> List[Dict[str, Any]]:
        """获取指定日程的所有活动"""
        try:
            sql = """
                SELECT 
                    ts.id,
                    sd.day_date,
                    ts.slot_name,
                    sd.day_date || ' ' || ts.slot_name as time,
                    ts.story_content as description,
                    ts.location,
                    ts.assigned_character as main_participant,
                    ts.activity_type,
                    ts.importance_level,
                    ts.mood_tone,
                    ts.story_id,
                    ts.start_time,
                    ts.end_time
                FROM time_slots ts
                JOIN schedule_days sd ON ts.day_date = sd.day_date AND ts.schedule_id = sd.schedule_id
                WHERE ts.schedule_id = ?
                ORDER BY sd.day_date, ts.slot_number
            """
            
            activities = self.execute_query(sql, (schedule_id,))
            result = []
            
            for activity in activities:
                # 获取可能的其他参与者（如果有的话）
                participants = []
                if activity['main_participant']:
                    participants = [activity['main_participant']]
                
                # 获取可能的故事引用（如果有的话）
                story_reference = ""
                if activity['story_id']:
                    story_reference = f"关联故事ID: {activity['story_id']}"
                
                result.append({
                    'time': activity['time'],  # 日期+时间段
                    'slot_name': activity['slot_name'],  # 时间段名称
                    'description': activity['description'],  # 活动描述
                    'location': activity['location'],  # 地点
                    'participants': participants,  # 参与者
                    'activity_type': activity['activity_type'],  # 活动类型
                    'importance_level': activity['importance_level'],  # 重要度
                    'mood': activity['mood_tone'],  # 情感基调
                    'story_reference': story_reference,  # 故事引用
                    'start_time': activity['start_time'],  # 开始时间
                    'end_time': activity['end_time']  # 结束时间
                })
            
            return result
            
        except Exception as e:
            logger.error(f"获取日程活动失败: {e}")
            return []