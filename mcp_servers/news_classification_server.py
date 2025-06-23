#!/usr/bin/env python3
"""
新闻标题和内容分类服务器
基于MCP协议，支持豆包LLM调用进行新闻分类
"""
import os
import csv
import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import asyncio
import logging

# 导入豆包LLM相关模块
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.llm.doubao import DoubaoLLM
from src.core.types import Message, MessageRole, LLMConfig

logger = logging.getLogger(__name__)


class NewsClassificationServer:
    """新闻标题和内容分类MCP服务器"""
    
    # 新闻分类标准（添加政治分类）
    CLASSIFICATION_CATEGORIES = [
        "音乐", "影视", "游戏", "运动", "阅读", "艺术", "二次元", "亚文化", 
        "旅行", "美食", "校园","摄影", "大自然", "科技数码", "家居", "绿植", "宠物", 
        "娱乐圈", "穿搭美妆", "生活方式", "日常琐事", "线下活动", "两性情感", 
        "职场", "家庭", "价值观", "政治"
    ]
    
    def __init__(self, data_dir: str = "./workspace/output"):
        """
        初始化新闻分类服务器
        
        Args:
            data_dir: 数据存储目录，默认输出到workspace/output
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化豆包LLM客户端
        self.doubao_client = None
        self._init_doubao_client()
    
    def _init_doubao_client(self):
        """初始化豆包LLM客户端"""
        try:
            # 创建豆包LLM配置
            config = LLMConfig(
                provider="doubao",
                model_name=os.getenv('DOUBAO_MODEL_DEEPSEEKV3', 'doubao-pro-32k'),
                api_key=os.getenv('ARK_API_KEY') or os.getenv('DOUBAO_API_KEY'),
                api_base=os.getenv('DOUBAO_BASE_URL', "https://ark.cn-beijing.volces.com/api/v3"),
                temperature=0.1,  # 分类任务使用较低温度确保一致性
                max_tokens=1000,
                timeout=30.0
            )
            
            # 创建豆包LLM实例
            self.doubao_client = DoubaoLLM(config)
            
            # 异步初始化（稍后执行）
            logger.info("豆包LLM客户端配置成功")
            
        except Exception as e:
            logger.error(f"初始化豆包LLM客户端失败: {e}")
            self.doubao_client = None

    async def classify_single_news(self, title: str, content: str = "", 
                                  model: str = "doubao-pro-32k") -> Dict[str, Any]:
        """
        对单条新闻进行分类
        
        Args:
            title: 新闻标题
            content: 新闻内容（可选）
            model: 豆包模型名称
            
        Returns:
            Dict: 分类结果
        """
        if not self.doubao_client:
            return {
                "success": False,
                "error": "未设置豆包API密钥，请设置环境变量 ARK_API_KEY 或 DOUBAO_API_KEY",
                "title": title,
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            result = await self._classify_with_doubao(title, content, model)
            # 添加时间戳
            result["timestamp"] = datetime.now().isoformat()
            return result
            
        except Exception as e:
            logger.error(f"新闻分类失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "title": title,
                "timestamp": datetime.now().isoformat()
            }

    async def _classify_with_doubao(self, title: str, content: str, model: str) -> Dict[str, Any]:
        """使用豆包LLM进行新闻分类，采用COT思维链，支持多标签"""
        # 确保豆包客户端已初始化
        if not self.doubao_client:
            raise Exception("豆包LLM客户端未初始化")
        
        # 执行异步初始化
        await self.doubao_client.initialize()
        
        # 构建分类提示词
        categories_str = "、".join(self.CLASSIFICATION_CATEGORIES)
        
        # 组合新闻文本
        news_text = f"标题：{title}"
        if content.strip():
            news_text += f"\n内容：{content[:500]}"  # 限制内容长度
        
        # 使用COT思维链提示，支持多标签
        prompt = f"""请按照以下步骤对新闻进行分类：

**第一步：理解分类标准**
可选的26个分类标准：{categories_str}

**第二步：分析新闻内容**
新闻内容：
{news_text}

请分析这篇新闻的核心主题是什么，主要讨论的内容和领域是什么，涉及哪些方面。

**第三步：匹配分类**
根据新闻的核心主题和涉及的多个方面，从26个分类标准中选择1-3个最合适的分类。一篇新闻可以有多个标签。

**最终输出**
请严格按照以下JSON格式输出结果，不要包含任何其他内容：
{{
    "thinking": "你的分析思考过程",
    "categories": ["分类1", "分类2"]
}}

要求：
1. thinking字段描述你的分析思考过程
2. categories字段是数组，包含1-3个分类，每个分类必须是上述26个分类之一
3. 如果新闻涉及多个领域，可以选择多个分类
4. 输出必须是有效的JSON格式
5. 分类不能重复
6. 政治话题禁止归为职场，必须独立分类"""
        
        # 调用豆包LLM
        success, response = await self.doubao_client.call_llm(
            prompt=prompt,
            max_tokens=800,
            temperature=0.1
        )
        
        if not success:
            raise Exception(f"豆包LLM调用失败: {response}")
        
        try:
            # 清理响应（移除可能的markdown代码块）
            clean_response = response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
            clean_response = clean_response.strip()
            
            # 解析JSON响应
            result_data = json.loads(clean_response)
            
            # 验证分类结果
            categories = result_data.get("categories", [])
            thinking = result_data.get("thinking", "")
            
            # 确保categories是列表
            if not isinstance(categories, list):
                categories = [str(categories)]
            
            # 验证每个分类都在预定义范围内
            valid_categories = []
            for category in categories:
                if category in self.CLASSIFICATION_CATEGORIES:
                    valid_categories.append(category)
                else:
                    # 尝试找到最接近的分类
                    category_lower = category.lower()
                    for valid_category in self.CLASSIFICATION_CATEGORIES:
                        if valid_category in category_lower or category_lower in valid_category:
                            if valid_category not in valid_categories:
                                valid_categories.append(valid_category)
                            break
            
            # 如果没有有效分类，默认为"日常琐事"
            if not valid_categories:
                valid_categories = ["日常琐事"]
                thinking += f" (注：原始分类无效，已修正为'日常琐事')"
            
            return {
                "success": True,
                "method": "doubao_llm_cot_multi",
                "categories": valid_categories,
                "thinking": thinking,
                "title": title,
                "model": model
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}, 响应内容: {response}")
            raise Exception(f"LLM响应格式错误，无法解析JSON: {response[:200]}...")

    async def classify_batch_news(self, input_file: str, output_file: Optional[str] = None,
                                 title_column: str = "title", content_column: str = "content",
                                 model: str = "doubao-pro-32k",
                                 batch_size: int = 10) -> Dict[str, Any]:
        """
        批量处理新闻分类
        
        Args:
            input_file: 输入CSV文件路径
            output_file: 输出文件路径，None时自动生成
            title_column: 标题列名
            content_column: 内容列名
            model: 豆包模型名称
            batch_size: 批处理大小
            
        Returns:
            Dict: 处理结果统计
        """
        try:
            # 读取输入文件
            input_path = Path(input_file)
            if not input_path.exists():
                raise FileNotFoundError(f"输入文件不存在: {input_file}")
            
            df = pd.read_csv(input_path)
            total_count = len(df)
            
            # 验证必要列是否存在
            if title_column not in df.columns:
                raise ValueError(f"标题列 '{title_column}' 不存在")
            
            # 如果内容列不存在，创建空列
            if content_column not in df.columns:
                df[content_column] = ""
            
            logger.info(f"开始批量处理 {total_count} 条新闻")
            
            # 准备结果列表
            results = []
            processed_count = 0
            success_count = 0
            
            # 批量处理
            for i in range(0, total_count, batch_size):
                batch_df = df.iloc[i:i + batch_size]
                
                # 处理当前批次
                batch_tasks = []
                for _, row in batch_df.iterrows():
                    title = str(row[title_column]) if pd.notna(row[title_column]) else ""
                    content = str(row[content_column]) if pd.notna(row[content_column]) else ""
                    
                    task = self.classify_single_news(title, content, model)
                    batch_tasks.append(task)
                
                # 并发执行当前批次
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # 处理批次结果
                for j, result in enumerate(batch_results):
                    row_idx = i + j
                    original_row = df.iloc[row_idx].to_dict()
                    
                    if isinstance(result, Exception):
                        # 处理异常
                        result_dict = {
                            "success": False,
                            "error": str(result),
                            "title": original_row.get(title_column, ""),
                            "timestamp": datetime.now().isoformat()
                        }
                        print(f"❌ 第{row_idx+1}条分类失败: {original_row.get(title_column, '')[:50]}... - {str(result)}")
                    else:
                        result_dict = result
                        if result_dict.get("success", False):
                            success_count += 1
                            # 打印每条成功的分类结果
                            categories_str = "、".join(result_dict.get("categories", []))
                            print(f"✅ 第{row_idx+1}条: {result_dict.get('title', '')[:50]}... → {categories_str}")
                        else:
                            print(f"❌ 第{row_idx+1}条分类失败: {result_dict.get('title', '')[:50]}... - {result_dict.get('error', '未知错误')}")
                    
                    # 合并原始数据和分类结果
                    combined_result = {**original_row, **result_dict}
                    results.append(combined_result)
                    processed_count += 1
                
                # 显示进度
                progress = (processed_count / total_count) * 100
                logger.info(f"批量分类进度: {processed_count}/{total_count} ({progress:.1f}%)")
                
                # API限制：延迟一下避免频率限制
                if i + batch_size < total_count:
                    await asyncio.sleep(1.5)  # 1.5秒延迟
            
            # 保存结果
            if output_file is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = self.data_dir / f"news_classification_result_{timestamp}.csv"
            else:
                output_file = Path(output_file)
            
            # 将结果保存为DataFrame
            result_df = pd.DataFrame(results)
            result_df.to_csv(output_file, index=False, encoding='utf-8-sig')
            
            # 统计结果
            stats = {
                "total_processed": processed_count,
                "success_count": success_count,
                "error_count": processed_count - success_count,
                "success_rate": success_count / processed_count if processed_count > 0 else 0,
                "output_file": str(output_file),
                "model": model
            }
            
            logger.info(f"批量分类完成: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"批量分类失败: {e}")
            raise

    async def get_classification_stats(self, result_file: str) -> Dict[str, Any]:
        """
        获取分类结果统计信息
        
        Args:
            result_file: 结果文件路径
            
        Returns:
            Dict: 统计信息
        """
        try:
            result_path = Path(result_file)
            if not result_path.exists():
                raise FileNotFoundError(f"结果文件不存在: {result_file}")
            
            df = pd.read_csv(result_path)
            
            # 基础统计
            total_count = len(df)
            success_count = df['success'].sum() if 'success' in df.columns else 0
            
            # 分类分布统计（处理多标签）
            category_distribution = {}
            if 'categories' in df.columns:
                all_categories = []
                for categories_str in df['categories'].dropna():
                    try:
                        # 尝试解析JSON格式的categories
                        if categories_str.startswith('['):
                            categories = json.loads(categories_str)
                        else:
                            # 如果不是JSON格式，按逗号分割
                            categories = [cat.strip() for cat in str(categories_str).split(',')]
                        all_categories.extend(categories)
                    except:
                        # 如果解析失败，当作单个分类处理
                        all_categories.append(str(categories_str))
                
                # 统计每个分类的出现次数
                from collections import Counter
                category_counts = Counter(all_categories)
                category_distribution = dict(category_counts)
            
            # 方法分布统计
            method_distribution = {}
            if 'method' in df.columns:
                method_counts = df['method'].value_counts()
                method_distribution = method_counts.to_dict()
            
            return {
                "file_path": result_file,
                "total_count": total_count,
                "success_count": int(success_count),
                "success_rate": success_count / total_count if total_count > 0 else 0,
                "category_distribution": category_distribution,
                "method_distribution": method_distribution,
                "analysis_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"统计分析失败: {e}")
            raise

    def get_classification_categories(self) -> List[str]:
        """获取所有分类标准"""
        return self.CLASSIFICATION_CATEGORIES.copy()


# MCP工具函数
async def classify_single_news_tool(title: str, content: str = "", model: str = "doubao-pro-32k") -> Dict[str, Any]:
    """MCP工具：单条新闻分类"""
    server = NewsClassificationServer()
    return await server.classify_single_news(title, content, model)


async def classify_batch_news_tool(input_file: str, output_file: Optional[str] = None,
                                  title_column: str = "title", content_column: str = "content",
                                  model: str = "doubao-pro-32k",
                                  batch_size: int = 10) -> Dict[str, Any]:
    """MCP工具：批量新闻分类"""
    server = NewsClassificationServer()
    return await server.classify_batch_news(input_file, output_file, title_column, content_column, model, batch_size)


async def get_classification_stats_tool(result_file: str) -> Dict[str, Any]:
    """MCP工具：获取分类统计"""
    server = NewsClassificationServer()
    return await server.get_classification_stats(result_file)


def get_classification_categories_tool() -> List[str]:
    """MCP工具：获取分类标准"""
    server = NewsClassificationServer()
    return server.get_classification_categories()


# 简化的本地运行函数
async def main():
    """本地运行入口函数"""
    print("新闻分类服务器启动中...")
    
    # 检查环境变量
    api_key = os.getenv('ARK_API_KEY') or os.getenv('DOUBAO_API_KEY')
    if not api_key:
        print("❌ 错误: 未设置豆包API密钥")
        print("请设置环境变量 ARK_API_KEY 或 DOUBAO_API_KEY")
        return
    else:
        print(f"✅ 豆包API密钥已设置: {api_key[:10]}...")
    
    # 创建服务器实例
    server = NewsClassificationServer()
    
    # 测试单条新闻分类
    print("\n=== 测试单条新闻分类 ===")
    test_cases = [
        ("小米14 Ultra正式发布，搭载徕卡专业摄影系统", "小米公司今日正式发布了年度旗舰手机小米14 Ultra"),
        ("美国总统拜登会见中国外交部长", "双方就中美关系和地区安全问题进行深入交流"),
        ("《流浪地球3》定档春节，刘慈欣科幻作品再上银幕", ""),
        ("NBA总决赛今晚开战，湖人vs凯尔特人", ""),
        ("春天赏花攻略：北京最美的10个公园", "踏青赏花的最佳时节已经到来")
    ]
    
    for i, (title, content) in enumerate(test_cases, 1):
        print(f"\n📰 测试案例 {i}:")
        print(f"标题: {title}")
        
        result = await server.classify_single_news(title, content)
        
        if result.get("success", False):
            categories_str = "、".join(result['categories'])
            print(f"✅ 分类: {categories_str}")
            print(f"🧠 思考过程: {result['thinking']}")
        else:
            print(f"❌ 分类失败: {result.get('error', '未知错误')}")
    
    # 测试批量分类（如果有测试文件）
    test_file = "workspace/input/news_examples_content_hot.csv"
    if os.path.exists(test_file):
        print(f"\n=== 测试批量分类 ===")
        print(f"📁 处理文件: {test_file}")
        
        batch_result = await server.classify_batch_news(
            input_file=test_file,
            batch_size=3  # 小批次测试
        )
        
        print(f"\n📊 批量处理结果:")
        print(f"   总数: {batch_result['total_processed']}")
        print(f"   成功: {batch_result['success_count']}")
        print(f"   成功率: {batch_result['success_rate']:.2%}")
        print(f"   输出文件: {batch_result['output_file']}")
    else:
        print(f"\n⚠️  测试文件不存在: {test_file}")
    
    # 显示支持的分类
    print(f"\n=== 支持的分类标准 ({len(server.get_classification_categories())}个) ===")
    categories = server.get_classification_categories()
    for i in range(0, len(categories), 5):
        print("  " + "、".join(categories[i:i+5]))
    
    print("\n🎉 新闻分类服务器测试完成!")


if __name__ == "__main__":
    # 本地直接运行
    asyncio.run(main())