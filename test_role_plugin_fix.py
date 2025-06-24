#!/usr/bin/env python3
"""
测试角色插件在流式ReAct Agent中的自动注入功能
"""
import asyncio
import os
import sys

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.plugins import get_role_plugin_manager
from src.tools.mcp_tools import MCPToolManager
from src.agents.react_agent import ReactAgent
from src.llm.base import LLMFactory
from src.core.types import LLMConfig

async def test_role_plugin_injection():
    """测试角色插件自动注入功能"""
    print("🎭 开始测试角色插件在流式ReAct Agent中的自动注入...")
    
    # 1. 配置角色插件
    print("\n📝 配置角色插件...")
    plugin_manager = get_role_plugin_manager("./workspace")
    
    # 配置角色资料
    role_profile = """角色名称：艾莉丝·薇拉诺瓦

基本信息：
- 年龄：25岁
- 职业：独立艺术家和咖啡店店主
- 性格：温柔、创意十足、细心周到
- 爱好：绘画、阅读、园艺、烘焙

背景故事：
艾莉丝是一位充满创意的年轻女性，在市中心经营着一家名为"月光画廊"的艺术咖啡店。
她将自己的绘画作品展示在咖啡店里，同时为顾客提供手工制作的咖啡和甜点。
艾莉丝热爱生活中的美好细节，总是能在平凡的日常中发现灵感。

性格特点：
- 对艺术充满热情，善于从生活中汲取创作灵感
- 性格温和友善，善于倾听他人的想法
- 注重细节，追求完美的生活品质
- 喜欢通过艺术和美食与他人建立连接"""
    
    plugin_manager.configure_profile(
        name="艾莉丝·薇拉诺瓦",
        content=role_profile,
        tags=["艺术家", "咖啡店主", "温柔", "创意"],
        enabled=True
    )
    
    # 创建测试知识库
    print("\n📚 创建测试知识库...")
    kb_content = """艾莉丝的绘画技巧包括水彩画、油画和素描，她特别擅长风景画和静物画。

艾莉丝的咖啡制作技能包括手冲咖啡、意式浓缩咖啡和拿铁艺术，她使用来自埃塞俄比亚和哥伦比亚的精品咖啡豆。

艾莉丝的园艺知识涵盖室内植物养护、花卉搭配和香草种植，她在咖啡店里种植了薄荷、迷迭香和罗勒等香草。

艾莉丝的烘焙技能包括制作司康饼、马卡龙和提拉米苏，她的招牌甜点是薰衣草蜂蜜司康饼。"""
    
    kb_file_path = "./workspace/alice_knowledge.txt"
    with open(kb_file_path, 'w', encoding='utf-8') as f:
        f.write(kb_content)
    
    plugin_manager.configure_knowledge_base(
        name="艾莉丝专属知识库",
        source_file=kb_file_path,
        description="包含艾莉丝的艺术技巧、咖啡制作、园艺知识和烘焙技能",
        search_limit=3,
        enabled=True
    )
    
    # 检查插件状态
    status = plugin_manager.get_status()
    print(f"✅ 角色资料插件状态: {status['profile_plugin']['enabled']} (可用: {status['profile_plugin']['available']})")
    print(f"✅ 知识库插件状态: {status['knowledge_base_plugin']['enabled']} (可用: {status['knowledge_base_plugin']['available']})")
    
    # 2. 创建MCPToolManager
    print("\n🔧 创建MCP工具管理器...")
    tool_manager = MCPToolManager()
    await tool_manager.initialize()
    
    # 启用角色扮演服务器
    tool_manager.set_enabled_servers(["roleplay"])
    
    # 检查权限
    has_permission = tool_manager.has_role_plugin_permission("roleplay")
    print(f"✅ 角色扮演服务器插件权限: {has_permission}")
    
    # 3. 创建LLM（如果有API密钥）
    print("\n🧠 创建LLM...")
    try:
        llm_config = LLMConfig(
            provider="doubao",
            model_name="ep-20250221154410-vh78x",
            temperature=0.7
        )
        llm = LLMFactory.create(llm_config)
        await llm.initialize()
        print("✅ LLM初始化成功")
    except Exception as e:
        print(f"⚠️ LLM初始化失败: {e}")
        print("⚠️ 将跳过实际Agent测试，仅测试参数注入逻辑")
        
        # 仅测试参数注入逻辑
        print("\n🧪 测试参数注入逻辑...")
        test_args = {
            "requirements": "生成一个关于绘画创作和咖啡制作的日程安排"
        }
        
        enhanced_args = await tool_manager.inject_role_context_to_arguments(
            "roleplay", "generate_schedule_plan", test_args
        )
        
        print(f"原始参数: {test_args}")
        print(f"增强参数包含角色描述: {'character_description' in enhanced_args}")
        if 'character_description' in enhanced_args:
            print(f"角色描述长度: {len(enhanced_args['character_description'])} 字符")
            print(f"角色描述开头: {enhanced_args['character_description'][:100]}...")
        
        print(f"需求参数是否增强: {len(enhanced_args.get('requirements', '')) > len(test_args.get('requirements', ''))}")
        if len(enhanced_args.get('requirements', '')) > len(test_args.get('requirements', '')):
            print("✅ 知识库内容已自动注入到需求参数中")
        
        return
    
    # 4. 创建ReactAgent
    print("\n🤖 创建ReactAgent...")
    agent = ReactAgent(
        llm=llm,
        tool_manager=tool_manager,
        max_iterations=3,
        memory_enabled=False  # 简化测试
    )
    
    # 5. 测试流式执行
    print("\n🚀 测试流式ReAct Agent...")
    query = "请帮我生成明天的日程安排，我想要安排一些绘画创作和咖啡制作的活动"
    
    print(f"查询: {query}")
    print("\n流式输出:")
    print("-" * 50)
    
    try:
        async for chunk in agent.stream_run(query):
            chunk_type = chunk.get("type", "unknown")
            content = chunk.get("content", "")
            
            if chunk_type == "text_chunk":
                print(content, end="", flush=True)
            elif chunk_type == "tool_result":
                print(f"\n[工具结果] {content}")
            elif chunk_type == "final_result":
                print(f"\n[最终结果] {content}")
            elif chunk_type == "error":
                print(f"\n[错误] {content}")
        
        print("\n" + "-" * 50)
        print("✅ 流式测试完成")
        
    except Exception as e:
        print(f"\n❌ 流式测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 6. 清理
    print("\n🧹 清理资源...")
    await agent.cleanup()
    await tool_manager.cleanup()
    
    print("\n✨ 测试完成！")

if __name__ == "__main__":
    asyncio.run(test_role_plugin_injection()) 