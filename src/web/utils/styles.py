"""
CSS样式配置
"""

# 自定义CSS样式
CUSTOM_CSS = """
* {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
}
.chat-window {
    border-radius: 10px;
    border: 1px solid #e0e0e0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
}

/* 字符渐显动画 */
.char-fade-in {
    animation: charFadeIn 0.3s ease-in-out;
    display: inline;
}

@keyframes charFadeIn {
    0% { 
        opacity: 0; 
        transform: translateY(-5px);
    }
    50% {
        opacity: 0.7;
        transform: translateY(-2px);
    }
    100% { 
        opacity: 1; 
        transform: translateY(0);
    }
}

/* 优化打字机光标动画 */
.typing-cursor {
    display: inline-block;
    width: 2px;
    height: 1.2em;
    background-color: #333;
    margin-left: 2px;
    animation: blink 1s infinite;
    vertical-align: text-bottom;
}

@keyframes blink {
    0%, 50% { opacity: 1; }
    51%, 100% { opacity: 0; }
}

/* 流式文本动画 */
.streaming-text {
    animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

/* 新文字高亮效果 */
.new-text-highlight {
    background-color: rgba(34, 197, 94, 0.1);
    animation: highlightFade 2s ease-out forwards;
}

@keyframes highlightFade {
    0% { background-color: rgba(34, 197, 94, 0.3); }
    100% { background-color: transparent; }
}

.chat-window .message {
    padding: 10px;
    margin: 5px;
    border-radius: 10px;
    transition: all 0.2s ease-in-out;
}
.chat-window .user {
    background-color: #e3f2fd;
    margin-left: 20%;
}
.chat-window .bot {
    background-color: #f5f5f5;
    margin-right: 20%;
}
.gradio-container {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
    height: 100vh;
    overflow-y: auto;
}

/* 代码块样式 - 黑色背景 */
.chat-window pre {
    background-color: #0d1117 !important;
    color: #e6edf3 !important;
    border-radius: 8px !important;
    padding: 16px !important;
    margin: 12px 0 !important;
    border: 1px solid #30363d !important;
    overflow-x: auto !important;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', 'source-code-pro', monospace !important;
    font-size: 14px !important;
    line-height: 1.5 !important;
    position: relative !important;
}

.chat-window pre code {
    background-color: transparent !important;
    color: inherit !important;
    padding: 0 !important;
    border-radius: 0 !important;
    font-family: inherit !important;
    font-size: inherit !important;
}

/* 内联代码样式 */
.chat-window code:not(pre code) {
    background-color: #f6f8fa !important;
    color: #d73a49 !important;
    padding: 2px 4px !important;
    border-radius: 3px !important;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', 'source-code-pro', monospace !important;
    font-size: 85% !important;
    border: 1px solid #e1e4e8 !important;
}

/* 确保代码块在聊天消息中正确显示 */
.chat-window .message {
    overflow: visible !important;
}

.chat-window .message pre {
    white-space: pre !important;
    word-wrap: normal !important;
}

/* Agent关键词高亮样式 */
.chat-window .bot .message-content {
    position: relative;
}

/* Question 样式 - 蓝色 */
.chat-window .agent-keyword-question {
    color: #0066cc !important;
    font-weight: bold !important;
    font-size: 16px !important;
    background-color: rgba(0, 102, 204, 0.1) !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
    border-left: 4px solid #0066cc !important;
    padding-left: 8px !important;
    display: inline-block !important;
    margin: 2px 0 !important;
    transition: none !important; /* 禁用过渡动画，防止跳动 */
    will-change: auto !important; /* 优化渲染性能 */
}

/* Thought 样式 - 绿色 */
.chat-window .agent-keyword-thought {
    color: #22c55e !important;
    font-weight: bold !important;
    font-size: 16px !important;
    background-color: rgba(34, 197, 94, 0.1) !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
    border-left: 4px solid #22c55e !important;
    padding-left: 8px !important;
    display: inline-block !important;
    margin: 2px 0 !important;
    transition: none !important;
    will-change: auto !important;
}

/* Action 样式 - 橙色 */
.chat-window .agent-keyword-action {
    color: #f59e0b !important;
    font-weight: bold !important;
    font-size: 16px !important;
    background-color: rgba(245, 158, 11, 0.1) !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
    border-left: 4px solid #f59e0b !important;
    padding-left: 8px !important;
    display: inline-block !important;
    margin: 2px 0 !important;
    transition: none !important;
    will-change: auto !important;
}

/* Action Input 样式 - 紫色 */
.chat-window .agent-keyword-action-input {
    color: #8b5cf6 !important;
    font-weight: bold !important;
    font-size: 16px !important;
    background-color: rgba(139, 92, 246, 0.1) !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
    border-left: 4px solid #8b5cf6 !important;
    padding-left: 8px !important;
    display: inline-block !important;
    margin: 2px 0 !important;
    transition: none !important;
    will-change: auto !important;
}

/* Observation 样式 - 青色 */
.chat-window .agent-keyword-observation {
    color: #06b6d4 !important;
    font-weight: bold !important;
    font-size: 16px !important;
    background-color: rgba(6, 182, 212, 0.1) !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
    border-left: 4px solid #06b6d4 !important;
    padding-left: 8px !important;
    display: inline-block !important;
    margin: 2px 0 !important;
    transition: none !important;
    will-change: auto !important;
}

/* Final Answer 样式 - 红色 */
.chat-window .agent-keyword-final-answer {
    color: #dc2626 !important;
    font-weight: bold !important;
    font-size: 16px !important;
    background-color: rgba(220, 38, 38, 0.1) !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
    border-left: 4px solid #dc2626 !important;
    padding-left: 8px !important;
    display: inline-block !important;
    margin: 2px 0 !important;
    transition: none !important;
    will-change: auto !important;
}

/* 让消息内容可以正确显示HTML */
.chat-window .message-content {
    white-space: pre-line;
    word-wrap: break-word;
    line-height: 1.4 !important;
    margin: 0 !important;
    padding: 0 !important;
    font-variant-numeric: tabular-nums !important; /* 数字等宽 */
    font-feature-settings: "kern" 1, "liga" 1 !important; /* 字符间距优化 */
    text-rendering: optimizeSpeed !important; /* 优化渲染性能 */
    font-size: 14px !important; /* 固定字体大小 */
}

/* 配置面板滚动样式 */
.config-panel-scroll {
    height: 600px !important;
    max-height: 600px !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    padding-right: 8px !important;
    box-sizing: border-box !important;
}

/* 美化滚动条 */
.config-panel-scroll::-webkit-scrollbar {
    width: 6px !important;
}

.config-panel-scroll::-webkit-scrollbar-track {
    background: #f1f1f1 !important;
    border-radius: 3px !important;
}

.config-panel-scroll::-webkit-scrollbar-thumb {
    background: #c1c1c1 !important;
    border-radius: 3px !important;
}

.config-panel-scroll::-webkit-scrollbar-thumb:hover {
    background: #a8a8a8 !important;
}

/* 工作流聊天界面高度与Agent窗口保持一致 */
#workflow_chatbot {
    height: 500px !important;
    min-height: 500px !important;
    max-height: 500px !important;
}

/* 快捷回复区域样式 */
#quick_replies_area {
    margin: 10px 0 !important;
}

.quick-reply-tag:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 2px 8px rgba(0, 123, 255, 0.3) !important;
}

.quick-reply-tag:active {
    transform: translateY(0) !important;
    box-shadow: 0 1px 4px rgba(0, 123, 255, 0.3) !important;
}

/* 针对机器人回复进行特殊优化 */
.chat-window .bot .message-content {
    white-space: pre-line !important;
    overflow-wrap: break-word !important;
    max-width: 100% !important;
}

/* 优化消息内容的段落间距 */
.chat-window .message p {
    margin: 0.2em 0 !important;
    line-height: 1.4 !important;
}

/* 修复Gradio聊天消息的默认样式 */
.chat-window .message {
    line-height: 1.4 !important;
    margin: 6px 0 !important;
}

/* 确保内容紧凑显示 */
.chat-window .message > div {
    line-height: 1.4 !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* 优化列表项间距 */
.chat-window .message ul, 
.chat-window .message ol {
    margin: 0.5em 0 !important;
    padding-left: 1.5em !important;
}

.chat-window .message li {
    margin: 0.2em 0 !important;
    line-height: 1.5 !important;
}

/* Markdown表格样式 */
.chat-window .markdown-table-container {
    margin: 15px 0 !important;
    padding: 10px !important;
    border-radius: 8px !important;
    background-color: #f9f9f9 !important;
    border: 1px solid #e0e0e0 !important;
    overflow-x: auto !important;
}

.chat-window .markdown-table {
    width: 100% !important;
    border-collapse: collapse !important;
    border: 1px solid #ddd !important;
    font-size: 14px !important;
    background-color: white !important;
    border-radius: 4px !important;
    overflow: hidden !important;
}

.chat-window .markdown-table th {
    background-color: #f5f5f5 !important;
    border: 1px solid #ddd !important;
    padding: 12px 8px !important;
    text-align: left !important;
    font-weight: bold !important;
    color: #333 !important;
    font-size: 13px !important;
}

.chat-window .markdown-table td {
    border: 1px solid #ddd !important;
    padding: 10px 8px !important;
    vertical-align: top !important;
    line-height: 1.4 !important;
    font-size: 13px !important;
    color: #555 !important;
}

.chat-window .markdown-table tr:nth-child(even) {
    background-color: #fafafa !important;
}

.chat-window .markdown-table tr:hover {
    background-color: #f0f8ff !important;
}

/* 表格响应式设计 */
@media (max-width: 768px) {
    .chat-window .markdown-table-container {
        font-size: 12px !important;
    }
    
    .chat-window .markdown-table th,
    .chat-window .markdown-table td {
        padding: 6px 4px !important;
        font-size: 11px !important;
    }
}

/* 流式输入指示器 */
.streaming-indicator {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #22c55e;
    margin-left: 8px;
    animation: pulse 1.5s infinite;
}

@keyframes pulse {
    0% {
        transform: scale(1);
        opacity: 1;
    }
    50% {
        transform: scale(1.2);
        opacity: 0.7;
    }
    100% {
        transform: scale(1);
        opacity: 1;
    }
}

/* 工具执行状态指示器 */
.tool-executing {
    display: inline-block;
    padding: 2px 8px;
    background-color: rgba(245, 158, 11, 0.1);
    color: #f59e0b;
    border-radius: 12px;
    font-size: 12px;
    font-weight: bold;
    margin: 2px 4px;
    animation: bounce 1s infinite alternate;
}

/* 工具执行错误指示器 */
.tool-error {
    display: inline-block;
    padding: 2px 8px;
    background-color: rgba(220, 38, 38, 0.1);
    color: #dc2626;
    border-radius: 12px;
    font-size: 12px;
    font-weight: bold;
    margin: 2px 4px;
}

@keyframes bounce {
    from { transform: translateY(0px); }
    to { transform: translateY(-3px); }
}

/* 响应完成指示器 */
.response-complete {
    color: #22c55e;
    font-weight: bold;
    opacity: 0;
    animation: fadeInComplete 0.5s ease-in forwards;
}

@keyframes fadeInComplete {
    to { opacity: 1; }
}

/* highlight.js 深色主题适配 */
.chat-window .hljs {
    background: #0d1117 !important;
    color: #e6edf3 !important;
}

/* 语言标签样式 */
.chat-window pre::before {
    content: attr(data-language);
    position: absolute;
    top: 8px;
    right: 12px;
    background: rgba(255, 255, 255, 0.1);
    color: #e6edf3;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 11px;
    text-transform: uppercase;
    font-weight: bold;
}

/* 工具输出样式 - 独特的框框显示 */
.tool-output {
    background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%) !important;
    border: 2px solid #cbd5e1 !important;
    border-radius: 8px !important;
    padding: 12px 16px !important;
    margin: 8px 0 !important;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1) !important;
    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace !important;
    font-size: 13px !important;
    line-height: 1.5 !important;
    position: relative !important;
    border-left: 4px solid #3b82f6 !important;
}

.tool-output::before {
    content: "🔧 工具输出";
    position: absolute !important;
    top: -8px !important;
    left: 8px !important;
    background: #3b82f6 !important;
    color: white !important;
    padding: 2px 8px !important;
    border-radius: 4px !important;
    font-size: 10px !important;
    font-weight: bold !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif !important;
}

/* 工具名称标签 */
.tool-name-tag {
    display: inline-block !important;
    background: #1e40af !important;
    color: white !important;
    padding: 2px 6px !important;
    border-radius: 3px !important;
    font-size: 10px !important;
    font-weight: bold !important;
    margin-bottom: 4px !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif !important;
}

/* 工具输出内容 */
.tool-output-content {
    white-space: pre-line !important; /* 改为pre-line避免过多空行 */
    word-wrap: break-word !important;
    color: #334155 !important;
    margin: 0 !important;
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