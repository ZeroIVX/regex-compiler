"""可视化模块 —— 把自动机渲染为 SVG 或 draw.io XML。"""

from __future__ import annotations

from .drawio import render_drawio_xml
from .layout import AutomatonGraph, GraphEdge, GraphNode
from .svg import (
    dfa_to_graph,
    min_dfa_to_graph,
    nfa_to_graph,
    render_dfa_svg,
    render_min_dfa_svg,
    render_nfa_svg,
)

__all__ = [
    "AutomatonGraph",
    "GraphEdge",
    "GraphNode",
    "dfa_to_graph",
    "min_dfa_to_graph",
    "nfa_to_graph",
    "render_dfa_svg",
    "render_drawio_xml",
    "render_min_dfa_svg",
    "render_nfa_svg",
]
