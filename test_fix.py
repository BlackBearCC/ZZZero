#!/usr/bin/env python3
"""
测试ChromaDB接口修复和BGE模型配置
"""
import sys
import os
sys.path.insert(0, 'src')

def test_embedding_function_interface():
    """测试EmbeddingFunction接口修复"""
    print("🔍 测试1: EmbeddingFunction接口修复")
    
    try:
        from core.plugins import RoleKnowledgeBasePlugin
        plugin = RoleKnowledgeBasePlugin()
        
        # 创建一个模拟的embedding模型
        class MockModel:
            def encode(self, texts, convert_to_numpy=True):
                import numpy as np
                # 返回模拟的384维向量（会被调整为512维）
                return np.random.random((len(texts), 384))
        
        # 创建Custom512EmbeddingFunction实例
        plugin._embedding_model = MockModel()
        custom_ef = plugin._create_custom_embedding_function()
        
        # 测试新的input参数接口
        test_texts = ["这是一个测试文本", "这是另一个测试文本"]
        result = custom_ef(input=test_texts)  # 使用新的input参数
        
        print(f"✅ 接口测试通过: 输入{len(test_texts)}个文本，输出{len(result)}个向量")
        print(f"✅ 向量维度: {len(result[0])}维（目标512维）")
        
        return True
        
    except Exception as e:
        print(f"❌ 接口测试失败: {e}")
        return False

def test_bge_model_config():
    """测试BGE模型配置"""
    print("\n🔍 测试2: BGE模型配置")
    
    try:
        from core.plugins import RoleKnowledgeBase
        
        # 测试默认配置
        kb = RoleKnowledgeBase(
            name="测试知识库",
            source_file="test.txt", 
            description="测试",
            created_at="2024-01-01"
        )
        
        print(f"✅ 默认embedding模型: {kb.embedding_model}")
        
        if kb.embedding_model == "BAAI/bge-small-zh-v1.5":
            print("✅ BGE模型配置正确")
            return True
        else:
            print(f"❌ BGE模型配置错误，期望: BAAI/bge-small-zh-v1.5，实际: {kb.embedding_model}")
            return False
            
    except Exception as e:
        print(f"❌ BGE模型配置测试失败: {e}")
        return False

def test_config_file():
    """测试配置文件更新"""
    print("\n🔍 测试3: 配置文件更新")
    
    try:
        import json
        config_file = "workspace/role_plugins_config.json"
        
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            kb_config = config.get("role_knowledge_base", {})
            embedding_model = kb_config.get("embedding_model", "")
            
            print(f"✅ 配置文件中的embedding模型: {embedding_model}")
            
            if embedding_model == "BAAI/bge-small-zh-v1.5":
                print("✅ 配置文件更新正确")
                return True
            else:
                print(f"❌ 配置文件更新错误，期望: BAAI/bge-small-zh-v1.5，实际: {embedding_model}")
                return False
        else:
            print("⚠️ 配置文件不存在")
            return True
            
    except Exception as e:
        print(f"❌ 配置文件测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("=" * 50)
    print("🚀 ZZZero ChromaDB修复验证测试")
    print("=" * 50)
    
    results = []
    
    # 运行所有测试
    results.append(test_embedding_function_interface())
    results.append(test_bge_model_config())
    results.append(test_config_file())
    
    # 汇总结果
    print("\n" + "=" * 50)
    print("📊 测试结果汇总")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ 通过: {passed}/{total}")
    print(f"❌ 失败: {total - passed}/{total}")
    
    if passed == total:
        print("\n🎉 所有测试通过！ChromaDB接口修复和BGE模型配置成功！")
        return True
    else:
        print(f"\n⚠️ 有{total - passed}个测试失败，请检查相关配置")
        return False

if __name__ == "__main__":
    main() 