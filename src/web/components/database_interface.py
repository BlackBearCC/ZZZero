"""
数据库管理界面组件 - 提供剧情数据的查看、编辑、导出功能
"""

import gradio as gr
import json
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime

# 确保数据库模块路径正确
import sys
import os

# 获取项目根目录路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logger = logging.getLogger(__name__)

# 尝试导入数据库管理器，如果失败则使用空的占位符
try:
    from database import story_manager, character_manager, schedule_manager, database_manager
    DATABASE_AVAILABLE = True
except Exception as e:
    logger.warning(f"数据库组件导入失败，将禁用数据库功能: {e}")
    story_manager = None
    character_manager = None
    schedule_manager = None
    database_manager = None
    DATABASE_AVAILABLE = False

class DatabaseInterface:
    """数据库管理界面"""
    
    def __init__(self):
        self.story_manager = story_manager
        self.character_manager = character_manager
        self.schedule_manager = schedule_manager
        self.database_manager = database_manager
    
    def create_interface(self) -> gr.Blocks:
        """创建数据库管理界面"""
        with gr.Blocks(title="数据库管理", theme=gr.themes.Soft()) as interface:
            gr.Markdown("# 📊 数据库管理中心")
            gr.Markdown("管理剧情数据、角色信息、日程安排、查看统计信息和执行数据库操作")
            
            with gr.Tabs():
                # 剧情管理标签页
                with gr.Tab("📚 剧情管理"):
                    self._create_story_management_tab()
                
                # 角色管理标签页
                with gr.Tab("👥 角色管理"):
                    self._create_character_management_tab()
                
                # 日程管理标签页
                with gr.Tab("📅 日程管理"):
                    self._create_schedule_management_tab()
                
                # 数据库操作标签页
                with gr.Tab("🛠️ 数据库操作"):
                    self._create_database_operations_tab()
                
                # 统计信息标签页
                with gr.Tab("📈 统计信息"):
                    self._create_statistics_tab()
                
                # 执行记录标签页
                with gr.Tab("🔍 执行记录"):
                    self._create_execution_records_tab()
        
        return interface
    
    def _create_story_management_tab(self):
        """创建剧情管理标签页"""
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## 筛选条件")
                
                # 筛选条件
                character_filter = gr.Textbox(
                    label="按角色筛选",
                    placeholder="输入角色名称",
                    info="显示包含该角色的所有剧情"
                )
                
                story_type_filter = gr.Dropdown(
                    label="剧情类型",
                    choices=["全部", "daily_life", "romance", "adventure", "mystery"],
                    value="全部"
                )
                
                protagonist_filter = gr.Dropdown(
                    label="主角",
                    choices=["全部", "方知衡"],
                    value="全部"
                )
                
                # 操作按钮
                search_btn = gr.Button("🔍 搜索剧情", variant="primary")
                refresh_btn = gr.Button("🔄 刷新列表")
                export_btn = gr.Button("📤 导出CSV")
                
            with gr.Column(scale=3):
                gr.Markdown("## 剧情列表")
                
                # 剧情列表表格
                story_table = gr.Dataframe(
                    headers=["剧情ID", "剧情名称", "剧情概述", "类型", "主角", "小节数", "角色", "创建时间"],
                    datatype=["str", "str", "str", "str", "str", "number", "str", "str"],
                    interactive=False,
                    wrap=True
                )
                
                # 选中剧情的详细信息
                with gr.Accordion("📖 剧情详情", open=False):
                    selected_story_info = gr.Markdown("请先选择一个剧情")
                    
                    # 小节列表
                    scenes_table = gr.Dataframe(
                        headers=["小节ID", "标题", "完整内容", "地点", "角色"],
                        datatype=["str", "str", "str", "str", "str"],
                        interactive=False,
                        wrap=True
                    )
                
                # 操作区域
                with gr.Row():
                    selected_story_id = gr.Textbox(
                        label="选中的剧情ID",
                        placeholder="点击表格行选择剧情",
                        interactive=False
                    )
                    delete_story_btn = gr.Button("🗑️ 删除剧情", variant="stop")
                    view_scenes_btn = gr.Button("👁️ 查看小节", variant="secondary")
        
        # 事件绑定
        search_btn.click(
            fn=self._search_stories,
            inputs=[character_filter, story_type_filter, protagonist_filter],
            outputs=[story_table]
        )
        
        refresh_btn.click(
            fn=self._load_all_stories,
            outputs=[story_table]
        )
        
        story_table.select(
            fn=self._on_story_selected,
            outputs=[selected_story_id, selected_story_info, scenes_table]
        )
        
        view_scenes_btn.click(
            fn=self._load_story_scenes,
            inputs=[selected_story_id],
            outputs=[scenes_table]
        )
        
        delete_story_btn.click(
            fn=self._delete_story,
            inputs=[selected_story_id],
            outputs=[story_table, selected_story_info, scenes_table]
        )
        
        export_btn.click(
            fn=self._export_stories,
            inputs=[character_filter, story_type_filter],
            outputs=[gr.File()]
        )
    
    def _create_character_management_tab(self):
        """创建角色管理标签页"""
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## 角色筛选")
                
                character_search = gr.Textbox(
                    label="搜索角色",
                    placeholder="输入角色名称关键词"
                )
                
                search_character_btn = gr.Button("🔍 搜索角色", variant="primary")
                refresh_character_btn = gr.Button("🔄 刷新列表")
                
            with gr.Column(scale=3):
                gr.Markdown("## 角色列表")
                
                # 角色统计表格
                character_table = gr.Dataframe(
                    headers=["角色名称", "剧情数量", "总互动次数", "平均重要度", "角色定位"],
                    datatype=["str", "number", "number", "number", "str"],
                    interactive=False,
                    wrap=True
                )
                
                # 选中角色的详细信息
                with gr.Accordion("👤 角色详情", open=False):
                    selected_character_info = gr.Markdown("请先选择一个角色")
                    
                    # 角色相关剧情
                    character_stories_table = gr.Dataframe(
                        headers=["剧情名称", "角色重要度", "互动次数", "创建时间"],
                        datatype=["str", "number", "number", "str"],
                        interactive=False,
                        wrap=True
                    )
                
                # 操作区域
                with gr.Row():
                    selected_character_name = gr.Textbox(
                        label="选中的角色",
                        placeholder="点击表格行选择角色",
                        interactive=False
                    )
                    view_character_stories_btn = gr.Button("📚 查看相关剧情", variant="secondary")
        
        # 事件绑定
        search_character_btn.click(
            fn=self._search_characters,
            inputs=[character_search],
            outputs=[character_table]
        )
        
        refresh_character_btn.click(
            fn=self._load_all_characters,
            outputs=[character_table]
        )
        
        character_table.select(
            fn=self._on_character_selected,
            outputs=[selected_character_name, selected_character_info]
        )
        
        view_character_stories_btn.click(
            fn=self._load_character_stories,
            inputs=[selected_character_name],
            outputs=[character_stories_table]
        )
    
    def _create_schedule_management_tab(self):
        """创建日程管理标签页"""
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## 筛选条件")
                
                # 筛选条件
                date_filter = gr.Textbox(
                    label="按日期筛选",
                    placeholder="YYYY-MM-DD",
                    info="按日期过滤日程"
                )
                
                character_filter = gr.Textbox(
                    label="按角色筛选",
                    placeholder="输入角色名称",
                    info="显示包含该角色的所有日程"
                )
                
                date_range_filter = gr.Radio(
                    label="日期范围",
                    choices=["全部", "今天", "本周", "本月", "未来7天"],
                    value="全部"
                )
                
                # 操作按钮
                search_btn = gr.Button("🔍 搜索日程", variant="primary")
                refresh_btn = gr.Button("🔄 刷新列表")
                export_btn = gr.Button("📤 导出CSV")
                
            with gr.Column(scale=3):
                gr.Markdown("## 日程列表")
                
                # 日程列表表格
                schedule_table = gr.Dataframe(
                    headers=["日程ID", "日程名称", "日期范围", "主角", "类型", "涉及角色", "总天数", "实际天数", "创建时间"],
                    datatype=["str", "str", "str", "str", "str", "str", "number", "number", "str"],
                    interactive=False,
                    wrap=True
                )
                
                # 选中日程的详细信息
                with gr.Accordion("📖 日程详情", open=False):
                    selected_schedule_info = gr.Markdown("请先选择一个日程")
                    
                    # 日程详细活动表
                    activities_table = gr.Dataframe(
                        headers=["日期时间", "时间段", "活动内容", "地点", "参与角色", "活动类型", "重要度"],
                        datatype=["str", "str", "str", "str", "str", "str", "number"],
                        interactive=False,
                        wrap=True
                    )
                
                # 操作区域
                with gr.Row():
                    selected_schedule_id = gr.Textbox(
                        label="选中的日程ID",
                        placeholder="点击表格行选择日程",
                        interactive=False
                    )
                    delete_schedule_btn = gr.Button("🗑️ 删除日程", variant="stop")
                    view_activities_btn = gr.Button("👁️ 查看详细活动", variant="secondary")
        
        # 事件绑定
        search_btn.click(
            fn=self._search_schedules,
            inputs=[date_filter, character_filter, date_range_filter],
            outputs=[schedule_table]
        )
        
        refresh_btn.click(
            fn=self._load_all_schedules,
            outputs=[schedule_table]
        )
        
        schedule_table.select(
            fn=self._on_schedule_selected,
            outputs=[selected_schedule_id, selected_schedule_info, activities_table]
        )
        
        view_activities_btn.click(
            fn=self._load_schedule_activities,
            inputs=[selected_schedule_id],
            outputs=[activities_table]
        )
        
        delete_schedule_btn.click(
            fn=self._delete_schedule,
            inputs=[selected_schedule_id],
            outputs=[schedule_table, selected_schedule_info, activities_table]
        )
        
        export_btn.click(
            fn=self._export_schedules,
            inputs=[date_filter, character_filter, date_range_filter],
            outputs=[gr.File()]
        )
    
    def _create_database_operations_tab(self):
        """创建数据库操作标签页"""
        with gr.Row():
            with gr.Column():
                gr.Markdown("## 数据库信息")
                
                db_info_display = gr.Markdown("点击刷新按钮获取数据库信息")
                refresh_db_info_btn = gr.Button("🔄 刷新数据库信息", variant="primary")
                
                gr.Markdown("## 导出操作")
                
                with gr.Row():
                    export_format = gr.Radio(
                        label="导出格式",
                        choices=["CSV", "JSON"],
                        value="CSV"
                    )
                    
                    export_scope = gr.Radio(
                        label="导出范围",
                        choices=["全部数据", "仅剧情表", "仅角色表"],
                        value="全部数据"
                    )
                
                export_data_btn = gr.Button("📤 导出数据", variant="secondary")
                export_result = gr.File(label="下载导出文件")
                
                gr.Markdown("## 数据库维护")
                
                with gr.Row():
                    vacuum_btn = gr.Button("🧹 清理优化数据库", variant="secondary")
                    backup_btn = gr.Button("💾 备份数据库", variant="secondary")
                
                maintenance_result = gr.Textbox(
                    label="操作结果",
                    interactive=False,
                    max_lines=5
                )
        
        # 事件绑定
        refresh_db_info_btn.click(
            fn=self._get_database_info,
            outputs=[db_info_display]
        )
        
        export_data_btn.click(
            fn=self._export_database,
            inputs=[export_format, export_scope],
            outputs=[export_result]
        )
        
        vacuum_btn.click(
            fn=self._vacuum_database,
            outputs=[maintenance_result]
        )
        
        backup_btn.click(
            fn=self._backup_database,
            outputs=[maintenance_result]
        )
    
    def _create_statistics_tab(self):
        """创建统计信息标签页"""
        with gr.Column():
            gr.Markdown("## 📊 数据库统计信息")
            
            refresh_stats_btn = gr.Button("🔄 刷新统计", variant="primary")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### 基础统计")
                    basic_stats_display = gr.Markdown("点击刷新按钮获取统计信息")
                
                with gr.Column():
                    gr.Markdown("### 分类统计")
                    category_stats_display = gr.Markdown("点击刷新按钮获取统计信息")
            
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### 最活跃角色")
                    active_characters_table = gr.Dataframe(
                        headers=["角色名称", "参与剧情数"],
                        datatype=["str", "number"],
                        interactive=False
                    )
                
                with gr.Column():
                    gr.Markdown("### 数据库表信息")
                    tables_info_display = gr.Markdown("点击刷新按钮获取表信息")
        
        # 事件绑定
        refresh_stats_btn.click(
            fn=self._get_statistics,
            outputs=[basic_stats_display, category_stats_display, active_characters_table, tables_info_display]
        )
    
    # 数据处理方法
    def _load_all_stories(self) -> pd.DataFrame:
        """加载所有剧情"""
        try:
            stories = self.story_manager.get_stories_by_filter({})
            
            data = []
            for story in stories:
                data.append([
                    story['story_id'],
                    story['story_name'],
                    story.get('story_overview', ''),  # 显示完整剧情概述
                    story['story_type'],
                    story['protagonist'],
                    story['scene_count'],
                    ', '.join(story['characters']),  # 显示所有角色
                    story['created_at'][:19]  # 只显示到秒
                ])
            
            return pd.DataFrame(data, columns=["剧情ID", "剧情名称", "剧情概述", "类型", "主角", "小节数", "角色", "创建时间"])
            
        except Exception as e:
            logger.error(f"加载剧情列表失败: {e}")
            return pd.DataFrame(columns=["剧情ID", "剧情名称", "剧情概述", "类型", "主角", "小节数", "角色", "创建时间"])
    
    def _search_stories(self, character_filter: str, story_type_filter: str, protagonist_filter: str) -> pd.DataFrame:
        """搜索剧情"""
        try:
            filters = {}
            
            if character_filter.strip():
                filters['character_name'] = character_filter.strip()
            
            if story_type_filter != "全部":
                filters['story_type'] = story_type_filter
            
            if protagonist_filter != "全部":
                filters['protagonist'] = protagonist_filter
            
            stories = self.story_manager.get_stories_by_filter(filters)
            
            data = []
            for story in stories:
                data.append([
                    story['story_id'],
                    story['story_name'],
                    story.get('story_overview', ''),  # 显示完整剧情概述
                    story['story_type'],
                    story['protagonist'],
                    story['scene_count'],
                    ', '.join(story['characters']),  # 显示所有角色
                    story['created_at'][:19]  # 只显示到秒
                ])
            
            return pd.DataFrame(data, columns=["剧情ID", "剧情名称", "剧情概述", "类型", "主角", "小节数", "角色", "创建时间"])
            
        except Exception as e:
            logger.error(f"搜索剧情失败: {e}")
            return pd.DataFrame(columns=["剧情ID", "剧情名称", "剧情概述", "类型", "主角", "小节数", "角色", "创建时间"])
    
    def _on_story_selected(self, evt: gr.SelectData) -> Tuple[str, str, pd.DataFrame]:
        """处理剧情选择事件"""
        try:
            if evt is None or evt.index is None:
                return "", "请先选择一个剧情", pd.DataFrame()
            
            # 获取选中行的索引
            row_index = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
            
            # 重新获取数据以确保索引对应正确
            stories = self.story_manager.get_stories_by_filter({})
            
            if row_index >= len(stories):
                return "", "选择的行索引超出范围", pd.DataFrame()
                
            story = stories[row_index]
            story_id = story['story_id']
            
            # 构建详细信息显示
            story_info = f"""### 📖 剧情详情

**剧情ID**: {story['story_id']}
**剧情名称**: {story['story_name']}
**剧情类型**: {story['story_type']}
**主角**: {story['protagonist']}
**小节数量**: {story['scene_count']}
**参与角色**: {', '.join(story['characters'])}
**创建时间**: {story['created_at']}

**剧情概述**:
{story.get('story_overview', '暂无概述')}

**主要冲突**: {story.get('main_conflict', '暂无')}
"""
            
            # 获取小节信息 - 显示完整内容
            scenes = self.story_manager.get_story_scenes(story_id)
            scenes_data = []
            
            for scene in scenes:
                scenes_data.append([
                    scene['scene_id'],
                    scene['scene_title'],
                    scene['scene_content'],  # 显示完整小节内容
                    scene['location'],
                    ', '.join(scene['participants'])
                ])
            
            scenes_df = pd.DataFrame(scenes_data, columns=["小节ID", "标题", "完整内容", "地点", "角色"])
            
            return story_id, story_info, scenes_df
            
        except Exception as e:
            logger.error(f"选择剧情失败: {e}")
            return "", f"处理剧情选择失败: {str(e)}", pd.DataFrame()
    
    def _load_story_scenes(self, story_id: str) -> pd.DataFrame:
        """加载剧情小节"""
        try:
            if not story_id:
                return pd.DataFrame(columns=["小节ID", "标题", "完整内容", "地点", "角色"])
            
            scenes = self.story_manager.get_story_scenes(story_id)
            data = []
            
            for scene in scenes:
                data.append([
                    scene['scene_id'],
                    scene['scene_title'],
                    scene['scene_content'],  # 显示完整小节内容
                    scene['location'],
                    ', '.join(scene['participants'])
                ])
            
            return pd.DataFrame(data, columns=["小节ID", "标题", "完整内容", "地点", "角色"])
            
        except Exception as e:
            logger.error(f"加载小节失败: {e}")
            return pd.DataFrame(columns=["小节ID", "标题", "完整内容", "地点", "角色"])
    
    def _delete_story(self, story_id: str) -> Tuple[pd.DataFrame, str, pd.DataFrame]:
        """删除剧情"""
        try:
            if not story_id:
                return self._load_all_stories(), "请先选择要删除的剧情", pd.DataFrame()
            
            success = self.story_manager.delete_story(story_id)
            
            if success:
                return (
                    self._load_all_stories(), 
                    f"✅ 成功删除剧情: {story_id}", 
                    pd.DataFrame(columns=["小节ID", "标题", "完整内容", "地点", "角色"])
                )
            else:
                return (
                    self._load_all_stories(), 
                    f"❌ 删除剧情失败: {story_id}", 
                    pd.DataFrame()
                )
                
        except Exception as e:
            logger.error(f"删除剧情失败: {e}")
            return (
                self._load_all_stories(), 
                f"❌ 删除剧情异常: {str(e)}", 
                pd.DataFrame()
            )
    
    def _export_stories(self, character_filter: str, story_type_filter: str) -> str:
        """导出剧情数据到CSV文件"""
        try:
            import tempfile
            import os
            from datetime import datetime
            
            # 获取筛选后的剧情数据
            stories_df = self._search_stories(character_filter, story_type_filter, "全部")
            
            if stories_df.empty:
                return "没有可导出的数据"
            
            # 创建临时文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"stories_export_{timestamp}.csv"
            
            # 使用工作空间输出目录
            output_dir = "./workspace/output"
            os.makedirs(output_dir, exist_ok=True)
            filepath = os.path.join(output_dir, filename)
            
            # 导出到CSV
            stories_df.to_csv(filepath, index=False, encoding='utf-8-sig')
            
            logger.info(f"剧情数据导出成功: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"导出剧情数据失败: {e}")
            return f"导出失败: {str(e)}"
    
    def _load_all_characters(self) -> pd.DataFrame:
        """加载所有角色"""
        try:
            characters = self.story_manager.get_all_characters()
            
            data = []
            for char in characters:
                data.append([
                    char['character_name'],
                    char['story_count'],
                    char['total_interactions'],
                    char['avg_importance'],
                    ', '.join(char['roles'])
                ])
            
            return pd.DataFrame(data, columns=["角色名称", "剧情数量", "总互动次数", "平均重要度", "角色定位"])
            
        except Exception as e:
            logger.error(f"加载角色列表失败: {e}")
            return pd.DataFrame(columns=["角色名称", "剧情数量", "总互动次数", "平均重要度", "角色定位"])
    
    def _search_characters(self, search_term: str) -> pd.DataFrame:
        """搜索角色"""
        try:
            all_characters = self._load_all_characters()
            
            if not search_term.strip():
                return all_characters
            
            # 简单的名称匹配筛选
            filtered = all_characters[all_characters['角色名称'].str.contains(search_term.strip(), case=False, na=False)]
            return filtered
            
        except Exception as e:
            logger.error(f"搜索角色失败: {e}")
            return pd.DataFrame(columns=["角色名称", "剧情数量", "总互动次数", "平均重要度", "角色定位"])
    
    def _on_character_selected(self, evt: gr.SelectData) -> Tuple[str, str]:
        """处理角色选择事件"""
        try:
            if evt is None or evt.index is None:
                return "", "请先选择一个角色"
            
            # 获取选中行的索引
            row_index = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
            
            # 重新获取数据以确保索引对应正确
            characters = self.story_manager.get_all_characters()
            
            if row_index >= len(characters):
                return "", "选择的行索引超出范围"
                
            character = characters[row_index]
            character_name = character['character_name']
            
            # 构建角色详细信息
            character_info = f"""### 👤 角色详情

**角色名称**: {character['character_name']}
**参与剧情数**: {character['story_count']} 个
**总互动次数**: {character['total_interactions']} 次
**平均重要度**: {character['avg_importance']} 级
**角色定位**: {', '.join(character['roles'])}

该角色在剧情中的活跃度较高，是重要的故事角色。
"""
            
            return character_name, character_info
            
        except Exception as e:
            logger.error(f"选择角色失败: {e}")
            return "", f"处理角色选择失败: {str(e)}"
    
    def _load_character_stories(self, character_name: str) -> pd.DataFrame:
        """加载角色相关剧情"""
        try:
            if not character_name:
                return pd.DataFrame(columns=["剧情名称", "角色重要度", "互动次数", "创建时间"])
            
            stories = self.story_manager.get_character_stories(character_name)
            data = []
            
            for story in stories:
                data.append([
                    story['story_name'],
                    story['importance_level'],
                    story['interaction_count'],
                    story['created_at'][:19]
                ])
            
            return pd.DataFrame(data, columns=["剧情名称", "角色重要度", "互动次数", "创建时间"])
            
        except Exception as e:
            logger.error(f"加载角色剧情失败: {e}")
            return pd.DataFrame(columns=["剧情名称", "角色重要度", "互动次数", "创建时间"])
    
    def _get_database_info(self) -> str:
        """获取数据库信息"""
        try:
            info = self.story_manager.get_database_info()
            
            info_text = f"""## 📊 数据库信息

### 基本信息
- **数据库路径**: {info.get('database_path', '未知')}
- **数据库大小**: {info.get('database_size', 0) / 1024:.2f} KB
- **总记录数**: {info.get('total_records', 0)}

### 表信息
"""
            
            for table_name, table_info in info.get('tables', {}).items():
                info_text += f"- **{table_name}**: {table_info['record_count']} 条记录\n"
            
            return info_text
            
        except Exception as e:
            logger.error(f"获取数据库信息失败: {e}")
            return f"❌ 获取数据库信息失败: {str(e)}"
    
    def _export_database(self, format_type: str, scope: str) -> str:
        """导出数据库"""
        try:
            if format_type == "CSV":
                if scope == "全部数据":
                    file_path = self.story_manager.export_story_data(format='csv')
                elif scope == "仅剧情表":
                    file_path = self.story_manager.export_table_to_csv('stories')
                else:
                    file_path = self.story_manager.export_table_to_csv('character_stories')
            else:  # JSON
                file_path = self.story_manager.export_story_data(format='json')
            
            return file_path
            
        except Exception as e:
            logger.error(f"导出数据库失败: {e}")
            return ""
    
    def _vacuum_database(self) -> str:
        """清理优化数据库"""
        try:
            self.story_manager.vacuum_database()
            return "✅ 数据库清理优化完成"
            
        except Exception as e:
            logger.error(f"数据库清理失败: {e}")
            return f"❌ 数据库清理失败: {str(e)}"
    
    def _backup_database(self) -> str:
        """备份数据库"""
        try:
            backup_path = self.story_manager.backup_table('stories')
            return f"✅ 数据库备份完成: {backup_path}"
            
        except Exception as e:
            logger.error(f"数据库备份失败: {e}")
            return f"❌ 数据库备份失败: {str(e)}"
    
    def _get_statistics(self) -> Tuple[str, str, pd.DataFrame, str]:
        """获取统计信息"""
        try:
            stats = self.story_manager.get_story_statistics()
            
            # 基础统计
            basic_stats = f"""### 📊 基础统计

- **总剧情数**: {stats.get('total_stories', 0)}
- **总小节数**: {stats.get('total_scenes', 0)}
- **参与角色数**: {stats.get('total_characters', 0)}
- **独立角色数**: {stats.get('unique_characters', 0)}
- **最新创建**: {stats.get('latest_creation', '未知')[:19] if stats.get('latest_creation') else '未知'}
"""
            
            # 分类统计
            category_stats = "### 📈 分类统计\n\n**按剧情类型**:\n"
            for story_type, count in stats.get('by_story_type', {}).items():
                category_stats += f"- {story_type}: {count}\n"
            
            category_stats += "\n**按主角**:\n"
            for protagonist, count in stats.get('by_protagonist', {}).items():
                category_stats += f"- {protagonist}: {count}\n"
            
            # 最活跃角色表格
            active_chars = stats.get('most_active_characters', [])
            active_chars_df = pd.DataFrame(active_chars, columns=["角色名称", "参与剧情数"])
            
            # 表信息
            db_info = self.story_manager.get_database_info()
            tables_info = "### 🗂️ 表信息\n\n"
            for table_name, table_info in db_info.get('tables', {}).items():
                tables_info += f"- **{table_name}**: {table_info['record_count']} 条记录\n"
            
            return basic_stats, category_stats, active_chars_df, tables_info
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            error_msg = f"❌ 获取统计信息失败: {str(e)}"
            return error_msg, error_msg, pd.DataFrame(), error_msg

    def _load_all_schedules(self) -> pd.DataFrame:
        """加载所有日程"""
        try:
            schedules = self.schedule_manager.get_all_schedules()
            
            data = []
            for schedule in schedules:
                data.append([
                    schedule['schedule_id'],
                    schedule.get('schedule_name', ''),
                    f"{schedule['start_date']} - {schedule['end_date']}",
                    schedule.get('protagonist', ''),
                    schedule.get('schedule_type', ''),
                    ', '.join(schedule.get('characters', [])),
                    schedule['total_days'],
                    schedule['actual_days'],
                    schedule['created_at'][:19] if schedule.get('created_at') else ''
                ])
            
            return pd.DataFrame(data, columns=["日程ID", "日程名称", "日期范围", "主角", "类型", "涉及角色", "总天数", "实际天数", "创建时间"])
            
        except Exception as e:
            logger.error(f"加载日程列表失败: {e}")
            return pd.DataFrame(columns=["日程ID", "日程名称", "日期范围", "主角", "类型", "涉及角色", "总天数", "实际天数", "创建时间"])

    def _search_schedules(self, date_filter: str, character_filter: str, date_range_filter: str) -> pd.DataFrame:
        """搜索日程"""
        try:
            filters = {}
            
            # 处理日期筛选
            if date_filter.strip():
                filters['date'] = date_filter.strip()
            
            # 处理角色筛选
            if character_filter.strip():
                filters['character'] = character_filter.strip()
            
            # 处理日期范围
            if date_range_filter != "全部":
                from datetime import datetime, timedelta
                today = datetime.now().date()
                
                if date_range_filter == "今天":
                    filters['date_range'] = {
                        'start': today.strftime('%Y-%m-%d'),
                        'end': today.strftime('%Y-%m-%d')
                    }
                elif date_range_filter == "本周":
                    start_of_week = today - timedelta(days=today.weekday())
                    end_of_week = start_of_week + timedelta(days=6)
                    filters['date_range'] = {
                        'start': start_of_week.strftime('%Y-%m-%d'),
                        'end': end_of_week.strftime('%Y-%m-%d')
                    }
                elif date_range_filter == "本月":
                    start_of_month = today.replace(day=1)
                    if today.month == 12:
                        end_of_month = today.replace(year=today.year+1, month=1, day=1) - timedelta(days=1)
                    else:
                        end_of_month = today.replace(month=today.month+1, day=1) - timedelta(days=1)
                    filters['date_range'] = {
                        'start': start_of_month.strftime('%Y-%m-%d'),
                        'end': end_of_month.strftime('%Y-%m-%d')
                    }
                elif date_range_filter == "未来7天":
                    filters['date_range'] = {
                        'start': today.strftime('%Y-%m-%d'),
                        'end': (today + timedelta(days=6)).strftime('%Y-%m-%d')
                    }
            
            schedules = self.schedule_manager.get_schedules_by_filter(filters)
            
            data = []
            for schedule in schedules:
                # 使用与_load_all_schedules相同的格式
                data.append([
                    schedule['schedule_id'],
                    schedule.get('schedule_name', ''),
                    f"{schedule['start_date']} - {schedule['end_date']}",
                    schedule.get('protagonist', ''),
                    schedule.get('schedule_type', ''),
                    ', '.join(schedule.get('characters', [])),
                    schedule['total_days'],
                    schedule.get('actual_days', schedule['total_days']),
                    schedule['created_at'][:19] if schedule.get('created_at') else ''
                ])
            
            return pd.DataFrame(data, columns=["日程ID", "日程名称", "日期范围", "主角", "类型", "涉及角色", "总天数", "实际天数", "创建时间"])
            
        except Exception as e:
            logger.error(f"搜索日程失败: {e}")
            return pd.DataFrame(columns=["日程ID", "日程名称", "日期范围", "主角", "类型", "涉及角色", "总天数", "实际天数", "创建时间"])

    def _on_schedule_selected(self, evt: gr.SelectData) -> Tuple[str, str, pd.DataFrame]:
        """处理日程选择事件"""
        try:
            if evt is None or evt.index is None:
                return "", "请先选择一个日程", pd.DataFrame()
            
            # 获取选中行的索引
            row_index = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
            
            # 重新获取数据以确保索引对应正确
            schedules = self.schedule_manager.get_all_schedules()
            
            if row_index >= len(schedules):
                return "", "选择的行索引超出范围", pd.DataFrame()
                
            schedule = schedules[row_index]
            schedule_id = schedule['schedule_id']
            
            # 构建详细信息显示
            schedule_info = f"""### 📅 日程详情

**日程ID**: {schedule['schedule_id']}
**日程名称**: {schedule['schedule_name']}
**日期范围**: {schedule['start_date']} - {schedule['end_date']}
**总天数**: {schedule['total_days']}天
**实际天数**: {schedule['actual_days']}天
**主角**: {schedule['protagonist']}
**涉及角色**: {', '.join(schedule.get('characters', []))}
**日程类型**: {schedule.get('schedule_type', '未指定')}

**描述**:
{schedule.get('description', '暂无描述')}

**创建时间**: {schedule.get('created_at', '未知')}
"""
            
            # 获取活动信息
            activities = self.schedule_manager.get_schedule_activities(schedule_id)
            activities_data = []
            
            for activity in activities:
                activities_data.append([
                    activity.get('time', ''),
                    activity.get('slot_name', ''),
                    activity.get('description', '')[:100] + ('...' if len(activity.get('description', '')) > 100 else ''),
                    activity.get('location', ''),
                    ', '.join(activity.get('participants', [])),
                    activity.get('activity_type', ''),
                    activity.get('importance_level', 3)
                ])
            
            activities_df = pd.DataFrame(activities_data, columns=["日期时间", "时间段", "活动内容", "地点", "参与角色", "活动类型", "重要度"])
            
            return schedule_id, schedule_info, activities_df
            
        except Exception as e:
            logger.error(f"选择日程失败: {e}")
            return "", f"处理日程选择失败: {str(e)}", pd.DataFrame()

    def _load_schedule_activities(self, schedule_id: str) -> pd.DataFrame:
        """加载日程活动"""
        try:
            if not schedule_id:
                return pd.DataFrame(columns=["日期时间", "时间段", "活动内容", "地点", "参与角色", "活动类型", "重要度"])
            
            activities = self.schedule_manager.get_schedule_activities(schedule_id)
            data = []
            
            for activity in activities:
                data.append([
                    activity.get('time', ''),
                    activity.get('slot_name', ''),
                    activity.get('description', '')[:100] + ('...' if len(activity.get('description', '')) > 100 else ''),
                    activity.get('location', ''),
                    ', '.join(activity.get('participants', [])),
                    activity.get('activity_type', ''),
                    activity.get('importance_level', 3)
                ])
            
            return pd.DataFrame(data, columns=["日期时间", "时间段", "活动内容", "地点", "参与角色", "活动类型", "重要度"])
            
        except Exception as e:
            logger.error(f"加载日程活动失败: {e}")
            return pd.DataFrame(columns=["日期时间", "时间段", "活动内容", "地点", "参与角色", "活动类型", "重要度"])

    def _delete_schedule(self, schedule_id: str) -> Tuple[pd.DataFrame, str, pd.DataFrame]:
        """删除日程"""
        try:
            if not schedule_id:
                return self._load_all_schedules(), "请先选择一个日程", pd.DataFrame()
            
            success = self.schedule_manager.delete_schedule(schedule_id)
            
            if success:
                return self._load_all_schedules(), f"已成功删除日程 {schedule_id}", pd.DataFrame()
            else:
                return self._load_all_schedules(), f"删除日程 {schedule_id} 失败", pd.DataFrame()
            
        except Exception as e:
            logger.error(f"删除日程失败: {e}")
            return self._load_all_schedules(), f"删除日程失败: {str(e)}", pd.DataFrame()

    def _export_schedules(self, date_filter: str, character_filter: str, date_range_filter: str) -> str:
        """导出日程为CSV"""
        try:
            # 先获取过滤后的日程数据
            df = self._search_schedules(date_filter, character_filter, date_range_filter)
            
            # 确保数据存在
            if df.empty:
                return None
            
            # 创建输出目录
            export_dir = os.path.join(project_root, "workspace", "exports")
            os.makedirs(export_dir, exist_ok=True)
            
            # 创建导出文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = os.path.join(export_dir, f"schedules_export_{timestamp}.csv")
            
            # 导出为CSV
            df.to_csv(export_path, index=False, encoding='utf-8-sig')
            
            return export_path
            
        except Exception as e:
            logger.error(f"导出日程失败: {e}")
            return None

    def _create_execution_records_tab(self):
        """创建执行记录管理标签页"""
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## 筛选条件")
                
                # 筛选条件
                graph_name_filter = gr.Textbox(
                    label="按图名称筛选",
                    placeholder="输入图名称",
                    info="显示包含该名称的执行记录"
                )
                
                execution_status_filter = gr.Dropdown(
                    label="执行状态",
                    choices=["全部", "成功", "失败"],
                    value="全部"
                )
                
                time_range_filter = gr.Radio(
                    label="时间范围",
                    choices=["全部", "今天", "本周", "本月", "最近100条"],
                    value="最近100条"
                )
                
                # 操作按钮
                search_execution_btn = gr.Button("🔍 搜索记录", variant="primary")
                refresh_execution_btn = gr.Button("🔄 刷新列表")
                export_execution_btn = gr.Button("📤 导出CSV")
                
            with gr.Column(scale=3):
                gr.Markdown("## 执行记录列表")
                
                # 执行记录列表表格
                execution_records_table = gr.Dataframe(
                    headers=["记录ID", "图名称", "开始时间", "结束时间", "执行时长(秒)", "状态", "错误信息"],
                    datatype=["str", "str", "str", "str", "number", "str", "str"],
                    interactive=False,
                    wrap=True
                )
                
                # 选中记录的详细信息
                with gr.Accordion("📖 执行详情", open=False):
                    selected_execution_info = gr.Markdown("请先选择一个执行记录")
                    
                    # 输入数据显示
                    with gr.Accordion("📥 输入数据", open=False):
                        execution_input_display = gr.JSON(
                            label="输入数据"
                        )
                    
                    # 输出结果显示
                    with gr.Accordion("📤 输出结果", open=False):
                        execution_output_display = gr.JSON(
                            label="输出结果"
                        )
                    
                    # 节点执行结果显示
                    with gr.Accordion("🔧 节点执行结果", open=False):
                        execution_nodes_display = gr.JSON(
                            label="节点执行结果"
                        )
                
                # 操作区域
                with gr.Row():
                    selected_execution_id = gr.Textbox(
                        label="选中的记录ID",
                        placeholder="点击表格行选择记录",
                        interactive=False
                    )
                    delete_execution_btn = gr.Button("🗑️ 删除记录", variant="stop")
                    view_execution_details_btn = gr.Button("👁️ 查看详情", variant="secondary")
        
        # 事件绑定
        search_execution_btn.click(
            fn=self._search_execution_records,
            inputs=[graph_name_filter, execution_status_filter, time_range_filter],
            outputs=[execution_records_table]
        )
        
        refresh_execution_btn.click(
            fn=self._load_all_execution_records,
            outputs=[execution_records_table]
        )
        
        execution_records_table.select(
            fn=self._on_execution_record_selected,
            outputs=[
                selected_execution_id, 
                selected_execution_info, 
                execution_input_display,
                execution_output_display,
                execution_nodes_display
            ]
        )
        
        view_execution_details_btn.click(
            fn=self._load_execution_record_details,
            inputs=[selected_execution_id],
            outputs=[
                execution_input_display,
                execution_output_display,
                execution_nodes_display
            ]
        )
        
        delete_execution_btn.click(
            fn=self._delete_execution_record,
            inputs=[selected_execution_id],
            outputs=[execution_records_table, selected_execution_info]
        )
        
        export_execution_btn.click(
            fn=self._export_execution_records,
            inputs=[graph_name_filter, execution_status_filter, time_range_filter],
            outputs=[gr.File()]
        )

    # 执行记录管理方法
    def _load_all_execution_records(self) -> pd.DataFrame:
        """加载所有执行记录"""
        try:
            from src.core.base import get_graph_recorder
            recorder = get_graph_recorder()
            
            # 获取最近的执行记录
            records = recorder.get_recent_executions(limit=100)
            
            data = []
            for record in records:
                data.append([
                    str(record['id']),
                    record['graph_name'],
                    record['start_time'][:19] if record['start_time'] else '',
                    record['end_time'][:19] if record['end_time'] else '',
                    record.get('duration_seconds', 0) or 0,
                    "成功" if record['success'] else "失败",
                    record.get('error_message', '') or ''
                ])
            
            return pd.DataFrame(data, columns=["记录ID", "图名称", "开始时间", "结束时间", "执行时长(秒)", "状态", "错误信息"])
            
        except Exception as e:
            logger.error(f"加载执行记录失败: {e}")
            return pd.DataFrame(columns=["记录ID", "图名称", "开始时间", "结束时间", "执行时长(秒)", "状态", "错误信息"])

    def _search_execution_records(self, graph_name_filter: str, status_filter: str, time_range_filter: str) -> pd.DataFrame:
        """搜索执行记录"""
        try:
            from src.core.base import get_graph_recorder
            import sqlite3
            from datetime import datetime, timedelta
            
            recorder = get_graph_recorder()
            
            # 构建查询条件
            where_conditions = []
            params = []
            
            if graph_name_filter.strip():
                where_conditions.append("graph_name LIKE ?")
                params.append(f"%{graph_name_filter.strip()}%")
            
            if status_filter != "全部":
                success_value = 1 if status_filter == "成功" else 0
                where_conditions.append("success = ?")
                params.append(success_value)
            
            # 时间范围处理
            if time_range_filter != "全部":
                now = datetime.now()
                if time_range_filter == "今天":
                    start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    where_conditions.append("start_time >= ?")
                    params.append(start_time.isoformat())
                elif time_range_filter == "本周":
                    start_time = now - timedelta(days=now.weekday())
                    start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
                    where_conditions.append("start_time >= ?")
                    params.append(start_time.isoformat())
                elif time_range_filter == "本月":
                    start_time = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    where_conditions.append("start_time >= ?")
                    params.append(start_time.isoformat())
            
            # 构建SQL查询
            query = "SELECT * FROM graph_executions"
            if where_conditions:
                query += " WHERE " + " AND ".join(where_conditions)
            query += " ORDER BY start_time DESC"
            
            # 限制结果数量
            if time_range_filter == "最近100条":
                query += " LIMIT 100"
            else:
                query += " LIMIT 500"  # 其他情况最多返回500条
            
            # 执行查询
            with sqlite3.connect(recorder.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, params)
                records = [dict(row) for row in cursor.fetchall()]
            
            data = []
            for record in records:
                data.append([
                    str(record['id']),
                    record['graph_name'],
                    record['start_time'][:19] if record['start_time'] else '',
                    record['end_time'][:19] if record['end_time'] else '',
                    record.get('duration_seconds', 0) or 0,
                    "成功" if record['success'] else "失败",
                    record.get('error_message', '') or ''
                ])
            
            return pd.DataFrame(data, columns=["记录ID", "图名称", "开始时间", "结束时间", "执行时长(秒)", "状态", "错误信息"])
            
        except Exception as e:
            logger.error(f"搜索执行记录失败: {e}")
            return pd.DataFrame(columns=["记录ID", "图名称", "开始时间", "结束时间", "执行时长(秒)", "状态", "错误信息"])

    def _on_execution_record_selected(self, evt: gr.SelectData) -> Tuple[str, str, Dict, Dict, List]:
        """处理执行记录选择事件"""
        try:
            if evt is None or evt.index is None:
                return "", "请先选择一个执行记录", {}, {}, []
            
            # 获取选中行的索引
            row_index = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
            
            # 重新获取数据以确保索引对应正确
            records_df = self._load_all_execution_records()
            
            if row_index >= len(records_df):
                return "", "选择的行索引超出范围", {}, {}, []
            
            # 获取记录ID
            record_id = records_df.iloc[row_index]['记录ID']
            
            # 从数据库获取完整记录信息
            from src.core.base import get_graph_recorder
            import sqlite3
            import json
            
            recorder = get_graph_recorder()
            
            with sqlite3.connect(recorder.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM graph_executions WHERE id = ?", (record_id,))
                record = cursor.fetchone()
            
            if not record:
                return "", "记录不存在", {}, {}, []
            
            # 构建详细信息显示
            record_info = f"""### 📖 执行记录详情

**记录ID**: {record['id']}
**图名称**: {record['graph_name']}
**开始时间**: {record['start_time']}
**结束时间**: {record['end_time']}
**执行时长**: {record.get('duration_seconds', 0):.2f} 秒
**执行状态**: {"✅ 成功" if record['success'] else "❌ 失败"}
**错误信息**: {record.get('error_message') or '无'}

**创建时间**: {record['created_at']}
"""
            
            # 解析JSON数据
            try:
                input_data = json.loads(record['input_data']) if record['input_data'] else {}
                output_result = json.loads(record['output_result']) if record['output_result'] else {}
                node_results = json.loads(record['node_results']) if record['node_results'] else []
            except json.JSONDecodeError as e:
                logger.error(f"解析JSON数据失败: {e}")
                input_data = {"error": "JSON解析失败"}
                output_result = {"error": "JSON解析失败"}
                node_results = [{"error": "JSON解析失败"}]
            
            return str(record_id), record_info, input_data, output_result, node_results
            
        except Exception as e:
            logger.error(f"选择执行记录失败: {e}")
            return "", f"处理记录选择失败: {str(e)}", {}, {}, []

    def _load_execution_record_details(self, record_id: str) -> Tuple[Dict, Dict, List]:
        """加载执行记录详细信息"""
        try:
            if not record_id:
                return {}, {}, []
            
            from src.core.base import get_graph_recorder
            import sqlite3
            import json
            
            recorder = get_graph_recorder()
            
            with sqlite3.connect(recorder.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM graph_executions WHERE id = ?", (record_id,))
                record = cursor.fetchone()
            
            if not record:
                return {"error": "记录不存在"}, {"error": "记录不存在"}, [{"error": "记录不存在"}]
            
            # 解析JSON数据
            try:
                input_data = json.loads(record['input_data']) if record['input_data'] else {}
                output_result = json.loads(record['output_result']) if record['output_result'] else {}
                node_results = json.loads(record['node_results']) if record['node_results'] else []
            except json.JSONDecodeError as e:
                logger.error(f"解析JSON数据失败: {e}")
                input_data = {"error": f"JSON解析失败: {str(e)}"}
                output_result = {"error": f"JSON解析失败: {str(e)}"}
                node_results = [{"error": f"JSON解析失败: {str(e)}"}]
            
            return input_data, output_result, node_results
            
        except Exception as e:
            logger.error(f"加载执行记录详情失败: {e}")
            return {"error": str(e)}, {"error": str(e)}, [{"error": str(e)}]

    def _delete_execution_record(self, record_id: str) -> Tuple[pd.DataFrame, str]:
        """删除执行记录"""
        try:
            if not record_id:
                return self._load_all_execution_records(), "请先选择要删除的记录"
            
            from src.core.base import get_graph_recorder
            import sqlite3
            
            recorder = get_graph_recorder()
            
            with sqlite3.connect(recorder.db_path) as conn:
                cursor = conn.execute("DELETE FROM graph_executions WHERE id = ?", (record_id,))
                conn.commit()
                
                if cursor.rowcount > 0:
                    return self._load_all_execution_records(), f"✅ 成功删除记录: {record_id}"
                else:
                    return self._load_all_execution_records(), f"❌ 记录不存在: {record_id}"
            
        except Exception as e:
            logger.error(f"删除执行记录失败: {e}")
            return self._load_all_execution_records(), f"❌ 删除记录异常: {str(e)}"

    def _export_execution_records(self, graph_name_filter: str, status_filter: str, time_range_filter: str) -> str:
        """导出执行记录到CSV文件"""
        try:
            import tempfile
            import os
            from datetime import datetime
            
            # 获取筛选后的执行记录数据
            records_df = self._search_execution_records(graph_name_filter, status_filter, time_range_filter)
            
            if records_df.empty:
                return "没有可导出的数据"
            
            # 创建临时文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"execution_records_export_{timestamp}.csv"
            
            # 使用工作空间输出目录
            output_dir = "./workspace/output"
            os.makedirs(output_dir, exist_ok=True)
            filepath = os.path.join(output_dir, filename)
            
            # 导出到CSV
            records_df.to_csv(filepath, index=False, encoding='utf-8-sig')
            
            logger.info(f"执行记录数据导出成功: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"导出执行记录数据失败: {e}")
            return f"导出失败: {str(e)}"


# 全局数据库界面实例 - 延迟初始化
database_interface = None

def get_database_interface():
    """获取数据库界面实例，延迟初始化"""
    global database_interface
    if database_interface is None:
        if DATABASE_AVAILABLE:
            database_interface = DatabaseInterface()
        else:
            # 创建一个空的占位符界面
            database_interface = gr.Markdown("❌ 数据库功能不可用（数据库连接失败）")
    return database_interface 