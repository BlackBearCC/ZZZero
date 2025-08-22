import pandas as pd

# 读取CSV文件
try:
    df = pd.read_csv('workspace/output/固化记忆标题更新_带标题.csv', encoding='utf-8')
    print("文件读取成功！")
    print(f"总行数: {len(df)}")
    print(f"列名: {df.columns.tolist()}")
    
    # 检查是否有标题列
    if '标题' in df.columns:
        print("\n标题列存在！")
        print(f"非空标题数量: {df['标题'].notna().sum()}")
        print(f"空标题数量: {df['标题'].isna().sum()}")
        
        # 显示前几个非空标题
        non_empty_titles = df[df['标题'].notna() & (df['标题'] != '')]['标题']
        if len(non_empty_titles) > 0:
            print("\n前5个生成的标题:")
            for i, title in enumerate(non_empty_titles.head(5)):
                print(f"  {i+1}. {title}")
        else:
            print("\n未找到任何生成的标题")
    else:
        print("\n标题列不存在！")
        
except Exception as e:
    print(f"读取文件时出错: {e}")