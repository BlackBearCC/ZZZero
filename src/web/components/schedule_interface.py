"""日程生成界面 - 基于Gradio的日程生成工作流界面
包含日历选择、角色配置、剧情设置等功能
"""

import gradio as gr
import json
import asyncio
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple
import calendar
import holidays
from chinese_calendar import is_holiday, is_workday, get_holiday_detail
from gradio_calendar import Calendar

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from workflow.schedule_workflow import ScheduleWorkflow
from web.components.workflow_chat import WorkflowChat
from llm.base import LLMFactory
from core.types import LLMConfig

logger = logging.getLogger(__name__)

class ScheduleInterface:
    """日程生成界面管理器"""
    
    def __init__(self, llm_factory: LLMFactory):
        self.llm_factory = llm_factory
        self.schedule_workflow = None
        self.workflow_chat = None
        # 设置默认日期为今天开始的一周
        today = datetime.now().strftime('%Y-%m-%d')
        end_date = (datetime.now() + timedelta(days=6)).strftime('%Y-%m-%d')
        
        # 初始化中国节假日数据
        self.cn_holidays = holidays.CN()
        
        self.current_config = {
            'protagonist': '方知衡',
            'schedule_type': 'weekly',
            'start_date': today,
            'end_date': end_date,
            'total_days': 7,
            'selected_characters': [],
            'selected_locations': [],
            'selected_stories': [],
            'time_slots_config': {
                '夜间': {'start': '23:00', 'end': '06:00'},
                '上午': {'start': '06:00', 'end': '11:00'},
                '中午': {'start': '11:00', 'end': '14:00'},
                '下午': {'start': '14:00', 'end': '18:00'},
                '晚上': {'start': '18:00', 'end': '23:00'}
            },
            'character_distribution': 'balanced',
            'story_integration': 'moderate',
            'include_holidays': True,
            'include_lunar': True,
            'mood_variety': True,
            'location_variety': True
        }
        
        # 初始化工作流
        self._init_workflow()
    
    def _init_workflow(self):
        """初始化日程工作流"""
        try:
            # 创建LLM实例 - 使用doubao与故事工作流保持一致
            llm_config = LLMConfig(
                provider="doubao",
                api_key=os.getenv('DOUBAO_API_KEY', 'b633a622-b5d0-4f16-a8a9-616239cf15d1'),
                model_name=os.getenv('DOUBAO_MODEL_DEEPSEEKR1', 'ep-20250221154107-c4qc7'),  # 使用豆包的默认模型
                temperature=0.7,
                max_tokens=16384
            )
            llm = self.llm_factory.create(llm_config)
            
            # 创建工作流实例
            self.schedule_workflow = ScheduleWorkflow(llm=llm)
            
            # 创建工作流聊天界面
            self.workflow_chat = WorkflowChat(
                workflow_name="日程生成工作流",
                nodes=[
                    {"id": "generate", "name": "日程生成", "description": "生成完整日程安排，包含日期、角色和剧情"},
                    {"id": "save", "name": "数据保存", "description": "保存日程到数据库"}
                ]
            )
            
            logger.info("日程生成工作流初始化成功")
            
        except Exception as e:
            logger.error(f"日程生成工作流初始化失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def create_schedule_interface(self) -> Dict[str, Any]:
        """创建完整的日程生成界面"""
        with gr.Column():
            # 标题和描述
            gr.Markdown("## 📅 日程生成工作流")
            gr.Markdown("为主角方知衡生成详细的日程安排，包含角色互动和剧情整合")
            
            # 日历导航控制区域
            with gr.Row():
                with gr.Column(scale=1):
                    month_selector = gr.Dropdown(
                        label="月份导航",
                        choices=self._get_month_options(),
                        value=f"{datetime.now().year}-{datetime.now().month:02d}",
                        info="选择要查看的月份"
                    )
                with gr.Column(scale=1):
                    date_range_preset = gr.Dropdown(
                        label="快捷日期范围",
                        choices=[
                            "未来一周", "未来两周", "未来一个月", 
                            "当前月份", "下个月", "未来三个月"
                        ],
                        value="未来一周",
                        info="选择预定义的日期范围"
                    )
            
            with gr.Row(equal_height=True):
                # 左侧配置面板 - 固定高度并添加滚动条
                with gr.Column(scale=1, min_width=400, elem_id="config_panel_container", elem_classes=["config-panel-scroll"]):
                    # 使用固定高度容器确保与右侧一致
                    config_components = self._create_config_panel()
                
                # 右侧工作流聊天界面 - 与Agent窗口相同高度
                with gr.Column(scale=2, min_width=600):
                    # 检查workflow_chat是否正确初始化
                    if self.workflow_chat is None:
                        # 如果为空，重新创建一个实例
                        self.workflow_chat = WorkflowChat(
                            workflow_name="日程生成工作流",
                            nodes=[
                                {"id": "generate", "name": "日程生成", "description": "生成完整日程安排，包含日期、角色和剧情"},
                                {"id": "save", "name": "数据保存", "description": "保存日程到数据库"}
                            ]
                        )
                        logger.info("在界面创建过程中重新初始化了WorkflowChat")
                    
                    workflow_components = self.workflow_chat.create_workflow_chat_interface()
            
            # 底部结果展示
            result_components = self._create_result_panel()
        
        # 合并所有组件
        all_components = {**config_components, **workflow_components, **result_components}
        
        # 绑定月份导航事件 - 确保输出只更新日历显示
        month_selector.change(
            fn=self._update_calendar_by_month,
            inputs=[month_selector],
            outputs=[config_components['calendar_display']]
        )
        
        # 绑定日期范围预设事件 - 修复输出顺序，确保类型匹配
        date_range_preset.change(
            fn=self._update_date_range_by_preset,
            inputs=[date_range_preset],
            outputs=[
                config_components['start_date'], 
                config_components['end_date'],
                config_components['total_days'],
                config_components['calendar_display']
            ]
        )
        
        # 传递组件列表给绑定函数
        components_list = [
            config_components['start_date'],
            config_components['end_date'],
            config_components['total_days'],
            config_components['calendar_display'],
            config_components['schedule_type'],
            config_components['selected_characters'],
            config_components['selected_locations'],
            config_components['selected_stories'],
            config_components['character_distribution'],
            config_components['story_integration'],
            config_components['include_holidays'],
            config_components['include_lunar'],
            config_components['location_variety'],
            config_components.get('mood_variety', gr.Checkbox(value=True)),
            config_components.get('time_slots_config', {}),
            config_components.get('date_picker_start'),
            config_components.get('date_picker_end'),
            config_components['generate_btn']
        ]
        
        # 绑定事件
        self._bind_config_events(*components_list)
        
        return all_components
    
    def _create_config_panel(self) -> Dict[str, Any]:
        """创建配置面板"""
        components = {}
        
        # 创建固定高度的滚动容器
        with gr.Column():
            gr.Markdown("## ⚙️ 日程配置")
            
            # 基础配置
            with gr.Group():
                gr.Markdown("### 📋 基础设置")
                
                # 主角显示（固定）
                components['protagonist_display'] = gr.Textbox(
                    label="主角",
                    value="方知衡",
                    interactive=False,
                    info="大学天文系教授、研究员"
                )
                
                # 日程类型
                components['schedule_type'] = gr.Radio(
                    label="日程类型",
                    choices=["weekly", "daily", "monthly"],
                    value="weekly",
                    info="选择生成的日程类型"
                )
                
                # 日期选择 - 更新为日期选择器
                with gr.Row():
                    components['start_date'] = gr.Dropdown(
                        label="开始日期",
                        choices=self._get_date_options(),
                        value=self.current_config['start_date'],
                        info="选择开始日期",
                        interactive=True
                    )
                    components['end_date'] = gr.Dropdown(
                        label="结束日期",
                        choices=self._get_date_options(days_forward=30),
                        value=self.current_config['end_date'],
                        info="选择结束日期",
                        interactive=True
                    )
                
                # 使用日期选择器组件
                with gr.Row():
                    components['date_picker_start'] = Calendar(
                        label="选择开始日期",
                        value=datetime.now().strftime('%Y-%m-%d'),  # 转换为字符串格式
                        info="点击选择开始日期",
                        type="string"  # 使用字符串类型
                    )
                    components['date_picker_end'] = Calendar(
                        label="选择结束日期",
                        value=(datetime.now() + timedelta(days=6)).strftime('%Y-%m-%d'),  # 转换为字符串格式
                        info="点击选择结束日期",
                        type="string"  # 使用字符串类型
                    )
                
                # 总天数（自动计算）
                components['total_days'] = gr.Number(
                    label="总天数",
                    value=7,
                    minimum=1,
                    maximum=366,  # 支持最多一年的日程规划
                    info="根据日期范围自动计算，最多支持366天"
                )
            
            # 日历配置
            with gr.Group():
                gr.Markdown("### 📅 日历设置")
                
                components['include_holidays'] = gr.Checkbox(
                    label="包含节假日",
                    value=True,
                    info="在日程中标记和考虑节假日"
                )
                
                components['include_lunar'] = gr.Checkbox(
                    label="包含农历",
                    value=True,
                    info="显示农历日期信息"
                )
                
                # 简化的日历显示
                components['calendar_display'] = gr.HTML(
                    value=self._generate_calendar_html(),
                    label="日历预览"
                )
            
            # 角色选择
            with gr.Group():
                gr.Markdown("### 👥 角色配置")
                
                # 获取角色列表
                characters_list = self._get_characters_options()
                components['selected_characters'] = gr.CheckboxGroup(
                    label="选择参与角色",
                    choices=characters_list,
                    value=[characters_list[0]] if characters_list else [],  # 默认选中第一个角色
                    info="选择将在日程中出现的角色"
                )
                
                components['character_distribution'] = gr.Radio(
                    label="角色分配策略",
                    choices=[
                        ("平衡分配", "balanced"),
                        ("随机分配", "random"),
                        ("加权分配", "weighted")
                    ],
                    value="balanced",
                    info="决定角色在时间段中的分配方式"
                )
            
            # 地点选择
            with gr.Group():
                gr.Markdown("### 🏢 地点配置")
                
                # 获取地点列表
                locations_list = self._get_locations_options()
                components['selected_locations'] = gr.CheckboxGroup(
                    label="选择活动地点",
                    choices=locations_list,
                    value=[locations_list[0]] if locations_list else [],  # 默认选中第一个地点
                    info="选择日程中的活动场所"
                )
                
                components['location_variety'] = gr.Checkbox(
                    label="地点多样性",
                    value=True,
                    info="确保不同时间段使用不同地点"
                )
            
            # 剧情配置
            with gr.Group():
                gr.Markdown("### 📚 剧情设置")
                
                # 获取剧情列表
                stories_list = self._get_stories_options()
                components['selected_stories'] = gr.CheckboxGroup(
                    label="选择剧情内容",
                    choices=stories_list,
                    value=[],
                    info="选择要整合到日程中的剧情"
                )
                
                components['story_integration'] = gr.Radio(
                    label="剧情整合程度",
                    choices=[
                        ("最少整合", "minimal"),
                        ("适度整合", "moderate"),
                        ("深度整合", "intensive")
                    ],
                    value="moderate",
                    info="决定剧情在日程中的分布密度"
                )
            
            # 高级设置
            with gr.Group():
                gr.Markdown("### 🔧 高级设置")
                
                components['mood_variety'] = gr.Checkbox(
                    label="情感多样性",
                    value=True,
                    info="确保不同时间段有不同的情感基调"
                )
                
                # 时间段配置
                with gr.Accordion("时间段设置", open=False):
                    components['time_slots_config'] = gr.JSON(
                        label="时间段配置",
                        value=self.current_config['time_slots_config']
                    )
            
            # 生成按钮 - 设置为明显的主要动作按钮
            with gr.Row():
                components['generate_btn'] = gr.Button(
                    "🚀 启动工作流",
                    variant="primary",
                    size="lg",
                    scale=2,  # 加大按钮
                    min_width=300  # 最小宽度确保足够明显
                )
        
        return components
    
    def _create_result_panel(self) -> Dict[str, Any]:
        """创建结果展示面板"""
        components = {}
        
        with gr.Column():
            gr.Markdown("## 📊 生成结果")
            
            with gr.Tabs():
                # 日程概览
                with gr.Tab("📅 日程概览"):
                    components['schedule_overview'] = gr.HTML(
                        value="<p>请先生成日程</p>",
                        label="日程总览"
                    )
                
                # 详细日程
                with gr.Tab("📝 详细日程"):
                    components['detailed_schedule'] = gr.JSON(
                        label="详细日程数据",
                        value={}
                    )
                
                # 统计信息
                with gr.Tab("📈 统计信息"):
                    components['statistics'] = gr.HTML(
                        value="<p>请先生成日程</p>",
                        label="统计数据"
                    )
                
                # 导出选项
                with gr.Tab("💾 导出选项"):
                    with gr.Row():
                        components['export_json_btn'] = gr.Button("导出JSON")
                        components['export_csv_btn'] = gr.Button("导出CSV")
                        components['export_calendar_btn'] = gr.Button("导出日历")
                    
                    components['export_result'] = gr.File(
                        label="导出文件",
                        visible=False
                    )
        
        return components
    
    def _get_characters_options(self) -> List[str]:
        """获取角色选项列表"""
        try:
            if self.schedule_workflow:
                characters = self.schedule_workflow.get_characters_list()
                return [f"{char['name']} - {char['description'][:50]}..." for char in characters]
            return []
        except Exception as e:
            logger.error(f"获取角色列表失败: {e}")
            return []
    
    def _get_locations_options(self) -> List[str]:
        """获取地点选项列表"""
        try:
            if self.schedule_workflow:
                locations = self.schedule_workflow.get_locations_list()
                return [f"{loc['name']} ({loc['district']})" for loc in locations]
            return []
        except Exception as e:
            logger.error(f"获取地点列表失败: {e}")
            return []
    
    def _get_stories_options(self) -> List[str]:
        """获取剧情选项列表"""
        try:
            if self.schedule_workflow:
                stories = self.schedule_workflow.get_stories_list()
                return [f"{story['story_name']} - {story['story_type']}" for story in stories]
            return []
        except Exception as e:
            logger.error(f"获取剧情列表失败: {e}")
            return []
    
    def _generate_calendar_html(self, year: int = None, month: int = None) -> str:
        """生成日历HTML"""
        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month
        
        # 生成增强的日历HTML
        cal = calendar.monthcalendar(year, month)
        month_name = calendar.month_name[month]
        
        html = f"""
        <div style="text-align: center; font-family: Arial, sans-serif; max-width: 100%; overflow-x: auto;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 10px; align-items: center;">
                <button onclick="prevMonth()" style="padding: 5px 10px; cursor: pointer;">◀</button>
            <h3>{year}年 {month_name}</h3>
                <button onclick="nextMonth()" style="padding: 5px 10px; cursor: pointer;">▶</button>
            </div>
            <table style="margin: 0 auto; border-collapse: collapse; width: 100%;">
                <tr style="background-color: #f0f0f0;">
                    <th style="padding: 8px; border: 1px solid #ddd; width: 14%;">周一</th>
                    <th style="padding: 8px; border: 1px solid #ddd; width: 14%;">周二</th>
                    <th style="padding: 8px; border: 1px solid #ddd; width: 14%;">周三</th>
                    <th style="padding: 8px; border: 1px solid #ddd; width: 14%;">周四</th>
                    <th style="padding: 8px; border: 1px solid #ddd; width: 14%;">周五</th>
                    <th style="padding: 8px; border: 1px solid #ddd; width: 14%;">周六</th>
                    <th style="padding: 8px; border: 1px solid #ddd; width: 14%;">周日</th>
                </tr>
        """
        
        for week in cal:
            html += "<tr>"
            for day in week:
                if day == 0:
                    html += '<td style="padding: 8px; border: 1px solid #ddd;"></td>'
                else:
                    # 检查是否为节假日或周末
                    date_str = f"{year:04d}-{month:02d}-{day:02d}"
                    date_obj = date(year, month, day)
                    is_weekend = date_obj.weekday() >= 5  # 5代表周六，6代表周日
                    
                    # 检查各种节假日
                    is_cn_holiday = date_str in self.cn_holidays
                    is_official_holiday = False
                    holiday_name = ""
                    
                    try:
                        is_official_holiday = is_holiday(date_obj)
                        if is_official_holiday:
                            holiday_detail = get_holiday_detail(date_obj)
                            holiday_name = holiday_detail[1]
                    except:
                        pass
                    
                    style = "padding: 8px; border: 1px solid #ddd; position: relative;"
                    holiday_badge = ""
                    
                    # 应用样式
                    if is_official_holiday or is_cn_holiday:
                        style += " background-color: #ffcccc; color: red;"
                        if holiday_name or is_cn_holiday:
                            holiday_text = holiday_name or (self.cn_holidays.get(date_str) if is_cn_holiday else "假日")
                            holiday_badge = f'<div style="font-size: 9px; color: red; position: absolute; bottom: 2px; right: 2px;">{holiday_text}</div>'
                    elif is_weekend:
                        style += " background-color: #e6f7ff; color: blue;"
                    
                    # 当前日期高亮
                    if date_obj == datetime.now().date():
                        style += " border: 2px solid #4CAF50; font-weight: bold;"
                    
                    html += f'<td style="{style}" data-date="{date_str}">{day}{holiday_badge}</td>'
            html += "</tr>"
        
        # 添加JavaScript交互
        html += """
            </table>
            <script>
                function prevMonth() {
                    // 添加月份导航功能
                    console.log("上一月");
                }
                
                function nextMonth() {
                    // 添加月份导航功能
                    console.log("下一月");
                }
                
                // 点击日期选择
                document.querySelectorAll('td[data-date]').forEach(cell => {
                    cell.style.cursor = 'pointer';
                    cell.addEventListener('click', function() {
                        let selectedDate = this.getAttribute('data-date');
                        console.log("选择日期:", selectedDate);
                        // 可以通过Gradio的JS事件机制传递到Python
                    });
                });
            </script>
        </div>
        """
        
        return html
    
    def _check_holiday(self, date_str: str) -> bool:
        """检查是否为节假日"""
        try:
            # 检查内置节假日库
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            return date_str in self.cn_holidays or is_holiday(date_obj) or date_obj.weekday() >= 5
        except:
            # 回退到工作流内的节假日数据
            if self.schedule_workflow:
                holidays = self.schedule_workflow.holidays_data
                return date_str in holidays
            return False
    
    def _bind_config_events(self, *components):
        """绑定配置面板事件"""
        start_date, end_date, total_days, calendar_display, schedule_type = components[:5]
        date_picker_start = components[-3] if len(components) > 17 else None
        date_picker_end = components[-2] if len(components) > 17 else None
        generate_btn = components[-1]
        
        # 日期变化时自动计算天数
        def calculate_days(start, end):
            try:
                if start and end:
                    start_dt = datetime.strptime(start, '%Y-%m-%d')
                    end_dt = datetime.strptime(end, '%Y-%m-%d')
                    days = (end_dt - start_dt).days + 1
                    return max(1, days)
                return 7
            except:
                return 7
        
        def update_calendar(start, end):
            try:
                if start:
                    start_dt = datetime.strptime(start, '%Y-%m-%d')
                    return self._generate_calendar_html(start_dt.year, start_dt.month)
                return self._generate_calendar_html()
            except:
                return self._generate_calendar_html()
        
        # 绑定日期计算
        start_date.change(
            fn=lambda s, e: [calculate_days(s, e), update_calendar(s, e)],
            inputs=[start_date, end_date],
            outputs=[total_days, calendar_display]
        )
        
        end_date.change(
            fn=lambda s, e: [calculate_days(s, e), update_calendar(s, e)],
            inputs=[start_date, end_date],
            outputs=[total_days, calendar_display]
        )
        
        # 绑定日期选择器事件 - 修复输出，仅更新对应的值
        if date_picker_start:
            date_picker_start.change(
                fn=lambda d: d,  # 简单传递值
                inputs=[date_picker_start],
                outputs=[start_date]
            )
        
        if date_picker_end:
            date_picker_end.change(
                fn=lambda d: d,  # 简单传递值
                inputs=[date_picker_end],
                outputs=[end_date]
            )
        
        # 当开始或结束日期更新时，更新天数并重新加载日历
        def update_total_days_and_calendar(start_val, end_val):
            try:
                days = calculate_days(start_val, end_val)
                cal_html = update_calendar(start_val, end_val)
                return days, cal_html
            except Exception as e:
                logger.warning(f"计算天数或更新日历失败: {e}")
                return total_days.value, calendar_display.value
                
        # 绑定开始日期变化
        start_date.change(
            fn=update_total_days_and_calendar,
            inputs=[start_date, end_date],
            outputs=[total_days, calendar_display]
        )
        
        # 绑定结束日期变化
        end_date.change(
            fn=update_total_days_and_calendar,
            inputs=[start_date, end_date],
            outputs=[total_days, calendar_display]
        )
        
        # 绑定生成按钮 - 确保只传递必要的组件并设置api_name以便更好地追踪
        generate_btn.click(
            fn=self._start_schedule_generation,
            inputs=components[:15],  # 仅传递前15个组件，跳过日期选择器和生成按钮
            outputs=[],
            api_name="start_schedule_generation"
        )
    
    async def _start_schedule_generation(self, *args):
        """开始日程生成"""
        try:
            # 解析参数
            config = self._parse_generation_config(*args)
            
            # 验证配置
            if not self._validate_config(config):
                return
            
            # 设置工作流的LLM（确保使用应用的LLM实例）
            if hasattr(self, 'app') and hasattr(self.app, 'llm') and self.app.llm:
                self.schedule_workflow.llm = self.app.llm
            
            # 执行工作流 - 确保正确使用async for处理异步生成器
            if self.schedule_workflow and self.workflow_chat:
                async for progress_update in self.schedule_workflow.execute_workflow_stream(
                    config, self.workflow_chat
                ):
                    # 这里只需要迭代，不需要额外操作
                    # 每次迭代会通过yield返回更新后的UI状态
                    pass
            
        except Exception as e:
            logger.error(f"日程生成失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # 添加错误消息到工作流聊天
            if self.workflow_chat:
                await self.workflow_chat.add_node_message(
                    "系统",
                    f"日程生成失败: {str(e)}",
                    "error"
                )
    
    def _parse_generation_config(self, *args) -> Dict[str, Any]:
        """解析生成配置"""
        config = self.current_config.copy()
        
        # 根据_bind_config_events中的参数顺序解析
        if len(args) >= 15:
            config.update({
                'start_date': args[0] if args[0] else '',
                'end_date': args[1] if args[1] else '',
                'total_days': args[2] if args[2] else 7,
                # args[3] 是 calendar_display，跳过
                'schedule_type': args[4] if args[4] else 'weekly',
                'selected_characters': args[5] if args[5] else [],
                'selected_locations': args[6] if args[6] else [],
                'selected_stories': args[7] if args[7] else [],
                'character_distribution': args[8] if args[8] else 'balanced',
                'story_integration': args[9] if args[9] else 'moderate',
                'include_holidays': args[10] if args[10] is not None else True,
                'include_lunar': args[11] if args[11] is not None else True,
                'mood_variety': args[12] if args[12] is not None else True,
                'location_variety': args[13] if args[13] is not None else True,
                'time_slots_config': args[14] if args[14] else self.current_config['time_slots_config']
            })
        
        return config
    
    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """验证配置"""
        required_fields = ['start_date', 'end_date', 'selected_characters']
        
        for field in required_fields:
            value = config.get(field)
            if not value or (isinstance(value, str) and not value.strip()):
                logger.warning(f"配置验证失败：缺少{field}，当前值: {repr(value)}")
                return False
        
        # 额外验证日期格式
        try:
            start_date = config.get('start_date', '').strip()
            end_date = config.get('end_date', '').strip()
            if start_date and end_date:
                from datetime import datetime
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                if start_dt > end_dt:
                    logger.warning("配置验证失败：开始日期不能晚于结束日期")
                    return False
        except ValueError as e:
            logger.warning(f"配置验证失败：日期格式错误 - {e}")
            return False
        
        return True
    
    def get_interface(self) -> Dict[str, Any]:
        """获取界面实例"""
        return self.create_schedule_interface()

    def _get_date_options(self, days_backward=7, days_forward=30) -> List[str]:
        """生成日期选项列表"""
        today = datetime.now().date()
        dates = []
        
        # 生成过去的日期
        for i in range(days_backward, 0, -1):
            past_date = today - timedelta(days=i)
            dates.append(past_date.strftime('%Y-%m-%d'))
        
        # 添加今天
        dates.append(today.strftime('%Y-%m-%d'))
        
        # 生成未来的日期
        for i in range(1, days_forward + 1):
            future_date = today + timedelta(days=i)
            dates.append(future_date.strftime('%Y-%m-%d'))
            
        return dates

    def _update_calendar_by_month(self, month_value: str) -> str:
        """根据选择的月份更新日历显示"""
        try:
            if month_value:
                year, month = map(int, month_value.split('-'))
                return self._generate_calendar_html(year, month)
            return self._generate_calendar_html()
        except:
            return self._generate_calendar_html()
    
    def _update_date_range_by_preset(self, preset: str):
        """根据预设更新日期范围"""
        today = datetime.now().date()
        start_date = today
        
        if preset == "未来一周":
            end_date = today + timedelta(days=6)
        elif preset == "未来两周":
            end_date = today + timedelta(days=13)
        elif preset == "未来一个月":
            end_date = today + timedelta(days=29)
        elif preset == "当前月份":
            # 当月最后一天
            last_day = calendar.monthrange(today.year, today.month)[1]
            end_date = date(today.year, today.month, last_day)
        elif preset == "下个月":
            # 下月第一天
            if today.month == 12:
                start_date = date(today.year + 1, 1, 1)
                end_date = date(today.year + 1, 1, calendar.monthrange(today.year + 1, 1)[1])
            else:
                start_date = date(today.year, today.month + 1, 1)
                end_date = date(today.year, today.month + 1, calendar.monthrange(today.year, today.month + 1)[1])
        elif preset == "未来三个月":
            if today.month <= 9:
                end_date = date(today.year, today.month + 3, today.day)
            else:
                # 跨年处理
                new_month = (today.month + 3) % 12
                if new_month == 0:
                    new_month = 12
                end_year = today.year + 1 if today.month > 9 else today.year
                # 确保日期有效（比如1月31日在4月可能无效）
                last_day = min(today.day, calendar.monthrange(end_year, new_month)[1])
                end_date = date(end_year, new_month, last_day)
        else:
            # 默认未来一周
            end_date = today + timedelta(days=6)
        
        # 计算天数
        total_days = (end_date - start_date).days + 1
        
        # 生成日历
        calendar_html = self._generate_calendar_html(start_date.year, start_date.month)
        
        # 格式化日期字符串
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        # 仅返回四个值：开始日期、结束日期、总天数、日历HTML
        # 确保顺序与outputs参数匹配
        return start_date_str, end_date_str, total_days, calendar_html
    
    def _get_month_options(self) -> List[str]:
        """生成月份选项列表"""
        today = datetime.now()
        months = []
        
        # 生成过去6个月
        for i in range(6, 0, -1):
            past_month = today.month - i
            past_year = today.year
            if past_month <= 0:
                past_month += 12
                past_year -= 1
            months.append(f"{past_year}-{past_month:02d}")
        
        # 当前月
        months.append(f"{today.year}-{today.month:02d}")
        
        # 未来12个月
        for i in range(1, 13):
            future_month = today.month + i
            future_year = today.year
            if future_month > 12:
                future_month -= 12
                future_year += 1
            months.append(f"{future_year}-{future_month:02d}")
        
        return months

# 工厂函数
def create_schedule_interface(llm_factory: LLMFactory) -> ScheduleInterface:
    """创建日程生成界面实例"""
    return ScheduleInterface(llm_factory)