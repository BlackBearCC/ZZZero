@echo off
REM 图片识别工作流环境变量设置脚本
REM 请根据您的实际API密钥配置下面的环境变量

echo ===============================================
echo 图片识别工作流环境变量设置
echo ===============================================

REM 设置豆包API密钥（请替换为您的实际密钥）
REM set ARK_API_KEY=your_doubao_api_key_here
REM set DOUBAO_API_KEY=your_doubao_api_key_here

REM 设置豆包多模态模型名称
set DOUBAO_MODEL_VISION_PRO=ep-20250704095927-j6t2g

echo.
echo 当前环境变量设置：
echo ARK_API_KEY=%ARK_API_KEY%
echo DOUBAO_API_KEY=%DOUBAO_API_KEY%
echo DOUBAO_MODEL_VISION_PRO=%DOUBAO_MODEL_VISION_PRO%
echo.

REM 检查是否设置了API密钥
if "%ARK_API_KEY%"=="" if "%DOUBAO_API_KEY%"=="" (
    echo ⚠️  警告：未设置API密钥，图片识别功能将无法正常工作
    echo.
    echo 请编辑此文件，取消注释并设置您的API密钥：
    echo   set ARK_API_KEY=your_doubao_api_key_here
    echo   或
    echo   set DOUBAO_API_KEY=your_doubao_api_key_here
    echo.
    echo 然后重新运行此脚本
    pause
    exit /b 1
) else (
    echo ✅ API密钥已设置
)

echo.
echo 环境变量设置完成！
echo 现在可以运行图片识别工作流了。
echo.
pause