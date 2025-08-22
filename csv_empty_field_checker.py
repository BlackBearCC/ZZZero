#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSV空字段检查器
分析CSV文件中的空字段，生成详细报告
"""

import csv
import pandas as pd
from collections import defaultdict
import os
from pathlib import Path

class CSVEmptyFieldChecker:
    def __init__(self, csv_file_path):
        self.csv_file_path = csv_file_path
        self.expected_fields = [
            '日期', '星期', '节日信息', '季节', '天气', '主题', 
            '周期计划', '每日计划', '每日总结', '涉及角色', 
            '角色简介', '上午', '中午', '下午', '晚上', '夜间'
        ]
        self.empty_fields_report = defaultdict(list)
        self.row_analysis = []
        # 不参与检查的字段
        self.excluded_fields = {"批次总结"}
        
    def read_csv_file(self):
        """读取CSV文件"""
        try:
            # 尝试不同编码
            encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312']
            
            for encoding in encodings:
                try:
                    self.df = pd.read_csv(self.csv_file_path, encoding=encoding)
                    print(f"成功使用编码 {encoding} 读取文件")
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise Exception("无法使用任何编码读取文件")
                
            print(f"文件读取成功，共 {len(self.df)} 行数据")
            print(f"列名: {list(self.df.columns)}")

            # 读取后立即删除指定列（如存在）
            removed_cols = [c for c in self.excluded_fields if c in self.df.columns]
            if removed_cols:
                self.df.drop(columns=removed_cols, inplace=True)
                print(f"已删除列: {removed_cols}")
            return True
            
        except Exception as e:
            print(f"读取CSV文件失败: {e}")
            return False
    
    def check_empty_fields(self):
        """检查空字段"""
        if not hasattr(self, 'df'):
            print("请先读取CSV文件")
            return
            
        total_rows = len(self.df)
        considered_columns = [col for col in self.df.columns if col not in self.excluded_fields]
        
        # 检查每一行
        for index, row in self.df.iterrows():
            row_num = index + 2  # +2 因为pandas从0开始，加上标题行
            empty_fields = []
            
            # 检查每个字段
            for field in considered_columns:
                value = row[field]
                # 检查是否为空值（NaN、空字符串、只有空白字符）
                if pd.isna(value) or str(value).strip() == '' or str(value).strip() == 'nan':
                    empty_fields.append(field)
                    self.empty_fields_report[field].append(row_num)
            
            # 记录行分析结果
            if empty_fields:
                self.row_analysis.append({
                    'row_number': row_num,
                    'empty_fields': empty_fields,
                    'empty_count': len(empty_fields),
                    'completion_rate': round((len(considered_columns) - len(empty_fields)) / max(len(considered_columns), 1) * 100, 2)
                })
    
    def generate_report(self):
        """生成详细报告"""
        if not self.empty_fields_report and not self.row_analysis:
            return "所有字段都已填写，无空值！"
        
        report = []
        report.append("=" * 60)
        report.append("CSV空字段检查报告")
        report.append("=" * 60)
        
        # 文件基本信息
        report.append(f"\n文件路径: {self.csv_file_path}")
        report.append(f"总行数: {len(self.df)}")
        report.append(f"总列数: {len(self.df.columns)}")
        
        # 字段列表
        report.append(f"\n字段列表:")
        for i, col in enumerate(self.df.columns, 1):
            report.append(f"  {i:2d}. {col}")
        
        # 按字段统计空值
        report.append(f"\n按字段统计空值:")
        report.append("-" * 40)
        considered_columns = [col for col in self.df.columns if col not in self.excluded_fields]
        total_empty_count = 0
        for field in considered_columns:
            empty_count = len(self.empty_fields_report[field])
            total_empty_count += empty_count
            percentage = round(empty_count / len(self.df) * 100, 2)
            
            if empty_count > 0:
                report.append(f"字段 '{field}': {empty_count} 个空值 ({percentage}%)")
                
                # 显示空值所在行号（限制显示数量）
                empty_rows = self.empty_fields_report[field]
                if len(empty_rows) <= 10:
                    report.append(f"  空值行号: {empty_rows}")
                else:
                    report.append(f"  空值行号: {empty_rows[:10]}... (还有{len(empty_rows)-10}个)")
                report.append("")
        
        # 按行统计空值
        if self.row_analysis:
            report.append(f"\n按行统计空值 (有空值的行):")
            report.append("-" * 40)
            
            # 按空字段数量排序
            sorted_rows = sorted(self.row_analysis, key=lambda x: x['empty_count'], reverse=True)
            
            for row_info in sorted_rows:
                report.append(f"第 {row_info['row_number']} 行: {row_info['empty_count']} 个空字段 "
                            f"(完整度: {row_info['completion_rate']}%)")
                report.append(f"  空字段: {row_info['empty_fields']}")
                report.append("")
        
        # 汇总统计
        report.append(f"\n汇总统计:")
        report.append("-" * 40)
        report.append(f"总空值数量: {total_empty_count}")
        report.append(f"有空值的行数: {len(self.row_analysis)}")
        report.append(f"空值行占比: {round(len(self.row_analysis) / len(self.df) * 100, 2)}%")
        
        # 最需要关注的字段
        most_empty_fields = sorted(
            [(field, len(rows)) for field, rows in self.empty_fields_report.items() if len(rows) > 0],
            key=lambda x: x[1], reverse=True
        )
        
        if most_empty_fields:
            report.append(f"\n最需要关注的字段 (空值最多):")
            report.append("-" * 40)
            for i, (field, count) in enumerate(most_empty_fields[:5], 1):
                percentage = round(count / len(self.df) * 100, 2)
                report.append(f"{i}. {field}: {count} 个空值 ({percentage}%)")
        
        return "\n".join(report)
    
    def save_report_to_file(self, output_file=None):
        """保存报告到文件"""
        if output_file is None:
            base_name = os.path.splitext(os.path.basename(self.csv_file_path))[0]
            output_file = f"{base_name}_empty_fields_report.txt"
        
        report_content = self.generate_report()
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            print(f"\n报告已保存到: {output_file}")
            return output_file
        except Exception as e:
            print(f"保存报告失败: {e}")
            return None
    
    def get_empty_rows_detail(self):
        """获取空行详细信息"""
        if not self.row_analysis:
            return "没有发现空字段"
        
        details = []
        for row_info in sorted(self.row_analysis, key=lambda x: x['row_number']):
            details.append(f"行 {row_info['row_number']}: 空字段 {row_info['empty_fields']}")
        
        return "\n".join(details)

def main():
    """主函数"""
    csv_file = str(
        Path(__file__).resolve().parent
        / "workspace"
        / "batch_schedule_output"
        / "batch_schedules.csv"
    )
    
    print("开始检查CSV文件空字段...")
    checker = CSVEmptyFieldChecker(csv_file)
    
    # 读取文件
    if not checker.read_csv_file():
        return
    
    # 检查空字段
    checker.check_empty_fields()
    
    # 生成并显示报告
    report = checker.generate_report()
    print(report)
    
    # 保存报告
    checker.save_report_to_file()
    
    # 显示空行详细信息
    print("\n" + "=" * 60)
    print("空行详细位置:")
    print("=" * 60)
    print(checker.get_empty_rows_detail())

if __name__ == "__main__":
    main()