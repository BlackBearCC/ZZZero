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
import aiofiles
import aiofiles.os

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
from pydantic import BaseModel, Field

# Pydantic 数据模型
class ProfileItem(BaseModel):
    """资料条目模型"""
    item: str = Field(..., description="条目名称")
    content: str = Field("", description="条目内容")
    keywords: str = Field("", description="关键词")
    notes: str = Field("", description="备注")

class ProfileCategory(BaseModel):
    """资料类别模型"""
    name: str = Field(..., description="类别名称")
    items: List[ProfileItem] = Field(default_factory=list, description="条目列表")

class ProfileRequest(BaseModel):
    """角色资料生成请求模型"""
    name: str = Field(..., description="角色名称")
    info: str = Field(..., description="基础信息")
    categories: List[str] = Field(default_factory=list, description="选中的类别")
    collections: List[str] = Field(default_factory=list, description="选中的知识集合")

class ProfileResult(BaseModel):
    """角色资料生成结果模型"""
    success: bool = Field(..., description="是否成功")
    name: str = Field("", description="角色名称")
    profile: Dict[str, Any] = Field(default_factory=dict, description="生成的资料")
    output_file: str = Field("", description="输出文件路径")
    error: str = Field("", description="错误信息")
    progress: str = Field("", description="进度信息")

# 配置日志 - 强制输出到标准输出
import sys
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
    force=True
)
logger = logging.getLogger(__name__)

# 自定义异常类
class ProfileGenerationError(Exception):
    """角色资料生成异常"""
    pass

class TemplateLoadError(ProfileGenerationError):
    """模板加载异常"""
    pass

class LLMGenerationError(ProfileGenerationError):
    """LLM生成异常"""
    pass

class FileSaveError(ProfileGenerationError):
    """文件保存异常"""
    pass

class ProfileGeneratorNode(BaseNode):
    """角色资料生成节点"""
    
    def __init__(self, 
                 name: str = "profile_generator",
                 llm_config: Optional[LLMConfig] = None,
                 kb: Optional[GlobalKnowledgeBase] = None):
        super().__init__(name=name, node_type=NodeType.CUSTOM, stream=True)
        self.llm_config = llm_config
        self.kb = kb
        self.template = {}
    
    async def _load_template(self):
        """加载人物资料需求模板"""
        if self.template:  # 如果已加载，直接返回
            return
            
        try:
            template_file = Path("workspace/input/主角人物资料需求表格.csv")
            if not await aiofiles.os.path.exists(template_file):
                raise TemplateLoadError(f"人物资料需求表格不存在: {template_file}")
            
            async with aiofiles.open(template_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                if not content.strip():
                    raise TemplateLoadError("模板文件为空")
                    
                reader = csv.DictReader(content.splitlines())
                for row in reader:
                    if not row.get('类别'):
                        logger.warning(f"跳过无效行: {row}")
                        continue
                        
                    category = row['类别']
                    if category not in self.template:
                        self.template[category] = []
                    
                    try:
                        item = ProfileItem(
                            item=row.get('条目', ''),
                            content=row.get('内容', ''),
                            keywords=row.get('关键词', ''),
                            notes=row.get('备注', '')
                        )
                        self.template[category].append(item)
                    except Exception as e:
                        logger.warning(f"跳过无效条目 {row}: {e}")
                        continue
            
            if not self.template:
                raise TemplateLoadError("模板文件中没有有效数据")
                
            logger.info(f"已加载人物资料模板，共{len(self.template)}个类别")
            
        except TemplateLoadError:
            raise
        except Exception as e:
            raise TemplateLoadError(f"加载人物资料模板失败: {e}") from e
    
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """执行角色资料生成"""
        final_result = None
        async for result in self.execute_stream(state):
            final_result = result
        return final_result or {"success": False, "error": "执行失败"}
    
    async def execute_stream(self, state: Dict[str, Any]):
        """流式执行角色资料生成"""
        try:
            # 加载模板和参数
            await self._load_template()
            name = state.get('character_name', '')
            info = state.get('basic_info', '')
            categories = state.get('selected_categories', []) or list(self.template.keys())
            collections = state.get('selected_collections', [])
            llm = state.get('llm')
            
            if not name or not info:
                yield {"success": False, "error": "缺少必要参数：角色名称和基础信息"}
                return
            
            # 生成角色资料
            profile = {}
            for i, category in enumerate(categories):
                if category not in self.template:
                    continue
                    
                try:
                    data = await self._generate_category_data(name, info, category, collections, llm)
                    profile[category] = data
                    
                    # 流式输出进度
                    yield {
                        "success": False,
                        "progress": f"已完成 {i+1}/{len(categories)} 个类别",
                        "profile": profile.copy(),
                        "name": name
                    }
                except Exception as e:
                    profile[category] = {"错误": str(e)}
            
            # 保存和返回最终结果
            try:
                output_file = await self._save_profile(name, profile)
            except Exception:
                output_file = ""
            
            yield {
                "success": True,
                "profile": profile,
                "output_file": output_file,
                "name": name
            }
            
        except Exception as e:
            yield {"success": False, "error": str(e)}
    
    async def _generate_category_data(self, name: str, info: str, category: str, collections: List[str], llm=None) -> Dict[str, Any]:
        """生成特定类别的角色数据"""
        items = self.template.get(category, [])
        if not items:
            return {}
        
        # 构建知识库上下文
        context = ""
        if self.kb and collections:
            context = await self._gather_context(name, info, category, collections)
        
        # 构建生成提示
        system_content, user_content = self._build_prompt(name, info, category, items, context)
        
        # 调用LLM生成
        if not llm:
            raise LLMGenerationError("LLM未配置，无法生成角色资料")
        
        if not hasattr(llm, 'config') or not llm.config:
            raise LLMGenerationError("LLM配置未正确初始化")
        
        # 尝试初始化LLM（如果需要）
        if hasattr(llm, 'initialize'):
            await llm.initialize()
        
        from core.types import Message, MessageRole
        messages = [
            Message(role=MessageRole.SYSTEM, content=system_content),
            Message(role=MessageRole.USER, content=user_content)
        ]
        
        response = await llm.generate(messages)
        if not response or not hasattr(response, 'content'):
            raise LLMGenerationError("LLM返回空响应或格式错误")
        
        return self._parse_response(response.content, items)
    
    async def _gather_context(self, 
                                      name: str, 
                                      info: str, 
                                      category: str,
                                      collections: List[str]) -> str:
        """从知识库收集相关上下文信息"""
        if not self.kb:
            return ""
        
        # 构建查询文本
        queries = [
            f"{name} {category}",
            f"{name} 角色 {category}",
            info
        ]
        
        context_list = []
        
        for collection in collections:
            for query in queries:
                try:
                    results = await self.kb.query_documents(
                        collection_name=collection, query_text=query, n_results=3
                    )
                    for result in results:
                        context_list.append(f"来源：{collection}\n内容：{result['document']}\n")
                except Exception:
                    continue
        
        return "\n---\n".join(context_list) if context_list else ""
    
    def _build_prompt(self, 
                               name: str, 
                               info: str, 
                               category: str, 
                               items: List[ProfileItem],
                               context: str) -> tuple[str, str]:
        """构建生成提示，返回(system_content, user_content)"""
        
        # 静态的system content
        system_content = """你是一个专业的角色设定生成专家，专门负责为角色生成详细的背景资料。你的任务是根据提供的基础信息和参考资料，生成具体、详细、符合逻辑的角色资料。

## 生成规则
1. 每个条目都要有具体、详细的内容，不能为空
2. 内容要符合角色的整体设定和背景
3. 充分利用参考资料中的信息，但要合理融合到角色设定中
4. 保持内容的逻辑一致性和可信度
5. 摈弃游戏化或特殊资料的参考，专注于现实化的角色塑造
6. 输出格式为JSON，字段名使用中文

## 输出格式要求
必须严格按照以下JSON格式输出：
```json
{
    "条目1": "详细内容...",
    "条目2": "详细内容...",
    ...
}
```"""

        # 构建条目说明
        items_desc = []
        for item in items:
            desc = f"- 条目：{item.item}"
            if item.content:
                desc += f"\n  内容：{item.content}"
            if item.keywords:
                desc += f"\n  关键词：{item.keywords}"
            items_desc.append(desc)
        
        # 动态的user content
        user_content = f"""请为角色"{name}"生成详细的"{category}"类别资料。该资料将用于剧情设计时人物资料的补足。

## 角色基础信息
{info}

## 需要生成的类别：{category}
## 具体条目要求：
{chr(10).join(items_desc)}

## 参考资料
{context if context else "无额外参考资料"}

请开始生成："""
        
        return system_content, user_content
    
    def _parse_response(self, response: str, items: List[Dict]) -> Dict[str, Any]:
        """解析LLM生成的响应"""
        try:
            # 尝试提取JSON
            start = response.find('{')
            end = response.rfind('}') + 1
            
            if start >= 0 and end > start:
                content = response[start:end]
                data = json.loads(content)
                return data
            else:
                # 如果没有找到JSON，尝试按行解析
                logger.warning("未找到JSON格式，尝试按行解析")
                return self._parse_text(response, items)
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            return self._parse_text(response, items)
    
    def _parse_text(self, response: str, items: List[ProfileItem]) -> Dict[str, Any]:
        """解析文本格式的响应"""
        result = {}
        lines = response.split('\n')
        
        field = None
        content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检查是否是字段开始
            found = False
            for item in items:
                if item.item in line and ':' in line:
                    # 保存前一个字段
                    if field and content:
                        result[field] = '\n'.join(content).strip()
                    
                    # 开始新字段
                    field = item.item
                    part = line.split(':', 1)[1].strip()
                    content = [part] if part else []
                    found = True
                    break
            
            if not found and field:
                # 继续添加内容到当前字段
                content.append(line)
        
        # 保存最后一个字段
        if field and content:
            result[field] = '\n'.join(content).strip()
        
        return result
    
    async def _save_profile(self, name: str, data: Dict[str, Any]) -> str:
        """保存生成的角色资料"""
        try:
            if not name:
                raise FileSaveError("角色名称不能为空")
            if not data:
                raise FileSaveError("资料数据不能为空")
                
            # 创建输出目录
            output_dir = Path("workspace/output")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # 清理文件名中的非法字符
            safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"profile_{safe_name}_{timestamp}.json"
            output_file = output_dir / filename
            
            # 构建完整的输出数据
            try:
                output_data = {
                    'name': name,
                    'generated_at': datetime.now().isoformat(),
                    'data': data,
                    'metadata': {
                        'categories': len(data),
                        'fields': sum(len(cat_data) for cat_data in data.values() if isinstance(cat_data, dict))
                    }
                }
            except Exception as e:
                raise FileSaveError(f"构建输出数据失败: {e}") from e
            
            # 保存为JSON文件
            try:
                async with aiofiles.open(output_file, 'w', encoding='utf-8') as f:
                    json_content = json.dumps(output_data, ensure_ascii=False, indent=2)
                    await f.write(json_content)
            except Exception as e:
                raise FileSaveError(f"写入文件失败: {e}") from e
            
            logger.info(f"角色资料已保存: {output_file}")
            return str(output_file)
            
        except FileSaveError:
            raise
        except Exception as e:
            raise FileSaveError(f"保存角色资料失败: {e}") from e

class ProfileWorkflow:
    """角色资料生成工作流"""
    
    def __init__(self, llm_config: Optional[LLMConfig] = None, workspace_dir: str = "./workspace"):
        self.llm_config = llm_config
        self.workspace_dir = workspace_dir
        self.kb = GlobalKnowledgeBase(workspace_dir)
        self.mcp_tools = MCPToolManager()
        self.graph = None
        self.history_file = Path(workspace_dir) / "profile_history.json"
        
        # 加载可用的知识集合
        self.collections = []
        self._load_available_collections()
        
        # 加载历史记录
        self.history = []
    
    async def initialize(self):
        """异步初始化方法"""
        self.history = await self._load_history()
    
    def _load_available_collections(self):
        """加载可用的知识集合"""
        try:
            self.collections = self.kb.list_collections()
            logger.info(f"已加载{len(self.collections)}个知识集合")
        except Exception as e:
            logger.error(f"加载知识集合失败: {e}")
    
    async def _load_history(self) -> List[Dict[str, Any]]:
        """加载角色资料历史记录"""
        try:
            if await aiofiles.os.path.exists(self.history_file):
                async with aiofiles.open(self.history_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    data = json.loads(content)
                    # 保持最多10条记录
                    return data[-10:] if len(data) > 10 else data
            return []
        except Exception as e:
            logger.error(f"加载历史记录失败: {e}")
            return []
    
    async def _save_history(self, record: Dict[str, Any]):
        """保存角色资料历史记录"""
        try:
            # 添加新记录
            self.history.append(record)
            
            # 保持最多10条记录
            if len(self.history) > 10:
                self.history = self.history[-10:]
            
            # 确保目录存在
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存到文件
            async with aiofiles.open(self.history_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(self.history, ensure_ascii=False, indent=2))
                
            logger.info(f"已保存历史记录，当前共{len(self.history)}条")
        except Exception as e:
            logger.error(f"保存历史记录失败: {e}")
    
    def get_history_records(self) -> List[Dict[str, Any]]:
        """获取历史记录"""
        return self.history.copy()
    
    def get_history_by_name(self, name: str) -> List[Dict[str, Any]]:
        """根据角色名称获取历史记录"""
        return [record for record in self.history 
                if record.get('name', '').strip() == name.strip()]
    
    async def setup_graph(self) -> 'CompiledStateGraph':
        """设置工作流图"""
        if self.graph:
            print("[ProfileWorkflow] 使用已存在的工作流图")
            logger.info("使用已存在的工作流图")
            return self.graph
        
        print("[ProfileWorkflow] 开始创建工作流图...")
        logger.info("开始创建工作流图...")
        
        # 创建节点（不需要传递LLM配置）
        node = ProfileGeneratorNode(
            kb=self.kb
        )
        
        print(f"[ProfileWorkflow] 角色资料生成节点创建完成: {node}")
        logger.info(f"角色资料生成节点创建完成: {node}")
        
        # 创建图
        graph = StateGraph()
        graph.add_node("generate_profile", node)
        graph.set_entry_point("generate_profile")
        
        print("[ProfileWorkflow] StateGraph 节点和入口点设置完成")
        logger.info("StateGraph 节点和入口点设置完成")
        
        # 添加条件边来处理结束
        def end_condition(state: Dict[str, Any]) -> str:
            # 生成完成后结束
            print("[ProfileWorkflow] 执行结束条件判断")
            logger.info("执行结束条件判断")
            return "END"
        
        graph.add_conditional_edges("generate_profile", end_condition)
        
        print("[ProfileWorkflow] 条件边设置完成，开始编译图...")
        logger.info("条件边设置完成，开始编译图...")
        
        # 编译图
        self.graph = graph.compile()
        
        print(f"[ProfileWorkflow] 工作流图编译完成: {self.graph}")
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
            print(f"[ProfileWorkflow] ===== 开始生成角色资料 =====")
            print(f"[ProfileWorkflow] 角色名称: {character_name}")
            print(f"[ProfileWorkflow] 基础信息长度: {len(basic_info) if basic_info else 0}")
            print(f"[ProfileWorkflow] 选中类别: {selected_categories}")
            print(f"[ProfileWorkflow] 选中知识集合: {selected_collections}")
            
            logger.info("===== 开始生成角色资料 =====")
            logger.info(f"角色名称: {character_name}")
            logger.info(f"基础信息长度: {len(basic_info) if basic_info else 0}")
            logger.info(f"选中类别: {selected_categories}")
            logger.info(f"选中知识集合: {selected_collections}")
            
            # 设置工作流图
            print("[ProfileWorkflow] 正在设置工作流图...")
            logger.info("正在设置工作流图...")
            compiled_graph = await self.setup_graph()
            
            # 创建LLM实例（如果配置可用）
            llm = None
            if self.llm_config:
                print(f"[ProfileWorkflow] 创建LLM实例，配置: {self.llm_config}")
                logger.info(f"创建LLM实例，配置: {self.llm_config}")
                llm = LLMFactory.create(self.llm_config)
                print(f"[ProfileWorkflow] LLM实例创建完成: {llm}")
                logger.info(f"LLM实例创建完成: {llm}")
            else:
                print("[ProfileWorkflow] 警告: 未提供LLM配置")
                logger.warning("未提供LLM配置")
            
            # 准备输入状态
            initial_state = {
                'character_name': character_name,
                'basic_info': basic_info,
                'selected_categories': selected_categories or [],
                'selected_collections': selected_collections or [],
                'llm': llm  # 传递LLM对象到状态中
            }
            
            print(f"[ProfileWorkflow] 准备执行工作流，初始状态键: {list(initial_state.keys())}")
            logger.info(f"准备执行工作流，初始状态键: {list(initial_state.keys())}")
            
            # 执行工作流
            print("[ProfileWorkflow] 开始执行compiled_graph.invoke()...")
            logger.info("开始执行compiled_graph.invoke()...")
            result = await compiled_graph.invoke(initial_state)
            
            print(f"[ProfileWorkflow] 工作流执行完成，结果键: {list(result.keys()) if isinstance(result, dict) else type(result)}")
            logger.info(f"工作流执行完成，结果键: {list(result.keys()) if isinstance(result, dict) else type(result)}")
            
            return result
            
        except Exception as e:
            print(f"[ProfileWorkflow] 角色资料生成工作流执行失败: {e}")
            logger.error(f"角色资料生成工作流执行失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e)
            }
    
    async def generate_character_profile_stream(self, 
                                              character_name: str,
                                              basic_info: str,
                                              selected_categories: Optional[List[str]] = None,
                                              selected_collections: Optional[List[str]] = None):
        """
        流式生成角色资料
        
        Args:
            character_name: 角色名称
            basic_info: 基础人设信息
            selected_categories: 选中的类别列表，如果为None则生成所有类别
            selected_collections: 选中的知识集合列表
            
        Yields:
            生成过程中的实时结果
        """
        try:
            # 设置工作流图
            compiled_graph = await self.setup_graph()
            
            # 创建LLM实例（如果配置可用）
            llm = None
            if self.llm_config:
                llm = LLMFactory.create(self.llm_config)
            
            # 准备输入状态
            initial_state = {
                'character_name': character_name,
                'basic_info': basic_info,
                'selected_categories': selected_categories or [],
                'selected_collections': selected_collections or [],
                'llm': llm
            }
            
            # 执行工作流并流式返回结果
            async for result in compiled_graph.astream(initial_state):
                yield result
                
        except Exception as e:
            logger.error(f"角色资料生成工作流流式执行失败: {e}")
            yield {
                'success': False,
                'error': str(e)
            }
    

    
    async def get_available_categories(self) -> List[str]:
        """获取可用的资料类别"""
        try:
            # 从人物资料需求表格中读取类别
            categories = set()
            template_file = Path("workspace/input/主角人物资料需求表格.csv")
            if await aiofiles.os.path.exists(template_file):
                import csv
                async with aiofiles.open(template_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    reader = csv.DictReader(content.splitlines())
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
            collections = self.kb.list_collections()
            return [coll.name for coll in collections]
        except Exception as e:
            logger.error(f"获取知识集合失败: {e}")
            return []
    
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
            await self.kb.create_collection(
                name=collection_name,
                description=description
            )
            
            # 导入文件
            success = await self.kb.import_from_text_file(
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

# 便捷函数
async def generate_character_profile(name: str,
                                   info: str,
                                   llm_config: Optional[LLMConfig] = None,
                                   categories: Optional[List[str]] = None,
                                   collections: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    便捷的角色资料生成函数
    
    Args:
        name: 角色名称
        info: 基础人设信息
        llm_config: LLM配置
        categories: 选中的类别列表
        collections: 选中的知识集合列表
        
    Returns:
        生成结果
    """
    workflow = ProfileWorkflow(llm_config)
    return await workflow.generate_character_profile(
        character_name=name,
        basic_info=info,
        selected_categories=categories,
        selected_collections=collections
    ) 