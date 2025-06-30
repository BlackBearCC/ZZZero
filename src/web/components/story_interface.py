"""
剧情生成工作流界面组件
"""

import gradio as gr
from typing import Dict, List, Any, Tuple
import json

class StoryInterface:
    """剧情生成工作流界面"""
    
    def __init__(self):
        pass
    
    def create_story_interface(self) -> Dict[str, Any]:
        """创建完整的剧情生成界面"""
        with gr.Column():
            # 标题和描述
            gr.Markdown("## 🎭 剧情生成工作流")
            gr.Markdown("基于云枢市角色和地点数据，自动生成游戏风格的剧情CSV文件")
            
            with gr.Row():
                # 左侧配置面板
                with gr.Column(scale=1):
                    config_components = self._create_config_panel()
                
                # 右侧执行和结果面板
                with gr.Column(scale=2):
                    execution_components = self._create_execution_panel()
            
            # 底部结果展示
            result_components = self._create_result_panel()
        
        # 合并所有组件
        all_components = {**config_components, **execution_components, **result_components}
        
        return all_components
    
    def _create_config_panel(self) -> Dict[str, Any]:
        """创建配置面板"""
        components = {}
        
        with gr.Accordion("📋 剧情配置", open=True):
            # 角色选择
            gr.Markdown("### 👥 角色选择")
            components['character_selector'] = gr.CheckboxGroup(
                label="选择参与剧情的角色",
                choices=[],  # 将通过事件动态填充
                value=[],
                info="至少选择1个角色"
            )
            
            components['refresh_characters_btn'] = gr.Button("🔄 刷新角色列表", size="sm")
            
            # 地点选择  
            gr.Markdown("### 🏢 地点选择")
            components['location_selector'] = gr.CheckboxGroup(
                label="选择剧情发生地点",
                choices=[],  # 将通过事件动态填充
                value=[],
                info="至少选择1个地点"
            )
            
            components['refresh_locations_btn'] = gr.Button("🔄 刷新地点列表", size="sm")
            
            # 剧情类型配置
            gr.Markdown("### 🎨 剧情设定")
            components['story_type'] = gr.Radio(
                label="剧情类型",
                choices=[
                    ("日常生活", "daily_life"),
                    ("浪漫恋爱", "romance"), 
                    ("冒险探索", "adventure"),
                    ("悬疑推理", "mystery")
                ],
                value="daily_life",
                info="选择剧情的主要风格"
            )
            
            components['story_length'] = gr.Radio(
                label="剧情长度",
                choices=[
                    ("简短(1-2个阶段)", "short"),
                    ("中等(3-5个阶段)", "medium"),
                    ("详细(5-8个阶段)", "long")
                ],
                value="medium",
                info="控制每个角色的剧情细分程度"
            )
            
            components['relationship_depth'] = gr.Radio(
                label="关系深度",
                choices=[
                    ("陌生人", "stranger"),
                    ("普通朋友", "casual"),
                    ("亲密朋友", "close"),
                    ("恋人关系", "intimate")
                ],
                value="casual",
                info="角色间的初始关系设定"
            )
        
        with gr.Accordion("📊 数据预览", open=False):
            components['characters_preview'] = gr.Dataframe(
                label="选中角色信息",
                headers=["角色名", "年龄", "性格", "活动地点"],
                datatype=["str", "str", "str", "str"],
                interactive=False,
                visible=True
            )
            
            components['locations_preview'] = gr.Dataframe(
                label="选中地点信息", 
                headers=["地点名", "类型", "区域", "氛围"],
                datatype=["str", "str", "str", "str"],
                interactive=False,
                visible=True
            )
        
        return components
    
    def _create_execution_panel(self) -> Dict[str, Any]:
        """创建执行面板"""
        components = {}
        
        with gr.Column():
            gr.Markdown("### 🚀 执行工作流")
            
            # 执行按钮
            components['generate_btn'] = gr.Button(
                "🎬 开始生成剧情",
                variant="primary",
                size="lg"
            )
            
            # 执行状态
            components['execution_status'] = gr.Markdown(
                "🔵 就绪状态，等待配置完成",
                visible=True
            )
            
            # 进度显示
            components['progress_display'] = gr.HTML(
                """
                <div style='padding: 10px; border-radius: 5px; background: #f8f9fa;'>
                    <h4>🔄 工作流进度</h4>
                    <div style='margin: 5px 0;'>
                        <span style='color: #6c757d;'>📋 剧情规划</span> → 
                        <span style='color: #6c757d;'>👥 角色分析</span> → 
                        <span style='color: #6c757d;'>📚 剧情生成</span> → 
                        <span style='color: #6c757d;'>📄 CSV导出</span>
                    </div>
                </div>
                """,
                visible=False
            )
            
            # 生成结果汇总
            components['generation_summary'] = gr.JSON(
                label="生成结果汇总",
                visible=False
            )
        
        return components
    
    def _create_result_panel(self) -> Dict[str, Any]:
        """创建结果展示面板"""
        components = {}
        
        with gr.Accordion("📄 生成结果", open=False):
            # 剧情表格预览
            components['story_table'] = gr.Dataframe(
                label="生成的剧情表格",
                headers=[
                    "剧情ID", "NPC", "剧情名", "剧情阶段", "触发地点", 
                    "前置条件", "描述", "关键事件", "触发概率", 
                    "完成条件", "解锁剧情", "状态"
                ],
                datatype=["str"] * 12,
                interactive=False,
                visible=False,
                wrap=True
            )
            
            # 文件下载
            components['download_file'] = gr.File(
                label="下载生成的CSV文件",
                visible=False
            )
            
            # 统计信息
            components['stats_display'] = gr.HTML(
                visible=False
            )
        
        with gr.Accordion("🎯 剧情规划详情", open=False):
            # 故事大纲
            components['story_outline'] = gr.Textbox(
                label="故事主线概述",
                lines=3,
                interactive=False,
                visible=False
            )
            
            # 角色关系图
            components['character_relationships'] = gr.JSON(
                label="角色关系分析",
                visible=False
            )
            
            # 地点利用方案
            components['location_usage'] = gr.JSON(
                label="地点利用方案",
                visible=False
            )
        
        return components
    
    def create_character_choices(self, characters_data: Dict[str, Any]) -> List[Tuple[str, str]]:
        """创建角色选择项"""
        choices = []
        char_list = characters_data.get("角色列表", {})
        
        for name, info in char_list.items():
            age = info.get('年龄', '未知')
            personality = info.get('性格', '')
            label = f"{name} ({age}岁) - {personality}"
            choices.append((label, name))
        
        return choices
    
    def create_location_choices(self, locations_data: Dict[str, Any]) -> List[Tuple[str, str]]:
        """创建地点选择项"""
        choices = []
        districts = locations_data.get("districts", {})
        
        for district_name, district_info in districts.items():
            district_locations = district_info.get("locations", {})
            for loc_name, loc_info in district_locations.items():
                name = loc_info.get('name', loc_name)
                type_info = loc_info.get('type', '')
                district = district_info.get('name', district_name)
                label = f"{name} ({type_info}) - {district}"
                choices.append((label, name))
        
        return choices
    
    def update_characters_preview(self, selected_characters: List[str], 
                                 characters_data: Dict[str, Any]) -> List[List[str]]:
        """更新角色预览表格"""
        if not selected_characters:
            return []
        
        preview_data = []
        char_list = characters_data.get("角色列表", {})
        
        for char_name in selected_characters:
            if char_name in char_list:
                char_info = char_list[char_name]
                preview_data.append([
                    char_name,
                    char_info.get('年龄', '未知'),
                    char_info.get('性格', ''),
                    ', '.join(char_info.get('活动地点', [])[:3])  # 只显示前3个地点
                ])
        
        return preview_data
    
    def update_locations_preview(self, selected_locations: List[str],
                                locations_data: Dict[str, Any]) -> List[List[str]]:
        """更新地点预览表格"""
        if not selected_locations:
            return []
        
        preview_data = []
        districts = locations_data.get("districts", {})
        
        for district_name, district_info in districts.items():
            district_locations = district_info.get("locations", {})
            for loc_name, loc_info in district_locations.items():
                name = loc_info.get('name', loc_name)
                if name in selected_locations:
                    preview_data.append([
                        name,
                        loc_info.get('type', ''),
                        district_info.get('name', district_name),
                        loc_info.get('atmosphere', '')
                    ])
        
        return preview_data 