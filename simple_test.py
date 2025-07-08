# -*- coding: utf-8 -*-
"""
简单测试ReactAgent结构
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from agents.react_agent import ReactAgent, ReactLoop, NodeInfoStream

def test_react_loop():
    """测试React循环结构"""
    print("=== 测试ReactLoop结构 ===")
    
    # 创建React循环
    loop = ReactLoop(max_iterations=3)
    
    # 模拟循环过程
    loop.add_thought("我需要分析这个问题")
    loop.add_action({"tool_name": "calculator", "parameters": {"expression": "123+456"}})
    loop.add_observation("计算结果是579")
    
    loop.next_iteration()
    
    loop.add_thought("现在我有了答案，可以给出解释")
    loop.complete("123 + 456 = 579。这是一个简单的加法运算。")
    
    print(f"循环完成状态: {loop.is_complete}")
    print(f"最终答案: {loop.final_answer}")
    print(f"思考次数: {len(loop.thoughts)}")
    print(f"行动次数: {len(loop.actions)}")
    print(f"观察次数: {len(loop.observations)}")
    
def test_info_stream():
    """测试信息流"""
    print("\n=== 测试NodeInfoStream ===")
    
    # 创建信息流
    info_stream = NodeInfoStream()
    
    # 添加事件回调
    def print_event(event):
        print(f"[事件] {event['type']} | {event['node_name']}: {event['content']}")
    
    info_stream.add_callback(print_event)
    
    # 发射事件
    info_stream.emit("agent_start", "react_agent", "开始处理任务")
    info_stream.emit("thought", "thought_node", "正在分析问题...")
    info_stream.emit("action", "action_node", "执行工具调用")
    info_stream.emit("observation", "observation_node", "获得结果")
    info_stream.emit("final_answer", "react_agent", "任务完成")
    
    print(f"\n总共记录了 {len(info_stream.get_events())} 个事件")

def test_react_prompt():
    """测试React提示词生成"""
    print("\n=== 测试React提示词 ===")
    
    # 创建一个虚拟的ReactAgent来测试提示词
    class MockReactAgent(ReactAgent):
        def __init__(self):
            self.tool_manager = None
    
    agent = MockReactAgent()
    
    # 生成提示词
    prompt = agent._build_react_prompt(
        query="计算123+456", 
        available_tools=["calculator", "search"],
        context_history="Thought: 我需要进行计算\nAction: calculator(expression=100+50)\nObservation: 结果是150\n"
    )
    
    print("生成的React提示词:")
    print("-" * 50)
    print(prompt)
    print("-" * 50)

if __name__ == "__main__":
    try:
        test_react_loop()
        test_info_stream() 
        test_react_prompt()
        print("\n✅ 所有测试通过！ReactAgent结构正常")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()