"""
快速启动示例 - 展示框架的基本用法
"""
import asyncio
import os
from src.agents import ReactAgent
from src.llm import create_llm_provider
from src.tools import MCPToolManager


async def basic_example():
    """基础示例 - 使用ReactAgent回答问题"""
    print("=== 基础ReactAgent示例 ===")
    
    # 设置API密钥（如果还没设置）
    if not os.getenv("ARK_API_KEY"):
        print("请设置ARK_API_KEY环境变量")
        return
    
    # 创建LLM提供者
    llm = create_llm_provider("doubao", model_name="ep-20241118192716-rrhxs")
    
    # 创建工具管理器
    tool_manager = MCPToolManager()
    await tool_manager.initialize()
    
    # 创建ReactAgent
    agent = ReactAgent(llm=llm, tool_manager=tool_manager)
    
    # 执行查询
    query = "计算 123 * 456 的结果，并告诉我这个数字有什么特殊含义"
    print(f"\n查询: {query}")
    
    result = await agent.run(query)
    
    print(f"\n回答: {result.result}")
    print(f"\n执行步骤数: {len(result.execution_trace)}")
    print(f"总耗时: {result.metrics.get('total_duration', 0):.2f}秒")


async def tool_example():
    """工具使用示例"""
    print("\n\n=== 工具使用示例 ===")
    
    # 创建LLM和工具管理器
    llm = create_llm_provider("doubao")
    tool_manager = MCPToolManager()
    await tool_manager.initialize()
    
    # 列出可用工具
    print("\n可用工具:")
    for tool_name, tool in tool_manager.tools.items():
        print(f"- {tool_name}: {tool.description}")
    
    # 创建Agent并执行需要工具的任务
    agent = ReactAgent(llm=llm, tool_manager=tool_manager)
    
    queries = [
        "搜索一下Python装饰器的最佳实践",
        "计算斐波那契数列的第20项",
        "读取并分析README.md文件的内容"
    ]
    
    for query in queries:
        print(f"\n查询: {query}")
        try:
            result = await agent.run(query)
            print(f"回答: {result.result[:200]}..." if len(result.result) > 200 else f"回答: {result.result}")
        except Exception as e:
            print(f"错误: {e}")


async def batch_example():
    """批量处理示例"""
    print("\n\n=== 批量处理示例 ===")
    
    # 创建Agent
    llm = create_llm_provider("doubao")
    tool_manager = MCPToolManager()
    await tool_manager.initialize()
    agent = ReactAgent(llm=llm, tool_manager=tool_manager)
    
    # 批量任务
    tasks = [
        "Python中的列表推导式是什么？",
        "解释一下JavaScript的闭包",
        "Go语言的goroutine是如何工作的？"
    ]
    
    print(f"\n批量处理 {len(tasks)} 个任务...")
    
    # 并行执行
    async def process_task(task):
        result = await agent.run(task)
        return task, result.result
    
    results = await asyncio.gather(*[process_task(task) for task in tasks])
    
    for task, answer in results:
        print(f"\n问题: {task}")
        print(f"答案: {answer[:100]}...")


async def main():
    """运行所有示例"""
    # 设置环境变量
    os.environ["ARK_BASE_URL"] = "https://ark.cn-beijing.volces.com/api/v3"
    
    # 运行基础示例
    await basic_example()
    
    # 运行工具示例
    await tool_example()
    
    # 运行批量示例
    await batch_example()
    
    print("\n\n=== 示例完成 ===")
    print("\n要启动Web界面，请运行: python main.py")


if __name__ == "__main__":
    # 检查API密钥
    if not os.getenv("ARK_API_KEY"):
        print("请先设置ARK_API_KEY环境变量:")
        print("export ARK_API_KEY=your_api_key")
        print("或在.env文件中设置")
    else:
        asyncio.run(main()) 