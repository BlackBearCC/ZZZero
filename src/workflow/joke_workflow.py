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

        self.current_config = {

            'batch_size': 50,  # 每批生成的笑话数量
            'total_target': 1000,  # 总目标数量
            'joke_categories': [
                '哲学日常梗', '科学双关梗', '逻辑生活梗', 
                '文字游戏梗', '生活科学梗', '反差幽默梗'
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
        
        # 初始化数据库
        self._init_database()
    

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
        database_save_node = JokeDatabaseSaveNode()  # 数据库保存节点
        
        # 添加节点到图
        self.graph.add_node("theme_planning", theme_planning_node)
        self.graph.add_node("joke_generate", joke_generate_node)
        self.graph.add_node("database_save", database_save_node)
        
        # 定义节点连接关系
        self.graph.add_edge("theme_planning", "joke_generate")
        self.graph.add_edge("joke_generate", "database_save")
        
        # 设置入口点
        self.graph.set_entry_point("theme_planning")
        
        return self.graph
    
    async def execute_workflow_stream(self, config: Dict[str, Any], workflow_chat):
        """流式执行笑话生成工作流"""
        try:
            # 准备初始输入
            initial_input = {
                'config': config,
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
        batch_size = input_data.get('batch_size', 50)
        total_target = input_data.get('total_target', 1000)
        joke_categories = input_data.get('joke_categories', [])
        
        if workflow_chat:
            await workflow_chat.add_node_message(
                "主题规划",
                f"正在规划{total_target}条笑话的主题分布...",
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
        
        generation_prompt = f"""
请创作{batch_size}条真正好笑的笑话，重点是要让人笑出来！

# 目标受众特征
- **理性思维**：喜欢逻辑清晰的幽默，不喜欢无厘头
- **高知背景**：能理解一些知识背景，但不是为了炫耀知识
- **内敛性格**：偏爱巧妙的笑点，不喜欢大吼大叫式的搞笑
- **冷幽默偏好**：欣赏需要反应一下才明白的笑点

# 本批次创作重点
- 主题类别：{', '.join(batch_categories)}
- 重点特征：{focus_trait}
- 幽默风格：{humor_emphasis}

# 笑话创作原则

## 笑点要求
1. **真正好笑**：第一要务是好笑，不是显示知识
2. **有巧思**：笑点要巧妙，有"啊哈"的感觉
3. **逻辑合理**：笑点建立在合理的逻辑基础上
4. **不做作**：自然流畅，不生硬
5. **有反转**：有意想不到的转折

## 避免的内容
- 为了显示知识而强行插入专业术语
- 过于学究气，失去幽默感
- 低俗或哗众取宠的内容

## 笑话特征
1. **笑点清晰**：让人能明确知道哪里好笑
2. **适度智慧**：有一定思考价值，但不炫技
3. **表达自然**：语言流畅，不别扭

## 笑话结构要求
每条笑话包含：
- **关键词**：搜索用关键词组，用逗号分隔，包含：主题，适用场合，情境等，方便检索，不要重复笑话内容
- **笑话内容**：完整的笑话，包含情境和笑点，100-200字

## 内容原则
1. **绿色健康**：内容积极向上，适合所有年龄段
2. **避免敏感**：不涉及政治、宗教、种族等敏感话题
3. **符合品味**：符合高知群体的审美标准
4. **贴近认知**：基于理性思考，有认知价值
5. **原创性**：避免俗套，确保新颖性

## 笑话创作方向
不限制具体类型，只要符合以下要求即可：
- 轻松有趣，让人想笑
- 有一定智慧含量，但不炫耀
- 语言自然流畅
- 适合在合适场合分享
- 符合爱上网年轻人的口味，有网感
- 让人听完笑话有一种 你牛逼的感觉

## 好笑话的标准
1. **简单好笑**：让人一听就笑，不需要解释
2. **巧妙转折**：有意想不到但合理的转折点
3. **语言轻松**：表达自然流畅，不生硬
4. **适度智慧**：有一点知识背景，但不炫耀
5. **朗朗上口**：容易记住和转述给别人



# 笑话示例风格

## 示例1：
- 关键词: 哲学课堂,师生对话,学费催收,古希腊
- 笑话内容: 苏格拉底问学生："什么是正义？"学生答："正义就是给每个人应得的东西。"苏格拉底又问："那如果一个疯子借了你的剑，你该还给他吗？"学生沉默，苏格拉底微笑："所以正义还需要智慧——但现在，你能先把我的学费还我吗？"

## 示例2：
- 关键词: 文学名句,程序员,编程术语,跨界对话
- 笑话内容: 莎士比亚说："To be or not to be，that's a question."程序员接话："To bug or not to bug，that's a syntax error."

## 示例3：
- 关键词: 天体物理,双关语,引力定律,科学幽默
- 笑话内容: 两个黑洞相遇，一个说："我觉得我们之间有引力。"另一个回答："别开玩笑了，我们连光都逃不出去，哪来的'玩笑'？"

## 示例4：
- 关键词: 情侣对话,物理学家,相对论,理科男
- 笑话内容: 物理学家对女朋友说："你就像光一样。"女朋友很开心："因为我照亮了你的世界？"物理学家："不，因为时间在你身边会变慢。"


# 重要提醒
1. **关键词要实用**：关键词是为了搜索和分类，要包含主题、场合、情境等，不要重复笑话内容
2. **类型自由发挥**：不限制笑话类型，只要好笑、有趣、有一定智慧含量即可
3. **简洁有趣**：笑话要简短，一听就懂，一听就笑
4. **避免说教**：不要解释笑点，让笑话自己说话
5. **JSON格式**：确保JSON格式正确

# 输出格式
请按以下JSON格式输出{batch_size}条笑话，禁止输出任何其他内容：

```json
{{
  "jokes": [
    {{
      "关键词": "简短主题关键词",
      "笑话内容": "完整笑话内容"
    }},
    {{
      "关键词": "简短主题关键词", 
      "笑话内容": "完整笑话内容"
    }},
    // ... 继续到第{batch_size}条
  ]
}}
```
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
        generated_jokes = input_data.get('generated_jokes', [])
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
        
        if not generated_jokes:
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
                f"正在将{len(generated_jokes)}条笑话保存到数据库...",
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
            
            for joke in generated_jokes:
                try:
                    # 生成唯一ID
                    import uuid
                    joke_id = str(uuid.uuid4())[:8]
                    
                    insert_sql = """
                    INSERT INTO jokes (
                        joke_id, category, difficulty_level, humor_style,
                        setup, punchline, context, character_traits, tags, rating
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (joke_id) DO NOTHING
                    """
                    
                    cursor.execute(insert_sql, (
                        joke_id,
                        '自由创作',
                        '中等',
                        '冷幽默',
                        joke.get('关键词', ''),
                        joke.get('笑话内容', ''),
                        '',
                        [],
                        joke.get('关键词', '').split(','),
                        80
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


# 本地测试运行入口
async def main():
    """本地测试运行笑话生成工作流"""
    print("🎭 启动方知衡笑话生成工作流本地测试...")
    
    # 简单的模拟聊天界面
    class MockWorkflowChat:
        def __init__(self):
            self.current_node = ""
        
        async def add_node_message(self, node_name: str, message: str, status: str):
            print(f"[{node_name}] {status}: {message}")
        
        def _create_workflow_progress(self):
            return "<div>工作流进度</div>"
    
    try:
        # 配置LLM（如果有有效的API密钥）
        llm = None
        try:
            from llm.doubao import DoubaoLLM
            from core.types import LLMConfig
            
            # 这里使用测试配置，实际使用时需要替换为真实的API密钥
            llm_config = LLMConfig(
                provider="doubao",
                model_name="ep-20241230141654-5tvbr",
                api_key="b633a622-b5d0-4f16-a8a9-616239cf15d1",  # 替换为真实的API密钥
                api_base="https://ark.cn-beijing.volces.com/api/v3"
            )
            llm = DoubaoLLM(config=llm_config)
            print("✅ LLM配置成功")
        except Exception as e:
            print(f"⚠️ LLM配置失败，将跳过实际生成: {e}")
        
        # 初始化工作流
        workflow = JokeWorkflow(llm=llm)
        print("✅ 笑话工作流初始化完成")
        
        # 测试配置
        test_config = {
            'total_target': 10,  # 生成10条笑话测试
            'batch_size': 10,
            'joke_categories': [
                '哲学日常梗', '科学双关梗', '逻辑生活梗', 
                '文字游戏梗', '生活科学梗', '反差幽默梗'
            ],
            'database_available': False  # 跳过数据库保存
        }
        
        print(f"📊 测试配置: {test_config}")
        
        # 创建模拟聊天界面
        mock_chat = MockWorkflowChat()
        
        # 创建工作流图
        graph = await workflow.create_joke_graph()
        compiled_graph = graph.compile()
        print("✅ 工作流图创建完成")
        
        # 准备输入数据
        input_data = {
            'config': test_config,
            'batch_size': test_config['batch_size'],
            'total_target': test_config['total_target'],
            'joke_categories': test_config['joke_categories'],
            'difficulty_levels': ['简单', '中等', '复杂'],
            'humor_styles': ['冷幽默', '自嘲', '观察式', '反差萌'],
            'pg_config': {},
            'workflow_chat': mock_chat,
            'llm': llm
        }
        
        print("\n🚀 开始执行笑话生成工作流...")
        
        # 执行工作流
        final_result = None
        async for result in compiled_graph.stream(input_data):
            if result:
                final_result = result
        
        # 显示结果
        if final_result:
            print("\n✅ 工作流执行完成!")
            
            generated_jokes = final_result.get('generated_jokes', [])
            print(f"📝 生成笑话数量: {len(generated_jokes)}")
            
            if generated_jokes:
                print("\n🎭 生成的笑话示例:")
                for i, joke in enumerate(generated_jokes[:5], 1):  # 显示前5条
                    print(f"\n--- 笑话 {i} ---")
                    print(f"关键词: {joke.get('关键词', 'N/A')}")
                    print(f"内容: {joke.get('笑话内容', 'N/A')}")
                    print("-" * 50)
                
                # 保存到本地文件
                import json
                from datetime import datetime
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"workspace/local_test_jokes_{timestamp}.json"
                
                # 确保目录存在
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'config': test_config,
                        'generated_jokes': generated_jokes,
                        'total_count': len(generated_jokes),
                        'timestamp': timestamp
                    }, f, ensure_ascii=False, indent=2)
                
                print(f"\n💾 结果已保存到: {output_file}")
            
            else:
                print("⚠️ 没有生成笑话（可能是API密钥无效或网络问题）")
        
        else:
            print("❌ 工作流执行失败")
    
    except Exception as e:
        print(f"❌ 测试执行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    """直接运行此文件进行本地测试"""
    print("🎭 方知衡笑话生成工作流 - 本地测试模式")
    print("=" * 60)
    
    # 运行异步主函数
    asyncio.run(main())