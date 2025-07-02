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
        """创建日程生成图工作流 - 新版本：先规划周期，再分批生成"""
        self.graph = StateGraph(name="schedule_generation_workflow")
        
        # 创建节点
        cycle_planning_node = CyclePlanningNode()  # 新增：周期规划节点
        schedule_generate_node = ScheduleGenerateNode()  # 修改：分批生成节点
        database_save_node = ScheduleDatabaseSaveNode()
        
        # 添加节点到图
        self.graph.add_node("cycle_planning", cycle_planning_node)
        self.graph.add_node("schedule_generate", schedule_generate_node)
        self.graph.add_node("database_save", database_save_node)
        
        # 定义节点连接关系
        self.graph.add_edge("cycle_planning", "schedule_generate")
        self.graph.add_edge("schedule_generate", "database_save")
        
        # 设置入口点
        self.graph.set_entry_point("cycle_planning")
        
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
            'cycle_planning': '周期规划',
            'schedule_generate': '日程生成',
            'database_save': '数据库保存'
        }
        return name_mapping.get(node_name, node_name)
    
    def _get_node_id(self, node_name: str) -> str:
        """获取节点ID"""
        id_mapping = {
            'cycle_planning': 'planning',
            'schedule_generate': 'generate',
            'database_save': 'save'
        }
        return id_mapping.get(node_name, node_name)


class CyclePlanningNode(BaseNode):
    """周期规划节点 - 预先规划所有批次的周期计划"""
    
    def __init__(self):
        super().__init__(name="cycle_planning", stream=True)
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行周期规划节点 - 非流式版本"""
        final_result = None
        async for result in self.execute_stream(input_data):
            final_result = result
        return final_result or input_data
    
    async def execute_stream(self, input_data: Dict[str, Any]):
        """流式执行周期规划节点"""
        print("📋 开始周期规划...")
        
        workflow_chat = input_data.get('workflow_chat')
        llm = input_data.get('llm')
        
        # 获取配置参数
        start_date = input_data.get('start_date', '')
        end_date = input_data.get('end_date', '')
        total_days = input_data.get('total_days', 7)
        protagonist = input_data.get('protagonist', '方知衡')
        selected_characters = input_data.get('selected_characters', [])
        selected_locations = input_data.get('selected_locations', [])
        config = input_data.get('config', {})
        
        # 更新UI
        if workflow_chat:
            await workflow_chat.add_node_message(
                "周期规划",
                f"正在为{total_days}天时间范围制定周期规划...",
                "progress"
            )
        
        try:
            from datetime import datetime, timedelta
            import math
            
            # 计算需要多少个周期（每个周期7-15天）
            min_cycle_days = 7
            max_cycle_days = 15
            
            # 智能分配周期长度
            cycles = []
            remaining_days = total_days
            current_date = datetime.strptime(start_date, '%Y-%m-%d')
            
            cycle_num = 1
            while remaining_days > 0:
                # 根据剩余天数智能决定周期长度
                if remaining_days <= max_cycle_days:
                    cycle_days = remaining_days
                else:
                    # 优先选择较长的周期，但保证最后一个周期不会太短
                    if remaining_days <= max_cycle_days + min_cycle_days:
                        cycle_days = remaining_days // 2
                    else:
                        cycle_days = random.randint(min_cycle_days, max_cycle_days)
                
                cycle_end_date = current_date + timedelta(days=cycle_days - 1)
                
                cycles.append({
                    'cycle_number': cycle_num,
                    'start_date': current_date.strftime('%Y-%m-%d'),
                    'end_date': cycle_end_date.strftime('%Y-%m-%d'),
                    'total_days': cycle_days,
                    'status': 'planned'
                })
                
                current_date = cycle_end_date + timedelta(days=1)
                remaining_days -= cycle_days
                cycle_num += 1
            
            logger.info(f"智能分配了 {len(cycles)} 个周期，总计 {total_days} 天")
            
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "周期规划",
                    f"已智能分配 {len(cycles)} 个周期，每个周期 {min_cycle_days}-{max_cycle_days} 天",
                    "progress"
                )
            
            # 准备历史上下文
            protagonist_data = input_data.get('protagonist_data', '')
            characters_info = []
            for char_name in selected_characters:
                char_list = input_data.get('characters_data', {}).get("角色列表", {})
                if char_name in char_list:
                    char_info = char_list[char_name]
                    char_desc = f"{char_name}：{char_info.get('简介', '')}"
                    if char_info.get('性格'):
                        char_desc += f"，性格{char_info.get('性格')}"
                    characters_info.append(char_desc)
                else:
                    characters_info.append(char_name)
            
            # 获取上一批次总结信息（如果有）
            previous_summary = config.get('previous_batch_summary', '')
            
            # 构建周期规划提示词
            planning_prompt = f"""
你是一名专业的长期规划师，需要为主角{protagonist}制定从{start_date}到{end_date}（共{total_days}天）的整体周期规划。

# 主角信息
{protagonist_data}

{f"# 历史背景信息\\n{previous_summary}\\n" if previous_summary else ''}

# 参与角色
{chr(10).join(characters_info)}

# 活动地点
{', '.join(selected_locations)}

# 周期分配
已智能分配为{len(cycles)}个周期：
{json.dumps(cycles, ensure_ascii=False, indent=2)}

# 规划要求

## 整体故事弧线
1. **时间跨度感**：{total_days}天是一个相对较长的时间段，需要体现时间的推移和变化
2. **角色关系发展**：每个角色的关系应该有明显的发展轨迹，不是静态的
3. **事件层次性**：包含日常事件、重要事件、转折事件等不同层次
4. **季节变化**：体现季节对活动和心情的影响
5. **工作生活平衡**：{protagonist}的学术工作与个人生活的平衡发展

## 周期特色差异
1. **前期周期**：适应新环境、建立日常节奏、初步社交
2. **中期周期**：深入工作、关系深化、面临挑战
3. **后期周期**：成果显现、关系稳定、新的规划

## 每个周期规划内容
为每个周期制定：
- **周期主题**：这个周期的核心主题和重点
- **主要目标**：{protagonist}在这个周期想要达成的具体目标
- **重点角色**：这个周期中会重点互动的角色（2-3个）
- **核心地点**：主要活动场所
- **关键事件**：预计会发生的重要事件
- **情感基调**：整个周期的情感发展方向
- **衔接要点**：与前后周期的连接点

# 输出格式
请按以下JSON格式输出周期规划，禁止输出任何其他内容：

```json
{{
  "overall_plan": {{
    "total_days": {total_days},
    "total_cycles": {len(cycles)},
    "story_theme": "整个时间段的故事主题",
    "character_arcs": {{
      "角色名1": "该角色的发展轨迹",
      "角色名2": "该角色的发展轨迹"
    }},
    "major_milestones": [
      "重要节点1",
      "重要节点2"
    ]
  }},
  "cycle_plans": [
    {{
      "cycle_number": 1,
      "start_date": "YYYY-MM-DD",
      "end_date": "YYYY-MM-DD", 
      "total_days": 7,
      "cycle_theme": "周期主题",
      "main_objectives": [
        "目标1",
        "目标2"
      ],
      "focus_characters": ["角色名1", "角色名2"],
      "core_locations": ["地点1", "地点2"],
      "key_events": [
        "事件1",
        "事件2"
      ],
      "emotional_tone": "情感基调描述",
      "connection_points": {{
        "from_previous": "与前周期的衔接",
        "to_next": "与后周期的衔接"
      }}
    }},
    // ... 其他周期
  ]
}}
```

# 重要要求
1. **连贯性**：确保各周期之间有自然的过渡和发展
2. **平衡性**：角色和地点的分配要相对均衡
3. **现实性**：规划要符合{protagonist}的身份和云枢市的设定
4. **发展性**：每个周期都要有明确的进展，避免重复
5. **完整性**：为所有{len(cycles)}个周期都制定详细规划

请开始制定这个全面而详细的周期规划，禁止输出任何其他内容。
"""
            
            # 调用LLM生成周期规划
            logger.info(f"周期规划: 开始LLM调用，提示词长度: {len(planning_prompt)}")
            
            if llm:
                # 构建消息
                from core.types import Message, MessageRole
                message = Message(role=MessageRole.USER, content=planning_prompt)
                messages = [message]
                
                # 流式调用LLM（豆包自带打印）
                final_content = ""
                
                async for chunk_data in llm.stream_generate(
                    messages, 
                    mode="think",
                    return_dict=True
                ):
                    content_part = chunk_data.get("content", "")
                    final_content += content_part
                
                logger.info(f"周期规划生成完成，内容长度: {len(final_content)}")
            else:
                raise Exception("LLM未初始化")
            
            # 解析JSON结果
            cycle_planning_data = None
            try:
                from parsers.json_parser import JSONParser
                parser = JSONParser()
                
                json_content = self._extract_json_from_content(final_content)
                parsed_result = parser.parse(json_content)
                
                if parsed_result and 'cycle_plans' in parsed_result:
                    cycle_planning_data = parsed_result
                    logger.info(f"成功解析周期规划，包含 {len(cycle_planning_data['cycle_plans'])} 个周期")
                    
                    if workflow_chat:
                        await workflow_chat.add_node_message(
                            "周期规划",
                            f"✅ 成功生成 {len(cycle_planning_data['cycle_plans'])} 个周期的详细规划",
                            "success"
                        )
                else:
                    raise Exception("解析结果中缺少cycle_plans字段")
                    
            except Exception as parse_error:
                logger.error(f"周期规划JSON解析失败: {parse_error}")
                # 使用原始分配的周期作为后备方案
                cycle_planning_data = {
                    'overall_plan': {
                        'total_days': total_days,
                        'total_cycles': len(cycles),
                        'story_theme': f"{protagonist}的{total_days}天生活规划",
                        'character_arcs': {},
                        'major_milestones': []
                    },
                    'cycle_plans': cycles
                }
                
                if workflow_chat:
                    await workflow_chat.add_node_message(
                        "周期规划",
                        f"⚠️ JSON解析失败，使用基础周期分配（{len(cycles)}个周期）",
                        "warning"
                    )
            
            # 输出最终结果
            output_data = input_data.copy()
            output_data['cycle_planning_result'] = cycle_planning_data
            output_data['cycles'] = cycle_planning_data['cycle_plans']
            output_data['current_cycle_index'] = 0  # 当前处理的周期索引
            
            logger.info(f"✅ 周期规划完成，生成了 {len(cycle_planning_data['cycle_plans'])} 个周期")
            yield output_data
            
        except Exception as e:
            logger.error(f"周期规划失败: {e}")
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "周期规划",
                    f"❌ 规划失败: {str(e)}",
                    "error"
                )
            raise Exception(f"周期规划失败: {str(e)}")
    
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


class ScheduleGenerateNode(BaseNode):
    """日程生成节点 - 分批渐进式生成，一次生成3天日程"""
    
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
        """流式执行日程生成节点 - 分批渐进式生成"""
        print("📅 开始分批日程生成...")
        
        workflow_chat = input_data.get('workflow_chat')
        llm = input_data.get('llm')
        
        # 获取周期规划数据
        cycles = input_data.get('cycles', [])
        current_cycle_index = input_data.get('current_cycle_index', 0)
        cycle_planning_result = input_data.get('cycle_planning_result', {})
        
        if not cycles:
            raise Exception("缺少周期规划数据，请先执行周期规划节点")
        
        # 获取当前周期信息
        if current_cycle_index >= len(cycles):
            # 所有周期都已完成
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "日程生成",
                    "✅ 所有周期的日程生成已完成！",
                    "success"
                )
            
            output_data = input_data.copy()
            output_data['generation_complete'] = True
            yield output_data
            return
        
        current_cycle = cycles[current_cycle_index]
        cycle_start_date = current_cycle['start_date']
        cycle_end_date = current_cycle['end_date']
        cycle_total_days = current_cycle['total_days']
        
        # 获取配置参数
        protagonist = input_data.get('protagonist', '方知衡')
        selected_characters = input_data.get('selected_characters', [])
        selected_locations = input_data.get('selected_locations', [])
        holidays_data = input_data.get('holidays_data', {})
        include_holidays = input_data.get('include_holidays', True)
        
        # 更新UI - 开始状态
        if workflow_chat:
            await workflow_chat.add_node_message(
                "日程生成",
                f"正在生成第 {current_cycle_index + 1}/{len(cycles)} 个周期的日程 ({cycle_start_date} - {cycle_end_date}, {cycle_total_days}天)...",
                "progress"
            )
        
        # 获取当前周期的规划信息
        current_cycle_plan = current_cycle.get('cycle_theme', '')
        current_cycle_objectives = current_cycle.get('main_objectives', [])
        focus_characters = current_cycle.get('focus_characters', [])
        core_locations = current_cycle.get('core_locations', [])
        key_events = current_cycle.get('key_events', [])
        emotional_tone = current_cycle.get('emotional_tone', '')
        
        # 获取历史总结上下文（前面周期的总结）
        history_context = ""
        if current_cycle_index > 0:
            # 获取前面周期的总结作为历史上下文
            try:
                from database.managers.schedule_manager import ScheduleManager
                schedule_manager = ScheduleManager()
                previous_summary = schedule_manager.get_latest_cycle_summary(before_date=cycle_start_date)
                if previous_summary:
                    history_context = f"## 历史周期总结\n{previous_summary}\n"
                    logger.info(f"获取到历史周期总结，长度: {len(previous_summary)} 字符")
            except Exception as e:
                logger.warning(f"准备历史周期总结失败: {e}")
        
        # 分批生成：将周期分成3天一批
        batch_size = 3  # 每次生成3天
        cycle_daily_schedules = []  # 存储整个周期的日程
        current_batch_start = 0

        # 准备当前周期的所有日期信息
        cycle_dates_info = []
        try:
            from datetime import datetime, timedelta
            
            # 解析周期日期范围
            cycle_start = datetime.strptime(cycle_start_date, '%Y-%m-%d')
            cycle_end = datetime.strptime(cycle_end_date, '%Y-%m-%d')
            
            # 获取周期内的所有日期信息
            current_date = cycle_start
            day_number = 1
            while current_date <= cycle_end:
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
                cycle_dates_info.append({
                    'date': date_str,
                    'weekday': weekday,
                    'weekday_name': weekday_name,
                    'is_holiday': is_holiday,
                    'holiday_name': holiday_name,
                    'day_number': day_number,  # 周期内的天数
                    'cycle_day_number': day_number
                })
                
                current_date += timedelta(days=1)
                day_number += 1
                
        except Exception as e:
            logger.error(f"周期日期处理失败: {e}")
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "日程生成",
                    f"周期日期处理失败: {str(e)}",
                    "error"
                )
            raise Exception(f"周期日期处理失败: {str(e)}")
            
        # 分批生成当前周期的日程
        while current_batch_start < len(cycle_dates_info):
            # 确定当前批次的日期范围
            batch_end = min(current_batch_start + batch_size, len(cycle_dates_info))
            batch_dates = cycle_dates_info[current_batch_start:batch_end]
            batch_days_count = len(batch_dates)
            
            batch_start_date = batch_dates[0]['date']
            batch_end_date = batch_dates[-1]['date']
            
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "日程生成",
                    f"正在生成第 {current_batch_start//batch_size + 1} 批次：{batch_start_date} - {batch_end_date} ({batch_days_count}天)",
                    "progress"
                )
        
            # 构建角色信息字符串（优先使用当前周期重点角色）
            characters_info = []
            # 先添加重点角色
            for char_name in focus_characters:
                char_list = input_data.get('characters_data', {}).get("角色列表", {})
                if char_name in char_list:
                    char_info = char_list[char_name]
                    char_desc = f"{char_name}（本周期重点）：{char_info.get('简介', '')}"
                    if char_info.get('性格'):
                        char_desc += f"，性格{char_info.get('性格')}"
                    characters_info.append(char_desc)
                else:
                    characters_info.append(f"{char_name}（本周期重点）")
            
            # 再添加其他角色
            for char_name in selected_characters:
                if char_name not in focus_characters:
                    char_list = input_data.get('characters_data', {}).get("角色列表", {})
                    if char_name in char_list:
                        char_info = char_list[char_name]
                        char_desc = f"{char_name}：{char_info.get('简介', '')}"
                        if char_info.get('性格'):
                            char_desc += f"，性格{char_info.get('性格')}"
                        characters_info.append(char_desc)
                    else:
                        characters_info.append(char_name)
            
            # 获取主角信息
            protagonist_data = input_data.get('protagonist_data', '')
            
            # 构建批次生成提示词
            generation_prompt = f"""
你是一名专业的日程规划师和故事编剧，需要为主角{protagonist}生成{batch_start_date}到{batch_end_date}的详细日程安排（共{batch_days_count}天）。

这是一个分批渐进式生成任务，当前生成的是一个更大周期中的一部分。

# 主角信息
{protagonist_data}

{history_context if history_context else ''}

# 当前周期规划背景
## 周期信息
- 周期日期：{cycle_start_date} 至 {cycle_end_date}（第{current_cycle_index + 1}个周期，共{len(cycles)}个周期）
- 周期主题：{current_cycle_plan}
- 情感基调：{emotional_tone}

## 周期目标
{chr(10).join([f"- {obj}" for obj in current_cycle_objectives])}

## 重点角色（本周期）
{chr(10).join([f"- {char}" for char in focus_characters])}

## 核心地点（本周期）
{chr(10).join([f"- {loc}" for loc in core_locations])}

## 关键事件（本周期预期）
{chr(10).join([f"- {event}" for event in key_events])}

# 当前批次任务
- 批次日期：{batch_start_date} 至 {batch_end_date}
- 批次天数：{batch_days_count}天
- 这是当前周期的第 {current_batch_start//batch_size + 1} 个批次
- 每天划分为5个时间段：夜间(23:00-06:00)、上午(06:00-11:00)、中午(11:00-14:00)、下午(14:00-18:00)、晚上(18:00-23:00)

# 参与角色详情
{chr(10).join(characters_info)}

# 可用地点
{', '.join(selected_locations)}

# 批次日期信息
{json.dumps(batch_dates, ensure_ascii=False, indent=2)}

# 核心生成要求

## 分批生成连贯性
1. **批次衔接**：虽然只生成{batch_days_count}天，但要与前后批次自然衔接
2. **周期目标推进**：在这{batch_days_count}天中推进当前周期的目标和主题
3. **重点角色优先**：优先安排重点角色的互动，其他角色根据情况穿插

## 云枢市真实生活感
1. **角色分布**：重点角色多安排，其他角色适当穿插
2. **日常随机事件**：增加偶遇、意外发现等真实生活元素
3. **城市生活细节**：路边小店、街头艺人、流浪动物、天气变化等
4. **环境互动**：与环境、动物、自然现象的互动，体现生活的丰富性

## 故事性要求
1. **情感推进**：每个角色的出现都应该有情感发展，推进周期主题
2. **细节丰富度**：每个时间段的描述包含具体的对话片段、内心活动、环境描写
3. **事件连贯性**：当前批次内的事件要相互呼应，形成完整的故事片段
4. **生活真实感**：包含工作压力、情绪波动、小确幸、意外惊喜等真实元素

## 计划与总结的区别
- **每日计划(daily_plan)**：{protagonist}早晨醒来时对这一天的预期和安排，基于他现有的信息和经验
- **每日总结(daily_summary)**：一天结束后对实际发生事件的回顾，可能与计划有出入，包含意外和惊喜
- **批次总结(batch_summary)**：{batch_days_count}天结束后的阶段性总结，关注这几天的重要发展

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
请按以下JSON格式输出批次日程安排：

```json
{{
  "batch_info": {{
    "批次天数": {batch_days_count},
    "批次开始日期": "{batch_start_date}",
    "批次结束日期": "{batch_end_date}",
    "所属周期": {current_cycle_index + 1},
    "周期主题": "{current_cycle_plan}",
    "批次特点": "描述这{batch_days_count}天的主要特色和故事发展",
    "重点角色": {focus_characters},
    "主要地点": {core_locations}
  }},

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
  "batch_summary": "批次总结：这{batch_days_count}天的重要发展和变化，第三人称以主角为主体，200-300字，重点关注：1. 周期目标的推进情况 2. 重点角色关系的发展 3. 关键事件的进展 4. 情感状态的变化 5. 为下个批次的铺垫",
}}
```

# 重要提醒
1. **分批生成要求**：
   - 只生成{batch_days_count}天的日程，不要生成整个周期
   - 要体现周期规划的主题和目标，但重点是当前批次
   - 要为后续批次留下自然的衔接点

2. **数据完整性要求**：
   - daily_plan：每天都要有具体的早晨计划
   - 每天必须有5个完整的时间段（夜间、上午、中午、下午、晚上）
   - involved_characters：每个时间段都要明确列出涉及的角色名称列表
   - batch_summary：必须包含这{batch_days_count}天的阶段性总结

3. **故事质量要求**：
   - 每个时间段的story_content必须丰富详实，像小说片段一样生动
   - 各时间段的故事必须是独立完整的，能够被单独提取和理解
   - 角色对话要符合各自的性格特点，有真实感
   - 增加随机事件：意外发现、巧遇等云枢市生活细节
   - 情节要有起伏，包含工作压力、小确幸、意外惊喜等真实元素
   - 禁止有任何男女恋爱元素
   - 禁止提起天文专业内容，主角不是工作狂，说话也是正常人

4. **角色处理要求**：
   - 重点角色要多安排，体现周期主题
   - 其他角色根据生活逻辑自然出现
   - 可以创造临时角色（如店主、路人、小动物）增加真实感
   - involved_characters中只需列出角色名称，不需要描述

5. **技术要求**：
   - 确保JSON格式完全正确，可以被程序解析
   - 每个字段都要填写完整，不能为空
   - 关注batch_summary字段，它是本批次的重要总结

请开始生成这{batch_days_count}天充满云枢市生活真实感的详细日程安排。
"""
        
            # 调用LLM生成当前批次的日程
            if llm:
                try:
                    # 构建消息列表
                    from core.types import Message, MessageRole
                    message = Message(role=MessageRole.USER, content=generation_prompt)
                    messages = [message]
                    
                    logger.info(f"日程生成批次 {current_batch_start//batch_size + 1}: 开始LLM调用，提示词长度: {len(generation_prompt)}")
                    
                    # 流式调用LLM（豆包自带打印）
                    final_content = ""
                    
                    async for chunk_data in llm.stream_generate(
                        messages, 
                        mode="think",
                        return_dict=True
                    ):
                        content_part = chunk_data.get("content", "")
                        final_content += content_part
                    
                    logger.info(f"批次 {current_batch_start//batch_size + 1} LLM生成完成，内容长度: {len(final_content)}")
                            
                except Exception as e:
                    error_msg = f"批次 {current_batch_start//batch_size + 1} LLM调用失败: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    raise Exception(error_msg)
            else:
                raise Exception("LLM未初始化")
            
            # 解析当前批次的JSON结果
            batch_data = None
            try:
                json_content = self._extract_json_from_content(final_content)
                from parsers.json_parser import JSONParser
                parser = JSONParser()
                parsed_result = parser.parse(json_content)
                
                if parsed_result and 'daily_schedules' in parsed_result:
                    batch_data = parsed_result
                    batch_daily_schedules = batch_data.get('daily_schedules', [])
                    logger.info(f"批次 {current_batch_start//batch_size + 1} 成功解析，包含 {len(batch_daily_schedules)} 天")
                    
                    # 合并到周期日程中
                    cycle_daily_schedules.extend(batch_daily_schedules)
                    
                    if workflow_chat:
                        await workflow_chat.add_node_message(
                            "日程生成",
                            f"✅ 批次 {current_batch_start//batch_size + 1} 生成完成（{len(batch_daily_schedules)}天）",
                            "success"
                        )
                else:
                    raise Exception(f"批次解析失败：缺少daily_schedules字段")
                    
            except Exception as parse_error:
                logger.error(f"批次 {current_batch_start//batch_size + 1} JSON解析失败: {parse_error}")
                if workflow_chat:
                    await workflow_chat.add_node_message(
                        "日程生成",
                        f"⚠️ 批次 {current_batch_start//batch_size + 1} 解析失败，跳过",
                        "warning"
                    )
            
            # 更新批次进度
            current_batch_start += batch_size
            
            # 批次间短暂休息
            await asyncio.sleep(1)
                
        # 当前周期所有批次生成完成，构建周期结果
        if cycle_daily_schedules:
            # 生成周期总结
            cycle_summary = await self._generate_cycle_summary(
                current_cycle, cycle_daily_schedules, llm, workflow_chat
            )
            
            # 构建周期完整数据
            schedule_data = {
                'cycle_info': {
                    'cycle_number': current_cycle_index + 1,
                    'start_date': cycle_start_date,
                    'end_date': cycle_end_date,
                    'total_days': cycle_total_days,
                    'cycle_theme': current_cycle_plan,
                    'focus_characters': focus_characters,
                    'core_locations': core_locations
                },
                'daily_schedules': cycle_daily_schedules,
                'cycle_summary': cycle_summary
            }
            
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "日程生成",
                    f"✅ 第 {current_cycle_index + 1} 个周期生成完成！共 {len(cycle_daily_schedules)} 天，{len(cycle_daily_schedules)//batch_size + (1 if len(cycle_daily_schedules)%batch_size else 0)} 个批次",
                    "success"
                )
        else:
            # 没有生成任何日程
            schedule_data = {"error": "周期内没有成功生成任何日程"}
            logger.error("周期内没有成功生成任何日程")
            
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "日程生成",
                    "❌ 当前周期生成失败，没有成功的批次",
                    "error"
                )
        
        # 更新输出数据
        output_data = input_data.copy()
        output_data['schedule_result'] = schedule_data
        output_data['daily_schedules'] = cycle_daily_schedules
        output_data['current_cycle_index'] = current_cycle_index + 1  # 指向下一个周期
        
        print(f"✅ 周期 {current_cycle_index + 1} 日程生成完成")
        yield output_data
        
    async def _generate_cycle_summary(self, cycle_info: Dict, daily_schedules: List[Dict], llm, workflow_chat) -> str:
        """生成周期总结"""
        try:
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "日程生成",
                    "正在生成周期总结...",
                    "progress"
                )
            
            # 提取周期关键信息
            cycle_theme = cycle_info.get('cycle_theme', '')
            objectives = cycle_info.get('main_objectives', [])
            focus_characters = cycle_info.get('focus_characters', [])
            
            # 统计各角色出现次数
            character_stats = {}
            location_stats = {}
            
            for day in daily_schedules:
                for slot in day.get('time_slots', []):
                    # 统计角色
                    chars = slot.get('involved_characters', [])
                    for char in chars:
                        character_stats[char] = character_stats.get(char, 0) + 1
                    
                    # 统计地点
                    location = slot.get('location', '')
                    if location:
                        location_stats[location] = location_stats.get(location, 0) + 1
            
            # 构建总结提示词
            summary_prompt = f"""
根据以下信息，为这个周期生成一个简洁的总结（300字以内）：

## 周期信息
- 主题：{cycle_theme}
- 目标：{', '.join(objectives)}
- 重点角色：{', '.join(focus_characters)}
- 实际天数：{len(daily_schedules)}天

## 角色互动统计
{chr(10).join([f"- {char}: {count}次互动" for char, count in sorted(character_stats.items(), key=lambda x: x[1], reverse=True)[:5]])}

## 地点活动统计  
{chr(10).join([f"- {loc}: {count}次" for loc, count in sorted(location_stats.items(), key=lambda x: x[1], reverse=True)[:5]])}

请生成一个第三人称的周期总结，重点关注：
1. 周期主题的体现和目标达成情况
2. 重点角色关系的发展变化
3. 主要活动和重要事件
4. 方知衡的成长和变化
5. 为下个周期的铺垫

要求：简洁明了，突出重点，300字以内。
"""
            
            # 调用LLM生成总结（豆包自带打印）
            from core.types import Message, MessageRole
            message = Message(role=MessageRole.USER, content=summary_prompt)
            messages = [message]
            
            summary_content = ""
            async for chunk_data in llm.stream_generate(messages, mode="normal", return_dict=True):
                summary_content += chunk_data.get("content", "")
            
            # 清理总结内容
            summary_content = summary_content.strip()
            if len(summary_content) > 500:
                summary_content = summary_content[:500] + "..."
            
            logger.info(f"周期总结生成完成，长度: {len(summary_content)} 字符")
            return summary_content
            
        except Exception as e:
            logger.error(f"生成周期总结失败: {e}")
            return f"周期{cycle_info.get('cycle_number', '')}完成，共{len(daily_schedules)}天，主题：{cycle_info.get('cycle_theme', '')}。"
        
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