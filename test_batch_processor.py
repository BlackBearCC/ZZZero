#!/usr/bin/env python3
"""
系统级批处理器测试脚本
"""
import asyncio
import sys
import os
import csv
from pathlib import Path

# 添加src路径
current_dir = Path(__file__).parent
src_path = current_dir / "src"
sys.path.insert(0, str(src_path))

from core.batch_processor import BatchProcessor
from tools.mcp_tools import MCPToolManager


async def create_test_csv():
    """创建测试用的CSV文件"""
    csv_file = "test_characters.csv"
    
    test_data = [
        {
            "character_name": "张三",
            "description": "古代书生，性格温和，喜欢读书写字",
            "duration_days": "7",
            "special_requirements": "需要包含科举考试准备"
        },
        {
            "character_name": "李四",
            "description": "现代程序员，工作忙碌，热爱技术",
            "duration_days": "5",
            "special_requirements": "工作日程要包含编程项目"
        },
        {
            "character_name": "王五",
            "description": "中世纪骑士，勇敢正直，保护领土",
            "duration_days": "10", 
            "special_requirements": "要有训练和巡逻任务"
        }
    ]
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=test_data[0].keys())
        writer.writeheader()
        writer.writerows(test_data)
    
    print(f"✅ 创建测试CSV文件: {csv_file}")
    return csv_file


async def test_batch_processor():
    """测试批处理器功能"""
    print("🚀 开始测试系统级批处理器...")
    
    # 创建测试CSV
    csv_file = await create_test_csv()
    
    try:
        # 创建MCP工具管理器
        mcp_manager = MCPToolManager()
        await mcp_manager.initialize()
        
        # 模拟LLM调用器（这里简化处理）
        class MockLLMCaller:
            async def call_llm(self, prompt, max_tokens=1000, temperature=0.3):
                # 模拟LLM返回批处理指令
                return True, '''
                {
                    "task_type": "schedule_generation",
                    "batch_description": "为每个角色生成个性化的日程安排",
                    "per_row_template": "为角色{character_name}（{description}）生成{duration_days}天的日程，特殊要求：{special_requirements}",
                    "expected_output": "详细的角色日程安排"
                }
                '''
        
        # 创建批处理器
        llm_caller = MockLLMCaller()
        batch_processor = BatchProcessor(llm_caller=llm_caller, mcp_tool_manager=mcp_manager)
        
        # 测试1: 配置批处理模式
        print("\n📋 测试1: 配置批处理模式")
        config_result = batch_processor.configure_batch_mode(
            enabled=True,
            csv_file_path=csv_file,
            batch_size=2,
            concurrent_tasks=2
        )
        print(f"配置结果: {config_result}")
        
        # 测试2: 检查批处理状态
        print("\n📊 测试2: 检查批处理状态")
        status = batch_processor.get_batch_status()
        print(f"批处理状态: {status}")
        
        # 测试3: 执行批处理任务
        print("\n⚡ 测试3: 执行批处理任务")
        user_message = "帮我为这些角色生成详细的日程安排"
        
        result = await batch_processor.process_batch_request(user_message)
        
        print(f"批处理结果成功: {result.get('success')}")
        
        if result.get('success'):
            summary = result.get('execution_summary', {})
            print(f"✅ 执行摘要:")
            print(f"   - 任务类型: {summary.get('task_type')}")
            print(f"   - 总任务数: {summary.get('total_tasks')}")
            print(f"   - 成功任务: {summary.get('successful_tasks')}")
            print(f"   - 失败任务: {summary.get('failed_tasks')}")
            print(f"   - 成功率: {summary.get('success_rate')}")
            print(f"   - 总执行时间: {summary.get('total_execution_time')}")
            
            # 显示部分详细结果
            detailed_results = result.get('detailed_results', [])
            print(f"\n📝 详细结果示例:")
            for i, task_result in enumerate(detailed_results[:2]):  # 只显示前2个
                print(f"   任务{i+1}: {task_result.get('task_prompt', '')[:50]}...")
                if task_result.get('success'):
                    print(f"   结果: {task_result.get('result', '')[:100]}...")
                else:
                    print(f"   错误: {task_result.get('error', '')}")
        else:
            print(f"❌ 批处理失败: {result.get('message')}")
        
        # 测试4: 关闭批处理模式
        print("\n🔄 测试4: 关闭批处理模式")
        close_result = batch_processor.configure_batch_mode(enabled=False)
        print(f"关闭结果: {close_result}")
        
        # 清理资源
        await mcp_manager.cleanup()
        
    finally:
        # 清理测试文件
        if os.path.exists(csv_file):
            os.remove(csv_file)
            print(f"🗑️ 清理测试文件: {csv_file}")


def main():
    """主函数"""
    print("🔧 系统级批处理器测试")
    
    # 检查环境
    llm_provider = os.getenv("LLM_PROVIDER", "doubao")
    api_key = os.getenv("ARK_API_KEY") or os.getenv("DOUBAO_API_KEY")
    print(f"🤖 LLM提供商: {llm_provider}")
    print(f"🔑 API密钥: {'已设置' if api_key else '未设置'}")
    
    # 设置Windows异步事件循环策略
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # 运行测试
    asyncio.run(test_batch_processor())
    
    print("\n🎉 批处理器测试完成！")


if __name__ == "__main__":
    main() 