#!/usr/bin/env python3
"""
测试新的多周期工作流功能
"""

import asyncio
import sys
import logging
from pathlib import Path

# 添加项目路径
current_dir = Path(__file__).parent
src_path = current_dir / "src"
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(current_dir))

from batch_schedule_generator import BatchScheduleGenerator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_new_workflow():
    """测试新的多周期工作流"""
    print("开始测试新的多周期工作流...")
    
    try:
        # 创建批量生成器 - 使用较小的配置进行测试
        generator = BatchScheduleGenerator(
            start_date='2025-07-20',
            batch_count=1  # 只测试1个批次
        )
        
        print(f"批量生成器初始化成功")
        print(f"开始日期: 2025-07-20")
        print(f"批次数量: 1")
        
        # 生成一个测试批次
        print(f"\n开始生成测试批次...")
        print(f"注意: 豆包LLM将显示实时生成过程")
        
        success_count, failed_count = await generator.generate_all_batches()
        
        print(f"\n测试结果:")
        print(f"成功批次: {success_count}")
        print(f"失败批次: {failed_count}")
        print(f"成功率: {success_count/(success_count+failed_count)*100:.1f}%" if (success_count+failed_count) > 0 else "无数据")
        
        if success_count > 0:
            print(f"\n新的多周期工作流测试成功！")
            print(f"输出目录: {generator.output_dir}")
            
            # 显示批次历史信息
            if generator.batch_history:
                batch_info = generator.batch_history[0]
                print(f"\n批次详情:")
                print(f"  日期范围: {batch_info.get('start_date')} - {batch_info.get('end_date')}")
                print(f"  总天数: {batch_info.get('total_days')}")
                print(f"  周期数: {batch_info.get('cycles_count', 'N/A')}")
                print(f"  角色数: {len(batch_info.get('characters', []))}")
                print(f"  地点数: {len(batch_info.get('locations', []))}")
                
                if 'cycle_summaries' in batch_info:
                    print(f"  周期总结数: {len(batch_info['cycle_summaries'])}")
        else:
            print(f"\n测试失败，请检查日志")
            
    except Exception as e:
        print(f"\n测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主函数"""
    print("=" * 60)
    print("新多周期工作流测试程序")
    print("=" * 60)
    
    await test_new_workflow()
    
    print(f"\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    # 设置Windows异步事件循环策略
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main()) 