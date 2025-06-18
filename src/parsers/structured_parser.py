"""
结构化输出解析器 - 将LLM输出解析为结构化数据
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

from typing import Type, TypeVar, Dict, Any, Optional, List
from pydantic import BaseModel, ValidationError
import json
import re

from core.base import BaseParser
from .json_parser import JSONParser


T = TypeVar('T', bound=BaseModel)


class StructuredOutputParser(BaseParser[T]):
    """结构化输出解析器"""
    
    def __init__(self, 
                 pydantic_model: Type[T],
                 json_parser: Optional[JSONParser] = None):
        """
        初始化结构化输出解析器
        
        Args:
            pydantic_model: Pydantic模型类
            json_parser: JSON解析器实例
        """
        self.pydantic_model = pydantic_model
        self.json_parser = json_parser or JSONParser()
        
    def parse(self, text: str) -> T:
        """解析文本为结构化数据"""
        # 首先尝试解析JSON
        try:
            data = self.json_parser.parse(text)
            return self.pydantic_model(**data)
        except (ValueError, ValidationError):
            pass
            
        # 尝试从文本中提取字段
        data = self._extract_fields_from_text(text)
        
        try:
            return self.pydantic_model(**data)
        except ValidationError as e:
            # 尝试使用默认值填充缺失字段
            data = self._fill_with_defaults(data)
            return self.pydantic_model(**data)
            
    async def aparse(self, text: str) -> T:
        """异步解析"""
        return self.parse(text)
        
    def _extract_fields_from_text(self, text: str) -> Dict[str, Any]:
        """从文本中提取字段"""
        data = {}
        
        # 获取模型的所有字段
        fields = self.pydantic_model.model_fields
        
        for field_name, field_info in fields.items():
            # 尝试不同的模式来提取字段值
            patterns = [
                rf"{field_name}:\s*([^\n]+)",  # field_name: value
                rf"{field_name}\s*=\s*([^\n]+)",  # field_name = value
                rf"{field_name}:\s*```(?:.*?)\n(.*?)\n```",  # field_name: ```value```
                rf"\*\*{field_name}\*\*:\s*([^\n]+)",  # **field_name**: value
                rf"#{1,3}\s*{field_name}[:\s]*([^\n]+)",  # # field_name: value
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if match:
                    value_str = match.group(1).strip()
                    # 尝试解析值
                    value = self._parse_value(value_str, field_info)
                    if value is not None:
                        data[field_name] = value
                        break
                        
        return data
        
    def _parse_value(self, value_str: str, field_info: Any) -> Any:
        """解析字段值"""
        # 获取字段类型
        field_type = field_info.annotation
        
        # 处理可选类型
        if hasattr(field_type, '__origin__'):
            if field_type.__origin__ is type(Optional):
                # 获取实际类型
                field_type = field_type.__args__[0]
                
        # 根据类型解析值
        if field_type == str:
            # 移除引号
            if value_str.startswith('"') and value_str.endswith('"'):
                return value_str[1:-1]
            elif value_str.startswith("'") and value_str.endswith("'"):
                return value_str[1:-1]
            return value_str
            
        elif field_type == int:
            try:
                return int(value_str)
            except:
                return None
                
        elif field_type == float:
            try:
                return float(value_str)
            except:
                return None
                
        elif field_type == bool:
            lower_val = value_str.lower()
            if lower_val in ['true', 'yes', '1', '是', '对']:
                return True
            elif lower_val in ['false', 'no', '0', '否', '错']:
                return False
            return None
            
        elif field_type == list or (hasattr(field_type, '__origin__') and field_type.__origin__ == list):
            # 尝试解析JSON数组
            try:
                return json.loads(value_str)
            except:
                # 尝试解析逗号分隔的列表
                if ',' in value_str:
                    return [item.strip() for item in value_str.split(',')]
                # 尝试解析换行分隔的列表
                elif '\n' in value_str:
                    return [item.strip() for item in value_str.split('\n') if item.strip()]
                return [value_str]
                
        elif field_type == dict or (hasattr(field_type, '__origin__') and field_type.__origin__ == dict):
            # 尝试解析JSON对象
            try:
                return json.loads(value_str)
            except:
                return {}
                
        else:
            # 对于其他类型，尝试JSON解析
            try:
                return json.loads(value_str)
            except:
                return value_str
                
    def _fill_with_defaults(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """使用默认值填充缺失字段"""
        fields = self.pydantic_model.model_fields
        
        for field_name, field_info in fields.items():
            if field_name not in data:
                # 检查是否有默认值
                if field_info.default is not None:
                    data[field_name] = field_info.default
                elif field_info.default_factory is not None:
                    data[field_name] = field_info.default_factory()
                # 对于可选字段，设置为None
                elif not field_info.is_required:
                    data[field_name] = None
                    
        return data
        
    def get_format_instructions(self) -> str:
        """获取格式化指令，告诉LLM如何输出"""
        schema = self.pydantic_model.model_json_schema()
        
        instructions = f"""请按照以下JSON模式格式化你的输出：

```json
{json.dumps(schema, indent=2, ensure_ascii=False)}
```

确保输出是有效的JSON格式，包含所有必需的字段。

示例输出格式：
```json
{{
"""
        
        # 添加字段示例
        fields = self.pydantic_model.model_fields
        field_examples = []
        
        for field_name, field_info in fields.items():
            field_type = field_info.annotation
            
            # 生成示例值
            if field_type == str:
                example = f'"{field_name}的值"'
            elif field_type == int:
                example = "123"
            elif field_type == float:
                example = "123.45"
            elif field_type == bool:
                example = "true"
            elif field_type == list:
                example = '["item1", "item2"]'
            elif field_type == dict:
                example = '{"key": "value"}'
            else:
                example = "null"
                
            field_examples.append(f'    "{field_name}": {example}')
            
        instructions += ",\n".join(field_examples)
        instructions += "\n}\n```"
        
        return instructions
        
    def validate(self, result: T) -> bool:
        """验证解析结果"""
        # Pydantic模型已经进行了验证
        return True 