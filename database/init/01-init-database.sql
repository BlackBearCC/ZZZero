-- -*- coding: utf-8 -*-
-- PostgreSQL 数据库初始化脚本
-- @author leo
-- @description 初始化ZZZero AI Agent Framework数据库结构
-- @tables
--   - stories - 剧情主表
--   - scenes - 小节详情表  
--   - character_stories - 角色剧情关联表
--   - story_tags - 剧情标签表
--   - schedules - 日程安排表
--   - characters - 角色信息表
-- @indexes 创建必要的索引提升查询性能
-- @extensions 启用必要的PostgreSQL扩展

-- 启用必要的扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- 用于模糊搜索

-- 设置时区
SET timezone = 'Asia/Shanghai';

-- 创建剧情相关表
CREATE TABLE IF NOT EXISTS stories (
    id SERIAL PRIMARY KEY,
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建小节详情表
CREATE TABLE IF NOT EXISTS scenes (
    id SERIAL PRIMARY KEY,
    story_id VARCHAR(100) NOT NULL,
    scene_id VARCHAR(100) NOT NULL,
    scene_title VARCHAR(500) NOT NULL,
    scene_content TEXT NOT NULL,
    location VARCHAR(200),
    participants TEXT,  -- JSON格式存储参与角色
    scene_order INTEGER DEFAULT 0,
    scene_metadata TEXT,  -- JSON格式存储额外元数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (story_id) REFERENCES stories(story_id) ON DELETE CASCADE,
    UNIQUE(story_id, scene_id)
);

-- 创建角色剧情关联表
CREATE TABLE IF NOT EXISTS character_stories (
    id SERIAL PRIMARY KEY,
    character_name VARCHAR(100) NOT NULL,
    story_id VARCHAR(100) NOT NULL,
    relationship_type VARCHAR(50),
    importance_level INTEGER DEFAULT 1,  -- 1-5级重要程度
    character_role VARCHAR(100),  -- 在剧情中的角色定位
    interaction_count INTEGER DEFAULT 0,  -- 互动次数
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (story_id) REFERENCES stories(story_id) ON DELETE CASCADE,
    UNIQUE(character_name, story_id)
);

-- 创建剧情标签表
CREATE TABLE IF NOT EXISTS story_tags (
    id SERIAL PRIMARY KEY,
    story_id VARCHAR(100) NOT NULL,
    tag_name VARCHAR(50) NOT NULL,
    tag_type VARCHAR(30) DEFAULT 'general',  -- general, emotion, theme, setting
    tag_weight DECIMAL(3,2) DEFAULT 1.0,     -- 标签权重
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (story_id) REFERENCES stories(story_id) ON DELETE CASCADE,
    UNIQUE(story_id, tag_name)
);

-- 创建日程安排表
CREATE TABLE IF NOT EXISTS schedules (
    id SERIAL PRIMARY KEY,
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (related_story_id) REFERENCES stories(story_id) ON DELETE SET NULL
);

-- 创建角色信息表
CREATE TABLE IF NOT EXISTS characters (
    id SERIAL PRIMARY KEY,
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建地点信息表
CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    location_id VARCHAR(100) UNIQUE NOT NULL,
    location_name VARCHAR(200) NOT NULL,
    location_type VARCHAR(50),  -- 住宅、商业、教育、娱乐等
    district VARCHAR(100),
    address TEXT,
    description TEXT,
    amenities TEXT,  -- JSON格式存储设施信息
    atmosphere VARCHAR(100),
    location_tags TEXT,  -- JSON格式存储标签
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

-- 创建全文搜索索引
CREATE INDEX IF NOT EXISTS idx_stories_search ON stories USING gin(to_tsvector('chinese', story_name || ' ' || COALESCE(story_overview, '')));
CREATE INDEX IF NOT EXISTS idx_scenes_search ON scenes USING gin(to_tsvector('chinese', scene_title || ' ' || scene_content));

-- 创建触发器自动更新 updated_at 字段
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为需要的表创建更新时间触发器
CREATE TRIGGER update_stories_updated_at BEFORE UPDATE ON stories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_scenes_updated_at BEFORE UPDATE ON scenes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_schedules_updated_at BEFORE UPDATE ON schedules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_characters_updated_at BEFORE UPDATE ON characters
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_locations_updated_at BEFORE UPDATE ON locations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 插入初始数据（可选）
-- INSERT INTO characters (character_id, character_name, character_description) VALUES 
-- ('CHAR_001', '方知衡', '大学天文系教授、研究员，主角');

-- 创建视图便于查询
CREATE OR REPLACE VIEW story_with_characters AS
SELECT 
    s.*,
    array_agg(cs.character_name) as involved_characters,
    count(sc.id) as scene_count
FROM stories s
LEFT JOIN character_stories cs ON s.story_id = cs.story_id
LEFT JOIN scenes sc ON s.story_id = sc.story_id
GROUP BY s.id;

-- 权限设置（生产环境中根据需要调整）
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO zzzero_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO zzzero_user;