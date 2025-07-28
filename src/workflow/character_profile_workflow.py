"""
角色资料生成工作流
基于人物资料需求表格，结合向量知识库，生成详细的角色背景资料
"""

import json
import asyncio
import csv
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

from core.graph import StateGraph, CompiledStateGraph
from core.base import BaseNode
from llm.base import LLMFactory
from core.types import LLMConfig, TaskResult, Message, MessageRole, NodeType
from tools.knowledge_base_manager import GlobalKnowledgeBase
from tools.mcp_tools import MCPToolManager

# 配置日志 - 强制输出到标准输出
import sys
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # 强制使用标准输出
    ],
    force=True  # 强制重新配置日志
)
logger = logging.getLogger(__name__)

class CharacterProfileGeneratorNode(BaseNode):
    """角色资料生成节点"""
    
    def __init__(self, 
                 name: str = "character_profile_generator",
                 llm_config: Optional[LLMConfig] = None,
                 knowledge_base: Optional[GlobalKnowledgeBase] = None):
        super().__init__(name=name, node_type=NodeType.CUSTOM, stream=True)
        self.llm_config = llm_config
        self.knowledge_base = knowledge_base
        self.profile_template = {}
        self._load_profile_template()
    
    def _load_profile_template(self):
        """加载人物资料需求模板"""
        try:
            template_file = Path("workspace/input/主角人物资料需求表格.csv")
            if not template_file.exists():
                logger.error(f"人物资料需求表格不存在: {template_file}")
                return
            
            with open(template_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    category = row['类别']
                    if category not in self.profile_template:
                        self.profile_template[category] = []
                    
                    self.profile_template[category].append({
                        'item': row['条目'],
                        'content': row['内容'],
                        'keywords': row['关键词'],
                        'notes': row['备注']
                    })
            
            logger.info(f"已加载人物资料模板，共{len(self.profile_template)}个类别")
            
        except Exception as e:
            logger.error(f"加载人物资料模板失败: {e}")
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行角色资料生成 - 非流式版本"""
        final_result = None
        async for result in self.execute_stream(state):
            final_result = result
        return final_result or {"success": False, "error": "执行失败"}
    
    async def execute_stream(self, state: Dict[str, Any]):
        """流式执行角色资料生成"""
        try:
            print(f"[CharacterProfileGeneratorNode] ===== 开始执行 execute_stream =====")
            print(f"[CharacterProfileGeneratorNode] 输入状态键: {list(state.keys())}")
            logger.info("===== CharacterProfileGeneratorNode 开始执行 =====")
            logger.info(f"输入状态键: {list(state.keys())}")
        
            print(f"[CharacterProfileGeneratorNode] 尝试获取输入参数...")
            # 获取输入参数
            character_name = state.get('character_name', '')
            basic_info = state.get('basic_info', '')
            selected_categories = state.get('selected_categories', [])
            selected_collections = state.get('selected_collections', [])
            
            # 从输入状态中获取LLM对象（与日程工作流保持一致）
            llm = state.get('llm')
            workflow_chat = state.get('workflow_chat')
            
            print(f"[CharacterProfileGeneratorNode] 参数解析完成:")
            print(f"  - character_name: {character_name}")
            print(f"  - basic_info: {basic_info}")
            print(f"  - selected_categories: {selected_categories}")
            print(f"  - llm: {llm}")
            
            logger.info(f"开始执行角色资料生成 - 角色: {character_name}")
        except Exception as init_error:
            error_msg = f"初始化阶段失败: {str(init_error)}"
            print(f"[CharacterProfileGeneratorNode] 严重错误 - 初始化失败: {init_error}")
            logger.error(error_msg)
            import traceback
            traceback.print_exc()
            # 确保即使初始化失败也有输出
            yield {
                'success': False,
                'error': error_msg
            }
            return
            
        try:
            
            if not character_name or not basic_info:
                error_msg = '缺少必要参数：角色名称和基础信息'
                print(f"[CharacterProfileGeneratorNode] 错误: {error_msg}")
                logger.error(error_msg)
                yield {
                    'success': False,
                    'error': error_msg
                }
                return
            
            # 如果未指定类别，使用所有类别
            if not selected_categories:
                selected_categories = list(self.profile_template.keys())
            
            print(f"[CharacterProfileGeneratorNode] 将生成类别: {selected_categories}")
            logger.info(f"将生成类别: {selected_categories}")
            
            # 生成角色资料
            generated_profile = {}
            
            for i, category in enumerate(selected_categories):
                if category not in self.profile_template:
                    print(f"[CharacterProfileGeneratorNode] 警告: 未知类别: {category}")
                    logger.warning(f"未知类别: {category}")
                    continue
                
                print(f"[CharacterProfileGeneratorNode] 正在生成类别 {i+1}/{len(selected_categories)}: {category}")
                logger.info(f"正在生成类别: {category}")
                
                try:
                    logger.info(f"开始生成类别数据: {category}")
                    category_data = await self._generate_category_data(
                        character_name, basic_info, category, selected_collections, llm
                    )
                    generated_profile[category] = category_data
                    print(f"[CharacterProfileGeneratorNode] 类别 {category} 生成完成")
                    logger.info(f"类别 {category} 生成完成: {category_data}")
                    
                    # 流式输出中间进度
                    yield {
                        'success': False,  # 还未完全完成
                        'progress': f"已完成 {i+1}/{len(selected_categories)} 个类别",
                        'generated_profile': generated_profile.copy(),
                        'character_name': character_name
                    }
                    
                except Exception as e:
                    error_msg = f"生成类别 {category} 失败: {str(e)}"
                    print(f"[CharacterProfileGeneratorNode] 错误: {error_msg}")
                    logger.error(error_msg)
                    logger.exception(f"类别 {category} 详细错误:")
                    import traceback
                    traceback.print_exc()
                    generated_profile[category] = {"错误": error_msg}
            
            # 保存生成的资料
            print(f"[CharacterProfileGeneratorNode] 开始保存角色资料")
            output_file = await self._save_profile(character_name, generated_profile)
            
            # 最终结果
            final_result = {
                'success': True,
                'generated_profile': generated_profile,
                'output_file': output_file,
                'character_name': character_name
            }
            
            print(f"[CharacterProfileGeneratorNode] 角色资料生成完成: {output_file}")
            print(f"[CharacterProfileGeneratorNode] ===== 正常结束 execute_stream =====")
            logger.info(f"角色资料生成完成: {output_file}")
            yield final_result
            
        except Exception as e:
            error_msg = f"角色资料生成失败: {str(e)}"
            print(f"[CharacterProfileGeneratorNode] 严重错误: {error_msg}")
            print(f"[CharacterProfileGeneratorNode] ===== 异常结束 execute_stream =====")
            logger.error(error_msg)
            logger.exception("详细错误信息:")
            import traceback
            traceback.print_exc()
            print(f"=== 节点执行异常 ===")
            print(f"错误类型: {type(e).__name__}")
            print(f"错误信息: {str(e)}")
            print(f"错误堆栈:")
            traceback.print_exc()
            print(f"========================")
            
            # 确保即使出错也有输出
            yield {
                'success': False,
                'error': error_msg
            }
    
    async def _generate_category_data(self, 
                                    character_name: str, 
                                    basic_info: str, 
                                    category: str,
                                    selected_collections: List[str],
                                    llm = None) -> Dict[str, Any]:
        """生成特定类别的角色数据"""
        category_items = self.profile_template.get(category, [])
        if not category_items:
            return {}
        
        # 构建知识库上下文
        knowledge_context = ""
        if self.knowledge_base and selected_collections:
            knowledge_context = await self._gather_knowledge_context(
                character_name, basic_info, category, selected_collections
            )
        
        # 构建生成提示
        prompt = self._build_generation_prompt(
            character_name, basic_info, category, category_items, knowledge_context
        )
        
        # 调用LLM生成
        if llm:
            try:
                print(f"[CharacterProfileGeneratorNode] 开始调用 LLM 生成，提示词长度: {len(prompt)} 字符")
                logger.info(f"准备调用LLM生成，提示长度: {len(prompt)} 字符")
                from core.types import Message, MessageRole
                message = Message(role=MessageRole.USER, content=prompt)
                print(f"[CharacterProfileGeneratorNode] 消息对象创建成功: {message}")
                logger.info(f"消息对象创建成功: {message}")
                
                # 先检查LLM是否初始化
                if not hasattr(llm, 'config') or not llm.config:
                    raise ValueError("LLM配置未正确初始化")
                
                print(f"[CharacterProfileGeneratorNode] LLM配置: {llm.config}")
                logger.info(f"LLM配置: {llm.config}")
                
                # 尝试初始化LLM（如果需要）
                if hasattr(llm, 'initialize'):
                    await llm.initialize()
                    print("[CharacterProfileGeneratorNode] LLM初始化完成")
                    logger.info("LLM初始化完成")
                
                print("[CharacterProfileGeneratorNode] 开始调用LLM.generate()...")
                logger.info("开始调用LLM.generate()...")
                response = await llm.generate([message])
                print(f"[CharacterProfileGeneratorNode] LLM响应成功，内容长度: {len(response.content) if hasattr(response, 'content') else 'N/A'}")
                logger.info(f"LLM响应成功，内容长度: {len(response.content) if hasattr(response, 'content') else 'N/A'}")
                
                parsed_result = self._parse_generation_response(response.content, category_items)
                print(f"[CharacterProfileGeneratorNode] 解析结果: {parsed_result}")
                logger.info(f"解析结果: {parsed_result}")
                return parsed_result
                
            except Exception as e:
                print(f"[CharacterProfileGeneratorNode] LLM生成失败: {e}")
                logger.error(f"LLM生成失败: {e}")
                logger.exception("LLM生成详细错误信息:")
                import traceback
                traceback.print_exc()
                return {"错误": f"LLM调用失败: {str(e)}"}
        else:
            print("[CharacterProfileGeneratorNode] LLM未配置，返回模拟结果")
            logger.warning("LLM未配置，返回模拟结果")
            # 返回模拟数据用于测试
            mock_result = {}
            for item in category_items:
                mock_result[item['item']] = f"模拟数据 - {item['notes']}"
            return mock_result
    
    async def _gather_knowledge_context(self, 
                                      character_name: str, 
                                      basic_info: str, 
                                      category: str,
                                      collections: List[str]) -> str:
        """从知识库收集相关上下文信息"""
        if not self.knowledge_base:
            return ""
        
        # 构建查询文本
        query_texts = [
            f"{character_name} {category}",
            f"{character_name} 角色 {category}",
            basic_info
        ]
        
        all_context = []
        
        for collection_name in collections:
            for query_text in query_texts:
                try:
                    results = await self.knowledge_base.query_documents(
                        collection_name=collection_name,
                        query_text=query_text,
                        n_results=3
                    )
                    
                    for result in results:
                        context_text = f"来源：{collection_name}\n内容：{result['document']}\n"
                        all_context.append(context_text)
                        
                except Exception as e:
                    logger.error(f"查询知识库失败: {e}")
        
        return "\n---\n".join(all_context) if all_context else ""
    
    def _build_generation_prompt(self, 
                               character_name: str, 
                               basic_info: str, 
                               category: str, 
                               category_items: List[Dict],
                               knowledge_context: str) -> str:
        """构建生成提示"""
        
        # 构建字段说明
        fields_description = []
        for item in category_items:
            field_desc = f"- {item['item']}: {item['notes']}"
            if item['keywords']:
                field_desc += f" (关键词: {item['keywords']})"
            fields_description.append(field_desc)
        
        prompt = f"""你是一个专业的角色设定生成专家。请根据提供的基础信息和参考资料，为角色"{character_name}"生成详细的"{category}"类别资料。

## 角色基础信息
{basic_info}

## 需要生成的字段
{chr(10).join(fields_description)}

## 参考资料
{knowledge_context if knowledge_context else "无额外参考资料"}

## 生成要求
1. 每个字段都要有具体、详细的内容，不能为空
2. 内容要符合角色的整体设定和背景
3. 充分利用参考资料中的信息，但要合理融合
4. 保持内容的逻辑一致性和可信度
5. 输出格式为JSON，字段名使用中文

## 输出格式示例
```json
{{
    "字段1": "详细内容...",
    "字段2": "详细内容...",
    ...
}}
```

请开始生成："""
        
        return prompt
    
    def _parse_generation_response(self, response: str, category_items: List[Dict]) -> Dict[str, Any]:
        """解析LLM生成的响应"""
        try:
            # 尝试提取JSON
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_content = response[json_start:json_end]
                parsed_data = json.loads(json_content)
                return parsed_data
            else:
                # 如果没有找到JSON，尝试按行解析
                logger.warning("未找到JSON格式，尝试按行解析")
                return self._parse_text_response(response, category_items)
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            return self._parse_text_response(response, category_items)
    
    def _parse_text_response(self, response: str, category_items: List[Dict]) -> Dict[str, Any]:
        """解析文本格式的响应"""
        result = {}
        lines = response.split('\n')
        
        current_field = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检查是否是字段开始
            field_found = False
            for item in category_items:
                if item['item'] in line and ':' in line:
                    # 保存前一个字段
                    if current_field and current_content:
                        result[current_field] = '\n'.join(current_content).strip()
                    
                    # 开始新字段
                    current_field = item['item']
                    content_part = line.split(':', 1)[1].strip()
                    current_content = [content_part] if content_part else []
                    field_found = True
                    break
            
            if not field_found and current_field:
                # 继续添加内容到当前字段
                current_content.append(line)
        
        # 保存最后一个字段
        if current_field and current_content:
            result[current_field] = '\n'.join(current_content).strip()
        
        return result
    
    async def _save_profile(self, character_name: str, profile_data: Dict[str, Any]) -> str:
        """保存生成的角色资料"""
        try:
            # 创建输出目录
            output_dir = Path("workspace/output")
            output_dir.mkdir(exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"character_profile_{character_name}_{timestamp}.json"
            output_file = output_dir / filename
            
            # 构建完整的输出数据
            output_data = {
                'character_name': character_name,
                'generated_at': datetime.now().isoformat(),
                'profile_data': profile_data,
                'metadata': {
                    'total_categories': len(profile_data),
                    'total_fields': sum(len(category_data) for category_data in profile_data.values())
                }
            }
            
            # 保存为JSON文件
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"角色资料已保存: {output_file}")
            return str(output_file)
            
        except Exception as e:
            logger.error(f"保存角色资料失败: {e}")
            return ""

class CharacterProfileWorkflow:
    """角色资料生成工作流"""
    
    def __init__(self, llm_config: Optional[LLMConfig] = None, workspace_dir: str = "./workspace"):
        self.llm_config = llm_config
        self.workspace_dir = workspace_dir
        self.knowledge_base = GlobalKnowledgeBase(workspace_dir)
        self.mcp_tools = MCPToolManager()
        self.graph = None
        self.history_file = Path(workspace_dir) / "character_profile_history.json"
        
        # 加载可用的知识集合
        self.available_collections = []
        self._load_available_collections()
        
        # 加载历史记录
        self.history_records = self._load_history()
    
    def _load_available_collections(self):
        """加载可用的知识集合"""
        try:
            self.available_collections = self.knowledge_base.list_collections()
            logger.info(f"已加载{len(self.available_collections)}个知识集合")
        except Exception as e:
            logger.error(f"加载知识集合失败: {e}")
    
    def _load_history(self) -> List[Dict[str, Any]]:
        """加载角色资料历史记录"""
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 保持最多10条记录
                    return data[-10:] if len(data) > 10 else data
            return []
        except Exception as e:
            logger.error(f"加载历史记录失败: {e}")
            return []
    
    def _save_history(self, record: Dict[str, Any]):
        """保存角色资料历史记录"""
        try:
            # 添加新记录
            self.history_records.append(record)
            
            # 保持最多10条记录
            if len(self.history_records) > 10:
                self.history_records = self.history_records[-10:]
            
            # 确保目录存在
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存到文件
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history_records, f, ensure_ascii=False, indent=2)
                
            logger.info(f"已保存历史记录，当前共{len(self.history_records)}条")
        except Exception as e:
            logger.error(f"保存历史记录失败: {e}")
    
    def get_history_records(self) -> List[Dict[str, Any]]:
        """获取历史记录"""
        return self.history_records.copy()
    
    def get_history_by_name(self, character_name: str) -> List[Dict[str, Any]]:
        """根据角色名称获取历史记录"""
        return [record for record in self.history_records 
                if record.get('character_name', '').strip() == character_name.strip()]
    
    async def setup_graph(self) -> 'CompiledStateGraph':
        """设置工作流图"""
        if self.graph:
            print("[CharacterProfileWorkflow] 使用已存在的工作流图")
            logger.info("使用已存在的工作流图")
            return self.graph
        
        print("[CharacterProfileWorkflow] 开始创建工作流图...")
        logger.info("开始创建工作流图...")
        
        # 创建节点（不需要传递LLM配置）
        generator_node = CharacterProfileGeneratorNode(
            knowledge_base=self.knowledge_base
        )
        
        print(f"[CharacterProfileWorkflow] 角色资料生成节点创建完成: {generator_node}")
        logger.info(f"角色资料生成节点创建完成: {generator_node}")
        
        # 创建图
        graph = StateGraph()
        graph.add_node("generate_profile", generator_node)
        graph.set_entry_point("generate_profile")
        
        print("[CharacterProfileWorkflow] StateGraph 节点和入口点设置完成")
        logger.info("StateGraph 节点和入口点设置完成")
        
        # 添加条件边来处理结束
        def end_condition(state: Dict[str, Any]) -> str:
            # 生成完成后结束
            print("[CharacterProfileWorkflow] 执行结束条件判断")
            logger.info("执行结束条件判断")
            return "END"
        
        graph.add_conditional_edges("generate_profile", end_condition)
        
        print("[CharacterProfileWorkflow] 条件边设置完成，开始编译图...")
        logger.info("条件边设置完成，开始编译图...")
        
        # 编译图
        self.graph = graph.compile()
        
        print(f"[CharacterProfileWorkflow] 工作流图编译完成: {self.graph}")
        logger.info(f"工作流图编译完成: {self.graph}")
        
        return self.graph
    
    async def generate_character_profile(self, 
                                       character_name: str,
                                       basic_info: str,
                                       selected_categories: Optional[List[str]] = None,
                                       selected_collections: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        生成角色资料
        
        Args:
            character_name: 角色名称
            basic_info: 基础人设信息
            selected_categories: 选中的类别列表，如果为None则生成所有类别
            selected_collections: 选中的知识集合列表
            
        Returns:
            生成结果
        """
        try:
            print(f"[CharacterProfileWorkflow] ===== 开始生成角色资料 =====")
            print(f"[CharacterProfileWorkflow] 角色名称: {character_name}")
            print(f"[CharacterProfileWorkflow] 基础信息长度: {len(basic_info) if basic_info else 0}")
            print(f"[CharacterProfileWorkflow] 选中类别: {selected_categories}")
            print(f"[CharacterProfileWorkflow] 选中知识集合: {selected_collections}")
            
            logger.info("===== 开始生成角色资料 =====")
            logger.info(f"角色名称: {character_name}")
            logger.info(f"基础信息长度: {len(basic_info) if basic_info else 0}")
            logger.info(f"选中类别: {selected_categories}")
            logger.info(f"选中知识集合: {selected_collections}")
            
            # 设置工作流图
            print("[CharacterProfileWorkflow] 正在设置工作流图...")
            logger.info("正在设置工作流图...")
            compiled_graph = await self.setup_graph()
            
            # 创建LLM实例（如果配置可用）
            llm = None
            if self.llm_config:
                print(f"[CharacterProfileWorkflow] 创建LLM实例，配置: {self.llm_config}")
                logger.info(f"创建LLM实例，配置: {self.llm_config}")
                llm = LLMFactory.create(self.llm_config)
                print(f"[CharacterProfileWorkflow] LLM实例创建完成: {llm}")
                logger.info(f"LLM实例创建完成: {llm}")
            else:
                print("[CharacterProfileWorkflow] 警告: 未提供LLM配置")
                logger.warning("未提供LLM配置")
            
            # 准备输入状态
            initial_state = {
                'character_name': character_name,
                'basic_info': basic_info,
                'selected_categories': selected_categories or [],
                'selected_collections': selected_collections or [],
                'llm': llm  # 传递LLM对象到状态中
            }
            
            print(f"[CharacterProfileWorkflow] 准备执行工作流，初始状态键: {list(initial_state.keys())}")
            logger.info(f"准备执行工作流，初始状态键: {list(initial_state.keys())}")
            
            # 执行工作流
            print("[CharacterProfileWorkflow] 开始执行compiled_graph.invoke()...")
            logger.info("开始执行compiled_graph.invoke()...")
            result = await compiled_graph.invoke(initial_state)
            
            print(f"[CharacterProfileWorkflow] 工作流执行完成，结果键: {list(result.keys()) if isinstance(result, dict) else type(result)}")
            logger.info(f"工作流执行完成，结果键: {list(result.keys()) if isinstance(result, dict) else type(result)}")
            
            return result
            
        except Exception as e:
            print(f"[CharacterProfileWorkflow] 角色资料生成工作流执行失败: {e}")
            logger.error(f"角色资料生成工作流执行失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }
    
    async def batch_generate_profiles(self, 
                                    profiles_data: List[Dict[str, Any]],
                                    selected_collections: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        批量生成角色资料
        
        Args:
            profiles_data: 角色数据列表，每个包含character_name和basic_info
            selected_collections: 选中的知识集合列表
            
        Returns:
            批量生成结果列表
        """
        results = []
        
        for profile_data in profiles_data:
            character_name = profile_data.get('character_name', '')
            basic_info = profile_data.get('basic_info', '')
            selected_categories = profile_data.get('selected_categories')
            
            if not character_name or not basic_info:
                results.append({
                    'character_name': character_name,
                    'success': False,
                    'error': '缺少必要参数'
                })
                continue
            
            logger.info(f"正在生成角色资料: {character_name}")
            
            try:
                result = await self.generate_character_profile(
                    character_name=character_name,
                    basic_info=basic_info,
                    selected_categories=selected_categories,
                    selected_collections=selected_collections
                )
                results.append(result)
                
                # 添加延迟避免请求过快
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"生成角色 {character_name} 的资料失败: {e}")
                results.append({
                    'character_name': character_name,
                    'success': False,
                    'error': str(e)
                })
        
        return results
    
    def get_available_categories(self) -> List[str]:
        """获取可用的资料类别"""
        generator_node = CharacterProfileGeneratorNode()
        return list(generator_node.profile_template.keys())
    
    def get_available_collections(self) -> List[str]:
        """获取可用的知识集合"""
        return [coll.name for coll in self.available_collections]
    
    async def import_knowledge_from_file(self, 
                                       collection_name: str, 
                                       file_path: str,
                                       description: str = "") -> bool:
        """
        从文件导入知识到指定集合
        
        Args:
            collection_name: 集合名称
            file_path: 文件路径
            description: 集合描述
            
        Returns:
            是否导入成功
        """
        try:
            # 创建集合（如果不存在）
            await self.knowledge_base.create_collection(
                name=collection_name,
                description=description
            )
            
            # 导入文件
            success = await self.knowledge_base.import_from_text_file(
                collection_name=collection_name,
                file_path=file_path
            )
            
            if success:
                # 更新可用集合列表
                self._load_available_collections()
            
            return success
            
        except Exception as e:
            logger.error(f"导入知识库失败: {e}")
            return False
    
    def get_available_categories(self) -> List[str]:
        """获取可用的资料类别"""
        try:
            # 从人物资料需求表格中读取类别
            categories = set()
            template_file = Path("workspace/input/主角人物资料需求表格.csv")
            if template_file.exists():
                import csv
                with open(template_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        category = row.get('类别', '').strip()
                        if category:
                            categories.add(category)
            
            # 转换为列表并排序
            categories_list = sorted(list(categories))
            
            # 如果没有从CSV读取到，使用默认类别
            if not categories_list:
                categories_list = [
                    "基本信息", "外貌特征", "性格特征", "背景故事", 
                    "技能能力", "人际关系", "个人物品", "行为习惯"
                ]
            
            return categories_list
        except Exception as e:
            logger.error(f"获取资料类别失败: {e}")
            return ["基本信息", "外貌特征", "性格特征", "背景故事"]
    
    def get_available_collections(self) -> List[str]:
        """获取可用的知识集合"""
        try:
            collections = self.knowledge_base.list_collections()
            return [coll.name for coll in collections]
        except Exception as e:
            logger.error(f"获取知识集合失败: {e}")
            return []
    
    
    async def batch_generate_profiles(self,
                                    profiles_data: List[Dict[str, Any]],
                                    selected_collections: List[str]) -> List[Dict[str, Any]]:
        """批量生成角色资料"""
        results = []
        
        for profile_data in profiles_data:
            character_name = profile_data.get('character_name', '未知角色')
            basic_info = profile_data.get('basic_info', '')
            categories = profile_data.get('selected_categories', self.get_available_categories()[:3])
            
            try:
                result = await self.generate_character_profile(
                    character_name=character_name,
                    basic_info=basic_info,
                    selected_categories=categories,
                    selected_collections=selected_collections
                )
                
                results.append({
                    'character_name': character_name,
                    'success': result['success'],
                    'output_file': result.get('output_file', ''),
                    'error': result.get('error', '')
                })
                
            except Exception as e:
                logger.error(f"批量生成角色 {character_name} 失败: {e}")
                results.append({
                    'character_name': character_name,
                    'success': False,
                    'output_file': '',
                    'error': str(e)
                })
        
        return results

# 便捷函数
async def generate_character_profile(character_name: str,
                                   basic_info: str,
                                   llm_config: Optional[LLMConfig] = None,
                                   selected_categories: Optional[List[str]] = None,
                                   selected_collections: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    便捷的角色资料生成函数
    
    Args:
        character_name: 角色名称
        basic_info: 基础人设信息
        llm_config: LLM配置
        selected_categories: 选中的类别列表
        selected_collections: 选中的知识集合列表
        
    Returns:
        生成结果
    """
    workflow = CharacterProfileWorkflow(llm_config)
    return await workflow.generate_character_profile(
        character_name=character_name,
        basic_info=basic_info,
        selected_categories=selected_categories,
        selected_collections=selected_collections
    ) 