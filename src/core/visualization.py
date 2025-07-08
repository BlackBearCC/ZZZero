"""
图可视化模块 - 支持多种格式和交互式图表
"""
import json
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
import logging

from .graph import StateGraph, Edge, ConditionalEdge
from .monitoring import ExecutionTrace, ExecutionEvent, EventType

logger = logging.getLogger(__name__)

class VisualizationFormat(Enum):
    """可视化格式"""
    MERMAID = "mermaid"
    GRAPHVIZ = "graphviz"
    D3_FORCE = "d3_force"
    CYTOSCAPE = "cytoscape"
    HTML = "html"

class NodeStyle(Enum):
    """节点样式"""
    DEFAULT = "default"
    START = "start"
    END = "end"
    ERROR = "error"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class VisualizationConfig:
    """可视化配置"""
    format: VisualizationFormat = VisualizationFormat.MERMAID
    include_metadata: bool = True
    include_timestamps: bool = False
    include_performance: bool = False
    include_state_info: bool = False
    theme: str = "default"
    layout: str = "TB"  # TB, LR, BT, RL for mermaid
    width: int = 800
    height: int = 600
    
@dataclass
class NodeVisualization:
    """节点可视化信息"""
    id: str
    label: str
    style: NodeStyle = NodeStyle.DEFAULT
    metadata: Dict[str, Any] = field(default_factory=dict)
    position: Optional[Tuple[float, float]] = None
    size: Optional[Tuple[float, float]] = None
    color: Optional[str] = None
    
@dataclass
class EdgeVisualization:
    """边可视化信息"""
    from_node: str
    to_node: str
    label: Optional[str] = None
    style: str = "solid"
    color: Optional[str] = None
    weight: float = 1.0
    
class GraphVisualizer:
    """图可视化器"""
    
    def __init__(self):
        self.color_schemes = {
            "default": {
                "start": "#4CAF50",
                "end": "#F44336", 
                "running": "#2196F3",
                "completed": "#4CAF50",
                "failed": "#F44336",
                "default": "#9E9E9E"
            },
            "dark": {
                "start": "#66BB6A",
                "end": "#EF5350",
                "running": "#42A5F5", 
                "completed": "#66BB6A",
                "failed": "#EF5350",
                "default": "#BDBDBD"
            }
        }
    
    def visualize_graph(self, 
                       graph: StateGraph,
                       config: VisualizationConfig = None,
                       execution_trace: Optional[ExecutionTrace] = None) -> str:
        """可视化图"""
        config = config or VisualizationConfig()
        
        if config.format == VisualizationFormat.MERMAID:
            return self._generate_mermaid(graph, config, execution_trace)
        elif config.format == VisualizationFormat.GRAPHVIZ:
            return self._generate_graphviz(graph, config, execution_trace)
        elif config.format == VisualizationFormat.D3_FORCE:
            return self._generate_d3_force(graph, config, execution_trace)
        elif config.format == VisualizationFormat.CYTOSCAPE:
            return self._generate_cytoscape(graph, config, execution_trace)
        elif config.format == VisualizationFormat.HTML:
            return self._generate_html(graph, config, execution_trace)
        else:
            raise ValueError(f"不支持的可视化格式: {config.format}")
    
    def _generate_mermaid(self, 
                         graph: StateGraph,
                         config: VisualizationConfig,
                         execution_trace: Optional[ExecutionTrace] = None) -> str:
        """生成Mermaid图"""
        lines = [f"graph {config.layout}"]
        
        # 生成节点可视化信息
        node_viz = self._build_node_visualizations(graph, config, execution_trace)
        edge_viz = self._build_edge_visualizations(graph, config, execution_trace)
        
        # 添加节点定义
        for node_id, node_info in node_viz.items():
            node_shape = self._get_mermaid_node_shape(node_info.style)
            node_label = node_info.label
            
            if config.include_metadata and node_info.metadata:
                metadata_str = self._format_metadata_for_mermaid(node_info.metadata)
                if metadata_str:
                    node_label += f"\\n{metadata_str}"
            
            lines.append(f'    {node_id}{node_shape[0]}"{node_label}"{node_shape[1]}')
        
        # 添加边
        for edge_info in edge_viz:
            edge_label = f"|{edge_info.label}|" if edge_info.label else ""
            arrow_style = "-->" if edge_info.style == "solid" else "-.->"
            lines.append(f"    {edge_info.from_node} {arrow_style}{edge_label} {edge_info.to_node}")
        
        # 添加样式
        if config.theme in self.color_schemes:
            colors = self.color_schemes[config.theme]
            for node_id, node_info in node_viz.items():
                if node_info.style.value in colors:
                    color = colors[node_info.style.value]
                    lines.append(f"    classDef {node_info.style.value}Style fill:{color}")
                    lines.append(f"    class {node_id} {node_info.style.value}Style")
        
        # 添加入口点标记
        if graph.entry_point:
            lines.append(f"    START((开始)) --> {graph.entry_point}")
        
        return "\n".join(lines)
    
    def _generate_graphviz(self, 
                          graph: StateGraph,
                          config: VisualizationConfig,
                          execution_trace: Optional[ExecutionTrace] = None) -> str:
        """生成Graphviz图"""
        lines = [
            "digraph StateGraph {",
            f"  rankdir={config.layout};",
            "  node [shape=box, style=rounded];",
            "  edge [fontsize=10];"
        ]
        
        # 生成节点可视化信息
        node_viz = self._build_node_visualizations(graph, config, execution_trace)
        edge_viz = self._build_edge_visualizations(graph, config, execution_trace)
        
        # 添加节点
        for node_id, node_info in node_viz.items():
            label = node_info.label.replace('\n', '\\n')
            color = node_info.color or self._get_node_color(node_info.style, config.theme)
            
            attrs = [
                f'label="{label}"',
                f'fillcolor="{color}"',
                'style="filled,rounded"'
            ]
            
            if config.include_metadata and node_info.metadata:
                tooltip = self._format_metadata_for_tooltip(node_info.metadata)
                attrs.append(f'tooltip="{tooltip}"')
            
            lines.append(f'  {node_id} [{", ".join(attrs)}];')
        
        # 添加边
        for edge_info in edge_viz:
            attrs = []
            if edge_info.label:
                attrs.append(f'label="{edge_info.label}"')
            if edge_info.color:
                attrs.append(f'color="{edge_info.color}"')
            if edge_info.style == "dashed":
                attrs.append('style="dashed"')
            
            attr_str = f' [{", ".join(attrs)}]' if attrs else ""
            lines.append(f"  {edge_info.from_node} -> {edge_info.to_node}{attr_str};")
        
        # 添加入口点
        if graph.entry_point:
            lines.append('  START [shape=circle, label="开始", fillcolor="lightgreen", style=filled];')
            lines.append(f"  START -> {graph.entry_point};")
        
        lines.append("}")
        return "\n".join(lines)
    
    def _generate_d3_force(self, 
                          graph: StateGraph,
                          config: VisualizationConfig,
                          execution_trace: Optional[ExecutionTrace] = None) -> str:
        """生成D3力导向图数据"""
        node_viz = self._build_node_visualizations(graph, config, execution_trace)
        edge_viz = self._build_edge_visualizations(graph, config, execution_trace)
        
        # 构建节点数据
        nodes = []
        for node_id, node_info in node_viz.items():
            node_data = {
                "id": node_id,
                "label": node_info.label,
                "group": node_info.style.value,
                "color": node_info.color or self._get_node_color(node_info.style, config.theme)
            }
            
            if config.include_metadata:
                node_data["metadata"] = node_info.metadata
            
            nodes.append(node_data)
        
        # 构建边数据
        links = []
        for edge_info in edge_viz:
            link_data = {
                "source": edge_info.from_node,
                "target": edge_info.to_node,
                "weight": edge_info.weight
            }
            
            if edge_info.label:
                link_data["label"] = edge_info.label
            if edge_info.color:
                link_data["color"] = edge_info.color
                
            links.append(link_data)
        
        return json.dumps({
            "nodes": nodes,
            "links": links,
            "config": {
                "width": config.width,
                "height": config.height,
                "theme": config.theme
            }
        }, indent=2)
    
    def _generate_cytoscape(self, 
                           graph: StateGraph,
                           config: VisualizationConfig,
                           execution_trace: Optional[ExecutionTrace] = None) -> str:
        """生成Cytoscape.js数据"""
        node_viz = self._build_node_visualizations(graph, config, execution_trace)
        edge_viz = self._build_edge_visualizations(graph, config, execution_trace)
        
        elements = []
        
        # 添加节点
        for node_id, node_info in node_viz.items():
            element = {
                "data": {
                    "id": node_id,
                    "label": node_info.label,
                    "type": node_info.style.value
                },
                "style": {
                    "background-color": node_info.color or self._get_node_color(node_info.style, config.theme)
                }
            }
            
            if config.include_metadata:
                element["data"]["metadata"] = node_info.metadata
            
            elements.append(element)
        
        # 添加边
        edge_id = 0
        for edge_info in edge_viz:
            element = {
                "data": {
                    "id": f"edge_{edge_id}",
                    "source": edge_info.from_node,
                    "target": edge_info.to_node
                }
            }
            
            if edge_info.label:
                element["data"]["label"] = edge_info.label
            if edge_info.color:
                element["style"] = {"line-color": edge_info.color}
            
            elements.append(element)
            edge_id += 1
        
        return json.dumps({
            "elements": elements,
            "style": self._get_cytoscape_style(config.theme),
            "layout": {"name": "dagre", "rankDir": config.layout}
        }, indent=2)
    
    def _generate_html(self, 
                      graph: StateGraph,
                      config: VisualizationConfig,
                      execution_trace: Optional[ExecutionTrace] = None) -> str:
        """生成HTML可视化页面"""
        
        # 根据配置选择可视化引擎
        if config.format == VisualizationFormat.HTML:
            # 使用D3.js作为默认引擎
            graph_data = self._generate_d3_force(graph, config, execution_trace)
            
            html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>StateGraph可视化 - {graph_name}</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
        #graph {{ border: 1px solid #ddd; }}
        .tooltip {{ position: absolute; padding: 10px; background: rgba(0,0,0,0.8); 
                   color: white; border-radius: 5px; font-size: 12px; }}
        .controls {{ margin-bottom: 20px; }}
        .node {{ cursor: pointer; }}
        .link {{ stroke: #999; stroke-opacity: 0.6; }}
        .node text {{ font: 12px sans-serif; pointer-events: none; text-anchor: middle; }}
    </style>
</head>
<body>
    <h1>StateGraph可视化: {graph_name}</h1>
    <div class="controls">
        <button onclick="restartSimulation()">重新布局</button>
        <button onclick="toggleLabels()">切换标签</button>
        <button onclick="exportSVG()">导出SVG</button>
    </div>
    <svg id="graph" width="{width}" height="{height}"></svg>
    
    <script>
        const data = {graph_data};
        
        const svg = d3.select("#graph");
        const width = {width};
        const height = {height};
        
        // 创建力仿真
        const simulation = d3.forceSimulation(data.nodes)
            .force("link", d3.forceLink(data.links).id(d => d.id).distance(100))
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(width / 2, height / 2));
        
        // 创建箭头标记
        svg.append("defs").append("marker")
            .attr("id", "arrow")
            .attr("viewBox", "0 -5 10 10")
            .attr("refX", 15)
            .attr("refY", 0)
            .attr("markerWidth", 6)
            .attr("markerHeight", 6)
            .attr("orient", "auto")
            .append("path")
            .attr("d", "M0,-5L10,0L0,5")
            .attr("fill", "#999");
        
        // 创建连线
        const link = svg.append("g")
            .selectAll("line")
            .data(data.links)
            .enter().append("line")
            .attr("class", "link")
            .attr("marker-end", "url(#arrow)");
        
        // 创建节点
        const node = svg.append("g")
            .selectAll("circle")
            .data(data.nodes)
            .enter().append("circle")
            .attr("class", "node")
            .attr("r", 20)
            .attr("fill", d => d.color)
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));
        
        // 添加标签
        const label = svg.append("g")
            .selectAll("text")
            .data(data.nodes)
            .enter().append("text")
            .text(d => d.label)
            .attr("font-size", "12px")
            .attr("dx", 25)
            .attr("dy", 5);
        
        // 添加工具提示
        const tooltip = d3.select("body").append("div")
            .attr("class", "tooltip")
            .style("opacity", 0);
        
        node.on("mouseover", function(event, d) {{
            tooltip.transition().duration(200).style("opacity", .9);
            tooltip.html(`<strong>${{d.label}}</strong><br/>类型: ${{d.group}}<br/>ID: ${{d.id}}`)
                .style("left", (event.pageX + 10) + "px")
                .style("top", (event.pageY - 28) + "px");
        }})
        .on("mouseout", function(d) {{
            tooltip.transition().duration(500).style("opacity", 0);
        }});
        
        // 更新位置
        simulation.on("tick", function() {{
            link.attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
            
            node.attr("cx", d => d.x)
                .attr("cy", d => d.y);
            
            label.attr("x", d => d.x)
                 .attr("y", d => d.y);
        }});
        
        // 拖拽函数
        function dragstarted(event, d) {{
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }}
        
        function dragged(event, d) {{
            d.fx = event.x;
            d.fy = event.y;
        }}
        
        function dragended(event, d) {{
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }}
        
        // 控制函数
        function restartSimulation() {{
            simulation.alpha(0.3).restart();
        }}
        
        function toggleLabels() {{
            label.style("display", label.style("display") === "none" ? "block" : "none");
        }}
        
        function exportSVG() {{
            const svgData = new XMLSerializer().serializeToString(svg.node());
            const blob = new Blob([svgData], {{type: "image/svg+xml"}});
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "stategraph.svg";
            a.click();
        }}
    </script>
</body>
</html>
"""
            
            return html_template.format(
                graph_name=graph.name,
                width=config.width,
                height=config.height,
                graph_data=graph_data
            )
    
    def _build_node_visualizations(self, 
                                  graph: StateGraph,
                                  config: VisualizationConfig,
                                  execution_trace: Optional[ExecutionTrace] = None) -> Dict[str, NodeVisualization]:
        """构建节点可视化信息"""
        node_viz = {}
        
        # 从执行轨迹获取节点状态
        node_states = {}
        if execution_trace:
            for event in execution_trace.events:
                if event.node_name:
                    if event.event_type == EventType.NODE_START:
                        node_states[event.node_name] = NodeStyle.RUNNING
                    elif event.event_type == EventType.NODE_COMPLETE:
                        node_states[event.node_name] = NodeStyle.COMPLETED
                    elif event.event_type == EventType.NODE_ERROR:
                        node_states[event.node_name] = NodeStyle.FAILED
        
        for node_name, node in graph.nodes.items():
            # 确定节点样式
            if node_name == graph.entry_point:
                style = NodeStyle.START
            elif node_name in node_states:
                style = node_states[node_name]
            else:
                style = NodeStyle.DEFAULT
            
            # 构建标签
            label = node_name
            if config.include_metadata:
                node_type = getattr(node, 'node_type', None)
                if node_type:
                    label += f"\\n({node_type})"
            
            # 构建元数据
            metadata = {}
            if config.include_metadata:
                metadata['type'] = str(getattr(node, 'node_type', 'unknown'))
                metadata['description'] = getattr(node, 'description', '')
            
            if config.include_performance and execution_trace:
                # 添加性能信息
                node_events = [e for e in execution_trace.events if e.node_name == node_name]
                if node_events:
                    durations = [e.duration for e in node_events if e.duration is not None]
                    if durations:
                        metadata['avg_duration'] = sum(durations) / len(durations)
                        metadata['total_executions'] = len(durations)
            
            node_viz[node_name] = NodeVisualization(
                id=node_name,
                label=label,
                style=style,
                metadata=metadata,
                color=self._get_node_color(style, config.theme)
            )
        
        return node_viz
    
    def _build_edge_visualizations(self, 
                                  graph: StateGraph,
                                  config: VisualizationConfig,
                                  execution_trace: Optional[ExecutionTrace] = None) -> List[EdgeVisualization]:
        """构建边可视化信息"""
        edge_viz = []
        
        # 普通边
        for edge in graph.edges:
            edge_viz.append(EdgeVisualization(
                from_node=edge.from_node,
                to_node=edge.to_node,
                style="solid"
            ))
        
        # 条件边
        for cond_edge in graph.conditional_edges:
            # 简化处理，可以根据路由映射添加多条边
            if hasattr(cond_edge, 'route_map') and cond_edge.route_map:
                for route_key, target_node in cond_edge.route_map.items():
                    if target_node and target_node in graph.nodes:
                        edge_viz.append(EdgeVisualization(
                            from_node=cond_edge.from_node,
                            to_node=target_node,
                            label=route_key,
                            style="dashed",
                            color="#666"
                        ))
            else:
                # 添加一般性条件边表示
                edge_viz.append(EdgeVisualization(
                    from_node=cond_edge.from_node,
                    to_node="condition",  # 临时目标
                    label="condition",
                    style="dashed",
                    color="#666"
                ))
        
        return edge_viz
    
    def _get_mermaid_node_shape(self, style: NodeStyle) -> Tuple[str, str]:
        """获取Mermaid节点形状"""
        shapes = {
            NodeStyle.START: ("(", ")"),
            NodeStyle.END: ("((", "))"),
            NodeStyle.ERROR: ("[", "]"),
            NodeStyle.DEFAULT: ("[", "]"),
            NodeStyle.RUNNING: ("[", "]"),
            NodeStyle.COMPLETED: ("[", "]"),
            NodeStyle.FAILED: ("[", "]")
        }
        return shapes.get(style, ("[", "]"))
    
    def _get_node_color(self, style: NodeStyle, theme: str) -> str:
        """获取节点颜色"""
        if theme in self.color_schemes:
            colors = self.color_schemes[theme]
            return colors.get(style.value, colors["default"])
        return "#9E9E9E"
    
    def _get_cytoscape_style(self, theme: str) -> List[Dict[str, Any]]:
        """获取Cytoscape样式"""
        colors = self.color_schemes.get(theme, self.color_schemes["default"])
        
        return [
            {
                "selector": "node",
                "style": {
                    "background-color": colors["default"],
                    "label": "data(label)",
                    "text-valign": "center",
                    "text-halign": "center",
                    "font-size": "12px"
                }
            },
            {
                "selector": "edge",
                "style": {
                    "width": 2,
                    "line-color": "#ccc",
                    "target-arrow-color": "#ccc",
                    "target-arrow-shape": "triangle",
                    "curve-style": "bezier"
                }
            }
        ]
    
    def _format_metadata_for_mermaid(self, metadata: Dict[str, Any]) -> str:
        """为Mermaid格式化元数据"""
        items = []
        for key, value in metadata.items():
            if isinstance(value, (int, float)):
                items.append(f"{key}: {value:.2f}" if isinstance(value, float) else f"{key}: {value}")
            elif isinstance(value, str) and len(value) < 20:
                items.append(f"{key}: {value}")
        return "\\n".join(items[:3])  # 限制显示数量
    
    def _format_metadata_for_tooltip(self, metadata: Dict[str, Any]) -> str:
        """为工具提示格式化元数据"""
        items = []
        for key, value in metadata.items():
            items.append(f"{key}: {value}")
        return "\\n".join(items)

# 全局可视化器实例
global_visualizer = GraphVisualizer()

def visualize_graph(graph: StateGraph, 
                   format: Union[str, VisualizationFormat] = VisualizationFormat.MERMAID,
                   **kwargs) -> str:
    """便捷的图可视化函数"""
    if isinstance(format, str):
        format = VisualizationFormat(format)
    
    config = VisualizationConfig(format=format, **kwargs)
    return global_visualizer.visualize_graph(graph, config)

def save_visualization(graph: StateGraph,
                      output_path: str,
                      format: Union[str, VisualizationFormat] = VisualizationFormat.HTML,
                      **kwargs):
    """保存可视化到文件"""
    if isinstance(format, str):
        format = VisualizationFormat(format)
    
    visualization = visualize_graph(graph, format, **kwargs)
    
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(visualization)
    
    logger.info(f"可视化已保存到: {output_path}")