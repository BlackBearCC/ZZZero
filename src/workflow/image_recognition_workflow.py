"""图片识别工作流 - 基于豆包/DoubaoLLM的图片识别系统
提供对图片的内容识别、标题生成和详细描述功能
"""

import json
import asyncio
import base64
import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import csv

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.graph import StateGraph
from core.base import BaseNode
from llm.base import LLMFactory
from core.types import LLMConfig, TaskResult, Message, MessageRole
from workflow.story_generator import StoryGenerationNode

logger = logging.getLogger(__name__)

class ImageRecognitionWorkflow:
    """图片识别工作流管理器"""
    
    def __init__(self, llm=None):
        self.llm = llm
        self.graph = None

        self.current_config = {
            'batch_size': 5,  # 每批处理的图片数量
            'csv_output': {
                'enabled': True,
                'output_dir': 'workspace/image_recognition_output',
                'filename': 'image_recognition_results.csv',
                'encoding': 'utf-8-sig'  # 支持中文的CSV编码
            }
        }
    
    def update_config(self, config_updates: Dict[str, Any]):
        """更新工作流配置"""
        self.current_config.update(config_updates)
    
    async def create_image_recognition_graph(self) -> StateGraph:
        """创建图片识别工作流图"""
        self.graph = StateGraph(name="image_recognition_workflow")
        
        # 创建节点
        image_loading_node = ImageLoadingNode()  # 图片加载和预处理节点
        recognition_node = ImageRecognitionNode()  # 图片识别节点
        save_result_node = ResultSaveNode()  # 结果保存节点
        story_generation_node = StoryGenerationNode()  # 故事生成节点
        
        # 添加节点到图
        self.graph.add_node("image_loading", image_loading_node)
        self.graph.add_node("image_recognition", recognition_node)
        self.graph.add_node("save_result", save_result_node)
        self.graph.add_node("story_generation", story_generation_node)
        
        # 定义节点连接关系
        self.graph.add_edge("image_loading", "image_recognition")
        self.graph.add_edge("image_recognition", "save_result")
        self.graph.add_edge("save_result", "story_generation")
        
        # 新增条件边：如果尚未完成全部批次，则回到图片加载节点
        def loop_condition(state):
            """当尚未完成全部批次时继续循环，否则结束"""
            if state.get('recognition_complete', False):
                return "__end__"
            return "image_loading"
        
        self.graph.add_conditional_edges("story_generation", loop_condition)
        
        # 设置入口点
        self.graph.set_entry_point("image_loading")
        
        return self.graph
    
    async def execute_workflow_stream(self, config: Dict[str, Any], workflow_chat, images=None):
        """流式执行图片识别工作流"""
        try:
            # 准备初始输入
            initial_input = {
                'config': config,
                'workflow_chat': workflow_chat,
                'llm': self.llm,
                'images': images or [],  # 图片路径列表
                'current_batch_index': 0,
                'recognition_complete': False
            }
            
            # 创建并编译图工作流
            if not self.graph:
                await self.create_image_recognition_graph()
            
            compiled_graph = self.graph.compile()
            
            # 使用图的流式执行
            async for stream_event in compiled_graph.stream(initial_input):
                event_type = stream_event.get('type')
                node_name = stream_event.get('node')
                
                if event_type == 'start':
                    yield (
                        workflow_chat._create_workflow_progress(),
                        "",
                        "图片识别工作流开始执行...",
                        False
                    )
                
                elif event_type == 'node_start':
                    node_display_name = self._get_node_display_name(node_name)
                    workflow_chat.current_node = self._get_node_id(node_name)
                    
                    await workflow_chat.add_node_message(
                        node_display_name,
                        "开始执行...",
                        "progress"
                    )
                    
                    yield (
                        workflow_chat._create_workflow_progress(),
                        "",
                        f"{node_display_name}开始执行...",
                        False
                    )
                
                elif event_type == 'node_streaming':
                    intermediate_result = stream_event.get('intermediate_result')
                    if intermediate_result and intermediate_result.state_update:
                        image_count = 0
                        for key in ['loaded_images', 'recognition_results']:
                            if key in intermediate_result.state_update:
                                if isinstance(intermediate_result.state_update[key], list):
                                    image_count = len(intermediate_result.state_update[key])
                                break
                        
                        if image_count > 0:
                            node_display_name = self._get_node_display_name(node_name)
                            await workflow_chat.add_node_message(
                                node_display_name,
                                f"正在处理图片... 当前数量: {image_count}",
                                "streaming"
                            )
                            
                            yield (
                                workflow_chat._create_workflow_progress(),
                                "",
                                f"正在处理图片... 当前数量: {image_count}",
                                False
                            )
                
                elif event_type == 'node_complete':
                    node_display_name = self._get_node_display_name(node_name)
                    
                    if node_name == 'image_recognition':
                        result_content = "✅ 图片识别完成"
                        if 'recognition_results' in stream_event.get('output', {}):
                            results = stream_event['output']['recognition_results']
                            if isinstance(results, list):
                                result_content = f"✅ 已成功识别{len(results)}张图片"
                    else:
                        result_content = "✅ 执行完成"
                        
                    await workflow_chat.add_node_message(
                        node_display_name,
                        result_content,
                        "completed"
                    )
                    
                    yield (
                        workflow_chat._create_workflow_progress(),
                        "",
                        f"{node_display_name}执行完成",
                        False
                    )
                
                elif event_type == 'node_error':
                    error_msg = stream_event.get('error', '未知错误')
                    node_display_name = self._get_node_display_name(node_name)
                    
                    await workflow_chat.add_node_message(
                        node_display_name,
                        f"执行失败: {error_msg}",
                        "error"
                    )
                    
                    yield (
                        workflow_chat._create_workflow_progress(),
                        "",
                        "",
                        False
                    )
                
                elif event_type == 'final':
                    yield (
                        workflow_chat._create_workflow_progress(),
                        "",
                        "图片识别工作流执行完成",
                        False
                    )
                
                else:
                    yield (
                        workflow_chat._create_workflow_progress(),
                        "",
                        "图片识别工作流执行中...",
                        False
                    )
                
        except Exception as e:
            logger.error(f"图片识别工作流流式执行失败: {e}")
            await workflow_chat.add_node_message(
                "系统",
                f"工作流执行失败: {str(e)}",
                "error"
            )
            yield (
                workflow_chat._create_workflow_progress(),
                "",
                "",
                False
            )
    
    def _get_node_display_name(self, node_name: str) -> str:
        """获取节点显示名称"""
        name_mapping = {
            'image_loading': '图片加载',
            'image_recognition': '图片识别',
            'save_result': '结果保存',
            'story_generation': '故事生成'
        }
        return name_mapping.get(node_name, node_name)
    
    def _get_node_id(self, node_name: str) -> str:
        """获取节点ID"""
        id_mapping = {
            'image_loading': 'loading',
            'image_recognition': 'recognition',
            'save_result': 'save',
            'story_generation': 'story'
        }
        return id_mapping.get(node_name, node_name)


class ImageLoadingNode(BaseNode):
    """图片加载和预处理节点 - 加载图片并进行预处理"""
    
    def __init__(self):
        super().__init__(name="image_loading", stream=True)
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行图片加载节点"""
        final_result = None
        async for result in self.execute_stream(input_data):
            final_result = result
        return final_result or input_data
    
    async def execute_stream(self, input_data: Dict[str, Any]):
        """流式执行图片加载节点"""
        print("📷 开始加载和预处理图片...")
        
        workflow_chat = input_data.get('workflow_chat')
        images = input_data.get('images', [])
        current_batch_index = input_data.get('current_batch_index', 0)
        batch_size = input_data.get('config', {}).get('batch_size', 5)
        
        if not images or current_batch_index * batch_size >= len(images):
            # 所有图片已处理完毕
            output_data = input_data.copy()
            output_data['recognition_complete'] = True
            output_data['loaded_images'] = []
            
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "图片加载",
                    "✅ 所有图片已处理完成",
                    "success"
                )
            
            yield output_data
            return
        
        # 计算当前批次的图片索引范围
        start_idx = current_batch_index * batch_size
        end_idx = min(start_idx + batch_size, len(images))
        current_batch_images = images[start_idx:end_idx]
        
        if workflow_chat:
            await workflow_chat.add_node_message(
                "图片加载",
                f"正在加载第 {current_batch_index + 1} 批次，共 {len(current_batch_images)} 张图片...",
                "progress"
            )
        
        # 加载和预处理图片
        loaded_images = []
        for img_idx, img_path in enumerate(current_batch_images):
            try:
                # 处理特殊文件名（以@开头的文件名）
                actual_path = img_path
                if img_path.startswith('@'):
                    # 检查当前目录是否有该文件
                    if os.path.exists(img_path):
                        actual_path = img_path
                    else:
                        # 尝试在各个可能的目录下查找
                        possible_paths = [
                            # 当前目录
                            img_path,
                            # 去掉@的文件名
                            img_path[1:],
                            # workspace/input目录
                            os.path.join('workspace', 'input', img_path),
                            os.path.join('workspace', 'input', img_path[1:]),
                            # 其他可能的目录
                            os.path.join('.', img_path),
                            os.path.join('.', img_path[1:])
                        ]
                        
                        # 寻找第一个存在的文件路径
                        for path in possible_paths:
                            if os.path.exists(path):
                                actual_path = path
                                logger.info(f"找到图片文件: {path}")
                                break
                
                # 检查文件是否存在
                if not os.path.exists(actual_path):
                    logger.warning(f"图片文件不存在: {img_path}，跳过处理")
                    continue
                
                # 读取图片文件并进行Base64编码
                with open(actual_path, "rb") as img_file:
                    img_data = img_file.read()
                    base64_img = base64.b64encode(img_data).decode("utf-8")
                
                # 获取文件信息
                img_name = os.path.basename(img_path)
                img_size = len(img_data)  # 使用文件内容大小而不是文件大小
                img_ext = os.path.splitext(img_path)[1].lower()
                if not img_ext:  # 如果没有扩展名，根据文件头推断
                    if img_data.startswith(b'\x89PNG'):
                        img_ext = '.png'
                    elif img_data.startswith(b'\xff\xd8'):
                        img_ext = '.jpg'
                    else:
                        img_ext = '.png'  # 默认为PNG
                
                # 确定MIME类型
                mime_type = "image/jpeg"  # 默认值
                if img_ext == ".png":
                    mime_type = "image/png"
                elif img_ext == ".gif":
                    mime_type = "image/gif"
                elif img_ext in [".jpg", ".jpeg"]:
                    mime_type = "image/jpeg"
                elif img_ext in [".webp"]:
                    mime_type = "image/webp"
                
                loaded_images.append({
                    "image_path": img_path,
                    "actual_path": actual_path,
                    "image_name": img_name,
                    "base64_data": base64_img,
                    "mime_type": mime_type,
                    "file_size": img_size,
                    "batch_index": current_batch_index,
                    "image_index": img_idx
                })
                
                logger.info(f"成功加载图片: {img_name} ({img_size} 字节)")
                
            except Exception as e:
                logger.error(f"加载图片失败 ({img_path}): {e}")
        
        if workflow_chat:
            await workflow_chat.add_node_message(
                "图片加载",
                f"✅ 已成功加载 {len(loaded_images)} 张图片",
                "success"
            )
        
        # 构建输出数据
        output_data = input_data.copy()
        output_data['loaded_images'] = loaded_images
        output_data['current_batch_index'] = current_batch_index + 1
        
        logger.info(f"✅ 第 {current_batch_index + 1} 批次图片加载完成，共 {len(loaded_images)} 张")
        yield output_data


class ImageRecognitionNode(BaseNode):
    """图片识别节点 - 使用DoubaoLLM分析图片内容"""
    
    def __init__(self):
        super().__init__(name="image_recognition", stream=True)
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行图片识别节点"""
        final_result = None
        async for result in self.execute_stream(input_data):
            final_result = result
        return final_result or input_data
    
    async def execute_stream(self, input_data: Dict[str, Any]):
        """流式执行图片识别节点"""
        print("🔍 开始图片识别...")
        
        workflow_chat = input_data.get('workflow_chat')
        llm = input_data.get('llm')
        loaded_images = input_data.get('loaded_images', [])
        
        if not loaded_images:
            # 没有图片需要处理，直接返回
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "图片识别",
                    "⚠️ 没有图片需要处理",
                    "warning"
                )
            
            output_data = input_data.copy()
            output_data['recognition_results'] = []
            yield output_data
            return
        
        if workflow_chat:
            await workflow_chat.add_node_message(
                "图片识别",
                f"正在识别 {len(loaded_images)} 张图片...",
                "progress"
            )
        
        # 处理每张图片
        recognition_results = []
        for img_idx, img_data in enumerate(loaded_images):
            try:
                # 检查是否有LLM
                if not llm:
                    raise Exception("LLM未初始化")
                
                # 构建图片识别提示词
                system_prompt = """你是一个专业的图片识别助手，擅长分析图片内容并生成准确的标题和详细描述。
请根据提供的图片内容，完成以下任务：
1. 生成一个简短而精确的标题（5-10个字）
2. 提供详细的图片内容描述（100-200字）
3. 识别图片中的关键物体、人物、场景等元素

输出格式要求：JSON格式，包含以下字段：
- title: 图片标题
- description: 详细描述
- elements: 图片中的主要元素，概念，风格，情感基调（数组）

请确保输出为严格的JSON格式，禁止输出任何其他内容。
{
  "title": "公园灰猫",
  "description": "在秋日公园拍摄的照片，画面中一只银灰色短毛猫正蹲坐在人行道上，好奇地用爪子触碰一片枯黄的落叶。背景是公园入口处的绿色拱门和标识牌，周围环绕着多棵落叶树木，树叶呈现金黄色调。阳光透过树叶形成柔和的光影效果，整个场景充满宁静祥和的秋日氛围。猫咪的绿色眼睛和警觉的姿态与周围环境形成了鲜明对比。",
  "elements": ["灰猫", "落叶", "公园", "拱门", "秋天景色", "树木", "城市风光", "宁静氛围"]
}

"""
                # 构建用户消息 - 这里我们需要扩展消息类来支持图片
                # 因为当前Message类不支持直接包含图片，我们将base64图片数据放在元数据中
                
                user_message = Message(
                    role=MessageRole.USER,
                    content="请分析这张图片，提供标题和详细描述。",
                    metadata={
                        "has_image": True,
                        "image_data": img_data["base64_data"],
                        "image_mime": img_data["mime_type"]
                    }
                )
                
                # 构建消息列表
                messages = [
                    Message(role=MessageRole.SYSTEM, content=system_prompt),
                    user_message
                ]
                
                # 修改doubao_llm的_convert_messages方法以支持图片
                # 这是一个monkey patch，实际应该在LLM类中实现
                original_convert_messages = llm._convert_messages
                
                def patched_convert_messages(messages_list):
                    """添加对图片的支持"""
                    converted = []
                    for msg in messages_list:
                        role = "user" if msg.role == MessageRole.USER else "assistant"
                        if msg.role == MessageRole.SYSTEM:
                            role = "system"
                        
                        # 检查是否有图片
                        if msg.metadata and msg.metadata.get("has_image"):
                            # 添加图片内容
                            converted.append({
                                "role": role,
                                "content": [
                                    {"type": "text", "text": msg.content},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:{msg.metadata.get('image_mime', 'image/jpeg')};base64,{msg.metadata.get('image_data')}",
                                        }
                                    }
                                ]
                            })
                        else:
                            # 普通文本消息
                            converted.append({
                                "role": role,
                                "content": msg.content
                            })
                    
                    return converted
                
                # 应用monkey patch
                llm._convert_messages = patched_convert_messages
                
                # 调用LLM进行图片识别
                logger.info(f"开始识别图片: {img_data['image_name']}")
                
                try:
                    # 更新模型名称为支持多模态的模型
                    original_model = llm.config.model_name
                    # 使用环境变量中的多模态模型名称，如果不存在则使用默认值
                    vision_model = os.getenv('DOUBAO_MODEL_VISION_PRO', 'ep-20250704095927-j6t2g')
                    llm.config.model_name = vision_model
                    
                    logger.info(f"使用多模态模型: {vision_model}")
                    
                    # 调用LLM
                    response = await llm.generate(
                        messages,
                        temperature=0.7,
                        max_tokens=4096,
                        mode="normal"
                    )
                    
                    # 恢复原始模型名称
                    llm.config.model_name = original_model
                    
                    # 恢复原始方法
                    llm._convert_messages = original_convert_messages
                    
                    # 解析结果
                    content = response.content
                    
                    # 从回复中提取JSON
                    import re
                    json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                    
                    if json_match:
                        json_str = json_match.group(1)
                    else:
                        # 尝试找到大括号包围的JSON
                        json_match = re.search(r'\{.*\}', content, re.DOTALL)
                        if json_match:
                            json_str = json_match.group(0)
                        else:
                            json_str = content
                    
                    # 解析JSON
                    try:
                        result_data = json.loads(json_str.strip())
                    except json.JSONDecodeError:
                        logger.warning(f"JSON解析失败，使用原始回复")
                        result_data = {
                            "title": "无法解析结果",
                            "description": content,
                            "elements": [],
                            "style": "未知",
                            "mood": "未知"
                        }
                    
                    # 添加图片信息
                    result_data["image_name"] = img_data["image_name"]
                    result_data["image_path"] = img_data["image_path"]
                    
                    recognition_results.append(result_data)
                    logger.info(f"图片识别成功: {img_data['image_name']}")
                    
                except Exception as e:
                    logger.error(f"LLM调用失败: {e}")
                    # 添加错误结果
                    recognition_results.append({
                        "image_name": img_data["image_name"],
                        "image_path": img_data["image_path"],
                        "title": "识别失败",
                        "description": f"图片识别过程中出错: {str(e)}",
                        "elements": [],
                        "style": "未知",
                        "mood": "错误",
                        "error": str(e)
                    })
                
            except Exception as e:
                logger.error(f"图片识别失败: {e}")
                recognition_results.append({
                    "image_name": img_data["image_name"] if "image_name" in img_data else "未知图片",
                    "image_path": img_data["image_path"] if "image_path" in img_data else "未知路径",
                    "title": "处理错误",
                    "description": f"图片处理过程中出错: {str(e)}",
                    "elements": [],
                    "style": "未知",
                    "mood": "错误",
                    "error": str(e)
                })
        
        if workflow_chat:
            await workflow_chat.add_node_message(
                "图片识别",
                f"✅ 已成功识别 {len(recognition_results)} 张图片",
                "success"
            )
        
        # 输出结果
        output_data = input_data.copy()
        output_data['recognition_results'] = recognition_results
        
        logger.info(f"✅ 图片识别完成，共 {len(recognition_results)} 张")
        yield output_data


class ResultSaveNode(BaseNode):
    """结果保存节点 - 将识别结果保存到CSV"""
    
    def __init__(self):
        super().__init__(name="result_save", stream=True)
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行结果保存节点"""
        final_result = None
        async for result in self.execute_stream(input_data):
            final_result = result
        return final_result or input_data
    
    async def execute_stream(self, input_data: Dict[str, Any]):
        """流式执行结果保存节点"""
        print("💾 开始保存识别结果...")
        
        workflow_chat = input_data.get('workflow_chat')
        recognition_results = input_data.get('recognition_results', [])
        config = input_data.get('config', {})
        
        if not recognition_results:
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "结果保存",
                    "⚠️ 没有结果需要保存",
                    "warning"
                )
            yield input_data
            return
        
        if workflow_chat:
            await workflow_chat.add_node_message(
                "结果保存",
                f"正在保存{len(recognition_results)}条识别结果...",
                "progress"
            )
        
        # 保存到CSV文件
        csv_save_result = await self._save_to_csv(recognition_results, config, workflow_chat)
        
        # 构建最终输出
        output_data = input_data.copy()
        output_data.update({
            'csv_save_result': csv_save_result,
            'save_success': csv_save_result.get('success', False),
            'save_message': csv_save_result.get('message', '保存完成')
        })
        
        yield output_data
    
    async def _save_to_csv(self, recognition_results: List[Dict], config: Dict, workflow_chat=None) -> Dict:
        """保存识别结果到CSV文件"""
        try:
            import csv
            from datetime import datetime
            
            # 获取CSV配置
            csv_config = config.get('csv_output', {})
            output_dir = csv_config.get('output_dir', 'workspace/image_recognition_output')
            filename = csv_config.get('filename', 'image_recognition_results.csv')
            encoding = csv_config.get('encoding', 'utf-8-sig')
            
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)
            
            # CSV文件路径
            csv_file = os.path.join(output_dir, filename)
            
            # 检查文件是否存在，决定是否写入表头
            file_exists = os.path.exists(csv_file)
            
            # 写入CSV文件（追加模式）
            with open(csv_file, 'a', newline='', encoding=encoding) as f:
                fieldnames = ['图片名称', '图片路径', '标题', '详细描述', '主要元素', '识别时间']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                # 如果文件不存在，先写入表头
                if not file_exists:
                    writer.writeheader()
                
                # 写入当前批次的识别结果
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for result in recognition_results:
                    writer.writerow({
                        '图片名称': result.get('image_name', ''),
                        '图片路径': result.get('image_path', ''),
                        '标题': result.get('title', ''),
                        '详细描述': result.get('description', ''),
                        '主要元素': ','.join(result.get('elements', [])) if isinstance(result.get('elements'), list) else result.get('elements', ''),
                        '识别时间': timestamp
                    })
            
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "结果保存",
                    f"✅ {len(recognition_results)}条识别结果已保存到CSV文件",
                    "success"
                )
            
            logger.info(f"✅ CSV保存完成：{len(recognition_results)}条识别结果保存到 {csv_file}")
            
            return {
                'success': True,
                'message': f"成功保存{len(recognition_results)}条识别结果",
                'count': len(recognition_results),
                'file_path': csv_file
            }
            
        except Exception as e:
            logger.error(f"CSV保存失败: {e}")
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "结果保存",
                    f"❌ CSV保存失败: {str(e)}",
                    "error"
                )
            
            return {
                'success': False,
                'message': f"保存失败: {str(e)}",
                'error': str(e)
            }


# 本地测试运行入口
async def main():
    """本地测试运行图片识别工作流"""
    print("🎭 启动图片识别工作流本地测试...")
    
    # 简单的模拟聊天界面
    class MockWorkflowChat:
        def __init__(self):
            self.current_node = ""
        
        async def add_node_message(self, node_name: str, message: str, status: str):
            print(f"[{node_name}] {status}: {message}")
        
        def _create_workflow_progress(self):
            return "<div>工作流进度</div>"
    
    try:
        # 配置LLM
        llm = None
        try:
            from llm.doubao import DoubaoLLM
            from core.types import LLMConfig
            
            # 使用环境变量获取模型名称和API密钥
            vision_model = os.getenv('DOUBAO_MODEL_VISION_PRO', 'ep-20250704095927-j6t2g')
            api_key = os.getenv('ARK_API_KEY') or os.getenv('DOUBAO_API_KEY')
            
            # 创建LLM配置
            llm_config = LLMConfig(
                provider="doubao",
                model_name=vision_model,  # 使用环境变量中的多模态模型
                api_key=api_key,  # 使用环境变量中的API密钥
                api_base="https://ark.cn-beijing.volces.com/api/v3"
            )
            llm = DoubaoLLM(config=llm_config)
            print(f"✅ LLM配置成功，使用模型: {vision_model}")
        except Exception as e:
            print(f"⚠️ LLM配置失败，将跳过实际识别: {e}")
        
        # 初始化工作流
        workflow = ImageRecognitionWorkflow(llm=llm)
        print("✅ 图片识别工作流初始化完成")
        
        # 测试配置
        test_config = {
            'batch_size': 2,  # 每批处理2张图片
            'csv_output': {
                'enabled': True,
                'output_dir': 'workspace/image_recognition_output',
                'filename': 'image_recognition_results.csv',
                'encoding': 'utf-8-sig'
            }
        }
        
        print(f"📊 测试配置: {test_config}")
        
        # 模拟图片路径（根据你的实际环境修改）
        test_images = [
            "@25455127221_185539693045_路边可爱动物 (4)(1).png"  # 使用提供的图片路径
        ]
        
        print(f"🖼️ 测试图片: {test_images}")
        
        # 创建模拟聊天界面
        mock_chat = MockWorkflowChat()
        
        # 创建工作流图
        graph = await workflow.create_image_recognition_graph()
        compiled_graph = graph.compile()
        print("✅ 工作流图创建完成")
        
        # 准备输入数据
        input_data = {
            'config': test_config,
            'workflow_chat': mock_chat,
            'llm': llm,
            'images': test_images,
            'current_batch_index': 0
        }
        
        print("\n🚀 开始执行图片识别工作流...")
        
        # 执行工作流
        final_result = None
        async for result in compiled_graph.stream(input_data):
            if result:
                final_result = result
        
        # 显示结果
        if final_result:
            print("\n✅ 工作流执行完成!")
            
            recognition_results = final_result.get('recognition_results', [])
            print(f"📝 识别结果数量: {len(recognition_results)}")
            
            if recognition_results:
                print("\n🖼️ 识别结果示例:")
                for i, result in enumerate(recognition_results[:2], 1):  # 显示前2条
                    print(f"\n--- 结果 {i} ---")
                    print(f"图片: {result.get('image_name', 'N/A')}")
                    print(f"标题: {result.get('title', 'N/A')}")
                    print(f"描述: {result.get('description', 'N/A')}")
                    print(f"元素: {result.get('elements', [])}")
                    print(f"风格: {result.get('style', 'N/A')}")
                    print(f"情感: {result.get('mood', 'N/A')}")
                    print("-" * 50)
                
                # 显示CSV保存结果
                csv_result = final_result.get('csv_save_result', {})
                if csv_result.get('success'):
                    csv_file = csv_result.get('file_path', '未知')
                    print(f"\n💾 CSV结果已保存到: {csv_file}")
                else:
                    print(f"\n⚠️ CSV保存失败: {csv_result.get('message', '未知错误')}")
            
            else:
                print("⚠️ 没有识别结果（可能是API密钥无效或网络问题）")
        
        else:
            print("❌ 工作流执行失败")
    
    except Exception as e:
        print(f"❌ 测试执行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    """直接运行此文件进行本地测试"""
    print("🖼️ 图片识别工作流 - 本地测试模式")
    print("=" * 60)
    
    # 运行异步主函数
    asyncio.run(main())