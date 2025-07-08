#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSV处理工具模块

@author leo
@description 通用CSV文件处理工具，支持删除指定字段、检查重复数据、数据清理等功能
@classes CSVProcessor - CSV文件处理器主类
@functions 
    - remove_columns: 删除指定字段
    - check_duplicates: 检查字段内容重复
    - clean_keywords: 清理关键词重复
    - process_file: 处理单个文件
    - batch_process: 批量处理文件
@example 
    processor = CSVProcessor()
    processor.process_file("input.csv", remove_columns=["重要程度"], output_file="output.csv")
@dependencies pandas, argparse, pathlib
"""

import pandas as pd
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('csv_processor.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class CSVProcessor:
    """CSV文件处理器"""
    
    def __init__(self):
        self.processed_files = []
        self.duplicate_reports = {}
        
    def load_csv(self, file_path: str) -> pd.DataFrame:
        """加载CSV文件"""
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
            logger.info(f"成功加载文件: {file_path}, 形状: {df.shape}")
            return df
        except UnicodeDecodeError:
            try:
                df = pd.read_csv(file_path, encoding='gbk')
                logger.info(f"使用GBK编码加载文件: {file_path}, 形状: {df.shape}")
                return df
            except Exception as e:
                logger.error(f"加载文件失败: {file_path}, 错误: {e}")
                raise
        except Exception as e:
            logger.error(f"加载文件失败: {file_path}, 错误: {e}")
            raise
    
    def remove_columns(self, df: pd.DataFrame, columns_to_remove: List[str]) -> pd.DataFrame:
        """删除指定字段"""
        existing_columns = [col for col in columns_to_remove if col in df.columns]
        missing_columns = [col for col in columns_to_remove if col not in df.columns]
        
        if missing_columns:
            logger.warning(f"以下字段不存在，将被忽略: {missing_columns}")
        
        if existing_columns:
            df_cleaned = df.drop(columns=existing_columns)
            logger.info(f"已删除字段: {existing_columns}")
            logger.info(f"删除后形状: {df_cleaned.shape}")
            return df_cleaned
        else:
            logger.warning("没有找到要删除的字段")
            return df
    
    def check_duplicates(self, df: pd.DataFrame, columns: Optional[List[str]] = None) -> Dict:
        """检查字段内容重复"""
        if columns is None:
            columns = df.columns.tolist()
        
        duplicate_report = {
            "overall_duplicates": {},
            "field_analysis": {},
            "duplicate_rows": []
        }
        
        # 检查整行重复
        full_duplicates = df.duplicated(keep=False)
        if full_duplicates.any():
            duplicate_rows = df[full_duplicates].to_dict('records')
            duplicate_report["duplicate_rows"] = duplicate_rows
            logger.warning(f"发现 {len(duplicate_rows)} 行完全重复的数据")
        
        # 检查指定字段的重复
        for column in columns:
            if column in df.columns:
                # 检查单个字段的重复值
                value_counts = df[column].value_counts()
                duplicates = value_counts[value_counts > 1]
                
                if not duplicates.empty:
                    duplicate_report["field_analysis"][column] = {
                        "duplicate_count": len(duplicates),
                        "duplicate_values": duplicates.to_dict(),
                        "total_duplicate_rows": duplicates.sum() - len(duplicates)
                    }
                    logger.warning(f"字段 '{column}' 发现 {len(duplicates)} 个重复值")
                else:
                    duplicate_report["field_analysis"][column] = {
                        "duplicate_count": 0,
                        "message": "无重复值"
                    }
                    logger.info(f"字段 '{column}' 无重复值")
        
        return duplicate_report
    
    def analyze_keywords(self, df: pd.DataFrame, keyword_column: str = "关键词", separator: str = "|") -> Dict:
        """分析关键词重复情况"""
        if keyword_column not in df.columns:
            logger.warning(f"字段 '{keyword_column}' 不存在")
            return {}
        
        # 收集所有关键词及其出现位置
        keyword_positions = {}
        row_keywords = {}
        
        for row_idx, keywords_str in enumerate(df[keyword_column]):
            if pd.isna(keywords_str):
                continue
            
            # 分割关键词
            keywords = [kw.strip() for kw in str(keywords_str).split(separator)]
            keywords = [kw for kw in keywords if kw]  # 过滤空字符串
            
            row_keywords[row_idx] = keywords
            
            # 记录每个关键词的出现位置
            for kw in keywords:
                if kw not in keyword_positions:
                    keyword_positions[kw] = []
                keyword_positions[kw].append(row_idx)
        
        # 找出重复的关键词
        duplicate_keywords = {}
        for keyword, positions in keyword_positions.items():
            if len(positions) > 1:
                duplicate_keywords[keyword] = {
                    'positions': positions,
                    'count': len(positions),
                    'rows_info': []
                }
                
                # 收集包含该关键词的行的详细信息
                for pos in positions:
                    row_info = {
                        'row_index': pos,
                        'row_number': pos + 1,  # 显示用的行号（从1开始）
                        'full_keywords': row_keywords[pos],
                        'other_columns': {}
                    }
                    
                    # 收集其他列的信息（前3列）
                    for col in df.columns[:3]:
                        if col != keyword_column:
                            row_info['other_columns'][col] = df.iloc[pos][col]
                    
                    duplicate_keywords[keyword]['rows_info'].append(row_info)
        
        analysis_result = {
            'total_keywords': len(keyword_positions),
            'duplicate_keywords': duplicate_keywords,
            'duplicate_count': len(duplicate_keywords),
            'row_keywords': row_keywords
        }
        
        return analysis_result
    
    def clean_keywords(self, df: pd.DataFrame, keyword_column: str = "关键词", separator: str = "|", 
                      interactive: bool = False) -> pd.DataFrame:
        """清理关键词字段的重复项"""
        if keyword_column not in df.columns:
            logger.warning(f"字段 '{keyword_column}' 不存在")
            return df
        
        # 分析关键词重复情况
        analysis = self.analyze_keywords(df, keyword_column, separator)
        
        if not analysis or analysis['duplicate_count'] == 0:
            logger.info("未发现重复关键词")
            return df
        
        print(f"\n=== 关键词重复分析 ===")
        print(f"总关键词数: {analysis['total_keywords']}")
        print(f"重复关键词数: {analysis['duplicate_count']}")
        
        # 显示重复关键词详情
        keywords_to_clean = {}
        for keyword, info in analysis['duplicate_keywords'].items():
            print(f"\n关键词 '{keyword}' 出现 {info['count']} 次:")
            for row_info in info['rows_info']:
                other_cols = ", ".join([f"{k}: {v}" for k, v in row_info['other_columns'].items()])
                print(f"  行 {row_info['row_number']}: {other_cols}")
                print(f"    完整关键词: {separator.join(row_info['full_keywords'])}")
        
        if interactive:
            # 交互式选择要清理的关键词
            print(f"\n请选择要清理的重复关键词:")
            duplicate_list = list(analysis['duplicate_keywords'].keys())
            for i, keyword in enumerate(duplicate_list, 1):
                count = analysis['duplicate_keywords'][keyword]['count']
                print(f"{i}. '{keyword}' (出现{count}次)")
            
            print(f"{len(duplicate_list) + 1}. 全部清理")
            print("0. 跳过清理")
            
            while True:
                try:
                    choice = input(f"\n请选择 (1-{len(duplicate_list) + 1}, 0跳过): ").strip()
                    
                    if choice == "0":
                        print("跳过关键词清理")
                        return df
                    
                    choice_num = int(choice)
                    
                    if choice_num == len(duplicate_list) + 1:
                        # 清理全部
                        keywords_to_clean = analysis['duplicate_keywords']
                        break
                    elif 1 <= choice_num <= len(duplicate_list):
                        # 清理指定关键词
                        selected_keyword = duplicate_list[choice_num - 1]
                        keywords_to_clean[selected_keyword] = analysis['duplicate_keywords'][selected_keyword]
                        break
                    else:
                        print(f"无效选择，请输入 1-{len(duplicate_list) + 1} 或 0")
                        continue
                        
                except ValueError:
                    print("请输入有效数字")
                    continue
        else:
            # 非交互模式，清理所有重复
            keywords_to_clean = analysis['duplicate_keywords']
        
        if not keywords_to_clean:
            return df
        
        # 执行清理
        df_cleaned = df.copy()
        cleaned_rows = set()
        
        for keyword, info in keywords_to_clean.items():
            # 只保留第一次出现，删除后续出现
            positions = info['positions']
            keep_position = positions[0]  # 保留第一个
            remove_positions = positions[1:]  # 删除其余的
            
            for pos in remove_positions:
                # 从该行的关键词中删除这个重复的关键词
                keywords_str = df_cleaned.iloc[pos][keyword_column]
                if pd.isna(keywords_str):
                    continue
                
                keywords = [kw.strip() for kw in str(keywords_str).split(separator)]
                # 移除重复的关键词（只移除一次）
                if keyword in keywords:
                    keywords.remove(keyword)
                
                # 更新关键词字符串
                new_keywords_str = separator.join(keywords) if keywords else ""
                df_cleaned.iloc[pos, df_cleaned.columns.get_loc(keyword_column)] = new_keywords_str
                cleaned_rows.add(pos)
        
        logger.info(f"清理了 {len(keywords_to_clean)} 个重复关键词，影响 {len(cleaned_rows)} 行数据")
        
        # 显示清理结果
        if interactive and cleaned_rows:
            print(f"\n清理结果:")
            for keyword in keywords_to_clean.keys():
                positions = keywords_to_clean[keyword]['positions'][1:]  # 被删除的位置
                print(f"关键词 '{keyword}' 已从以下行中删除: {[p+1 for p in positions]}")
        
        return df_cleaned
    
    def generate_report(self, file_path: str, original_df: pd.DataFrame, 
                       processed_df: pd.DataFrame, duplicate_report: Dict, 
                       removed_columns: List[str]) -> str:
        """生成处理报告"""
        report = f"""
=== CSV文件处理报告 ===
文件路径: {file_path}
处理时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}

原始文件信息:
- 行数: {len(original_df)}
- 列数: {len(original_df.columns)}
- 字段: {list(original_df.columns)}

处理后文件信息:
- 行数: {len(processed_df)}
- 列数: {len(processed_df.columns)}
- 字段: {list(processed_df.columns)}

删除的字段: {removed_columns if removed_columns else '无'}

重复数据分析:
"""
        
        # 添加重复数据报告
        if duplicate_report["duplicate_rows"]:
            report += f"- 完全重复行数: {len(duplicate_report['duplicate_rows'])}\n"
        else:
            report += "- 无完全重复行\n"
        
        for field, analysis in duplicate_report["field_analysis"].items():
            if analysis["duplicate_count"] > 0:
                report += f"- 字段 '{field}': {analysis['duplicate_count']} 个重复值\n"
            else:
                report += f"- 字段 '{field}': 无重复值\n"
        
        return report
    
    def process_file(self, input_file: str, output_file: Optional[str] = None, 
                    remove_columns: Optional[List[str]] = None,
                    check_duplicate_columns: Optional[List[str]] = None,
                    clean_keyword_duplicates: bool = False,
                    keyword_column: str = "关键词",
                    keyword_separator: str = "|") -> Dict:
        """处理单个CSV文件"""
        
        logger.info(f"开始处理文件: {input_file}")
        
        # 加载文件
        original_df = self.load_csv(input_file)
        processed_df = original_df.copy()
        
        # 检查重复数据
        duplicate_report = self.check_duplicates(
            processed_df, 
            check_duplicate_columns or processed_df.columns.tolist()
        )
        
        # 清理关键词重复
        if clean_keyword_duplicates:
            processed_df = self.clean_keywords(processed_df, keyword_column, keyword_separator, interactive=False)
        
        # 删除指定字段
        removed_columns = []
        if remove_columns:
            processed_df = self.remove_columns(processed_df, remove_columns)
            removed_columns = [col for col in remove_columns if col in original_df.columns]
        
        # 生成输出文件名
        if output_file is None:
            input_path = Path(input_file)
            output_file = str(input_path.parent / f"{input_path.stem}_processed{input_path.suffix}")
        
        # 保存处理后的文件
        processed_df.to_csv(output_file, index=False, encoding='utf-8')
        logger.info(f"处理完成，输出文件: {output_file}")
        
        # 生成报告
        report = self.generate_report(input_file, original_df, processed_df, 
                                    duplicate_report, removed_columns)
        
        # 保存报告
        report_file = Path(output_file).parent / f"{Path(output_file).stem}_report.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"报告已保存: {report_file}")
        print(report)
        
        return {
            "input_file": input_file,
            "output_file": output_file,
            "report_file": str(report_file),
            "original_shape": original_df.shape,
            "processed_shape": processed_df.shape,
            "duplicate_report": duplicate_report,
            "removed_columns": removed_columns
        }
    
    def batch_process(self, input_pattern: str, **kwargs) -> List[Dict]:
        """批量处理文件"""
        from glob import glob
        
        files = glob(input_pattern)
        if not files:
            logger.error(f"未找到匹配的文件: {input_pattern}")
            return []
        
        results = []
        for file_path in files:
            try:
                result = self.process_file(file_path, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"处理文件 {file_path} 时出错: {e}")
                continue
        
        logger.info(f"批量处理完成，共处理 {len(results)} 个文件")
        return results


def interactive_mode():
    """交互式模式"""
    print("=== CSV 文件处理工具 (交互式模式) ===\n")
    
    # 获取config目录下的CSV文件
    config_dir = Path(__file__).parent.parent / "config"
    csv_files = list(config_dir.glob("*.csv"))
    
    if not csv_files:
        print(f"在 {config_dir} 目录下没有找到CSV文件")
        return
    
    # 显示文件列表
    print("可用的CSV文件:")
    for i, file_path in enumerate(csv_files, 1):
        print(f"{i}. {file_path.name}")
    
    print(f"{len(csv_files) + 1}. 自定义文件路径")
    print("0. 退出")
    
    while True:
        try:
            choice = input(f"\n请选择文件 (1-{len(csv_files) + 1}, 0退出): ").strip()
            
            if choice == "0":
                print("退出程序")
                return
            
            choice_num = int(choice)
            
            if choice_num == len(csv_files) + 1:
                # 自定义文件路径
                custom_path = input("请输入CSV文件的完整路径: ").strip()
                if not Path(custom_path).exists():
                    print(f"文件不存在: {custom_path}")
                    continue
                selected_file = custom_path
            elif 1 <= choice_num <= len(csv_files):
                selected_file = str(csv_files[choice_num - 1])
            else:
                print(f"无效选择，请输入 1-{len(csv_files) + 1} 或 0")
                continue
            
            break
            
        except ValueError:
            print("请输入有效数字")
            continue
    
    # 加载文件并显示字段信息
    processor = CSVProcessor()
    try:
        df = processor.load_csv(selected_file)
        print(f"\n文件: {Path(selected_file).name}")
        print(f"行数: {len(df)}")
        print(f"列数: {len(df.columns)}")
        print(f"字段: {list(df.columns)}")
        
        # 显示前几行数据
        print(f"\n前3行数据预览:")
        print(df.head(3).to_string())
        
    except Exception as e:
        print(f"加载文件失败: {e}")
        return
    
    # 选择操作
    print(f"\n可用操作:")
    print("1. 删除指定字段")
    print("2. 检查重复数据")
    print("3. 分析关键词重复（仅查看）")
    print("4. 清理关键词重复")
    print("5. 完整处理（删除字段+检查重复+清理关键词）")
    print("0. 返回文件选择")
    
    while True:
        try:
            operation = input("\n请选择操作 (1-5, 0返回): ").strip()
            
            if operation == "0":
                return interactive_mode()  # 重新开始
            
            operation_num = int(operation)
            if operation_num not in [1, 2, 3, 4, 5]:
                print("无效选择，请输入 1-5 或 0")
                continue
            
            break
            
        except ValueError:
            print("请输入有效数字")
            continue
    
    # 根据选择执行操作
    remove_columns = []
    check_duplicates = True
    clean_keywords = False
    keyword_column = "关键词"
    
    # 仅分析关键词重复（不处理）
    if operation_num == 3:
        keyword_column = input("请输入关键词字段名（默认'关键词'，直接回车使用默认）: ").strip()
        if not keyword_column:
            keyword_column = "关键词"
        
        if keyword_column in df.columns:
            print(f"\n正在分析字段 '{keyword_column}' 的关键词重复情况...")
            analysis = processor.analyze_keywords(df, keyword_column)
            if analysis and analysis['duplicate_count'] > 0:
                # 显示详细的重复分析
                print(f"\n=== 关键词重复分析 ===")
                print(f"总关键词数: {analysis['total_keywords']}")
                print(f"重复关键词数: {analysis['duplicate_count']}")
                
                for keyword, info in analysis['duplicate_keywords'].items():
                    print(f"\n关键词 '{keyword}' 出现 {info['count']} 次:")
                    for row_info in info['rows_info']:
                        other_cols = ", ".join([f"{k}: {v}" for k, v in row_info['other_columns'].items()])
                        print(f"  行 {row_info['row_number']}: {other_cols}")
                        print(f"    完整关键词: {'|'.join(row_info['full_keywords'])}")
                
                print(f"\n分析完成。")
            else:
                print(f"字段 '{keyword_column}' 中未发现重复关键词")
        else:
            print(f"字段 '{keyword_column}' 不存在")
        
        # 询问是否继续其他操作
        continue_choice = input("\n是否继续其他操作？(y/n): ").strip().lower()
        if continue_choice in ['y', 'yes']:
            return interactive_mode()
        else:
            return
    
    if operation_num in [1, 5]:
        # 删除字段
        print(f"\n当前字段: {list(df.columns)}")
        columns_input = input("请输入要删除的字段名（多个用逗号分隔，直接回车跳过）: ").strip()
        if columns_input:
            remove_columns = [col.strip() for col in columns_input.split(",")]
    
    if operation_num in [4, 5]:
        # 清理关键词
        keyword_column = input("请输入关键词字段名（默认'关键词'，直接回车使用默认）: ").strip()
        if not keyword_column:
            keyword_column = "关键词"
        
        if keyword_column in df.columns:
            # 首先分析关键词重复情况
            analysis = processor.analyze_keywords(df, keyword_column)
            if analysis and analysis['duplicate_count'] > 0:
                clean_keywords = True
                print(f"在字段 '{keyword_column}' 中发现 {analysis['duplicate_count']} 个重复关键词")
            else:
                print(f"字段 '{keyword_column}' 中未发现重复关键词")
                clean_keywords = False
        else:
            print(f"字段 '{keyword_column}' 不存在，跳过关键词清理")
            clean_keywords = False
    
    # 生成输出文件名
    input_path = Path(selected_file)
    output_file = str(input_path.parent / f"{input_path.stem}_processed{input_path.suffix}")
    
    custom_output = input(f"输出文件路径（默认: {output_file}，直接回车使用默认）: ").strip()
    if custom_output:
        output_file = custom_output
    
    # 执行处理
    try:
        print(f"\n开始处理...")
        
        # 如果需要清理关键词，先进行交互式清理
        if clean_keywords:
            print(f"\n开始分析关键词重复情况...")
            df_cleaned = processor.clean_keywords(df, keyword_column, "|", interactive=True)
            
            # 保存清理后的数据到临时文件
            temp_file = str(input_path.parent / f"{input_path.stem}_temp{input_path.suffix}")
            df_cleaned.to_csv(temp_file, index=False, encoding='utf-8')
            
            # 使用清理后的文件进行后续处理
            process_file = temp_file
        else:
            process_file = selected_file
        
        result = processor.process_file(
            process_file,
            output_file=output_file,
            remove_columns=remove_columns if remove_columns else None,
            check_duplicate_columns=None,  # 检查所有字段
            clean_keyword_duplicates=False,  # 已经在上面交互式处理了
            keyword_column=keyword_column if clean_keywords else "关键词"
        )
        
        # 如果使用了临时文件，删除它
        if clean_keywords:
            import os
            try:
                os.remove(temp_file)
            except:
                pass
        
        print(f"\n处理完成！")
        print(f"输出文件: {result['output_file']}")
        print(f"报告文件: {result['report_file']}")
        
        # 询问是否继续处理其他文件
        continue_choice = input("\n是否继续处理其他文件？(y/n): ").strip().lower()
        if continue_choice in ['y', 'yes']:
            interactive_mode()
        
    except Exception as e:
        print(f"处理失败: {e}")


def main():
    """命令行入口函数"""
    parser = argparse.ArgumentParser(description="CSV文件处理工具")
    parser.add_argument("input_file", nargs="?", help="输入CSV文件路径（可选，不提供则进入交互模式）")
    parser.add_argument("-o", "--output", help="输出文件路径（可选）")
    parser.add_argument("-r", "--remove-columns", nargs="+", help="要删除的字段名称")
    parser.add_argument("-d", "--check-duplicates", nargs="*", help="检查重复的字段名称（默认检查所有字段）")
    parser.add_argument("-c", "--clean-keywords", action="store_true", help="清理关键词字段的重复项")
    parser.add_argument("--keyword-column", default="关键词", help="关键词字段名称（默认：关键词）")
    parser.add_argument("--keyword-separator", default="|", help="关键词分隔符（默认：|）")
    parser.add_argument("-b", "--batch", action="store_true", help="批量处理模式（输入文件支持通配符）")
    parser.add_argument("-i", "--interactive", action="store_true", help="交互式模式")
    
    args = parser.parse_args()
    
    # 如果没有提供输入文件或明确指定交互模式，则启动交互模式
    if not args.input_file or args.interactive:
        interactive_mode()
        return
    
    processor = CSVProcessor()
    
    try:
        if args.batch:
            results = processor.batch_process(
                args.input_file,
                output_file=args.output,
                remove_columns=args.remove_columns,
                check_duplicate_columns=args.check_duplicates,
                clean_keyword_duplicates=args.clean_keywords,
                keyword_column=args.keyword_column,
                keyword_separator=args.keyword_separator
            )
            logger.info(f"批量处理完成，共处理 {len(results)} 个文件")
        else:
            result = processor.process_file(
                args.input_file,
                output_file=args.output,
                remove_columns=args.remove_columns,
                check_duplicate_columns=args.check_duplicates,
                clean_keyword_duplicates=args.clean_keywords,
                keyword_column=args.keyword_column,
                keyword_separator=args.keyword_separator
            )
            logger.info("文件处理完成")
            
    except Exception as e:
        logger.error(f"处理过程中出现错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()