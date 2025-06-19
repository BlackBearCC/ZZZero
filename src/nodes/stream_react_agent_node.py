"""
流式ReAct Agent节点 - 支持流式输出和Observation检测
"""
import sys
import os
import re
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
            'action_input': r'Action Input:\s*([^\n]+)', 
            'thought': r'Thought:\s*([^\n]+)',
            'observation': r'Observation:\s*([^\n]+)'
        })
        
    async def execute(self, input_data: NodeInput) -> NodeOutput:
        """执行流式ReAct推理逻辑"""
        context = input_data.context
        
        # 获取对话历史
        messages = context.messages.copy()
        
        # 添加系统提示
        system_prompt = self._build_system_prompt(context)
        if not any(msg.role == MessageRole.SYSTEM for msg in messages):
            messages.insert(0, Message(
                role=MessageRole.SYSTEM,
                content=system_prompt
            ))
        
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
        accumulated_content = ""
        
        # 定义中断检查器，用于检测ReAct的Observation模式
        def should_interrupt_for_observation(content: str) -> bool:
            """检查是否应该因为空Observation而中断生成"""
            return self._should_trigger_tool_execution(content)
        
        # 开始流式生成
        try:
            # 检查LLM是否支持中断机制
            if hasattr(self.llm, 'stream_generate_with_interrupt'):
                # 使用支持中断的流式生成
                async for chunk in self.llm.stream_generate_with_interrupt(
                    messages, 
                    interrupt_checker=should_interrupt_for_observation
                ):
                    accumulated_content += chunk
                    
                    # 发送文本块
                    yield {
                        "type": "text_chunk",
                        "content": chunk,
                        "accumulated": accumulated_content
                    }
                    
                    # 检查是否因为Observation而中断了
                    if should_interrupt_for_observation(accumulated_content):
                        # 执行工具调用逻辑
                        async for tool_chunk in self._handle_tool_execution(accumulated_content, messages):
                            yield tool_chunk
                        return
            else:
                # 回退到原有的实现
                async for chunk in self.llm.stream_generate(messages):
                    accumulated_content += chunk
                    
                    # 发送文本块
                    yield {
                        "type": "text_chunk",
                        "content": chunk,
                        "accumulated": accumulated_content
                    }
                    
                    # 检测是否包含Observation:标记且没有实际观察内容
                    if "Observation:" in accumulated_content and not self._has_filled_observation(accumulated_content):
                        # 检查是否在当前块结束时有完整的Action和Action Input
                        if self._should_trigger_tool_execution(accumulated_content):
                            async for tool_chunk in self._handle_tool_execution(accumulated_content, messages):
                                yield tool_chunk
                            return
                            
        except Exception as e:
            yield {
                "type": "stream_error",
                "content": f"\n[流式生成错误: {str(e)}]\n",
                "error": str(e)
            }
    
    async def _handle_tool_execution(self, accumulated_content: str, messages: List[Message]) -> AsyncIterator[Dict[str, Any]]:
        """处理工具执行逻辑"""
        # 解析Action和Action Input
        parsed_content = self.react_parser.parse(accumulated_content)
        
        action = parsed_content.get('action')
        action_input = parsed_content.get('action_input')
        
        if action and self.tool_manager:
            # 调用MCP工具
            try:
                tool_result = await self._execute_tool(action.strip(), action_input.strip() if action_input else "")
                
                # 构造Observation结果，替换空的Observation
                observation_text = f" {tool_result}\n"
                
                # 发送工具结果
                yield {
                    "type": "tool_result",
                    "content": observation_text,
                    "tool_name": action.strip(),
                    "tool_input": action_input.strip() if action_input else "",
                    "tool_output": tool_result
                }
                
                # 更新累积内容
                accumulated_content += observation_text
                
                # 继续生成，基于新的上下文
                messages_with_observation = messages.copy()
                messages_with_observation.append(Message(
                    role=MessageRole.ASSISTANT,
                    content=accumulated_content
                ))
                
                # 递归继续流式生成
                async for next_chunk in self._stream_react_generation(messages_with_observation):
                    yield next_chunk
                    
            except Exception as e:
                error_text = f" 工具执行错误: {str(e)}\n"
                
                yield {
                    "type": "tool_error",
                    "content": error_text,
                    "error": str(e)
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
        
        # 查找最后一个Observation的位置和内容
        observation_matches = list(re.finditer(r'Observation:\s*([^\n]*)', text))
        
        if observation_matches:
            last_observation = observation_matches[-1]
            observation_content = last_observation.group(1).strip()
            
            # 如果最后一个Observation后面没有实际内容，则应该触发工具执行
            if not observation_content:
                # 检查Observation后面是否有其他内容（如新的Thought、Final Answer等）
                observation_end = last_observation.end()
                remaining_text = text[observation_end:].strip()
                
                # 如果Observation后面没有内容，或者只有少量空白字符，则触发
                if not remaining_text or len(remaining_text) < 3:
                    return True
        
        # 特殊情况：检查是否以"Observation:"结尾（正在等待工具执行）
        if text.rstrip().endswith("Observation:"):
            return True
            
        return False
    
    async def _execute_tool(self, tool_name: str, tool_input: str) -> str:
        """执行MCP工具"""
        if not self.tool_manager:
            return "错误：没有可用的工具管理器"
        
        # 解析工具输入参数
        try:
            # 尝试将tool_input解析为字典
            import json
            if tool_input.strip().startswith('{'):
                arguments = json.loads(tool_input)
            else:
                # 如果不是JSON，将其作为单个参数
                arguments = {"input": tool_input}
        except:
            arguments = {"input": tool_input}
        
        # 调用工具
        try:
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
    
    def _build_system_prompt(self, context: Any) -> str:
        """构建流式ReAct系统提示词"""
        # 获取工具描述
        tools_desc = ""
        tool_names = []
        
        # 从工具管理器获取工具信息
        if self.tool_manager:
            tools_desc = self.tool_manager.get_tools_description()
            tool_names = self.tool_manager.list_tools()
        
        # 流式ReAct提示词模板
        if tools_desc:
            return f"""你是一个基于ReAct（Reasoning and Acting）范式的智能助手，支持流式输出。

可用工具：
{tools_desc}

使用以下格式进行推理和行动：

Question: 你需要回答的问题
Thought: 你应该思考要做什么
Action: 要采取的行动，应该是 [{', '.join(tool_names)}] 中的一个
Action Input: 行动的输入
Observation: 行动的结果（此处会自动填入工具执行结果）
... (这个 Thought/Action/Action Input/Observation 可以重复N次)
Thought: 我现在知道最终答案了
Final Answer: 对原始问题的最终答案

重要规则：
1. 当你输出"Action:"和"Action Input:"后，系统会自动执行工具并在"Observation:"后填入结果
2. 不要自己编写Observation的内容，系统会自动填充
3. 基于Observation的结果继续你的推理
4. 如果有足够信息，给出Final Answer

开始！"""
        else:
            return """你是一个智能助手，支持流式输出。

请根据你的知识回答用户的问题。
如果你不确定答案，请诚实地说明你不知道。
请提供清晰、有帮助的回复。""" 