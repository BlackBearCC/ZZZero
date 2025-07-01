"""
工作流处理器
处理流式工作流聊天和节点执行
"""

import asyncio
import logging
import json
import os
from typing import Dict, Any, List, Tuple, Optional
import gradio as gr
from ..components.workflow_chat import WorkflowChat

logger = logging.getLogger(__name__)

class WorkflowHandlers:
    """工作流处理器"""
    
    def __init__(self, app_instance):
        self.app = app_instance
        self.workflow_chat = WorkflowChat()
        self.story_workflow = None
        self.characters_data = {}
        self.locations_data = {}
        
        # 工作流上下文
        self.planning_context = ""
        self.character_context = ""
        self.plot_context = ""
        
        self._initialize_data()
        
    def _initialize_data(self):
        """初始化角色和地点数据"""
        try:
            # 加载角色数据
            characters_file = os.path.join(os.path.dirname(__file__), '../../../config/yunhub_characters.json')
            if os.path.exists(characters_file):
                with open(characters_file, 'r', encoding='utf-8') as f:
                    self.characters_data = json.load(f)
                    
            # 加载地点数据
            locations_file = os.path.join(os.path.dirname(__file__), '../../../config/yunhub_locations.json')
            if os.path.exists(locations_file):
                with open(locations_file, 'r', encoding='utf-8') as f:
                    self.locations_data = json.load(f)
                    
            logger.info("角色和地点数据加载成功")
            
        except Exception as e:
            logger.error(f"数据加载失败: {e}")
    
    def _initialize_workflow(self):
        """初始化工作流"""
        try:
            from src.workflow.story_workflow import StoryWorkflow
            self.story_workflow = StoryWorkflow()
            logger.info("工作流初始化成功")
        except Exception as e:
            logger.error(f"工作流初始化失败: {e}")
            self.story_workflow = None
    
    async def on_start_workflow(self, 
                               selected_characters: List[str],
                               selected_locations: List[str],
                               story_type: str,
                               story_length: str,
                               relationship_depth: str):
        """启动工作流 - 事件分发器"""
        try:
            # 重置工作流状态
            progress_html, quick_replies, user_placeholder, send_interactive = self.workflow_chat.reset_workflow()
            
            # 验证输入
            if not selected_characters:
                await self.workflow_chat.add_node_message(
                    "系统", 
                    "❌ 错误：请至少选择一个角色", 
                    "error"
                )
                yield (
                    self.workflow_chat.update_node_state("planning", "error"),
                    "",
                    "",
                    False
                )
                return
            
            if not selected_locations:
                await self.workflow_chat.add_node_message(
                    "系统",
                    "❌ 错误：请至少选择一个地点", 
                    "error"
                )
                yield (
                    self.workflow_chat.update_node_state("planning", "error"),
                    "",
                    "",
                    False
                )
                return
            
            # 初始化工作流
            if not self.story_workflow:
                self._initialize_workflow()
                
            if not self.story_workflow:
                await self.workflow_chat.add_node_message(
                    "系统",
                    "❌ 错误：工作流初始化失败",
                    "error"
                )
                yield (
                    self.workflow_chat.update_node_state("planning", "error"),
                    "",
                    "",
                    False
                )
                return
            
            # 配置参数
            config = {
                'protagonist': '方知衡',
                'selected_characters': selected_characters,
                'selected_locations': selected_locations,
                'story_type': story_type,
                'story_length': story_length,
                'relationship_depth': relationship_depth,
                'time_setting': 'current',
                'mood_tone': 'neutral',
                'interaction_level': 'normal'
            }
            
            # 设置LLM
            if self.app and self.app.llm:
                self.story_workflow.llm = self.app.llm
            
            # 调用真正的工作流执行
            async for progress_update in self.story_workflow.execute_workflow_stream(config, self.workflow_chat):
                yield progress_update
                
        except Exception as e:
            error_msg = f"工作流执行失败: {str(e)}"
            logger.error(error_msg)
            
            await self.workflow_chat.add_node_message(
                "系统",
                error_msg,
                "error"
            )
            yield (
                self.workflow_chat.update_node_state("planning", "error"),
                "",
                "",
                False
            )



    async def on_user_input(self, user_input: str, workflow_progress: str):
        """处理用户输入 - 简化版，不支持交互"""
        try:
            # 添加用户消息
            await self.workflow_chat.add_user_input(user_input)
            
            # 简单回复，不处理复杂交互
            await self.workflow_chat.add_node_message(
                "系统",
                "工作流采用自动执行模式，无需用户交互。请使用'启动工作流'按钮开始执行。",
                "info"
            )
            
            quick_replies, placeholder, send_btn_interactive = self.workflow_chat.disable_user_input()
            yield (
                self.workflow_chat._create_workflow_progress(),
                quick_replies,
                placeholder,
                send_btn_interactive
            )
                
        except Exception as e:
            logger.error(f"用户输入处理失败: {e}")
            await self.workflow_chat.add_node_message(
                "系统",
                f"输入处理失败: {str(e)}",
                "error"
            )
            quick_replies, placeholder, send_btn_interactive = self.workflow_chat.disable_user_input()
            yield (
                self.workflow_chat._create_workflow_progress(),
                quick_replies,
                placeholder,
                send_btn_interactive
            )
 
    
    async def on_reset_workflow(self):
        """重置工作流"""
        progress_html, quick_replies, user_placeholder, send_interactive = self.workflow_chat.reset_workflow()
        return (
            progress_html,
            quick_replies,
            user_placeholder,
            send_interactive
        )
    
    async def on_refresh_characters(self) -> Tuple[gr.CheckboxGroup, List[List[str]]]:
        """刷新角色列表"""
        try:
            # 重新加载数据
            self._initialize_data()
            
            from src.web.components.story_interface import StoryInterface
            story_interface = StoryInterface()
            
            # 创建角色选择"""
            character_choices = story_interface.create_character_choices(self.characters_data)
            
            return (
                gr.update(choices=character_choices, value=[]),
                []  # 清空预览表格
            )
            
        except Exception as e:
            logger.error(f"刷新角色列表失败: {e}")
            return gr.update(choices=[], value=[]), []
    
    async def on_refresh_locations(self) -> Tuple[gr.CheckboxGroup, List[List[str]]]:
        """刷新地点列表"""
        try:
            # 重新加载数据
            self._initialize_data()
            
            from src.web.components.story_interface import StoryInterface
            story_interface = StoryInterface()
            
            # 创建地点选择"""
            location_choices = story_interface.create_location_choices(self.locations_data)
            
            return (
                gr.update(choices=location_choices, value=[]),
                []  # 清空预览表格
            )
            
        except Exception as e:
            logger.error(f"刷新地点列表失败: {e}")
            return gr.update(choices=[], value=[]), []
    
    async def on_characters_change(self, selected_characters: List[str]) -> List[List[str]]:
        """角色选择变化处理"""
        try:
            from src.web.components.story_interface import StoryInterface
            story_interface = StoryInterface()
            
            return story_interface.update_characters_preview(selected_characters, self.characters_data)
            
        except Exception as e:
            logger.error(f"角色预览更新失败: {e}")
            return []
    
    async def on_locations_change(self, selected_locations: List[str]) -> List[List[str]]:
        """地点选择变化处理"""
        try:
            from src.web.components.story_interface import StoryInterface
            story_interface = StoryInterface()
            
            return story_interface.update_locations_preview(selected_locations, self.locations_data)
            
        except Exception as e:
            logger.error(f"地点预览更新失败: {e}")
            return []
    
    async def on_story_load(self) -> Tuple[gr.CheckboxGroup, gr.CheckboxGroup]:
        """页面加载时初始化"""
        try:
            from src.web.components.story_interface import StoryInterface
            story_interface = StoryInterface()
            
            # 创建角色和地点选择"""
            character_choices = story_interface.create_character_choices(self.characters_data)
            location_choices = story_interface.create_location_choices(self.locations_data)
            
            return (
                gr.update(choices=character_choices, value=[]),
                gr.update(choices=location_choices, value=[])
            )
            
        except Exception as e:
            logger.error(f"页面加载失败: {e}")
            return gr.update(choices=[], value=[]), gr.update(choices=[], value=[]) 
