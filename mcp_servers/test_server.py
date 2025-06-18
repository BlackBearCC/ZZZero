"""
MCP服务器测试脚本
用于测试简单CSV服务器的功能
"""

import json
import asyncio
import subprocess
import time
from pathlib import Path


class MCPServerTester:
    """MCP服务器测试器"""
    
    def __init__(self, server_script: str):
        self.server_script = server_script
        self.process = None
        
    async def start_server(self):
        """启动服务器"""
        print(f"启动服务器: {self.server_script}")
        self.process = await asyncio.create_subprocess_exec(
            "python", self.server_script,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # 等待服务器启动
        await asyncio.sleep(1)
        
    async def send_request(self, request: dict) -> dict:
        """发送请求到服务器"""
        if not self.process:
            raise RuntimeError("服务器未启动")
            
        # 发送请求
        request_json = json.dumps(request) + "\n"
        self.process.stdin.write(request_json.encode())
        await self.process.stdin.drain()
        
        # 读取响应
        response_line = await self.process.stdout.readline()
        response = json.loads(response_line.decode().strip())
        
        return response
        
    async def stop_server(self):
        """停止服务器"""
        if self.process:
            self.process.terminate()
            await self.process.wait()
            
    async def test_initialize(self):
        """测试初始化"""
        print("\n=== 测试初始化 ===")
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocol_version": "2024-11-05",
                "capabilities": {},
                "client_info": {
                    "name": "test-client",
                    "version": "0.1.0"
                }
            }
        }
        
        response = await self.send_request(request)
        print(f"请求: {json.dumps(request, indent=2, ensure_ascii=False)}")
        print(f"响应: {json.dumps(response, indent=2, ensure_ascii=False)}")
        
        return response.get("result") is not None
        
    async def test_list_tools(self):
        """测试工具列表"""
        print("\n=== 测试工具列表 ===")
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        response = await self.send_request(request)
        print(f"请求: {json.dumps(request, indent=2, ensure_ascii=False)}")
        print(f"响应: {json.dumps(response, indent=2, ensure_ascii=False)}")
        
        tools = response.get("result", {}).get("tools", [])
        return len(tools) > 0
        
    async def test_csv_list_files(self):
        """测试CSV文件列表"""
        print("\n=== 测试CSV文件列表 ===")
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "csv_list_files",
                "arguments": {
                    "directory": "."
                }
            }
        }
        
        response = await self.send_request(request)
        print(f"请求: {json.dumps(request, indent=2, ensure_ascii=False)}")
        print(f"响应: {json.dumps(response, indent=2, ensure_ascii=False)}")
        
        return response.get("result") is not None
        
    async def create_test_csv(self):
        """创建测试CSV文件"""
        test_data = """名称,年龄,城市
张三,25,北京
李四,30,上海
王五,28,广州"""
        
        with open("test_data.csv", "w", encoding="utf-8") as f:
            f.write(test_data)
            
        print("创建测试CSV文件: test_data.csv")
        
    async def test_csv_query(self):
        """测试CSV查询"""
        print("\n=== 测试CSV查询 ===")
        
        # 确保测试文件存在
        await self.create_test_csv()
        
        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "csv_query",
                "arguments": {
                    "file_path": "test_data.csv",
                    "limit": 5
                }
            }
        }
        
        response = await self.send_request(request)
        print(f"请求: {json.dumps(request, indent=2, ensure_ascii=False)}")
        print(f"响应: {json.dumps(response, indent=2, ensure_ascii=False)}")
        
        return response.get("result") is not None
        
    async def run_all_tests(self):
        """运行所有测试"""
        print("开始MCP服务器测试...")
        
        try:
            await self.start_server()
            
            tests = [
                ("初始化", self.test_initialize),
                ("工具列表", self.test_list_tools),
                ("CSV文件列表", self.test_csv_list_files),
                ("CSV查询", self.test_csv_query),
            ]
            
            results = []
            for test_name, test_func in tests:
                try:
                    result = await test_func()
                    results.append((test_name, result))
                    print(f"✅ {test_name}: {'通过' if result else '失败'}")
                except Exception as e:
                    results.append((test_name, False))
                    print(f"❌ {test_name}: 错误 - {e}")
                    
            # 总结
            print(f"\n=== 测试总结 ===")
            passed = sum(1 for _, result in results if result)
            total = len(results)
            print(f"通过: {passed}/{total}")
            
            for test_name, result in results:
                status = "✅" if result else "❌"
                print(f"{status} {test_name}")
                
        finally:
            await self.stop_server()
            
            # 清理测试文件
            test_file = Path("test_data.csv")
            if test_file.exists():
                test_file.unlink()
                print("清理测试文件")


async def main():
    """主函数"""
    tester = MCPServerTester("simple_csv_server.py")
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main()) 