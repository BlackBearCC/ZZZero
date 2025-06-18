"""
MCP服务端工具类
"""
import logging
from typing import Dict, Any, Optional


class ServerConfig:
    """服务器配置"""
    
    def __init__(self, **kwargs):
        """初始化配置"""
        self.max_request_size = kwargs.get('max_request_size', 1024 * 1024)  # 1MB
        self.request_timeout = kwargs.get('request_timeout', 30.0)
        self.enable_metrics = kwargs.get('enable_metrics', True)
        self.protocol_version = kwargs.get('protocol_version', "2024-11-05")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'max_request_size': self.max_request_size,
            'request_timeout': self.request_timeout,
            'enable_metrics': self.enable_metrics,
            'protocol_version': self.protocol_version,
        }


class ServerLogger:
    """服务器日志器"""
    
    def __init__(self, name: str, level: int = logging.INFO):
        """初始化日志器"""
        self.logger = logging.getLogger(f"mcp.server.{name}")
        self.logger.setLevel(level)
        
        # 创建处理器
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def debug(self, message: str, *args, **kwargs):
        """调试日志"""
        self.logger.debug(message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """信息日志"""
        self.logger.info(message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """警告日志"""
        self.logger.warning(message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """错误日志"""
        self.logger.error(message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        """严重错误日志"""
        self.logger.critical(message, *args, **kwargs) 