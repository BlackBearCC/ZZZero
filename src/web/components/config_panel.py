"""
配置面板组件 - 包含所有配置相关的UI组件
"""
import gradio as gr
from typing import Dict, Any, List, Tuple, Optional


class ConfigPanel:
    """配置面板组件"""
    
    def __init__(self):
        self.components = {}
    
    def create_llm_config(self) -> Dict[str, Any]:
        """创建LLM配置组件"""
        with gr.Accordion("🧠 LLM配置", open=False):
            llm_provider = gr.Dropdown(
                choices=["doubao", "openai"],
                value="doubao",
                label="LLM提供商"
            )
            model_name = gr.Textbox(
                value="ep-20250221154410-vh78x",
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
        
        return {
            "llm_provider": llm_provider,
            "model_name": model_name,
            "temperature": temperature
        }
    
    def create_agent_config(self) -> Dict[str, Any]:
        """创建Agent配置组件"""
        with gr.Accordion("🤖 Agent配置", open=False):
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
        
        return {
            "agent_type": agent_type,
            "max_iterations": max_iterations
        }
    
    def create_mcp_server_config(self) -> Dict[str, Any]:
        """创建MCP服务器配置组件"""
        with gr.Accordion("🔌 MCP服务器管理", open=False):
            # 服务器状态显示
            mcp_servers_status = gr.HTML(
                value="<p>正在加载MCP服务器信息...</p>",
                label="MCP服务器状态"
            )
            
            # 启用的服务器选择
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
            
            # 远程服务器状态显示
            remote_server_status = gr.HTML(
                value="",
                label="远程服务器操作状态"
            )
            
            refresh_mcp_btn = gr.Button("刷新MCP服务器", variant="secondary")
        
        return {
            "mcp_servers_status": mcp_servers_status,
            "enabled_mcp_servers": enabled_mcp_servers,
            "remote_server_name": remote_server_name,
            "remote_server_url": remote_server_url,
            "add_remote_btn": add_remote_btn,
            "remote_server_status": remote_server_status,
            "refresh_mcp_btn": refresh_mcp_btn
        }
    
    def create_tools_config(self) -> Dict[str, Any]:
        """创建传统工具配置组件"""
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
        
        return {"available_tools": available_tools}
    
    def create_role_info_section(self) -> None:
        """创建角色信息管理说明"""
        with gr.Accordion("🎭 角色信息管理", open=False):
            gr.Markdown("""
            **角色信息现已通过MCP工具管理：**
            
            - **角色人设**: 使用 `role_info_create_profile` 创建角色，`role_info_query_profile` 查询角色
            - **角色知识库**: 使用 `role_info_add_knowledge` 添加知识，`role_info_search_knowledge` 搜索知识
            - **世界书**: 使用 `role_info_add_world_entry` 添加世界设定，`role_info_search_world` 搜索世界设定
            - **完整上下文**: 使用 `role_info_get_role_context` 获取包含人设、知识库和世界书的完整角色上下文
            
            **优势：**
            - ✅ 支持向量数据库搜索，更智能的相关性匹配
            - ✅ 完整的CRUD操作（增删查改）
            - ✅ 数据持久化存储，重启后自动恢复
            - ✅ 分类管理：人设、知识库、世界书独立管理
            - ✅ 可以通过Agent直接调用，无需手动配置
            
            **使用方法：** 在对话中直接告诉Agent创建/查询角色信息即可
            """)
    
    def create_memory_config(self) -> Dict[str, Any]:
        """创建记忆管理组件"""
        with gr.Accordion("🧠 记忆管理", open=False):
            memory_status = gr.HTML(
                value="<p>正在加载记忆状态...</p>",
                label="记忆状态"
            )
            
            with gr.Row():
                refresh_memory_btn = gr.Button("刷新记忆状态", variant="secondary", scale=1)
                clear_memory_btn = gr.Button("清空会话记忆", variant="stop", scale=1)
                export_memory_btn = gr.Button("导出记忆数据", variant="secondary", scale=1)
            
            memory_export_display = gr.JSON(
                label="记忆导出数据",
                visible=False
            )
        
        return {
            "memory_status": memory_status,
            "refresh_memory_btn": refresh_memory_btn,
            "clear_memory_btn": clear_memory_btn,
            "export_memory_btn": export_memory_btn,
            "memory_export_display": memory_export_display
        }
    
    def create_file_management(self) -> Dict[str, Any]:
        """创建文件管理组件"""
        with gr.Accordion("📁 文件管理", open=False):
            # 文件上传
            with gr.Tab("上传文件"):
                file_upload = gr.File(
                    label="上传文件到输入目录",
                    file_count="multiple",
                    file_types=None
                )
                upload_btn = gr.Button("上传文件", variant="primary")
                upload_status = gr.HTML()
            
            # 文件浏览
            with gr.Tab("文件浏览"):
                refresh_files_btn = gr.Button("刷新文件列表", variant="secondary")
                
                input_files_display = gr.HTML(
                    value="<p>正在加载输入文件...</p>",
                    label="输入文件夹"
                )
                
                output_files_display = gr.HTML(
                    value="<p>正在加载输出文件...</p>", 
                    label="输出文件夹"
                )
        
        return {
            "file_upload": file_upload,
            "upload_btn": upload_btn,
            "upload_status": upload_status,
            "refresh_files_btn": refresh_files_btn,
            "input_files_display": input_files_display,
            "output_files_display": output_files_display
        }
    
    def create_config_status(self) -> gr.Textbox:
        """创建配置状态显示"""
        return gr.Textbox(
            label="配置状态", 
            interactive=False, 
            value="✅ 配置已自动应用"
        )
    

    
    def create_full_panel(self) -> Dict[str, Any]:
        """创建完整的配置面板"""
        gr.Markdown("## ⚙️ 配置面板")
        
        # 创建各个配置组件
        llm_components = self.create_llm_config()
        agent_components = self.create_agent_config()
        mcp_components = self.create_mcp_server_config()
        tools_components = self.create_tools_config()
        self.create_role_info_section()
        memory_components = self.create_memory_config()
        file_components = self.create_file_management()
        config_status = self.create_config_status()
        
        # 合并所有组件
        all_components = {}
        all_components.update(llm_components)
        all_components.update(agent_components)
        all_components.update(mcp_components)
        all_components.update(tools_components)
        all_components.update(memory_components)
        all_components.update(file_components)
        all_components["config_status"] = config_status
        
        self.components = all_components
        return all_components 