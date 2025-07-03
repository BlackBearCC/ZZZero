#!/usr/bin/env python3
"""
批量处理器输出保存功能修复脚本
自动检测问题并提供修复建议，不会直接修改用户文件
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple

class BatchProcessorFixAnalyzer:
    """批量处理器修复分析器"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.issues_found = []
        self.fix_suggestions = []
        
    def analyze_batch_processor(self) -> Dict:
        """分析批量处理器的问题"""
        print("🔍 开始分析批量处理器保存功能...")
        
        results = {
            "core_processor_issues": self._check_core_processor(),
            "workflow_issues": self._check_workflow_integration(), 
            "file_structure": self._check_file_structure(),
            "import_issues": self._check_imports(),
            "method_missing": self._check_missing_methods()
        }
        
        return results
    
    def _check_core_processor(self) -> Dict:
        """检查核心批量处理器文件"""
        core_file = self.project_root / "src/core/batch_processor.py"
        issues = []
        
        if not core_file.exists():
            issues.append("核心批量处理器文件不存在")
            return {"issues": issues, "has_save_method": False}
            
        try:
            with open(core_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 检查是否有save_results_to_csv方法
            has_save_method = bool(re.search(r'def save_results_to_csv', content))
            
            if not has_save_method:
                issues.append("缺少 save_results_to_csv 方法")
                
            # 检查是否有保存相关的导入
            has_csv_import = bool(re.search(r'import csv', content))
            if not has_csv_import:
                issues.append("缺少 csv 模块导入")
                
            return {
                "issues": issues,
                "has_save_method": has_save_method,
                "has_csv_import": has_csv_import,
                "file_exists": True
            }
            
        except Exception as e:
            issues.append(f"读取文件失败: {e}")
            return {"issues": issues, "has_save_method": False}
    
    def _check_workflow_integration(self) -> Dict:
        """检查工作流集成"""
        workflow_file = self.project_root / "src/workflow/schedule_workflow.py"
        issues = []
        
        if not workflow_file.exists():
            issues.append("工作流文件不存在")
            return {"issues": issues}
            
        try:
            with open(workflow_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 检查是否有批量处理方法
            has_batch_method = bool(re.search(r'def.*batch.*process', content, re.IGNORECASE))
            
            # 检查是否调用了保存方法
            has_save_call = bool(re.search(r'save.*csv|save_results', content, re.IGNORECASE))
            
            if has_batch_method and not has_save_call:
                issues.append("批量处理方法存在但未调用保存功能")
                
            return {
                "issues": issues,
                "has_batch_method": has_batch_method,
                "has_save_call": has_save_call,
                "file_exists": True
            }
            
        except Exception as e:
            issues.append(f"读取工作流文件失败: {e}")
            return {"issues": issues}
    
    def _check_file_structure(self) -> Dict:
        """检查文件结构"""
        required_dirs = [
            "src/core",
            "src/workflow", 
            "workspace/batch_schedule_output"
        ]
        
        missing_dirs = []
        for dir_path in required_dirs:
            if not (self.project_root / dir_path).exists():
                missing_dirs.append(dir_path)
                
        return {
            "missing_directories": missing_dirs,
            "output_dir_exists": (self.project_root / "workspace/batch_schedule_output").exists()
        }
    
    def _check_imports(self) -> Dict:
        """检查导入问题"""
        files_to_check = [
            "src/core/batch_processor.py",
            "src/workflow/schedule_workflow.py"
        ]
        
        import_issues = {}
        
        for file_path in files_to_check:
            full_path = self.project_root / file_path
            if full_path.exists():
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 检查必要的导入
                    required_imports = ['csv', 'json', 'os', 'pathlib']
                    missing_imports = []
                    
                    for imp in required_imports:
                        if not re.search(f'import.*{imp}', content):
                            missing_imports.append(imp)
                    
                    if missing_imports:
                        import_issues[file_path] = missing_imports
                        
                except Exception as e:
                    import_issues[file_path] = [f"读取失败: {e}"]
                    
        return import_issues
    
    def _check_missing_methods(self) -> List[str]:
        """检查缺失的方法"""
        missing_methods = []
        
        # 检查批量处理器核心方法
        core_file = self.project_root / "src/core/batch_processor.py"
        if core_file.exists():
            try:
                with open(core_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                required_methods = [
                    'save_results_to_csv',
                    'configure_batch_mode',
                    'process_batch_request'
                ]
                
                for method in required_methods:
                    if not re.search(f'def {method}', content):
                        missing_methods.append(f"BatchProcessor.{method}")
                        
            except Exception:
                pass
                
        return missing_methods
    
    def generate_fix_suggestions(self, analysis_results: Dict) -> List[str]:
        """生成修复建议"""
        suggestions = []
        
        # 核心处理器问题修复
        core_issues = analysis_results.get("core_processor_issues", {})
        if not core_issues.get("has_save_method", False):
            suggestions.append("""
1. 在 src/core/batch_processor.py 中添加 save_results_to_csv 方法:

def save_results_to_csv(self, results: List[Dict], output_file: str = None) -> str:
    \"\"\"保存批量处理结果到CSV文件\"\"\"
    try:
        import csv
        from datetime import datetime
        
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"workspace/batch_schedule_output/batch_results_{timestamp}.csv"
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        if not results:
            return output_file
            
        # 获取所有字段名
        fieldnames = set()
        for result in results:
            fieldnames.update(result.keys())
        fieldnames = sorted(list(fieldnames))
        
        # 写入CSV文件
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
            
        print(f"✅ 批量处理结果已保存到: {output_file}")
        return output_file
        
    except Exception as e:
        print(f"❌ 保存CSV文件失败: {e}")
        raise
""")
        
        # 工作流集成问题修复
        workflow_issues = analysis_results.get("workflow_issues", {})
        if workflow_issues.get("has_batch_method") and not workflow_issues.get("has_save_call"):
            suggestions.append("""
2. 在 src/workflow/schedule_workflow.py 的批量处理方法中添加保存调用:

# 在批量处理完成后添加:
try:
    # 假设你的批量处理器实例叫 batch_processor
    if hasattr(self, 'batch_processor') and results:
        output_file = self.batch_processor.save_results_to_csv(results)
        logger.info(f"批量处理结果已保存: {output_file}")
except Exception as e:
    logger.error(f"保存批量处理结果失败: {e}")
""")
        
        # 目录结构问题修复  
        file_structure = analysis_results.get("file_structure", {})
        if file_structure.get("missing_directories"):
            suggestions.append(f"""
3. 创建缺失的目录结构:
{chr(10).join([f"   mkdir -p {d}" for d in file_structure["missing_directories"]])}
""")
        
        # 导入问题修复
        import_issues = analysis_results.get("import_issues", {})
        if import_issues:
            suggestions.append("""
4. 添加缺失的导入语句:
在相应文件顶部添加:
import csv
import json
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
""")
        
        # 缺失方法修复
        missing_methods = analysis_results.get("method_missing", [])
        if missing_methods:
            suggestions.append(f"""
5. 实现缺失的方法:
需要实现以下方法: {', '.join(missing_methods)}
""")
        
        return suggestions
    
    def create_fix_patch(self) -> str:
        """创建修复补丁"""
        patch_content = """
# 批量处理器保存功能修复补丁
# 将以下代码添加到相应文件中

# === src/core/batch_processor.py 修复 ===
def save_results_to_csv(self, results: List[Dict], output_file: str = None) -> str:
    \"\"\"保存批量处理结果到CSV文件\"\"\"
    try:
        import csv
        import os
        from datetime import datetime
        
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  
            output_file = f"workspace/batch_schedule_output/batch_results_{timestamp}.csv"
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        if not results:
            logger.warning("没有结果数据需要保存")
            return output_file
            
        # 获取所有字段名
        fieldnames = set()
        for result in results:
            if isinstance(result, dict):
                fieldnames.update(result.keys())
        fieldnames = sorted(list(fieldnames))
        
        # 写入CSV文件
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                if isinstance(result, dict):
                    writer.writerow(result)
                    
        logger.info(f"✅ 批量处理结果已保存到: {output_file}")
        return output_file
        
    except Exception as e:
        logger.error(f"❌ 保存CSV文件失败: {e}")
        raise

# === src/workflow/schedule_workflow.py 修复 ===  
# 在批量处理方法的末尾添加保存调用:

def run_batch_processor(self, config):
    \"\"\"运行批量处理器\"\"\"
    try:
        # ... 现有的批量处理逻辑 ...
        
        # 获取处理结果
        results = self.get_batch_results()  # 根据你的实际方法名调整
        
        # 保存结果到CSV
        if results:
            from core.batch_processor import BatchProcessor
            processor = BatchProcessor()
            output_file = processor.save_results_to_csv(results)
            logger.info(f"批量处理完成，结果已保存: {output_file}")
        else:
            logger.warning("批量处理未产生结果数据")
            
    except Exception as e:
        logger.error(f"批量处理失败: {e}")
        raise
"""
        return patch_content
    
    def run_analysis(self) -> None:
        """运行完整分析"""
        print("=" * 60)
        print("🔧 批量处理器输出保存功能修复分析")
        print("=" * 60)
        
        # 执行分析
        analysis_results = self.analyze_batch_processor()
        
        # 显示分析结果
        print("\n📊 分析结果:")
        print("-" * 40)
        
        for category, results in analysis_results.items():
            print(f"\n🔍 {category}:")
            if isinstance(results, dict):
                for key, value in results.items():
                    if isinstance(value, list) and value:
                        print(f"  ❌ {key}: {', '.join(value)}")
                    elif isinstance(value, bool):
                        status = "✅" if value else "❌"
                        print(f"  {status} {key}: {value}")
            elif isinstance(results, list) and results:
                for item in results:
                    print(f"  ❌ {item}")
        
        # 生成修复建议
        suggestions = self.generate_fix_suggestions(analysis_results)
        
        if suggestions:
            print("\n🛠️ 修复建议:")
            print("-" * 40)
            for i, suggestion in enumerate(suggestions, 1):
                print(suggestion)
        else:
            print("\n✅ 未发现需要修复的问题！")
        
        # 创建修复补丁文件
        patch_content = self.create_fix_patch()
        patch_file = self.project_root / "batch_processor_fix_patch.txt"
        
        try:
            with open(patch_file, 'w', encoding='utf-8') as f:
                f.write(patch_content)
            print(f"\n📄 修复补丁已生成: {patch_file}")
        except Exception as e:
            print(f"\n❌ 生成补丁文件失败: {e}")
        
        print("\n" + "=" * 60)
        print("🎉 分析完成！请根据建议进行修复。")
        print("=" * 60)

def main():
    """主函数"""
    if len(sys.argv) > 1:
        project_root = sys.argv[1]
    else:
        project_root = "."
    
    analyzer = BatchProcessorFixAnalyzer(project_root)
    analyzer.run_analysis()

if __name__ == "__main__":
    main() 