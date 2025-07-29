"""
SSE（Server-Sent Events）流式接口实现
"""

import json
import asyncio
import uuid
from typing import Dict, Any, AsyncGenerator, Optional
from datetime import datetime
from flask import Flask, Response, request
import logging

logger = logging.getLogger(__name__)

class SSEManager:
    """SSE连接管理器"""
    
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, Any]] = {}
        self.workflow_sessions: Dict[str, Dict[str, Any]] = {}
    
    def create_session(self, session_id: str = None) -> str:
        """创建新的流式会话"""
        if not session_id:
            session_id = str(uuid.uuid4())
        
        self.workflow_sessions[session_id] = {
            "created_at": datetime.now(),
            "status": "created",
            "messages": [],
            "current_content": {}
        }
        
        logger.info(f"创建SSE会话: {session_id}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        return self.workflow_sessions.get(session_id)
    
    def update_session(self, session_id: str, update_data: Dict[str, Any]):
        """更新会话数据"""
        if session_id in self.workflow_sessions:
            self.workflow_sessions[session_id].update(update_data)
    
    def add_message(self, session_id: str, sender: str, content: str, msg_type: str = "normal"):
        """添加消息到会话"""
        if session_id not in self.workflow_sessions:
            return
        
        message = {
            "timestamp": datetime.now().isoformat(),
            "sender": sender,
            "content": content,
            "type": msg_type
        }
        
        self.workflow_sessions[session_id]["messages"].append(message)
    
    def update_streaming_content(self, session_id: str, node_name: str, content: str):
        """更新流式内容（打字机效果）"""
        if session_id not in self.workflow_sessions:
            return
        
        if "current_content" not in self.workflow_sessions[session_id]:
            self.workflow_sessions[session_id]["current_content"] = {}
        
        self.workflow_sessions[session_id]["current_content"][node_name] = content
    
    async def stream_events(self, session_id: str) -> AsyncGenerator[str, None]:
        """生成SSE事件流"""
        if session_id not in self.workflow_sessions:
            yield f"data: {json.dumps({'error': 'Session not found'})}\n\n"
            return
        
        session = self.workflow_sessions[session_id]
        last_message_count = 0
        
        while session.get("status") != "completed":
            # 检查是否有新消息
            current_message_count = len(session["messages"])
            if current_message_count > last_message_count:
                # 发送新消息
                new_messages = session["messages"][last_message_count:]
                for message in new_messages:
                    event_data = {
                        "type": "message",
                        "data": message
                    }
                    yield f"data: {json.dumps(event_data)}\n\n"
                
                last_message_count = current_message_count
            
            # 发送流式内容更新
            if session.get("current_content"):
                for node_name, content in session["current_content"].items():
                    event_data = {
                        "type": "streaming_content",
                        "node": node_name,
                        "content": content
                    }
                    yield f"data: {json.dumps(event_data)}\n\n"
            
            # 发送状态更新
            if session.get("status"):
                event_data = {
                    "type": "status",
                    "status": session["status"]
                }
                yield f"data: {json.dumps(event_data)}\n\n"
            
            await asyncio.sleep(0.1)  # 100ms间隔
        
        # 发送完成信号
        yield f"data: {json.dumps({'type': 'complete'})}\n\n"

# 全局SSE管理器实例
sse_manager = SSEManager()


def create_sse_routes(app: Flask):
    """创建SSE路由"""
    
    @app.route('/api/sse/create_session', methods=['POST'])
    def create_sse_session():
        """创建SSE会话"""
        session_id = sse_manager.create_session()
        return {"session_id": session_id}
    
    @app.route('/api/sse/stream/<session_id>')
    def stream_events(session_id):
        """SSE事件流端点"""
        def generate():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def async_generator():
                async for event in sse_manager.stream_events(session_id):
                    yield event
            
            try:
                gen = async_generator()
                while True:
                    try:
                        event = loop.run_until_complete(gen.__anext__())
                        yield event
                    except StopAsyncIteration:
                        break
            finally:
                loop.close()
        
        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Cache-Control'
            }
        )
    
    @app.route('/api/workflow/character_profile_stream', methods=['POST'])
    def start_character_profile_stream():
        """启动角色资料生成流式工作流"""
        try:
            data = request.get_json()
            
            character_name = data.get('character_name', '')
            basic_info = data.get('basic_info', '')
            selected_categories = data.get('selected_categories', [])
            selected_collections = data.get('selected_collections', [])
            llm_provider = data.get('llm_provider', 'doubao')
            model_name = data.get('model_name', 'ep-20250221154410-vh78x')
            temperature = data.get('temperature', 0.7)
            
            # 输入验证
            if not character_name or not character_name.strip():
                return {"error": "请输入角色名称"}, 400
            
            if not basic_info or not basic_info.strip():
                return {"error": "请输入基础人设信息"}, 400
            
            if not selected_categories:
                return {"error": "请至少选择一个生成类别"}, 400
            
            # 创建会话
            session_id = sse_manager.create_session()
            
            # 使用线程启动异步工作流
            import threading
            
            def run_workflow_thread():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(run_character_profile_workflow(
                        session_id, character_name, basic_info, selected_categories,
                        selected_collections, llm_provider, model_name, temperature
                    ))
                finally:
                    loop.close()
            
            workflow_thread = threading.Thread(target=run_workflow_thread, daemon=True)
            workflow_thread.start()
            
            return {"session_id": session_id}
            
        except Exception as e:
            logger.error(f"启动工作流失败: {e}")
            return {"error": f"启动工作流失败: {str(e)}"}, 500


async def run_character_profile_workflow(session_id: str, character_name: str,
                                       basic_info: str, selected_categories: list,
                                       selected_collections: list, llm_provider: str,
                                       model_name: str, temperature: float):
    """异步运行角色资料生成工作流"""
    try:
        # 导入必要模块
        import sys
        import os
        
        # 添加项目根目录到路径
        project_root = os.path.join(os.path.dirname(__file__), '../../..')
        if project_root not in sys.path:
            sys.path.append(project_root)
        
        from workflow.character_profile_workflow import ProfileWorkflow
        from core.types import LLMConfig
        from llm.base import LLMFactory
        
        # 更新会话状态
        sse_manager.update_session(session_id, {"status": "running"})
        sse_manager.add_message(session_id, "系统", f"🚀 开始为角色 **{character_name}** 生成资料...")
        
        # 创建工作流
        workflow = ProfileWorkflow()
        
        # 配置LLM
        llm_config = LLMConfig(
            provider=llm_provider,
            api_key=os.getenv('DOUBAO_API_KEY', 'b633a622-b5d0-4f16-a8a9-616239cf15d1'),
            model_name=model_name,
            temperature=temperature,
            max_tokens=16384
        )
        workflow.llm_config = llm_config
        
        sse_manager.add_message(session_id, "系统", f"⚙️ LLM配置：{llm_provider} | {model_name} | temp={temperature}")
        
        # 设置信息流监听器
        from core.base import NodeInfoStream
        info_stream = NodeInfoStream()
        
        def handle_info_event(event):
            event_type = event.get("type", "")
            node_name = event.get("node_name", "")
            content = event.get("content", "")
            metadata = event.get("metadata", {})
            
            # 处理LLM流式输出
            if event_type == "llm_streaming":
                category = metadata.get("category", "")
                accumulated_content = metadata.get("accumulated_content", "")
                think_content = metadata.get("think_content", "")
                
                # 构建显示内容
                display_content = ""
                if think_content and think_content.strip():
                    display_content += f"🤔 **思考过程：**\n{think_content}\n\n"
                
                if accumulated_content:
                    display_content += f"✨ **生成内容：**\n{accumulated_content}"
                
                # 更新流式内容
                sse_manager.update_streaming_content(session_id, f"LLM-{category}", display_content)
            
            # 处理其他重要事件
            else:
                important_events = ["init", "start", "category_start", "category_complete", 
                                  "llm_start", "llm_complete", "complete", "error"]
                if event_type in important_events:
                    formatted_msg = f"{content}"
                    if metadata:
                        if "progress" in metadata:
                            formatted_msg += f" - {metadata['progress']}"
                    
                    sse_manager.add_message(session_id, f"[{node_name}]", formatted_msg)
        
        info_stream.add_callback(handle_info_event)
        
        # 执行工作流
        async for result in workflow.generate_character_profile_stream(
            character_name=character_name,
            basic_info=basic_info,
            selected_categories=selected_categories,
            selected_collections=selected_collections
        ):
            if result.get('success') is False and 'error' in result:
                sse_manager.add_message(session_id, "ProfileGenerator", f"❌ 生成失败：{result['error']}")
                sse_manager.update_session(session_id, {"status": "failed"})
                return
                
            elif 'progress' in result:
                progress_msg = f"⏳ {result['progress']}"
                current_category = result.get('current_category', '')
                if current_category:
                    progress_msg += f" - 当前类别：**{current_category}**"
                sse_manager.add_message(session_id, "ProfileGenerator", progress_msg)
                
            elif result.get('success') is True:
                output_file = result.get('output_file', '')
                profile_data = result.get('profile', {})
                
                success_msg = f"✅ 角色资料生成完成！\n\n"
                success_msg += f"🎯 生成了 {len(profile_data)} 个类别的资料\n"
                if output_file:
                    success_msg += f"📁 文件保存位置：{output_file}\n\n"
                
                for category, data in profile_data.items():
                    if isinstance(data, dict):
                        success_msg += f"📋 **{category}**：{len(data)} 个条目\n"
                
                sse_manager.add_message(session_id, "ProfileGenerator", success_msg)
                
                if output_file:
                    sse_manager.add_message(session_id, "FileSaver", f"✅ 文件已保存：{output_file}")
                
                sse_manager.update_session(session_id, {"status": "completed"})
                return
        
        sse_manager.update_session(session_id, {"status": "completed"})
        
    except Exception as e:
        logger.error(f"工作流执行失败: {e}")
        sse_manager.add_message(session_id, "系统", f"❌ 执行异常：{str(e)}")
        sse_manager.update_session(session_id, {"status": "failed"})