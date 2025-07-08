"""
聊天界面组件 - 包含聊天窗口、批处理配置、执行详情等
"""
import gradio as gr
from typing import Dict, Any, List


class ChatInterface:
    """聊天界面组件"""
    
    def __init__(self):
        self.components = {}
    
    def create_chat_window(self) -> Dict[str, Any]:
        """创建聊天窗口"""
        with gr.Row():
            # 左侧聊天区域
            with gr.Column(scale=2):
                # 聊天历史
                chatbot = gr.Chatbot(
                    show_label=False,
                    elem_classes=["chat-window"],
                    type="messages",
                    render_markdown=True,
                    sanitize_html=True
                )
                
                # 动态表格显示区域
                dynamic_table = gr.DataFrame(
                    value=[],
                    headers=None,
                    label="[表格] 表格数据",
                    interactive=False,
                    wrap=True,
                    visible=False
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
            
            # 右侧节点信息流面板
            with gr.Column(scale=1):
                gr.Markdown("### [信息流] 节点执行详情")
                info_stream = gr.Textbox(
                    label="实时信息流",
                    value="[等待] 等待Agent执行...",
                    interactive=False,
                    lines=20,
                    max_lines=30,
                    elem_classes=["info-stream"]
                )
                
                with gr.Row():
                    clear_info_btn = gr.Button("清空信息流", size="sm")
                    reload_agent_btn = gr.Button("重载Agent", variant="secondary", size="sm")
        
        return {
            "chatbot": chatbot,
            "dynamic_table": dynamic_table,
            "msg_input": msg_input,
            "send_btn": send_btn,
            "info_stream": info_stream,
            "clear_info_btn": clear_info_btn,
            "reload_agent_btn": reload_agent_btn
        }
    
    def create_batch_config(self) -> Dict[str, Any]:
        """创建批处理配置"""
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
        
        return {
            "batch_enabled": batch_enabled,
            "processing_mode": processing_mode,
            "batch_csv_file": csv_file_upload,  # 改名为batch_csv_file
            "batch_fields_group": csv_fields_section,  # 改名为batch_fields_group
            "batch_structure_display": csv_info_display,  # 改名为batch_structure_display
            "batch_preview_table": csv_preview_table,
            "batch_fields_checkbox": csv_fields_selection,  # 改名为batch_fields_checkbox
            "fields_update_btn": fields_update_btn,
            "batch_size": batch_size,
            "concurrent_tasks": concurrent_tasks,
            "batch_config_display": batch_status  # 改名为batch_config_display
        }
    
    def create_execution_details(self) -> Dict[str, Any]:
        """创建执行详情"""
        with gr.Accordion("📊 执行详情", open=False):
            execution_trace = gr.JSON(label="执行轨迹")
            metrics_display = gr.Textbox(label="执行指标", lines=3)
        
        return {
            "execution_trace": execution_trace,
            "metrics_display": metrics_display
        }
    
    def create_flow_visualization(self) -> Dict[str, Any]:
        """创建流程可视化"""
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
        
        return {
            "node_status": node_status,
            "flow_diagram": flow_diagram,
            "auto_refresh": auto_refresh
        }
    
    def create_full_interface(self) -> Dict[str, Any]:
        """创建完整的聊天界面"""
        # 创建各个组件
        chat_components = self.create_chat_window()
        batch_components = self.create_batch_config()
        execution_components = self.create_execution_details()
        flow_components = self.create_flow_visualization()
        
        # 合并所有组件
        all_components = {}
        all_components.update(chat_components)
        all_components.update(batch_components)
        all_components.update(execution_components)
        all_components.update(flow_components)
        
        self.components = all_components
        return all_components 