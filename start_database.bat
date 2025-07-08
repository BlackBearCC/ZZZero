@echo off
REM -*- coding: utf-8 -*-
REM PostgreSQL数据库启动脚本 (Windows)
REM @author leo
REM @description 在Windows环境下启动PostgreSQL数据库服务
REM @usage 双击运行或在命令行执行 start_database.bat

echo ==============================================
echo    ZZZero AI Agent Framework
echo    PostgreSQL Database Startup Script
echo ==============================================
echo.

REM 检查Docker是否安装
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not installed or not in PATH
    echo Please install Docker Desktop first
    echo Download from: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

REM 检查docker-compose是否可用
docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: docker-compose is not available
    echo Please ensure Docker Desktop is running
    pause
    exit /b 1
)

echo ✅ Docker environment check passed
echo.

REM 启动PostgreSQL数据库
echo 🚀 Starting PostgreSQL database...
docker-compose up -d postgres

if %errorlevel% equ 0 (
    echo ✅ PostgreSQL database started successfully
    echo.
    echo Database connection details:
    echo - Host: localhost
    echo - Port: 5432
    echo - Database: zzzero
    echo - Username: zzzero_user
    echo - Password: zzzero_pass
    echo.
    echo 📊 You can check database status with:
    echo    docker-compose ps
    echo.
    echo 📝 View database logs with:
    echo    docker-compose logs -f postgres
    echo.
    echo 🛑 Stop database with:
    echo    docker-compose stop postgres
) else (
    echo ❌ Failed to start PostgreSQL database
    echo.
    echo Troubleshooting tips:
    echo 1. Make sure Docker Desktop is running
    echo 2. Check if port 5432 is already in use
    echo 3. Verify docker-compose.yml file exists
    echo 4. Check Docker logs for more details
)

echo.
echo Press any key to exit...
pause >nul