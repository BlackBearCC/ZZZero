"""
状态管理和执行器功能 - 增强版
"""
from typing import Dict, List, Any, Optional, Callable, AsyncIterator, Union, Tuple
from datetime import datetime
import json
import pickle
import hashlib
import uuid
import os
from pathlib import Path
import threading
import asyncio
from dataclasses import dataclass, field
from enum import Enum

# 状态合并函数类型
StateReducer = Callable[[Any, Any], Any]

class CheckpointStorage(Enum):
    """检查点存储类型"""
    MEMORY = "memory"
    FILE = "file"
    DATABASE = "database"

@dataclass
class StateCheckpoint:
    """状态检查点数据结构"""
    id: str
    state: Dict[str, Any]
    node_name: str
    timestamp: datetime
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: int = 1
    hash: Optional[str] = None
    
    def __post_init__(self):
        if not self.hash:
            self.hash = self._calculate_hash()
    
    def _calculate_hash(self) -> str:
        """计算状态哈希值"""
        state_str = json.dumps(self.state, sort_keys=True, default=str)
        return hashlib.md5(state_str.encode()).hexdigest()

@dataclass
class StateVersion:
    """状态版本信息"""
    version: int
    checkpoint_id: str
    timestamp: datetime
    changes: Dict[str, Any]
    previous_version: Optional[int] = None


def default_reducer(existing_value: Any, new_value: Any) -> Any:
    """默认的状态合并器 - 直接覆盖"""
    return new_value


def add_reducer(existing_value: List, new_value: List) -> List:
    """列表追加合并器"""
    if existing_value is None:
        return new_value or []
    if new_value is None:
        return existing_value
    return existing_value + new_value


def merge_reducer(existing_value: Dict, new_value: Dict) -> Dict:
    """字典合并器"""
    if existing_value is None:
        return new_value or {}
    if new_value is None:
        return existing_value
    result = existing_value.copy()
    result.update(new_value)
    return result


def max_reducer(existing_value: Any, new_value: Any) -> Any:
    """最大值合并器"""
    if existing_value is None:
        return new_value
    if new_value is None:
        return existing_value
    return max(existing_value, new_value)


def min_reducer(existing_value: Any, new_value: Any) -> Any:
    """最小值合并器"""
    if existing_value is None:
        return new_value
    if new_value is None:
        return existing_value
    return min(existing_value, new_value)


def count_reducer(existing_value: int, new_value: int) -> int:
    """计数合并器"""
    if existing_value is None:
        existing_value = 0
    if new_value is None:
        new_value = 0
    return existing_value + new_value


def set_reducer(existing_value: set, new_value: set) -> set:
    """集合合并器"""
    if existing_value is None:
        return new_value or set()
    if new_value is None:
        return existing_value
    return existing_value.union(new_value)


def priority_reducer(existing_value: Dict[str, Any], new_value: Dict[str, Any]) -> Dict[str, Any]:
    """基于优先级的合并器"""
    if existing_value is None:
        return new_value or {}
    if new_value is None:
        return existing_value
    
    result = existing_value.copy()
    for key, value in new_value.items():
        if isinstance(value, dict) and 'priority' in value and 'data' in value:
            existing_priority = existing_value.get(key, {}).get('priority', 0)
            new_priority = value.get('priority', 0)
            if new_priority >= existing_priority:
                result[key] = value
        else:
            result[key] = value
    return result


def timestamp_reducer(existing_value: Dict[str, Any], new_value: Dict[str, Any]) -> Dict[str, Any]:
    """基于时间戳的合并器（保留最新的）"""
    if existing_value is None:
        return new_value or {}
    if new_value is None:
        return existing_value
    
    result = existing_value.copy()
    for key, value in new_value.items():
        if isinstance(value, dict) and 'timestamp' in value:
            existing_timestamp = existing_value.get(key, {}).get('timestamp', datetime.min)
            new_timestamp = value.get('timestamp', datetime.now())
            if isinstance(existing_timestamp, str):
                existing_timestamp = datetime.fromisoformat(existing_timestamp)
            if isinstance(new_timestamp, str):
                new_timestamp = datetime.fromisoformat(new_timestamp)
            if new_timestamp >= existing_timestamp:
                result[key] = value
        else:
            result[key] = value
    return result


def strategy_reducer(strategy: str = "latest"):
    """可配置策略的合并器工厂"""
    def reducer(existing_value: Any, new_value: Any) -> Any:
        if strategy == "latest":
            return new_value if new_value is not None else existing_value
        elif strategy == "earliest":
            return existing_value if existing_value is not None else new_value
        elif strategy == "merge" and isinstance(existing_value, dict) and isinstance(new_value, dict):
            return merge_reducer(existing_value, new_value)
        elif strategy == "append" and isinstance(existing_value, list) and isinstance(new_value, list):
            return add_reducer(existing_value, new_value)
        else:
            return new_value if new_value is not None else existing_value
    
    return reducer


class CheckpointManager:
    """检查点管理器 - 支持持久化存储"""
    
    def __init__(self, 
                 storage_type: CheckpointStorage = CheckpointStorage.MEMORY,
                 storage_path: Optional[str] = None,
                 max_checkpoints: int = 100):
        self.storage_type = storage_type
        self.storage_path = Path(storage_path) if storage_path else Path("./workspace/checkpoints")
        self.max_checkpoints = max_checkpoints
        self.checkpoints: Dict[str, StateCheckpoint] = {}
        self._lock = threading.Lock()
        
        if storage_type == CheckpointStorage.FILE:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self._load_checkpoints_from_file()
    
    def save_checkpoint(self, 
                       state: Dict[str, Any], 
                       node_name: str,
                       parent_id: Optional[str] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> str:
        """保存检查点"""
        checkpoint_id = str(uuid.uuid4())
        checkpoint = StateCheckpoint(
            id=checkpoint_id,
            state=state.copy(),
            node_name=node_name,
            timestamp=datetime.now(),
            parent_id=parent_id,
            metadata=metadata or {}
        )
        
        with self._lock:
            self.checkpoints[checkpoint_id] = checkpoint
            
            # 限制检查点数量
            if len(self.checkpoints) > self.max_checkpoints:
                oldest_id = min(self.checkpoints.keys(), 
                              key=lambda k: self.checkpoints[k].timestamp)
                del self.checkpoints[oldest_id]
                if self.storage_type == CheckpointStorage.FILE:
                    self._delete_checkpoint_file(oldest_id)
            
            # 持久化存储
            if self.storage_type == CheckpointStorage.FILE:
                self._save_checkpoint_to_file(checkpoint)
        
        return checkpoint_id
    
    def load_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """加载检查点"""
        with self._lock:
            if checkpoint_id in self.checkpoints:
                return self.checkpoints[checkpoint_id].state.copy()
            
            # 尝试从文件加载
            if self.storage_type == CheckpointStorage.FILE:
                checkpoint = self._load_checkpoint_from_file(checkpoint_id)
                if checkpoint:
                    self.checkpoints[checkpoint_id] = checkpoint
                    return checkpoint.state.copy()
        
        return None
    
    def list_checkpoints(self, 
                        node_name: Optional[str] = None,
                        limit: Optional[int] = None) -> List[StateCheckpoint]:
        """列出检查点"""
        with self._lock:
            checkpoints = list(self.checkpoints.values())
            
            if node_name:
                checkpoints = [cp for cp in checkpoints if cp.node_name == node_name]
            
            checkpoints.sort(key=lambda cp: cp.timestamp, reverse=True)
            
            if limit:
                checkpoints = checkpoints[:limit]
            
            return checkpoints
    
    def _save_checkpoint_to_file(self, checkpoint: StateCheckpoint):
        """保存检查点到文件"""
        try:
            file_path = self.storage_path / f"{checkpoint.id}.pkl"
            with open(file_path, 'wb') as f:
                pickle.dump(checkpoint, f)
        except Exception as e:
            print(f"保存检查点到文件失败: {e}")
    
    def _load_checkpoint_from_file(self, checkpoint_id: str) -> Optional[StateCheckpoint]:
        """从文件加载检查点"""
        try:
            file_path = self.storage_path / f"{checkpoint_id}.pkl"
            if file_path.exists():
                with open(file_path, 'rb') as f:
                    return pickle.load(f)
        except Exception as e:
            print(f"从文件加载检查点失败: {e}")
        return None
    
    def _load_checkpoints_from_file(self):
        """从文件加载所有检查点"""
        if not self.storage_path.exists():
            return
        
        for file_path in self.storage_path.glob("*.pkl"):
            checkpoint_id = file_path.stem
            checkpoint = self._load_checkpoint_from_file(checkpoint_id)
            if checkpoint:
                self.checkpoints[checkpoint_id] = checkpoint
    
    def _delete_checkpoint_file(self, checkpoint_id: str):
        """删除检查点文件"""
        try:
            file_path = self.storage_path / f"{checkpoint_id}.pkl"
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            print(f"删除检查点文件失败: {e}")


class StateManager:
    """状态管理器 - 处理状态合并和更新"""
    
    def __init__(self, 
                 reducers: Optional[Dict[str, StateReducer]] = None,
                 enable_versioning: bool = True,
                 enable_checkpoints: bool = True,
                 checkpoint_storage: CheckpointStorage = CheckpointStorage.MEMORY,
                 checkpoint_path: Optional[str] = None):
        self.reducers = reducers or {}
        self.enable_versioning = enable_versioning
        self.enable_checkpoints = enable_checkpoints
        
        # 版本控制
        if enable_versioning:
            self.versions: Dict[int, StateVersion] = {}
            self.current_version = 0
        
        # 检查点管理
        if enable_checkpoints:
            self.checkpoint_manager = CheckpointManager(
                storage_type=checkpoint_storage,
                storage_path=checkpoint_path
            )
        
        self._lock = threading.Lock()
        
    def merge_state(self, 
                   current_state: Dict[str, Any], 
                   updates: Dict[str, Any],
                   node_name: Optional[str] = None) -> Dict[str, Any]:
        """合并状态更新"""
        with self._lock:
            result = current_state.copy()
            changes = {}
            
            for key, new_value in updates.items():
                old_value = result.get(key)
                
                if key in self.reducers:
                    # 使用自定义合并器
                    reducer = self.reducers[key]
                    merged_value = reducer(old_value, new_value)
                    result[key] = merged_value
                    if merged_value != old_value:
                        changes[key] = merged_value
                else:
                    # 使用默认合并器（直接覆盖）
                    result[key] = new_value
                    if new_value != old_value:
                        changes[key] = new_value
            
            # 版本控制
            if self.enable_versioning and changes:
                self._create_version(changes, node_name)
            
            return result
    
    def merge_state_transactional(self,
                                 current_state: Dict[str, Any],
                                 updates: Dict[str, Any],
                                 node_name: Optional[str] = None) -> Tuple[Dict[str, Any], str]:
        """事务性状态合并（自动创建检查点）"""
        checkpoint_id = None
        
        # 创建检查点
        if self.enable_checkpoints:
            checkpoint_id = self.create_checkpoint(current_state, node_name or "unknown")
        
        try:
            # 合并状态
            new_state = self.merge_state(current_state, updates, node_name)
            return new_state, checkpoint_id
        except Exception as e:
            # 回滚到检查点
            if checkpoint_id:
                self.rollback_to_checkpoint(checkpoint_id)
            raise e
    
    def add_reducer(self, key: str, reducer: StateReducer):
        """添加状态合并器"""
        self.reducers[key] = reducer
    
    def create_checkpoint(self, 
                         state: Dict[str, Any], 
                         node_name: str,
                         metadata: Optional[Dict[str, Any]] = None) -> str:
        """创建状态检查点"""
        if not self.enable_checkpoints:
            return ""
        
        return self.checkpoint_manager.save_checkpoint(
            state=state,
            node_name=node_name,
            metadata=metadata
        )
    
    def restore_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """恢复到指定检查点"""
        if not self.enable_checkpoints:
            return None
        
        return self.checkpoint_manager.load_checkpoint(checkpoint_id)
    
    def rollback_to_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """回滚到指定检查点（别名方法）"""
        return self.restore_checkpoint(checkpoint_id)
    
    def list_checkpoints(self, node_name: Optional[str] = None) -> List[StateCheckpoint]:
        """列出检查点"""
        if not self.enable_checkpoints:
            return []
        
        return self.checkpoint_manager.list_checkpoints(node_name)
    
    def get_state_diff(self, old_state: Dict[str, Any], new_state: Dict[str, Any]) -> Dict[str, Any]:
        """获取状态差异"""
        diff = {}
        for key, value in new_state.items():
            if key not in old_state or old_state[key] != value:
                diff[key] = {
                    'old': old_state.get(key),
                    'new': value,
                    'changed': True
                }
        
        # 检查删除的键
        for key in old_state:
            if key not in new_state:
                diff[key] = {
                    'old': old_state[key],
                    'new': None,
                    'changed': True,
                    'deleted': True
                }
        
        return diff
    
    def _create_version(self, changes: Dict[str, Any], node_name: Optional[str]):
        """创建新版本"""
        if not self.enable_versioning:
            return
        
        self.current_version += 1
        version = StateVersion(
            version=self.current_version,
            checkpoint_id="",  # 如果需要可以关联检查点
            timestamp=datetime.now(),
            changes=changes,
            previous_version=self.current_version - 1 if self.current_version > 1 else None
        )
        self.versions[self.current_version] = version
    
    def get_version_history(self, limit: Optional[int] = None) -> List[StateVersion]:
        """获取版本历史"""
        if not self.enable_versioning:
            return []
        
        versions = list(self.versions.values())
        versions.sort(key=lambda v: v.version, reverse=True)
        
        if limit:
            versions = versions[:limit]
        
        return versions
    
    def get_current_version(self) -> int:
        """获取当前版本号"""
        return self.current_version if self.enable_versioning else 0 