"""
测试剧情生成工作流
"""

import asyncio
import sys
import os

# 添加src目录到路径
sys.path.append('src')

from src.workflow.story_workflow import StoryWorkflow

async def test_story_workflow():
    """测试剧情生成工作流"""
    print("🎭 开始测试剧情生成工作流...")
    
    try:
        # 创建工作流实例
        workflow = StoryWorkflow()
        
        # 获取角色和地点列表
        characters = workflow.get_characters_list()
        locations = workflow.get_locations_list()
        
        print(f"📋 加载了 {len(characters)} 个角色")
        print(f"🏢 加载了 {len(locations)} 个地点")
        
        # 选择测试角色和地点
        test_characters = [char['name'] for char in characters[:3]]  # 前3个角色
        test_locations = [loc['name'] for loc in locations[:3]]      # 前3个地点
        
        print(f"🎯 测试角色: {test_characters}")
        print(f"🎯 测试地点: {test_locations}")
        
        # 配置测试参数
        config = {
            'selected_characters': test_characters,
            'selected_locations': test_locations,
            'story_type': 'daily_life',
            'story_length': 'medium',
            'relationship_depth': 'casual'
        }
        
        # 执行工作流
        print("🚀 开始执行剧情生成工作流...")
        result = await workflow.execute_story_generation(config)
        
        # 检查结果
        if hasattr(result, 'data'):
            result_data = result.data
        else:
            result_data = result
        
        story_events = result_data.get('story_events', [])
        export_file = result_data.get('export_file', '')
        
        print(f"✅ 工作流执行成功！")
        print(f"📚 生成了 {len(story_events)} 个剧情事件")
        if export_file:
            print(f"📄 导出文件: {export_file}")
        
        # 显示前几个剧情事件
        print("\n📖 前几个剧情事件预览:")
        for i, event in enumerate(story_events[:3]):
            print(f"  {i+1}. {event.get('plot_name', '')} - {event.get('character', '')} @ {event.get('location', '')}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # 运行测试
    success = asyncio.run(test_story_workflow())
    if success:
        print("\n🎉 剧情生成工作流测试通过！")
    else:
        print("\n💥 剧情生成工作流测试失败！") 