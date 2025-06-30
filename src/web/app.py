"""
Gradio应用主文件 - 提供类ChatGPT风格的界面（重构版）
"""
import gradio as gr
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
import json
from datetime import datetime

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.types import AgentType, ToolConfig, LLMConfig, TaskResult
from agents.react_agent import ReactAgent
from llm.base import LLMFactory
from tools.mcp_tools import MCPToolManager

# 导入重构后的模块
from web.components.config_panel import ConfigPanel
from web.components.chat_interface import ChatInterface
from web.components.story_interface import StoryInterface
from web.handlers.event_handlers import EventHandlers
from web.handlers.workflow_handlers import WorkflowHandlers
from web.utils.text_processing import TextProcessor
from web.utils.file_utils import FileUtils
from web.utils.styles import CUSTOM_CSS, HTML_HEAD

# 配置日志
logger = logging.getLogger(__name__)

class AgentApp:
    """Agent应用界面（重构版）"""
    
    def __init__(self, 
                 title: str = "ZZZero AI Agent",
                 description: str = "基于节点编排的AI Agent框架"):
        self.title = title
        self.description = description
        self.current_agent = None
        self.agent = None
        self.tool_manager = None
        self.llm = None
        
        # 保存当前配置
        self.current_config = {
            'llm_provider': 'doubao',
            'model_name': 'ep-20250221154410-vh78x',
            'temperature': 0.7,
            'agent_type': 'react',
            'max_iterations': 5,
            'simplified_output': True,  # 默认启用简化输出
            'available_tools': [],
            'enabled_mcp_servers': ['csv', 'chromadb', 'python', 'role_info', 'roleplay'],
            'batch_enabled': False,
            'batch_csv_path': None,
            'batch_size': 20,
            'concurrent_tasks': 5,
            'processing_mode': 'parallel'
        }
        
        # 批处理器
        self.batch_processor = None
        
        # 工作空间配置
        self.workspace_config = {
            'base_dir': './workspace',
            'input_dir': './workspace/input',
            'output_dir': './workspace/output',
            'vectordb_dir': './workspace/vectordb',
            'temp_dir': './workspace/temp'
        }
        
        # 初始化组件和处理器
        self.config_panel = ConfigPanel()
        self.chat_interface = ChatInterface()
        self.story_interface = StoryInterface()
        self.event_handlers = EventHandlers(self)
        self.workflow_handlers = WorkflowHandlers(self)
        self.text_processor = TextProcessor()
        self.file_utils = FileUtils()
        
        # 创建工作空间目录
        self.file_utils.ensure_workspace_dirs(self.workspace_config)
        
    async def _update_agent_config(self):
        """更新Agent配置"""
        try:
            # 创建工具管理器（只创建一次）
            if not self.tool_manager:
                self.tool_manager = MCPToolManager()
                await self.tool_manager.initialize()
            
            # 创建LLM实例（只创建一次）
            if not self.llm:
                # 创建LLM配置对象
                llm_config = LLMConfig(
                    provider=self.current_config.get('llm_provider', 'doubao'),
                    model_name=self.current_config.get('model_name', 'ep-20250221154410-vh78x'),
                    temperature=self.current_config.get('temperature', 0.7)
                )
                
                # 使用工厂创建LLM实例
                self.llm = LLMFactory.create(llm_config)
                await self.llm.initialize()
            
            # 更新工具管理器的启用服务器（仅在工具管理器存在时）
            enabled_servers = self.current_config.get('enabled_mcp_servers', ['csv', 'chromadb', 'python', 'role_info', 'roleplay'])  # 默认启用
            if self.tool_manager:
                self.tool_manager.set_enabled_servers(enabled_servers)
            
            # 创建记忆存储
            from core.memory import SQLiteMemoryStore
            import uuid
            
            memory_store = SQLiteMemoryStore("workspace/memory.db")
            session_id = str(uuid.uuid4())[:8]  # 生成短会话ID
            
            # 创建或更新Agent（启用记忆功能）
            self.agent = ReactAgent(
                llm=self.llm,  # 传递LLM实例作为第一个参数
                tool_manager=self.tool_manager,
                max_iterations=self.current_config.get('max_iterations', 10),
                name="智能助手",
                memory_enabled=True,  # 启用记忆功能
                memory_store=memory_store,  # 传递记忆存储
                short_term_limit=3000,  # 短期记忆限制
                session_id=session_id,  # 会话ID
                simplified_output=self.current_config.get('simplified_output', True)  # 传递简化输出配置
            )
            
            # 同时设置current_agent以兼容其他方法
            self.current_agent = self.agent
            
            # 创建批处理器（如果还没有）
            if not self.batch_processor:
                from core.batch_processor import BatchProcessor
                self.batch_processor = BatchProcessor(
                    llm_caller=self.llm,
                    mcp_tool_manager=self.tool_manager
                )
                logger.info("批处理器初始化成功")
            
            logger.info("Agent配置更新成功")
            
        except Exception as e:
            error_msg = f"更新Agent配置失败: {e}"
            logger.error(error_msg)
            return error_msg
            
    def create_interface(self) -> gr.Blocks:
        """创建Gradio界面（重构版）"""
        with gr.Blocks(title=self.title, theme=gr.themes.Soft(), head=HTML_HEAD) as app:
            # 标题
            gr.Markdown(f"# {self.title}")
            gr.Markdown(f"{self.description}")
            
            # 创建Tab界面
            with gr.Tabs() as tabs:
                # Tab 1: Agent助手
                with gr.TabItem("🤖 Agent助手", id="agent_tab"):
                    with gr.Row():
                        # 左侧配置面板
                        with gr.Column(scale=1):
                            config_components = self.config_panel.create_full_panel()
                        
                        # 右侧聊天界面
                        with gr.Column(scale=3):
                            chat_components = self.chat_interface.create_full_interface()
                
                # Tab 2: 剧情生成工作流
                with gr.TabItem("🎭 剧情生成工作流", id="story_tab"):
                    story_components = self.story_interface.create_story_interface()
            
            # === 事件绑定 ===
            self._bind_events(config_components, chat_components, story_components, app)
            
            # 添加自定义CSS
            app.css = CUSTOM_CSS
            
        return app
    
    def _bind_events(self, config_components: Dict[str, Any], chat_components: Dict[str, Any], story_components: Dict[str, Any], app):
        """绑定所有事件处理器"""
        # 配置变化事件
        for component in [
            config_components.get('llm_provider'), 
            config_components.get('model_name'), 
            config_components.get('temperature'), 
            config_components.get('agent_type'), 
            config_components.get('max_iterations'), 
            config_components.get('simplified_output'),  # 添加简化输出选项
            config_components.get('available_tools'), 
            config_components.get('enabled_mcp_servers')
        ]:
            if component:
                component.change(
                    fn=self.event_handlers.on_config_change,
                    inputs=[
                        config_components.get('llm_provider'), 
                        config_components.get('model_name'), 
                        config_components.get('temperature'), 
                        config_components.get('agent_type'), 
                        config_components.get('max_iterations'), 
                        config_components.get('simplified_output'),  # 添加简化输出选项
                        config_components.get('available_tools'), 
                        config_components.get('enabled_mcp_servers')
                    ],
                    outputs=[]
                )
        
        # 批处理配置事件 - 从chat_components获取
        for component in [
            chat_components.get('batch_enabled'), 
            chat_components.get('batch_csv_file'), 
            chat_components.get('batch_size'), 
            chat_components.get('concurrent_tasks'), 
            chat_components.get('processing_mode')
        ]:
            if component:
                component.change(
                    fn=self.event_handlers.on_batch_config_change,
                    inputs=[
                        chat_components.get('batch_enabled'), 
                        chat_components.get('batch_csv_file'), 
                        chat_components.get('batch_size'), 
                        chat_components.get('concurrent_tasks'), 
                        chat_components.get('processing_mode')
                    ],
                    outputs=[
                        chat_components.get('batch_config_display'),
                        chat_components.get('batch_fields_group'),
                        chat_components.get('batch_structure_display'),
                        chat_components.get('batch_preview_table'),
                        chat_components.get('batch_fields_checkbox')
                    ]
                )
        
        # 字段选择事件 - 从chat_components获取
        if chat_components.get('batch_fields_checkbox'):
            chat_components['batch_fields_checkbox'].change(
                fn=self.event_handlers.on_fields_update,
                inputs=[chat_components['batch_fields_checkbox']],
                outputs=[chat_components.get('batch_config_display')]
            )
        
        # MCP服务器变化事件
        if config_components.get('enabled_mcp_servers'):
            config_components['enabled_mcp_servers'].change(
                fn=self.event_handlers.on_mcp_servers_change,
                inputs=[config_components['enabled_mcp_servers']],
                outputs=[config_components.get('mcp_servers_status')]
            )
        
        # 刷新MCP服务器按钮
        if config_components.get('refresh_mcp_btn'):
            config_components['refresh_mcp_btn'].click(
                fn=self.event_handlers.refresh_mcp_servers,
                outputs=[
                    config_components.get('mcp_servers_status'), 
                    config_components.get('enabled_mcp_servers')
                ]
            )
        
        # 添加远程服务器按钮
        if config_components.get('add_remote_btn'):
            config_components['add_remote_btn'].click(
                fn=self.event_handlers.on_add_remote_server,
                inputs=[
                    config_components.get('remote_server_name'), 
                    config_components.get('remote_server_url')
                ],
                outputs=[
                    config_components.get('remote_server_name'), 
                    config_components.get('remote_server_url'), 
                    config_components.get('remote_server_status'), 
                    config_components.get('enabled_mcp_servers')
                ]
            )
        
        # 记忆管理按钮
        if config_components.get('refresh_memory_btn'):
            config_components['refresh_memory_btn'].click(
                fn=self.event_handlers.refresh_memory_status,
                outputs=[config_components.get('memory_status')]
            )
        
        if config_components.get('clear_memory_btn'):
            config_components['clear_memory_btn'].click(
                fn=self.event_handlers.clear_memory,
                outputs=[config_components.get('memory_status')]
            )
        
        if config_components.get('export_memory_btn'):
            config_components['export_memory_btn'].click(
                fn=self.event_handlers.export_memory,
                outputs=[
                    config_components.get('memory_status'), 
                    config_components.get('memory_export_display')
                ]
            )
        
        # 文件上传和刷新
        if config_components.get('file_upload'):
            config_components['file_upload'].change(
                fn=self.event_handlers.on_upload_files,
                inputs=[config_components['file_upload']],
                outputs=[
                    config_components.get('upload_status'), 
                    config_components.get('input_files_display')
                ]
            )
        
        if config_components.get('refresh_files_btn'):
            config_components['refresh_files_btn'].click(
                fn=self.event_handlers.on_refresh_file_lists,
                outputs=[
                    config_components.get('input_files_display'), 
                    config_components.get('output_files_display')
                ]
            )
        
        # 聊天功能
        if chat_components.get('msg_input') and chat_components.get('chatbot'):
            chat_components['msg_input'].submit(
                fn=self.event_handlers.on_stream_chat,
                inputs=[
                    chat_components['msg_input'], 
                    chat_components['chatbot']
                ],
                outputs=[
                    chat_components['chatbot'], 
                    chat_components['msg_input'], 
                    chat_components.get('dynamic_table'), 
                    chat_components.get('metrics_display'), 
                    chat_components.get('flow_diagram'),
                    chat_components.get('send_btn')  # 添加发送按钮控制
                ]
            )
        
        if chat_components.get('send_btn'):
            chat_components['send_btn'].click(
                fn=self.event_handlers.on_stream_chat,
                inputs=[
                    chat_components['msg_input'], 
                    chat_components['chatbot']
                ],
                outputs=[
                    chat_components['chatbot'], 
                    chat_components['msg_input'], 
                    chat_components.get('dynamic_table'), 
                    chat_components.get('metrics_display'), 
                    chat_components.get('flow_diagram'),
                    chat_components.get('send_btn')  # 添加发送按钮控制
                ]
            )
        
        # 角色信息管理事件
        self._bind_role_events(config_components)
        
        # === 剧情工作流事件绑定 ===
        
        # 工作流聊天事件绑定
        if story_components.get('start_workflow_btn'):
            story_components['start_workflow_btn'].click(
                fn=self.workflow_handlers.on_start_workflow,
                inputs=[
                    story_components.get('character_selector'),
                    story_components.get('location_selector'),
                    story_components.get('story_type'),
                    story_components.get('story_length'),
                    story_components.get('relationship_depth')
                ],
                outputs=[
                    story_components.get('workflow_chatbot'),
                    story_components.get('node_indicator'),
                    story_components.get('quick_replies'),
                    story_components.get('user_input'),
                    story_components.get('send_btn')
                ]
            )
        
        if story_components.get('send_btn'):
            story_components['send_btn'].click(
                fn=self.workflow_handlers.on_user_input,
                inputs=[
                    story_components.get('user_input'),
                    story_components.get('workflow_chatbot')
                ],
                outputs=[
                    story_components.get('workflow_chatbot'),
                    story_components.get('node_indicator'),
                    story_components.get('quick_replies'),
                    story_components.get('user_input'),
                    story_components.get('send_btn')
                ]
            ).then(
                lambda: "",  # 清空输入框
                outputs=[story_components.get('user_input')]
            )
        
        if story_components.get('reset_workflow_btn'):
            story_components['reset_workflow_btn'].click(
                fn=self.workflow_handlers.on_reset_workflow,
                outputs=[
                    story_components.get('workflow_chatbot'),
                    story_components.get('node_indicator'),
                    story_components.get('quick_replies'),
                    story_components.get('user_input'),
                    story_components.get('send_btn')
                ]
            )
        
        # 刷新角色和地点列表
        if story_components.get('refresh_characters_btn'):
            story_components['refresh_characters_btn'].click(
                fn=self.workflow_handlers.on_refresh_characters,
                outputs=[
                    story_components.get('character_selector'),
                    story_components.get('characters_preview')
                ]
            )
        
        if story_components.get('refresh_locations_btn'):
            story_components['refresh_locations_btn'].click(
                fn=self.workflow_handlers.on_refresh_locations,
                outputs=[
                    story_components.get('location_selector'),
                    story_components.get('locations_preview')
                ]
            )
        
        # 角色和地点选择变化
        if story_components.get('character_selector'):
            story_components['character_selector'].change(
                fn=self.workflow_handlers.on_characters_change,
                inputs=[story_components['character_selector']],
                outputs=[story_components.get('characters_preview')]
            )
        
        if story_components.get('location_selector'):
            story_components['location_selector'].change(
                fn=self.workflow_handlers.on_locations_change,
                inputs=[story_components['location_selector']],
                outputs=[story_components.get('locations_preview')]
            )

        # 页面加载事件
        app.load(
            fn=self._on_load,
            outputs=[
                config_components.get('mcp_servers_status'), 
                config_components.get('enabled_mcp_servers'), 
                chat_components.get('chatbot'), 
                chat_components.get('dynamic_table'), 
                config_components.get('memory_status'), 
                config_components.get('input_files_display'), 
                config_components.get('output_files_display'),
                story_components.get('character_selector'),
                story_components.get('location_selector')
            ]
        )

    async def _on_load(self):
        """页面加载时的初始化（重构版）"""
        try:
            # 初始化配置（MCP服务器已在main.py中启动）
            await self._update_agent_config()
            
            # 获取服务器状态并更新界面
            servers_status = self.tool_manager.get_servers_status() if self.tool_manager else {}
            
            # 生成状态HTML
            status_html = "<div style='font-family: monospace;'>"
            status_html += "<h4>🔌 MCP服务器状态</h4>"
            
            if not servers_status:
                status_html += "<p>暂无可用的MCP服务器</p>"
            else:
                for server_id, info in servers_status.items():
                    status_icon = "🟢" if info['running'] else "🔴"
                    enable_icon = "✅" if info.get('enabled', False) else "⚪"
                    
                    # 依赖状态图标
                    deps_info = info.get('dependencies', {})
                    deps_status = deps_info.get('status', 'unknown')
                    deps_icon = {"ok": "✅", "missing": "❌", "unknown": "❓"}.get(deps_status, "❓")
                    
                    status_html += f"<div style='margin: 8px 0; padding: 8px; border: 1px solid #ddd; border-radius: 4px;'>"
                    status_html += f"<strong>{status_icon} {enable_icon} {deps_icon} {info['name']}</strong><br/>"
                    status_html += f"<small>ID: {server_id} | 状态: {'运行中' if info['running'] else '未运行'}</small><br/>"
                    status_html += f"<small>工具: {info.get('enabled_tools', 0)}/{info.get('total_tools', 0)} 个可用</small><br/>"
                    status_html += f"<small>依赖: {deps_info.get('message', '未知')}</small><br/>"
                    if deps_status == "missing" and "install_command" in deps_info:
                        status_html += f"<small style='color: #ff6600;'>安装: {deps_info['install_command']}</small><br/>"
                    status_html += f"<small>{info['description']}</small>"
                    status_html += "</div>"
            
            status_html += "</div>"
            
            # 生成可选择的服务器列表
            choices = []
            default_enabled = []
            
            for server_id, info in servers_status.items():
                label = f"{info['name']} ({server_id})"
                choices.append((label, server_id))
                # 默认勾选已启用的服务器，或者如果是注册的服务器就默认启用
                if info.get('enabled', False) or server_id in ['csv', 'chromadb', 'python', 'role_info', 'roleplay']:
                    default_enabled.append(server_id)
            
            # 演示消息
            demo_messages = [
                {
                    "role": "assistant", 
                    "content": """🎉 欢迎使用 ZZZero AI Agent！

**✨ 新功能：角色信息CRUD服务**
不再需要手动配置角色插件！现在可以通过对话直接管理角色信息：

• **创建角色**：`"请创建一个名为艾莉丝的角色人设"`
• **查询角色**：`"查询艾莉丝的角色设定"`  
• **添加知识**：`"为艾莉丝添加咖啡制作技巧的知识"`
• **搜索知识**：`"搜索关于绘画的知识"`
• **世界书**：`"添加世界背景：未来都市赛博朋克设定"`

**🧠 记忆系统已启用**
系统已配备完整的记忆管理功能：
• **对话历史保持**：能够记住完整的对话上下文
• **自动记忆压缩**：长期对话会自动压缩存储
• **智能上下文检索**：根据对话内容智能检索相关记忆

现在可以开始对话了！试试创建你的第一个角色吧～"""
                }
            ]
            
            # 获取初始记忆状态
            memory_status_html = await self.event_handlers.refresh_memory_status()
            
            # 获取文件列表
            input_files_html, output_files_html = await self.event_handlers.on_refresh_file_lists()
            
            # 初始化剧情工作流数据
            story_character_choices, story_location_choices = await self.workflow_handlers.on_story_load()
            
            return (
                status_html,
                gr.update(choices=choices, value=default_enabled),
                demo_messages,
                gr.update(value=[], headers=None, visible=False),  # 初始隐藏表格
                memory_status_html,  # 记忆状态
                input_files_html,
                output_files_html,
                story_character_choices,  # 剧情角色选择
                story_location_choices    # 剧情地点选择
            )
            
        except Exception as e:
            error_msg = f"页面加载初始化失败: {e}"
            logger.error(error_msg)
            return (
                f"❌ 初始化失败: {str(e)}",
                gr.update(choices=[], value=[]),
                [],
                gr.update(value=[], headers=None, visible=False),
                "<div style='color: red;'>❌ 记忆状态获取失败</div>",
                "❌ 获取文件列表失败",
                "❌ 获取文件列表失败",
                gr.update(choices=[], value=[]),  # 剧情角色选择
                gr.update(choices=[], value=[])   # 剧情地点选择
            )
    
    async def _refresh_mcp_servers(self):
        """刷新MCP服务器状态"""
        try:
            if not self.tool_manager:
                await self._update_agent_config()
            
            servers_status = self.tool_manager.get_servers_status() if self.tool_manager else {}
            
            # 生成状态HTML
            status_html = "<div style='font-family: monospace;'>"
            status_html += "<h4>🔌 MCP服务器状态</h4>"
            
            if not servers_status:
                status_html += "<p>暂无可用的MCP服务器</p>"
            else:
                for server_id, info in servers_status.items():
                    status_icon = "🟢" if info['running'] else "🔴"
                    enable_icon = "✅" if info.get('enabled', False) else "⚪"
                    
                    # 依赖状态图标
                    deps_info = info.get('dependencies', {})
                    deps_status = deps_info.get('status', 'unknown')
                    deps_icon = {"ok": "✅", "missing": "❌", "unknown": "❓"}.get(deps_status, "❓")
                    
                    status_html += f"<div style='margin: 8px 0; padding: 8px; border: 1px solid #ddd; border-radius: 4px;'>"
                    status_html += f"<strong>{status_icon} {enable_icon} {deps_icon} {info['name']}</strong><br/>"
                    status_html += f"<small>ID: {server_id} | 状态: {'运行中' if info['running'] else '未运行'}</small><br/>"
                    status_html += f"<small>工具: {info.get('enabled_tools', 0)}/{info.get('total_tools', 0)} 个可用</small><br/>"
                    status_html += f"<small>依赖: {deps_info.get('message', '未知')}</small><br/>"
                    if deps_status == "missing" and "install_command" in deps_info:
                        status_html += f"<small style='color: #ff6600;'>安装: {deps_info['install_command']}</small><br/>"
                    status_html += f"<small>{info['description']}</small>"
                    status_html += "</div>"
            
            status_html += "</div>"
            
            # 生成可选择的服务器列表
            choices = []
            default_enabled = []
            
            for server_id, info in servers_status.items():
                label = f"{info['name']} ({server_id})"
                choices.append((label, server_id))
                # 默认勾选已启用的服务器
                if info.get('enabled', False) or server_id in ['csv', 'chromadb', 'python', 'role_info', 'roleplay']:
                    default_enabled.append(server_id)
            
            return status_html, gr.update(choices=choices, value=default_enabled)
            
        except Exception as e:
            error_msg = f"刷新MCP服务器状态失败: {e}"
            logger.error(error_msg)
            return (
                f"❌ {error_msg}",
                gr.update(choices=[], value=[])
            )
    
    def _bind_role_events(self, config_components: Dict[str, Any]):
        """绑定角色信息管理事件"""
        import gradio as gr
        
        # 角色信息文件上传
        if config_components.get('role_profile_file'):
            config_components['role_profile_file'].change(
                fn=self.event_handlers.on_role_profile_file_upload,
                inputs=[config_components['role_profile_file']],
                outputs=[config_components.get('role_profile_text')]
            )
        
        # 加载角色按钮
        if config_components.get('role_load_btn'):
            config_components['role_load_btn'].click(
                fn=self.event_handlers.on_role_load,
                inputs=[config_components.get('role_name')],
                outputs=[
                    config_components.get('role_profile_text'),
                    config_components.get('role_status')
                ]
            )
        
        # 保存角色按钮
        if config_components.get('role_save_btn'):
            config_components['role_save_btn'].click(
                fn=self.event_handlers.on_role_save,
                inputs=[
                    config_components.get('role_name'),
                    config_components.get('role_profile_text')
                ],
                outputs=[config_components.get('role_status')]
            )
        
        # 清空角色内容按钮
        if config_components.get('role_clear_btn'):
            config_components['role_clear_btn'].click(
                fn=lambda: "",
                outputs=[config_components.get('role_profile_text')]
            )
        
        # 知识文件上传
        if config_components.get('knowledge_file'):
            config_components['knowledge_file'].change(
                fn=self.event_handlers.on_knowledge_file_upload,
                inputs=[config_components['knowledge_file']],
                outputs=[config_components.get('knowledge_text')]
            )
        
        # 添加知识按钮
        if config_components.get('knowledge_add_btn'):
            config_components['knowledge_add_btn'].click(
                fn=self.event_handlers.on_knowledge_add,
                inputs=[
                    config_components.get('role_name'),
                    config_components.get('knowledge_category'),
                    config_components.get('knowledge_text')
                ],
                outputs=[
                    config_components.get('role_status'),
                    config_components.get('knowledge_list')
                ]
            )
        
        # 搜索知识按钮
        if config_components.get('knowledge_search_btn'):
            config_components['knowledge_search_btn'].click(
                fn=self.event_handlers._get_knowledge_list,
                inputs=[config_components.get('role_name')],
                outputs=[config_components.get('knowledge_list')]
            )
        
        # 世界书文件上传
        if config_components.get('world_file'):
            config_components['world_file'].change(
                fn=self.event_handlers.on_world_file_upload,
                inputs=[config_components['world_file']],
                outputs=[config_components.get('world_text')]
            )
        
        # 添加世界设定按钮
        if config_components.get('world_add_btn'):
            config_components['world_add_btn'].click(
                fn=self.event_handlers.on_world_add,
                inputs=[
                    config_components.get('role_name'),
                    config_components.get('world_category'),
                    config_components.get('world_text')
                ],
                outputs=[
                    config_components.get('role_status'),
                    config_components.get('world_list')
                ]
            )
        
        # 搜索世界设定按钮
        if config_components.get('world_search_btn'):
            config_components['world_search_btn'].click(
                fn=self.event_handlers._get_world_list,
                inputs=[config_components.get('role_name')],
                outputs=[config_components.get('world_list')]
            )
        
        # 预览完整上下文按钮
        if config_components.get('role_preview_btn'):
            async def show_context(role_name):
                content, visible = await self.event_handlers.on_role_preview_context(role_name)
                return content, gr.update(visible=visible)
            
            config_components['role_preview_btn'].click(
                fn=show_context,
                inputs=[config_components.get('role_name')],
                outputs=[
                    config_components.get('role_context_display'),
                    config_components.get('role_context_display')  # 控制显示/隐藏
                ]
            )
            
    def launch(self, **kwargs):
        """启动应用"""
        interface = self.create_interface()
        interface.launch(**kwargs) 