#!/usr/bin/env python3
"""
高级MCP服务器测试脚本
测试CSV CRUD和ChromaDB CRUD服务器的功能
"""
import asyncio
import json
import pandas as pd
import os
import sys
from pathlib import Path
from typing import Dict, Any, List
import logging

# 添加路径以便导入服务器
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

logger = logging.getLogger(__name__)


class ServerTester:
    """服务器测试器"""
    
    def __init__(self):
        """初始化测试器"""
        self.test_results = []
    
    def log_test(self, test_name: str, success: bool, message: str = "", details: Dict[str, Any] = None):
        """记录测试结果"""
        result = {
            'test_name': test_name,
            'success': success,
            'message': message,
            'details': details or {}
        }
        self.test_results.append(result)
        
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status} {test_name}: {message}")
        
        if details and not success:
            print(f"   详情: {details}")
    
    async def test_csv_server(self):
        """测试CSV服务器"""
        print("\n=== 测试CSV CRUD服务器 ===")
        
        try:
            from csv_crud_server import CSVCRUDServer
            
            # 初始化服务器
            server = CSVCRUDServer("./test_csv_data")
            self.log_test("CSV服务器初始化", True, "成功创建服务器实例")
            
            # 测试创建表
            try:
                result = server.db.create_table(
                    "test_users", 
                    ["id", "name", "email", "age"],
                    [
                        {"id": 1, "name": "张三", "email": "zhang@test.com", "age": 25},
                        {"id": 2, "name": "李四", "email": "li@test.com", "age": 30}
                    ]
                )
                self.log_test("创建表", True, f"成功创建表，包含{result['rows_created']}行数据")
            except Exception as e:
                self.log_test("创建表", False, str(e))
            
            # 测试插入记录
            try:
                result = server.db.insert_records(
                    "test_users",
                    [
                        {"id": 3, "name": "王五", "email": "wang@test.com", "age": 28},
                        {"id": 4, "name": "赵六", "email": "zhao@test.com", "age": 35}
                    ]
                )
                self.log_test("插入记录", True, f"成功插入{result['records_inserted']}条记录")
            except Exception as e:
                self.log_test("插入记录", False, str(e))
            
            # 测试查询记录
            try:
                result = server.db.query_records(
                    "test_users",
                    where={"age": {"$gt": 25}},
                    limit=10
                )
                self.log_test("查询记录", True, f"查询到{result['returned_count']}条记录")
            except Exception as e:
                self.log_test("查询记录", False, str(e))
            
            # 测试更新记录
            try:
                result = server.db.update_records(
                    "test_users",
                    where={"id": 1},
                    updates={"age": 26, "email": "zhang_new@test.com"}
                )
                self.log_test("更新记录", True, f"成功更新{result['records_updated']}条记录")
            except Exception as e:
                self.log_test("更新记录", False, str(e))
            
            # 测试删除记录
            try:
                result = server.db.delete_records(
                    "test_users",
                    where={"id": 4}
                )
                self.log_test("删除记录", True, f"成功删除{result['records_deleted']}条记录")
            except Exception as e:
                self.log_test("删除记录", False, str(e))
            
            # 测试获取表信息
            try:
                result = server.db.get_table_info("test_users")
                self.log_test("获取表信息", True, f"表有{result['rows']}行，{len(result['columns'])}列")
            except Exception as e:
                self.log_test("获取表信息", False, str(e))
            
            # 测试列出表
            try:
                result = server.db.list_tables()
                self.log_test("列出表", True, f"找到{len(result)}个表")
            except Exception as e:
                self.log_test("列出表", False, str(e))
            
        except ImportError as e:
            self.log_test("CSV服务器导入", False, f"导入失败: {e}")
        except Exception as e:
            self.log_test("CSV服务器", False, f"未知错误: {e}")
    
    async def test_chromadb_server(self):
        """测试ChromaDB服务器"""
        print("\n=== 测试ChromaDB CRUD服务器 ===")
        
        try:
            from chromadb_crud_server import ChromaDBCRUDServer
            
            # 初始化服务器
            server = ChromaDBCRUDServer("./test_chroma_data")
            self.log_test("ChromaDB服务器初始化", True, "成功创建服务器实例")
            
            # 测试创建集合
            try:
                result = server.db.create_collection(
                    "test_documents",
                    embedding_function="default",
                    metadata={"description": "测试文档集合"}
                )
                self.log_test("创建集合", True, f"成功创建集合: {result['collection_name']}")
            except Exception as e:
                self.log_test("创建集合", False, str(e))
            
            # 测试添加文档
            try:
                result = server.db.add_documents(
                    "test_documents",
                    documents=[
                        "Python是一种高级编程语言",
                        "机器学习是人工智能的一个分支",
                        "自然语言处理用于理解文本",
                        "深度学习使用神经网络"
                    ],
                    metadatas=[
                        {"category": "programming", "language": "zh"},
                        {"category": "ai", "language": "zh"},
                        {"category": "nlp", "language": "zh"},
                        {"category": "dl", "language": "zh"}
                    ]
                )
                self.log_test("添加文档", True, f"成功添加{result['documents_added']}个文档")
            except Exception as e:
                self.log_test("添加文档", False, str(e))
            
            # 测试查询文档
            try:
                result = server.db.query_documents(
                    "test_documents",
                    query_texts=["什么是编程语言"],
                    n_results=2
                )
                returned_count = len(result['results']['ids'][0]) if result['results']['ids'] else 0
                self.log_test("查询文档", True, f"查询到{returned_count}个相似文档")
            except Exception as e:
                self.log_test("查询文档", False, str(e))
            
            # 测试获取文档
            try:
                result = server.db.get_documents(
                    "test_documents",
                    where={"category": "ai"},
                    limit=5
                )
                self.log_test("获取文档", True, f"获取到{result['returned_count']}个文档")
            except Exception as e:
                self.log_test("获取文档", False, str(e))
            
            # 测试集合信息
            try:
                result = server.db.get_collection_info("test_documents")
                self.log_test("获取集合信息", True, f"集合包含{result['document_count']}个文档")
            except Exception as e:
                self.log_test("获取集合信息", False, str(e))
            
            # 测试列出集合
            try:
                result = server.db.list_collections()
                self.log_test("列出集合", True, f"找到{len(result)}个集合")
            except Exception as e:
                self.log_test("列出集合", False, str(e))
            
        except ImportError as e:
            self.log_test("ChromaDB服务器导入", False, f"导入失败，可能需要安装chromadb: {e}")
        except Exception as e:
            self.log_test("ChromaDB服务器", False, f"未知错误: {e}")
    
    def create_sample_data(self):
        """创建示例数据"""
        print("\n=== 创建示例数据 ===")
        
        # 创建CSV示例数据
        csv_data_dir = Path("./test_csv_data")
        csv_data_dir.mkdir(exist_ok=True)
        
        # 示例产品数据
        products_data = [
            {"id": 1, "name": "笔记本电脑", "price": 5999.99, "category": "电子产品", "stock": 50},
            {"id": 2, "name": "手机", "price": 3999.99, "category": "电子产品", "stock": 100},
            {"id": 3, "name": "耳机", "price": 299.99, "category": "电子产品", "stock": 200},
            {"id": 4, "name": "键盘", "price": 199.99, "category": "电子产品", "stock": 150},
            {"id": 5, "name": "鼠标", "price": 99.99, "category": "电子产品", "stock": 300}
        ]
        
        products_df = pd.DataFrame(products_data)
        products_df.to_csv(csv_data_dir / "products.csv", index=False, encoding='utf-8-sig')
        
        # 示例订单数据
        orders_data = [
            {"order_id": "ORD001", "customer_name": "张三", "product_id": 1, "quantity": 1, "order_date": "2024-01-15"},
            {"order_id": "ORD002", "customer_name": "李四", "product_id": 2, "quantity": 2, "order_date": "2024-01-16"},
            {"order_id": "ORD003", "customer_name": "王五", "product_id": 3, "quantity": 1, "order_date": "2024-01-17"},
            {"order_id": "ORD004", "customer_name": "赵六", "product_id": 4, "quantity": 3, "order_date": "2024-01-18"},
            {"order_id": "ORD005", "customer_name": "钱七", "product_id": 5, "quantity": 2, "order_date": "2024-01-19"}
        ]
        
        orders_df = pd.DataFrame(orders_data)
        orders_df.to_csv(csv_data_dir / "orders.csv", index=False, encoding='utf-8-sig')
        
        print(f"✅ 创建CSV示例数据:")
        print(f"   - products.csv: {len(products_data)}条产品记录")
        print(f"   - orders.csv: {len(orders_data)}条订单记录")
    
    def print_summary(self):
        """打印测试总结"""
        print("\n" + "="*50)
        print("测试总结")
        print("="*50)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"总测试数: {total_tests}")
        print(f"通过: {passed_tests}")
        print(f"失败: {failed_tests}")
        print(f"成功率: {(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "0%")
        
        if failed_tests > 0:
            print("\n失败的测试:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  ❌ {result['test_name']}: {result['message']}")
        
        print("\n推荐操作:")
        print("1. 安装缺少的依赖:")
        print("   pip install pandas chardet chromadb numpy")
        print("2. 运行高级启动器:")
        print("   python advanced_launcher.py")
        print("3. 测试服务器功能:")
        print("   python advanced_launcher.py list")


async def main():
    """主函数"""
    print("高级MCP服务器功能测试")
    print("="*50)
    
    tester = ServerTester()
    
    # 创建示例数据
    tester.create_sample_data()
    
    # 测试CSV服务器
    await tester.test_csv_server()
    
    # 测试ChromaDB服务器
    await tester.test_chromadb_server()
    
    # 打印总结
    tester.print_summary()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main()) 