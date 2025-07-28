"""
角色资料生成工作流界面组件
"""

import gradio as gr
import asyncio
import json
import logging
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime
from pathlib import Path

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from workflow.character_profile_workflow import CharacterProfileWorkflow
from tools.knowledge_base_manager import GlobalKnowledgeBase
from core.types import LLMConfig

logger = logging.getLogger(__name__)

class CharacterProfileInterface:
    """角色资料生成工作流界面"""
    
    def __init__(self):
        self.workflow = CharacterProfileWorkflow()
        self.knowledge_base = GlobalKnowledgeBase("./workspace")
        
        # 缓存数据
        self.available_categories = []
        self.available_collections = []
        self._load_categories()
        self._load_collections()
    
    def _load_categories(self):
        """加载可用的资料类别"""
        try:
            self.available_categories = self.workflow.get_available_categories()
            logger.info(f"已加载{len(self.available_categories)}个资料类别")
        except Exception as e:
            logger.error(f"加载资料类别失败: {e}")
            self.available_categories = []
    
    def _load_collections(self):
        """加载可用的知识集合"""
        try:
            self.available_collections = self.workflow.get_available_collections()
            logger.info(f"已加载{len(self.available_collections)}个知识集合")
        except Exception as e:
            logger.error(f"加载知识集合失败: {e}")
            self.available_collections = []
    
    def create_character_profile_interface(self) -> Dict[str, Any]:
        """创建完整的角色资料生成界面"""
        components = {}
        
        with gr.Column():
            # 标题和描述
            gr.Markdown("## 🎭 角色资料生成工作流")
            gr.Markdown("基于人物资料需求表格，结合向量知识库，生成详细的角色背景资料")
            
            with gr.Row(equal_height=True):
                # 左侧配置面板
                with gr.Column(scale=1, min_width=400):
                    config_components = self._create_config_panel()
                    components.update(config_components)
                
                # 右侧生成结果面板
                with gr.Column(scale=2, min_width=600):
                    result_components = self._create_result_panel()
                    components.update(result_components)
            
            # 底部批量处理面板
            batch_components = self._create_batch_panel()
            components.update(batch_components)
        
        # 绑定事件
        self._bind_events(components)
        
        return components
    
    def _create_config_panel(self) -> Dict[str, Any]:
        """创建配置面板"""
        components = {}
        
        with gr.Column():
            gr.Markdown("### ⚙️ 生成配置")
            
            # 历史记录选择
            with gr.Group():
                gr.Markdown("#### 📚 历史记录")
                components['history_dropdown'] = gr.Dropdown(
                    label="选择历史记录",
                    choices=self._get_history_choices(),
                    value=None,
                    interactive=True,
                    info="选择之前的角色配置"
                )
                
                with gr.Row():
                    components['load_history'] = gr.Button(
                        "载入选中记录",
                        size="sm",
                        variant="secondary"
                    )
                    
                    components['refresh_history'] = gr.Button(
                        "刷新历史",
                        size="sm",
                        variant="secondary"
                    )
            
            # 角色基本信息
            with gr.Group():
                gr.Markdown("#### 角色信息")
                components['character_name'] = gr.Textbox(
                    label="角色名称",
                    placeholder="请输入角色名称...",
                    value=""
                )
                
                components['basic_info'] = gr.Textbox(
                    label="基础人设",
                    placeholder="请输入角色的基础人设信息...",
                    lines=6,
                    value=""
                )
            
            # 类别选择
            with gr.Group():
                gr.Markdown("#### 生成类别")
                components['category_selector'] = gr.CheckboxGroup(
                    label="选择要生成的资料类别",
                    choices=self.available_categories,
                    value=self.available_categories[:3] if self.available_categories else [],
                    interactive=True
                )
                
                components['select_all_categories'] = gr.Button(
                    "全选类别",
                    size="sm",
                    variant="secondary"
                )
            
            # 知识库选择
            with gr.Group():
                gr.Markdown("#### 知识库选择")
                components['knowledge_selector'] = gr.CheckboxGroup(
                    label="选择启用的知识集合",
                    choices=self.available_collections,
                    value=[],
                    interactive=True,
                    info="选中的知识库将在生成时提供参考信息"
                )
                
                components['refresh_collections'] = gr.Button(
                    "刷新知识库",
                    size="sm",
                    variant="secondary"
                )
            
            # LLM配置
            with gr.Group():
                gr.Markdown("#### LLM配置")
                components['llm_provider'] = gr.Dropdown(
                    label="LLM提供商",
                    choices=["doubao", "openai"],
                    value="doubao",
                    interactive=True
                )
                
                components['model_name'] = gr.Textbox(
                    label="模型名称",
                    value="ep-20250221154410-vh78x",
                    interactive=True
                )
                
                components['temperature'] = gr.Slider(
                    label="Temperature",
                    minimum=0.0,
                    maximum=2.0,
                    value=0.7,
                    step=0.1,
                    interactive=True
                )
                
                components['max_tokens'] = gr.Number(
                    label="最大Token数",
                    value=2000,
                    minimum=100,
                    maximum=8000,
                    interactive=True
                )
            
            # 生成按钮
            components['generate_button'] = gr.Button(
                "🚀 开始生成",
                variant="primary",
                size="lg"
            )
        
        return components
    
    def _create_result_panel(self) -> Dict[str, Any]:
        """创建结果展示面板"""
        components = {}
        
        with gr.Column():
            gr.Markdown("### 📋 生成结果")
            
            # 状态显示
            components['status_display'] = gr.Markdown(
                "**状态:** 等待生成...",
                visible=True
            )
            
            # 进度条（将在需要时使用）
            # components['progress_bar'] = gr.Progress()  # Progress组件不支持visible参数
            
            # 结果展示区域
            with gr.Tabs() as tabs:
                with gr.Tab("📊 结果概览"):
                    components['result_summary'] = gr.Markdown(
                        "暂无生成结果",
                        visible=True
                    )
                
                with gr.Tab("📄 详细内容"):
                    components['result_detail'] = gr.JSON(
                        label="生成的角色资料",
                        value={},
                        visible=True
                    )
                
                with gr.Tab("💾 文件下载"):
                    components['download_file'] = gr.File(
                        label="下载生成的角色资料文件",
                        visible=False
                    )
                    
                    components['file_path_display'] = gr.Textbox(
                        label="文件保存路径",
                        interactive=False,
                        visible=False
                    )
        
        return components
    
    def _create_batch_panel(self) -> Dict[str, Any]:
        """创建批量处理面板"""
        components = {}
        
        with gr.Accordion("🔄 批量处理", open=False):
            gr.Markdown("批量生成多个角色的资料")
            
            with gr.Row():
                with gr.Column(scale=2):
                    components['batch_input'] = gr.Textbox(
                        label="批量角色信息 (JSON格式)",
                        placeholder="""示例格式：
[
    {
        "character_name": "角色1",
        "basic_info": "角色1的基础信息...",
        "selected_categories": ["基本信息", "外貌特征"]
    },
    {
        "character_name": "角色2", 
        "basic_info": "角色2的基础信息..."
    }
]""",
                        lines=8,
                        interactive=True
                    )
                
                with gr.Column(scale=1):
                    components['batch_example'] = gr.Button(
                        "加载示例",
                        variant="secondary"
                    )
                    
                    components['batch_generate'] = gr.Button(
                        "🚀 批量生成",
                        variant="primary"
                    )
            
            # 批量结果展示
            components['batch_results'] = gr.Dataframe(
                label="批量生成结果",
                headers=["角色名称", "生成状态", "文件路径", "错误信息"],
                datatype=["str", "str", "str", "str"],
                interactive=False,
                visible=False
            )
        
        return components
    
    def _bind_events(self, components: Dict[str, Any]):
        """绑定界面事件"""
        
        # 刷新历史记录按钮
        components['refresh_history'].click(
            fn=self._refresh_history,
            outputs=components['history_dropdown']
        )
        
        # 载入历史记录按钮
        components['load_history'].click(
            fn=self._load_history_record,
            inputs=components['history_dropdown'],
            outputs=[
                components['character_name'],
                components['basic_info'],
                components['category_selector'],
                components['knowledge_selector']
            ]
        )
        
        # 全选类别按钮
        components['select_all_categories'].click(
            fn=lambda: gr.update(value=self.available_categories),
            outputs=components['category_selector']
        )
        
        # 刷新知识库按钮
        components['refresh_collections'].click(
            fn=self._refresh_collections,
            outputs=components['knowledge_selector']
        )
        
        # 生成按钮
        components['generate_button'].click(
            fn=self._generate_character_profile,
            inputs=[
                components['character_name'],
                components['basic_info'],
                components['category_selector'],
                components['knowledge_selector'],
                components['llm_provider'],
                components['model_name'],
                components['temperature'],
                components['max_tokens']
            ],
            outputs=[
                components['status_display'],
                components['result_summary'],
                components['result_detail'],
                components['download_file'],
                components['file_path_display']
            ]
        )
        
        # 批量示例按钮
        components['batch_example'].click(
            fn=self._load_batch_example,
            outputs=components['batch_input']
        )
        
        # 批量生成按钮
        components['batch_generate'].click(
            fn=self._batch_generate_profiles,
            inputs=[
                components['batch_input'],
                components['knowledge_selector'],
                components['llm_provider'],
                components['model_name'],
                components['temperature'],
                components['max_tokens']
            ],
            outputs=[
                components['batch_results'],
                components['status_display']
            ]
        )
    
    def _get_history_choices(self) -> List[str]:
        """获取历史记录选择项"""
        try:
            history_records = self.workflow.get_history_records()
            choices = []
            for i, record in enumerate(reversed(history_records)):  # 最新的在前
                character_name = record.get('character_name', '未知角色')[:20]
                created_at = record.get('created_at', '')
                if created_at:
                    try:
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        time_str = dt.strftime('%m-%d %H:%M')
                    except:
                        time_str = created_at[:16]
                else:
                    time_str = '未知时间'
                
                choice = f"{character_name} ({time_str})"
                choices.append(choice)
            
            return choices
        except Exception as e:
            logger.error(f"获取历史记录选择项失败: {e}")
            return []
    
    def _refresh_history(self):
        """刷新历史记录下拉列表"""
        try:
            choices = self._get_history_choices()
            return gr.update(choices=choices, value=None)
        except Exception as e:
            logger.error(f"刷新历史记录失败: {e}")
            return gr.update()
    
    def _load_history_record(self, selected_choice: str):
        """载入选中的历史记录"""
        try:
            if not selected_choice:
                return "", "", [], []
            
            # 获取历史记录
            history_records = self.workflow.get_history_records()
            if not history_records:
                return "", "", [], []
            
            # 从选择项中提取索引（反向索引，因为显示时是最新的在前）
            choices = self._get_history_choices()
            if selected_choice not in choices:
                return "", "", [], []
            
            choice_index = choices.index(selected_choice)
            record_index = len(history_records) - 1 - choice_index  # 反向索引
            
            if 0 <= record_index < len(history_records):
                record = history_records[record_index]
                
                character_name = record.get('character_name', '')
                basic_info = record.get('basic_info', '')
                selected_categories = record.get('selected_categories', [])
                selected_collections = record.get('selected_collections', [])
                
                return (
                    character_name,
                    basic_info,
                    selected_categories,
                    selected_collections
                )
            else:
                return "", "", [], []
                
        except Exception as e:
            logger.error(f"载入历史记录失败: {e}")
            return "", "", [], []
    
    def _refresh_collections(self):
        """刷新知识集合列表"""
        try:
            self._load_collections()
            return gr.update(choices=self.available_collections, value=[])
        except Exception as e:
            logger.error(f"刷新知识集合失败: {e}")
            return gr.update()
    
    def _generate_character_profile(self, 
                                  character_name: str,
                                  basic_info: str,
                                  selected_categories: List[str],
                                  selected_collections: List[str],
                                  llm_provider: str,
                                  model_name: str,
                                  temperature: float,
                                  max_tokens: int):
        """生成角色资料"""
        try:
            # 验证输入
            if not character_name or not basic_info:
                return (
                    "**状态:** ❌ 请输入角色名称和基础信息",
                    "请先填写必要信息",
                    {},
                    None,
                    ""
                )
            
            # 更新状态
            status_update = "**状态:** 🔄 正在生成角色资料..."
            
            # 创建LLM配置 - 添加API密钥
            import os
            api_key = os.getenv('ARK_API_KEY') or os.getenv('DOUBAO_API_KEY')
            if not api_key:
                return (
                    "**状态:** ❌ 缺少API密钥配置，请检查.env文件中的DOUBAO_API_KEY或ARK_API_KEY",
                    "请先配置API密钥",
                    {},
                    None,
                    ""
                )
            
            # 根据提供商设置API base URL
            api_base = None
            if llm_provider == "doubao":
                api_base = os.getenv('DOUBAO_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')
            elif llm_provider == "openai":
                api_base = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
            
            llm_config = LLMConfig(
                provider=llm_provider,
                model_name=model_name,
                api_key=api_key,
                api_base=api_base,
                temperature=temperature,
                max_tokens=int(max_tokens)
            )
            
            # 创建工作流实例
            workflow = CharacterProfileWorkflow(llm_config=llm_config)
            
            # 执行生成（同步方式，在实际使用中可能需要异步处理）
            result = asyncio.run(workflow.generate_character_profile(
                character_name=character_name,
                basic_info=basic_info,
                selected_categories=selected_categories,
                selected_collections=selected_collections
            ))
            
            if result.get('success'):
                # 生成成功
                profile_data = result.get('generated_profile', {})
                output_file = result.get('output_file', '')
                
                # 构建概览信息
                total_categories = len(profile_data)
                total_fields = sum(len(category_data) for category_data in profile_data.values())
                
                summary = f"""
### ✅ 生成成功！

- **角色名称:** {character_name}
- **生成类别:** {total_categories} 个
- **总字段数:** {total_fields} 个
- **使用知识库:** {len(selected_collections)} 个
- **生成时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
                
                return (
                    "**状态:** ✅ 生成完成",
                    summary,
                    profile_data,
                    output_file if Path(output_file).exists() else None,
                    output_file
                )
            else:
                # 生成失败
                error_msg = result.get('error', '未知错误')
                return (
                    f"**状态:** ❌ 生成失败: {error_msg}",
                    f"生成失败: {error_msg}",
                    {},
                    None,
                    ""
                )
                
        except Exception as e:
            logger.error(f"生成角色资料失败: {e}")
            return (
                f"**状态:** ❌ 生成失败: {str(e)}",
                f"发生错误: {str(e)}",
                {},
                None,
                ""
            )
    
    def _load_batch_example(self):
        """加载批量处理示例"""
        example = [
            {
                "character_name": "穆昭",
                "basic_info": "22岁，神秘电竞高手，代号J，异端组织大阿卡那成员",
                "selected_categories": ["基本信息", "外貌特征", "性格特征"]
            },
            {
                "character_name": "测试角色A",
                "basic_info": "勇敢的战士，擅长剑术，正义感强",
                "selected_categories": ["基本信息", "性格特征", "技能能力"]
            },
            {
                "character_name": "测试角色B",
                "basic_info": "聪明的法师，精通魔法，性格内向",
                "selected_categories": ["基本信息", "技能能力"]
            }
        ]
        
        return json.dumps(example, ensure_ascii=False, indent=2)
    
    def _batch_generate_profiles(self,
                               batch_input: str,
                               selected_collections: List[str],
                               llm_provider: str,
                               model_name: str,
                               temperature: float,
                               max_tokens: int):
        """批量生成角色资料"""
        try:
            # 解析输入
            try:
                profiles_data = json.loads(batch_input)
                if not isinstance(profiles_data, list):
                    raise ValueError("输入必须是数组格式")
            except json.JSONDecodeError as e:
                return (
                    gr.update(visible=False),
                    f"**状态:** ❌ JSON格式错误: {str(e)}"
                )
            
            # 创建LLM配置 - 添加API密钥
            import os
            api_key = os.getenv('ARK_API_KEY') or os.getenv('DOUBAO_API_KEY')
            if not api_key:
                return (
                    gr.update(visible=False),
                    "**状态:** ❌ 缺少API密钥配置，请检查.env文件中的DOUBAO_API_KEY或ARK_API_KEY"
                )
            
            # 根据提供商设置API base URL
            api_base = None
            if llm_provider == "doubao":
                api_base = os.getenv('DOUBAO_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')
            elif llm_provider == "openai":
                api_base = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
            
            llm_config = LLMConfig(
                provider=llm_provider,
                model_name=model_name,
                api_key=api_key,
                api_base=api_base,
                temperature=temperature,
                max_tokens=int(max_tokens)
            )
            
            # 创建工作流实例
            workflow = CharacterProfileWorkflow(llm_config=llm_config)
            
            # 更新状态
            status_update = f"**状态:** 🔄 正在批量生成 {len(profiles_data)} 个角色的资料..."
            
            # 执行批量生成
            results = asyncio.run(workflow.batch_generate_profiles(
                profiles_data=profiles_data,
                selected_collections=selected_collections
            ))
            
            # 构建结果表格
            result_rows = []
            success_count = 0
            
            for result in results:
                character_name = result.get('character_name', '未知')
                success = result.get('success', False)
                output_file = result.get('output_file', '')
                error = result.get('error', '')
                
                if success:
                    success_count += 1
                    status = "✅ 成功"
                else:
                    status = "❌ 失败"
                
                result_rows.append([
                    character_name,
                    status,
                    output_file,
                    error
                ])
            
            final_status = f"**状态:** ✅ 批量生成完成！成功: {success_count}/{len(profiles_data)}"
            
            return (
                gr.update(value=result_rows, visible=True),
                final_status
            )
            
        except Exception as e:
            logger.error(f"批量生成失败: {e}")
            return (
                gr.update(visible=False),
                f"**状态:** ❌ 批量生成失败: {str(e)}"
            ) 