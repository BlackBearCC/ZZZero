"""
剧情生成工作流 - 基于Graph+Node的剧情创作系统
集成角色库、地点库、剧情生成等功能
"""

import json
import asyncio
import csv
import random
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.graph import StateGraph
from core.base import BaseNode
from llm.base import LLMFactory
from core.types import LLMConfig, TaskResult, Message, MessageRole

logger = logging.getLogger(__name__)

class StoryWorkflow:
    """剧情生成工作流管理器"""
    
    def __init__(self, llm=None):
        self.llm = llm
        self.graph = None
        self.characters_data = {}
        self.locations_data = {}
        self.protagonist_data = ""  # 主角方知衡的详细人设
        self.current_config = {
            'protagonist': '方知衡',  # 固定主角
            'selected_characters': [],
            'selected_locations': [],
            'story_type': 'daily_life',  # daily_life, romance, adventure, mystery
            'story_length': 'medium',    # short, medium, long
            'relationship_depth': 'casual',  # casual, close, intimate
            'time_setting': 'current',   # current, specific_date
            'mood_tone': 'neutral',      # light, neutral, serious, dramatic
            'interaction_level': 'normal'  # minimal, normal, intensive
        }
        
        # 加载角色、地点和主角数据
        self._load_game_data()
        self._load_protagonist_data()
    
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
    
    def get_protagonist_info(self) -> Dict[str, Any]:
        """获取主角信息"""
        return {
            'name': '方知衡',
            'type': 'protagonist',
            'description': '云枢大学天文系客座教授、香丘天文院研究员，28岁，理性严谨、内敛温和、平等包容、责任感强',
            'full_profile': self.protagonist_data[:200] + "..." if len(self.protagonist_data) > 200 else self.protagonist_data
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
    
    def get_character_details(self, character_name: str) -> Dict[str, Any]:
        """获取指定角色的详细信息"""
        char_list = self.characters_data.get("角色列表", {})
        char_info = char_list.get(character_name, {})
        
        if not char_info:
            return {}
            
        return {
            'name': character_name,
            'age': char_info.get('年龄', '未知'),
            'personality': char_info.get('性格', ''),
            'description': char_info.get('简介', ''),
            'backstory': char_info.get('背景故事', ''),
            'relationships': char_info.get('人际关系', {}),
            'habits': char_info.get('生活习惯', []),
            'appearance': char_info.get('外貌特征', ''),
            'skills': char_info.get('特长技能', []),
            'locations': char_info.get('活动地点', []),
            'plots': char_info.get('可触发剧情', []),
            'dialogue_style': char_info.get('对话风格', ''),
            'motivations': char_info.get('动机目标', [])
        }
    
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
    
    def update_config(self, config_updates: Dict[str, Any]):
        """更新工作流配置"""
        self.current_config.update(config_updates)
    
    async def create_story_graph(self) -> StateGraph:
        """创建剧情生成图工作流"""
        self.graph = StateGraph(name="story_generation_workflow")
        
        # 创建节点（移除角色分析节点）
        story_plan_node = StoryPlanningNode()
        plot_generation_node = PlotGenerationNode()
        csv_export_node = CSVExportNode()
        
        # 添加节点到图
        self.graph.add_node("story_planning", story_plan_node)
        self.graph.add_node("plot_generation", plot_generation_node)
        self.graph.add_node("csv_export", csv_export_node)
        
        # 定义节点连接关系（直接从规划到生成）
        self.graph.add_edge("story_planning", "plot_generation")
        self.graph.add_edge("plot_generation", "csv_export")
        
        # 设置入口点
        self.graph.set_entry_point("story_planning")
        
        return self.graph
    
    async def execute_story_generation(self, config: Dict[str, Any]) -> TaskResult:
        """执行剧情生成工作流"""
        if not self.graph:
            await self.create_story_graph()
        
        # 准备初始输入
        initial_input = {
            'characters_data': self.characters_data,
            'locations_data': self.locations_data,
            'protagonist_data': self.protagonist_data,
            'config': config,
            'protagonist': config.get('protagonist', '方知衡'),
            'selected_characters': config.get('selected_characters', []),
            'selected_locations': config.get('selected_locations', []),
            'story_type': config.get('story_type', 'daily_life'),
            'story_length': config.get('story_length', 'medium'),
            'relationship_depth': config.get('relationship_depth', 'casual'),
            'time_setting': config.get('time_setting', 'current'),
            'mood_tone': config.get('mood_tone', 'neutral'),
            'interaction_level': config.get('interaction_level', 'normal')
        }
        
        # 编译并执行图工作流
        compiled_graph = self.graph.compile()
        result = await compiled_graph.invoke(initial_input)
        
        return result

    async def execute_workflow_stream(self, config: Dict[str, Any], workflow_chat):
        """流式执行工作流 - 使用StateGraph自动编排"""
        try:
            # 准备初始输入
            initial_input = {
                'characters_data': self.characters_data,
                'locations_data': self.locations_data,
                'protagonist_data': self.protagonist_data,  # 添加主角完整人设
                'config': config,
                'protagonist': config.get('protagonist', '方知衡'),
                'selected_characters': config.get('selected_characters', []),
                'selected_locations': config.get('selected_locations', []),
                'story_type': config.get('story_type', 'daily_life'),
                'story_length': config.get('story_length', 'medium'),
                'relationship_depth': config.get('relationship_depth', 'casual'),
                'time_setting': config.get('time_setting', 'current'),
                'mood_tone': config.get('mood_tone', 'neutral'),
                'interaction_level': config.get('interaction_level', 'normal'),
                'workflow_chat': workflow_chat,  # 传递UI更新器
                'llm': self.llm  # 传递LLM实例
            }
            
            # 创建并编译图工作流
            if not self.graph:
                await self.create_story_graph()
            
            compiled_graph = self.graph.compile()
            
            # 使用图的流式执行
            async for stream_event in compiled_graph.stream(initial_input):
                event_type = stream_event.get('type')
                node_name = stream_event.get('node')
                
                if event_type == 'start':
                    # 工作流开始
                    yield (
                        workflow_chat._create_workflow_progress(),
                        "",
                        "工作流开始执行...",
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
                    # 节点流式执行中 - 实时更新UI显示进度
                    intermediate_result = stream_event.get('intermediate_result')
                    if intermediate_result and intermediate_result.state_update:
                        # 获取当前生成的内容长度
                        content_length = 0
                        for key in ['planning_result', 'plot_content']:
                            if key in intermediate_result.state_update:
                                content_length = len(intermediate_result.state_update[key])
                                break
                        
                        # 实时更新进度信息 - 重要：获取最新的进度HTML，因为节点内部已经更新了结果
                        if content_length > 0:
                            yield (
                                workflow_chat._create_workflow_progress(),  # 这个会包含节点内部更新的最新内容
                                "",  # 快捷回复区域保持空
                                f"正在生成内容... 当前长度: {content_length} 字符",
                                False  # 发送按钮保持禁用
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
                        "工作流执行完成",
                        False
                    )
                
                # 其他事件类型可以忽略或记录日志
                else:
                    # 持续更新UI以保持流畅性
                    yield (
                        workflow_chat._create_workflow_progress(),
                        "",
                        "工作流执行中...",
                        False
                    )
                
        except Exception as e:
            logger.error(f"工作流流式执行失败: {e}")
            await workflow_chat.add_node_message(
                "系统",
                f"工作流执行失败: {str(e)}",
                "error"
            )
            yield (
                workflow_chat.update_node_state("planning", "error"),
                "",
                "",
                False
            )
    
    def _get_node_display_name(self, node_name: str) -> str:
        """获取节点显示名称"""
        name_mapping = {
            'story_planning': '剧情规划',
            'plot_generation': '剧情生成',
            'csv_export': 'CSV导出'
        }
        return name_mapping.get(node_name, node_name)
    
    def _get_node_id(self, node_name: str) -> str:
        """获取节点ID"""
        id_mapping = {
            'story_planning': 'planning',
            'plot_generation': 'plot', 
            'csv_export': 'export'
        }
        return id_mapping.get(node_name, node_name)


class StoryPlanningNode(BaseNode):
    """剧情规划节点 - 分析角色关系和故事大纲"""
    
    def __init__(self):
        super().__init__(name="story_planning", stream=True)
    
    async def execute_stream(self, input_data: Dict[str, Any]):
        """流式执行剧情规划节点 - 每个LLM chunk都yield"""
        print("🎯 开始剧情规划...")
        
        workflow_chat = input_data.get('workflow_chat')
        llm = input_data.get('llm')
        
        # 获取所有配置参数
        protagonist_data = input_data.get('protagonist_data', '')
        characters_data = input_data.get('characters_data', {})
        locations_data = input_data.get('locations_data', {})
        selected_characters = input_data.get('selected_characters', [])
        selected_locations = input_data.get('selected_locations', [])
        story_type = input_data.get('story_type', 'daily_life')
        story_length = input_data.get('story_length', 'medium')
        relationship_depth = input_data.get('relationship_depth', 'casual')
        time_setting = input_data.get('time_setting', 'current')
        mood_tone = input_data.get('mood_tone', 'neutral')
        interaction_level = input_data.get('interaction_level', 'normal')
        
        # 更新UI - 开始状态
        if workflow_chat:
            await workflow_chat.add_node_message(
                "剧情规划",
                "正在分析主角方知衡与选定角色的关系，生成剧情框架...",
                "progress"
            )
        
        # 构建详细的角色信息
        character_details = []
        char_list = characters_data.get("角色列表", {})
        for char_name in selected_characters:
            if char_name in char_list:
                char_info = char_list[char_name]
                detail = f"""
## {char_name}

- 年龄：{char_info.get('年龄', '未知')}
- 性格：{char_info.get('性格', '')}
- 简介：{char_info.get('简介', '')}
- 背景故事：{char_info.get('背景故事', '')}
- 活动地点：{', '.join(char_info.get('活动地点', []))}
- 人际关系：{char_info.get('人际关系', {})}
- 可触发剧情：{', '.join(char_info.get('可触发剧情', []))}
"""
                character_details.append(detail)
        
        # 构建详细的地点信息
        location_details = []
        districts = locations_data.get("districts", {})
        for loc_name in selected_locations:
            for district_name, district_info in districts.items():
                locations = district_info.get("locations", {})
                for location_key, location_info in locations.items():
                    if location_info.get('name') == loc_name or location_key == loc_name:
                        detail = f"""
## {location_info.get('name', loc_name)}（{district_info.get('name', district_name)}区）

- 类型：{location_info.get('type', '')}
- 描述：{location_info.get('description', '')}
- 氛围：{location_info.get('atmosphere', '')}
- 关键词：{', '.join(location_info.get('keywords', []))}
"""
                        location_details.append(detail)
        
        # 构建通用的剧情规划提示词
        planning_prompt = f"""
你是一名专业的剧情策划师，需要基于以下信息制定剧情规划框架：

# 主角设定

{protagonist_data}

# 参与角色信息

{''.join(character_details) if character_details else '无其他角色参与'}

# 地点信息

{''.join(location_details) if location_details else '无特定地点限制'}

# 剧情配置

- 剧情类型：{story_type}
- 剧情长度：{story_length}
- 关系深度：{relationship_depth}
- 时间设定：{time_setting}
- 情感基调：{mood_tone}
- 互动程度：{interaction_level}

# 输出要求

请以JSON格式输出剧情规划，简洁明了：

```json
{{
  "planning": "基于上述角色、地点和配置，制定一个完整的剧情规划框架，包括故事主题、核心冲突、主要情节发展和关键转折点。规划应该符合指定的剧情类型和情感基调，合理安排角色互动和地点运用。"
}}
```

请确保规划内容详细且具有可执行性。
"""
        
        # 流式调用LLM并在每个chunk时yield
        full_content = ""
        if llm:
            try:
                # 构建消息列表
                message = Message(role=MessageRole.USER, content=planning_prompt)
                messages = [message]
                
                logger.info(f"剧情规划: 开始流式LLM调用，提示词长度: {len(planning_prompt)}")
                
                # 使用think模式流式调用
                chunk_count = 0
                think_content = ""
                final_content = ""
                full_content = ""  # 初始化full_content变量，用于兼容模式
                
                async for chunk_data in llm.stream_generate(
                    messages, 
                    mode="think",
                    return_dict=True  # 工作流需要字典格式来区分think和content
                ):
                    chunk_count += 1
                    
                    # think模式返回的是字典格式：{"think": "思考内容", "content": "正式回答"}
                    if isinstance(chunk_data, dict):
                        think_part = chunk_data.get("think", "")
                        content_part = chunk_data.get("content", "")
                        
                        think_content += think_part
                        final_content += content_part
                        
                        # 实时更新UI - 显示思考过程和正式内容
                        if workflow_chat:
                            try:
                                # 构建带样式区分的显示内容
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
📋 规划结果：<br>
{final_content}
</div>"""
                                
                                await workflow_chat.add_node_message(
                                    "剧情规划",
                                    display_content,
                                    "streaming"
                                )
                            except Exception as ui_error:
                                logger.warning(f"剧情规划UI更新失败: {ui_error}")
                    else:
                        # 兼容字符串格式
                        full_content += str(chunk_data)
                        final_content = full_content
                        
                        if workflow_chat:
                            try:
                                await workflow_chat.add_node_message(
                                    "剧情规划",
                                    full_content,
                                    "streaming"
                                )
                            except Exception as ui_error:
                                logger.warning(f"剧情规划UI更新失败: {ui_error}")
                    
                    # 每个chunk都yield，让StateGraphExecutor能实时感知进度
                    yield {
                        'planning_result': final_content,  # 只传递正式内容给下一个节点
                        'planning_think': think_content,   # 保存思考过程用于调试
                        'chunk_progress': f"{chunk_count} chunks processed"
                    }
                
                logger.info(f"剧情规划: 流式生成完成，总chunk数: {chunk_count}，内容长度: {len(final_content)}")
                        
            except Exception as e:
                error_msg = f"剧情规划LLM调用失败: {type(e).__name__}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                raise Exception(error_msg)
        else:
            error_msg = "剧情规划: LLM未初始化"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        # 更新UI - 完成状态
        if workflow_chat:
            # 显示最终完成状态，保留完整内容
            final_display_content = ""
            if think_content.strip():
                final_display_content += f"""
<div style="background: #f8f9fa; border-left: 4px solid #6c757d; padding: 10px; margin: 10px 0; border-radius: 4px;">
🤔 思考过程：<br>
{think_content}
</div>"""
            
            if final_content.strip():
                final_display_content += f"""
<div style="background: #e8f5e9; border-left: 4px solid #28a745; padding: 10px; margin: 10px 0; border-radius: 4px;">
📋 规划结果：<br>
{final_content}
</div>"""
            
            await workflow_chat.add_node_message(
                "剧情规划",
                final_display_content if final_display_content else final_content,
                "completed"
            )
        
        # 尝试解析JSON格式的结果
        try:
            # 使用BaseNode的parse功能解析JSON
            from parsers.json_parser import JSONParser
            parser = JSONParser()
            
            # 从生成的内容中提取JSON部分
            json_content = self._extract_json_from_content(final_content)
            parsed_result = parser.parse(json_content)
            
            if parsed_result and 'planning' in parsed_result:
                planning_data = parsed_result['planning']
                logger.info("成功解析剧情规划JSON结果")
            else:
                # 如果解析失败，使用原始内容作为备选
                planning_data = final_content
                logger.warning("剧情规划JSON解析失败，使用原始内容")
                
        except Exception as parse_error:
            logger.warning(f"剧情规划JSON解析异常: {parse_error}，使用原始内容")
            planning_data = final_content
        
        # 最终完整结果
        output_data = input_data.copy()
        output_data['planning_result'] = planning_data  # 传递解析后的结果给下一个节点
        
        print(f"✅ 剧情规划完成，planning_data类型: {type(planning_data)}")
        logger.info(f"剧情规划节点输出数据: planning_result类型={type(planning_data)}")
        logger.info(f"剧情规划节点输出数据键: {list(output_data.keys())}")
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
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """兼容性方法，实际使用 execute_stream"""
        last_result = None
        async for result in self.execute_stream(input_data):
            last_result = result
        return last_result



class PlotGenerationNode(BaseNode):
    """剧情生成节点 - 生成具体的剧情事件"""
    
    def __init__(self):
        super().__init__(name="plot_generation", stream=True)
    
    async def execute_stream(self, input_data: Dict[str, Any]):
        """流式执行剧情生成节点 - 每个LLM chunk都yield"""
        print("📚 开始生成剧情...")
        
        workflow_chat = input_data.get('workflow_chat')
        llm = input_data.get('llm')
        planning_result = input_data.get('planning_result', '')
        
        # 调试：输出input_data的键和值
        logger.info(f"剧情生成节点接收到的input_data键: {list(input_data.keys())}")
        logger.info(f"planning_result类型: {type(planning_result)}")
        logger.info(f"planning_result值: {repr(planning_result[:100]) if planning_result else 'None或空'}")
        logger.info(f"planning_result是否为空字符串: {planning_result == ''}")
        logger.info(f"planning_result长度: {len(planning_result) if planning_result else 0}")
        
        # 验证规划结果
        if not planning_result or not planning_result.strip():
            error_msg = f"剧情生成失败：缺少剧情规划结果。input_data键: {list(input_data.keys())}"
            logger.error(error_msg)
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "剧情生成",
                    error_msg,
                    "error"
                )
            raise Exception(error_msg)
        
        # 更新UI - 开始状态
        if workflow_chat:
            await workflow_chat.add_node_message(
                "剧情生成", 
                f"正在基于规划结果生成具体剧情（规划长度：{len(planning_result)} 字符）...",
                "progress"
            )
        
        # 获取完整的配置和规划结果
        protagonist_data = input_data.get('protagonist_data', '')
        characters_data = input_data.get('characters_data', {})
        selected_characters = input_data.get('selected_characters', [])
        selected_locations = input_data.get('selected_locations', [])
        story_type = input_data.get('story_type', 'daily_life')
        story_length = input_data.get('story_length', 'medium')
        relationship_depth = input_data.get('relationship_depth', 'casual')
        time_setting = input_data.get('time_setting', 'current')
        mood_tone = input_data.get('mood_tone', 'neutral')
        interaction_level = input_data.get('interaction_level', 'normal')
        
        # 构建通用的剧情生成提示词
        plot_prompt = f"""
你是一名专业的剧情编剧，需要基于剧情规划生成具体的剧情内容。

# 剧情规划

{planning_result}

# 角色设定

{protagonist_data}

# 剧情配置

- 剧情类型：{story_type}
- 剧情长度：{story_length}
- 关系深度：{relationship_depth}
- 时间设定：{time_setting}
- 情感基调：{mood_tone}
- 互动程度：{interaction_level}

# 输出要求

请以JSON格式输出剧情内容，结构简洁：

```json
{{
  "story": {{
    "剧情名称": "整个剧情的名称",
    "剧情小节": [
      {{
        "小节ID": "SCENE_001",
        "小节标题": "小节的简短标题",
        "小节内容": "详细的剧情内容和场景描述",
        "地点": "发生地点",
        "参与角色": ["主角", "其他角色"],
        "关键对话": "浓缩的重要对话内容"
      }}
    ]
  }}
}}
```

请确保：
1. 生成3-6个剧情小节
2. 小节内容详细生动
3. 对话符合角色特征
4. 剧情连贯有逻辑
"""
        
        # 流式调用LLM
        full_content = ""
        if llm:
            try:
                # 构建消息列表
                message = Message(role=MessageRole.USER, content=plot_prompt)
                messages = [message]
                
                logger.info(f"剧情生成: 开始流式LLM调用，提示词长度: {len(plot_prompt)}")
                
                # 使用think模式流式调用
                chunk_count = 0
                think_content = ""
                final_content = ""
                full_content = ""  # 兼容模式
                
                async for chunk_data in llm.stream_generate(
                    messages, 
                    mode="think",
                    return_dict=True  # 工作流需要字典格式来区分think和content
                ):
                    chunk_count += 1
                    
                    # think模式返回的是字典格式：{"think": "思考内容", "content": "正式回答"}
                    if isinstance(chunk_data, dict):
                        think_part = chunk_data.get("think", "")
                        content_part = chunk_data.get("content", "")
                        
                        think_content += think_part
                        final_content += content_part
                        
                        # 实时更新UI - 显示思考过程和正式内容
                        if workflow_chat:
                            try:
                                # 构建带样式区分的显示内容
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
📖 剧情内容：<br>
{final_content}
</div>"""
                                
                                await workflow_chat.add_node_message(
                                    "剧情生成",
                                    display_content,
                                    "streaming"
                                )
                            except Exception as ui_error:
                                logger.warning(f"剧情生成UI更新失败: {ui_error}")
                    else:
                        # 兼容字符串格式
                        full_content += str(chunk_data)
                        final_content = full_content
                        
                        if workflow_chat:
                            try:
                                await workflow_chat.add_node_message(
                                    "剧情生成",
                                    full_content,
                                    "streaming"
                                )
                            except Exception as ui_error:
                                logger.warning(f"剧情生成UI更新失败: {ui_error}")
                    
                    # 每个chunk都yield，只传递正式内容给下一个节点
                    yield {
                        'plot_content': final_content,  # 只传递正式内容
                        'plot_think': think_content,    # 保存思考过程用于调试
                        'chunk_progress': f"{chunk_count} chunks processed"
                    }
                
                logger.info(f"剧情生成: 流式生成完成，总chunk数: {chunk_count}，内容长度: {len(final_content)}")
                        
            except Exception as e:
                error_msg = f"剧情生成LLM调用失败: {type(e).__name__}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                raise Exception(error_msg)
        else:
            error_msg = f"剧情生成: LLM未初始化"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        # 更新UI - 完成状态
        if workflow_chat:
            # 显示最终完成状态，保留完整内容
            final_display_content = ""
            if think_content.strip():
                final_display_content += f"""
<div style="background: #f8f9fa; border-left: 4px solid #6c757d; padding: 10px; margin: 10px 0; border-radius: 4px;">
🤔 思考过程：<br>
{think_content}
</div>"""
            
            if final_content.strip():
                final_display_content += f"""
<div style="background: #e8f5e9; border-left: 4px solid #28a745; padding: 10px; margin: 10px 0; border-radius: 4px;">
📖 剧情内容：<br>
{final_content}
</div>"""
            
            await workflow_chat.add_node_message(
                "剧情生成",
                final_display_content if final_display_content else final_content,
                "completed"
            )
        
        # 尝试解析JSON格式的结果
        try:
            # 使用BaseNode的parse功能解析JSON
            from parsers.json_parser import JSONParser
            parser = JSONParser()
            
            # 从生成的内容中提取JSON部分
            json_content = self._extract_json_from_content(final_content)
            parsed_result = parser.parse(json_content)
            
            if parsed_result and 'story' in parsed_result:
                story_data = parsed_result['story']
                logger.info("成功解析剧情生成JSON结果")
            else:
                # 如果解析失败，使用原始内容作为备选
                story_data = final_content
                logger.warning("剧情生成JSON解析失败，使用原始内容")
                
        except Exception as parse_error:
            logger.warning(f"剧情生成JSON解析异常: {parse_error}，使用原始内容")
            story_data = final_content
        
        output_data = input_data.copy()
        output_data['plot_content'] = story_data
        
        print("✅ 剧情生成完成")
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
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """兼容性方法，实际使用 execute_stream"""
        last_result = None
        async for result in self.execute_stream(input_data):
            last_result = result
        return last_result


class CSVExportNode(BaseNode):
    """CSV导出节点 - 将剧情数据导出为CSV格式"""
    
    def __init__(self):
        super().__init__(name="csv_export")
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行CSV导出 - 支持JSON数据解析"""
        print("📄 开始导出CSV...")
        
        workflow_chat = input_data.get('workflow_chat')
        plot_content = input_data.get('plot_content', '')
        
        # 更新UI - 开始状态
        if workflow_chat:
            await workflow_chat.add_node_message(
                "CSV导出",
                "正在解析剧情数据并导出为CSV格式...",
                "progress"
            )
        
        try:
            # 生成文件名
            from datetime import datetime
            import csv
            import os
            import json
            from pathlib import Path
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"story_plot_{timestamp}.csv"
            
            # 确保输出目录存在
            output_dir = Path("workspace/output")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            filepath = output_dir / filename
            
            # CSV标题行 - 精简字段
            csv_headers = [
                "剧情名称", "小节ID", "小节标题", "小节内容", "地点", "参与角色", "关键对话"
            ]
            
            csv_data = []
            story_name = ""
            
            # 解析JSON格式的剧情数据
            if isinstance(plot_content, dict) and '剧情小节' in plot_content:
                # plot_content是已解析的JSON对象
                story_name = plot_content.get('剧情名称', '未命名剧情')
                scenes = plot_content.get('剧情小节', [])
                logger.info(f"成功解析JSON格式剧情数据，剧情名称: {story_name}，包含 {len(scenes)} 个小节")
                
                for scene in scenes:
                    csv_data.append([
                        story_name,
                        scene.get('小节ID', ''),
                        scene.get('小节标题', ''),
                        scene.get('小节内容', ''),
                        scene.get('地点', ''),
                        ', '.join(scene.get('参与角色', [])),
                        scene.get('关键对话', '')
                    ])
                    
            elif isinstance(plot_content, str):
                # 尝试从字符串中解析JSON
                try:
                    # 使用JSONParser解析
                    from parsers.json_parser import JSONParser
                    parser = JSONParser()
                    
                    # 提取JSON内容
                    json_content = self._extract_json_from_content(plot_content)
                    parsed_data = parser.parse(json_content)
                    
                    if parsed_data and 'story' in parsed_data:
                        story_data = parsed_data['story']
                        story_name = story_data.get('剧情名称', '未命名剧情')
                        scenes = story_data.get('剧情小节', [])
                        logger.info(f"从字符串解析JSON成功，剧情名称: {story_name}，包含 {len(scenes)} 个小节")
                        
                        for scene in scenes:
                            csv_data.append([
                                story_name,
                                scene.get('小节ID', ''),
                                scene.get('小节标题', ''),
                                scene.get('小节内容', ''),
                                scene.get('地点', ''),
                                ', '.join(scene.get('参与角色', [])),
                                scene.get('关键对话', '')
                            ])
                    else:
                        raise ValueError("未找到story.剧情小节字段")
                        
                except Exception as parse_error:
                    logger.warning(f"JSON解析失败: {parse_error}，使用文本分段方式")
                    # 回退到简单文本分段方式
                    story_name = "文本解析剧情"
                    lines = plot_content.split('\n')
                    for i, line in enumerate(lines[:10]):
                        if line.strip():
                            csv_data.append([
                                story_name,
                                f"SCENE_{i+1:03d}",
                                f"第{i+1}节",
                                line,
                                "默认地点",
                                "主角",
                                line[:50] + "..." if len(line) > 50 else line
                            ])
            else:
                logger.error(f"无法处理的剧情数据类型: {type(plot_content)}")
                raise ValueError(f"无法处理的剧情数据类型: {type(plot_content)}")
            
            # 写入CSV文件
            with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(csv_headers)
                writer.writerows(csv_data)
            
            # 获取绝对路径
            abs_filepath = str(filepath.absolute())
            
            # 生成结果信息
            result = f"""✅ CSV导出成功！

# 文件信息

- 文件名：{filename}
- 保存路径：{filepath}
- 绝对路径：{abs_filepath}

# 统计信息

- 剧情名称：{story_name}
- 导出小节数：{len(csv_data)} 个
- 数据解析方式：{'JSON结构化解析' if isinstance(plot_content, dict) else 'JSON字符串解析'}

# 访问文件

🔗 点击打开文件：file:///{abs_filepath.replace(os.sep, '/')}
📂 在文件夹中查看：{filepath.parent}

# 下载说明

文件已保存到项目的 workspace/output 目录中。
"""
            
            # 更新UI - 完成状态
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "CSV导出",
                    result,
                    "completed"
                )
            
            output_data = input_data.copy()
            output_data['export_file'] = str(filepath)
            output_data['csv_data'] = csv_data
            output_data['csv_headers'] = csv_headers
            
            print(f"✅ CSV导出完成: {filepath}")
            return output_data
            
        except Exception as e:
            error_msg = f"CSV导出失败: {str(e)}"
            print(error_msg)
            logger.error(error_msg, exc_info=True)
            
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "CSV导出",
                    error_msg,
                    "error"
                )
            
            raise e
    
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