#!/usr/bin/env python3
"""
高级MCP服务器启动器
支持启动和管理CSV CRUD服务器和ChromaDB CRUD服务器
"""
import os
import sys
import asyncio
import subprocess
import signal
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
import argparse

# 添加父目录到路径以便导入MCP模块
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

logger = logging.getLogger(__name__)


class ServerConfig:
    """服务器配置类"""
    
    def __init__(self, name: str, script_path: str, description: str, 
                 data_dir: Optional[str] = None, dependencies: Optional[List[str]] = None):
        self.name = name
        self.script_path = script_path
        self.description = description
        self.data_dir = data_dir
        self.dependencies = dependencies or []


class AdvancedMCPLauncher:
    """高级MCP服务器启动器"""
    
    def __init__(self):
        """初始化启动器"""
        self.base_dir = Path(__file__).parent
        self.servers = self._load_server_configs()
        self.running_processes: Dict[str, subprocess.Popen] = {}
        
        # 设置信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("高级MCP启动器初始化完成")
    
    def _load_server_configs(self) -> Dict[str, ServerConfig]:
        """加载服务器配置"""
        configs = {
            'csv': ServerConfig(
                name="CSV CRUD服务器",
                script_path="csv_crud_server.py",
                description="高级CSV数据库服务器，支持完整的CRUD操作、复杂查询、数据验证等",
                data_dir="./csv_data",
                dependencies=["pandas", "chardet"]
            ),
            'chromadb': ServerConfig(
                name="ChromaDB CRUD服务器",
                script_path="chromadb_crud_server.py",
                description="高级ChromaDB向量数据库服务器，支持向量存储、语义搜索、集合管理等",
                data_dir="./chroma_data",
                dependencies=["chromadb", "numpy"]
            )
        }
        return configs
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"接收到信号 {signum}，正在关闭所有服务器...")
        asyncio.create_task(self.stop_all_servers())
    
    def check_dependencies(self, server_key: str) -> Dict[str, bool]:
        """检查服务器依赖"""
        config = self.servers.get(server_key)
        if not config:
            return {}
        
        results = {}
        for dep in config.dependencies:
            try:
                __import__(dep)
                results[dep] = True
            except ImportError:
                results[dep] = False
        
        return results
    
    def list_servers(self) -> List[Dict[str, Any]]:
        """列出可用的服务器"""
        servers_info = []
        for key, config in self.servers.items():
            script_path = self.base_dir / config.script_path
            deps = self.check_dependencies(key)
            
            info = {
                'key': key,
                'name': config.name,
                'description': config.description,
                'script_exists': script_path.exists(),
                'dependencies': deps,
                'all_deps_available': all(deps.values()) if deps else True,
                'running': key in self.running_processes,
                'data_dir': config.data_dir
            }
            servers_info.append(info)
        
        return servers_info
    
    async def start_server(self, server_key: str) -> Dict[str, Any]:
        """启动指定服务器"""
        if server_key not in self.servers:
            raise ValueError(f"未知服务器: {server_key}")
        
        config = self.servers[server_key]
        
        # 检查依赖
        deps = self.check_dependencies(server_key)
        missing_deps = [dep for dep, available in deps.items() if not available]
        if missing_deps:
            return {
                'success': False,
                'error': f"缺少依赖: {missing_deps}",
                'install_command': f"pip install {' '.join(missing_deps)}"
            }
        
        # 检查是否已经运行
        if server_key in self.running_processes:
            return {
                'success': False,
                'error': f"服务器 '{config.name}' 已经在运行"
            }
        
        # 检查脚本文件
        script_path = self.base_dir / config.script_path
        if not script_path.exists():
            return {
                'success': False,
                'error': f"服务器脚本不存在: {script_path}"
            }
        
        try:
            # 创建数据目录
            if config.data_dir:
                data_path = Path(config.data_dir)
                data_path.mkdir(exist_ok=True)
            
            # 启动服务器进程
            cmd = [sys.executable, str(script_path)]
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(self.base_dir)
            )
            
            self.running_processes[server_key] = process
            
            logger.info(f"启动服务器: {config.name} (PID: {process.pid})")
            
            return {
                'success': True,
                'server_name': config.name,
                'pid': process.pid,
                'data_dir': config.data_dir
            }
            
        except Exception as e:
            logger.error(f"启动服务器失败 {config.name}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def stop_server(self, server_key: str) -> Dict[str, Any]:
        """停止指定服务器"""
        if server_key not in self.running_processes:
            return {
                'success': False,
                'error': f"服务器未运行: {server_key}"
            }
        
        config = self.servers[server_key]
        process = self.running_processes[server_key]
        
        try:
            # 优雅地关闭进程
            process.terminate()
            
            # 等待进程结束
            try:
                await asyncio.wait_for(
                    asyncio.create_task(self._wait_for_process(process)),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                # 强制杀死进程
                process.kill()
                await asyncio.create_task(self._wait_for_process(process))
            
            del self.running_processes[server_key]
            
            logger.info(f"停止服务器: {config.name}")
            
            return {
                'success': True,
                'server_name': config.name
            }
            
        except Exception as e:
            logger.error(f"停止服务器失败 {config.name}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _wait_for_process(self, process: subprocess.Popen):
        """等待进程结束"""
        while process.poll() is None:
            await asyncio.sleep(0.1)
    
    async def stop_all_servers(self):
        """停止所有服务器"""
        for server_key in list(self.running_processes.keys()):
            await self.stop_server(server_key)
    
    def get_server_status(self, server_key: str) -> Dict[str, Any]:
        """获取服务器状态"""
        if server_key not in self.servers:
            return {'error': f"未知服务器: {server_key}"}
        
        config = self.servers[server_key]
        
        if server_key in self.running_processes:
            process = self.running_processes[server_key]
            return {
                'running': True,
                'pid': process.pid,
                'name': config.name,
                'data_dir': config.data_dir
            }
        else:
            return {
                'running': False,
                'name': config.name,
                'data_dir': config.data_dir
            }
    
    async def interactive_mode(self):
        """交互模式"""
        print("=== 高级MCP服务器启动器 ===")
        print("可用命令:")
        print("  list    - 列出所有服务器")
        print("  start   - 启动服务器")
        print("  stop    - 停止服务器")
        print("  status  - 查看服务器状态")
        print("  deps    - 检查依赖")
        print("  quit    - 退出")
        print()
        
        while True:
            try:
                command = input("请输入命令 > ").strip().lower()
                
                if command == 'quit' or command == 'q':
                    print("正在停止所有服务器...")
                    await self.stop_all_servers()
                    print("再见!")
                    break
                
                elif command == 'list' or command == 'l':
                    servers = self.list_servers()
                    print("\n可用服务器:")
                    for server in servers:
                        status = "✅ 运行中" if server['running'] else "⭕ 已停止"
                        deps_status = "✅ 依赖完整" if server['all_deps_available'] else "❌ 缺少依赖"
                        print(f"  {server['key']}: {server['name']} - {status} - {deps_status}")
                        print(f"     {server['description']}")
                    print()
                
                elif command == 'start' or command == 's':
                    print("可用服务器:")
                    for key, config in self.servers.items():
                        print(f"  {key}: {config.name}")
                    
                    server_key = input("请输入要启动的服务器键 > ").strip()
                    if server_key:
                        result = await self.start_server(server_key)
                        if result['success']:
                            print(f"✅ 成功启动: {result['server_name']} (PID: {result['pid']})")
                        else:
                            print(f"❌ 启动失败: {result['error']}")
                            if 'install_command' in result:
                                print(f"   安装命令: {result['install_command']}")
                
                elif command == 'stop':
                    running_servers = [k for k in self.running_processes.keys()]
                    if not running_servers:
                        print("没有运行中的服务器")
                        continue
                    
                    print("运行中的服务器:")
                    for key in running_servers:
                        print(f"  {key}: {self.servers[key].name}")
                    
                    server_key = input("请输入要停止的服务器键 > ").strip()
                    if server_key:
                        result = await self.stop_server(server_key)
                        if result['success']:
                            print(f"✅ 成功停止: {result['server_name']}")
                        else:
                            print(f"❌ 停止失败: {result['error']}")
                
                elif command == 'status':
                    print("\n服务器状态:")
                    for key, config in self.servers.items():
                        status = self.get_server_status(key)
                        if status['running']:
                            print(f"  {key}: ✅ 运行中 (PID: {status['pid']})")
                        else:
                            print(f"  {key}: ⭕ 已停止")
                    print()
                
                elif command == 'deps':
                    print("\n依赖检查:")
                    for key, config in self.servers.items():
                        print(f"  {config.name}:")
                        deps = self.check_dependencies(key)
                        for dep, available in deps.items():
                            status = "✅ 已安装" if available else "❌ 未安装"
                            print(f"    {dep}: {status}")
                    print()
                
                else:
                    print("未知命令，请输入 'list', 'start', 'stop', 'status', 'deps' 或 'quit'")
                
            except KeyboardInterrupt:
                print("\n正在退出...")
                await self.stop_all_servers()
                break
            except Exception as e:
                print(f"错误: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="高级MCP服务器启动器")
    parser.add_argument('command', nargs='?', choices=['list', 'start', 'stop', 'interactive'], 
                      help='要执行的命令')
    parser.add_argument('--server', '-s', help='服务器键 (csv 或 chromadb)')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    # 设置日志级别
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    launcher = AdvancedMCPLauncher()
    
    async def run_command():
        if args.command == 'list':
            servers = launcher.list_servers()
            print("\n=== 可用服务器 ===")
            for server in servers:
                status = "运行中" if server['running'] else "已停止"
                deps_status = "依赖完整" if server['all_deps_available'] else "缺少依赖"
                print(f"\n{server['key']}: {server['name']}")
                print(f"  状态: {status}")
                print(f"  依赖: {deps_status}")
                print(f"  描述: {server['description']}")
                if not server['all_deps_available']:
                    missing = [dep for dep, avail in server['dependencies'].items() if not avail]
                    print(f"  缺少: {missing}")
        
        elif args.command == 'start':
            if not args.server:
                print("错误: 请指定要启动的服务器 (--server csv 或 --server chromadb)")
                return
            
            result = await launcher.start_server(args.server)
            if result['success']:
                print(f"✅ 成功启动: {result['server_name']}")
                print(f"   PID: {result['pid']}")
                print(f"   数据目录: {result.get('data_dir', 'N/A')}")
            else:
                print(f"❌ 启动失败: {result['error']}")
                if 'install_command' in result:
                    print(f"   安装命令: {result['install_command']}")
        
        elif args.command == 'stop':
            if not args.server:
                print("错误: 请指定要停止的服务器 (--server csv 或 --server chromadb)")
                return
            
            result = await launcher.stop_server(args.server)
            if result['success']:
                print(f"✅ 成功停止: {result['server_name']}")
            else:
                print(f"❌ 停止失败: {result['error']}")
        
        else:
            # 默认进入交互模式
            await launcher.interactive_mode()
    
    try:
        asyncio.run(run_command())
    except KeyboardInterrupt:
        print("\n程序被中断")
    except Exception as e:
        logger.error(f"程序错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()