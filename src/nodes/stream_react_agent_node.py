"""
流式ReAct Agent节点 - 支持流式输出和Observation检测
"""
import sys
import os
import re
import json
import asyncio
from typing import Dict, Any, List, AsyncIterator, Optional

sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

from core.base import BaseNode
from core.types import NodeInput, NodeOutput, NodeType, Message, MessageRole
from llm.base import BaseLLMProvider
from parsers.regex_parser import RegexParser


class StreamReactAgentNode(BaseNode):
    """支持流式输出和Observation检测的ReAct Agent节点"""
    
    def __init__(self, name: str, llm: BaseLLMProvider, tool_manager=None, **kwargs):
        """
        初始化流式ReAct Agent节点
        
        Args:
            name: 节点名称
            llm: LLM提供者
            tool_manager: 工具管理器（可选）
            **kwargs: 其他配置参数
        """
        super().__init__(name, NodeType.AGENT, "流式ReAct智能代理节点", **kwargs)
        self.llm = llm
        self.tool_manager = tool_manager
        
        # 创建正则解析器用于提取Action和Action Input
        self.react_parser = RegexParser({
            'action': r'Action:\s*([^\n]+)',
            'action_input': r'Action Input:\s*(.*?)(?=\nObservation:|$)', 
            'thought': r'Thought:\s*([^\n]+)',
            'observation': r'Observation:\s*([^\n]+)'
        }, flags=re.DOTALL)
        
    async def execute(self, input_data: NodeInput) -> NodeOutput:
        """执行流式ReAct推理逻辑"""
        context = input_data.context
        
        # 获取对话历史
        messages = context.messages.copy()
        
        # 添加系统提示
        system_prompt = self._build_system_prompt(context)
        print(f"[StreamReactAgentNode.execute] 系统提示词长度: {len(system_prompt)}")
        
        if not any(msg.role == MessageRole.SYSTEM for msg in messages):
            messages.insert(0, Message(
                role=MessageRole.SYSTEM,
                content=system_prompt
            ))
            print(f"[StreamReactAgentNode.execute] 已添加系统提示词")
        else:
            print(f"[StreamReactAgentNode.execute] 已存在系统提示词，跳过")
        
        # 执行流式生成
        full_response = ""
        response_chunks = []
        
        async for chunk_data in self._stream_react_generation(messages):
            if chunk_data["type"] == "text_chunk":
                full_response += chunk_data["content"]
                response_chunks.append(chunk_data)
            elif chunk_data["type"] == "tool_result":
                # 工具执行结果
                full_response += chunk_data["content"]
                response_chunks.append(chunk_data)
        
        # 创建完整的响应消息
        response = Message(
            role=MessageRole.ASSISTANT,
            content=full_response,
            metadata={
                "stream_chunks": response_chunks,
                "tool_calls_executed": sum(1 for chunk in response_chunks if chunk["type"] == "tool_result")
            }
        )
        
        # 添加响应到上下文
        context.messages.append(response)
        
        return NodeOutput(
            data={
                "messages": [response],
                "agent_response": full_response,
                "stream_chunks": response_chunks,
                "has_tool_calls": any(chunk["type"] == "tool_result" for chunk in response_chunks)
            },
            next_node=None,
            should_continue=True,
            metadata={
                "node_type": "stream_react_agent",
                "total_chunks": len(response_chunks),
                "tool_calls_count": sum(1 for chunk in response_chunks if chunk["type"] == "tool_result")
            }
        )
    
    async def _stream_react_generation(self, messages: List[Message]) -> AsyncIterator[Dict[str, Any]]:
        """流式生成ReAct响应，检测Observation并调用工具"""
        # 委托给带深度控制的版本，初始深度为0
        async for chunk in self._stream_react_generation_with_depth(messages, 0):
            yield chunk
    
    async def _handle_tool_execution(self, accumulated_content: str, messages: List[Message], recursion_depth: int = 0) -> AsyncIterator[Dict[str, Any]]:
        """处理工具执行逻辑 - ZZZero分析版本"""
        # 防止递归过深
        if recursion_depth > 10:
            yield {
                "type": "tool_error",
                "content": "推理深度超过限制，停止进一步递归分析\n",
                "error": "递归深度超过最大限制"
            }
            return
        
        # 解析Action和Action Input
        parsed_content = self.react_parser.parse(accumulated_content)
        
        action = parsed_content.get('action')
        action_input = parsed_content.get('action_input')
        
        if action and self.tool_manager:
            # 调用MCP工具
            try:
                tool_result = await self._execute_tool(action.strip(), action_input.strip() if action_input else "")
                
                # ZZZero对工具结果进行分析和校验
                observation_analysis = await self._analyze_tool_result(
                    tool_name=action.strip(),
                    tool_input=action_input.strip() if action_input else "",
                    tool_result=tool_result,
                    context_content=accumulated_content
                )
                
                # 构造ZZZero风格的Observation结果
                observation_text = f" {observation_analysis}\n"
                
                # 发送工具结果
                yield {
                    "type": "tool_result",
                    "content": observation_text,
                    "tool_name": action.strip(),
                    "tool_input": action_input.strip() if action_input else "",
                    "tool_output": tool_result,
                    "analysis": observation_analysis,
                    "recursion_depth": recursion_depth
                }
                
                # 更新累积内容 - 将分析结果拼接到Observation后面
                updated_content = accumulated_content + observation_text
                
                # 继续生成，基于更新后的上下文
                messages_with_observation = messages.copy()
                messages_with_observation.append(Message(
                    role=MessageRole.ASSISTANT,
                    content=updated_content
                ))
                
                # 递归继续流式生成，传递递归深度
                async for next_chunk in self._stream_react_generation_with_depth(messages_with_observation, recursion_depth + 1):
                    yield next_chunk
                    
            except Exception as e:
                error_text = f"工具执行异常: {str(e)}\n"
                
                yield {
                    "type": "tool_error",
                    "content": error_text,
                    "error": str(e),
                    "recursion_depth": recursion_depth
                }
        else:
            # 没有找到有效的action或tool_manager
            yield {
                "type": "tool_error", 
                "content": "无法解析Action或工具管理器不可用\n",
                "error": "Action解析失败或工具管理器不可用",
                "parsed_action": action,
                "has_tool_manager": bool(self.tool_manager)
            }
    
    async def _stream_react_generation_with_depth(self, messages: List[Message], recursion_depth: int = 0) -> AsyncIterator[Dict[str, Any]]:
        """带递归深度控制的流式生成ReAct响应"""
        if recursion_depth > 10:
            yield {
                "type": "stream_error",
                "content": "\n推理深度超过限制，停止进一步分析\n",
                "error": "递归深度超过最大限制"
            }
            return
            
        accumulated_content = ""
        
        # 定义中断检查器，用于检测ReAct的Observation模式
        def should_interrupt_for_observation(content: str) -> bool:
            """检查是否应该因为空Observation而中断生成"""
            return self._should_trigger_tool_execution(content)
        
        # 开始流式生成
        try:
            # 使用doubao llm的中断机制进行流式生成
            async for chunk in self.llm.stream_generate(
                messages, 
                interrupt_checker=should_interrupt_for_observation
            ):
                accumulated_content += chunk
                
                # 发送文本块
                yield {
                    "type": "text_chunk",
                    "content": chunk,
                    "accumulated": accumulated_content,
                    "recursion_depth": recursion_depth
                }
                
                # 检查是否因为Observation而中断了
                if should_interrupt_for_observation(accumulated_content):
                    # 执行工具调用逻辑
                    async for tool_chunk in self._handle_tool_execution(accumulated_content, messages, recursion_depth):
                        yield tool_chunk
                    return
                            
        except Exception as e:
            yield {
                "type": "stream_error",
                "content": f"\n流式生成异常: {str(e)}\n",
                "error": str(e),
                "recursion_depth": recursion_depth
            }
    
    def _has_filled_observation(self, text: str) -> bool:
        """检查Observation是否已经有内容"""
        import re
        # 匹配 "Observation:" 后面有非空白内容
        pattern = r'Observation:\s*\S+'
        return bool(re.search(pattern, text))
    
    def _should_trigger_tool_execution(self, text: str) -> bool:
        """判断是否应该触发工具执行 - 检测空的Observation"""
        import re
        
        # 检查是否有Action和Action Input
        has_action = "Action:" in text
        has_action_input = "Action Input:" in text
        has_observation = "Observation:" in text
        
        # 只有当所有必要元素都存在时才考虑触发
        if not (has_action and has_action_input and has_observation):
            return False
        
        # 特殊情况：检查是否以"Observation:"结尾（正在等待工具执行）
        if text.rstrip().endswith("Observation:"):
            return True
        
        # 查找所有Observation的位置和内容，检查是否有空的Observation
        observation_matches = list(re.finditer(r'Observation:([^\n]*?)(?=\n|$)', text))
        
        for observation_match in observation_matches:
            observation_content = observation_match.group(1).strip()
            
            # 如果找到空的Observation，则应该触发工具执行
            if not observation_content:
                return True
        return False
    
    async def _execute_tool(self, tool_name: str, tool_input: str) -> str:
        """执行MCP工具（支持角色插件自动注入）"""
        if not self.tool_manager:
            return "错误：没有可用的工具管理器"
        
        # 使用基类的通用参数解析方法
        arguments = self.parse_tool_arguments(tool_input)
        
        # 调用工具 - 优先使用MCPToolManager的增强功能
        try:
            # 直接使用工具管理器执行工具
            print(f"[StreamReactAgentNode._execute_tool] 执行工具: {tool_name}")
            result = await self.tool_manager.execute_tool(tool_name, arguments)
            
            # 格式化结果
            if isinstance(result, dict):
                return json.dumps(result, ensure_ascii=False, indent=2)
            elif isinstance(result, (list, tuple)):
                return json.dumps(result, ensure_ascii=False, indent=2)
            else:
                return str(result)
                
        except Exception as e:
            return f"工具执行失败: {str(e)}"
    
    async def _analyze_tool_result(self, tool_name: str, tool_input: str, tool_result: str, context_content: str) -> str:
        """专业分析工具执行结果"""
        
        # 分析结果的基本信息
        result_length = len(tool_result)
        
        # 智能检测执行状态 - 优先解析JSON结构
        has_error = False
        is_json_result = False
        json_data = None
        
        try:
            # 尝试解析JSON结果
            json_data = json.loads(tool_result)
            is_json_result = True
            
            # 检查JSON结构中的成功/错误标志
            if isinstance(json_data, dict):
                # 优先检查success字段
                if "success" in json_data:
                    has_error = not json_data["success"]
                # 检查error字段是否为真值
                elif "error" in json_data:
                    has_error = bool(json_data["error"])
                # 检查status字段
                elif "status" in json_data:
                    has_error = json_data["status"] not in ["success", "ok", "200"]
                else:
                    # 没有明确标志，基于数据内容判断
                    has_error = False
            else:
                # 非字典类型的JSON，基本认为是成功的
                has_error = False
                
        except json.JSONDecodeError:
            # 非JSON结果，使用传统的文本检测
            has_error = ("错误" in tool_result or "失败" in tool_result or 
                        "error:" in tool_result.lower() or
                        "exception:" in tool_result.lower() or
                        tool_result.startswith("工具执行失败"))
        
        # 构建专业分析
        analysis_parts = ["正在分析工具执行结果..."]
        
        # 1. 执行状态分析
        if has_error:
            analysis_parts.append("⚠️ 工具执行遇到异常")
            if is_json_result and json_data:
                error_detail = json_data.get("error", json_data.get("message", "未知错误"))
                analysis_parts.append(f"错误详情: {error_detail}")
            else:
                analysis_parts.append(f"错误详情: {tool_result}")
        else:
            analysis_parts.append("✅ 工具执行成功")
            
            # 对成功结果进行详细分析
            if is_json_result and json_data:
                if isinstance(json_data, dict):
                    # 分析返回的数据结构
                    if "count" in json_data:
                        count = json_data["count"]
                        analysis_parts.append(f"📊 数据量: 返回{count}条记录")
                    
                    if "profiles" in json_data:
                        profiles = json_data["profiles"]
                        if profiles:
                            analysis_parts.append(f"👤 角色信息: 找到{len(profiles)}个角色档案")
                        else:
                            analysis_parts.append("👤 角色信息: 未找到匹配的角色")
                    
                    if "data" in json_data:
                        data = json_data["data"]
                        if isinstance(data, list):
                            analysis_parts.append(f"📋 数据集: {len(data)}个条目")
                        elif isinstance(data, dict):
                            analysis_parts.append("📋 结构化数据对象")
        
        # 2. 数据质量评估
        if result_length == 0:
            analysis_parts.append("📊 返回数据为空，可能需要调整参数")
        elif result_length < 50:
            analysis_parts.append("📊 返回简短结果，数据量较小")
        elif result_length > 1000:
            analysis_parts.append("📊 返回大量数据，信息丰富")
        else:
            analysis_parts.append("📊 返回适量数据")
        
        # 3. 结果类型分析
        if is_json_result:
            analysis_parts.append("🔍 结果为结构化JSON数据")
        elif tool_result.strip():
            if "\n" in tool_result:
                analysis_parts.append("🔍 结果为多行文本数据")
            else:
                analysis_parts.append("🔍 结果为单行文本数据")
        
        # 4. 基于上下文判断是否需要继续
        thought_count = context_content.count("Thought:")
        if thought_count >= 5:
            analysis_parts.append("🔄 已进行多轮分析，建议总结结论")
        elif has_error:
            analysis_parts.append("🔄 建议尝试其他工具或调整参数")
        elif "Final Answer" not in context_content:
            analysis_parts.append("🔄 可以基于此结果继续分析或给出最终答案")
        
        # 5. 分析完成状态
        analysis_parts.append("✨ 结果分析完成")
        
        # 6. 实际工具结果（简化显示，但对于角色信息要显示关键内容）
        if tool_name.startswith('role_info_') and is_json_result and json_data:
            # 角色信息工具的特殊处理
            if isinstance(json_data, dict) and "profiles" in json_data:
                profiles = json_data["profiles"]
                if profiles:
                    # 显示第一个角色的关键信息
                    first_profile = profiles[0]
                    key_info = []
                    for key in ["name", "age", "personality", "background", "description"]:
                        if key in first_profile:
                            value = first_profile[key]
                            if len(str(value)) > 100:
                                value = str(value)[:100] + "..."
                            key_info.append(f"{key}: {value}")
                    
                    analysis_parts.append(f"\n📋 角色档案预览:\n" + "\n".join(key_info))
                    
                    if len(profiles) > 1:
                        analysis_parts.append(f"（还有{len(profiles)-1}个相关角色档案）")
                else:
                    analysis_parts.append(f"\n📋 工具输出:\n{tool_result}")
            else:
                # 其他角色工具结果
                if len(tool_result) > 500:
                    display_result = tool_result[:500] + "...[结果已截断]"
                else:
                    display_result = tool_result
                analysis_parts.append(f"\n📋 工具输出:\n{display_result}")
        else:
            # 普通工具结果处理
            if len(tool_result) > 1000:
                display_result = tool_result[:1000] + "...[结果已截断]"
            else:
                display_result = tool_result
                
            analysis_parts.append(f"\n📋 工具输出:\n{display_result}")
        
        return "\n".join(analysis_parts)

    def _build_system_prompt(self, context: Any) -> str:
        """构建流式ReAct系统提示词 - 专业AI助手版本"""
        base_prompt = ""
        
        print(f"[StreamReactAgentNode._build_system_prompt] 开始构建")
        
        # 从上下文中获取记忆信息
        memory_context = ""
        if hasattr(context, 'variables') and context.variables:
            memory_context = context.variables.get("memory_context", "")
            print(f"[StreamReactAgentNode._build_system_prompt] 记忆上下文: {len(memory_context)}字符")
            
            # 检查是否有角色信息查询工具
            if self.tool_manager and hasattr(self.tool_manager, 'list_tools'):
                try:
                    available_tools = self.tool_manager.list_tools()
                    role_info_tools = [tool for tool in available_tools if tool.startswith('role_info_')]
                    if role_info_tools:
                        base_prompt += "=== 角色信息系统 ===\n"
                        base_prompt += "如需获取角色设定，请使用以下工具：\n"
                        base_prompt += "- role_info_query_profile: 查询角色人设\n"
                        base_prompt += "- role_info_search_knowledge: 搜索角色知识库\n"
                        base_prompt += "- role_info_get_role_context: 获取完整角色上下文\n\n"
                        print(f"[StreamReactAgentNode._build_system_prompt] 检测到{len(role_info_tools)}个角色信息工具")
                except Exception as e:
                    print(f"检查角色信息工具失败: {e}")
        
        # 添加记忆上下文
        if memory_context:
            base_prompt += f"=== 相关历史信息 ===\n{memory_context}\n\n"
        
        # 获取工具描述
        tools_desc = ""
        tool_names = []
        
        # 从工具管理器获取工具信息
        if self.tool_manager:
            tools_desc = self.tool_manager.get_tools_description()
            tool_names = self.tool_manager.list_tools()
            print(f"[StreamReactAgentNode._build_system_prompt] 工具: {tool_names}")
        
        # 专业AI助手ReAct提示词模板
        if tools_desc:
            base_prompt += "你是一个专业的AI助手，具备强大的推理和分析能力。你可以使用多种工具来帮助用户解决问题。\n\n"
            base_prompt += f"可用工具：\n{tools_desc}\n\n"
            base_prompt += "推理格式：\n"
            base_prompt += "Question: 用户提出的问题\n"
            base_prompt += "Thought: 对问题的分析和思考过程\n"
            base_prompt += f"Action: 选择执行的工具，必须是 [{', '.join(tool_names)}] 中的一个\n"
            base_prompt += "Action Input: 工具的输入参数\n"
            base_prompt += "Observation: 对工具执行结果的分析和评估\n"
            base_prompt += "... (可以重复这个推理循环，直到获得满意的结果)\n"
            base_prompt += "Thought: 基于所有信息的最终分析\n"
            base_prompt += "Final Answer: 给用户的最终专业回复\n\n"
            base_prompt += "工作原则：\n"
            base_prompt += "1. 📋 仔细分析用户问题，制定合理的解决方案\n"
            base_prompt += "2. 🛠️ 合理选择和使用工具获取所需信息\n"
            base_prompt += "3. 🔍 在Observation中深入分析工具结果的有效性和质量\n"
            base_prompt += "4. 🔄 如果信息不足或结果不满意，继续推理循环\n"
            base_prompt += "5. ✅ 确保回答完整、准确、有用\n"
            base_prompt += "6. 💡 充分利用历史信息提供连贯的服务\n"
            base_prompt += "7. 🎭 如需角色扮演，先获取角色设定，然后按照角色特征回应\n"
            base_prompt += "8. 📝 保持回复的专业性和简洁性\n\n"
            base_prompt += "现在准备为用户提供专业的AI助手服务。"
            print(f"[StreamReactAgentNode._build_system_prompt] 使用专业助手工具模板")
        else:
            base_prompt += "你是一个专业的AI助手，具备丰富的知识和分析能力。\n"
            base_prompt += "虽然当前没有外部工具可用，但我会基于我的知识库为你提供专业的帮助。\n"
            base_prompt += "如果问题超出我的知识范围，我会诚实地告知并建议其他解决方案。\n"
            base_prompt += "我会充分利用历史信息和上下文为你提供连贯、准确的回复。\n"
            base_prompt += "现在请告诉我你需要什么帮助。"
            print(f"[StreamReactAgentNode._build_system_prompt] 使用专业助手无工具模板")
        
        print(f"[StreamReactAgentNode._build_system_prompt] 完成，总长度: {len(base_prompt)}")
        return base_prompt

    async def stream_execute(self, input_data: NodeInput) -> AsyncIterator[Dict[str, Any]]:
        """流式执行方法 - 专门用于流式处理"""
        context = input_data.context
        
        # 获取对话历史
        messages = context.messages.copy()
        
        # 添加系统提示
        system_prompt = self._build_system_prompt(context)
        print(f"[StreamReactAgentNode.stream_execute] 系统提示词长度: {len(system_prompt)}")
        
        if not any(msg.role == MessageRole.SYSTEM for msg in messages):
            messages.insert(0, Message(
                role=MessageRole.SYSTEM,
                content=system_prompt
            ))
            print(f"[StreamReactAgentNode.stream_execute] 已添加系统提示词")
        else:
            print(f"[StreamReactAgentNode.stream_execute] 已存在系统提示词，跳过")
        
        # 直接进行流式生成
        async for chunk_data in self._stream_react_generation(messages):
            yield chunk_data 