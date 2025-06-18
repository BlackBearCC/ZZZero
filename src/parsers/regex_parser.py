"""
正则表达式解析器 - 使用正则表达式提取信息
"""
import re
from typing import Dict, List, Any, Pattern, Union, Optional

from ..core.base import BaseParser


class RegexParser(BaseParser[Dict[str, Any]]):
    """正则表达式解析器"""
    
    def __init__(self, 
                 patterns: Dict[str, Union[str, Pattern]],
                 flags: int = 0):
        """
        初始化正则表达式解析器
        
        Args:
            patterns: 模式字典，键为字段名，值为正则表达式
            flags: 正则表达式标志
        """
        self.patterns = {}
        self.flags = flags
        
        # 编译正则表达式
        for key, pattern in patterns.items():
            if isinstance(pattern, str):
                self.patterns[key] = re.compile(pattern, flags)
            else:
                self.patterns[key] = pattern
                
    def parse(self, text: str) -> Dict[str, Any]:
        """解析文本"""
        result = {}
        
        for field_name, pattern in self.patterns.items():
            match = pattern.search(text)
            if match:
                # 如果有分组，使用分组
                if match.groups():
                    if len(match.groups()) == 1:
                        result[field_name] = match.group(1)
                    else:
                        result[field_name] = match.groups()
                else:
                    # 没有分组，使用整个匹配
                    result[field_name] = match.group(0)
                    
        return result
        
    async def aparse(self, text: str) -> Dict[str, Any]:
        """异步解析"""
        return self.parse(text)
        
    def find_all(self, text: str) -> Dict[str, List[Any]]:
        """查找所有匹配项"""
        result = {}
        
        for field_name, pattern in self.patterns.items():
            matches = pattern.findall(text)
            if matches:
                result[field_name] = matches
                
        return result
        
    def validate(self, result: Dict[str, Any]) -> bool:
        """验证解析结果"""
        # 检查是否至少有一个字段被提取
        return len(result) > 0 