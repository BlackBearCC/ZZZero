#!/usr/bin/env python
"""merge_model_params.py

异步脚本：
1. 从 src/workflow/模型参数.txt 读取所有模型参数。
2. 从 src/workflow/模型参数名排序.txt 读取模型排序（按文件中的顺序）。
3. 生成新文件 workspace/output/整理后的模型参数.txt，格式：
   <模型名>\n
   ============\n
   <对应参数行>\n
   ============\n
   每个模型之间空行分隔。

运行：
    python scripts/merge_model_params.py
"""

import asyncio
from pathlib import Path
from typing import Dict, List

# 源文件路径
PARAMS_FILE = Path("src/workflow/模型参数.txt")
ORDER_FILE = Path("src/workflow/模型参数名排序.txt")
# 输出文件路径
OUTPUT_FILE = Path("workspace/output/整理后的模型参数.txt")


async def read_lines(path: Path) -> List[str]:
    """异步读取文件所有行 (保持顺序)。"""
    return await asyncio.to_thread(path.read_text, encoding="utf-8")  # type: ignore


def parse_params_file(content: str) -> Dict[str, List[str]]:
    """解析模型参数文件 -> {模型名: [参数行,...]}"""
    params_map: Dict[str, List[str]] = {}
    current_name: str | None = None
    current_lines: List[str] = []

    for raw_line in content.splitlines():
        line = raw_line.rstrip("\n")
        if line.endswith(".yaml:"):
            # 如果已有模型正在收集，先保存
            if current_name:
                params_map[current_name] = current_lines
            # 新模型开始
            name_with_ext = line[:-1]  # 去掉尾部冒号
            # 去掉 .yaml 后缀 => 模型名
            current_name = name_with_ext[:-5] if name_with_ext.endswith(".yaml") else name_with_ext
            current_lines = []
        else:
            if line.strip():  # 跳过空行
                current_lines.append(line)
    # 收尾
    if current_name:
        params_map[current_name] = current_lines
    return params_map


def parse_order_file(content: str) -> List[str]:
    """解析排序文件 -> 按行顺序返回模型名列表。"""
    lines = content.splitlines()
    order: List[str] = []
    # 跳过首行表头
    for raw_line in lines[1:]:
        line = raw_line.strip()
        if not line:
            continue
        # 尝试按制表符或空格分割，第一列即 preset 名字
        if "\t" in line:
            preset = line.split("\t", 1)[0]
        else:
            preset = line.split(maxsplit=1)[0]
        order.append(preset)
    return order


async def write_output(order: List[str], params_map: Dict[str, List[str]]):
    """异步写入合并后的结果。"""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    def build_content() -> str:
        """按照顺序生成带序号的内容。"""
        sections: List[str] = []
        counter = 0  # 用于连续编号
        for preset in order:
            lines_list = params_map.get(preset)
            if not lines_list:
                # 如果 params 文件里没有对应项，跳过
                continue

            # 过滤逻辑：若存在 top_p < 0.05 或 top_k < 3，则跳过
            top_p_val: float | None = None
            top_k_val: float | None = None
            for l in lines_list:
                if l.strip().startswith("top_p:"):
                    try:
                        top_p_val = float(l.split(":", 1)[1].strip())
                    except ValueError:
                        pass
                if l.strip().startswith("top_k:"):
                    try:
                        top_k_val = float(l.split(":", 1)[1].strip())
                    except ValueError:
                        pass

            if (top_p_val is not None and top_p_val < 0.05) or (
                top_k_val is not None and top_k_val < 3
            ):
                # 跳过此模型
                continue

            counter += 1
            param_lines_str = "\n".join(lines_list)
            sections.append(
                f"{counter}. {preset}\n============\n{param_lines_str}\n============"
            )
        return "\n\n".join(sections) + "\n"

    content = await asyncio.to_thread(build_content)
    await asyncio.to_thread(OUTPUT_FILE.write_text, content, encoding="utf-8")


async def main():
    params_content, order_content = await asyncio.gather(
        read_lines(PARAMS_FILE), read_lines(ORDER_FILE)
    )

    params_map = await asyncio.to_thread(parse_params_file, params_content)
    order = await asyncio.to_thread(parse_order_file, order_content)
    await write_output(order, params_map)
    print(f"已生成: {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main()) 