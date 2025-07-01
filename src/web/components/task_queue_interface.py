"""
任务队列管理界面
纯粹的队列操作，不包含任务配置功能
"""

import gradio as gr
import pandas as pd
import logging
from typing import Dict, List, Any, Tuple
from datetime import datetime
import asyncio

# 导入任务队列
from core.task_queue import task_queue, TaskStatus

logger = logging.getLogger(__name__)


class TaskQueueInterface:
    """任务队列管理界面"""
    
    def __init__(self):
        self.refresh_interval = 2  # 自动刷新间隔（秒）
        
    def create_interface(self) -> gr.Blocks:
        """创建任务队列界面"""
        with gr.Blocks(title="任务队列管理") as interface:
            gr.Markdown("# 🔄 任务队列管理")
            gr.Markdown("管理剧情生成任务的排队执行，新增任务请前往故事工作流页面")
            
            with gr.Row():
                # 左侧队列状态
                with gr.Column(scale=1):
                    gr.Markdown("## 📊 队列状态")
                    
                    queue_status_display = gr.HTML(
                        value=self._create_queue_status_display(),
                        label="队列状态"
                    )
                    
                    # 队列控制按钮
                    with gr.Row():
                        start_queue_btn = gr.Button("▶️ 启动队列", variant="primary")
                        stop_queue_btn = gr.Button("⏸️ 停止队列", variant="secondary")
                    
                    with gr.Row():
                        clear_completed_btn = gr.Button("🧹 清除已完成", variant="secondary")
                        refresh_btn = gr.Button("🔄 刷新", variant="secondary")
                    
                    # 自动刷新控制
                    auto_refresh_checkbox = gr.Checkbox(
                        label="自动刷新",
                        value=True,
                        info="每2秒自动更新队列状态"
                    )
                
                # 右侧任务列表
                with gr.Column(scale=2):
                    gr.Markdown("## 📋 任务列表")
                    
                    # 任务列表表格
                    task_table = gr.Dataframe(
                        value=self._load_task_table(),
                        headers=["任务ID", "任务名称", "状态", "优先级", "创建时间", "开始时间", "完成时间"],
                        datatype=["str", "str", "str", "number", "str", "str", "str"],
                        interactive=False,
                        wrap=True
                    )
                    
                    # 选中任务的详细信息
                    with gr.Accordion("📝 任务详情", open=False):
                        selected_task_id = gr.Textbox(
                            label="选中的任务ID",
                            placeholder="点击表格行选择任务",
                            interactive=False
                        )
                        
                        task_detail_display = gr.Markdown("请先选择一个任务")
                    
                    # 任务操作按钮
                    with gr.Row():
                        delete_task_btn = gr.Button("🗑️ 删除任务", variant="stop")
                        move_up_btn = gr.Button("⬆️ 上移", variant="secondary")
                        move_down_btn = gr.Button("⬇️ 下移", variant="secondary")
        
        # 事件绑定
        start_queue_btn.click(
            fn=self._start_queue,
            outputs=[queue_status_display, task_table]
        )
        
        stop_queue_btn.click(
            fn=self._stop_queue,
            outputs=[queue_status_display, task_table]
        )
        
        clear_completed_btn.click(
            fn=self._clear_completed_tasks,
            outputs=[queue_status_display, task_table]
        )
        
        refresh_btn.click(
            fn=self._refresh_interface,
            outputs=[queue_status_display, task_table]
        )
        
        task_table.select(
            fn=self._on_task_selected,
            outputs=[selected_task_id, task_detail_display]
        )
        
        delete_task_btn.click(
            fn=self._delete_task,
            inputs=[selected_task_id],
            outputs=[queue_status_display, task_table, selected_task_id, task_detail_display]
        )
        
        move_up_btn.click(
            fn=self._move_task_up,
            inputs=[selected_task_id],
            outputs=[queue_status_display, task_table]
        )
        
        move_down_btn.click(
            fn=self._move_task_down,
            inputs=[selected_task_id],
            outputs=[queue_status_display, task_table]
        )
        
        return interface
    
    def _create_queue_status_display(self) -> str:
        """创建队列状态显示"""
        try:
            status = task_queue.get_queue_status()
            
            # 状态图标和颜色
            if status['is_running']:
                status_icon = "🟢"
                status_text = "运行中"
                status_color = "#10b981"
            else:
                status_icon = "🔴"
                status_text = "已停止"
                status_color = "#ef4444"
            
            # 当前任务信息
            current_task_info = ""
            if status['current_task']:
                current_task = status['current_task']
                current_task_info = f"""
                <div style="background: #f0f9ff; border: 1px solid #0ea5e9; border-radius: 8px; padding: 10px; margin: 10px 0;">
                    <strong>🔄 当前执行任务:</strong><br>
                    <strong>{current_task['task_name']}</strong><br>
                    <small>ID: {current_task['task_id'][:8]}...</small>
                </div>
                """
            
            # 下一个任务信息
            next_task_info = ""
            if status['next_task']:
                next_task = status['next_task']
                next_task_info = f"""
                <div style="background: #fefce8; border: 1px solid #eab308; border-radius: 8px; padding: 10px; margin: 10px 0;">
                    <strong>⏳ 下一个任务:</strong><br>
                    <strong>{next_task['task_name']}</strong><br>
                    <small>ID: {next_task['task_id'][:8]}...</small>
                </div>
                """
            
            html = f"""
            <div style="background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);">
                <div style="display: flex; align-items: center; margin-bottom: 15px;">
                    <span style="font-size: 24px; margin-right: 10px;">{status_icon}</span>
                    <div>
                        <h3 style="margin: 0; color: {status_color};">队列状态: {status_text}</h3>
                        <p style="margin: 5px 0 0 0; color: #6b7280; font-size: 14px;">
                            总任务数: {status['total_tasks']} | 
                            等待: {status['pending_count']} | 
                            运行: {status['running_count']} | 
                            完成: {status['completed_count']} | 
                            失败: {status['failed_count']}
                        </p>
                    </div>
                </div>
                
                {current_task_info}
                {next_task_info}
                
                <div style="font-size: 12px; color: #9ca3af; text-align: center; margin-top: 10px;">
                    最后更新: {datetime.now().strftime('%H:%M:%S')}
                </div>
            </div>
            """
            
            return html
            
        except Exception as e:
            logger.error(f"创建队列状态显示失败: {e}")
            return f"<div style='color: red;'>状态加载失败: {str(e)}</div>"
    
    def _load_task_table(self) -> pd.DataFrame:
        """加载任务列表表格"""
        try:
            tasks = task_queue.get_task_list()
            
            data = []
            for task in tasks:
                # 状态图标
                status_icons = {
                    TaskStatus.PENDING.value: "⏳ 等待中",
                    TaskStatus.RUNNING.value: "🔄 执行中", 
                    TaskStatus.COMPLETED.value: "✅ 已完成",
                    TaskStatus.FAILED.value: "❌ 失败",
                    TaskStatus.CANCELLED.value: "🚫 已取消"
                }
                
                status_display = status_icons.get(task['status'], task['status'])
                
                data.append([
                    task['task_id'][:8] + "...",  # 显示短ID
                    task['task_name'],
                    status_display,
                    task['priority'],
                    task['created_at'][:19] if task['created_at'] else "",
                    task['started_at'][:19] if task['started_at'] else "",
                    task['completed_at'][:19] if task['completed_at'] else ""
                ])
            
            return pd.DataFrame(data, columns=["任务ID", "任务名称", "状态", "优先级", "创建时间", "开始时间", "完成时间"])
            
        except Exception as e:
            logger.error(f"加载任务列表失败: {e}")
            return pd.DataFrame(columns=["任务ID", "任务名称", "状态", "优先级", "创建时间", "开始时间", "完成时间"])
    
    def _start_queue(self) -> Tuple[str, pd.DataFrame]:
        """启动队列"""
        try:
            task_queue.start_queue()
            return self._refresh_interface()
        except Exception as e:
            logger.error(f"启动队列失败: {e}")
            return f"<div style='color: red;'>启动失败: {str(e)}</div>", self._load_task_table()
    
    def _stop_queue(self) -> Tuple[str, pd.DataFrame]:
        """停止队列"""
        try:
            task_queue.stop_queue()
            return self._refresh_interface()
        except Exception as e:
            logger.error(f"停止队列失败: {e}")
            return f"<div style='color: red;'>停止失败: {str(e)}</div>", self._load_task_table()
    
    def _clear_completed_tasks(self) -> Tuple[str, pd.DataFrame]:
        """清除已完成任务"""
        try:
            task_queue.clear_completed_tasks()
            return self._refresh_interface()
        except Exception as e:
            logger.error(f"清除任务失败: {e}")
            return f"<div style='color: red;'>清除失败: {str(e)}</div>", self._load_task_table()
    
    def _refresh_interface(self) -> Tuple[str, pd.DataFrame]:
        """刷新界面"""
        return self._create_queue_status_display(), self._load_task_table()
    
    def _on_task_selected(self, evt: gr.SelectData) -> Tuple[str, str]:
        """处理任务选择事件"""
        try:
            if evt is None or evt.index is None:
                return "", "请先选择一个任务"
            
            # 获取选中行的索引
            row_index = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
            
            # 重新获取数据以确保索引对应正确
            tasks = task_queue.get_task_list()
            
            if row_index >= len(tasks):
                return "", "选择的行索引超出范围"
                
            task = tasks[row_index]
            task_id = task['task_id']
            
            # 构建任务详细信息
            status_icons = {
                TaskStatus.PENDING.value: "⏳",
                TaskStatus.RUNNING.value: "🔄", 
                TaskStatus.COMPLETED.value: "✅",
                TaskStatus.FAILED.value: "❌",
                TaskStatus.CANCELLED.value: "🚫"
            }
            
            status_icon = status_icons.get(task['status'], "❓")
            
            detail_info = f"""### {status_icon} 任务详情

**任务ID**: `{task['task_id']}`
**任务名称**: {task['task_name']}
**状态**: {task['status']}
**优先级**: {task['priority']}
**创建时间**: {task['created_at']}
**开始时间**: {task['started_at'] or '未开始'}
**完成时间**: {task['completed_at'] or '未完成'}

**配置信息**:
```json
{task['config']}
```
"""
            
            # 如果有错误信息
            if task.get('error_message'):
                detail_info += f"\n**错误信息**: {task['error_message']}"
            
            # 如果有执行结果
            if task.get('result'):
                detail_info += f"\n**执行结果**: {task['result']}"
            
            return task_id, detail_info
            
        except Exception as e:
            logger.error(f"选择任务失败: {e}")
            return "", f"处理任务选择失败: {str(e)}"
    
    def _delete_task(self, task_id: str) -> Tuple[str, pd.DataFrame, str, str]:
        """删除任务"""
        try:
            if not task_id:
                return self._refresh_interface() + ("", "请先选择要删除的任务")
            
            success = task_queue.remove_task(task_id)
            
            if success:
                return self._refresh_interface() + ("", f"✅ 任务已删除: {task_id}")
            else:
                return self._refresh_interface() + (task_id, f"❌ 删除任务失败: {task_id}")
                
        except Exception as e:
            logger.error(f"删除任务失败: {e}")
            return self._refresh_interface() + (task_id, f"❌ 删除任务异常: {str(e)}")
    
    def _move_task_up(self, task_id: str) -> Tuple[str, pd.DataFrame]:
        """任务上移"""
        try:
            if not task_id:
                return self._refresh_interface()
            
            # 找到任务当前位置
            tasks = task_queue.get_task_list()
            current_pos = None
            for i, task in enumerate(tasks):
                if task['task_id'] == task_id:
                    current_pos = i
                    break
            
            if current_pos is None or current_pos == 0:
                return self._refresh_interface()  # 无法上移
            
            task_queue.move_task(task_id, current_pos - 1)
            return self._refresh_interface()
            
        except Exception as e:
            logger.error(f"任务上移失败: {e}")
            return self._refresh_interface()
    
    def _move_task_down(self, task_id: str) -> Tuple[str, pd.DataFrame]:
        """任务下移"""
        try:
            if not task_id:
                return self._refresh_interface()
            
            # 找到任务当前位置
            tasks = task_queue.get_task_list()
            current_pos = None
            for i, task in enumerate(tasks):
                if task['task_id'] == task_id:
                    current_pos = i
                    break
            
            if current_pos is None or current_pos >= len(tasks) - 1:
                return self._refresh_interface()  # 无法下移
            
            task_queue.move_task(task_id, current_pos + 1)
            return self._refresh_interface()
            
        except Exception as e:
            logger.error(f"任务下移失败: {e}")
            return self._refresh_interface() 