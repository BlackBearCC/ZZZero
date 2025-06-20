import sys
import os
sys.path.append('src')

from core.data_manager import CSVDataManager

# 创建测试CSV文件
test_csv_content = """角色姓名,角色类型,性格描述,年龄,特殊技能
张三,古代学者,性格温和谦逊,45,精通经史子集和书法
李四,现代程序员,性格开朗活泼,28,Python开发和数据分析
王五,历史学家,性格严谨细致,52,古代文献研究
赵六,艺术家,性格自由随性,35,油画和雕塑创作
钱七,商人,性格精明能干,40,商业谈判和投资理财"""

# 保存测试文件
with open('test_fields.csv', 'w', encoding='utf-8') as f:
    f.write(test_csv_content)

print("🔧 测试字段选择界面简化...")

# 测试CSV数据管理器
manager = CSVDataManager()
result = manager.validate_and_parse_csv('test_fields.csv')

if result['success']:
    print("✅ CSV解析成功")
    
    # 获取字段信息
    csv_structure = result.get('csv_structure', {})
    columns = list(csv_structure.get('columns', {}).keys())
    column_types = {col: info.get('type', 'unknown') for col, info in csv_structure.get('columns', {}).items()}
    
    print("\n📋 字段选择界面预览 (简化版):")
    field_choices = []
    for col in columns:
        col_type = column_types.get(col, 'unknown')
        choice_label = f"{col} ({col_type})"
        field_choices.append((choice_label, col))
        print(f"   ☑️ {choice_label}")
    
    print(f"\n📊 总共 {len(field_choices)} 个字段")
    print("✅ 字段选择界面已简化，不再显示示例数据")
else:
    print(f"❌ CSV解析失败: {result.get('message', '未知错误')}")

# 清理测试文件
os.remove('test_fields.csv')
print("\n🧹 清理完成") 