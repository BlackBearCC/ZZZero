# -*- coding: utf-8 -*-
"""
ReactAgent实现 - 基于标准Reasoning and Acting循环

@author leo
@description 实现标准的ReactAgent架构，采用Thought->Action->Observation循环，擅长调用工具解决复杂问题
@classes ReactAgent - 标准ReactAgent实现类
@functions run, stream_run - 核心执行方法
@example 
    agent = ReactAgent(llm, tool_manager)
    result = await agent.run("帮我搜索北京的天气")
@dependencies src.core.base, src.llm.base, src.tools.base
"""

import uuid
import json
import asyncio
import time
from typing import Dict, Any, Optional, List, AsyncIterator, Union
from datetime import datetime

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.base import BaseAgent, BaseNode, Command
from core.types import AgentType, TaskResult, Message, MessageRole, NodeType
from llm.base import BaseLLMProvider
from tools.base import ToolManager

# 添加MCPToolManager的导入（避免循环导入）
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from tools.mcp_tools import MCPToolManager


class ReactLoop:
    """标准React循环状态管理"""
    
    def __init__(self, max_iterations: int = 10):
        self.max_iterations = max_iterations
        self.current_iteration = 0
        self.thoughts = []
        self.actions = []
        self.observations = []
        self.is_complete = False
        self.final_answer = ""
        self.empty_thought_count = 0  # 追踪空思考次数
        
    def add_thought(self, thought: str) -> None:
        """添加思考过程"""
        self.thoughts.append({
            "iteration": self.current_iteration,
            "content": thought,
            "timestamp": datetime.now().isoformat()
        })
        
    def add_action(self, action: Dict[str, Any]) -> None:
        """添加行动记录"""
        self.actions.append({
            "iteration": self.current_iteration,
            "action": action,
            "timestamp": datetime.now().isoformat()
        })
        
    def add_observation(self, observation: str) -> None:
        """添加观察结果"""
        self.observations.append({
            "iteration": self.current_iteration,
            "content": observation,
            "timestamp": datetime.now().isoformat()
        })
        
    def should_continue(self) -> bool:
        """判断是否应该继续循环"""
        return (not self.is_complete and 
                self.current_iteration < self.max_iterations)
        
    def next_iteration(self) -> None:
        """进入下一轮迭代"""
        self.current_iteration += 1
        
    def complete(self, final_answer: str) -> None:
        """完成循环"""
        self.is_complete = True
        self.final_answer = final_answer


class NodeInfoStream:
    """节点信息流系统 - 收集和分发节点执行信息"""
    
    def __init__(self):
        self.events = []
        self.callbacks = []
        
    def emit(self, event_type: str, node_name: str, content: str, metadata: Dict[str, Any] = None):
        """发射事件到信息流"""
        event = {
            "type": event_type,
            "node_name": node_name, 
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat()
        }
        self.events.append(event)
        
        # 通知所有回调
        for callback in self.callbacks:
            try:
                callback(event)
            except Exception as e:
                print(f"InfoStream callback error: {e}")
    
    def add_callback(self, callback):
        """添加事件回调"""
        self.callbacks.append(callback)
        
    def get_events(self) -> List[Dict[str, Any]]:
        """获取所有事件"""
        return self.events.copy()


class ReactAgent(BaseAgent):
    """ReactAgent - 标准Reasoning and Acting循环实现"""
    
    def __init__(self,
                 llm: BaseLLMProvider,
                 tool_manager: Optional[Union[ToolManager, 'MCPToolManager']] = None,
                 max_iterations: int = 10,
                 name: Optional[str] = None,
                 **kwargs):
        """
        初始化ReactAgent
        
        Args:
            llm: LLM提供者
            tool_manager: 工具管理器
            max_iterations: 最大循环迭代次数
            name: Agent名称
        """
        super().__init__(
            agent_type=AgentType.REACT,
            name=name or "react_agent",
            description="标准ReactAgent - 基于Thought->Action->Observation循环",
            **kwargs
        )
        self.llm = llm
        self.tool_manager = tool_manager
        self.max_iterations = max_iterations
        self.info_stream = NodeInfoStream()
        
    def _build_react_prompt(self, query: str, available_tools: List[str], 
                           context_history: str = "") -> str:
        """构建标准React提示词"""
        tools_description = ""
        if self.tool_manager and available_tools:
            tools_description = self.tool_manager.get_tools_description()
        
        prompt = f"""你是一个使用ReAct方法的AI助手，需要通过思考-行动-观察的循环来解决问题。

你可以使用以下工具：
{tools_description if tools_description else "无可用工具"}

严格按照以下格式进行推理，每个部分都必须有具体内容：

示例1 - 简单问题：
Thought: 用户问的是"你好"，这是一个简单的问候，我可以直接回应。
Final Answer: 你好！我是AI助手，很高兴为您服务。有什么我可以帮助您的吗？

示例2 - 复杂问题：
Thought: 用户询问天气信息，我需要使用天气查询工具来获取准确信息。
Action: get_weather(city="北京")
Observation: [系统返回天气数据]
Thought: 根据获取的天气数据，我现在可以给出完整的天气信息。
Final Answer: 根据最新数据，北京今天...

关键要求：
1. Thought后面必须写具体的思考内容，不能为空
2. 要么给出Final Answer，要么执行Action
3. 如果执行Action，必须等待Observation再继续
4. 每次Thought都要有实质性的分析内容

当前任务: {query}

{context_history}

现在开始，请写出具体的思考内容："""
        return prompt
        
    def _parse_react_response(self, response: str) -> Dict[str, Any]:
        """解析React格式的响应 - 智能解析，容错性强"""
        lines = response.strip().split('\n')
        current_thought = ""
        current_action = None
        final_answer = ""
        
        # 查找第一个有意义的Thought行
        thought_found = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith("Thought:"):
                current_thought = line[8:].strip()
                thought_found = True
            elif line.startswith("Action:"):
                action_text = line[7:].strip()
                current_action = self._parse_action(action_text)
            elif line.startswith("Final Answer:"):
                final_answer = line[13:].strip()
            elif not thought_found and not line.startswith(("Action:", "Observation:", "Final Answer:")):
                # 如果还没找到Thought行，且这行不是其他关键字，可能是隐含的思考内容
                current_thought = line
                thought_found = True
                
        # 检查是否有空的思考
        has_empty_thought = thought_found and not current_thought.strip()
        
        return {
            "thought": current_thought,
            "action": current_action,
            "final_answer": final_answer,
            "has_final_answer": bool(final_answer),
            "has_empty_thought": has_empty_thought
        }
        
    def _parse_action(self, action_text: str) -> Optional[Dict[str, Any]]:
        """解析动作文本"""
        try:
            # 尝试解析 tool_name(param1=value1, param2=value2) 格式
            if '(' in action_text and ')' in action_text:
                tool_name = action_text.split('(')[0].strip()
                params_text = action_text.split('(')[1].rsplit(')', 1)[0]
                
                parameters = {}
                if params_text.strip():
                    # 简单解析参数
                    param_pairs = params_text.split(',')
                    for pair in param_pairs:
                        if '=' in pair:
                            key, value = pair.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"\'')
                            parameters[key] = value
                
                return {
                    "tool_name": tool_name,
                    "parameters": parameters
                }
            else:
                # 简单工具名
                return {
                    "tool_name": action_text,
                    "parameters": {}
                }
        except Exception as e:
            print(f"解析动作失败: {e}, action_text: {action_text}")
            return None
            
    async def _execute_action(self, action: Dict[str, Any]) -> str:
        """执行动作并返回观察结果"""
        if not self.tool_manager:
            return "错误：没有可用的工具管理器"
            
        tool_name = action.get("tool_name", "")
        parameters = action.get("parameters", {})
        
        try:
            result = await self.tool_manager.execute_tool(tool_name, parameters)
            return f"工具 {tool_name} 执行成功：{result}"
        except Exception as e:
            return f"工具 {tool_name} 执行失败：{str(e)}"
            
    async def run(self, query: str, context: Optional[Dict[str, Any]] = None) -> TaskResult:
        """运行标准ReactAgent"""
        task_id = str(uuid.uuid4())
        
        result = TaskResult(
            task_id=task_id,
            query=query,
            agent_type=self.agent_type
        )
        
        try:
            # 初始化
            await self.initialize()
            
            # 获取可用工具
            available_tools = []
            if self.tool_manager:
                available_tools = self.tool_manager.list_tools()
                
            # 初始化React循环
            react_loop = ReactLoop(self.max_iterations)
            
            # 构建初始消息
            messages = [Message(role=MessageRole.USER, content=query)]
            context_history = ""
            
            self.info_stream.emit("agent_start", "react_agent", f"开始处理任务: {query}")
            
            # 标准React循环
            while react_loop.should_continue():
                # 构建当前上下文
                current_context = self._build_context_history(react_loop)
                system_prompt = self._build_react_prompt(query, available_tools, current_context)
                
                self.info_stream.emit("iteration_start", "react_loop", 
                                    f"开始第 {react_loop.current_iteration + 1} 轮循环")
                
                # 思考阶段
                self.info_stream.emit("node_start", "thought", "开始思考...")
                response = await self.llm.generate(messages, system_prompt=system_prompt)
                response_text = response.content if hasattr(response, 'content') else str(response)
                
                # 解析响应
                parsed = self._parse_react_response(response_text)
                
                # 检查是否有空思考
                if parsed.get("has_empty_thought", False):
                    react_loop.empty_thought_count += 1
                    self.info_stream.emit("error", "react_agent", f"检测到空思考（第{react_loop.empty_thought_count}次），重新引导")
                    
                    # 如果空思考次数过多，直接结束
                    if react_loop.empty_thought_count >= 3:
                        final_answer = f"抱歉，我在思考您的问题时遇到了困难。您的问题是：{query}。请尝试重新描述问题或提供更多上下文信息。"
                        react_loop.complete(final_answer)
                        result.result = final_answer
                        result.success = True
                        break
                    
                    guidance = f"请重新回答，在'Thought:'后面必须写出具体的思考内容。例如：\nThought: 我需要分析用户的问题：{query}。这个问题需要..."
                    messages.append(Message(role=MessageRole.USER, content=guidance))
                    react_loop.next_iteration()
                    continue
                
                if parsed["has_final_answer"]:
                    # 得到最终答案
                    react_loop.complete(parsed["final_answer"])
                    self.info_stream.emit("final_answer", "react_agent", parsed["final_answer"])
                    result.result = parsed["final_answer"]
                    result.success = True
                    break
                    
                # 记录思考
                if parsed["thought"]:
                    react_loop.add_thought(parsed["thought"])
                    self.info_stream.emit("thought", "thought", parsed["thought"])
                    
                # 执行动作
                if parsed["action"]:
                    self.info_stream.emit("action", "action", 
                                        f"执行动作: {parsed['action']['tool_name']}")
                    react_loop.add_action(parsed["action"])
                    
                    # 执行工具
                    observation = await self._execute_action(parsed["action"])
                    react_loop.add_observation(observation)
                    self.info_stream.emit("observation", "observation", observation)
                    
                    # 将观察结果添加到消息历史
                    messages.append(Message(role=MessageRole.ASSISTANT, content=response_text))
                    messages.append(Message(role=MessageRole.USER, content=f"Observation: {observation}"))
                else:
                    # 没有动作但有思考，继续下一轮
                    if parsed["thought"]:
                        messages.append(Message(role=MessageRole.ASSISTANT, content=response_text))
                    else:
                        # 既没有动作也没有思考，可能需要引导
                        guidance = "请继续思考问题并确定下一步行动，或者给出最终答案。"
                        messages.append(Message(role=MessageRole.ASSISTANT, content=response_text))
                        messages.append(Message(role=MessageRole.USER, content=guidance))
                        
                react_loop.next_iteration()
                
            # 如果循环结束但没有最终答案，尝试生成总结
            if not react_loop.is_complete:
                if react_loop.thoughts:
                    # 基于已有思考生成总结
                    summary_prompt = "根据以上的思考过程，请提供一个总结性的答案。如果无法得出确定结论，请说明原因并建议下一步行动。"
                    messages.append(Message(role=MessageRole.USER, content=summary_prompt))
                    
                    try:
                        summary_response = await self.llm.generate(messages, system_prompt="请基于之前的思考过程提供一个清晰的总结答案。")
                        summary_text = summary_response.content if hasattr(summary_response, 'content') else str(summary_response)
                        final_answer = summary_text.strip()
                    except Exception as e:
                        final_answer = f"思考过程中遇到问题: {str(e)}。建议重新描述问题或提供更多信息。"
                else:
                    # 没有任何思考过程
                    final_answer = "未能开始有效的思考过程。请检查问题描述或提供更明确的指导。"
                    
                react_loop.complete(final_answer)
                result.result = final_answer
                result.success = True
                
            self.info_stream.emit("agent_complete", "react_agent", "任务完成")
            
            # 构建执行轨迹
            result.execution_trace = [{
                "iterations": react_loop.current_iteration,
                "thoughts": len(react_loop.thoughts),
                "actions": len(react_loop.actions),
                "observations": len(react_loop.observations)
            }]
            
            result.metadata = {
                "react_loop": {
                    "thoughts": react_loop.thoughts,
                    "actions": react_loop.actions, 
                    "observations": react_loop.observations
                },
                "info_stream_events": self.info_stream.get_events()
            }
            
        except Exception as e:
            result.result = f"执行失败: {str(e)}"
            result.success = False
            self.info_stream.emit("error", "react_agent", str(e))
            
        return result
        
    async def stream_run(self, query: str, context: Optional[Dict[str, Any]] = None) -> AsyncIterator[Dict[str, Any]]:
        """流式运行ReactAgent"""
        task_id = str(uuid.uuid4())
        
        # 设置流式回调
        async def stream_callback(event):
            yield {
                "type": "info_stream",
                "event_type": event["type"],
                "node_name": event["node_name"],
                "content": event["content"],
                "metadata": event["metadata"],
                "task_id": task_id
            }
            
        self.info_stream.add_callback(stream_callback)
        
        try:
            yield {"type": "start", "content": "开始ReactAgent执行...", "task_id": task_id}
            
            # 初始化
            await self.initialize()
            
            # 获取可用工具
            available_tools = []
            if self.tool_manager:
                available_tools = self.tool_manager.list_tools()
                
            # 初始化React循环
            react_loop = ReactLoop(self.max_iterations)
            
            # 构建初始消息
            messages = [Message(role=MessageRole.USER, content=query)]
            
            # 标准React循环
            while react_loop.should_continue():
                # 构建当前上下文
                current_context = self._build_context_history(react_loop)
                system_prompt = self._build_react_prompt(query, available_tools, current_context)
                
                yield {
                    "type": "text_chunk",
                    "content": f"\n\n--- 迭代 {react_loop.current_iteration + 1} ---\n",
                    "task_id": task_id
                }
                
                # 思考阶段 - 流式输出
                yield {
                    "type": "text_chunk", 
                    "content": "**Thought**: ",
                    "task_id": task_id
                }
                
                thought_content = ""
                async for chunk in self.llm.stream_generate(messages, system_prompt=system_prompt):
                    if hasattr(chunk, 'content') and chunk.content:
                        thought_content += chunk.content
                        yield {
                            "type": "text_chunk",
                            "content": chunk.content,
                            "task_id": task_id
                        }
                
                # 解析响应
                parsed = self._parse_react_response(thought_content)
                
                # 检查是否有空思考
                if parsed.get("has_empty_thought", False):
                    react_loop.empty_thought_count += 1
                    yield {
                        "type": "text_chunk",
                        "content": f"\n❌ 检测到空思考（第{react_loop.empty_thought_count}次）",
                        "task_id": task_id
                    }
                    
                    # 如果空思考次数过多，直接结束
                    if react_loop.empty_thought_count >= 3:
                        final_answer = f"抱歉，我在思考您的问题时遇到了困难。请尝试重新描述问题或提供更多上下文信息。"
                        yield {
                            "type": "text_chunk",
                            "content": f"\n\n**Final Answer**: {final_answer}",
                            "task_id": task_id
                        }
                        react_loop.complete(final_answer)
                        break
                    
                    react_loop.next_iteration()
                    continue
                
                if parsed["has_final_answer"]:
                    # 得到最终答案
                    yield {
                        "type": "text_chunk",
                        "content": f"\n\n**Final Answer**: {parsed['final_answer']}",
                        "task_id": task_id
                    }
                    react_loop.complete(parsed["final_answer"])
                    break
                    
                # 记录思考
                if parsed["thought"]:
                    react_loop.add_thought(parsed["thought"])
                    
                # 执行动作
                if parsed["action"]:
                    yield {
                        "type": "text_chunk",
                        "content": f"\n**Action**: {parsed['action']['tool_name']}({parsed['action']['parameters']})",
                        "task_id": task_id
                    }
                    
                    react_loop.add_action(parsed["action"])
                    
                    # 执行工具
                    observation = await self._execute_action(parsed["action"])
                    react_loop.add_observation(observation)
                    
                    yield {
                        "type": "text_chunk", 
                        "content": f"\n**Observation**: {observation}\n",
                        "task_id": task_id
                    }
                    
                    # 将观察结果添加到消息历史
                    messages.append(Message(role=MessageRole.ASSISTANT, content=thought_content))
                    messages.append(Message(role=MessageRole.USER, content=f"Observation: {observation}"))
                else:
                    # 没有动作，可能需要更多思考
                    if not parsed["thought"]:
                        break
                        
                react_loop.next_iteration()
                
            # 如果循环结束但没有最终答案
            if not react_loop.is_complete:
                final_answer = "基于以上分析，我无法得出确定的结论。请提供更多信息或重新描述问题。"
                yield {
                    "type": "text_chunk",
                    "content": f"\n\n**Final Answer**: {final_answer}",
                    "task_id": task_id
                }
                react_loop.complete(final_answer)
                
        except Exception as e:
            yield {
                "type": "error",
                "content": f"执行失败: {str(e)}",
                "task_id": task_id,
                "error": str(e)
            }
            
    def _build_context_history(self, react_loop: ReactLoop) -> str:
        """构建上下文历史"""
        if not react_loop.thoughts and not react_loop.actions:
            return ""
            
        history_parts = []
        
        for i in range(react_loop.current_iteration):
            if i < len(react_loop.thoughts):
                thought = react_loop.thoughts[i]
                history_parts.append(f"Thought: {thought['content']}")
                
            if i < len(react_loop.actions):
                action = react_loop.actions[i]
                action_str = f"{action['action']['tool_name']}({action['action']['parameters']})"
                history_parts.append(f"Action: {action_str}")
                
            if i < len(react_loop.observations):
                observation = react_loop.observations[i]
                history_parts.append(f"Observation: {observation['content']}")
                
        return "\n".join(history_parts) + "\n\n" if history_parts else ""
        
    def build_graph(self):
        """构建StateGraph - ReactAgent不使用StateGraph，直接在run中实现循环"""
        # ReactAgent使用自己的循环逻辑，不需要StateGraph
        # 为了兼容BaseAgent的抽象方法，返回一个简单的占位符
        from core.graph import StateGraph
        return StateGraph("react_placeholder")
        
    async def initialize(self):
        """初始化Agent"""
        await self.llm.initialize()
        if self.tool_manager:
            await self.tool_manager.initialize()
            
    async def cleanup(self):
        """清理资源"""
        await self.llm.cleanup()
        if self.tool_manager:
            await self.tool_manager.cleanup()