"""
工具调用解析器 - 解析LLM输出中的工具调用
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

import re
import json
import uuid
from typing import List, Dict, Any, Optional, Union

from core.base import BaseParser
from core.types import ToolCall
from .json_parser import JSONParser


class ToolCallParser(BaseParser[List[ToolCall]]):
    """工具调用解析器"""
    
    def __init__(self, 
                 formats: Optional[List[str]] = None,
                 json_parser: Optional[JSONParser] = None):
        """
        初始化工具调用解析器
        
        Args:
            formats: 支持的格式列表，默认支持所有格式
            json_parser: JSON解析器实例
        """
        self.formats = formats or ["json", "xml", "markdown", "function"]
        self.json_parser = json_parser or JSONParser()
        
    def parse(self, text: str) -> List[ToolCall]:
        """解析文本中的工具调用"""
        tool_calls = []
        
        # 尝试不同的解析格式
        if "json" in self.formats:
            tool_calls.extend(self._parse_json_format(text))
            
        if "xml" in self.formats:
            tool_calls.extend(self._parse_xml_format(text))
            
        if "markdown" in self.formats:
            tool_calls.extend(self._parse_markdown_format(text))
            
        if "function" in self.formats:
            tool_calls.extend(self._parse_function_format(text))
            
        # 去重
        seen = set()
        unique_calls = []
        for call in tool_calls:
            key = (call.name, json.dumps(call.arguments, sort_keys=True))
            if key not in seen:
                seen.add(key)
                unique_calls.append(call)
                
        return unique_calls
        
    async def aparse(self, text: str) -> List[ToolCall]:
        """异步解析"""
        return self.parse(text)
        
    def _parse_json_format(self, text: str) -> List[ToolCall]:
        """解析JSON格式的工具调用"""
        tool_calls = []
        
        # 尝试解析整个文本作为JSON
        try:
            data = self.json_parser.parse(text)
            
            # 检查是否是工具调用格式
            if isinstance(data, dict):
                if "tool" in data or "name" in data:
                    tool_calls.append(self._create_tool_call(data))
                elif "tool_calls" in data:
                    for call in data["tool_calls"]:
                        tool_calls.append(self._create_tool_call(call))
                        
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and ("tool" in item or "name" in item):
                        tool_calls.append(self._create_tool_call(item))
                        
        except:
            pass
            
        # 查找JSON代码块中的工具调用
        json_blocks = re.findall(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
        for block in json_blocks:
            try:
                data = json.loads(block)
                if isinstance(data, dict) and ("tool" in data or "name" in data):
                    tool_calls.append(self._create_tool_call(data))
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            tool_calls.append(self._create_tool_call(item))
            except:
                continue
                
        return tool_calls
        
    def _parse_xml_format(self, text: str) -> List[ToolCall]:
        """解析XML格式的工具调用"""
        tool_calls = []
        
        # 简单的XML解析
        xml_pattern = r'<tool_call>\s*<name>(.*?)</name>\s*<arguments>(.*?)</arguments>\s*</tool_call>'
        matches = re.findall(xml_pattern, text, re.DOTALL)
        
        for name, args_str in matches:
            try:
                arguments = json.loads(args_str)
                tool_calls.append(ToolCall(
                    id=str(uuid.uuid4()),
                    name=name.strip(),
                    arguments=arguments
                ))
            except:
                # 尝试解析为键值对
                arguments = self._parse_key_value_pairs(args_str)
                if arguments:
                    tool_calls.append(ToolCall(
                        id=str(uuid.uuid4()),
                        name=name.strip(),
                        arguments=arguments
                    ))
                    
        return tool_calls
        
    def _parse_markdown_format(self, text: str) -> List[ToolCall]:
        """解析Markdown格式的工具调用"""
        tool_calls = []
        
        # 查找工具调用标记
        patterns = [
            r'Tool:\s*`([^`]+)`\s*Arguments:\s*```(?:json)?\s*\n(.*?)\n```',
            r'\*\*Tool\*\*:\s*([^\n]+)\s*\*\*Arguments\*\*:\s*```(?:json)?\s*\n(.*?)\n```',
            r'### Tool:\s*([^\n]+)\s*### Arguments:\s*```(?:json)?\s*\n(.*?)\n```',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for name, args_str in matches:
                try:
                    arguments = json.loads(args_str)
                    tool_calls.append(ToolCall(
                        id=str(uuid.uuid4()),
                        name=name.strip(),
                        arguments=arguments
                    ))
                except:
                    continue
                    
        return tool_calls
        
    def _parse_function_format(self, text: str) -> List[ToolCall]:
        """解析函数调用格式的工具调用"""
        tool_calls = []
        
        # 匹配函数调用格式: function_name(arg1=value1, arg2=value2)
        pattern = r'(\w+)\((.*?)\)'
        matches = re.findall(pattern, text)
        
        for name, args_str in matches:
            # 跳过常见的非工具调用
            if name in ['print', 'len', 'str', 'int', 'float', 'bool']:
                continue
                
            arguments = self._parse_function_arguments(args_str)
            if arguments:
                tool_calls.append(ToolCall(
                    id=str(uuid.uuid4()),
                    name=name,
                    arguments=arguments
                ))
                
        return tool_calls
        
    def _parse_function_arguments(self, args_str: str) -> Dict[str, Any]:
        """解析函数参数"""
        arguments = {}
        
        # 尝试解析键值对
        kv_pattern = r'(\w+)\s*=\s*([^,]+)'
        matches = re.findall(kv_pattern, args_str)
        
        for key, value in matches:
            # 尝试解析值
            value = value.strip()
            
            # 字符串
            if value.startswith('"') and value.endswith('"'):
                arguments[key] = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                arguments[key] = value[1:-1]
            # 数字
            elif value.replace('.', '').replace('-', '').isdigit():
                try:
                    arguments[key] = int(value) if '.' not in value else float(value)
                except:
                    arguments[key] = value
            # 布尔值
            elif value.lower() in ['true', 'false']:
                arguments[key] = value.lower() == 'true'
            # null
            elif value.lower() == 'null' or value.lower() == 'none':
                arguments[key] = None
            # 其他
            else:
                arguments[key] = value
                
        return arguments
        
    def _parse_key_value_pairs(self, text: str) -> Dict[str, Any]:
        """解析键值对文本"""
        arguments = {}
        
        # 尝试不同的键值对格式
        patterns = [
            r'(\w+):\s*([^\n,]+)',  # key: value
            r'(\w+)\s*=\s*([^\n,]+)',  # key = value
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for key, value in matches:
                value = value.strip()
                # 尝试解析值类型
                try:
                    # JSON值
                    arguments[key] = json.loads(value)
                except:
                    # 字符串值
                    arguments[key] = value
                    
        return arguments
        
    def _create_tool_call(self, data: Dict[str, Any]) -> ToolCall:
        """从字典创建ToolCall对象"""
        # 提取工具名称
        name = data.get("tool") or data.get("name") or data.get("tool_name")
        if not name:
            raise ValueError("工具名称缺失")
            
        # 提取参数
        arguments = (
            data.get("arguments") or 
            data.get("params") or 
            data.get("parameters") or 
            {}
        )
        
        # 提取ID
        tool_id = data.get("id") or str(uuid.uuid4())
        
        return ToolCall(
            id=tool_id,
            name=name,
            arguments=arguments
        )
        
    def validate(self, result: List[ToolCall]) -> bool:
        """验证解析结果"""
        if not result:
            return False
            
        # 检查每个工具调用是否有效
        for call in result:
            if not call.name:
                return False
                
        return True 