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
import random
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


class ConfigManager:
    """配置管理器 - 管理地点、天气、情绪配置数据"""
    
    def __init__(self):
        # 地点配置
        self.locations = {
            "居住场所": ["卧室", "客厅", "厨房", "阳台", "花园", "书房", "工作室"],
            "工作场所": ["办公室", "会议室", "实验室", "工厂", "商店", "餐厅", "学校"],
            "休闲场所": ["公园", "咖啡厅", "图书馆", "健身房", "电影院", "商场", "海边"],
            "社交场所": ["朋友家", "社区中心", "俱乐部", "聚会场所", "宴会厅"],
            "户外场所": ["山林", "湖泊", "城市广场", "街道", "景区", "运动场"]
        }
        
        # 天气配置
        self.weather = {
            "晴朗": ["阳光明媚", "微风徐徐", "万里无云", "温暖舒适"],
            "阴天": ["多云", "凉爽", "微风", "适合户外活动"],
            "雨天": ["小雨", "中雨", "大雨", "雷雨", "毛毛雨", "阵雨"],
            "特殊天气": ["雪天", "雾天", "沙尘", "炎热", "寒冷"]
        }
        
        # 情绪氛围配置
        self.emotions = {
            "积极情绪": ["兴奋", "愉悦", "专注", "充满活力", "满足", "平静"],
            "中性情绪": ["平常", "淡定", "思考", "观察", "等待", "准备"],
            "挑战情绪": ["紧张", "忙碌", "压力", "期待", "不安", "困惑"]
        }
    
    def get_random_location(self, category: str = None) -> str:
        """随机获取地点"""
        if category and category in self.locations:
            return random.choice(self.locations[category])
        # 随机选择分类和地点
        category = random.choice(list(self.locations.keys()))
        return random.choice(self.locations[category])
    
    def get_random_weather(self, category: str = None) -> str:
        """随机获取天气"""
        if category and category in self.weather:
            return random.choice(self.weather[category])
        # 随机选择分类和天气
        category = random.choice(list(self.weather.keys()))
        return random.choice(self.weather[category])
    
    def get_random_emotion(self, category: str = None) -> str:
        """随机获取情绪"""
        if category and category in self.emotions:
            return random.choice(self.emotions[category])
        # 随机选择分类和情绪
        category = random.choice(list(self.emotions.keys()))
        return random.choice(self.emotions[category])
    
    def get_all_config(self) -> Dict[str, Any]:
        """获取所有配置"""
        return {
            "locations": self.locations,
            "weather": self.weather,
            "emotions": self.emotions
        }


class PromptManager:
    """提示词管理器 - 管理预置的标准提示词模板"""
    
    def __init__(self):
        self.schedule_plan_prompt = """你是一个专业的角色扮演日程规划助手。请为指定角色生成一个合理的日程计划框架。

【角色设定】
{character_description}

【任务描述】
{requirements}

请按照以下格式生成日程计划框架：
1. **角色日程标题**（结合角色特点和任务描述）
2. **计划时间范围**（具体日期或时间段）
3. **角色当前状态**（基于角色设定的心理状态和生活状况）
4. **主要目标**（符合角色性格和任务要求的核心目标）
5. **关键活动概览**（简洁描述主要活动）
6. **角色生活节奏特点**（基于角色设定的作息习惯和生活方式）
7. **特殊注意事项**（角色的限制条件、偏好、禁忌等）

要求：
- 严格按照角色设定中的性格特点、生活方式来制定计划
- 时间安排要符合角色的个人特质和生活习惯
- 考虑角色的工作性质、社交需求、个人爱好
- 活动安排要有明确的背景原因和目的
- 预留符合角色性格的弹性时间和休息方式
- 使用中文回复"""
        
        self.detailed_schedule_prompt = """你是一个专业的角色扮演日程细化专家。根据提供的计划框架，为指定角色生成详细的5阶段日程安排。

【重要说明】
必须按照JSON格式输出，每个活动只包含活动名称和细节两个字段。

【角色设定】
{character_description}

【计划框架】
{plan_framework}

【补充要求】
{requirements}

请按照以下JSON格式生成详细日程，将一天分为5个时间阶段：

```json
{{
  "morning": [
    {{
      "activity_name": "活动名称",
      "details": "活动的详细描述，包括背景原因、目的、具体行为等"
    }}
  ],
  "noon": [
    {{
      "activity_name": "活动名称", 
      "details": "活动的详细描述"
    }}
  ],
  "afternoon": [
    {{
      "activity_name": "活动名称",
      "details": "活动的详细描述"
    }}
  ],
  "evening": [
    {{
      "activity_name": "活动名称",
      "details": "活动的详细描述"
    }}
  ],
  "night": [
    {{
      "activity_name": "活动名称",
      "details": "活动的详细描述"
    }}
  ]
}}
```

生成要求：
1. **严格按照角色设定中描述的性格特点、生活方式来安排活动**
2. **每个活动都要说明背景原因和目的**，让用户理解为什么要这样安排
3. **安排符合角色个人特质的具体活动**，包含日常生活的细节体现
4. **考虑工作日和休息日的不同节奏**，体现角色的时间管理方式
5. **活动之间要有自然的衔接和过渡**，体现真实生活的连贯性
6. **details字段要详细描述活动内容、背景原因、角色行为等**
7. **输出必须是有效的JSON格式**
- 使用中文回复
- 必须严格按照JSON格式输出"""
    
    def get_schedule_plan_prompt(self, character_description: str = "", requirements: str = "") -> str:
        """获取日程计划生成提示词"""
        return self.schedule_plan_prompt.format(
            character_description=character_description or "未指定角色，请按通用需求处理",
            requirements=requirements or "生成标准的日程计划"
        )
    
    def get_detailed_schedule_prompt(self, character_description: str = "", plan_framework: str = "", requirements: str = "") -> str:
        """获取详细日程生成提示词"""
        return self.detailed_schedule_prompt.format(
            character_description=character_description or "未指定角色，请按通用需求处理",
            plan_framework=plan_framework or "未提供计划框架",
            requirements=requirements or "生成标准的详细日程"
        )


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
                temperature=0.4,
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
        self.config_manager = ConfigManager()
        self.generation_history = []
    
    async def generate_schedule_plan(self, character_description: str = "", requirements: str = "") -> Dict[str, Any]:
        """
        生成日程计划框架
        
        Args:
            character_description: 角色设定描述，包含角色的性格特点、生活方式等
            requirements: 任务要求描述，用于输入生成的要求和需求
            
        Returns:
            生成结果字典
        """
        generation_id = f"plan_{int(datetime.now().timestamp())}"
        start_time = datetime.now()
        
        try:
            # 获取提示词
            prompt = self.prompt_manager.get_schedule_plan_prompt(character_description, requirements)
            
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
                "character_description": character_description[:200] + "..." if len(character_description) > 200 else character_description,
                "requirements": requirements,
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
                "character_description": character_description[:200] + "..." if len(character_description) > 200 else character_description,
                "requirements": requirements,
                "generated_at": start_time.isoformat()
            }
    
    async def generate_detailed_schedule(self, character_description: str = "", 
                                       plan_framework: str = "",
                                       requirements: str = "") -> Dict[str, Any]:
        """
        根据计划框架生成详细的5阶段日程
        
        Args:
            character_description: 角色设定描述，包含角色的性格特点、生活方式等
            plan_framework: 计划框架（来自generate_schedule_plan的结果）
            requirements: 补充要求描述，用于输入补充要求和需求
            
        Returns:
            生成结果字典
        """
        generation_id = f"schedule_{int(datetime.now().timestamp())}"
        start_time = datetime.now()
        
        try:
            # 获取提示词
            prompt = self.prompt_manager.get_detailed_schedule_prompt(
                character_description, plan_framework, requirements
            )
            
            # 调用LLM生成
            success, content = await self.llm_caller.call_llm(
                prompt, max_tokens=4000, temperature=0.6  # 增加max_tokens以支持更详细的输出
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
                "character_description": character_description[:200] + "..." if len(character_description) > 200 else character_description,
                "plan_framework": plan_framework[:500] + "..." if len(plan_framework) > 500 else plan_framework,
                "requirements": requirements,
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
                "character_description": character_description[:200] + "..." if len(character_description) > 200 else character_description,
                "plan_framework": plan_framework[:200] + "..." if len(plan_framework) > 200 else plan_framework,
                "requirements": requirements,
                "generated_at": start_time.isoformat()
            }
    
    def _parse_schedule_phases(self, content: str) -> Dict[str, Any]:
        """解析日程内容，提取JSON格式的5个时间阶段信息"""
        try:
            # 尝试从内容中提取JSON
            json_start = content.find('{')
            json_end = content.rfind('}')
            
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end + 1]
                schedule_data = json.loads(json_str)
                
                # 为每个阶段添加配置数据
                phases = {}
                phase_mapping = {
                    "morning": TimePhase.MORNING,
                    "noon": TimePhase.NOON,
                    "afternoon": TimePhase.AFTERNOON,
                    "evening": TimePhase.EVENING,
                    "night": TimePhase.NIGHT
                }
                
                for phase_key, activities in schedule_data.items():
                    if phase_key in phase_mapping:
                        phase_enum = phase_mapping[phase_key]
                        
                        # 为每个活动随机分配地点、天气、情绪
                        enhanced_activities = []
                        for activity in activities:
                            enhanced_activity = {
                                "activity_name": activity.get("activity_name", ""),
                                "details": activity.get("details", ""),
                                "location": self.config_manager.get_random_location(),
                                "weather": self.config_manager.get_random_weather(),
                                "emotion": self.config_manager.get_random_emotion()
                            }
                            enhanced_activities.append(enhanced_activity)
                        
                        phases[phase_key] = {
                            "name": phase_enum.phase_name,
                            "time_range": phase_enum.time_range,
                            "start_time": phase_enum.start_time,
                            "end_time": phase_enum.end_time,
                            "activities": enhanced_activities
                        }
                
                return phases
            else:
                logger.warning("未找到有效的JSON格式")
                return {}
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            return {}
        except Exception as e:
            logger.error(f"解析阶段数据失败: {e}")
            return {}
    
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
            description="为指定角色生成日程计划框架。根据角色设定和任务描述生成一个基础的日程规划，包含主要目标、关键活动等",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "character_description": {
                        "type": "string",
                        "description": "角色设定描述，包含角色的性格特点、生活方式、工作性质、个人爱好等详细信息",
                        "default": ""
                    },
                    "requirements": {
                        "type": "string",
                        "description": "任务要求描述，说明希望生成什么样的日程计划，有什么特殊要求等",
                        "default": ""
                    }
                }
            )
        ))
        
        # 生成详细日程工具
        self.register_tool(Tool(
            name="generate_detailed_schedule",
            description="根据角色设定和计划框架生成详细的5阶段日程安排（上午、中午、下午、晚上、夜间），包含地点、天气、情绪氛围等丰富细节",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "character_description": {
                        "type": "string",
                        "description": "角色设定描述，包含角色的性格特点、生活方式、工作性质、个人爱好等详细信息",
                        "default": ""
                    },
                    "plan_framework": {
                        "type": "string",
                        "description": "计划框架内容（通常来自generate_schedule_plan的结果）",
                        "default": ""
                    },
                    "requirements": {
                        "type": "string",
                        "description": "补充要求描述，用于输入额外的细化要求和特殊需求",
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
                character_description = arguments.get("character_description", "")
                requirements = arguments.get("requirements", "")
                return await self.generator.generate_schedule_plan(character_description, requirements)
            
            elif name == "generate_detailed_schedule":
                character_description = arguments.get("character_description", "")
                plan_framework = arguments.get("plan_framework", "")
                requirements = arguments.get("requirements", "")
                
                return await self.generator.generate_detailed_schedule(
                    character_description, plan_framework, requirements
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