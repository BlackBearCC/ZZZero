#!/usr/bin/env python3
"""
简化的角色扮演数据生成服务测试
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


async def test_simple_calls():
    """测试简单的工具调用"""
    print("=== 简化角色扮演服务测试 ===")
    
    # 创建工具管理器
    tool_manager = MCPToolManager()
    
    # 初始化
    await tool_manager.initialize()
    
    # 测试1: 获取时间阶段（不需要LLM）
    print("\n📅 测试1: 获取5阶段时间规划信息")
    try:
        result = await tool_manager.call_tool("roleplay_get_time_phases", {})
        if result.success:
            print("✅ 成功")
            phases = result.result.get("phases", [])
            for phase in phases[:3]:  # 只显示前3个
                print(f"   {phase['name']}: {phase['time_range']}")
        else:
            print(f"❌ 失败: {result.error}")
    except Exception as e:
        print(f"❌ 异常: {e}")
    
    # 测试2: 非常简单的计划生成
    print("\n📝 测试2: 生成简单计划")
    try:
        result = await tool_manager.call_tool("roleplay_generate_schedule_plan", {
            "requirements": "简单一天安排"
        })
        if result.success:
            print("✅ 计划生成成功")
            content = str(result.result)
            # 只显示前200个字符
            preview = content[:200] + "..." if len(content) > 200 else content
            print(f"📋 内容: {preview}")
        else:
            print(f"❌ 计划生成失败: {result.error}")
    except Exception as e:
        print(f"❌ 异常: {e}")
    
    # 清理
    await tool_manager.cleanup()
    print("\n🧹 测试完成")


def main():
    """主函数"""
    print("🚀 开始简化测试...")
    
    # 检查环境
    llm_provider = os.getenv("LLM_PROVIDER", "doubao")
    api_key = os.getenv("ARK_API_KEY") or os.getenv("DOUBAO_API_KEY")
    print(f"🤖 LLM提供商: {llm_provider}")
    print(f"🔑 API密钥: {'已设置' if api_key else '未设置'}")
    
    # 设置Windows异步事件循环策略
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # 运行测试
    asyncio.run(test_simple_calls())
    
    print("\n🎉 简化测试完成！")


if __name__ == "__main__":
    main() 