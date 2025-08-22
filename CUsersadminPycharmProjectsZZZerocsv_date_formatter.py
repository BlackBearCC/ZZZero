#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSV日期格式转换器
交互式脚本，用于转换CSV文件中指定字段的日期格式
支持多种日期格式转换为 yyyy-mm-dd 格式
"""

import pandas as pd
import re
from datetime import datetime
from pathlib import Path
import os

class CSVDateFormatter:
    def __init__(self):
        self.df = None
        self.csv_file_path = None
        self.date_patterns = [
            # 常见日期格式模式
            (r'(\d{4})/(\d{1,2})/(\d{1,2})', '%Y/%m/%d'),  # 2025/8/11
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', '%Y-%m-%d'),  # 2025-8-11
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', '%m/%d/%Y'),  # 8/11/2025
            (r'(\d{1,2})-(\d{1,2})-(\d{4})', '%m-%d-%Y'),  # 8-11-2025
            (r'(\d{4})\.(\d{1,2})\.(\d{1,2})', '%Y.%m.%d'), # 2025.8.11
            (r'(\d{1,2})\.(\d{1,2})\.(\d{4})', '%m.%d.%Y'), # 8.11.2025
            (r'(\d{4})年(\d{1,2})月(\d{1,2})日', None),      # 中文格式
        ]
    
    def get_csv_file_path(self):
        """获取CSV文件路径"""
        print("=" * 60)
        print("CSV日期格式转换器")
        print("=" * 60)
        
        # 默认路径建议
        default_path = Path.cwd() / "workspace" / "batch_schedule_output" / "batch_schedules.csv"
        
        print(f"\n默认文件路径: {default_path}")
        print("\n选择输入方式:")
        print("1. 使用默认路径")
        print("2. 输入自定义路径")
        print("3. 拖拽文件到此窗口")
        
        choice = input("\n请选择 (1-3): ").strip()
        
        if choice == "1":
            self.csv_file_path = str(default_path)
        elif choice == "2":
            self.csv_file_path = input("请输入CSV文件完整路径: ").strip()
        elif choice == "3":
            print("请将CSV文件拖拽到此窗口，然后按回车:")
            self.csv_file_path = input().strip().strip('"\'')
        else:
            print("无效选择，使用默认路径")
            self.csv_file_path = str(default_path)
        
        # 清理路径
        self.csv_file_path = self.csv_file_path.replace('\\', '/')
        
        # 检查文件是否存在
        if not Path(self.csv_file_path).exists():
            print(f"❌ 文件不存在: {self.csv_file_path}")
            return False
        
        print(f"✅ 选择的文件: {self.csv_file_path}")
        return True
    
    def read_csv_file(self):
        """读取CSV文件"""
        try:
            # 尝试不同编码
            encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312']
            
            for encoding in encodings:
                try:
                    self.df = pd.read_csv(self.csv_file_path, encoding=encoding)
                    print(f"✅ 成功使用编码 {encoding} 读取文件")
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise Exception("无法使用任何编码读取文件")
                
            print(f"📊 文件读取成功，共 {len(self.df)} 行数据")
            print(f"📋 列名: {list(self.df.columns)}")
            return True
            
        except Exception as e:
            print(f"❌ 读取CSV文件失败: {e}")
            return False
    
    def select_date_field(self):
        """选择要转换的日期字段"""
        print("\n" + "=" * 60)
        print("选择要转换的日期字段")
        print("=" * 60)
        
        columns = list(self.df.columns)
        
        # 显示所有字段
        print("\n可用字段:")
        for i, col in enumerate(columns, 1):
            # 显示前几个值作为示例
            sample_values = []
            for j in range(min(3, len(self.df))):
                val = self.df.iloc[j][col]
                if pd.notna(val):
                    sample_values.append(str(val))
            
            sample_text = ", ".join(sample_values[:2])
            if len(sample_text) > 30:
                sample_text = sample_text[:30] + "..."
            
            print(f"  {i:2d}. {col} (示例: {sample_text})")
        
        # 让用户选择
        while True:
            try:
                choice = input(f"\n请选择要转换的字段 (1-{len(columns)}): ").strip()
                field_index = int(choice) - 1
                
                if 0 <= field_index < len(columns):
                    selected_field = columns[field_index]
                    print(f"✅ 选择的字段: {selected_field}")
                    return selected_field
                else:
                    print("❌ 无效选择，请重新输入")
            except ValueError:
                print("❌ 请输入数字")
    
    def preview_date_values(self, field_name):
        """预览日期字段的值"""
        print(f"\n📋 预览字段 '{field_name}' 的前10个值:")
        print("-" * 40)
        
        unique_formats = set()
        for i in range(min(10, len(self.df))):
            val = self.df.iloc[i][field_name]
            if pd.notna(val):
                val_str = str(val).strip()
                print(f"  行 {i+2}: {val_str}")
                unique_formats.add(val_str)
        
        print(f"\n🔍 检测到 {len(unique_formats)} 种不同的格式")
        return True
    
    def detect_date_format(self, date_string):
        """检测日期格式"""
        date_string = str(date_string).strip()
        
        # 中文格式特殊处理
        chinese_match = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_string)
        if chinese_match:
            year, month, day = chinese_match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # 其他格式
        for pattern, format_str in self.date_patterns:
            if re.match(pattern, date_string):
                try:
                    # 特殊处理不规则格式
                    if '/' in date_string and len(date_string.split('/')) == 3:
                        parts = date_string.split('/')
                        if len(parts[0]) == 4:  # 年份在前
                            year, month, day = parts
                        else:  # 月份在前
                            month, day, year = parts
                        
                        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    
                    elif '-' in date_string and len(date_string.split('-')) == 3:
                        parts = date_string.split('-')
                        if len(parts[0]) == 4:  # 年份在前
                            year, month, day = parts
                        else:  # 月份在前
                            month, day, year = parts
                        
                        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    
                    elif '.' in date_string and len(date_string.split('.')) == 3:
                        parts = date_string.split('.')
                        if len(parts[0]) == 4:  # 年份在前
                            year, month, day = parts
                        else:  # 月份在前
                            month, day, year = parts
                        
                        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                        
                except:
                    continue
        
        # 如果已经是正确格式
        if re.match(r'\d{4}-\d{2}-\d{2}', date_string):
            return date_string
        
        return None
    
    def convert_date_field(self, field_name):
        """转换日期字段"""
        print(f"\n🔄 开始转换字段 '{field_name}'...")
        
        converted_count = 0
        failed_count = 0
        failed_values = []
        
        # 创建新列存储转换结果
        new_values = []
        
        for index, row in self.df.iterrows():
            original_value = row[field_name]
            
            if pd.isna(original_value):
                new_values.append(original_value)
                continue
            
            converted_date = self.detect_date_format(original_value)
            
            if converted_date:
                new_values.append(converted_date)
                converted_count += 1
            else:
                new_values.append(original_value)  # 保持原值
                failed_count += 1
                if len(failed_values) < 5:  # 只记录前5个失败的
                    failed_values.append(f"行{index+2}: {original_value}")
        
        # 更新DataFrame
        self.df[field_name] = new_values
        
        # 显示转换结果
        print(f"✅ 转换完成:")
        print(f"   成功转换: {converted_count} 个值")
        print(f"   转换失败: {failed_count} 个值")
        
        if failed_values:
            print(f"\n⚠️  转换失败的值 (显示前5个):")
            for fv in failed_values:
                print(f"   {fv}")
        
        return converted_count > 0
    
    def preview_conversion_result(self, field_name):
        """预览转换结果"""
        print(f"\n📋 转换结果预览 (字段: {field_name}):")
        print("-" * 40)
        
        for i in range(min(10, len(self.df))):
            val = self.df.iloc[i][field_name]
            print(f"  行 {i+2}: {val}")
    
    def save_result(self):
        """保存转换结果"""
        print("\n" + "=" * 60)
        print("保存转换结果")
        print("=" * 60)
        
        # 生成输出文件名
        input_path = Path(self.csv_file_path)
        output_path = input_path.parent / f"{input_path.stem}_formatted{input_path.suffix}"
        
        print(f"\n建议的输出文件名: {output_path}")
        
        choice = input("\n选择保存方式:\n1. 使用建议文件名\n2. 自定义文件名\n3. 覆盖原文件\n请选择 (1-3): ").strip()
        
        if choice == "2":
            custom_path = input("请输入输出文件路径: ").strip()
            output_path = Path(custom_path)
        elif choice == "3":
            output_path = input_path
            confirm = input("⚠️  确定要覆盖原文件吗? (y/N): ").strip().lower()
            if confirm != 'y':
                print("❌ 取消保存")
                return False
        
        try:
            self.df.to_csv(output_path, index=False, encoding='utf-8-sig')
            print(f"✅ 文件已保存: {output_path}")
            return True
        except Exception as e:
            print(f"❌ 保存失败: {e}")
            return False
    
    def run(self):
        """运行主程序"""
        # 1. 获取文件路径
        if not self.get_csv_file_path():
            return
        
        # 2. 读取CSV文件
        if not self.read_csv_file():
            return
        
        # 3. 选择日期字段
        field_name = self.select_date_field()
        if not field_name:
            return
        
        # 4. 预览字段值
        self.preview_date_values(field_name)
        
        # 5. 确认转换
        confirm = input(f"\n❓ 确定要转换字段 '{field_name}' 的日期格式吗? (Y/n): ").strip().lower()
        if confirm and confirm != 'y':
            print("❌ 取消转换")
            return
        
        # 6. 执行转换
        if self.convert_date_field(field_name):
            # 7. 预览结果
            self.preview_conversion_result(field_name)
            
            # 8. 保存结果
            save_choice = input(f"\n❓ 要保存转换结果吗? (Y/n): ").strip().lower()
            if not save_choice or save_choice == 'y':
                self.save_result()
        
        print("\n🎉 程序执行完成!")

def main():
    """主函数"""
    try:
        formatter = CSVDateFormatter()
        formatter.run()
    except KeyboardInterrupt:
        print("\n\n❌ 用户中断程序")
    except Exception as e:
        print(f"\n❌ 程序执行出错: {e}")
    
    input("\n按回车键退出...")

if __name__ == "__main__":
    main()