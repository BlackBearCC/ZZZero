"""
笑话生成工作流测试脚本
测试基于方知衡人设的笑话生成功能
"""

import asyncio
import logging
import sys
import os

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from llm.doubao import DoubaoLLM
from workflow.joke_workflow import JokeWorkflow

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('joke_workflow_test.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

class MockWorkflowChat:
    """模拟工作流聊天界面"""
    
    def __init__(self):
        self.current_node = ""
        self.messages = []
    
    async def add_node_message(self, node_name: str, message: str, status: str):
        """添加节点消息"""
        timestamp = asyncio.get_event_loop().time()
        self.messages.append({
            'node': node_name,
            'message': message,
            'status': status,
            'timestamp': timestamp
        })
        print(f"[{node_name}] {status}: {message}")
    
    def _create_workflow_progress(self):
        """创建工作流进度HTML"""
        return "<div>工作流进度模拟</div>"

async def test_joke_workflow():
    """测试笑话生成工作流"""
    print("=== 开始测试笑话生成工作流 ===")
    
    try:
        # 初始化LLM
        llm_config = {
            'api_key': 'b633a622-b5d0-4f16-a8a9-616239cf15d1',  # 需要配置实际的API密钥
            'model': 'ep-20241228203630-nqr7v',
            'base_url': 'https://ark.cn-beijing.volces.com/api/v3'
        }
        
        print("初始化豆包LLM...")
        llm = DoubaoLLM(llm_config)
        
        # 初始化笑话工作流
        print("初始化笑话生成工作流...")
        joke_workflow = JokeWorkflow(llm=llm)
        
        # 配置测试参数
        test_config = {
            'protagonist': '方知衡',
            'batch_size': 10,  # 测试时使用较小的批次
            'total_target': 10,  # 测试时只生成10条笑话
            'joke_categories': [
                '学术幽默', '生活日常', '毒奶体质', '网络落伍'
            ],
            'difficulty_levels': ['简单', '中等', '复杂'],
            'humor_styles': ['冷幽默', '自嘲', '观察式', '反差萌'],
            'pg_config': {
                'host': 'localhost',
                'port': 5432,
                'database': 'jokes_db',
                'user': 'postgres',
                'password': 'password'
            }
        }
        
        # 创建模拟的工作流聊天界面
        mock_chat = MockWorkflowChat()
        
        print("开始执行笑话生成工作流...")
        print(f"配置：{test_config['total_target']}条笑话，每批{test_config['batch_size']}条")
        
        # 执行工作流
        result_count = 0
        async for result in joke_workflow.execute_workflow_stream(test_config, mock_chat):
            result_count += 1
            if result_count % 5 == 0:  # 每5个结果打印一次进度
                print(f"已处理{result_count}个工作流事件...")
        
        print("=== 笑话生成工作流测试完成 ===")
        print(f"总共处理了{result_count}个工作流事件")
        print(f"工作流消息数量：{len(mock_chat.messages)}")
        
        # 打印最后几条消息
        print("\n最后几条工作流消息：")
        for msg in mock_chat.messages[-5:]:
            print(f"  [{msg['node']}] {msg['status']}: {msg['message']}")
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        print(f"❌ 测试失败: {e}")

async def test_database_connection():
    """测试数据库连接"""
    print("\n=== 测试PostgreSQL数据库连接 ===")
    
    try:
        import psycopg2
        
        pg_config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'jokes_db',
            'user': 'postgres',
            'password': 'password'
        }
        
        print("尝试连接PostgreSQL数据库...")
        conn = psycopg2.connect(**pg_config)
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'jokes'
            );
        """)
        
        table_exists = cursor.fetchone()[0]
        print(f"jokes表是否存在: {table_exists}")
        
        if table_exists:
            # 查询现有笑话数量
            cursor.execute("SELECT COUNT(*) FROM jokes;")
            joke_count = cursor.fetchone()[0]
            print(f"数据库中现有笑话数量: {joke_count}")
        
        cursor.close()
        conn.close()
        print("✅ 数据库连接测试成功")
        
    except Exception as e:
        print(f"❌ 数据库连接测试失败: {e}")
        print("请确保PostgreSQL服务正在运行，并且配置了正确的数据库参数")

def test_protagonist_data():
    """测试主角人设数据加载"""
    print("\n=== 测试主角人设数据加载 ===")
    
    try:
        from workflow.joke_workflow import JokeWorkflow
        
        workflow = JokeWorkflow()
        
        if workflow.protagonist_data:
            print(f"✅ 成功加载主角人设，长度: {len(workflow.protagonist_data)} 字符")
            print("人设数据前200字符：")
            print(workflow.protagonist_data[:200] + "...")
        else:
            print("❌ 主角人设数据为空")
            
    except Exception as e:
        print(f"❌ 主角人设数据加载失败: {e}")

if __name__ == "__main__":
    print("开始笑话生成工作流测试...")
    
    # 先测试基础组件
    test_protagonist_data()
    
    # 测试数据库连接（需要PostgreSQL服务运行）
    asyncio.run(test_database_connection())
    
    # 主测试（需要配置LLM API）
    print("\n注意：以下测试需要配置有效的LLM API密钥")
    choice = input("是否继续执行完整工作流测试？(y/n): ")
    
    if choice.lower() == 'y':
        asyncio.run(test_joke_workflow())
    else:
        print("跳过完整工作流测试")
    
    print("\n测试脚本执行完成") 