#!/usr/bin/env python3
"""
测试日期库功能和工具参数
"""
from datetime import datetime

def test_date_libs():
    """测试日期库"""
    print("🗓️ 测试日期库功能...")
    
    # 测试日期
    test_date = datetime(2025, 6, 24)
    print(f"测试日期: {test_date.strftime('%Y年%m月%d日')}")
    
    # 测试星期几
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday = weekdays[test_date.weekday()]
    print(f"星期: {weekday}")
    
    # 测试zhdate库
    print("\n📅 测试zhdate库（农历）:")
    try:
        from zhdate import ZhDate
        lunar = ZhDate.from_datetime(test_date)
        print(f"✅ 农历: {lunar.chinese()}")
        print(f"✅ 年份: {lunar.lunar_year}")
        print(f"✅ 月份: {lunar.lunar_month}")
        print(f"✅ 日期: {lunar.lunar_day}")
    except ImportError:
        print("❌ zhdate库未安装")
    except Exception as e:
        print(f"❌ zhdate库错误: {e}")
    
    # 测试holidays库
    print("\n🎉 测试holidays库（节日）:")
    try:
        import holidays
        
        cn_holidays = holidays.China(years=2025)
        us_holidays = holidays.UnitedStates(years=2025)
        
        date_obj = test_date.date()
        
        print(f"✅ holidays库可用")
        print(f"📊 中国节日数量: {len(cn_holidays)}")
        print(f"📊 美国节日数量: {len(us_holidays)}")
        
        if date_obj in cn_holidays:
            print(f"🇨🇳 中国节日: {cn_holidays[date_obj]}")
        else:
            print("🇨🇳 中国节日: 无")
            
        if date_obj in us_holidays:
            print(f"🇺🇸 美国节日: {us_holidays[date_obj]}")
        else:
            print("🇺🇸 美国节日: 无")
            
        # 测试几个已知节日
        print("\n📋 已知节日测试:")
        test_dates = [
            (2025, 1, 1, "元旦"),
            (2025, 12, 25, "圣诞节"),
            (2025, 10, 1, "国庆节")
        ]
        
        for year, month, day, name in test_dates:
            date_check = datetime(year, month, day).date()
            cn_result = cn_holidays.get(date_check, "无")
            us_result = us_holidays.get(date_check, "无")
            print(f"  {year}-{month:02d}-{day:02d} {name}: 中国={cn_result}, 美国={us_result}")
            
    except ImportError:
        print("❌ holidays库未安装")
    except Exception as e:
        print(f"❌ holidays库错误: {e}")

def test_tool_params():
    """测试工具参数"""
    print("\n🛠️ 测试工具参数功能...")
    
    # 模拟不同的max_days参数
    test_params = [
        {},  # 默认参数
        {"max_days": 7},  # 7天
        {"max_days": 30},  # 30天
    ]
    
    for i, params in enumerate(test_params, 1):
        max_days = params.get("max_days", 3)  # 默认3天
        print(f"  测试{i}: 参数={params} -> max_days={max_days}")

if __name__ == "__main__":
    test_date_libs()
    test_tool_params()
    print("\n🎉 测试完成!") 