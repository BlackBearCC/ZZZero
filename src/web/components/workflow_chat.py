"""
工作流聊天界面组件
支持流式显示节点执行状态和用户交互
"""

import gradio as gr
import json
from typing import Dict, Any, List, Tuple, Optional
import asyncio
import time
import logging

class WorkflowChat:
    """工作流聊天界面类"""
    
    def __init__(self, workflow_name: str = "工作流", nodes: List[Dict[str, str]] = None):
        """
        初始化工作流聊天界面
        
        Args:
            workflow_name: 工作流名称
            nodes: 节点列表，每个节点包含id、name、description字段
        """
        self.workflow_name = workflow_name
        self.nodes = nodes or []
        self.messages = []
        self.current_node = None
        self.node_states = {}
        self.node_results = {}  # 存储每个节点的结果
        self.user_inputs = {}
        
        # 初始化节点状态
        for node in self.nodes:
            self.node_states[node['id']] = 'pending'
        
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
                components['add_to_queue_btn'] = gr.Button(
                    "➕ 添加到队列",
                    variant="secondary",
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
        # 使用动态节点配置，如果没有配置则使用默认节点
        if self.nodes:
            # 为每个节点添加默认图标
            node_icons = {
                "planning": "📋",
                "daily": "📅", 
                "assignment": "👥",
                "integration": "🔗",
                "save": "💾",
                "plot": "📚",
                "character": "👤",
                "location": "📍"
            }
            nodes = [(node_icons.get(node['id'], "⚙️"), node['name'], node['id']) for node in self.nodes]
        else:
            # 默认节点配置（向后兼容）
            nodes = [
                ("📋", "剧情规划", "planning"),
                ("📚", "剧情生成", "plot"),
                ("💾", "数据库写入", "save")
            ]
        
        progress_html = f"""
        <div style='background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);'>
            <h3 style='color: #374151; margin: 0 0 20px 0; text-align: center; font-weight: 700; font-size: 18px;'>🔄 {self.workflow_name}执行进度</h3>
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
            
            # 获取节点结果 - 修复键名不匹配问题
            result_content = self.node_results.get(name, "")  # 使用节点显示名称作为key
            
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
                    <div id='node_result_{node_id}' style='background: #ffffff; border: 1px solid {status_color}; border-radius: 8px; padding: 8px; min-height: 50px;'>
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
        
        progress_html += """
        </div>
        """
        return progress_html
    
    async def add_node_message(self, node_name: str, content: str, status: str = "completed"):
        """添加节点消息并立即更新UI
        
        Args:
            node_name: 节点名称
            content: 消息内容
            status: 状态 (running/completed/streaming)
        """
        try:
            # 更新结果存储
            if node_name not in self.node_results:
                self.node_results[node_name] = ""
            
            if status == "streaming":
                # 流式更新：完全替换内容
                formatted_content = self._format_result_content(content, "streaming")
            elif status == "completed":
                # 完成状态：设置最终内容
                formatted_content = self._format_result_content(content, "completed")
            else:
                # 其他状态
                formatted_content = self._format_result_content(content, status)
            
            self.node_results[node_name] = formatted_content
            
            # 更新节点状态
            node_mapping = {
                "剧情规划": "planning",
                "角色分析": "character", 
                "剧情生成": "plot",
                "数据库写入": "save"
            }
            
            node_id = node_mapping.get(node_name)
            if node_id:
                if status == "streaming":
                    self.node_states[node_id] = "active"
                elif status == "completed":
                    self.node_states[node_id] = "completed"
                elif status in ["error", "failed"]:
                    self.node_states[node_id] = "error"
                else:
                    self.node_states[node_id] = "active"
            
            # # 记录日志
            # logging.getLogger(__name__).info(f"节点 {node_name} 内容已更新，状态: {status}，内容长度: {len(content)}")
            
            # 返回更新后的进度HTML供UI刷新
            return self._create_workflow_progress()
            
        except Exception as e:
            logging.getLogger(__name__).error(f"更新节点消息失败: {e}", exc_info=True)
            return self._create_workflow_progress()
    
    def _format_result_content(self, message: str, message_type: str) -> str:
        """格式化结果内容 - 简单直接，无滚动条"""
        if message_type == "completed":
            # 已完成状态 - 简洁的绿色样式
            return f"""
            <div style='color: #10b981;'>
                <div style='font-weight: 600; margin-bottom: 8px; display: flex; align-items: center;'>
                    <span>✅ 执行完成</span>
                    <div style='margin-left: 10px; width: 12px; height: 12px; background-color: #10b981; border-radius: 50%;'></div>
                </div>
                <div style='background: #f0fdf4; border: 1px solid #10b981; border-radius: 6px; padding: 12px; font-size: 13px; border-left: 4px solid #10b981;'>
                    <pre style='white-space: pre-wrap; margin: 0; font-family: inherit; line-height: 1.5; color: #166534;'>{message}</pre>
                </div>
                <div style='margin-top: 5px; font-size: 12px; color: #10b981; display: flex; justify-content: space-between; align-items: center;'>
                    <span>最终长度: {len(message)} 字符</span>
                    <span style='font-style: italic;'>生成已完成</span>
                </div>
            </div>
            """
        elif message_type == "streaming":
            # 流式内容实时显示 - 简洁的橙色样式
            return f"""
            <div style='color: #f59e0b;'>
                <div style='font-weight: 600; margin-bottom: 8px; display: flex; align-items: center;'>
                    <span>⚡ 实时生成中...</span>
                    <div style='margin-left: 10px; width: 12px; height: 12px; background-color: #f59e0b; border-radius: 50%; animation: pulse 1.5s infinite;'></div>
                </div>
                <div style='background: #fffbeb; border: 1px solid #fbbf24; border-radius: 6px; padding: 12px; font-size: 13px; border-left: 4px solid #f59e0b;'>
                    <pre style='white-space: pre-wrap; margin: 0; font-family: inherit; line-height: 1.5; color: #92400e;'>{message}</pre>
                </div>
                <div style='margin-top: 5px; font-size: 12px; color: #92400e; display: flex; justify-content: space-between; align-items: center;'>
                    <span>当前长度: {len(message)} 字符</span>
                    <span style='font-style: italic;'>内容持续更新中...</span>
                </div>
            </div>
            <style>
                @keyframes pulse {{
                    0% {{ opacity: 1; transform: scale(1); }}
                    50% {{ opacity: 0.5; transform: scale(1.1); }}
                    100% {{ opacity: 1; transform: scale(1); }}
                }}
            </style>
            """
        elif message_type == "progress":
            return f"""
            <div style='color: #f59e0b;'>
                <div style='font-weight: 600; margin-bottom: 5px; display: flex; align-items: center;'>
                    <span>⏳ 执行中...</span>
                    <div style='margin-left: 8px; width: 8px; height: 8px; background-color: #f59e0b; border-radius: 50%; animation: bounce 1s infinite;'></div>
                </div>
                <div style='font-size: 14px; color: #92400e; font-style: italic;'>{message}</div>
            </div>
            <style>
                @keyframes bounce {{
                    0%, 20%, 50%, 80%, 100% {{ transform: translateY(0); }}
                    40% {{ transform: translateY(-3px); }}
                    60% {{ transform: translateY(-1px); }}
                }}
            </style>
            """
        elif message_type == "error":
            return f"""
            <div style='color: #ef4444;'>
                <div style='font-weight: 600; margin-bottom: 5px;'>❌ 执行失败</div>
                <div style='background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 12px; font-size: 13px; border-left: 4px solid #ef4444;'>
                    <pre style='white-space: pre-wrap; margin: 0; font-family: inherit; line-height: 1.5; color: #dc2626;'>{message}</pre>
                </div>
            </div>
            """
        
        return f"<div style='font-size: 14px; padding: 8px;'>{message}</div>"
    
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