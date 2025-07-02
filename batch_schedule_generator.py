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
        """生成随机配置"""
        # 随机天数 (7-14天)
        total_days = random.randint(5, 14)
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
            
            # 创建简化的工作流聊天接口（不需要UI），避免使用emoji符号
            class SimpleWorkflowChat:
                def __init__(self):
                    self.current_node = ""
                
                async def add_node_message(self, node_name: str, message: str, status: str):
                    # 移除emoji符号，使用纯文本
                    clean_message = message.replace('✅', '[成功]').replace('❌', '[失败]').replace('📅', '[日程]').replace('💾', '[保存]')
                    logger.info(f"[{node_name}] {clean_message}")
                
                def _create_workflow_progress(self):
                    return ""
            
            workflow_chat = SimpleWorkflowChat()
            
            # 执行工作流 - 修复结果收集逻辑
            logger.info(f"开始执行工作流...")
            
            final_state = None
            final_output = None
            progress_count = 0
            
            async for stream_event in self.workflow.execute_workflow_stream(config, workflow_chat):
                progress_count += 1
                logger.info(f"收到工作流事件 {progress_count}: {type(stream_event)}")
                
                # 检查是否是最终输出事件
                if isinstance(stream_event, tuple) and len(stream_event) >= 4:
                    # 元组格式: (html, content, message, is_complete)
                    html, content, message, is_complete = stream_event
                    logger.info(f"收到UI事件: message='{message}', is_complete={is_complete}")
                    
                    # 如果包含成功完成的信息，说明有实际的执行结果
                    if "执行完成" in message or "生成完成" in message:
                        logger.info("检测到任务完成信号")
                
            logger.info(f"工作流UI流执行完成，共收到 {progress_count} 次事件")
            
            # 使用流式获取最终状态数据
            logger.info("通过流式调用获取最终数据...")
            
            try:
                # 准备相同的输入数据
                initial_input = {
                    'characters_data': self.workflow.characters_data,
                    'locations_data': self.workflow.locations_data,
                    'stories_data': self.workflow.stories_data,
                    'protagonist_data': self.workflow.protagonist_data,
                    'holidays_data': self.workflow.holidays_data,
                    'config': config,
                    'protagonist': config.get('protagonist', '方知衡'),
                    'schedule_type': config.get('schedule_type', 'weekly'),
                    'start_date': config.get('start_date', ''),
                    'end_date': config.get('end_date', ''),
                    'total_days': config.get('total_days', 7),
                    'selected_characters': config.get('selected_characters', []),
                    'selected_locations': config.get('selected_locations', []),
                    'selected_stories': config.get('selected_stories', []),
                    'time_slots_config': config.get('time_slots_config', self.workflow.current_config['time_slots_config']),
                    'character_distribution': config.get('character_distribution', 'balanced'),
                    'story_integration': config.get('story_integration', 'moderate'),
                    'include_holidays': config.get('include_holidays', True),
                    'include_lunar': config.get('include_lunar', True),
                    'workflow_chat': workflow_chat,
                    'llm': self.workflow.llm
                }
                
                # 使用流式执行图获取最终状态
                if not self.workflow.graph:
                    await self.workflow.create_schedule_graph()
                
                compiled_graph = self.workflow.graph.compile()
                
                # 简单执行流式图，不需要收集状态
                async for stream_chunk in compiled_graph.stream(initial_input):
                    # 只是让工作流执行完成，不收集状态
                    pass
                
                logger.info("工作流执行完成，准备从数据库获取数据")
                
                # 等待1秒确保数据库写入完成
                import time
                time.sleep(1)
                
                # 从数据库获取最新的日程记录
                try:
                    from database.managers.schedule_manager import ScheduleManager
                    schedule_manager = ScheduleManager()
                    
                    # 获取最新的日程记录（按创建时间排序）
                    recent_schedules = schedule_manager.get_schedules_by_filter({}, limit=1)
                    
                    if recent_schedules:
                        latest_schedule = recent_schedules[0]
                        actual_schedule_id = latest_schedule['schedule_id']
                        logger.info(f"从数据库获取到最新日程ID: {actual_schedule_id}")
                        
                        # 创建最终状态
                        final_state = {
                            'schedule_id': actual_schedule_id,
                            'config': config,
                            'database_success': True
                        }
                    else:
                        logger.error("数据库中没有找到新创建的日程记录")
                        final_state = {'database_success': False}
                        
                except Exception as db_error:
                    logger.error(f"从数据库获取最新记录失败: {db_error}")
                    final_state = {'database_success': False}
                
                if final_state.get('database_success', False):
                    schedule_id = final_state.get('schedule_id')
                    logger.info(f"批次 {batch_num} 工作流执行成功，数据库记录ID: {schedule_id}")
                    
                    # 直接从数据库获取完整数据构建批次信息
                    batch_info = self._get_batch_info_from_database(schedule_id)
                    
                    if batch_info:
                        # 更新批次编号
                        batch_info['batch_number'] = batch_num
                        # 保存到历史记录
                        self.batch_history.append(batch_info)
                        logger.info(f"批次 {batch_num} 完成，从数据库获取了完整数据")
                        return batch_info
                    else:
                        logger.error(f"批次 {batch_num} 从数据库获取数据失败")
                        return None
                else:
                    logger.error(f"批次 {batch_num} 数据库操作失败")
                    return None
                
            except Exception as graph_error:
                logger.error(f"流式图执行失败: {graph_error}")
                import traceback
                logger.error(traceback.format_exc())
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
                    # 更新当前日期为下一批次的开始日期（确保日期连续）
                    next_start_date = datetime.strptime(batch_info['end_date'], '%Y-%m-%d') + timedelta(days=1)
                    self.current_date = next_start_date
                    
                    success_count += 1
                    logger.info(f"批次 {batch_num} 完成，下次开始日期: {self.current_date.strftime('%Y-%m-%d')}")
                    
                    # 数据已经从数据库获取，无需重复操作
                    
                    # 验证日期连续性
                    logger.info(f"日期连续性检查: 当前批次结束 {batch_info['end_date']}, 下批次开始 {self.current_date.strftime('%Y-%m-%d')}")
                else:
                    failed_count += 1
                    logger.error(f"批次 {batch_num} 失败，跳过")
                    # 即使失败也要推进日期，避免重复 - 使用随机天数确保时间连续
                    skip_days = random.randint(7, 14)  # 与成功时的随机天数保持一致
                    self.current_date += timedelta(days=skip_days)
                    logger.info(f"批次 {batch_num} 失败，推进日期 {skip_days} 天到: {self.current_date.strftime('%Y-%m-%d')}")
                
                # 批次间短暂休息，避免API限制
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"批次 {batch_num} 处理异常: {e}")
                failed_count += 1
                # 异常时也要推进日期，避免重复
                skip_days = random.randint(7, 14)
                self.current_date += timedelta(days=skip_days)
                logger.info(f"批次 {batch_num} 异常，推进日期 {skip_days} 天到: {self.current_date.strftime('%Y-%m-%d')}")
                continue
        
        # 生成总结报告
        self._generate_summary_report(success_count, failed_count)
        
        logger.info(f"\n批量生成完成!")
        logger.info(f"成功: {success_count} 批次")
        logger.info(f"失败: {failed_count} 批次")
        logger.info(f"输出目录: {self.output_dir}")
        
        # 确保程序能够正常结束
        print(f"\n所有批次处理完成，程序即将退出...")
        return success_count, failed_count
    
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
    parser.add_argument('--start-date', default='2025-07-03', help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--batch-count', type=int, default=3, help='批次数量')
    
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