"""
数据库管理界面组件 - 提供剧情数据的查看、编辑、导出功能
"""

import gradio as gr
import json
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
import logging

# 确保数据库模块路径正确
import sys
import os

# 获取项目根目录路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database import story_manager, character_manager, database_manager

logger = logging.getLogger(__name__)

class DatabaseInterface:
    """数据库管理界面"""
    
    def __init__(self):
        self.story_manager = story_manager
        self.character_manager = character_manager
        self.database_manager = database_manager
    
    def create_interface(self) -> gr.Blocks:
        """创建数据库管理界面"""
        with gr.Blocks(title="数据库管理", theme=gr.themes.Soft()) as interface:
            gr.Markdown("# 📊 数据库管理中心")
            gr.Markdown("管理剧情数据、角色信息、查看统计信息和执行数据库操作")
            
            with gr.Tabs():
                # 剧情管理标签页
                with gr.Tab("📚 剧情管理"):
                    self._create_story_management_tab()
                
                # 角色管理标签页
                with gr.Tab("👥 角色管理"):
                    self._create_character_management_tab()
                
                # 数据库操作标签页
                with gr.Tab("🛠️ 数据库操作"):
                    self._create_database_operations_tab()
                
                # 统计信息标签页
                with gr.Tab("📈 统计信息"):
                    self._create_statistics_tab()
        
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
                    headers=["剧情ID", "剧情名称", "类型", "主角", "小节数", "角色", "创建时间"],
                    datatype=["str", "str", "str", "str", "number", "str", "str"],
                    interactive=False,
                    wrap=True
                )
                
                # 选中剧情的详细信息
                with gr.Accordion("📖 剧情详情", open=False):
                    selected_story_info = gr.Markdown("请先选择一个剧情")
                    
                    # 小节列表
                    scenes_table = gr.Dataframe(
                        headers=["小节ID", "标题", "内容预览", "地点", "角色"],
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
            inputs=[story_table],
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
            inputs=[character_table],
            outputs=[selected_character_name, selected_character_info]
        )
        
        view_character_stories_btn.click(
            fn=self._load_character_stories,
            inputs=[selected_character_name],
            outputs=[character_stories_table]
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
                    story['story_type'],
                    story['protagonist'],
                    story['scene_count'],
                    ', '.join(story['characters'][:3]) + ('...' if len(story['characters']) > 3 else ''),
                    story['created_at'][:19]  # 只显示到秒
                ])
            
            return pd.DataFrame(data, columns=["剧情ID", "剧情名称", "类型", "主角", "小节数", "角色", "创建时间"])
            
        except Exception as e:
            logger.error(f"加载剧情列表失败: {e}")
            return pd.DataFrame(columns=["剧情ID", "剧情名称", "类型", "主角", "小节数", "角色", "创建时间"])
    
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
                    story['story_type'],
                    story['protagonist'],
                    story['scene_count'],
                    ', '.join(story['characters'][:3]) + ('...' if len(story['characters']) > 3 else ''),
                    story['created_at'][:19]
                ])
            
            return pd.DataFrame(data, columns=["剧情ID", "剧情名称", "类型", "主角", "小节数", "角色", "创建时间"])
            
        except Exception as e:
            logger.error(f"搜索剧情失败: {e}")
            return pd.DataFrame(columns=["剧情ID", "剧情名称", "类型", "主角", "小节数", "角色", "创建时间"])
    
    def _on_story_selected(self, table_data) -> Tuple[str, str, pd.DataFrame]:
        """处理剧情选择事件"""
        try:
            if table_data is None or len(table_data) == 0:
                return "", "请先选择一个剧情", pd.DataFrame()
            
            # 获取选中行的剧情ID（第一列）
            story_id = table_data.iloc[0, 0] if len(table_data.iloc[0]) > 0 else ""
            
            if not story_id:
                return "", "无效的剧情ID", pd.DataFrame()
            
            # 获取剧情详细信息
            story_info = f"### 剧情详情\n\n**剧情ID**: {story_id}\n\n正在加载详细信息..."
            
            # 获取小节信息
            scenes = self.story_manager.get_story_scenes(story_id)
            scenes_data = []
            
            for scene in scenes:
                content_preview = scene['scene_content'][:50] + "..." if len(scene['scene_content']) > 50 else scene['scene_content']
                scenes_data.append([
                    scene['scene_id'],
                    scene['scene_title'],
                    content_preview,
                    scene['location'],
                    ', '.join(scene['participants'])
                ])
            
            scenes_df = pd.DataFrame(scenes_data, columns=["小节ID", "标题", "内容预览", "地点", "角色"])
            
            return story_id, story_info, scenes_df
            
        except Exception as e:
            logger.error(f"选择剧情失败: {e}")
            return "", f"处理剧情选择失败: {str(e)}", pd.DataFrame()
    
    def _load_story_scenes(self, story_id: str) -> pd.DataFrame:
        """加载剧情小节"""
        try:
            if not story_id:
                return pd.DataFrame(columns=["小节ID", "标题", "内容预览", "地点", "角色"])
            
            scenes = self.story_manager.get_story_scenes(story_id)
            data = []
            
            for scene in scenes:
                content_preview = scene['scene_content'][:100] + "..." if len(scene['scene_content']) > 100 else scene['scene_content']
                data.append([
                    scene['scene_id'],
                    scene['scene_title'],
                    content_preview,
                    scene['location'],
                    ', '.join(scene['participants'])
                ])
            
            return pd.DataFrame(data, columns=["小节ID", "标题", "内容预览", "地点", "角色"])
            
        except Exception as e:
            logger.error(f"加载小节失败: {e}")
            return pd.DataFrame(columns=["小节ID", "标题", "内容预览", "地点", "角色"])
    
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
                    pd.DataFrame(columns=["小节ID", "标题", "内容预览", "地点", "角色"])
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
    
    def _on_character_selected(self, table_data) -> Tuple[str, str]:
        """处理角色选择事件"""
        try:
            if table_data is None or len(table_data) == 0:
                return "", "请先选择一个角色"
            
            character_name = table_data.iloc[0, 0] if len(table_data.iloc[0]) > 0 else ""
            
            if not character_name:
                return "", "无效的角色名称"
            
            character_info = f"### 角色详情\n\n**角色名称**: {character_name}\n\n正在加载详细信息..."
            
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


# 全局数据库界面实例
database_interface = DatabaseInterface() 