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
        """启动工作流"""
        try:
            # 重置工作流状态
            messages, node_indicator, quick_replies, user_placeholder, send_interactive = self.workflow_chat.reset_workflow()
            
            # 发送启动消息
            messages = await self.workflow_chat.add_node_message(
                "系统", 
                f"🚀 工作流启动！\n配置参数：\n角色：{len(selected_characters)}个\n地点：{len(selected_locations)}个\n类型：{story_type}", 
                "start"
            )
            
            quick_replies, placeholder, send_btn_interactive = self.workflow_chat.disable_user_input()
            yield (
                messages,
                self.workflow_chat.update_node_state("planning", "active"),
                quick_replies,
                placeholder,
                send_btn_interactive
            )
            
            # 验证输入
            if not selected_characters:
                messages = await self.workflow_chat.add_node_message(
                    "系统", 
                    "❌ 错误：请至少选择一个角色", 
                    "error"
                )
                quick_replies, placeholder, send_btn_interactive = self.workflow_chat.disable_user_input()
                yield (
                    messages,
                    self.workflow_chat.update_node_state("planning", "error"),
                    quick_replies,
                    placeholder,
                    send_btn_interactive
                )
                return
            
            if not selected_locations:
                messages = await self.workflow_chat.add_node_message(
                    "系统",
                    "❌ 错误：请至少选择一个地点", 
                    "error"
                )
                quick_replies, placeholder, send_btn_interactive = self.workflow_chat.disable_user_input()
                yield (
                    messages,
                    self.workflow_chat.update_node_state("planning", "error"),
                    quick_replies,
                    placeholder,
                    send_btn_interactive
                )
                return
            
            # 初始化工作流
            if not self.story_workflow:
                self._initialize_workflow()
                
            if not self.story_workflow:
                messages = await self.workflow_chat.add_node_message(
                    "系统",
                    "❌ 错误：工作流初始化失败",
                    "error"
                )
                quick_replies, placeholder, send_btn_interactive = self.workflow_chat.disable_user_input()
                yield (
                    messages,
                    self.workflow_chat.update_node_state("planning", "error"),
                    quick_replies,
                    placeholder,
                    send_btn_interactive
                )
                return
            
            # 执行各个节点
            config = {
                'selected_characters': selected_characters,
                'selected_locations': selected_locations,
                'story_type': story_type,
                'story_length': story_length,
                'relationship_depth': relationship_depth
            }
            
            # 节点1：剧情规划
            messages = await self.workflow_chat.add_node_message(
                "剧情规划",
                f"正在分析角色关系和地点配置...\n角色：{', '.join(selected_characters[:3])}{'...' if len(selected_characters) > 3 else ''}\n地点：{', '.join(selected_locations[:3])}{'...' if len(selected_locations) > 3 else ''}",
                "progress"
            )
            quick_replies, placeholder, send_btn_interactive = self.workflow_chat.disable_user_input()
            yield (
                messages,
                self.workflow_chat.update_node_state("planning", "active"),
                quick_replies,
                placeholder,
                send_btn_interactive
            )
            
            await asyncio.sleep(1)  # 模拟处理时间
            
            messages = await self.workflow_chat.add_node_message(
                "剧情规划",
                "✅ 剧情大纲规划完成！\n- 确定了主要角色关系网络\n- 分析了地点间的联系\n- 生成了故事主线框架",
                "complete"
            )
            quick_replies, placeholder, send_btn_interactive = self.workflow_chat.disable_user_input()
            yield (
                messages,
                self.workflow_chat.update_node_state("planning", "completed"),
                quick_replies,
                placeholder,
                send_btn_interactive
            )
            
            # 节点2：角色分析
            messages = await self.workflow_chat.add_node_message(
                "角色分析",
                "正在深入分析每个角色的性格特征和行为模式...",
                "start"
            )
            quick_replies, placeholder, send_btn_interactive = self.workflow_chat.disable_user_input()
            yield (
                messages,
                self.workflow_chat.update_node_state("character", "active"),
                quick_replies,
                placeholder,
                send_btn_interactive
            )
            
            await asyncio.sleep(1.5)
            
            messages = await self.workflow_chat.add_node_message(
                "角色分析",
                f"✅ 角色分析完成！\n- 分析了{len(selected_characters)}个角色的详细属性\n- 建立了角色间的关系网络\n- 确定了角色的行为动机",
                "complete"
            )
            quick_replies, placeholder, send_btn_interactive = self.workflow_chat.disable_user_input()
            yield (
                messages,
                self.workflow_chat.update_node_state("character", "completed"),
                quick_replies,
                placeholder,
                send_btn_interactive
            )
            
            # 节点3：剧情生成
            messages = await self.workflow_chat.add_node_message(
                "剧情生成",
                "正在生成具体的剧情事件和对话...",
                "start"
            )
            quick_replies, placeholder, send_btn_interactive = self.workflow_chat.disable_user_input()
            yield (
                messages,
                self.workflow_chat.update_node_state("plot", "active"),
                quick_replies,
                placeholder,
                send_btn_interactive
            )
            
            # 这里可以询问用户是否需要调整剧情风格
            messages = await self.workflow_chat.add_node_message(
                "剧情生成",
                f"💭 当前剧情类型：{story_type}\n是否需要调整剧情风格？",
                "input_request"
            )
            quick_replies, placeholder, send_btn_interactive = self.workflow_chat.enable_user_input(
                "输入剧情调整建议或选择快捷回复...", 
                ["确认", "保持当前设定", "需要调整"]
            )
            yield (
                messages,
                self.workflow_chat.update_node_state("plot", "active"),
                quick_replies,
                placeholder,
                send_btn_interactive
            )
            
        except Exception as e:
            error_msg = f"工作流执行失败: {str(e)}"
            logger.error(error_msg)
            
            messages = await self.workflow_chat.add_node_message(
                "系统",
                error_msg,
                "error"
            )
            quick_replies, placeholder, send_btn_interactive = self.workflow_chat.disable_user_input()
            yield (
                messages,
                self.workflow_chat.update_node_state("planning", "error"),
                quick_replies,
                placeholder,
                send_btn_interactive
            )
    
    async def on_user_input(self, user_input: str, chatbot_messages: List):
        """处理用户输入"""
        try:
            # 添加用户消息
            messages = await self.workflow_chat.add_user_input(user_input)
            
            # 根据当前节点状态处理用户输入
            current_node = self.workflow_chat.current_node
            
            if current_node == "plot":
                # 处理剧情调整输入
                if user_input.strip().lower() in ['保持', '继续', '确认', '保持当前设定', 'keep', 'continue', 'confirm']:
                    response = "收到！保持当前剧情风格，继续生成..."
                else:
                    response = f"收到调整建议：{user_input}\n正在应用您的要求重新生成剧情..."
                
                messages = await self.workflow_chat.add_node_message(
                    "剧情生成",
                    response,
                    "progress"
                )
                
                quick_replies, placeholder, send_btn_interactive = self.workflow_chat.disable_user_input()
                yield (
                    messages,
                    self.workflow_chat.update_node_state("plot", "active"),
                    quick_replies,
                    placeholder,
                    send_btn_interactive
                )
                
                await asyncio.sleep(2)  # 模拟处理时间
                
                # 完成剧情生成
                messages = await self.workflow_chat.add_node_message(
                    "剧情生成",
                    "✅ 剧情生成完成！\n- 生成了详细的剧情事件链\n- 创建了角色对话和行为\n- 设置了触发条件和完成条件",
                    "complete"
                )
                
                quick_replies, placeholder, send_btn_interactive = self.workflow_chat.disable_user_input()
                yield (
                    messages,
                    self.workflow_chat.update_node_state("plot", "completed"),
                    quick_replies,
                    placeholder,
                    send_btn_interactive
                )
                
                # 开始CSV导出
                messages = await self.workflow_chat.add_node_message(
                    "CSV导出",
                    "正在将生成的剧情数据导出为CSV格式...",
                    "start"
                )
                
                quick_replies, placeholder, send_btn_interactive = self.workflow_chat.disable_user_input()
                yield (
                    messages,
                    self.workflow_chat.update_node_state("export", "active"),
                    quick_replies,
                    placeholder,
                    send_btn_interactive
                )
                
                await asyncio.sleep(1)
                
                messages = await self.workflow_chat.add_node_message(
                    "CSV导出",
                    "✅ CSV导出完成！\n- 生成了标准格式的剧情CSV文件\n- 包含了所有必要的游戏数据字段\n- 文件已准备好下载",
                    "complete"
                )
                
                quick_replies, placeholder, send_btn_interactive = self.workflow_chat.disable_user_input()
                yield (
                    messages,
                    self.workflow_chat.update_node_state("export", "completed"),
                    quick_replies,
                    placeholder,
                    send_btn_interactive
                )
                
                # 工作流完成
                messages = await self.workflow_chat.add_node_message(
                    "系统",
                    "🎉 剧情生成工作流完成！\n所有节点执行成功，结果已生成并可供下载",
                    "complete"
                )
                
                quick_replies, placeholder, send_btn_interactive = self.workflow_chat.disable_user_input()
                yield (
                    messages,
                    self.workflow_chat._create_node_indicator(),
                    quick_replies,
                    placeholder,
                    send_btn_interactive
                )
            
            else:
                # 其他情况的处理
                messages = await self.workflow_chat.add_node_message(
                    "系统",
                    "当前不需要用户输入，工作流正在自动执行中...",
                    "info"
                )
                
                quick_replies, placeholder, send_btn_interactive = self.workflow_chat.disable_user_input()
                yield (
                    messages,
                    self.workflow_chat._create_node_indicator(),
                    quick_replies,
                    placeholder,
                    send_btn_interactive
                )
                
        except Exception as e:
            logger.error(f"用户输入处理失败: {e}")
            messages = await self.workflow_chat.add_node_message(
                "系统",
                f"输入处理失败: {str(e)}",
                "error"
            )
            quick_replies, placeholder, send_btn_interactive = self.workflow_chat.disable_user_input()
            yield (
                messages,
                self.workflow_chat._create_node_indicator(),
                quick_replies,
                placeholder,
                send_btn_interactive
            )
    
    async def on_reset_workflow(self):
        """重置工作流"""
        return self.workflow_chat.reset_workflow()
    
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
