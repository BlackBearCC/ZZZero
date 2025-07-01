"""
剧情生成工作流 - 基于Graph+Node的剧情创作系统
集成角色库、地点库、剧情生成等功能
"""

import json
import asyncio
import csv
import random
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

logger = logging.getLogger(__name__)

class StoryWorkflow:
    """剧情生成工作流管理器"""
    
    def __init__(self, llm=None):
        self.llm = llm
        self.graph = None
        self.characters_data = {}
        self.locations_data = {}
        self.current_config = {
            'selected_characters': [],
            'selected_locations': [],
            'story_type': 'daily_life',  # daily_life, romance, adventure, mystery
            'story_length': 'medium',    # short, medium, long
            'relationship_depth': 'casual',  # casual, close, intimate
        }
        
        # 加载角色和地点数据
        self._load_game_data()
    
    def _load_game_data(self):
        """加载游戏角色和地点数据"""
        try:
            # 加载角色数据
            char_path = os.path.join(os.path.dirname(__file__), '../../config/yunhub_characters.json')
            if os.path.exists(char_path):
                with open(char_path, 'r', encoding='utf-8') as f:
                    self.characters_data = json.load(f)
            
            # 加载地点数据
            loc_path = os.path.join(os.path.dirname(__file__), '../../config/yunhub_locations.json')
            if os.path.exists(loc_path):
                with open(loc_path, 'r', encoding='utf-8') as f:
                    self.locations_data = json.load(f)
                    
        except Exception as e:
            print(f"加载游戏数据失败: {e}")
    
    def get_characters_list(self) -> List[Dict[str, Any]]:
        """获取角色列表"""
        characters = []
        char_list = self.characters_data.get("角色列表", {})
        
        for name, info in char_list.items():
            characters.append({
                'name': name,
                'age': info.get('年龄', '未知'),
                'personality': info.get('性格', ''),
                'description': info.get('简介', ''),
                'locations': info.get('活动地点', []),
                'plots': info.get('可触发剧情', [])
            })
        
        return characters
    
    def get_locations_list(self) -> List[Dict[str, Any]]:
        """获取地点列表"""
        locations = []
        districts = self.locations_data.get("districts", {})
        
        for district_name, district_info in districts.items():
            district_locations = district_info.get("locations", {})
            for loc_name, loc_info in district_locations.items():
                locations.append({
                    'name': loc_info.get('name', loc_name),
                    'type': loc_info.get('type', ''),
                    'district': district_info.get('name', district_name),
                    'description': loc_info.get('description', ''),
                    'atmosphere': loc_info.get('atmosphere', ''),
                    'keywords': loc_info.get('keywords', [])
                })
        
        return locations
    
    def update_config(self, config_updates: Dict[str, Any]):
        """更新工作流配置"""
        self.current_config.update(config_updates)
    
    async def create_story_graph(self) -> StateGraph:
        """创建剧情生成图工作流"""
        self.graph = StateGraph(name="story_generation_workflow")
        
        # 创建节点
        story_plan_node = StoryPlanningNode("story_planning", self.llm)
        character_analysis_node = CharacterAnalysisNode("character_analysis", self.llm)
        plot_generation_node = PlotGenerationNode("plot_generation", self.llm)
        csv_export_node = CSVExportNode("csv_export", self.llm)
        
        # 添加节点到图
        self.graph.add_node("story_planning", story_plan_node)
        self.graph.add_node("character_analysis", character_analysis_node)
        self.graph.add_node("plot_generation", plot_generation_node)
        self.graph.add_node("csv_export", csv_export_node)
        
        # 定义节点连接关系
        self.graph.add_edge("story_planning", "character_analysis")
        self.graph.add_edge("character_analysis", "plot_generation")
        self.graph.add_edge("plot_generation", "csv_export")
        
        # 设置入口点
        self.graph.set_entry_point("story_planning")
        
        return self.graph
    
    async def execute_story_generation(self, config: Dict[str, Any]) -> TaskResult:
        """执行剧情生成工作流"""
        if not self.graph:
            await self.create_story_graph()
        
        # 准备初始输入
        initial_input = {
            'characters_data': self.characters_data,
            'locations_data': self.locations_data,
            'config': config,
            'selected_characters': config.get('selected_characters', []),
            'selected_locations': config.get('selected_locations', []),
            'story_type': config.get('story_type', 'daily_life'),
            'story_length': config.get('story_length', 'medium'),
            'relationship_depth': config.get('relationship_depth', 'casual')
        }
        
        # 编译并执行图工作流
        compiled_graph = self.graph.compile()
        result = await compiled_graph.invoke(initial_input)
        
        return result

    async def execute_workflow_stream(self, config: Dict[str, Any], workflow_chat):
        """流式执行工作流"""
        try:
            # 准备初始输入
            initial_input = {
                'characters_data': self.characters_data,
                'locations_data': self.locations_data,
                'config': config,
                'selected_characters': config.get('selected_characters', []),
                'selected_locations': config.get('selected_locations', []),
                'story_type': config.get('story_type', 'daily_life'),
                'story_length': config.get('story_length', 'medium'),
                'relationship_depth': config.get('relationship_depth', 'casual'),
                'workflow_chat': workflow_chat,  # 传递UI更新器
                'llm': self.llm  # 传递LLM实例
            }
            
            # 创建图工作流
            if not self.graph:
                await self.create_story_graph()
            
            # 手动逐步执行每个节点
            current_state = initial_input.copy()
            
            # ===== 执行节点1：剧情规划 =====
            yield (
                workflow_chat.update_node_state("planning", "active"),
                "",
                "剧情规划开始执行...",
                False
            )
            
            planning_node = self.graph.nodes["story_planning"]
            # 改为流式执行，支持实时更新
            async for chunk_update in planning_node.execute_stream(current_state):
                current_state = chunk_update  # 更新状态
                yield (
                    workflow_chat._create_workflow_progress(),
                    "",
                    "剧情规划执行中...",
                    False
                )
            
            yield (
                workflow_chat.update_node_state("planning", "completed"),
                "",
                "剧情规划完成",
                False
            )
            
            # ===== 执行节点2：角色分析 =====
            yield (
                workflow_chat.update_node_state("character", "active"),
                "",
                "角色分析开始执行...",
                False
            )
            
            character_node = self.graph.nodes["character_analysis"]
            # 改为流式执行，支持实时更新
            async for chunk_update in character_node.execute_stream(current_state):
                current_state = chunk_update  # 更新状态
                yield (
                    workflow_chat._create_workflow_progress(),
                    "",
                    "角色分析执行中...",
                    False
                )
            
            yield (
                workflow_chat.update_node_state("character", "completed"),
                "",
                "角色分析完成",
                False
            )
            
            # ===== 执行节点3：剧情生成 =====
            yield (
                workflow_chat.update_node_state("plot", "active"),
                "",
                "剧情生成开始执行...",
                False
            )
            
            plot_node = self.graph.nodes["plot_generation"]
            # 改为流式执行，支持实时更新
            async for chunk_update in plot_node.execute_stream(current_state):
                current_state = chunk_update  # 更新状态
                yield (
                    workflow_chat._create_workflow_progress(),
                    "",
                    "剧情生成执行中...",
                    False
                )
            
            yield (
                workflow_chat.update_node_state("plot", "completed"),
                "",
                "剧情生成完成",
                False
            )
            
            # ===== 执行节点4：CSV导出 =====
            yield (
                workflow_chat.update_node_state("export", "active"),
                "",
                "CSV导出开始执行...",
                False
            )
            
            csv_node = self.graph.nodes["csv_export"]
            current_state = await csv_node.execute(current_state)
            
            yield (
                workflow_chat.update_node_state("export", "completed"),
                "",
                "工作流执行完成",
                False
            )
                
        except Exception as e:
            logger.error(f"工作流流式执行失败: {e}")
            await workflow_chat.add_node_message(
                "系统",
                f"工作流执行失败: {str(e)}",
                "error"
            )
            yield (
                workflow_chat.update_node_state("planning", "error"),
                "",
                "",
                False
            )


class StoryPlanningNode(BaseNode):
    """剧情规划节点 - 分析角色关系和故事大纲"""
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行剧情规划 - 流式版本"""
        print("🎯 开始剧情规划...")
        
        workflow_chat = input_data.get('workflow_chat')
        llm = input_data.get('llm')
        selected_characters = input_data.get('selected_characters', [])
        selected_locations = input_data.get('selected_locations', [])
        story_type = input_data.get('story_type', 'daily_life')
        relationship_depth = input_data.get('relationship_depth', 'casual')
        
        # 更新UI - 开始状态
        if workflow_chat:
            await workflow_chat.add_node_message(
                "剧情规划",
                "正在分析角色关系和地点配置，生成剧情框架...",
                "progress"
            )
        
        # 构建LLM提示词
        planning_prompt = f"""
请基于以下信息制定详细的剧情规划框架：

**角色信息：**
{', '.join(selected_characters)}

**地点信息：**
{', '.join(selected_locations)}

**剧情类型：** {story_type}
**关系深度：** {relationship_depth}

请生成：
1. 故事主题和核心冲突
2. 角色关系网络图
3. 主要剧情线（开端-发展-高潮-结局）
4. 各地点的作用和意义
5. 关键事件节点（至少3个）

请以结构化的方式输出，包含具体的情节细节。
"""
        
        # 流式调用LLM
        full_content = ""
        if llm:
            try:
                # 构建消息列表
                message = Message(role=MessageRole.USER, content=planning_prompt)
                messages = [message]
                
                logger.info(f"开始调用LLM流式生成，消息数量: {len(messages)}")
                logger.info(f"LLM类型: {type(llm)}")
                logger.info(f"提示词长度: {len(planning_prompt)}")
                
                # 使用think模式流式调用，不设置超时时间
                chunk_count = 0
                async for chunk in llm.stream_generate(
                    messages, 
                    mode="think"  # 使用think模式
                ):
                    chunk_count += 1
                    if chunk_count % 10 == 0:  # 每10个chunk记录一次
                        logger.info(f"剧情规划: 已接收 {chunk_count} 个chunk，内容长度: {len(full_content)}")
                    
                    full_content += chunk
                    
                    # 实时更新UI - 确保每个chunk都立即显示
                    if workflow_chat:
                        try:
                            await workflow_chat.add_node_message(
                                "剧情规划",
                                full_content,
                                "streaming"
                            )
                            # 小延时确保UI更新
                            await asyncio.sleep(0.01)
                            
                        except Exception as ui_error:
                            logger.warning(f"UI更新失败: {ui_error}")
                
                logger.info(f"LLM流式生成完成，总共接收 {chunk_count} 个chunk，最终内容长度: {len(full_content)}")
                        
            except Exception as e:
                error_msg = f"LLM流式调用失败: {type(e).__name__}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                raise Exception(error_msg)
        else:
            error_msg = "LLM未初始化"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        # 更新UI - 完成状态
        if workflow_chat:
            await workflow_chat.add_node_message(
                "剧情规划",
                full_content,
                "completed"
            )
        
        # 传递给下一个节点
        output_data = input_data.copy()
        output_data['planning_result'] = full_content
        
        print("✅ 剧情规划完成")
        return output_data
    
    async def execute_stream(self, input_data: Dict[str, Any]):
        """流式执行剧情规划节点"""
        # 先执行节点
        result = await self.execute(input_data)
        # 返回结果作为流式更新
        yield result


class CharacterAnalysisNode(BaseNode):
    """角色分析节点 - 深度分析角色特征和行为模式"""
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行角色分析 - 流式版本"""
        print("👥 开始角色分析...")
        
        workflow_chat = input_data.get('workflow_chat')
        llm = input_data.get('llm')
        selected_characters = input_data.get('selected_characters', [])
        planning_result = input_data.get('planning_result', '')
        
        # 更新UI - 开始状态
        if workflow_chat:
            await workflow_chat.add_node_message(
                "角色分析",
                "正在深入分析角色属性和关系网络...",
                "progress"
            )
        
        # 构建角色分析提示词
        character_prompt = f"""
基于以下剧情规划，对每个角色进行深入分析：

**剧情规划背景：**
{planning_result[:500]}...

**需要分析的角色：**
{', '.join(selected_characters)}

请为每个角色生成：
1. 详细性格描述和行为特征
2. 在剧情中的作用和地位
3. 与其他角色的具体关系
4. 角色动机和目标
5. 角色弧光（成长轨迹）
6. 典型对话风格示例

请以角色名为标题，分别详细描述每个角色。
"""
        
        # 流式调用LLM
        full_content = ""
        if llm:
            try:
                # 构建消息列表
                message = Message(role=MessageRole.USER, content=character_prompt)
                messages = [message]
                
                logger.info(f"角色分析: 开始调用LLM流式生成，提示词长度: {len(character_prompt)}")
                
                # 不设置超时时间的流式调用
                chunk_count = 0
                async for chunk in llm.stream_generate(messages):
                    chunk_count += 1
                    if chunk_count % 10 == 0:  # 每10个chunk记录一次
                        logger.info(f"角色分析: 已接收 {chunk_count} 个chunk，内容长度: {len(full_content)}")
                    
                    full_content += chunk
                    
                    # 实时更新UI
                    if workflow_chat:
                        try:
                            await workflow_chat.add_node_message(
                                "角色分析",
                                full_content,
                                "streaming"
                            )
                            # 小延时确保UI更新
                            await asyncio.sleep(0.01)
                        except Exception as ui_error:
                            logger.warning(f"UI更新失败: {ui_error}")
                
                logger.info(f"角色分析: LLM流式生成完成，总共接收 {chunk_count} 个chunk")
                        
            except Exception as e:
                error_msg = f"角色分析LLM流式调用失败: {type(e).__name__}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                raise Exception(error_msg)
        else:
            error_msg = "角色分析: LLM未初始化"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        # 更新UI - 完成状态
        if workflow_chat:
            await workflow_chat.add_node_message(
                "角色分析",
                full_content,
                "completed"
            )
        
        output_data = input_data.copy()
        output_data['character_analysis'] = full_content
        
        print("✅ 角色分析完成")
        return output_data
    
    async def execute_stream(self, input_data: Dict[str, Any]):
        """流式执行角色分析节点"""
        # 先执行节点
        result = await self.execute(input_data)
        # 返回结果作为流式更新
        yield result


class PlotGenerationNode(BaseNode):
    """剧情生成节点 - 生成具体的剧情事件"""
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行剧情生成 - 流式版本"""
        print("📚 开始生成剧情...")
        
        workflow_chat = input_data.get('workflow_chat')
        llm = input_data.get('llm')
        config = input_data.get('config', {})
        character_analysis = input_data.get('character_analysis', '')
        planning_result = input_data.get('planning_result', '')
        
        # 更新UI - 开始状态
        if workflow_chat:
            await workflow_chat.add_node_message(
                "剧情生成",
                "正在生成具体的剧情事件和对话内容...",
                "progress"
            )
        
        # 构建剧情生成提示词
        plot_prompt = f"""
基于前面的规划和角色分析，生成具体的剧情内容：

**配置参数：**
- 剧情类型：{config.get('story_type', 'daily_life')}
- 剧情长度：{config.get('story_length', 'medium')}
- 关系深度：{config.get('relationship_depth', 'casual')}

**剧情规划：**
{planning_result[:400]}...

**角色分析结果：**
{character_analysis[:400]}...

请生成：
1. 详细的剧情事件序列（按时间顺序）
2. 每个事件的具体场景描述
3. 角色对话内容（至少3段重要对话）
4. 事件触发条件和完成条件
5. 分支剧情选项（如果有）
6. 情感张力点和戏剧冲突

输出格式要求：
- 事件ID：事件名称
- 场景：具体地点和环境
- 参与角色：主要和次要角色
- 对话内容：关键对话
- 触发条件：什么情况下发生
- 结果：对剧情的影响
"""
        
        # 流式调用LLM
        full_content = ""
        if llm:
            try:
                # 构建消息列表
                message = Message(role=MessageRole.USER, content=plot_prompt)
                messages = [message]
                
                logger.info(f"剧情生成: 开始调用LLM流式生成，提示词长度: {len(plot_prompt)}")
                
                # 不设置超时时间的流式调用
                chunk_count = 0
                async for chunk in llm.stream_generate(messages):
                    chunk_count += 1
                    if chunk_count % 10 == 0:  # 每10个chunk记录一次
                        logger.info(f"剧情生成: 已接收 {chunk_count} 个chunk，内容长度: {len(full_content)}")
                    
                    full_content += chunk
                    
                    # 实时更新UI
                    if workflow_chat:
                        try:
                            await workflow_chat.add_node_message(
                                "剧情生成",
                                full_content,
                                "streaming"
                            )
                            # 小延时确保UI更新
                            await asyncio.sleep(0.01)
                        except Exception as ui_error:
                            logger.warning(f"UI更新失败: {ui_error}")
                
                logger.info(f"剧情生成: LLM流式生成完成，总共接收 {chunk_count} 个chunk")
                        
            except Exception as e:
                error_msg = f"剧情生成LLM流式调用失败: {type(e).__name__}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                raise Exception(error_msg)
        else:
            error_msg = "剧情生成: LLM未初始化"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        # 更新UI - 完成状态
        if workflow_chat:
            await workflow_chat.add_node_message(
                "剧情生成",
                full_content,
                "completed"
            )
        
        output_data = input_data.copy()
        output_data['plot_content'] = full_content
        
        print("✅ 剧情生成完成")
        return output_data
    
    async def execute_stream(self, input_data: Dict[str, Any]):
        """流式执行剧情生成节点"""
        # 先执行节点
        result = await self.execute(input_data)
        # 返回结果作为流式更新
        yield result


class CSVExportNode(BaseNode):
    """CSV导出节点 - 将剧情数据导出为CSV格式"""
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行CSV导出"""
        print("📄 开始导出CSV...")
        
        workflow_chat = input_data.get('workflow_chat')
        plot_content = input_data.get('plot_content', '')
        
        # 更新UI - 开始状态
        if workflow_chat:
            await workflow_chat.add_node_message(
                "CSV导出",
                "正在将剧情数据导出为CSV格式...",
                "progress"
            )
        
        try:
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"story_plot_{timestamp}.csv"
            
            # 确保输出目录存在
            output_dir = Path("workspace/output")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            filepath = output_dir / filename
            
            # 构建CSV内容（简化版，直接使用生成的剧情内容）
            csv_headers = [
                "剧情ID", "NPC", "剧情名", "剧情阶段", "触发地点", 
                "前置条件", "描述", "关键事件", "触发概率", 
                "完成条件", "解锁剧情", "状态"
            ]
            
            # 将剧情内容分段并转换为CSV格式
            lines = plot_content.split('\n')
            csv_data = []
            
            # 简单解析剧情内容
            for i, line in enumerate(lines[:10]):  # 取前10行作为剧情事件
                if line.strip():
                    csv_data.append([
                        f"PLOT_{i+1:03d}",  # 剧情ID
                        "自动生成",  # NPC
                        line[:20] + "..." if len(line) > 20 else line,  # 剧情名
                        f"阶段{i+1}",  # 剧情阶段
                        "默认地点",  # 触发地点
                        "无" if i == 0 else f"完成PLOT_{i:03d}",  # 前置条件
                        line,  # 描述
                        f"事件{i+1}",  # 关键事件
                        f"{100-i*10}%",  # 触发概率
                        "完成对话",  # 完成条件
                        f"PLOT_{i+2:03d}" if i < 9 else "",  # 解锁剧情
                        "未触发"  # 状态
                    ])
            
            # 写入CSV文件
            with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(csv_headers)
                writer.writerows(csv_data)
            
            # 获取绝对路径
            abs_filepath = str(filepath.absolute())
            
            # 生成结果信息
            result = f"""✅ CSV导出成功！

**文件信息：**
- 文件名：{filename}
- 保存路径：{filepath}
- 绝对路径：{abs_filepath}
- 文件大小：{len(plot_content)} 字符

**统计信息：**
- 生成剧情事件数：{len(csv_data)} 个
- 原始内容长度：{len(plot_content)} 字符

**访问文件：**
🔗 点击打开文件：file:///{abs_filepath.replace(os.sep, '/')}
📂 在文件夹中查看：{filepath.parent}

**下载说明：**
文件已保存到项目的 workspace/output 目录中。
"""
            
            # 更新UI - 完成状态
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "CSV导出",
                    result,
                    "complete"
                )
            
            output_data = input_data.copy()
            output_data['export_file'] = str(filepath)
            output_data['csv_data'] = csv_data
            output_data['csv_headers'] = csv_headers
            
            print(f"✅ CSV导出完成: {filepath}")
            return output_data
            
        except Exception as e:
            error_msg = f"CSV导出失败: {str(e)}"
            print(error_msg)
            
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "CSV导出",
                    error_msg,
                    "error"
                )
            
            raise e 