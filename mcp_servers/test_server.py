#!/usr/bin/env python3
"""
简单的MCP测试服务器
用于测试MCP连接
"""
import logging
from mcp.server.fastmcp import FastMCP

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 创建MCP服务器
mcp = FastMCP("test_server")

@mcp.tool()
def hello(name: str = "World") -> str:
    """简单的问候工具"""
    logger.debug(f"hello工具被调用，name={name}")
    return f"Hello, {name}!"

@mcp.tool()
def add(a: int, b: int) -> int:
    """简单的加法工具"""
    logger.debug(f"add工具被调用，a={a}, b={b}")
    return a + b

if __name__ == "__main__":
    logger.info("启动测试MCP服务器...")
    mcp.run(transport="stdio") 