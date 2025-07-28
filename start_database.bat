@echo off
REM -*- coding: utf-8 -*-
REM SQLite数据库初始化脚本 (Windows)
REM @author leo
REM @description 在Windows环境下初始化SQLite数据库
REM @usage 双击运行或在命令行执行 start_database.bat

echo ==============================================
echo    ZZZero AI Agent Framework
echo    SQLite Database Initialization Script
echo ==============================================
echo.

REM 设置数据库路径
set DATABASE_DIR=.\workspace\database
set DATABASE_FILE=%DATABASE_DIR%\zzzero.db
set INIT_SQL=.\database\init\01-init-database.sql

echo 🔧 Initializing SQLite database...
echo.

REM 创建数据库目录
if not exist "%DATABASE_DIR%" (
    echo 📁 Creating database directory: %DATABASE_DIR%
    mkdir "%DATABASE_DIR%"
)

REM 检查是否有SQLite3可执行文件（通常Python内置）
python -c "import sqlite3; print('SQLite3 available')" >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python with SQLite3 support is required
    echo Please install Python from: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✅ SQLite3 environment check passed
echo.

REM 初始化数据库
if exist "%INIT_SQL%" (
    echo 🚀 Initializing database from: %INIT_SQL%
    
    REM 使用Python执行SQL初始化脚本
    python -c "
import sqlite3
import sys

try:
    # 连接到数据库
    conn = sqlite3.connect('%DATABASE_FILE%')
    
    # 读取并执行SQL脚本
    with open('%INIT_SQL%', 'r', encoding='utf-8') as f:
        sql_script = f.read()
    
    conn.executescript(sql_script)
    conn.commit()
    conn.close()
    
    print('✅ SQLite database initialized successfully')
except Exception as e:
    print(f'❌ Failed to initialize database: {e}')
    sys.exit(1)
"
    
    if %errorlevel% equ 0 (
        echo.
        echo Database details:
        echo - Type: SQLite
        echo - Path: %DATABASE_FILE%
        
        REM 获取文件大小
        for %%A in ("%DATABASE_FILE%") do echo - Size: %%~zA bytes
        echo.
        
        echo 📊 Database tables:
        python -c "
import sqlite3
conn = sqlite3.connect('%DATABASE_FILE%')
cursor = conn.cursor()
cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%%' ORDER BY name\")
tables = cursor.fetchall()
for table in tables:
    print(f'  - {table[0]}')
conn.close()
"
        echo.
        
        echo 🔍 You can inspect the database with:
        echo    python -c "import sqlite3; conn=sqlite3.connect('%DATABASE_FILE%'); # your queries here"
        echo.
        echo 📝 Or use any SQLite GUI tool to open: %DATABASE_FILE%
        echo.
        
        echo 🎉 Database initialization completed!
    ) else (
        echo ❌ Failed to initialize SQLite database
    )
) else (
    echo ❌ ERROR: Database initialization script not found: %INIT_SQL%
)

echo.
echo Press any key to exit...
pause >nul