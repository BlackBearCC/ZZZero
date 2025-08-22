import pandas as pd
import os

def test_new_save_logic():
    """测试新的保存逻辑"""
    
    # 创建测试数据
    test_data = {
        'ID': [1, 2, 3],
        '内容': [
            '这是第一条测试内容，用来测试新的保存逻辑',
            '这是第二条测试内容，验证所有字段都能保留',
            '第三条内容，确保标题列正确添加'
        ],
        '分类': ['类型A', '类型B', '类型C'],
        '时间': ['2025-01-01', '2025-01-02', '2025-01-03']
    }
    
    # 创建原始DataFrame
    original_df = pd.DataFrame(test_data)
    test_input = 'test_original.csv'
    test_output = 'test_with_titles.csv'
    
    # 保存原始文件
    original_df.to_csv(test_input, index=False, encoding='utf-8')
    print("创建测试原始文件:")
    print(f"列: {original_df.columns.tolist()}")
    print(f"行数: {len(original_df)}")
    
    # 模拟新的保存逻辑
    print("\n模拟新的保存逻辑...")
    
    # 1. 读取原始文件
    source_df = pd.read_csv(test_input, encoding='utf-8')
    
    # 2. 创建结果DataFrame（包含所有原始列）
    result_df = source_df.copy()
    
    # 3. 添加标题列
    if '标题' not in result_df.columns:
        result_df['标题'] = ""
        print("已添加标题列")
    
    # 4. 模拟生成标题
    for index, row in result_df.iterrows():
        content = row['内容']
        title = f"标题{index+1}: 测试标题"
        result_df.at[index, '标题'] = title
        print(f"第{index+1}行: 生成标题 -> '{title}'")
    
    # 5. 保存新文件（包含所有原始列 + 标题列）
    result_df.to_csv(test_output, index=False, encoding='utf-8')
    print(f"\n已保存到: {test_output}")
    
    # 6. 验证保存结果
    saved_df = pd.read_csv(test_output, encoding='utf-8')
    print("\n验证保存结果:")
    print(f"原始列数: {len(original_df.columns)}")
    print(f"保存列数: {len(saved_df.columns)}")
    print(f"原始列: {original_df.columns.tolist()}")
    print(f"保存列: {saved_df.columns.tolist()}")
    
    # 检查所有原始列是否都保留
    missing_columns = set(original_df.columns) - set(saved_df.columns)
    if missing_columns:
        print(f"警告: 丢失的列: {missing_columns}")
    else:
        print("✓ 所有原始列都已保留")
    
    # 检查标题列
    if '标题' in saved_df.columns:
        filled_titles = saved_df['标题'].notna() & (saved_df['标题'] != '')
        print(f"✓ 标题列存在，共有 {filled_titles.sum()} 个非空标题")
    else:
        print("✗ 标题列不存在")
    
    # 显示最终结果
    print("\n最终保存的数据:")
    print(saved_df.to_string())
    
    # 清理测试文件
    os.remove(test_input)
    os.remove(test_output)
    print("\n测试完成，已清理临时文件")

if __name__ == "__main__":
    test_new_save_logic()