#!/usr/bin/env python3
"""
批量日程生成器 - 本地main启动脚本
支持按批次生成日程，每批次随机配置，保存为CSV格式
"""

import asyncio
import random
import json
import csv
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging
import io



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
        logging.FileHandler('batch_schedule_generator.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class BatchScheduleGenerator:
    """批量日程生成器"""
    
    def __init__(self, start_date: str = "2025-07-02", batch_count: int = 3):
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
        
        # CSV文件路径
        self.csv_file = self.output_dir / f"batch_schedules_{start_date.replace('-', '')}.csv"
        
        # 初始化LLM和工作流
        self._init_workflow()
        
        logger.info(f"批量日程生成器初始化完成")
        logger.info(f"开始日期: {start_date}")
        logger.info(f"批次数量: {batch_count}")
        logger.info(f"输出文件: {self.csv_file}")
    
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
        """生成随机配置"""
        # 随机天数 (7-30天)
        total_days = random.randint(7, 30)
        end_date = self.current_date + timedelta(days=total_days - 1)
        
        # 获取可用角色列表（排除主角方知衡）
        available_characters = list(self.workflow.characters_data.get("角色列表", {}).keys())
        if '方知衡' in available_characters:
            available_characters.remove('方知衡')
        
        # 随机选择角色 (3-9个)
        char_count = min(random.randint(3, 9), len(available_characters))
        selected_characters = random.sample(available_characters, char_count)
        
        # 获取可用地点列表
        available_locations = []
        for district_name, district_info in self.workflow.locations_data.get("districts", {}).items():
            for loc_name, loc_info in district_info.get("locations", {}).items():
                available_locations.append(loc_info.get('name', loc_name))
        
        # 随机选择地点 (3-9个)
        loc_count = min(random.randint(3, 9), len(available_locations))
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
            # 添加上一批次总结信息用于连续性
            'previous_batch_summary': self._get_previous_summary() if batch_num > 1 else ""
        }
        
        return config
    
    def _get_previous_summary(self) -> str:
        """获取上一批次的总结信息，用于保持连续性"""
        if not self.batch_history:
            return ""
        
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
    
    async def _generate_single_batch(self, batch_num: int) -> Optional[Dict[str, Any]]:
        """生成单个批次的日程"""
        try:
            logger.info(f"开始生成第 {batch_num} 批次日程...")
            
            # 生成随机配置
            config = self._get_random_config(batch_num)
            
            logger.info(f"批次 {batch_num} 配置:")
            logger.info(f"  日期范围: {config['start_date']} - {config['end_date']} ({config['total_days']}天)")
            logger.info(f"  角色数量: {len(config['selected_characters'])}")
            logger.info(f"  地点数量: {len(config['selected_locations'])}")
            logger.info(f"  选择角色: {', '.join(config['selected_characters'])}")
            logger.info(f"  选择地点: {', '.join(config['selected_locations'])}")
            
            # 创建简化的工作流聊天接口（不需要UI）
            class SimpleWorkflowChat:
                def __init__(self):
                    self.current_node = ""
                
                async def add_node_message(self, node_name: str, message: str, status: str):
                    logger.info(f"[{node_name}] {message}")
                
                def _create_workflow_progress(self):
                    return ""
            
            workflow_chat = SimpleWorkflowChat()
            
            # 执行工作流
            schedule_result = None
            async for progress in self.workflow.execute_workflow_stream(config, workflow_chat):
                # 获取最终结果
                schedule_result = progress
            
            if schedule_result and schedule_result.get('save_success'):
                logger.info(f"批次 {batch_num} 生成并保存成功!")
                
                # 提取生成的数据用于CSV保存
                schedule_data = schedule_result.get('schedule_result', {})
                daily_schedules = schedule_data.get('daily_schedules', [])
                
                # 构建批次信息
                batch_info = {
                    'batch_number': batch_num,
                    'schedule_id': schedule_result.get('schedule_id', ''),
                    'start_date': config['start_date'],
                    'end_date': config['end_date'],
                    'total_days': config['total_days'],
                    'characters': config['selected_characters'],
                    'locations': config['selected_locations'],
                    'daily_schedules': daily_schedules,
                    'schedule_summary': schedule_data.get('schedule_summary', {}),
                    'weekly_plan': schedule_data.get('weekly_plan', ''),
                    'key_events': self._extract_key_events(daily_schedules),
                    'emotional_progress': self._extract_emotional_progress(daily_schedules),
                    'pending_issues': self._extract_pending_issues(daily_schedules)
                }
                
                # 保存到历史记录
                self.batch_history.append(batch_info)
                
                return batch_info
            else:
                logger.error(f"批次 {batch_num} 生成失败")
                return None
                
        except Exception as e:
            logger.error(f"批次 {batch_num} 生成异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
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
    
    def _save_batch_to_csv(self, batch_info: Dict[str, Any]):
        """将批次数据按日期行保存到CSV文件"""
        try:
            # 检查文件是否存在，确定是否需要写入表头
            file_exists = self.csv_file.exists()
            
            # 验证日期是否包含节假日
            holidays_in_batch = self._check_holidays_in_batch(batch_info)
            
            with open(self.csv_file, 'a', newline='', encoding='utf-8-sig') as csvfile:
                fieldnames = [
                    '批次编号', '日期', '天气', '地点', '季节', '节假日',
                    '周期计划', '每日计划', '夜间', '上午', '中午', '下午', '晚上', '涉及角色'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # 如果是新文件，写入表头
                if not file_exists:
                    writer.writeheader()
                
                # 逐日写入数据
                daily_schedules = batch_info.get('daily_schedules', [])
                weekly_plan = batch_info.get('weekly_plan', '')
                
                for day_data in daily_schedules:
                    # 提取当日的5个时间段故事
                    time_slots = {slot['slot_name']: slot.get('story_content', '') 
                                for slot in day_data.get('time_slots', [])}
                    
                    # 提取当日涉及的角色
                    daily_characters = set()
                    for slot in day_data.get('time_slots', []):
                        involved_chars = slot.get('involved_characters', [])
                        if isinstance(involved_chars, list):
                            daily_characters.update(involved_chars)
                    
                    # 确定季节
                    season = self._get_season_from_date(day_data.get('date', ''))
                    
                    # 写入该日数据
                    writer.writerow({
                        '批次编号': batch_info['batch_number'],
                        '日期': day_data.get('date', ''),
                        '天气': day_data.get('weather', ''),
                        '地点': self._extract_daily_locations(day_data),
                        '季节': season,
                        '节假日': day_data.get('holiday_name', '') if day_data.get('is_holiday', False) else '',
                        '周期计划': weekly_plan,
                        '每日计划': day_data.get('daily_plan', ''),
                        '夜间': time_slots.get('夜间', ''),
                        '上午': time_slots.get('上午', ''),
                        '中午': time_slots.get('中午', ''),
                        '下午': time_slots.get('下午', ''),
                        '晚上': time_slots.get('晚上', ''),
                        '涉及角色': ', '.join(sorted(daily_characters))
                    })
            
            logger.info(f"批次 {batch_info['batch_number']} 数据已按日期行保存到 CSV 文件")
            
        except Exception as e:
            logger.error(f"保存批次数据到CSV失败: {e}")
    
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
    
    def _extract_daily_locations(self, day_data: Dict) -> str:
        """提取当日的主要地点"""
        locations = set()
        for slot in day_data.get('time_slots', []):
            location = slot.get('location', '')
            if location:
                locations.add(location)
        return ', '.join(sorted(locations))
    
    def _extract_daily_plans(self, daily_schedules: List[Dict]) -> str:
        """提取每日计划摘要"""
        plans = []
        for day in daily_schedules[:3]:  # 只取前3天作为摘要
            date = day.get('date', '')
            plan = day.get('daily_plan', '')
            if plan:
                plans.append(f"{date}: {plan[:80]}...")
        return '; '.join(plans)
    
    def _extract_time_slot_stories(self, daily_schedules: List[Dict]) -> str:
        """提取5个时间段的故事摘要"""
        stories = []
        time_slots = ['夜间', '上午', '中午', '下午', '晚上']
        
        for day in daily_schedules[:2]:  # 取前2天的故事
            date = day.get('date', '')
            for slot in day.get('time_slots', []):
                slot_name = slot.get('slot_name', '')
                story = slot.get('story_content', '')
                if story and slot_name in time_slots:
                    stories.append(f"{date}-{slot_name}: {story[:60]}...")
        
        return '; '.join(stories[:5])  # 限制长度
    
    def _extract_character_interactions(self, daily_schedules: List[Dict]) -> str:
        """提取角色互动详情，只包含角色名称"""
        characters = set()
        
        for day in daily_schedules:
            for slot in day.get('time_slots', []):
                involved_chars = slot.get('involved_characters', [])
                if isinstance(involved_chars, list):
                    characters.update(involved_chars)
        
        return ', '.join(sorted(characters))
    
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
        """生成所有批次的日程"""
        logger.info(f"开始批量生成 {self.batch_count} 个批次的日程...")
        
        success_count = 0
        failed_count = 0
        
        for batch_num in range(1, self.batch_count + 1):
            try:
                logger.info(f"\n{'='*50}")
                logger.info(f"正在处理第 {batch_num}/{self.batch_count} 批次")
                logger.info(f"{'='*50}")
                
                # 生成单个批次
                batch_info = await self._generate_single_batch(batch_num)
                
                if batch_info:
                    # 立即保存到CSV（增量保存）
                    self._save_batch_to_csv(batch_info)
                    logger.info(f"✅ 批次 {batch_num} 已增量保存到CSV")
                    
                    # 保存详细JSON（可选）
                    self._save_detailed_json(batch_info)
                    
                    # 更新当前日期为下一批次的开始日期（确保日期连续）
                    next_start_date = datetime.strptime(batch_info['end_date'], '%Y-%m-%d') + timedelta(days=1)
                    self.current_date = next_start_date
                    
                    success_count += 1
                    logger.info(f"批次 {batch_num} 完成，下次开始日期: {self.current_date.strftime('%Y-%m-%d')}")
                    
                    # 验证日期连续性
                    logger.info(f"📅 日期连续性检查: 当前批次结束 {batch_info['end_date']}, 下批次开始 {self.current_date.strftime('%Y-%m-%d')}")
                else:
                    failed_count += 1
                    logger.error(f"批次 {batch_num} 失败，跳过")
                    # 即使失败也要推进日期，避免重复
                    self.current_date += timedelta(days=7)  # 跳过7天
                
                # 批次间短暂休息，避免API限制
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"批次 {batch_num} 处理异常: {e}")
                failed_count += 1
                continue
        
        # 生成总结报告
        self._generate_summary_report(success_count, failed_count)
        
        logger.info(f"\n批量生成完成!")
        logger.info(f"成功: {success_count} 批次")
        logger.info(f"失败: {failed_count} 批次")
        logger.info(f"CSV文件: {self.csv_file}")
    
    def _generate_summary_report(self, success_count: int, failed_count: int):
        """生成总结报告"""
        try:
            report_file = self.output_dir / f"batch_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(f"批量日程生成总结报告\n")
                f.write(f"{'='*50}\n\n")
                f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"开始日期: {self.start_date.strftime('%Y-%m-%d')}\n")
                f.write(f"计划批次: {self.batch_count}\n")
                f.write(f"成功批次: {success_count}\n")
                f.write(f"失败批次: {failed_count}\n")
                f.write(f"成功率: {success_count/self.batch_count*100:.1f}%\n\n")
                
                f.write("批次详情:\n")
                f.write("-" * 30 + "\n")
                for batch in self.batch_history:
                    f.write(f"批次 {batch['batch_number']}: {batch['start_date']} - {batch['end_date']} "
                           f"({batch['total_days']}天, {len(batch['characters'])}角色, {len(batch['locations'])}地点)\n")
                
                if self.batch_history:
                    total_days = sum(batch['total_days'] for batch in self.batch_history)
                    f.write(f"\n总计生成天数: {total_days} 天\n")
                    f.write(f"平均每批次天数: {total_days/len(self.batch_history):.1f} 天\n")
            
            logger.info(f"总结报告已保存到: {report_file}")
            
        except Exception as e:
            logger.error(f"生成总结报告失败: {e}")


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='批量日程生成器')
    parser.add_argument('--start-date', default='2025-07-02', help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--batch-count', type=int, default=3, help='批次数量')
    
    args = parser.parse_args()
    
    print(f"🚀 批量日程生成器启动")
    print(f"📅 开始日期: {args.start_date}")
    print(f"🔢 批次数量: {args.batch_count}")
    print(f"📁 输出目录: workspace/batch_schedule_output/")
    
    try:
        generator = BatchScheduleGenerator(
            start_date=args.start_date,
            batch_count=args.batch_count
        )
        
        await generator.generate_all_batches()
        
        print(f"✅ 批量生成完成!")
        print(f"📊 查看结果: {generator.csv_file}")
        
    except KeyboardInterrupt:
        print(f"\n⏹️  用户中断，程序退出")
    except Exception as e:
        print(f"❌ 程序执行失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 设置Windows异步事件循环策略
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main()) 