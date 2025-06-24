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
from core.plugins import get_role_plugin_manager 

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
        # 角色插件管理器
        self.role_plugin_manager = get_role_plugin_manager()
        # 保存当前配置
        self.current_config = {
            'llm_provider': 'doubao',
            'model_name': 'ep-20250221154410-vh78x',
            'temperature': 0.7,
            'agent_type': 'react',
            'max_iterations': 5,
            'available_tools': [],
            'enabled_mcp_servers': ['csv', 'chromadb', 'python', 'roleplay'],
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
        
        # 创建工作空间目录
        self._ensure_workspace_dirs()
        
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
            enabled_servers = self.current_config.get('enabled_mcp_servers', ['csv', 'chromadb', 'python', 'roleplay'])  # 默认启用
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
                session_id=session_id  # 会话ID
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
    
    def _ensure_workspace_dirs(self):
        """确保工作空间目录存在"""
        import os
        for dir_path in self.workspace_config.values():
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"创建工作空间目录: {dir_path}")
    
    def _list_files_in_dir(self, dir_path: str) -> List[Dict[str, Any]]:
        """列出目录中的文件"""
        import os
        from pathlib import Path
        
        files = []
        if os.path.exists(dir_path):
            for item in Path(dir_path).iterdir():
                if item.is_file():
                    stat = item.stat()
                    files.append({
                        'name': item.name,
                        'path': str(item),
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                        'type': item.suffix.lower()
                    })
        return sorted(files, key=lambda x: x['modified'], reverse=True)
    
    def _format_file_list_html(self, files: List[Dict], title: str) -> str:
        """格式化文件列表为HTML"""
        if not files:
            return f"<div style='padding: 10px; color: #666;'>{title}: 暂无文件</div>"
        
        html = f"<div style='margin-bottom: 10px;'><strong>{title} ({len(files)} 个文件)</strong></div>"
        html += "<div style='max-height: 200px; overflow-y: auto; border: 1px solid #ddd; border-radius: 4px;'>"
        
        for file in files:
            size_str = self._format_file_size(file['size'])
            html += f"""
            <div style='padding: 8px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between;'>
                <div>
                    <strong>{file['name']}</strong>
                    <div style='font-size: 0.8em; color: #666;'>{file['modified']}</div>
                </div>
                <div style='text-align: right; color: #888;'>{size_str}</div>
            </div>
            """
        html += "</div>"
        return html
    
    def _format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
    

            
    def create_interface(self) -> gr.Blocks:
        """创建Gradio界面"""
        with gr.Blocks(title=self.title, theme=gr.themes.Soft(), head="""
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/python.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/json.min.js"></script>
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                // 初始化highlight.js
                hljs.highlightAll();
                
                // 监听DOM变化以高亮新添加的代码块
                const observer = new MutationObserver(function(mutations) {
                    mutations.forEach(function(mutation) {
                        mutation.addedNodes.forEach(function(node) {
                            if (node.nodeType === 1) {
                                // 查找新添加的代码块
                                const codeBlocks = node.querySelectorAll('pre code, code');
                                codeBlocks.forEach(function(block) {
                                    if (!block.classList.contains('hljs')) {
                                        hljs.highlightElement(block);
                                    }
                                });
                            }
                        });
                    });
                });
                
                observer.observe(document.body, {
                    childList: true,
                    subtree: true
                });
            });
        </script>
        """) as app:
            # 标题
            gr.Markdown(f"# {self.title}")
            gr.Markdown(f"{self.description}")
            
            with gr.Row():
                # 左侧配置面板
                with gr.Column(scale=1):
                    gr.Markdown("## ⚙️ 配置面板")
                    
                    # LLM配置
                    with gr.Accordion("🧠 LLM配置", open=False):
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
                    
                    # MCP服务器管理
                    with gr.Accordion("🔌 MCP服务器管理", open=False):
                        # 服务器状态和勾选在一起
                        mcp_servers_status = gr.HTML(
                            value="<p>正在加载MCP服务器信息...</p>",
                            label="MCP服务器状态"
                        )
                        
                        # 获取初始的servers列表并设置默认值
                        initial_choices = []
                        default_enabled = []
                        try:
                            if self.tool_manager:
                                servers_status = self.tool_manager.get_servers_status()
                                for server_id, server_info in servers_status.items():
                                    choice = (f"{server_info['name']} ({server_id})", server_id)
                                    initial_choices.append(choice)
                                    # 默认勾选已注册的服务器
                                    if server_id in ['csv', 'chromadb', 'python', 'roleplay']:
                                        default_enabled.append(server_id)
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
                    
                    # 角色插件配置
                    with gr.Accordion("🎭 角色插件配置", open=False):
                        role_plugin_status = gr.HTML(
                            value="<p>正在加载角色插件状态...</p>",
                            label="角色插件状态"
                        )
                        
                        # 角色资料配置
                        with gr.Group():
                            gr.Markdown("### 📝 角色资料配置")
                            
                            with gr.Row():
                                role_profile_enabled = gr.Checkbox(
                                    label="启用角色资料插件",
                                    value=False
                                )
                                clear_profile_btn = gr.Button("清空角色资料", variant="secondary", scale=1)
                            
                            role_profile_name = gr.Textbox(
                                label="角色名称",
                                placeholder="例如：艾莉丝",
                                value=""
                            )
                            
                            # 支持文本输入和文件上传
                            with gr.Tab("文本输入"):
                                role_profile_content = gr.Textbox(
                                    label="角色资料内容",
                                    placeholder="详细描述角色的性格、背景、特点等...",
                                    lines=6,
                                    value=""
                                )
                            
                            with gr.Tab("文件上传"):
                                gr.Markdown("""
                                **📁 文件上传说明：**
                                - 支持txt格式的角色资料文件
                                - 文件大小限制：5MB以内
                                - 支持编码：UTF-8、GBK、GB2312等
                                - 加载后内容会显示在"文本输入"标签页中，可继续编辑
                                """)
                                
                                role_profile_file = gr.File(
                                    label="选择角色资料文件（txt格式）",
                                    file_types=[".txt"],
                                    file_count="single"
                                )
                                
                                # 处理状态显示
                                profile_processing_status = gr.HTML(
                                    value="",
                                    label="处理状态",
                                    visible=False
                                )
                                
                                with gr.Row():
                                    load_profile_btn = gr.Button("📥 从文件加载角色资料", variant="primary")
                                    gr.HTML('<small style="color: #666; margin-left: 10px;">加载后请切换到"文本输入"标签页查看和编辑</small>')
                            
                            role_profile_tags = gr.Textbox(
                                label="角色标签（用逗号分隔）",
                                placeholder="例如：温柔,聪明,艺术家",
                                value=""
                            )
                        
                        # 角色知识库配置
                        with gr.Group():
                            gr.Markdown("### 📚 角色知识库配置")
                            
                            with gr.Row():
                                role_kb_enabled = gr.Checkbox(
                                    label="启用角色知识库插件",
                                    value=False
                                )
                                clear_kb_btn = gr.Button("清空知识库配置", variant="secondary", scale=1)
                            
                            role_kb_name = gr.Textbox(
                                label="知识库名称",
                                placeholder="例如：艾莉丝专属知识库",
                                value=""
                            )
                            
                            role_kb_file = gr.File(
                                label="上传知识库文件（txt或csv格式）",
                                file_types=[".txt", ".csv"],
                                file_count="single"
                            )
                            
                            # 处理进度显示
                            kb_processing_status = gr.HTML(
                                value="",
                                label="处理状态",
                                visible=False
                            )
                            
                            role_kb_description = gr.Textbox(
                                label="知识库描述",
                                placeholder="描述知识库的内容和用途...",
                                lines=2,
                                value=""
                            )
                            
                            role_kb_search_limit = gr.Slider(
                                minimum=1,
                                maximum=10,
                                value=3,
                                step=1,
                                label="搜索结果数量限制"
                            )
                        
                        # 操作按钮
                        with gr.Row():
                            save_role_config_btn = gr.Button("保存角色插件配置", variant="primary", scale=2)
                            refresh_role_status_btn = gr.Button("刷新状态", variant="secondary", scale=1)
                            show_kb_contents_btn = gr.Button("显示库内容", variant="secondary", scale=1)
                        
                        # 知识库内容显示区域
                        kb_contents_display = gr.HTML(
                            value="<div style='color: gray;'>点击'显示库内容'查看知识库中的文档片段</div>",
                            label="知识库内容",
                            visible=False
                        )
                        
                        # 配置说明
                        gr.Markdown("""
                        **角色插件说明：**
                        - **角色资料**：可直接输入文本或上传txt文件，自动填入prompt
                        - **角色知识库**：上传txt或csv文件，系统自动处理成可搜索的知识库
                        - 目前只有角色扮演数据生成工具可以使用这些插件
                        - 启用插件后，工具调用时会自动注入角色信息，无需手动输入
                        - 配置会自动保存到本地，重启后自动恢复
                        """)
                    
                    # 记忆管理
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
                    
                    # 文件管理
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
                    
                    # 配置状态（只显示，不需要应用按钮）
                    config_status = gr.Textbox(label="配置状态", interactive=False, value="✅ 配置已自动应用")
                
                # 右侧聊天界面
                with gr.Column(scale=3):
                    # 聊天历史
                    chatbot = gr.Chatbot(
                        height=800,
                        show_label=False,
                        elem_classes=["chat-window"],
                        type="messages",
                        render_markdown=True,
                        sanitize_html=False  # 允许HTML渲染以支持高亮
                    )
                    
                    # 动态表格显示区域
                    dynamic_table = gr.DataFrame(
                        value=[],
                        headers=None,
                        label="📊 表格数据",
                        interactive=False,
                        wrap=True,
                        visible=False  # 默认隐藏
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
                    
                    # 批处理配置
                    with gr.Accordion("📊 批处理配置", open=False):
                        with gr.Row():
                            batch_enabled = gr.Checkbox(
                                label="启用批处理模式",
                                value=False
                            )
                            processing_mode = gr.Dropdown(
                                choices=[
                                    ("并行模式 - 快速高效", "parallel"),
                                    ("遍历模式 - 顺序执行", "sequential")
                                ],
                                value="parallel",
                                label="处理模式",
                                info="并行模式：同时执行多个任务，速度快；遍历模式：逐个执行，可实时查看每个任务进度"
                            )
                        
                        with gr.Row():
                            csv_file_upload = gr.File(
                                label="上传CSV文件",
                                file_types=[".csv"],
                                file_count="single"
                            )
                        
                        # CSV字段选择区域
                        csv_fields_section = gr.Column(visible=False)
                        with csv_fields_section:
                            gr.Markdown("### 📋 CSV字段选择")
                            csv_info_display = gr.HTML(
                                value="<div>等待CSV文件解析...</div>",
                                label="CSV文件信息"
                            )
                            
                            # 数据预览表格
                            csv_preview_table = gr.DataFrame(
                                value=[],
                                headers=None,
                                label="📊 数据预览（前5行）",
                                interactive=False,
                                wrap=True
                            )
                            
                            csv_fields_selection = gr.CheckboxGroup(
                                choices=[],
                                value=[],
                                label="选择要在批处理中使用的字段（勾选需要的字段）",
                                interactive=True
                            )
                            
                            fields_update_btn = gr.Button("更新字段选择", variant="secondary")
                        
                        with gr.Row():
                            batch_size = gr.Slider(
                                minimum=1,
                                maximum=50,
                                value=5,
                                step=1,
                                label="每批处理行数"
                            )
                            concurrent_tasks = gr.Slider(
                                minimum=1,
                                maximum=50,
                                value=10,
                                step=1,
                                label="并发任务数"
                            )
                        
                        batch_status = gr.HTML(
                            value="<div style='color: #666;'>📋 批处理模式未启用</div>",
                            label="批处理状态"
                        )
                        
                        # CSV格式说明
                        gr.Markdown("""
                        **CSV格式说明：**
                        - 支持多种编码格式（UTF-8、GBK、GB2312等）
                        - 必须包含列头行
                        - 上传后可选择使用的字段
                        - 示例：character_name,description,duration_days,special_requirements
                        
                        **处理模式说明：**
                        - **并行模式**：同时执行多个任务，速度快，适合独立任务
                        - **遍历模式**：逐个执行任务，可实时查看每个任务进度，适合依赖性任务
                        """, visible=True)
                    
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
            
            # === 批处理配置处理 ===
            async def on_batch_config_change(enabled, csv_file, batch_size_val, concurrent_tasks_val, processing_mode_val):
                """批处理配置变化处理"""
                try:
                    # 更新配置
                    self.current_config['batch_enabled'] = enabled
                    self.current_config['batch_size'] = batch_size_val
                    self.current_config['concurrent_tasks'] = concurrent_tasks_val
                    self.current_config['processing_mode'] = processing_mode_val
                    
                    if not self.batch_processor:
                        return ("<div style='color: red;'>❌ 批处理器未初始化</div>", 
                                gr.update(visible=False), 
                                "<div>批处理器未初始化</div>", 
                                gr.update(value=[], headers=None),
                                gr.update(choices=[], value=[]))
                    
                    if enabled and csv_file:
                        # 保存CSV文件路径
                        csv_path = csv_file.name if csv_file else None
                        self.current_config['batch_csv_path'] = csv_path
                        
                        # 配置批处理模式
                        result = self.batch_processor.configure_batch_mode(
                            enabled=True,
                            csv_file_path=csv_path,
                            batch_size=batch_size_val,
                            concurrent_tasks=concurrent_tasks_val,
                            processing_mode=processing_mode_val
                        )
                        
                        if result['success']:
                            csv_structure = result.get('csv_structure', {})
                            columns = csv_structure.get('columns', [])
                            column_types = csv_structure.get('column_types', {})
                            sample_data = csv_structure.get('sample_data', {})
                            
                            # 生成CSV信息HTML
                            csv_info_html = f"""
                            <div style='font-family: monospace; padding: 10px; border: 1px solid #ddd; border-radius: 4px; background-color: #f9f9f9;'>
                                <h4>📊 CSV文件解析成功</h4>
                                <p><strong>文件:</strong> {csv_path.split('/')[-1] if csv_path else 'unknown'}</p>
                                <p><strong>编码:</strong> {csv_structure.get('detected_encoding', 'unknown')}</p>
                                <p><strong>行数:</strong> {result.get('csv_rows', 0)}</p>
                                <p><strong>列数:</strong> {len(columns)}</p>
                                <p><strong>💡 提示:</strong> 请查看下方的数据预览表格，了解每个字段的内容，然后选择需要在批处理中使用的字段。</p>
                            </div>
                            """
                            
                            # 生成数据预览表格
                            preview_data = []
                            max_preview_rows = min(5, len(self.batch_processor.csv_data) if self.batch_processor else 0)
                            
                            if self.batch_processor and self.batch_processor.csv_data:
                                for i in range(max_preview_rows):
                                    row_data = []
                                    for col in columns:
                                        cell_value = self.batch_processor.csv_data[i].get(col, '')
                                        # 限制单元格内容长度，避免界面过宽
                                        if isinstance(cell_value, str) and len(cell_value) > 50:
                                            cell_value = cell_value[:47] + "..."
                                        row_data.append(str(cell_value))
                                    preview_data.append(row_data)
                            
                            # 生成字段选择选项（显示列名、类型和示例数据）
                            field_choices = []
                            default_selected = []
                            for col in columns:
                                col_type = column_types.get(col, 'unknown')
                                choice_label = f"{col} ({col_type})"
                                field_choices.append((choice_label, col))
                                default_selected.append(col)  # 默认全选
                            
                            status_html = f"""
                            <div style='color: green; padding: 10px; border: 1px solid #4CAF50; border-radius: 4px; background-color: #f1f8e9;'>
                                ✅ <strong>CSV文件解析成功</strong><br/>
                                📄 文件: {csv_path.split('/')[-1] if csv_path else 'unknown'}<br/>
                                📊 数据行数: {result.get('csv_rows', 0)}<br/>
                                🔤 编码: {csv_structure.get('detected_encoding', 'unknown')}<br/>
                                📋 字段数: {len(columns)}<br/>
                                ⚙️ 请查看数据预览，选择需要的字段，然后点击"更新字段选择"
                            </div>
                            """
                            
                            return (status_html, 
                                    gr.update(visible=True), 
                                    csv_info_html, 
                                    gr.update(value=preview_data, headers=columns),
                                    gr.update(choices=field_choices, value=default_selected))
                        else:
                            status_html = f"""
                            <div style='color: red; padding: 10px; border: 1px solid #f44336; border-radius: 4px; background-color: #ffebee;'>
                                ❌ <strong>批处理模式启用失败</strong><br/>
                                {result.get('message', '未知错误')}
                            </div>
                            """
                            
                            return (status_html, 
                                    gr.update(visible=False), 
                                    "<div>CSV解析失败</div>", 
                                    gr.update(value=[], headers=None),
                                    gr.update(choices=[], value=[]))
                            
                    elif enabled and not csv_file:
                        status_html = """
                        <div style='color: orange; padding: 10px; border: 1px solid #ff9800; border-radius: 4px; background-color: #fff3e0;'>
                            ⚠️ <strong>请上传CSV文件以启用批处理模式</strong>
                        </div>
                        """
                        
                        return (status_html, 
                                gr.update(visible=False), 
                                "<div>等待CSV文件...</div>", 
                                gr.update(value=[], headers=None),
                                gr.update(choices=[], value=[]))
                    else:
                        # 关闭批处理模式
                        self.current_config['batch_csv_path'] = None
                        result = self.batch_processor.configure_batch_mode(
                            enabled=False,
                            processing_mode=processing_mode_val
                        )
                        
                        status_html = """
                        <div style='color: #666; padding: 10px; border: 1px solid #ccc; border-radius: 4px; background-color: #f9f9f9;'>
                            📋 批处理模式已关闭
                        </div>
                        """
                        
                        return (status_html, 
                                gr.update(visible=False), 
                                "<div>批处理模式已关闭</div>", 
                                gr.update(value=[], headers=None),
                                gr.update(choices=[], value=[]))
                    
                except Exception as e:
                    error_html = f"""
                    <div style='color: red; padding: 10px; border: 1px solid #f44336; border-radius: 4px; background-color: #ffebee;'>
                        ❌ <strong>批处理配置失败</strong><br/>
                        {str(e)}
                    </div>
                    """
                    return (error_html, 
                            gr.update(visible=False), 
                            f"<div>错误: {str(e)}</div>", 
                            gr.update(value=[], headers=None),
                            gr.update(choices=[], value=[]))
            
            async def on_fields_update(selected_fields):
                """更新字段选择"""
                try:
                    if not self.batch_processor:
                        return "<div style='color: red;'>❌ 批处理器未初始化</div>"
                    
                    if not selected_fields:
                        return """
                        <div style='color: orange; padding: 10px; border: 1px solid #ff9800; border-radius: 4px; background-color: #fff3e0;'>
                            ⚠️ 请至少选择一个字段
                        </div>
                        """
                    
                    # 构建字段选择映射
                    all_fields = self.batch_processor.csv_structure.get('columns', [])
                    field_selection = {field: field in selected_fields for field in all_fields}
                    
                    # 更新字段选择
                    result = self.batch_processor.update_field_selection(field_selection)
                    
                    if result['success']:
                        # 最终启用批处理模式
                        final_result = self.batch_processor.configure_batch_mode(
                            enabled=True,
                            csv_file_path=self.current_config['batch_csv_path'],
                            batch_size=self.current_config['batch_size'],
                            concurrent_tasks=self.current_config['concurrent_tasks'],
                            processing_mode=self.current_config.get('processing_mode', 'parallel')
                        )
                        
                        return f"""
                        <div style='color: green; padding: 10px; border: 1px solid #4CAF50; border-radius: 4px; background-color: #f1f8e9;'>
                            ✅ <strong>批处理模式已完全启用</strong><br/>
                            📋 已选择字段: {', '.join(selected_fields)}<br/>
                            📊 数据行数: {len(self.batch_processor.csv_data)}<br/>
                                                            ⚙️ 每批处理: {self.current_config['batch_size']} 行<br/>
                                🔄 并发数: {self.current_config['concurrent_tasks']}<br/>
                                🚀 处理模式: {'并行模式' if self.current_config['processing_mode'] == 'parallel' else '遍历模式'}<br/>
                                💡 现在可以在聊天框中发送批处理请求了！
                        </div>
                        """
                    else:
                        return f"""
                        <div style='color: red; padding: 10px; border: 1px solid #f44336; border-radius: 4px; background-color: #ffebee;'>
                            ❌ <strong>字段选择更新失败</strong><br/>
                            {result.get('message', '未知错误')}
                        </div>
                        """
                        
                except Exception as e:
                    return f"""
                    <div style='color: red; padding: 10px; border: 1px solid #f44336; border-radius: 4px; background-color: #ffebee;'>
                        ❌ <strong>字段选择更新失败</strong><br/>
                        {str(e)}
                    </div>
                    """
            
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
            
            # 绑定批处理配置变化事件
            for component in [batch_enabled, csv_file_upload, batch_size, concurrent_tasks, processing_mode]:
                component.change(
                    on_batch_config_change,
                    inputs=[batch_enabled, csv_file_upload, batch_size, concurrent_tasks, processing_mode],
                    outputs=[batch_status, csv_fields_section, csv_info_display, csv_preview_table, csv_fields_selection]
                )
            
            # 绑定字段选择更新事件
            fields_update_btn.click(
                on_fields_update,
                inputs=[csv_fields_selection],
                outputs=[batch_status]
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
                        if info.get('enabled', False) or server_id in ['csv', 'chromadb', 'python', 'roleplay']:
                            default_enabled.append(server_id)
                    
                    # 返回状态HTML和更新后的CheckboxGroup，以及演示消息
                    import gradio as gr
                    demo_messages = [
                        {
                            "role": "assistant", 
                            "content": """🎉 欢迎使用 ZZZero AI Agent！

**样式演示**：

<span class="agent-keyword-question">Question:</span> 这是一个问题示例
<span class="agent-keyword-thought">Thought:</span> 这是思考过程
<span class="agent-keyword-action">Action:</span> 这是执行的动作
<span class="agent-keyword-action-input">Action Input:</span> 这是动作输入
<span class="agent-keyword-observation">Observation:</span> 这是观察结果
<span class="agent-keyword-final-answer">Final Answer:</span> 这是最终答案

**代码块示例**：

```python
def hello_world():
    print("Hello, World!")
    return {"status": "success"}
```

```json
{
  "name": "ZZZero Agent",
  "version": "1.0.0",
  "features": ["markdown", "syntax_highlighting", "keyword_highlighting"]
}
```

内联代码：`print("Hello")`

现在可以开始对话了！"""
                        }
                    ]
                    
                    # 获取初始记忆状态
                    memory_status_html = await self._refresh_memory_status()
                    
                    # 获取角色插件状态
                    role_plugin_status_html = await self._refresh_role_plugin_status()
                    
                    # 加载角色插件当前配置
                    role_config = self._load_role_plugin_current_config()
                    
                    return (
                        status_html,
                        gr.update(choices=choices, value=default_enabled),
                        demo_messages,
                        gr.update(value=[], headers=None, visible=False),  # 初始隐藏表格
                        memory_status_html,  # 记忆状态
                        role_plugin_status_html,  # 角色插件状态
                        *role_config  # 角色插件配置字段
                    )
                    
                except Exception as e:
                    error_msg = f"页面加载初始化失败: {e}"
                    logger.error(error_msg)
                    import gradio as gr
                    return (
                        f"❌ 初始化失败: {str(e)}",
                        gr.update(choices=[], value=[]),
                        [],
                        gr.update(value=[], headers=None, visible=False),
                        "<div style='color: red;'>❌ 记忆状态获取失败</div>",
                        "<div style='color: red;'>❌ 角色插件状态获取失败</div>",
                        False, "", "", "", False, "", "", 3  # 角色插件配置默认值
                    )
            
            app.load(
                on_load,
                outputs=[
                    mcp_servers_status, enabled_mcp_servers, chatbot, dynamic_table, memory_status,
                    role_plugin_status,
                    role_profile_enabled, role_profile_name, role_profile_content, role_profile_tags,
                    role_kb_enabled, role_kb_name, role_kb_description, role_kb_search_limit
                ]
            )
            
            # MCP服务器勾选变化事件
            enabled_mcp_servers.change(
                self._on_mcp_servers_change,
                inputs=[enabled_mcp_servers],
                outputs=[mcp_servers_status]
            )
            
            # 记忆管理事件
            refresh_memory_btn.click(
                self._refresh_memory_status,
                outputs=[memory_status]
            )
            
            clear_memory_btn.click(
                self._clear_memory,
                outputs=[memory_status]
            )
            
            export_memory_btn.click(
                self._export_memory,
                outputs=[memory_status, memory_export_display]
            )
            
            # 文件管理事件
            upload_btn.click(
                self._upload_files,
                inputs=[file_upload],
                outputs=[upload_status, input_files_display]
            )
            
            refresh_files_btn.click(
                self._refresh_file_lists,
                outputs=[input_files_display, output_files_display]
            )
            
            # 角色插件事件绑定
            load_profile_btn.click(
                self._load_profile_from_file,
                inputs=[role_profile_file],
                outputs=[role_profile_content]
            )
            
            # 角色资料文件上传自动处理
            role_profile_file.upload(
                self._process_profile_file_upload,
                inputs=[role_profile_name, role_profile_file, role_profile_tags],
                outputs=[profile_processing_status, role_profile_content]
            ).then(
                lambda: gr.update(visible=True),
                outputs=[profile_processing_status]
            )
            
            # 知识库文件上传自动处理
            role_kb_file.upload(
                self._process_kb_file_upload,
                inputs=[role_kb_name, role_kb_file, role_kb_description, role_kb_search_limit],
                outputs=[kb_processing_status, kb_processing_status]
            ).then(
                lambda: gr.update(visible=True),
                outputs=[kb_processing_status]
            )
            
            save_role_config_btn.click(
                self._save_role_plugin_config,
                inputs=[
                    role_profile_enabled, role_profile_name, role_profile_content, role_profile_tags,
                    role_kb_enabled, role_kb_name, role_kb_file, role_kb_description, role_kb_search_limit
                ],
                outputs=[role_plugin_status]
            )
            
            refresh_role_status_btn.click(
                self._refresh_role_plugin_status,
                outputs=[role_plugin_status]
            )
            
            clear_profile_btn.click(
                self._clear_role_profile,
                outputs=[role_plugin_status]
            )
            
            clear_kb_btn.click(
                self._clear_role_knowledge_base,
                outputs=[role_plugin_status]
            )
            
            show_kb_contents_btn.click(
                self._show_knowledge_base_contents,
                outputs=[kb_contents_display]
            ).then(
                lambda: gr.update(visible=True),
                outputs=[kb_contents_display]
            )
            

            
            # 页面加载时刷新文件列表
            app.load(
                self._refresh_file_lists,
                outputs=[input_files_display, output_files_display]
            )
            
            msg_input.submit(
                self._stream_chat,
                inputs=[msg_input, chatbot],
                outputs=[msg_input, chatbot, dynamic_table, execution_trace, metrics_display, node_status, flow_diagram],
                show_progress=False  # 禁用进度条以支持流式输出
            )
            
            send_btn.click(
                self._stream_chat,
                inputs=[msg_input, chatbot],
                outputs=[msg_input, chatbot, dynamic_table, execution_trace, metrics_display, node_status, flow_diagram],
                show_progress=False  # 禁用进度条以支持流式输出
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
            
            /* 代码块样式 - 黑色背景 */
            .chat-window pre {
                background-color: #0d1117 !important;
                color: #e6edf3 !important;
                border-radius: 8px !important;
                padding: 16px !important;
                margin: 12px 0 !important;
                border: 1px solid #30363d !important;
                overflow-x: auto !important;
                font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', 'source-code-pro', monospace !important;
                font-size: 14px !important;
                line-height: 1.5 !important;
                position: relative !important;
            }
            
            .chat-window pre code {
                background-color: transparent !important;
                color: inherit !important;
                padding: 0 !important;
                border-radius: 0 !important;
                font-family: inherit !important;
                font-size: inherit !important;
            }
            
            /* 内联代码样式 */
            .chat-window code:not(pre code) {
                background-color: #f6f8fa !important;
                color: #d73a49 !important;
                padding: 2px 4px !important;
                border-radius: 3px !important;
                font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', 'source-code-pro', monospace !important;
                font-size: 85% !important;
                border: 1px solid #e1e4e8 !important;
            }
            
            /* 确保代码块在聊天消息中正确显示 */
            .chat-window .message {
                overflow: visible !important;
            }
            
            .chat-window .message pre {
                white-space: pre !important;
                word-wrap: normal !important;
            }
            
            /* Agent关键词高亮样式 */
            .chat-window .bot .message-content {
                position: relative;
            }
            
            /* Question 样式 - 蓝色 */
            .chat-window .agent-keyword-question {
                color: #0066cc !important;
                font-weight: bold !important;
                font-size: 16px !important;
                background-color: rgba(0, 102, 204, 0.1) !important;
                padding: 2px 6px !important;
                border-radius: 4px !important;
                border-left: 4px solid #0066cc !important;
                padding-left: 8px !important;
                display: inline-block !important;
                margin: 2px 0 !important;
            }
            
            /* Thought 样式 - 绿色 */
            .chat-window .agent-keyword-thought {
                color: #22c55e !important;
                font-weight: bold !important;
                font-size: 16px !important;
                background-color: rgba(34, 197, 94, 0.1) !important;
                padding: 2px 6px !important;
                border-radius: 4px !important;
                border-left: 4px solid #22c55e !important;
                padding-left: 8px !important;
                display: inline-block !important;
                margin: 2px 0 !important;
            }
            
            /* Action 样式 - 橙色 */
            .chat-window .agent-keyword-action {
                color: #f59e0b !important;
                font-weight: bold !important;
                font-size: 16px !important;
                background-color: rgba(245, 158, 11, 0.1) !important;
                padding: 2px 6px !important;
                border-radius: 4px !important;
                border-left: 4px solid #f59e0b !important;
                padding-left: 8px !important;
                display: inline-block !important;
                margin: 2px 0 !important;
            }
            
            /* Action Input 样式 - 紫色 */
            .chat-window .agent-keyword-action-input {
                color: #8b5cf6 !important;
                font-weight: bold !important;
                font-size: 16px !important;
                background-color: rgba(139, 92, 246, 0.1) !important;
                padding: 2px 6px !important;
                border-radius: 4px !important;
                border-left: 4px solid #8b5cf6 !important;
                padding-left: 8px !important;
                display: inline-block !important;
                margin: 2px 0 !important;
            }
            
            /* Observation 样式 - 青色 */
            .chat-window .agent-keyword-observation {
                color: #06b6d4 !important;
                font-weight: bold !important;
                font-size: 16px !important;
                background-color: rgba(6, 182, 212, 0.1) !important;
                padding: 2px 6px !important;
                border-radius: 4px !important;
                border-left: 4px solid #06b6d4 !important;
                padding-left: 8px !important;
                display: inline-block !important;
                margin: 2px 0 !important;
            }
            
            /* Final Answer 样式 - 红色 */
            .chat-window .agent-keyword-final-answer {
                color: #dc2626 !important;
                font-weight: bold !important;
                font-size: 16px !important;
                background-color: rgba(220, 38, 38, 0.1) !important;
                padding: 2px 6px !important;
                border-radius: 4px !important;
                border-left: 4px solid #dc2626 !important;
                padding-left: 8px !important;
                display: inline-block !important;
                margin: 2px 0 !important;
            }
            
            /* highlight.js 深色主题适配 */
            .chat-window .hljs {
                background: #0d1117 !important;
                color: #e6edf3 !important;
            }
            
            /* 语言标签样式 */
            .chat-window pre::before {
                content: attr(data-language);
                position: absolute;
                top: 8px;
                right: 12px;
                background: rgba(255, 255, 255, 0.1);
                color: #e6edf3;
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 11px;
                text-transform: uppercase;
                font-weight: bold;
            }
            
            /* 让消息内容可以正确显示HTML */
            .chat-window .message-content {
                white-space: pre-wrap;
                word-wrap: break-word;
                line-height: 1.6 !important;
            }
            
            /* 优化消息内容的段落间距 */
            .chat-window .message p {
                margin: 0.5em 0 !important;
                line-height: 1.6 !important;
            }
            
            .chat-window .message p:first-child {
                margin-top: 0 !important;
            }
            
            .chat-window .message p:last-child {
                margin-bottom: 0 !important;
            }
            
            /* 减少空行的高度 */
            .chat-window .message br {
                line-height: 0.8 !important;
            }
            
            /* 优化列表项间距 */
            .chat-window .message ul, 
            .chat-window .message ol {
                margin: 0.5em 0 !important;
                padding-left: 1.5em !important;
            }
            
            .chat-window .message li {
                margin: 0.2em 0 !important;
                line-height: 1.5 !important;
            }
            
            /* Markdown表格样式 */
            .chat-window .markdown-table-container {
                margin: 15px 0 !important;
                padding: 10px !important;
                border-radius: 8px !important;
                background-color: #f9f9f9 !important;
                border: 1px solid #e0e0e0 !important;
                overflow-x: auto !important;
            }
            
            .chat-window .markdown-table {
                width: 100% !important;
                border-collapse: collapse !important;
                border: 1px solid #ddd !important;
                font-size: 14px !important;
                background-color: white !important;
                border-radius: 4px !important;
                overflow: hidden !important;
            }
            
            .chat-window .markdown-table th {
                background-color: #f5f5f5 !important;
                border: 1px solid #ddd !important;
                padding: 12px 8px !important;
                text-align: left !important;
                font-weight: bold !important;
                color: #333 !important;
                font-size: 13px !important;
            }
            
            .chat-window .markdown-table td {
                border: 1px solid #ddd !important;
                padding: 10px 8px !important;
                vertical-align: top !important;
                line-height: 1.4 !important;
                font-size: 13px !important;
                color: #555 !important;
            }
            
            .chat-window .markdown-table tr:nth-child(even) {
                background-color: #fafafa !important;
            }
            
            .chat-window .markdown-table tr:hover {
                background-color: #f0f8ff !important;
            }
            
            /* 表格响应式设计 */
            @media (max-width: 768px) {
                .chat-window .markdown-table-container {
                    font-size: 12px !important;
                }
                
                .chat-window .markdown-table th,
                .chat-window .markdown-table td {
                    padding: 6px 4px !important;
                    font-size: 11px !important;
                }
            }
            """
            
        return app
    
    async def _refresh_memory_status(self):
        """刷新记忆状态"""
        try:
            if not self.current_agent or not hasattr(self.current_agent, 'memory_enabled'):
                return "<div style='color: #666;'>🧠 记忆功能未启用</div>"
            
            if not self.current_agent.memory_enabled:
                return "<div style='color: #666;'>🧠 记忆功能已禁用</div>"
            
            memory_manager = self.current_agent.memory_manager
            stats = await memory_manager.get_stats()
            
            # 解析统计信息
            short_term = stats.get('short_term', {})
            long_term = stats.get('long_term', {})
            
            short_term_count = short_term.get('item_count', 0)
            short_term_chars = short_term.get('current_size', 0)
            long_term_count = long_term.get('total_memories', 0)
            compression_count = long_term.get('compressed_memories', 0)
            
            status_html = f"""
            <div style='font-family: monospace; padding: 10px; border: 1px solid #ddd; border-radius: 4px; background-color: #f0f8ff;'>
                <h4>🧠 记忆系统状态</h4>
                <p><strong>会话ID:</strong> {memory_manager.session_id}</p>
                <p><strong>短期记忆:</strong> {short_term_count} 条 ({short_term_chars} 字符)</p>
                <p><strong>长期记忆:</strong> {long_term_count} 条</p>
                <p><strong>压缩记忆:</strong> {compression_count} 条</p>
                <p><strong>状态:</strong> {'🟢 正常' if short_term_chars < 3000 else '🟡 接近压缩阈值'}</p>
            </div>
            """
            
            return status_html
            
        except Exception as e:
            return f"<div style='color: red;'>❌ 获取记忆状态失败: {str(e)}</div>"
    
    async def _clear_memory(self):
        """清空会话记忆"""
        try:
            if not self.current_agent or not hasattr(self.current_agent, 'memory_enabled'):
                return "<div style='color: #666;'>🧠 记忆功能未启用</div>"
            
            if not self.current_agent.memory_enabled:
                return "<div style='color: #666;'>🧠 记忆功能已禁用</div>"
            
            memory_manager = self.current_agent.memory_manager
            await memory_manager.clear_all()
            
            return "<div style='color: green;'>✅ 会话记忆已清空</div>"
            
        except Exception as e:
            return f"<div style='color: red;'>❌ 清空记忆失败: {str(e)}</div>"
    
    async def _export_memory(self):
        """导出记忆数据"""
        try:
            if not self.current_agent or not hasattr(self.current_agent, 'memory_enabled'):
                return "<div style='color: #666;'>🧠 记忆功能未启用</div>", {}
            
            if not self.current_agent.memory_enabled:
                return "<div style='color: #666;'>🧠 记忆功能已禁用</div>", {}
            
            memory_manager = self.current_agent.memory_manager
            memory_data = await memory_manager.export_data()
            
            # 保存到文件
            import json
            import os
            export_path = os.path.join("workspace", "memory_export.json")
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(memory_data, f, ensure_ascii=False, indent=2)
            
            status_html = f"""
            <div style='color: green; font-family: monospace;'>
                ✅ 记忆数据已导出<br/>
                <small>文件路径: {export_path}</small><br/>
                <small>数据条数: {len(memory_data.get('memories', []))}</small>
            </div>
            """
            
            import gradio as gr
            return status_html, gr.update(value=memory_data, visible=True)
            
        except Exception as e:
            return f"<div style='color: red;'>❌ 导出记忆失败: {str(e)}</div>", {}
    
    async def _refresh_role_plugin_status(self):
        """刷新角色插件状态"""
        try:
            status = self.role_plugin_manager.get_status()
            
            # 生成状态HTML
            status_html = "<div style='font-family: monospace; padding: 10px; border: 1px solid #ddd; border-radius: 4px; background-color: #f0f8ff;'>"
            status_html += "<h4>🎭 角色插件状态</h4>"
            
            # 角色资料插件状态
            profile_info = status['profile_plugin']
            profile_enabled_icon = "✅" if profile_info['enabled'] else "⚪"
            profile_available_icon = "🟢" if profile_info['available'] else "🔴"
            
            status_html += f"<div style='margin: 8px 0; padding: 8px; border: 1px solid #ddd; border-radius: 4px;'>"
            status_html += f"<strong>{profile_enabled_icon} {profile_available_icon} 角色资料插件</strong><br/>"
            status_html += f"<small>启用状态: {'已启用' if profile_info['enabled'] else '已禁用'}</small><br/>"
            status_html += f"<small>可用状态: {'可用' if profile_info['available'] else '不可用'}</small><br/>"
            
            if profile_info['info']:
                info = profile_info['info']
                status_html += f"<small>角色名称: {info['name']}</small><br/>"
                status_html += f"<small>内容长度: {info['content_length']} 字符</small><br/>"
                status_html += f"<small>标签: {', '.join(info['tags']) if info['tags'] else '无'}</small><br/>"
                status_html += f"<small>更新时间: {info['updated_at']}</small>"
            else:
                status_html += "<small>未配置角色资料</small>"
            status_html += "</div>"
            
            # 知识库插件状态
            kb_info = status['knowledge_base_plugin']
            kb_enabled_icon = "✅" if kb_info['enabled'] else "⚪"
            kb_available_icon = "🟢" if kb_info['available'] else "🔴"
            
            status_html += f"<div style='margin: 8px 0; padding: 8px; border: 1px solid #ddd; border-radius: 4px;'>"
            status_html += f"<strong>{kb_enabled_icon} {kb_available_icon} 角色知识库插件</strong><br/>"
            status_html += f"<small>启用状态: {'已启用' if kb_info['enabled'] else '已禁用'}</small><br/>"
            status_html += f"<small>可用状态: {'可用' if kb_info['available'] else '不可用'}</small><br/>"
            
            if kb_info['info']:
                info = kb_info['info']
                status_html += f"<small>知识库名称: {info['name']}</small><br/>"
                status_html += f"<small>源文件路径: {info['source_file']}</small><br/>"
                status_html += f"<small>搜索限制: {info['search_limit']} 条</small><br/>"
                status_html += f"<small>数据条数: {info['data_count']} 条</small><br/>"
                
                # 向量数据库信息
                if 'vector_count' in info:
                    status_html += f"<small>向量数量: {info['vector_count']} 个</small><br/>"
                if 'collection_name' in info:
                    status_html += f"<small>集合名称: {info['collection_name']}</small><br/>"
                if 'embedding_model' in info:
                    status_html += f"<small>Embedding模型: {info['embedding_model']}</small><br/>"
                if 'chunk_size' in info:
                    status_html += f"<small>文本块大小: {info['chunk_size']} 字</small><br/>"
                
                # 处理进度信息
                progress_info = info.get('progress', {})
                if progress_info:
                    if progress_info.get('error_message'):
                        status_html += f"<small style='color: red;'>❌ 错误: {progress_info['error_message']}</small><br/>"
                    elif progress_info.get('is_complete'):
                        status_html += f"<small style='color: green;'>✅ 向量化处理完成</small><br/>"
                    else:
                        status_html += f"<small>📊 处理进度: {progress_info.get('progress_percentage', 0):.1f}%</small><br/>"
                        if progress_info.get('current_step'):
                            status_html += f"<small>当前步骤: {progress_info['current_step']}</small><br/>"
                
                status_html += f"<small>创建时间: {info['created_at']}</small>"
            else:
                status_html += "<small>未配置知识库</small>"
            status_html += "</div>"
            
            status_html += "</div>"
            
            return status_html
            
        except Exception as e:
            return f"<div style='color: red;'>❌ 获取角色插件状态失败: {str(e)}</div>"
    
    async def _load_profile_from_file(self, profile_file):
        """从文件加载角色资料"""
        try:
            if not profile_file:
                return "❌ 请先选择文件"
            
            # 处理文件路径
            if hasattr(profile_file, 'name'):
                file_path = profile_file.name
            else:
                file_path = str(profile_file)
            
            # 检查文件是否存在
            import os
            if not os.path.exists(file_path):
                return "❌ 文件不存在，请重新选择文件"
            
            # 获取文件信息
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                return "❌ 文件为空，请选择有内容的文件"
            
            # 检查文件大小（限制为5MB）
            max_size = 5 * 1024 * 1024  # 5MB
            if file_size > max_size:
                return f"❌ 文件过大（{file_size / (1024*1024):.1f}MB），请选择小于5MB的文件"
            
            # 尝试不同的编码格式读取文件
            encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030', 'utf-16']
            content = None
            used_encoding = None
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    used_encoding = encoding
                    break
                except UnicodeDecodeError:
                    continue
                except Exception:
                    continue
            
            if content is None:
                return "❌ 无法读取文件，请检查文件编码格式（支持UTF-8、GBK、GB2312等）"
            
            if not content.strip():
                return "❌ 文件内容为空或只包含空白字符"
            
            # 清理内容：去除多余的空行和空白字符
            content = content.strip()
            
            # 添加文件加载信息
            filename = os.path.basename(file_path)
            file_size_mb = file_size / (1024 * 1024)
            
            info_header = f"""# 📄 已从文件加载：{filename}
# 📊 文件大小：{file_size_mb:.1f}MB | 编码：{used_encoding}
# ✅ 加载成功，您可以继续编辑内容

"""
            
            return info_header + content
            
        except Exception as e:
            return f"❌ 加载文件失败: {str(e)}"
    
    async def _process_profile_file_upload(self, profile_name, profile_file, profile_tags):
        """处理角色资料文件上传并自动保存"""
        try:
            if not profile_file:
                return "", ""
            
            if not profile_name.strip():
                return "❌ 请先填写角色名称", ""
            
            # 加载文件内容
            content = await self._load_profile_from_file(profile_file)
            
            if content.startswith("❌"):
                return content, ""
            
            # 自动保存角色资料
            tags = [tag.strip() for tag in profile_tags.split(",") if tag.strip()] if profile_tags else []
            self.role_plugin_manager.configure_profile(
                name=profile_name.strip(),
                content=content,
                tags=tags,
                enabled=True
            )
            
            success_msg = f"✅ 角色资料已自动保存：{profile_name.strip()}"
            logger.info(success_msg)
            
            return success_msg, content
            
        except Exception as e:
            logger.error(f"处理角色资料文件失败: {e}")
            return f"❌ 处理失败: {str(e)}", ""
    
    async def _save_role_plugin_config(self, profile_enabled, profile_name, profile_content, profile_tags,
                                      kb_enabled, kb_name, kb_file, kb_description, kb_search_limit):
        """保存角色插件配置（主要用于启用/禁用和手动文本配置）"""
        try:
            # 配置角色资料（如果有手动输入的内容）
            if profile_name.strip() and profile_content.strip():
                tags = [tag.strip() for tag in profile_tags.split(",") if tag.strip()] if profile_tags else []
                self.role_plugin_manager.configure_profile(
                    name=profile_name.strip(),
                    content=profile_content.strip(),
                    tags=tags,
                    enabled=profile_enabled
                )
                logger.info(f"角色资料已配置: {profile_name}")
            elif profile_enabled and not self.role_plugin_manager.profile_plugin.profile:
                return "❌ 启用角色资料插件时，请先填写角色名称和内容，或上传角色资料文件"
            
            # 处理插件启用/禁用状态
            if profile_enabled:
                self.role_plugin_manager.enable_plugin("role_profile")
            else:
                self.role_plugin_manager.disable_plugin("role_profile")
            
            if kb_enabled:
                self.role_plugin_manager.enable_plugin("role_knowledge_base")
            else:
                self.role_plugin_manager.disable_plugin("role_knowledge_base")
            
            # 检查当前状态
            status = self.role_plugin_manager.get_status()
            profile_info = status['profile_plugin']
            kb_info = status['knowledge_base_plugin']
            
            result_msgs = []
            
            if profile_info['enabled']:
                if profile_info['available']:
                    result_msgs.append("✅ 角色资料插件已启用")
                else:
                    result_msgs.append("⚠️ 角色资料插件已启用，但缺少角色资料内容")
            else:
                result_msgs.append("🔴 角色资料插件已禁用")
            
            if kb_info['enabled']:
                if kb_info['available']:
                    kb_data = kb_info.get('info', {})
                    vector_count = kb_data.get('vector_count', 0)
                    result_msgs.append(f"✅ 角色知识库插件已启用（{vector_count} 个向量）")
                else:
                    result_msgs.append("⚠️ 角色知识库插件已启用，但缺少知识库数据")
            else:
                result_msgs.append("🔴 角色知识库插件已禁用")
            
            return "\n".join(result_msgs)
            
        except Exception as e:
            logger.error(f"保存角色插件配置失败: {e}")
            return f"❌ 保存配置失败: {str(e)}"
    
    async def _clear_role_profile(self):
        """清空角色资料"""
        try:
            self.role_plugin_manager.profile_plugin.clear_profile()
            self.role_plugin_manager.profile_plugin.disable()
            self.role_plugin_manager._save_config()
            return "✅ 角色资料已清空"
        except Exception as e:
            return f"❌ 清空角色资料失败: {str(e)}"
    
    async def _clear_role_knowledge_base(self):
        """清空角色知识库配置"""
        try:
            self.role_plugin_manager.knowledge_base_plugin.clear_knowledge_base()
            self.role_plugin_manager.knowledge_base_plugin.disable()
            self.role_plugin_manager._save_config()
            return "✅ 角色知识库配置已清空"
        except Exception as e:
            return f"❌ 清空知识库配置失败: {str(e)}"
    
    async def _process_kb_file_upload(self, kb_name, kb_file, kb_description, kb_search_limit):
        """处理知识库文件上传"""
        try:
            if not kb_file:
                return "", gr.update(visible=False)
            
            if not kb_name.strip():
                return "<div style='color: red;'>❌ 请先填写知识库名称</div>", gr.update(visible=True)
            
            # 显示开始处理状态
            processing_html = "<div style='color: blue;'>📤 开始处理知识库文件...</div>"
            
            # 保存上传的文件到工作空间
            import shutil
            kb_file_path = f"./workspace/kb_{kb_name.strip().replace(' ', '_')}.{kb_file.name.split('.')[-1]}"
            shutil.copy2(kb_file.name, kb_file_path)
            
            # 设置进度回调函数
            progress_messages = []
            
            def progress_callback(progress):
                """进度回调函数"""
                message = f"📊 {progress.current_step} ({progress.processed_chunks}/{progress.total_chunks}) - {progress.progress_percentage:.1f}%"
                progress_messages.append(message)
                logger.info(message)
            
            self.role_plugin_manager.knowledge_base_plugin.set_progress_callback(progress_callback)
            
            # 配置知识库（包含向量化处理）
            await self.role_plugin_manager.configure_knowledge_base(
                name=kb_name.strip(),
                source_file=kb_file_path,
                description=kb_description.strip() if kb_description else "",
                search_limit=int(kb_search_limit) if kb_search_limit else 3,
                enabled=True,
                process_immediately=True
            )
            
            # 获取处理结果信息
            kb_info = self.role_plugin_manager.knowledge_base_plugin.get_knowledge_base_info()
            progress_info = kb_info.get('progress', {}) if kb_info else {}
            
            if progress_info.get('error_message'):
                result_html = f"<div style='color: red;'>❌ 知识库处理失败: {progress_info['error_message']}</div>"
            elif progress_info.get('is_complete'):
                vector_count = kb_info.get('vector_count', 0)
                data_count = kb_info.get('data_count', 0)
                collection_name = kb_info.get('collection_name', 'N/A')
                result_html = f"""
                <div style='color: green; border: 1px solid #4CAF50; padding: 10px; border-radius: 5px; background-color: #f0fff0;'>
                    ✅ <strong>知识库处理完成！</strong><br/>
                    📊 处理了 {data_count} 个文档段落<br/>
                    🔢 生成了 {vector_count} 个512维向量<br/>
                    📚 集合名称: {collection_name}<br/>
                    🎯 知识库已启用，可以开始使用
                </div>
                """
            else:
                result_html = "<div style='color: orange;'>⚠️ 知识库配置已保存，但向量化处理可能未完成</div>"
            
            return result_html, gr.update(visible=True)
            
        except Exception as e:
            logger.error(f"处理知识库文件失败: {e}")
            error_html = f"<div style='color: red;'>❌ 处理失败: {str(e)}</div>"
            return error_html, gr.update(visible=True)

    async def _show_knowledge_base_contents(self, limit: int = 50):
        """显示知识库内容"""
        try:
            if not self.role_plugin_manager.knowledge_base_plugin.knowledge_base:
                return "<div style='color: orange;'>⚠️ 暂无知识库配置</div>"
            
            # 获取集合内容
            contents = await self.role_plugin_manager.knowledge_base_plugin.get_collection_contents(limit)
            
            if not contents:
                return "<div style='color: orange;'>⚠️ 知识库为空或未完成向量化处理</div>"
            
            # 生成内容HTML
            content_html = "<div style='font-family: monospace; max-height: 600px; overflow-y: auto;'>"
            content_html += f"<h4>📚 知识库内容（显示前 {len(contents)} 条）</h4>"
            
            for i, item in enumerate(contents, 1):
                content_html += f"<div style='margin: 8px 0; padding: 8px; border: 1px solid #ddd; border-radius: 4px; background-color: #f9f9f9;'>"
                content_html += f"<strong>📄 文档片段 {i}</strong><br/>"
                content_html += f"<small>ID: {item['id']}</small><br/>"
                
                # 显示元数据
                metadata = item.get('metadata', {})
                if metadata:
                    content_html += f"<small>来源索引: {metadata.get('source_index', 'N/A')}</small><br/>"
                    content_html += f"<small>块索引: {metadata.get('chunk_index', 'N/A')}</small><br/>"
                    if 'source_text' in metadata:
                        content_html += f"<small>原始文本: {metadata['source_text']}</small><br/>"
                
                # 显示内容预览
                preview = item.get('preview', item.get('content', ''))
                content_html += f"<div style='margin-top: 4px; padding: 4px; background-color: white; border-radius: 2px;'>"
                content_html += f"<small>{preview}</small>"
                content_html += "</div>"
                content_html += "</div>"
            
            content_html += "</div>"
            return content_html
            
        except Exception as e:
            logger.error(f"显示知识库内容失败: {e}")
            return f"<div style='color: red;'>❌ 显示知识库内容失败: {str(e)}</div>"
    
    def _load_role_plugin_current_config(self):
        """加载当前角色插件配置到界面"""
        try:
            status = self.role_plugin_manager.get_status()
            
            # 角色资料配置
            profile_info = status['profile_plugin']
            profile_enabled = profile_info['enabled']
            profile_name = ""
            profile_content = ""
            profile_tags = ""
            
            if profile_info['info']:
                info = profile_info['info']
                profile_name = info['name']
                profile_content = self.role_plugin_manager.profile_plugin.profile.content if self.role_plugin_manager.profile_plugin.profile else ""
                profile_tags = ", ".join(info['tags']) if info['tags'] else ""
            
            # 知识库配置
            kb_info = status['knowledge_base_plugin']
            kb_enabled = kb_info['enabled']
            kb_name = ""
            kb_description = ""
            kb_search_limit = 3
            
            if kb_info['info']:
                info = kb_info['info']
                kb_name = info['name']
                kb_description = info['description']
                kb_search_limit = info['search_limit']
            
            import gradio as gr
            return (
                profile_enabled, profile_name, profile_content, profile_tags,
                kb_enabled, kb_name, kb_description, kb_search_limit
            )
        except Exception as e:
            logger.error(f"加载角色插件配置失败: {e}")
            import gradio as gr
            return (False, "", "", "", False, "", "", 3)
    
    async def _refresh_mcp_servers(self):
        """刷新MCP服务器状态"""
        import gradio as gr
        
        try:
            if not self.tool_manager:
                error_html = "<div style='color: red;'>❌ 工具管理器未初始化</div>"
                return error_html, gr.update(choices=[])
            
            # 使用工具管理器获取服务器状态
            servers_dict = self.tool_manager.get_servers_status()
            
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
                    
                    # 获取原始服务器信息以显示依赖状态
                    original_info = servers_dict.get(server['id'], {})
                    deps_info = original_info.get('dependencies', {})
                    deps_status = deps_info.get('status', 'unknown')
                    deps_icon = {"ok": "✅", "missing": "❌", "unknown": "❓"}.get(deps_status, "❓")
                    
                    status_html += f"<div style='margin: 8px 0; padding: 8px; border: 1px solid #ddd; border-radius: 4px;'>"
                    status_html += f"<strong>{status_icon} {type_icon} {deps_icon} {server['name']}</strong><br/>"
                    status_html += f"<small>ID: {server['id']} | 类型: {server['type']}</small><br/>"
                    status_html += f"<small>状态: {'已连接' if server['connected'] else '未连接'}</small><br/>"
                    status_html += f"<small>依赖: {deps_info.get('message', '未知')}</small><br/>"
                    if deps_status == "missing" and "install_command" in deps_info:
                        status_html += f"<small style='color: #ff6600;'>安装: {deps_info['install_command']}</small><br/>"
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
    
    async def _upload_files(self, files):
        """上传文件到输入目录"""
        import shutil
        import os
        
        if not files:
            return "❌ 请选择要上传的文件", self._format_file_list_html([], "输入文件夹")
        
        try:
            uploaded_count = 0
            for file_info in files:
                if hasattr(file_info, 'name') and file_info.name:
                    # 文件路径
                    src_path = file_info.name
                    filename = os.path.basename(src_path)
                    dst_path = os.path.join(self.workspace_config['input_dir'], filename)
                    
                    # 复制文件
                    shutil.copy2(src_path, dst_path)
                    uploaded_count += 1
                    logger.info(f"文件上传成功: {filename} -> {dst_path}")
            
            status_msg = f"✅ 成功上传 {uploaded_count} 个文件到输入目录"
            
            # 刷新输入文件列表
            input_files = self._list_files_in_dir(self.workspace_config['input_dir'])
            input_files_html = self._format_file_list_html(input_files, "输入文件夹")
            
            return status_msg, input_files_html
            
        except Exception as e:
            error_msg = f"❌ 文件上传失败: {str(e)}"
            logger.error(error_msg)
            return error_msg, self._format_file_list_html([], "输入文件夹")
    
    async def _refresh_file_lists(self):
        """刷新文件列表"""
        try:
            # 确保目录存在
            self._ensure_workspace_dirs()
            
            # 获取输入文件
            input_files = self._list_files_in_dir(self.workspace_config['input_dir'])
            input_files_html = self._format_file_list_html(input_files, "输入文件夹")
            
            # 获取输出文件
            output_files = self._list_files_in_dir(self.workspace_config['output_dir'])
            output_files_html = self._format_file_list_html(output_files, "输出文件夹")
            
            return input_files_html, output_files_html
            
        except Exception as e:
            error_msg = f"❌ 刷新文件列表失败: {str(e)}"
            logger.error(error_msg)
            return error_msg, error_msg
    
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
            
            # 更新配置中的enabled_mcp_servers
            self.current_config['enabled_mcp_servers'] = enabled_servers
            
            # 获取所有服务器状态
            servers_dict = self.tool_manager.get_servers_status() if self.tool_manager else {}
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
    
    def _extract_tables_from_text(self, text: str) -> tuple:
        """从文本中提取表格数据，返回(处理后的文本, 表格数据列表)"""
        import re
        
        tables_data = []
        
        def parse_table_content(table_content):
            """解析表格内容为DataFrame格式"""
            lines = [line.strip() for line in table_content.split('\n') if line.strip()]
            
            if len(lines) < 3:  # 至少需要表头、分隔线、数据行
                return None
            
            # 解析表头
            header_line = lines[0]
            if not header_line.startswith('|') or not header_line.endswith('|'):
                return None
            
            headers = [h.strip() for h in header_line.split('|')[1:-1]]
            
            # 解析数据行
            data_rows = []
            for line in lines[2:]:  # 跳过表头和分隔线
                if line.startswith('|') and line.endswith('|'):
                    row_data = [cell.strip() for cell in line.split('|')[1:-1]]
                    if len(row_data) == len(headers):  # 确保列数匹配
                        data_rows.append(row_data)
            
            if not data_rows:
                return None
                
            return {
                'headers': headers,
                'data': data_rows
            }
        
        # 1. 处理 ```table 代码块格式
        table_block_pattern = r'```table\s*\n([\s\S]*?)\n```'
        
        def extract_table_block(match):
            table_content = match.group(1).strip()
            table_data = parse_table_content(table_content)
            if table_data:
                tables_data.append(table_data)
                return f"\n📊 **表格 {len(tables_data)}**\n\n"  # 用占位符替换
            return match.group(0)
        
        text = re.sub(table_block_pattern, extract_table_block, text, flags=re.MULTILINE)
        
        # 2. 处理普通markdown表格格式
        table_pattern = r'((?:^\|.*\|[ \t]*$\n?){3,})'  # 至少3行
        
        def extract_markdown_table(match):
            table_content = match.group(1).strip()
            table_data = parse_table_content(table_content)
            if table_data:
                tables_data.append(table_data)
                return f"\n📊 **表格 {len(tables_data)}**\n\n"  # 用占位符替换
            return match.group(0)
        
        text = re.sub(table_pattern, extract_markdown_table, text, flags=re.MULTILINE)
        
        return text, tables_data

    def _highlight_agent_keywords(self, text: str) -> tuple:
        """为Agent关键词添加高亮样式，同时提取表格数据，返回(处理后的文本, 表格数据列表)"""
        import re
        
        # 首先提取表格数据
        text, tables_data = self._extract_tables_from_text(text)
        
        # 先提取所有代码块，避免在代码块内进行关键词替换
        preserved_blocks = []
        # 匹配代码块等
        preserve_pattern = r'```[\s\S]*?```|`[^`]+`'
        
        def preserve_block(match):
            preserved_blocks.append(match.group())
            return f"__PRESERVED_BLOCK_{len(preserved_blocks) - 1}__"
        
        # 暂时替换所有需要保护的块
        text_without_blocks = re.sub(preserve_pattern, preserve_block, text)
        
        # 定义关键词及其对应的CSS类
        keywords = {
            r'\bQuestion\s*:': 'agent-keyword-question',
            r'\bThought\s*:': 'agent-keyword-thought', 
            r'\bAction\s*:': 'agent-keyword-action',
            r'\bAction\s+Input\s*:': 'agent-keyword-action-input',
            r'\bObservation\s*:': 'agent-keyword-observation',
            r'\bFinal\s+Answer\s*:': 'agent-keyword-final-answer'
        }
        
        # 对每个关键词进行替换（只在非保护块区域）
        for pattern, css_class in keywords.items():
            text_without_blocks = re.sub(
                pattern,
                lambda m: f'<span class="{css_class}">{m.group()}</span>',
                text_without_blocks,
                flags=re.IGNORECASE
            )
        
        # 恢复保护的块
        for i, block in enumerate(preserved_blocks):
            text_without_blocks = text_without_blocks.replace(f"__PRESERVED_BLOCK_{i}__", block)
        
        return text_without_blocks, tables_data
    
    def _prepare_table_update(self, tables_data: list) -> "gr.update":
        """准备表格更新"""
        import gradio as gr
        
        if not tables_data:
            return gr.update(value=[], headers=None, visible=False)
        
        # 如果有多个表格，合并显示最后一个或者最重要的一个
        # 这里选择显示最后一个表格
        last_table = tables_data[-1]
        
        return gr.update(
            value=last_table['data'],
            headers=last_table['headers'],
            visible=True,
            label=f"📊 表格数据 ({len(tables_data)} 个表格)" if len(tables_data) > 1 else "📊 表格数据"
        )
    
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
                empty_table_update = self._prepare_table_update([])
                yield "", history, empty_table_update, {}, "", [], ""
                return
        
        # 添加用户消息
        history.append({"role": "user", "content": message})
        
        # 检查是否启用批处理模式
        if self.batch_processor and self.batch_processor.is_batch_mode_enabled():
            # 批处理模式：流式处理批量请求
            history.append({"role": "assistant", "content": "🔄 检测到批处理模式，正在初始化..."})
            
            try:
                accumulated_content = "🔄 检测到批处理模式，正在初始化...\n\n"
                execution_trace = []
                
                # 使用流式批处理方法
                async for progress_data in self.batch_processor.process_batch_request_with_progress(message):
                    progress_type = progress_data.get("type", "")
                    progress_content = progress_data.get("content", "")
                    
                    if progress_type == "progress":
                        # 初始化阶段
                        accumulated_content = progress_content + "\n\n"
                        
                    elif progress_type == "instruction_generated":
                        # 指令生成完成
                        accumulated_content = progress_content + "\n\n"
                        
                    elif progress_type == "batch_start":
                        # 批次开始
                        accumulated_content += progress_content + "\n"
                        
                    elif progress_type == "batch_completed":
                        # 批次完成
                        accumulated_content += progress_content + "\n"
                        
                        # 添加进度信息到执行轨迹
                        progress_info = progress_data.get("progress", {})
                        execution_trace.append({
                            "node": "batch_progress",
                            "type": "progress",
                            "duration": 0.0,
                            "state": "success",
                            "output": progress_info
                        })
                        
                    elif progress_type == "sequential_start":
                        # 顺序模式开始
                        accumulated_content += progress_content + "\n\n"
                        
                    elif progress_type == "task_start":
                        # 单个任务开始（顺序模式）
                        accumulated_content += progress_content + "\n"
                        
                    elif progress_type == "task_completed":
                        # 单个任务完成（顺序模式）
                        accumulated_content += progress_content + "\n\n"
                        
                        # 添加任务结果到执行轨迹
                        task_result = progress_data.get("result", {})
                        execution_trace.append({
                            "node": f"task_{task_result.get('row_index', 'unknown')}",
                            "type": "task",
                            "duration": task_result.get('execution_time', 0),
                            "state": "success" if task_result.get('success') else "failed",
                            "output": {
                                "task_prompt": task_result.get('task_prompt', ''),
                                "result_preview": str(task_result.get('result', ''))[:100] + "..." if task_result.get('result') else task_result.get('error', '')
                            }
                        })
                        
                    elif progress_type == "task_error":
                        # 单个任务失败（顺序模式）
                        accumulated_content += progress_content + "\n\n"
                        
                        # 添加错误到执行轨迹
                        task_info = progress_data.get("task_info", {})
                        execution_trace.append({
                            "node": f"task_{task_info.get('task_index', 'unknown')}",
                            "type": "task",
                            "duration": 0.0,
                            "state": "failed",
                            "output": {
                                "error": progress_data.get("error", ""),
                                "task_prompt": task_info.get('task_prompt', '')[:50] + "..."
                            }
                        })
                        
                    elif progress_type == "final_summary":
                        # 最终汇总
                        accumulated_content += "\n" + progress_content
                        
                    elif progress_type == "error":
                        # 错误
                        accumulated_content += "\n" + progress_content
                        
                    # 应用关键词高亮并更新界面
                    highlighted_content, tables_data = self._highlight_agent_keywords(accumulated_content)
                    history[-1]["content"] = highlighted_content
                    
                    # 准备表格数据
                    table_update = self._prepare_table_update(tables_data)
                    
                    # 流式更新界面
                    yield "", history, table_update, execution_trace, "", [], ""
                    
                    # 短暂延迟以便观察进度更新
                    await asyncio.sleep(0.1)
                
                return
                    
            except Exception as e:
                error_msg = f"❌ 批处理执行异常: {str(e)}"
                history[-1]["content"] = error_msg
                empty_table_update = self._prepare_table_update([])
                yield "", history, empty_table_update, {}, "", [], ""
                return
        
        # 正常单次处理模式
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
                    
                    # 应用关键词高亮并提取表格数据
                    highlighted_content, tables_data = self._highlight_agent_keywords(accumulated_response)
                    
                    # 更新历史记录中的最后一条助手消息
                    history[-1]["content"] = highlighted_content
                    
                    # 准备表格数据
                    table_update = self._prepare_table_update(tables_data)
                    
                    # 返回更新的历史记录实现打字机效果
                    yield "", history, table_update, {}, "", [], ""
                    
                    # 短暂延迟实现打字机效果
                    await asyncio.sleep(0.02)  # 20ms延迟
                    
                elif chunk_type == "tool_result":
                    # 工具调用结果
                    tool_name = chunk_data.get("metadata", {}).get("tool_name", "")
                    tool_input = chunk_data.get("metadata", {}).get("tool_input", "")
                    tool_output = chunk_data.get("metadata", {}).get("tool_output", "")
                    
                    accumulated_response += chunk_content
                    highlighted_content, tables_data = self._highlight_agent_keywords(accumulated_response)
                    history[-1]["content"] = highlighted_content
                    
                    # 准备表格数据
                    table_update = self._prepare_table_update(tables_data)
                    
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
                    
                    yield "", history, table_update, execution_trace, "", [], ""
                    
                elif chunk_type == "tool_error":
                    # 工具执行错误
                    error_msg = chunk_data.get("metadata", {}).get("error", "")
                    accumulated_response += chunk_content
                    highlighted_content, tables_data = self._highlight_agent_keywords(accumulated_response)
                    history[-1]["content"] = highlighted_content
                    
                    # 准备表格数据
                    table_update = self._prepare_table_update(tables_data)
                    
                    execution_trace.append({
                        "node": "tool_error",
                        "type": "tool",
                        "duration": 0.0,
                        "state": "failed",
                        "output": {"error": error_msg}
                    })
                    
                    yield "", history, table_update, execution_trace, "", [], ""
                    
                elif chunk_type == "final_result":
                    # 最终结果（回退模式）
                    highlighted_content, tables_data = self._highlight_agent_keywords(chunk_content)
                    history[-1]["content"] = highlighted_content
                    
                    # 准备表格数据
                    table_update = self._prepare_table_update(tables_data)
                    
                    yield "", history, table_update, {}, "", [], ""
            
            # 生成最终指标
            metrics_text = self._format_stream_metrics(tool_calls_made, accumulated_response)
            
            # 生成节点状态表
            node_status = self._generate_node_status(execution_trace)
            
            # 生成流程图
            flow_diagram = self._generate_flow_diagram(execution_trace)
            
            # 保存对话到记忆（流式模式）
            if (self.current_agent and hasattr(self.current_agent, 'memory_enabled') and 
                self.current_agent.memory_enabled and accumulated_response.strip()):
                try:
                    await self.current_agent.memory_manager.add_conversation(message, accumulated_response)
                    print(f"流式对话已保存到记忆，会话ID: {self.current_agent.memory_manager.session_id}")
                except Exception as e:
                    print(f"保存流式对话记忆失败: {e}")
            
            # 最终输出
            final_highlighted_content, final_tables_data = self._highlight_agent_keywords(accumulated_response)
            history[-1]["content"] = final_highlighted_content
            final_table_update = self._prepare_table_update(final_tables_data)
            
            yield "", history, final_table_update, execution_trace, metrics_text, node_status, flow_diagram
            
        except Exception as e:
            # 处理错误
            error_msg = f"处理请求时出现错误: {str(e)}"
            print(error_msg)
            history[-1]["content"] = f"抱歉，{error_msg}"
            empty_table_update = self._prepare_table_update([])
            yield "", history, empty_table_update, {}, "", [], ""
    
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
    

    
    def launch(self, **kwargs):
        """启动应用"""
        app = self.create_interface()
        app.launch(**kwargs)