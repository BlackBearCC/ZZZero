"""
Web界面样式配置
"""

def get_custom_css() -> str:
    """获取自定义CSS样式"""
    return """
    /* 基础样式 */
    .gradio-container {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
    }
    
    /* 工作流进度样式 */
    .workflow-progress {
        background: #ffffff;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        border: 1px solid #e5e7eb;
    }
    
    .workflow-node {
        display: flex;
        align-items: flex-start;
        margin: 15px 0;
        padding: 15px;
        border-radius: 10px;
    }
    
    .workflow-node.active {
        background: rgba(245, 158, 11, 0.1);
        border-left: 4px solid #f59e0b;
    }
    
    .workflow-node.completed {
        background: rgba(16, 185, 129, 0.1);
        border-left: 4px solid #10b981;
    }
    
    .workflow-node.error {
        background: rgba(239, 68, 68, 0.1);
        border-left: 4px solid #ef4444;
    }
    
    .workflow-node.pending {
        background: rgba(156, 163, 175, 0.1);
        border-left: 4px solid #9ca3af;
    }
    
    .node-info {
        flex: 0 0 200px;
        margin-right: 20px;
    }
    
    .node-result {
        flex: 1;
        min-height: 60px;
        background: #ffffff;
        border-radius: 8px;
        padding: 12px;
        border: 1px solid currentColor;
    }
    
    /* 响应式设计 */
    @media (max-width: 768px) {
        .workflow-node {
            flex-direction: column;
        }
        
        .node-info {
            flex: none;
            margin-right: 0;
            margin-bottom: 10px;
        }
    }
    """

# HTML头部代码（包含JavaScript库）
HTML_HEAD = """
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/python.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/json.min.js"></script>
<script>
    document.addEventListener('DOMContentLoaded', function() {
        // 初始化highlight.js
        hljs.highlightAll();
        
        // 监听DOM变化以高亮新添加的代码块
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                mutation.addedNodes.forEach(function(node) {
                    if (node.nodeType === 1) {
                        // 查找新添加的代码块
                        const codeBlocks = node.querySelectorAll('pre code, code');
                        codeBlocks.forEach(function(block) {
                            if (!block.classList.contains('hljs')) {
                                hljs.highlightElement(block);
                            }
                        });
                    }
                });
            });
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    });
</script>
""" 