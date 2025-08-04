import pandas as pd
import asyncio
import os
from typing import Optional
import sys

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# 尝试加载.env文件
try:
    from dotenv import load_dotenv
    env_file = os.path.join(project_root, '.env')
    if os.path.exists(env_file):
        load_dotenv(env_file)
        print(f"已加载环境变量文件: {env_file}")
    else:
        print("未找到.env文件，使用系统环境变量")
except ImportError:
    print("未安装python-dotenv，使用系统环境变量")

from src.core.types import MessageRole, Message, LLMConfig
from src.llm.doubao import DoubaoLLM



class TitleGenerator:
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化标题生成器
        
        Args:
            api_key: 豆包API密钥，如果为None则从环境变量获取
        """
        self.api_key = api_key or os.getenv("ARK_API_KEY") or os.getenv("DOUBAO_API_KEY")
        if not self.api_key:
            print("错误: 未找到豆包API密钥")
            print("请设置以下环境变量之一:")
            print("  - ARK_API_KEY")
            print("  - DOUBAO_API_KEY")
            print()
            print("或者在main()函数中直接设置:")
            print("  generator = TitleGenerator(api_key='your-api-key-here')")
            raise ValueError("请设置豆包API密钥：ARK_API_KEY 或 DOUBAO_API_KEY 环境变量")
        
        # 初始化豆包LLM
        config = LLMConfig(
            provider="doubao",
            api_key=self.api_key,
            model_name=os.getenv("DOUBAO_MODEL_DEEPSEEKV3", "ep-20250312153153-npj4s"),
            temperature=0.3,
            max_tokens=2048
        )
        
        self.llm = DoubaoLLM(config)
    
    async def initialize(self):
        """初始化LLM"""
        await self.llm.initialize()
    
    async def generate_title(self, content: str) -> str:
        """
        为给定内容生成标题
        
        Args:
            content: 需要生成标题的内容
            
        Returns:
            生成的标题
        """
        system_prompt = """
请为以下内容生成一个简洁、口语化的一句话标题。这个标题将作为角色发起对话的话题索引，要求：

不要包含角色名字
语言简洁口语化
只返回标题文本，10个字以内，不要添加其他内容
确保标题全是有效实体名称，不要添加“回忆”“概念”“滋味”等抽象名词描述

示例：

输入：小学四年级的暑假，方知衡在陕西的亲戚家第一次尝到街边小摊的现做米皮。那是个炎热的午后，蝉鸣声此起彼伏，摊主大叔熟练地将米浆倒入蒸笼，几分钟后揭盖，一张晶莹剔透的米皮就做好了。淋上特制的辣椒油和醋，撒上黄瓜丝和豆芽，米皮入口的瞬间，米香和调料的香气在舌尖交融，成为他童年最难忘的味觉记忆之一。
输出：陕西米皮的做法


        """
        user_prompt = f"{content}"
        

        messages = [
            Message(
                role=MessageRole.SYSTEM,
                content=system_prompt
            ),
            Message(
                role=MessageRole.USER,
                content=user_prompt
            )
        ]
        
        try:
            response = await self.llm.generate(messages, temperature=0.7)
            return response.content.strip()
        except Exception as e:
            print(f"生成标题时出错: {e}")
            return "标题生成失败"
    
    async def batch_generate(self, input_file: str, output_file: str, content_column: str = "内容", batch_size: int = 20):
        """
        批量生成标题
        
        Args:
            input_file: 输入CSV文件路径
            output_file: 输出CSV文件路径
            content_column: 内容列的名称
            batch_size: 每批处理的数量
        """
        # 读取CSV文件
        df = pd.read_csv(input_file, encoding='utf-8')
        
        # 检查内容列是否存在
        if content_column not in df.columns:
            raise ValueError(f"CSV文件中未找到'{content_column}'列")
        
        # 初始化LLM
        await self.initialize()
        
        # 如果没有标题列，添加一个空的标题列
        if '标题' not in df.columns:
            df['标题'] = ""
        
        total_rows = len(df)
        processed_count = 0
        
        print(f"开始批量生成标题，总共{total_rows}行，每批处理{batch_size}行")
        
        # 按批次处理
        for batch_start in range(0, total_rows, batch_size):
            batch_end = min(batch_start + batch_size, total_rows)
            current_batch_size = batch_end - batch_start
            
            print(f"\n=== 处理第{batch_start+1}-{batch_end}行 (当前批次: {current_batch_size}行) ===")
            
            # 处理当前批次 - 异步并发生成
            async def process_single_item(index):
                row = df.iloc[index]
                content = row[content_column]
                
                if pd.isna(content) or content == "":
                    print(f"第{index+1}行: [空内容，跳过]")
                    return index, ""
                
                print(f"第{index+1}行: 正在生成标题...")
                
                try:
                    title = await self.generate_title(content)
                    # 打印生成的标题
                    print(f"第{index+1}行: 生成标题 -> '{title}'")
                    return index, title
                    
                except Exception as e:
                    error_title = f"生成失败: {str(e)}"
                    print(f"第{index+1}行: 标题生成失败 -> {error_title}")
                    return index, error_title
            
            # 创建并发任务列表
            tasks = [process_single_item(index) for index in range(batch_start, batch_end)]
            
            # 并发执行所有任务
            results = await asyncio.gather(*tasks)
            
            # 将结果写入DataFrame
            for index, title in results:
                df.iloc[index, df.columns.get_loc('标题')] = title
                if title and not title.startswith("生成失败"):
                    processed_count += 1
            
            # 批次完成后增量保存
            df.to_csv(output_file, index=False, encoding='utf-8')
            print(f"批次完成，已保存到: {output_file} (已处理 {processed_count}/{total_rows} 行)")
            
            # 批次间稍微长一点的延迟
            if batch_end < total_rows:
                print("等待3秒后继续下一批次...")
                await asyncio.sleep(3)
        
        print(f"\n所有标题生成完成！")
        print(f"总计处理: {processed_count}/{total_rows} 行")
        print(f"最终结果已保存到: {output_file}")


def main():
    # 输入和输出文件路径
    input_file = r"C:\Users\admin\PycharmProjects\ZZZero\workspace\input\固化记忆标题更新.csv"
    output_file = r"C:\Users\admin\PycharmProjects\ZZZero\workspace\output\固化记忆标题更新_带标题.csv"
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # 创建标题生成器并执行批量生成
    generator = TitleGenerator()
    
    # 运行异步任务 - 每批处理20个
    asyncio.run(generator.batch_generate(input_file, output_file, batch_size=20))


if __name__ == "__main__":
    # 注意：需要设置环境变量
    # os.environ["ARK_API_KEY"] = "your-api-key"
    # os.environ["DOUBAO_MODEL_NAME"] = "your-model-name"
    
    main()