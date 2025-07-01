# 📊 数据库管理系统使用指南

## 🎯 概述

ZZZero项目现已集成完整的SQLite数据库管理系统，用于存储和管理剧情数据、角色信息等。数据库系统具有以下特点：

- ✅ **数据持久化**：剧情数据永久保存，不会丢失
- ✅ **关系查询**：支持按角色、类型等多维度查询
- ✅ **可视化管理**：前端界面支持增删改查操作
- ✅ **数据导出**：支持CSV、JSON格式导出
- ✅ **扩展性强**：支持未来添加更多数据类型

## 🏗️ 架构设计

### 目录结构
```
database/
├── __init__.py                 # 模块初始化
├── managers/
│   ├── base_manager.py        # 通用数据库管理基类
│   ├── story_manager.py       # 剧情专用管理器
│   └── character_manager.py   # 角色专用管理器
```

### 数据表设计

#### 1. stories表（剧情主表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键ID |
| story_id | TEXT | 剧情唯一标识 |
| story_name | TEXT | 剧情名称 |
| story_type | TEXT | 剧情类型 |
| protagonist | TEXT | 主角名称 |
| selected_characters | TEXT | 参与角色（JSON） |
| selected_locations | TEXT | 地点信息（JSON） |
| main_conflict | TEXT | 主要冲突 |
| created_at | TIMESTAMP | 创建时间 |

#### 2. scenes表（小节详情表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键ID |
| story_id | TEXT | 关联剧情ID |
| scene_id | TEXT | 小节唯一标识 |
| scene_title | TEXT | 小节标题 |
| scene_content | TEXT | 小节内容 |
| location | TEXT | 发生地点 |
| participants | TEXT | 参与角色（JSON） |
| scene_order | INTEGER | 小节顺序 |

#### 3. character_stories表（角色剧情关联表）
| 字段 | 类型 | 说明 |
|------|------|------|
| character_name | TEXT | 角色名称 |
| story_id | TEXT | 关联剧情ID |
| importance_level | INTEGER | 重要程度（1-5级） |
| interaction_count | INTEGER | 互动次数 |
| character_role | TEXT | 角色定位 |

#### 4. story_tags表（剧情标签表）
| 字段 | 类型 | 说明 |
|------|------|------|
| story_id | TEXT | 关联剧情ID |
| tag_name | TEXT | 标签名称 |
| tag_category | TEXT | 标签分类 |

## 🚀 使用方法

### 1. 生成剧情并自动保存
在剧情生成工作流中：
1. 配置剧情参数（角色、地点、类型等）
2. 执行工作流生成剧情
3. 数据自动保存到SQLite数据库
4. 同时生成CSV导出文件

### 2. 前端数据库管理

访问Web界面的"📊 数据库管理"标签页：

#### 📚 剧情管理
- **查看剧情列表**：显示所有已生成的剧情
- **筛选搜索**：按角色、类型、主角等条件筛选
- **查看详情**：点击剧情查看完整小节内容
- **删除剧情**：移除不需要的剧情数据

#### 👥 角色管理
- **角色统计**：查看各角色的剧情参与统计
- **相关剧情**：按角色查看所有相关剧情
- **重要度分析**：了解角色在剧情中的重要程度

#### 🛠️ 数据库操作
- **数据导出**：导出CSV或JSON格式文件
- **数据备份**：创建数据库备份文件
- **数据库优化**：清理和优化数据库性能

#### 📈 统计信息
- **基础统计**：剧情总数、小节总数、角色数量
- **分类统计**：按类型、主角的剧情分布
- **活跃角色**：最常出现的角色排行

### 3. 程序化访问

#### 导入数据库管理器
```python
from database import story_manager, character_manager

# 获取剧情统计
stats = story_manager.get_story_statistics()

# 按角色查询剧情
character_stories = story_manager.get_character_stories("方知衡")

# 获取剧情小节
scenes = story_manager.get_story_scenes("STORY_001")
```

#### 保存剧情数据
```python
# 剧情数据格式
story_data = {
    "剧情列表": [
        {
            "剧情ID": "STORY_001",
            "剧情名称": "剧情名称",
            "剧情小节": [
                {
                    "小节ID": "SCENE_001",
                    "小节标题": "标题",
                    "小节内容": "内容",
                    "地点": "地点",
                    "参与角色": ["角色1", "角色2"]
                }
            ]
        }
    ]
}

# 配置信息
config = {
    "story_type": "daily_life",
    "protagonist": "方知衡",
    "selected_characters": ["角色1"],
    "selected_locations": ["地点1"]
}

# 保存到数据库
success = story_manager.save_story_data(story_data, config)
```

#### 查询和筛选
```python
# 多条件筛选
filters = {
    "story_type": "daily_life",
    "character_name": "方知衡",
    "created_after": "2025-01-01"
}
stories = story_manager.get_stories_by_filter(filters)

# 导出数据
csv_path = story_manager.export_story_data(format='csv')
json_path = story_manager.export_story_data(format='json')
```

## 📁 数据库文件位置

- **主数据库**：`workspace/databases/story.db`
- **备份文件**：`workspace/backups/`
- **导出文件**：`workspace/exports/`

## 🔧 维护操作

### 数据库清理优化
```python
story_manager.vacuum_database()
```

### 数据备份
```python
backup_path = story_manager.backup_table('stories')
```

### 获取数据库信息
```python
db_info = story_manager.get_database_info()
```

## 🎯 最佳实践

1. **定期备份**：重要数据定期备份到安全位置
2. **标签管理**：利用自动生成的标签进行分类管理
3. **角色追踪**：使用角色查询功能追踪角色发展
4. **数据导出**：定期导出数据用于分析或备份
5. **性能优化**：大量数据时定期执行数据库清理

## 🆘 故障排除

### 常见问题

1. **导入错误**：确保项目根目录在Python路径中
2. **权限问题**：确保workspace目录有读写权限
3. **数据库锁定**：避免同时多个进程访问数据库

### 重置数据库
如需重置，删除数据库文件即可：
```bash
rm workspace/databases/story.db
```

下次启动时会自动重新创建空数据库。

## 🚀 扩展开发

### 添加新的管理器
1. 继承`DatabaseManager`基类
2. 实现`_init_database()`方法创建表结构
3. 添加业务特定的方法
4. 在`database/__init__.py`中导出

### 自定义查询
利用`execute_query()`方法执行自定义SQL：
```python
results = story_manager.execute_query(
    "SELECT * FROM stories WHERE created_at > ?",
    ("2025-01-01",)
)
```

## 📞 技术支持

如有问题或建议，请参考项目文档或提交Issue。

---

✨ **数据库系统已就绪，享受高效的剧情数据管理体验！** ✨ 