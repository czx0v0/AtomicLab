"""
ECharts Graph Generator
=======================
Generate ECharts HTML containers with data-option attributes.
JS initialization handled by global_js.py via MutationObserver.

No inline <script> — Gradio gr.HTML() strips them via innerHTML.
"""

import json
import time
import html as html_lib


def _unique_id(prefix: str) -> str:
    """Generate a unique container ID to avoid collisions."""
    return f"{prefix}-{int(time.time() * 1000) % 999999}"


def generate_echarts_html(
    option: dict,
    container_id: str = "echarts-graph",
    height: int = 600,
    click_type: str = "node-select",
) -> str:
    """Generate ECharts container HTML (no script).

    The global JS (MutationObserver) auto-detects .echarts-auto elements,
    reads data-option, and calls echarts.init().

    Args:
        option: ECharts option dict
        container_id: Container ID prefix
        height: Chart height in pixels
        click_type: Click handler type ('node-select' or 'none')

    Returns:
        HTML string with data-option attribute
    """
    cid = _unique_id(container_id)
    option_json = json.dumps(option, ensure_ascii=False)
    escaped = html_lib.escape(option_json, quote=True)
    return (
        f'<div class="echarts-auto" id="{cid}" '
        f'data-option="{escaped}" data-click="{click_type}" '
        f'style="width:100%;height:{height}px;"></div>'
    )


def generate_empty_graph_html(
    message: str = "暂无知识图谱数据",
    height: int = 600,
) -> str:
    """Generate placeholder HTML for empty graph."""
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
    """Generate ECharts HTML with highlighted search results."""
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


def generate_tree_echarts_html(
    option: dict,
    container_id: str = "write-tree-graph",
    height: int = 500,
) -> str:
    """Generate ECharts HTML for tree layout visualization."""
    return generate_echarts_html(option, container_id, height, click_type="none")


def graphrag_edges_to_echarts_option(edges, title: str = "GraphRAG 知识图谱") -> dict:
    """将 GraphRAG 的 (主体, 谓语, 宾语) 三元组列表转为 ECharts graph 配置，便于可视化。

    Args:
        edges: List of (s, p, o) or [s, p, o]; 每条边对应主谓宾
        title: 图表标题（用于 tooltip 等）

    Returns:
        ECharts option dict，可直接传给 generate_echarts_html
    """
    if not edges:
        return {}
    node_ids = set()
    links_data = []
    for e in edges:
        s, p, o = (e[0], e[1], e[2]) if len(e) >= 3 else ("", "", "")
        if not s and not o:
            continue
        if s:
            node_ids.add(s)
        if o:
            node_ids.add(o)
        links_data.append({
            "source": s or "_",
            "target": o or "_",
            "value": p or "",
        })
    nodes_data = [
        {
            "id": nid,
            "name": nid[:24] + ("..." if len(nid) > 24 else ""),
            "symbolSize": 28,
            "category": 0,
            "itemStyle": {"color": "#63b3ed"},
            "label": {"show": True, "fontSize": 10},
        }
        for nid in sorted(node_ids)
    ]
    if not nodes_data:
        return {}
    return {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}",
            "triggerOn": "mousemove",
        },
        "series": [
            {
                "type": "graph",
                "layout": "force",
                "data": nodes_data,
                "links": links_data,
                "categories": [{"name": "实体"}],
                "roam": True,
                "draggable": True,
                "force": {
                    "repulsion": 200,
                    "gravity": 0.08,
                    "edgeLength": [80, 200],
                },
                "label": {"position": "right", "formatter": "{b}"},
                "edgeLabel": {"show": True, "formatter": "{c}"},
                "lineStyle": {"curveness": 0.2, "width": 2},
                "emphasis": {"focus": "adjacency", "lineStyle": {"width": 4}},
            }
        ],
    }


def generate_graphrag_html(edges, container_id: str = "graphrag-graph", height: int = 380) -> str:
    """根据 GraphRAG 边列表生成 ECharts 图 HTML。无边时返回占位提示。"""
    option = graphrag_edges_to_echarts_option(edges)
    if not option:
        return generate_empty_graph_html("当前文档暂无三元组图（GraphRAG 边）", height=height)
    return generate_echarts_html(option, container_id=container_id, height=height, click_type="none")
