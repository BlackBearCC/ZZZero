#!/usr/bin/env python3
"""
系统级批处理器 - ReactAgent的通用批处理功能
支持前端配置、CSV解析、LLM指令生成、并发Agent执行
支持并行/遍历两种处理模式和实时进度展示
"""
import os
import csv
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class ProcessingMode(Enum):
    """处理模式枚举"""
    PARALLEL = "parallel"      # 并行模式 - 快速高效
    SEQUENTIAL = "sequential"  # 遍历模式 - 顺序执行


@dataclass
class BatchConfig:
    """批处理配置"""
    enabled: bool = False
    csv_file_path: Optional[str] = None
    batch_size: int = 20
    concurrent_tasks: int = 5
    max_rows: int = 1000  # 最大处理行数限制
    processing_mode: ProcessingMode = ProcessingMode.PARALLEL  # 处理模式


@dataclass
class BatchProgress:
    """批处理进度信息"""
    total_tasks: int = 0
    completed_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    current_batch: int = 0
    total_batches: int = 0
    current_task_description: str = ""
    start_time: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    average_task_time: float = 0.0
    
    @property
    def progress_percentage(self) -> float:
        """计算进度百分比"""
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100
    
    @property
    def success_rate(self) -> float:
        """计算成功率"""
        if self.completed_tasks == 0:
            return 0.0
        return (self.successful_tasks / self.completed_tasks) * 100


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
                success, response = await self.llm_caller.call_llm(prompt,  temperature=0.3)
                
                if success:
                    # 解析LLM响应
                    logger.info(f"批处理LLM响应的通用指令: {response}")
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
        """处理日程生成任务（已改为通用任务处理）"""
        # 角色扮演服务器已移除，使用通用任务处理
        return await self._handle_general_task(task_prompt, row_data)
    
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
        self.current_progress = BatchProgress()  # 当前进度状态
    
    def configure_batch_mode(self, enabled: bool, csv_file_path: str = None, 
                           batch_size: int = 20, concurrent_tasks: int = 5,
                           processing_mode: str = "parallel") -> Dict[str, Any]:
        """配置批处理模式"""
        self.config.enabled = enabled
        self.config.batch_size = batch_size
        self.config.concurrent_tasks = concurrent_tasks
        
        # 设置处理模式
        try:
            self.config.processing_mode = ProcessingMode(processing_mode)
        except ValueError:
            self.config.processing_mode = ProcessingMode.PARALLEL
            logger.warning(f"无效的处理模式: {processing_mode}，使用默认并行模式")
        
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
                        "concurrent_tasks": concurrent_tasks,
                        "processing_mode": processing_mode
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
    
    async def process_batch_request_with_progress(self, user_message: str) -> AsyncIterator[Dict[str, Any]]:
        """处理批处理请求并提供流式进度更新"""
        if not self.is_batch_mode_enabled():
            yield {
                "type": "error",
                "content": "❌ 批处理模式未启用或CSV数据未加载"
            }
            return
        
        try:
            # 1. 生成批处理指令
            yield {
                "type": "progress",
                "content": "🧠 正在分析任务需求并生成批处理指令...",
                "stage": "instruction_generation"
            }
            
            csv_structure = CSVDataManager.get_csv_structure_info(self.csv_data)
            batch_instruction = await self.instruction_generator.generate_batch_instruction(
                user_message, csv_structure
            )
            
            logger.info(f"生成批处理指令: {batch_instruction.batch_description}")
            
            # 初始化进度
            self.current_progress = BatchProgress(
                total_tasks=len(self.csv_data),
                start_time=datetime.now()
            )
            
            yield {
                "type": "instruction_generated",
                "content": f"📋 **批处理指令已生成**\n\n"
                          f"**任务类型**: {batch_instruction.task_type}\n"
                          f"**任务描述**: {batch_instruction.batch_description}\n"
                          f"**处理模板**: {batch_instruction.per_row_template}\n"
                          f"**总任务数**: {self.current_progress.total_tasks}\n"
                          f"**处理模式**: {'并行模式' if self.config.processing_mode == ProcessingMode.PARALLEL else '顺序模式'}\n\n"
                          f"🚀 开始执行批处理任务...",
                "instruction": batch_instruction
            }
            
            # 2. 根据模式执行批处理任务
            if self.config.processing_mode == ProcessingMode.PARALLEL:
                async for progress_data in self._execute_batch_tasks_parallel(batch_instruction):
                    yield progress_data
            else:
                async for progress_data in self._execute_batch_tasks_sequential(batch_instruction):
                    yield progress_data
            
            # 3. 生成最终汇总
            yield {
                "type": "final_summary",
                "content": self._generate_final_summary(),
                "progress": self.current_progress
            }
            
        except Exception as e:
            logger.error(f"批处理执行失败: {e}")
            yield {
                "type": "error",
                "content": f"❌ 批处理执行失败: {str(e)}"
            }
    
    async def process_batch_request(self, user_message: str) -> Dict[str, Any]:
        """处理批处理请求 - 兼容原有接口"""
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
    
    async def _execute_batch_tasks_parallel(self, instruction: BatchInstruction) -> AsyncIterator[Dict[str, Any]]:
        """并行模式执行批处理任务"""
        all_results = []
        
        # 计算总批次数
        total_batches = (len(self.csv_data) + self.config.batch_size - 1) // self.config.batch_size
        self.current_progress.total_batches = total_batches
        
        # 分批处理
        for batch_idx, batch_start in enumerate(range(0, len(self.csv_data), self.config.batch_size)):
            batch_end = min(batch_start + self.config.batch_size, len(self.csv_data))
            batch_data = self.csv_data[batch_start:batch_end]
            
            self.current_progress.current_batch = batch_idx + 1
            
            yield {
                "type": "batch_start",
                "content": f"📦 开始处理第 {batch_idx + 1}/{total_batches} 批次 (第{batch_start+1}-{batch_end}行)",
                "batch_info": {
                    "batch_index": batch_idx + 1,
                    "total_batches": total_batches,
                    "batch_start": batch_start + 1,
                    "batch_end": batch_end,
                    "batch_size": len(batch_data)
                }
            }
            
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
            
            # 处理结果并更新进度
            for result in batch_results:
                if isinstance(result, Exception):
                    result_data = {
                        "success": False,
                        "error": str(result),
                        "processed_at": datetime.now().isoformat()
                    }
                    self.current_progress.failed_tasks += 1
                else:
                    result_data = result
                    if result.get('success', False):
                        self.current_progress.successful_tasks += 1
                    else:
                        self.current_progress.failed_tasks += 1
                
                self.current_progress.completed_tasks += 1
                all_results.append(result_data)
                
                # 更新平均耗时
                if result_data.get('execution_time'):
                    total_time = self.current_progress.average_task_time * (self.current_progress.completed_tasks - 1) + result_data.get('execution_time', 0)
                    self.current_progress.average_task_time = total_time / self.current_progress.completed_tasks
            
            # 发送批次完成进度
            yield {
                "type": "batch_completed",
                "content": f"✅ 第 {batch_idx + 1}/{total_batches} 批次完成 - "
                          f"进度: {self.current_progress.progress_percentage:.1f}% "
                          f"({self.current_progress.completed_tasks}/{self.current_progress.total_tasks})",
                "progress": {
                    "percentage": self.current_progress.progress_percentage,
                    "completed": self.current_progress.completed_tasks,
                    "total": self.current_progress.total_tasks,
                    "successful": self.current_progress.successful_tasks,
                    "failed": self.current_progress.failed_tasks,
                    "success_rate": self.current_progress.success_rate,
                    "average_time": self.current_progress.average_task_time
                }
            }
        
        # 保存结果供最终汇总使用
        self.current_progress.results = all_results
    
    async def _execute_batch_tasks_sequential(self, instruction: BatchInstruction) -> AsyncIterator[Dict[str, Any]]:
        """顺序模式执行批处理任务"""
        all_results = []
        self.current_progress.total_batches = 1
        self.current_progress.current_batch = 1
        
        yield {
            "type": "sequential_start",
            "content": f"🔄 开始顺序处理 {len(self.csv_data)} 个任务..."
        }
        
        # 顺序处理每个任务
        for idx, row_data in enumerate(self.csv_data):
            # 生成具体的任务提示词
            task_prompt = self._generate_task_prompt(instruction.per_row_template, row_data)
            row_index = row_data.get('_row_index', idx + 1)
            
            # 更新当前任务描述
            task_preview = task_prompt[:50] + "..." if len(task_prompt) > 50 else task_prompt
            self.current_progress.current_task_description = task_preview
            
            yield {
                "type": "task_start",
                "content": f"🔄 正在处理第 {idx + 1}/{len(self.csv_data)} 个任务\n"
                          f"**任务内容**: {task_preview}\n"
                          f"**进度**: {((idx) / len(self.csv_data) * 100):.1f}%",
                "task_info": {
                    "task_index": idx + 1,
                    "total_tasks": len(self.csv_data),
                    "task_prompt": task_prompt,
                    "row_data": row_data
                }
            }
            
            # 执行单个任务
            try:
                result = await self.task_executor.execute_single_task(task_prompt, row_data, row_index)
                
                if result.get('success', False):
                    self.current_progress.successful_tasks += 1
                    status_icon = "✅"
                else:
                    self.current_progress.failed_tasks += 1
                    status_icon = "❌"
                
                # 更新进度
                self.current_progress.completed_tasks += 1
                
                # 更新平均耗时
                if result.get('execution_time'):
                    total_time = self.current_progress.average_task_time * (self.current_progress.completed_tasks - 1) + result.get('execution_time', 0)
                    self.current_progress.average_task_time = total_time / self.current_progress.completed_tasks
                
                all_results.append(result)
                
                # 发送任务完成状态
                result_preview = ""
                if result.get('success') and result.get('result'):
                    result_content = str(result.get('result', ''))
                    result_preview = (result_content[:100] + "...") if len(result_content) > 100 else result_content
                elif result.get('error'):
                    result_preview = f"错误: {result.get('error', '')[:50]}..."
                
                yield {
                    "type": "task_completed",
                    "content": f"{status_icon} 第 {idx + 1}/{len(self.csv_data)} 个任务完成\n"
                              f"**执行时间**: {result.get('execution_time', 0):.2f}秒\n"
                              f"**结果预览**: {result_preview}\n"
                              f"**总体进度**: {self.current_progress.progress_percentage:.1f}%",
                    "result": result,
                    "progress": {
                        "percentage": self.current_progress.progress_percentage,
                        "completed": self.current_progress.completed_tasks,
                        "total": self.current_progress.total_tasks,
                        "successful": self.current_progress.successful_tasks,
                        "failed": self.current_progress.failed_tasks,
                        "success_rate": self.current_progress.success_rate,
                        "average_time": self.current_progress.average_task_time
                    }
                }
                
            except Exception as e:
                # 处理异常
                result = {
                    "row_index": row_index,
                    "success": False,
                    "task_prompt": task_prompt,
                    "error": str(e),
                    "execution_time": 0.0,
                    "processed_at": datetime.now().isoformat(),
                    "row_data": row_data
                }
                
                self.current_progress.failed_tasks += 1
                self.current_progress.completed_tasks += 1
                all_results.append(result)
                
                yield {
                    "type": "task_error",
                    "content": f"❌ 第 {idx + 1}/{len(self.csv_data)} 个任务失败\n"
                              f"**错误**: {str(e)}\n"
                              f"**进度**: {self.current_progress.progress_percentage:.1f}%",
                    "error": str(e),
                    "task_info": {
                        "task_index": idx + 1,
                        "task_prompt": task_prompt
                    }
                }
        
        # 保存结果供最终汇总使用
        self.current_progress.results = all_results
    
    async def _execute_batch_tasks(self, instruction: BatchInstruction) -> List[Dict[str, Any]]:
        """执行批处理任务 - 兼容原有接口（并行模式）"""
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
    
    def _generate_final_summary(self) -> str:
        """生成最终汇总报告"""
        progress = self.current_progress
        end_time = datetime.now()
        total_duration = (end_time - progress.start_time).total_seconds() if progress.start_time else 0
        
        summary = f"""🎉 **批处理任务完成！**

📊 **执行统计**:
- 总任务数: {progress.total_tasks}
- 成功任务: {progress.successful_tasks}
- 失败任务: {progress.failed_tasks}
- 成功率: {progress.success_rate:.1f}%

⏱️ **时间统计**:
- 总耗时: {total_duration:.2f}秒
- 平均耗时: {progress.average_task_time:.2f}秒/任务
- 处理模式: {'并行模式' if self.config.processing_mode == ProcessingMode.PARALLEL else '顺序模式'}

💡 **提示**: 详细结果已保存，您可以在执行详情中查看完整的批处理结果。"""

        if progress.failed_tasks > 0:
            summary += f"\n\n⚠️ **注意**: 有 {progress.failed_tasks} 个任务执行失败，请检查执行详情了解失败原因。"
        
        return summary
    
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
    

    def save_results_to_csv(self, results: List[Dict[str, Any]], output_path: str = None) -> bool:
        """保存批量处理结果到CSV文件"""
        try:
            import csv
            from datetime import datetime
            
            if not results:
                logger.warning("没有结果数据需要保存")
                return False
            
            # 确定输出路径
            if output_path is None:
                output_dir = Path("workspace/batch_schedule_output")
                output_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = output_dir / f"batch_results_{timestamp}.csv"
            
            output_path = Path(output_path)
            
            # 获取所有可能的字段名
            all_fields = set()
            for result in results:
                if isinstance(result, dict):
                    all_fields.update(result.keys())
            
            # 写入CSV文件
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=sorted(all_fields))
                writer.writeheader()
                
                for result in results:
                    if isinstance(result, dict):
                        writer.writerow(result)
            
            logger.info(f"✅ 批量处理结果已保存到: {output_path}")
            logger.info(f"📊 共保存 {len(results)} 条记录")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 保存批量处理结果失败: {e}")
            return False

    def get_batch_status(self) -> Dict[str, Any]:
        """获取批处理状态"""
        status = {
            "enabled": self.config.enabled,
            "csv_loaded": bool(self.csv_data),
            "csv_rows": len(self.csv_data),
            "csv_file": self.config.csv_file_path,
            "batch_size": self.config.batch_size,
            "concurrent_tasks": self.config.concurrent_tasks,
            "processing_mode": self.config.processing_mode.value
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