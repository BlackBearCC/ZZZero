# -*- coding: utf-8 -*-
"""
CSV文件唯一ID添加工具

功能：为CSV文件添加唯一序号ID，格式为99XXXNNNN
- 99: 固定前缀
- XXX: 基于路径的3位类别码 (000-通用，001-风景, 002-美食, 003-动物...)
- NNNN: 4位全局唯一序号

支持：
- 路径关键词分类
- 全局ID唯一性保证
- 重复处理检测
- 多种编码支持
"""

import csv
import json
import os
import hashlib
import sys
from datetime import datetime
from collections import defaultdict


def calculate_file_hash(filepath):
    """计算文件MD5哈希值"""
    hash_md5 = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
    except Exception as e:
        print(f"计算文件哈希失败: {e}")
        return None
    return hash_md5.hexdigest()


def classify_content(row):
    """
    根据路径关键词进行分类
    
    Args:
        row: CSV行数据
        
    Returns:
        str: 3位类别编码
    """
    # 将所有列内容合并为一个字符串进行匹配
    content = " ".join(str(cell) for cell in row).lower()
    
    # 路径关键词分类
    if "风景修" in content:
        return "001"
    elif "美食修" in content:
        return "002"
    elif "动物修" in content:
        return "003"
    else:
        # 默认分类（如果没有匹配到任何关键词）
        return "001"


def load_id_registry():
    """加载ID注册表"""
    registry_file = "id_registry.json"
    
    if os.path.exists(registry_file):
        try:
            with open(registry_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载ID注册表失败: {e}")
    
    # 返回默认结构
    return {
        "used_ids": [],
        "category_counters": {
            "001": 0,  # 风景修
            "002": 0,  # 美食修
            "003": 0   # 动物修
        },
        "files_processed": [],
        "last_update": datetime.now().isoformat()
    }


def save_id_registry(registry):
    """保存ID注册表"""
    registry_file = "id_registry.json"
    registry["last_update"] = datetime.now().isoformat()
    
    try:
        with open(registry_file, 'w', encoding='utf-8') as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存ID注册表失败: {e}")
        return False


def generate_unique_id(category_code, registry):
    """
    生成分类独立的唯一ID
    
    Args:
        category_code: 3位类别编码
        registry: ID注册表
        
    Returns:
        str: 9位唯一ID
    """
    # 确保分类计数器存在
    if "category_counters" not in registry:
        registry["category_counters"] = {
            "001": 0,  # 风景修
            "002": 0,  # 美食修
            "003": 0   # 动物修
        }
    
    # 如果当前分类不存在，初始化为0
    if category_code not in registry["category_counters"]:
        registry["category_counters"][category_code] = 0
    
    # 递增分类计数器
    registry["category_counters"][category_code] += 1
    sequence_num = f"{registry['category_counters'][category_code]:04d}"
    unique_id = f"99{category_code}{sequence_num}"
    
    # 检查是否已存在（保险起见）
    while unique_id in registry["used_ids"]:
        registry["category_counters"][category_code] += 1
        sequence_num = f"{registry['category_counters'][category_code]:04d}"
        unique_id = f"99{category_code}{sequence_num}"
        
        # 防止无限循环
        if registry["category_counters"][category_code] >= 9999:
            raise ValueError(f"类别 {category_code} 序号已达到上限（9999）")
    
    registry["used_ids"].append(unique_id)
    return unique_id


def check_file_processed(filepath, registry):
    """检查文件是否已处理过"""
    file_hash = calculate_file_hash(filepath)
    if not file_hash:
        return False, None
    
    for processed_file in registry["files_processed"]:
        if processed_file["hash"] == file_hash:
            return True, processed_file
    
    return False, None


def process_file(input_file, output_file=None):
    """
    处理CSV文件，添加唯一ID
    
    Args:
        input_file: 输入文件路径
        output_file: 输出文件路径（可选）
        
    Returns:
        bool: 处理是否成功
    """
    # 检查输入文件
    if not os.path.exists(input_file):
        print(f"错误：输入文件不存在 - {input_file}")
        return False
    
    # 确定输出文件名
    if output_file is None:
        base_name = os.path.splitext(input_file)[0]
        output_file = f"{base_name}_with_unique_id.csv"
    
    # 加载ID注册表
    registry = load_id_registry()
    
    # 检查文件是否已处理过
    is_processed, processed_info = check_file_processed(input_file, registry)
    if is_processed:
        print(f"警告：文件可能已处理过")
        print(f"  处理时间: {processed_info['processed_time']}")
        print(f"  输出文件: {processed_info['output_file']}")
        print(f"  记录数量: {processed_info['record_count']}")
        
        # 自动跳过已处理的文件
        print("自动跳过已处理的文件")
        return True
    
    # 尝试不同编码读取文件
    encodings = ['utf-8-sig', 'utf-8', 'gbk']
    rows = []
    headers = []
    
    for encoding in encodings:
        try:
            with open(input_file, 'r', encoding=encoding, newline='') as f:
                reader = csv.reader(f)
                headers = next(reader)
                rows = list(reader)
            print(f"成功读取文件（编码: {encoding}）")
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"读取文件失败 ({encoding}): {e}")
            continue
    
    if not rows:
        print("错误：无法读取文件，请检查文件格式和编码")
        return False
    
    # 统计信息
    category_stats = defaultdict(int)
    processed_rows = []
    
    print(f"开始处理 {len(rows)} 条记录...")
    
    # 处理每一行
    for i, row in enumerate(rows):
        if i % 10 == 0:
            print(f"处理进度: {i}/{len(rows)}")
        
        # 分类
        category_code = classify_content(row)
        category_stats[category_code] += 1
        
        # 生成唯一ID
        try:
            unique_id = generate_unique_id(category_code, registry)
            processed_row = [unique_id] + row
            processed_rows.append(processed_row)
        except ValueError as e:
            print(f"生成ID失败: {e}")
            return False
    
    # 写入输出文件
    output_headers = ['序号ID'] + headers
    
    try:
        with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(output_headers)
            writer.writerows(processed_rows)
        print(f"成功写入输出文件: {output_file}")
    except Exception as e:
        print(f"写入输出文件失败: {e}")
        return False
    
    # 记录处理信息
    processed_info = {
        "input_file": input_file,
        "output_file": output_file,
        "hash": calculate_file_hash(input_file),
        "processed_time": datetime.now().isoformat(),
        "record_count": len(rows)
    }
    
    registry["files_processed"].append(processed_info)
    
    # 保存注册表
    if not save_id_registry(registry):
        print("警告：ID注册表保存失败")
    
    # 输出统计信息
    print(f"\n✅ 处理完成")
    print(f"输出文件: {output_file}")
    print(f"总记录数: {len(rows)}")
    print(f"\n📊 分类统计:")
    
    category_names = {
        "001": "风景修",
        "002": "美食修", 
        "003": "动物修"
    }
    
    for category, count in sorted(category_stats.items()):
        category_name = category_names.get(category, f"未知类别{category}")
        current_counter = registry["category_counters"].get(category, 0)
        print(f"  99{category} ({category_name}): {count}条 (当前计数器: {current_counter})")
    
    print(f"\n🔢 各分类计数器状态:")
    for category, counter in sorted(registry["category_counters"].items()):
        category_name = category_names.get(category, f"未知类别{category}")
        print(f"  {category} ({category_name}): {counter}")
    
    print(f"\n下次处理时将从以上计数器继续...")
    
    # 生成CSV报告
    report_file = "category_counter_report.csv"
    try:
        with open(report_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['类别编码', '类别名称', '当前计数器', '最新ID范围'])
            
            for category, counter in sorted(registry["category_counters"].items()):
                category_name = category_names.get(category, f"未知类别{category}")
                if counter > 0:
                    id_range = f"99{category}0001 - 99{category}{counter:04d}"
                else:
                    id_range = "暂无"
                writer.writerow([category, category_name, counter, id_range])
        
        print(f"📋 计数器报告已保存: {report_file}")
    except Exception as e:
        print(f"保存报告失败: {e}")
    
    return True


def scan_csv_files():
    """扫描csv_data目录下的CSV文件"""
    csv_dir = "csv_data"
    if not os.path.exists(csv_dir):
        print(f"错误：{csv_dir} 目录不存在")
        return []
    
    csv_files = []
    for file in os.listdir(csv_dir):
        if file.endswith('.csv') and not file.endswith('_with_unique_id.csv'):
            csv_files.append(os.path.join(csv_dir, file))
    
    return csv_files


def show_file_menu(csv_files):
    """显示文件选择菜单"""
    print("\n" + "="*60)
    print("🎯 CSV文件唯一ID添加工具")
    print("="*60)
    print("📁 发现以下CSV文件:")
    print()
    
    for i, file in enumerate(csv_files, 1):
        filename = os.path.basename(file)
        print(f"  {i}. {filename}")
    
    print()
    print("💡 请输入数字编号选择要处理的文件 (输入0退出)")
    print("-"*60)


def main():
    """主函数"""
    # 默认使用的CSV文件
    default_csv_file = "csv_data/image_recognition_20250704_112047_with_story(1).csv"
    
    # 检查命令行参数
    auto_mode = len(sys.argv) > 1 and sys.argv[1] == '--auto'
    
    # 扫描CSV文件
    csv_files = scan_csv_files()
    
    # 如果默认文件存在但不在扫描列表中，则添加它
    if os.path.exists(default_csv_file) and default_csv_file not in csv_files:
        csv_files.insert(0, default_csv_file)  # 插入到第一个位置
    
    if not csv_files:
        print("❌ 在csv_data目录下没有找到可处理的CSV文件")
        print("💡 提示：确保文件在csv_data目录下，且不是以'_with_unique_id.csv'结尾的文件")
        return
    
    # 如果默认文件存在且在列表第一位，询问是否直接处理
    if csv_files and csv_files[0] == default_csv_file:
        default_filename = os.path.basename(default_csv_file)
        print(f"\n🎯 发现默认文件: {default_filename}")
        
        # 自动模式或用户确认
        if auto_mode:
            auto_process = 'y'
            print("自动模式启动，直接处理默认文件")
        else:
            auto_process = input("是否直接处理该文件？(y/n，默认为y): ").strip().lower()
        
        if auto_process in ['', 'y', 'yes', '是']:
            print(f"\n🚀 开始处理默认文件: {default_filename}")
            print("-"*60)
            
            success = process_file(default_csv_file)
            
            if success:
                print("\n🎯 任务完成！")
            else:
                print("\n❌ 任务失败！")
            return
    
    # 显示文件选择菜单
    while True:
        show_file_menu(csv_files)
        
        try:
            choice = input("👉 请选择: ").strip()
            
            if choice == '0':
                print("👋 退出程序")
                return
            
            if not choice.isdigit():
                print("❌ 请输入有效数字")
                continue
            
            choice_num = int(choice)
            
            if choice_num < 1 or choice_num > len(csv_files):
                print(f"❌ 请输入1-{len(csv_files)}之间的数字")
                continue
            
            # 处理选中的文件
            selected_file = csv_files[choice_num - 1]
            filename = os.path.basename(selected_file)
            
            print(f"\n🚀 开始处理文件: {filename}")
            print("-"*60)
            
            success = process_file(selected_file)
            
            if success:
                print("\n🎯 任务完成！")
                
                # 询问是否继续处理其他文件
                while True:
                    continue_choice = input("\n❓ 是否继续处理其他文件？(y/n): ").lower().strip()
                    if continue_choice in ['y', 'yes', '是']:
                        break
                    elif continue_choice in ['n', 'no', '否']:
                        print("👋 程序结束")
                        return
                    else:
                        print("❌ 请输入 y 或 n")
            else:
                print("\n❌ 任务失败！")
                
                # 询问是否重试或继续
                while True:
                    retry_choice = input("\n❓ 是否重试或处理其他文件？(r-重试/c-继续/q-退出): ").lower().strip()
                    if retry_choice in ['r', 'retry', '重试']:
                        break
                    elif retry_choice in ['c', 'continue', '继续']:
                        break
                    elif retry_choice in ['q', 'quit', '退出']:
                        return
                    else:
                        print("❌ 请输入 r(重试)、c(继续) 或 q(退出)")
                
                if retry_choice in ['q', 'quit', '退出']:
                    return
                
        except KeyboardInterrupt:
            print("\n\n👋 用户取消操作，程序退出")
            return
        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
            continue


if __name__ == "__main__":
    main()