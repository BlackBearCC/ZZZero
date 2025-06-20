#!/usr/bin/env python3
"""
测试角色扮演数据生成服务
"""
import asyncio
import sys
import os
from pathlib import Path

# 添加src路径
current_dir = Path(__file__).parent
src_path = current_dir / "src"
sys.path.insert(0, str(src_path))

from tools.mcp_tools import MCPToolManager


async def test_roleplay_tools():
    """测试角色扮演数据生成工具"""
    print("=== 角色扮演数据生成服务测试 ===")
    
    # 创建工具管理器
    tool_manager = MCPToolManager()
    
    # 初始化
    await tool_manager.initialize()
    
    # 检查服务器状态
    status = tool_manager.get_servers_status()
    print("\n🔧 服务器状态:")
    for server_id, info in status.items():
        print(f"  {server_id}: {'✅运行中' if info['running'] else '❌未运行'} ({info['name']})")
        if info['running']:
            print(f"    工具数量: {info['enabled_tools']}/{info['total_tools']}")
    
    # 列出可用工具
    tools = tool_manager.list_tools()
    print(f"\n🛠️ 可用工具 ({len(tools)} 个):")
    for tool in tools:
        if "roleplay" in tool:
            print(f"  ✅ {tool}")
        else:
            print(f"  - {tool}")
    
    print("\n" + "="*50)
    
    # 测试1: 获取时间阶段信息
    print("📅 测试1: 获取5阶段时间规划信息")
    try:
        result = await tool_manager.call_tool("roleplay_get_time_phases", {})
        if result.success:
            print("✅ 成功获取时间阶段信息")
            # 打印阶段信息
            if isinstance(result.result, dict) and "phases" in result.result:
                for phase in result.result["phases"]:
                    print(f"   {phase['name']}: {phase['time_range']}")
            else:
                print(f"   结果: {result.result}")
        else:
            print(f"❌ 失败: {result.error}")
    except Exception as e:
        print(f"❌ 异常: {e}")
    
    print("\n" + "="*50)
    
    # 测试2: 生成基础日程计划
    print("📝 测试2: 生成工作日程计划框架")
    try:
        result = await tool_manager.call_tool("roleplay_generate_schedule_plan", {
            "requirements": "明天需要安排项目开发、团队会议和代码评审，希望合理分配时间"
        })
        if result.success:
            print("✅ 成功生成工作日程计划")
            print("📋 计划内容预览:")
            content = result.result if isinstance(result.result, str) else str(result.result)
            # 只显示前500个字符
            preview = content[:500] + "..." if len(content) > 500 else content
            print(f"   {preview}")
            
            # 保存完整计划用于下一步测试
            global plan_framework
            plan_framework = content
        else:
            print(f"❌ 失败: {result.error}")
    except Exception as e:
        print(f"❌ 异常: {e}")
    
    print("\n" + "="*50)
    
    # 测试3: 生成详细5阶段日程（如果第2步成功）
    if 'plan_framework' in globals():
        print("🕐 测试3: 生成详细5阶段日程")
        try:
            result = await tool_manager.call_tool("roleplay_generate_detailed_schedule", {
                "plan_framework": plan_framework,
                "requirements": "需要在下午安排客户演示，请重点优化下午时间段"
            })
            if result.success:
                print("✅ 成功生成详细5阶段日程")
                print("🕐 详细日程预览:")
                content = result.result if isinstance(result.result, str) else str(result.result)
                # 只显示前800个字符
                preview = content[:800] + "..." if len(content) > 800 else content
                print(f"   {preview}")
            else:
                print(f"❌ 失败: {result.error}")
        except Exception as e:
            print(f"❌ 异常: {e}")
    else:
        print("⏭️ 跳过测试3: 上一步计划生成失败")
    
    print("\n" + "="*50)
    
    # 测试4: 获取生成历史
    print("📚 测试4: 获取生成历史")
    try:
        result = await tool_manager.call_tool("roleplay_get_generation_history", {
            "limit": 5
        })
        if result.success:
            print("✅ 成功获取生成历史")
            if isinstance(result.result, dict) and "history" in result.result:
                history = result.result["history"]
                print(f"   历史记录数量: {len(history)}")
                for i, record in enumerate(history, 1):
                    print(f"   {i}. {record['type']} - {'✅成功' if record['success'] else '❌失败'} ({record['generated_at']})")
            else:
                print(f"   结果: {result.result}")
        else:
            print(f"❌ 失败: {result.error}")
    except Exception as e:
        print(f"❌ 异常: {e}")
    
    print("\n" + "="*50)
    
    # 清理
    await tool_manager.cleanup()
    print("🧹 测试完成，已清理资源")


async def test_simple_plan():
    """简单的计划生成测试"""
    print("\n=== 简单日程计划测试 ===")
    
    tool_manager = MCPToolManager()
    await tool_manager.initialize()
    
    # 测试学习计划生成
    print("📚 生成学习计划...")
    try:
        result = await tool_manager.call_tool("roleplay_generate_schedule_plan", {
            "requirements": "准备考试，需要复习数学、英语和计算机科学，每天8小时学习时间"
        })
        if result.success:
            print("✅ 学习计划生成成功")
            content = result.result if isinstance(result.result, str) else str(result.result)
            print(f"📝 计划内容:\n{content}")
        else:
            print(f"❌ 失败: {result.error}")
    except Exception as e:
        print(f"❌ 异常: {e}")
    
    await tool_manager.cleanup()


def main():
    """主函数"""
    print("🚀 开始测试角色扮演数据生成服务...")
    
    # 检查环境变量
    llm_provider = os.getenv("LLM_PROVIDER", "doubao")
    print(f"🤖 当前LLM提供商: {llm_provider}")
    
    if llm_provider == "doubao":
        api_key = os.getenv("ARK_API_KEY") or os.getenv("DOUBAO_API_KEY")
        if not api_key:
            print("⚠️  警告: 未设置豆包API密钥 (ARK_API_KEY 或 DOUBAO_API_KEY)")
            print("   某些测试可能会失败，但服务器启动测试仍会进行")
        else:
            print("✅ 豆包API密钥已配置")
    elif llm_provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            print("⚠️  警告: 未设置OPENAI_API_KEY环境变量")
            print("   某些测试可能会失败，但服务器启动测试仍会进行")
        else:
            print("✅ OpenAI API密钥已配置")
    else:
        print(f"⚠️  未知的LLM提供商: {llm_provider}")
    
    # 设置Windows异步事件循环策略
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # 运行测试
    asyncio.run(test_roleplay_tools())
    print("\n" + "="*60)
    asyncio.run(test_simple_plan())
    
    print("\n🎉 所有测试完成！")


if __name__ == "__main__":
    main() 