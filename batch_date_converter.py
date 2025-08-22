#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSV日期格式批量转换器
自动转换 CSV 文件中 "日期" 字段的格式从 2025/8/11 到 2025-08-11
"""

import pandas as pd
import re
from pathlib import Path
import os

def detect_and_convert_date(date_string):
    """检测并转换日期格式"""
    if pd.isna(date_string):
        return date_string
    
    date_string = str(date_string).strip()
    
    # 处理 2025/8/11 这样的格式
    if '/' in date_string:
        parts = date_string.split('/')
        if len(parts) == 3:
            try:
                if len(parts[0]) == 4:  # 年份在前: 2025/8/11
                    year, month, day = parts
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                else:  # 月份在前: 8/11/2025
                    month, day, year = parts
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            except:
                pass
    
    # 如果已经是正确格式
    if re.match(r'\d{4}-\d{2}-\d{2}', date_string):
        return date_string
    
    return date_string

def convert_csv_dates(input_file, output_file=None):
    """转换CSV文件中的日期格式"""
    try:
        # 读取CSV文件
        encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312']
        df = None
        
        for encoding in encodings:
            try:
                df = pd.read_csv(input_file, encoding=encoding)
                print(f"✅ 成功使用编码 {encoding} 读取文件")
                break
            except UnicodeDecodeError:
                continue
        
        if df is None:
            raise Exception("无法使用任何编码读取文件")
        
        print(f"📊 文件读取成功，共 {len(df)} 行数据")
        print(f"📋 列名: {list(df.columns)}")
        
        # 检查是否存在"日期"字段
        if '日期' not in df.columns:
            print("❌ 文件中未找到'日期'字段")
            return False
        
        # 转换日期字段
        print("\n🔄 开始转换日期格式...")
        
        converted_count = 0
        failed_count = 0
        
        original_dates = df['日期'].copy()
        
        for index, original_date in enumerate(original_dates):
            converted_date = detect_and_convert_date(original_date)
            
            if str(converted_date) != str(original_date):
                converted_count += 1
                df.at[index, '日期'] = converted_date
            
            # 显示前几个转换示例
            if converted_count <= 5 and str(converted_date) != str(original_date):
                print(f"   行 {index+2}: {original_date} → {converted_date}")
        
        print(f"\n✅ 转换完成:")
        print(f"   成功转换: {converted_count} 个日期")
        print(f"   保持不变: {len(df) - converted_count} 个日期")
        
        # 保存结果
        if output_file is None:
            input_path = Path(input_file)
            output_file = input_path.parent / f"{input_path.stem}_formatted{input_path.suffix}"
        
        df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"✅ 文件已保存: {output_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ 转换失败: {e}")
        return False

def main():
    """主函数"""
    input_file = "/mnt/c/Users/admin/PycharmProjects/ZZZero/workspace/batch_schedule_output/batch_schedules.csv"
    
    print("=" * 60)
    print("CSV 日期格式批量转换器")
    print("=" * 60)
    print(f"处理文件: {input_file}")
    
    if not Path(input_file).exists():
        print(f"❌ 文件不存在: {input_file}")
        return
    
    success = convert_csv_dates(input_file)
    
    if success:
        print("\n🎉 转换完成!")
    else:
        print("\n❌ 转换失败!")

if __name__ == "__main__":
    main()