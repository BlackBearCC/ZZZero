"""
游戏风格剧情表格生成器 - 生成可触发的剧情CSV表格
包含剧情ID、NPC、触发地点、前置条件、剧情名、剧情阶段、描述等信息
"""

import json
import asyncio
import csv
import random
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

from src.utils.logger import Logger
from src.agents.workflow.schedule_utils import ScheduleUtils

logger = Logger()

class GameStoryGenerator:
    """游戏风格剧情生成器"""
    
    def __init__(self, llm=None):
        if llm:
            self.llm = llm
        else:
            # 参考clean_schedule_planning的导入方式
            try:
                # 优先使用通义千问
                from src.llm.tongyi_langchian import ChatTongyi
                self.llm = ChatTongyi(model="qwen-max", top_p=0.7, streaming=False)
            except:
                try:
                    # 备用豆包模型
                    from src.llm.doubao_langchain import DaobaoChatModel
                    self.llm = DaobaoChatModel(temperature=0.9, max_tokens=4096)
                except Exception as e:
                    raise Exception(f"无法加载LLM模型: {e}")
        self.utils = ScheduleUtils()
    
    async def generate_character_storyline_with_llm(self, character_info: dict, llm) -> List[Dict[str, Any]]:
        """为单个角色生成游戏风格剧情线"""
        character_name = character_info.get("name", "")
        logger.info(f"📖 为{character_name}生成游戏风格剧情线...")
        
        # 加载角色基础信息
        with open("docs/基础人设.txt", "r", encoding="utf-8") as f:
            character_base = f.read()
        
        # 获取角色的活动地点和可触发剧情
        activity_locations = character_info.get("活动地点", [])
        existing_plots = character_info.get("可触发剧情", [])
        
        prompt = f"""
## 角色基础信息
{character_base}

## 目标NPC角色
{json.dumps(character_info, ensure_ascii=False, indent=2)}

## 任务说明
为方知衡与{character_name}设计游戏风格的剧情线。这是一个地点触发的剧情系统，主角到特定地点时可能随机触发剧情。

## 设计要求
1. **地点触发**：每个剧情都绑定到具体的活动地点
2. **顺序依赖**：剧情必须按照逻辑顺序触发，有明确的前置条件
3. **细分阶段**：将现有的可触发剧情细分成更详细的小阶段
4. **可扩展性**：为将来的支线剧情预留接口

## 角色活动地点
{', '.join(activity_locations)}

## 现有可触发剧情
{', '.join(existing_plots)}

## 输出格式
[
  {{
    "剧情ID": "char_001_01",
    "剧情名": "初次相遇",
    "剧情阶段": "偶然邂逅",
    "触发地点": "图书馆",
    "前置条件": "无",
    "描述": "方知衡在图书馆天文区域偶然遇到正在查阅天体物理资料的林晚，两人因为对同一本书的争夺而开始对话",
    "关键事件": ["图书馆相遇", "学术讨论", "交换联系方式"],
    "触发概率": "80%",
    "完成条件": "成功对话并交换联系方式",
    "解锁剧情": ["char_001_02"]
  }},
  {{
    "剧情ID": "char_001_02",
    "剧情名": "初次相遇",
    "剧情阶段": "学术交流", 
    "触发地点": "图书馆",
    "前置条件": "char_001_01",
    "描述": "再次在图书馆遇到林晚，两人开始就天文学话题进行深入交流",
    "关键事件": ["学术讨论深入", "发现共同兴趣", "约定下次见面"],
    "触发概率": "70%",
    "完成条件": "完成深度学术讨论",
    "解锁剧情": ["char_001_03"]
  }}
]

请基于{character_name}的现有剧情设定，生成详细的游戏风格剧情线。每个剧情阶段都要有明确的触发条件和完成标准。
"""
        
        try:
            response = await self.utils.generate_with_retry(llm, prompt, desc=f"生成{character_name}剧情线")
            if isinstance(response, list):
                return response
            else:
                logger.error(f"为{character_name}生成剧情线失败，返回格式错误")
                return []
                
        except Exception as e:
            logger.error(f"为{character_name}生成剧情线失败: {e}")
            return []
    
    async def generate_story_csv(self, character_name: str = "方知衡") -> str:
        """生成游戏风格剧情CSV文件"""
        logger.info(f"🎮 开始生成{character_name}的游戏剧情表格...")
        
        # 加载所有NPC角色
        with open("src/agents/workflow/yunhub_characters.json", "r", encoding="utf-8") as f:
            characters_data = json.load(f)
        
        # 逐个角色生成剧情线，使用质量模型
        all_storylines = []
        characters_list = characters_data.get("角色列表", {})
        
        for char_name, character_info in characters_list.items():
            # char_name从字典key获取，character_info需要添加name字段
            character_info["name"] = char_name
            if char_name:
                # 为剧情生成使用高质量模型（通义千问）
                try:
                    from src.llm.tongyi_langchian import ChatTongyi
                    high_quality_llm = ChatTongyi(model="qwen-max", top_p=0.7, streaming=False)
                except:
                    # 备选豆包模型
                    from src.llm.doubao_langchain import DaobaoChatModel
                    high_quality_llm = DaobaoChatModel(temperature=0.9, max_tokens=4096)
                
                storyline = await self.generate_character_storyline_with_llm(character_info, high_quality_llm)
                if storyline:
                    # 为每个剧情添加NPC信息
                    for story in storyline:
                        story["NPC"] = char_name
                    all_storylines.extend(storyline)
                    logger.info(f"✅ {char_name}的剧情线生成完成，共{len(storyline)}个阶段")
                
                # 避免过快请求
                await asyncio.sleep(1)
        
        # 生成CSV数据
        csv_data = []
        csv_headers = [
            "剧情ID", "NPC", "剧情名", "剧情阶段", "触发地点", 
            "前置条件", "描述", "关键事件", "触发概率", 
            "完成条件", "解锁剧情", "状态"
        ]
        
        logger.info("📋 整理剧情数据...")
        
        for story in all_storylines:
            csv_data.append([
                story.get("剧情ID", ""),
                story.get("NPC", ""),
                story.get("剧情名", ""),
                story.get("剧情阶段", ""),
                story.get("触发地点", ""),
                story.get("前置条件", "无"),
                story.get("描述", ""),
                "; ".join(story.get("关键事件", [])),
                story.get("触发概率", "50%"),
                story.get("完成条件", ""),
                "; ".join(story.get("解锁剧情", [])),
                "未触发"  # 初始状态
            ])
        
        # 保存CSV文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"output/{character_name}_game_story_{timestamp}.csv"
        
        Path("output").mkdir(exist_ok=True)
        
        with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(csv_headers)
            writer.writerows(csv_data)
        
        logger.info(f"✅ 游戏剧情表格已生成: {filename}")
        logger.info(f"📊 统计信息:")
        logger.info(f"   - 总剧情数: {len(csv_data)}")
        logger.info(f"   - 参与角色: {len(set(story.get('NPC', '') for story in all_storylines))}")
        logger.info(f"   - 触发地点: {len(set(story.get('触发地点', '') for story in all_storylines))}")
        
        return filename

# 便捷函数
async def generate_game_story(character_name: str = "方知衡") -> str:
    """生成游戏风格剧情表格"""
    generator = GameStoryGenerator()
    return await generator.generate_story_csv(character_name)

async def main():
    """测试函数"""
    filename = await generate_game_story()
    print(f"游戏剧情表格生成完成: {filename}")

if __name__ == "__main__":
    asyncio.run(main()) 