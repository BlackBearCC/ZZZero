#!/bin/bash
# -*- coding: utf-8 -*-
# SQLite数据库初始化脚本 (Linux/macOS)
# @author leo
# @description 在Linux/macOS环境下初始化SQLite数据库
# @usage bash start_database.sh 或 ./start_database.sh

set -e

echo "=============================================="
echo "   ZZZero AI Agent Framework"
echo "   SQLite Database Initialization Script"
echo "=============================================="
echo

# 设置数据库路径
DATABASE_DIR="./workspace/database"
DATABASE_FILE="$DATABASE_DIR/zzzero.db"
INIT_SQL="./database/init/01-init-database.sql"

echo "🔧 Initializing SQLite database..."
echo

# 创建数据库目录
if [ ! -d "$DATABASE_DIR" ]; then
    echo "📁 Creating database directory: $DATABASE_DIR"
    mkdir -p "$DATABASE_DIR"
fi

# 检查SQLite是否可用
if ! command -v sqlite3 &> /dev/null; then
    echo "❌ ERROR: SQLite3 is not installed or not in PATH"
    echo "Please install SQLite3:"
    echo "  Ubuntu/Debian: sudo apt-get install sqlite3"
    echo "  CentOS/RHEL: sudo yum install sqlite"
    echo "  macOS: brew install sqlite3"
    exit 1
fi

echo "✅ SQLite3 environment check passed"
echo

# 初始化数据库
if [ -f "$INIT_SQL" ]; then
    echo "🚀 Initializing database from: $INIT_SQL"
    
    # 执行SQL初始化脚本
    sqlite3 "$DATABASE_FILE" < "$INIT_SQL"
    
    if [ $? -eq 0 ]; then
        echo "✅ SQLite database initialized successfully"
        echo
        echo "Database details:"
        echo "- Type: SQLite"
        echo "- Path: $DATABASE_FILE"
        echo "- Size: $(ls -lh "$DATABASE_FILE" | awk '{print $5}')"
        echo
        
        # 显示数据库表
        echo "📊 Database tables:"
        sqlite3 "$DATABASE_FILE" ".tables"
        echo
        
        echo "🔍 You can inspect the database with:"
        echo "   sqlite3 $DATABASE_FILE"
        echo
        echo "📝 View database schema with:"
        echo "   sqlite3 $DATABASE_FILE .schema"
        echo
    else
        echo "❌ Failed to initialize SQLite database"
        exit 1
    fi
else
    echo "❌ ERROR: Database initialization script not found: $INIT_SQL"
    exit 1
fi

echo "🎉 Database initialization completed!"