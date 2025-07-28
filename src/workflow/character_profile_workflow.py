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

from core.graph import StateGraph
from core.base import BaseNode
from llm.base import LLMFactory
from core.types import LLMConfig, TaskResult, Message, MessageRole
from tools.knowledge_base_manager import GlobalKnowledgeBase
from tools.mcp_tools import MCPToolManager

logger = logging.getLogger(__name__)

class CharacterProfileGeneratorNode(BaseNode):
    """角色资料生成节点"""
    
    def __init__(self, 
                 name: str = "character_profile_generator",
                 llm_config: Optional[LLMConfig] = None,
                 knowledge_base: Optional[GlobalKnowledgeBase] = None):
        super().__init__(name, llm_config)
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
        """执行角色资料生成"""
        try:
            # 获取输入参数
            character_name = state.get('character_name', '')
            basic_info = state.get('basic_info', '')
            selected_categories = state.get('selected_categories', [])
            selected_collections = state.get('selected_collections', [])
            
            if not character_name or not basic_info:
                return {
                    'success': False,
                    'error': '缺少必要参数：角色名称和基础信息'
                }
            
            # 如果未指定类别，使用所有类别
            if not selected_categories:
                selected_categories = list(self.profile_template.keys())
            
            # 生成角色资料
            generated_profile = {}
            
            for category in selected_categories:
                if category not in self.profile_template:
                    logger.warning(f"未知类别: {category}")
                    continue
                
                logger.info(f"正在生成类别: {category}")
                category_data = await self._generate_category_data(
                    character_name, basic_info, category, selected_collections
                )
                generated_profile[category] = category_data
            
            # 保存生成的资料
            output_file = await self._save_profile(character_name, generated_profile)
            
            return {
                'success': True,
                'generated_profile': generated_profile,
                'output_file': output_file,
                'character_name': character_name
            }
            
        except Exception as e:
            logger.error(f"角色资料生成失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _generate_category_data(self, 
                                    character_name: str, 
                                    basic_info: str, 
                                    category: str,
                                    selected_collections: List[str]) -> Dict[str, Any]:
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
        if self.llm:
            response = await self.llm.agenerate(prompt)
            return self._parse_generation_response(response, category_items)
        else:
            logger.warning("LLM未配置，返回空结果")
            return {}
    
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
        
        # 加载可用的知识集合
        self.available_collections = []
        self._load_available_collections()
    
    def _load_available_collections(self):
        """加载可用的知识集合"""
        try:
            self.available_collections = self.knowledge_base.list_collections()
            logger.info(f"已加载{len(self.available_collections)}个知识集合")
        except Exception as e:
            logger.error(f"加载知识集合失败: {e}")
    
    async def setup_graph(self) -> StateGraph:
        """设置工作流图"""
        if self.graph:
            return self.graph
        
        # 创建LLM实例
        llm = None
        if self.llm_config:
            llm = LLMFactory.create(self.llm_config)
        
        # 创建节点
        generator_node = CharacterProfileGeneratorNode(
            llm_config=self.llm_config,
            knowledge_base=self.knowledge_base
        )
        
        # 如果LLM配置可用，为节点设置LLM
        if llm:
            generator_node.llm = llm
        
        # 创建图
        self.graph = StateGraph()
        self.graph.add_node("generate_profile", generator_node)
        self.graph.set_entry_point("generate_profile")
        
        # 添加条件边来处理结束
        def end_condition(state: Dict[str, Any]) -> str:
            # 生成完成后结束
            return "END"
        
        self.graph.add_conditional_edges("generate_profile", end_condition)
        
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
            # 设置工作流图
            graph = await self.setup_graph()
            
            # 准备输入状态
            initial_state = {
                'character_name': character_name,
                'basic_info': basic_info,
                'selected_categories': selected_categories or [],
                'selected_collections': selected_collections or []
            }
            
            # 执行工作流
            result = await graph.ainvoke(initial_state)
            
            return result
            
        except Exception as e:
            logger.error(f"角色资料生成工作流执行失败: {e}")
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
            categories = []
            template_file = Path("workspace/input/主角人物资料需求表格.csv")
            if template_file.exists():
                import csv
                with open(template_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    headers = reader.fieldnames
                    if headers and len(headers) > 1:
                        # 跳过第一列（通常是字段名），获取类别列
                        categories = [h for h in headers[1:] if h and h.strip()]
            
            # 如果没有从CSV读取到，使用默认类别
            if not categories:
                categories = [
                    "基本信息", "外貌特征", "性格特征", "背景故事", 
                    "技能能力", "人际关系", "个人物品", "行为习惯"
                ]
            
            return categories
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
    
    async def generate_character_profile(self,
                                       character_name: str,
                                       basic_info: str,
                                       selected_categories: List[str],
                                       selected_collections: List[str]) -> Dict[str, Any]:
        """生成角色资料"""
        try:
            # 准备输入数据
            input_data = {
                'character_name': character_name,
                'basic_info': basic_info,
                'selected_categories': selected_categories,
                'selected_collections': selected_collections,
                'knowledge_context': "",
                'generated_profile': {}
            }
            
            # 如果选择了知识库，先获取相关知识
            if selected_collections:
                try:
                    knowledge_context = []
                    for collection_name in selected_collections:
                        # 使用角色名称和基础信息进行查询
                        query_text = f"{character_name} {basic_info}"
                        results = await self.knowledge_base.query_documents(
                            collection_name=collection_name,
                            query_text=query_text,
                            n_results=3
                        )
                        
                        if results:
                            for result in results:
                                knowledge_context.append(f"[{collection_name}] {result['document']}")
                    
                    input_data['knowledge_context'] = "\n\n".join(knowledge_context)
                    logger.info(f"获取到知识上下文，共{len(knowledge_context)}条")
                    
                except Exception as e:
                    logger.warning(f"获取知识上下文失败: {e}")
                    input_data['knowledge_context'] = ""
            
            # 执行工作流
            result = await self.run(input_data)
            
            if result.success:
                # 保存结果到文件
                output_dir = Path("workspace/output")
                output_dir.mkdir(exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = output_dir / f"character_profile_{character_name}_{timestamp}.json"
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result.data, ensure_ascii=False, indent=2)
                
                return {
                    'success': True,
                    'generated_profile': result.data.get('generated_profile', {}),
                    'output_file': str(output_file)
                }
            else:
                return {
                    'success': False,
                    'error': result.error or "生成失败"
                }
                
        except Exception as e:
            logger.error(f"生成角色资料失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
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