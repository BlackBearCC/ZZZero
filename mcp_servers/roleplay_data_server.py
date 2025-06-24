#!/usr/bin/env python3
"""
角色扮演数据生成服务器 - 基于MCP协议的AI驱动的角色扮演数据生成服务
支持计划日程表生成、详细日程生成等功能
"""
import os
import sys

# 首先添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from enum import Enum

# 使用本地mcp模块
from mcp.server.stdio_server import StdioMCPServer
from mcp.types import Tool, Resource, JSONSchema, ToolInputSchema

# 导入项目的LLM系统
from src.llm.base import LLMFactory
from src.core.types import LLMConfig, Message, MessageRole

# 导入角色插件系统
from src.core.plugins import get_role_plugin_manager, RolePluginManager

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
        
        # 初始化角色插件管理器
        self.role_plugin_manager = get_role_plugin_manager()
        logger.info("角色插件管理器已集成到角色扮演数据生成器")
        
        # 自动初始化知识库
        asyncio.create_task(self._initialize_knowledge_base())
    
    async def _initialize_knowledge_base(self):
        """自动初始化知识库，加载roleplay_data_README.md"""
        try:
            # 检查是否已有知识库配置
            status = self.role_plugin_manager.get_status()
            kb_info = status.get('knowledge_base_plugin', {})
            
            if kb_info.get('enabled') and kb_info.get('available'):
                logger.info("知识库已存在且可用，跳过自动初始化")
                return
            
            # 获取README文件路径
            readme_path = Path(__file__).parent / "roleplay_data_README.md"
            
            if not readme_path.exists():
                logger.warning(f"README文件不存在: {readme_path}")
                return
            
            # 配置知识库
            await self.role_plugin_manager.configure_knowledge_base(
                name="角色扮演数据生成服务知识库",
                source_file=str(readme_path),
                description="包含角色扮演数据生成服务的功能说明、使用方法、配置信息等",
                search_limit=5,
                enabled=True,
                process_immediately=True
            )
            
            logger.info("✅ 已自动配置角色扮演数据生成服务知识库")
            
        except Exception as e:
            logger.error(f"自动初始化知识库失败: {e}")
            # 不抛出异常，允许服务继续运行
    
    async def _generate_search_keywords(self, character_description: str = "", requirements: str = "") -> List[str]:
        """使用LLM生成搜索关键词"""
        try:
            # 构建关键词生成提示词
            keyword_prompt = f"""请根据以下角色设定和需求描述，生成5-10个适合搜索知识库的关键词。
关键词应该涵盖角色特点、活动类型、专业领域等方面。

角色设定：
{character_description if character_description else "未提供角色设定"}

需求描述：
{requirements if requirements else "未提供具体需求"}

请只返回关键词，用逗号分隔，不要其他解释。
例如：日程规划,时间管理,工作安排,休闲活动,个人爱好

关键词："""

            # 调用LLM生成关键词
            success, content = await self.llm_caller.call_llm(
                keyword_prompt, max_tokens=100, temperature=0.3
            )
            
            if success and content:
                # 解析生成的关键词
                keywords = [kw.strip() for kw in content.strip().split(",") if kw.strip()]
                # 限制关键词数量
                keywords = keywords[:10]
                logger.info(f"✅ LLM生成搜索关键词: {keywords}")
                return keywords
            else:
                logger.warning("LLM关键词生成失败，使用默认关键词")
                
        except Exception as e:
            logger.error(f"LLM关键词生成出错: {e}")
        
        # 回退方案：使用默认关键词
        default_keywords = ["日程", "计划", "安排", "时间管理", "角色扮演"]
        if requirements:
            # 简单提取一些明显的关键词作为补充
            simple_keywords = [word.strip() for word in requirements.replace("，", ",").split(",") if word.strip()]
            default_keywords.extend(simple_keywords[:5])
        
        return default_keywords[:10]
    
    async def _enhance_with_role_plugins(self, character_description: str = "", requirements: str = "") -> Tuple[str, str]:
        """使用角色插件增强参数 - 分离角色人设和参考资料"""
        enhanced_character = character_description
        enhanced_requirements = requirements
        
        try:
            # 第一步：确定最终的角色人设信息
            role_context = await self.role_plugin_manager.get_role_context([])  # 先不用关键词，直接获取基础角色资料
            
            # 处理角色人设 - 确定角色的基础身份信息
            final_character_profile = ""
            if "profile" in role_context and role_context["profile"]:
                plugin_profile = role_context["profile"]
                
                if enhanced_character and enhanced_character.strip():
                    # 用户提供了角色描述，以用户描述为准
                    final_character_profile = enhanced_character
                    logger.info("✅ 使用用户提供的角色描述作为人设")
                else:
                    # 用户未提供角色描述，使用插件中的角色人设
                    final_character_profile = plugin_profile
                    enhanced_character = plugin_profile
                    logger.info("✅ 使用插件中的角色人设作为基础")
            else:
                # 没有插件角色资料，使用用户提供的描述
                final_character_profile = enhanced_character
                logger.info("✅ 仅使用用户角色描述，无插件人设")
            
            # 第二步：基于确定的角色人设生成搜索关键词，获取参考资料
            if final_character_profile:
                keywords = await self._generate_search_keywords(final_character_profile, enhanced_requirements)
                
                # 重新获取角色上下文，这次带上关键词搜索知识库
                role_context_with_search = await self.role_plugin_manager.get_role_context(keywords)
                
                # 处理知识库参考资料 - 仅作为背景参考，不影响角色人设
                if "knowledge" in role_context_with_search and role_context_with_search["knowledge"]:
                    knowledge_results = role_context_with_search["knowledge"]
                    
                    # 筛选和格式化参考资料
                    reference_materials = []
                    for i, result in enumerate(knowledge_results[:3], 1):  # 最多3条参考资料
                        content = result['content']
                        # 简化参考资料，突出关键信息
                        if len(content) > 120:
                            content = content[:120] + "..."
                        reference_materials.append(f"参考资料{i}: {content}")
                    
                    if reference_materials:
                        reference_section = f"\n\n【背景参考资料】\n" + "\n".join(reference_materials)
                        enhanced_requirements = enhanced_requirements + reference_section if enhanced_requirements else f"请参考以下背景资料：{reference_section}"
                        logger.info(f"✅ 已添加 {len(reference_materials)} 条背景参考资料")
            
            # 记录处理结果
            if enhanced_character != character_description:
                logger.info(f"✅ 角色人设已确定：{enhanced_character[:50]}...")
            if enhanced_requirements != requirements:
                logger.info(f"✅ 需求已增强，添加了参考资料（新长度: {len(enhanced_requirements)}）")
            
            return enhanced_character, enhanced_requirements
            
        except Exception as e:
            logger.error(f"角色插件增强失败: {e}")
            # 如果插件增强失败，返回原始参数
            return character_description, requirements
    
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
            # 使用角色插件增强参数
            enhanced_character, enhanced_requirements = await self._enhance_with_role_plugins(
                character_description, requirements
            )
            
            # 获取提示词
            prompt = self.prompt_manager.get_schedule_plan_prompt(enhanced_character, enhanced_requirements)
            
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
                "enhanced_character_description": enhanced_character[:200] + "..." if len(enhanced_character) > 200 else enhanced_character,
                "requirements": requirements,
                "enhanced_requirements": enhanced_requirements[:200] + "..." if len(enhanced_requirements) > 200 else enhanced_requirements,
                "role_plugin_used": enhanced_character != character_description or enhanced_requirements != requirements,
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
            # 使用角色插件增强参数（详细日程生成时也需要增强）
            enhanced_character, enhanced_requirements = await self._enhance_with_role_plugins(
                character_description, requirements
            )
            
            # 获取提示词
            prompt = self.prompt_manager.get_detailed_schedule_prompt(
                enhanced_character, plan_framework, enhanced_requirements
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
                "enhanced_character_description": enhanced_character[:200] + "..." if len(enhanced_character) > 200 else enhanced_character,
                "plan_framework": plan_framework[:500] + "..." if len(plan_framework) > 500 else plan_framework,
                "requirements": requirements,
                "enhanced_requirements": enhanced_requirements[:200] + "..." if len(enhanced_requirements) > 200 else enhanced_requirements,
                "role_plugin_used": enhanced_character != character_description or enhanced_requirements != requirements,
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
    
    async def query_role_profile(self, include_metadata: bool = False) -> Dict[str, Any]:
        """
        查询角色资料信息
        
        Args:
            include_metadata: 是否包含元数据信息
            
        Returns:
            角色资料查询结果字典
        """
        try:
            # 检查角色资料插件是否可用
            profile_plugin = self.role_plugin_manager.get_plugin("role_profile")
            if not profile_plugin:
                return {
                    "success": False,
                    "error": "角色资料插件未找到",
                    "available": False
                }
            
            # 检查插件是否启用且有数据
            is_available = await profile_plugin.is_available()
            if not is_available:
                return {
                    "success": False,
                    "error": "角色资料插件未启用或无可用数据",
                    "available": False,
                    "enabled": profile_plugin.enabled
                }
            
            # 获取角色资料内容
            profile_content = await profile_plugin.get_data()
            result = {
                "success": True,
                "available": True,
                "enabled": profile_plugin.enabled,
                "content": profile_content,
                "content_length": len(profile_content) if profile_content else 0,
                "queried_at": datetime.now().isoformat()
            }
            
            # 如果需要包含元数据，添加详细信息
            if include_metadata:
                profile_info = profile_plugin.get_profile_info()
                if profile_info:
                    result.update({
                        "metadata": profile_info,
                        "name": profile_info.get("name"),
                        "tags": profile_info.get("tags", []),
                        "created_at": profile_info.get("created_at"),
                        "updated_at": profile_info.get("updated_at")
                    })
            
            logger.info(f"✅ 角色资料查询成功，内容长度: {result['content_length']}")
            return result
            
        except Exception as e:
            logger.error(f"查询角色资料失败: {e}")
            return {
                "success": False,
                "error": f"查询角色资料时发生错误: {str(e)}",
                "available": False,
                "queried_at": datetime.now().isoformat()
            }
    
    async def search_role_knowledge(self, keywords: List[str], limit: int = 5, min_score: float = 0.0) -> Dict[str, Any]:
        """
        搜索角色知识库
        
        Args:
            keywords: 搜索关键词列表
            limit: 返回结果数量限制
            min_score: 最小相似度分数阈值
            
        Returns:
            知识库搜索结果字典
        """
        try:
            # 检查参数
            if not keywords or not isinstance(keywords, list):
                return {
                    "success": False,
                    "error": "搜索关键词不能为空且必须是列表格式",
                    "keywords": keywords
                }
            
            # 过滤空关键词
            valid_keywords = [kw.strip() for kw in keywords if kw and kw.strip()]
            if not valid_keywords:
                return {
                    "success": False,
                    "error": "没有有效的搜索关键词",
                    "keywords": keywords
                }
            
            # 检查知识库插件是否可用
            kb_plugin = self.role_plugin_manager.get_plugin("role_knowledge_base")
            if not kb_plugin:
                return {
                    "success": False,
                    "error": "角色知识库插件未找到",
                    "available": False,
                    "keywords": valid_keywords
                }
            
            # 检查插件是否启用且有数据
            is_available = await kb_plugin.is_available()
            if not is_available:
                kb_info = kb_plugin.get_knowledge_base_info()
                return {
                    "success": False,
                    "error": "角色知识库插件未启用或知识库未配置",
                    "available": False,
                    "enabled": kb_plugin.enabled,
                    "knowledge_base_info": kb_info,
                    "keywords": valid_keywords
                }
            
            # 执行搜索
            search_results = await kb_plugin.search_knowledge(valid_keywords, limit)
            
            # 根据最小分数过滤结果
            filtered_results = []
            if search_results:
                for result in search_results:
                    score = result.get("score", 0.0)
                    if score >= min_score:
                        filtered_results.append(result)
            
            # 构建返回结果
            result = {
                "success": True,
                "available": True,
                "enabled": kb_plugin.enabled,
                "keywords": valid_keywords,
                "total_results": len(search_results),
                "filtered_results": len(filtered_results),
                "results": filtered_results,
                "search_params": {
                    "limit": limit,
                    "min_score": min_score
                },
                "searched_at": datetime.now().isoformat()
            }
            
            # 添加知识库基本信息
            kb_info = kb_plugin.get_knowledge_base_info()
            if kb_info:
                result["knowledge_base_info"] = {
                    "name": kb_info.get("name"),
                    "description": kb_info.get("description"),
                    "data_count": kb_info.get("data_count", 0),
                    "vector_count": kb_info.get("vector_count", 0)
                }
            
            logger.info(f"✅ 角色知识库搜索完成: {valid_keywords} -> {len(filtered_results)} 个结果")
            return result
            
        except Exception as e:
            logger.error(f"搜索角色知识库失败: {e}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            return {
                "success": False,
                "error": f"搜索角色知识库时发生错误: {str(e)}",
                "available": False,
                "keywords": keywords,
                "searched_at": datetime.now().isoformat()
            }
    
    def get_role_plugin_status(self) -> Dict[str, Any]:
        """
        获取角色插件系统状态
        
        Returns:
            角色插件系统状态字典
        """
        try:
            # 获取插件管理器状态
            status = self.role_plugin_manager.get_status()
            
            # 添加额外的状态信息
            result = {
                "success": True,
                "status": status,
                "checked_at": datetime.now().isoformat(),
                "summary": {
                    "profile_enabled": status.get("profile_plugin", {}).get("enabled", False),
                    "profile_available": status.get("profile_plugin", {}).get("available", False),
                    "knowledge_base_enabled": status.get("knowledge_base_plugin", {}).get("enabled", False),
                    "knowledge_base_available": status.get("knowledge_base_plugin", {}).get("available", False)
                }
            }
            
            # 添加可用性描述
            profile_status = "可用" if result["summary"]["profile_available"] else "不可用"
            kb_status = "可用" if result["summary"]["knowledge_base_available"] else "不可用"
            
            result["description"] = f"角色资料: {profile_status}, 知识库: {kb_status}"
            
            logger.info(f"✅ 角色插件状态查询完成: {result['description']}")
            return result
            
        except Exception as e:
            logger.error(f"获取角色插件状态失败: {e}")
            return {
                "success": False,
                "error": f"获取角色插件状态时发生错误: {str(e)}",
                "checked_at": datetime.now().isoformat()
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
        
        # 查询角色资料工具
        self.register_tool(Tool(
            name="query_role_profile",
            description="查询当前配置的角色资料信息，包括角色的基本设定、性格特点、背景故事等详细信息",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "include_metadata": {
                        "type": "boolean",
                        "description": "是否包含元数据信息（创建时间、更新时间、标签等）",
                        "default": False
                    }
                }
            )
        ))
        
        # 搜索角色知识库工具
        self.register_tool(Tool(
            name="search_role_knowledge",
            description="基于关键词在角色知识库中进行向量相似度搜索，获取相关的角色背景知识、专业信息等",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "搜索关键词列表，用于在知识库中查找相关信息",
                        "minItems": 1
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回结果数量限制，默认使用知识库配置的限制",
                        "minimum": 1,
                        "maximum": 20,
                        "default": 5
                    },
                    "min_score": {
                        "type": "number",
                        "description": "最小相似度分数阈值（0-1），低于此分数的结果将被过滤",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.0
                    }
                },
                required=["keywords"]
            )
        ))
        
        # 获取角色插件状态工具
        self.register_tool(Tool(
            name="get_role_plugin_status",
            description="获取角色插件系统的状态信息，包括角色资料和知识库的配置状态",
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
            
            elif name == "query_role_profile":
                include_metadata = arguments.get("include_metadata", False)
                return await self.generator.query_role_profile(include_metadata)
            
            elif name == "search_role_knowledge":
                keywords = arguments.get("keywords", [])
                limit = arguments.get("limit", 5)
                min_score = arguments.get("min_score", 0.0)
                return await self.generator.search_role_knowledge(keywords, limit, min_score)
            
            elif name == "get_role_plugin_status":
                return self.generator.get_role_plugin_status()
            
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


async def test_local_generation():
    """本地测试生成功能"""
    print("🚀 角色扮演数据生成服务 - 本地测试模式")
    print("=" * 60)
    
    # 创建生成器实例
    generator = RolePlayDataGenerator()
    
    # 等待知识库初始化完成
    await asyncio.sleep(2)
    
    print("🔍 第一步：测试角色插件状态查询...")
    plugin_status = generator.get_role_plugin_status()
    print(f"✅ 插件状态: {plugin_status.get('description', 'N/A')}")
    print(f"📊 角色资料可用: {plugin_status.get('summary', {}).get('profile_available', False)}")
    print(f"📊 知识库可用: {plugin_status.get('summary', {}).get('knowledge_base_available', False)}")
    print("-" * 60)
    
    print("🔍 第二步：测试角色资料查询...")
    profile_result = await generator.query_role_profile(include_metadata=True)
    if profile_result["success"]:
        print("✅ 角色资料查询成功！")
        print(f"📝 内容长度: {profile_result.get('content_length', 0)} 字符")
        if profile_result.get("content"):
            print(f"📋 角色资料预览: {profile_result['content'][:200]}...")
        if profile_result.get("metadata"):
            print(f"🏷️ 角色名称: {profile_result.get('name', 'N/A')}")
            print(f"🏷️ 标签: {profile_result.get('tags', [])}")
    else:
        print(f"❌ 角色资料查询失败: {profile_result.get('error', 'N/A')}")
    print("-" * 60)
    
    print("🔍 第三步：测试角色知识库搜索...")
    search_keywords = ["旅行", "偏好", "喜好", "兴趣", "习惯"]
    kb_result = await generator.search_role_knowledge(
        keywords=search_keywords, 
        limit=3, 
        min_score=0.1
    )
    if kb_result["success"]:
        print("✅ 知识库搜索成功！")
        print(f"🔍 搜索关键词: {kb_result.get('keywords', [])}")
        print(f"📊 总结果数: {kb_result.get('total_results', 0)}")
        print(f"📊 过滤后结果数: {kb_result.get('filtered_results', 0)}")
        
        results = kb_result.get("results", [])
        if results:
            print("📋 搜索结果预览:")
            for i, result in enumerate(results[:2], 1):  # 只显示前2个结果
                score = result.get("score", 0.0)
                content = result.get("content", "")
                print(f"  {i}. 相似度: {score:.3f}")
                print(f"     内容: {content[:150]}...")
        
        kb_info = kb_result.get("knowledge_base_info", {})
        if kb_info:
            print(f"📚 知识库: {kb_info.get('name', 'N/A')}")
            print(f"📚 数据量: {kb_info.get('data_count', 0)} 条，向量: {kb_info.get('vector_count', 0)} 个")
    else:
        print(f"❌ 知识库搜索失败: {kb_result.get('error', 'N/A')}")
    print("-" * 60)
    
    # 测试角色设定
    test_character = """
    方知衡，28岁，云枢大学天文系客座教授
    性格温和，喜欢观星，有条理的生活方式
    平时喜欢在咖啡店工作，热爱阅读和研究
    """
    
    test_requirements = """
    安排一个充实的周六，包括学术研究时间、休闲活动
    希望能平衡工作和生活，体现角色的天文学家身份
    """
    
    print("📝 第四步：测试日程生成功能...")
    print(f"角色设定: {test_character.strip()}")
    print(f"需求描述: {test_requirements.strip()}")
    print("-" * 60)
    
    try:
        # 演示LLM生成搜索关键词
        print("🔍 演示：LLM生成搜索关键词...")
        keywords = await generator._generate_search_keywords(test_character, test_requirements)
        print(f"🏷️ 生成的搜索关键词: {', '.join(keywords)}")
        print("-" * 60)
        
        # 第一步：生成日程计划框架
        print("🎯 第一步：生成日程计划框架...")
        plan_result = await generator.generate_schedule_plan(
            character_description=test_character,
            requirements=test_requirements
        )
        
        if plan_result["success"]:
            print("✅ 日程计划框架生成成功！")
            print(f"🔧 是否使用了角色插件: {plan_result.get('role_plugin_used', False)}")
            print(f"📊 生成时间: {plan_result['generation_time']:.2f}秒")
            print("\n📋 生成的计划框架:")
            print(plan_result["content"])
            print("-" * 60)
            
            # 第二步：生成详细5阶段日程
            print("🎯 第二步：生成详细5阶段日程...")
            detailed_result = await generator.generate_detailed_schedule(
                character_description=test_character,
                plan_framework=plan_result["content"],
                requirements="请确保每个时间段都有具体的活动安排"
            )
            
            if detailed_result["success"]:
                print("✅ 详细日程生成成功！")
                print(f"🔧 是否使用了角色插件: {detailed_result.get('role_plugin_used', False)}")
                print(f"📊 生成时间: {detailed_result['generation_time']:.2f}秒")
                
                # 显示5阶段日程
                if detailed_result.get("phases_data"):
                    print("\n📅 详细5阶段日程:")
                    for phase_key, phase_data in detailed_result["phases_data"].items():
                        print(f"\n🕐 {phase_data['name']} ({phase_data['time_range']}):")
                        for i, activity in enumerate(phase_data['activities'], 1):
                            print(f"  {i}. {activity['activity_name']}")
                            print(f"     📍 地点: {activity.get('location', 'N/A')}")
                            print(f"     🌤️ 天气: {activity.get('weather', 'N/A')}")
                            print(f"     😊 情绪: {activity.get('emotion', 'N/A')}")
                            print(f"     📝 详情: {activity['details'][:100]}...")
                else:
                    print("\n📝 原始生成内容:")
                    print(detailed_result["content"])
            else:
                print(f"❌ 详细日程生成失败: {detailed_result['error']}")
        else:
            print(f"❌ 日程计划框架生成失败: {plan_result['error']}")
            
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理资源
        await generator.cleanup()
        print("\n🏁 测试完成")


async def main():
    """主函数"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 检查启动模式
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # 本地测试模式
        await test_local_generation()
    else:
        # MCP服务器模式
        server = RolePlayDataServer()
        logger.info("🚀 启动角色扮演数据生成MCP服务器...")
        await server.start()


if __name__ == "__main__":
    asyncio.run(main()) 