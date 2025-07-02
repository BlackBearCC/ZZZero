#!/usr/bin/env python3
"""节假日生成工具 - 获取法定节假日和主要农历节日"""

import csv
import sys
from datetime import datetime, date
from pathlib import Path
import subprocess

# 配置参数
START_YEAR = 2025
YEARS_COUNT = 3
OUTPUT_FILE = 'config/holidays.csv'

def install_packages():
    """安装必需的第三方库"""
    packages = ['holidays', 'lunardate', 'sxtwl']
    
    for package in packages:
        try:
            if package == 'lunardate':
                import lunardate
                print(f"✓ {package} 已安装") 
            elif package == 'sxtwl':
                import sxtwl
                print(f"✓ {package} 已安装")
            else:
                import holidays
                print(f"✓ {package} 已安装")
        except ImportError:
            print(f"正在安装 {package}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])

def get_holidays_from_libraries(start_year=START_YEAR, years_count=YEARS_COUNT):
    """从第三方库获取节假日数据"""
    
    # 安装依赖
    install_packages()
    
    try:
        import holidays
        from lunardate import LunarDate
    except ImportError as e:
        print(f"导入失败: {e}，重新安装...")
        install_packages()
        import holidays
        from lunardate import LunarDate
    
    holidays_data = []
    years = list(range(start_year, start_year + years_count))
    
    print(f"📅 获取{start_year}-{start_year + years_count - 1}年节假日...")
    
    # 1. 获取中国法定节假日（holidays库）
    print("🇨🇳 获取法定节假日...")
    china_holidays = holidays.China(years=years)
    for holiday_date, name in china_holidays.items():
        holidays_data.append({
            'date': holiday_date.strftime('%Y-%m-%d'),
            'name': name,
            'type': 'national',
            'lunar': False,
            'description': f'中国法定节假日：{name}'
        })
    
    # 2. 获取主要农历节日（lunardate库）
    print("🏮 获取主要农历节日...")
    
    # 主要农历节日
    lunar_festivals = [
        (1, 15, '元宵节'),      # 正月十五
        (2, 2, '龙抬头'),       # 二月初二
        (5, 5, '端午节'),       # 五月初五  
        (7, 7, '七夕节'),       # 七月初七
        (7, 15, '中元节'),      # 七月十五
        (8, 15, '中秋节'),      # 八月十五
        (9, 9, '重阳节'),       # 九月初九
        (10, 15, '下元节'),     # 十月十五
        (12, 8, '腊八节'),      # 腊月初八
        (12, 23, '小年'),       # 腊月二十三
    ]
    
    for year in years:
        for lunar_month, lunar_day, festival_name in lunar_festivals:
            try:
                # 将农历日期转换为公历
                lunar_date = LunarDate(year, lunar_month, lunar_day)
                solar_date = lunar_date.toSolarDate()
                
                holidays_data.append({
                    'date': solar_date.strftime('%Y-%m-%d'),
                    'name': festival_name,
                    'type': 'traditional',
                    'lunar': True,
                    'description': f'传统农历节日：{festival_name}'
                })
            except Exception as e:
                print(f"⚠️  {year}年{festival_name}日期转换失败: {e}")
    
    # 3. 获取二十四节气（使用sxtwl库）
    print("🌱 获取二十四节气...")
    
    try:
        import sxtwl
        
        # 二十四节气名称
        solar_terms = [
            '立春', '雨水', '惊蛰', '春分', '清明', '谷雨',
            '立夏', '小满', '芒种', '夏至', '小暑', '大暑',
            '立秋', '处暑', '白露', '秋分', '寒露', '霜降',
            '立冬', '小雪', '大雪', '冬至', '小寒', '大寒'
        ]
        
        for year in years:
            try:
                # 获取该年的所有节气
                jieqi_list = sxtwl.getJieQiByYear(year)
                
                for i, jieqi_info in enumerate(jieqi_list):
                    if i < len(solar_terms):
                        term_name = solar_terms[i]
                        
                        # 使用jd属性转换为日期
                        day = sxtwl.JD2DD(jieqi_info.jd)
                        date_str = f"{day.Y:04d}-{day.M:02d}-{day.D:02d}"
                        
                        holidays_data.append({
                            'date': date_str,
                            'name': term_name,
                            'type': 'traditional',
                            'lunar': True,
                            'description': f'二十四节气：{term_name}'
                        })
                        
            except Exception as e:
                print(f"⚠️  {year}年二十四节气获取失败: {e}")
                    
    except ImportError:
        print("⚠️  sxtwl库未安装，跳过二十四节气")
        print("💡 可运行: pip install sxtwl 来获取精确的二十四节气")
    except Exception as e:
        print(f"⚠️  二十四节气获取失败: {e}")
    
    # 4. 添加现代节日（固定日期）
    print("🌍 添加现代节日...")
    modern_holidays = [
        ('01-01', '元旦'),      # 已在法定节假日中
        ('02-14', '情人节'),
        ('03-08', '妇女节'), 
        ('03-12', '植树节'),
        ('04-01', '愚人节'),
        ('05-01', '劳动节'),    # 已在法定节假日中
        ('05-04', '青年节'),
        ('06-01', '儿童节'),
        ('08-01', '建军节'),
        ('09-10', '教师节'),
        ('10-01', '国庆节'),    # 已在法定节假日中
        ('10-31', '万圣节'),
        ('11-11', '双十一'),
        ('12-24', '平安夜'),
        ('12-25', '圣诞节'),
        ('12-31', '跨年夜'),
    ]
    
    for year in years:
        for month_day, name in modern_holidays:
            # 检查是否已存在（避免与法定节假日重复）
            date_str = f'{year}-{month_day}'
            existing = any(h['date'] == date_str and h['name'] == name for h in holidays_data)
            
            if not existing:
                holidays_data.append({
                    'date': date_str,
                    'name': name,
                    'type': 'modern',
                    'lunar': False,
                    'description': f'现代节日：{name}'
                })
    
    # 按日期排序并去重
    seen = set()
    unique_holidays = []
    for holiday in sorted(holidays_data, key=lambda x: x['date']):
        key = (holiday['date'], holiday['name'])
        if key not in seen:
            seen.add(key)
            unique_holidays.append(holiday)
    
    return unique_holidays

def save_to_csv(holidays_data, output_file=OUTPUT_FILE):
    """保存到CSV文件"""
    output_dir = Path(output_file).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    fieldnames = ['date', 'name', 'type', 'lunar', 'description']
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for holiday in holidays_data:
            writer.writerow(holiday)
    
    print(f"✅ 保存到: {output_file}")
    print(f"📊 总计: {len(holidays_data)} 个节假日")
    
    # 统计
    type_counts = {}
    lunar_count = 0
    for holiday in holidays_data:
        type_counts[holiday['type']] = type_counts.get(holiday['type'], 0) + 1
        if holiday['lunar']:
            lunar_count += 1
    
    print("📈 分布:", ", ".join(f"{k}:{v}" for k, v in type_counts.items()))
    print(f"🌙 农历: {lunar_count}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='节假日生成工具')
    parser.add_argument('--start', type=int, default=START_YEAR, help=f'起始年份 (默认: {START_YEAR})')
    parser.add_argument('--years', type=int, default=YEARS_COUNT, help=f'年份数量 (默认: {YEARS_COUNT})')
    parser.add_argument('--output', default=OUTPUT_FILE, help=f'输出文件 (默认: {OUTPUT_FILE})')
    
    args = parser.parse_args()
    
    print(f"🎉 生成{args.start}-{args.start + args.years - 1}年节假日数据...")
    
    holidays_data = get_holidays_from_libraries(args.start, args.years)
    save_to_csv(holidays_data, args.output)
    
    print("✅ 完成!")

if __name__ == "__main__":
    main()