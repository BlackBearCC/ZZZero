"""笑话生成工作流 - 基于方知衡人设的笑话创作系统
根据主角的性格特点生成符合人设的幽默内容，支持批量生成几千条不重样的笑话
"""

import json
import asyncio
import random
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.graph import StateGraph
from core.base import BaseNode
from llm.base import LLMFactory
from core.types import LLMConfig, TaskResult, Message, MessageRole

logger = logging.getLogger(__name__)

class JokeWorkflow:
    """笑话生成工作流管理器"""
    
    def __init__(self, llm=None):
        self.llm = llm
        self.graph = None
        self.protagonist_data = ""  # 主角方知衡的详细人设
        self.current_config = {
            'protagonist': '方知衡',  # 固定主角
            'batch_size': 50,  # 每批生成的笑话数量
            'total_target': 1000,  # 总目标数量
            'joke_categories': [
                '学术幽默', '生活日常', '毒奶体质', '网络落伍', 
                '古板认真', '温和吐槽', '理性分析', '意外反差'
            ],
            'difficulty_levels': ['简单', '中等', '复杂'],
            'humor_styles': ['冷幽默', '自嘲', '观察式', '反差萌'],
            'pg_config': {
                'host': 'localhost',
                'port': 5432,
                'database': 'jokes_db',
                'user': 'postgres',
                'password': 'password'
            }
        }
        
        # 加载主角人设
        self._load_protagonist_data()
        
        # 初始化数据库
        self._init_database()
    
    def _load_protagonist_data(self):
        """加载主角方知衡的详细人设"""
        try:
            protagonist_path = os.path.join(os.path.dirname(__file__), '../../config/基础人设.txt')
            if os.path.exists(protagonist_path):
                with open(protagonist_path, 'r', encoding='utf-8') as f:
                    self.protagonist_data = f.read()
                    logger.info(f"成功加载主角人设，内容长度: {len(self.protagonist_data)} 字符")
            else:
                logger.warning("主角人设文件不存在")
                
        except Exception as e:
            logger.error(f"加载主角人设失败: {e}")
    
    def _init_database(self):
        """初始化PostgreSQL数据库和表结构"""
        try:
            pg_config = self.current_config['pg_config']
            
            # 连接数据库
            conn = psycopg2.connect(**pg_config)
            cursor = conn.cursor()
            
            # 创建笑话表
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS jokes (
                id SERIAL PRIMARY KEY,
                joke_id VARCHAR(50) UNIQUE NOT NULL,
                category VARCHAR(50) NOT NULL,
                difficulty_level VARCHAR(20) NOT NULL,
                humor_style VARCHAR(30) NOT NULL,
                setup TEXT NOT NULL,
                punchline TEXT NOT NULL,
                context TEXT,
                character_traits TEXT[],
                tags TEXT[],
                rating INTEGER DEFAULT 0,
                is_used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_jokes_category ON jokes(category);
            CREATE INDEX IF NOT EXISTS idx_jokes_rating ON jokes(rating);
            CREATE INDEX IF NOT EXISTS idx_jokes_created_at ON jokes(created_at);
            """
            
            cursor.execute(create_table_sql)
            conn.commit()
            
            cursor.close()
            conn.close()
            
            logger.info("数据库表结构初始化完成")
            
        except Exception as e:
            logger.warning(f"数据库初始化失败，将跳过数据库相关操作: {e}")
            # 设置标志，表示数据库不可用
            self.current_config['database_available'] = False
    
    def update_config(self, config_updates: Dict[str, Any]):
        """更新工作流配置"""
        self.current_config.update(config_updates)
    
    async def create_joke_graph(self) -> StateGraph:
        """创建笑话生成图工作流"""
        self.graph = StateGraph(name="joke_generation_workflow")
        
        # 创建节点
        theme_planning_node = ThemePlanningNode()  # 主题规划节点
        joke_generate_node = JokeGenerateNode()   # 笑话生成节点
        quality_check_node = QualityCheckNode()   # 质量检查节点
        database_save_node = JokeDatabaseSaveNode()  # 数据库保存节点
        
        # 添加节点到图
        self.graph.add_node("theme_planning", theme_planning_node)
        self.graph.add_node("joke_generate", joke_generate_node)
        self.graph.add_node("quality_check", quality_check_node)
        self.graph.add_node("database_save", database_save_node)
        
        # 定义节点连接关系
        self.graph.add_edge("theme_planning", "joke_generate")
        self.graph.add_edge("joke_generate", "quality_check")
        self.graph.add_edge("quality_check", "database_save")
        
        # 设置入口点
        self.graph.set_entry_point("theme_planning")
        
        return self.graph
    
    async def execute_workflow_stream(self, config: Dict[str, Any], workflow_chat):
        """流式执行笑话生成工作流"""
        try:
            # 准备初始输入
            initial_input = {
                'protagonist_data': self.protagonist_data,
                'config': config,
                'protagonist': config.get('protagonist', '方知衡'),
                'batch_size': config.get('batch_size', 50),
                'total_target': config.get('total_target', 1000),
                'joke_categories': config.get('joke_categories', self.current_config['joke_categories']),
                'difficulty_levels': config.get('difficulty_levels', self.current_config['difficulty_levels']),
                'humor_styles': config.get('humor_styles', self.current_config['humor_styles']),
                'pg_config': config.get('pg_config', self.current_config['pg_config']),
                'workflow_chat': workflow_chat,
                'llm': self.llm
            }
            
            # 创建并编译图工作流
            if not self.graph:
                await self.create_joke_graph()
            
            compiled_graph = self.graph.compile()
            
            # 使用图的流式执行
            async for stream_event in compiled_graph.stream(initial_input):
                event_type = stream_event.get('type')
                node_name = stream_event.get('node')
                
                if event_type == 'start':
                    yield (
                        workflow_chat._create_workflow_progress(),
                        "",
                        "笑话生成工作流开始执行...",
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
                        content_length = 0
                        for key in ['jokes_data', 'generated_jokes', 'checked_jokes']:
                            if key in intermediate_result.state_update:
                                if isinstance(intermediate_result.state_update[key], list):
                                    content_length = len(intermediate_result.state_update[key])
                                break
                        
                        if content_length > 0:
                            node_display_name = self._get_node_display_name(node_name)
                            await workflow_chat.add_node_message(
                                node_display_name,
                                f"正在处理笑话内容... 当前数量: {content_length}",
                                "streaming"
                            )
                            
                            yield (
                                workflow_chat._create_workflow_progress(),
                                "",
                                f"正在处理笑话... 当前数量: {content_length}",
                                False
                            )
                
                elif event_type == 'node_complete':
                    node_display_name = self._get_node_display_name(node_name)
                    
                    if node_name == 'joke_generate':
                        result_content = "✅ 笑话生成完成"
                        if 'generated_jokes' in stream_event.get('output', {}):
                            jokes_data = stream_event['output']['generated_jokes']
                            if isinstance(jokes_data, list):
                                result_content = f"✅ 已成功生成{len(jokes_data)}条笑话"
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
                        "笑话生成工作流执行完成",
                        False
                    )
                
                else:
                    yield (
                        workflow_chat._create_workflow_progress(),
                        "",
                        "笑话生成工作流执行中...",
                        False
                    )
                
        except Exception as e:
            logger.error(f"笑话生成工作流流式执行失败: {e}")
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
            'theme_planning': '主题规划',
            'joke_generate': '笑话生成',
            'quality_check': '质量检查',
            'database_save': '数据库保存'
        }
        return name_mapping.get(node_name, node_name)
    
    def _get_node_id(self, node_name: str) -> str:
        """获取节点ID"""
        id_mapping = {
            'theme_planning': 'planning',
            'joke_generate': 'generate',
            'quality_check': 'check',
            'database_save': 'save'
        }
        return id_mapping.get(node_name, node_name)


class ThemePlanningNode(BaseNode):
    """主题规划节点 - 根据人设特点规划笑话主题和风格"""
    
    def __init__(self):
        super().__init__(name="theme_planning", stream=True)
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行主题规划节点 - 非流式版本"""
        final_result = None
        async for result in self.execute_stream(input_data):
            final_result = result
        return final_result or input_data
    
    async def execute_stream(self, input_data: Dict[str, Any]):
        """流式执行主题规划节点"""
        print("🎯 开始主题规划...")
        
        workflow_chat = input_data.get('workflow_chat')
        
        # 获取配置参数
        protagonist = input_data.get('protagonist', '方知衡')
        batch_size = input_data.get('batch_size', 50)
        total_target = input_data.get('total_target', 1000)
        joke_categories = input_data.get('joke_categories', [])
        
        if workflow_chat:
            await workflow_chat.add_node_message(
                "主题规划",
                f"正在为{protagonist}规划{total_target}条笑话的主题分布...",
                "progress"
            )
        
        try:
            # 计算需要多少个批次
            total_batches = (total_target + batch_size - 1) // batch_size
            
            # 为每个批次分配主题
            theme_plan = {
                'total_batches': total_batches,
                'batch_size': batch_size,
                'category_distribution': {},
                'batch_themes': []
            }
            
            # 平衡分配各个类别
            categories_per_batch = max(1, len(joke_categories) // total_batches)
            
            for batch_idx in range(total_batches):
                # 为当前批次选择主题类别
                start_cat = (batch_idx * categories_per_batch) % len(joke_categories)
                end_cat = min(start_cat + categories_per_batch, len(joke_categories))
                batch_categories = joke_categories[start_cat:end_cat]
                
                # 如果类别不够，从头开始补充
                if len(batch_categories) < categories_per_batch:
                    remaining = categories_per_batch - len(batch_categories)
                    batch_categories.extend(joke_categories[:remaining])
                
                batch_theme = {
                    'batch_number': batch_idx + 1,
                    'categories': batch_categories,
                    'focus_trait': self._get_focus_trait(batch_idx),
                    'humor_emphasis': self._get_humor_emphasis(batch_idx)
                }
                
                theme_plan['batch_themes'].append(batch_theme)
            
            # 统计类别分布
            for theme in theme_plan['batch_themes']:
                for cat in theme['categories']:
                    theme_plan['category_distribution'][cat] = theme_plan['category_distribution'].get(cat, 0) + 1
            
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "主题规划",
                    f"✅ 规划完成：{total_batches}个批次，平衡分配{len(joke_categories)}个主题类别",
                    "success"
                )
            
            # 输出结果
            output_data = input_data.copy()
            output_data['theme_plan'] = theme_plan
            output_data['current_batch_index'] = 0
            
            logger.info(f"✅ 主题规划完成，生成了{total_batches}个批次的主题分配")
            yield output_data
            
        except Exception as e:
            logger.error(f"主题规划失败: {e}")
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "主题规划",
                    f"❌ 规划失败: {str(e)}",
                    "error"
                )
            raise Exception(f"主题规划失败: {str(e)}")
    
    def _get_focus_trait(self, batch_idx: int) -> str:
        """根据批次获取重点人设特征"""
        traits = [
            '理性严谨', '内敛温和', '毒奶体质', '网络落伍',
            '古板认真', '学术专注', '生活细致', '温和吐槽'
        ]
        return traits[batch_idx % len(traits)]
    
    def _get_humor_emphasis(self, batch_idx: int) -> str:
        """根据批次获取幽默重点"""
        emphasis = [
            '冷幽默', '自嘲式', '观察式', '反差萌',
            '学者风范', '生活智慧', '意外惊喜', '温和吐槽'
        ]
        return emphasis[batch_idx % len(emphasis)]


class JokeGenerateNode(BaseNode):
    """笑话生成节点 - 基于人设生成符合特点的笑话"""
    
    def __init__(self):
        super().__init__(name="joke_generate", stream=True)
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行笑话生成节点 - 非流式版本"""
        final_result = None
        async for result in self.execute_stream(input_data):
            final_result = result
        return final_result or input_data
    
    async def execute_stream(self, input_data: Dict[str, Any]):
        """流式执行笑话生成节点 - 分批生成"""
        print("😄 开始笑话生成...")
        
        workflow_chat = input_data.get('workflow_chat')
        llm = input_data.get('llm')
        
        # 获取主题规划数据
        theme_plan = input_data.get('theme_plan', {})
        current_batch_index = input_data.get('current_batch_index', 0)
        batch_themes = theme_plan.get('batch_themes', [])
        
        if not batch_themes or current_batch_index >= len(batch_themes):
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "笑话生成",
                    "✅ 所有批次的笑话生成已完成！",
                    "success"
                )
            
            output_data = input_data.copy()
            output_data['generation_complete'] = True
            yield output_data
            return
        
        # 获取当前批次信息
        current_batch = batch_themes[current_batch_index]
        batch_categories = current_batch['categories']
        focus_trait = current_batch['focus_trait']
        humor_emphasis = current_batch['humor_emphasis']
        batch_size = input_data.get('batch_size', 50)
        
        if workflow_chat:
            await workflow_chat.add_node_message(
                "笑话生成",
                f"正在生成第 {current_batch_index + 1}/{len(batch_themes)} 批次笑话（{batch_size}条）...",
                "progress"
            )
        
        # 构建笑话生成提示词
        protagonist_data = input_data.get('protagonist_data', '')
        
        generation_prompt = f"""
你需要创作{batch_size}条笑话，这些笑话是方知衡这个角色会说的笑话，要符合他的说话风格和幽默感。

# 方知衡角色分析
{protagonist_data}

# 本批次重点特征
- 重点人设特征：{focus_trait}
- 幽默风格重点：{humor_emphasis}
- 主题类别：{', '.join(batch_categories)}

# 创作要求

## 方知衡的说话风格特点
1. **学者语言习惯**：偶尔使用专业术语，喜欢用理性分析的方式表达
2. **温和有礼**：说话方式温文尔雅，不会使用粗俗语言
3. **古板认真**：有时过于认真地对待玩笑话题，形成反差萌
4. **网络落伍**：对流行语和网络梗理解有偏差，产生代沟笑话
5. **自我反省**：习惯性地进行自我分析和反思
6. **毒奶体质**：无意中说出不吉利的话，但很快意识到并自嘲
7. **生活细致**：对细节过度关注，用学术思维分析生活小事
8. **内敛幽默**：不会大声说笑话，而是温和地表达幽默

## 笑话内容方向
这些笑话应该是方知衡在以下场景中会说的：
- 与学生、同事聊天时的冷幽默
- 对生活现象的理性分析式吐槽
- 对自己毒奶体质的自嘲式调侃
- 对网络流行语的误解性解读
- 学术思维应用到日常生活的反差笑话
- 温和地调侃生活中的小事和现象

## 笑话特征要求
2. **符合身份**：内容要符合大学教授的身份和修养
3. **温和幽默**：不尖刻，不伤人，体现温和性格

## 笑话结构要求
每条笑话包含：
- **关键词**：简短的主题关键词，5-10字
- **笑话内容**：方知衡会说的完整笑话，包含情境和笑点，100-200字

## 内容原则
1. **绿色健康**：内容积极向上，适合所有年龄段
2. **避免敏感**：不涉及政治、宗教、种族等敏感话题
3. **符合身份**：符合大学教授的身份和修养
4. **贴近生活**：基于真实生活场景，有代入感
5. **原创性**：避免抄袭已有笑话，确保原创性

## 笑话类型分布
- 数学逻辑梗：用数学/逻辑思维解构日常对话（8-12条）
- 物理学梗：用物理概念类比生活现象（8-12条）
- 文学哲学梗：引用经典作品或思想进行现代化解读（6-10条）
- 学术生活梗：教授日常工作中的观察和自嘲（8-12条）
- 毒奶定律梗：将毒奶体质理论化、学术化（6-8条）
- 跨学科融合梗：用一个学科解释另一个学科的现象（剩余条数）

## 高质量知识梗要求
1. **专业术语自然融入**：不生硬，符合对话语境
2. **逻辑层次清晰**：有铺垫、有转折、有妙点
4. **幽默点巧妙**：不是简单的知识炫耀，而是巧妙的认知反差
6. **温和自嘲**：体现学者的自我反省和幽默感

# 输出格式
请按以下JSON格式输出{batch_size}条笑话：

```json
{{
  "jokes": [
    {{
      "关键词": "简短主题关键词",
      "笑话内容": "方知衡会说的完整笑话内容"
    }},
    {{
      "关键词": "简短主题关键词", 
      "笑话内容": "方知衡会说的完整笑话内容"
    }},
    // ... 继续到第{batch_size}条
  ]
}}
```

# 笑话示例风格

## 数学逻辑冷幽默：
- 关键词: 数学逻辑买面包
- 笑话内容: 妻子让我去买面包，临走前叮嘱："如果看到卖西瓜的，就买一个。"结果我回家时只买了一个面包，妻子问："西瓜呢？"我回答："因为看到了卖西瓜的，所以只买了一个面包。"她说我想多了，我说这叫数学逻辑的严格执行。

## 物理学冷笑话：
- 关键词: 黑洞引力玩笑
- 笑话内容: 两个黑洞相遇，一个说："我觉得我们之间有引力。"另一个回答："别开玩笑了，我们连光都逃不出去，哪来的'玩笑'？"

## 哲学思辨笑话：
- 关键词: 苏格拉底学费
- 笑话内容: 苏格拉底问学生："什么是正义？"学生答："正义就是给每个人应得的东西。"苏格拉底又问："那如果一个疯子借了你的剑，你该还给他吗？"学生沉默，苏格拉底微笑："所以正义还需要智慧——但现在，你能先把我的学费还我吗？"

## 毒奶体质自嘲：
- 关键词: 墨菲定律天气
- 笑话内容: 我今天出门前看天气很好，跟同事说："今天肯定不会下雨，我都没带伞。"结果下午就开始下雨了。同事说我又乌鸦嘴了，我解释："这不是乌鸦嘴，这是墨菲定律的个人化验证——凡是可能出错的事，在我这里都会出错。"

# 重要提醒
1. **简化格式**：只要关键词和笑话内容，不要复杂的字段
5. **JSON格式**：确保JSON格式正确

请开始创作这些简洁的高质量知识梗笑话。
"""
        
        # 调用LLM生成笑话
        if llm:
            try:
                from core.types import Message, MessageRole
                message = Message(role=MessageRole.USER, content=generation_prompt)
                messages = [message]
                
                logger.info(f"笑话生成批次 {current_batch_index + 1}: 开始LLM调用")
                
                # 流式调用LLM
                final_content = ""
                async for chunk_data in llm.stream_generate(
                    messages, 
                    mode="think",
                    return_dict=True
                ):
                    content_part = chunk_data.get("content", "")
                    final_content += content_part
                
                logger.info(f"批次 {current_batch_index + 1} LLM生成完成，内容长度: {len(final_content)}")
                        
            except Exception as e:
                error_msg = f"批次 {current_batch_index + 1} LLM调用失败: {str(e)}"
                logger.error(error_msg, exc_info=True)
                raise Exception(error_msg)
        else:
            raise Exception("LLM未初始化")
        
        # 解析JSON结果
        jokes_data = None
        try:
            json_content = self._extract_json_from_content(final_content)
            from parsers.json_parser import JSONParser
            parser = JSONParser()
            parsed_result = parser.parse(json_content)
            
            if parsed_result and 'jokes' in parsed_result:
                jokes_data = parsed_result
                generated_jokes = jokes_data.get('jokes', [])
                logger.info(f"批次 {current_batch_index + 1} 成功解析，包含 {len(generated_jokes)} 条笑话")
                
                if workflow_chat:
                    await workflow_chat.add_node_message(
                        "笑话生成",
                        f"✅ 批次 {current_batch_index + 1} 生成完成（{len(generated_jokes)}条笑话）",
                        "success"
                    )
            else:
                raise Exception(f"批次解析失败：缺少jokes字段")
                
        except Exception as parse_error:
            logger.error(f"批次 {current_batch_index + 1} JSON解析失败: {parse_error}")
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "笑话生成",
                    f"⚠️ 批次 {current_batch_index + 1} 解析失败，跳过",
                    "warning"
                )
            jokes_data = None
        
        # 构建输出数据
        output_data = input_data.copy()
        output_data['generated_jokes'] = jokes_data.get('jokes', []) if jokes_data else []
        output_data['current_batch_index'] = current_batch_index + 1
        
        print(f"✅ 批次 {current_batch_index + 1} 笑话生成完成")
        yield output_data
    
    def _extract_json_from_content(self, content: str) -> str:
        """从生成内容中提取JSON部分"""
        import re
        
        # 查找```json...```代码块
        json_pattern = r'```json\s*(.*?)\s*```'
        matches = re.findall(json_pattern, content, re.DOTALL | re.IGNORECASE)
        
        if matches:
            return matches[0].strip()
        
        # 如果没有代码块，尝试查找以{开头}结尾的内容
        json_pattern2 = r'\{.*\}'
        matches2 = re.findall(json_pattern2, content, re.DOTALL)
        
        if matches2:
            return matches2[0].strip()
        
        return content.strip()


class QualityCheckNode(BaseNode):
    """质量检查节点 - 检查生成的笑话质量和人设符合度"""
    
    def __init__(self):
        super().__init__(name="quality_check", stream=True)
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行质量检查节点 - 非流式版本"""
        final_result = None
        async for result in self.execute_stream(input_data):
            final_result = result
        return final_result or input_data
    
    async def execute_stream(self, input_data: Dict[str, Any]):
        """流式执行质量检查节点"""
        print("🔍 开始质量检查...")
        
        workflow_chat = input_data.get('workflow_chat')
        generated_jokes = input_data.get('generated_jokes', [])
        
        if not generated_jokes:
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "质量检查",
                    "⚠️ 没有笑话需要检查",
                    "warning"
                )
            yield input_data
            return
        
        if workflow_chat:
            await workflow_chat.add_node_message(
                "质量检查",
                f"正在检查{len(generated_jokes)}条笑话的质量...",
                "progress"
            )
        
        # 质量检查逻辑
        checked_jokes = []
        filtered_count = 0
        
        for joke in generated_jokes:
            try:
                # 基本字段检查
                required_fields = ['joke_id', 'category', 'setup', 'punchline']
                if not all(field in joke and joke[field] for field in required_fields):
                    filtered_count += 1
                    continue
                
                # 内容长度检查
                setup = joke.get('setup', '')
                punchline = joke.get('punchline', '')
                
                if len(setup) < 10 or len(punchline) < 5:
                    filtered_count += 1
                    continue
                
                if len(setup) > 300 or len(punchline) > 200:
                    filtered_count += 1
                    continue
                
                # 内容健康性检查（简单关键词过滤）
                sensitive_words = ['政治', '宗教', '种族', '色情', '暴力']
                content_check = setup + punchline
                if any(word in content_check for word in sensitive_words):
                    filtered_count += 1
                    continue
                
                # 通过检查的笑话
                joke['quality_score'] = self._calculate_quality_score(joke)
                checked_jokes.append(joke)
                
            except Exception as e:
                logger.warning(f"检查笑话时出错: {e}")
                filtered_count += 1
                continue
        
        if workflow_chat:
            await workflow_chat.add_node_message(
                "质量检查",
                f"✅ 质量检查完成：{len(checked_jokes)}条通过，{filtered_count}条被过滤",
                "success"
            )
        
        # 按质量分数排序
        checked_jokes.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
        
        output_data = input_data.copy()
        output_data['checked_jokes'] = checked_jokes
        output_data['filtered_count'] = filtered_count
        
        logger.info(f"✅ 质量检查完成，{len(checked_jokes)}条笑话通过检查")
        yield output_data
    
    def _calculate_quality_score(self, joke: Dict[str, Any]) -> int:
        """计算笑话质量分数"""
        score = 50  # 基础分数
        
        # 长度合理性加分
        setup_len = len(joke.get('setup', ''))
        punchline_len = len(joke.get('punchline', ''))
        
        if 50 <= setup_len <= 150:
            score += 10
        if 20 <= punchline_len <= 100:
            score += 10
        
        # 人设特征加分
        traits = joke.get('character_traits', [])
        if len(traits) >= 2:
            score += 15
        
        # 标签丰富度加分
        tags = joke.get('tags', [])
        if len(tags) >= 3:
            score += 10
        
        # 内容原创性判断（简单实现）
        if '方知衡' in joke.get('setup', '') or '方知衡' in joke.get('punchline', ''):
            score += 5
        
        return min(score, 100)


class JokeDatabaseSaveNode(BaseNode):
    """数据库保存节点 - 将检查过的笑话保存到PostgreSQL"""
    
    def __init__(self):
        super().__init__(name="joke_database_save", stream=True)
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行数据库保存节点 - 非流式版本"""
        final_result = None
        async for result in self.execute_stream(input_data):
            final_result = result
        return final_result or input_data
    
    async def execute_stream(self, input_data: Dict[str, Any]):
        """流式执行数据库保存节点"""
        print("💾 开始保存到PostgreSQL数据库...")
        
        workflow_chat = input_data.get('workflow_chat')
        checked_jokes = input_data.get('checked_jokes', [])
        pg_config = input_data.get('pg_config', {})
        config = input_data.get('config', {})
        
        # 检查数据库是否可用
        if config.get('database_available', True) == False:
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "数据库保存",
                    "⚠️ 数据库不可用，跳过保存步骤",
                    "warning"
                )
            
            output_data = input_data.copy()
            output_data.update({
                'save_success': False,
                'save_message': "数据库不可用，跳过保存"
            })
            yield output_data
            return
        
        if not checked_jokes:
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "数据库保存",
                    "⚠️ 没有笑话需要保存",
                    "warning"
                )
            yield input_data
            return
        
        if workflow_chat:
            await workflow_chat.add_node_message(
                "数据库保存",
                f"正在将{len(checked_jokes)}条笑话保存到数据库...",
                "progress"
            )
        
        try:
            # 连接数据库
            conn = psycopg2.connect(**pg_config)
            cursor = conn.cursor()
            
            # 批量插入笑话
            success_count = 0
            duplicate_count = 0
            error_count = 0
            
            for joke in checked_jokes:
                try:
                    insert_sql = """
                    INSERT INTO jokes (
                        joke_id, category, difficulty_level, humor_style,
                        setup, punchline, context, character_traits, tags, rating
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (joke_id) DO NOTHING
                    """
                    
                    cursor.execute(insert_sql, (
                        joke.get('joke_id'),
                        joke.get('category'),
                        joke.get('difficulty_level', '中等'),
                        joke.get('humor_style', '冷幽默'),
                        joke.get('setup'),
                        joke.get('punchline'),
                        joke.get('context', ''),
                        joke.get('character_traits', []),
                        joke.get('tags', []),
                        joke.get('quality_score', 50)
                    ))
                    
                    if cursor.rowcount > 0:
                        success_count += 1
                    else:
                        duplicate_count += 1
                        
                except Exception as e:
                    logger.warning(f"保存单条笑话失败: {e}")
                    error_count += 1
                    continue
            
            # 提交事务
            conn.commit()
            cursor.close()
            conn.close()
            
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "数据库保存",
                    f"✅ 保存完成：{success_count}条成功，{duplicate_count}条重复，{error_count}条失败",
                    "success"
                )
            
            output_data = input_data.copy()
            output_data.update({
                'save_success': True,
                'saved_count': success_count,
                'duplicate_count': duplicate_count,
                'error_count': error_count,
                'save_message': f"成功保存{success_count}条笑话到数据库"
            })
            
            logger.info(f"✅ 数据库保存完成：{success_count}条成功保存")
            yield output_data
            
        except Exception as e:
            logger.error(f"数据库保存失败: {e}")
            if workflow_chat:
                await workflow_chat.add_node_message(
                    "数据库保存",
                    f"❌ 保存失败: {str(e)}",
                    "error"
                )
            
            output_data = input_data.copy()
            output_data.update({
                'save_success': False,
                'save_message': f"保存失败：{str(e)}"
            })
            yield output_data 