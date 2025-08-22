"""
图片识别性能测试启动脚本
运行图片识别性能分析工作流，测试多个模型的表现
"""

import os
import sys
import asyncio
import glob
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from workflow.vision_performance_workflow import VisionPerformanceWorkflow

class SimpleWorkflowChat:
    """简单的工作流聊天界面模拟"""
    
    def __init__(self):
        self.current_node = ""
        self.messages = []
    
    async def add_node_message(self, node_name: str, message: str, status: str):
        """添加节点消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        status_icon = {
            "progress": "⏳",
            "success": "✅", 
            "error": "❌",
            "warning": "⚠️",
            "streaming": "🔄",
            "completed": "✅"
        }.get(status, "ℹ️")
        
        formatted_msg = f"[{timestamp}] {status_icon} [{node_name}] {message}"
        print(formatted_msg)
        self.messages.append(formatted_msg)
    
    def _create_workflow_progress(self):
        """创建工作流进度显示"""
        return f"<div>当前节点: {self.current_node}</div>"

async def main():
    """主函数"""
    print("🖼️ 图片识别性能分析工作流")
    print("=" * 80)
    print("测试多个模型的图片识别性能，包括耗时和Token消耗统计")
    print("=" * 80)
    
    try:
        # 初始化工作流
        workflow = VisionPerformanceWorkflow()
        print("✅ 工作流初始化完成")
        
        # 扫描测试图片
        print("\n📁 扫描测试图片...")
        image_paths = []
        
        # 定义图片搜索路径
        search_patterns = [
            "workspace/input/穆昭/宠物/*.png",

            # 也可以添加其他格式
            "workspace/input/穆昭/宠物/*.jpg",

        ]
        
        for pattern in search_patterns:
            found_images = glob.glob(pattern)
            image_paths.extend(found_images)
            if found_images:
                print(f"  📂 {pattern}: 发现 {len(found_images)} 张图片")
        
        # 去重并限制数量（可根据需要调整）
        image_paths = list(set(image_paths))
        
        # 限制测试图片数量（避免测试时间过长）
        max_images = int(input(f"发现 {len(image_paths)} 张图片，请输入要测试的图片数量（直接回车使用全部）: ") or len(image_paths))
        image_paths = image_paths[:max_images]
        
        print(f"📊 将测试 {len(image_paths)} 张图片")
        
        if not image_paths:
            print("❌ 没有找到测试图片，请确保 workspace/input/方知衡/ 目录下有图片文件")
            return
        
        # 显示将要测试的模型
        print(f"\n🤖 将测试以下模型:")
        for key, config in workflow.model_configs.items():
            model_name = os.getenv(config['env_key'], config['default'])
            print(f"  • {config['name']}: {model_name}")
        
        # 配置测试参数
        config = {
            'batch_size': 10,
            'test_all_models': True,
            'csv_output': {
                'enabled': True,
                'output_dir': 'workspace/vision_performance_output',
                'recognition_filename': 'vision_recognition_results.csv',
                'performance_filename': 'vision_performance_stats.csv',
                'encoding': 'utf-8-sig'
            }
        }
        
        # 创建输出目录
        output_dir = config['csv_output']['output_dir']
        os.makedirs(output_dir, exist_ok=True)
        print(f"📁 结果将保存到: {output_dir}")
        
        # 创建模拟聊天界面
        mock_chat = SimpleWorkflowChat()
        
        print(f"\n🚀 开始性能测试...")
        print("-" * 80)
        
        # 执行工作流
        final_result = None
        async for stream_result in workflow.execute_workflow_stream(config, mock_chat, image_paths):
            # 流式结果处理（在这里主要是进度显示）
            pass
        
        print("-" * 80)
        print("✅ 图片识别性能测试完成!")
        
        # 显示结果文件位置
        print(f"\n📋 测试结果已保存到:")
        print(f"  📄 详细识别结果: {output_dir}/vision_recognition_results_*.csv")
        print(f"  📊 性能统计报告: {output_dir}/vision_performance_stats_*.csv")
        
        print("\n🎯 测试总结:")
        print(f"  • 测试图片数量: {len(image_paths)}")
        print(f"  • 测试模型数量: {len(workflow.model_configs)}")
        print(f"  • 总测试次数: {len(image_paths) * len(workflow.model_configs)}")
        
    except KeyboardInterrupt:
        print("\n⚠️ 用户取消了测试")
    except Exception as e:
        print(f"\n❌ 测试执行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 运行主函数
    asyncio.run(main())