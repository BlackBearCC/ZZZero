"""
Gradio应用主文件 - 提供类ChatGPT风格的界面
"""
import gradio as gr
import asyncio
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


class AgentApp:
    """Agent应用界面"""
    
    def __init__(self, 
                 title: str = "ZZZero AI Agent",
                 description: str = "基于节点编排的AI Agent框架"):
        self.title = title
        self.description = description
        self.current_agent = None
        self.tool_manager = None
        self.llm = None
        
    def create_interface(self) -> gr.Blocks:
        """创建Gradio界面"""
        with gr.Blocks(title=self.title, theme=gr.themes.Soft()) as app:
            # 标题
            gr.Markdown(f"# {self.title}")
            gr.Markdown(f"{self.description}")
            
            with gr.Row():
                # 左侧配置面板
                with gr.Column(scale=1):
                    # LLM配置
                    with gr.Accordion("🤖 LLM配置", open=True):
                        llm_provider = gr.Dropdown(
                            choices=["openai", "anthropic", "doubao"],
                            value="doubao",
                            label="LLM提供商"
                        )
                        model_name = gr.Textbox(
                            value="ep-20250221154410-vh78x",
                            label="模型名称"
                        )
                        api_key = gr.Textbox(
                            type="password",
                            label="API密钥",
                            placeholder="输入API密钥"
                        )
                        temperature = gr.Slider(
                            minimum=0,
                            maximum=1,
                            value=0.7,
                            step=0.1,
                            label="Temperature"
                        )
                    
                    # Agent选择
                    with gr.Accordion("🎯 Agent选择", open=True):
                        agent_type = gr.Dropdown(
                            choices=[
                                ("ReAct", "react"),
                                ("思维链", "chain_of_thought"),
                                ("计划执行", "plan_execute")
                            ],
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
                    
                    # MCP服务器选择
                    with gr.Accordion("🔌 MCP服务器", open=True):
                        mcp_servers_status = gr.HTML(
                            value="<p>正在加载MCP服务器信息...</p>",
                            label="MCP服务器状态"
                        )
                        enabled_mcp_servers = gr.CheckboxGroup(
                            choices=[],
                            value=[],
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
                    
                    # 应用配置按钮
                    apply_config_btn = gr.Button("应用配置", variant="primary")
                    config_status = gr.Textbox(label="配置状态", interactive=False)
                
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
            
            # 事件处理
            apply_config_btn.click(
                self._apply_config,
                inputs=[
                    llm_provider, model_name, api_key, temperature,
                    agent_type, max_iterations, available_tools, enabled_mcp_servers
                ],
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
            
            # 页面加载时自动刷新MCP服务器状态
            app.load(
                self._refresh_mcp_servers,
                outputs=[mcp_servers_status, enabled_mcp_servers]
            )
            
            msg_input.submit(
                self._chat,
                inputs=[msg_input, chatbot],
                outputs=[msg_input, chatbot, execution_trace, metrics_display, node_status, flow_diagram]
            )
            
            send_btn.click(
                self._chat,
                inputs=[msg_input, chatbot],
                outputs=[msg_input, chatbot, execution_trace, metrics_display, node_status, flow_diagram]
            )
            
            batch_btn.click(
                self._batch_execute,
                inputs=[batch_input, batch_parallel],
                outputs=[batch_results]
            )
            
            # 添加自定义CSS
            app.css = """
            .chat-window {
                border-radius: 10px;
                border: 1px solid #e0e0e0;
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
            """
            
        return app
    
    async def _apply_config(self,
                           llm_provider, model_name, api_key, temperature,
                           agent_type, max_iterations, available_tools, enabled_mcp_servers):
        """应用配置"""
        try:
            # 创建LLM配置
            llm_config = LLMConfig(
                provider=llm_provider,
                model_name=model_name,
                api_key=api_key,
                temperature=temperature
            )
            
            # 创建LLM实例
            self.llm = LLMFactory.create(llm_config)
            await self.llm.initialize()
            
            # 创建工具管理器，传入启用的MCP服务器
            self.tool_manager = MCPToolManager(enabled_servers=enabled_mcp_servers)
            await self.tool_manager.initialize()
            
            # 启用选中的传统工具
            for tool in available_tools:
                await self.tool_manager.enable_tool(tool)
            
            # 创建Agent
            if agent_type == "react":
                self.current_agent = ReactAgent(
                    llm=self.llm,
                    tool_manager=self.tool_manager,
                    max_iterations=max_iterations
                )
            else:
                return "❌ 暂不支持该Agent类型"
            
            total_tools = len(available_tools) + len(enabled_mcp_servers)
            return f"✅ 配置成功！使用 {llm_provider}/{model_name}，启用 {total_tools} 个工具（{len(available_tools)} 个传统工具 + {len(enabled_mcp_servers)} 个MCP服务器）"
            
        except Exception as e:
            return f"❌ 配置失败: {str(e)}"
    
    async def _refresh_mcp_servers(self):
        """刷新MCP服务器状态"""
        try:
            from tools.mcp_manager import mcp_manager
            
            servers = mcp_manager.list_servers()
            
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
                    
                    if server['tools']:
                        status_html += f"<small>工具: {', '.join(server['tools'][:3])}"
                        if len(server['tools']) > 3:
                            status_html += f" (+{len(server['tools'])-3} 个更多)"
                        status_html += "</small><br/>"
                    
                    status_html += f"<small>{server['description']}</small>"
                    status_html += "</div>"
            
            status_html += "</div>"
            
            # 生成可选择的服务器列表
            choices = [(f"{server['name']} ({server['id']})", server['id']) for server in servers]
            
            return status_html, choices
            
        except Exception as e:
            error_html = f"<div style='color: red;'>❌ 刷新MCP服务器失败: {str(e)}</div>"
            return error_html, []
    
    async def _add_remote_server(self, name: str, url: str):
        """添加远程MCP服务器"""
        try:
            if not name or not url:
                return name, url, "<div style='color: red;'>❌ 请填写服务器名称和URL</div>", []
            
            from tools.mcp_manager import mcp_manager
            
            # 生成服务器ID
            server_id = f"remote_{name.lower().replace(' ', '_')}"
            
            # 添加远程服务器
            mcp_manager.add_remote_server(server_id, name, url, f"远程服务器: {name}")
            
            # 刷新状态
            status_html, checkbox_update = await self._refresh_mcp_servers()
            
            success_html = f"<div style='color: green;'>✅ 成功添加远程服务器: {name}</div>"
            
            # 清空输入框
            return "", "", success_html, checkbox_update
            
        except Exception as e:
            error_html = f"<div style='color: red;'>❌ 添加远程服务器失败: {str(e)}</div>"
            return name, url, error_html, []
    
    async def _chat(self, message: str, history: List[Dict[str, str]]):
        """处理聊天消息"""
        if not self.current_agent:
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": "请先配置Agent！"})
            return "", history, {}, "", [], ""
        
        # 添加用户消息
        history.append({"role": "user", "content": message})
        
        try:
            # 运行Agent
            result = await self.current_agent.run(message)
            
            # 添加助手回复
            assistant_reply = result.result or "抱歉，无法生成回复。"
            history.append({"role": "assistant", "content": assistant_reply})
            
            # 提取执行轨迹和指标
            trace = result.execution_trace
            metrics_text = self._format_metrics(result.metrics)
            
            # 生成节点状态表
            node_status = self._generate_node_status(trace)
            
            # 生成流程图
            flow_diagram = self._generate_flow_diagram(trace)
            
            return "", history, trace, metrics_text, node_status, flow_diagram
            
        except Exception as e:
            history.append({"role": "assistant", "content": f"错误: {str(e)}"})
            return "", history, {}, "", [], ""
    
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
    
    def _format_metrics(self, metrics: Dict[str, Any]) -> str:
        """格式化指标显示"""
        if not metrics:
            return "无指标数据"
        
        lines = []
        for key, value in metrics.items():
            # 转换键名为更友好的显示
            display_key = key.replace('_', ' ').title()
            lines.append(f"{display_key}: {value}")
        
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
    
    def launch(self, **kwargs):
        """启动应用"""
        app = self.create_interface()
        app.launch(**kwargs) 