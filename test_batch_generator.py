#!/usr/bin/env python3
"""
批量日程生成器测试脚本 - 快速验证功能
"""

import asyncio
import sys
from pathlib import Path
import logging

# 添加项目路径
current_dir = Path(__file__).parent
src_path = current_dir / "src"
sys.path.insert(0, str(src_path))

from batch_schedule_generator import BatchScheduleGenerator

# 配置简单日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_batch_generator():
    """测试批量生成器的基本功能"""
    print("🧪 开始测试批量日程生成器...")
    
    try:
        # 创建一个小规模的测试实例（只生成2个批次）
        generator = BatchScheduleGenerator(
            start_date="2025-07-02",
            batch_count=2
        )
        
        print("✅ 生成器初始化成功")
        
        # 测试随机配置生成
        print("\n📋 测试随机配置生成...")
        config1 = generator._get_random_config(1)
        config2 = generator._get_random_config(2)
        
        print(f"  批次1配置: {config1['total_days']}天, {len(config1['selected_characters'])}角色, {len(config1['selected_locations'])}地点")
        print(f"  批次2配置: {config2['total_days']}天, {len(config2['selected_characters'])}角色, {len(config2['selected_locations'])}地点")
        
        # 检查角色和地点数据是否正确加载
        print(f"\n📊 数据加载状态:")
        print(f"  可用角色数: {len(generator.workflow.characters_data.get('角色列表', {}))}")
        print(f"  可用地点数: {len([loc for district in generator.workflow.locations_data.get('districts', {}).values() for loc in district.get('locations', {})])}")
        print(f"  节假日数: {len(generator.workflow.holidays_data)}")
        
        # 测试单个批次生成（注释掉实际生成，避免API调用）
        print(f"\n⚠️  为了避免API调用，跳过实际生成测试")
        print(f"✅ 基本功能验证完成")
        
        # 显示输出路径
        print(f"\n📁 输出配置:")
        print(f"  输出目录: {generator.output_dir}")
        print(f"  CSV文件: {generator.csv_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主测试函数"""
    print("🚀 批量日程生成器功能测试")
    print("=" * 50)
    
    success = await test_batch_generator()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ 所有测试通过!")
        print("\n💡 如需完整测试，请运行:")
        print("   python batch_schedule_generator.py --batch-count 2")
    else:
        print("❌ 测试失败，请检查配置和依赖")
    
    return success

if __name__ == "__main__":
    # 设置Windows异步事件循环策略
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    result = asyncio.run(main())
    sys.exit(0 if result else 1) 