"""
任务队列处理器
处理队列相关的事件和操作
"""

import logging
from typing import Dict, List, Any, Tuple
from datetime import datetime

from core.task_queue import task_queue

logger = logging.getLogger(__name__)


class QueueHandlers:
    """任务队列处理器"""
    
    def __init__(self):
        pass
    
    def add_task_to_queue(
        self,
        task_name: str,
        selected_characters: List[str],
        selected_locations: List[str],
        story_count: int,
        story_type: str,
        story_length: str,
        relationship_depth: str,
        time_setting: str,
        mood_tone: str,
        interaction_level: str,
        llm_provider: str,
        llm_model: str,
        llm_api_key: str,
        llm_base_url: str = "",
        priority: int = 0
    ) -> str:
        """添加任务到队列"""
        try:
            # 验证必要参数
            if not task_name.strip():
                return "❌ 任务名称不能为空"
            
            if not selected_characters:
                return "❌ 请至少选择一个角色"
            
            if not llm_api_key.strip():
                return "❌ 请配置LLM API Key"
            
            # 构建任务配置
            config = {
                'protagonist': '方知衡',
                'selected_characters': selected_characters,
                'selected_locations': selected_locations,
                'story_count': story_count,
                'story_type': story_type,
                'story_length': story_length,
                'relationship_depth': relationship_depth,
                'time_setting': time_setting,
                'mood_tone': mood_tone,
                'interaction_level': interaction_level,
                'llm_config': {
                    'provider': llm_provider,
                    'model': llm_model,
                    'api_key': llm_api_key,
                    'base_url': llm_base_url
                },
                'created_by': 'user',
                'created_time': datetime.now().isoformat()
            }
            
            # 添加到队列
            task_id = task_queue.add_task(task_name, config, priority)
            
            logger.info(f"任务已添加到队列: {task_name} (ID: {task_id})")
            
            return f"✅ 任务已添加到队列！\n\n**任务ID**: {task_id[:8]}...\n**任务名称**: {task_name}\n**参与角色**: {', '.join(selected_characters)}\n**队列位置**: {len(task_queue.get_task_list())}\n\n请前往「任务队列」页面管理和执行任务。"
            
        except Exception as e:
            logger.error(f"添加任务到队列失败: {e}")
            return f"❌ 添加任务失败: {str(e)}"
    
    def get_queue_status_summary(self) -> str:
        """获取队列状态摘要"""
        try:
            status = task_queue.get_queue_status()
            
            # 状态摘要
            if status['is_running']:
                status_text = "🟢 队列运行中"
            else:
                status_text = "🔴 队列已停止"
            
            summary = f"""### 📊 队列状态摘要

{status_text}

**统计信息**:
- 总任务数: {status['total_tasks']}
- 等待执行: {status['pending_count']}
- 正在执行: {status['running_count']}
- 已完成: {status['completed_count']}
- 执行失败: {status['failed_count']}
"""
            
            # 当前任务信息
            if status['current_task']:
                current_task = status['current_task']
                summary += f"\n**当前执行**: {current_task['task_name']}"
            
            # 下一个任务信息
            if status['next_task']:
                next_task = status['next_task']
                summary += f"\n**下一个任务**: {next_task['task_name']}"
            
            return summary
            
        except Exception as e:
            logger.error(f"获取队列状态失败: {e}")
            return f"❌ 获取队列状态失败: {str(e)}"
    
    def validate_task_config(
        self,
        selected_characters: List[str],
        llm_api_key: str
    ) -> Tuple[bool, str]:
        """验证任务配置是否有效"""
        try:
            if not selected_characters:
                return False, "请至少选择一个角色"
            
            if not llm_api_key or not llm_api_key.strip():
                return False, "请配置LLM API Key"
            
            return True, "配置有效"
            
        except Exception as e:
            logger.error(f"验证任务配置失败: {e}")
            return False, f"验证失败: {str(e)}"
    
    def generate_task_name(
        self,
        selected_characters: List[str],
        story_type: str,
        story_count: int
    ) -> str:
        """自动生成任务名称"""
        try:
            # 基于配置生成任务名称
            char_names = "、".join(selected_characters[:3])  # 最多显示3个角色名
            if len(selected_characters) > 3:
                char_names += "等"
            
            type_map = {
                'daily_life': '日常',
                'romance': '恋爱',
                'adventure': '冒险',
                'mystery': '悬疑'
            }
            
            story_type_name = type_map.get(story_type, story_type)
            
            timestamp = datetime.now().strftime('%m%d_%H%M')
            
            task_name = f"{char_names}_{story_type_name}剧情_{story_count}个_{timestamp}"
            
            return task_name
            
        except Exception as e:
            logger.error(f"生成任务名称失败: {e}")
            return f"剧情生成任务_{datetime.now().strftime('%m%d_%H%M')}"


# 全局处理器实例
queue_handlers = QueueHandlers() 