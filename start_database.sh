#!/bin/bash
# -*- coding: utf-8 -*-
# PostgreSQL数据库启动脚本 (Linux/macOS)
# @author leo
# @description 在Linux/macOS环境下启动PostgreSQL数据库服务
# @usage bash start_database.sh 或 ./start_database.sh

set -e

echo "=============================================="
echo "   ZZZero AI Agent Framework"
echo "   PostgreSQL Database Startup Script"
echo "=============================================="
echo

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ ERROR: Docker is not installed or not in PATH"
    echo "Please install Docker first"
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# 检查docker-compose是否可用
if ! command -v docker-compose &> /dev/null; then
    echo "❌ ERROR: docker-compose is not available"
    echo "Please install docker-compose"
    echo "Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✅ Docker environment check passed"
echo

# 启动PostgreSQL数据库
echo "🚀 Starting PostgreSQL database..."
docker-compose up -d postgres

if [ $? -eq 0 ]; then
    echo "✅ PostgreSQL database started successfully"
    echo
    echo "Database connection details:"
    echo "- Host: localhost"
    echo "- Port: 5432"
    echo "- Database: zzzero"
    echo "- Username: zzzero_user"
    echo "- Password: zzzero_pass"
    echo
    echo "📊 You can check database status with:"
    echo "   docker-compose ps"
    echo
    echo "📝 View database logs with:"
    echo "   docker-compose logs -f postgres"
    echo
    echo "🛑 Stop database with:"
    echo "   docker-compose stop postgres"
    echo
    
    # 等待数据库就绪
    echo "⏳ Waiting for database to be ready..."
    timeout=60
    count=0
    
    while [ $count -lt $timeout ]; do
        if docker-compose exec -T postgres pg_isready -U zzzero_user -d zzzero &> /dev/null; then
            echo "✅ Database is ready!"
            break
        fi
        
        echo -n "."
        sleep 2
        count=$((count + 2))
    done
    
    if [ $count -ge $timeout ]; then
        echo
        echo "⚠️  Database startup timeout. Please check logs:"
        echo "   docker-compose logs postgres"
    fi
    
else
    echo "❌ Failed to start PostgreSQL database"
    echo
    echo "Troubleshooting tips:"
    echo "1. Make sure Docker daemon is running"
    echo "2. Check if port 5432 is already in use"
    echo "3. Verify docker-compose.yml file exists"
    echo "4. Check Docker logs for more details"
    exit 1
fi