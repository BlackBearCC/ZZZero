"""
剧情生成工作流 - 基于Graph+Node的剧情创作系统
集成角色库、地点库、剧情生成等功能
"""

import json
import asyncio
import csv
import random
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.graph import StateGraph
from core.base import BaseNode
from llm.base import LLMFactory
from core.types import LLMConfig, TaskResult

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
            char_path = os.path.join(os.path.dirname(__file__), '../agents/yunhub_characters.json')
            if os.path.exists(char_path):
                with open(char_path, 'r', encoding='utf-8') as f:
                    self.characters_data = json.load(f)
            
            # 加载地点数据
            loc_path = os.path.join(os.path.dirname(__file__), '../agents/yunhub_locations.json')
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


class StoryPlanningNode(BaseNode):
    """剧情规划节点 - 分析角色关系和故事大纲"""
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行剧情规划"""
        print("🎯 开始剧情规划...")
        
        selected_characters = input_data.get('selected_characters', [])
        selected_locations = input_data.get('selected_locations', [])
        story_type = input_data.get('story_type', 'daily_life')
        
        # 构建角色信息
        characters_info = []
        char_list = input_data.get('characters_data', {}).get("角色列表", {})
        
        for char_name in selected_characters:
            if char_name in char_list:
                char_info = char_list[char_name]
                characters_info.append({
                    'name': char_name,
                    'info': char_info
                })
        
        # 构建地点信息
        locations_info = []
        districts = input_data.get('locations_data', {}).get("districts", {})
        
        for district_name, district_info in districts.items():
            district_locations = district_info.get("locations", {})
            for loc_name, loc_info in district_locations.items():
                if loc_info.get('name') in selected_locations:
                    locations_info.append({
                        'name': loc_info.get('name'),
                        'info': loc_info
                    })
        
        # LLM生成剧情规划
        if self.llm:
            prompt = f"""
# 剧情规划任务

## 角色信息
{json.dumps(characters_info, ensure_ascii=False, indent=2)}

## 地点信息  
{json.dumps(locations_info, ensure_ascii=False, indent=2)}

## 剧情类型
{story_type}

## 任务要求
请为这些角色在指定地点创建一个完整的剧情规划，包括：
1. 故事主线概述
2. 角色关系分析
3. 关键剧情节点
4. 地点利用方案

输出格式为JSON：
{{
  "story_outline": "故事主线概述",
  "character_relationships": [
    {{"char1": "角色1", "char2": "角色2", "relationship": "关系描述"}}
  ],
  "key_plot_points": ["关键剧情点1", "关键剧情点2"],
  "location_usage": [
    {{"location": "地点名", "purpose": "用途描述"}}
  ]
}}
"""
            
            try:
                response = await self.llm.generate(prompt)
                if isinstance(response, str):
                    planning_result = json.loads(response)
                else:
                    planning_result = response
            except Exception as e:
                print(f"剧情规划生成失败: {e}")
                planning_result = {
                    "story_outline": "默认剧情概述",
                    "character_relationships": [],
                    "key_plot_points": [],
                    "location_usage": []
                }
        else:
            planning_result = {
                "story_outline": "默认剧情概述", 
                "character_relationships": [],
                "key_plot_points": [],
                "location_usage": []
            }
        
        # 传递给下一个节点
        output_data = input_data.copy()
        output_data['planning_result'] = planning_result
        output_data['characters_info'] = characters_info
        output_data['locations_info'] = locations_info
        
        print("✅ 剧情规划完成")
        return output_data


class CharacterAnalysisNode(BaseNode):
    """角色分析节点 - 深度分析角色特征和行为模式"""
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行角色分析"""
        print("👥 开始角色分析...")
        
        characters_info = input_data.get('characters_info', [])
        planning_result = input_data.get('planning_result', {})
        
        character_analysis = []
        
        for char_data in characters_info:
            char_name = char_data['name']
            char_info = char_data['info']
            
            # 分析角色特征
            analysis = {
                'name': char_name,
                'personality_traits': char_info.get('性格', '').split('、'),
                'daily_schedule': char_info.get('每日行程', {}),
                'activity_locations': char_info.get('活动地点', []),
                'potential_plots': char_info.get('可触发剧情', []),
                'interaction_style': self._analyze_interaction_style(char_info),
                'story_role': self._determine_story_role(char_info)
            }
            
            character_analysis.append(analysis)
        
        output_data = input_data.copy()
        output_data['character_analysis'] = character_analysis
        
        print("✅ 角色分析完成")
        return output_data
    
    def _analyze_interaction_style(self, char_info: Dict[str, Any]) -> str:
        """分析角色互动风格"""
        personality = char_info.get('性格', '')
        if '温和' in personality or '善良' in personality:
            return '温和友善'
        elif '冷艳' in personality or '厌世' in personality:
            return '冷淡疏离'
        elif '火爆' in personality or '强干' in personality:
            return '直接热情'
        else:
            return '中性平和'
    
    def _determine_story_role(self, char_info: Dict[str, Any]) -> str:
        """确定角色在故事中的作用"""
        plots = char_info.get('可触发剧情', [])
        if len(plots) > 5:
            return '主要角色'
        elif len(plots) > 2:
            return '重要配角'
        else:
            return '背景角色'


class PlotGenerationNode(BaseNode):
    """剧情生成节点 - 生成具体的剧情事件"""
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行剧情生成"""
        print("📚 开始生成剧情...")
        
        planning_result = input_data.get('planning_result', {})
        character_analysis = input_data.get('character_analysis', [])
        locations_info = input_data.get('locations_info', [])
        config = input_data.get('config', {})
        
        # 生成剧情事件
        story_events = []
        
        # 根据角色分析和地点信息生成剧情
        for i, char_analysis in enumerate(character_analysis):
            char_name = char_analysis['name']
            potential_plots = char_analysis['potential_plots']
            activity_locations = char_analysis['activity_locations']
            
            # 为每个角色生成3-5个剧情事件
            for j, plot_idea in enumerate(potential_plots[:5]):
                # 选择适合的地点
                suitable_location = self._find_suitable_location(
                    activity_locations, locations_info
                )
                
                event = {
                    'plot_id': f"{char_name}_{j+1:02d}",
                    'character': char_name,
                    'plot_name': plot_idea,
                    'location': suitable_location,
                    'description': f"在{suitable_location}发生的{plot_idea}相关剧情",
                    'trigger_condition': self._generate_trigger_condition(j),
                    'success_condition': f"完成{plot_idea}相关互动",
                    'unlock_plots': self._generate_unlock_plots(char_name, j+2),
                    'probability': self._calculate_probability(j),
                    'stage': f"阶段{j+1}",
                    'keywords': self._extract_keywords(plot_idea, suitable_location)
                }
                
                story_events.append(event)
        
        output_data = input_data.copy()
        output_data['story_events'] = story_events
        
        print(f"✅ 剧情生成完成，共生成{len(story_events)}个剧情事件")
        return output_data
    
    def _find_suitable_location(self, activity_locations: List[str], 
                               locations_info: List[Dict[str, Any]]) -> str:
        """为剧情寻找合适的地点"""
        for loc_name in activity_locations:
            for loc_info in locations_info:
                if loc_info['name'] == loc_name:
                    return loc_name
        
        # 如果没有匹配的选择地点，返回第一个活动地点
        return activity_locations[0] if activity_locations else "未知地点"
    
    def _generate_trigger_condition(self, index: int) -> str:
        """生成触发条件"""
        if index == 0:
            return "无"
        else:
            return f"完成前置剧情阶段{index}"
    
    def _generate_unlock_plots(self, char_name: str, next_index: int) -> List[str]:
        """生成解锁剧情"""
        return [f"{char_name}_{next_index:02d}"] if next_index <= 5 else []
    
    def _calculate_probability(self, index: int) -> str:
        """计算触发概率"""
        probabilities = ["85%", "75%", "65%", "55%", "45%"]
        return probabilities[min(index, len(probabilities)-1)]
    
    def _extract_keywords(self, plot_idea: str, location: str) -> List[str]:
        """提取关键词"""
        keywords = []
        if "相遇" in plot_idea or "邂逅" in plot_idea:
            keywords.extend(["相遇", "初识"])
        if "交流" in plot_idea or "聊天" in plot_idea:
            keywords.extend(["对话", "交流"])
        if "帮助" in plot_idea:
            keywords.extend(["帮助", "互助"])
        if "回忆" in plot_idea or "故事" in plot_idea:
            keywords.extend(["回忆", "分享"])
        
        keywords.append(location)
        return keywords


class CSVExportNode(BaseNode):
    """CSV导出节点 - 将剧情数据导出为CSV格式"""
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行CSV导出"""
        print("📄 开始导出CSV...")
        
        story_events = input_data.get('story_events', [])
        
        # 准备CSV数据
        csv_headers = [
            "剧情ID", "NPC", "剧情名", "剧情阶段", "触发地点", 
            "前置条件", "描述", "关键事件", "触发概率", 
            "完成条件", "解锁剧情", "状态"
        ]
        
        csv_data = []
        for event in story_events:
            csv_data.append([
                event.get('plot_id', ''),
                event.get('character', ''),
                event.get('plot_name', ''),
                event.get('stage', ''),
                event.get('location', ''),
                event.get('trigger_condition', '无'),
                event.get('description', ''),
                '; '.join(event.get('keywords', [])),
                event.get('probability', '50%'),
                event.get('success_condition', ''),
                '; '.join(event.get('unlock_plots', [])),
                "未触发"
            ])
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"story_plot_{timestamp}.csv"
        
        # 确保输出目录存在
        output_dir = Path("workspace/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = output_dir / filename
        
        # 写入CSV文件
        with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(csv_headers)
            writer.writerows(csv_data)
        
        output_data = input_data.copy()
        output_data['export_file'] = str(filepath)
        output_data['csv_data'] = csv_data
        output_data['csv_headers'] = csv_headers
        
        print(f"✅ CSV导出完成: {filepath}")
        return output_data 