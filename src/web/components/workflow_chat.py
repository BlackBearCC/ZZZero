"""
工作流聊天界面组件
支持流式显示节点执行状态和用户交互
"""

import gradio as gr
import json
from typing import Dict, Any, List, Tuple, Optional
import asyncio
import time

class WorkflowChat:
    """工作流聊天界面类"""
    
    def __init__(self):
        self.messages = []
        self.current_node = None
        self.node_states = {}
        self.user_inputs = {}
        
    def create_workflow_chat_interface(self) -> Dict[str, Any]:
        """创建工作流聊天界面"""
        components = {}
        
        with gr.Column():
            # 工作流聊天显示区域 - 调整高度与Agent窗口一致
            components['workflow_chatbot'] = gr.Chatbot(
                label="🔄 剧情生成工作流",
                height=500,  # 减少高度为快捷回复留出空间
                show_copy_button=True,
                show_share_button=False,
                bubble_full_width=False,
                type="messages",
                value=[],
                elem_id="workflow_chatbot"
            )
            
            # 节点状态指示器
            components['node_indicator'] = gr.HTML(
                value=self._create_node_indicator(),
                visible=True
            )
            
            # 快捷回复区域（在输入框上方）
            components['quick_replies'] = gr.HTML(
                value="",
                visible=False,
                elem_id="quick_replies_area"
            )
            
            # 用户输入区域（支持节点交互）
            with gr.Row():
                components['user_input'] = gr.Textbox(
                    label="💬 与工作流交互",
                    placeholder="等待工作流启动...",
                    interactive=False,
                    scale=4
                )
                components['send_btn'] = gr.Button(
                    "发送",
                    variant="primary",
                    interactive=False,
                    scale=1
                )
            
            # 工作流控制按钮
            with gr.Row():
                components['start_workflow_btn'] = gr.Button(
                    "🚀 启动工作流",
                    variant="primary",
                    scale=2
                )
                components['pause_workflow_btn'] = gr.Button(
                    "⏸️ 暂停",
                    variant="secondary",
                    interactive=False,
                    scale=1
                )
                components['reset_workflow_btn'] = gr.Button(
                    "🔄 重置",
                    variant="secondary", 
                    scale=1
                )
        
        return components
    
    def _create_node_indicator(self, current_node: str = None) -> str:
        """创建节点状态指示器"""
        nodes = [
            ("📋", "剧情规划", "planning"),
            ("👥", "角色分析", "character"), 
            ("📚", "剧情生成", "plot"),
            ("📄", "CSV导出", "export")
        ]
        
        # 使用白色背景与大背景色一致
        indicator_html = """
        <div style='padding: 15px; border-radius: 10px; background: #ffffff; margin: 10px 0; border: 1px solid #e5e7eb; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);'>
            <h4 style='color: #374151; margin: 0 0 10px 0; text-align: center; font-weight: 600;'>🔄 工作流进度</h4>
            <div style='display: flex; justify-content: space-between; align-items: center;'>
        """
        
        for i, (icon, name, node_id) in enumerate(nodes):
            # 判断节点状态
            if current_node == node_id:
                status_class = "active"
                color = "#f59e0b"  # 橙色
                bg_color = "rgba(245, 158, 11, 0.1)"
                border_color = "#f59e0b"
            elif self.node_states.get(node_id, "pending") == "completed":
                status_class = "completed"
                color = "#10b981"  # 绿色
                bg_color = "rgba(16, 185, 129, 0.1)"
                border_color = "#10b981"
            elif self.node_states.get(node_id, "pending") == "error":
                status_class = "error"
                color = "#ef4444"  # 红色
                bg_color = "rgba(239, 68, 68, 0.1)"
                border_color = "#ef4444"
            else:
                status_class = "pending"
                color = "#9ca3af"  # 灰色
                bg_color = "rgba(156, 163, 175, 0.1)"
                border_color = "#d1d5db"
            
            indicator_html += f"""
                <div style='text-align: center; padding: 12px; border-radius: 8px; background: {bg_color}; margin: 0 5px; flex: 1; border: 2px solid {border_color}; transition: all 0.3s ease;'>
                    <div style='font-size: 28px; color: {color}; margin-bottom: 5px;'>{icon}</div>
                    <div style='font-size: 12px; color: {color}; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;'>{name}</div>
                </div>
            """
            
            # 添加箭头（除了最后一个节点）
            if i < len(nodes) - 1:
                indicator_html += """
                    <div style='color: #9ca3af; font-size: 20px; margin: 0 8px; font-weight: bold;'>→</div>
                """
        
        indicator_html += """
            </div>
        </div>
        """
        
        return indicator_html
    
    async def add_node_message(self, node_name: str, message: str, message_type: str = "info") -> List:
        """添加节点消息到聊天记录"""
        # 根据消息类型设置不同的样式
        if message_type == "start":
            icon = "🚀"
            prefix = f"**[{node_name}] 开始执行**"
        elif message_type == "progress":
            icon = "⏳"
            prefix = f"**[{node_name}] 进行中**"
        elif message_type == "complete":
            icon = "✅"
            prefix = f"**[{node_name}] 完成**"
        elif message_type == "error":
            icon = "❌"
            prefix = f"**[{node_name}] 错误**"
        elif message_type == "input_request":
            icon = "💭"
            prefix = f"**[{node_name}] 需要输入**"
        else:
            icon = "ℹ️"
            prefix = f"**[{node_name}] 信息**"
        
        formatted_message = f"{icon} {prefix}\n{message}"
        
        # 添加时间戳
        timestamp = time.strftime("%H:%M:%S")
        
        # 构造消息对象
        bot_message = {
            "role": "assistant",
            "content": formatted_message,
            "metadata": {
                "title": f"{node_name} - {timestamp}",
                "node": node_name.lower().replace(" ", "_"),
                "type": message_type
            }
        }
        
        self.messages.append(bot_message)
        return self.messages.copy()
    
    async def add_user_input(self, user_input: str) -> List:
        """添加用户输入到聊天记录"""
        if user_input.strip():
            user_message = {
                "role": "user", 
                "content": user_input,
                "metadata": {
                    "title": f"用户 - {time.strftime('%H:%M:%S')}"
                }
            }
            self.messages.append(user_message)
        return self.messages.copy()
    
    def update_node_state(self, node_id: str, state: str) -> str:
        """更新节点状态"""
        self.node_states[node_id] = state
        self.current_node = node_id if state == "active" else None
        return self._create_node_indicator(self.current_node)
    
    def reset_workflow(self) -> Tuple[List, str, str, str, bool]:
        """重置工作流状态"""
        self.messages = []
        self.node_states = {}
        self.current_node = None
        self.user_inputs = {}
        
        return (
            [],  # 清空聊天记录
            self._create_node_indicator(),  # 重置节点指示器
            "",  # 隐藏快捷回复
            "",  # 清空输入框
            False   # 禁用发送按钮
        )
    
    def enable_user_input(self, prompt: str = "请输入...", quick_replies: List[str] = None) -> Tuple[str, str, bool]:
        """启用用户输入 - 简化版"""
        return (
            "",  # 不显示快捷回复
            prompt,  # 设置提示文本
            True     # 启用发送按钮
        )
    
    def disable_user_input(self) -> Tuple[str, str, bool]:
        """禁用用户输入"""
        return (
            "",  # 隐藏快捷回复
            "工作流执行中...",  # 设置提示文本
            False   # 禁用发送按钮
        )
    
    async def stream_node_execution(self, node_name: str, execution_func, *args, **kwargs):
        """流式执行节点并更新界面"""
        try:
            # 开始执行
            yield await self.add_node_message(
                node_name, 
                f"正在执行{node_name}...", 
                "start"
            ), self.update_node_state(node_name.lower().replace(" ", "_"), "active")
            
            # 执行节点函数
            if asyncio.iscoroutinefunction(execution_func):
                result = await execution_func(*args, **kwargs)
            else:
                result = execution_func(*args, **kwargs)
            
            # 完成执行
            yield await self.add_node_message(
                node_name,
                f"{node_name}执行完成！\n结果：{str(result)[:200]}...",
                "complete"
            ), self.update_node_state(node_name.lower().replace(" ", "_"), "completed")
            
        except Exception as e:
            # 错误处理
            yield await self.add_node_message(
                node_name,
                f"执行失败：{str(e)}",
                "error"
            ), self.update_node_state(node_name.lower().replace(" ", "_"), "error")

    def _create_quick_replies(self, replies: List[str]) -> str:
        """创建快捷回复HTML - 简化版，不再使用"""
        return ""  # 直接返回空字符串，不再生成快捷回复 