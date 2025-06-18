"""
MCP客户端工具类
"""
import logging
from typing import Dict, Any, Optional


class ClientConfig:
    """客户端配置"""
    
    def __init__(self, **kwargs):
        """初始化配置"""
        self.request_timeout = kwargs.get('request_timeout', 30.0)
        self.max_concurrent_requests = kwargs.get('max_concurrent_requests', 100)
        self.enable_metrics = kwargs.get('enable_metrics', True)
        self.auto_reconnect = kwargs.get('auto_reconnect', True)
        self.reconnect_delay = kwargs.get('reconnect_delay', 1.0)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'request_timeout': self.request_timeout,
            'max_concurrent_requests': self.max_concurrent_requests,
            'enable_metrics': self.enable_metrics,
            'auto_reconnect': self.auto_reconnect,
            'reconnect_delay': self.reconnect_delay,
        }


class ClientLogger:
    """客户端日志器"""
    
    def __init__(self, name: str, level: int = logging.INFO):
        """初始化日志器"""
        self.logger = logging.getLogger(f"mcp.client.{name}")
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