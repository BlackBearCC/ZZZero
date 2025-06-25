"""
文件工具 - 文件管理、工作空间操作等
"""
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class FileUtils:
    """文件工具类"""
    
    @staticmethod
    def ensure_workspace_dirs(workspace_config: Dict[str, str]) -> None:
        """确保工作空间目录存在"""
        for dir_path in workspace_config.values():
            os.makedirs(dir_path, exist_ok=True)
            logger.info(f"创建工作空间目录: {dir_path}")
    
    @staticmethod
    def list_files_in_dir(dir_path: str) -> List[Dict[str, Any]]:
        """列出目录中的文件"""
        files = []
        if os.path.exists(dir_path):
            for item in Path(dir_path).iterdir():
                if item.is_file():
                    stat = item.stat()
                    files.append({
                        'name': item.name,
                        'path': str(item),
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                        'type': item.suffix.lower()
                    })
        return sorted(files, key=lambda x: x['modified'], reverse=True)
    
    @staticmethod
    def format_file_list_html(files: List[Dict], title: str) -> str:
        """格式化文件列表为HTML"""
        if not files:
            return f"<div style='padding: 10px; color: #666;'>{title}: 暂无文件</div>"
        
        html = f"<div style='margin-bottom: 10px;'><strong>{title} ({len(files)} 个文件)</strong></div>"
        html += "<div style='max-height: 200px; overflow-y: auto; border: 1px solid #ddd; border-radius: 4px;'>"
        
        for file in files:
            size_str = FileUtils.format_file_size(file['size'])
            html += f"""
            <div style='padding: 8px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between;'>
                <div>
                    <strong>{file['name']}</strong>
                    <div style='font-size: 0.8em; color: #666;'>{file['modified']}</div>
                </div>
                <div style='text-align: right; color: #888;'>{size_str}</div>
            </div>
            """
        html += "</div>"
        return html
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB" 