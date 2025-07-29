#!/usr/bin/env python3
"""
角色资料SSE流式功能测试脚本
"""

import requests
import json
import time
import sys

def test_sse_endpoints():
    """测试SSE端点是否可用"""
    print("🧪 测试SSE端点...")
    
    # 测试创建会话
    try:
        response = requests.post('http://127.0.0.1:5001/api/sse/create_session', 
                                timeout=5)
        if response.status_code == 200:
            session_data = response.json()
            session_id = session_data.get('session_id')
            print(f"✅ 创建会话成功: {session_id}")
            return session_id
        else:
            print(f"❌ 创建会话失败: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ 连接SSE服务失败: {e}")
        return None

def test_workflow_start():
    """测试工作流启动"""
    print("\n🚀 测试工作流启动...")
    
    test_params = {
        "character_name": "测试角色",
        "basic_info": "一个用于测试的角色，性格开朗活泼。",
        "selected_categories": ["基本信息", "性格特征"],
        "selected_collections": [],
        "llm_provider": "doubao",
        "model_name": "ep-20250221154410-vh78x",
        "temperature": 0.7
    }
    
    try:
        response = requests.post(
            'http://127.0.0.1:5001/api/workflow/character_profile_stream',
            headers={'Content-Type': 'application/json'},
            json=test_params,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            session_id = result.get('session_id')
            print(f"✅ 工作流启动成功: {session_id}")
            return session_id
        else:
            print(f"❌ 工作流启动失败: {response.status_code}")
            print(f"响应内容: {response.text}")
            return None
    except Exception as e:
        print(f"❌ 工作流启动请求失败: {e}")
        return None

def test_sse_stream(session_id):
    """测试SSE流式接收"""
    print(f"\n📡 测试SSE流式接收 (会话: {session_id})...")
    
    try:
        import sseclient  # 需要安装: pip install sseclient-py
        
        response = requests.get(f'http://127.0.0.1:5001/api/sse/stream/{session_id}', 
                               stream=True)
        client = sseclient.SSEClient(response)
        
        event_count = 0
        for event in client.events():
            event_count += 1
            print(f"📨 收到事件 #{event_count}: {event.data[:100]}...")
            
            # 解析事件数据
            try:
                data = json.loads(event.data)
                if data.get('type') == 'complete':
                    print("✅ 工作流完成")
                    break
            except:
                pass
            
            # 限制测试时间
            if event_count > 20:
                print("⏰ 测试时间限制，停止接收")
                break
                
        print(f"✅ SSE流式测试完成，共收到 {event_count} 个事件")
        
    except ImportError:
        print("⚠️  sseclient-py未安装，跳过流式测试")
        print("   安装命令: pip install sseclient-py")
    except Exception as e:
        print(f"❌ SSE流式测试失败: {e}")

def check_flask_service():
    """检查Flask服务是否运行"""
    print("🔍 检查Flask服务状态...")
    
    try:
        response = requests.get('http://127.0.0.1:5001/', timeout=3)
        print("✅ Flask服务正在运行")
        return True
    except requests.exceptions.ConnectionError:
        print("❌ Flask服务未运行")
        print("💡 请确保主应用已启动: python3 main.py")
        return False
    except Exception as e:
        print(f"❌ Flask服务检查失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🎯 ZZZero 角色资料SSE功能测试")
    print("=" * 50)
    
    # 检查Flask服务
    if not check_flask_service():
        return
    
    # 测试SSE端点
    session_id = test_sse_endpoints()
    if not session_id:
        return
    
    # 测试工作流启动
    workflow_session = test_workflow_start()
    if not workflow_session:
        return
    
    # 测试SSE流式接收
    test_sse_stream(workflow_session)
    
    print("\n🎉 测试完成！")
    print("💡 现在可以在浏览器中访问: http://127.0.0.1:7861")
    print("   切换到'🎭 角色资料'标签页测试完整功能")

if __name__ == "__main__":
    main()