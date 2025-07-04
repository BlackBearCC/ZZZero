#!/usr/bin/env python3
"""
图片识别工作流测试脚本
用于测试基于豆包多模态模型的图片识别功能
"""

import asyncio
import argparse
import os
import glob
import logging
import shutil
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime
import base64

# 导入工作流
import sys
sys.path.append(os.path.dirname(__file__))
from src.workflow.image_recognition_workflow import ImageRecognitionWorkflow
from src.llm.doubao import DoubaoLLM
from src.core.types import LLMConfig

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SimpleChatInterface:
    """简单的聊天界面模拟"""
    
    def __init__(self):
        self.current_node = ""
        self.messages = []
    
    async def add_node_message(self, node_name: str, message: str, status: str):
        """添加节点消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        full_message = f"[{timestamp}] [{node_name}] {status}: {message}"
        self.messages.append(full_message)
        print(full_message)
    
    def _create_workflow_progress(self):
        """创建工作流进度模拟"""
        return "<工作流进度>"


def prepare_special_image(image_path: str) -> str:
    """为特殊文件名准备实际的图片文件
    
    Args:
        image_path: 图片路径或特殊标识符
        
    Returns:
        str: 实际的图片文件路径
    """
    # 如果是普通文件且存在，直接返回
    if os.path.exists(image_path) and not image_path.startswith('@'):
        return image_path
    
    # 创建临时目录
    temp_dir = os.path.join(os.getcwd(), 'workspace', 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    
    # 特殊处理@开头的文件名
    if image_path.startswith('@'):
        # 提取文件名作为新的文件名
        base_name = os.path.basename(image_path)
        if base_name.startswith('@'):
            base_name = base_name[1:]
        
        # 创建新的文件路径
        new_path = os.path.join(temp_dir, base_name)
        
        # 首先检查是否有对应的本地文件
        for check_path in [image_path, image_path[1:], os.path.join('workspace', 'input', base_name)]:
            if os.path.exists(check_path):
                # 复制文件
                shutil.copy(check_path, new_path)
                logger.info(f"已复制文件: {check_path} -> {new_path}")
                return new_path
        
        # 如果没有找到实际文件，返回原始路径
        logger.warning(f"无法找到图片文件: {image_path}")
        return image_path
    
    # 默认返回原路径
    return image_path


async def run_image_recognition(args):
    """运行图片识别工作流"""
    logger.info("开始图片识别工作流测试")
    
    # 准备图片列表
    image_files = []
    for image_pattern in args.images:
        # 支持通配符匹配
        matched_files = glob.glob(image_pattern, recursive=True)
        if matched_files:
            image_files.extend(matched_files)
        else:
            # 特殊处理
            prepared_path = prepare_special_image(image_pattern)
            image_files.append(prepared_path)
    
    # 去重
    image_files = sorted(list(set(image_files)))
    
    if not image_files:
        logger.error("没有找到匹配的图片文件")
        return
    
    logger.info(f"找到 {len(image_files)} 张图片")
    for i, img in enumerate(image_files[:5], 1):  # 只显示前5张
        logger.info(f"图片 {i}: {img}")
    
    if len(image_files) > 5:
        logger.info(f"... 还有 {len(image_files) - 5} 张图片未显示")
    
    # 创建输出目录
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"image_recognition_{timestamp}.csv")
    
    # 配置LLM
    llm = None
    try:
        # 获取环境变量中的模型ID和API密钥
        vision_model = os.getenv('DOUBAO_MODEL_VISION_PRO', 'ep-20250704095927-j6t2g')
        logger.info(f"使用多模态模型: {vision_model}")
        
        # 创建豆包LLM配置
        llm_config = LLMConfig(
            provider="doubao",
            model_name=vision_model,  # 使用支持多模态的模型
            api_key=os.getenv('ARK_API_KEY') or os.getenv('DOUBAO_API_KEY'),
            api_base=os.getenv('DOUBAO_BASE_URL', "https://ark.cn-beijing.volces.com/api/v3"),
            temperature=0.2,
            max_tokens=4096
        )
        llm = DoubaoLLM(config=llm_config)
        await llm.initialize()  # 初始化客户端
        logger.info("LLM客户端初始化成功")
    except Exception as e:
        logger.error(f"LLM初始化失败: {e}")
        return
    
    # 初始化工作流
    workflow = ImageRecognitionWorkflow(llm=llm)
    
    # 工作流配置
    workflow_config = {
        'batch_size': args.batch_size,
        'csv_output': {
            'enabled': True,
            'output_dir': output_dir,
            'filename': os.path.basename(output_file),
            'encoding': 'utf-8-sig'
        }
    }
    
    # 创建聊天界面模拟
    chat_interface = SimpleChatInterface()
    
    # 创建工作流图
    graph = await workflow.create_image_recognition_graph()
    
    # 运行工作流
    try:
        logger.info(f"开始执行工作流，处理 {len(image_files)} 张图片，批次大小: {args.batch_size}")
        start_time = datetime.now()
        
        async for event in workflow.execute_workflow_stream(
            workflow_config, chat_interface, image_files
        ):
            # 已经在聊天界面中打印进度
            pass
            
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        
        logger.info(f"工作流执行完成！耗时: {elapsed:.2f} 秒")
        logger.info(f"结果已保存到: {output_file}")
        
    except Exception as e:
        logger.error(f"工作流执行失败: {e}")
    finally:
        # 清理资源
        if llm:
            await llm.cleanup()


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='图片识别工作流测试脚本')
    parser.add_argument('-i', '--images', nargs='+', required=True, 
                        help='图片文件路径，支持通配符，如 "./images/*.jpg"')
    parser.add_argument('-o', '--output-dir', default='./workspace/image_recognition_output',
                        help='输出目录')
    parser.add_argument('-b', '--batch-size', type=int, default=5,
                        help='批次大小（默认5张图片一批）')
    parser.add_argument('--create-sample', action='store_true',
                        help='创建示例图片用于测试')
    return parser.parse_args()


if __name__ == "__main__":
    # 如果没有提供命令行参数，使用默认批处理所有目录
    if len(sys.argv) == 1:
        # 处理所有指定目录下的图片
        sys.argv.extend([
            '-i', 
            'workspace/input/对话日常图片/风景修/*.png',
            'workspace/input/对话日常图片/动物修/*.png',
            'workspace/input/对话日常图片/美食修/*.png',
            'workspace/input/对话日常图片/*/*.png'  # 匹配所有子目录中的PNG图片
        ])
    
    args = parse_args()
    
    # 如果指定了创建示例，提示用户这个功能已被禁用
    if args.create_sample:
        logger.warning("创建示例图片功能已被禁用，请使用实际图片文件")
    
    asyncio.run(run_image_recognition(args)) 