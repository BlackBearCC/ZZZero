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
            'location_variety': True
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
        return {
            'name': '方知衡',
            'type': 'protagonist',
            'description': '大学天文系教授、研究员，28岁，理性严谨、内敛温和、平等包容、责任感强',
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
                    
                    yield (
                        workflow_chat.update_node_state(self._get_node_id(node_name), "active"),
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
                        
                        # 实时更新进度信息
                        if content_length > 0:
                            yield (
                                workflow_chat._create_workflow_progress(),
                                "",
                                f"正在生成日程内容... 当前长度: {content_length} 字符",
                                False
                            )
                
                elif event_type == 'node_complete':
                    # 节点执行完成
                    node_display_name = self._get_node_display_name(node_name)
                    
                    yield (
                        workflow_chat.update_node_state(self._get_node_id(node_name), "completed"),
                        "",
                        f"{node_display_name}执行完成",
                        False
                    )
                
                elif event_type == 'node_error':
                    # 节点执行错误
                    error_msg = stream_event.get('error', '未知错误')
                    
                    await workflow_chat.add_node_message(
                        "系统",
                        f"节点执行失败: {error_msg}",
                        "error"
                    )
                    
                    yield (
                        workflow_chat.update_node_state(self._get_node_id(node_name), "error"),
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
                workflow_chat.update_node_state("generate", "error"),
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
        
        # 构建日程生成提示词
        generation_prompt = f"""
你是一名专业的日程规划师，需要为主角方知衡生成从{start_date}到{end_date}的详细日程安排。

# 主角信息
方知衡：大学天文系教授、研究员，28岁，理性严谨、内敛温和、平等包容、责任感强

# 日程需求
- 日程类型：{schedule_type}（周期规划）
- 日期范围：{start_date} 至 {end_date}，共{total_days}天
- 每天划分为5个时间段：夜间(23:00-06:00)、上午(06:00-11:00)、中午(11:00-14:00)、下午(14:00-18:00)、晚上(18:00-23:00)

# 参与角色
{', '.join(selected_characters)}

# 活动地点
{', '.join(selected_locations)}

# 日期信息
{json.dumps(dates_info, ensure_ascii=False, indent=2)}

# 生成要求
1. 为每天生成合理的日程安排，每个时间段都要有具体安排
2. 考虑工作日和休息日的区别，工作日以教学科研为主，休息日以休闲娱乐为主
3. 合理分配不同角色的出现频率，确保主要角色互动更频繁
4. 考虑天气、季节、节假日等因素对日程的影响
5. 为每天生成一个主题和总结
6. 确保日程安排的连贯性和合理性

# 输出格式
请按以下JSON格式输出日程安排：

```json
{{
  "schedule_summary": {{
    "总天数": {total_days},
    "周期类型": "{schedule_type}",
    "开始日期": "{start_date}",
    "结束日期": "{end_date}",
    "日程特点": "简要描述整体日程特点",
    "常规活动": ["活动1", "活动2", ...],
    "主要互动角色": ["角色1", "角色2", ...],
    "常去地点": ["地点1", "地点2", ...]
  }},
  "daily_schedules": [
    {{
      "date": "YYYY-MM-DD",
      "day_number": 1,
      "weekday_name": "周几",
      "is_holiday": true/false,
      "holiday_name": "节日名称（如果是节假日）",
      "weather": "天气情况",
      "daily_theme": "当日主题",
      "time_slots": [
        {{
          "slot_name": "夜间",
          "start_time": "23:00",
          "end_time": "06:00",
          "assigned_character": "角色名称",
          "activity_type": "活动类型",
          "location": "地点",
          "story_content": "详细内容描述"
        }},
        // ... 其他时间段
      ],
      "daily_summary": "当日总结"
    }},
    // ... 其他日期
  ]
}}
```

请确保输出结果是完整有效的JSON格式。生成的内容需要丰富详实，考虑主角的身份特点和日常习惯，以及与不同角色的互动方式。
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
                                display_content += f"""
<div style="background: #f8f9fa; border-left: 4px solid #6c757d; padding: 10px; margin: 10px 0; border-radius: 4px;">
🤔 思考过程：<br>
{think_content}
</div>"""
                            
                            if final_content.strip():
                                display_content += f"""
<div style="background: #e8f5e9; border-left: 4px solid #28a745; padding: 10px; margin: 10px 0; border-radius: 4px;">
📋 生成结果：<br>
{final_content}
</div>"""
                            
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
        try:
            from parsers.json_parser import JSONParser
            parser = JSONParser()
            
            json_content = self._extract_json_from_content(final_content)
            parsed_result = parser.parse(json_content)
            
            if parsed_result:
                # 生成成功，提取日程数据
                schedule_data = parsed_result
                daily_schedules = schedule_data.get('daily_schedules', [])
                logger.info(f"成功解析日程JSON结果，包含 {len(daily_schedules)} 天")
                
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
            
            # 构建保存数据
            schedule_data = {
                'schedule_id': schedule_id,
                'schedule_name': f"{protagonist}的{schedule_type}日程_{start_date}",
                'start_date': start_date,
                'end_date': end_date,
                'total_days': total_days,
                'description': f"为{protagonist}生成的{total_days}天详细日程安排",
                'daily_schedules': daily_schedules
            }
            
            # 保存到数据库
            success = schedule_manager.save_schedule_data(schedule_data, config)
            
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