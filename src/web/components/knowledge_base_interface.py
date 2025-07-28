"""
知识库管理界面组件
支持知识库的增删查改操作
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

from tools.knowledge_base_manager import GlobalKnowledgeBase

logger = logging.getLogger(__name__)

class KnowledgeBaseInterface:
    """知识库管理界面"""
    
    def __init__(self):
        self.knowledge_base = GlobalKnowledgeBase("./workspace")
        self.collections_cache = []
        self._refresh_collections()
    
    def _refresh_collections(self):
        """刷新知识集合缓存"""
        try:
            self.collections_cache = self.knowledge_base.list_collections()
            logger.info(f"已刷新知识集合缓存，共{len(self.collections_cache)}个集合")
        except Exception as e:
            logger.error(f"刷新知识集合缓存失败: {e}")
            self.collections_cache = []
    
    def create_knowledge_base_interface(self) -> Dict[str, Any]:
        """创建完整的知识库管理界面"""
        components = {}
        
        with gr.Column():
            # 标题和描述
            gr.Markdown("## 📚 知识库管理")
            gr.Markdown("管理向量知识库，支持创建、查询、导入和删除知识集合")
            
            with gr.Tabs() as tabs:
                # 集合管理标签页
                with gr.Tab("📋 集合管理"):
                    collection_components = self._create_collection_management()
                    components.update(collection_components)
                
                # 文档管理标签页
                with gr.Tab("📄 文档管理"):
                    document_components = self._create_document_management()
                    components.update(document_components)
                
                # 文件导入标签页
                with gr.Tab("📁 文件导入"):
                    import_components = self._create_file_import()
                    components.update(import_components)
                
                # 查询测试标签页
                with gr.Tab("🔍 查询测试"):
                    query_components = self._create_query_test()
                    components.update(query_components)
                
                # 内容浏览标签页
                with gr.Tab("👁️ 内容浏览"):
                    browse_components = self._create_content_browser()
                    components.update(browse_components)
        
        # 绑定事件
        self._bind_events(components)
        
        return components
    
    def _create_collection_management(self) -> Dict[str, Any]:
        """创建集合管理面板"""
        components = {}
        
        with gr.Column():
            # 集合列表
            with gr.Group():
                gr.Markdown("### 📋 知识集合列表")
                
                components['refresh_list'] = gr.Button(
                    "🔄 刷新列表",
                    variant="secondary",
                    size="sm"
                )
                
                components['collections_table'] = gr.Dataframe(
                    label="知识集合",
                    headers=["集合名称", "描述", "文档数量", "创建时间"],
                    datatype=["str", "str", "number", "str"],
                    interactive=False,
                    value=self._get_collections_data()
                )
            
            # 创建新集合
            with gr.Group():
                gr.Markdown("### ➕ 创建新集合")
                
                with gr.Row():
                    components['new_collection_name'] = gr.Textbox(
                        label="集合名称",
                        placeholder="请输入集合名称...",
                        scale=2
                    )
                    
                    components['new_collection_desc'] = gr.Textbox(
                        label="集合描述",
                        placeholder="请输入集合描述...",
                        scale=3
                    )
                    
                    components['create_collection'] = gr.Button(
                        "创建集合",
                        variant="primary",
                        scale=1
                    )
            
            # 删除集合
            with gr.Group():
                gr.Markdown("### ❌ 删除集合")
                
                with gr.Row():
                    components['delete_collection_name'] = gr.Dropdown(
                        label="选择要删除的集合",
                        choices=[coll.name for coll in self.collections_cache],
                        interactive=True,
                        scale=2
                    )
                    
                    components['delete_collection'] = gr.Button(
                        "删除集合",
                        variant="stop",
                        scale=1
                    )
                
                components['delete_confirm'] = gr.Checkbox(
                    label="我确认要删除此集合（此操作不可撤销）",
                    value=False
                )
            
            # 操作状态
            components['collection_status'] = gr.Markdown(
                "**状态:** 等待操作...",
                visible=True
            )
        
        return components
    
    def _create_document_management(self) -> Dict[str, Any]:
        """创建文档管理面板"""
        components = {}
        
        with gr.Column():
            # 添加文档
            with gr.Group():
                gr.Markdown("### ➕ 添加文档")
                
                components['doc_collection_select'] = gr.Dropdown(
                    label="选择集合",
                    choices=[coll.name for coll in self.collections_cache],
                    interactive=True
                )
                
                components['doc_content'] = gr.Textbox(
                    label="文档内容",
                    placeholder="请输入文档内容...",
                    lines=8,
                    interactive=True
                )
                
                with gr.Row():
                    components['doc_id'] = gr.Textbox(
                        label="文档ID（可选）",
                        placeholder="留空将自动生成...",
                        scale=2
                    )
                    
                    components['auto_split'] = gr.Checkbox(
                        label="自动分割长文档",
                        value=True,
                        scale=1
                    )
                
                components['add_document'] = gr.Button(
                    "添加文档",
                    variant="primary"
                )
            
            # 文档元数据
            with gr.Group():
                gr.Markdown("### 🏷️ 文档元数据（JSON格式）")
                
                components['doc_metadata'] = gr.Textbox(
                    label="元数据",
                    placeholder='{"type": "character", "source": "user_input"}',
                    lines=3,
                    interactive=True
                )
            
            # 文档操作状态
            components['document_status'] = gr.Markdown(
                "**状态:** 等待操作...",
                visible=True
            )
        
        return components
    
    def _create_file_import(self) -> Dict[str, Any]:
        """创建文件导入面板"""
        components = {}
        
        with gr.Column():
            # 文件上传
            with gr.Group():
                gr.Markdown("### 📁 上传文件")
                
                components['upload_file'] = gr.File(
                    label="选择文本文件",
                    file_types=[".txt", ".md", ".csv"],
                    file_count="single"
                )
                
                components['import_collection_name'] = gr.Textbox(
                    label="目标集合名称",
                    placeholder="请输入集合名称...",
                    info="如果集合不存在将自动创建"
                )
                
                components['import_collection_desc'] = gr.Textbox(
                    label="集合描述（仅在新建时使用）",
                    placeholder="请输入集合描述..."
                )
            
            # 导入配置
            with gr.Group():
                gr.Markdown("### ⚙️ 导入配置")
                
                with gr.Row():
                    components['import_separator'] = gr.Textbox(
                        label="文本分割符",
                        value="\n",
                        scale=1
                    )
                    
                    components['import_encoding'] = gr.Dropdown(
                        label="文件编码",
                        choices=["utf-8", "gbk", "gb2312"],
                        value="utf-8",
                        scale=1
                    )
                
                components['import_button'] = gr.Button(
                    "开始导入",
                    variant="primary"
                )
            
            # 导入进度和结果
            components['import_progress'] = gr.Textbox(
                label="导入进度",
                lines=5,
                interactive=False,
                visible=False
            )
            
            components['import_status'] = gr.Markdown(
                "**状态:** 等待文件上传...",
                visible=True
            )
        
        return components
    
    def _create_query_test(self) -> Dict[str, Any]:
        """创建查询测试面板"""
        components = {}
        
        with gr.Column():
            # 查询配置
            with gr.Group():
                gr.Markdown("### 🔍 查询配置")
                
                components['query_collection'] = gr.Dropdown(
                    label="选择集合",
                    choices=[coll.name for coll in self.collections_cache],
                    interactive=True
                )
                
                components['query_text'] = gr.Textbox(
                    label="查询文本",
                    placeholder="请输入要查询的内容...",
                    lines=3,
                    interactive=True
                )
                
                with gr.Row():
                    components['query_limit'] = gr.Number(
                        label="返回结果数量",
                        value=5,
                        minimum=1,
                        maximum=20,
                        scale=1
                    )
                    
                    components['query_button'] = gr.Button(
                        "执行查询",
                        variant="primary",
                        scale=1
                    )
            
            # 查询结果
            with gr.Group():
                gr.Markdown("### 📊 查询结果")
                
                components['query_results'] = gr.JSON(
                    label="查询结果",
                    value={},
                    visible=True
                )
                
                components['query_summary'] = gr.Markdown(
                    "暂无查询结果",
                    visible=True
                )
            
            components['query_status'] = gr.Markdown(
                "**状态:** 等待查询...",
                visible=True
            )
        
        return components
    
    def _create_content_browser(self) -> Dict[str, Any]:
        """创建内容浏览面板"""
        components = {}
        
        with gr.Column():
            # 浏览控制
            with gr.Group():
                gr.Markdown("### 👁️ 内容浏览")
                
                with gr.Row():
                    components['browse_collection'] = gr.Dropdown(
                        label="选择要浏览的集合",
                        choices=[coll.name for coll in self.collections_cache],
                        interactive=True,
                        scale=2
                    )
                    
                    components['browse_load'] = gr.Button(
                        "📋 加载内容",
                        variant="primary",
                        scale=1
                    )
                    
                    components['browse_refresh'] = gr.Button(
                        "🔄 刷新",
                        variant="secondary",
                        scale=1
                    )
                
                # 分页控制
                with gr.Row():
                    components['browse_page_size'] = gr.Number(
                        label="每页显示数量",
                        value=10,
                        minimum=5,
                        maximum=50,
                        scale=1
                    )
                    
                    components['browse_current_page'] = gr.Number(
                        label="当前页",
                        value=1,
                        minimum=1,
                        scale=1
                    )
                    
                    components['browse_total_pages'] = gr.Number(
                        label="总页数",
                        value=1,
                        interactive=False,
                        scale=1
                    )
                
                with gr.Row():
                    components['browse_prev_page'] = gr.Button(
                        "⬅️ 上一页",
                        variant="secondary",
                        size="sm"
                    )
                    
                    components['browse_next_page'] = gr.Button(
                        "➡️ 下一页", 
                        variant="secondary",
                        size="sm"
                    )
                    
                    components['browse_first_page'] = gr.Button(
                        "⏮️ 首页",
                        variant="secondary", 
                        size="sm"
                    )
                    
                    components['browse_last_page'] = gr.Button(
                        "⏭️ 末页",
                        variant="secondary",
                        size="sm"
                    )
            
            # 内容显示区域
            with gr.Group():
                gr.Markdown("### 📄 文档内容")
                
                # 集合信息
                components['browse_collection_info'] = gr.Markdown(
                    "**集合信息:** 请选择集合并加载内容",
                    visible=True
                )
                
                # 搜索过滤
                with gr.Row():
                    components['browse_search'] = gr.Textbox(
                        label="搜索关键词",
                        placeholder="输入关键词过滤文档内容...",
                        scale=3
                    )
                    
                    components['browse_search_btn'] = gr.Button(
                        "🔍 搜索",
                        variant="primary",
                        scale=1
                    )
                    
                    components['browse_clear_search'] = gr.Button(
                        "🗑️ 清空",
                        variant="secondary",
                        scale=1
                    )
                
                # 文档列表
                components['browse_documents'] = gr.Dataframe(
                    label="文档列表",
                    headers=["ID", "内容预览", "元数据", "创建时间"],
                    datatype=["str", "str", "str", "str"],
                    interactive=False,
                    wrap=True,
                    value=[],
                    visible=True
                )
                
                # 详细内容查看
                with gr.Accordion("📖 文档详细内容", open=False):
                    components['browse_doc_selector'] = gr.Dropdown(
                        label="选择要查看的文档",
                        choices=[],
                        interactive=True
                    )
                    
                    components['browse_doc_content'] = gr.Textbox(
                        label="完整文档内容",
                        lines=15,
                        interactive=False,
                        placeholder="选择文档查看详细内容..."
                    )
                    
                    components['browse_doc_metadata'] = gr.JSON(
                        label="文档元数据",
                        value={},
                        visible=True
                    )
            
            # 批量操作
            with gr.Group():
                gr.Markdown("### 🔧 批量操作")
                
                with gr.Row():
                    components['browse_export_all'] = gr.Button(
                        "📥 导出所有文档",
                        variant="primary"
                    )
                    
                    components['browse_export_filtered'] = gr.Button(
                        "📥 导出筛选结果",
                        variant="secondary"
                    )
                    
                    components['browse_delete_filtered'] = gr.Button(
                        "🗑️ 删除筛选结果",
                        variant="stop"
                    )
                
                components['browse_export_file'] = gr.File(
                    label="导出文件下载",
                    visible=False
                )
            
            # 状态显示
            components['browse_status'] = gr.Markdown(
                "**状态:** 等待加载...",
                visible=True
            )
        
        return components
    
    def _bind_events(self, components: Dict[str, Any]):
        """绑定界面事件"""
        
        # 刷新集合列表
        components['refresh_list'].click(
            fn=self._refresh_collections_display,
            outputs=[
                components['collections_table'],
                components['delete_collection_name'],
                components['doc_collection_select'],
                components['query_collection']
            ]
        )
        
        # 创建集合
        components['create_collection'].click(
            fn=self._create_new_collection,
            inputs=[
                components['new_collection_name'],
                components['new_collection_desc']
            ],
            outputs=[
                components['collection_status'],
                components['collections_table'],
                components['delete_collection_name'],
                components['doc_collection_select'],
                components['query_collection']
            ]
        )
        
        # 删除集合
        components['delete_collection'].click(
            fn=self._delete_collection,
            inputs=[
                components['delete_collection_name'],
                components['delete_confirm']
            ],
            outputs=[
                components['collection_status'],
                components['collections_table'],
                components['delete_collection_name'],
                components['doc_collection_select'],
                components['query_collection']
            ]
        )
        
        # 添加文档
        components['add_document'].click(
            fn=self._add_document,
            inputs=[
                components['doc_collection_select'],
                components['doc_content'],
                components['doc_id'],
                components['doc_metadata'],
                components['auto_split']
            ],
            outputs=[
                components['document_status'],
                components['collections_table']
            ]
        )
        
        # 文件导入
        components['import_button'].click(
            fn=self._import_file,
            inputs=[
                components['upload_file'],
                components['import_collection_name'],
                components['import_collection_desc'],
                components['import_separator'],
                components['import_encoding']
            ],
            outputs=[
                components['import_status'],
                components['import_progress'],
                components['collections_table']
            ]
        )
        
        # 执行查询
        components['query_button'].click(
            fn=self._execute_query,
            inputs=[
                components['query_collection'],
                components['query_text'],
                components['query_limit']
            ],
            outputs=[
                components['query_status'],
                components['query_results'],
                components['query_summary']
            ]
        )
        
        # === 内容浏览事件 ===
        
        # 加载内容
        components['browse_load'].click(
            fn=self._load_collection_content,
            inputs=[
                components['browse_collection'],
                components['browse_page_size'],
                components['browse_current_page']
            ],
            outputs=[
                components['browse_status'],
                components['browse_collection_info'],
                components['browse_documents'],
                components['browse_doc_selector'],
                components['browse_total_pages']
            ]
        )
        
        # 刷新集合列表
        components['browse_refresh'].click(
            fn=self._refresh_browse_collections,
            outputs=[
                components['browse_collection']
            ]
        )
        
        # 分页导航
        components['browse_prev_page'].click(
            fn=self._browse_prev_page,
            inputs=[
                components['browse_collection'],
                components['browse_page_size'],
                components['browse_current_page']
            ],
            outputs=[
                components['browse_current_page'],
                components['browse_documents'],
                components['browse_doc_selector']
            ]
        )
        
        components['browse_next_page'].click(
            fn=self._browse_next_page,
            inputs=[
                components['browse_collection'],
                components['browse_page_size'],
                components['browse_current_page'],
                components['browse_total_pages']
            ],
            outputs=[
                components['browse_current_page'],
                components['browse_documents'],
                components['browse_doc_selector']
            ]
        )
        
        components['browse_first_page'].click(
            fn=self._browse_first_page,
            inputs=[
                components['browse_collection'],
                components['browse_page_size']
            ],
            outputs=[
                components['browse_current_page'],
                components['browse_documents'],
                components['browse_doc_selector']
            ]
        )
        
        components['browse_last_page'].click(
            fn=self._browse_last_page,
            inputs=[
                components['browse_collection'],
                components['browse_page_size'],
                components['browse_total_pages']
            ],
            outputs=[
                components['browse_current_page'],
                components['browse_documents'],
                components['browse_doc_selector']
            ]
        )
        
        # 文档详细查看
        components['browse_doc_selector'].change(
            fn=self._view_document_detail,
            inputs=[
                components['browse_collection'],
                components['browse_doc_selector']
            ],
            outputs=[
                components['browse_doc_content'],
                components['browse_doc_metadata']
            ]
        )
        
        # 搜索功能
        components['browse_search_btn'].click(
            fn=self._search_documents,
            inputs=[
                components['browse_collection'],
                components['browse_search'],
                components['browse_page_size']
            ],
            outputs=[
                components['browse_status'],
                components['browse_documents'],
                components['browse_doc_selector'],
                components['browse_current_page'],
                components['browse_total_pages']
            ]
        )
        
        components['browse_clear_search'].click(
            fn=self._clear_search,
            inputs=[
                components['browse_collection'],
                components['browse_page_size']
            ],
            outputs=[
                components['browse_search'],
                components['browse_documents'],
                components['browse_doc_selector'],
                components['browse_current_page'],
                components['browse_total_pages']
            ]
        )
        
        # 导出功能
        components['browse_export_all'].click(
            fn=self._export_all_documents,
            inputs=[
                components['browse_collection']
            ],
            outputs=[
                components['browse_status'],
                components['browse_export_file']
            ]
        )
    
    def _get_collections_data(self) -> List[List[str]]:
        """获取集合数据表格"""
        data = []
        for coll in self.collections_cache:
            data.append([
                coll.name,
                coll.description,
                coll.document_count,
                coll.created_at[:19] if coll.created_at else "未知"
            ])
        return data
    
    def _refresh_collections_display(self):
        """刷新集合显示"""
        self._refresh_collections()
        collection_names = [coll.name for coll in self.collections_cache]
        
        return (
            gr.update(value=self._get_collections_data()),
            gr.update(choices=collection_names),
            gr.update(choices=collection_names),
            gr.update(choices=collection_names)
        )
    
    def _create_new_collection(self, name: str, description: str):
        """创建新集合"""
        try:
            if not name:
                return (
                    "**状态:** ❌ 请输入集合名称",
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update()
                )
            
            # 检查集合是否已存在
            if any(coll.name == name for coll in self.collections_cache):
                return (
                    f"**状态:** ❌ 集合 '{name}' 已存在",
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update()
                )
            
            # 创建集合
            success = asyncio.run(self.knowledge_base.create_collection(
                name=name,
                description=description or f"集合 {name}"
            ))
            
            if success:
                self._refresh_collections()
                collection_names = [coll.name for coll in self.collections_cache]
                
                return (
                    f"**状态:** ✅ 成功创建集合 '{name}'",
                    gr.update(value=self._get_collections_data()),
                    gr.update(choices=collection_names),
                    gr.update(choices=collection_names),
                    gr.update(choices=collection_names)
                )
            else:
                return (
                    f"**状态:** ❌ 创建集合 '{name}' 失败",
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update()
                )
                
        except Exception as e:
            logger.error(f"创建集合失败: {e}")
            return (
                f"**状态:** ❌ 创建失败: {str(e)}",
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update()
            )
    
    def _delete_collection(self, collection_name: str, confirm: bool):
        """删除集合"""
        try:
            if not collection_name:
                return (
                    "**状态:** ❌ 请选择要删除的集合",
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update()
                )
            
            if not confirm:
                return (
                    "**状态:** ❌ 请确认删除操作",
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update()
                )
            
            # 删除集合
            success = asyncio.run(self.knowledge_base.delete_collection(collection_name))
            
            if success:
                self._refresh_collections()
                collection_names = [coll.name for coll in self.collections_cache]
                
                return (
                    f"**状态:** ✅ 成功删除集合 '{collection_name}'",
                    gr.update(value=self._get_collections_data()),
                    gr.update(choices=collection_names, value=None),
                    gr.update(choices=collection_names),
                    gr.update(choices=collection_names)
                )
            else:
                return (
                    f"**状态:** ❌ 删除集合 '{collection_name}' 失败",
                    gr.update(),
                    gr.update(),
                    gr.update(),
                    gr.update()
                )
                
        except Exception as e:
            logger.error(f"删除集合失败: {e}")
            return (
                f"**状态:** ❌ 删除失败: {str(e)}",
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update()
            )
    
    def _add_document(self, collection_name: str, content: str, doc_id: str, metadata_str: str, auto_split: bool):
        """添加文档"""
        try:
            if not collection_name or not content:
                return (
                    "**状态:** ❌ 请选择集合并输入文档内容",
                    gr.update()
                )
            
            # 解析元数据
            metadata = {}
            if metadata_str:
                try:
                    metadata = json.loads(metadata_str)
                except json.JSONDecodeError:
                    return (
                        "**状态:** ❌ 元数据JSON格式错误",
                        gr.update()
                    )
            
            # 添加文档
            success = asyncio.run(self.knowledge_base.add_documents(
                collection_name=collection_name,
                documents=[content],
                metadatas=[metadata] if metadata else None,
                ids=[doc_id] if doc_id else None,
                auto_split=auto_split
            ))
            
            if success:
                self._refresh_collections()
                return (
                    f"**状态:** ✅ 成功添加文档到集合 '{collection_name}'",
                    gr.update(value=self._get_collections_data())
                )
            else:
                return (
                    f"**状态:** ❌ 添加文档失败",
                    gr.update()
                )
                
        except Exception as e:
            logger.error(f"添加文档失败: {e}")
            return (
                f"**状态:** ❌ 添加失败: {str(e)}",
                gr.update()
            )
    
    def _import_file(self, file_obj, collection_name: str, description: str, separator: str, encoding: str):
        """导入文件"""
        try:
            if not file_obj or not collection_name:
                return (
                    "**状态:** ❌ 请选择文件并输入集合名称",
                    gr.update(visible=False),
                    gr.update()
                )
            
            file_path = file_obj.name
            
            # 创建集合（如果不存在）
            if not any(coll.name == collection_name for coll in self.collections_cache):
                asyncio.run(self.knowledge_base.create_collection(
                    name=collection_name,
                    description=description or f"从文件导入: {Path(file_path).name}"
                ))
            
            # 导入文件
            success = asyncio.run(self.knowledge_base.import_from_text_file(
                collection_name=collection_name,
                file_path=file_path,
                separator=separator,
                encoding=encoding
            ))
            
            if success:
                self._refresh_collections()
                progress_text = f"✅ 文件 '{Path(file_path).name}' 导入完成\n导入到集合: {collection_name}"
                
                return (
                    f"**状态:** ✅ 文件导入成功",
                    gr.update(value=progress_text, visible=True),
                    gr.update(value=self._get_collections_data())
                )
            else:
                return (
                    "**状态:** ❌ 文件导入失败",
                    gr.update(visible=False),
                    gr.update()
                )
                
        except Exception as e:
            logger.error(f"文件导入失败: {e}")
            return (
                f"**状态:** ❌ 导入失败: {str(e)}",
                gr.update(visible=False),
                gr.update()
            )
    
    def _execute_query(self, collection_name: str, query_text: str, limit: int):
        """执行查询"""
        try:
            if not collection_name or not query_text:
                return (
                    "**状态:** ❌ 请选择集合并输入查询文本",
                    {},
                    "请先选择集合并输入查询内容"
                )
            
            # 执行查询
            results = asyncio.run(self.knowledge_base.query_documents(
                collection_name=collection_name,
                query_text=query_text,
                n_results=int(limit)
            ))
            
            if results:
                # 构建摘要
                summary = f"""
### 🔍 查询结果摘要

- **查询集合:** {collection_name}
- **查询文本:** {query_text}
- **结果数量:** {len(results)} 个
- **查询时间:** {datetime.now().strftime('%H:%M:%S')}

#### 最相关的结果:
{chr(10).join([f"**{i+1}.** {result['document'][:100]}..." for i, result in enumerate(results[:3])])}
                """
                
                return (
                    f"**状态:** ✅ 查询完成，找到 {len(results)} 个结果",
                    results,
                    summary
                )
            else:
                return (
                    "**状态:** ⚠️ 未找到相关结果",
                    [],
                    "未找到相关文档，请尝试调整查询条件"
                )
                
        except Exception as e:
            logger.error(f"查询执行失败: {e}")
            return (
                f"**状态:** ❌ 查询失败: {str(e)}",
                {},
                f"查询出错: {str(e)}"
            )
    
    # === 内容浏览方法 ===
    
    def _refresh_browse_collections(self):
        """刷新浏览界面的集合列表"""
        self._refresh_collections()
        collection_names = [coll.name for coll in self.collections_cache]
        return gr.update(choices=collection_names)
    
    def _load_collection_content(self, collection_name: str, page_size: int, current_page: int):
        """加载集合内容"""
        try:
            if not collection_name:
                return (
                    "**状态:** ❌ 请选择要浏览的集合",
                    "**集合信息:** 请选择集合",
                    [],
                    gr.update(choices=[]),
                    1
                )
            
            # 获取集合信息
            collection_info = None
            for coll in self.collections_cache:
                if coll.name == collection_name:
                    collection_info = coll
                    break
            
            if not collection_info:
                return (
                    f"**状态:** ❌ 集合 '{collection_name}' 不存在",
                    "**集合信息:** 集合不存在",
                    [],
                    gr.update(choices=[]),
                    1
                )
            
            # 计算分页
            total_docs = collection_info.document_count
            total_pages = max(1, (total_docs + page_size - 1) // page_size)
            current_page = max(1, min(current_page, total_pages))
            
            # 获取当前页的文档
            offset = (current_page - 1) * page_size
            documents = asyncio.run(self.knowledge_base.get_all_documents(
                collection_name=collection_name,
                limit=page_size,
                offset=offset
            ))
            
            if not documents:
                return (
                    f"**状态:** ⚠️ 集合 '{collection_name}' 暂无文档",
                    f"**集合信息:** {collection_name} | 文档数: 0 | 描述: {collection_info.description}",
                    [],
                    gr.update(choices=[]),
                    1
                )
            
            # 构建文档列表
            doc_rows = []
            doc_choices = []
            
            for i, doc in enumerate(documents):
                doc_id = doc.get('id', f'doc_{offset + i + 1}')
                content = doc.get('document', doc.get('content', ''))
                metadata = doc.get('metadata', {})
                
                # 内容预览（前100字符）
                preview = content[:100] + "..." if len(content) > 100 else content
                
                # 元数据简要显示
                metadata_str = json.dumps(metadata, ensure_ascii=False)[:50] + "..." if len(str(metadata)) > 50 else json.dumps(metadata, ensure_ascii=False)
                
                # 创建时间（如果有的话）
                created_at = metadata.get('created_at', '未知')
                
                doc_rows.append([doc_id, preview, metadata_str, created_at])
                doc_choices.append(f"{doc_id}: {preview[:30]}")
            
            collection_info_text = f"""
**集合信息:** {collection_name}

- **描述:** {collection_info.description}
- **总文档数:** {total_docs}
- **当前页:** {current_page}/{total_pages}
- **每页显示:** {page_size}
            """
            
            return (
                f"**状态:** ✅ 已加载 {len(documents)} 个文档 (第{current_page}页/共{total_pages}页)",
                collection_info_text,
                doc_rows,
                gr.update(choices=doc_choices),
                total_pages
            )
            
        except Exception as e:
            logger.error(f"加载集合内容失败: {e}")
            return (
                f"**状态:** ❌ 加载失败: {str(e)}",
                "**集合信息:** 加载失败",
                [],
                gr.update(choices=[]),
                1
            )
    
    def _browse_prev_page(self, collection_name: str, page_size: int, current_page: int):
        """上一页"""
        new_page = max(1, current_page - 1)
        if new_page == current_page:
            return current_page, gr.update(), gr.update()
        
        _, _, docs, doc_selector, _ = self._load_collection_content(collection_name, page_size, new_page)
        return new_page, docs, doc_selector
    
    def _browse_next_page(self, collection_name: str, page_size: int, current_page: int, total_pages: int):
        """下一页"""
        new_page = min(total_pages, current_page + 1)
        if new_page == current_page:
            return current_page, gr.update(), gr.update()
        
        _, _, docs, doc_selector, _ = self._load_collection_content(collection_name, page_size, new_page)
        return new_page, docs, doc_selector
    
    def _browse_first_page(self, collection_name: str, page_size: int):
        """首页"""
        _, _, docs, doc_selector, _ = self._load_collection_content(collection_name, page_size, 1)
        return 1, docs, doc_selector
    
    def _browse_last_page(self, collection_name: str, page_size: int, total_pages: int):
        """末页"""
        _, _, docs, doc_selector, _ = self._load_collection_content(collection_name, page_size, total_pages)
        return total_pages, docs, doc_selector
    
    def _view_document_detail(self, collection_name: str, doc_selector: str):
        """查看文档详细内容"""
        try:
            if not collection_name or not doc_selector:
                return "", {}
            
            # 从选择器中提取文档ID
            doc_id = doc_selector.split(":")[0].strip()
            
            # 获取文档详细内容
            document = asyncio.run(self.knowledge_base.get_document_by_id(
                collection_name=collection_name,
                document_id=doc_id
            ))
            
            if document:
                content = document.get('document', document.get('content', ''))
                metadata = document.get('metadata', {})
                return content, metadata
            else:
                return "文档不存在或已被删除", {}
                
        except Exception as e:
            logger.error(f"查看文档详情失败: {e}")
            return f"加载失败: {str(e)}", {}
    
    def _search_documents(self, collection_name: str, search_text: str, page_size: int):
        """搜索文档"""
        try:
            if not collection_name:
                return (
                    "**状态:** ❌ 请选择集合",
                    [],
                    gr.update(choices=[]),
                    1,
                    1
                )
            
            if not search_text:
                # 如果搜索为空，显示所有文档
                return self._load_collection_content(collection_name, page_size, 1)[0:2] + self._load_collection_content(collection_name, page_size, 1)[2:5]
            
            # 使用向量搜索
            results = asyncio.run(self.knowledge_base.query_documents(
                collection_name=collection_name,
                query_text=search_text,
                n_results=page_size
            ))
            
            if not results:
                return (
                    f"**状态:** ⚠️ 未找到包含 '{search_text}' 的文档",
                    [],
                    gr.update(choices=[]),
                    1,
                    1
                )
            
            # 构建搜索结果
            doc_rows = []
            doc_choices = []
            
            for i, result in enumerate(results):
                doc_id = result.get('id', f'search_{i+1}')
                content = result.get('document', '')
                metadata = result.get('metadata', {})
                
                # 高亮搜索关键词
                preview = content[:100] + "..." if len(content) > 100 else content
                
                metadata_str = json.dumps(metadata, ensure_ascii=False)[:50] + "..." if len(str(metadata)) > 50 else json.dumps(metadata, ensure_ascii=False)
                created_at = metadata.get('created_at', '未知')
                
                doc_rows.append([doc_id, preview, metadata_str, created_at])
                doc_choices.append(f"{doc_id}: {preview[:30]}")
            
            return (
                f"**状态:** ✅ 找到 {len(results)} 个相关文档",
                doc_rows,
                gr.update(choices=doc_choices),
                1,
                1
            )
            
        except Exception as e:
            logger.error(f"搜索文档失败: {e}")
            return (
                f"**状态:** ❌ 搜索失败: {str(e)}",
                [],
                gr.update(choices=[]),
                1,
                1
            )
    
    def _clear_search(self, collection_name: str, page_size: int):
        """清空搜索"""
        result = self._load_collection_content(collection_name, page_size, 1)
        return ("", result[2], result[3], result[4], result[4])  # 清空搜索框，返回第一页数据
    
    def _export_all_documents(self, collection_name: str):
        """导出所有文档"""
        try:
            if not collection_name:
                return (
                    "**状态:** ❌ 请选择要导出的集合",
                    None
                )
            
            # 获取所有文档
            all_documents = asyncio.run(self.knowledge_base.get_all_documents(
                collection_name=collection_name,
                limit=10000  # 设置一个较大的限制
            ))
            
            if not all_documents:
                return (
                    f"**状态:** ⚠️ 集合 '{collection_name}' 无文档可导出",
                    None
                )
            
            # 生成导出文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_path = f"workspace/exports/knowledge_export_{collection_name}_{timestamp}.json"
            
            # 确保目录存在
            Path(export_path).parent.mkdir(parents=True, exist_ok=True)
            
            # 导出数据
            export_data = {
                "collection_name": collection_name,
                "export_time": datetime.now().isoformat(),
                "document_count": len(all_documents),
                "documents": all_documents
            }
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            return (
                f"**状态:** ✅ 已导出 {len(all_documents)} 个文档到 {export_path}",
                export_path
            )
            
        except Exception as e:
            logger.error(f"导出文档失败: {e}")
            return (
                f"**状态:** ❌ 导出失败: {str(e)}",
                None
            ) 