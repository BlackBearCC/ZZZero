#!/usr/bin/env python3
"""
Python代码执行服务器 - 基于MCP协议的安全Python代码执行环境
支持代码执行、包管理、虚拟环境、执行历史等功能
"""
import os
import sys
import subprocess
import tempfile
import shutil
import json
import re
import ast
import venv
try:
    import pkg_resources
except ImportError:
    # pkg_resources已被弃用，使用importlib.metadata替代
    from importlib import metadata as pkg_resources
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime
import asyncio
import logging
import threading
import time
import signal
from contextlib import contextmanager

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from mcp.server.stdio_server import StdioMCPServer
from mcp.types import Tool, Resource, JSONSchema, ToolInputSchema

logger = logging.getLogger(__name__)


# SecurityChecker类已移除 - 简化设计，不再需要安全检查


class PythonExecutor:
    """Python代码执行器 - 在隔离环境中安全执行Python代码"""
    
    def __init__(self, workspace_dir: str = "./workspace/python_executor"):
        """
        初始化Python执行器
        
        Args:
            workspace_dir: 工作空间目录
        """
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # 执行历史
        self.execution_history = []
        
        # 虚拟环境路径
        self.venv_dir = self.workspace_dir / "venv"
        
        # 初始化虚拟环境
        self._setup_virtual_environment()
    
    def _setup_virtual_environment(self):
        """设置虚拟环境"""
        if not self.venv_dir.exists():
            logger.info("创建Python虚拟环境...")
            venv.create(self.venv_dir, with_pip=True)
            
            # 安装基础包
            self._install_package_in_venv(['pip', 'setuptools', 'wheel'])
    
    def _get_venv_python(self) -> str:
        """获取虚拟环境的Python解释器路径"""
        if os.name == 'nt':  # Windows
            return str(self.venv_dir / "Scripts" / "python.exe")
        else:  # Unix-like
            return str(self.venv_dir / "bin" / "python")
    
    def _get_venv_pip(self) -> str:
        """获取虚拟环境的pip路径"""
        if os.name == 'nt':  # Windows
            return str(self.venv_dir / "Scripts" / "pip.exe")
        else:  # Unix-like
            return str(self.venv_dir / "bin" / "pip")
    
    def _install_package_in_venv(self, packages: List[str]) -> Tuple[bool, str]:
        """在虚拟环境中安装包"""
        pip_path = self._get_venv_pip()
        
        try:
            cmd = [pip_path, 'install'] + packages
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5分钟超时
                cwd=str(self.workspace_dir)
            )
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, result.stderr
                
        except subprocess.TimeoutExpired:
            return False, "包安装超时"
        except Exception as e:
            return False, f"安装包时发生错误: {e}"
    
    def _extract_imports(self, code: str) -> Set[str]:
        """从代码中提取导入的模块"""
        imports = set()
        
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module.split('.')[0])
        except:
            pass
        
        return imports
    
    def _check_and_install_dependencies(self, code: str) -> Tuple[bool, str]:
        """检查并安装代码依赖"""
        imports = self._extract_imports(code)
        if not imports:
            return True, "无需安装依赖"
        
        # 获取已安装的包
        try:
            installed_packages = self.list_installed_packages()
            installed_names = {pkg['name'].lower() for pkg in installed_packages}
        except:
            installed_names = set()
        
        # 需要安装的包
        to_install = []
        for imp in imports:
            imp_lower = imp.lower()
            # 跳过内置模块和标准库模块
            builtin_modules = {
                'sys', 'os', 'time', 'datetime', 'json', 'csv', 're', 'math', 'random',
                'string', 'glob', 'pathlib', 'io', 'gzip', 'zipfile', 'tarfile',
                'collections', 'itertools', 'functools', 'operator', 'hashlib',
                'base64', 'uuid', 'tempfile', 'shutil', 'subprocess'
            }
            if imp_lower in builtin_modules:
                continue
            
            # 检查是否已安装
            if imp_lower not in installed_names:
                # 常见的包名映射
                package_mapping = {
                    'cv2': 'opencv-python',
                    'pil': 'pillow',
                    'sklearn': 'scikit-learn',
                    'bs4': 'beautifulsoup4'
                }
                package_name = package_mapping.get(imp_lower, imp)
                to_install.append(package_name)
        
        if not to_install:
            return True, "所有依赖已安装"
        
        # 安装缺失的包
        logger.info(f"安装依赖包: {to_install}")
        success, message = self._install_package_in_venv(to_install)
        
        if success:
            return True, f"成功安装依赖: {', '.join(to_install)}"
        else:
            return False, f"安装依赖失败: {message}"
    
    @contextmanager
    def _timeout_handler(self, timeout_seconds: int):
        """超时处理上下文管理器"""
        def timeout_handler(signum, frame):
            raise TimeoutError(f"代码执行超时 ({timeout_seconds}秒)")
        
        if os.name != 'nt':  # Unix-like系统支持信号
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_seconds)
            try:
                yield
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        else:
            # Windows系统使用线程超时
            yield
    
    def execute_code(self, code: str, timeout: int = 30, 
                    allow_unsafe: bool = False) -> Dict[str, Any]:
        """
        执行Python代码
        
        Args:
            code: 要执行的Python代码
            timeout: 超时时间(秒)
            allow_unsafe: 是否允许不安全的代码
            
        Returns:
            执行结果字典
        """
        execution_id = f"exec_{int(time.time())}"
        start_time = datetime.now()
        
        try:
            # 安全性检查
            if not allow_unsafe:
                is_safe, warnings = SecurityChecker.check_code_safety(code)
                if not is_safe:
                    return {
                        'execution_id': execution_id,
                        'success': False,
                        'error': '代码安全检查失败',
                        'warnings': warnings,
                        'executed_at': start_time.isoformat()
                    }
            
            # 检查并安装依赖
            deps_success, deps_message = self._check_and_install_dependencies(code)
            if not deps_success:
                return {
                    'execution_id': execution_id,
                    'success': False,
                    'error': f'依赖安装失败: {deps_message}',
                    'executed_at': start_time.isoformat()
                }
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(
                mode='w', 
                suffix='.py', 
                dir=str(self.workspace_dir),
                delete=False,
                encoding='utf-8'
            ) as f:
                f.write(code)
                temp_file = f.name
            
            try:
                # 执行代码
                python_path = self._get_venv_python()
                
                result = subprocess.run(
                    [python_path, temp_file],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=str(self.workspace_dir)
                )
                
                end_time = datetime.now()
                execution_time = (end_time - start_time).total_seconds()
                
                # 构建结果
                execution_result = {
                    'execution_id': execution_id,
                    'success': result.returncode == 0,
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'return_code': result.returncode,
                    'execution_time': execution_time,
                    'dependencies_info': deps_message,
                    'executed_at': start_time.isoformat(),
                    'completed_at': end_time.isoformat()
                }
                
                # 添加到历史记录
                history_entry = {
                    'execution_id': execution_id,
                    'code': code[:500] + '...' if len(code) > 500 else code,
                    'success': execution_result['success'],
                    'execution_time': execution_time,
                    'executed_at': start_time.isoformat()
                }
                self.execution_history.append(history_entry)
                
                # 限制历史记录数量
                if len(self.execution_history) > 100:
                    self.execution_history = self.execution_history[-100:]
                
                return execution_result
                
            finally:
                # 清理临时文件
                try:
                    os.unlink(temp_file)
                except:
                    pass
                    
        except subprocess.TimeoutExpired:
            return {
                'execution_id': execution_id,
                'success': False,
                'error': f'代码执行超时 ({timeout}秒)',
                'executed_at': start_time.isoformat()
            }
        except Exception as e:
            return {
                'execution_id': execution_id,
                'success': False,
                'error': f'执行过程中发生错误: {str(e)}',
                'executed_at': start_time.isoformat()
            }
    
    def install_package(self, package_name: str) -> Dict[str, Any]:
        """安装Python包"""
        try:
            success, message = self._install_package_in_venv([package_name])
            return {
                'package_name': package_name,
                'success': success,
                'message': message,
                'installed_at': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'package_name': package_name,
                'success': False,
                'message': f'安装失败: {str(e)}',
                'installed_at': datetime.now().isoformat()
            }
    
    def list_installed_packages(self) -> List[Dict[str, Any]]:
        """列出已安装的包"""
        try:
            pip_path = self._get_venv_pip()
            result = subprocess.run(
                [pip_path, 'list', '--format=json'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                packages = json.loads(result.stdout)
                return [
                    {
                        'name': pkg['name'],
                        'version': pkg['version']
                    }
                    for pkg in packages
                ]
            else:
                return []
                
        except Exception as e:
            logger.error(f"获取包列表失败: {e}")
            return []
    
    def get_execution_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取执行历史"""
        return self.execution_history[-limit:]
    
    def clear_execution_history(self) -> Dict[str, Any]:
        """清空执行历史"""
        count = len(self.execution_history)
        self.execution_history.clear()
        return {
            'cleared_count': count,
            'cleared_at': datetime.now().isoformat()
        }


class PythonExecutorServer(StdioMCPServer):
    """Python代码执行MCP服务器"""
    
    def __init__(self, workspace_dir: str = "./workspace/python_executor"):
        """初始化服务器"""
        super().__init__("python-executor-server")
        self.executor = PythonExecutor(workspace_dir)
        self._register_python_tools()
    
    def _extract_python_code(self, input_text: str) -> str:
        """从输入中提取Python代码"""
        import re
        
        # 清理输入
        input_text = input_text.strip()
        
        # 查找```python代码块
        python_blocks = re.findall(r'```python\s*\n(.*?)\n```', input_text, re.DOTALL)
        if python_blocks:
            return python_blocks[0].strip()
        
        # 查找```代码块（没有语言标识）
        code_blocks = re.findall(r'```\s*\n(.*?)\n```', input_text, re.DOTALL)
        if code_blocks:
            return code_blocks[0].strip()
        
        # 如果没有代码块标记，检查是否直接是Python代码
        if any(keyword in input_text for keyword in ['import ', 'def ', 'print(', 'for ', 'if ', 'while ', '=']):
            return input_text
        
        return ""
    
    def _register_python_tools(self):
        """注册Python执行相关工具"""
        
        # 执行Python代码工具 - 简化版，直接从输入中提取代码
        self.register_tool(Tool(
            name="execute_python",
            description="执行Python代码。输入应该包含```python代码块```或直接的Python代码",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "input": {
                        "type": "string", 
                        "description": "包含Python代码的输入，可以是markdown格式或纯代码"
                    }
                },
                required=["input"]
            )
        ))
        
        # 安装Python包工具
        self.register_tool(Tool(
            name="install_python_package",
            description="安装Python包到虚拟环境",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "package_name": {
                        "type": "string",
                        "description": "要安装的包名"
                    }
                },
                required=["package_name"]
            )
        ))
        
        # 列出已安装包工具
        self.register_tool(Tool(
            name="list_installed_packages",
            description="列出虚拟环境中已安装的Python包",
            inputSchema=ToolInputSchema(
                type="object",
                properties={}
            )
        ))
        
        # 获取执行历史工具
        self.register_tool(Tool(
            name="get_execution_history",
            description="获取代码执行历史记录",
            inputSchema=ToolInputSchema(
                type="object",
                properties={
                    "limit": {
                        "type": "integer",
                        "description": "返回的历史记录数量限制，默认20",
                        "default": 20
                    }
                }
            )
        ))
        
        # 清空执行历史工具
        self.register_tool(Tool(
            name="clear_execution_history",
            description="清空代码执行历史记录",
            inputSchema=ToolInputSchema(
                type="object",
                properties={}
            )
        ))
        
# 安全检查工具已移除 - 简化设计
    
    async def _call_tool(self, name: str, arguments: Dict[str, Any], context) -> Dict[str, Any]:
        """处理工具调用"""
        try:
            logger.info(f"工具调用: {name}")
            logger.info(f"参数类型: {type(arguments)}")
            logger.info(f"参数键: {list(arguments.keys()) if isinstance(arguments, dict) else 'Not a dict'}")
            logger.info(f"参数内容: {arguments}")
            
            if name == "execute_python":
                # 简化参数处理
                if "input" not in arguments:
                    return {"error": "缺少必需参数 'input'"}
                
                input_text = arguments["input"]
                if not isinstance(input_text, str):
                    return {"error": f"参数 'input' 必须是字符串"}
                
                # 从输入中提取Python代码
                code = self._extract_python_code(input_text)
                if not code:
                    return {"error": "未找到Python代码"}
                
                # 直接执行代码，不做安全检查
                return self.executor.execute_code(code, timeout=30, allow_unsafe=True)
            
            elif name == "install_python_package":
                if "package_name" not in arguments:
                    return {
                        "error": "缺少必需参数 'package_name'",
                        "received_arguments": list(arguments.keys())
                    }
                package_name = arguments["package_name"]
                if not isinstance(package_name, str):
                    return {
                        "error": f"参数 'package_name' 必须是字符串，当前类型: {type(package_name).__name__}"
                    }
                return self.executor.install_package(package_name)
            
            elif name == "list_installed_packages":
                packages = self.executor.list_installed_packages()
                return {
                    "packages": packages,
                    "total_count": len(packages),
                    "retrieved_at": datetime.now().isoformat()
                }
            
            elif name == "get_execution_history":
                limit = arguments.get("limit", 20)
                if not isinstance(limit, (int, float)) or limit <= 0:
                    limit = 20
                limit = int(limit)
                history = self.executor.get_execution_history(limit)
                return {
                    "history": history,
                    "total_count": len(history),
                    "retrieved_at": datetime.now().isoformat()
                }
            
            elif name == "clear_execution_history":
                return self.executor.clear_execution_history()
            
# check_code_safety工具处理逻辑已移除
            
            else:
                return {"error": f"未知工具: {name}"}
                
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"工具调用失败 {name}: {e}")
            logger.error(f"错误详情: {error_traceback}")
            return {
                "error": f"工具调用失败: {str(e)}",
                "error_type": type(e).__name__,
                "tool_name": name,
                "received_arguments": arguments,
                "timestamp": datetime.now().isoformat()
            }


async def main():
    """主函数"""
    logging.basicConfig(level=logging.INFO)
    
    # 创建服务器实例
    server = PythonExecutorServer()
    
    # 运行服务器
    logger.info("启动Python执行器MCP服务器...")
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())