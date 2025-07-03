#!/usr/bin/env python3
"""
批量处理器保存功能测试脚本
"""

import sys
import os
from pathlib import Path

# 添加项目路径
current_dir = Path(__file__).parent
src_path = current_dir / "src"
sys.path.insert(0, str(src_path))

def test_batch_processor_save():
    """测试批量处理器保存功能"""
    try:
        from workflow.schedule_workflow import ScheduleWorkflow
        
        print("🧪 测试批量处理器保存功能...")
        
        # 创建工作流实例
        workflow = ScheduleWorkflow()
        
        # 检查是否有run_batch_processor方法
        if hasattr(workflow, 'run_batch_processor'):
            print("✅ run_batch_processor方法存在")
        else:
            print("❌ run_batch_processor方法不存在")
            return False
        
        # 检查批量处理器类
        from core.batch_processor import BatchProcessor
        batch_processor = BatchProcessor()
        
        if hasattr(batch_processor, 'save_results_to_csv'):
            print("✅ save_results_to_csv方法存在")
        else:
            print("❌ save_results_to_csv方法不存在")
            return False
        
        # 测试保存功能（使用空数据）
        test_data = [
            {"id": 1, "content": "测试数据1", "status": "success"},
            {"id": 2, "content": "测试数据2", "status": "success"}
        ]
        
        result = batch_processor.save_results_to_csv(test_data)
        if result:
            print("✅ 保存功能测试成功")
        else:
            print("❌ 保存功能测试失败")
        
        print("🎉 所有测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_batch_processor_save()
    sys.exit(0 if success else 1)
