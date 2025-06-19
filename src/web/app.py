"""
Gradio应用主文件 - 提供类ChatGPT风格的界面
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

# 配置日志
logger = logging.getLogger(__name__)

class AgentApp:
    """Agent应用界面"""
    
    def __init__(self, 
                 title: str = "ZZZero AI Agent",
                 description: str = "基于节点编排的AI Agent框架"):
        self.title = title
        self.description = description
        self.current_agent = None
        self.agent = None  # 添加agent属性
        self.tool_manager = None
        self.llm = None
        # 保存当前配置
        self.current_config = {
            'llm_provider': 'doubao',
            'model_name': 'ep-20250221154410-vh78x',
            'temperature': 0.7,
            'agent_type': 'react',
            'max_iterations': 5,
            'available_tools': [],
            'enabled_mcp_servers': []
        }
        
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
            enabled_servers = self.current_config.get('enabled_mcp_servers', ['csv', 'chromadb'])  # 默认启用
            if self.tool_manager:
                self.tool_manager.set_enabled_servers(enabled_servers)
            
            # 创建或更新Agent
            self.agent = ReactAgent(
                llm=self.llm,  # 传递LLM实例作为第一个参数
                tool_manager=self.tool_manager,
                max_iterations=self.current_config.get('max_iterations', 10),
                name="智能助手"
            )
            
            # 同时设置current_agent以兼容其他方法
            self.current_agent = self.agent
            
            logger.info("Agent配置更新成功")
            
        except Exception as e:
            error_msg = f"更新Agent配置失败: {e}"
            logger.error(error_msg)
            return error_msg
    

            
    def create_interface(self) -> gr.Blocks:
        """创建Gradio界面"""
        with gr.Blocks(title=self.title, theme=gr.themes.Soft()) as app:
            # 标题
            gr.Markdown(f"# {self.title}")
            gr.Markdown(f"{self.description}")
            
            with gr.Row():
                # 左侧配置面板
                with gr.Column(scale=1):
                    gr.Markdown("## ⚙️ 配置面板")
                    
                    # LLM配置
                    with gr.Accordion("🧠 LLM配置", open=True):
                        llm_provider = gr.Dropdown(
                            choices=["doubao", "openai"],
                            value="doubao",
                            label="LLM提供商"
                        )
                        model_name = gr.Textbox(
                            value="ep-20250221154410-vh78x",  # DOUBAO_MODEL_DEEPSEEKV3
                            label="模型名称",
                            placeholder="例如: ep-20250221154410-vh78x (deepseekv3)"
                        )
                        temperature = gr.Slider(
                            minimum=0.0,
                            maximum=1.0,
                            value=0.7,
                            step=0.1,
                            label="生成温度"
                        )
                    
                    # Agent配置
                    with gr.Accordion("🤖 Agent配置", open=True):
                        agent_type = gr.Dropdown(
                            choices=["react"],
                            value="react",
                            label="Agent类型"
                        )
                        max_iterations = gr.Slider(
                            minimum=1,
                            maximum=10,
                            value=5,
                            step=1,
                            label="最大迭代次数"
                        )
                    
                    # MCP服务器管理
                    with gr.Accordion("🔌 MCP服务器管理", open=True):
                        # 服务器状态和勾选在一起
                        mcp_servers_status = gr.HTML(
                            value="<p>正在加载MCP服务器信息...</p>",
                            label="MCP服务器状态"
                        )
                        
                        # 获取初始的servers列表并设置默认值
                        initial_choices = []
                        default_enabled = []
                        try:
                            from tools.mcp_manager import mcp_manager
                            servers = mcp_manager.list_servers()
                            for server in servers:
                                if 'name' in server and 'id' in server:
                                    choice = (f"{server['name']} ({server['id']})", server['id'])
                                    initial_choices.append(choice)
                                    # 默认勾选csv和chromadb
                                    if server['id'] in ['csv', 'chromadb']:
                                        default_enabled.append(server['id'])
                        except Exception as e:
                            print(f"初始化MCP服务器失败: {e}")
                        
                        enabled_mcp_servers = gr.CheckboxGroup(
                            choices=initial_choices,
                            value=default_enabled,
                            label="启用的MCP服务器"
                        )
                        
                        # 远程服务器添加
                        with gr.Row():
                            remote_server_name = gr.Textbox(
                                placeholder="服务器名称",
                                scale=2,
                                label="远程服务器名称"
                            )
                            remote_server_url = gr.Textbox(
                                placeholder="http://localhost:3000",
                                scale=3,
                                label="远程服务器URL"
                            )
                            add_remote_btn = gr.Button("添加远程服务器", scale=1)
                        
                        refresh_mcp_btn = gr.Button("刷新MCP服务器", variant="secondary")
                    
                    # 工具选择
                    with gr.Accordion("🔧 传统工具配置", open=False):
                        available_tools = gr.CheckboxGroup(
                            choices=[
                                "web_search",
                                "calculator", 
                                "file_reader",
                                "code_executor",
                                "database_query"
                            ],
                            value=[],
                            label="启用的传统工具"
                        )
                    
                    # 配置状态（只显示，不需要应用按钮）
                    config_status = gr.Textbox(label="配置状态", interactive=False, value="✅ 配置已自动应用")
                
                # 右侧聊天界面
                with gr.Column(scale=3):
                    # 聊天历史
                    chatbot = gr.Chatbot(
                        height=500,
                        show_label=False,
                        elem_classes=["chat-window"],
                        type="messages"
                    )
                    
                    # 输入区域
                    with gr.Row():
                        msg_input = gr.Textbox(
                            placeholder="输入消息...",
                            show_label=False,
                            scale=9,
                            lines=1,
                            max_lines=5
                        )
                        send_btn = gr.Button("发送", variant="primary", scale=1)
                    
                    # 批量任务
                    with gr.Accordion("📋 批量任务", open=False):
                        batch_input = gr.Textbox(
                            placeholder="每行一个任务...",
                            lines=5,
                            label="批量任务列表"
                        )
                        batch_parallel = gr.Checkbox(
                            label="并行执行",
                            value=True
                        )
                        batch_btn = gr.Button("执行批量任务")
                        batch_results = gr.Dataframe(
                            headers=["任务", "状态", "结果", "耗时"],
                            label="批量任务结果"
                        )
                    
                    # 执行详情
                    with gr.Accordion("📊 执行详情", open=False):
                        execution_trace = gr.JSON(label="执行轨迹")
                        metrics_display = gr.Textbox(label="执行指标", lines=3)
                        
                    # 流程可视化
                    with gr.Accordion("🔄 流程可视化", open=False):
                        # 实时节点状态
                        node_status = gr.DataFrame(
                            headers=["节点", "类型", "状态", "耗时(s)", "输出预览"],
                            label="节点执行状态",
                            interactive=False
                        )
                        # 流程图
                        flow_diagram = gr.HTML(label="执行流程图")
                        # 自动刷新
                        auto_refresh = gr.Checkbox(label="自动刷新", value=True)
            
            # === 配置变化自动应用 ===
            async def on_config_change(*args):
                """配置变化时自动应用"""
                llm_provider, model_name, temperature, agent_type, max_iterations, available_tools, enabled_mcp_servers = args
                
                # 更新配置
                old_config = self.current_config.copy()
                self.current_config.update({
                    'llm_provider': llm_provider,
                    'model_name': model_name,
                    'temperature': temperature,
                    'agent_type': agent_type,
                    'max_iterations': max_iterations,
                    'available_tools': available_tools,
                    'enabled_mcp_servers': enabled_mcp_servers
                })
                
                # 只有在配置真正改变时才更新Agent
                config_changed = old_config != self.current_config
                if config_changed:
                    await self._update_agent_config()
                    logger.info("配置已更改，Agent已更新")
                
                total_tools = len(available_tools) + len(enabled_mcp_servers)
                status_text = f"✅ 配置已应用！使用 {llm_provider}/{model_name}，启用 {total_tools} 个工具"
                if not config_changed:
                    status_text += " (无变化)"
                
                return status_text
            
            # 绑定配置变化事件
            for component in [llm_provider, model_name, temperature, agent_type, max_iterations, available_tools, enabled_mcp_servers]:
                component.change(
                    on_config_change,
                    inputs=[llm_provider, model_name, temperature, agent_type, max_iterations, available_tools, enabled_mcp_servers],
                    outputs=[config_status]
                )
            
            # MCP服务器相关事件
            refresh_mcp_btn.click(
                self._refresh_mcp_servers,
                outputs=[mcp_servers_status, enabled_mcp_servers]
            )
            
            add_remote_btn.click(
                self._add_remote_server,
                inputs=[remote_server_name, remote_server_url],
                outputs=[remote_server_name, remote_server_url, mcp_servers_status, enabled_mcp_servers]
            )
            
            # 页面加载时的初始化
            async def on_load():
                """页面加载时的初始化"""
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
                            
                            status_html += f"<div style='margin: 8px 0; padding: 8px; border: 1px solid #ddd; border-radius: 4px;'>"
                            status_html += f"<strong>{status_icon} {enable_icon} {info['name']}</strong><br/>"
                            status_html += f"<small>ID: {server_id} | 状态: {'运行中' if info['running'] else '未运行'}</small><br/>"
                            status_html += f"<small>工具: {info.get('enabled_tools', 0)}/{info.get('total_tools', 0)} 个可用</small><br/>"
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
                        if info.get('enabled', False):
                            default_enabled.append(server_id)
                    
                    # 返回状态HTML和更新后的CheckboxGroup
                    import gradio as gr
                    return (
                        status_html,
                        gr.update(choices=choices, value=default_enabled)
                    )
                    
                except Exception as e:
                    error_msg = f"页面加载初始化失败: {e}"
                    logger.error(error_msg)
                    import gradio as gr
                    return (
                        f"❌ 初始化失败: {str(e)}",
                        gr.update(choices=[], value=[])
                    )
            
            app.load(
                on_load,
                outputs=[mcp_servers_status, enabled_mcp_servers]
            )
            
            # MCP服务器勾选变化事件
            enabled_mcp_servers.change(
                self._on_mcp_servers_change,
                inputs=[enabled_mcp_servers],
                outputs=[mcp_servers_status]
            )
            
            msg_input.submit(
                self._stream_chat,
                inputs=[msg_input, chatbot],
                outputs=[msg_input, chatbot, execution_trace, metrics_display, node_status, flow_diagram],
                show_progress=False  # 禁用进度条以支持流式输出
            )
            
            send_btn.click(
                self._stream_chat,
                inputs=[msg_input, chatbot],
                outputs=[msg_input, chatbot, execution_trace, metrics_display, node_status, flow_diagram],
                show_progress=False  # 禁用进度条以支持流式输出
            )
            
            batch_btn.click(
                self._batch_execute,
                inputs=[batch_input, batch_parallel],
                outputs=[batch_results]
            )
            
            # 添加自定义CSS
            app.css = """
            * {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
            }
            .chat-window {
                border-radius: 10px;
                border: 1px solid #e0e0e0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
            }
            .chat-window .message {
                padding: 10px;
                margin: 5px;
                border-radius: 10px;
            }
            .chat-window .user {
                background-color: #e3f2fd;
                margin-left: 20%;
            }
            .chat-window .bot {
                background-color: #f5f5f5;
                margin-right: 20%;
            }
            .gradio-container {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
                height: 100vh;
                overflow-y: auto;
            }
            """
            
        return app
    
    async def _refresh_mcp_servers(self):
        """刷新MCP服务器状态"""
        import gradio as gr
        
        try:
            from tools.mcp_manager import mcp_manager
            
            # 使用正确的方法获取服务器列表
            servers_dict = mcp_manager.list_servers()
            
            # 转换为列表格式以兼容后续代码
            servers = []
            for server_id, info in servers_dict.items():
                servers.append({
                    'id': server_id,
                    'name': info['name'],
                    'description': info['description'],
                    'connected': info['running'],  # running 对应 connected
                    'type': 'local_stdio',
                    'tools': []  # 简化版没有工具列表
                })
            
            # 生成状态HTML
            status_html = "<div style='font-family: monospace;'>"
            status_html += "<h4>🔌 MCP服务器状态</h4>"
            
            if not servers:
                status_html += "<p>暂无可用的MCP服务器</p>"
            else:
                for server in servers:
                    status_icon = "🟢" if server['connected'] else "🔴"
                    type_icon = {"local_stdio": "💻", "remote_http": "🌐", "local_http": "🏠"}.get(server['type'], "❓")
                    
                    status_html += f"<div style='margin: 8px 0; padding: 8px; border: 1px solid #ddd; border-radius: 4px;'>"
                    status_html += f"<strong>{status_icon} {type_icon} {server['name']}</strong><br/>"
                    status_html += f"<small>ID: {server['id']} | 类型: {server['type']}</small><br/>"
                    status_html += f"<small>状态: {'已连接' if server['connected'] else '未连接'}</small><br/>"
                    status_html += f"<small>{server['description']}</small>"
                    status_html += "</div>"
            
            status_html += "</div>"
            
            # 生成可选择的服务器列表
            choices = []
            for server in servers:
                try:
                    if 'name' in server and 'id' in server:
                        label = f"{server['name']} ({server['id']})"
                        value = server['id']
                        choices.append((label, value))
                except Exception as e:
                    print(f"跳过无效服务器配置: {e}")
                    continue
            
            return status_html, gr.update(choices=choices)
            
        except Exception as e:
            error_html = f"<div style='color: red;'>❌ 刷新MCP服务器失败: {str(e)}</div>"
            return error_html, gr.update(choices=[])
    
    async def _on_mcp_servers_change(self, enabled_servers: List[str]):
        """处理MCP服务器勾选变化 - 只更新工具暴露，不重启服务器"""
        try:
            # 防护：如果 enabled_servers 为空或者无效，直接返回当前状态
            if not isinstance(enabled_servers, list):
                enabled_servers = []
            
            # 更新工具管理器的启用服务器（只影响工具暴露）
            if self.tool_manager:
                self.tool_manager.set_enabled_servers(enabled_servers)
                logger.info(f"已更新启用的MCP服务器: {enabled_servers}")
            
            # 获取最新的服务器状态
            from tools.mcp_manager import mcp_manager
            
            # 更新配置中的enabled_mcp_servers
            self.current_config['enabled_mcp_servers'] = enabled_servers
            
            # 获取所有服务器
            servers_dict = mcp_manager.list_servers()
            if not servers_dict:
                status_html, _ = await self._refresh_mcp_servers()
                return status_html
            
            status_messages = []
            
            for server_id, info in servers_dict.items():
                is_enabled = server_id in enabled_servers
                is_running = info['running']
                
                # 只记录状态变化，不实际启动/停止服务器
                if is_enabled:
                    status_messages.append(f"✅ 已启用工具: {info['name']}")
                else:
                    status_messages.append(f"⚪ 已禁用工具: {info['name']}")
            
            # 刷新状态
            status_html, _ = await self._refresh_mcp_servers()
            
            # 添加操作消息
            if status_messages:
                messages_html = "<br/>".join(status_messages)
                status_html = f"{status_html}<div style='margin-top: 10px; padding: 10px; background-color: #f0f8ff; border-radius: 4px;'>{messages_html}</div>"
            
            return status_html
            
        except Exception as e:
            # 发生错误时，返回刷新后的状态
            try:
                status_html, _ = await self._refresh_mcp_servers()
                error_msg = f"<div style='color: red;'>❌ 处理MCP服务器变化失败: {str(e)}</div>"
                return f"{status_html}<br/>{error_msg}"
            except:
                return f"<div style='color: red;'>❌ 处理MCP服务器变化失败: {str(e)}</div>"

    async def _add_remote_server(self, name: str, url: str):
        """添加远程MCP服务器"""
        import gradio as gr
        
        try:
            if not name or not url:
                return name, url, "<div style='color: red;'>❌ 请填写服务器名称和URL</div>", gr.update()
            
            from tools.mcp_manager import mcp_manager
            
            # 生成服务器ID
            server_id = f"remote_{name.lower().replace(' ', '_')}"
            
            # 暂时不支持添加远程服务器功能
            raise NotImplementedError("暂时不支持添加远程服务器功能")
            
            # 刷新状态
            status_html, checkbox_update = await self._refresh_mcp_servers()
            
            success_html = f"<div style='color: green;'>✅ 成功添加远程服务器: {name}</div>"
            
            # 清空输入框
            return "", "", success_html, checkbox_update
            
        except Exception as e:
            error_html = f"<div style='color: red;'>❌ 添加远程服务器失败: {str(e)}</div>"
            return name, url, error_html, gr.update()
    
    async def _stream_chat(self, message: str, history: List[Dict[str, str]]):
        """流式处理聊天消息，支持打字机效果"""
        # 如果没有Agent，尝试创建一个默认的
        if not self.current_agent:
            try:
                if not self.tool_manager:
                    await self._update_agent_config()
                else:
                    from agents.react_agent import ReactAgent
                    self.agent = ReactAgent(
                        llm=self.llm,
                        tool_manager=self.tool_manager,
                        max_iterations=self.current_config.get('max_iterations', 10),
                        name="智能助手"
                    )
                    self.current_agent = self.agent
                    logger.info("Agent创建完成（复用现有工具管理器）")
            except Exception as e:
                print(f"创建默认Agent失败: {e}")
                history.append({"role": "user", "content": message})
                history.append({"role": "assistant", "content": "抱歉，系统初始化中，请稍后再试。"})
                yield "", history, {}, "", [], ""
                return
        
        # 添加用户消息
        history.append({"role": "user", "content": message})
        
        # 添加空的助手消息用于流式更新
        history.append({"role": "assistant", "content": ""})
        
        try:
            accumulated_response = ""
            tool_calls_made = []
            execution_trace = []
            
            # 使用流式方法
            async for chunk_data in self.current_agent.stream_run(message):
                chunk_type = chunk_data.get("type", "")
                chunk_content = chunk_data.get("content", "")
                
                if chunk_type == "text_chunk":
                    # 文本块 - 打字机效果
                    accumulated_response += chunk_content
                    
                    # 更新历史记录中的最后一条助手消息
                    history[-1]["content"] = accumulated_response
                    
                    # 返回更新的历史记录实现打字机效果
                    yield "", history, {}, "", [], ""
                    
                    # 短暂延迟实现打字机效果
                    await asyncio.sleep(0.02)  # 20ms延迟
                    
                elif chunk_type == "tool_result":
                    # 工具调用结果
                    tool_name = chunk_data.get("metadata", {}).get("tool_name", "")
                    tool_input = chunk_data.get("metadata", {}).get("tool_input", "")
                    tool_output = chunk_data.get("metadata", {}).get("tool_output", "")
                    
                    accumulated_response += chunk_content
                    history[-1]["content"] = accumulated_response
                    
                    # 记录工具调用
                    tool_calls_made.append({
                        "tool_name": tool_name,
                        "input": tool_input,
                        "output": tool_output
                    })
                    
                    # 添加工具调用到执行轨迹
                    execution_trace.append({
                        "node": "tool_execution",
                        "type": "tool",
                        "duration": 0.0,
                        "state": "success",
                        "output": {
                            "tool_name": tool_name,
                            "tool_input": tool_input,
                            "tool_output": tool_output
                        }
                    })
                    
                    yield "", history, execution_trace, "", [], ""
                    
                elif chunk_type == "tool_error":
                    # 工具执行错误
                    error_msg = chunk_data.get("metadata", {}).get("error", "")
                    accumulated_response += chunk_content
                    history[-1]["content"] = accumulated_response
                    
                    execution_trace.append({
                        "node": "tool_error",
                        "type": "tool",
                        "duration": 0.0,
                        "state": "failed",
                        "output": {"error": error_msg}
                    })
                    
                    yield "", history, execution_trace, "", [], ""
                    
                elif chunk_type == "final_result":
                    # 最终结果（回退模式）
                    history[-1]["content"] = chunk_content
                    yield "", history, {}, "", [], ""
            
            # 生成最终指标
            metrics_text = self._format_stream_metrics(tool_calls_made, accumulated_response)
            
            # 生成节点状态表
            node_status = self._generate_node_status(execution_trace)
            
            # 生成流程图
            flow_diagram = self._generate_flow_diagram(execution_trace)
            
            # 最终输出
            yield "", history, execution_trace, metrics_text, node_status, flow_diagram
            
        except Exception as e:
            # 处理错误
            error_msg = f"处理请求时出现错误: {str(e)}"
            print(error_msg)
            history[-1]["content"] = f"抱歉，{error_msg}"
            yield "", history, {}, "", [], ""
    
    def _format_stream_metrics(self, tool_calls: List[Dict], response_text: str) -> str:
        """格式化流式处理指标"""
        metrics = {
            "工具调用次数": len(tool_calls),
            "响应字符数": len(response_text),
            "工具类型": list(set(call.get("tool_name", "") for call in tool_calls)) if tool_calls else []
        }
        
        lines = []
        for key, value in metrics.items():
            if isinstance(value, list):
                lines.append(f"{key}: {', '.join(value) if value else '无'}")
            else:
                lines.append(f"{key}: {value}")
        
        return "\n".join(lines)
    
    def _generate_node_status(self, trace: List[Dict[str, Any]]) -> List[List[Any]]:
        """生成节点状态表"""
        if not trace:
            return []
        
        status_data = []
        for step in trace:
            node_name = step.get("node", "")
            node_type = step.get("type", "")
            state = step.get("state", "")
            duration = step.get("duration", 0)
            
            # 获取输出预览
            output = step.get("output", {})
            if isinstance(output, dict):
                # 提取关键信息作为预览
                if "answer" in output:
                    preview = output["answer"][:50] + "..." if len(output.get("answer", "")) > 50 else output.get("answer", "")
                elif "thought" in output:
                    preview = output["thought"][:50] + "..." if len(output.get("thought", "")) > 50 else output.get("thought", "")
                elif "action" in output:
                    preview = f"执行: {output.get('action', '')[:30]}..."
                else:
                    preview = str(output)[:50] + "..." if len(str(output)) > 50 else str(output)
            else:
                preview = str(output)[:50] + "..." if len(str(output)) > 50 else str(output)
            
            # 添加表情符号表示状态
            state_emoji = {
                "success": "✅",
                "failed": "❌",
                "running": "🔄",
                "pending": "⏳"
            }.get(state, "❓")
            
            status_data.append([
                node_name,
                node_type,
                f"{state_emoji} {state}",
                f"{duration:.2f}" if duration else "0.00",
                preview
            ])
        
        return status_data
    
    def _generate_flow_diagram(self, trace: List[Dict[str, Any]]) -> str:
        """生成流程图HTML"""
        if not trace:
            return "<p>暂无执行流程</p>"
        
        # 使用Mermaid生成流程图
        mermaid_code = "graph TD\n"
        
        # 添加节点
        for i, step in enumerate(trace):
            node_name = step.get("node", f"node_{i}")
            node_type = step.get("type", "unknown")
            state = step.get("state", "")
            
            # 根据状态选择样式
            if state == "success":
                style = "fill:#90EE90"
            elif state == "failed":
                style = "fill:#FFB6C1"
            elif state == "running":
                style = "fill:#87CEEB"
            else:
                style = "fill:#F0F0F0"
            
            # 添加节点定义
            label = f"{node_name}\\n[{node_type}]"
            mermaid_code += f"    {node_name}[\"{label}\"]:::state{i}\n"
            mermaid_code += f"    classDef state{i} {style}\n"
            
            # 添加连接
            if i > 0:
                prev_node = trace[i-1].get("node", f"node_{i-1}")
                mermaid_code += f"    {prev_node} --> {node_name}\n"
        
        # 生成HTML
        html = f"""
        <div id="mermaid-diagram">
            <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
            <script>
                mermaid.initialize({{ startOnLoad: true }});
            </script>
            <div class="mermaid">
                {mermaid_code}
            </div>
        </div>
        <style>
            #mermaid-diagram {{
                width: 100%;
                min-height: 300px;
                background: #f9f9f9;
                border-radius: 8px;
                padding: 20px;
            }}
            .mermaid {{
                text-align: center;
            }}
        </style>
        """
        
        return html
    
    async def _batch_execute(self, batch_input: str, parallel: bool):
        """执行批量任务"""
        if not self.current_agent:
            return [["", "错误", "请先配置Agent！", ""]]
        
        tasks = [line.strip() for line in batch_input.split('\n') if line.strip()]
        results = []
        
        if parallel:
            # 并行执行
            async_tasks = [self.current_agent.run(task) for task in tasks]
            task_results = await asyncio.gather(*async_tasks, return_exceptions=True)
            
            for task, result in zip(tasks, task_results):
                if isinstance(result, Exception):
                    results.append([task, "失败", str(result), ""])
                else:
                    results.append([
                        task,
                        "成功" if result.success else "失败",
                        result.result or result.error,
                        f"{result.duration:.2f}s" if result.duration else ""
                    ])
        else:
            # 串行执行
            for task in tasks:
                try:
                    result = await self.current_agent.run(task)
                    results.append([
                        task,
                        "成功" if result.success else "失败",
                        result.result or result.error,
                        f"{result.duration:.2f}s" if result.duration else ""
                    ])
                except Exception as e:
                    results.append([task, "失败", str(e), ""])
        
        return results
    
    def launch(self, **kwargs):
        """启动应用"""
        app = self.create_interface()
        app.launch(**kwargs)