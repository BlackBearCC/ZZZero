@echo off
chcp 65001 > nul
title 图片识别性能测试

echo ==========================================
echo    图片识别性能分析工作流
echo ==========================================
echo.

REM 设置环境变量（如果没有在系统中设置）
if not defined ARK_API_KEY (
    set ARK_API_KEY=b633a622-b5d0-4f16-a8a9-616239cf15d1
)

REM 设置豆包模型环境变量
if not defined DOUBAO_MODEL_VISION_PRO (
    set DOUBAO_MODEL_VISION_PRO=ep-20250704095927-j6t2g
)

if not defined DOUBAO_MODEL_DEEPSEEKR1 (
    set DOUBAO_MODEL_DEEPSEEKR1=ep-20250221154107-c4qc7
)

if not defined DOUBAO_MODEL_DEEPSEEKV3 (
    set DOUBAO_MODEL_DEEPSEEKV3=ep-20250221154410-vh78x
)

echo 🤖 模型配置:
echo   VISION_PRO: %DOUBAO_MODEL_VISION_PRO%
echo   DEEPSEEK_R1: %DOUBAO_MODEL_DEEPSEEKR1%
echo   DEEPSEEK_V3: %DOUBAO_MODEL_DEEPSEEKV3%
echo.

REM 检查Python环境
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python 未安装或不在 PATH 中
    echo 请安装 Python 3.8 或更高版本
    pause
    exit /b 1
)

REM 检查必要的目录
if not exist "workspace\input\对话日常图片" (
    echo ⚠️  警告: 没有找到测试图片目录 workspace\input\对话日常图片
    echo 请确保该目录下有图片文件用于测试
    echo.
)

REM 创建输出目录
if not exist "workspace\vision_performance_output" (
    mkdir "workspace\vision_performance_output"
    echo 📁 已创建输出目录: workspace\vision_performance_output
)

echo 🚀 启动图片识别性能测试...
echo.

REM 运行测试
python run_vision_performance_test.py

if %errorlevel% neq 0 (
    echo.
    echo ❌ 测试执行失败，错误代码: %errorlevel%
) else (
    echo.
    echo ✅ 测试执行完成
    echo 📋 请查看 workspace\vision_performance_output 目录下的结果文件
)

echo.
pause