"""
角色资料生成工作流界面组件 - 简化版，使用框架级自动流式显示
"""

import gradio as gr
import asyncio
import json
import logging
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime
from pathlib import Path

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from workflow.character_profile_workflow import ProfileWorkflow
from tools.knowledge_base_manager import GlobalKnowledgeBase
from core.types import LLMConfig
from web.components.workflow_chat import WorkflowChat

logger = logging.getLogger(__name__)

class CharacterProfileInterface:
    """角色资料生成工作流界面 - 简化版，使用框架级自动流式显示"""
    
    def __init__(self, llm_factory=None):
        self.llm_factory = llm_factory
        self.workflow = ProfileWorkflow()
        self.knowledge_base = GlobalKnowledgeBase("./workspace")
        
        # 缓存数据
        self.available_categories = []
        self.available_collections = []
        self.category_details = {}
        self._load_categories()
        self._load_collections()
        
        # 初始化聊天消息存储
        self.chat_messages = []
        self.node_status = {}
        
        # 初始化框架级NodeInfoStream监听
        self._setup_info_stream_listener()
    
    def _load_categories(self):
        """加载可用的资料类别"""
        try:
            import csv
            from pathlib import Path
            
            template_file = Path("workspace/input/主角人物资料需求表格.csv")
            if template_file.exists():
                categories = {}
                with open(template_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        category = row.get('类别', '').strip()
                        if category:
                            if category not in categories:
                                categories[category] = []
                            
                            item_info = {
                                '条目': row.get('条目', '').strip(),
                                '内容': row.get('内容', '').strip(),
                                '关键词': row.get('关键词', '').strip(),
                                '备注': row.get('备注', '').strip()
                            }
                            categories[category].append(item_info)
                
                self.category_details = categories
                self.available_categories = list(categories.keys())
                
                logger.info(f"已加载{len(self.available_categories)}个资料类别：{self.available_categories}")
            else:
                # 使用默认类别
                self.available_categories = [
                    "基本信息", "外貌特征", "性格特征", "兴趣爱好", "生活经历", 
                    "喜好厌恶", "个人物品", "成长经历", "家庭情况", "社交关系",
                    "行为偏好", "健康状况", "心理状态", "技能能力", "语言能力",
                    "数字足迹", "生活节奏", "财务状况", "观点立场", "法律状况", "梦想与目标"
                ]
                self.category_details = {cat: [] for cat in self.available_categories}
                logger.warning(f"CSV模板文件不存在，使用默认类别: {len(self.available_categories)}个")
                
        except Exception as e:
            logger.error(f"加载资料类别失败: {e}")
            self.available_categories = [
                "基本信息", "外貌特征", "性格特征", "成长经历", "家庭情况", "社交关系"
            ]
            self.category_details = {cat: [] for cat in self.available_categories}
    
    def _load_collections(self):
        """加载可用的知识集合"""
        try:
            self.available_collections = self.workflow.get_available_collections()
            logger.info(f"已加载{len(self.available_collections)}个知识集合")
        except Exception as e:
            logger.error(f"加载知识集合失败: {e}")
            self.available_collections = []
    
    def create_character_profile_interface(self) -> Dict[str, Any]:
        """创建完整的角色资料生成界面"""
        components = {}
        
        with gr.Column():
            # 标题和描述
            gr.Markdown("## 👤 角色资料生成工作流")
            gr.Markdown("基于人物资料需求表格，结合向量知识库，生成详细的角色背景资料")
            
            with gr.Row(equal_height=True, variant="panel"):
                # 左侧：参数配置面板 (30%)
                with gr.Column(scale=3, min_width=350):
                    config_components = self._create_config_panel()
                    components.update(config_components)
                
                # 右侧：对话显示区域 (70%)
                with gr.Column(scale=7, min_width=500):
                    chat_components = self._create_chat_display()
                    components.update(chat_components)
        
        # 绑定事件
        self._bind_events(components)
        
        return components
    
    def _create_config_panel(self) -> Dict[str, Any]:
        """创建左侧参数配置面板"""
        components = {}
        
        with gr.Column(variant="panel"):
            gr.Markdown("### ⚙️ 参数配置")
            
            # 角色基本信息
            with gr.Group():
                gr.Markdown("#### 👤 角色信息")
                components['character_name'] = gr.Textbox(
                    label="角色名称",
                    placeholder="请输入角色名称...",
                    value=""
                )
                
                components['basic_info'] = gr.Textbox(
                    label="基础人设",
                    placeholder="请输入角色的基础人设信息...",
                    lines=4,
                    value=""
                )
            
            # 类别选择
            with gr.Group():
                gr.Markdown("#### 📋 生成类别")
                category_choices = []
                for category in self.available_categories:
                    item_count = len(self.category_details.get(category, []))
                    choice_label = f"{category} ({item_count}项)"
                    category_choices.append((choice_label, category))
                
                components['category_selector'] = gr.CheckboxGroup(
                    label="选择要生成的资料类别",
                    choices=category_choices,
                    value=self.available_categories[:3] if self.available_categories else [],
                    interactive=True,
                    info=f"共{len(self.available_categories)}个类别可选"
                )
                
                with gr.Row():
                    components['select_all_categories'] = gr.Button(
                        "全选", size="sm", variant="secondary"
                    )
                    components['clear_all_categories'] = gr.Button(
                        "清空", size="sm", variant="secondary"
                    )
            
            # 知识库选择
            with gr.Group():
                gr.Markdown("#### 🗂️ 知识库选择")
                components['knowledge_selector'] = gr.CheckboxGroup(
                    label="选择启用的知识集合",
                    choices=self.available_collections if self.available_collections else [],
                    value=[],
                    interactive=True,
                    info="选中的知识库将提供参考信息"
                )
                
                components['refresh_collections'] = gr.Button(
                    "刷新知识库", size="sm", variant="secondary"
                )
            
            # LLM配置（折叠）
            with gr.Accordion("🤖 LLM配置", open=False):
                components['llm_provider'] = gr.Dropdown(
                    label="LLM提供商",
                    choices=["doubao", "openai"],
                    value="doubao",
                    interactive=True
                )
                
                components['model_name'] = gr.Textbox(
                    label="模型名称",
                    value="ep-20250312153153-npj4s",
                    interactive=True
                )
                
                components['temperature'] = gr.Slider(
                    label="Temperature",
                    minimum=0.0,
                    maximum=2.0,
                    value=0.7,
                    step=0.1,
                    interactive=True
                )
            
            # 历史记录（折叠）
            with gr.Accordion("📚 历史记录", open=False):
                components['history_dropdown'] = gr.Dropdown(
                    label="选择历史记录",
                    choices=self._get_history_choices(),
                    value=None,
                    interactive=True
                )
                
                with gr.Row():
                    components['load_history'] = gr.Button(
                        "载入", size="sm", variant="secondary"
                    )
                    components['refresh_history'] = gr.Button(
                        "刷新", size="sm", variant="secondary"
                    )
            
            # 生成按钮
            components['generate_button'] = gr.Button(
                "🚀 开始生成角色资料",
                variant="primary",
                size="lg"
            )
        
        return components
    
    def _create_chat_display(self) -> Dict[str, Any]:
        """创建右侧对话显示区域 - 简化版，使用统一的Stream API"""
        components = {}
        
        with gr.Column():
            gr.Markdown("### 💬 工作流执行过程")
            
            # 使用标准Gradio聊天组件
            components['chat_display'] = gr.Chatbot(
                label="执行日志",
                height=500,
                show_label=False,
                bubble_full_width=False,
                avatar_images=None,
                type="messages"
            )
            
            # 工作流状态面板
            with gr.Row():
                components['workflow_status'] = gr.Markdown(
                    "**状态：** 等待开始...",
                    visible=True
                )
            
            # 控制按钮
            with gr.Row():
                components['clear_chat'] = gr.Button(
                    "清空对话", size="sm", variant="secondary"
                )
                components['export_log'] = gr.Button(
                    "导出日志", size="sm", variant="secondary"
                )
        
        return components
    
    def _setup_info_stream_listener(self):
        """设置框架级自动信息流监听器 - 用于收集事件但不直接更新界面"""
        from core.base import NodeInfoStream
        
        self.info_stream = NodeInfoStream()
        # 清空之前的事件回调，使用新的收集模式
        self.info_stream.callbacks.clear()
        self.collected_events = []  # 收集事件，由生成器函数处理
        
        # 添加事件收集回调
        def collect_event(event):
            self.collected_events.append(event)
        
        self.info_stream.add_callback(collect_event)
    
    def _format_event_for_display(self, event):
        """格式化事件用于显示"""
        try:
            event_type = event.get("type", "")
            node_name = event.get("node_name", "")
            content = event.get("content", "")
            metadata = event.get("metadata", {})
            
            # 格式化框架级事件消息
            formatted_message = self._format_framework_event(event_type, node_name, content, metadata)
            sender = self._get_event_sender(event_type, node_name)
            
            return sender, formatted_message
            
        except Exception as e:
            logger.error(f"格式化事件失败: {e}")
            return "系统", f"❌ 事件处理错误: {str(e)}"
    
    def _format_framework_event(self, event_type: str, node_name: str, content: str, metadata: Dict) -> str:
        """格式化框架级事件消息 - 统一样式"""
        icons = {
            # 图级事件
            "graph_start": "🚀",
            "graph_complete": "🎉",
            
            # 节点生命周期事件
            "node_start": "⚡",
            "node_executing": "🔄",
            "node_streaming": "📡",
            "node_stream_complete": "✨",
            "node_complete": "✅",
            "node_error": "❌",
            
            # 状态管理事件
            "state_merge_start": "🔀",
            "state_merge_complete": "✅",
            
            # 路由事件
            "routing_start": "🧭",
            "routing_complete": "🎯",
            
            # 兼容旧版事件
            "init": "🔧",
            "start": "🚀",
            "category_start": "📝",
            "category_complete": "✅",
            "llm_start": "🤖",
            "llm_streaming": "⚡",
            "llm_complete": "✨",
            "complete": "🎉",
            "error": "❌",
            "fatal_error": "💥"
        }
        
        icon = icons.get(event_type, "ℹ️")
        message = f"{icon} **{content}**"
        
        # 添加关键元数据
        if metadata:
            important_keys = [
                "iteration", "chunk_count", "node_type", "success", 
                "next_nodes", "error_type", "update_keys", "total_chunks"
            ]
            meta_info = []
            
            for key in important_keys:
                if key in metadata and metadata[key] is not None:
                    meta_info.append(f"{key}: {metadata[key]}")
            
            if meta_info:
                message += f"\n_{', '.join(meta_info)}_"
        
        return message
    
    def _get_event_sender(self, event_type: str, node_name: str) -> str:
        """获取事件发送者标识"""
        if event_type.startswith("graph_"):
            return "🏗️ 图引擎"
        elif event_type.startswith("node_"):
            return f"📦 {node_name}"
        elif event_type.startswith("state_"):
            return "💾 状态管理"
        elif event_type.startswith("routing_"):
            return "🧭 路由器"
        elif event_type == "llm_streaming":
            category = node_name  # 对于LLM事件，node_name实际是category
            return f"🤖 LLM-{category}"
        else:
            return f"[{node_name}]"
    
    def _bind_events(self, components: Dict[str, Any]):
        """绑定界面事件 - 简化版"""
        
        # 刷新历史记录按钮
        if 'refresh_history' in components:
            components['refresh_history'].click(
                fn=self._refresh_history,
                outputs=components['history_dropdown']
            )
        
        # 载入历史记录按钮
        if 'load_history' in components:
            components['load_history'].click(
                fn=self._load_history_record,
                inputs=components['history_dropdown'],
                outputs=[
                    components['character_name'],
                    components['basic_info'],
                    components['category_selector'],
                    components['knowledge_selector']
                ]
            )
        
        # 全选类别按钮
        if 'select_all_categories' in components:
            components['select_all_categories'].click(
                fn=lambda: gr.update(value=self.available_categories),
                outputs=components['category_selector']
            )
        
        # 清空类别按钮
        if 'clear_all_categories' in components:
            components['clear_all_categories'].click(
                fn=lambda: gr.update(value=[]),
                outputs=components['category_selector']
            )
        
        # 刷新知识库按钮
        if 'refresh_collections' in components:
            components['refresh_collections'].click(
                fn=self._refresh_collections,
                outputs=components['knowledge_selector']
            )
        
        # 生成按钮事件绑定 - 使用Gradio生成器模式实现真正的流式更新
        if 'generate_button' in components:
            components['generate_button'].click(
                fn=self._start_unified_workflow,
                inputs=[
                    components['character_name'],
                    components['basic_info'],
                    components['category_selector'],
                    components['knowledge_selector'],
                    components['llm_provider'],
                    components['model_name'],
                    components['temperature']
                ],
                outputs=[
                    components['chat_display'],
                    components['workflow_status']
                ],
                # 关键：使用show_progress=True启用Gradio流式模式
                show_progress=True
            )
        
        # 清空对话按钮
        if 'clear_chat' in components:
            components['clear_chat'].click(
                fn=self._clear_chat,
                outputs=[components['chat_display']]
            )
    
    def _start_unified_workflow(self, 
                               character_name: str, 
                               basic_info: str, 
                               selected_categories: List[str], 
                               selected_collections: List[str],
                               llm_provider: str,
                               model_name: str,
                               temperature: float):
        """统一的工作流启动器 - 使用Gradio生成器模式实现真正的实时流式显示"""
        import asyncio
        
        # 输入验证
        if not character_name or not character_name.strip():
            return [{"role": "assistant", "content": "❌ 请输入角色名称"}], "状态：输入验证失败"
        
        if not basic_info or not basic_info.strip():
            return [{"role": "assistant", "content": "❌ 请输入基础人设信息"}], "状态：输入验证失败"
        
        if not selected_categories:
            return [{"role": "assistant", "content": "❌ 请至少选择一个生成类别"}], "状态：输入验证失败"
        
        # 创建LLM配置
        if not self.llm_factory:
            return [{"role": "assistant", "content": "❌ LLM工厂未配置"}], "状态：配置错误"
        
        try:
            llm_config = LLMConfig(
                provider=llm_provider,
                api_key=os.getenv('DOUBAO_API_KEY', 'b633a622-b5d0-4f16-a8a9-616239cf15d1'),
                model_name=model_name,
                temperature=temperature,
                max_tokens=16384
            )
            self.workflow.llm_config = llm_config
        except Exception as e:
            return [{"role": "assistant", "content": f"❌ LLM配置失败：{str(e)}"}], "状态：配置错误"
        
        # 使用生成器函数实现真正的流式更新
        yield from self._stream_workflow_execution(
            character_name=character_name,
            basic_info=basic_info,
            selected_categories=selected_categories,
            selected_collections=selected_collections,
            llm_provider=llm_provider,
            model_name=model_name,
            temperature=temperature
        )
    
    def _stream_workflow_execution(self, **kwargs):
        """流式工作流执行生成器 - 优化LLM流式显示"""
        import asyncio
        
        # 清空事件收集器
        self.collected_events = []
        current_messages = []
        
        # 用于跟踪当前正在进行的LLM生成
        current_llm_session = {
            'active': False,
            'item_name': '',
            'category': '',
            'accumulated_content': '',
            'message_index': -1
        }
        
        # 添加开始消息
        start_msg = f"🚀 启动实时流式工作流\n\n角色：**{kwargs['character_name']}**\n类别：{len(kwargs['selected_categories'])} 个"
        current_messages.append({"role": "assistant", "content": start_msg})
        
        config_msg = f"⚙️ LLM配置：{kwargs['llm_provider']} | {kwargs['model_name']} | temp={kwargs['temperature']}"
        current_messages.append({"role": "assistant", "content": config_msg})
        
        # 首次返回初始状态
        yield current_messages, "状态：正在启动工作流..."
        
        try:
            # 执行异步工作流
            async def run_stream_workflow():
                final_status = "状态：执行中..."
                nonlocal current_messages, current_llm_session
                
                async for result in self.workflow.generate_character_profile_stream(
                    character_name=kwargs['character_name'],
                    basic_info=kwargs['basic_info'],
                    selected_categories=kwargs['selected_categories'],
                    selected_collections=kwargs['selected_collections']
                ):
                    # 处理收集到的框架级事件
                    events_processed = False
                    while self.collected_events:
                        event = self.collected_events.pop(0)
                        events_processed = True
                        
                        event_type = event.get("type", "")
                        node_name = event.get("node_name", "")
                        content = event.get("content", "")
                        metadata = event.get("metadata", {})
                        
                        # 特殊处理LLM流式事件
                        if event_type == "llm_streaming":
                            item_name = metadata.get('item', '')
                            category = metadata.get('category', '')
                            current_content = metadata.get('current_content', '')
                            accumulated_content = metadata.get('accumulated_content', '')
                            
                            # 如果是新的LLM会话或不同的条目
                            if not current_llm_session['active'] or current_llm_session['item_name'] != item_name:
                                # 开始新的LLM会话
                                current_llm_session = {
                                    'active': True,
                                    'item_name': item_name,
                                    'category': category,
                                    'accumulated_content': accumulated_content,
                                    'message_index': len(current_messages)
                                }
                                
                                # 创建新的LLM生成消息
                                llm_msg = f"🤖 **正在生成：{category} - {item_name}**\n\n{accumulated_content}"
                                current_messages.append({"role": "assistant", "content": llm_msg})
                            else:
                                # 更新现有的LLM消息
                                current_llm_session['accumulated_content'] = accumulated_content
                                llm_msg = f"🤖 **正在生成：{category} - {item_name}**\n\n{accumulated_content}"
                                current_messages[current_llm_session['message_index']] = {"role": "assistant", "content": llm_msg}
                        
                        elif event_type == "llm_complete":
                            # LLM生成完成，结束当前会话
                            if current_llm_session['active']:
                                item_name = metadata.get('item', current_llm_session['item_name'])
                                category = metadata.get('category', current_llm_session['category'])
                                
                                # 更新为完成状态
                                final_content = current_llm_session['accumulated_content']
                                completion_msg = f"✅ **已完成：{category} - {item_name}**\n\n{final_content}"
                                current_messages[current_llm_session['message_index']] = {"role": "assistant", "content": completion_msg}
                                
                                # 重置LLM会话
                                current_llm_session['active'] = False
                        
                        elif event_type == "llm_start":
                            # LLM开始生成新条目
                            item_name = metadata.get('item', '')
                            category = metadata.get('category', '')
                            start_msg = f"🚀 开始生成：{category} - {item_name}"
                            current_messages.append({"role": "assistant", "content": start_msg})
                        
                        else:
                            # 处理其他类型的事件
                            sender, message = self._format_event_for_display(event)
                            # 过滤掉无价值的重复事件
                            if not (event_type in ["node_streaming", "chunk_count"] and "chunk_count" in str(message)):
                                current_messages.append({"role": "assistant", "content": f"**{sender}**: {message}"})
                    
                    # 只有在处理了事件时才更新界面
                    if events_processed:
                        yield current_messages.copy(), "状态：正在处理..."
                    
                    # 处理工作流结果
                    if result.get('success') is False and 'error' in result:
                        error_msg = f"❌ 生成失败：{result['error']}"
                        current_messages.append({"role": "assistant", "content": error_msg})
                        final_status = "状态：执行失败"
                        yield current_messages.copy(), final_status
                        return
                        
                    elif result.get('success') is True:
                        output_file = result.get('output_file', '')
                        profile_data = result.get('profile', {})
                        
                        success_msg = f"🎉 **角色资料生成完成！**\n\n"
                        success_msg += f"🎯 生成了 {len(profile_data)} 个类别的资料\n"
                        if output_file:
                            success_msg += f"📁 文件保存位置：{output_file}\n\n"
                        
                        for category, data in profile_data.items():
                            if isinstance(data, dict):
                                success_msg += f"📋 **{category}**：{len(data)} 个条目\n"
                        
                        current_messages.append({"role": "assistant", "content": success_msg})
                        
                        if output_file:
                            file_msg = f"✅ 文件已保存：{output_file}"
                            current_messages.append({"role": "assistant", "content": file_msg})
                        
                        final_status = f"状态：生成完成 - {len(profile_data)} 个类别"
                        yield current_messages.copy(), final_status
                        return
                    
                    # 处理进度更新
                    elif 'progress' in result:
                        progress_msg = result['progress']
                        current_messages.append({"role": "assistant", "content": f"📊 {progress_msg}"})
                        yield current_messages.copy(), f"状态：{progress_msg}"
                
                # 处理剩余的事件
                while self.collected_events:
                    event = self.collected_events.pop(0)
                    event_type = event.get("type", "")
                    
                    # 跳过无价值的事件
                    if event_type not in ["node_streaming", "chunk_count"]:
                        sender, message = self._format_event_for_display(event)
                        current_messages.append({"role": "assistant", "content": f"**{sender}**: {message}"})
                
                yield current_messages.copy(), final_status
            
            # 在新的事件循环中运行
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 使用同步生成器包装异步生成器
            async_gen = run_stream_workflow()
            try:
                while True:
                    try:
                        result = loop.run_until_complete(async_gen.__anext__())
                        yield result
                    except StopAsyncIteration:
                        break
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"流式工作流执行失败: {e}")
            error_msg = f"❌ 执行异常：{str(e)}"
            current_messages.append({"role": "assistant", "content": error_msg})
            yield current_messages, f"状态：异常 - {str(e)}"
    
    def _clear_chat(self):
        """清空聊天记录"""
        self.chat_messages = []
        self.node_status = {}
        return []
    
    def _get_history_choices(self) -> List[str]:
        """获取历史记录选择项"""
        try:
            history_records = self.workflow.get_history_records()
            choices = []
            for i, record in enumerate(reversed(history_records)):  # 最新的在前
                character_name = record.get('character_name', '未知角色')[:20]
                created_at = record.get('created_at', '')
                if created_at:
                    try:
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        time_str = dt.strftime('%m-%d %H:%M')
                    except:
                        time_str = created_at[:16]
                else:
                    time_str = '未知时间'
                
                choice = f"{character_name} ({time_str})"
                choices.append(choice)
            
            return choices
        except Exception as e:
            logger.error(f"获取历史记录选择项失败: {e}")
            return []
    
    def _refresh_history(self):
        """刷新历史记录下拉列表"""
        try:
            choices = self._get_history_choices()
            return gr.update(choices=choices, value=None)
        except Exception as e:
            logger.error(f"刷新历史记录失败: {e}")
            return gr.update()
    
    def _load_history_record(self, selected_choice: str):
        """载入选中的历史记录"""
        try:
            if not selected_choice:
                return "", "", [], []
            
            # 获取历史记录
            history_records = self.workflow.get_history_records()
            if not history_records:
                return "", "", [], []
            
            # 从选择项中提取索引（反向索引，因为显示时是最新的在前）
            choices = self._get_history_choices()
            if selected_choice not in choices:
                return "", "", [], []
            
            choice_index = choices.index(selected_choice)
            record_index = len(history_records) - 1 - choice_index  # 反向索引
            
            if 0 <= record_index < len(history_records):
                record = history_records[record_index]
                
                character_name = record.get('character_name', '')
                basic_info = record.get('basic_info', '')
                selected_categories = record.get('selected_categories', [])
                selected_collections = record.get('selected_collections', [])
                
                return (
                    character_name,
                    basic_info,
                    selected_categories,
                    selected_collections
                )
            else:
                return "", "", [], []
                
        except Exception as e:
            logger.error(f"载入历史记录失败: {e}")
            return "", "", [], []
    
    def _refresh_collections(self):
        """刷新知识集合列表"""
        try:
            self._load_collections()
            return gr.update(choices=self.available_collections, value=[])
        except Exception as e:
            logger.error(f"刷新知识集合失败: {e}")
            return gr.update()