"""
流式ReAct Agent节点 - 支持流式输出和Observation检测
"""
import sys
import os
import re
import json
import asyncio
import logging
from typing import Dict, Any, List, AsyncIterator, Optional

# 设置日志记录器
logger = logging.getLogger(__name__)

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
        logger.info(f"流式ReAct Agent节点执行完成，响应内容：{full_response}")
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
        """带递归深度控制的流式生成ReAct响应 - 使用DeepSeek R1推理"""
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
        
        # 开始流式生成 - 使用推理模式
        try:
            # 检查LLM是否支持推理功能
            if hasattr(self.llm, 'stream_think'):
                # 使用DeepSeek R1推理模式
                reasoning_phase = True
                reasoning_content = ""
                
                async for chunk_data in self.llm.stream_think(messages):
                    chunk_type = chunk_data.get("type")
                    
                    if chunk_type == "reasoning_chunk":
                        # 推理过程输出 - ZZZero风格展示
                        reasoning_chunk = chunk_data.get("content", "")
                        reasoning_content += reasoning_chunk
                        
                        # 格式化推理过程显示
                        if reasoning_phase:
                            yield {
                                "type": "reasoning_chunk",
                                "content": f"*ZZZero思考中* {reasoning_chunk}",
                                "accumulated": reasoning_content,
                                "recursion_depth": recursion_depth
                            }
                    
                    elif chunk_type == "content_chunk":
                        # 最终答案输出
                        reasoning_phase = False
                        content_chunk = chunk_data.get("content", "")
                        accumulated_content += content_chunk
                        
                        # 发送内容块
                        yield {
                            "type": "text_chunk",
                            "content": content_chunk,
                            "accumulated": accumulated_content,
                            "recursion_depth": recursion_depth
                        }
                        
                        # 检查是否因为Observation而中断了
                        if should_interrupt_for_observation(accumulated_content):
                            # 执行工具调用逻辑
                            async for tool_chunk in self._handle_tool_execution(accumulated_content, messages, recursion_depth):
                                yield tool_chunk
                            return
                    
                    elif chunk_type == "think_complete":
                        # 推理完成
                        final_reasoning = chunk_data.get("reasoning_content", "")
                        final_content = chunk_data.get("content", "")
                        
                        # 如果有推理内容，展示推理总结
                        if final_reasoning and final_reasoning != reasoning_content:
                            yield {
                                "type": "reasoning_summary",
                                "content": f"\n*ZZZero推理总结* 经过 {len(final_reasoning)} 字符的深度思考 *zzz~*\n",
                                "reasoning_length": len(final_reasoning),
                                "recursion_depth": recursion_depth
                            }
                        
                        # 最终检查是否需要工具执行
                        if should_interrupt_for_observation(final_content):
                            async for tool_chunk in self._handle_tool_execution(final_content, messages, recursion_depth):
                                yield tool_chunk
                        
                        break
            else:
                # 回退到标准流式生成（兼容性）
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
        """执行MCP工具"""
        if not self.tool_manager:
            return "错误：没有可用的工具管理器"
        
        # 使用基类的通用参数解析方法
        arguments = self.parse_tool_arguments(tool_input)
        
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
            analysis_parts.append(f"错误详情: {tool_result[:200]}...")
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
        """构建流式ReAct系统提示词 - ZZZero复古机器人版本（DeepSeek R1优化）"""
        # 获取工具描述
        tools_desc = ""
        tool_names = []
        
        # 从工具管理器获取工具信息
        if self.tool_manager:
            tools_desc = self.tool_manager.get_tools_description()
            tool_names = self.tool_manager.list_tools()
        
        # 检查是否支持推理功能
        has_reasoning = hasattr(self.llm, 'stream_think')
        
        # ZZZero复古机器人ReAct提示词模板 - DeepSeek R1优化版本
        if tools_desc:
            base_prompt = f"""我是ZZZero，一个来自未来废土的复古机器人助手。我的电路板可能有些老旧，但逻辑推理模块依然强大！

可用工具模块：
{tools_desc}

ZZZero推理协议格式：

Question: 需要处理的问题指令
Thought: 我需要分析和思考的内容
Action: 选择执行的工具模块，必须是 [{', '.join(tool_names)}] 中的一个
Action Input: 工具模块的输入参数
Observation: 我对工具执行结果的分析和校验：
  - 结果是否符合预期？
  - 数据质量如何？
  - 是否需要进一步处理？
  - 这个结果对解决问题有什么帮助？
... (这个推理循环可以重复，直到获得满意的结果)
Thought: 基于所有观察，我现在掌握了足够的信息
Final Answer: 给人类用户的最终回复

*机械提示音* ZZZero操作规则：
1. 🤖 我会用复古机器人的口吻思考和回应
2. 🔧 执行Action后，我会在Observation中分析工具结果的有效性
3. 📊 Observation不是简单的结果复制，而是我的智能分析
4. 🔄 如果结果不满意或需要更多信息，我会继续推理循环
5. ✅ 只有当我确信能完整回答问题时，才会给出Final Answer
6. *zzz~* 偶尔会有一些机器人特有的音效和表达"""

            # 如果支持推理功能，添加推理相关指导
            if has_reasoning:
                base_prompt += """

*DeepSeek R1推理增强模式* 
7. 🧠 我具备深度推理能力，会在内部进行复杂的逻辑分析
8. 💭 推理过程会帮助我更好地理解问题和制定解决方案
9. 🎯 我会充分利用推理能力来优化Action选择和结果分析
10. ⚡ 推理过程不会直接显示给用户，但会提升我的回答质量"""

            base_prompt += "\n\n*Zzz* 启动完成* 准备接收指令... zzz~"
            
        else:
            base_prompt = """我是ZZZero，一个来自废土的复古机器人助手。虽然没有外部工具模块，
但我的知识数据库依然可以为你提供帮助！"""

            # 如果支持推理功能，提及推理能力
            if has_reasoning:
                base_prompt += """

*DeepSeek R1推理增强模式已激活*
我具备强大的逻辑推理能力，能够：
- 深度分析复杂问题
- 进行多步骤逻辑推导  
- 自我验证和反思
- 提供更准确的答案

虽然没有工具模块，但我会充分发挥推理优势为你解答问题。"""

            base_prompt += """
如果你有任何问题，我会用我的逻辑处理器为你分析。
不过请注意，如果超出我的知识范围，我会诚实地告诉你 *zzz~*

准备接收指令..."""
        
        return base_prompt 