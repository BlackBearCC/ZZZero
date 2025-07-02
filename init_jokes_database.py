"""
PostgreSQL数据库初始化脚本
为笑话生成工作流创建数据库和表结构
"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_database():
    """创建jokes_db数据库"""
    try:
        # 连接到默认的postgres数据库
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='postgres',
            user='postgres',
            password='password'
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # 检查数据库是否已存在
        cursor.execute("SELECT 1 FROM pg_database WHERE datname='jokes_db'")
        exists = cursor.fetchone()
        
        if not exists:
            cursor.execute('CREATE DATABASE jokes_db')
            logger.info("✅ 数据库 jokes_db 创建成功")
        else:
            logger.info("📋 数据库 jokes_db 已存在")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ 创建数据库失败: {e}")
        raise

def create_tables():
    """创建表结构"""
    try:
        # 连接到jokes_db数据库
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='jokes_db',
            user='postgres',
            password='password'
        )
        cursor = conn.cursor()
        
        # 创建笑话表
        create_jokes_table_sql = """
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
            rating INTEGER DEFAULT 0 CHECK (rating >= 0 AND rating <= 100),
            is_used BOOLEAN DEFAULT FALSE,
            use_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        cursor.execute(create_jokes_table_sql)
        logger.info("✅ jokes表创建成功")
        
        # 创建索引
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_jokes_category ON jokes(category);",
            "CREATE INDEX IF NOT EXISTS idx_jokes_rating ON jokes(rating);",
            "CREATE INDEX IF NOT EXISTS idx_jokes_created_at ON jokes(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_jokes_difficulty ON jokes(difficulty_level);",
            "CREATE INDEX IF NOT EXISTS idx_jokes_humor_style ON jokes(humor_style);",
            "CREATE INDEX IF NOT EXISTS idx_jokes_is_used ON jokes(is_used);",
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        
        logger.info("✅ 索引创建成功")
        
        # 创建统计视图
        create_stats_view_sql = """
        CREATE OR REPLACE VIEW joke_stats AS
        SELECT 
            category,
            difficulty_level,
            humor_style,
            COUNT(*) as total_count,
            AVG(rating) as avg_rating,
            COUNT(CASE WHEN is_used THEN 1 END) as used_count,
            COUNT(CASE WHEN NOT is_used THEN 1 END) as unused_count
        FROM jokes
        GROUP BY category, difficulty_level, humor_style
        ORDER BY category, difficulty_level, humor_style;
        """
        
        cursor.execute(create_stats_view_sql)
        logger.info("✅ 统计视图创建成功")
        
        # 创建更新时间触发器函数
        create_trigger_function_sql = """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        """
        
        cursor.execute(create_trigger_function_sql)
        
        # 创建触发器
        create_trigger_sql = """
        DROP TRIGGER IF EXISTS update_jokes_updated_at ON jokes;
        CREATE TRIGGER update_jokes_updated_at
            BEFORE UPDATE ON jokes
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        """
        
        cursor.execute(create_trigger_sql)
        logger.info("✅ 更新时间触发器创建成功")
        
        # 提交更改
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info("✅ 所有表结构创建完成")
        
    except Exception as e:
        logger.error(f"❌ 创建表结构失败: {e}")
        raise

def insert_sample_data():
    """插入示例数据"""
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='jokes_db',
            user='postgres',
            password='password'
        )
        cursor = conn.cursor()
        
        # 示例笑话数据
        sample_jokes = [
            {
                'joke_id': 'SAMPLE_001',
                'category': '学术幽默',
                'difficulty_level': '中等',
                'humor_style': '冷幽默',
                'setup': '方知衡在实验室里观测星空时，助手问他："教授，您觉得宇宙有多大？"',
                'punchline': '方知衡认真地回答："根据最新观测数据，宇宙的直径约为930亿光年...不过我觉得还是没有我的书房整理难度大。"',
                'context': '体现方知衡的学术严谨和生活细致的反差',
                'character_traits': ['学术严谨', '生活细致', '冷幽默'],
                'tags': ['天文学', '书房整理', '反差萌'],
                'rating': 75
            },
            {
                'joke_id': 'SAMPLE_002',
                'category': '毒奶体质',
                'difficulty_level': '简单',
                'humor_style': '自嘲',
                'setup': '方知衡准备去参加学术会议，出门前对着镜子说："今天天气这么好，会议应该很顺利。"',
                'punchline': '结果一到会场就下起了暴雨，演讲设备也故障了。方知衡无奈地想：果然，我还是不要随便预测比较好。',
                'context': '展现方知衡的毒奶体质特征',
                'character_traits': ['毒奶体质', '自我反省', '无奈'],
                'tags': ['学术会议', '天气', '预测失灵'],
                'rating': 80
            },
            {
                'joke_id': 'SAMPLE_003',
                'category': '网络落伍',
                'difficulty_level': '中等',
                'humor_style': '观察式',
                'setup': '学生向方知衡解释网络流行语，说："教授，yyds是永远的神的意思。"',
                'punchline': '方知衡若有所思地点头："那yydx是永远的星吗？我觉得这个说法在天文学上更有意义。"学生们哭笑不得。',
                'context': '体现方知衡对网络用语的不理解和学者思维',
                'character_traits': ['网络落伍', '学者思维', '认真'],
                'tags': ['网络用语', '师生对话', '天文学思维'],
                'rating': 70
            }
        ]
        
        # 插入示例数据
        for joke in sample_jokes:
            insert_sql = """
            INSERT INTO jokes (
                joke_id, category, difficulty_level, humor_style,
                setup, punchline, context, character_traits, tags, rating
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (joke_id) DO NOTHING
            """
            
            cursor.execute(insert_sql, (
                joke['joke_id'],
                joke['category'],
                joke['difficulty_level'],
                joke['humor_style'],
                joke['setup'],
                joke['punchline'],
                joke['context'],
                joke['character_traits'],
                joke['tags'],
                joke['rating']
            ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"✅ 插入了{len(sample_jokes)}条示例笑话")
        
    except Exception as e:
        logger.error(f"❌ 插入示例数据失败: {e}")
        raise

def check_database_status():
    """检查数据库状态"""
    try:
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='jokes_db',
            user='postgres',
            password='password'
        )
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = cursor.fetchall()
        logger.info(f"📋 数据库中的表: {[table[0] for table in tables]}")
        
        # 检查笑话数量
        cursor.execute("SELECT COUNT(*) FROM jokes")
        joke_count = cursor.fetchone()[0]
        logger.info(f"📊 当前笑话总数: {joke_count}")
        
        # 按类别统计
        cursor.execute("""
            SELECT category, COUNT(*) 
            FROM jokes 
            GROUP BY category 
            ORDER BY COUNT(*) DESC
        """)
        category_stats = cursor.fetchall()
        logger.info("📈 按类别统计:")
        for category, count in category_stats:
            logger.info(f"  - {category}: {count}条")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ 检查数据库状态失败: {e}")

def main():
    """主函数"""
    print("=== PostgreSQL数据库初始化 ===")
    
    try:
        # 1. 创建数据库
        logger.info("步骤1: 创建数据库...")
        create_database()
        
        # 2. 创建表结构
        logger.info("步骤2: 创建表结构...")
        create_tables()
        
        # 3. 插入示例数据
        logger.info("步骤3: 插入示例数据...")
        insert_sample_data()
        
        # 4. 检查状态
        logger.info("步骤4: 检查数据库状态...")
        check_database_status()
        
        print("\n✅ 数据库初始化完成！")
        print("现在您可以运行笑话生成工作流了。")
        
    except Exception as e:
        print(f"\n❌ 数据库初始化失败: {e}")
        print("请检查PostgreSQL服务是否正在运行，以及连接参数是否正确。")

if __name__ == "__main__":
    main() 