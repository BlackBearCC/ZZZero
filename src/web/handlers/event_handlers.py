"""
事件处理器 - 处理所有UI事件的逻辑
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
import gradio as gr
import re
import time

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
        """处理角色信息文件上传"""
        if not file:
            return ""
        
        try:
            with open(file.name, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except Exception as e:
            logger.error(f"读取角色信息文件失败: {e}")
            return f"读取文件失败: {str(e)}"
    
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
        """处理知识文件上传"""
        if not files:
            return ""
        
        try:
            combined_content = []
            for file in files:
                with open(file.name, 'r', encoding='utf-8') as f:
                    content = f.read()
                    combined_content.append(f"=== {file.name} ===\n{content}")
            
            return "\n\n".join(combined_content)
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
            
            # 调用MCP工具添加知识
            result = await self.app.tool_manager.call_tool(
                "role_info_add_knowledge",
                {
                    "keyword": category.strip() if category else "通用知识",
                    "content": content.strip(),
                    "description": f"角色 {role_name.strip()} 的知识"
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
        """处理世界书文件上传"""
        if not files:
            return ""
        
        try:
            combined_content = []
            for file in files:
                with open(file.name, 'r', encoding='utf-8') as f:
                    content = f.read()
                    combined_content.append(f"=== {file.name} ===\n{content}")
            
            return "\n\n".join(combined_content)
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
            
            # 调用MCP工具添加世界设定
            result = await self.app.tool_manager.call_tool(
                "role_info_add_world_entry",
                {
                    "concept": category.strip() if category else "通用设定",
                    "content": content.strip(),
                    "category": "世界书",
                    "keywords": [role_name.strip()]
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
        """预览完整角色上下文"""
        if not role_name or not role_name.strip():
            return "<div style='color: red;'>❌ 请输入角色名称</div>", False
        
        try:
            if not self.app.tool_manager:
                return "<div style='color: red;'>❌ 工具管理器未初始化</div>", False
            
            # 调用MCP工具获取完整上下文
            result = await self.app.tool_manager.call_tool(
                "role_info_get_role_context",
                {"role_name": role_name.strip()}
            )
            
            # 处理ToolResult对象
            success, result_data, error_msg = self._handle_tool_result(result)
            
            if success:
                context_data = result_data.get('context', {})
                
                # 格式化显示
                context_html = f"""
                <div style='font-family: monospace; padding: 15px; border: 1px solid #ddd; border-radius: 8px; background-color: #f9f9f9;'>
                    <h3>🎭 {role_name} - 完整角色上下文</h3>
                    
                    <div style='margin: 10px 0;'>
                        <h4>👤 角色信息:</h4>
                        <div style='background-color: #fff; padding: 10px; border-radius: 4px; margin: 5px 0;'>
                            {context_data.get('profile', {}).get('description', '暂无角色信息')}
                        </div>
                    </div>
                    
                    <div style='margin: 10px 0;'>
                        <h4>📚 角色知识 ({len(context_data.get('knowledge', []))} 条):</h4>
                        <div style='background-color: #fff; padding: 10px; border-radius: 4px; margin: 5px 0;'>
                """
                
                for knowledge in context_data.get('knowledge', []):
                    context_html += f"<p><strong>{knowledge.get('category', '未分类')}:</strong> {knowledge.get('content', '')[:100]}{'...' if len(knowledge.get('content', '')) > 100 else ''}</p>"
                
                context_html += """
                        </div>
                    </div>
                    
                    <div style='margin: 10px 0;'>
                        <h4>🌍 世界设定 ({} 条):</h4>
                        <div style='background-color: #fff; padding: 10px; border-radius: 4px; margin: 5px 0;'>
                """.format(len(context_data.get('world_entries', [])))
                
                for world_entry in context_data.get('world_entries', []):
                    context_html += f"<p><strong>{world_entry.get('category', '未分类')}:</strong> {world_entry.get('content', '')[:100]}{'...' if len(world_entry.get('content', '')) > 100 else ''}</p>"
                
                context_html += """
                        </div>
                    </div>
                </div>
                """
                
                return context_html, True
            else:
                return f"<div style='color: red;'>❌ 获取上下文失败: {error_msg}</div>", False
                
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
                yield history + [{"role": "assistant", "content": "❌ Agent未初始化，请先配置LLM"}], "", gr.update(value=[], headers=None, visible=False), "", ""
                return
            
            # 检查是否为空消息
            if not message or not message.strip():
                yield history, message, gr.update(value=[], headers=None, visible=False), "", ""
                return
            
            # 添加用户消息到历史
            new_history = history + [{"role": "user", "content": message}]
            
            # 创建空的助手回复位置 
            assistant_reply = {"role": "assistant", "content": ""}
            new_history.append(assistant_reply)
            
            # 初始化追踪数据
            full_response = ""
            tool_calls = []
            chunk_buffer = ""  # 用于缓冲字符
            last_update_time = time.time()
            update_interval = 0.1  # 100ms更新一次，避免更新过于频繁
            min_chars_for_update = 5  # 至少积累5个字符再更新
            
            # 启动流式处理
            async for chunk in self.app.current_agent.stream_run(message):
                if chunk.get("type") == "text_chunk":
                    # 获取新的文本内容
                    text_content = chunk.get("content", "")
                    chunk_buffer += text_content
                    
                    # 控制更新频率，实现打字机效果
                    current_time = time.time()
                    if current_time - last_update_time >= update_interval or len(chunk_buffer) > min_chars_for_update:
                        # 将缓冲区内容添加到完整响应
                        full_response += chunk_buffer
                        chunk_buffer = ""
                        last_update_time = current_time
                        
                        # 处理文本：提取表格和高亮关键词，标记为流式状态
                        processed_text, tables_data = self.app.text_processor.highlight_agent_keywords(full_response, is_streaming=True)
                        
                        # 更新助手回复内容
                        assistant_reply["content"] = processed_text
                        
                        # 准备表格更新
                        table_update = self.app.text_processor.prepare_table_update(tables_data)
                        
                        # 生成指标
                        metrics_text = self.app.text_processor.format_stream_metrics(tool_calls, full_response)
                        
                        # 实时更新界面
                        yield new_history, "", table_update, metrics_text, ""
                    
                elif chunk.get("type") == "tool_result":
                    # 处理剩余缓冲区内容
                    if chunk_buffer:
                        full_response += chunk_buffer
                        chunk_buffer = ""
                    
                    # 获取工具信息
                    tool_name = chunk.get("tool_name", "未知工具")
                    tool_result_content = chunk.get("content", "")
                    
                    # 先显示工具执行完成状态
                    tool_status = self.app.text_processor.format_tool_execution_status(tool_name, "completed")
                    full_response += f"\n{tool_status}\n"
                    
                    # 添加工具执行结果
                    full_response += tool_result_content
                    
                    # 记录工具调用
                    tool_call_info = {
                        "tool_name": tool_name,
                        "args": chunk.get("tool_input", {}),
                        "result": chunk.get("tool_output", "")
                    }
                    tool_calls.append(tool_call_info)
                    
                    # 处理文本：提取表格和高亮关键词
                    processed_text, tables_data = self.app.text_processor.highlight_agent_keywords(full_response, is_streaming=True)
                    
                    # 更新助手回复内容
                    assistant_reply["content"] = processed_text
                    
                    # 准备表格更新
                    table_update = self.app.text_processor.prepare_table_update(tables_data)
                    
                    # 生成指标
                    metrics_text = self.app.text_processor.format_stream_metrics(tool_calls, full_response)
                    
                    yield new_history, "", table_update, metrics_text, ""
                    
                elif chunk.get("type") == "tool_call":
                    # 处理剩余缓冲区内容
                    if chunk_buffer:
                        full_response += chunk_buffer
                        chunk_buffer = ""
                    
                    # 显示工具执行状态
                    tool_name = chunk.get("tool_name", "未知工具")
                    tool_status = self.app.text_processor.format_tool_execution_status(tool_name, "executing")
                    full_response += f"\n{tool_status}\n"
                    
                    # 记录工具调用
                    tool_call_info = {
                        "tool_name": tool_name,
                        "args": chunk.get("args", {}),
                        "result": chunk.get("result", "")
                    }
                    tool_calls.append(tool_call_info)
                    
                    # 处理文本：提取表格和高亮关键词
                    processed_text, tables_data = self.app.text_processor.highlight_agent_keywords(full_response, is_streaming=True)
                    
                    # 更新助手回复内容
                    assistant_reply["content"] = processed_text
                    
                    # 生成指标
                    metrics_text = self.app.text_processor.format_stream_metrics(tool_calls, full_response)
                    
                    yield new_history, "", gr.update(), metrics_text, ""
                    
                elif chunk.get("type") == "trace":
                    # 处理追踪信息
                    trace_data = chunk.get("trace", [])
                    
                    # 生成节点状态表
                    node_status = self.app.text_processor.generate_node_status(trace_data)
                    
                    # 生成流程图
                    flow_diagram = self.app.text_processor.generate_flow_diagram(trace_data)
                    
                    yield new_history, "", gr.update(), "", flow_diagram
                    
                elif chunk.get("type") in ["stream_error", "tool_error"]:
                    # 处理错误
                    error_content = chunk.get("content", "")
                    full_response += error_content
                    
                    # 处理文本：提取表格和高亮关键词
                    processed_text, tables_data = self.app.text_processor.highlight_agent_keywords(full_response)
                    
                    # 更新助手回复内容
                    assistant_reply["content"] = processed_text
                    
                    yield new_history, "", gr.update(), f"错误: {chunk.get('error', '未知错误')}", ""
            
            # 处理最后的缓冲区内容
            if chunk_buffer:
                full_response += chunk_buffer
                
                # 处理文本：提取表格和高亮关键词，不再是流式状态
                processed_text, tables_data = self.app.text_processor.highlight_agent_keywords(full_response, is_streaming=False)
                
                # 更新助手回复内容
                assistant_reply["content"] = processed_text
                
                # 准备表格更新
                table_update = self.app.text_processor.prepare_table_update(tables_data)
                
                # 生成指标
                metrics_text = self.app.text_processor.format_stream_metrics(tool_calls, full_response)
                
                yield new_history, "", table_update, metrics_text, ""
            else:
                # 即使没有缓冲区内容，也要最终更新一次以移除流式指示器
                processed_text, tables_data = self.app.text_processor.highlight_agent_keywords(full_response, is_streaming=False)
                assistant_reply["content"] = processed_text + '<span class="response-complete"> ✨ 回复完成</span>'
                
                table_update = self.app.text_processor.prepare_table_update(tables_data)
                metrics_text = self.app.text_processor.format_stream_metrics(tool_calls, full_response)
                
                yield new_history, "", table_update, metrics_text, ""
            
        except Exception as e:
            error_msg = f"❌ 聊天处理失败: {str(e)}"
            logger.error(error_msg)
            
            # 添加错误消息到历史
            error_history = history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": error_msg}
            ]
            
            yield error_history, "", gr.update(value=[], headers=None, visible=False), f"错误: {str(e)}", "" 