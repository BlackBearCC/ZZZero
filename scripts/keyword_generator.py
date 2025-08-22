# -*- coding: utf-8 -*-
"""
关键词生成器 - 读取CSV文件指定字段，使用LLM提取名词实体作为关键词

功能：
- 读取CSV文件的指定字段
- 使用LLM提取名词实体作为关键词
- 保存原始内容+生成的关键词到新文件
"""

import csv
import json
import os
import sys
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

# 添加项目根目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.llm.doubao import DoubaoLLM
from src.core.types import LLMConfig, Message, MessageRole

logger = logging.getLogger(__name__)

class KeywordGenerator:
    """关键词生成器"""
    
    def __init__(self):
        self.llm = None
        self._init_llm()
    
    def _init_llm(self):
        """初始化LLM"""
        try:
            # 使用环境变量获取模型名称和API密钥
            text_model = os.getenv('DOUBAO_MODEL_DEEPSEEKV3', 'ep-20250221154410-vh78x')
            api_key = os.getenv('ARK_API_KEY', "b633a622-b5d0-4f16-a8a9-616239cf15d1")
            
            # 创建LLM配置
            llm_config = LLMConfig(
                provider="doubao",
                model_name=text_model,
                api_key=api_key.strip(),
                api_base="https://ark.cn-beijing.volces.com/api/v3"
            )
            self.llm = DoubaoLLM(config=llm_config)
            print(f"✅ LLM配置成功，使用模型: {text_model}")
        except Exception as e:
            print(f"⚠️ LLM配置失败: {e}")
            self.llm = None
    
    async def extract_keywords(self, text: str) -> List[str]:
        """从文本中提取关键词（名词实体）"""
        if not self.llm or not text.strip():
            return []
        
        try:
            # 构建提示词
            system_prompt = """你是一个专业的文本分析助手，擅长从文本中提取名词实体作为关键词。

请从提供的文本中提取具体的名词实体，作为关键词。要求：
1. 只提取具体的名词实体（如：人物、物品、动物、植物、建筑、地点等）
2. 不要抽象概念、形容词、动词、颜色、情感词汇
3. 不要重复的词汇，不要词组例如：城市街道，会拆分为城市、街道
4. 按重要性排序，最多20个关键词
5. 物品禁止包含颜色描述

输出格式要求：JSON格式，包含以下字段：
- keywords: 关键词数组

请确保输出为严格的JSON格式，禁止输出任何其他内容。
示例：
{
  "keywords": ["风车", "油菜花", "蓝天", "小猫", "树枝"]
}"""
            
            # 构建用户消息
            user_message = Message(
                role=MessageRole.USER,
                content=f"请从以下文本中提取名词实体作为关键词：\n\n{text}"
            )
            
            # 构建消息列表
            messages = [
                Message(role=MessageRole.SYSTEM, content=system_prompt),
                user_message
            ]
            
            # 调用LLM
            response = await self.llm.generate(
                messages,
                temperature=0.3,  # 较低温度，确保一致性
                max_tokens=1024,
                mode="normal"
            )
            
            content = response.content
            
            # 从回复中提取JSON
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试找到大括号包围的JSON
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    json_str = content
            
            # 解析JSON
            try:
                result_data = json.loads(json_str.strip())
                keywords = result_data.get('keywords', [])
                if isinstance(keywords, list):
                    return keywords
                else:
                    return []
            except json.JSONDecodeError:
                logger.warning(f"JSON解析失败，使用原始回复")
                return []
                
        except Exception as e:
            logger.error(f"关键词提取失败: {e}")
            return []
    
    async def process_csv_file(self, input_file: str, output_file: str = None, 
                             source_field: str = "故事内容", 
                             target_field: str = "LLM关键词",
                             batch_size: int = 5) -> bool:
        """
        处理CSV文件，提取关键词
        
        Args:
            input_file: 输入CSV文件路径
            output_file: 输出CSV文件路径（可选）
            source_field: 源字段名（从哪个字段提取关键词）
            target_field: 目标字段名（新增的关键词字段名）
            batch_size: 批处理大小
            
        Returns:
            bool: 处理是否成功
        """
        # 检查输入文件
        if not os.path.exists(input_file):
            print(f"❌ 输入文件不存在: {input_file}")
            return False
        
        # 确定输出文件名
        if output_file is None:
            base_name, ext = os.path.splitext(input_file)
            output_file = f"{base_name}_with_keywords{ext}"
        
        print(f"📖 读取文件: {input_file}")
        print(f"🎯 源字段: {source_field}")
        print(f"💾 输出文件: {output_file}")
        print(f"🔤 目标字段: {target_field}")
        
        # 尝试不同编码读取文件
        encodings = ['utf-8-sig', 'utf-8', 'gbk']
        rows = []
        headers = []
        
        for encoding in encodings:
            try:
                with open(input_file, 'r', encoding=encoding, newline='') as f:
                    reader = csv.DictReader(f)
                    headers = reader.fieldnames
                    rows = list(reader)
                print(f"✅ 成功读取文件（编码: {encoding}）")
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                print(f"读取文件失败 ({encoding}): {e}")
                continue
        
        if not rows:
            print("❌ 无法读取文件，请检查文件格式和编码")
            return False
        
        # 检查源字段是否存在
        if source_field not in headers:
            print(f"❌ 源字段 '{source_field}' 不存在")
            print(f"可用字段: {', '.join(headers)}")
            return False
        
        # 准备新的字段名列表
        new_headers = list(headers)
        if target_field not in new_headers:
            new_headers.append(target_field)
        
        print(f"📊 开始处理 {len(rows)} 条记录...")
        
        # 分批处理
        total_batches = (len(rows) + batch_size - 1) // batch_size
        processed_count = 0
        
        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(rows))
            batch_rows = rows[start_idx:end_idx]
            
            print(f"\n🔄 处理第 {batch_idx + 1}/{total_batches} 批 ({len(batch_rows)} 条记录)")
            
            # 处理当前批次
            for i, row in enumerate(batch_rows):
                source_text = row.get(source_field, "")
                if source_text.strip():
                    print(f"  📝 处理第 {start_idx + i + 1} 条记录...")
                    keywords = await self.extract_keywords(source_text)
                    row[target_field] = " ".join(keywords) if keywords else ""
                    if keywords:
                        print(f"    ✅ 提取到 {len(keywords)} 个关键词: {', '.join(keywords[:15])}{'...' if len(keywords) > 5 else ''}")
                    else:
                        print(f"    ⚠️ 未提取到关键词")
                else:
                    row[target_field] = ""
                    print(f"    ⚠️ 第 {start_idx + i + 1} 条记录的源字段为空")
                
                processed_count += 1
            
            print(f"  ✅ 第 {batch_idx + 1} 批处理完成")
        
        # 写入输出文件
        try:
            with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=new_headers)
                writer.writeheader()
                writer.writerows(rows)
            
            print(f"\n✅ 处理完成！")
            print(f"📄 输出文件: {output_file}")
            print(f"📊 处理记录数: {processed_count}")
            
            return True
            
        except Exception as e:
            print(f"❌ 写入输出文件失败: {e}")
            return False

def show_field_menu(headers: List[str]) -> str:
    """显示字段选择菜单"""
    print("\n" + "="*60)
    print("📋 可用字段列表:")
    print("-"*60)
    
    for i, field in enumerate(headers, 1):
        print(f"  {i}. {field}")
    
    print("\n💡 请输入数字编号选择源字段 (默认选择包含'故事'或'内容'的字段)")
    print("-"*60)
    
    # 自动检测包含'故事'或'内容'的字段
    auto_field = None
    for field in headers:
        if '故事' in field or '内容' in field:
            auto_field = field
            break
    
    if auto_field:
        print(f"🎯 自动检测到推荐字段: {auto_field}")
        choice = input("👉 请选择 (直接回车使用推荐字段): ").strip()
        
        if choice == "":
            return auto_field
    else:
        choice = input("👉 请选择: ").strip()
    
    try:
        choice_num = int(choice)
        if 1 <= choice_num <= len(headers):
            return headers[choice_num - 1]
        else:
            print(f"❌ 请输入1-{len(headers)}之间的数字")
            return show_field_menu(headers)
    except ValueError:
        print("❌ 请输入有效数字")
        return show_field_menu(headers)

async def main():
    """主函数"""
    print("🔤 关键词生成器")
    print("=" * 60)
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        # 默认文件
        input_file = "workspace/input/image_recognition_20250704_112047_with_story_with_unique_id.csv"
    
    if not os.path.exists(input_file):
        print(f"❌ 文件不存在: {input_file}")
        return
    
    # 先读取文件头，显示字段选择
    try:
        with open(input_file, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
    except Exception as e:
        print(f"❌ 读取文件头失败: {e}")
        return
    
    print(f"📖 输入文件: {input_file}")
    
    # 选择源字段
    source_field = show_field_menu(headers)
    print(f"\n✅ 已选择源字段: {source_field}")
    
    # 输入目标字段名
    target_field = input("\n🔤 请输入新关键词字段名 (默认: LLM关键词): ").strip()
    if not target_field:
        target_field = "LLM关键词"
    
    # 批处理大小
    batch_size_input = input("\n📦 请输入批处理大小 (默认: 3): ").strip()
    try:
        batch_size = int(batch_size_input) if batch_size_input else 3
    except ValueError:
        batch_size = 3
    
    print(f"\n🎯 配置确认:")
    print(f"  📖 输入文件: {input_file}")
    print(f"  📝 源字段: {source_field}")
    print(f"  🔤 目标字段: {target_field}")
    print(f"  📦 批处理大小: {batch_size}")
    
    confirm = input("\n❓ 确认开始处理？(y/n): ").lower().strip()
    if confirm not in ['y', 'yes', '是']:
        print("👋 取消处理")
        return
    
    # 创建关键词生成器
    generator = KeywordGenerator()
    
    if not generator.llm:
        print("❌ LLM未初始化，无法继续")
        return
    
    # 开始处理
    print(f"\n🚀 开始处理...")
    success = await generator.process_csv_file(
        input_file=input_file,
        source_field=source_field,
        target_field=target_field,
        batch_size=batch_size
    )
    
    if success:
        print("\n🎉 关键词生成完成！")
    else:
        print("\n❌ 处理失败")

if __name__ == "__main__":
    asyncio.run(main())