"""
ECharts Graph Generator
=======================
Generate ECharts HTML for knowledge graph visualization.
"""

import json
from typing import Optional


def generate_echarts_html(
    option: dict,
    container_id: str = "echarts-graph",
    height: int = 600,
    on_click_callback: str = None,
) -> str:
    """Generate self-contained ECharts HTML.
    
    Args:
        option: ECharts option dict
        container_id: Container element ID
        height: Chart height in pixels
        on_click_callback: Optional JS callback for node clicks
        
    Returns:
        Complete HTML string with embedded ECharts
    """
    option_json = json.dumps(option, ensure_ascii=False)
    
    # Default click handler that updates hidden textbox
    if not on_click_callback:
        on_click_callback = """
            function(params) {
                if (params.dataType === 'node') {
                    // Find the hidden textbox and update its value
                    var hiddenInput = document.querySelector('#selected-node-input textarea');
                    if (hiddenInput) {
                        hiddenInput.value = params.data.id;
                        hiddenInput.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                }
            }
        """
    
    html = f"""
<div id="{container_id}" style="width:100%;height:{height}px;"></div>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<script>
(function() {{
    var chartDom = document.getElementById('{container_id}');
    var myChart = echarts.init(chartDom);
    var option = {option_json};
    
    myChart.setOption(option);
    
    // Handle click events
    myChart.on('click', {on_click_callback});
    
    // Responsive resize
    window.addEventListener('resize', function() {{
        myChart.resize();
    }});
}})();
</script>
"""
    return html


def generate_empty_graph_html(
    message: str = "暂无知识图谱数据",
    height: int = 600,
) -> str:
    """Generate placeholder HTML for empty graph.
    
    Args:
        message: Placeholder message
        height: Container height
        
    Returns:
        HTML string
    """
    return f"""
<div class="graph-container" style="height:{height}px;">
    <div class="graph-empty">{message}</div>
</div>
"""


def generate_graph_with_search_highlight(
    option: dict,
    highlight_ids: list[str],
    container_id: str = "echarts-graph",
    height: int = 600,
) -> str:
    """Generate ECharts HTML with highlighted search results.
    
    Args:
        option: ECharts option dict
        highlight_ids: Node IDs to highlight
        container_id: Container element ID
        height: Chart height
        
    Returns:
        HTML string with highlighted nodes
    """
    # Modify node styles for highlighted nodes
    if "series" in option and option["series"]:
        series = option["series"][0]
        if "data" in series:
            for node in series["data"]:
                if node.get("id") in highlight_ids:
                    node["itemStyle"] = {
                        "color": "#f56565",
                        "borderWidth": 4,
                        "borderColor": "#c53030",
                        "shadowBlur": 10,
                        "shadowColor": "rgba(245, 101, 101, 0.5)",
                    }
                    node["symbolSize"] = node.get("symbolSize", 30) * 1.3
    
    return generate_echarts_html(option, container_id, height)


def generate_tree_view_html(nodes: list[dict], selected_id: str = None) -> str:
    """Generate collapsible tree view HTML.
    
    Args:
        nodes: List of node dicts with children
        selected_id: ID of selected node
        
    Returns:
        HTML string for tree view
    """
    def render_node(node: dict, level: int = 0) -> str:
        node_id = node.get("id", "")
        label = node.get("label", "")[:30]
        node_type = node.get("type", "")
        children = node.get("children", [])
        is_selected = node_id == selected_id
        
        selected_class = " selected" if is_selected else ""
        has_children = len(children) > 0
        
        html = f"""
<div class="tree-node{selected_class}" style="margin-left:{level * 16}px;" data-node-id="{node_id}">
    <span class="tree-toggle">{('▶' if has_children else '•')}</span>
    <span class="tree-type tree-type-{node_type}">{node_type[:1].upper()}</span>
    <span class="tree-label">{label}</span>
</div>
"""
        for child in children:
            html += render_node(child, level + 1)
        return html
    
    tree_html = ""
    for node in nodes:
        tree_html += render_node(node)
    
    return f"""
<div class="tree-view">
    {tree_html}
</div>
<style>
.tree-view {{ font-size: .85em; }}
.tree-node {{ padding: 4px 8px; cursor: pointer; display: flex; align-items: center; gap: 6px; border-radius: 4px; }}
.tree-node:hover {{ background: #f7fafc; }}
.tree-node.selected {{ background: #e6f0ff; }}
.tree-toggle {{ color: #a0aec0; font-size: .7em; width: 12px; }}
.tree-type {{ font-size: .7em; padding: 1px 4px; border-radius: 2px; font-weight: 600; }}
.tree-type-domain {{ background: #e6f0ff; color: #5b8def; }}
.tree-type-atom {{ background: #e6ffed; color: #48bb78; }}
.tree-type-note {{ background: #fefce8; color: #d69e2e; }}
.tree-type-concept {{ background: #f3e8ff; color: #9f7aea; }}
.tree-label {{ color: #2d3748; }}
</style>
"""
