#!/usr/bin/env python3
"""
角色扮演数据生成服务器 - 基于MCP协议的AI驱动的角色扮演数据生成服务
支持计划日程表生成、详细日程生成等功能
"""
import os
import sys
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from enum import Enum

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from mcp.server.stdio_server import StdioMCPServer
from mcp.types import Tool, Resource, JSONSchema, ToolInputSchema

# 导入项目的LLM系统
from src.llm.base import LLMFactory
from src.core.types import LLMConfig, Message, MessageRole

# 确保LLM提供商已注册
try:
    from src.llm.doubao import DoubaoLLM  # 注册豆包
except ImportError:
    logger.warning("豆包LLM模块导入失败，将不支持豆包")

try:
    from src.llm.openai import OpenAILLM  # 注册OpenAI（如果存在）
except ImportError:
    logger.info("OpenAI LLM模块未找到，如需使用请实现相应模块")

logger = logging.getLogger(__name__)


class TimePhase(Enum):
    """时间阶段枚举"""
    MORNING = ("上午", "06:00-11:00", "06:00", "11:00")
    NOON = ("中午", "11:00-14:00", "11:00", "14:00")
    AFTERNOON = ("下午", "14:00-18:00", "14:00", "18:00")
    EVENING = ("晚上", "18:00-23:00", "18:00", "23:00")
    NIGHT = ("夜间", "23:00-06:00", "23:00", "06:00")
    
    def __init__(self, name: str, time_range: str, start_time: str, end_time: str):
        self.phase_name = name
        self.time_range = time_range
        self.start_time = start_time
        self.end_time = end_time


class PromptManager:
    """提示词管理器 - 管理预置的标准提示词模板"""
    
    def __init__(self):
        self.schedule_plan_prompt = """你是一个专业的日程规划助手。请为用户生成一个合理的日程计划框架。

用户要求：{requirements}

请按照以下格式生成日程计划：
1. 计划标题
2. 计划日期/时间范围
3. 主要目标
4. 关键活动列表（每个活动包含：活动名称、预计时长、重要性级别）
5. 注意事项

要求：
- 时间安排要合理，考虑人的作息规律
- 活动之间要有适当的休息时间
- 重要活动安排在精力最佳的时段
- 预留一定的弹性时间
- 使用中文回复"""
        
        self.detailed_schedule_prompt = """你是一个专业的日程细化专家。根据提供的计划框架，生成详细的5阶段日程安排。

计划框架：
{plan_framework}

用户补充要求：{requirements}

请按照以下5个时间阶段生成详细日程：

**上午阶段（06:00-11:00）**：
- 具体活动安排（精确到30分钟时间段）
- 活动内容描述
- 所需资源/工具
- 注意事项

**中午阶段（11:00-14:00）**：
- 具体活动安排
- 活动内容描述
- 所需资源/工具
- 注意事项

**下午阶段（14:00-18:00）**：
- 具体活动安排
- 活动内容描述
- 所需资源/工具
- 注意事项

**晚上阶段（18:00-23:00）**：
- 具体活动安排
- 活动内容描述
- 所需资源/工具
- 注意事项

**夜间阶段（23:00-06:00）**：
- 具体活动安排
- 活动内容描述
- 所需资源/工具
- 注意事项

要求：
- 时间安排要精确具体
- 活动内容要详细可执行
- 考虑活动之间的衔接
- 包含必要的休息时间
- 使用中文回复"""
    
    def get_schedule_plan_prompt(self, description: str = "") -> str:
        """获取日程计划生成提示词"""
        return self.schedule_plan_prompt.format(requirements=description)
    
    def get_detailed_schedule_prompt(self, plan_framework: str = "", description: str = "") -> str:
        """获取详细日程生成提示词"""
        return self.detailed_schedule_prompt.format(plan_framework=plan_framework, requirements=description)


class LLMCaller:
    """LLM调用器 - 使用项目的统一LLM框架"""
    
    def __init__(self):
        self.llm_provider = None
        self._initialize_llm()
        
    def _initialize_llm(self):
        """初始化LLM提供者"""
        # 从环境变量获取配置
        provider = os.getenv("LLM_PROVIDER", "doubao")  # 默认使用豆包
        model_name = os.getenv("LLM_MODEL_NAME", "ep-20250221154410-vh78x")  # 豆包默认模型
        api_key = os.getenv("ARK_API_KEY") or os.getenv("DOUBAO_API_KEY") or os.getenv("OPENAI_API_KEY")
        api_base = os.getenv("DOUBAO_BASE_URL") or os.getenv("OPENAI_BASE_URL")
        
        # 根据provider自动设置默认值
        if provider == "doubao":
            api_base = api_base or "https://ark.cn-beijing.volces.com/api/v3"
            model_name = model_name or "ep-20250221154410-vh78x"
        elif provider == "openai":
            api_base = api_base or "https://api.openai.com/v1"
            model_name = model_name or "gpt-3.5-turbo"
        
        try:
            # 创建LLM配置
            llm_config = LLMConfig(
                provider=provider,
                model_name=model_name,
                api_key=api_key,
                api_base=api_base,
                temperature=0.5,
                timeout=600  # 增加超时时间到60秒
            )
            
            # 创建LLM实例
            self.llm_provider = LLMFactory.create(llm_config)
            logger.info(f"✅ LLM调用器初始化成功，使用提供商: {provider}，模型: {model_name}")
            
        except Exception as e:
            logger.error(f"❌ LLM调用器初始化失败: {e}")
            logger.error(f"提供商: {provider}, 模型: {model_name}, API密钥已设置: {bool(api_key)}")
            self.llm_provider = None
    
    async def call_llm(self, prompt: str, max_tokens: int = 2000, 
                       temperature: float = 0.7) -> Tuple[bool, str]:
        """统一的LLM调用接口"""
        if not self.llm_provider:
            return False, "LLM服务未正确初始化"
        
        try:
            # 确保LLM已初始化
            await self.llm_provider.initialize()
            
            # 构建消息
            messages = [
                Message(role=MessageRole.SYSTEM, 
                       content="你是一个专业的日程规划助手，能够生成详细、实用的日程安排。"),
                Message(role=MessageRole.USER, content=prompt)
            ]
            
            # 调用LLM生成
            response = await self.llm_provider.generate(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            return True, response.content
            
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            return False, f"LLM调用失败: {str(e)}"
            
    async def cleanup(self):
        """清理LLM资源"""
        if self.llm_provider:
            try:
                await self.llm_provider.cleanup()
            except Exception as e:
                logger.warning(f"LLM清理失败: {e}")


class RolePlayDataGenerator:
    """角色扮演数据生成器 - 核心生成逻辑"""
    
    def __init__(self):
        self.prompt_manager = PromptManager()
        self.llm_caller = LLMCaller()
        self.generation_history = []
    
    async def generate_schedule_plan(self, description: str = "") -> Dict[str, Any]:
        """
        生成日程计划框架
        
        Args:
            description: 生成描述，用于输入生成的要求和需求
            
        Returns:
            生成结果字典
        """
        generation_id = f"plan_{int(datetime.now().timestamp())}"
        start_time = datetime.now()
        
        try:
            # 获取提示词
            prompt = self.prompt_manager.get_schedule_plan_prompt(description)
            
            # 调用LLM生成
            success, content = await self.llm_caller.call_llm(prompt)
            
            end_time = datetime.now()
            generation_time = (end_time - start_time).total_seconds()
            
            result = {
                "generation_id": generation_id,
                "type": "schedule_plan",
                "success": success,
                "content": content if success else None,
                "error": content if not success else None,
                "description": description,
                "generation_time": generation_time,
                "generated_at": start_time.isoformat(),
                "completed_at": end_time.isoformat()
            }
            
            # 添加到历史记录
            self._add_to_history(result)
            
            return result
            
        except Exception as e:
            return {
                "generation_id": generation_id,
                "type": "schedule_plan",
                "success": False,
                "error": f"生成过程中发生错误: {str(e)}",
                "description": description,
                "generated_at": start_time.isoformat()
            }
    
    async def generate_detailed_schedule(self, plan_framework: str = "",
                                       description: str = "") -> Dict[str, Any]:
        """
        根据计划框架生成详细的5阶段日程
        
        Args:
            plan_framework: 计划框架（来自generate_schedule_plan的结果）
            description: 生成描述，用于输入补充要求和需求
            
        Returns:
            生成结果字典
        """
        generation_id = f"schedule_{int(datetime.now().timestamp())}"
        start_time = datetime.now()
        
        try:
            # 获取提示词
            prompt = self.prompt_manager.get_detailed_schedule_prompt(
                plan_framework, description
            )
            
            # 调用LLM生成
            success, content = await self.llm_caller.call_llm(
                prompt, max_tokens=3000, temperature=0.6
            )
            
            end_time = datetime.now()
            generation_time = (end_time - start_time).total_seconds()
            
            # 解析生成的内容，提取5个阶段
            phases_data = self._parse_schedule_phases(content) if success else None
            
            result = {
                "generation_id": generation_id,
                "type": "detailed_schedule",
                "success": success,
                "content": content if success else None,
                "phases_data": phases_data,
                "error": content if not success else None,
                "plan_framework": plan_framework[:500] + "..." if len(plan_framework) > 500 else plan_framework,
                "description": description,
                "generation_time": generation_time,
                "generated_at": start_time.isoformat(),
                "completed_at": end_time.isoformat()
            }
            
            # 添加到历史记录
            self._add_to_history(result)
            
            return result
            
        except Exception as e:
            return {
                "generation_id": generation_id,
                "type": "detailed_schedule",
                "success": False,
                "error": f"生成过程中发生错误: {str(e)}",
                "plan_framework": plan_framework[:200] + "..." if len(plan_framework) > 200 else plan_framework,
                "description": description,
                "generated_at": start_time.isoformat()
            }
    
    def _parse_schedule_phases(self, content: str) -> Dict[str, Any]:
        """解析日程内容，提取5个时间阶段的信息"""
        phases = {}
        
        for phase in TimePhase:
            phase_key = phase.name.lower()
            phase_pattern = f"**{phase.phase_name}阶段（{phase.time_range}）**"
            
            # 简单的文本匹配提取（实际项目中可以使用更复杂的解析逻辑）
            if phase_pattern in content:
                start_idx = content.find(phase_pattern)
                # 查找下一个阶段的开始位置
                next_phase_idx = len(content)
                for next_phase in TimePhase:
                    if next_phase != phase:
                        next_pattern = f"**{next_phase.phase_name}阶段"
                        idx = content.find(next_pattern, start_idx + 1)
                        if idx != -1 and idx < next_phase_idx:
                            next_phase_idx = idx
                
                phase_content = content[start_idx:next_phase_idx].strip()
                phases[phase_key] = {
                    "name": phase.phase_name,
                    "time_range": phase.time_range,
                    "start_time": phase.start_time,
                    "end_time": phase.end_time,
                    "content": phase_content
                }
        
        return phases
    
    def _add_to_history(self, result: Dict[str, Any]):
        """添加生成结果到历史记录"""
        # 简化历史记录，只保留关键信息
        history_entry = {
            "generation_id": result["generation_id"],
            "type": result["type"],
            "success": result["success"],
            "generated_at": result["generated_at"],
            "generation_time": result.get("generation_time", 0)
        }
        
        self.generation_history.append(history_entry)
        
        # 限制历史记录数量
        if len(self.generation_history) > 50:
            self.generation_history = self.generation_history[-50:]
    
    def get_generation_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取生成历史"""
        return self.generation_history[-limit:]
    
    def clear_generation_history(self) -> Dict[str, Any]:
        """清空生成历史"""
        count = len(self.generation_history)
        self.generation_history.clear()
        return {
            "cleared_count": count,
            "cleared_at": datetime.now().isoformat()
        }
    
    async def cleanup(self):
        """清理资源"""
        if self.llm_caller:
            await self.llm_caller.cleanup()


class RolePlayDataServer(StdioMCPServer):
    """角色扮演数据生成MCP服务器"""
    
    def __init__(self):
        """初始化服务器"""
        super().__init__("roleplay-data-server")
        self.generator = RolePlayDataGenerator()
        self._register_roleplay_tools()
    
    def _register_roleplay_tools(self):
        """注册角色扮演数据生成工具"""
        
        # 生成计划日程表工具
        self.register_tool(Tool(
            name="generate_schedule_plan",
            description="生成日程计划框架。根据用户描述生成一个基础的日程规划，包含主要目标、关键活动等",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "description": {
                        "type": "string",
                        "description": "生成描述，用于输入生成的要求和需求",
                        "default": ""
                    }
                }
            )
        ))
        
        # 生成详细日程工具
        self.register_tool(Tool(
            name="generate_detailed_schedule",
            description="根据计划框架生成详细的5阶段日程安排（上午、中午、下午、晚上、夜间）",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "plan_framework": {
                        "type": "string",
                        "description": "计划框架内容（通常来自generate_schedule_plan的结果）",
                        "default": ""
                    },
                    "description": {
                        "type": "string",
                        "description": "生成描述，用于输入补充要求和需求",
                        "default": ""
                    }
                }
            )
        ))
        
        # 获取生成历史工具
        self.register_tool(Tool(
            name="get_generation_history",
            description="获取角色扮演数据生成历史记录",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "limit": {
                        "type": "integer",
                        "description": "返回的历史记录数量限制，默认20",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 50
                    }
                }
            )
        ))
        
        # 清空生成历史工具
        self.register_tool(Tool(
            name="clear_generation_history",
            description="清空角色扮演数据生成历史记录",
            inputSchema=ToolInputSchema(
                type="object",
                properties={}
            )
        ))
        
        # 获取时间阶段信息工具
        self.register_tool(Tool(
            name="get_time_phases",
            description="获取5阶段时间规划的详细信息",
            inputSchema=ToolInputSchema(
                type="object",
                properties={}
            )
        ))
    
    async def _call_tool(self, name: str, arguments: Dict[str, Any], context) -> Dict[str, Any]:
        """处理工具调用"""
        try:
            logger.info(f"角色扮演数据生成工具调用: {name}")
            logger.info(f"参数: {arguments}")
            
            if name == "generate_schedule_plan":
                description = arguments.get("description", "")
                return await self.generator.generate_schedule_plan(description)
            
            elif name == "generate_detailed_schedule":
                plan_framework = arguments.get("plan_framework", "")
                description = arguments.get("description", "")
                
                return await self.generator.generate_detailed_schedule(
                    plan_framework, description
                )
            
            elif name == "get_generation_history":
                limit = arguments.get("limit", 20)
                if not isinstance(limit, int) or limit < 1 or limit > 50:
                    limit = 20
                
                history = self.generator.get_generation_history(limit)
                return {
                    "history": history,
                    "total_count": len(history),
                    "retrieved_at": datetime.now().isoformat()
                }
            
            elif name == "clear_generation_history":
                return self.generator.clear_generation_history()
            
            elif name == "get_time_phases":
                phases_info = []
                for phase in TimePhase:
                    phases_info.append({
                        "name": phase.phase_name,
                        "time_range": phase.time_range,
                        "start_time": phase.start_time,
                        "end_time": phase.end_time,
                        "description": f"{phase.phase_name}时间段，适合进行相应的活动安排"
                    })
                
                return {
                    "phases": phases_info,
                    "total_phases": len(phases_info),
                    "description": "5阶段时间规划原则，将一天分为5个时间段进行精细化管理"
                }
            
            else:
                return {"error": f"未知工具: {name}"}
                
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"角色扮演数据生成工具调用失败 {name}: {e}")
            logger.error(f"错误详情: {error_traceback}")
            return {
                "error": f"工具调用失败: {str(e)}",
                "error_type": type(e).__name__,
                "tool_name": name,
                "received_arguments": arguments,
                "timestamp": datetime.now().isoformat()
            }
    
    async def cleanup(self):
        """清理服务器资源"""
        if hasattr(self, 'generator') and self.generator:
            await self.generator.cleanup()


async def main():
    """主函数"""
    logging.basicConfig(level=logging.INFO)
    
    # 创建服务器实例
    server = RolePlayDataServer()
    
    # 运行服务器
    logger.info("启动角色扮演数据生成MCP服务器...")
    await server.run()


if __name__ == "__main__":
    asyncio.run(main()) 