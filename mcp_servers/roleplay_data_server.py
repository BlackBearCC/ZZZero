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
import csv
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


class AnnualScheduleData:
    """年度日程数据结构"""
    
    def __init__(self):
        self.csv_events = []  # CSV中的年度事件
        self.daily_summaries = {}  # 每日摘要 {day_index: summary}
        self.weekly_compressions = {}  # 每周压缩摘要 {week_index: compressed_summary}
        self.generation_progress = {
            "current_day": 0,
            "total_days": 365,
            "completed_days": 0,
            "started_at": None,
            "estimated_completion": None,
            "status": "not_started"  # not_started, in_progress, completed, paused, error
        }
        self.character_description = ""
        self.csv_file_path = ""


class AnnualScheduleManager:
    """年度日程管理器 - 负责CSV读取和日程数据管理"""
    
    def __init__(self):
        self.current_schedule_data = None
        self.output_dir = Path("workspace/annual_schedule_output")
        self.output_dir.mkdir(exist_ok=True)
        
    def load_csv_schedule(self, csv_file_path: str) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """加载CSV年度日程文件"""
        try:
            csv_path = Path(csv_file_path)
            if not csv_path.exists():
                return False, f"CSV文件不存在: {csv_file_path}", []
            
            events = []
            with open(csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row_idx, row in enumerate(reader, 1):
                    # 验证必要字段
                    required_fields = ['月份', '日期', '活动类型', '具体安排']
                    missing_fields = [field for field in required_fields if not row.get(field, '').strip()]
                    
                    if missing_fields:
                        logger.warning(f"第{row_idx}行缺少必要字段: {missing_fields}")
                        continue
                    
                    # 解析日期范围
                    date_range = row.get('日期', '').strip()
                    start_date, end_date = self._parse_date_range(row.get('月份', ''), date_range)
                    
                    if not start_date:
                        logger.warning(f"第{row_idx}行日期解析失败: {date_range}")
                        continue
                    
                    event = {
                        'row_index': row_idx,
                        'month': row.get('月份', '').strip(),
                        'date_range': date_range,
                        'start_date': start_date,
                        'end_date': end_date,
                        'activity_type': row.get('活动类型', '').strip(),
                        'activity_name': row.get('具体安排', '').strip(),
                        'location': row.get('地点', '').strip(),
                        'remarks': row.get('备注', '').strip(),
                        'duration_days': (end_date - start_date).days + 1
                    }
                    events.append(event)
            
            logger.info(f"✅ 成功加载CSV日程: {len(events)} 个事件")
            return True, f"成功加载 {len(events)} 个年度事件", events
            
        except Exception as e:
            error_msg = f"加载CSV文件失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, []
    
    def _parse_date_range(self, month_str: str, date_range: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """解析日期范围，返回开始和结束日期"""
        try:
            # 解析月份
            month = int(month_str.replace('月', ''))
            year = 2024  # 默认年份
            
            # 解析日期范围 "01-05" 或 "15-17"
            if '-' in date_range:
                start_day, end_day = date_range.split('-')
                start_day = int(start_day)
                end_day = int(end_day)
            else:
                # 单日事件
                start_day = end_day = int(date_range)
            
            start_date = datetime(year, month, start_day)
            end_date = datetime(year, month, end_day)
            
            return start_date, end_date
            
        except Exception as e:
            logger.error(f"日期解析失败 {month_str}-{date_range}: {e}")
            return None, None
    
    def get_day_events(self, day_index: int, base_date: datetime) -> List[Dict[str, Any]]:
        """获取指定天的事件（day_index: 0-364）"""
        if not self.current_schedule_data:
            return []
        
        current_date = base_date + timedelta(days=day_index)
        day_events = []
        
        for event in self.current_schedule_data.csv_events:
            if event['start_date'] <= current_date <= event['end_date']:
                # 计算事件在当天的阶段（第几天）
                event_day_offset = (current_date - event['start_date']).days
                
                day_event = event.copy()
                day_event['event_day_offset'] = event_day_offset
                day_event['is_event_start'] = (event_day_offset == 0)
                day_event['is_event_end'] = (current_date == event['end_date'])
                day_event['current_date'] = current_date
                
                day_events.append(day_event)
        
        return day_events
    
    def save_daily_schedule(self, day_index: int, daily_data: Dict[str, Any]) -> bool:
        """保存单日详细日程"""
        try:
            filename = f"day_{day_index + 1:03d}_{daily_data.get('date', 'unknown')}.json"
            filepath = self.output_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(daily_data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"保存第{day_index + 1}天日程失败: {e}")
            return False
    
    def save_weekly_compression(self, week_index: int, compression_data: Dict[str, Any]) -> bool:
        """保存每周压缩摘要"""
        try:
            filename = f"week_{week_index + 1:02d}_compression.json"
            filepath = self.output_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(compression_data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"保存第{week_index + 1}周压缩摘要失败: {e}")
            return False
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """获取生成进度摘要"""
        if not self.current_schedule_data:
            return {"error": "未加载年度日程数据"}
        
        progress = self.current_schedule_data.generation_progress
        return {
            "current_day": progress["current_day"],
            "completed_days": progress["completed_days"],
            "total_days": progress["total_days"],
            "progress_percentage": (progress["completed_days"] / progress["total_days"]) * 100,
            "status": progress["status"],
            "started_at": progress["started_at"],
            "estimated_completion": progress["estimated_completion"]
        }


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
        # 单日详细日程生成提示词
        self.daily_schedule_prompt = """你是一个专业的角色扮演日程规划专家。请为指定角色生成今天的详细5阶段日程安排。

【角色设定】
{character_description}

【今日基本信息】
- 日期: {current_date}
- 星期: {weekday}
- 天数: 第{day_index}天

【今日预定活动】
{scheduled_events}

【昨日活动摘要】
{previous_day_summary}

【近期背景信息】
{recent_context}

【知识库参考信息】
{knowledge_references}

请按照以下JSON格式生成今日详细5阶段日程：

```json
{{
  "daily_summary": "今日整体安排的简要概述（不超过100字）",
  "character_state": "角色今日的心理状态和精神状况描述",
  "morning": [
    {{
      "activity_name": "活动名称",
      "time_detail": "具体时间安排",
      "location": "活动地点",
      "details": "活动的详细描述，包括背景原因、目的、具体行为、角色心理等"
    }}
  ],
  "noon": [
    {{
      "activity_name": "活动名称",
      "time_detail": "具体时间安排", 
      "location": "活动地点",
      "details": "活动的详细描述"
    }}
  ],
  "afternoon": [
    {{
      "activity_name": "活动名称",
      "time_detail": "具体时间安排",
      "location": "活动地点", 
      "details": "活动的详细描述"
    }}
  ],
  "evening": [
    {{
      "activity_name": "活动名称",
      "time_detail": "具体时间安排",
      "location": "活动地点",
      "details": "活动的详细描述"
    }}
  ],
  "night": [
    {{
      "activity_name": "活动名称",
      "time_detail": "具体时间安排",
      "location": "活动地点",
      "details": "活动的详细描述"
    }}
  ]
}}
```

生成要求：
1. **严格遵循角色设定**：所有活动安排必须符合角色的性格特点、生活习惯、职业特征
2. **融合预定活动**：巧妙地将今日的预定活动融入到5个时间段中，确保活动的合理性和连贯性
3. **考虑昨日衔接**：参考昨日活动摘要，确保今日安排的延续性和逻辑性
4. **利用知识库信息**：结合知识库中的角色背景信息，丰富活动的细节和深度
5. **时间安排合理**：每个时间段的活动要符合该时段的特点，活动间有自然过渡
6. **细节生动具体**：details字段要包含角色的心理活动、具体行为、环境描述等
7. **保持角色一致性**：整天的安排要体现角色的个人风格和生活节奏
- 使用中文回复
- 必须严格按照JSON格式输出"""

        # 周度压缩提示词
        self.weekly_compression_prompt = """你是一个专业的角色扮演数据分析师。请对指定角色过去7天的日程安排进行智能压缩总结。

【角色设定】
{character_description}

【本周时间范围】
第{week_index}周 ({start_date} 至 {end_date})

【本周每日摘要】
{daily_summaries}

【上周压缩摘要】
{previous_week_summary}

【知识库验证信息】
{knowledge_verification}

请按照以下JSON格式生成本周压缩摘要：

```json
{{
  "week_summary": "本周整体情况的综合概述（200-300字）",
  "character_development": "角色在本周的心理状态变化和成长轨迹",
  "key_activities": [
    {{
      "activity_type": "活动类型",
      "frequency": "出现频次",
      "importance": "重要程度评级（1-5）",
      "description": "活动描述和影响"
    }}
  ],
  "relationship_dynamics": "角色与他人的互动情况和关系变化",
  "habit_patterns": "发现的生活习惯模式和行为规律",
  "emotional_trends": "情绪变化趋势和主要感受",
  "continuity_notes": "需要在下周延续或关注的重要事项",
  "character_consistency_check": "角色行为与设定的一致性检查结果"
}}
```

分析要求：
1. **保持角色一致性**：检查本周的活动安排是否符合角色设定，发现并记录任何偏差
2. **提取关键模式**：识别角色的行为模式、情感变化、社交状况等重要趋势
3. **确保连贯性**：分析本周与上周的连接点，为下周的安排提供背景支撑
4. **深度分析**：不仅记录发生了什么，更要分析为什么发生，对角色的意义是什么
5. **前瞻规划**：基于本周的发展，预判下周可能的发展方向和需要关注的重点
6. **验证合理性**：结合知识库信息，验证角色行为的合理性和专业性
- 使用中文回复
- 必须严格按照JSON格式输出"""

        # 角色验证提示词  
        self.character_verification_prompt = """你是一个专业的角色扮演一致性检查专家。请根据角色设定和知识库信息，对近期的行为安排进行验证。

【角色设定】
{character_description}

【检查时间范围】
{time_range}

【近期行为摘要】
{behavior_summary}

【知识库核心信息】
{knowledge_core}

请按照以下格式进行验证分析：

```json
{{
  "consistency_score": "一致性评分（0-100）",
  "verification_result": "总体验证结果（通过/警告/不通过）",
  "analysis_details": {{
    "personality_match": "性格特征匹配度分析",
    "lifestyle_match": "生活方式匹配度分析", 
    "professional_match": "职业特征匹配度分析",
    "relationship_match": "人际关系匹配度分析"
  }},
  "identified_issues": [
    {{
      "issue_type": "问题类型",
      "severity": "严重程度（高/中/低）",
      "description": "问题描述",
      "suggestion": "改进建议"
    }}
  ],
  "positive_highlights": [
    "表现良好的角色特征体现"
  ],
  "adjustment_recommendations": "下一阶段的调整建议"
}}
```

验证要求：
1. **全面性检查**：从性格、生活方式、职业特征、人际关系等多维度验证
2. **专业性判断**：结合知识库中的专业信息，验证角色行为的专业准确性
3. **连贯性分析**：检查角色行为的前后一致性和发展的合理性
4. **建设性反馈**：不仅指出问题，更要提供具体的改进方案
5. **动态适应性**：考虑角色可能的合理变化和成长轨迹
- 使用中文回复
- 必须严格按照JSON格式输出"""
    
    def get_daily_schedule_prompt(self, character_description: str, current_date: str, 
                                 weekday: str, day_index: int, scheduled_events: str, 
                                 previous_day_summary: str, recent_context: str, 
                                 knowledge_references: str) -> str:
        """获取单日详细日程生成提示词"""
        return self.daily_schedule_prompt.format(
            character_description=character_description or "未指定角色设定",
            current_date=current_date,
            weekday=weekday,
            day_index=day_index,
            scheduled_events=scheduled_events or "今日无特别预定活动",
            previous_day_summary=previous_day_summary or "昨日信息不可用",
            recent_context=recent_context or "无近期背景信息",
            knowledge_references=knowledge_references or "无相关知识库信息"
        )
    
    def get_weekly_compression_prompt(self, character_description: str, week_index: int,
                                    start_date: str, end_date: str, daily_summaries: str,
                                    previous_week_summary: str, knowledge_verification: str) -> str:
        """获取周度压缩提示词"""
        return self.weekly_compression_prompt.format(
            character_description=character_description or "未指定角色设定",
            week_index=week_index,
            start_date=start_date,
            end_date=end_date,
            daily_summaries=daily_summaries or "本周日程摘要不可用",
            previous_week_summary=previous_week_summary or "上周摘要不可用",
            knowledge_verification=knowledge_verification or "无知识库验证信息"
        )
        
    def get_character_verification_prompt(self, character_description: str, time_range: str,
                                        behavior_summary: str, knowledge_core: str) -> str:
        """获取角色验证提示词"""
        return self.character_verification_prompt.format(
            character_description=character_description or "未指定角色设定",
            time_range=time_range,
            behavior_summary=behavior_summary or "无行为摘要",
            knowledge_core=knowledge_core or "无知识库核心信息"
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
        
        # 初始化年度日程管理器
        self.annual_manager = AnnualScheduleManager()
        
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
    
    async def generate_annual_schedule(self, csv_file_path: str, character_description: str = "", 
                                     start_from_day: int = 0, max_days: int = 365) -> Dict[str, Any]:
        """
        基于CSV年度日程规划生成365天详细日程
        
        Args:
            csv_file_path: CSV年度日程文件路径
            character_description: 角色设定描述，包含角色的性格特点、生活方式等
            start_from_day: 从第几天开始生成（用于断点续传，0-364）
            max_days: 最大生成天数（用于测试或分段生成）
            
        Returns:
            生成结果字典
        """
        generation_id = f"annual_{int(datetime.now().timestamp())}"
        start_time = datetime.now()
        
        logger.info(f"🚀 开始生成365天详细日程，生成ID: {generation_id}")
        logger.info(f"📋 CSV文件路径: {csv_file_path}")
        logger.info(f"📝 角色描述长度: {len(character_description)} 字符")
        logger.info(f"🎯 生成范围: 第{start_from_day + 1}天 至 第{min(start_from_day + max_days, 365)}天")
        
        try:
            # 第一步：加载CSV年度日程
            logger.info("📊 第一步：加载CSV年度日程文件...")
            success, message, events = self.annual_manager.load_csv_schedule(csv_file_path)
            if not success:
                logger.error(f"❌ CSV加载失败: {message}")
                return {
                    "generation_id": generation_id,
                    "type": "annual_schedule",
                    "success": False,
                    "error": f"CSV加载失败: {message}",
                    "started_at": start_time.isoformat()
                }
            
            logger.info(f"✅ CSV加载成功，共解析到 {len(events)} 个年度事件")
            
            # 第二步：初始化年度日程数据
            schedule_data = AnnualScheduleData()
            schedule_data.csv_events = events
            schedule_data.character_description = character_description
            schedule_data.csv_file_path = csv_file_path
            schedule_data.generation_progress["started_at"] = start_time.isoformat()
            schedule_data.generation_progress["status"] = "in_progress"
            
            self.annual_manager.current_schedule_data = schedule_data
            
            # 第三步：获取增强的角色描述
            logger.info("🔧 第三步：使用角色插件增强角色设定...")
            enhanced_character, _ = await self._enhance_with_role_plugins(character_description, "")
            
            if enhanced_character != character_description:
                logger.info(f"✅ 角色设定已通过插件增强，增强后长度: {len(enhanced_character)} 字符")
                schedule_data.character_description = enhanced_character
            
            # 第四步：开始逐日生成
            logger.info("📅 第四步：开始逐日生成详细日程...")
            base_date = datetime(2024, 1, 1)  # 基准日期
            
            total_generated = 0
            total_errors = 0
            generation_results = []
            
            end_day = min(start_from_day + max_days, 365)
            
            for day_index in range(start_from_day, end_day):
                current_date = base_date + timedelta(days=day_index)
                weekday_name = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][current_date.weekday()]
                
                logger.info(f"📅 正在生成第{day_index + 1}天日程: {current_date.strftime('%Y-%m-%d')} {weekday_name}")
                
                try:
                    # 生成当日详细日程
                    daily_result = await self._generate_single_day_schedule(
                        day_index, current_date, weekday_name, schedule_data
                    )
                    
                    if daily_result["success"]:
                        total_generated += 1
                        schedule_data.generation_progress["completed_days"] = total_generated
                        logger.info(f"✅ 第{day_index + 1}天日程生成成功")
                        
                        # 保存到文件
                        save_success = self.annual_manager.save_daily_schedule(day_index, daily_result)
                        if save_success:
                            logger.info(f"💾 第{day_index + 1}天日程已保存到文件")
                        else:
                            logger.warning(f"⚠️ 第{day_index + 1}天日程保存失败")
                        
                    else:
                        total_errors += 1
                        logger.error(f"❌ 第{day_index + 1}天日程生成失败: {daily_result.get('error', '未知错误')}")
                    
                    generation_results.append(daily_result)
                    
                    # 每7天进行一次周度压缩
                    if (day_index + 1) % 7 == 0:
                        week_index = day_index // 7
                        logger.info(f"📊 第{week_index + 1}周结束，开始周度压缩...")
                        
                        compression_result = await self._perform_weekly_compression(
                            week_index, schedule_data
                        )
                        
                        if compression_result["success"]:
                            logger.info(f"✅ 第{week_index + 1}周压缩摘要生成成功")
                            
                            # 保存周度压缩摘要
                            save_success = self.annual_manager.save_weekly_compression(week_index, compression_result)
                            if save_success:
                                logger.info(f"💾 第{week_index + 1}周压缩摘要已保存到文件")
                            
                            # 进行角色一致性验证
                            verification_result = await self._perform_character_verification(
                                week_index, schedule_data
                            )
                            
                            if verification_result["success"]:
                                logger.info(f"🔍 第{week_index + 1}周角色一致性验证完成")
                                logger.info(f"📊 验证结果: {verification_result.get('content', {}).get('verification_result', 'N/A')}")
                            else:
                                logger.warning(f"⚠️ 第{week_index + 1}周角色一致性验证失败")
                        else:
                            logger.error(f"❌ 第{week_index + 1}周压缩摘要生成失败")
                    
                    # 更新进度
                    schedule_data.generation_progress["current_day"] = day_index + 1
                    
                    # 防止请求过于频繁，适当延迟
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    total_errors += 1
                    logger.error(f"❌ 第{day_index + 1}天生成过程中发生异常: {e}")
                    import traceback
                    logger.error(f"详细错误信息: {traceback.format_exc()}")
                    
                    error_result = {
                        "day_index": day_index,
                        "date": current_date.strftime('%Y-%m-%d'),
                        "success": False,
                        "error": str(e)
                    }
                    generation_results.append(error_result)
            
            # 第五步：完成生成，更新状态
            end_time = datetime.now()
            total_time = (end_time - start_time).total_seconds()
            
            schedule_data.generation_progress["status"] = "completed" if total_errors == 0 else "completed_with_errors"
            schedule_data.generation_progress["estimated_completion"] = end_time.isoformat()
            
            logger.info(f"🎉 年度日程生成完成！")
            logger.info(f"📊 总共生成: {total_generated} 天")
            logger.info(f"❌ 生成失败: {total_errors} 天")
            logger.info(f"⏱️ 总耗时: {total_time:.2f} 秒")
            logger.info(f"📂 输出目录: {self.annual_manager.output_dir}")
            
            result = {
                "generation_id": generation_id,
                "type": "annual_schedule",
                "success": total_errors == 0,
                "csv_file_path": csv_file_path,
                "character_description": character_description[:200] + "..." if len(character_description) > 200 else character_description,
                "enhanced_character_used": enhanced_character != character_description,
                "generation_stats": {
                    "total_days_requested": end_day - start_from_day,
                    "total_days_generated": total_generated,
                    "total_errors": total_errors,
                    "success_rate": (total_generated / (total_generated + total_errors)) * 100 if (total_generated + total_errors) > 0 else 0
                },
                "csv_events": {
                    "total_events": len(events),
                    "event_summary": [{"date_range": e["date_range"], "activity": e["activity_name"][:50]} for e in events[:5]]
                },
                "progress": schedule_data.generation_progress,
                "output_directory": str(self.annual_manager.output_dir),
                "generation_time": total_time,
                "started_at": start_time.isoformat(),
                "completed_at": end_time.isoformat(),
                "daily_results_sample": generation_results[:3] if generation_results else []
            }
            
            # 添加到历史记录
            self._add_to_history(result)
            
            return result
            
        except Exception as e:
            end_time = datetime.now()
            error_msg = f"年度日程生成失败: {str(e)}"
            logger.error(f"❌ {error_msg}")
            import traceback
            logger.error(f"详细错误信息: {traceback.format_exc()}")
            
            return {
                "generation_id": generation_id,
                "type": "annual_schedule",
                "success": False,
                "error": error_msg,
                "csv_file_path": csv_file_path,
                "character_description": character_description[:200] + "..." if len(character_description) > 200 else character_description,
                "started_at": start_time.isoformat(),
                "failed_at": end_time.isoformat()
            }
    
    async def _generate_single_day_schedule(self, day_index: int, current_date: datetime, 
                                           weekday_name: str, schedule_data: AnnualScheduleData) -> Dict[str, Any]:
        """生成单日详细日程"""
        try:
            # 获取当日预定事件
            day_events = self.annual_manager.get_day_events(day_index, datetime(2024, 1, 1))
            
            # 格式化预定事件信息
            if day_events:
                events_text = "\n".join([
                    f"- {event['activity_name']} ({event['activity_type']}) "
                    f"{'[事件开始]' if event['is_event_start'] else ''}"
                    f"{'[事件结束]' if event['is_event_end'] else ''}"
                    f" 备注: {event['remarks']}" if event['remarks'] else ""
                    for event in day_events
                ])
            else:
                events_text = "今日无特别预定活动，安排常规日程"
            
            # 获取昨日摘要
            previous_summary = schedule_data.daily_summaries.get(day_index - 1, "昨日信息不可用") if day_index > 0 else "这是第一天"
            
            # 获取近期背景信息（最近3天的简要摘要）
            recent_context = self._get_recent_context(day_index, schedule_data)
            
            # 搜索知识库获取相关信息
            knowledge_references = await self._search_knowledge_for_day(day_events, schedule_data.character_description)
            
            # 构建提示词
            prompt = self.prompt_manager.get_daily_schedule_prompt(
                character_description=schedule_data.character_description,
                current_date=current_date.strftime('%Y-%m-%d'),
                weekday=weekday_name,
                day_index=day_index + 1,
                scheduled_events=events_text,
                previous_day_summary=previous_summary,
                recent_context=recent_context,
                knowledge_references=knowledge_references
            )
            
            # 调用LLM生成
            success, content = await self.llm_caller.call_llm(
                prompt, max_tokens=4000, temperature=0.7
            )
            
            if success:
                # 解析生成的JSON内容
                daily_data = self._parse_daily_schedule_json(content)
                if daily_data:
                    # 保存当日摘要
                    daily_summary = daily_data.get("daily_summary", "当日日程摘要未生成")
                    schedule_data.daily_summaries[day_index] = daily_summary
                    
                    return {
                        "day_index": day_index,
                        "date": current_date.strftime('%Y-%m-%d'),
                        "weekday": weekday_name,
                        "success": True,
                        "scheduled_events": day_events,
                        "daily_data": daily_data,
                        "knowledge_references_used": len(knowledge_references.split('\n')) if knowledge_references else 0,
                        "generated_at": datetime.now().isoformat()
                    }
                else:
                    return {
                        "day_index": day_index,
                        "date": current_date.strftime('%Y-%m-%d'),
                        "success": False,
                        "error": "JSON解析失败，生成内容格式不正确"
                    }
            else:
                return {
                    "day_index": day_index,
                    "date": current_date.strftime('%Y-%m-%d'),
                    "success": False,
                    "error": f"LLM生成失败: {content}"
                }
                
        except Exception as e:
            return {
                "day_index": day_index,
                "date": current_date.strftime('%Y-%m-%d') if current_date else "unknown",
                "success": False,
                "error": f"单日生成异常: {str(e)}"
            }
    
    def _parse_daily_schedule_json(self, content: str) -> Optional[Dict[str, Any]]:
        """解析单日日程JSON内容"""
        try:
            # 尝试从内容中提取JSON
            json_start = content.find('{')
            json_end = content.rfind('}')
            
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end + 1]
                schedule_data = json.loads(json_str)
                
                # 验证必要字段
                required_phases = ["morning", "noon", "afternoon", "evening", "night"]
                for phase in required_phases:
                    if phase not in schedule_data:
                        logger.warning(f"缺少时间段: {phase}")
                        schedule_data[phase] = []
                
                return schedule_data
            else:
                logger.warning("未找到有效的JSON格式")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            return None
        except Exception as e:
            logger.error(f"解析日程JSON失败: {e}")
            return None
    
    def _get_recent_context(self, day_index: int, schedule_data: AnnualScheduleData) -> str:
        """获取近期背景信息"""
        if day_index <= 0:
            return "这是第一天，没有近期背景信息"
        
        # 获取最近3天的摘要
        recent_summaries = []
        for i in range(max(0, day_index - 3), day_index):
            summary = schedule_data.daily_summaries.get(i)
            if summary:
                date = (datetime(2024, 1, 1) + timedelta(days=i)).strftime('%m-%d')
                recent_summaries.append(f"{date}: {summary}")
        
        if recent_summaries:
            return "最近几天的活动摘要:\n" + "\n".join(recent_summaries)
        else:
            return "近期背景信息不可用"
    
    async def _search_knowledge_for_day(self, day_events: List[Dict[str, Any]], character_description: str) -> str:
        """为当日搜索相关知识库信息"""
        try:
            # 根据当日事件和角色描述生成搜索关键词
            keywords = []
            
            # 从事件中提取关键词
            for event in day_events:
                activity_type = event.get('activity_type', '')
                activity_name = event.get('activity_name', '')
                keywords.extend([activity_type, activity_name])
            
            # 添加角色相关的通用关键词
            if '天文' in character_description:
                keywords.extend(['天文', '观测', '研究'])
            if '教授' in character_description:
                keywords.extend(['教学', '学术', '课程'])
            
            # 过滤和去重
            keywords = list(set([kw.strip() for kw in keywords if kw and len(kw.strip()) > 1]))[:8]
            
            if not keywords:
                return "无相关知识库信息"
            
            # 搜索知识库
            kb_result = await self.search_role_knowledge(keywords, limit=3, min_score=0.1)
            
            if kb_result["success"] and kb_result.get("results"):
                references = []
                for i, result in enumerate(kb_result["results"][:3], 1):
                    content = result.get("content", "")
                    if len(content) > 150:
                        content = content[:150] + "..."
                    references.append(f"参考{i}: {content}")
                
                return "\n".join(references)
            else:
                return "知识库搜索无相关结果"
                
        except Exception as e:
            logger.error(f"知识库搜索失败: {e}")
            return "知识库搜索失败"
    
    async def _perform_weekly_compression(self, week_index: int, schedule_data: AnnualScheduleData) -> Dict[str, Any]:
        """执行周度压缩"""
        try:
            logger.info(f"📊 开始第{week_index + 1}周压缩摘要生成...")
            
            # 获取本周的每日摘要
            start_day = week_index * 7
            end_day = min(start_day + 7, 365)
            
            daily_summaries = []
            for day_idx in range(start_day, end_day):
                if day_idx in schedule_data.daily_summaries:
                    date = (datetime(2024, 1, 1) + timedelta(days=day_idx)).strftime('%m-%d')
                    summary = schedule_data.daily_summaries[day_idx]
                    daily_summaries.append(f"{date}: {summary}")
            
            daily_summaries_text = "\n".join(daily_summaries) if daily_summaries else "本周日程摘要不可用"
            
            # 获取上周压缩摘要
            previous_week_summary = schedule_data.weekly_compressions.get(week_index - 1, "上周摘要不可用") if week_index > 0 else "这是第一周"
            
            # 搜索知识库进行验证
            verification_keywords = ["周度总结", "行为模式", "性格特征", "生活习惯"]
            kb_result = await self.search_role_knowledge(verification_keywords, limit=2, min_score=0.1)
            
            knowledge_verification = "无知识库验证信息"
            if kb_result["success"] and kb_result.get("results"):
                verification_texts = [result.get("content", "")[:200] for result in kb_result["results"][:2]]
                knowledge_verification = "\n".join(verification_texts)
            
            # 构建压缩提示词
            start_date = (datetime(2024, 1, 1) + timedelta(days=start_day)).strftime('%Y-%m-%d')
            end_date = (datetime(2024, 1, 1) + timedelta(days=end_day - 1)).strftime('%Y-%m-%d')
            
            prompt = self.prompt_manager.get_weekly_compression_prompt(
                character_description=schedule_data.character_description,
                week_index=week_index + 1,
                start_date=start_date,
                end_date=end_date,
                daily_summaries=daily_summaries_text,
                previous_week_summary=previous_week_summary,
                knowledge_verification=knowledge_verification
            )
            
            # 调用LLM生成压缩摘要
            success, content = await self.llm_caller.call_llm(
                prompt, max_tokens=3000, temperature=0.5
            )
            
            if success:
                # 解析压缩结果
                compression_data = self._parse_weekly_compression_json(content)
                if compression_data:
                    # 保存到周度压缩记录
                    week_summary = compression_data.get("week_summary", "本周摘要未生成")
                    schedule_data.weekly_compressions[week_index] = week_summary
                    
                    logger.info(f"✅ 第{week_index + 1}周压缩摘要生成成功")
                    
                    return {
                        "week_index": week_index,
                        "start_date": start_date,
                        "end_date": end_date,
                        "success": True,
                        "compression_data": compression_data,
                        "daily_count": len(daily_summaries),
                        "generated_at": datetime.now().isoformat()
                    }
                else:
                    return {
                        "week_index": week_index,
                        "success": False,
                        "error": "周度压缩JSON解析失败"
                    }
            else:
                return {
                    "week_index": week_index,
                    "success": False,
                    "error": f"周度压缩LLM生成失败: {content}"
                }
                
        except Exception as e:
            logger.error(f"周度压缩执行失败: {e}")
            return {
                "week_index": week_index,
                "success": False,
                "error": f"周度压缩异常: {str(e)}"
            }
    
    def _parse_weekly_compression_json(self, content: str) -> Optional[Dict[str, Any]]:
        """解析周度压缩JSON内容"""
        try:
            # 尝试从内容中提取JSON
            json_start = content.find('{')
            json_end = content.rfind('}')
            
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end + 1]
                compression_data = json.loads(json_str)
                return compression_data
            else:
                logger.warning("周度压缩未找到有效的JSON格式")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"周度压缩JSON解析失败: {e}")
            return None
        except Exception as e:
            logger.error(f"解析周度压缩JSON失败: {e}")
            return None
    
    async def _perform_character_verification(self, week_index: int, schedule_data: AnnualScheduleData) -> Dict[str, Any]:
        """执行角色一致性验证"""
        try:
            logger.info(f"🔍 开始第{week_index + 1}周角色一致性验证...")
            
            # 获取本周行为摘要
            current_week_summary = schedule_data.weekly_compressions.get(week_index, "本周摘要不可用")
            
            # 构建时间范围
            start_day = week_index * 7
            end_day = min(start_day + 7, 365)
            start_date = (datetime(2024, 1, 1) + timedelta(days=start_day)).strftime('%Y-%m-%d')
            end_date = (datetime(2024, 1, 1) + timedelta(days=end_day - 1)).strftime('%Y-%m-%d')
            time_range = f"第{week_index + 1}周 ({start_date} 至 {end_date})"
            
            # 搜索知识库获取核心角色信息
            core_keywords = ["角色设定", "性格特征", "职业特点", "生活方式", "个人爱好"]
            kb_result = await self.search_role_knowledge(core_keywords, limit=3, min_score=0.2)
            
            knowledge_core = "无知识库核心信息"
            if kb_result["success"] and kb_result.get("results"):
                core_texts = [result.get("content", "")[:300] for result in kb_result["results"][:3]]
                knowledge_core = "\n".join(core_texts)
            
            # 构建验证提示词
            prompt = self.prompt_manager.get_character_verification_prompt(
                character_description=schedule_data.character_description,
                time_range=time_range,
                behavior_summary=current_week_summary,
                knowledge_core=knowledge_core
            )
            
            # 调用LLM进行验证
            success, content = await self.llm_caller.call_llm(
                prompt, max_tokens=2000, temperature=0.3
            )
            
            if success:
                # 解析验证结果
                verification_data = self._parse_character_verification_json(content)
                if verification_data:
                    logger.info(f"✅ 第{week_index + 1}周角色验证完成")
                    
                    return {
                        "week_index": week_index,
                        "time_range": time_range,
                        "success": True,
                        "content": verification_data,
                        "generated_at": datetime.now().isoformat()
                    }
                else:
                    return {
                        "week_index": week_index,
                        "success": False,
                        "error": "角色验证JSON解析失败"
                    }
            else:
                return {
                    "week_index": week_index,
                    "success": False,
                    "error": f"角色验证LLM生成失败: {content}"
                }
                
        except Exception as e:
            logger.error(f"角色验证执行失败: {e}")
            return {
                "week_index": week_index,
                "success": False,
                "error": f"角色验证异常: {str(e)}"
            }
    
    def _parse_character_verification_json(self, content: str) -> Optional[Dict[str, Any]]:
        """解析角色验证JSON内容"""
        try:
            # 尝试从内容中提取JSON
            json_start = content.find('{')
            json_end = content.rfind('}')
            
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end + 1]
                verification_data = json.loads(json_str)
                return verification_data
            else:
                logger.warning("角色验证未找到有效的JSON格式")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"角色验证JSON解析失败: {e}")
            return None
        except Exception as e:
            logger.error(f"解析角色验证JSON失败: {e}")
            return None
    
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
        
        # 生成365天年度详细日程工具
        self.register_tool(Tool(
            name="generate_annual_schedule",
            description="基于CSV年度日程规划生成365天详细的每日5阶段日程安排。自动使用预设的角色配置和CSV文件，无需额外参数",
            inputSchema=ToolInputSchema(
                type="object",
                properties={}
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
            
            if name == "generate_annual_schedule":
                # 使用默认配置，无需参数
                csv_file_path = "workspace/方知衡年度日程规划.csv"  # 默认CSV文件路径
                character_description = ""  # 从角色插件中自动获取
                start_from_day = 0  # 从第1天开始
                max_days = 3  # 演示模式：只生成前3天
                
                logger.info(f"📋 开始生成年度日程）：CSV文件={csv_file_path}, 生成天数={max_days}")
                
                return await self.generator.generate_annual_schedule(
                    csv_file_path, character_description, start_from_day, max_days
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
    print("🚀 角色扮演数据生成服务 - 本地测试模式（365天年度日程生成）")
    print("=" * 80)
    
    # 创建生成器实例
    generator = RolePlayDataGenerator()
    
    # 等待知识库初始化完成
    await asyncio.sleep(2)
    
    print("🔍 第一步：测试角色插件状态查询...")
    plugin_status = generator.get_role_plugin_status()
    print(f"✅ 插件状态: {plugin_status.get('description', 'N/A')}")
    print(f"📊 角色资料可用: {plugin_status.get('summary', {}).get('profile_available', False)}")
    print(f"📊 知识库可用: {plugin_status.get('summary', {}).get('knowledge_base_available', False)}")
    print("-" * 80)
    
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
    print("-" * 80)
    
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
    print("-" * 80)
    
    # 测试年度日程生成
    csv_file_path = "workspace/方知衡年度日程规划.csv"
    test_character = """
    方知衡，28岁，云枢大学天文系客座教授、博士
    性格清冷但不傲慢，有责任感，善于内省
    平时喜欢在咖啡店工作，热爱阅读和天文研究
    作息规律，不喜欢熬夜，有每日晨跑习惯
    """
    
    print("📝 第四步：测试365天年度日程生成功能...")
    print(f"📂 CSV文件路径: {csv_file_path}")
    print(f"👤 角色设定: {test_character.strip()}")
    print(f"🎯 测试生成天数: 前3天（演示模式）")
    print("-" * 80)
    
    try:
        # 测试年度日程生成（只生成前3天作为演示）
        print("🎯 开始生成365天年度详细日程（演示：前3天）...")
        annual_result = await generator.generate_annual_schedule(
            csv_file_path=csv_file_path,
            character_description=test_character,
            start_from_day=0,
            max_days=3  # 演示模式，只生成前3天
        )
        
        if annual_result["success"]:
            print("✅ 年度日程生成成功！")
            print(f"🔧 是否使用了角色插件增强: {annual_result.get('enhanced_character_used', False)}")
            print(f"📊 生成统计: {annual_result.get('generation_stats', {})}")
            print(f"📋 CSV事件: {annual_result.get('csv_events', {})}")
            print(f"📂 输出目录: {annual_result.get('output_directory', 'N/A')}")
            print(f"⏱️ 总耗时: {annual_result.get('generation_time', 0):.2f} 秒")
            
            # 显示每日生成结果样例
            daily_samples = annual_result.get("daily_results_sample", [])
            if daily_samples:
                print("\n📅 每日生成结果样例:")
                for sample in daily_samples:
                    if sample.get("success"):
                        day_index = sample.get("day_index", 0)
                        date = sample.get("date", "unknown")
                        weekday = sample.get("weekday", "unknown")
                        print(f"\n📅 第{day_index + 1}天 ({date} {weekday}):")
                        
                        daily_data = sample.get("daily_data", {})
                        if daily_data:
                            print(f"   📝 当日摘要: {daily_data.get('daily_summary', 'N/A')}")
                            print(f"   😊 角色状态: {daily_data.get('character_state', 'N/A')}")
                            
                            # 显示5个时间段的活动简要
                            phases = ["morning", "noon", "afternoon", "evening", "night"]
                            phase_names = ["上午", "中午", "下午", "晚上", "夜间"]
                            for phase, name in zip(phases, phase_names):
                                activities = daily_data.get(phase, [])
                                if activities:
                                    print(f"   🕐 {name}: {len(activities)} 个活动")
                                    for act in activities[:2]:  # 只显示前2个活动
                                        print(f"      • {act.get('activity_name', 'N/A')}")
                        
                        kb_refs = sample.get("knowledge_references_used", 0)
                        print(f"   📚 使用知识库参考: {kb_refs} 条")
                    else:
                        day_index = sample.get("day_index", 0)
                        error = sample.get("error", "未知错误")
                        print(f"❌ 第{day_index + 1}天生成失败: {error}")
            
            # 显示生成进度
            progress = annual_result.get("progress", {})
            if progress:
                print(f"\n📊 生成进度: {progress}")
            
        else:
            print(f"❌ 年度日程生成失败: {annual_result.get('error', '未知错误')}")
            
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理资源
        await generator.cleanup()
        print("\n🏁 测试完成")
        print(f"📂 如果生成成功，请查看输出目录: workspace/annual_schedule_output/")
        print(f"💡 提示：完整365天生成请使用max_days=365参数")


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