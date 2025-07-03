# 笑话生成工作流使用指南

## 简介

这是一个基于方知衡人设的笑话生成工作流，能够根据主角的性格特点（理性严谨、内敛温和、毒奶体质、网络落伍等）生成符合人设的幽默内容。支持批量生成几千条不重样的笑话，并存储到PostgreSQL数据库中。

## 工作流架构

### 节点设计
1. **主题规划节点 (ThemePlanningNode)**：根据目标数量和人设特点制定主题分配计划
2. **笑话生成节点 (JokeGenerateNode)**：基于人设分批生成符合特点的笑话
3. **质量检查节点 (QualityCheckNode)**：检查生成笑话的质量和人设符合度
4. **数据库保存节点 (JokeDatabaseSaveNode)**：将检查过的笑话保存到PostgreSQL

### 数据流
```
主题规划 → 笑话生成 → 质量检查 → 数据库保存
```

## 功能特点

### 人设符合度
- **理性严谨**：用学术思维分析日常小事的反差幽默
- **内敛温和**：温和有礼貌的幽默方式，不说粗话
- **毒奶体质**：说好的不灵坏的灵，经常无意中"乌鸦嘴"
- **网络落伍**：对网络梗和流行语不熟悉产生的代沟笑话
- **古板认真**：用过于认真的态度对待小事形成反差
- **学者风范**：偶尔用专业术语解释生活现象
- **生活细致**：对细节的过度关注产生的幽默
- **温和吐槽**：以温和方式表达对某些现象的不理解

### 笑话类别
- 学术幽默：用学术思维解释日常
- 生活日常：生活中的小尴尬和小发现
- 毒奶体质：无意中说中坏事的情况
- 网络落伍：对新事物的不理解
- 古板认真：过度认真产生的反差
- 温和吐槽：温和的观察式幽默
- 理性分析：用理性思维分析荒唐事
- 意外反差：人设与行为的反差萌

## 快速开始

### 1. 环境准备

确保已安装必要的依赖：
```bash
pip install psycopg2-binary
```

### 2. 数据库设置

启动PostgreSQL服务，然后运行初始化脚本：
```bash
python init_jokes_database.py
```

这将创建：
- `jokes_db` 数据库
- `jokes` 表及相关索引
- 统计视图和触发器
- 示例数据

### 3. 配置LLM

在使用前需要配置有效的LLM API密钥，编辑测试脚本中的配置：
```python
llm_config = {
    'api_key': 'your_doubao_api_key_here',
    'model': 'ep-20241228203630-nqr7v',
    'base_url': 'https://ark.cn-beijing.volces.com/api/v3'
}
```

### 4. 运行测试

```bash
python test_joke_workflow.py
```

## 数据库结构

### jokes表字段

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL | 主键，自增ID |
| joke_id | VARCHAR(50) | 笑话唯一标识 |
| category | VARCHAR(50) | 笑话类别 |
| difficulty_level | VARCHAR(20) | 难度等级（简单/中等/复杂） |
| humor_style | VARCHAR(30) | 幽默风格（冷幽默/自嘲/观察式/反差萌） |
| setup | TEXT | 笑话铺垫部分 |
| punchline | TEXT | 笑话笑点部分 |
| context | TEXT | 笑话背景说明 |
| character_traits | TEXT[] | 体现的人设特征数组 |
| tags | TEXT[] | 相关标签数组 |
| rating | INTEGER | 质量评分（0-100） |
| is_used | BOOLEAN | 是否已使用 |
| use_count | INTEGER | 使用次数 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

### 统计视图 joke_stats

提供按类别、难度和风格的统计信息：
- 总数量
- 平均评分
- 已使用数量
- 未使用数量

## 配置参数

### 基础配置
```python
config = {
    'protagonist': '方知衡',        # 主角名称（固定）
    'batch_size': 50,              # 每批生成数量
    'total_target': 1000,          # 总目标数量
    'joke_categories': [           # 笑话类别
        '学术幽默', '生活日常', '毒奶体质', '网络落伍',
        '古板认真', '温和吐槽', '理性分析', '意外反差'
    ],
    'difficulty_levels': ['简单', '中等', '复杂'],
    'humor_styles': ['冷幽默', '自嘲', '观察式', '反差萌']
}
```

### 数据库配置
```python
pg_config = {
    'host': 'localhost',
    'port': 5432,
    'database': 'jokes_db',
    'user': 'postgres',
    'password': 'password'
}
```

## 使用示例

### 在Web界面中集成

如果要在现有的Web界面中使用，可以参考 `src/web/app.py` 的模式：

```python
from workflow.joke_workflow import JokeWorkflow

# 初始化工作流
joke_workflow = JokeWorkflow(llm=your_llm_instance)

# 执行生成
async for result in joke_workflow.execute_workflow_stream(config, workflow_chat):
    # 处理流式结果
    pass
```

### 直接批量生成

```python
import asyncio
from workflow.joke_workflow import JokeWorkflow
from llm.doubao import DoubaoLLM

async def generate_jokes():
    # 初始化LLM和工作流
    llm = DoubaoLLM(llm_config)
    workflow = JokeWorkflow(llm)
    
    # 配置参数
    config = {
        'batch_size': 100,
        'total_target': 1000,
        # ... 其他配置
    }
    
    # 执行生成（需要mock的workflow_chat）
    async for result in workflow.execute_workflow_stream(config, mock_chat):
        print("生成进度:", result)

# 运行
asyncio.run(generate_jokes())
```

## 质量控制

### 自动质量检查
- 字段完整性检查
- 内容长度合理性检查
- 敏感词过滤
- 健康内容检查

### 评分机制
根据以下因素计算质量分数（0-100）：
- 长度合理性（+20分）
- 人设特征丰富度（+15分）
- 标签完整性（+10分）
- 内容原创性（+5分）
- 基础分数：50分

### 人工审核
可以通过SQL查询进行人工审核：
```sql
-- 查看低评分笑话
SELECT * FROM jokes WHERE rating < 60 ORDER BY rating ASC;

-- 按类别查看
SELECT * FROM jokes WHERE category = '学术幽默' ORDER BY rating DESC;

-- 查看统计信息
SELECT * FROM joke_stats;
```

## 扩展功能

### 批量操作
```sql
-- 批量标记为已使用
UPDATE jokes SET is_used = true WHERE id IN (1,2,3);

-- 批量调整评分
UPDATE jokes SET rating = rating + 10 WHERE category = '毒奶体质';
```

### 导出功能
```sql
-- 导出高质量笑话
COPY (SELECT setup, punchline FROM jokes WHERE rating >= 80) TO '/path/to/high_quality_jokes.csv' CSV HEADER;
```

## 注意事项

1. **API密钥安全**：确保不要将API密钥提交到版本控制系统
2. **数据库连接**：确保PostgreSQL服务正在运行
3. **内容审核**：生成的内容需要进行人工审核确保合适性
4. **批次大小**：根据API限制调整batch_size，避免超时
5. **重复检查**：系统会自动处理重复的joke_id，但建议定期清理

## 问题排查

### 常见问题

1. **数据库连接失败**
   - 检查PostgreSQL服务状态
   - 验证连接参数是否正确
   - 确认数据库用户权限

2. **LLM调用失败**
   - 检查API密钥是否有效
   - 验证网络连接
   - 确认模型参数正确

3. **生成质量不佳**
   - 调整提示词中的人设描述
   - 修改质量检查标准
   - 增加人工审核环节

4. **性能问题**
   - 减小batch_size
   - 优化数据库索引
   - 增加并发控制

## 后续优化

1. **智能去重**：基于语义相似度的智能去重
2. **质量预测**：使用机器学习预测笑话质量
3. **用户反馈**：集成用户评分和反馈系统
4. **个性化生成**：根据用户喜好调整生成策略
5. **多语言支持**：支持生成其他语言的笑话

---

## 📈 v2.0 重大升级 (2025-01-03)

### 升级要点
- **笑话视角转换**：从"关于方知衡的笑话"升级为"方知衡会说的笑话"
- **高质量知识梗**：强调学术幽默的深度和巧妙性
- **第一人称叙述**：所有笑话都以"我"的角度，符合角色口吻
- **跨学科融合**：涵盖数学、物理、哲学、文学等多个学科知识点

### 笑话类型升级
- 数学逻辑梗：用严谨的逻辑思维解构日常对话
- 物理学梗：以物理概念巧妙类比生活现象
- 文学哲学梗：引用经典进行现代化幽默解读
- 学术生活梗：教授工作日常的温和自嘲
- 毒奶定律梗：将毒奶体质理论化、学术化
- 跨学科融合梗：用跨领域知识创造认知反差

### 示例效果
参考 `workspace/joke_examples_upgraded.json` 查看升级后的笑话示例，体验高质量学术幽默的魅力。

---

这个工作流设计简洁高效，专注于生成符合方知衡人设的高质量知识梗笑话。通过分批处理和质量控制，能够稳定生成大量不重样的学术幽默内容。 