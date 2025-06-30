"""
剧情生成工作流事件处理器
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Tuple, Optional
from pathlib import Path
import gradio as gr

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from workflow.story_workflow import StoryWorkflow
from llm.base import LLMFactory
from core.types import LLMConfig

logger = logging.getLogger(__name__)

class StoryHandlers:
    """剧情生成工作流事件处理器"""
    
    def __init__(self, app_instance):
        self.app = app_instance
        self.story_workflow = None
        self.characters_data = {}
        self.locations_data = {}
        
        # 初始化工作流
        self._initialize_workflow()
    
    def _initialize_workflow(self):
        """初始化剧情工作流"""
        try:
            # 使用应用的LLM实例
            llm = self.app.llm if hasattr(self.app, 'llm') and self.app.llm else None
            self.story_workflow = StoryWorkflow(llm=llm)
            
            # 获取数据
            self.characters_data = self.story_workflow.characters_data
            self.locations_data = self.story_workflow.locations_data
            
            logger.info("剧情工作流初始化成功")
            
        except Exception as e:
            logger.error(f"剧情工作流初始化失败: {e}")
            self.story_workflow = None
    
    async def on_refresh_characters(self) -> Tuple[gr.CheckboxGroup, List[List[str]]]:
        """刷新角色列表"""
        try:
            if not self.story_workflow:
                self._initialize_workflow()
            
            from ..components.story_interface import StoryInterface
            story_interface = StoryInterface()
            
            # 创建角色选择项
            character_choices = story_interface.create_character_choices(self.characters_data)
            
            # 返回更新的组件
            return (
                gr.update(choices=character_choices, value=[]),
                []  # 清空预览表格
            )
            
        except Exception as e:
            logger.error(f"刷新角色列表失败: {e}")
            return gr.update(choices=[], value=[]), []
    
    async def on_refresh_locations(self) -> Tuple[gr.CheckboxGroup, List[List[str]]]:
        """刷新地点列表"""
        try:
            if not self.story_workflow:
                self._initialize_workflow()
            
            from ..components.story_interface import StoryInterface
            story_interface = StoryInterface()
            
            # 创建地点选择项
            location_choices = story_interface.create_location_choices(self.locations_data)
            
            # 返回更新的组件
            return (
                gr.update(choices=location_choices, value=[]),
                []  # 清空预览表格
            )
            
        except Exception as e:
            logger.error(f"刷新地点列表失败: {e}")
            return gr.update(choices=[], value=[]), []
    
    async def on_characters_change(self, selected_characters: List[str]) -> List[List[str]]:
        """角色选择变化事件"""
        try:
            from ..components.story_interface import StoryInterface
            story_interface = StoryInterface()
            
            # 更新角色预览表格
            preview_data = story_interface.update_characters_preview(
                selected_characters, self.characters_data
            )
            
            return preview_data
            
        except Exception as e:
            logger.error(f"更新角色预览失败: {e}")
            return []
    
    async def on_locations_change(self, selected_locations: List[str]) -> List[List[str]]:
        """地点选择变化事件"""
        try:
            from ..components.story_interface import StoryInterface
            story_interface = StoryInterface()
            
            # 更新地点预览表格
            preview_data = story_interface.update_locations_preview(
                selected_locations, self.locations_data
            )
            
            return preview_data
            
        except Exception as e:
            logger.error(f"更新地点预览失败: {e}")
            return []
    
    async def on_generate_story(self, 
                               selected_characters: List[str],
                               selected_locations: List[str],
                               story_type: str,
                               story_length: str,
                               relationship_depth: str):
        """执行剧情生成"""
        try:
            # 验证输入
            if not selected_characters:
                yield (
                    "❌ 请至少选择一个角色",
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False)
                )
                return
            
            if not selected_locations:
                yield (
                    "❌ 请至少选择一个地点",
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False)
                )
                return
            
            # 更新状态
            status = "🔄 正在执行剧情生成工作流..."
            progress_html = """
            <div style='padding: 10px; border-radius: 5px; background: #f8f9fa;'>
                <h4>🔄 工作流进度</h4>
                <div style='margin: 5px 0;'>
                    <span style='color: #007bff;'>📋 剧情规划</span> → 
                    <span style='color: #6c757d;'>👥 角色分析</span> → 
                    <span style='color: #6c757d;'>📚 剧情生成</span> → 
                    <span style='color: #6c757d;'>📄 CSV导出</span>
                </div>
            </div>
            """
            
            # 首先返回进度状态
            yield (
                status,
                gr.update(value=progress_html, visible=True),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False)
            )
            
            # 初始化工作流（如果需要）
            if not self.story_workflow:
                self._initialize_workflow()
            
            if not self.story_workflow:
                yield (
                    "❌ 工作流初始化失败",
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=False)
                )
                # 在异步生成器中不能使用return语句，直接结束函数
                return
            
            # 准备配置
            config = {
                'selected_characters': selected_characters,
                'selected_locations': selected_locations,
                'story_type': story_type,
                'story_length': story_length,
                'relationship_depth': relationship_depth
            }
            
            # 执行工作流
            logger.info(f"开始执行剧情生成工作流: {config}")
            
            # 更新进度: 角色分析
            progress_html = """
            <div style='padding: 10px; border-radius: 5px; background: #f8f9fa;'>
                <h4>🔄 工作流进度</h4>
                <div style='margin: 5px 0;'>
                    <span style='color: #28a745;'>✅ 剧情规划</span> → 
                    <span style='color: #007bff;'>👥 角色分析</span> → 
                    <span style='color: #6c757d;'>📚 剧情生成</span> → 
                    <span style='color: #6c757d;'>📄 CSV导出</span>
                </div>
            </div>
            """
            
            yield (
                "🔄 正在分析角色特征...",
                gr.update(value=progress_html, visible=True),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False)
            )
            
            # 执行工作流
            result = await self.story_workflow.execute_story_generation(config)
            
            # 更新进度: 剧情生成
            progress_html = """
            <div style='padding: 10px; border-radius: 5px; background: #f8f9fa;'>
                <h4>🔄 工作流进度</h4>
                <div style='margin: 5px 0;'>
                    <span style='color: #28a745;'>✅ 剧情规划</span> → 
                    <span style='color: #28a745;'>✅ 角色分析</span> → 
                    <span style='color: #007bff;'>📚 剧情生成</span> → 
                    <span style='color: #6c757d;'>📄 CSV导出</span>
                </div>
            </div>
            """
            
            yield (
                "🔄 正在生成剧情事件...",
                gr.update(value=progress_html, visible=True),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False)
            )
            
            # 更新进度: CSV导出
            progress_html = """
            <div style='padding: 10px; border-radius: 5px; background: #f8f9fa;'>
                <h4>🔄 工作流进度</h4>
                <div style='margin: 5px 0;'>
                    <span style='color: #28a745;'>✅ 剧情规划</span> → 
                    <span style='color: #28a745;'>✅ 角色分析</span> → 
                    <span style='color: #28a745;'>✅ 剧情生成</span> → 
                    <span style='color: #007bff;'>📄 CSV导出</span>
                </div>
            </div>
            """
            
            yield (
                "🔄 正在导出CSV文件...",
                gr.update(value=progress_html, visible=True),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False)
            )
            
            # 处理结果
            if hasattr(result, 'data'):
                result_data = result.data
            else:
                result_data = result
            
            # 提取结果数据
            story_events = result_data.get('story_events', [])
            csv_data = result_data.get('csv_data', [])
            csv_headers = result_data.get('csv_headers', [])
            export_file = result_data.get('export_file', '')
            planning_result = result_data.get('planning_result', {})
            
            # 生成统计信息
            stats_html = f"""
            <div style='padding: 15px; border-radius: 8px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;'>
                <h4 style='margin: 0 0 10px 0; color: white;'>📊 生成统计</h4>
                <div style='display: flex; justify-content: space-between; flex-wrap: wrap;'>
                    <div style='text-align: center; margin: 5px;'>
                        <div style='font-size: 24px; font-weight: bold;'>{len(story_events)}</div>
                        <div style='font-size: 12px; opacity: 0.9;'>剧情事件</div>
                    </div>
                    <div style='text-align: center; margin: 5px;'>
                        <div style='font-size: 24px; font-weight: bold;'>{len(selected_characters)}</div>
                        <div style='font-size: 12px; opacity: 0.9;'>参与角色</div>
                    </div>
                    <div style='text-align: center; margin: 5px;'>
                        <div style='font-size: 24px; font-weight: bold;'>{len(selected_locations)}</div>
                        <div style='font-size: 12px; opacity: 0.9;'>涉及地点</div>
                    </div>
                </div>
            </div>
            """
            
            # 生成汇总
            summary = {
                "执行状态": "成功",
                "生成时间": result_data.get('timestamp', '未知'),
                "剧情数量": len(story_events),
                "参与角色": selected_characters,
                "涉及地点": selected_locations,
                "配置信息": config
            }
            
            # 完成进度
            progress_html = """
            <div style='padding: 10px; border-radius: 5px; background: #d4edda; border: 1px solid #c3e6cb;'>
                <h4 style='color: #155724;'>✅ 工作流完成</h4>
                <div style='margin: 5px 0; color: #155724;'>
                    <span style='color: #28a745;'>✅ 剧情规划</span> → 
                    <span style='color: #28a745;'>✅ 角色分析</span> → 
                    <span style='color: #28a745;'>✅ 剧情生成</span> → 
                    <span style='color: #28a745;'>✅ CSV导出</span>
                </div>
            </div>
            """
            
            # 返回最终结果
            yield (
                f"✅ 剧情生成完成！共生成 {len(story_events)} 个剧情事件",
                gr.update(value=progress_html, visible=True),
                gr.update(value=summary, visible=True),
                gr.update(value=csv_data, headers=csv_headers, visible=True),
                gr.update(value=export_file, visible=True) if export_file else gr.update(visible=False),
                gr.update(value=stats_html, visible=True),
                gr.update(value=planning_result.get('story_outline', ''), visible=True),
                gr.update(value=planning_result.get('character_relationships', []), visible=True),
                gr.update(value=planning_result.get('location_usage', []), visible=True)
            )
            
            logger.info(f"剧情生成工作流执行成功，生成了{len(story_events)}个剧情事件")
            
        except Exception as e:
            error_msg = f"剧情生成失败: {str(e)}"
            logger.error(error_msg)
            
            yield (
                f"❌ {error_msg}",
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False)
            )
    
    async def on_story_load(self) -> Tuple[gr.CheckboxGroup, gr.CheckboxGroup]:
        """页面加载时初始化剧情工作流"""
        try:
            # 确保工作流已初始化
            if not self.story_workflow:
                self._initialize_workflow()
            
            from ..components.story_interface import StoryInterface
            story_interface = StoryInterface()
            
            # 创建角色和地点选择项
            character_choices = story_interface.create_character_choices(self.characters_data)
            location_choices = story_interface.create_location_choices(self.locations_data)
            
            return (
                gr.update(choices=character_choices, value=[]),
                gr.update(choices=location_choices, value=[])
            )
            
        except Exception as e:
            logger.error(f"剧情工作流加载失败: {e}")
            return gr.update(choices=[], value=[]), gr.update(choices=[], value=[]) 