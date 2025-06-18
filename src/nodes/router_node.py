"""
路由节点 - 负责根据条件选择下一个执行节点
"""
from typing import Dict, Any, Optional, List, Callable, Union
from enum import Enum

from ..core.base import BaseNode
from ..core.types import NodeInput, NodeOutput, NodeType


class RouteCondition(Enum):
    """路由条件类型"""
    ALWAYS = "always"  # 总是路由到指定节点
    EXPRESSION = "expression"  # 基于表达式评估
    FUNCTION = "function"  # 基于函数返回值
    PATTERN = "pattern"  # 基于模式匹配
    LOOP = "loop"  # 循环条件


class RouterNode(BaseNode):
    """路由节点 - 根据条件动态选择下一个节点"""
    
    def __init__(self,
                 name: str,
                 routes: List[Dict[str, Any]],
                 default_route: Optional[str] = None,
                 max_loops: int = 10,
                 **kwargs):
        """
        初始化路由节点
        
        Args:
            name: 节点名称
            routes: 路由配置列表，每个配置包含:
                - condition_type: 条件类型
                - condition: 条件内容（表达式、函数等）
                - target: 目标节点名称
                - metadata: 额外元数据
            default_route: 默认路由（当所有条件都不满足时）
            max_loops: 最大循环次数（防止无限循环）
            **kwargs: 其他配置参数
        """
        super().__init__(name, NodeType.ROUTER, "条件路由", **kwargs)
        self.routes = routes
        self.default_route = default_route
        self.max_loops = max_loops
        self.loop_counter = {}  # 记录每个节点的循环次数
        
    async def execute(self, input_data: NodeInput) -> NodeOutput:
        """执行路由逻辑"""
        context = input_data.context
        previous_output = input_data.previous_output
        
        # 评估上下文，构建评估环境
        eval_context = self._build_eval_context(context, previous_output)
        
        # 遍历路由规则，找到第一个满足条件的
        selected_route = None
        for route in self.routes:
            if self._evaluate_condition(route, eval_context):
                selected_route = route
                break
                
        # 如果没有匹配的路由，使用默认路由
        if not selected_route:
            if self.default_route:
                selected_route = {
                    "target": self.default_route,
                    "condition_type": RouteCondition.ALWAYS.value,
                    "metadata": {"reason": "default"}
                }
            else:
                # 没有默认路由，结束执行
                return NodeOutput(
                    data={
                        "message": "没有匹配的路由条件",
                        "evaluated_routes": len(self.routes)
                    },
                    next_node=None,
                    should_continue=False,
                    metadata={"router": self.name}
                )
                
        # 检查循环次数
        target_node = selected_route["target"]
        if selected_route.get("condition_type") == RouteCondition.LOOP.value:
            self.loop_counter[target_node] = self.loop_counter.get(target_node, 0) + 1
            if self.loop_counter[target_node] >= self.max_loops:
                # 达到最大循环次数，选择备用路由
                fallback = selected_route.get("fallback")
                if fallback:
                    target_node = fallback
                else:
                    return NodeOutput(
                        data={
                            "message": f"达到最大循环次数 {self.max_loops}",
                            "loop_node": target_node
                        },
                        next_node=None,
                        should_continue=False,
                        metadata={"router": self.name, "max_loops_reached": True}
                    )
        
        # 构建输出
        return NodeOutput(
            data={
                "selected_route": target_node,
                "condition_type": selected_route.get("condition_type"),
                "reason": selected_route.get("metadata", {}).get("reason", "条件匹配"),
                "loop_count": self.loop_counter.get(target_node, 0)
            },
            next_node=target_node,
            should_continue=True,
            metadata={
                "router": self.name,
                "route_info": selected_route
            }
        )
        
    def _build_eval_context(self, context: Any, previous_output: Any) -> Dict[str, Any]:
        """构建评估上下文"""
        eval_ctx = {
            "context": context,
            "previous_output": previous_output,
            "messages": context.messages if hasattr(context, 'messages') else [],
            "variables": context.variables if hasattr(context, 'variables') else {},
            "loop_counter": self.loop_counter
        }
        
        # 添加便捷访问的属性
        if previous_output and isinstance(previous_output, dict):
            eval_ctx.update({
                "has_error": previous_output.get("error") is not None,
                "has_result": previous_output.get("result") is not None,
                "success": previous_output.get("success", False),
                "continue": previous_output.get("continue", True)
            })
            
        return eval_ctx
        
    def _evaluate_condition(self, route: Dict[str, Any], eval_context: Dict[str, Any]) -> bool:
        """评估路由条件"""
        condition_type = route.get("condition_type", RouteCondition.ALWAYS.value)
        condition = route.get("condition")
        
        try:
            if condition_type == RouteCondition.ALWAYS.value:
                return True
                
            elif condition_type == RouteCondition.EXPRESSION.value:
                # 评估Python表达式
                if isinstance(condition, str):
                    # 安全的表达式评估
                    allowed_names = {
                        "True": True,
                        "False": False,
                        "None": None,
                        "len": len,
                        "str": str,
                        "int": int,
                        "float": float,
                        "bool": bool
                    }
                    # 合并评估上下文
                    eval_env = {**allowed_names, **eval_context}
                    return eval(condition, {"__builtins__": {}}, eval_env)
                return False
                
            elif condition_type == RouteCondition.FUNCTION.value:
                # 调用函数
                if callable(condition):
                    return condition(eval_context)
                return False
                
            elif condition_type == RouteCondition.PATTERN.value:
                # 模式匹配
                if isinstance(condition, dict):
                    return self._match_pattern(condition, eval_context)
                return False
                
            elif condition_type == RouteCondition.LOOP.value:
                # 循环条件
                loop_config = condition if isinstance(condition, dict) else {}
                max_loops = loop_config.get("max", self.max_loops)
                current_loops = self.loop_counter.get(route["target"], 0)
                
                # 检查循环条件
                if "while" in loop_config:
                    # while条件
                    while_condition = loop_config["while"]
                    if isinstance(while_condition, str):
                        eval_env = {**eval_context, "loop_count": current_loops}
                        should_continue = eval(while_condition, {"__builtins__": {}}, eval_env)
                        return should_continue and current_loops < max_loops
                    
                # 默认循环条件：未达到最大次数
                return current_loops < max_loops
                
        except Exception as e:
            # 条件评估失败，返回False
            import logging
            logging.warning(f"路由条件评估失败: {e}")
            return False
            
        return False
        
    def _match_pattern(self, pattern: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """模式匹配"""
        for key, expected_value in pattern.items():
            actual_value = self._get_nested_value(context, key)
            
            if isinstance(expected_value, dict) and "$in" in expected_value:
                # 包含检查
                if actual_value not in expected_value["$in"]:
                    return False
            elif isinstance(expected_value, dict) and "$regex" in expected_value:
                # 正则匹配
                import re
                if not re.match(expected_value["$regex"], str(actual_value)):
                    return False
            elif isinstance(expected_value, dict) and "$gt" in expected_value:
                # 大于检查
                if not (actual_value > expected_value["$gt"]):
                    return False
            elif isinstance(expected_value, dict) and "$lt" in expected_value:
                # 小于检查
                if not (actual_value < expected_value["$lt"]):
                    return False
            else:
                # 直接相等检查
                if actual_value != expected_value:
                    return False
                    
        return True
        
    def _get_nested_value(self, obj: Any, path: str) -> Any:
        """获取嵌套对象的值"""
        keys = path.split('.')
        current = obj
        
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            elif hasattr(current, key):
                current = getattr(current, key)
            else:
                return None
                
        return current
        
    def reset_loop_counter(self, node_name: Optional[str] = None):
        """重置循环计数器"""
        if node_name:
            self.loop_counter.pop(node_name, None)
        else:
            self.loop_counter.clear()


# 便捷函数：创建常用的路由配置
def create_conditional_route(condition: str, target: str, fallback: Optional[str] = None) -> Dict[str, Any]:
    """创建条件路由"""
    route = {
        "condition_type": RouteCondition.EXPRESSION.value,
        "condition": condition,
        "target": target,
        "metadata": {"created_by": "conditional_route"}
    }
    if fallback:
        route["fallback"] = fallback
    return route


def create_loop_route(target: str, 
                     while_condition: str,
                     max_loops: int = 5,
                     fallback: Optional[str] = None) -> Dict[str, Any]:
    """创建循环路由"""
    return {
        "condition_type": RouteCondition.LOOP.value,
        "condition": {
            "while": while_condition,
            "max": max_loops
        },
        "target": target,
        "fallback": fallback,
        "metadata": {"created_by": "loop_route"}
    }


def create_pattern_route(pattern: Dict[str, Any], target: str) -> Dict[str, Any]:
    """创建模式匹配路由"""
    return {
        "condition_type": RouteCondition.PATTERN.value,
        "condition": pattern,
        "target": target,
        "metadata": {"created_by": "pattern_route"}
    } 