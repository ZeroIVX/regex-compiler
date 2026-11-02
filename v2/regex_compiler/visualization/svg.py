"""SVG 渲染 —— 把自动机图绘制为可缩放的矢量图形。

三种自动机共用同一套绘制管线：先转换为 :class:`AutomatonGraph`，
再由 :func:`render_graph` 统一渲染，只是配色方案不同。
"""

from __future__ import annotations

from ..backend.dfa import DFA
from ..backend.minimize import MinDFA
from ..backend.nfa import EPSILON, NFA
from .layout import (
    STATE_RADIUS,
    SVG_WIDTH,
    AutomatonGraph,
    GraphEdge,
    GraphNode,
    graph_height,
    layout_positions,
    merge_edge_labels,
)

# 三种自动机的配色方案
THEME_NFA = {
    "normal_fill": "#E3F2FD",
    "normal_stroke": "#1E88E5",
    "final_fill": "#E8F5E9",
    "final_stroke": "#43A047",
    "edge": "#4A90D9",
    "label": "#D85A30",
}

THEME_DFA = {
    "normal_fill": "#E3F2FD",
    "normal_stroke": "#1E88E5",
    "final_fill": "#FFF3E0",
    "final_stroke": "#EF6C00",
    "edge": "#4A90D9",
    "label": "#D85A30",
}

THEME_MIN_DFA = {
    "normal_fill": "#E3F2FD",
    "normal_stroke": "#1E88E5",
    "final_fill": "#F3E5F5",
    "final_stroke": "#8E24AA",
    "edge": "#4A90D9",
    "label": "#D85A30",
}


# ============================================================
# 自动机 -> 通用图结构
# ============================================================

def nfa_to_graph(nfa: NFA) -> AutomatonGraph:
    """把 NFA 转换为通用图结构。"""
    nodes = [
        GraphNode(
            id=state.id,
            label=str(state.id),
            is_final=state.is_final,
            is_start=state.id == nfa.start.id,
        )
        for state in nfa.states
    ]

    edges: list[GraphEdge] = []
    for state in nfa.states:
        for charset, targets in state.transitions.items():
            label = "ε" if charset is EPSILON else charset.label()
            for target in targets:
                edges.append(
                    GraphEdge(
                        source=state.id,
                        target=target.id,
                        label=label,
                        is_epsilon=charset is EPSILON,
                    )
                )

    return AutomatonGraph(nodes=nodes, edges=edges)


def dfa_to_graph(dfa: DFA) -> AutomatonGraph:
    """把 DFA 转换为通用图结构。"""
    nodes = [
        GraphNode(
            id=state.id,
            label=str(state.id),
            is_final=state.is_final,
            is_start=state.id == dfa.start.id,
            sublabel="{" + ",".join(
                str(s.id) for s in sorted(state.nfa_states, key=lambda x: x.id)
            ) + "}",
        )
        for state in dfa.states
    ]

    edges: list[GraphEdge] = []
    for state in dfa.states:
        for block_id, target in state.transitions.items():
            edges.append(
                GraphEdge(
                    source=state.id,
                    target=target.id,
                    label=dfa.alphabet.label_of(block_id),
                )
            )

    return AutomatonGraph(nodes=nodes, edges=edges)


def min_dfa_to_graph(min_dfa: MinDFA) -> AutomatonGraph:
    """把最小化 DFA 转换为通用图结构。"""
    nodes = [
        GraphNode(
            id=state.id,
            label=str(state.id),
            is_final=state.is_final,
            is_start=state.id == min_dfa.start.id,
            sublabel="[" + ",".join(str(x) for x in state.original_ids) + "]",
        )
        for state in min_dfa.states
    ]

    edges: list[GraphEdge] = []
    for state in min_dfa.states:
        for block_id, target in state.transitions.items():
            edges.append(
                GraphEdge(
                    source=state.id,
                    target=target.id,
                    label=min_dfa.alphabet.label_of(block_id),
                )
            )

    return AutomatonGraph(nodes=nodes, edges=edges)


# ============================================================
# SVG 渲染
# ============================================================

def render_graph(
    graph: AutomatonGraph,
    theme: dict[str, str],
    output_path: str | None = None,
) -> str:
    """把通用图结构渲染为 SVG 字符串（可选写入文件）。"""
    positions = layout_positions(len(graph.nodes))
    height = graph_height(len(graph.nodes))

    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {SVG_WIDTH} {height}" width="100%">',
        '<rect width="100%" height="100%" fill="#FAFAFA"/>',
        _arrow_defs(),
    ]

    edges = merge_edge_labels(graph.edges)

    # 先画边，再画节点，保证节点覆盖在边上
    for edge in edges:
        source_pos = positions.get(edge.source)
        target_pos = positions.get(edge.target)
        if source_pos is None or target_pos is None:
            continue
        svg.extend(
            _render_edge(source_pos, target_pos, edge, theme, edge.source == edge.target)
        )

    for node in graph.nodes:
        pos = positions.get(node.id)
        if pos is None:
            continue
        svg.extend(_render_node(pos, node, theme))

    svg.append("</svg>")
    result = "\n".join(svg)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(result)

    return result


def _render_node(
    pos: tuple[float, float],
    node: GraphNode,
    theme: dict[str, str],
) -> list[str]:
    """渲染单个状态节点（含起始箭头、终态双圈、副标题）。"""
    cx, cy = pos
    fill = theme["final_fill"] if node.is_final else theme["normal_fill"]
    stroke = theme["final_stroke"] if node.is_final else theme["normal_stroke"]

    elements = [
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{STATE_RADIUS}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>',
        f'<text x="{cx:.1f}" y="{cy + 4:.1f}" text-anchor="middle" '
        f'font-size="12" font-family="sans-serif" font-weight="bold">'
        f'{node.label}</text>',
    ]

    if node.sublabel:
        elements.append(
            f'<text x="{cx:.1f}" y="{cy + STATE_RADIUS + 14:.1f}" '
            f'text-anchor="middle" font-size="9" fill="#888">'
            f'{node.sublabel}</text>'
        )

    if node.is_start:
        elements.append(
            f'<polygon points="{cx - STATE_RADIUS - 4:.1f},{cy:.1f} '
            f'{cx - STATE_RADIUS - 16:.1f},{cy - 8:.1f} '
            f'{cx - STATE_RADIUS - 16:.1f},{cy + 8:.1f}" fill="#333"/>'
        )

    if node.is_final:
        elements.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{STATE_RADIUS + 3}" '
            f'fill="none" stroke="{stroke}" stroke-width="1.5"/>'
        )

    return elements


def _render_edge(
    source_pos: tuple[float, float],
    target_pos: tuple[float, float],
    edge: GraphEdge,
    theme: dict[str, str],
    is_self_loop: bool,
) -> list[str]:
    """渲染一条转移边（含标签）。"""
    x1, y1 = source_pos
    x2, y2 = target_pos

    if is_self_loop:
        # 自环：从节点右上方绕出再回到右上方
        elements = [
            f'<path d="M {x1 + STATE_RADIUS - 4:.1f} {y1 - 6:.1f} '
            f'Q {x1 + STATE_RADIUS + 26:.1f} {y1 - 42:.1f} '
            f'{x1 + STATE_RADIUS + 10:.1f} {y1 - 28:.1f} '
            f'Q {x1 + STATE_RADIUS - 5:.1f} {y1 - 16:.1f} '
            f'{x1 + STATE_RADIUS - 2:.1f} {y1 - 5:.1f}" '
            f'fill="none" stroke="{theme["edge"]}" stroke-width="1.5" '
            f'marker-end="url(#arrowhead)"/>'
        ]
        label_x = x1 + STATE_RADIUS + 8
        label_y = y1 - 44
    else:
        dx = x2 - x1
        dy = y2 - y1
        dist = (dx * dx + dy * dy) ** 0.5
        if dist < 1:
            return []

        ux = dx / dist
        uy = dy / dist
        start_x = x1 + ux * STATE_RADIUS
        start_y = y1 + uy * STATE_RADIUS
        end_x = x2 - ux * STATE_RADIUS
        end_y = y2 - uy * STATE_RADIUS

        dash = 'stroke-dasharray="5,3"' if edge.is_epsilon else ""
        elements = [
            f'<line x1="{start_x:.1f}" y1="{start_y:.1f}" '
            f'x2="{end_x:.1f}" y2="{end_y:.1f}" '
            f'fill="none" stroke="{theme["edge"]}" stroke-width="1.5" '
            f'marker-end="url(#arrowhead)" {dash}/>'
        ]
        label_x = (x1 + x2) / 2 + 8
        label_y = (y1 + y2) / 2 - 8

    if edge.label:
        color = "#888" if edge.is_epsilon else theme["label"]
        elements.append(
            f'<text x="{label_x:.1f}" y="{label_y:.1f}" fill="{color}" '
            f'font-size="11" font-family="monospace" text-anchor="middle">'
            f'{edge.label}</text>'
        )

    return elements


def _arrow_defs() -> str:
    """SVG 箭头标记定义。"""
    return (
        '<defs>'
        '<marker id="arrowhead" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="6" markerHeight="6" orient="auto">'
        '<path d="M 0 0 L 10 5 L 0 10 Z" fill="#4A90D9"/>'
        '</marker>'
        '</defs>'
    )


# ============================================================
# 公开渲染接口
# ============================================================

def render_nfa_svg(nfa: NFA, output_path: str | None = None) -> str:
    """把 NFA 渲染为 SVG。"""
    return render_graph(nfa_to_graph(nfa), THEME_NFA, output_path)


def render_dfa_svg(dfa: DFA, output_path: str | None = None) -> str:
    """把 DFA 渲染为 SVG。"""
    return render_graph(dfa_to_graph(dfa), THEME_DFA, output_path)


def render_min_dfa_svg(min_dfa: MinDFA, output_path: str | None = None) -> str:
    """把最小化 DFA 渲染为 SVG。"""
    return render_graph(min_dfa_to_graph(min_dfa), THEME_MIN_DFA, output_path)


__all__ = [
    "AutomatonGraph",
    "GraphEdge",
    "GraphNode",
    "dfa_to_graph",
    "min_dfa_to_graph",
    "nfa_to_graph",
    "render_dfa_svg",
    "render_graph",
    "render_min_dfa_svg",
    "render_nfa_svg",
]
