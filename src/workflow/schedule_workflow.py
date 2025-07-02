"""日程生成工作流 - 基于Graph+Node的日程创作系统
集成角色库、地点库、剧情库等功能，为主角生成每周和每天的详细日程安排
"""

import json
import asyncio
import csv
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import calendar

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.graph import StateGraph
from core.base import BaseNode
from llm.base import LLMFactory
from core.types import LLMConfig, TaskResult, Message, MessageRole

logger = logging.getLogger(__name__)

class ScheduleWorkflow:
    """日程生成工作流管理器"""
    
    def __init__(self, llm=None):
        self.llm = llm
        self.graph = None
        self.characters_data = {}
        self.locations_data = {}
        self.stories_data = {}  # 剧情库数据
        self.protagonist_data = ""  # 主角方知衡的详细人设
        self.holidays_data = {}  # 节假日数据
        self.current_config = {
            'protagonist': '方知衡',  # 固定主角
            'schedule_type': 'weekly',  # weekly, daily, monthly
            'start_date': '',
            'end_date': '',
            'total_days': 7,
            'selected_characters': [],
            'selected_locations': [],
            'selected_stories': [],  # 选择的剧情
            'time_slots_config': {
                '夜间': {'start': '23:00', 'end': '06:00'},
                '上午': {'start': '06:00', 'end': '11:00'},
                '中午': {'start': '11:00', 'end': '14:00'},
                '下午': {'start': '14:00', 'end': '18:00'},
                '晚上': {'start': '18:00', 'end': '23:00'}
            },
            'character_distribution': 'balanced',  # balanced, random, weighted
            'story_integration': 'moderate',  # minimal, moderate, intensive
            'include_holidays': True,
            'include_lunar': True,
            'mood_variety': True,
            'location_variety': True,
            'enable_cycle_summary': False,  # 是否启用周期总结功能，默认关闭
            'cycle_summary': ''  # 当前周期总结内容
        }
        
        # 预先初始化数据库表结构，防止执行时才创建导致错误
        try:
            from database.managers import schedule_manager
            schedule_manager.ScheduleManager()  # 初始化会自动创建表结构
            logger.info("数据库表结构初始化完成")
        except Exception as e:
            logger.warning(f"预初始化数据库表结构失败，稍后将重试: {e}")
        
        # 加载各种数据
        self._load_game_data()
        self._load_protagonist_data()
        self._load_stories_data()
        self._load_holidays_data()
    
    def _load_game_data(self):
        """加载游戏角色和地点数据"""
        try:
            # 加载角色数据
            char_path = os.path.join(os.path.dirname(__file__), '../../config/yunhub_characters.json')
            if os.path.exists(char_path):
                with open(char_path, 'r', encoding='utf-8') as f:
                    self.characters_data = json.load(f)
                    logger.info(f"成功加载角色数据，包含 {len(self.characters_data.get('角色列表', {}))} 个角色")
            
            # 加载地点数据
            loc_path = os.path.join(os.path.dirname(__file__), '../../config/yunhub_locations.json')
            if os.path.exists(loc_path):
                with open(loc_path, 'r', encoding='utf-8') as f:
                    self.locations_data = json.load(f)
                    district_count = len(self.locations_data.get("districts", {}))
                    logger.info(f"成功加载地点数据，包含 {district_count} 个区域")
                    
        except Exception as e:
            logger.error(f"加载游戏数据失败: {e}")
    
    def _load_protagonist_data(self):
        """加载主角方知衡的详细人设"""
        try:
            protagonist_path = os.path.join(os.path.dirname(__file__), '../../config/基础人设.txt')
            if os.path.exists(protagonist_path):
                with open(protagonist_path, 'r', encoding='utf-8') as f:
                    self.protagonist_data = f.read()
                    logger.info(f"成功加载主角人设，内容长度: {len(self.protagonist_data)} 字符")
            else:
                logger.warning("主角人设文件不存在")
                
        except Exception as e:
            logger.error(f"加载主角人设失败: {e}")
    
    def _load_stories_data(self):
        """加载已有剧情数据作为参考"""
        try:
            from database import story_manager
            
            # 获取所有剧情作为参考
            all_stories = story_manager.get_stories_by_filter({}, limit=100)
            
            # 按角色分组剧情
            self.stories_data = {
                'all_stories': all_stories,
                'by_character': {},
                'by_location': {},
                'by_type': {}
            }
            
            for story in all_stories:
                # 按角色分组
                characters = json.loads(story.get('selected_characters', '[]'))
                for char in characters:
                    if char not in self.stories_data['by_character']:
                        self.stories_data['by_character'][char] = []
                    self.stories_data['by_character'][char].append(story)
                
                # 按地点分组
                locations = json.loads(story.get('selected_locations', '[]'))
                for loc in locations:
                    if loc not in self.stories_data['by_location']:
                        self.stories_data['by_location'][loc] = []
                    self.stories_data['by_location'][loc].append(story)
                
                # 按类型分组
                story_type = story.get('story_type', 'daily_life')
                if story_type not in self.stories_data['by_type']:
                    self.stories_data['by_type'][story_type] = []
                self.stories_data['by_type'][story_type].append(story)
            
            logger.info(f"成功加载剧情数据，包含 {len(all_stories)} 个剧情")
            
        except Exception as e:
            logger.error(f"加载剧情数据失败: {e}")
            self.stories_data = {'all_stories': [], 'by_character': {}, 'by_location': {}, 'by_type': {}}
    
    def _load_holidays_data(self):
        """加载节假日数据"""
        try:
            # 这里可以加载节假日API或本地数据
            # 暂时使用硬编码的常见节假日
            self.holidays_data = {
                '2025-01-01': {'name': '元旦', 'type': 'national', 'lunar': False},
                '2025-02-12': {'name': '春节', 'type': 'traditional', 'lunar': True},
                '2025-02-14': {'name': '情人节', 'type': 'international', 'lunar': False},
                '2025-03-08': {'name': '妇女节', 'type': 'international', 'lunar': False},
                '2025-04-05': {'name': '清明节', 'type': 'traditional', 'lunar': True},
                '2025-05-01': {'name': '劳动节', 'type': 'national', 'lunar': False},
                '2025-06-01': {'name': '儿童节', 'type': 'international', 'lunar': False},
                '2025-10-01': {'name': '国庆节', 'type': 'national', 'lunar': False},
                '2025-12-25': {'name': '圣诞节', 'type': 'international', 'lunar': False}
            }
            logger.info(f"加载节假日数据，包含 {len(self.holidays_data)} 个节假日")
            
        except Exception as e:
            logger.error(f"加载节假日数据失败: {e}")
    
    def get_protagonist_info(self) -> Dict[str, Any]:
        """获取主角信息"""
        protagonist_name = self.current_config.get('protagonist', '方知衡')
        return {
            'name': protagonist_name,
            'type': 'protagonist',
            'description': self.protagonist_data.split('\n')[0] if self.protagonist_data else '主角信息',
            'full_profile': self.protagonist_data
        }
    
    def get_characters_list(self) -> List[Dict[str, Any]]:
        """获取角色列表（不包含主角）"""
        characters = []
        char_list = self.characters_data.get("角色列表", {})
        
        for name, info in char_list.items():
            # 跳过主角，主角单独处理
            if name == '方知衡':
                continue
                
            characters.append({
                'name': name,
                'age': info.get('年龄', '未知'),
                'personality': info.get('性格', ''),
                'description': info.get('简介', ''),
                'locations': info.get('活动地点', []),
                'plots': info.get('可触发剧情', []),
                'backstory': info.get('背景故事', ''),
                'relationships': info.get('人际关系', {}),
                'habits': info.get('生活习惯', []),
                'appearance': info.get('外貌特征', ''),
                'skills': info.get('特长技能', [])
            })
        
        return characters
    
    def get_locations_list(self) -> List[Dict[str, Any]]:
        """获取地点列表"""
        locations = []
        districts = self.locations_data.get("districts", {})
        
        for district_name, district_info in districts.items():
            district_locations = district_info.get("locations", {})
            for loc_name, loc_info in district_locations.items():
                locations.append({
                    'name': loc_info.get('name', loc_name),
                    'type': loc_info.get('type', ''),
                    'district': district_info.get('name', district_name),
                    'description': loc_info.get('description', ''),
                    'atmosphere': loc_info.get('atmosphere', ''),
                    'keywords': loc_info.get('keywords', [])
                })
        
        return locations
    
    def get_stories_list(self) -> List[Dict[str, Any]]:
        """获取剧情列表"""
        stories = []
        for story in self.stories_data.get('all_stories', []):
            stories.append({
                'story_id': story.get('story_id', ''),
                'story_name': story.get('story_name', ''),
                'story_overview': story.get('story_overview', ''),
                'story_type': story.get('story_type', ''),
                'characters': json.loads(story.get('selected_characters', '[]')),
                'locations': json.loads(story.get('selected_locations', '[]')),
                'main_conflict': story.get('main_conflict', ''),
                'emotional_development': story.get('emotional_development', '')
            })
        
        return stories
    
    def get_holidays_in_range(self, start_date: str, end_date: str) -> Dict[str, Dict[str, Any]]:
        """获取指定日期范围内的节假日"""
        holidays = {}
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        for date_str, holiday_info in self.holidays_data.items():
            holiday_date = datetime.strptime(date_str, '%Y-%m-%d')
            if start <= holiday_date <= end:
                holidays[date_str] = holiday_info
        
        return holidays
    
    def update_config(self, config_updates: Dict[str, Any]):
        """更新工作流配置"""
        self.current_config.update(config_updates)
    
    async def prepare_cycle_summary(self, config: Dict[str, Any]) -> str:
        """准备周期总结，获取历史数据"""
        try:
            # 检查是否启用周期总结
            if not config.get('enable_cycle_summary', False):
                logger.info("周期总结功能未启用")
                return ""
            
            # 等待1秒，确保数据库写入完成
            import time
            time.sleep(1)
            
            # 从数据库获取最新的周期总结
            from database.managers.schedule_manager import ScheduleManager
            schedule_manager = ScheduleManager()
            
            # 传递开始日期，确保获取早于开始日期且时间不超过三天的总结
            start_date = config.get('start_date', '')
            previous_summary = schedule_manager.get_latest_cycle_summary(before_date=start_date)
            
            if previous_summary:
                logger.info(f"获取到适当的历史周期总结，长度: {len(previous_summary)} 字符")
                return previous_summary
            else:
                logger.info(f"未找到{start_date}前三天内的周期总结，这可能是第一个周期或时间间隔较长")
                return ""
                
        except Exception as e:
            logger.error(f"准备周期总结失败: {e}")
            return ""
    
    async def create_schedule_graph(self) -> StateGraph:
        """创建日程生成图工作流 - 简化版本，只有生成和保存两个节点"""
        self.graph = StateGraph(name="schedule_generation_workflow")
        
        # 创建节点 - 只保留生成和保存两个节点
        schedule_generate_node = ScheduleGenerateNode()
        database_save_node = ScheduleDatabaseSaveNode()
        
        # 添加节点到图
        self.graph.add_node("schedule_generate", schedule_generate_node)
        self.graph.add_node("database_save", database_save_node)
        
        # 定义节点连接关系
        self.graph.add_edge("schedule_generate", "database_save")
        
        # 设置入口点
        self.graph.set_entry_point("schedule_generate")
        
        return self.graph
    
    async def execute_workflow_stream(self, config: Dict[str, Any], workflow_chat):
        """流式执行工作流 - 使用StateGraph自动编排"""
        try:
            # 准备初始输入
            initial_input = {
                'characters_data': self.characters_data,
                'locations_data': self.locations_data,
                'stories_data': self.stories_data,
                'protagonist_data': self.protagonist_data,
                'holidays_data': self.holidays_data,
                'config': config,
                'protagonist': config.get('protagonist', '方知衡'),
                'schedule_type': config.get('schedule_type', 'weekly'),
                'start_date': config.get('start_date', ''),
                'end_date': config.get('end_date', ''),
                'total_days': config.get('total_days', 7),
                'selected_characters': config.get('selected_characters', []),
                'selected_locations': config.get('selected_locations', []),
                'selected_stories': config.get('selected_stories', []),
                'time_slots_config': config.get('time_slots_config', self.current_config['time_slots_config']),
                'character_distribution': config.get('character_distribution', 'balanced'),
                'story_integration': config.get('story_integration', 'moderate'),
                'include_holidays': config.get('include_holidays', True),
                'include_lunar': config.get('include_lunar', True),
                'workflow_chat': workflow_chat,  # 传递UI更新器
                'llm': self.llm  # 传递LLM实例
            }
            
            # 创建并编译图工作流
            if not self.graph:
                await self.create_schedule_graph()
            
            compiled_graph = self.graph.compile()
            
            # 使用图的流式执行 - 使用async for正确处理异步生成器
            async for stream_event in compiled_graph.stream(initial_input):
                event_type = stream_event.get('type')
                node_name = stream_event.get('node')
                
                if event_type == 'start':
                    # 工作流开始
                    yield (
                        workflow_chat._create_workflow_progress(),
                        "",
                        "日程生成工作流开始执行...",
                        False
                    )
                
                elif event_type == 'node_start':
                    # 节点开始执行
                    node_display_name = self._get_node_display_name(node_name)
                    workflow_chat.current_node = self._get_node_id(node_name)
                    
                    # 更新UI - 节点开始状态
                    await workflow_chat.add_node_message(
                        node_display_name,
                        "开始执行...",
                        "progress"
                    )
                    
                    yield (
                        workflow_chat._create_workflow_progress(),
                        "",
                        f"{node_display_name}开始执行...",
                        False
                    )
                
                elif event_type == 'node_streaming':
                    # 节点流式执行中
                    intermediate_result = stream_event.get('intermediate_result')
                    if intermediate_result and intermediate_result.state_update:
                        # 获取当前生成的内容长度
                        content_length = 0
                        for key in ['schedule_content', 'daily_schedules', 'schedule_result']:
                            if key in intermediate_result.state_update:
                                if isinstance(intermediate_result.state_update[key], str):
                                    content_length = len(intermediate_result.state_update[key])
                                elif isinstance(intermediate_result.state_update[key], (list, dict)):
                                    content_length = len(str(intermediate_result.state_update[key]))
                                break
                        
                        # 实时更新进度信息 - 获取最新的进度HTML，与story_workflow保持一致
                        if content_length > 0:
                            node_display_name = self._get_node_display_name(node_name)
                            await workflow_chat.add_node_message(
                                node_display_name,
                                f"正在生成日程内容... 当前生成{content_length}字符",
                                "streaming"
                            )
                            
                            yield (
                                workflow_chat._create_workflow_progress(),
                                "",
                                f"正在生成日程内容... 当前长度: {content_length} 字符",
                                False
                            )
                
                elif event_type == 'node_complete':
                    # 节点执行完成
                    node_display_name = self._get_node_display_name(node_name)
                    node_id = self._get_node_id(node_name)
                    
                    # 为节点添加完成消息，确保UI正确更新
                    if node_name == 'schedule_generate':
                        result_content = "✅ 日程生成完成"
                        if 'schedule_result' in stream_event.get('output', {}):
                            schedule_data = stream_event['output']['schedule_result']
                            if isinstance(schedule_data, (dict, list)):
                                result_content = f"✅ 已成功生成{config['total_days']}天的日程安排"
                    else:
                        result_content = "✅ 执行完成"
                        
                    # 更新节点消息
                    await workflow_chat.add_node_message(
                        node_display_name,
                        result_content,
                        "completed"
                    )
                    
                    yield (
                        workflow_chat._create_workflow_progress(),
                        "",
                        f"{node_display_name}执行完成",
                        False
                    )
                
                elif event_type == 'node_error':
                    # 节点执行错误
                    error_msg = stream_event.get('error', '未知错误')
                    node_display_name = self._get_node_display_name(node_name)
                    
                    await workflow_chat.add_node_message(
                        node_display_name,
                        f"执行失败: {error_msg}",
                        "error"
                    )
                    
                    yield (
                        workflow_chat._create_workflow_progress(),
                        "",
                        "",
                        False
                    )
                
                elif event_type == 'final':
                    # 工作流完成
                    yield (
                        workflow_chat._create_workflow_progress(),
                        "",
                        "日程生成工作流执行完成",
                        False
                    )
                
                # 其他事件类型可以忽略或记录日志
                else:
                    # 持续更新UI以保持流畅性
                    yield (
                        workflow_chat._create_workflow_progress(),
                        "",
                        "日程生成工作流执行中...",
                        False
                    )
                
        except Exception as e:
            logger.error(f"日程生成工作流流式执行失败: {e}")
            await workflow_chat.add_node_message(
                "系统",
                f"工作流执行失败: {str(e)}",
                "error"
            )
            yield (
                workflow_chat._create_workflow_progress(),
                "",
                "",
                False
            )
    
    def _get_node_display_name(self, node_name: str) -> str:
        """获取节点显示名称"""
        name_mapping = {
            'schedule_generate': '日程生成',
            'database_save': '数据库保存'
        }
        return name_mapping.get(node_name, node_name)
    
    def _get_node_id(self, node_name: str) -> str:
        """获取节点ID"""
        id_mapping = {
            'schedule_generate': 'generate',
            'database_save': 'save'
        }
        return id_mapping.get(node_name, node_name)


class ScheduleGenerateNode(BaseNode):
    """日程生成节点 - 合并多个节点功能，直接生成完整日程"""
    
    def __init__(self):
        super().__init__(name="schedule_generate", stream=True)
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行日程生成节点 - 非流式版本"""
        # 使用流式执行并返回最终结果
        final_result = None
        async for result in self.execute_stream(input_data):
            final_result = result
        return final_result or input_data
    
    async def execute_stream(self, input_data: Dict[str, Any]):
        """流式执行日程生成节点"""
        print("📅 开始日程生成...")
        
        workflow_chat = input_data.get('workflow_chat')
        llm = input_data.get('llm')
        
        # 获取配置参数
        start_date = input_data.get('start_date', '')
        end_date = input_data.get('end_date', '')
        total_days = input_data.get('total_days', 7)
        schedule_type = input_data.get('schedule_type', 'weekly')
        protagonist = input_data.get('protagonist', '方知衡')
        selected_characters = input_data.get('selected_characters', [])
        selected_locations = input_data.get('selected_locations', [])
        holidays_data = input_data.get('holidays_data', {})
        include_holidays = input_data.get('include_holidays', True)
        include_lunar = input_data.get('include_lunar', True)
        
        # 更新UI - 开始状态
        if workflow_chat:
            await workflow_chat.add_node_message(
                "日程生成",
                "正在分析日期范围、角色信息和配置参数，准备生成详细日程...",
                "progress"
            )
        
        # 准备历史周期总结（如果启用）
        workflow_instance = input_data.get('workflow_instance')
        history_context = ""
        cycle_summary_requirement = ""
        
        if workflow_instance and input_data.get('config', {}).get('enable_cycle_summary', False):
            try:
                previous_summary = await workflow_instance.prepare_cycle_summary(input_data['config'])
                if previous_summary:
                    logger.info("已准备历史周期总结上下文")
                    if workflow_chat:
                        await workflow_chat.add_node_message(
                            "日程生成",
                            "已获取历史周期总结，将保持故事连续性...",
                            "progress"
                        )
                    
                    # 如果有历史总结，添加简化的上下文
                    history_context = f"## 历史周期总结\n{previous_summary}\n"
                    
                else:
                    # 第一个周期，不需要历史上下文
                    history_context = ""
                    
            except Exception as e:
                logger.warning(f"准备历史周期总结失败: {e}")
                history_context = ""

        # 准备日期信息
        dates_info = []
        try:
            from datetime import datetime, timedelta
            from calendar import day_name
            
            # 解析日期范围
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            
            # 获取日期范围内的所有日期
            current_date = start
            while current_date <= end:
                date_str = current_date.strftime('%Y-%m-%d')
                weekday = current_date.weekday()
                weekday_name = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][weekday]
            
                # 检查是否节假日
                is_holiday = False
                holiday_name = ""
                if include_holidays and date_str in holidays_data:
                    is_holiday = True
                    holiday_name = holidays_data[date_str]['name']
            
                # 添加日期信息
                dates_info.append({
                    'date': date_str,
                    'weekday': weekday,
                    'weekday_name': weekday_name,
                    'is_holiday': is_holiday,
                    'holiday_name': holiday_name,
                    'day_number': (current_date - start).days + 1  # 从1开始的天数
                })
                
                current_date += timedelta(days=1)
                
        except Exception as e:
            logger.error(f"日期处理失败: {e}")
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "日程生成",
                    f"日期处理失败: {str(e)}",
                    "error"
                )
            raise Exception(f"日期处理失败: {str(e)}")
        
        # 构建角色信息字符串
        characters_info = []
        for char_name in selected_characters:
            # 从角色数据中获取详细信息
            char_list = input_data.get('characters_data', {}).get("角色列表", {})
            if char_name in char_list:
                char_info = char_list[char_name]
                char_desc = f"{char_name}：{char_info.get('简介', '')}"
                if char_info.get('性格'):
                    char_desc += f"，性格{char_info.get('性格')}"
                if char_info.get('年龄'):
                    char_desc += f"，{char_info.get('年龄')}岁"
                characters_info.append(char_desc)
            else:
                characters_info.append(char_name)
        
        # 获取主角信息
        protagonist = input_data.get('protagonist', '方知衡')
        protagonist_data = input_data.get('protagonist_data', '')
        
        # 获取上一批次总结信息（如果有）
        config = input_data.get('config', {})
        previous_summary = config.get('previous_batch_summary', '')
        
        # 构建日程生成提示词
        generation_prompt = f"""
你是一名专业的日程规划师和故事编剧，需要为主角{protagonist}生成从{start_date}到{end_date}的详细日程安排。这不仅是简单的时间安排，更是一个完整的生活故事，要体现他在云枢市真实的日常生活。

# 主角信息
{protagonist_data}

{history_context if history_context else ''}

{previous_summary if previous_summary else ''}



# 日程需求
- 日程类型：{schedule_type}（周期规划）
- 日期范围：{start_date} 至 {end_date}，共{total_days}天
- 每天划分为5个时间段：夜间(23:00-06:00)、上午(06:00-11:00)、中午(11:00-14:00)、下午(14:00-18:00)、晚上(18:00-23:00)

# 参与角色详情
{chr(10).join(characters_info)}

# 活动地点
{', '.join(selected_locations)}

# 日期信息
{json.dumps(dates_info, ensure_ascii=False, indent=2)}

# 核心生成要求

## 云枢市真实生活感
1. **角色均衡分布**：所有角色（除主角外）都平等重要，根据自然的生活节奏出现
2. **日常随机事件**：增加偶遇、意外发现等真实生活元素
3. **城市生活细节**：路边小店、街头艺人、流浪动物、天气变化等
4. **非NPC互动**：与环境、动物、自然现象的互动，体现生活的丰富性
5. **节日活动**：节日活动、文化活动等

## 故事性要求
1. **情感发展线**：每个角色的出现都应该有情感推进，不是简单的功能性互动
2. **细节丰富度**：每个时间段的描述应该包含具体的对话片段、内心活动、环境描写
3. **连贯性**：前一天的事件应该对后续产生影响，形成完整的故事链
4. **生活真实感**：包含工作压力、情绪波动、小确幸、意外惊喜等真实元素

## 计划与总结的区别
- **周期计划(cycle_plan)**：{protagonist}对整个{total_days}天周期的整体规划和期望
- **每日计划(daily_plan)**：{protagonist}早晨醒来时对这一天的预期和安排，基于他现有的信息和经验
- **每日总结(daily_summary)**：一天结束后对实际发生事件的回顾，可能与计划有出入，包含意外和惊喜

## 时间段内容要求
1. **夜间(23:00-06:00)**：休息、梦境、深夜思考，偶尔有特殊情况
2. **上午(06:00-11:00)**：工作、研究、重要会议，精神状态最佳的时段
3. **中午(11:00-14:00)**：用餐、轻松社交、短暂休息
4. **下午(14:00-18:00)**：继续工作、实地考察、学术活动
5. **晚上(18:00-23:00)**：社交活动、娱乐、个人时间、深度交流

## 角色出现原则
1. **自然分布**：根据生活逻辑和工作关系自然出现，不强制平均分配
2. **互动深度**：每次互动都要有具体的对话内容和情感变化
3. **关系发展**：角色间的关系应该随时间推进而发展变化
4. **随机偶遇**：增加意外碰面、巧合事件等真实生活元素

## 独立故事要求
1. **时间段故事独立性**：每个时间段的故事内容必须是独立完整的，能够单独阅读理解
2. **前因后果清晰**：即使是独立的时间段故事，也要描述清楚事件的前因后果
3. **情境完整性**：包含明确的场景、人物、对话和情感描述，保证内容的完整性
4. **独立叙事**：每个时间段内容可能被单独提取使用，因此必须是自包含的完整故事
5. **上下文连贯**：虽然是独立的，但各时间段之间应该有连贯的关系，形成日常生活的完整画面

# 输出格式
请按以下JSON格式输出日程安排：

```json
{{
  "schedule_summary": {{
    "总天数": {total_days},
    "周期类型": "{schedule_type}",
    "开始日期": "{start_date}",
    "结束日期": "{end_date}",
    "日程特点": "描述这段时间的整体特点和主要故事线",
    "情感主线": "这段时间的主要情感发展线",
    "常规活动": ["教学工作", "锻炼", "习惯", "..."],
    "主要互动角色": ["角色1", "角色2", "..."],
    "常去地点": ["地点1", "地点2", "..."]
  }},
  "cycle_plan": "{protagonist}对这{total_days}天的整体规划，第三人称描述，200-300字",

  "daily_schedules": [
    {{
      "date": "YYYY-MM-DD",
      "day_number": 1,
      "weekday_name": "周几",
      "is_holiday": true/false,
      "holiday_name": "节日名称（如果是节假日）",
      "weather": "天气情况",
      "daily_plan": "{protagonist}早晨对这一天的计划和期望，基于他现有的认知，第三人称描述，250字以内",
      "time_slots": [
        {{
          "slot_name": "夜间",
          "location": "具体地点",
          "story_content": "详细的第三人称故事描述，方知衡为主体，像小说片段一样生动，环境，事件，剧情描述为主，少量对话，200-300字。内容必须独立完整，描述清楚前因后果，即使单独阅读也能理解。",
          "involved_characters": ["角色名1", "角色名2"]
        }},
        {{
          "slot_name": "上午",
          "location": "具体地点",
          "story_content": "详细的第三人称故事描述，方知衡为主体，像小说片段一样生动，环境，事件，剧情描述为主，少量对话，200-300字。内容必须独立完整，描述清楚前因后果，即使单独阅读也能理解。",
          "involved_characters": ["角色名1", "角色名2"]
        }},
        {{
          "slot_name": "中午",
          "location": "具体地点",
          "story_content": "详细的第三人称故事描述，方知衡为主体，像小说片段一样生动，环境，事件，剧情描述为主，少量对话，200-300字。内容必须独立完整，描述清楚前因后果，即使单独阅读也能理解。",
          "involved_characters": ["角色名1", "小动物名等"]
        }},
        {{
          "slot_name": "下午",
          "location": "具体地点",
          "story_content": "详细的第三人称故事描述，方知衡为主体，像小说片段一样生动，环境，事件，剧情描述为主，少量对话，200-300字。内容必须独立完整，描述清楚前因后果，即使单独阅读也能理解。",
          "involved_characters": ["角色名1", "角色名2"]
        }},
        {{
          "slot_name": "晚上",
          "location": "具体地点",
          "story_content": "详细的第三人称故事描述，方知衡为主体，像小说片段一样生动，环境，事件，剧情描述为主，少量对话，200-300字。内容必须独立完整，描述清楚前因后果，即使单独阅读也能理解。",
          "involved_characters": ["角色名1", "角色名2"]
        }}
      ],
      "daily_summary": "第三人称，一天结束时对实际发生事件的总结，200-300字",

    }},
    // ... 其他日期
  ],
  "cycle_summary": "周期总结：1. 如有历史总结则压缩到200字以内保留核心信息 2. 添加本周期重要发展300字以内 3. 总计500字以内 4. 第三人称以主角为主体 5. 重点关注角色关系发展、情感变化、重要事件、地点活动等",
}}
```

# 重要提醒
1. **数据完整性要求**：
   - cycle_plan：必须包含整个周期的计划
   - daily_plan：每天都要有具体的早晨计划
   - 每天必须有5个完整的时间段（夜间、上午、中午、下午、晚上）
   - involved_characters：每个时间段都要明确列出涉及的角色名称列表

2. **故事质量要求**：
   - 每个时间段的story_content必须丰富详实，像小说片段一样生动
   - 各时间段的故事必须是独立完整的，能够被单独提取和理解
   - 角色对话要符合各自的性格特点，有真实感
   - 增加随机事件：意外发现、巧遇等云枢市生活细节
   - 情节要有起伏，包含工作压力、小确幸、意外惊喜等真实元素
   - 禁止有任何男女恋爱元素
   - 禁止提起生活中提起天文，主角不是工作狂，说话也是正常人，不会用精确到秒的数字

3. **角色处理要求**：
   - 所有角色平等重要，根据生活逻辑自然出现
   - 可以创造临时角色（如店主、路人、小动物）增加真实感
   - involved_characters中只需列出角色名称，不需要描述

4. **生活真实感要求**：
   - 体现{protagonist}的职业特色和个人特点
   - 包含云枢市的城市生活细节
   - daily_plan是计划，daily_summary是实际发生的总结，可以有差异

5. **技术要求**：
   - 确保JSON格式完全正确，可以被程序解析
   - 每个字段都要填写完整，不能为空

请开始生成这个充满云枢市生活真实感的详细日程安排。
"""
        
        # 流式调用LLM
        if llm:
            try:
                # 构建消息列表
                message = Message(role=MessageRole.USER, content=generation_prompt)
                messages = [message]
                
                logger.info(f"日程生成: 开始流式LLM调用，提示词长度: {len(generation_prompt)}")
                
                # 使用think模式流式调用
                chunk_count = 0
                think_content = ""
                final_content = ""
                
                # 流式调用LLM
                async for chunk_data in llm.stream_generate(
                    messages, 
                    mode="think",
                    return_dict=True
                ):
                    chunk_count += 1
                    
                    think_part = chunk_data.get("think", "")
                    content_part = chunk_data.get("content", "")
                    
                    think_content += think_part
                    final_content += content_part
                    
                    # 实时更新UI
                    if workflow_chat:
                        try:
                            display_content = ""
                            if think_content.strip():
                                display_content = think_part
#                                 display_content += f"""
# <div style="background: #f8f9fa; border-left: 4px solid #6c757d; padding: 10px; margin: 10px 0; border-radius: 4px;">
# 思考过程：<br>
# {think_content}
# </div>"""
                            
                            if final_content.strip():
                                display_content = content_part
#                                 display_content += f"""
# <div style="background: #e8f5e9; border-left: 4px solid #28a745; padding: 10px; margin: 10px 0; border-radius: 4px;">
# 生成结果：<br>
# {final_content}
# </div>"""
                            
                            await workflow_chat.add_node_message(
                                "日程生成",
                                display_content,
                                "streaming"
                            )
                        except Exception as ui_error:
                            logger.warning(f"日程生成UI更新失败: {ui_error}")
                    
                    # 每个chunk都yield最新状态
                    yield {
                        'schedule_content': final_content,
                        'schedule_thinking': think_content,
                        'chunk_progress': f"{chunk_count} chunks processed"
                    }
                
                logger.info(f"日程生成: 流式生成完成，总chunk数: {chunk_count}，内容长度: {len(final_content)}")
                        
            except Exception as e:
                error_msg = f"日程生成LLM调用失败: {type(e).__name__}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                raise Exception(error_msg)
        else:
            error_msg = "日程生成: LLM未初始化"
            logger.error(error_msg)
            raise Exception(error_msg)
                
        # 解析JSON格式的结果
        schedule_data = None
        try:
            from parsers.json_parser import JSONParser
            parser = JSONParser()
            
            json_content = self._extract_json_from_content(final_content)
            parsed_result = parser.parse(json_content)
            
            if parsed_result:
                # 生成成功，提取日程数据
                schedule_data = parsed_result
                daily_schedules = schedule_data.get('daily_schedules', [])
                # logger.info(f"成功解析日程JSON结果，包含 {len(daily_schedules)} 天")
                # logger.info(f"日程数据: {schedule_data}")
                if workflow_chat:
                    await workflow_chat.add_node_message(
                        "日程生成",
                        f"生成完成！已成功创建 {len(daily_schedules)} 天的详细日程安排。",
                        "success"
                    )
            else:
                # 解析失败，使用原始内容
                schedule_data = {"schedule_content": final_content}
                logger.warning(f"日程JSON解析失败，使用原始内容")
                
                if workflow_chat:
                    await workflow_chat.add_node_message(
                        "日程生成",
                        "JSON解析失败，但已生成日程内容文本。",
                        "warning"
                    )
        except Exception as parse_error:
            logger.warning(f"日程JSON解析异常: {parse_error}，使用原始内容")
            schedule_data = {"schedule_content": final_content}
            
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "日程生成",
                    f"JSON解析异常: {str(parse_error)}，但已保存原始内容。",
                    "warning"
                )
        
        # 最终完整结果
        output_data = input_data.copy()
        output_data['schedule_result'] = schedule_data
        output_data['daily_schedules'] = schedule_data.get('daily_schedules', [])
        
        print(f"✅ 日程生成完成")
        yield output_data
        
    def _extract_json_from_content(self, content: str) -> str:
        """从生成内容中提取JSON部分"""
        import re
        
        # 查找```json...```代码块
        json_pattern = r'```json\s*(.*?)\s*```'
        matches = re.findall(json_pattern, content, re.DOTALL | re.IGNORECASE)
        
        if matches:
            return matches[0].strip()
        
        # 如果没有代码块，尝试查找以{开头}结尾的内容
        json_pattern2 = r'\{.*\}'
        matches2 = re.findall(json_pattern2, content, re.DOTALL)
        
        if matches2:
            return matches2[0].strip()
        
        # 如果都没找到，返回原内容
        return content.strip()

class ScheduleDatabaseSaveNode(BaseNode):
    """日程数据库保存节点 - 将生成的日程保存到数据库"""
    
    def __init__(self):
        super().__init__(name="schedule_database_save", stream=True)
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行数据库保存节点 - 非流式版本"""
        final_result = None
        async for result in self.execute_stream(input_data):
            final_result = result
        return final_result or input_data
    
    async def execute_stream(self, input_data: Dict[str, Any]):
        """流式执行数据库保存节点"""
        print("💾 开始保存到数据库...")
        
        workflow_chat = input_data.get('workflow_chat')
        
        # 获取数据
        schedule_result = input_data.get('schedule_result', {})
        daily_schedules = input_data.get('daily_schedules', [])
        config = input_data.get('config', {})
        protagonist = input_data.get('protagonist', '方知衡')
        start_date = input_data.get('start_date', '')
        end_date = input_data.get('end_date', '')
        total_days = input_data.get('total_days', 0)
        schedule_type = input_data.get('schedule_type', 'weekly')
        
        if workflow_chat:
            await workflow_chat.add_node_message(
                "数据库保存",
                "正在将生成的日程数据保存到数据库...",
                "progress"
            )
        
        try:
            # 导入日程管理器
            from database.managers.schedule_manager import ScheduleManager
            schedule_manager = ScheduleManager()
            
            # 生成日程ID
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            schedule_id = f"SCHEDULE_{timestamp}"
            
            # 获取周期总结（如果启用且已在JSON中生成）
            cycle_summary = ""
            if config.get('enable_cycle_summary', False):
                if isinstance(schedule_result, dict) and 'cycle_summary' in schedule_result:
                    cycle_summary = schedule_result.get('cycle_summary', '')
                    logger.info(f"从JSON结果中提取周期总结，长度: {len(cycle_summary)} 字符")
                    if workflow_chat:
                        await workflow_chat.add_node_message(
                            "数据库保存",
                            f"已提取周期总结（{len(cycle_summary)}字符）",
                            "progress"
                        )
                else:
                    logger.warning("启用了周期总结功能但JSON结果中未找到cycle_summary字段")
            
            # 构建保存数据 - 需要从schedule_result中提取正确的数据
            if isinstance(schedule_result, dict) and 'daily_schedules' in schedule_result:
                # 从解析好的JSON数据中获取
                daily_schedules = schedule_result.get('daily_schedules', [])
                schedule_summary = schedule_result.get('schedule_summary', {})
                cycle_plan = schedule_result.get('cycle_plan', '')
                
                schedule_data = {
                    'schedule_id': schedule_id,
                    'schedule_name': f"{protagonist}的{schedule_type}日程_{start_date}",
                    'start_date': start_date,
                    'end_date': end_date,
                    'total_days': total_days,
                    'description': schedule_summary.get('日程特点', f"为{protagonist}生成的{total_days}天详细日程安排"),
                    'cycle_plan': cycle_plan,
                    'cycle_summary': cycle_summary,
                    'daily_schedules': daily_schedules
                }
            else:
                # 后备方案：使用基础数据
                schedule_data = {
                    'schedule_id': schedule_id,
                    'schedule_name': f"{protagonist}的{schedule_type}日程_{start_date}",
                    'start_date': start_date,
                    'end_date': end_date,
                    'total_days': total_days,
                    'description': f"为{protagonist}生成的{total_days}天详细日程安排",
                    'cycle_plan': '',
                    'cycle_summary': cycle_summary,
                    'daily_schedules': daily_schedules
                }
            
            # 保存到数据库
            success = schedule_manager.save_schedule_data(schedule_data, config)
            
            # 将日程数据保存为CSV文件
            if success and daily_schedules:
                try:
                    # 创建输出目录
                    output_dir = os.path.join(os.path.dirname(__file__), '../../workspace/annual_schedule_output')
                    os.makedirs(output_dir, exist_ok=True)
                    
                    # 使用固定CSV文件名，便于增量更新
                    csv_file_path = os.path.join(output_dir, f"schedule_summary.csv")
                    
                    # 定义CSV列头
                    csv_headers = [
                        "日期", "星期", "季节", "天气", "是否节假日", "节日名称",
                        "周期计划", "周期总结", "每日计划", "每日总结", "当日角色",
                        "上午内容", "上午角色",
                        "中午内容", "中午角色",
                        "下午内容", "下午角色",
                        "晚上内容", "晚上角色",
                        "夜间内容", "夜间角色"
                    ]
                    
                    # 检查文件是否存在，决定是追加还是创建新文件
                    file_exists = os.path.isfile(csv_file_path)
                    write_mode = 'a' if file_exists else 'w'
                    
                    # 写入CSV文件
                    with open(csv_file_path, write_mode, encoding='utf-8', newline='') as csvfile:
                        writer = csv.writer(csvfile)
                        
                        # 只在文件不存在时写入表头
                        if not file_exists:
                            writer.writerow(csv_headers)
                        
                        # 获取周期计划和周期总结
                        cycle_plan = schedule_result.get('cycle_plan', '')
                        cycle_summary = schedule_result.get('cycle_summary', '')
                        
                        # 遍历每天的日程数据
                        for day_data in daily_schedules:
                            date = day_data.get('date', '')
                            weekday = day_data.get('weekday_name', '')
                            weather = day_data.get('weather', '')
                            is_holiday = day_data.get('is_holiday', False)
                            holiday_name = day_data.get('holiday_name', '')
                            
                            # 根据日期确定季节（简单实现）
                            month = int(date.split('-')[1]) if '-' in date else 0
                            season = '春季'
                            if 3 <= month <= 5:
                                season = '春季'
                            elif 6 <= month <= 8:
                                season = '夏季'
                            elif 9 <= month <= 11:
                                season = '秋季'
                            else:
                                season = '冬季'
                            
                            daily_plan = day_data.get('daily_plan', '')
                            daily_summary = day_data.get('daily_summary', '')
                            
                            # 初始化时间段数据
                            time_slots_data = {
                                '上午': {'content': '', 'characters': []},
                                '中午': {'content': '', 'characters': []},
                                '下午': {'content': '', 'characters': []},
                                '晚上': {'content': '', 'characters': []},
                                '夜间': {'content': '', 'characters': []}
                            }
                            
                            # 提取时间段数据
                            time_slots = day_data.get('time_slots', [])
                            all_characters = set()  # 收集所有角色
                            
                            for slot in time_slots:
                                slot_name = slot.get('slot_name', '')
                                if slot_name in time_slots_data:
                                    time_slots_data[slot_name]['content'] = slot.get('story_content', '')
                                    chars = slot.get('involved_characters', [])
                                    time_slots_data[slot_name]['characters'] = chars
                                    # 添加到所有角色集合
                                    all_characters.update(chars)
                            
                            # 将所有角色合并为一个字符串
                            all_characters_str = ', '.join(all_characters)
                            
                            # 为了支持数据库保存，在每天的数据中添加时间段信息
                            # 这些字段将被传递给数据库保存函数
                            day_data['cycle_plan'] = cycle_plan
                            day_data['cycle_summary'] = cycle_summary
                            day_data['season'] = season
                            day_data['is_holiday'] = is_holiday
                            day_data['holiday_name'] = holiday_name
                            day_data['daily_characters'] = all_characters_str
                            
                            # 查找每个时间段的数据，并添加到day_data中
                            for time_slot in time_slots:
                                slot_name = time_slot.get('slot_name', '')
                                if slot_name == '上午':
                                    day_data['morning_content'] = time_slot.get('story_content', '')
                                    day_data['morning_characters'] = time_slot.get('involved_characters', [])
                                elif slot_name == '中午':
                                    day_data['noon_content'] = time_slot.get('story_content', '')
                                    day_data['noon_characters'] = time_slot.get('involved_characters', [])
                                elif slot_name == '下午':
                                    day_data['afternoon_content'] = time_slot.get('story_content', '')
                                    day_data['afternoon_characters'] = time_slot.get('involved_characters', [])
                                elif slot_name == '晚上':
                                    day_data['evening_content'] = time_slot.get('story_content', '')
                                    day_data['evening_characters'] = time_slot.get('involved_characters', [])
                                elif slot_name == '夜间':
                                    day_data['night_content'] = time_slot.get('story_content', '')
                                    day_data['night_characters'] = time_slot.get('involved_characters', [])
                            
                            # 确保所有字段都有默认值
                            if 'morning_content' not in day_data:
                                day_data['morning_content'] = ''
                                day_data['morning_characters'] = []
                            if 'noon_content' not in day_data:
                                day_data['noon_content'] = ''
                                day_data['noon_characters'] = []
                            if 'afternoon_content' not in day_data:
                                day_data['afternoon_content'] = ''
                                day_data['afternoon_characters'] = []
                            if 'evening_content' not in day_data:
                                day_data['evening_content'] = ''
                                day_data['evening_characters'] = []
                            if 'night_content' not in day_data:
                                day_data['night_content'] = ''
                                day_data['night_characters'] = []
                            
                            # 构建CSV行数据
                            row_data = [
                                date, weekday, season, weather, 'Yes' if is_holiday else 'No', holiday_name,
                                cycle_plan, cycle_summary, daily_plan, daily_summary, all_characters_str,
                                time_slots_data['上午']['content'], ', '.join(time_slots_data['上午']['characters']),
                                time_slots_data['中午']['content'], ', '.join(time_slots_data['中午']['characters']),
                                time_slots_data['下午']['content'], ', '.join(time_slots_data['下午']['characters']),
                                time_slots_data['晚上']['content'], ', '.join(time_slots_data['晚上']['characters']),
                                time_slots_data['夜间']['content'], ', '.join(time_slots_data['夜间']['characters'])
                            ]
                            
                            writer.writerow(row_data)
                    
                    logger.info(f"日程数据已保存为CSV文件: {csv_file_path}")
                    
                    if workflow_chat:
                        await workflow_chat.add_node_message(
                            "数据库保存",
                            f"日程数据已{'追加到' if file_exists else '保存为新'}CSV文件: schedule_summary.csv",
                            "success"
                        )
                    
                except Exception as csv_error:
                    logger.error(f"保存CSV文件失败: {csv_error}")
                    if workflow_chat:
                        await workflow_chat.add_node_message(
                            "数据库保存",
                            f"保存CSV文件失败: {str(csv_error)}",
                            "warning"
                        )
            
            if success:
                if workflow_chat:
                    await workflow_chat.add_node_message(
                        "数据库保存",
                        f"日程数据保存成功！日程ID：{schedule_id}",
                        "success"
                    )
                
                # 更新状态
                result_data = input_data.copy()
                result_data.update({
                    'schedule_id': schedule_id,
                    'save_success': True,
                    'save_message': f"日程已保存，ID：{schedule_id}"
                })
            else:
                if workflow_chat:
                    await workflow_chat.add_node_message(
                        "数据库保存",
                        "日程数据保存失败！",
                        "error"
                    )
                
                result_data = input_data.copy()
                result_data.update({
                    'save_success': False,
                    'save_message': "保存失败"
                })
        
        except Exception as e:
            logger.error(f"保存日程数据失败: {e}")
            
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "数据库保存",
                    f"保存失败：{str(e)}",
                    "error"
                )
            
            result_data = input_data.copy()
            result_data.update({
                'save_success': False,
                'save_message': f"保存失败：{str(e)}"
            })
        
        yield result_data