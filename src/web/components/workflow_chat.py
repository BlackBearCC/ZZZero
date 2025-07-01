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
        self.node_results = {}  # 存储每个节点的结果
        self.user_inputs = {}
        
    def create_workflow_chat_interface(self) -> Dict[str, Any]:
        """创建工作流聊天界面"""
        components = {}
        
        with gr.Column():
            # 工作流进度区域 - 竖向布局
            components['workflow_progress'] = gr.HTML(
                value=self._create_workflow_progress(),
                label="🔄 工作流执行进度",
                visible=True
            )
            
            # 快捷回复区域（保留，但初始为空）
            components['quick_replies'] = gr.HTML(
                value="",
                visible=False,
                elem_id="quick_replies_area"
            )
            
            # 用户输入区域（支持节点交互）
            with gr.Row():
                components['user_input'] = gr.Textbox(
                    label="💬 与工作流交互",
                    placeholder="工作流采用自动执行模式...",
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
    
    def _create_workflow_progress(self) -> str:
        """创建竖向工作流进度显示"""
        nodes = [
            ("📋", "剧情规划", "planning"),
            ("👥", "角色分析", "character"), 
            ("📚", "剧情生成", "plot"),
            ("📄", "CSV导出", "export")
        ]
        
        progress_html = """
        <div style='background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);'>
            <h3 style='color: #374151; margin: 0 0 20px 0; text-align: center; font-weight: 700; font-size: 18px;'>🔄 工作流执行进度</h3>
        """
        
        for i, (icon, name, node_id) in enumerate(nodes):
            # 判断节点状态
            state = self.node_states.get(node_id, "pending")
            if self.current_node == node_id and state != "completed":
                status_class = "active"
                status_color = "#f59e0b"
                status_bg = "rgba(245, 158, 11, 0.1)"
                status_text = "执行中..."
            elif state == "completed":
                status_class = "completed"
                status_color = "#10b981"
                status_bg = "rgba(16, 185, 129, 0.1)"
                status_text = "已完成"
            elif state == "error":
                status_class = "error"
                status_color = "#ef4444"
                status_bg = "rgba(239, 68, 68, 0.1)"
                status_text = "执行失败"
            else:
                status_class = "pending"
                status_color = "#9ca3af"
                status_bg = "rgba(156, 163, 175, 0.1)"
                status_text = "等待中..."
            
            # 获取节点结果
            result_content = self.node_results.get(node_id, "")
            
            progress_html += f"""
            <div style='display: flex; align-items: flex-start; margin: 15px 0; padding: 15px; border-radius: 10px; background: {status_bg}; border-left: 4px solid {status_color};'>
                <!-- 左侧节点信息 -->
                <div style='flex: 0 0 200px; margin-right: 20px;'>
                    <div style='display: flex; align-items: center; margin-bottom: 8px;'>
                        <span style='font-size: 24px; margin-right: 8px;'>{icon}</span>
                        <div>
                            <div style='font-weight: 600; color: {status_color}; font-size: 16px;'>{name}</div>
                            <div style='font-size: 12px; color: {status_color}; font-weight: 500;'>{status_text}</div>
                        </div>
                    </div>
                </div>
                
                <!-- 右侧结果展示 -->
                <div style='flex: 1; min-height: 60px;'>
                    <div style='background: #ffffff; border: 1px solid {status_color}; border-radius: 8px; padding: 12px; min-height: 50px;'>
                        {result_content if result_content else '<span style="color: #9ca3af; font-style: italic;">等待执行结果...</span>'}
                    </div>
                </div>
            </div>
            """
            
            # 添加连接线（除了最后一个节点）
            if i < len(nodes) - 1:
                progress_html += """
                <div style='text-align: center; margin: 5px 0;'>
                    <div style='width: 2px; height: 15px; background: #e5e7eb; margin: 0 auto;'></div>
                    <div style='color: #9ca3af; font-size: 14px; margin: 2px 0;'>↓</div>
                </div>
                """
        
        progress_html += "</div>"
        return progress_html
    
    async def add_node_message(self, node_name: str, message: str, message_type: str = "info") -> List:
        """添加节点消息到聊天记录 - 简化版"""
        # 直接更新节点结果而不是聊天记录
        node_mapping = {
            "剧情规划": "planning",
            "角色分析": "character", 
            "剧情生成": "plot",
            "CSV导出": "export"
        }
        
        node_id = node_mapping.get(node_name)
        if node_id:
            # 根据消息类型更新节点结果
            if message_type in ["complete", "progress"]:
                self.node_results[node_id] = self._format_result_content(message, message_type)
        
        return []  # 不再使用聊天记录
    
    def _format_result_content(self, message: str, message_type: str) -> str:
        """格式化结果内容"""
        if message_type == "complete":
            # 处理真实的LLM生成内容
            if len(message) > 500:
                # 长内容需要截断显示
                preview = message[:500] + "..."
                return f"""
                <div style='color: #10b981;'>
                    <div style='font-weight: 600; margin-bottom: 8px;'>✅ 执行完成</div>
                    <div style='background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 6px; padding: 10px; font-size: 13px; max-height: 200px; overflow-y: auto;'>
                        <pre style='white-space: pre-wrap; margin: 0; font-family: inherit;'>{preview}</pre>
                    </div>
                    <div style='margin-top: 8px; font-size: 12px; color: #6c757d;'>
                        总长度: {len(message)} 字符 | <a href="#" onclick="this.previousElementSibling.previousElementSibling.firstElementChild.style.maxHeight='none'; this.style.display='none';">展开全部</a>
                    </div>
                </div>
                """
            else:
                # 短内容直接显示
                return f"""
                <div style='color: #10b981;'>
                    <div style='font-weight: 600; margin-bottom: 8px;'>✅ 执行完成</div>
                    <div style='background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 6px; padding: 10px; font-size: 13px;'>
                        <pre style='white-space: pre-wrap; margin: 0; font-family: inherit;'>{message}</pre>
                    </div>
                </div>
                """
        elif message_type == "streaming":
            # 流式内容显示
            return f"""
            <div style='color: #f59e0b;'>
                <div style='font-weight: 600; margin-bottom: 8px;'>⚡ 实时生成中...</div>
                <div style='background: #fffbeb; border: 1px solid #fbbf24; border-radius: 6px; padding: 10px; font-size: 13px; max-height: 300px; overflow-y: auto; border-left: 4px solid #f59e0b;'>
                    <pre style='white-space: pre-wrap; margin: 0; font-family: inherit; line-height: 1.4;'>{message}</pre>
                    <div style='display: inline-block; width: 8px; height: 8px; background-color: #f59e0b; border-radius: 50%; margin-left: 4px; animation: pulse 1s infinite;'></div>
                </div>
                <div style='margin-top: 5px; font-size: 12px; color: #92400e;'>
                    当前长度: {len(message)} 字符
                </div>
            </div>
            """
        elif message_type == "progress":
            return f"""
            <div style='color: #f59e0b;'>
                <div style='font-weight: 600; margin-bottom: 5px;'>⏳ 执行中...</div>
                <div style='font-size: 14px;'>{message}</div>
            </div>
            """
        elif message_type == "error":
            return f"""
            <div style='color: #ef4444;'>
                <div style='font-weight: 600; margin-bottom: 5px;'>❌ 执行失败</div>
                <div style='font-size: 14px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 8px;'>{message}</div>
            </div>
            """
        
        return f"<div style='font-size: 14px;'>{message}</div>"
    
    async def add_user_input(self, user_input: str) -> List:
        """添加用户输入到聊天记录 - 简化版"""
        return []  # 不再使用聊天记录
    
    def update_node_state(self, node_id: str, state: str) -> str:
        """更新节点状态"""
        self.node_states[node_id] = state
        self.current_node = node_id if state == "active" else None
        return self._create_workflow_progress()
    
    def reset_workflow(self) -> Tuple[str, str, str, bool]:
        """重置工作流状态"""
        self.messages = []
        self.node_states = {}
        self.node_results = {}
        self.current_node = None
        self.user_inputs = {}
        
        return (
            self._create_workflow_progress(),  # 重置进度显示
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

    def _create_node_indicator(self, current_node: str = None) -> str:
        """创建节点状态指示器 - 废弃，使用新的进度显示"""
        return self._create_workflow_progress() 