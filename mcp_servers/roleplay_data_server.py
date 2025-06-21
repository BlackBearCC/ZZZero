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
        self.schedule_plan_prompt = """你是一个专业的角色扮演日程规划助手。请为指定角色生成一个合理的日程计划框架。

【角色设定】
{character_description}

【任务描述】
{requirements}

【参考选项库】
参考地点类型：
- 居住场所：卧室、客厅、厨房、阳台、花园、书房、工作室
- 工作场所：办公室、会议室、实验室、工厂、商店、餐厅、学校
- 休闲场所：公园、咖啡厅、图书馆、健身房、电影院、商场、海边
- 社交场所：朋友家、社区中心、俱乐部、聚会场所、宴会厅
- 户外场所：山林、湖泊、城市广场、街道、景区、运动场

参考天气类型：
- 晴朗：阳光明媚、微风徐徐、万里无云、温暖舒适
- 阴天：多云、凉爽、微风、适合户外活动
- 雨天：小雨、中雨、大雨、雷雨、毛毛雨、阵雨
- 特殊天气：雪天、雾天、沙尘、炎热、寒冷

参考情绪氛围：
- 积极情绪：兴奋、愉悦、专注、充满活力、满足、平静
- 中性情绪：平常、淡定、思考、观察、等待、准备
- 挑战情绪：紧张、忙碌、压力、期待、不安、困惑

请按照以下格式生成日程计划框架：
1. **角色日程标题**（结合角色特点和任务描述）
2. **计划时间范围**（具体日期或时间段）
3. **角色当前状态**（基于角色设定的心理状态和生活状况）
4. **主要目标**（符合角色性格和任务要求的核心目标）
5. **关键活动概览**（使用markdown表格格式）

对于关键活动概览，请使用以下markdown表格格式：

```table
| 活动名称 | 预计时长 | 重要性级别 | 适合时间段 | 背景原因/目的 |
|---------|---------|-----------|-----------|-------------|
| 示例活动1 | 30分钟 | 高 | 上午 | 活动的具体原因和目标 |
| 示例活动2 | 1小时 | 中 | 下午 | 活动的具体原因和目标 |
```

6. **角色生活节奏特点**（基于角色设定的作息习惯和生活方式）
7. **特殊注意事项**（角色的限制条件、偏好、禁忌等）

要求：
- 严格按照角色设定中的性格特点、生活方式来制定计划
- 时间安排要符合角色的个人特质和生活习惯
- 考虑角色的工作性质、社交需求、个人爱好
- 活动安排要有明确的背景原因和目的
- 预留符合角色性格的弹性时间和休息方式
- **重要：必须使用```table```代码块格式来展示关键活动概览表格**
- 使用中文回复"""
        
        self.detailed_schedule_prompt = """你是一个专业的角色扮演日程细化专家。根据提供的计划框架，为指定角色生成详细的5阶段日程安排。

【重要说明】
本详细日程将作为最终执行资料使用，必须详细说明所有相关的背景和计划内容。每个活动安排都要让用户理解其背景原因和目的。

【角色设定】
{character_description}

【计划框架】
{plan_framework}

【补充要求】
{requirements}

请按照以下5个时间阶段生成详细日程：

**上午阶段（06:00-11:00）**：
使用以下markdown表格格式展示活动安排：

```table
| 时间段 | 活动名称 | 地点 | 天气情况 | 情绪氛围 | 活动内容详述 | 角色行为细节 | 所需资源/工具 | 注意事项 |
|--------|---------|-----|---------|---------|-------------|-------------|-------------|---------|
| 06:00-06:30 | 晨起活动 | 卧室 | 晴朗微风 | 平静清醒 | 活动的背景原因和目的 | 符合性格的具体表现 | 所需物品 | 特殊考虑 |
| 06:30-07:00 | 下一活动 | 相应地点 | 天气状况 | 情绪状态 | 详细描述 | 行为细节 | 需要资源 | 注意要点 |
```

**中午阶段（11:00-14:00）**：
使用以下markdown表格格式展示活动安排：

```table
| 时间段 | 活动名称 | 地点 | 天气情况 | 情绪氛围 | 活动内容详述 | 角色行为细节 | 所需资源/工具 | 注意事项 |
|--------|---------|-----|---------|---------|-------------|-------------|-------------|---------|
| 11:00-11:30 | 午间活动 | 相应地点 | 天气状况 | 情绪状态 | 从上午活动的自然过渡及详述 | 午餐时间的个人习惯体现 | 需要资源 | 休息调整的个性化需求 |
```

**下午阶段（14:00-18:00）**：
使用以下markdown表格格式展示活动安排：

```table
| 时间段 | 活动名称 | 地点 | 天气情况 | 情绪氛围 | 活动内容详述 | 角色行为细节 | 所需资源/工具 | 注意事项 |
|--------|---------|-----|---------|---------|-------------|-------------|-------------|---------|
| 14:00-14:30 | 下午活动 | 适合场所 | 下午特征 | 专注状态 | 背景原因和目的详述 | 工作/学习风格体现 | 需要资源 | 避免疲劳的策略 |
```

**晚上阶段（18:00-23:00）**：
使用以下markdown表格格式展示活动安排：

```table
| 时间段 | 活动名称 | 地点 | 天气情况 | 情绪氛围 | 活动内容详述 | 角色行为细节 | 所需资源/工具 | 注意事项 |
|--------|---------|-----|---------|---------|-------------|-------------|-------------|---------|
| 18:00-18:30 | 晚间活动 | 休闲场所 | 夜晚氛围 | 心境转换 | 背景原因和目的详述 | 个人爱好和放松方式 | 需要资源 | 对睡眠质量的影响 |
```

**夜间阶段（23:00-06:00）**：
使用以下markdown表格格式展示活动安排：

```table
| 时间段 | 活动名称 | 地点 | 环境氛围 | 情绪状态 | 活动内容详述 | 角色行为细节 | 所需资源/工具 | 注意事项 |
|--------|---------|-----|---------|---------|-------------|-------------|-------------|---------|
| 23:00-23:30 | 睡前准备 | 睡眠环境 | 夜间设置 | 心理调节 | 睡前仪式的个性化体现 | 睡眠习惯和晨起风格 | 需要资源 | 保证睡眠质量的措施 |
```

生成要求：
1. **地点选择要合理且符合角色需要**，可参考地点类型库，也可根据角色特质创造新地点
2. **天气安排要符合季节特点和情节需要**，要与活动性质相匹配
3. **情绪氛围要贴合活动性质和角色当前状态**，体现角色的心理变化过程
4. **严格按照角色设定中描述的性格特点、生活方式来安排活动**
5. **每个活动都要说明背景原因和目的**，让用户理解为什么要这样安排
6. **安排符合角色个人特质的具体活动**，包含日常生活的细节体现
7. **考虑工作日和休息日的不同节奏**，体现角色的时间管理方式
8. **地点选择要符合角色的个人特质和当前阶段主题**
9. **活动之间要有自然的衔接和过渡**，体现真实生活的连贯性
10. **时间安排要精确具体**，便于实际执行和跟踪
- **重要：必须使用```table```代码块格式来展示每个阶段的活动安排表格**
- 使用中文回复"""
    
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