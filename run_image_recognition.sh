#!/bin/bash
# 设置豆包API环境变量
export DOUBAO_MODEL_VISION_PRO=ep-20250704095927-j6t2g

# 请在下面设置您的API密钥
export ARK_API_KEY="您的API密钥"

# 确保临时目录存在
mkdir -p workspace/temp

# 创建示例图片
echo "正在创建示例图片..."
python -c "import base64; f = open('workspace/temp/cat_sample.png', 'wb'); f.write(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVQI12P4//8/AAX+Av7czFnnAAAAAElFTkSuQmCC')); f.close(); print('已创建示例图片')"

# 执行图片识别脚本，处理指定图片
python test_image_recognition.py -i "workspace/temp/cat_sample.png" -o ./workspace/image_recognition_output -b 1 --create-sample

read -p "按Enter键退出..." 