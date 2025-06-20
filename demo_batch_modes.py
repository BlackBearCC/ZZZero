#!/usr/bin/env python3
"""
批处理器模式演示 - 展示并行/遍历两种模式的差异
"""
import asyncio
import time
from typing import Dict, Any, AsyncIterator
from datetime import datetime


class MockBatchProcessor:
    """模拟批处理器 - 用于演示进度展示功能"""
    
    def __init__(self):
        self.mode = "parallel"
        self.tasks = [
            {"id": 1, "name": "生成张三的日程", "duration": 2.0},
            {"id": 2, "name": "生成李四的日程", "duration": 1.5},
            {"id": 3, "name": "生成王五的日程", "duration": 2.5},
            {"id": 4, "name": "生成赵六的日程", "duration": 1.8},
            {"id": 5, "name": "生成孙七的日程", "duration": 2.2}
        ]
    
    async def process_parallel_mode(self) -> AsyncIterator[Dict[str, Any]]:
        """并行模式处理演示"""
        yield {
            "type": "instruction_generated",
            "content": "📋 **批处理指令已生成**\n\n**处理模式**: 并行模式\n**任务数量**: 5个\n\n🚀 开始并行执行..."
        }
        
        # 模拟分批处理
        batches = [self.tasks[:3], self.tasks[3:]]
        
        for batch_idx, batch_tasks in enumerate(batches):
            yield {
                "type": "batch_start",
                "content": f"📦 开始处理第 {batch_idx + 1}/2 批次 ({len(batch_tasks)}个任务)"
            }
            
            # 模拟并行执行（同时开始）
            start_time = time.time()
            max_duration = max(task["duration"] for task in batch_tasks)
            
            # 等待最长任务完成
            await asyncio.sleep(max_duration)
            
            # 批次完成
            completed = (batch_idx + 1) * len(batch_tasks)
            if batch_idx == 1:
                completed = 5  # 总共5个任务
                
            progress = completed / 5 * 100
            
            yield {
                "type": "batch_completed",
                "content": f"✅ 第 {batch_idx + 1}/2 批次完成 - 进度: {progress:.1f}% ({completed}/5)",
                "progress": {
                    "percentage": progress,
                    "completed": completed,
                    "total": 5,
                    "successful": completed,
                    "failed": 0
                }
            }
        
        yield {
            "type": "final_summary",
            "content": "🎉 **批处理任务完成！**\n\n📊 **执行统计**:\n- 总任务数: 5\n- 成功任务: 5\n- 失败任务: 0\n- 成功率: 100.0%\n\n⏱️ **时间统计**:\n- 处理模式: 并行模式\n- 优势: 快速高效，适合独立任务"
        }
    
    async def process_sequential_mode(self) -> AsyncIterator[Dict[str, Any]]:
        """遍历模式处理演示"""
        yield {
            "type": "instruction_generated", 
            "content": "📋 **批处理指令已生成**\n\n**处理模式**: 遍历模式\n**任务数量**: 5个\n\n🚀 开始顺序执行..."
        }
        
        yield {
            "type": "sequential_start",
            "content": "🔄 开始顺序处理 5 个任务..."
        }
        
        # 逐个处理任务
        for idx, task in enumerate(self.tasks):
            yield {
                "type": "task_start",
                "content": f"🔄 正在处理第 {idx + 1}/5 个任务\n**任务内容**: {task['name']}\n**进度**: {(idx / 5 * 100):.1f}%"
            }
            
            # 模拟任务执行
            await asyncio.sleep(task["duration"])
            
            progress = ((idx + 1) / 5) * 100
            
            yield {
                "type": "task_completed",
                "content": f"✅ 第 {idx + 1}/5 个任务完成\n**执行时间**: {task['duration']:.1f}秒\n**任务**: {task['name']}\n**总体进度**: {progress:.1f}%",
                "progress": {
                    "percentage": progress,
                    "completed": idx + 1,
                    "total": 5,
                    "successful": idx + 1,
                    "failed": 0
                }
            }
        
        yield {
            "type": "final_summary",
            "content": "🎉 **批处理任务完成！**\n\n📊 **执行统计**:\n- 总任务数: 5\n- 成功任务: 5\n- 失败任务: 0\n- 成功率: 100.0%\n\n⏱️ **时间统计**:\n- 处理模式: 遍历模式\n- 优势: 实时反馈，适合监控任务进度"
        }


async def demo_parallel_mode():
    """演示并行模式"""
    print("🔥 并行模式演示")
    print("="*50)
    print("特点：同时执行多个任务，速度快")
    print("适用：独立任务，追求效率")
    print("-"*50)
    
    processor = MockBatchProcessor()
    start_time = time.time()
    
    async for progress_data in processor.process_parallel_mode():
        progress_type = progress_data.get("type", "")
        content = progress_data.get("content", "")
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{timestamp}] {progress_type.upper()}")
        
        # 格式化显示内容
        lines = content.split('\n')
        for line in lines:
            if line.strip():
                print(f"  {line}")
        
        # 显示进度信息
        if "progress" in progress_data:
            progress_info = progress_data["progress"]
            percentage = progress_info.get("percentage", 0)
            completed = progress_info.get("completed", 0)
            total = progress_info.get("total", 0)
            print(f"  📊 进度条: {'█' * int(percentage/10):<10} {percentage:.1f}% ({completed}/{total})")
    
    duration = time.time() - start_time
    print(f"\n⏱️ 并行模式总耗时: {duration:.1f}秒")


async def demo_sequential_mode():
    """演示遍历模式"""
    print("\n\n🔥 遍历模式演示")
    print("="*50)
    print("特点：逐个执行任务，可实时查看每个任务进度")
    print("适用：依赖性任务，需要监控细节")
    print("-"*50)
    
    processor = MockBatchProcessor()
    start_time = time.time()
    
    async for progress_data in processor.process_sequential_mode():
        progress_type = progress_data.get("type", "")
        content = progress_data.get("content", "")
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{timestamp}] {progress_type.upper()}")
        
        # 格式化显示内容
        lines = content.split('\n')
        for line in lines:
            if line.strip():
                print(f"  {line}")
        
        # 显示进度信息
        if "progress" in progress_data:
            progress_info = progress_data["progress"]
            percentage = progress_info.get("percentage", 0)
            completed = progress_info.get("completed", 0)
            total = progress_info.get("total", 0)
            print(f"  📊 进度条: {'█' * int(percentage/10):<10} {percentage:.1f}% ({completed}/{total})")
    
    duration = time.time() - start_time
    print(f"\n⏱️ 遍历模式总耗时: {duration:.1f}秒")


async def demo_comparison():
    """演示两种模式的对比"""
    print("\n\n🎯 模式对比总结")
    print("="*60)
    
    print("""
📊 **并行模式 (Parallel)**
✅ 优势：
  - 执行速度快，效率高
  - 适合处理大量独立任务
  - 充分利用系统资源

⚠️ 限制：
  - 进度反馈较粗糙（按批次）
  - 不适合有依赖关系的任务
  - 错误定位相对困难

🔄 **遍历模式 (Sequential)**  
✅ 优势：
  - 实时详细的进度反馈
  - 容易监控和调试
  - 适合有依赖关系的任务
  - 错误可以即时发现和处理

⚠️ 限制：
  - 执行时间较长
  - 无法并行利用资源
  - 某个任务失败会影响后续任务

💡 **选择建议**：
  - 大量独立任务 → 选择并行模式
  - 需要实时监控 → 选择遍历模式  
  - 任务间有依赖 → 选择遍历模式
  - 追求最快速度 → 选择并行模式
    """)


async def main():
    """主演示函数"""
    print("🎯 批处理器模式演示")
    print("展示内容：并行模式 vs 遍历模式的差异和应用场景")
    print("="*70)
    
    # 演示并行模式
    await demo_parallel_mode()
    
    # 等待用户观察
    await asyncio.sleep(1)
    
    # 演示遍历模式
    await demo_sequential_mode()
    
    # 对比总结
    await demo_comparison()
    
    print("\n🎉 演示完成！")
    print("\n💡 在实际的ZZZero系统中，您可以在Web界面的批处理配置中选择适合的模式。")


if __name__ == "__main__":
    asyncio.run(main()) 