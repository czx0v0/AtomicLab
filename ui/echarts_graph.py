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
