"""
错误处理和重试机制模块
"""
import asyncio
import time
import random
from typing import Dict, List, Any, Optional, Callable, Union, Type
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """错误严重性级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorAction(Enum):
    """错误处理动作"""
    RETRY = "retry"
    SKIP = "skip"
    FALLBACK = "fallback"
    ABORT = "abort"
    IGNORE = "ignore"

@dataclass
class RetryPolicy:
    """重试策略配置"""
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    retry_on_exceptions: List[Type[Exception]] = field(default_factory=lambda: [Exception])
    
    def calculate_delay(self, attempt: int) -> float:
        """计算重试延迟"""
        if attempt <= 0:
            return 0
        
        delay = self.initial_delay * (self.backoff_multiplier ** (attempt - 1))
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            # 添加随机抖动，避免雷群效应
            jitter_range = delay * 0.1
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(delay, 0)

@dataclass
class ErrorContext:
    """错误上下文信息"""
    node_name: str
    error: Exception
    attempt: int
    timestamp: datetime
    state: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CircuitBreakerConfig:
    """断路器配置"""
    failure_threshold: int = 5  # 失败阈值
    success_threshold: int = 3  # 成功阈值（半开状态）
    timeout: float = 60.0  # 开路超时时间
    
class CircuitBreakerState(Enum):
    """断路器状态"""
    CLOSED = "closed"    # 正常状态
    OPEN = "open"        # 开路状态
    HALF_OPEN = "half_open"  # 半开状态

class CircuitBreaker:
    """断路器实现"""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs):
        """通过断路器调用函数"""
        async with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.success_count = 0
                else:
                    raise CircuitBreakerOpenError("Circuit breaker is open")
        
        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """检查是否应该尝试重置断路器"""
        if self.last_failure_time is None:
            return True
        
        return time.time() - self.last_failure_time >= self.config.timeout
    
    async def _on_success(self):
        """成功回调"""
        async with self._lock:
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitBreakerState.CLOSED
                    self.failure_count = 0
            elif self.state == CircuitBreakerState.CLOSED:
                self.failure_count = 0
    
    async def _on_failure(self):
        """失败回调"""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitBreakerState.OPEN

class CircuitBreakerOpenError(Exception):
    """断路器开路异常"""
    pass

class ErrorHandler:
    """错误处理器"""
    
    def __init__(self):
        self.retry_policies: Dict[str, RetryPolicy] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.error_handlers: Dict[Type[Exception], Callable] = {}
        self.fallback_handlers: Dict[str, Callable] = {}
        
        # 默认重试策略
        self.default_retry_policy = RetryPolicy()
        
        # 错误统计
        self.error_stats: Dict[str, Dict[str, int]] = {}
    
    def add_retry_policy(self, node_name: str, policy: RetryPolicy):
        """为特定节点添加重试策略"""
        self.retry_policies[node_name] = policy
    
    def add_circuit_breaker(self, node_name: str, config: CircuitBreakerConfig):
        """为特定节点添加断路器"""
        self.circuit_breakers[node_name] = CircuitBreaker(config)
    
    def add_error_handler(self, 
                         exception_type: Type[Exception], 
                         handler: Callable[[ErrorContext], ErrorAction]):
        """添加错误处理器"""
        self.error_handlers[exception_type] = handler
    
    def add_fallback_handler(self, node_name: str, handler: Callable):
        """添加降级处理器"""
        self.fallback_handlers[node_name] = handler
    
    async def handle_error(self, 
                          error: Exception,
                          node_name: str,
                          attempt: int,
                          state: Dict[str, Any],
                          metadata: Optional[Dict[str, Any]] = None) -> ErrorAction:
        """处理错误"""
        
        # 更新错误统计
        self._update_error_stats(node_name, type(error).__name__)
        
        # 创建错误上下文
        context = ErrorContext(
            node_name=node_name,
            error=error,
            attempt=attempt,
            timestamp=datetime.now(),
            state=state,
            metadata=metadata or {}
        )
        
        # 检查是否有特定的错误处理器
        for exception_type, handler in self.error_handlers.items():
            if isinstance(error, exception_type):
                try:
                    action = handler(context)
                    logger.info(f"错误处理器返回动作: {action} for {node_name}")
                    return action
                except Exception as handler_error:
                    logger.error(f"错误处理器执行失败: {handler_error}")
        
        # 默认错误处理逻辑
        return await self._default_error_handling(context)
    
    async def _default_error_handling(self, context: ErrorContext) -> ErrorAction:
        """默认错误处理逻辑"""
        error_type = type(context.error).__name__
        
        # 获取重试策略
        retry_policy = self.retry_policies.get(
            context.node_name, 
            self.default_retry_policy
        )
        
        # 检查是否应该重试
        if (context.attempt < retry_policy.max_retries and 
            any(isinstance(context.error, exc_type) 
                for exc_type in retry_policy.retry_on_exceptions)):
            
            # 计算延迟
            delay = retry_policy.calculate_delay(context.attempt)
            if delay > 0:
                logger.info(f"节点 {context.node_name} 将在 {delay:.2f}s 后重试 (尝试 {context.attempt + 1}/{retry_policy.max_retries})")
                await asyncio.sleep(delay)
            
            return ErrorAction.RETRY
        
        # 检查是否有降级处理器
        if context.node_name in self.fallback_handlers:
            logger.info(f"节点 {context.node_name} 使用降级处理器")
            return ErrorAction.FALLBACK
        
        # 根据错误类型决定动作
        if isinstance(context.error, (ConnectionError, TimeoutError)):
            return ErrorAction.RETRY if context.attempt < 2 else ErrorAction.SKIP
        elif isinstance(context.error, (ValueError, TypeError)):
            return ErrorAction.SKIP
        else:
            return ErrorAction.ABORT
    
    async def execute_with_retry(self,
                                func: Callable,
                                node_name: str,
                                state: Dict[str, Any],
                                *args, **kwargs) -> Any:
        """带重试的执行函数"""
        
        retry_policy = self.retry_policies.get(node_name, self.default_retry_policy)
        circuit_breaker = self.circuit_breakers.get(node_name)
        
        last_error = None
        
        for attempt in range(retry_policy.max_retries + 1):
            try:
                # 使用断路器（如果存在）
                if circuit_breaker:
                    return await circuit_breaker.call(func, *args, **kwargs)
                else:
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)
                        
            except Exception as error:
                last_error = error
                
                # 处理错误
                action = await self.handle_error(
                    error=error,
                    node_name=node_name,
                    attempt=attempt,
                    state=state
                )
                
                if action == ErrorAction.RETRY:
                    continue
                elif action == ErrorAction.FALLBACK:
                    return await self._execute_fallback(node_name, state, *args, **kwargs)
                elif action == ErrorAction.SKIP:
                    logger.warning(f"跳过节点 {node_name} 的执行")
                    return None
                elif action == ErrorAction.IGNORE:
                    logger.info(f"忽略节点 {node_name} 的错误")
                    return None
                else:  # ABORT
                    logger.error(f"中止节点 {node_name} 的执行")
                    raise error
        
        # 所有重试都失败
        if last_error:
            raise last_error
    
    async def _execute_fallback(self, 
                               node_name: str,
                               state: Dict[str, Any],
                               *args, **kwargs) -> Any:
        """执行降级处理"""
        fallback_handler = self.fallback_handlers.get(node_name)
        if fallback_handler:
            try:
                if asyncio.iscoroutinefunction(fallback_handler):
                    return await fallback_handler(state, *args, **kwargs)
                else:
                    return fallback_handler(state, *args, **kwargs)
            except Exception as e:
                logger.error(f"降级处理器执行失败: {e}")
                raise e
        else:
            logger.warning(f"节点 {node_name} 没有配置降级处理器")
            return None
    
    def _update_error_stats(self, node_name: str, error_type: str):
        """更新错误统计"""
        if node_name not in self.error_stats:
            self.error_stats[node_name] = {}
        
        if error_type not in self.error_stats[node_name]:
            self.error_stats[node_name][error_type] = 0
        
        self.error_stats[node_name][error_type] += 1
    
    def get_error_stats(self) -> Dict[str, Dict[str, int]]:
        """获取错误统计"""
        return self.error_stats.copy()
    
    def reset_error_stats(self):
        """重置错误统计"""
        self.error_stats.clear()

# 全局错误处理器实例
global_error_handler = ErrorHandler()