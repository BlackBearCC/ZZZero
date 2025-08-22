import pandas as pd
import os

# 创建一个小的测试CSV文件
test_data = {
    '内容': [
        '这是第一条测试内容，用来测试标题生成功能',
        '这是第二条测试内容，看看能否正确保存标题',
        '第三条内容，验证标题列是否能正确添加到CSV中'
    ]
}

test_df = pd.DataFrame(test_data)
test_input_file = 'test_input.csv'
test_output_file = 'test_output.csv'

# 保存测试输入文件
test_df.to_csv(test_input_file, index=False, encoding='utf-8')
print(f"创建测试输入文件: {test_input_file}")

# 模拟添加标题列的过程
print("\n模拟标题生成过程...")
df = pd.read_csv(test_input_file, encoding='utf-8')

# 添加标题列
if '标题' not in df.columns:
    df['标题'] = ""
    print("已添加新的'标题'列")

# 模拟为每行添加标题
for index, row in df.iterrows():
    title = f"测试标题{index+1}"
    df.at[index, '标题'] = title
    print(f"第{index+1}行: 设置标题 -> '{title}'")

# 保存结果
df.to_csv(test_output_file, index=False, encoding='utf-8')
print(f"\n保存到: {test_output_file}")

# 验证保存结果
print("\n验证保存结果...")
saved_df = pd.read_csv(test_output_file, encoding='utf-8')
print(f"列名: {saved_df.columns.tolist()}")
print(f"标题列内容:")
for i, title in enumerate(saved_df['标题']):
    print(f"  第{i+1}行: {title}")

# 清理测试文件
os.remove(test_input_file)
os.remove(test_output_file)
print(f"\n已清理测试文件")