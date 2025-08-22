@echo off
REM Image Recognition Workflow Startup Script (Windows)
REM Description: Starts the image recognition workflow application on Windows
REM Usage: Double-click to run or execute from command line

echo ==============================================
echo    ZZZero AI Agent Framework
echo    Image Recognition Workflow Application
echo ==============================================
echo.

REM 设置环境变量（请根据需要修改）
REM set ARK_API_KEY=your_doubao_api_key_here
REM set DOUBAO_API_KEY=your_doubao_api_key_here
set DOUBAO_MODEL_VISION_PRO=ep-20250704095927-j6t2g

REM 检查API密钥
if "%ARK_API_KEY%"=="" if "%DOUBAO_API_KEY%"=="" (
    echo ⚠️  注意：未设置API密钥，将在演示模式下运行
    echo 如需完整功能，请在脚本中设置 ARK_API_KEY 或 DOUBAO_API_KEY
    echo.
) else (
    echo ✅ API密钥已设置
)

REM Check Python environment
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is required but not found
    echo Please install Python from: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Check required dependencies
echo Checking required dependencies...
python -c "import asyncio" >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: asyncio is required but not found
    pause
    exit /b 1
)

python -c "import base64" >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: base64 is required but not found
    pause
    exit /b 1
)

python -c "import json" >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: json is required but not found
    pause
    exit /b 1
)

python -c "import os" >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: os is required but not found
    pause
    exit /b 1
)

python -c "import sys" >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: sys is required but not found
    pause
    exit /b 1
)

python -c "import logging" >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: logging is required but not found
    pause
    exit /b 1
)

python -c "import csv" >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: csv is required but not found
    pause
    exit /b 1
)

echo All required dependencies are available
echo.

REM Check core module file
set LAUNCHER_FILE=run_image_recognition.py
if not exist "%LAUNCHER_FILE%" (
    echo ERROR: Launcher file not found: %LAUNCHER_FILE%
    pause
    exit /b 1
)

echo Starting Image Recognition Workflow...
echo.

REM Start image recognition workflow, passing all arguments
python run_image_recognition.py %*

echo.
echo Image Recognition Workflow execution completed
echo.

REM Pause so user can see results
pause