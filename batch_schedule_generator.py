#!/usr/bin/env python3
"""
批量日程生成器 - 本地main启动脚本
支持按批次生成日程，每批次随机配置，保存为CSV格式
"""

import asyncio
import random
import json
import os
import sys
import csv
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging



# 添加项目路径
current_dir = Path(__file__).parent
src_path = current_dir / "src"
sys.path.insert(0, str(src_path))

# 添加项目根路径以支持绝对导入
sys.path.insert(0, str(current_dir))

from src.workflow.schedule_workflow import ScheduleWorkflow
from src.llm.base import LLMFactory
from src.core.types import LLMConfig
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('batch_schedule_generator.log', encoding='utf-8'),  # 明确指定UTF-8编码
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class BatchScheduleGenerator:
    """批量日程生成器"""
    
    def __init__(self, start_date: str = "2025-07-18", batch_count: int = 100):
        """
        初始化批量生成器
        
        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            batch_count: 批次数量
        """
        self.start_date = datetime.strptime(start_date, '%Y-%m-%d')
        self.batch_count = batch_count
        self.current_date = self.start_date
        self.workflow = None
        self.llm = None
        self.batch_history = []  # 存储每批次的总结，用于连续性
        
        # 输出目录
        self.output_dir = Path("workspace/batch_schedule_output")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化LLM和工作流
        self._init_workflow()
        
        logger.info(f"批量日程生成器初始化完成")
        logger.info(f"开始日期: {start_date}")
        logger.info(f"批次数量: {batch_count}")
        logger.info(f"输出目录: {self.output_dir}")
    
    def _init_workflow(self):
        """初始化工作流和LLM"""
        try:
            # 创建LLM实例
            llm_config = LLMConfig(
                provider="doubao",
                api_key=os.getenv('DOUBAO_API_KEY', 'b633a622-b5d0-4f16-a8a9-616239cf15d1'),
                model_name=os.getenv('DOUBAO_MODEL_DEEPSEEKR1', 'ep-20250221154107-c4qc7'),
                temperature=0.7,
                max_tokens=16384
            )
            
            llm_factory = LLMFactory()
            self.llm = llm_factory.create(llm_config)
            
            # 创建工作流实例
            self.workflow = ScheduleWorkflow(llm=self.llm)
            
            logger.info("LLM和工作流初始化成功")
            
        except Exception as e:
            logger.error(f"LLM和工作流初始化失败: {e}")
            raise
    
    def _get_random_config(self, batch_num: int) -> Dict[str, Any]:
        """生成随机配置 - 每次生成较短周期，保持灵活性"""
        # 随机天数 (每次生成30-50天的周期，保持灵活性)
        total_days = random.randint(30, 50)  # 每个批次30-50天，避免过长周期
        end_date = self.current_date + timedelta(days=total_days - 1)
        
        # 获取可用角色列表（排除主角方知衡）
        available_characters = list(self.workflow.characters_data.get("角色列表", {}).keys())
        if '方知衡' in available_characters:
            available_characters.remove('方知衡')
        
        # 随机选择角色 (2-6)
        char_count = min(random.randint(2, 6), len(available_characters))
        selected_characters = random.sample(available_characters, char_count)
        
        # 获取可用地点列表
        available_locations = []
        for district_name, district_info in self.workflow.locations_data.get("districts", {}).items():
            for loc_name, loc_info in district_info.get("locations", {}).items():
                available_locations.append(loc_info.get('name', loc_name))
        
        # 随机选择地点 (3-9个)
        loc_count = min(random.randint(2, 6), len(available_locations))
        selected_locations = random.sample(available_locations, loc_count)
        
        # 生成配置
        config = {
            'protagonist': '方知衡',
            'schedule_type': 'weekly',
            'start_date': self.current_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'total_days': total_days,
            'selected_characters': selected_characters,
            'selected_locations': selected_locations,
            'selected_stories': [],  # 暂时不使用剧情
            'time_slots_config': {
                '夜间': {'start': '23:00', 'end': '06:00'},
                '上午': {'start': '06:00', 'end': '11:00'},
                '中午': {'start': '11:00', 'end': '14:00'},
                '下午': {'start': '14:00', 'end': '18:00'},
                '晚上': {'start': '18:00', 'end': '23:00'}
            },
            'character_distribution': 'balanced',
            'story_integration': 'moderate',
            'include_holidays': True,
            'include_lunar': True,
            'mood_variety': True,
            'location_variety': True,
            # 启用周期总结功能
            'enable_cycle_summary': True,
            # 添加上一批次总结信息用于连续性
            'previous_batch_summary': self._get_previous_summary() if batch_num > 1 else ""
        }
        
        return config
    
    def _get_previous_summary(self) -> str:
        """获取上一批次的总结信息，用于保持连续性"""
        if not self.batch_history:
            # 尝试从CSV文件读取最近的总结
            return self._get_latest_cycle_summary_from_csv()
        
        last_batch = self.batch_history[-1]
        summary = f"""
## 上一批次总结（{last_batch['start_date']} - {last_batch['end_date']}）

**时间范围**: {last_batch['start_date']} 至 {last_batch['end_date']}（{last_batch['total_days']}天）
**主要角色**: {', '.join(last_batch['characters'])}
**主要地点**: {', '.join(last_batch['locations'])}
**重要事件**: {last_batch.get('key_events', '工作、研究、社交等日常活动')}
**情感发展**: {last_batch.get('emotional_progress', '与各角色保持良好关系')}
**遗留问题**: {last_batch.get('pending_issues', '无特别遗留问题')}

请确保新的日程与上述情况自然衔接，避免突兀的变化。
"""
        return summary

    def _get_latest_cycle_summary_from_csv(self) -> str:
        """从CSV文件中获取最新的周期总结"""
        try:
            import pandas as pd
            
            # 查找最新的CSV文件
            csv_files = [f for f in os.listdir(self.output_dir) if f.startswith('batch_schedules_') and f.endswith('.csv')]
            if not csv_files:
                logger.info("未找到历史批次总结，这是第一个批次或历史文件为空")
                return ""
            
            # 读取最新的CSV文件
            latest_csv = sorted(csv_files)[-1]
            csv_path = os.path.join(self.output_dir, latest_csv)
            
            df = pd.read_csv(csv_path)
            if df.empty:
                logger.info("CSV文件为空，未找到历史批次总结")
                return ""
            
            # 获取最新批次的周期总结（非空的）
            latest_summaries = df[df['cycle_summary'].notna() & (df['cycle_summary'] != '')]['cycle_summary']
            if latest_summaries.empty:
                logger.info("未找到历史批次总结，这是第一个批次或历史文件为空")
                return ""
            
            latest_summary = latest_summaries.iloc[-1]
            logger.info(f"从CSV文件中找到历史总结，长度: {len(latest_summary)} 字符")
            return latest_summary
            
        except Exception as e:
            logger.warning(f"读取CSV历史总结失败: {e}")
            logger.info("未找到历史批次总结，这是第一个批次或历史文件为空")
            return ""
    
    async def _generate_single_batch(self, batch_num: int, retry_count: int = 0) -> Optional[Dict[str, Any]]:
        """生成单个批次的日程 - 支持异常重试机制"""
        max_retries = 3
        
        # 生成配置（保持一致）
        config = self._get_random_config(batch_num)
        
        for attempt in range(max_retries):
            try:
                current_attempt = retry_count + attempt + 1
                logger.info(f"开始生成第 {batch_num} 批次日程（第 {current_attempt} 次尝试）...")
                
                if attempt > 0:
                    logger.info(f"批次 {batch_num} 重试第 {attempt} 次，使用相同配置")
                
                logger.info(f"批次 {batch_num} 配置:")
                logger.info(f"  日期范围: {config['start_date']} - {config['end_date']} ({config['total_days']}天)")
                logger.info(f"  预计周期数: {(config['total_days'] + 10) // 11} 个周期（每周期7-15天）")
                logger.info(f"  角色数量: {len(config['selected_characters'])}")
                logger.info(f"  地点数量: {len(config['selected_locations'])}")
                logger.info(f"  选择角色: {', '.join(config['selected_characters'])}")
                logger.info(f"  选择地点: {', '.join(config['selected_locations'])}")
                
                # 创建简化的工作流聊天接口
                class SimpleWorkflowChat:
                    def __init__(self):
                        self.current_node = ""
                    
                    async def add_node_message(self, node_name: str, message: str, status: str):
                        # 只打印重要的状态信息
                        if status in ['success', 'error', 'warning']:
                            clean_message = message.replace('✅', '[成功]').replace('❌', '[失败]').replace('⚠️', '[警告]')
                            logger.info(f"[{node_name}] {clean_message}")
                    
                    def _create_workflow_progress(self):
                        return ""
                
                workflow_chat = SimpleWorkflowChat()
                
                # 执行多周期工作流
                logger.info(f"开始执行多周期工作流...")
                
                progress_count = 0
                async for stream_event in self.workflow.execute_workflow_stream(config, workflow_chat):
                    progress_count += 1
                    
                    # 检查是否是最终输出事件
                    if isinstance(stream_event, tuple) and len(stream_event) >= 4:
                        html, content, message, is_complete = stream_event
                        if "周期生成完成" in message or "执行完成" in message:
                            logger.info(f"检测到周期完成信号: {message}")
                    
                logger.info(f"多周期工作流执行完成，共收到 {progress_count} 次事件")
                
                # 等待数据库写入完成
                logger.info("等待数据库写入完成...")
                import time
                time.sleep(2)
                
                # 从数据库获取生成的日程记录
                from database.managers.schedule_manager import ScheduleManager
                schedule_manager = ScheduleManager()
                
                # 获取批次日期范围内的所有日程记录
                recent_schedules = schedule_manager.get_schedules_by_filter({}, limit=10)
                
                # 筛选出当前批次日期范围内的日程
                batch_schedules = []
                for schedule in recent_schedules:
                    schedule_start = schedule.get('start_date', '')
                    schedule_end = schedule.get('end_date', '')
                    
                    # 检查是否在当前批次的日期范围内或有重叠
                    if (schedule_start <= config['end_date'] and schedule_end >= config['start_date']):
                        batch_schedules.append(schedule)
                        logger.info(f"找到匹配周期: {schedule_start} - {schedule_end}, daily_schedules数量: {len(schedule.get('daily_schedules', []))}")
                
                if batch_schedules:
                    logger.info(f"批次 {batch_num} 找到 {len(batch_schedules)} 个周期的日程记录")
                    
                    # 合并所有周期的数据
                    batch_info = self._merge_multiple_cycles_data(batch_schedules, batch_num, config)
                    
                    if batch_info:
                        # 保存到历史记录
                        self.batch_history.append(batch_info)
                        logger.info(f"✅ 批次 {batch_num} 完成（第 {current_attempt} 次尝试成功）")
                        return batch_info
                    else:
                        raise Exception("合并周期数据失败")
                else:
                    raise Exception("数据库中没有找到当前批次的日程记录")
                        
            except Exception as e:
                current_attempt = retry_count + attempt + 1
                logger.error(f"❌ 批次 {batch_num} 第 {current_attempt} 次尝试失败: {e}")
                
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 递增等待时间：2s, 4s, 6s
                    logger.info(f"⏳ 等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ 批次 {batch_num} 经过 {max_retries} 次尝试仍然失败，跳过该批次")
                    import traceback
                    logger.error(traceback.format_exc())
                    return None
        
        return None
    
    def _extract_key_events(self, daily_schedules: List[Dict]) -> str:
        """从日程中提取关键事件"""
        key_events = []
        for day in daily_schedules[:3]:  # 只取前3天的事件作为摘要
            for slot in day.get('time_slots', []):
                content = slot.get('story_content', '')
                if len(content) > 100:  # 内容较丰富的事件
                    key_events.append(f"{day.get('date', '')} {slot.get('slot_name', '')}: {content[:50]}...")
        return '; '.join(key_events[:3])  # 最多3个关键事件
    
    def _extract_emotional_progress(self, daily_schedules: List[Dict]) -> str:
        """提取情感发展线"""
        # 简化提取，查找包含情感词汇的内容
        emotional_keywords = ['感动', '开心', '担心', '期待', '满意', '感谢', '友谊', '关系', '交流']
        emotional_events = []
        
        for day in daily_schedules:
            for slot in day.get('time_slots', []):
                content = slot.get('story_content', '')
                for keyword in emotional_keywords:
                    if keyword in content:
                        emotional_events.append(f"与{slot.get('assigned_character', '')}的{keyword}")
                        break
        
        return '; '.join(set(emotional_events[:3]))  # 去重并限制数量
    
    def _extract_pending_issues(self, daily_schedules: List[Dict]) -> str:
        """提取遗留问题"""
        # 简化提取，查找最后一天的计划或未完成事项
        if daily_schedules:
            last_day = daily_schedules[-1]
            daily_plan = last_day.get('daily_plan', '')
            if '计划' in daily_plan or '准备' in daily_plan:
                return daily_plan[:100] + "..." if len(daily_plan) > 100 else daily_plan
        return "无特别遗留问题"
    
    def _merge_multiple_cycles_data(self, batch_schedules: List[Dict], batch_num: int, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """合并多个周期的数据为一个批次信息，并保存CSV"""
        try:
            if not batch_schedules:
                return None
            
            # 合并所有周期的每日安排
            all_daily_schedules = []
            all_cycle_summaries = []
            all_characters = set()
            all_locations = set()
            
            # 找到最早和最晚的日期
            start_dates = []
            end_dates = []
            total_days = 0
            
            for i, schedule in enumerate(batch_schedules):
                # 收集日期信息
                start_dates.append(schedule.get('start_date', ''))
                end_dates.append(schedule.get('end_date', ''))
                total_days += schedule.get('total_days', 0)
                
                # 合并每日安排
                daily_schedules = schedule.get('daily_schedules', [])
                logger.info(f"周期 {i+1}: {schedule.get('start_date', '')} - {schedule.get('end_date', '')}, 包含 {len(daily_schedules)} 天")
                all_daily_schedules.extend(daily_schedules)
                
                # 收集周期总结
                cycle_summary = schedule.get('cycle_summary', '')
                if cycle_summary:
                    all_cycle_summaries.append(cycle_summary)
                
                # 提取角色和地点
                for day in daily_schedules:
                    for slot in day.get('time_slots', []):
                        chars = slot.get('involved_characters', [])
                        for char in chars:
                            if char and char != '方知衡':
                                all_characters.add(char)
                        
                        location = slot.get('location', '')
                        if location:
                            all_locations.add(location)
            
            # 按日期排序
            all_daily_schedules.sort(key=lambda x: x.get('date', ''))
            
            # 直接保存为CSV文件
            self._save_batch_to_csv(all_daily_schedules, batch_schedules, batch_num)
            
            # 构建批次信息
            batch_info = {
                'batch_number': batch_num,
                'schedule_ids': [s.get('schedule_id', '') for s in batch_schedules],
                'start_date': min(start_dates) if start_dates else config['start_date'],
                'end_date': max(end_dates) if end_dates else config['end_date'],
                'total_days': total_days,
                'cycles_count': len(batch_schedules),
                'characters': list(all_characters),
                'locations': list(all_locations),
                'daily_schedules': all_daily_schedules,
                'cycle_summaries': all_cycle_summaries,
                'key_events': self._extract_key_events(all_daily_schedules),
                'emotional_progress': self._extract_emotional_progress(all_daily_schedules),
                'pending_issues': self._extract_pending_issues(all_daily_schedules)
            }
            
            logger.info(f"成功合并批次信息:")
            logger.info(f"  包含 {len(batch_schedules)} 个周期，{len(all_daily_schedules)} 天安排")
            logger.info(f"  涉及 {len(all_characters)} 个角色: {', '.join(list(all_characters)[:3])}...")
            logger.info(f"  涉及 {len(all_locations)} 个地点: {', '.join(list(all_locations)[:3])}...")
            
            return batch_info
            
        except Exception as e:
            logger.error(f"合并多周期数据失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _get_batch_info_from_database(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        """从数据库获取完整的批次信息"""
        try:
            from database.managers.schedule_manager import ScheduleManager
            
            # 创建数据库管理器
            schedule_manager = ScheduleManager()
            
            # 获取完整的日程数据
            full_schedule = schedule_manager.get_schedule_by_id(schedule_id)
            
            if not full_schedule:
                logger.warning(f"数据库中未找到日程: {schedule_id}")
                return None
            
            # 提取每日安排
            daily_schedules = full_schedule.get('daily_schedules', [])
            
            # 构建批次信息
            batch_info = {
                'batch_number': len(self.batch_history) + 1,  # 基于当前历史数量
                'schedule_id': schedule_id,
                'start_date': full_schedule.get('start_date', ''),
                'end_date': full_schedule.get('end_date', ''),
                'total_days': full_schedule.get('total_days', 0),
                'characters': [],  # 从时间段中提取
                'locations': [],   # 从时间段中提取
                'daily_schedules': daily_schedules,
                'schedule_summary': {},  # 可以从描述中解析
                'weekly_plan': full_schedule.get('weekly_plan', ''),
                'key_events': self._extract_key_events(daily_schedules),
                'emotional_progress': self._extract_emotional_progress(daily_schedules),
                'pending_issues': self._extract_pending_issues(daily_schedules)
            }
            
            # 从时间段中提取参与的角色和地点
            characters = set()
            locations = set()
            
            for day in daily_schedules:
                for slot in day.get('time_slots', []):
                    assigned_char = slot.get('assigned_character', '')
                    if assigned_char and assigned_char != '方知衡':
                        characters.add(assigned_char)
                    
                    location = slot.get('location', '')
                    if location:
                        locations.add(location)
            
            batch_info['characters'] = list(characters)
            batch_info['locations'] = list(locations)
            
            logger.info(f"从数据库成功获取批次信息: {schedule_id}")
            logger.info(f"  包含 {len(daily_schedules)} 天安排")
            logger.info(f"  涉及 {len(characters)} 个角色: {', '.join(list(characters)[:3])}...")
            logger.info(f"  涉及 {len(locations)} 个地点: {', '.join(list(locations)[:3])}...")
            
            return batch_info
            
        except Exception as e:
            logger.error(f"从数据库获取批次信息失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    

    
    def _check_holidays_in_batch(self, batch_info: Dict[str, Any]) -> Dict[str, str]:
        """验证批次中的节假日"""
        holidays = {}
        try:
            start_date = batch_info['start_date']
            end_date = batch_info['end_date']
            
            # 使用工作流的节假日数据
            holidays_data = self.workflow.get_holidays_in_range(start_date, end_date)
            
            if holidays_data:
                logger.info(f"批次 {batch_info['batch_number']} 包含节假日: {list(holidays_data.keys())}")
                for date, holiday_info in holidays_data.items():
                    holidays[date] = holiday_info.get('name', '')
            else:
                logger.info(f"批次 {batch_info['batch_number']} 无节假日")
                
        except Exception as e:
            logger.warning(f"检查节假日失败: {e}")
            
        return holidays
    
    def _get_season_from_date(self, date_str: str) -> str:
        """根据日期确定季节"""
        try:
            from datetime import datetime
            date = datetime.strptime(date_str, '%Y-%m-%d')
            month = date.month
            
            if month in [12, 1, 2]:
                return '冬季'
            elif month in [3, 4, 5]:
                return '春季'
            elif month in [6, 7, 8]:
                return '夏季'
            elif month in [9, 10, 11]:
                return '秋季'
            else:
                return '未知'
        except:
            return '未知'
    
    def _save_batch_to_csv(self, daily_schedules: List[Dict], batch_schedules: List[Dict], batch_num: int):
        """保存批次数据到CSV文件"""
        try:
            # 创建输出目录
            self.output_dir.mkdir(parents=True, exist_ok=True)
            
            # 使用固定CSV文件名，便于增量更新
            csv_file_path = self.output_dir / "batch_schedules.csv"
            
            # 定义CSV列头
            csv_headers = [
                "日期", "星期", "节日信息", "季节", "天气", "主题", 
                "周期计划", "3天总结", "每日计划", "每日总结", "涉及角色", "角色简介",
                "上午", "中午", "下午", "晚上", "夜间"
            ]
            
            # 检查文件是否存在，决定是追加还是创建新文件
            file_exists = csv_file_path.exists() and csv_file_path.stat().st_size > 0
            write_mode = 'a' if file_exists else 'w'
            
            # 获取周期计划和周期总结
            cycle_theme = ""
            cycle_summary = ""
            if batch_schedules:
                first_schedule = batch_schedules[0]
                if isinstance(first_schedule, dict) and 'cycle_summary' in first_schedule:
                    cycle_summary = first_schedule.get('cycle_summary', '')
                    # 从周期数据中提取主题
                    cycle_info = first_schedule.get('cycle_info', {})
                    cycle_theme = cycle_info.get('cycle_theme', '')
            
            # 写入CSV文件
            with open(csv_file_path, write_mode, encoding='utf-8', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # 只在文件不存在时写入表头
                if not file_exists:
                    writer.writerow(csv_headers)
                
                # 获取LLM生成的批次总结(batch_summary)
                llm_batch_summary = ""
                logger.info(f"正在查找LLM生成的batch_summary...")
                
                # 从batch_schedules中查找LLM生成的batch_summary
                for schedule in batch_schedules:
                    # 直接从schedule中查找batch_summary
                    if 'batch_summary' in schedule and schedule['batch_summary']:
                        llm_batch_summary = schedule['batch_summary']
                        logger.info(f"✅ 从周期数据中找到LLM生成的batch_summary: {llm_batch_summary[:150]}...")
                        break
                    
                    # 从daily_schedules中查找batch_summary
                    daily_schedules_in_cycle = schedule.get('daily_schedules', [])
                    for day in daily_schedules_in_cycle:
                        if 'batch_summary' in day and day['batch_summary']:
                            llm_batch_summary = day['batch_summary']
                            logger.info(f"✅ 从每日数据中找到LLM生成的batch_summary: {llm_batch_summary[:150]}...")
                            break
                    if llm_batch_summary:
                        break
                
                if not llm_batch_summary:
                    logger.warning("⚠️ 未找到LLM生成的batch_summary，将使用空值")
                
                # 遍历每天的日程数据
                for day_index, day_data in enumerate(daily_schedules):
                    date = day_data.get('date', '')
                    weekday = day_data.get('weekday_name', '')
                    weather = day_data.get('weather', '')
                    is_holiday = day_data.get('is_holiday', False)
                    holiday_name = day_data.get('holiday_name', '')
                    
                    # 节日信息处理
                    holiday_info = holiday_name if is_holiday and holiday_name else "无"
                    
                    # 根据日期确定季节
                    season = self._get_season_from_date(date)
                    
                    daily_plan = day_data.get('daily_plan', '')
                    daily_summary = day_data.get('daily_summary', '')  # 每日总结
                    
                    # 提取每日涉及角色信息
                    daily_involved_characters = day_data.get('daily_involved_characters', [])
                    daily_characters_info = day_data.get('daily_characters_info', '')
                    
                    # 如果没有提供字符串格式的角色信息，则自动生成
                    if not daily_characters_info and daily_involved_characters:
                        # 从角色数据中获取简介
                        char_infos = []
                        char_list = self.workflow.characters_data.get("角色列表", {})
                        for char_name in daily_involved_characters:
                            if char_name in char_list:
                                char_desc = char_list[char_name].get('简介', '')
                                char_infos.append(f"{char_name}-{char_desc}")
                        daily_characters_info = '；'.join(char_infos)
                    
                    # 初始化时间段数据
                    time_slots_data = {
                        '上午': '',
                        '中午': '', 
                        '下午': '',
                        '晚上': '',
                        '夜间': ''
                    }
                    
                    # 提取时间段数据
                    time_slots = day_data.get('time_slots', [])
                    for slot in time_slots:
                        slot_name = slot.get('slot_name', '')
                        if slot_name in time_slots_data:
                            time_slots_data[slot_name] = slot.get('story_content', '')
                    
                    # 3天总结：只在每3天的第一天显示LLM生成的batch_summary，其他天为空
                    day_batch_summary = ""
                    if day_index % 3 == 0:  # 每3天的第一天显示LLM生成的总结
                        day_batch_summary = llm_batch_summary
                    
                    # 构建CSV行数据
                    row_data = [
                        date,                          # 日期
                        weekday,                       # 星期
                        holiday_info,                  # 节日信息
                        season,                        # 季节
                        weather,                       # 天气
                        cycle_theme,                   # 主题
                        cycle_summary,                 # 周期计划
                        day_batch_summary,             # 3天总结
                        daily_plan,                    # 每日计划
                        daily_summary,                 # 每日总结
                        ', '.join(daily_involved_characters),  # 涉及角色
                        daily_characters_info,         # 角色简介
                        time_slots_data['上午'],        # 上午
                        time_slots_data['中午'],        # 中午
                        time_slots_data['下午'],        # 下午
                        time_slots_data['晚上'],        # 晚上
                        time_slots_data['夜间']         # 夜间
                    ]
                    
                    writer.writerow(row_data)
            
            logger.info(f"批次 {batch_num} CSV数据已{'追加到' if file_exists else '保存为新'}文件: {csv_file_path}")
            
        except Exception as e:
            logger.error(f"保存批次 {batch_num} CSV文件失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
    

    
    def _save_detailed_json(self, batch_info: Dict[str, Any]):
        """保存详细的JSON数据（可选）"""
        try:
            json_file = self.output_dir / f"batch_{batch_info['batch_number']:03d}_{batch_info['start_date']}.json"
            
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(batch_info, f, ensure_ascii=False, indent=2)
            
            logger.info(f"批次 {batch_info['batch_number']} 详细数据已保存到 {json_file}")
            
        except Exception as e:
            logger.error(f"保存详细JSON数据失败: {e}")
    
    async def generate_all_batches(self):
        """连续生成所有批次的日程，实现时间连续性和异常重试"""
        logger.info(f"开始连续生成 {self.batch_count} 个批次的日程...")
        
        success_count = 0
        failed_count = 0
        total_attempts = 0
        
        for batch_num in range(1, self.batch_count + 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"正在处理第 {batch_num}/{self.batch_count} 批次")
            logger.info(f"当前开始日期: {self.current_date.strftime('%Y-%m-%d')}")
            logger.info(f"{'='*60}")
            
            # 生成单个批次（内含重试机制）
            batch_info = await self._generate_single_batch(batch_num)
            total_attempts += 1  # 统计总尝试次数
            
            if batch_info:
                # 确保日期连续性：下一批次从当前批次结束日期+1天开始
                batch_end_date = batch_info['end_date']
                next_start_date = datetime.strptime(batch_end_date, '%Y-%m-%d') + timedelta(days=1)
                self.current_date = next_start_date
                
                success_count += 1
                logger.info(f"🎉 批次 {batch_num} 最终成功")
                logger.info(f"   📊 覆盖天数: {batch_info['total_days']} 天")
                logger.info(f"   🔄 涉及周期: {batch_info.get('cycles_count', 1)} 个")
                logger.info(f"   📅 下批次开始: {self.current_date.strftime('%Y-%m-%d')}")
                logger.info(f"   ✓ 日期连续性: {batch_end_date} → {self.current_date.strftime('%Y-%m-%d')}")
            else:
                failed_count += 1
                logger.error(f"💥 批次 {batch_num} 最终失败（已重试3次）")
                
                # 失败时推进随机天数，保持时间前进
                try:
                    config = self._get_random_config(batch_num)
                    skip_days = config['total_days']
                except Exception as config_error:
                    logger.warning(f"获取配置失败: {config_error}，使用默认跳过天数")
                    skip_days = random.randint(30, 50)
                
                self.current_date += timedelta(days=skip_days)
                logger.info(f"   ⏭️ 跳过 {skip_days} 天到: {self.current_date.strftime('%Y-%m-%d')}")
            
            # 批次间休息，给系统恢复时间
            logger.info(f"⏸️ 批次间休息 3 秒...")
            await asyncio.sleep(3)
        
        # 生成总结报告
        self._generate_summary_report(success_count, failed_count, total_attempts)
        
        logger.info(f"\n🏁 连续批量生成完成!")
        logger.info(f"✅ 成功批次: {success_count}/{self.batch_count}")
        logger.info(f"❌ 失败批次: {failed_count}/{self.batch_count}")
        logger.info(f"📈 成功率: {success_count/self.batch_count*100:.1f}%")
        logger.info(f"🔄 总尝试次数: {total_attempts}")
        logger.info(f"📁 输出目录: {self.output_dir}")
        logger.info(f"📅 最终日期: {self.current_date.strftime('%Y-%m-%d')}")
        
        return success_count, failed_count
    
    def _generate_summary_report(self, success_count: int, failed_count: int, total_attempts: int = None):
        """生成带重试统计的总结报告"""
        try:
            report_file = self.output_dir / f"batch_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(f"📊 批量日程生成总结报告（异常重试版）\n")
                f.write(f"{'='*60}\n\n")
                f.write(f"🕐 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"📅 开始日期: {self.start_date.strftime('%Y-%m-%d')}\n")
                f.write(f"📅 结束日期: {self.current_date.strftime('%Y-%m-%d')}\n")
                f.write(f"🎯 计划批次: {self.batch_count}\n")
                f.write(f"✅ 成功批次: {success_count}\n")
                f.write(f"❌ 失败批次: {failed_count}\n")
                f.write(f"📈 成功率: {success_count/self.batch_count*100:.1f}%\n")
                if total_attempts:
                    f.write(f"🔄 总尝试次数: {total_attempts}\n")
                    f.write(f"💪 平均每批次尝试: {total_attempts/self.batch_count:.1f} 次\n")
                f.write(f"\n")
                
                f.write("📋 批次详情:\n")
                f.write("-" * 40 + "\n")
                for batch in self.batch_history:
                    cycle_count = batch.get('cycles_count', 1)
                    f.write(f"批次 {batch['batch_number']}: {batch['start_date']} - {batch['end_date']} "
                           f"({batch['total_days']}天, {cycle_count}周期, {len(batch['characters'])}角色, {len(batch['locations'])}地点)\n")
                
                if self.batch_history:
                    total_days = sum(batch['total_days'] for batch in self.batch_history)
                    total_cycles = sum(batch.get('cycles_count', 1) for batch in self.batch_history)
                    f.write(f"\n📊 统计汇总:\n")
                    f.write(f"   📅 总生成天数: {total_days} 天\n")
                    f.write(f"   🔄 总周期数: {total_cycles} 个\n")
                    f.write(f"   📊 平均每批次天数: {total_days/len(self.batch_history):.1f} 天\n")
                    f.write(f"   📊 平均每批次周期: {total_cycles/len(self.batch_history):.1f} 个\n")
                    f.write(f"   📊 平均每周期天数: {total_days/total_cycles:.1f} 天\n")
                
                f.write(f"\n🎉 报告生成完成!\n")
                f.write(f"📁 CSV输出文件: workspace/batch_schedule_output/batch_schedules.csv\n")
            
            logger.info(f"📋 总结报告已保存到: {report_file}")
            
        except Exception as e:
            logger.error(f"生成总结报告失败: {e}")


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='批量日程生成器')
    parser.add_argument('--start-date', default='2025-07-03', help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--batch-count', type=int, default=30, help='批次数量')
    
    args = parser.parse_args()
    
    print(f"批量日程生成器启动")
    print(f"开始日期: {args.start_date}")
    print(f"批次数量: {args.batch_count}")
    print(f"输出目录: workspace/batch_schedule_output/")
    
    try:
        generator = BatchScheduleGenerator(
            start_date=args.start_date,
            batch_count=args.batch_count
        )
        
        success_count, failed_count = await generator.generate_all_batches()
        
        print(f"批量生成完成!")
        print(f"输出目录: {generator.output_dir}")
        print(f"成功率: {success_count}/{generator.batch_count} ({success_count/generator.batch_count*100:.1f}%)")
        
    except KeyboardInterrupt:
        print(f"\n用户中断，程序退出")
    except Exception as e:
        print(f"程序执行失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"\n程序退出")
        sys.exit(0)


if __name__ == "__main__":
    # 设置Windows异步事件循环策略
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main()) 