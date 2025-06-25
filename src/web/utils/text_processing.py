"""
文本处理工具 - 表格提取、关键词高亮、文本格式化等
"""
import re
import gradio as gr
from typing import Dict, Any, List, Tuple


class TextProcessor:
    """文本处理工具类"""
    
    @staticmethod
    def extract_tables_from_text(text: str) -> Tuple[str, List[Dict]]:
        """从文本中提取表格数据，返回(处理后的文本, 表格数据列表)"""
        tables_data = []
        
        def parse_table_content(table_content):
            """解析表格内容为DataFrame格式"""
            lines = [line.strip() for line in table_content.split('\n') if line.strip()]
            
            if len(lines) < 3:  # 至少需要表头、分隔线、数据行
                return None
            
            # 解析表头
            header_line = lines[0]
            if not header_line.startswith('|') or not header_line.endswith('|'):
                return None
            
            headers = [h.strip() for h in header_line.split('|')[1:-1]]
            
            # 解析数据行
            data_rows = []
            for line in lines[2:]:  # 跳过表头和分隔线
                if line.startswith('|') and line.endswith('|'):
                    row_data = [cell.strip() for cell in line.split('|')[1:-1]]
                    if len(row_data) == len(headers):  # 确保列数匹配
                        data_rows.append(row_data)
            
            if not data_rows:
                return None
                
            return {
                'headers': headers,
                'data': data_rows
            }
        
        # 1. 处理 ```table 代码块格式
        table_block_pattern = r'```table\s*\n([\s\S]*?)\n```'
        
        def extract_table_block(match):
            table_content = match.group(1).strip()
            table_data = parse_table_content(table_content)
            if table_data:
                tables_data.append(table_data)
                return f"\n📊 **表格 {len(tables_data)}**\n\n"  # 用占位符替换
            return match.group(0)
        
        text = re.sub(table_block_pattern, extract_table_block, text, flags=re.MULTILINE)
        
        # 2. 处理普通markdown表格格式
        table_pattern = r'((?:^\|.*\|[ \t]*$\n?){3,})'  # 至少3行
        
        def extract_markdown_table(match):
            table_content = match.group(1).strip()
            table_data = parse_table_content(table_content)
            if table_data:
                tables_data.append(table_data)
                return f"\n📊 **表格 {len(tables_data)}**\n\n"  # 用占位符替换
            return match.group(0)
        
        text = re.sub(table_pattern, extract_markdown_table, text, flags=re.MULTILINE)
        
        return text, tables_data
    
    @staticmethod
    def highlight_agent_keywords(text: str, is_streaming: bool = False) -> Tuple[str, List[Dict]]:
        """为Agent关键词添加高亮样式，同时提取表格数据，返回(处理后的文本, 表格数据列表)"""
        # 首先提取表格数据
        text, tables_data = TextProcessor.extract_tables_from_text(text)
        
        # 先提取所有代码块，避免在代码块内进行关键词替换
        preserved_blocks = []
        # 匹配代码块等
        preserve_pattern = r'```[\s\S]*?```|`[^`]+`'
        
        def preserve_block(match):
            preserved_blocks.append(match.group())
            return f"__PRESERVED_BLOCK_{len(preserved_blocks) - 1}__"
        
        # 暂时替换所有需要保护的块
        text_without_blocks = re.sub(preserve_pattern, preserve_block, text)
        
        # 定义关键词及其对应的CSS类
        keywords = {
            r'\bQuestion\s*:': 'agent-keyword-question',
            r'\bThought\s*:': 'agent-keyword-thought', 
            r'\bAction\s*:': 'agent-keyword-action',
            r'\bAction\s+Input\s*:': 'agent-keyword-action-input',
            r'\bObservation\s*:': 'agent-keyword-observation',
            r'\bFinal\s+Answer\s*:': 'agent-keyword-final-answer'
        }
        
        # 对每个关键词进行替换（只在非保护块区域）
        for pattern, css_class in keywords.items():
            text_without_blocks = re.sub(
                pattern,
                lambda m: f'<span class="{css_class}">{m.group()}</span>',
                text_without_blocks,
                flags=re.IGNORECASE
            )
        
        # 恢复保护的块
        for i, block in enumerate(preserved_blocks):
            text_without_blocks = text_without_blocks.replace(f"__PRESERVED_BLOCK_{i}__", block)
        
        # 如果正在流式传输，添加流式指示器
        if is_streaming:
            # 简化判断，只在文本末尾添加打字机光标
            if text_without_blocks.strip():
                text_without_blocks += '<span class="typing-cursor"></span>'
        
        return text_without_blocks, tables_data
    
    @staticmethod
    def prepare_table_update(tables_data: List[Dict]) -> "gr.update":
        """准备表格更新"""
        if not tables_data:
            return gr.update(value=[], headers=None, visible=False)
        
        # 如果有多个表格，合并显示最后一个或者最重要的一个
        # 这里选择显示最后一个表格
        last_table = tables_data[-1]
        
        return gr.update(
            value=last_table['data'],
            headers=last_table['headers'],
            visible=True,
            label=f"📊 表格数据 ({len(tables_data)} 个表格)" if len(tables_data) > 1 else "📊 表格数据"
        )
    
    @staticmethod
    def format_stream_metrics(tool_calls: List[Dict], response_text: str) -> str:
        """格式化流式处理指标"""
        metrics = {
            "工具调用次数": len(tool_calls),
            "响应字符数": len(response_text),
            "工具类型": list(set(call.get("tool_name", "") for call in tool_calls)) if tool_calls else []
        }
        
        lines = []
        for key, value in metrics.items():
            if isinstance(value, list):
                lines.append(f"{key}: {', '.join(value) if value else '无'}")
            else:
                lines.append(f"{key}: {value}")
        
        return "\n".join(lines)
    
    @staticmethod
    def generate_node_status(trace: List[Dict[str, Any]]) -> List[List[Any]]:
        """生成节点状态表"""
        if not trace:
            return []
        
        status_data = []
        for step in trace:
            node_name = step.get("node", "")
            node_type = step.get("type", "")
            state = step.get("state", "")
            duration = step.get("duration", 0)
            
            # 获取输出预览
            output = step.get("output", {})
            if isinstance(output, dict):
                # 提取关键信息作为预览
                if "answer" in output:
                    preview = output["answer"][:50] + "..." if len(output.get("answer", "")) > 50 else output.get("answer", "")
                elif "thought" in output:
                    preview = output["thought"][:50] + "..." if len(output.get("thought", "")) > 50 else output.get("thought", "")
                elif "action" in output:
                    preview = f"执行: {output.get('action', '')[:30]}..."
                else:
                    preview = str(output)[:50] + "..." if len(str(output)) > 50 else str(output)
            else:
                preview = str(output)[:50] + "..." if len(str(output)) > 50 else str(output)
            
            # 添加表情符号表示状态
            state_emoji = {
                "success": "✅",
                "failed": "❌",
                "running": "🔄",
                "pending": "⏳"
            }.get(state, "❓")
            
            status_data.append([
                node_name,
                node_type,
                f"{state_emoji} {state}",
                f"{duration:.2f}" if duration else "0.00",
                preview
            ])
        
        return status_data
    
    @staticmethod
    def generate_flow_diagram(trace: List[Dict[str, Any]]) -> str:
        """生成流程图HTML"""
        if not trace:
            return "<p>暂无执行流程</p>"
        
        # 使用Mermaid生成流程图
        mermaid_code = "graph TD\n"
        
        # 添加节点
        for i, step in enumerate(trace):
            node_name = step.get("node", f"node_{i}")
            node_type = step.get("type", "unknown")
            state = step.get("state", "")
            
            # 根据状态选择样式
            if state == "success":
                style = "fill:#90EE90"
            elif state == "failed":
                style = "fill:#FFB6C1"
            elif state == "running":
                style = "fill:#87CEEB"
            else:
                style = "fill:#F0F0F0"
            
            # 添加节点定义
            label = f"{node_name}\\n[{node_type}]"
            mermaid_code += f"    {node_name}[\"{label}\"]:::state{i}\n"
            mermaid_code += f"    classDef state{i} {style}\n"
            
            # 添加连接
            if i > 0:
                prev_node = trace[i-1].get("node", f"node_{i-1}")
                mermaid_code += f"    {prev_node} --> {node_name}\n"
        
        # 生成HTML
        html = f"""
        <div id="mermaid-diagram">
            <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
            <script>
                mermaid.initialize({{ startOnLoad: true }});
            </script>
            <div class="mermaid">
                {mermaid_code}
            </div>
        </div>
        <style>
            #mermaid-diagram {{
                width: 100%;
                min-height: 300px;
                background: #f9f9f9;
                border-radius: 8px;
                padding: 20px;
            }}
            .mermaid {{
                text-align: center;
            }}
        </style>
        """
        
        return html
    
    @staticmethod
    def add_streaming_wrapper(text: str, is_new_content: bool = False) -> str:
        """为流式文本添加包装器和动画效果"""
        wrapper_class = "streaming-text"
        if is_new_content:
            wrapper_class += " new-text-highlight"
        
        return f'<span class="{wrapper_class}">{text}</span>'
    
    @staticmethod
    def format_tool_execution_status(tool_name: str, status: str = "executing") -> str:
        """格式化工具执行状态"""
        status_text = {
            "executing": f"🔧 正在执行 {tool_name}...",
            "completed": f"✅ {tool_name} 执行完成",
            "failed": f"❌ {tool_name} 执行失败"
        }.get(status, f"⚠️ {tool_name} 状态未知")
        
        css_class = {
            "executing": "tool-executing",
            "completed": "response-complete", 
            "failed": "tool-error"
        }.get(status, "")
        
        return f'<span class="{css_class}">{status_text}</span>' 