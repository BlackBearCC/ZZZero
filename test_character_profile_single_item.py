"""
测试角色资料工作流的逐个条目生成功能
"""

import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '.'))

from src.workflow.character_profile_workflow import ProfileGeneratorNode, ProfileRequest
from src.llm.base import LLMFactory
from src.core.types import LLMConfig

async def test_single_item_generation():
    """测试逐个条目生成功能"""
    
    # 创建LLM配置
    llm_config = LLMConfig(
        provider="zhipu",
        model="glm-4-flash",
        api_key=os.getenv("ZHIPU_API_KEY"),
        temperature=0.7
    )
    
    # 创建LLM实例
    llm = LLMFactory.create_llm(llm_config)
    
    # 创建角色资料生成节点
    generator = ProfileGeneratorNode(
        name="test_profile_generator",
        llm_config=llm_config
    )
    
    # 准备测试请求
    request = {
        "name": "测试角色",
        "info": "一个年轻的剑客，来自江南水乡，性格温和但内心坚韧。",
        "categories": ["基本信息"],  # 只选择一个类别进行测试
        "collections": []  # 不使用知识库
    }
    
    # 准备状态
    state = {
        "request": request,
        "llm": llm,
        "_graph_name": "character_profile_test"
    }
    
    print("开始测试逐个条目生成功能...")
    print(f"角色名称: {request['name']}")
    print(f"基础信息: {request['info']}")
    print(f"选择类别: {request['categories']}")
    print("-" * 50)
    
    # 执行流式生成
    try:
        async for result in generator.execute_stream(state):
            if result.get("success") is False and "progress" in result:
                # 中间进度
                print(f"进度: {result['progress']}")
                if "current_item" in result:
                    print(f"当前条目: {result['current_item']}")
                if "completed_items" in result and "total_items" in result:
                    print(f"完成进度: {result['completed_items']}/{result['total_items']}")
                print("-" * 30)
            elif result.get("success") is True:
                # 最终结果
                print("生成完成！")
                print(f"输出文件: {result.get('output_file', '未知')}")
                profile = result.get("profile", {})
                
                for category, category_data in profile.items():
                    print(f"\n类别: {category}")
                    if isinstance(category_data, dict):
                        for item_name, item_content in category_data.items():
                            print(f"  条目: {item_name}")
                            print(f"  内容: {item_content[:100]}..." if len(item_content) > 100 else f"  内容: {item_content}")
                            print()
                break
            elif result.get("success") is False and "error" in result:
                # 错误
                print(f"生成失败: {result['error']}")
                break
                
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

    # 查看SQLite记录
    print("\n" + "="*50)
    print("查看SQLite执行记录...")
    try:
        from src.core.base import get_graph_recorder
        recorder = get_graph_recorder()
        
        recent_executions = recorder.get_recent_executions(limit=5)
        if recent_executions:
            print(f"找到 {len(recent_executions)} 条执行记录:")
            for i, execution in enumerate(recent_executions, 1):
                print(f"\n记录 {i}:")
                print(f"  图名字: {execution['graph_name']}")
                print(f"  开始时间: {execution['start_time']}")
                print(f"  持续时间: {execution['duration_seconds']:.2f}秒")
                print(f"  成功: {execution['success']}")
                if execution['error_message']:
                    print(f"  错误: {execution['error_message']}")
        else:
            print("没有找到执行记录")
    except Exception as e:
        print(f"查看记录时发生错误: {e}")

if __name__ == "__main__":
    asyncio.run(test_single_item_generation())