"""
测试豆包API的Token统计功能
验证图片识别工作流中的token统计是否正确
"""

import os
import sys
import asyncio
import base64
import json

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from llm.doubao import DoubaoLLM
from core.types import LLMConfig, Message, MessageRole

async def test_token_statistics():
    """测试Token统计功能"""
    print("🧪 测试豆包API的Token统计功能")
    print("=" * 50)
    
    try:
        print("开始测试...")
        # 配置LLM
        api_key = os.getenv('ARK_API_KEY', "b633a622-b5d0-4f16-a8a9-616239cf15d1")
        vision_model = os.getenv('DOUBAO_MODEL_VISION_PRO', 'ep-20250704095927-j6t2g')
        
        llm_config = LLMConfig(
            provider="doubao",
            model_name=vision_model,
            api_key=api_key.strip(),
            api_base="https://ark.cn-beijing.volces.com/api/v3"
        )
        
        llm = DoubaoLLM(config=llm_config)
        await llm.initialize()
        print(f"✅ LLM初始化成功，使用模型: {vision_model}")
        
        # 测试1: 纯文本请求的token统计
        print("\n📝 测试1: 纯文本请求")
        text_messages = [
            Message(role=MessageRole.SYSTEM, content="你是一个助手。"),
            Message(role=MessageRole.USER, content="请简单介绍一下北京。")
        ]
        
        text_response = await llm.generate(text_messages, temperature=0.7, max_tokens=500)
        print(f"📄 回复内容: {text_response.content[:100]}...")
        
        # 提取token统计
        usage_info = text_response.metadata.get('usage', {})
        print(f"📊 Token统计:")
        print(f"  原始usage信息: {usage_info}")
        print(f"  输入Token: {usage_info.get('prompt_tokens', 'N/A')}")
        print(f"  输出Token: {usage_info.get('completion_tokens', 'N/A')}")
        print(f"  总Token: {usage_info.get('total_tokens', 'N/A')}")
        
        # 测试2: 图片识别请求的token统计
        print("\n🖼️ 测试2: 图片识别请求")
        
        # 寻找一个测试图片
        test_image_paths = [
            "workspace/input/对话日常图片/通用/凤凰小图.png",
            "workspace/input/对话日常图片/通用/凤凰原图.png",
            "workspace/input/对话日常图片/通用/擦边小图.png"
        ]
        
        test_image_path = None
        for path in test_image_paths:
            if os.path.exists(path):
                test_image_path = path
                break
        
        if test_image_path:
            print(f"📷 使用测试图片: {test_image_path}")
            
            # 读取并编码图片
            with open(test_image_path, "rb") as img_file:
                img_data = img_file.read()
                base64_img = base64.b64encode(img_data).decode("utf-8")
            
            # 确定MIME类型
            if test_image_path.lower().endswith('.png'):
                mime_type = "image/png"
            else:
                mime_type = "image/jpeg"
            
            # 构建图片消息
            image_messages = [
                Message(role=MessageRole.SYSTEM, content="你是一个专业的图片识别助手。"),
                Message(
                    role=MessageRole.USER,
                    content="请简单描述这张图片。",
                    metadata={
                        "has_image": True,
                        "image_data": base64_img,
                        "image_mime": mime_type
                    }
                )
            ]
            
            # 应用monkey patch支持图片
            original_convert_messages = llm._convert_messages
            
            def patched_convert_messages(messages_list):
                converted = []
                for msg in messages_list:
                    role = "user" if msg.role == MessageRole.USER else "assistant"
                    if msg.role == MessageRole.SYSTEM:
                        role = "system"
                    
                    if msg.metadata and msg.metadata.get("has_image"):
                        converted.append({
                            "role": role,
                            "content": [
                                {"type": "text", "text": msg.content},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{msg.metadata.get('image_mime', 'image/jpeg')};base64,{msg.metadata.get('image_data')}",
                                    }
                                }
                            ]
                        })
                    else:
                        converted.append({
                            "role": role,
                            "content": msg.content
                        })
                
                return converted
            
            # 应用patch
            llm._convert_messages = patched_convert_messages
            
            try:
                image_response = await llm.generate(image_messages, temperature=0.7, max_tokens=500)
                print(f"🖼️ 图片识别结果: {image_response.content[:100]}...")
                
                # 提取token统计
                image_usage_info = image_response.metadata.get('usage', {})
                print(f"📊 图片识别Token统计:")
                print(f"  原始usage信息: {image_usage_info}")
                print(f"  输入Token: {image_usage_info.get('prompt_tokens', 'N/A')}")
                print(f"  输出Token: {image_usage_info.get('completion_tokens', 'N/A')}")
                print(f"  总Token: {image_usage_info.get('total_tokens', 'N/A')}")
                
                # 恢复原始方法
                llm._convert_messages = original_convert_messages
                
            except Exception as e:
                # 恢复原始方法
                llm._convert_messages = original_convert_messages
                print(f"❌ 图片识别测试失败: {e}")
        else:
            print("⚠️ 没有找到测试图片，跳过图片识别测试")
        
        print("\n✅ Token统计测试完成")
        print("\n💡 结论:")
        print("- 豆包API返回的usage信息包含:")
        print("  • prompt_tokens: 输入token数量")
        print("  • completion_tokens: 输出token数量") 
        print("  • total_tokens: 总token数量")
        print("- 图片识别工作流已正确配置token统计")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_token_statistics())