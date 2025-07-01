"""
任务队列管理器
支持剧情生成任务的排队执行
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 等待中
    RUNNING = "running"      # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 已取消


@dataclass
class QueueTask:
    """队列任务数据结构"""
    task_id: str
    task_name: str
    config: Dict[str, Any]
    status: TaskStatus
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    priority: int = 0  # 优先级，数字越大优先级越高
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueueTask':
        """从字典创建任务"""
        data['status'] = TaskStatus(data['status'])
        return cls(**data)


class TaskQueue:
    """任务队列管理器"""
    
    def __init__(self):
        self.tasks: List[QueueTask] = []
        self.is_running = False
        self.current_task: Optional[QueueTask] = None
        self.executor_task: Optional[asyncio.Task] = None
        self._callbacks: Dict[str, List[Callable]] = {
            'task_added': [],
            'task_started': [],
            'task_completed': [],
            'task_failed': [],
            'queue_started': [],
            'queue_stopped': []
        }
        
    def add_task(self, task_name: str, config: Dict[str, Any], priority: int = 0) -> str:
        """添加任务到队列"""
        task_id = str(uuid.uuid4())
        task = QueueTask(
            task_id=task_id,
            task_name=task_name,
            config=config,
            status=TaskStatus.PENDING,
            created_at=datetime.now().isoformat(),
            priority=priority
        )
        
        # 按优先级插入任务
        inserted = False
        for i, existing_task in enumerate(self.tasks):
            if existing_task.status == TaskStatus.PENDING and task.priority > existing_task.priority:
                self.tasks.insert(i, task)
                inserted = True
                break
        
        if not inserted:
            self.tasks.append(task)
        
        logger.info(f"任务已添加到队列: {task_name} (ID: {task_id})")
        self._trigger_callback('task_added', task)
        
        return task_id
    
    def remove_task(self, task_id: str) -> bool:
        """移除任务"""
        for i, task in enumerate(self.tasks):
            if task.task_id == task_id:
                if task.status == TaskStatus.RUNNING:
                    logger.warning(f"无法删除正在执行的任务: {task_id}")
                    return False
                
                self.tasks.pop(i)
                logger.info(f"任务已从队列移除: {task_id}")
                return True
        
        logger.warning(f"未找到任务: {task_id}")
        return False
    
    def move_task(self, task_id: str, new_position: int) -> bool:
        """调整任务在队列中的位置"""
        try:
            # 找到任务
            task_index = None
            for i, task in enumerate(self.tasks):
                if task.task_id == task_id and task.status == TaskStatus.PENDING:
                    task_index = i
                    break
            
            if task_index is None:
                logger.warning(f"未找到待执行任务: {task_id}")
                return False
            
            # 移动任务
            task = self.tasks.pop(task_index)
            new_position = max(0, min(new_position, len(self.tasks)))
            self.tasks.insert(new_position, task)
            
            logger.info(f"任务位置已调整: {task_id} -> 位置 {new_position}")
            return True
            
        except Exception as e:
            logger.error(f"调整任务位置失败: {e}")
            return False
    
    def get_task_list(self) -> List[Dict[str, Any]]:
        """获取任务列表"""
        return [task.to_dict() for task in self.tasks]
    
    def get_task(self, task_id: str) -> Optional[QueueTask]:
        """获取指定任务"""
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        return None
    
    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        pending_count = sum(1 for task in self.tasks if task.status == TaskStatus.PENDING)
        running_count = sum(1 for task in self.tasks if task.status == TaskStatus.RUNNING)
        completed_count = sum(1 for task in self.tasks if task.status == TaskStatus.COMPLETED)
        failed_count = sum(1 for task in self.tasks if task.status == TaskStatus.FAILED)
        
        return {
            'is_running': self.is_running,
            'current_task': self.current_task.to_dict() if self.current_task else None,
            'total_tasks': len(self.tasks),
            'pending_count': pending_count,
            'running_count': running_count,
            'completed_count': completed_count,
            'failed_count': failed_count,
            'next_task': self._get_next_pending_task().to_dict() if self._get_next_pending_task() else None
        }
    
    def start_queue(self):
        """启动队列执行"""
        if self.is_running:
            logger.warning("队列已在运行中")
            return
        
        self.is_running = True
        self.executor_task = asyncio.create_task(self._execute_queue())
        logger.info("任务队列已启动")
        self._trigger_callback('queue_started')
    
    def stop_queue(self):
        """停止队列执行"""
        if not self.is_running:
            logger.warning("队列未在运行")
            return
        
        self.is_running = False
        if self.executor_task:
            self.executor_task.cancel()
        
        logger.info("任务队列已停止")
        self._trigger_callback('queue_stopped')
    
    def clear_completed_tasks(self):
        """清除已完成的任务"""
        before_count = len(self.tasks)
        self.tasks = [task for task in self.tasks if task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED]]
        after_count = len(self.tasks)
        
        logger.info(f"已清除 {before_count - after_count} 个已完成的任务")
    
    def add_callback(self, event_type: str, callback: Callable):
        """添加事件回调"""
        if event_type in self._callbacks:
            self._callbacks[event_type].append(callback)
    
    def _get_next_pending_task(self) -> Optional[QueueTask]:
        """获取下一个待执行任务"""
        for task in self.tasks:
            if task.status == TaskStatus.PENDING:
                return task
        return None
    
    async def _execute_queue(self):
        """队列执行主循环"""
        try:
            while self.is_running:
                next_task = self._get_next_pending_task()
                
                if next_task is None:
                    # 没有待执行任务，等待
                    await asyncio.sleep(1)
                    continue
                
                # 执行任务
                await self._execute_task(next_task)
                
        except asyncio.CancelledError:
            logger.info("队列执行器已取消")
        except Exception as e:
            logger.error(f"队列执行器异常: {e}")
        finally:
            self.is_running = False
            self.current_task = None
    
    async def _execute_task(self, task: QueueTask):
        """执行单个任务"""
        try:
            # 更新任务状态
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now().isoformat()
            self.current_task = task
            
            logger.info(f"开始执行任务: {task.task_name} (ID: {task.task_id})")
            self._trigger_callback('task_started', task)
            
            # 执行剧情生成工作流
            from src.workflow.story_workflow import StoryWorkflow
            
            # 获取LLM实例
            from src.llm.base import LLMFactory
            llm_config = task.config.get('llm_config', {})
            llm = LLMFactory.create_llm(llm_config)
            
            workflow = StoryWorkflow(llm=llm)
            result = await workflow.execute_story_generation(task.config)
            
            # 任务完成
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now().isoformat()
            task.result = {
                'success': True,
                'message': '剧情生成完成',
                'data': result.__dict__ if hasattr(result, '__dict__') else str(result)
            }
            
            logger.info(f"任务执行完成: {task.task_name} (ID: {task.task_id})")
            self._trigger_callback('task_completed', task)
            
        except Exception as e:
            # 任务失败
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now().isoformat()
            task.error_message = str(e)
            task.result = {
                'success': False,
                'message': f'任务执行失败: {str(e)}',
                'error': str(e)
            }
            
            logger.error(f"任务执行失败: {task.task_name} (ID: {task.task_id}) - {e}")
            self._trigger_callback('task_failed', task)
        
        finally:
            self.current_task = None
    
    def _trigger_callback(self, event_type: str, task: Optional[QueueTask] = None):
        """触发事件回调"""
        for callback in self._callbacks.get(event_type, []):
            try:
                if task:
                    callback(task)
                else:
                    callback()
            except Exception as e:
                logger.error(f"回调函数执行失败: {e}")


# 全局任务队列实例
task_queue = TaskQueue() 