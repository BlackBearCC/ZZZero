"""
JSON解析器 - 从文本中提取和解析JSON
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

import json
import re
from typing import Any, Dict, List, Union, Optional

from core.base import BaseParser


class JSONParser(BaseParser[Dict[str, Any]]):
    """JSON解析器"""
    
    def __init__(self, 
                 strict: bool = False,
                 allow_partial: bool = True):
        """
        初始化JSON解析器
        
        Args:
            strict: 是否严格模式，严格模式下必须是完整的JSON
            allow_partial: 是否允许部分匹配（从文本中提取JSON片段）
        """
        self.strict = strict
        self.allow_partial = allow_partial
        
    def parse(self, text: str) -> Dict[str, Any]:
        """解析文本中的JSON"""
        if not text:
            return {}
            
        # 首先尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
            
        if self.strict:
            raise ValueError("文本不是有效的JSON格式")
            
        # 尝试提取JSON片段
        if self.allow_partial:
            json_obj = self._extract_json(text)
            if json_obj:
                return json_obj
                
        # 尝试修复常见的JSON错误
        fixed_json = self._fix_json(text)
        try:
            return json.loads(fixed_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"无法解析JSON: {e}")
            
    async def aparse(self, text: str) -> Dict[str, Any]:
        """异步解析 - JSON解析通常很快，直接调用同步方法"""
        return self.parse(text)
        
    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """从文本中提取JSON片段"""
        # 查找JSON代码块
        json_patterns = [
            r'```json\s*\n(.*?)\n```',  # Markdown JSON代码块
            r'```\s*\n(\{.*?\})\s*\n```',  # Markdown代码块带花括号
            r'```\s*\n(\[.*?\])\s*\n```',  # Markdown代码块带方括号
            r'(\{[^{}]*\})',  # 简单的对象
            r'(\[[^\[\]]*\])',  # 简单的数组
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match)
                except:
                    continue
                    
        # 尝试更复杂的嵌套结构
        json_obj = self._extract_nested_json(text)
        if json_obj:
            return json_obj
            
        return None
        
    def _extract_nested_json(self, text: str) -> Optional[Dict[str, Any]]:
        """提取嵌套的JSON结构"""
        # 找到第一个{或[
        start = -1
        for i, char in enumerate(text):
            if char in '{[':
                start = i
                break
                
        if start == -1:
            return None
            
        # 使用栈来匹配括号
        stack = []
        end = -1
        
        for i in range(start, len(text)):
            char = text[i]
            if char in '{[':
                stack.append(char)
            elif char in '}]':
                if not stack:
                    continue
                opening = stack.pop()
                # 检查括号匹配
                if (char == '}' and opening != '{') or (char == ']' and opening != '['):
                    return None
                # 如果栈空了，说明找到了完整的JSON
                if not stack:
                    end = i + 1
                    break
                    
        if end != -1:
            json_str = text[start:end]
            try:
                return json.loads(json_str)
            except:
                pass
                
        return None
        
    def _fix_json(self, text: str) -> str:
        """尝试修复常见的JSON错误"""
        # 移除注释
        text = re.sub(r'//.*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        
        # 修复尾随逗号
        text = re.sub(r',\s*}', '}', text)
        text = re.sub(r',\s*]', ']', text)
        
        # 修复单引号
        # 这个比较危险，可能会破坏包含单引号的字符串
        # text = text.replace("'", '"')
        
        # 确保属性名有引号
        text = re.sub(r'(\w+):', r'"\1":', text)
        
        # 修复布尔值和null
        text = re.sub(r'\btrue\b', 'true', text, flags=re.IGNORECASE)
        text = re.sub(r'\bfalse\b', 'false', text, flags=re.IGNORECASE)
        text = re.sub(r'\bnull\b', 'null', text, flags=re.IGNORECASE)
        
        return text
        
    def validate(self, result: Dict[str, Any]) -> bool:
        """验证解析结果"""
        # 检查是否为空
        if not result:
            return False
            
        # 可以添加更多验证逻辑
        return True 