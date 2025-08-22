@echo off
REM 关键词生成器启动脚本
REM 描述：读取CSV文件指定字段，使用LLM提取名词实体作为关键词

echo ==============================================
echo    ZZZero AI Agent Framework
echo    关键词生成器应用
echo ==============================================
echo.

REM 设置环境变量（请根据需要修改）
REM set ARK_API_KEY=your_doubao_api_key_here
REM set DOUBAO_API_KEY=your_doubao_api_key_here
set DOUBAO_MODEL_PRO=ep-20250312153153-npj4s

REM 检查API密钥
if "%ARK_API_KEY%"=="" if "%DOUBAO_API_KEY%"=="" (
    echo ⚠️  注意：未设置API密钥，将使用默认密钥
    echo 如需使用自己的密钥，请在脚本中设置 ARK_API_KEY 或 DOUBAO_API_KEY
    echo.
) else (
    echo ✅ API密钥已设置
)

REM 检查Python环境
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is required but not found
    echo Please install Python from: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✅ Python环境检查通过
echo.

REM 检查是否提供了文件参数
if "%1"=="" (
    echo 💡 使用默认文件: workspace/input/image_recognition_20250704_112047_with_story_with_unique_id.csv
    echo.
    echo 🚀 启动关键词生成器...
    python scripts/keyword_generator.py
) else (
    echo 💡 使用指定文件: %1
    echo.
    echo 🚀 启动关键词生成器...
    python scripts/keyword_generator.py "%1"
)

echo.
echo 📝 使用说明:
echo   - 直接双击运行，使用默认文件
echo   - 或者拖拽CSV文件到此脚本上
echo   - 或者命令行：run_keyword_generator.bat "文件路径"
echo.

pause