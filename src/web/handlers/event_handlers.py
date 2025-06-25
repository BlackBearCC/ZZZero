"""
事件处理器 - 处理所有UI事件的逻辑
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
import gradio as gr
import re
import time
import pandas as pd
import hashlib
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class EventHandlers:
    """UI事件处理器"""
    
    def __init__(self, app_instance):
        """
        初始化事件处理器
        
        Args:
            app_instance: AgentApp实例，用于访问应用状态和方法
        """
        self.app = app_instance
        
        # 预编译正则表达式（提高性能）
        self.llm_config_pattern = re.compile(r'provider|model|temperature|agent_type|iterations|tools|servers')
        self.batch_config_pattern = re.compile(r'batch|csv|concurrent|processing')
        
        # 初始化文件内容记录存储
        self.workspace_dir = Path("./workspace")
        self.workspace_dir.mkdir(exist_ok=True)
        self.file_hash_record = self.workspace_dir / "file_content_hashes.json"
        self._load_file_hashes()
    
    def _load_file_hashes(self):
        """加载已处理文件的哈希记录"""
        try:
            if self.file_hash_record.exists():
                with open(self.file_hash_record, 'r', encoding='utf-8') as f:
                    self.processed_files = json.load(f)
            else:
                self.processed_files = {}
        except Exception as e:
            logger.warning(f"加载文件哈希记录失败: {e}")
            self.processed_files = {}
    
    def _save_file_hashes(self):
        """保存文件哈希记录"""
        try:
            with open(self.file_hash_record, 'w', encoding='utf-8') as f:
                json.dump(self.processed_files, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存文件哈希记录失败: {e}")
    
    def _calculate_content_hash(self, content: str) -> str:
        """计算文件内容的MD5哈希"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _is_content_already_processed(self, content: str, file_name: str) -> bool:
        """检查文件内容是否已经被处理过"""
        content_hash = self._calculate_content_hash(content)
        
        # 检查哈希是否已存在
        if content_hash in self.processed_files:
            existing_info = self.processed_files[content_hash]
            logger.info(f"文件内容重复: {file_name} 与 {existing_info['original_file']} 内容相同")
            return True
        
        return False
    
    def _record_processed_content(self, content: str, file_name: str, category: str):
        """记录已处理的文件内容"""
        content_hash = self._calculate_content_hash(content)
        self.processed_files[content_hash] = {
            "original_file": file_name,
            "category": category,
            "processed_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "content_length": len(content)
        }
        self._save_file_hashes()
    
    def _handle_tool_result(self, result) -> tuple:
        """统一处理ToolResult对象
        
        Returns:
            tuple: (success: bool, data: dict, error_msg: str)
        """
        if hasattr(result, 'success') and hasattr(result, 'result'):
            # 这是一个ToolResult对象
            if result.success and isinstance(result.result, dict):
                result_data = result.result
                if result_data.get('success', False):
                    return True, result_data, None
                else:
                    error_msg = result_data.get('error', '未知错误')
                    return False, result_data, error_msg
            else:
                error_msg = getattr(result, 'error', '未知错误')
                return False, {}, error_msg
        elif hasattr(result, 'content'):
            result_data = result.content
        else:
            result_data = result
        
        if isinstance(result_data, dict) and result_data.get('success', False):
            return True, result_data, None
        else:
            error_msg = result_data.get('error', '未知错误') if isinstance(result_data, dict) else str(result_data)
            return False, result_data if isinstance(result_data, dict) else {}, error_msg
    
    async def on_config_change(self, *args):
        """配置变化时自动应用"""
        llm_provider, model_name, temperature, agent_type, max_iterations, available_tools, enabled_mcp_servers = args
        
        # 更新配置
        old_config = self.app.current_config.copy()
        self.app.current_config.update({
            'llm_provider': llm_provider,
            'model_name': model_name,
            'temperature': temperature,
            'agent_type': agent_type,
            'max_iterations': max_iterations,
            'available_tools': available_tools,
            'enabled_mcp_servers': enabled_mcp_servers
        })
        
        # 只有在配置真正改变时才更新Agent
        config_changed = old_config != self.app.current_config
        if config_changed:
            await self.app._update_agent_config()
            logger.info("配置已更改，Agent已更新")
        
        total_tools = len(available_tools) + len(enabled_mcp_servers)
        status_text = f"✅ 配置已应用！使用 {llm_provider}/{model_name}，启用 {total_tools} 个工具"
        if not config_changed:
            status_text += " (无变化)"
        
        logger.info(status_text)
        # 不返回任何值，因为outputs=[]
    
    async def on_batch_config_change(self, enabled, csv_file, batch_size_val, concurrent_tasks_val, processing_mode_val):
        """批处理配置变化处理"""
        try:
            # 更新配置
            self.app.current_config['batch_enabled'] = enabled
            self.app.current_config['batch_size'] = batch_size_val
            self.app.current_config['concurrent_tasks'] = concurrent_tasks_val
            self.app.current_config['processing_mode'] = processing_mode_val
            
            if not self.app.batch_processor:
                return (
                    "<div style='color: red;'>❌ 批处理器未初始化</div>", 
                    gr.update(visible=False), 
                    "<div>批处理器未初始化</div>", 
                    gr.update(value=[], headers=None),
                    gr.update(choices=[], value=[])
                )
            
            if enabled and csv_file:
                # 保存CSV文件路径
                csv_path = csv_file.name if csv_file else None
                self.app.current_config['batch_csv_path'] = csv_path
                
                # 配置批处理模式
                result = self.app.batch_processor.configure_batch_mode(
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
                    max_preview_rows = min(5, len(self.app.batch_processor.csv_data) if self.app.batch_processor else 0)
                    
                    if self.app.batch_processor and self.app.batch_processor.csv_data:
                        for i in range(max_preview_rows):
                            row_data = []
                            for col in columns:
                                cell_value = self.app.batch_processor.csv_data[i].get(col, '')
                                # 限制单元格内容长度，避免界面过宽
                                if isinstance(cell_value, str) and len(cell_value) > 50:
                                    cell_value = cell_value[:47] + "..."
                                row_data.append(str(cell_value))
                            preview_data.append(row_data)
                    
                    # 生成字段选择选项
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
                    
                    return (
                        status_html, 
                        gr.update(visible=True), 
                        csv_info_html, 
                        gr.update(value=preview_data, headers=columns),
                        gr.update(choices=field_choices, value=default_selected)
                    )
                else:
                    status_html = f"""
                    <div style='color: red; padding: 10px; border: 1px solid #f44336; border-radius: 4px; background-color: #ffebee;'>
                        ❌ <strong>批处理模式启用失败</strong><br/>
                        {result.get('message', '未知错误')}
                    </div>
                    """
                    
                    return (
                        status_html, 
                        gr.update(visible=False), 
                        "<div>CSV解析失败</div>", 
                        gr.update(value=[], headers=None),
                        gr.update(choices=[], value=[])
                    )
                    
            elif enabled and not csv_file:
                status_html = """
                <div style='color: orange; padding: 10px; border: 1px solid #ff9800; border-radius: 4px; background-color: #fff3e0;'>
                    ⚠️ <strong>请上传CSV文件以启用批处理模式</strong>
                </div>
                """
                
                return (
                    status_html, 
                    gr.update(visible=False), 
                    "<div>等待CSV文件...</div>", 
                    gr.update(value=[], headers=None),
                    gr.update(choices=[], value=[])
                )
            else:
                # 关闭批处理模式
                self.app.current_config['batch_csv_path'] = None
                result = self.app.batch_processor.configure_batch_mode(
                    enabled=False,
                    processing_mode=processing_mode_val
                )
                
                status_html = """
                <div style='color: #666; padding: 10px; border: 1px solid #ccc; border-radius: 4px; background-color: #f9f9f9;'>
                    📋 批处理模式已关闭
                </div>
                """
                
                return (
                    status_html, 
                    gr.update(visible=False), 
                    "<div>批处理模式已关闭</div>", 
                    gr.update(value=[], headers=None),
                    gr.update(choices=[], value=[])
                )
                
        except Exception as e:
            error_html = f"""
            <div style='color: red; padding: 10px; border: 1px solid #f44336; border-radius: 4px; background-color: #ffebee;'>
                ❌ <strong>批处理配置失败</strong><br/>
                {str(e)}
            </div>
            """
            return (
                error_html, 
                gr.update(visible=False), 
                f"<div>错误: {str(e)}</div>", 
                gr.update(value=[], headers=None),
                gr.update(choices=[], value=[])
            )
    
    async def on_fields_update(self, selected_fields):
        """更新字段选择"""
        try:
            if not self.app.batch_processor:
                return "<div style='color: red;'>❌ 批处理器未初始化</div>"
            
            if not selected_fields:
                return """
                <div style='color: orange; padding: 10px; border: 1px solid #ff9800; border-radius: 4px; background-color: #fff3e0;'>
                    ⚠️ 请至少选择一个字段
                </div>
                """
            
            # 构建字段选择映射
            all_fields = self.app.batch_processor.csv_structure.get('columns', [])
            field_selection = {field: field in selected_fields for field in all_fields}
            
            # 更新字段选择
            result = self.app.batch_processor.update_field_selection(field_selection)
            
            if result['success']:
                # 最终启用批处理模式
                final_result = self.app.batch_processor.configure_batch_mode(
                    enabled=True,
                    csv_file_path=self.app.current_config['batch_csv_path'],
                    batch_size=self.app.current_config['batch_size'],
                    concurrent_tasks=self.app.current_config['concurrent_tasks'],
                    processing_mode=self.app.current_config.get('processing_mode', 'parallel')
                )
                
                return f"""
                <div style='color: green; padding: 10px; border: 1px solid #4CAF50; border-radius: 4px; background-color: #f1f8e9;'>
                    ✅ <strong>批处理模式已完全启用</strong><br/>
                    📋 已选择字段: {', '.join(selected_fields)}<br/>
                    📊 数据行数: {len(self.app.batch_processor.csv_data)}<br/>
                    ⚙️ 每批处理: {self.app.current_config['batch_size']} 行<br/>
                    🔄 并发数: {self.app.current_config['concurrent_tasks']}<br/>
                    🚀 处理模式: {'并行模式' if self.app.current_config['processing_mode'] == 'parallel' else '遍历模式'}<br/>
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
    
    async def on_mcp_servers_change(self, enabled_servers: List[str]):
        """处理MCP服务器勾选变化"""
        try:
            # 防护：如果 enabled_servers 为空或者无效，直接返回当前状态
            if not isinstance(enabled_servers, list):
                enabled_servers = []
            
            # 更新工具管理器的启用服务器（只影响工具暴露）
            if self.app.tool_manager:
                self.app.tool_manager.set_enabled_servers(enabled_servers)
                logger.info(f"已更新启用的MCP服务器: {enabled_servers}")
            
            # 更新配置中的enabled_mcp_servers
            self.app.current_config['enabled_mcp_servers'] = enabled_servers
            
            # 获取所有服务器状态
            servers_dict = self.app.tool_manager.get_servers_status() if self.app.tool_manager else {}
            if not servers_dict:
                status_html, _ = await self.app._refresh_mcp_servers()
                return status_html
            
            status_messages = []
            
            for server_id, info in servers_dict.items():
                is_enabled = server_id in enabled_servers
                
                # 只记录状态变化，不实际启动/停止服务器
                if is_enabled:
                    status_messages.append(f"✅ 已启用工具: {info['name']}")
                else:
                    status_messages.append(f"⚪ 已禁用工具: {info['name']}")
            
            # 刷新状态
            status_html, _ = await self.app._refresh_mcp_servers()
            
            # 添加操作消息
            if status_messages:
                messages_html = "<br/>".join(status_messages)
                status_html = f"{status_html}<div style='margin-top: 10px; padding: 10px; background-color: #f0f8ff; border-radius: 4px;'>{messages_html}</div>"
            
            return status_html
            
        except Exception as e:
            # 发生错误时，返回刷新后的状态
            try:
                status_html, _ = await self.app._refresh_mcp_servers()
                error_msg = f"<div style='color: red;'>❌ 处理MCP服务器变化失败: {str(e)}</div>"
                return f"{status_html}<br/>{error_msg}"
            except:
                return f"<div style='color: red;'>❌ 处理MCP服务器变化失败: {str(e)}</div>"
    
    async def on_add_remote_server(self, name: str, url: str):
        """添加远程MCP服务器"""
        try:
            if not name or not url:
                return name, url, "<div style='color: red;'>❌ 请填写服务器名称和URL</div>", gr.update()
            
            # 生成服务器ID
            server_id = f"remote_{name.lower().replace(' ', '_')}"
            
            # 暂时不支持添加远程服务器功能
            raise NotImplementedError("暂时不支持添加远程服务器功能")
            
            # 刷新状态
            status_html, checkbox_update = await self.app._refresh_mcp_servers()
            
            success_html = f"<div style='color: green;'>✅ 成功添加远程服务器: {name}</div>"
            
            # 清空输入框
            return "", "", success_html, checkbox_update
            
        except Exception as e:
            error_html = f"<div style='color: red;'>❌ 添加远程服务器失败: {str(e)}</div>"
            return name, url, error_html, gr.update()
    
    async def on_upload_files(self, files):
        """上传文件到输入目录"""
        import shutil
        import os
        
        if not files:
            return "❌ 请选择要上传的文件", self.app.file_utils.format_file_list_html([], "输入文件夹")
        
        try:
            uploaded_count = 0
            for file_info in files:
                if hasattr(file_info, 'name') and file_info.name:
                    # 文件路径
                    src_path = file_info.name
                    filename = os.path.basename(src_path)
                    dst_path = os.path.join(self.app.workspace_config['input_dir'], filename)
                    
                    # 复制文件
                    shutil.copy2(src_path, dst_path)
                    uploaded_count += 1
                    logger.info(f"文件上传成功: {filename} -> {dst_path}")
            
            status_msg = f"✅ 成功上传 {uploaded_count} 个文件到输入目录"
            
            # 刷新输入文件列表
            input_files = self.app.file_utils.list_files_in_dir(self.app.workspace_config['input_dir'])
            input_files_html = self.app.file_utils.format_file_list_html(input_files, "输入文件夹")
            
            return status_msg, input_files_html
            
        except Exception as e:
            error_msg = f"❌ 文件上传失败: {str(e)}"
            logger.error(error_msg)
            return error_msg, self.app.file_utils.format_file_list_html([], "输入文件夹")
    
    async def on_refresh_file_lists(self):
        """刷新文件列表"""
        try:
            # 确保目录存在
            self.app.file_utils.ensure_workspace_dirs(self.app.workspace_config)
            
            # 获取输入文件
            input_files = self.app.file_utils.list_files_in_dir(self.app.workspace_config['input_dir'])
            input_files_html = self.app.file_utils.format_file_list_html(input_files, "输入文件夹")
            
            # 获取输出文件
            output_files = self.app.file_utils.list_files_in_dir(self.app.workspace_config['output_dir'])
            output_files_html = self.app.file_utils.format_file_list_html(output_files, "输出文件夹")
            
            return input_files_html, output_files_html
            
        except Exception as e:
            error_msg = f"❌ 刷新文件列表失败: {str(e)}"
            logger.error(error_msg)
            return error_msg, error_msg
    
    async def refresh_memory_status(self):
        """刷新记忆状态"""
        try:
            if not self.app.current_agent or not hasattr(self.app.current_agent, 'memory_enabled'):
                return "<div style='color: #666;'>🧠 记忆功能未启用</div>"
            
            if not self.app.current_agent.memory_enabled:
                return "<div style='color: #666;'>🧠 记忆功能已禁用</div>"
            
            memory_manager = self.app.current_agent.memory_manager
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
    
    async def clear_memory(self):
        """清空会话记忆"""
        try:
            if not self.app.current_agent or not hasattr(self.app.current_agent, 'memory_enabled'):
                return "<div style='color: #666;'>🧠 记忆功能未启用</div>"
            
            if not self.app.current_agent.memory_enabled:
                return "<div style='color: #666;'>🧠 记忆功能已禁用</div>"
            
            memory_manager = self.app.current_agent.memory_manager
            await memory_manager.clear_all()
            
            return "<div style='color: green;'>✅ 会话记忆已清空</div>"
            
        except Exception as e:
            return f"<div style='color: red;'>❌ 清空记忆失败: {str(e)}</div>"
    
    async def export_memory(self):
        """导出记忆数据"""
        try:
            if not self.app.current_agent or not hasattr(self.app.current_agent, 'memory_enabled'):
                return "<div style='color: #666;'>🧠 记忆功能未启用</div>", {}
            
            if not self.app.current_agent.memory_enabled:
                return "<div style='color: #666;'>🧠 记忆功能已禁用</div>", {}
            
            memory_manager = self.app.current_agent.memory_manager
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
    
    async def refresh_mcp_servers(self):
        """刷新MCP服务器状态"""
        import gradio as gr
        
        try:
            if not self.app.tool_manager:
                error_html = "<div style='color: red;'>❌ 工具管理器未初始化</div>"
                return error_html, gr.update(choices=[])
            
            # 使用工具管理器获取服务器状态
            servers_dict = self.app.tool_manager.get_servers_status()
            
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
    
    # === 角色信息管理方法 ===
    
    async def on_role_profile_file_upload(self, file):
        """处理角色信息文件上传 - 支持txt和csv格式，自动向量化，包含查重"""
        if not file:
            return ""
        
        try:
            file_path = file.name
            file_ext = file_path.lower().split('.')[-1]
            file_name = Path(file_path).name
            
            if file_ext == 'csv':
                # 处理CSV文件
                try:
                    df = pd.read_csv(file_path, encoding='utf-8')
                except UnicodeDecodeError:
                    try:
                        df = pd.read_csv(file_path, encoding='gbk')
                    except:
                        df = pd.read_csv(file_path, encoding='gb2312')
                
                # 将CSV转换为文本格式
                content_parts = []
                for index, row in df.iterrows():
                    row_text = " | ".join([f"{col}: {str(val)}" for col, val in row.items() if pd.notna(val)])
                    content_parts.append(row_text)
                
                content = "\n".join(content_parts)
                
            else:
                # 处理TXT文件
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            
            # 检查内容是否已经处理过
            if self._is_content_already_processed(content, file_name):
                return f"⚠️ 文件内容重复，已跳过处理\n\n{content}"
            
            # 自动切割并存储到向量数据库
            success = await self._auto_vectorize_content(content, "knowledge", file_name, file_ext)
            
            if success:
                # 记录已处理的文件内容
                self._record_processed_content(content, file_name, "角色信息")
                return f"✅ 文件处理完成，已存储到向量数据库\n\n{content}"
            else:
                return f"⚠️ 文件读取成功，但向量化失败\n\n{content}"
            
        except Exception as e:
            logger.error(f"读取角色信息文件失败: {e}")
            return f"读取文件失败: {str(e)}"
    
    async def _auto_vectorize_content(self, content: str, collection_type: str, source_file: str, file_ext: str = "txt") -> bool:
        """自动切割内容并存储到向量数据库 - 优化切割策略"""
        try:
            if not content or not content.strip():
                return False
            
            chunks = []
            
            if file_ext == 'csv':
                # CSV文件按行切割，每行一个片段
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    line = line.strip()
                    if not line or len(line) < 10:  # 跳过空行或太短的行
                        continue
                    chunks.append({
                        "content": line,
                        "metadata": {
                            "source": source_file,
                            "chunk_index": i,
                            "chunk_type": "csv_row"
                        }
                    })
            else:
                # TXT文件智能切割
                paragraphs = content.split('\n\n')  # 按双换行符分段
                
                for para_idx, para in enumerate(paragraphs):
                    para = para.strip()
                    if not para:
                        continue
                    
                    # 如果段落太长，按句子切割
                    if len(para) > 500:
                        sentences = para.split('。')
                        current_chunk = ""
                        sentence_start_idx = 0
                        
                        for sent_idx, sentence in enumerate(sentences):
                            sentence = sentence.strip()
                            if not sentence:
                                continue
                            
                            if len(current_chunk) + len(sentence) < 400:
                                current_chunk += sentence + "。"
                            else:
                                if current_chunk:
                                    chunks.append({
                                        "content": current_chunk.strip(),
                                        "metadata": {
                                            "source": source_file,
                                            "paragraph_index": para_idx,
                                            "sentence_range": f"{sentence_start_idx}-{sent_idx-1}",
                                            "chunk_type": "paragraph_split"
                                        }
                                    })
                                current_chunk = sentence + "。"
                                sentence_start_idx = sent_idx
                        
                        if current_chunk:
                            chunks.append({
                                "content": current_chunk.strip(),
                                "metadata": {
                                    "source": source_file,
                                    "paragraph_index": para_idx,
                                    "sentence_range": f"{sentence_start_idx}-{len(sentences)-1}",
                                    "chunk_type": "paragraph_split"
                                }
                            })
                    else:
                        chunks.append({
                            "content": para,
                            "metadata": {
                                "source": source_file,
                                "paragraph_index": para_idx,
                                "chunk_type": "paragraph"
                            }
                        })
            
            # 将切割后的内容存储到向量数据库
            if self.app.tool_manager and chunks:
                success_count = 0
                
                for chunk_data in chunks:
                    chunk_content = chunk_data["content"]
                    chunk_metadata = chunk_data["metadata"]
                    
                    if len(chunk_content.strip()) < 10:  # 跳过太短的片段
                        continue
                    
                    try:
                        # 使用集合名称作为分类
                        if collection_type == "knowledge":
                            # 存储为知识条目，使用集合名称
                            await self.app.tool_manager.call_tool(
                                "role_info_add_knowledge",
                                {
                                    "keyword": "knowledge_collection",  # 使用集合名称
                                    "content": chunk_content,
                                    "description": f"来源: {source_file} | 类型: {chunk_metadata['chunk_type']} | 索引: {chunk_metadata.get('chunk_index', chunk_metadata.get('paragraph_index', 0))}"
                                }
                            )
                        elif collection_type == "worldbook":
                            # 存储为世界书条目，使用集合名称
                            await self.app.tool_manager.call_tool(
                                "role_info_add_world_entry",
                                {
                                    "concept": "worldbook_collection",  # 使用集合名称
                                    "content": chunk_content,
                                    "category": "worldbook_collection",
                                    "keywords": [source_file, chunk_metadata['chunk_type']]
                                }
                            )
                        
                        success_count += 1
                        logger.info(f"成功存储切割片段 {success_count}/{len(chunks)}")
                        
                    except Exception as e:
                        logger.warning(f"存储切割片段失败: {e}")
                        continue
                
                logger.info(f"✅ 成功处理并向量化 {success_count}/{len(chunks)} 个文本片段")
                return success_count > 0
                
        except Exception as e:
            logger.error(f"自动向量化失败: {e}")
            return False
    
    async def on_role_save(self, role_name: str, role_content: str):
        """保存角色信息"""
        if not role_name or not role_name.strip():
            return "<div style='color: red;'>❌ 请输入角色名称</div>"
        
        if not role_content or not role_content.strip():
            return "<div style='color: red;'>❌ 请输入角色信息内容</div>"
        
        try:
            if not self.app.tool_manager:
                return "<div style='color: red;'>❌ 工具管理器未初始化</div>"
            
            # 调用MCP工具保存角色信息
            result = await self.app.tool_manager.call_tool(
                "role_info_create_profile",
                {
                    "name": role_name.strip(),
                    "content": role_content.strip()  # 修改为content参数
                }
            )
            
            # 处理ToolResult对象
            success, result_data, error_msg = self._handle_tool_result(result)
            
            if success:
                message = result_data.get('message', f"角色 '{role_name}' 保存成功")
                return f"<div style='color: green;'>{message}</div>"
            else:
                return f"<div style='color: red;'>❌ 保存失败: {error_msg}</div>"
                
        except Exception as e:
            logger.error(f"保存角色信息失败: {e}")
            return f"<div style='color: red;'>❌ 保存失败: {str(e)}</div>"
    
    async def on_role_load(self, role_name: str):
        """加载角色信息"""
        if not role_name or not role_name.strip():
            return "", "<div style='color: red;'>❌ 请输入角色名称</div>"
        
        try:
            if not self.app.tool_manager:
                return "", "<div style='color: red;'>❌ 工具管理器未初始化</div>"
            
            # 调用MCP工具查询角色信息
            result = await self.app.tool_manager.call_tool(
                "role_info_query_profile",
                {"name": role_name.strip()}
            )
            
            # 处理ToolResult对象
            success, result_data, error_msg = self._handle_tool_result(result)
            
            if success:
                profiles = result_data.get('profiles', [])
                if profiles:
                    # 取第一个匹配的角色
                    profile_data = profiles[0]
                    content = profile_data.get('content', '')
                    return content, f"<div style='color: green;'>✅ 角色 '{role_name}' 加载成功</div>"
                else:
                    return "", f"<div style='color: orange;'>⚠️ 未找到角色 '{role_name}'</div>"
            else:
                return "", f"<div style='color: red;'>❌ 加载失败: {error_msg}</div>"
                
        except Exception as e:
            logger.error(f"加载角色信息失败: {e}")
            return "", f"<div style='color: red;'>❌ 加载失败: {str(e)}</div>"
    
    async def on_knowledge_file_upload(self, files):
        """处理知识文件上传 - 支持txt和csv格式，自动向量化，包含查重"""
        if not files:
            return ""
        
        try:
            combined_content = []
            processed_files = []
            skipped_files = []
            
            for file in files:
                file_path = file.name
                file_ext = file_path.lower().split('.')[-1]
                file_name = Path(file_path).name
                
                if file_ext == 'csv':
                    # 处理CSV文件
                    try:
                        df = pd.read_csv(file_path, encoding='utf-8')
                    except UnicodeDecodeError:
                        try:
                            df = pd.read_csv(file_path, encoding='gbk')
                        except:
                            df = pd.read_csv(file_path, encoding='gb2312')
                    
                    # 将CSV转换为文本格式
                    content_parts = []
                    for index, row in df.iterrows():
                        row_text = " | ".join([f"{col}: {str(val)}" for col, val in row.items() if pd.notna(val)])
                        content_parts.append(row_text)
                    
                    content = "\n".join(content_parts)
                    
                else:
                    # 处理TXT文件
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                
                # 检查内容是否已经处理过
                if self._is_content_already_processed(content, file_name):
                    skipped_files.append(file_name)
                    combined_content.append(f"=== {file_name} (已跳过，内容重复) ===\n{content}")
                    continue
                
                # 自动切割并存储到向量数据库
                success = await self._auto_vectorize_content(content, "knowledge", file_name, file_ext)
                
                if success:
                    # 记录已处理的文件内容
                    self._record_processed_content(content, file_name, "角色知识")
                    processed_files.append(file_name)
                    combined_content.append(f"=== {file_name} (已处理) ===\n{content}")
                else:
                    combined_content.append(f"=== {file_name} (处理失败) ===\n{content}")
            
            # 添加处理状态提示
            status_info = []
            if processed_files:
                status_info.append(f"✅ 成功处理: {', '.join(processed_files)}")
            if skipped_files:
                status_info.append(f"⚠️ 跳过重复: {', '.join(skipped_files)}")
            
            result_content = "\n\n".join(combined_content)
            if status_info:
                result_content = "\n".join(status_info) + "\n\n" + result_content
            
            return result_content
            
        except Exception as e:
            logger.error(f"读取知识文件失败: {e}")
            return f"读取文件失败: {str(e)}"
    
    async def on_knowledge_add(self, role_name: str, category: str, content: str):
        """添加角色知识"""
        if not role_name or not role_name.strip():
            return "<div style='color: red;'>❌ 请先输入角色名称</div>", ""
        
        if not content or not content.strip():
            return "<div style='color: red;'>❌ 请输入知识内容</div>", ""
        
        try:
            if not self.app.tool_manager:
                return "<div style='color: red;'>❌ 工具管理器未初始化</div>", ""
            
            # 调用MCP工具添加知识，使用集合名称
            result = await self.app.tool_manager.call_tool(
                "role_info_add_knowledge",
                {
                    "keyword": "knowledge_collection",  # 使用集合名称
                    "content": content.strip(),
                    "description": f"角色: {role_name.strip()} | 分类: {category.strip() if category else '通用知识'}"
                }
            )
            
            # 处理ToolResult对象
            success, result_data, error_msg = self._handle_tool_result(result)
            
            if success:
                # 刷新知识列表
                knowledge_html = await self._get_knowledge_list(role_name.strip())
                status_msg = f"<div style='color: green;'>✅ 知识添加成功</div>"
                return status_msg, knowledge_html
            else:
                return f"<div style='color: red;'>❌ 添加失败: {error_msg}</div>", ""
                
        except Exception as e:
            logger.error(f"添加知识失败: {e}")
            return f"<div style='color: red;'>❌ 添加失败: {str(e)}</div>", ""
    
    async def on_world_file_upload(self, files):
        """处理世界书文件上传 - 支持txt和csv格式，自动向量化，包含查重"""
        if not files:
            return ""
        
        try:
            combined_content = []
            processed_files = []
            skipped_files = []
            
            for file in files:
                file_path = file.name
                file_ext = file_path.lower().split('.')[-1]
                file_name = Path(file_path).name
                
                if file_ext == 'csv':
                    # 处理CSV文件
                    try:
                        df = pd.read_csv(file_path, encoding='utf-8')
                    except UnicodeDecodeError:
                        try:
                            df = pd.read_csv(file_path, encoding='gbk')
                        except:
                            df = pd.read_csv(file_path, encoding='gb2312')
                    
                    # 将CSV转换为文本格式
                    content_parts = []
                    for index, row in df.iterrows():
                        row_text = " | ".join([f"{col}: {str(val)}" for col, val in row.items() if pd.notna(val)])
                        content_parts.append(row_text)
                    
                    content = "\n".join(content_parts)
                    
                else:
                    # 处理TXT文件
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                
                # 检查内容是否已经处理过
                if self._is_content_already_processed(content, file_name):
                    skipped_files.append(file_name)
                    combined_content.append(f"=== {file_name} (已跳过，内容重复) ===\n{content}")
                    continue
                
                # 自动切割并存储到向量数据库
                success = await self._auto_vectorize_content(content, "worldbook", file_name, file_ext)
                
                if success:
                    # 记录已处理的文件内容
                    self._record_processed_content(content, file_name, "世界书")
                    processed_files.append(file_name)
                    combined_content.append(f"=== {file_name} (已处理) ===\n{content}")
                else:
                    combined_content.append(f"=== {file_name} (处理失败) ===\n{content}")
            
            # 添加处理状态提示
            status_info = []
            if processed_files:
                status_info.append(f"✅ 成功处理: {', '.join(processed_files)}")
            if skipped_files:
                status_info.append(f"⚠️ 跳过重复: {', '.join(skipped_files)}")
            
            result_content = "\n\n".join(combined_content)
            if status_info:
                result_content = "\n".join(status_info) + "\n\n" + result_content
            
            return result_content
            
        except Exception as e:
            logger.error(f"读取世界书文件失败: {e}")
            return f"读取文件失败: {str(e)}"
    
    async def on_world_add(self, role_name: str, category: str, content: str):
        """添加世界设定"""
        if not role_name or not role_name.strip():
            return "<div style='color: red;'>❌ 请先输入角色名称</div>", ""
        
        if not content or not content.strip():
            return "<div style='color: red;'>❌ 请输入世界设定内容</div>", ""
        
        try:
            if not self.app.tool_manager:
                return "<div style='color: red;'>❌ 工具管理器未初始化</div>", ""
            
            # 调用MCP工具添加世界设定，使用集合名称
            result = await self.app.tool_manager.call_tool(
                "role_info_add_world_entry",
                {
                    "concept": "worldbook_collection",  # 使用集合名称
                    "content": content.strip(),
                    "category": "worldbook_collection",
                    "keywords": [role_name.strip(), category.strip() if category else "通用设定"]
                }
            )
            
            # 处理ToolResult对象
            success, result_data, error_msg = self._handle_tool_result(result)
            
            if success:
                # 刷新世界设定列表
                world_html = await self._get_world_list(role_name.strip())
                status_msg = f"<div style='color: green;'>✅ 世界设定添加成功</div>"
                return status_msg, world_html
            else:
                return f"<div style='color: red;'>❌ 添加失败: {error_msg}</div>", ""
                
        except Exception as e:
            logger.error(f"添加世界设定失败: {e}")
            return f"<div style='color: red;'>❌ 添加失败: {str(e)}</div>", ""
    
    async def on_role_preview_context(self, role_name: str):
        """预览完整角色上下文 - 基于已有数据，不依赖输入内容"""
        if not role_name or not role_name.strip():
            return "<div style='color: red;'>❌ 请输入角色名称</div>", False
        
        try:
            if not self.app.tool_manager:
                return "<div style='color: red;'>❌ 工具管理器未初始化</div>", False
            
            role_name = role_name.strip()
            
            # 查询角色信息
            profile_result = await self.app.tool_manager.call_tool(
                "role_info_query_profile",
                {"name": role_name}
            )
            
            # 查询角色知识
            knowledge_result = await self.app.tool_manager.call_tool(
                "role_info_search_knowledge",
                {"query": role_name, "limit": 50}
            )
            
            # 查询世界书
            world_result = await self.app.tool_manager.call_tool(
                "role_info_search_world",
                {"query": role_name, "limit": 50}
            )
            
            # 处理查询结果
            profile_success, profile_data, _ = self._handle_tool_result(profile_result)
            knowledge_success, knowledge_data, _ = self._handle_tool_result(knowledge_result)
            world_success, world_data, _ = self._handle_tool_result(world_result)
            
            # 整合数据
            context_data = {
                "profile": {},
                "knowledge": [],
                "world_entries": []
            }
            
            # 获取角色基础信息
            if profile_success and profile_data.get('profiles'):
                profiles = profile_data['profiles']
                if profiles:
                    profile = profiles[0]  # 取第一个匹配的角色
                    context_data["profile"] = {
                        "description": profile.get('content', '暂无角色信息'),
                        "name": profile.get('name', role_name),
                        "tags": profile.get('tags', [])
                    }
            
            # 获取知识条目
            if knowledge_success and knowledge_data.get('results'):
                for knowledge in knowledge_data['results']:
                    context_data["knowledge"].append({
                        "category": knowledge.get('keyword', '未分类'),
                        "content": knowledge.get('content', ''),
                        "description": knowledge.get('description', '')
                    })
            
            # 获取世界书条目
            if world_success and world_data.get('results'):
                for world_entry in world_data['results']:
                    context_data["world_entries"].append({
                        "category": world_entry.get('concept', '未分类'),
                        "content": world_entry.get('content', ''),
                        "keywords": world_entry.get('keywords', [])
                    })
            
            # 检查是否有任何数据
            has_profile = bool(context_data["profile"].get("description", "").strip())
            has_knowledge = len(context_data["knowledge"]) > 0
            has_world = len(context_data["world_entries"]) > 0
            
            if not (has_profile or has_knowledge or has_world):
                return f"<div style='color: orange;'>⚠️ 角色 '{role_name}' 暂无相关数据<br/>请先上传角色信息、知识或世界书文件</div>", True
            
            # 格式化显示
            context_html = f"""
            <div style='font-family: monospace; padding: 15px; border: 1px solid #ddd; border-radius: 8px; background-color: #f9f9f9;'>
                <h3>🎭 {role_name} - 完整角色上下文</h3>
                
                <div style='margin: 10px 0;'>
                    <h4>👤 角色信息:</h4>
                    <div style='background-color: #fff; padding: 10px; border-radius: 4px; margin: 5px 0;'>
                        {context_data['profile'].get('description', '暂无角色信息')}
                    </div>
                    {f'<small>标签: {", ".join(context_data["profile"].get("tags", []))}</small>' if context_data["profile"].get("tags") else ''}
                </div>
                
                <div style='margin: 10px 0;'>
                    <h4>📚 角色知识 ({len(context_data['knowledge'])} 条):</h4>
                    <div style='background-color: #fff; padding: 10px; border-radius: 4px; margin: 5px 0; max-height: 300px; overflow-y: auto;'>
            """
            
            if context_data['knowledge']:
                for i, knowledge in enumerate(context_data['knowledge'], 1):
                    context_html += f"""
                    <div style='margin: 5px 0; padding: 5px; border-left: 3px solid #007bff;'>
                        <strong>{i}. {knowledge.get('category', '未分类')}:</strong> 
                        {knowledge.get('content', '')[:200]}{'...' if len(knowledge.get('content', '')) > 200 else ''}
                        {f'<br/><small style="color: #666;">{knowledge.get("description", "")}</small>' if knowledge.get('description') else ''}
                    </div>
                    """
            else:
                context_html += "<p style='color: #666;'>暂无知识条目</p>"
            
            context_html += """
                    </div>
                </div>
                
                <div style='margin: 10px 0;'>
                    <h4>🌍 世界设定 ({} 条):</h4>
                    <div style='background-color: #fff; padding: 10px; border-radius: 4px; margin: 5px 0; max-height: 300px; overflow-y: auto;'>
            """.format(len(context_data['world_entries']))
            
            if context_data['world_entries']:
                for i, world_entry in enumerate(context_data['world_entries'], 1):
                    context_html += f"""
                    <div style='margin: 5px 0; padding: 5px; border-left: 3px solid #28a745;'>
                        <strong>{i}. {world_entry.get('category', '未分类')}:</strong> 
                        {world_entry.get('content', '')[:200]}{'...' if len(world_entry.get('content', '')) > 200 else ''}
                        {f'<br/><small style="color: #666;">关键词: {", ".join(world_entry.get("keywords", []))}</small>' if world_entry.get('keywords') else ''}
                    </div>
                    """
            else:
                context_html += "<p style='color: #666;'>暂无世界设定</p>"
            
            context_html += """
                    </div>
                </div>
                
                <div style='margin: 15px 0; padding: 10px; background-color: #e9ecef; border-radius: 4px;'>
                    <h5>📊 数据统计:</h5>
                    <ul style='margin: 5px 0;'>
                        <li>角色信息: {}</li>
                        <li>知识条目: {} 条</li>
                        <li>世界设定: {} 条</li>
                        <li>总文本长度: 约 {} 字符</li>
                    </ul>
                </div>
            </div>
            """.format(
                "已设置" if has_profile else "未设置",
                len(context_data['knowledge']),
                len(context_data['world_entries']),
                len(context_data['profile'].get('description', '')) + 
                sum(len(k.get('content', '')) for k in context_data['knowledge']) +
                sum(len(w.get('content', '')) for w in context_data['world_entries'])
            )
            
            return context_html, True
                
        except Exception as e:
            logger.error(f"预览角色上下文失败: {e}")
            return f"<div style='color: red;'>❌ 预览失败: {str(e)}</div>", False
    
    async def _get_knowledge_list(self, role_name: str) -> str:
        """获取知识列表HTML"""
        try:
            result = await self.app.tool_manager.call_tool(
                "role_info_search_knowledge",
                {"query": role_name, "limit": 20}
            )
            
            # 处理ToolResult对象
            success, result_data, error_msg = self._handle_tool_result(result)
            
            if success:
                knowledge_list = result_data.get('results', [])
                if not knowledge_list:
                    return "<div style='color: #666;'>暂无知识条目</div>"
                
                html = "<div style='font-family: monospace;'>"
                for idx, knowledge in enumerate(knowledge_list, 1):
                    html += f"""
                    <div style='margin: 5px 0; padding: 8px; border: 1px solid #ddd; border-radius: 4px; background-color: #f9f9f9;'>
                        <strong>{idx}. {knowledge.get('keyword', '未分类')}</strong><br/>
                        <small>{knowledge.get('content', '')[:150]}{'...' if len(knowledge.get('content', '')) > 150 else ''}</small>
                    </div>
                    """
                html += "</div>"
                return html
            else:
                return "<div style='color: #666;'>暂无知识条目</div>"
                
        except Exception as e:
            return f"<div style='color: red;'>获取知识列表失败: {str(e)}</div>"
    
    async def _get_world_list(self, role_name: str) -> str:
        """获取世界设定列表HTML"""
        try:
            result = await self.app.tool_manager.call_tool(
                "role_info_search_world",
                {"query": role_name, "limit": 20}
            )
            
            # 处理ToolResult对象
            success, result_data, error_msg = self._handle_tool_result(result)
            
            if success:
                world_list = result_data.get('results', [])
                if not world_list:
                    return "<div style='color: #666;'>暂无世界设定</div>"
                
                html = "<div style='font-family: monospace;'>"
                for idx, world_entry in enumerate(world_list, 1):
                    html += f"""
                    <div style='margin: 5px 0; padding: 8px; border: 1px solid #ddd; border-radius: 4px; background-color: #f9f9f9;'>
                        <strong>{idx}. {world_entry.get('concept', '未分类')}</strong><br/>
                        <small>{world_entry.get('content', '')[:150]}{'...' if len(world_entry.get('content', '')) > 150 else ''}</small>
                    </div>
                    """
                html += "</div>"
                return html
            else:
                return "<div style='color: #666;'>暂无世界设定</div>"
                
        except Exception as e:
            return f"<div style='color: red;'>获取世界设定列表失败: {str(e)}</div>"
    
    async def on_stream_chat(self, message: str, history: List[Dict[str, str]]):
        """处理流式聊天 - 实现打字机效果"""
        import gradio as gr
        
        try:
            # 检查是否有Agent
            if not self.app.current_agent:
                yield history + [{"role": "assistant", "content": "❌ Agent未初始化，请先配置LLM"}], "", gr.update(value=[], headers=None, visible=False), "", "", gr.update(interactive=True)
                return
            
            # 检查是否为空消息
            if not message or not message.strip():
                yield history, message, gr.update(value=[], headers=None, visible=False), "", "", gr.update(interactive=True)
                return
            
            # 添加用户消息到历史
            new_history = history + [{"role": "user", "content": message}]
            
            # 创建空的助手回复位置 
            assistant_reply = {"role": "assistant", "content": ""}
            new_history.append(assistant_reply)
            
            # 初始化追踪数据
            full_response = ""
            tool_calls = []
            displayed_length = 0  # 已显示的字符长度
            typing_speed = 0.008  # 每批字符的显示间隔，稍快一些
            chars_per_batch = 2  # 每次显示的字符数，减少批次大小提高流畅度
            
            # 关键词列表，用于检测是否需要立即刷新
            keywords = ['Question:', 'Thought:', 'Action:', 'Action Input:', 'Observation:', 'Final Answer:']
            
            # ✅ 修复：构建完整的对话历史上下文
            # 将gradio的history格式转换为Message对象列表
            from core.types import Message, MessageRole
            
            conversation_messages = []
            
            # 转换历史对话（包括当前用户消息）
            for item in new_history:
                if item["role"] == "user":
                    conversation_messages.append(Message(
                        role=MessageRole.USER,
                        content=item["content"]
                    ))
                elif item["role"] == "assistant" and item["content"].strip():
                    # 只添加有内容的助手消息，跳过空的回复位置
                    conversation_messages.append(Message(
                        role=MessageRole.ASSISTANT,
                        content=item["content"]
                    ))
            
            # 构建包含历史的上下文
            context_with_history = {
                "conversation_history": conversation_messages,  # 完整的对话历史
                "preserve_history": True  # 标记需要保留历史
            }
            
            # ✅ 修复：传递完整上下文给Agent，而不仅仅是当前消息
            async for chunk in self.app.current_agent.stream_run(message, context_with_history):
                if chunk.get("type") == "text_chunk":
                    # 获取新的文本内容
                    text_content = chunk.get("content", "")
                    full_response += text_content
                    
                    # 批量字符显示，但在遇到关键词时立即刷新
                    while displayed_length < len(full_response):
                        # 计算本批次要显示的字符数
                        remaining_chars = len(full_response) - displayed_length
                        current_batch_size = min(chars_per_batch, remaining_chars)
                        
                        # 检查即将显示的内容是否包含关键词
                        next_display_text = full_response[:displayed_length + current_batch_size]
                        prev_display_text = full_response[:displayed_length]
                        
                        # 如果新增内容包含关键词，立即显示到关键词结束
                        keyword_found = False
                        for keyword in keywords:
                            if keyword in next_display_text and keyword not in prev_display_text:
                                # 找到关键词，显示到关键词结束位置
                                keyword_end = next_display_text.find(keyword) + len(keyword)
                                if keyword_end > displayed_length:
                                    displayed_length = keyword_end
                                    keyword_found = True
                                    break
                        
                        if not keyword_found:
                            displayed_length += current_batch_size
                        
                        # 获取当前应该显示的文本
                        current_display_text = full_response[:displayed_length]
                        
                        # 实时应用关键词高亮，但不提取表格（避免复杂处理）
                        processed_text, _ = self.app.text_processor.highlight_agent_keywords(
                            current_display_text, 
                            is_streaming=True
                        )
                        
                        # 更新助手回复内容
                        assistant_reply["content"] = processed_text
                        
                        # 生成指标
                        metrics_text = self.app.text_processor.format_stream_metrics(tool_calls, current_display_text)
                        
                        # 更新界面
                        yield new_history, message, gr.update(), metrics_text, "", gr.update(interactive=False)
                        
                        # 如果遇到关键词，稍作停顿让用户注意
                        if keyword_found:
                            await asyncio.sleep(typing_speed * 3)  # 关键词后停顿稍长
                        else:
                            await asyncio.sleep(typing_speed)
                    
                elif chunk.get("type") == "tool_result":
                    # 获取工具信息和结果
                    tool_name = chunk.get("tool_name", "未知工具")
                    tool_output = chunk.get("tool_output", "")
                    tool_result_content = chunk.get("content", "")
                    
                    # 如果有实际的工具输出，用框框样式立即显示
                    if tool_output and tool_output.strip():
                        formatted_tool_output = self.app.text_processor.format_tool_output(tool_name, tool_output)
                        
                        # 将格式化的工具输出添加到累积文本中，但不参与流式显示
                        full_response += formatted_tool_output
                        
                        # 立即显示包含工具输出的完整内容
                        display_text = full_response + '<span class="typing-cursor"></span>'
                        assistant_reply["content"] = display_text
                        
                        # 更新displayed_length以跳过工具输出部分的流式显示
                        displayed_length = len(full_response)
                    
                    # 如果还有其他内容（非工具输出），正常添加
                    if tool_result_content and tool_result_content != tool_output:
                        full_response += tool_result_content
                    
                    # 记录工具调用
                    tool_call_info = {
                        "tool_name": tool_name,
                        "args": chunk.get("tool_input", {}),
                        "result": tool_output
                    }
                    tool_calls.append(tool_call_info)
                    
                    # 生成指标
                    metrics_text = self.app.text_processor.format_stream_metrics(tool_calls, full_response)
                    
                    yield new_history, message, gr.update(), metrics_text, "", gr.update(interactive=False)
                    
                elif chunk.get("type") == "tool_call":
                    # 记录工具调用，但不显示执行状态
                    tool_name = chunk.get("tool_name", "未知工具")
                    tool_call_info = {
                        "tool_name": tool_name,
                        "args": chunk.get("args", {}),
                        "result": chunk.get("result", "")
                    }
                    tool_calls.append(tool_call_info)
                    
                    # 生成指标
                    metrics_text = self.app.text_processor.format_stream_metrics(tool_calls, full_response)
                    
                    # 不更新文本内容，只更新指标
                    yield new_history, message, gr.update(), metrics_text, "", gr.update(interactive=False)
                    
                elif chunk.get("type") == "trace":
                    # 处理追踪信息
                    trace_data = chunk.get("trace", [])
                    
                    # 生成节点状态表
                    node_status = self.app.text_processor.generate_node_status(trace_data)
                    
                    # 生成流程图
                    flow_diagram = self.app.text_processor.generate_flow_diagram(trace_data)
                    
                    yield new_history, message, gr.update(), "", flow_diagram, gr.update(interactive=False)
                    
                elif chunk.get("type") in ["stream_error", "tool_error"]:
                    # 处理错误
                    error_content = chunk.get("content", "")
                    full_response += error_content
                    
                    # 直接显示累积的文本内容
                    assistant_reply["content"] = full_response
                    
                    yield new_history, message, gr.update(), f"错误: {chunk.get('error', '未知错误')}", "", gr.update(interactive=False)
            
            # ✅ 修复：对话完成后，将完整的对话保存到记忆系统
            if self.app.current_agent and hasattr(self.app.current_agent, 'memory_enabled') and self.app.current_agent.memory_enabled:
                try:
                    if self.app.current_agent.memory_manager and full_response.strip():
                        await self.app.current_agent.memory_manager.add_conversation(message, full_response)
                        logger.info(f"对话已保存到记忆系统，会话ID: {self.app.current_agent.memory_manager.session_id}")
                except Exception as e:
                    logger.warning(f"保存对话到记忆系统失败: {e}")
            
            # 流式处理完成，最终应用完整的样式处理（关键词高亮、表格提取等）
            processed_text, tables_data = self.app.text_processor.highlight_agent_keywords(full_response, is_streaming=False)
            
            # 更新助手回复内容，添加完成标记
            assistant_reply["content"] = processed_text + '<span class="response-complete"> ✨ 回复完成</span>'
            
            # 准备表格更新
            table_update = self.app.text_processor.prepare_table_update(tables_data)
            
            # 生成指标
            metrics_text = self.app.text_processor.format_stream_metrics(tool_calls, full_response)
            
            # 最后清空输入框并启用发送按钮
            yield new_history, "", table_update, metrics_text, "", gr.update(interactive=True)
            
        except Exception as e:
            error_msg = f"❌ 聊天处理失败: {str(e)}"
            logger.error(error_msg)
            
            # 添加错误消息到历史
            error_history = history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": error_msg}
            ]
            
            yield error_history, "", gr.update(value=[], headers=None, visible=False), f"错误: {str(e)}", "", gr.update(interactive=True) 