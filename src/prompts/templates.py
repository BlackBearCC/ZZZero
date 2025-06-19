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


class ThinkingPromptTemplate(JinjaPromptTemplate):
    """思考提示模板"""
    
    DEFAULT_TEMPLATE = """【思考阶段】

用户问题: {{ query }}

{% if previous_thought %}
之前的思考: {{ previous_thought }}
{% endif %}

{% if previous_action %}
之前的行动结果: {{ previous_action }}
{% endif %}

请进行深入的推理分析：

1. **问题理解**：
   - 这个问题的核心是什么？
   - 用户真正想要什么信息或解决方案？
   - 问题的复杂程度如何？

2. **信息评估**：
   - 基于我的知识，我能直接回答这个问题吗？
   - 还缺少哪些关键信息？
   - 需要外部数据或工具支持吗？

3. **解决策略**：
   - 如果信息充足：可以直接进入最终回答
   - 如果信息不足：需要通过什么方式获取信息？
   - 应该采取什么步骤来解决问题？

4. **下一步决策**：
   - 选择"行动"获取更多信息
   - 或者选择"最终回答"直接解决问题

注意：此阶段专注于分析和推理，暂不考虑具体工具细节。

请给出清晰的思考过程和决策。"""
    
    def __init__(self, template: Optional[str] = None):
        super().__init__(template or self.DEFAULT_TEMPLATE)


class ActionPromptTemplate(JinjaPromptTemplate):
    """行动提示模板"""
    
    DEFAULT_TEMPLATE = """基于以下思考结果，选择合适的工具来执行：

思考结果：
{{ thought }}

可用工具：
{{ tools_description }}

请选择最合适的工具来执行下一步行动。输出格式：

```json
{
    "tool": "工具名称",
    "arguments": {
        "参数名": "参数值"
    }
}
```

选择工具时请考虑：
1. 工具是否能获取所需信息
2. 参数是否完整且正确
3. 是否是最高效的选择

如果需要调用多个工具，请返回多个JSON块。"""
    
    def __init__(self, template: Optional[str] = None):
        super().__init__(template or self.DEFAULT_TEMPLATE)


class ObservationPromptTemplate(JinjaPromptTemplate):
    """观察提示模板"""
    
    DEFAULT_TEMPLATE = """分析以下工具执行结果：

执行结果：
{{ results }}

原始问题：{{ query }}

请进行以下分析：

1. **结果评估**：
   - 工具执行是否成功？
   - 返回的信息质量如何？
   - 信息是否相关且有用？

2. **信息整合**：
   - 从结果中获得了哪些关键信息？
   - 这些信息如何帮助解决问题？
   - 是否存在矛盾或需要验证的地方？

3. **下一步决策**：
   - 是否已经收集到足够的信息？
   - 如果不够，还需要什么信息？
   - 建议的下一步行动是什么？

请给出详细的分析和明确的结论。"""
    
    def __init__(self, template: Optional[str] = None):
        super().__init__(template or self.DEFAULT_TEMPLATE)


class FinalizePromptTemplate(JinjaPromptTemplate):
    """最终化提示模板"""
    
    DEFAULT_TEMPLATE = """基于整个执行过程，生成最终答案：

用户问题：{{ query }}

执行轨迹：
{% for step in execution_trace %}
{{ loop.index }}. {{ step.node_type }}:
   - 输出: {{ step.output }}
   - 耗时: {{ step.duration }}s
{% endfor %}

关键发现：
{% for finding in key_findings %}
- {{ finding }}
{% endfor %}

请生成一个：
1. **准确**：基于收集到的信息，确保答案准确
2. **完整**：涵盖用户问题的所有方面
3. **清晰**：使用简洁明了的语言
4. **有用**：提供实际可行的建议或信息

的最终答案。如果有任何不确定的地方，请明确指出。"""
    
    def __init__(self, template: Optional[str] = None):
        super().__init__(template or self.DEFAULT_TEMPLATE) 