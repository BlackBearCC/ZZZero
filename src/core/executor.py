"""
状态管理和执行器功能
"""
from typing import Dict, List, Any, Optional, Callable, AsyncIterator

# 状态合并函数类型
StateReducer = Callable[[Any, Any], Any]


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


class StateManager:
    """状态管理器 - 处理状态合并和更新"""
    
    def __init__(self, reducers: Optional[Dict[str, StateReducer]] = None):
        self.reducers = reducers or {}
        
    def merge_state(self, current_state: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        """合并状态更新"""
        result = current_state.copy()
        
        for key, new_value in updates.items():
            if key in self.reducers:
                # 使用自定义合并器
                reducer = self.reducers[key]
                existing_value = result.get(key)
                result[key] = reducer(existing_value, new_value)
            else:
                # 使用默认合并器（直接覆盖）
                result[key] = new_value
                
        return result
    
    def add_reducer(self, key: str, reducer: StateReducer):
        """添加状态合并器"""
        self.reducers[key] = reducer 