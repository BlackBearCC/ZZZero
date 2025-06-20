#!/usr/bin/env python3
"""
系统级批处理器 - ReactAgent的通用批处理功能
支持前端配置、CSV解析、LLM指令生成、并发Agent执行
"""
import os
import csv
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class BatchConfig:
    """批处理配置"""
    enabled: bool = False
    csv_file_path: Optional[str] = None
    batch_size: int = 20
    concurrent_tasks: int = 5
    max_rows: int = 1000  # 最大处理行数限制


@dataclass
class BatchInstruction:
    """批处理指令"""
    task_type: str
    batch_description: str
    per_row_template: str
    total_rows: int
    expected_output: str


class CSVDataManager:
    """CSV数据管理器"""
    
    @staticmethod
    def detect_encoding(file_path: str) -> str:
        """检测文件编码"""
        try:
            import chardet
            with open(file_path, 'rb') as f:
                raw_data = f.read(10000)  # 读取前10KB用于检测
                result = chardet.detect(raw_data)
                detected_encoding = result.get('encoding', 'utf-8')
                confidence = result.get('confidence', 0)
                
                # 如果置信度太低，使用默认编码
                if confidence < 0.5:
                    detected_encoding = 'utf-8'
                    
                logger.info(f"检测到文件编码: {detected_encoding} (置信度: {confidence:.2f})")
                return detected_encoding
        except ImportError:
            logger.warning("chardet未安装，使用utf-8编码")
            return 'utf-8'
        except Exception as e:
            logger.warning(f"编码检测失败: {e}，使用utf-8编码")
            return 'utf-8'
    
    @staticmethod
    def validate_and_parse_csv(file_path: str) -> tuple[bool, str, List[Dict[str, Any]], Dict[str, Any]]:
        """验证并解析CSV文件，返回数据和文件结构信息"""
        try:
            if not os.path.exists(file_path):
                return False, f"文件不存在: {file_path}", [], {}
            
            # 检测编码
            detected_encoding = CSVDataManager.detect_encoding(file_path)
            
            # 尝试多种编码读取CSV
            csv_data = []
            fieldnames = []
            successful_encoding = None
            
            encodings_to_try = [
                detected_encoding, 
                'utf-8-sig', 
                'utf-8', 
                'gbk', 
                'gb2312', 
                'gb18030',
                'big5',
                'latin1',
                'cp1252'
            ]
            
            # 去重并保持顺序
            encodings_to_try = list(dict.fromkeys(encodings_to_try))
            
            for encoding in encodings_to_try:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        reader = csv.DictReader(f)
                        
                        # 获取列名
                        fieldnames = reader.fieldnames
                        if not fieldnames:
                            continue
                        
                        # 读取数据行
                        csv_data = []
                        for index, row in enumerate(reader):
                            # 清理数据中的BOM和特殊字符
                            cleaned_row = {}
                            for key, value in row.items():
                                # 清理列名中的BOM
                                clean_key = key.replace('\ufeff', '').strip() if key else ''
                                # 清理值中的特殊字符
                                clean_value = value.strip() if value else ''
                                cleaned_row[clean_key] = clean_value
                            
                            # 添加行索引
                            cleaned_row['_row_index'] = index + 1
                            csv_data.append(cleaned_row)
                        
                        successful_encoding = encoding
                        break
                        
                except (UnicodeDecodeError, UnicodeError):
                    continue
                except Exception as e:
                    logger.warning(f"使用编码 {encoding} 读取失败: {e}")
                    continue
            
            if not successful_encoding:
                return False, "无法使用任何编码解析CSV文件", [], {}
            
            if not fieldnames:
                return False, "CSV文件没有列头", [], {}
            
            if not csv_data:
                return False, "CSV文件没有数据行", [], {}
            
            # 清理列名中的BOM和特殊字符
            clean_fieldnames = [col.replace('\ufeff', '').strip() for col in fieldnames]
            
            # 生成文件结构信息
            structure_info = CSVDataManager.get_csv_structure_info(csv_data, clean_fieldnames)
            structure_info['detected_encoding'] = successful_encoding
            structure_info['file_size'] = os.path.getsize(file_path)
            
            success_msg = f"成功解析{len(csv_data)}行数据，使用编码: {successful_encoding}，列: {clean_fieldnames}"
            logger.info(success_msg)
            
            return True, success_msg, csv_data, structure_info
            
        except Exception as e:
            error_msg = f"CSV解析错误: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, [], {}
    
    @staticmethod
    def get_csv_structure_info(csv_data: List[Dict[str, Any]], fieldnames: List[str] = None) -> Dict[str, Any]:
        """获取CSV结构信息用于LLM分析"""
        if not csv_data:
            return {}
        
        # 获取列信息
        sample_row = csv_data[0]
        if fieldnames:
            columns = fieldnames
        else:
            columns = [col for col in sample_row.keys() if not col.startswith('_')]
        
        # 获取数据样例和数据类型分析
        sample_data = {}
        column_types = {}
        for col in columns:
            values = [row.get(col, '') for row in csv_data[:5]]  # 取前5行作为样例
            sample_data[col] = values
            
            # 简单的数据类型推断
            non_empty_values = [v for v in values if v and str(v).strip()]
            if non_empty_values:
                # 检查是否为数字
                try:
                    float(non_empty_values[0])
                    column_types[col] = 'numeric'
                except ValueError:
                    # 检查是否为日期
                    if any(keyword in str(non_empty_values[0]).lower() for keyword in ['日期', 'date', '时间', 'time']):
                        column_types[col] = 'datetime'
                    else:
                        column_types[col] = 'text'
            else:
                column_types[col] = 'unknown'
        
        return {
            "total_rows": len(csv_data),
            "columns": columns,
            "column_types": column_types,
            "sample_data": sample_data,
            "first_row_example": {col: csv_data[0].get(col, '') for col in columns},
            # 添加字段选择的默认配置
            "field_selection": {col: True for col in columns},  # 默认全选
            "field_descriptions": {col: f"{col} - {column_types.get(col, 'unknown')}" for col in columns}
        }


class BatchInstructionGenerator:
    """批处理指令生成器 - 使用LLM分析用户意图并生成批处理指令"""
    
    def __init__(self, llm_caller=None):
        self.llm_caller = llm_caller
    
    async def generate_batch_instruction(self, user_message: str, csv_structure: Dict[str, Any]) -> BatchInstruction:
        """根据用户消息和CSV结构生成批处理指令"""
        
        # 构建LLM提示词
        prompt = self._build_instruction_prompt(user_message, csv_structure)
        
        try:
            if self.llm_caller:
                # 调用LLM生成指令
                success, response = await self.llm_caller.call_llm(prompt, max_tokens=1000, temperature=0.3)
                
                if success:
                    # 解析LLM响应
                    return self._parse_llm_response(response, csv_structure)
                else:
                    logger.warning(f"LLM调用失败，使用默认指令: {response}")
            
            # 如果LLM不可用，生成默认指令
            return self._generate_default_instruction(user_message, csv_structure)
            
        except Exception as e:
            logger.error(f"批处理指令生成失败: {e}")
            return self._generate_default_instruction(user_message, csv_structure)
    
    def _build_instruction_prompt(self, user_message: str, csv_structure: Dict[str, Any]) -> str:
        """构建LLM提示词"""
        return f"""你是一个批处理任务分析专家。用户想要对CSV数据进行批量处理，请分析用户意图并生成批处理指令。

用户消息: "{user_message}"

CSV数据结构:
- 总行数: {csv_structure.get('total_rows', 0)}
- 列名: {csv_structure.get('columns', [])}
- 数据样例: {csv_structure.get('first_row_example', {})}

请分析用户意图，生成JSON格式的批处理指令：
{{
    "task_type": "任务类型(如: schedule_generation, content_creation, data_analysis等)",
    "batch_description": "批处理任务的总体描述",
    "per_row_template": "单行处理模板，使用{{列名}}占位符，如: 为角色{{character_name}}生成{{duration_days}}天的日程",
    "expected_output": "期望的输出格式描述"
}}

注意：
1. per_row_template中的占位符必须与CSV列名完全匹配
2. 要体现用户的具体需求
3. 确保指令清晰、可执行
4. 只返回JSON，不要其他文字

JSON:"""
    
    def _parse_llm_response(self, response: str, csv_structure: Dict[str, Any]) -> BatchInstruction:
        """解析LLM响应"""
        try:
            # 尝试解析JSON
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.endswith('```'):
                response = response[:-3]
            response = response.strip()
            
            instruction_data = json.loads(response)
            
            return BatchInstruction(
                task_type=instruction_data.get('task_type', 'general_processing'),
                batch_description=instruction_data.get('batch_description', '批量处理任务'),
                per_row_template=instruction_data.get('per_row_template', '处理数据行'),
                total_rows=csv_structure.get('total_rows', 0),
                expected_output=instruction_data.get('expected_output', '处理结果')
            )
            
        except Exception as e:
            logger.warning(f"LLM响应解析失败: {e}，使用默认指令")
            return self._generate_default_instruction("批量处理", csv_structure)
    
    def _generate_default_instruction(self, user_message: str, csv_structure: Dict[str, Any]) -> BatchInstruction:
        """生成默认批处理指令"""
        columns = csv_structure.get('columns', [])
        
        # 根据常见列名推测任务类型
        if any('name' in col.lower() for col in columns):
            task_type = 'character_processing'
            template = f"处理{{{columns[0] if columns else 'data'}}}"
        else:
            task_type = 'general_processing'
            template = "处理CSV数据行"
        
        return BatchInstruction(
            task_type=task_type,
            batch_description=f"根据用户需求进行批量处理: {user_message}",
            per_row_template=template,
            total_rows=csv_structure.get('total_rows', 0),
            expected_output="批量处理结果"
        )


class ReactAgentTaskExecutor:
    """ReactAgent任务执行器 - 模拟ReactAgent处理单个任务"""
    
    def __init__(self, mcp_tool_manager=None):
        self.mcp_tool_manager = mcp_tool_manager
    
    async def execute_single_task(self, task_prompt: str, row_data: Dict[str, Any], row_index: int) -> Dict[str, Any]:
        """执行单个ReactAgent任务"""
        start_time = datetime.now()
        
        try:
            logger.info(f"执行第{row_index}行任务: {task_prompt[:50]}...")
            
            # 模拟ReactAgent的思考和行动过程
            result = await self._simulate_react_process(task_prompt, row_data)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return {
                "row_index": row_index,
                "success": True,
                "task_prompt": task_prompt,
                "result": result,
                "execution_time": execution_time,
                "processed_at": datetime.now().isoformat(),
                "row_data": row_data
            }
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return {
                "row_index": row_index,
                "success": False,
                "task_prompt": task_prompt,
                "error": str(e),
                "execution_time": execution_time,
                "processed_at": datetime.now().isoformat(),
                "row_data": row_data
            }
    
    async def _simulate_react_process(self, task_prompt: str, row_data: Dict[str, Any]) -> str:
        """模拟ReactAgent的React过程"""
        
        # 如果有MCP工具管理器，尝试调用相应的工具
        if self.mcp_tool_manager:
            try:
                # 检查是否是角色日程生成任务
                if any(keyword in task_prompt.lower() for keyword in ['日程', 'schedule', '计划', '安排']):
                    return await self._handle_schedule_task(task_prompt, row_data)
                
                # 其他类型的任务可以在这里扩展
                return await self._handle_general_task(task_prompt, row_data)
                
            except Exception as e:
                logger.warning(f"MCP工具调用失败，返回模拟结果: {e}")
        
        # 返回模拟的处理结果
        return f"模拟处理结果: 基于 '{task_prompt}' 对数据 {row_data} 的处理完成"
    
    async def _handle_schedule_task(self, task_prompt: str, row_data: Dict[str, Any]) -> str:
        """处理日程生成任务"""
        try:
            # 确保MCP工具管理器已初始化
            if not hasattr(self.mcp_tool_manager, 'enabled_tools'):
                await self.mcp_tool_manager.initialize()
            
            # 调用角色扮演服务生成日程
            result = await self.mcp_tool_manager.call_tool(
                "roleplay_generate_schedule_plan",
                {"description": task_prompt}
            )
            
            if result.success:
                content = result.result.get('content', '') if isinstance(result.result, dict) else str(result.result)
                return f"✅ 日程生成成功:\n{content}"
            else:
                return f"❌ 日程生成失败: {result.error}"
                
        except Exception as e:
            return f"❌ 日程生成异常: {str(e)}"
    
    async def _handle_general_task(self, task_prompt: str, row_data: Dict[str, Any]) -> str:
        """处理通用任务"""
        # 这里可以根据任务类型调用不同的MCP工具
        return f"通用任务处理: {task_prompt}"


class BatchProcessor:
    """系统级批处理器主控制器"""
    
    def __init__(self, llm_caller=None, mcp_tool_manager=None):
        self.config = BatchConfig()
        self.csv_data: List[Dict[str, Any]] = []
        self.csv_structure: Dict[str, Any] = {}  # 存储CSV结构信息
        self.instruction_generator = BatchInstructionGenerator(llm_caller)
        self.task_executor = ReactAgentTaskExecutor(mcp_tool_manager)
        self.current_batch_task = None
    
    def configure_batch_mode(self, enabled: bool, csv_file_path: str = None, 
                           batch_size: int = 20, concurrent_tasks: int = 5) -> Dict[str, Any]:
        """配置批处理模式"""
        self.config.enabled = enabled
        self.config.batch_size = batch_size
        self.config.concurrent_tasks = concurrent_tasks
        
        if enabled and csv_file_path:
            # 验证和解析CSV
            success, message, csv_data, structure_info = CSVDataManager.validate_and_parse_csv(csv_file_path)
            
            if success:
                self.config.csv_file_path = csv_file_path
                self.csv_data = csv_data
                self.csv_structure = structure_info
                
                return {
                    "success": True,
                    "message": f"批处理模式已启用: {message}",
                    "csv_rows": len(csv_data),
                    "csv_structure": structure_info,
                    "config": {
                        "batch_size": batch_size,
                        "concurrent_tasks": concurrent_tasks
                    }
                }
            else:
                self.config.enabled = False
                return {
                    "success": False,
                    "message": f"批处理模式启用失败: {message}"
                }
        
        elif not enabled:
            self.config.csv_file_path = None
            self.csv_data = []
            return {
                "success": True,
                "message": "批处理模式已关闭"
            }
        
        return {
            "success": False,
            "message": "配置参数不完整"
        }
    
    def is_batch_mode_enabled(self) -> bool:
        """检查是否启用批处理模式"""
        return self.config.enabled and bool(self.csv_data)
    
    async def process_batch_request(self, user_message: str) -> Dict[str, Any]:
        """处理批处理请求"""
        if not self.is_batch_mode_enabled():
            return {
                "success": False,
                "message": "批处理模式未启用或CSV数据未加载"
            }
        
        try:
            # 1. 生成批处理指令
            csv_structure = CSVDataManager.get_csv_structure_info(self.csv_data)
            batch_instruction = await self.instruction_generator.generate_batch_instruction(
                user_message, csv_structure
            )
            
            logger.info(f"生成批处理指令: {batch_instruction.batch_description}")
            
            # 2. 执行批处理任务
            results = await self._execute_batch_tasks(batch_instruction)
            
            # 3. 汇总结果
            summary = self._summarize_results(results, batch_instruction)
            
            return {
                "success": True,
                "batch_instruction": {
                    "task_type": batch_instruction.task_type,
                    "description": batch_instruction.batch_description,
                    "template": batch_instruction.per_row_template
                },
                "execution_summary": summary,
                "detailed_results": results
            }
            
        except Exception as e:
            logger.error(f"批处理执行失败: {e}")
            return {
                "success": False,
                "message": f"批处理执行失败: {str(e)}"
            }
    
    async def _execute_batch_tasks(self, instruction: BatchInstruction) -> List[Dict[str, Any]]:
        """执行批处理任务"""
        all_results = []
        
        # 分批处理
        for batch_start in range(0, len(self.csv_data), self.config.batch_size):
            batch_end = min(batch_start + self.config.batch_size, len(self.csv_data))
            batch_data = self.csv_data[batch_start:batch_end]
            
            logger.info(f"处理批次 {batch_start+1}-{batch_end}")
            
            # 并发执行当前批次
            semaphore = asyncio.Semaphore(self.config.concurrent_tasks)
            
            async def execute_with_semaphore(row_data):
                async with semaphore:
                    # 生成具体的任务提示词
                    task_prompt = self._generate_task_prompt(instruction.per_row_template, row_data)
                    
                    # 执行单个任务
                    return await self.task_executor.execute_single_task(
                        task_prompt, row_data, row_data.get('_row_index', 0)
                    )
            
            # 并发执行当前批次的所有任务
            batch_results = await asyncio.gather(
                *[execute_with_semaphore(row_data) for row_data in batch_data],
                return_exceptions=True
            )
            
            # 处理结果
            for result in batch_results:
                if isinstance(result, Exception):
                    all_results.append({
                        "success": False,
                        "error": str(result),
                        "processed_at": datetime.now().isoformat()
                    })
                else:
                    all_results.append(result)
        
        return all_results
    
    def _generate_task_prompt(self, template: str, row_data: Dict[str, Any]) -> str:
        """根据模板和行数据生成具体的任务提示词"""
        try:
            # 使用format方法替换占位符
            return template.format(**row_data)
        except KeyError as e:
            # 如果模板中的占位符在数据中不存在，记录警告并返回原模板
            logger.warning(f"模板占位符 {e} 在CSV数据中不存在")
            return template
        except Exception as e:
            logger.error(f"任务提示词生成失败: {e}")
            return template
    
    def _summarize_results(self, results: List[Dict[str, Any]], instruction: BatchInstruction) -> Dict[str, Any]:
        """汇总批处理结果"""
        total_tasks = len(results)
        successful_tasks = sum(1 for r in results if r.get('success', False))
        failed_tasks = total_tasks - successful_tasks
        
        total_time = sum(r.get('execution_time', 0) for r in results)
        avg_time = total_time / total_tasks if total_tasks > 0 else 0
        
        return {
            "task_type": instruction.task_type,
            "batch_description": instruction.batch_description,
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "failed_tasks": failed_tasks,
            "success_rate": f"{(successful_tasks / total_tasks * 100):.1f}%" if total_tasks > 0 else "0%",
            "total_execution_time": f"{total_time:.2f}秒",
            "average_task_time": f"{avg_time:.2f}秒",
            "completed_at": datetime.now().isoformat()
        }
    
    def update_field_selection(self, field_selection: Dict[str, bool]) -> Dict[str, Any]:
        """更新字段选择配置"""
        if not self.csv_structure:
            return {"success": False, "message": "没有加载CSV结构信息"}
        
        # 验证字段选择
        available_fields = set(self.csv_structure.get("columns", []))
        selected_fields = set(field for field, selected in field_selection.items() if selected)
        
        if not selected_fields:
            return {"success": False, "message": "至少需要选择一个字段"}
        
        invalid_fields = selected_fields - available_fields
        if invalid_fields:
            return {"success": False, "message": f"无效字段: {invalid_fields}"}
        
        # 更新字段选择
        self.csv_structure["field_selection"] = field_selection
        
        return {
            "success": True,
            "message": f"已更新字段选择，选中 {len(selected_fields)} 个字段",
            "selected_fields": list(selected_fields)
        }
    
    def get_batch_status(self) -> Dict[str, Any]:
        """获取批处理状态"""
        status = {
            "enabled": self.config.enabled,
            "csv_loaded": bool(self.csv_data),
            "csv_rows": len(self.csv_data),
            "csv_file": self.config.csv_file_path,
            "batch_size": self.config.batch_size,
            "concurrent_tasks": self.config.concurrent_tasks
        }
        
        # 如果有CSV结构信息，添加到状态中
        if self.csv_structure:
            status.update({
                "csv_structure": self.csv_structure,
                "available_fields": self.csv_structure.get("columns", []),
                "selected_fields": [
                    field for field, selected in self.csv_structure.get("field_selection", {}).items() 
                    if selected
                ]
            })
        
        return status 