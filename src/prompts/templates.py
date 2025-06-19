"""
提示模板实现
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

from typing import List, Dict, Any, Optional
import re
from jinja2 import Template

from core.base import BasePromptTemplate


class JinjaPromptTemplate(BasePromptTemplate):
    """基于Jinja2的提示模板"""
    
    def __init__(self, template: str, **default_variables):
        super().__init__(template, **default_variables)
        self.jinja_template = Template(template)
        
    def format(self, **kwargs) -> str:
        """格式化模板"""
        # 合并默认变量和传入变量
        variables = {**self.variables, **kwargs}
        
        # 验证变量
        if not self.validate_variables(**variables):
            missing = set(self.get_variables()) - set(variables.keys())
            raise ValueError(f"缺少必需的变量: {missing}")
            
        # 使用Jinja2渲染
        return self.jinja_template.render(**variables)
        
    def get_variables(self) -> List[str]:
        """获取模板变量列表"""
        # 使用正则表达式提取Jinja2变量
        pattern = r'\{\{\s*(\w+)\s*\}\}'
        variables = re.findall(pattern, self.template)
        return list(set(variables))
