#!/usr/bin/env python3
"""
简化的笑话工作流测试脚本
不依赖数据库，专注测试笑话生成功能
"""

import asyncio
import json
from pathlib import Path
from src.workflow.joke_workflow import JokeWorkflow
from src.llm.doubao import DoubaoLLM
from core.types import LLMConfig

async def test_joke_generation():
    """测试笑话生成功能"""
    print("🎭 开始测试方知衡笑话生成...")
    
    # 配置LLM
    llm_config = LLMConfig(
        provider="doubao",
        model_name="ep-20241230141654-5tvbr",
        api_key="sk-7a7b5c6d4e8f9a0b1c2d3e4f5g6h7i8j",
        api_base="https://ark.cn-beijing.volces.com/api/v3"
    )
    
    # 初始化LLM
    llm = DoubaoLLM(config=llm_config)
    
    # 初始化工作流
    workflow = JokeWorkflow(llm=llm)
    
    # 测试配置
    test_config = {
        'total_target': 5,  # 只生成5条笑话用于测试
        'batch_size': 5,
        'save_to_database': False,  # 不保存到数据库
        'quality_threshold': 60,
        'joke_categories': [
            '学术幽默', '生活日常', '毒奶体质', '网络落伍', 
            '古板认真', '温和吐槽', '理性分析', '意外反差'
        ]
    }
    
    print(f"📊 测试配置: {test_config}")
    
    # 执行工作流
    try:
        print("\n🚀 开始执行笑话生成工作流...")
        
        # 创建工作流图
        graph = await workflow.create_joke_graph()
        
        # 编译图
        compiled_graph = graph.compile()
        
        # 准备输入数据（使用工作流的标准格式）
        input_data = {
            'protagonist_data': workflow.protagonist_data,
            'config': test_config,
            'protagonist': test_config.get('protagonist', '方知衡'),
            'batch_size': test_config.get('batch_size', 5),
            'total_target': test_config.get('total_target', 5),
            'joke_categories': test_config.get('joke_categories', []),
            'difficulty_levels': test_config.get('difficulty_levels', ['简单', '中等', '复杂']),
            'humor_styles': test_config.get('humor_styles', ['冷幽默', '自嘲', '观察式', '反差萌']),
            'pg_config': test_config.get('pg_config', {}),
            'workflow_chat': None,  # 简化测试不使用聊天界面
            'llm': llm
        }
        
        # 执行工作流
        final_result = None
        async for result in compiled_graph.stream(input_data):
            if result:
                final_result = result
                # 显示进度
                node_name = result.get('current_node', 'unknown')
                print(f"📍 当前节点: {node_name}")
        
        # 分析结果
        if final_result:
            print("\n✅ 工作流执行完成!")
            
            # 检查生成的笑话
            generated_jokes = final_result.get('generated_jokes', [])
            print(f"📝 生成笑话数量: {len(generated_jokes)}")
            
            if generated_jokes:
                print("\n🎭 生成的笑话示例:")
                for i, joke in enumerate(generated_jokes[:3], 1):  # 显示前3条
                    print(f"\n--- 笑话 {i} ---")
                    print(f"ID: {joke.get('joke_id', 'N/A')}")
                    print(f"类型: {joke.get('humor_style', 'N/A')}")
                    print(f"情境: {joke.get('setup', 'N/A')}")
                    print(f"笑话: {joke.get('punchline', 'N/A')}")
                    print(f"人设特征: {joke.get('character_traits', [])}")
                    
                    # 验证是否符合要求
                    punchline = joke.get('punchline', '')
                    if '我' in punchline or '我的' in punchline:
                        print("✅ 符合第一人称视角")
                    else:
                        print("⚠️ 缺少第一人称视角")
            
            # 检查质量分数
            quality_scores = final_result.get('quality_scores', [])
            if quality_scores:
                avg_score = sum(quality_scores) / len(quality_scores)
                print(f"\n📊 平均质量分数: {avg_score:.1f}")
                print(f"📊 质量分数范围: {min(quality_scores):.1f} - {max(quality_scores):.1f}")
            
            # 保存测试结果
            test_output_file = Path("workspace/test_joke_output.json")
            test_output_file.parent.mkdir(exist_ok=True)
            
            with open(test_output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'config': test_config,
                    'generated_jokes': generated_jokes,
                    'quality_scores': quality_scores,
                    'total_jokes': len(generated_jokes)
                }, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 测试结果已保存到: {test_output_file}")
            
        else:
            print("❌ 工作流执行失败，没有返回结果")
            
    except Exception as e:
        print(f"❌ 测试执行失败: {e}")
        import traceback
        traceback.print_exc()

async def analyze_joke_style():
    """分析生成的笑话风格是否符合要求"""
    print("\n🔍 分析笑话风格...")
    
    test_output_file = Path("workspace/test_joke_output.json")
    if not test_output_file.exists():
        print("❌ 没有找到测试结果文件")
        return
    
    with open(test_output_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    jokes = data.get('generated_jokes', [])
    if not jokes:
        print("❌ 没有找到生成的笑话")
        return
    
    print(f"📊 分析 {len(jokes)} 条笑话...")
    
    # 分析指标
    first_person_count = 0
    academic_style_count = 0
    self_deprecating_count = 0
    mild_humor_count = 0
    
    for joke in jokes:
        punchline = joke.get('punchline', '')
        setup = joke.get('setup', '')
        
        # 检查第一人称
        if '我' in punchline or '我的' in punchline:
            first_person_count += 1
        
        # 检查学术风格
        academic_keywords = ['根据', '定律', '理论', '分析', '研究', '发现', '实验']
        if any(keyword in punchline for keyword in academic_keywords):
            academic_style_count += 1
        
        # 检查自嘲风格
        self_keywords = ['我的', '我又', '我都', '我总是', '我发现我']
        if any(keyword in punchline for keyword in self_keywords):
            self_deprecating_count += 1
        
        # 检查温和幽默
        mild_keywords = ['看来', '似乎', '可能', '应该', '大概', '或许']
        if any(keyword in punchline for keyword in mild_keywords):
            mild_humor_count += 1
    
    # 输出分析结果
    print(f"\n📈 风格分析结果:")
    print(f"✅ 第一人称视角: {first_person_count}/{len(jokes)} ({first_person_count/len(jokes)*100:.1f}%)")
    print(f"🎓 学术风格: {academic_style_count}/{len(jokes)} ({academic_style_count/len(jokes)*100:.1f}%)")
    print(f"😅 自嘲风格: {self_deprecating_count}/{len(jokes)} ({self_deprecating_count/len(jokes)*100:.1f}%)")
    print(f"😊 温和幽默: {mild_humor_count}/{len(jokes)} ({mild_humor_count/len(jokes)*100:.1f}%)")
    
    # 判断是否符合要求
    if first_person_count >= len(jokes) * 0.8:
        print("✅ 第一人称视角符合要求")
    else:
        print("⚠️ 第一人称视角需要改进")

if __name__ == "__main__":
    print("🎭 方知衡笑话生成测试")
    print("=" * 50)
    
    # 运行测试
    asyncio.run(test_joke_generation())
    
    # 分析结果
    asyncio.run(analyze_joke_style())
    
    print("\n🎉 测试完成!") 