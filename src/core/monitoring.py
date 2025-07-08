"""
监控和性能指标模块
"""
import time
import asyncio
import threading
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"

class EventType(Enum):
    """事件类型"""
    NODE_START = "node_start"
    NODE_COMPLETE = "node_complete"
    NODE_ERROR = "node_error"
    GRAPH_START = "graph_start"
    GRAPH_COMPLETE = "graph_complete"
    GRAPH_ERROR = "graph_error"
    STATE_UPDATE = "state_update"
    CHECKPOINT_CREATED = "checkpoint_created"
    RETRY_ATTEMPT = "retry_attempt"

@dataclass
class ExecutionEvent:
    """执行事件"""
    event_id: str
    event_type: EventType
    timestamp: datetime
    node_name: Optional[str] = None
    graph_name: Optional[str] = None
    duration: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat(),
            'node_name': self.node_name,
            'graph_name': self.graph_name,
            'duration': self.duration,
            'metadata': self.metadata,
            'error': self.error
        }

@dataclass
class PerformanceMetric:
    """性能指标"""
    name: str
    metric_type: MetricType
    value: Union[int, float]
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'name': self.name,
            'type': self.metric_type.value,
            'value': self.value,
            'timestamp': self.timestamp.isoformat(),
            'tags': self.tags
        }

@dataclass
class ExecutionTrace:
    """执行轨迹"""
    trace_id: str
    graph_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    events: List[ExecutionEvent] = field(default_factory=list)
    metrics: List[PerformanceMetric] = field(default_factory=list)
    status: str = "running"
    total_nodes: int = 0
    completed_nodes: int = 0
    failed_nodes: int = 0
    
    @property
    def duration(self) -> Optional[float]:
        """计算总持续时间"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    @property
    def success_rate(self) -> float:
        """计算成功率"""
        if self.total_nodes == 0:
            return 0.0
        return (self.completed_nodes / self.total_nodes) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'trace_id': self.trace_id,
            'graph_name': self.graph_name,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'status': self.status,
            'duration': self.duration,
            'total_nodes': self.total_nodes,
            'completed_nodes': self.completed_nodes,
            'failed_nodes': self.failed_nodes,
            'success_rate': self.success_rate,
            'events': [event.to_dict() for event in self.events],
            'metrics': [metric.to_dict() for metric in self.metrics]
        }

class MetricsCollector:
    """指标收集器"""
    
    def __init__(self, max_metrics: int = 10000):
        self.max_metrics = max_metrics
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_metrics))
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.timers: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()
    
    def increment_counter(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
        """增加计数器"""
        with self._lock:
            full_name = self._build_metric_name(name, tags)
            self.counters[full_name] += value
            
            metric = PerformanceMetric(
                name=name,
                metric_type=MetricType.COUNTER,
                value=self.counters[full_name],
                timestamp=datetime.now(),
                tags=tags or {}
            )
            self.metrics[full_name].append(metric)
    
    def set_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """设置仪表值"""
        with self._lock:
            full_name = self._build_metric_name(name, tags)
            self.gauges[full_name] = value
            
            metric = PerformanceMetric(
                name=name,
                metric_type=MetricType.GAUGE,
                value=value,
                timestamp=datetime.now(),
                tags=tags or {}
            )
            self.metrics[full_name].append(metric)
    
    def record_histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """记录直方图值"""
        with self._lock:
            full_name = self._build_metric_name(name, tags)
            self.histograms[full_name].append(value)
            
            metric = PerformanceMetric(
                name=name,
                metric_type=MetricType.HISTOGRAM,
                value=value,
                timestamp=datetime.now(),
                tags=tags or {}
            )
            self.metrics[full_name].append(metric)
    
    def record_timer(self, name: str, duration: float, tags: Optional[Dict[str, str]] = None):
        """记录计时器值"""
        with self._lock:
            full_name = self._build_metric_name(name, tags)
            self.timers[full_name].append(duration)
            
            metric = PerformanceMetric(
                name=name,
                metric_type=MetricType.TIMER,
                value=duration,
                timestamp=datetime.now(),
                tags=tags or {}
            )
            self.metrics[full_name].append(metric)
    
    def get_metric_stats(self, name: str, tags: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """获取指标统计"""
        full_name = self._build_metric_name(name, tags)
        
        with self._lock:
            if full_name in self.counters:
                return {
                    'type': 'counter',
                    'value': self.counters[full_name],
                    'count': len(self.metrics[full_name])
                }
            
            elif full_name in self.gauges:
                return {
                    'type': 'gauge',
                    'value': self.gauges[full_name],
                    'count': len(self.metrics[full_name])
                }
            
            elif full_name in self.histograms:
                values = self.histograms[full_name]
                return {
                    'type': 'histogram',
                    'count': len(values),
                    'min': min(values) if values else 0,
                    'max': max(values) if values else 0,
                    'avg': sum(values) / len(values) if values else 0,
                    'p50': self._percentile(values, 50),
                    'p95': self._percentile(values, 95),
                    'p99': self._percentile(values, 99)
                }
            
            elif full_name in self.timers:
                values = self.timers[full_name]
                return {
                    'type': 'timer',
                    'count': len(values),
                    'min': min(values) if values else 0,
                    'max': max(values) if values else 0,
                    'avg': sum(values) / len(values) if values else 0,
                    'p50': self._percentile(values, 50),
                    'p95': self._percentile(values, 95),
                    'p99': self._percentile(values, 99)
                }
        
        return {}
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有指标"""
        result = {}
        
        with self._lock:
            all_metric_names = set()
            all_metric_names.update(self.counters.keys())
            all_metric_names.update(self.gauges.keys())
            all_metric_names.update(self.histograms.keys())
            all_metric_names.update(self.timers.keys())
            
            for metric_name in all_metric_names:
                stats = self.get_metric_stats(metric_name)
                if stats:
                    result[metric_name] = stats
        
        return result
    
    def _build_metric_name(self, name: str, tags: Optional[Dict[str, str]]) -> str:
        """构建指标全名"""
        if not tags:
            return name
        
        tag_str = ','.join([f"{k}={v}" for k, v in sorted(tags.items())])
        return f"{name}[{tag_str}]"
    
    def _percentile(self, values: List[float], percentile: int) -> float:
        """计算百分位数"""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = (percentile / 100.0) * (len(sorted_values) - 1)
        
        if index.is_integer():
            return sorted_values[int(index)]
        else:
            lower = sorted_values[int(index)]
            upper = sorted_values[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))

class ExecutionMonitor:
    """执行监控器"""
    
    def __init__(self, 
                 enable_metrics: bool = True,
                 enable_tracing: bool = True,
                 max_traces: int = 1000,
                 export_interval: int = 60):
        self.enable_metrics = enable_metrics
        self.enable_tracing = enable_tracing
        self.max_traces = max_traces
        self.export_interval = export_interval
        
        # 组件
        self.metrics_collector = MetricsCollector() if enable_metrics else None
        self.traces: Dict[str, ExecutionTrace] = {}
        self.trace_history: deque = deque(maxlen=max_traces)
        
        # 当前活跃的轨迹
        self.current_traces: Dict[str, ExecutionTrace] = {}
        
        # 事件回调
        self.event_callbacks: List[Callable[[ExecutionEvent], None]] = []
        
        # 导出器
        self.exporters: List[Callable[[Dict[str, Any]], None]] = []
        
        # 定时导出任务
        self._export_task = None
        self._running = False
        
        # 线程锁
        self._lock = threading.Lock()
    
    async def start(self):
        """启动监控器"""
        self._running = True
        if self.export_interval > 0:
            self._export_task = asyncio.create_task(self._export_loop())
        logger.info("执行监控器已启动")
    
    async def stop(self):
        """停止监控器"""
        self._running = False
        if self._export_task:
            self._export_task.cancel()
            try:
                await self._export_task
            except asyncio.CancelledError:
                pass
        logger.info("执行监控器已停止")
    
    def start_trace(self, trace_id: str, graph_name: str) -> ExecutionTrace:
        """开始执行轨迹"""
        if not self.enable_tracing:
            return None
        
        with self._lock:
            trace = ExecutionTrace(
                trace_id=trace_id,
                graph_name=graph_name,
                start_time=datetime.now(),
                status="running"
            )
            
            self.current_traces[trace_id] = trace
            
            # 记录开始事件
            self.record_event(
                trace_id=trace_id,
                event_type=EventType.GRAPH_START,
                graph_name=graph_name
            )
            
            # 记录指标
            if self.metrics_collector:
                self.metrics_collector.increment_counter(
                    "graph_executions_total",
                    tags={"graph": graph_name}
                )
                self.metrics_collector.set_gauge(
                    "active_graphs",
                    len(self.current_traces)
                )
            
            return trace
    
    def complete_trace(self, trace_id: str, status: str = "completed"):
        """完成执行轨迹"""
        if not self.enable_tracing or trace_id not in self.current_traces:
            return
        
        with self._lock:
            trace = self.current_traces[trace_id]
            trace.end_time = datetime.now()
            trace.status = status
            
            # 记录完成事件
            self.record_event(
                trace_id=trace_id,
                event_type=EventType.GRAPH_COMPLETE,
                graph_name=trace.graph_name,
                duration=trace.duration
            )
            
            # 移动到历史记录
            self.trace_history.append(trace)
            del self.current_traces[trace_id]
            
            # 记录指标
            if self.metrics_collector:
                self.metrics_collector.record_timer(
                    "graph_execution_duration",
                    trace.duration or 0,
                    tags={"graph": trace.graph_name, "status": status}
                )
                self.metrics_collector.set_gauge(
                    "active_graphs",
                    len(self.current_traces)
                )
    
    def record_event(self, 
                    trace_id: str,
                    event_type: EventType,
                    node_name: Optional[str] = None,
                    graph_name: Optional[str] = None,
                    duration: Optional[float] = None,
                    metadata: Optional[Dict[str, Any]] = None,
                    error: Optional[str] = None):
        """记录事件"""
        if not self.enable_tracing:
            return
        
        event = ExecutionEvent(
            event_id=f"{trace_id}_{len(self.current_traces.get(trace_id, ExecutionTrace('', '', datetime.now())).events)}",
            event_type=event_type,
            timestamp=datetime.now(),
            node_name=node_name,
            graph_name=graph_name,
            duration=duration,
            metadata=metadata or {},
            error=error
        )
        
        with self._lock:
            if trace_id in self.current_traces:
                trace = self.current_traces[trace_id]
                trace.events.append(event)
                
                # 更新统计
                if event_type == EventType.NODE_START:
                    trace.total_nodes += 1
                elif event_type == EventType.NODE_COMPLETE:
                    trace.completed_nodes += 1
                elif event_type == EventType.NODE_ERROR:
                    trace.failed_nodes += 1
        
        # 调用事件回调
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"事件回调执行失败: {e}")
        
        # 记录指标
        if self.metrics_collector:
            self.metrics_collector.increment_counter(
                f"events_{event_type.value}_total",
                tags={"graph": graph_name, "node": node_name} if node_name else {"graph": graph_name}
            )
    
    def add_event_callback(self, callback: Callable[[ExecutionEvent], None]):
        """添加事件回调"""
        self.event_callbacks.append(callback)
    
    def add_exporter(self, exporter: Callable[[Dict[str, Any]], None]):
        """添加导出器"""
        self.exporters.append(exporter)
    
    def get_trace(self, trace_id: str) -> Optional[ExecutionTrace]:
        """获取轨迹"""
        with self._lock:
            if trace_id in self.current_traces:
                return self.current_traces[trace_id]
            
            for trace in self.trace_history:
                if trace.trace_id == trace_id:
                    return trace
        
        return None
    
    def get_active_traces(self) -> List[ExecutionTrace]:
        """获取活跃轨迹"""
        with self._lock:
            return list(self.current_traces.values())
    
    def get_trace_history(self, limit: Optional[int] = None) -> List[ExecutionTrace]:
        """获取历史轨迹"""
        with self._lock:
            traces = list(self.trace_history)
            if limit:
                traces = traces[-limit:]
            return traces
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """获取指标摘要"""
        if not self.metrics_collector:
            return {}
        
        return {
            "timestamp": datetime.now().isoformat(),
            "active_traces": len(self.current_traces),
            "total_traces": len(self.trace_history),
            "metrics": self.metrics_collector.get_all_metrics()
        }
    
    def export_data(self) -> Dict[str, Any]:
        """导出数据"""
        return {
            "timestamp": datetime.now().isoformat(),
            "active_traces": [trace.to_dict() for trace in self.get_active_traces()],
            "recent_traces": [trace.to_dict() for trace in self.get_trace_history(limit=10)],
            "metrics": self.get_metrics_summary()
        }
    
    async def _export_loop(self):
        """导出循环"""
        while self._running:
            try:
                await asyncio.sleep(self.export_interval)
                
                if not self._running:
                    break
                
                # 导出数据
                data = self.export_data()
                
                for exporter in self.exporters:
                    try:
                        exporter(data)
                    except Exception as e:
                        logger.error(f"数据导出失败: {e}")
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"导出循环异常: {e}")
                await asyncio.sleep(1)

class FileExporter:
    """文件导出器"""
    
    def __init__(self, output_dir: str = "./workspace/monitoring"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def __call__(self, data: Dict[str, Any]):
        """导出数据到文件"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"monitoring_{timestamp}.json"
            filepath = self.output_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # 保持文件数量限制
            self._cleanup_old_files()
            
        except Exception as e:
            logger.error(f"文件导出失败: {e}")
    
    def _cleanup_old_files(self, max_files: int = 100):
        """清理旧文件"""
        try:
            files = list(self.output_dir.glob("monitoring_*.json"))
            files.sort(key=lambda x: x.stat().st_mtime)
            
            while len(files) > max_files:
                oldest_file = files.pop(0)
                oldest_file.unlink()
                
        except Exception as e:
            logger.error(f"清理旧文件失败: {e}")

class ConsoleExporter:
    """控制台导出器"""
    
    def __init__(self, log_level: int = logging.INFO):
        self.logger = logging.getLogger("ExecutionMonitor")
        self.logger.setLevel(log_level)
    
    def __call__(self, data: Dict[str, Any]):
        """导出数据到控制台"""
        try:
            summary = data.get("metrics", {})
            active_traces = len(data.get("active_traces", []))
            total_traces = summary.get("total_traces", 0)
            
            self.logger.info(f"监控摘要 - 活跃轨迹: {active_traces}, 总轨迹: {total_traces}")
            
            # 打印关键指标
            metrics = summary.get("metrics", {})
            for metric_name, metric_data in metrics.items():
                if "graph_execution_duration" in metric_name:
                    avg_duration = metric_data.get("avg", 0)
                    self.logger.info(f"平均执行时间: {avg_duration:.2f}s ({metric_name})")
                    
        except Exception as e:
            logger.error(f"控制台导出失败: {e}")

# 全局监控器实例
global_monitor = ExecutionMonitor()

# 上下文管理器，用于简化轨迹管理
class TraceContext:
    """轨迹上下文管理器"""
    
    def __init__(self, trace_id: str, graph_name: str, monitor: ExecutionMonitor = None):
        self.trace_id = trace_id
        self.graph_name = graph_name
        self.monitor = monitor or global_monitor
        self.trace = None
    
    async def __aenter__(self):
        self.trace = self.monitor.start_trace(self.trace_id, self.graph_name)
        return self.trace
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        status = "failed" if exc_type else "completed"
        self.monitor.complete_trace(self.trace_id, status)
        
        if exc_type:
            self.monitor.record_event(
                trace_id=self.trace_id,
                event_type=EventType.GRAPH_ERROR,
                graph_name=self.graph_name,
                error=str(exc_val)
            )

# 装饰器，用于简化节点监控
def monitor_node(node_name: str, trace_id: str = None, monitor: ExecutionMonitor = None):
    """节点监控装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            _monitor = monitor or global_monitor
            _trace_id = trace_id or getattr(args[0], 'trace_id', 'default')
            
            start_time = time.time()
            
            # 记录开始事件
            _monitor.record_event(
                trace_id=_trace_id,
                event_type=EventType.NODE_START,
                node_name=node_name
            )
            
            try:
                result = await func(*args, **kwargs)
                
                duration = time.time() - start_time
                
                # 记录完成事件
                _monitor.record_event(
                    trace_id=_trace_id,
                    event_type=EventType.NODE_COMPLETE,
                    node_name=node_name,
                    duration=duration
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                # 记录错误事件
                _monitor.record_event(
                    trace_id=_trace_id,
                    event_type=EventType.NODE_ERROR,
                    node_name=node_name,
                    duration=duration,
                    error=str(e)
                )
                
                raise e
        
        return wrapper
    return decorator