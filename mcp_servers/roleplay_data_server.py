#!/usr/bin/env python3
"""
角色扮演数据生成服务器 - 简化版MCP服务
两步核心流程：
1. 根据CSV规划生成中等日期安排
2. 根据中等安排生成每天5时间段具体安排及概要
"""
import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import asyncio
import logging
import csv
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

# 使用本地mcp模块
from mcp.server.stdio_server import StdioMCPServer
from mcp.types import Tool, ToolInputSchema

# 导入项目的LLM系统
from src.llm.base import LLMFactory
from src.core.types import LLMConfig, Message, MessageRole

# 确保LLM提供商已注册
try:
    from src.llm.doubao import DoubaoLLM
except ImportError:
    pass

logger = logging.getLogger(__name__)


class SimpleScheduleData:
    """简化的日程数据结构"""
    
    def __init__(self):
        self.csv_events = []  # CSV中的年度事件
        self.medium_arrangements = []  # 中等粒度安排（第一步输出）
        self.daily_summaries = {}  # 每日概要 {day_index: summary}
        self.character_description = ""
        self.csv_file_path = ""


class SimpleLLMCaller:
    """简化的LLM调用器"""
    
    def __init__(self):
        self.llm_provider = None
        self._initialize_llm()
        
    def _initialize_llm(self):
        """初始化LLM提供者"""
        provider = os.getenv("LLM_PROVIDER", "doubao")
        model_name = os.getenv("LLM_MODEL_NAME", "ep-20250221154410-vh78x")
        api_key = os.getenv("ARK_API_KEY") or os.getenv("DOUBAO_API_KEY")
        api_base = os.getenv("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
        
        try:
            llm_config = LLMConfig(
                provider=provider,
                model_name=model_name,
                api_key=api_key,
                api_base=api_base,
                temperature=0.4,
                timeout=600
            )
            
            self.llm_provider = LLMFactory.create(llm_config)
            logger.info(f"✅ LLM初始化成功: {provider}/{model_name}")
            
        except Exception as e:
            logger.error(f"❌ LLM初始化失败: {e}")
            self.llm_provider = None
    
    async def call_llm(self, prompt: str, max_tokens: int = 2000) -> Tuple[bool, str]:
        """调用LLM"""
        if not self.llm_provider:
            return False, "LLM服务未初始化"
        
        try:
            await self.llm_provider.initialize()
            
            messages = [
                Message(role=MessageRole.SYSTEM, 
                       content="你是专业的日程规划助手，能够生成详细实用的日程安排。"),
                Message(role=MessageRole.USER, content=prompt)
            ]
            
            response = await self.llm_provider.generate(
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7
            )
            
            return True, response.content
            
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return False, f"LLM调用失败: {str(e)}"
    
    async def cleanup(self):
        """清理资源"""
        if self.llm_provider:
            try:
                await self.llm_provider.cleanup()
            except Exception as e:
                logger.warning(f"LLM清理失败: {e}")


class SimpleScheduleGenerator:
    """简化的日程生成器"""
    
    def __init__(self):
        self.llm_caller = SimpleLLMCaller()
        self.output_dir = Path("workspace/simple_schedule_output")
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
                    # 基本字段验证
                    if not all(row.get(field, '').strip() for field in ['月份', '日期', '活动类型', '具体安排']):
                        logger.warning(f"第{row_idx}行数据不完整，跳过")
                        continue
                    
                    # 解析日期
                    start_date, end_date = self._parse_date_range(row.get('月份', ''), row.get('日期', ''))
                    if not start_date:
                        logger.warning(f"第{row_idx}行日期解析失败，跳过")
                        continue
                    
                    event = {
                        'month': row.get('月份', '').strip(),
                        'date_range': row.get('日期', '').strip(),
                        'start_date': start_date,
                        'end_date': end_date,
                        'activity_type': row.get('活动类型', '').strip(),
                        'activity_name': row.get('具体安排', '').strip(),
                        'location': row.get('地点', '').strip(),
                        'remarks': row.get('备注', '').strip()
                    }
                    events.append(event)
            
            logger.info(f"✅ 成功加载 {len(events)} 个年度事件")
            return True, f"成功加载 {len(events)} 个年度事件", events
            
        except Exception as e:
            error_msg = f"加载CSV文件失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, []
    
    def _parse_date_range(self, month_str: str, date_range: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """解析日期范围，映射到2025年6月24日开始的557天"""
        try:
            month = int(month_str.replace('月', ''))
            base_date = datetime(2025, 6, 24)
            total_days = 557  # 到2027年1月1日
            
            # 将原始12个月映射到557天
            month_start_ratio = (month - 1) / 12.0
            month_end_ratio = month / 12.0
            
            # 解析日期范围
            if '-' in date_range:
                start_day, end_day = date_range.split('-')
                start_day = int(start_day)
                end_day = int(end_day)
            else:
                start_day = end_day = int(date_range)
            
            # 计算在月份内的位置
            days_in_month = 31
            day_start_ratio = (start_day - 1) / days_in_month
            day_end_ratio = end_day / days_in_month
            
            # 计算在整个557天中的位置
            absolute_start_ratio = month_start_ratio + (month_end_ratio - month_start_ratio) * day_start_ratio
            absolute_end_ratio = month_start_ratio + (month_end_ratio - month_start_ratio) * day_end_ratio
            
            start_offset_days = int(absolute_start_ratio * total_days)
            end_offset_days = int(absolute_end_ratio * total_days)
            
            start_date = base_date + timedelta(days=start_offset_days)
            end_date = base_date + timedelta(days=end_offset_days)
            
            return start_date, end_date
            
        except Exception as e:
            logger.error(f"日期解析失败 {month_str}-{date_range}: {e}")
            return None, None
    
    async def generate_schedule(self, csv_file_path: str, character_description: str = "", 
                               max_days: int = 7) -> Dict[str, Any]:
        """
        两步生成日程：
        1. 生成中等日期安排
        2. 生成每天具体安排
        """
        start_time = datetime.now()
        generation_id = f"simple_{int(start_time.timestamp())}"
        
        logger.info(f"🚀 开始简化日程生成，生成ID: {generation_id}")
        logger.info(f"📋 CSV文件: {csv_file_path}")
        logger.info(f"🎯 生成天数: {max_days}")
        
        try:
            # 加载CSV
            success, message, events = self.load_csv_schedule(csv_file_path)
            if not success:
                return {"success": False, "error": message}
            
            # 初始化数据
            schedule_data = SimpleScheduleData()
            schedule_data.csv_events = events
            schedule_data.character_description = character_description
            schedule_data.csv_file_path = csv_file_path
            
            # 第一步：生成中等日期安排
            logger.info("📊 第一步：生成中等日期安排...")
            medium_success = await self._generate_medium_arrangements(schedule_data, max_days)
            if not medium_success:
                return {"success": False, "error": "中等日期安排生成失败"}
            
            # 第二步：生成每天具体安排
            logger.info("📅 第二步：生成每天具体安排...")
            daily_results = await self._generate_daily_arrangements(schedule_data, max_days)
            
            # 保存为CSV
            csv_file = await self._save_to_csv(daily_results, max_days)
            
            end_time = datetime.now()
            total_time = (end_time - start_time).total_seconds()
            
            return {
                "generation_id": generation_id,
                "success": True,
                "csv_file_path": csv_file_path,
                "character_description": character_description[:100] + "..." if len(character_description) > 100 else character_description,
                "max_days": max_days,
                "csv_events_count": len(events),
                "medium_arrangements_count": len(schedule_data.medium_arrangements),
                "daily_results": daily_results,
                "output_csv_file": csv_file,
                "generation_time": total_time,
                "started_at": start_time.isoformat(),
                "completed_at": end_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ 日程生成失败: {e}")
            return {
                "generation_id": generation_id,
                "success": False,
                "error": f"日程生成失败: {str(e)}",
                "started_at": start_time.isoformat()
            }
    
    async def _generate_medium_arrangements(self, schedule_data: SimpleScheduleData, max_days: int) -> bool:
        """第一步：生成中等粒度的日期安排"""
        try:
            # 构建CSV事件摘要
            events_summary = "年度重要事件安排:\n"
            for event in schedule_data.csv_events:
                events_summary += f"- {event['start_date'].strftime('%Y-%m-%d')} 至 {event['end_date'].strftime('%Y-%m-%d')}: {event['activity_type']} - {event['activity_name']}\n"
            
            # 构建中等安排生成提示词
            prompt = f"""请根据以下年度事件安排，为角色制定{max_days}天的中等粒度日期安排。

【角色设定】
{schedule_data.character_description if schedule_data.character_description else "未指定角色，请设定一个合理的日常生活角色"}

【年度事件安排】
{events_summary}

【时间范围】
从2025年6月24日开始的{max_days}天

请生成中等粒度的安排（以3-7天为一个周期），为后续每日具体安排提供框架。

请按以下JSON格式输出：
{{
  "arrangements": [
    {{
      "period": "第1-3天",
      "theme": "安排主题",
      "focus": "重点关注内容",
      "description": "这几天的整体安排描述"
    }}
  ]
}}

要求：
1. 合理分配时间周期
2. 结合年度事件制定主题
3. 为每日具体安排提供指导框架
4. 使用中文回复"""

            success, content = await self.llm_caller.call_llm(prompt, max_tokens=2000)
            
            if success:
                # 解析JSON
                arrangements = self._parse_json_content(content)
                if arrangements and "arrangements" in arrangements:
                    schedule_data.medium_arrangements = arrangements["arrangements"]
                    logger.info(f"✅ 成功生成 {len(schedule_data.medium_arrangements)} 个中等安排")
                    return True
                else:
                    logger.error("❌ 中等安排JSON解析失败")
                    return False
            else:
                logger.error(f"❌ 中等安排LLM生成失败: {content}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 生成中等安排异常: {e}")
            return False
    
    async def _generate_daily_arrangements(self, schedule_data: SimpleScheduleData, max_days: int) -> List[Dict[str, Any]]:
        """第二步：生成每天具体的5时间段安排"""
        daily_results = []
        base_date = datetime(2025, 6, 24)
        
        for day_index in range(max_days):
            current_date = base_date + timedelta(days=day_index)
            weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][current_date.weekday()]
            
            logger.info(f"📅 生成第{day_index + 1}天: {current_date.strftime('%Y-%m-%d')} {weekday}")
            
            try:
                # 获取当天相关的事件
                day_events = self._get_day_events(day_index, base_date, schedule_data.csv_events)
                
                # 获取相关的中等安排
                relevant_arrangement = self._get_relevant_arrangement(day_index, schedule_data.medium_arrangements)
                
                # 获取前一天的概要
                previous_summary = schedule_data.daily_summaries.get(day_index - 1, "这是第一天") if day_index > 0 else "这是第一天"
                
                # 构建每日安排生成提示词
                prompt = f"""请为角色制定今天的详细5时间段日程安排。

【角色设定】
{schedule_data.character_description if schedule_data.character_description else "普通上班族，规律作息"}

【今日基本信息】
- 日期: {current_date.strftime('%Y-%m-%d')}
- 星期: {weekday}
- 天数: 第{day_index + 1}天

【今日预定事件】
{day_events if day_events else "今日无特殊事件"}

【中等安排指导】
{relevant_arrangement if relevant_arrangement else "按常规安排"}

【昨日概要】
{previous_summary}

请按以下JSON格式制定今日详细安排：
{{
  "daily_summary": "今日简要概述（供明天参考）",
  "morning": ["上午活动1", "上午活动2"],
  "noon": ["中午活动1", "中午活动2"],
  "afternoon": ["下午活动1", "下午活动2"],
  "evening": ["晚上活动1", "晚上活动2"],
  "night": ["夜间活动1"]
}}

要求：
1. 每个时间段安排2-3个活动
2. 活动要具体可执行
3. 符合角色设定和作息习惯
4. daily_summary要简洁，为明天提供背景
5. 使用中文回复"""

                success, content = await self.llm_caller.call_llm(prompt, max_tokens=3000)
                
                if success:
                    daily_data = self._parse_json_content(content)
                    if daily_data and "daily_summary" in daily_data:
                        # 保存当日概要供下一天使用
                        schedule_data.daily_summaries[day_index] = daily_data["daily_summary"]
                        
                        daily_result = {
                            "day": day_index + 1,
                            "date": current_date.strftime('%Y-%m-%d'),
                            "weekday": weekday,
                            "success": True,
                            "daily_summary": daily_data["daily_summary"],
                            "morning": daily_data.get("morning", []),
                            "noon": daily_data.get("noon", []),
                            "afternoon": daily_data.get("afternoon", []),
                            "evening": daily_data.get("evening", []),
                            "night": daily_data.get("night", [])
                        }
                        
                        logger.info(f"✅ 第{day_index + 1}天生成成功")
                        daily_results.append(daily_result)
                    else:
                        logger.error(f"❌ 第{day_index + 1}天JSON解析失败")
                        daily_results.append({
                            "day": day_index + 1,
                            "date": current_date.strftime('%Y-%m-%d'),
                            "success": False,
                            "error": "JSON解析失败"
                        })
                else:
                    logger.error(f"❌ 第{day_index + 1}天LLM生成失败")
                    daily_results.append({
                        "day": day_index + 1,
                        "date": current_date.strftime('%Y-%m-%d'),
                        "success": False,
                        "error": f"LLM生成失败: {content}"
                    })
                
                # 防止请求过快
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"❌ 第{day_index + 1}天生成异常: {e}")
                daily_results.append({
                    "day": day_index + 1,
                    "date": current_date.strftime('%Y-%m-%d'),
                    "success": False,
                    "error": f"生成异常: {str(e)}"
                })
        
        return daily_results
    
    def _get_day_events(self, day_index: int, base_date: datetime, events: List[Dict[str, Any]]) -> str:
        """获取当天的事件"""
        current_date = base_date + timedelta(days=day_index)
        day_events = []
        
        for event in events:
            if event['start_date'] <= current_date <= event['end_date']:
                day_events.append(f"- {event['activity_type']}: {event['activity_name']}")
        
        return "\n".join(day_events) if day_events else ""
    
    def _get_relevant_arrangement(self, day_index: int, arrangements: List[Dict[str, Any]]) -> str:
        """获取相关的中等安排"""
        if not arrangements:
            return ""
        
        # 简单的匹配逻辑，可以根据需要优化
        for arr in arrangements:
            period = arr.get("period", "")
            if f"第{day_index + 1}" in period or f"{day_index + 1}天" in period:
                return f"主题: {arr.get('theme', '')}\n重点: {arr.get('focus', '')}\n描述: {arr.get('description', '')}"
        
        # 如果没有直接匹配，返回第一个作为参考
        if arrangements:
            arr = arrangements[0]
            return f"参考主题: {arr.get('theme', '')}\n参考重点: {arr.get('focus', '')}"
        
        return ""
    
    def _parse_json_content(self, content: str) -> Optional[Dict[str, Any]]:
        """解析JSON内容"""
        try:
            json_start = content.find('{')
            json_end = content.rfind('}')
            
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end + 1]
                return json.loads(json_str)
            else:
                logger.warning("未找到有效的JSON格式")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            return None
        except Exception as e:
            logger.error(f"解析JSON异常: {e}")
            return None
    
    async def _save_to_csv(self, daily_results: List[Dict[str, Any]], max_days: int) -> str:
        """保存结果为CSV文件"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"schedule_{max_days}days_{timestamp}.csv"
            filepath = self.output_dir / filename
            
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
                fieldnames = ['天数', '日期', '星期', '时间段', '活动安排', '当日概要']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for result in daily_results:
                    if not result.get("success", False):
                        continue
                    
                    day = result["day"]
                    date = result["date"]
                    weekday = result["weekday"]
                    summary = result["daily_summary"]
                    
                    # 写入5个时间段
                    time_phases = [
                        ("上午", result.get("morning", [])),
                        ("中午", result.get("noon", [])),
                        ("下午", result.get("afternoon", [])),
                        ("晚上", result.get("evening", [])),
                        ("夜间", result.get("night", []))
                    ]
                    
                    for phase_name, activities in time_phases:
                        activity_text = "; ".join(activities) if activities else "无安排"
                        writer.writerow({
                            '天数': day,
                            '日期': date,
                            '星期': weekday,
                            '时间段': phase_name,
                            '活动安排': activity_text,
                            '当日概要': summary if phase_name == "上午" else ""  # 只在上午显示概要
                        })
            
            logger.info(f"✅ CSV文件保存成功: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"❌ 保存CSV文件失败: {e}")
            return ""
    
    async def cleanup(self):
        """清理资源"""
        if self.llm_caller:
            await self.llm_caller.cleanup()


class SimpleRolePlayDataServer(StdioMCPServer):
    """简化的角色扮演数据生成MCP服务器"""
    
    def __init__(self):
        super().__init__("simple-roleplay-data-server")
        self.generator = SimpleScheduleGenerator()
        self._register_tools()
    
    def _register_tools(self):
        """注册工具"""
        
        # 生成日程安排工具
        self.register_tool(Tool(
            name="generate_schedule",
            description="生成角色扮演日程安排。根据年度规划CSV文件，为方知衡（天文教授）生成指定天数的详细日程，包含每天5个时间段（上午/中午/下午/晚上/夜间）的具体活动安排，并输出CSV文件",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "max_days": {
                        "type": "integer",
                        "description": "生成的天数，默认7天",
                        "minimum": 1,
                        "maximum": 557,
                        "default": 7
                    }
                },
                required=["max_days"]
            )
        ))
    
    async def _call_tool(self, name: str, arguments: Dict[str, Any], context) -> Dict[str, Any]:
        """处理工具调用"""
        try:
            logger.info(f"简化日程生成工具调用: {name}")
            logger.info(f"参数: {arguments}")
            
            if name == "generate_schedule":
                # 硬编码CSV文件路径和角色描述
                csv_file_path = "workspace/方知衡年度日程规划.csv"
                character_description = """
                方知衡，28岁，天文系客座教授
                性格清冷但负责任，喜欢在咖啡店工作
                作息规律，有晨跑习惯，热爱阅读和研究
                """
                max_days = arguments.get("max_days", 7)
                
                return await self.generator.generate_schedule(
                    csv_file_path, character_description, max_days
                )
            
            else:
                return {"error": f"未知工具: {name}"}
                
        except Exception as e:
            logger.error(f"工具调用失败 {name}: {e}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")
            return {
                "error": f"工具调用失败: {str(e)}",
                "tool_name": name,
                "arguments": arguments,
                "timestamp": datetime.now().isoformat()
            }
    
    async def cleanup(self):
        """清理资源"""
        if hasattr(self, 'generator') and self.generator:
            await self.generator.cleanup()


async def test_simple_generation():
    """测试简化版生成功能"""
    print("🚀 简化角色扮演数据生成服务 - 本地测试")
    print("=" * 60)
    
    generator = SimpleScheduleGenerator()
    
    try:
        # 测试参数
        csv_file_path = "workspace/方知衡年度日程规划.csv"
        character_description = """
        方知衡，28岁，天文系客座教授
        性格清冷但负责任，喜欢在咖啡店工作
        作息规律，有晨跑习惯，热爱阅读和研究
        """
        max_days = 3  # 测试3天
        
        print(f"📂 CSV文件: {csv_file_path}")
        print(f"👤 角色: {character_description.strip()}")
        print(f"📅 生成天数: {max_days}")
        print("-" * 60)
        
        # 开始生成
        result = await generator.generate_schedule(csv_file_path, character_description, max_days)
        
        if result["success"]:
            print("✅ 生成成功！")
            print(f"🆔 生成ID: {result.get('generation_id', 'N/A')}")
            print(f"📊 CSV事件数: {result.get('csv_events_count', 0)}")
            print(f"📊 中等安排数: {result.get('medium_arrangements_count', 0)}")
            print(f"⏱️ 总耗时: {result.get('generation_time', 0):.2f} 秒")
            print(f"📁 输出CSV: {result.get('output_csv_file', 'N/A')}")
            
            # 显示每日结果
            print("\n📅 每日生成结果:")
            daily_results = result.get("daily_results", [])
            for daily in daily_results[:3]:  # 只显示前3天
                if daily.get("success"):
                    print(f"\n第{daily['day']}天 ({daily['date']} {daily['weekday']}):")
                    print(f"  📝 概要: {daily['daily_summary']}")
                    print(f"  🌅 上午: {', '.join(daily.get('morning', []))}")
                    print(f"  ☀️ 中午: {', '.join(daily.get('noon', []))}")
                    print(f"  🌇 下午: {', '.join(daily.get('afternoon', []))}")
                    print(f"  🌃 晚上: {', '.join(daily.get('evening', []))}")
                    print(f"  🌙 夜间: {', '.join(daily.get('night', []))}")
                else:
                    print(f"❌ 第{daily['day']}天生成失败: {daily.get('error', 'N/A')}")
                    
        else:
            print(f"❌ 生成失败: {result.get('error', 'N/A')}")
        
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
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
        await test_simple_generation()
    else:
        # MCP服务器模式
        server = SimpleRolePlayDataServer()
        logger.info("🚀 启动简化角色扮演数据生成MCP服务器...")
        await server.start()


if __name__ == "__main__":
    asyncio.run(main()) 