-- -*- coding: utf-8 -*-
-- SQLite 数据库初始化脚本
-- @author leo
-- @description 初始化ZZZero AI Agent Framework数据库结构
-- @tables
--   - stories - 剧情主表
--   - scenes - 小节详情表  
--   - character_stories - 角色剧情关联表
--   - story_tags - 剧情标签表
--   - schedules - 日程安排表
--   - characters - 角色信息表
--   - locations - 地点信息表
-- @indexes 创建必要的索引提升查询性能

-- 启用外键约束
PRAGMA foreign_keys = ON;

-- 创建剧情相关表
CREATE TABLE IF NOT EXISTS stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id VARCHAR(100) UNIQUE NOT NULL,
    story_name VARCHAR(500) NOT NULL,
    story_overview TEXT,
    story_type VARCHAR(50) DEFAULT 'daily_life',
    story_length VARCHAR(20) DEFAULT 'medium',
    relationship_depth VARCHAR(20) DEFAULT 'casual',
    protagonist VARCHAR(100) DEFAULT '方知衡',
    selected_characters TEXT,  -- JSON格式存储角色列表
    selected_locations TEXT,   -- JSON格式存储地点列表
    story_summary TEXT,        -- JSON格式存储剧情总结
    main_conflict TEXT,
    emotional_development TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 创建小节详情表
CREATE TABLE IF NOT EXISTS scenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id VARCHAR(100) NOT NULL,
    scene_id VARCHAR(100) NOT NULL,
    scene_title VARCHAR(500) NOT NULL,
    scene_content TEXT NOT NULL,
    location VARCHAR(200),
    participants TEXT,  -- JSON格式存储参与角色
    scene_order INTEGER DEFAULT 0,
    scene_metadata TEXT,  -- JSON格式存储额外元数据
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (story_id) REFERENCES stories(story_id) ON DELETE CASCADE,
    UNIQUE(story_id, scene_id)
);

-- 创建角色剧情关联表
CREATE TABLE IF NOT EXISTS character_stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_name VARCHAR(100) NOT NULL,
    story_id VARCHAR(100) NOT NULL,
    relationship_type VARCHAR(50),
    importance_level INTEGER DEFAULT 1,  -- 1-5级重要程度
    character_role VARCHAR(100),  -- 在剧情中的角色定位
    interaction_count INTEGER DEFAULT 0,  -- 互动次数
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (story_id) REFERENCES stories(story_id) ON DELETE CASCADE,
    UNIQUE(character_name, story_id)
);

-- 创建剧情标签表
CREATE TABLE IF NOT EXISTS story_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id VARCHAR(100) NOT NULL,
    tag_name VARCHAR(50) NOT NULL,
    tag_type VARCHAR(30) DEFAULT 'general',  -- general, emotion, theme, setting
    tag_weight DECIMAL(3,2) DEFAULT 1.0,     -- 标签权重
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (story_id) REFERENCES stories(story_id) ON DELETE CASCADE,
    UNIQUE(story_id, tag_name)
);

-- 创建日程安排表
CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id VARCHAR(100) UNIQUE NOT NULL,
    protagonist VARCHAR(100) DEFAULT '方知衡',
    schedule_date DATE NOT NULL,
    time_slot VARCHAR(20) NOT NULL,  -- 上午、下午、晚上等
    start_time TIME,
    end_time TIME,
    activity_title VARCHAR(500) NOT NULL,
    activity_description TEXT,
    location VARCHAR(200),
    participants TEXT,  -- JSON格式存储参与角色
    activity_type VARCHAR(50) DEFAULT 'daily',  -- daily, work, social, leisure
    mood VARCHAR(30),
    weather VARCHAR(50),
    special_notes TEXT,
    related_story_id VARCHAR(100),  -- 关联的剧情ID
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (related_story_id) REFERENCES stories(story_id) ON DELETE SET NULL
);

-- 创建角色信息表
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id VARCHAR(100) UNIQUE NOT NULL,
    character_name VARCHAR(100) NOT NULL,
    character_description TEXT,
    personality TEXT,
    background TEXT,
    relationships TEXT,  -- JSON格式存储与其他角色的关系
    appearance TEXT,
    occupation VARCHAR(100),
    residence VARCHAR(200),
    age_range VARCHAR(20),
    character_tags TEXT,  -- JSON格式存储标签
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 创建地点信息表
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id VARCHAR(100) UNIQUE NOT NULL,
    location_name VARCHAR(200) NOT NULL,
    location_type VARCHAR(50),  -- 住宅、商业、教育、娱乐等
    district VARCHAR(100),
    address TEXT,
    description TEXT,
    amenities TEXT,  -- JSON格式存储设施信息
    atmosphere VARCHAR(100),
    location_tags TEXT,  -- JSON格式存储标签
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引提升查询性能
CREATE INDEX IF NOT EXISTS idx_stories_story_id ON stories(story_id);
CREATE INDEX IF NOT EXISTS idx_stories_type ON stories(story_type);
CREATE INDEX IF NOT EXISTS idx_stories_created_at ON stories(created_at);

CREATE INDEX IF NOT EXISTS idx_scenes_story_id ON scenes(story_id);
CREATE INDEX IF NOT EXISTS idx_scenes_order ON scenes(scene_order);

CREATE INDEX IF NOT EXISTS idx_character_stories_character ON character_stories(character_name);
CREATE INDEX IF NOT EXISTS idx_character_stories_story ON character_stories(story_id);

CREATE INDEX IF NOT EXISTS idx_schedules_date ON schedules(schedule_date);
CREATE INDEX IF NOT EXISTS idx_schedules_protagonist ON schedules(protagonist);
CREATE INDEX IF NOT EXISTS idx_schedules_type ON schedules(activity_type);

CREATE INDEX IF NOT EXISTS idx_characters_name ON characters(character_name);
CREATE INDEX IF NOT EXISTS idx_locations_name ON locations(location_name);
CREATE INDEX IF NOT EXISTS idx_locations_district ON locations(district);

-- 创建全文搜索索引（SQLite FTS5）
-- 注意：SQLite的FTS语法与PostgreSQL不同
CREATE VIRTUAL TABLE IF NOT EXISTS stories_fts USING fts5(
    story_id,
    story_name,
    story_overview,
    content='stories',
    content_rowid='id'
);

CREATE VIRTUAL TABLE IF NOT EXISTS scenes_fts USING fts5(
    story_id,
    scene_title,
    scene_content,
    content='scenes',
    content_rowid='id'
);

-- 创建触发器自动更新 updated_at 字段
-- SQLite 触发器语法
CREATE TRIGGER IF NOT EXISTS update_stories_updated_at 
AFTER UPDATE ON stories
BEGIN
    UPDATE stories SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_scenes_updated_at 
AFTER UPDATE ON scenes
BEGIN
    UPDATE scenes SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_schedules_updated_at 
AFTER UPDATE ON schedules
BEGIN
    UPDATE schedules SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_characters_updated_at 
AFTER UPDATE ON characters
BEGIN
    UPDATE characters SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_locations_updated_at 
AFTER UPDATE ON locations
BEGIN
    UPDATE locations SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- 创建触发器维护FTS索引
CREATE TRIGGER IF NOT EXISTS stories_fts_insert AFTER INSERT ON stories
BEGIN
    INSERT INTO stories_fts(rowid, story_id, story_name, story_overview)
    VALUES (NEW.id, NEW.story_id, NEW.story_name, NEW.story_overview);
END;

CREATE TRIGGER IF NOT EXISTS stories_fts_delete AFTER DELETE ON stories
BEGIN
    DELETE FROM stories_fts WHERE rowid = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS stories_fts_update AFTER UPDATE ON stories
BEGIN
    DELETE FROM stories_fts WHERE rowid = OLD.id;
    INSERT INTO stories_fts(rowid, story_id, story_name, story_overview)
    VALUES (NEW.id, NEW.story_id, NEW.story_name, NEW.story_overview);
END;

CREATE TRIGGER IF NOT EXISTS scenes_fts_insert AFTER INSERT ON scenes
BEGIN
    INSERT INTO scenes_fts(rowid, story_id, scene_title, scene_content)
    VALUES (NEW.id, NEW.story_id, NEW.scene_title, NEW.scene_content);
END;

CREATE TRIGGER IF NOT EXISTS scenes_fts_delete AFTER DELETE ON scenes
BEGIN
    DELETE FROM scenes_fts WHERE rowid = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS scenes_fts_update AFTER UPDATE ON scenes
BEGIN
    DELETE FROM scenes_fts WHERE rowid = OLD.id;
    INSERT INTO scenes_fts(rowid, story_id, scene_title, scene_content)
    VALUES (NEW.id, NEW.story_id, NEW.scene_title, NEW.scene_content);
END;

-- 插入初始数据（可选）
-- INSERT INTO characters (character_id, character_name, character_description) VALUES 
-- ('CHAR_001', '方知衡', '大学天文系教授、研究员，主角');

-- 创建视图便于查询
CREATE VIEW IF NOT EXISTS story_with_characters AS
SELECT 
    s.*,
    GROUP_CONCAT(cs.character_name) as involved_characters,
    COUNT(DISTINCT sc.id) as scene_count
FROM stories s
LEFT JOIN character_stories cs ON s.story_id = cs.story_id
LEFT JOIN scenes sc ON s.story_id = sc.story_id
GROUP BY s.id;