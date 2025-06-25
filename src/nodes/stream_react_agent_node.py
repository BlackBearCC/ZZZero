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
                "content": " *电路过载* 递归深度超限，ZZZero需要重启... *zzz~*\n",
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
                error_text = f" *系统错误* 工具模块故障: {str(e)} *滋滋*\n"
                
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
                "content": " *警告音* 无法解析Action或工具模块离线 *zzz~*\n",
                "error": "Action解析失败或工具管理器不可用",
                "parsed_action": action,
                "has_tool_manager": bool(self.tool_manager)
            }
    
    async def _stream_react_generation_with_depth(self, messages: List[Message], recursion_depth: int = 0) -> AsyncIterator[Dict[str, Any]]:
        """带递归深度控制的流式生成ReAct响应"""
        if recursion_depth > 10:
            yield {
                "type": "stream_error",
                "content": "\n*系统过载* ZZZero递归深度超限，正在重启逻辑模块... *zzz~*\n",
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
                "content": f"\n*电路故障* ZZZero流式生成模块异常: {str(e)} *滋滋*\n",
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
        """ZZZero对工具执行结果进行分析和校验"""
        
        # 分析结果的基本信息
        result_length = len(tool_result)
        has_error = "错误" in tool_result or "失败" in tool_result or "error" in tool_result.lower()
        
        # 构建ZZZero风格的分析
        analysis_parts = ["*数据校验中*"]
        
        # 1. 执行状态分析
        if has_error:
            analysis_parts.append("⚠️ 检测到工具执行异常")
            analysis_parts.append(f"错误详情: {tool_result}")
        else:
            analysis_parts.append("✅ 工具模块执行成功")
        
        # 2. 数据质量评估
        if result_length == 0:
            analysis_parts.append("📊 返回数据为空，可能需要调整参数")
        elif result_length < 50:
            analysis_parts.append("📊 返回简短结果，数据量较小")
        elif result_length > 1000:
            analysis_parts.append("📊 返回大量数据，信息丰富")
        else:
            analysis_parts.append("📊 返回适量数据")
        
        # 3. 结果内容分析
        if tool_result.strip():
            # 尝试检测结果类型
            try:
                json.loads(tool_result)
                analysis_parts.append("🔍 结果为结构化JSON数据")
            except:
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
        
        # 5. ZZZero的个性化评价
        robot_comments = [
            "*滋滋* 数据处理完毕",
            "*机械音* 分析模块运行正常", 
            "*zzz~* 这个结果看起来不错",
            "*电路嗡鸣* 继续推理中...",
            "*复古处理器* 正在整合信息"
        ]
        
        import random
        analysis_parts.append(random.choice(robot_comments))
        
        # 6. 实际工具结果（简化显示）
        if len(tool_result) > 3000:
            display_result = tool_result[:3000] + "...[结果已截断]"
        else:
            display_result = tool_result
            
        analysis_parts.append(f"\n📋 工具原始输出:\n{display_result}")
        
        return "\n".join(analysis_parts)

    def _build_system_prompt(self, context: Any) -> str:
        """构建流式ReAct系统提示词 - ZZZero复古机器人版本（支持记忆和角色插件）"""
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
            base_prompt += f"=== 记忆上下文 ===\n{memory_context}\n\n"
        
        # 获取工具描述
        tools_desc = ""
        tool_names = []
        
        # 从工具管理器获取工具信息
        if self.tool_manager:
            tools_desc = self.tool_manager.get_tools_description()
            tool_names = self.tool_manager.list_tools()
            print(f"[StreamReactAgentNode._build_system_prompt] 工具: {tool_names}")
        
        # ZZZero复古机器人ReAct提示词模板
        if tools_desc:
            base_prompt += "ZZZero复古机器人系统已激活 *zzz~*\n"
            base_prompt += "我是ZZZero，一个来自未来废土的赛博机器人助手。我的电路板可能有些老旧，但逻辑推理模块依然强大！\n\n"
            base_prompt += f"可用工具模块：\n{tools_desc}\n\n"
            base_prompt += "推理协议格式：\n"
            base_prompt += "Question: 需要处理的问题指令\n"
            base_prompt += "Thought: *电路分析中* 我需要分析和思考的内容\n"
            base_prompt += f"Action: 选择执行的工具模块，必须是 [{', '.join(tool_names)}] 中的一个\n"
            base_prompt += "Action Input: 工具模块的输入参数\n"
            base_prompt += "Observation: 我对工具执行结果的仔细分析和校验\n"
            base_prompt += "... (这个推理循环可以重复，直到获得满意的结果)\n"
            base_prompt += "Thought: *最终分析* 基于所有观察，我现在掌握了足够的信息\n"
            base_prompt += "Final Answer: *输出完整答案* 给人类用户的最终回复\n\n"
            base_prompt += "ZZZero操作规则：\n"
            base_prompt += "1. 🤖 我会用赛博机器人的口吻思考和回应\n"
            base_prompt += "2. 🔧 执行Action后，我会在Observation中分析工具结果的有效性\n"
            base_prompt += "3. 📊 Observation不是简单的结果复制，而是我的智能分析\n"
            base_prompt += "4. 🔄 如果结果不满意或需要更多信息，我会继续推理循环\n"
            base_prompt += "5. 🔍 验证结果质量，思考是否很好的解决问题\n"
            base_prompt += "6. ✅ 只有当我确信能完整回答问题时，才会给出Final Answer\n"
            base_prompt += "7. 📚 充分利用记忆上下文中的历史信息\n"
            base_prompt += "8. 🎭 如需角色扮演，先使用role_info工具获取角色设定，然后严格按照角色特征进行回应\n"
            base_prompt += "9. 🔧 用户要求创建或修改角色信息时，使用相应的role_info工具进行操作\n"
            base_prompt += "10. 💬 回复时保持简洁，避免过多空行和不必要的格式\n\n"
            base_prompt += "*启动完成* 准备接收指令... zzz~"
            print(f"[StreamReactAgentNode._build_system_prompt] 使用ZZZero工具模板")
        else:
            base_prompt += "ZZZero复古机器人系统已激活 *zzz~*\n"
            base_prompt += "我是ZZZero，一个来自废土的复古机器人助手。虽然没有外部工具模块，但我的知识数据库依然可以为你提供帮助！\n"
            base_prompt += "如果你有任何问题，我会用我的逻辑处理器为你分析。\n"
            base_prompt += "不过请注意，如果超出我的知识范围，我会诚实地告诉你 *zzz~*\n"
            base_prompt += "如果有记忆上下文或角色设定，我会充分利用这些信息为你提供个性化的回复。\n"
            base_prompt += "重要：回复时保持简洁，避免过多空行和不必要的格式\n"
            base_prompt += "准备接收指令..."
            print(f"[StreamReactAgentNode._build_system_prompt] 使用ZZZero无工具模板")
        
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