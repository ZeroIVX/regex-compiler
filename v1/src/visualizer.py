"""可视化器 —— 将 NFA/DFA/最小化 DFA 输出为 SVG 和 draw.io XML"""

from __future__ import annotations
import os
from xml.etree import ElementTree as ET
from xml.dom import minidom

from .nfa import NFA, NFAState, EPSILON
from .dfa import DFA, DFAState
from .minimize import MinDFA, MinDFAState

# ============================================================
# SVG 可视化
# ============================================================

SVG_WIDTH = 800
STATE_RADIUS = 22
H_SPACING = 140
V_SPACING = 100
MARGIN_X = 80
MARGIN_Y = 60


def _layout_states(num_states: int) -> list[tuple[float, float]]:
    """简单的网格布局：每行最多 5 个状态"""
    cols = min(num_states, 5)
    positions: list[tuple[float, float]] = []
    for i in range(num_states):
        row = i // cols
        col = i % cols
        x = MARGIN_X + col * H_SPACING
        y = MARGIN_Y + row * V_SPACING
        positions.append((x, y))
    return positions


def _svg_arrow(from_pos: tuple[float, float], to_pos: tuple[float, float],
               label: str, is_epsilon: bool = False,
               self_loop: bool = False) -> list[str]:
    """生成 SVG 箭头元素"""
    elements: list[str] = []
    x1, y1 = from_pos
    x2, y2 = to_pos

    if self_loop:
        elements.append(
            f'<path d="M {x1 + STATE_RADIUS - 4} {y1 - 6} '
            f'Q {x1 + STATE_RADIUS + 25} {y1 - 40} '
            f'{x1 + STATE_RADIUS + 10} {y1 - 28} '
            f'Q {x1 + STATE_RADIUS - 5} {y1 - 16} '
            f'{x1 + STATE_RADIUS - 2} {y1 - 5}" '
            f'fill="none" stroke="#666" stroke-width="1.5" marker-end="url(#arrowhead)"/>'
        )
        # 标签放在自环上方
        label_x = x1 + STATE_RADIUS + 5
        label_y = y1 - 45
    else:
        # 计算切线交点
        dx = x2 - x1
        dy = y2 - y1
        dist = (dx ** 2 + dy ** 2) ** 0.5
        if dist < 1:
            return elements

        ux = dx / dist
        uy = dy / dist

        start_x = x1 + ux * STATE_RADIUS
        start_y = y1 + uy * STATE_RADIUS
        end_x = x2 - ux * STATE_RADIUS
        end_y = y2 - uy * STATE_RADIUS

        stroke_style = 'stroke-dasharray="5,3"' if is_epsilon else ''
        elements.append(
            f'<line x1="{start_x:.1f}" y1="{start_y:.1f}" '
            f'x2="{end_x:.1f}" y2="{end_y:.1f}" '
            f'fill="none" stroke="#4A90D9" stroke-width="1.5" '
            f'marker-end="url(#arrowhead)" {stroke_style}/>'
        )
        label_x = (x1 + x2) / 2 + 8
        label_y = (y1 + y2) / 2 - 8

    # 标签
    if is_epsilon:
        display_label = "ε"
        label_color = "#888"
    elif label == '':
        return elements
    else:
        display_label = label
        label_color = "#D85A30"

    elements.append(
        f'<text x="{label_x:.1f}" y="{label_y:.1f}" '
        f'fill="{label_color}" font-size="11" font-family="monospace" '
        f'text-anchor="middle">{display_label}</text>'
    )
    return elements


def render_nfa_svg(nfa: NFA, output_path: str | None = None) -> str:
    """将 NFA 渲染为 SVG"""
    states = nfa.states
    positions = _layout_states(len(states))

    id_to_pos: dict[int, tuple[float, float]] = {}
    for st, pos in zip(states, positions):
        id_to_pos[st.id] = pos

    # 收集所有转移（去重）
    edges: list[tuple[tuple[float, float], tuple[float, float], str, bool, bool]] = []
    for st in states:
        from_pos = id_to_pos[st.id]
        for sym, targets in st.transitions.items():
            for target in targets:
                to_pos = id_to_pos[target.id]
                label = '' if sym is EPSILON else sym
                is_eps = sym is EPSILON
                self_loop = (st.id == target.id)
                edges.append((from_pos, to_pos, label, is_eps, self_loop))

    rows = max(1, (len(states) + 4) // 5)
    svg_height = MARGIN_Y + rows * V_SPACING + 80

    svg = _svg_template_begin(svg_height)
    svg.append(_svg_arrow_defs())

    # 画转移边
    for from_pos, to_pos, label, is_eps, self_loop in edges:
        svg.extend(_svg_arrow(from_pos, to_pos, label, is_eps, self_loop))

    # 画状态
    for st, (cx, cy) in zip(states, positions):
        fill = "#E8F5E9" if st.is_final else "#E3F2FD"
        stroke = "#43A047" if st.is_final else "#1E88E5"
        svg.append(f'<circle cx="{cx}" cy="{cy}" r="{STATE_RADIUS}" '
                   f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        svg.append(f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" '
                   f'font-size="12" font-family="sans-serif" font-weight="bold">'
                   f'{st.id}</text>')

        # 起始状态：入口箭头
        if st.id == nfa.start.id:
            svg.append(
                f'<polygon points="{cx - STATE_RADIUS - 4},{cy} '
                f'{cx - STATE_RADIUS - 16},{cy - 8} '
                f'{cx - STATE_RADIUS - 16},{cy + 8}" '
                f'fill="#333"/>'
            )

        # 终态：双圈
        if st.is_final:
            svg.append(f'<circle cx="{cx}" cy="{cy}" r="{STATE_RADIUS + 3}" '
                       f'fill="none" stroke="#43A047" stroke-width="1.5"/>')

    svg.append(_svg_template_end())
    result = "\n".join(svg)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)

    return result


def render_dfa_svg(dfa: DFA, output_path: str | None = None) -> str:
    """将 DFA 渲染为 SVG"""
    states = dfa.states
    positions = _layout_states(len(states))

    id_to_pos: dict[int, tuple[float, float]] = {}
    for st, pos in zip(states, positions):
        id_to_pos[st.id] = pos

    # 收集转移
    edges: list[tuple[tuple[float, float], tuple[float, float], str, bool]] = []
    for st in states:
        from_pos = id_to_pos[st.id]
        for sym, target in st.transitions.items():
            to_pos = id_to_pos[target.id]
            self_loop = (st.id == target.id)
            edges.append((from_pos, to_pos, sym, self_loop))

    rows = max(1, (len(states) + 4) // 5)
    svg_height = MARGIN_Y + rows * V_SPACING + 80

    svg = _svg_template_begin(svg_height)
    svg.append(_svg_arrow_defs())

    # 分离自环和普通转移，合并同目标的多转移
    merged_edges: dict[tuple, list[str]] = {}
    self_edges = []
    for from_pos, to_pos, label, is_self in edges:
        if is_self:
            self_edges.append((from_pos, to_pos, label))
        else:
            key = (from_pos, to_pos)
            if key not in merged_edges:
                merged_edges[key] = []
            merged_edges[key].append(label)

    # 画自环
    for from_pos, to_pos, label in self_edges:
        svg.extend(_svg_arrow(from_pos, to_pos, label, is_epsilon=False, self_loop=True))

    # 画普通转移（合并标签）
    for (from_pos, to_pos), labels in merged_edges.items():
        combined = ",".join(sorted(labels))
        if len(combined) > 8:
            combined = combined[:7] + "…"
        svg.extend(_svg_arrow(from_pos, to_pos, combined, is_epsilon=False, self_loop=False))

    # 画状态
    for st, (cx, cy) in zip(states, positions):
        fill = "#FFF3E0" if st.is_final else "#E3F2FD"
        stroke = "#EF6C00" if st.is_final else "#1E88E5"
        svg.append(f'<circle cx="{cx}" cy="{cy}" r="{STATE_RADIUS}" '
                   f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        svg.append(f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" '
                   f'font-size="12" font-family="sans-serif" font-weight="bold">'
                   f'{st.id}</text>')

        if st.id == dfa.start.id:
            svg.append(
                f'<polygon points="{cx - STATE_RADIUS - 4},{cy} '
                f'{cx - STATE_RADIUS - 16},{cy - 8} '
                f'{cx - STATE_RADIUS - 16},{cy + 8}" '
                f'fill="#333"/>'
            )

        if st.is_final:
            svg.append(f'<circle cx="{cx}" cy="{cy}" r="{STATE_RADIUS + 3}" '
                       f'fill="none" stroke="#EF6C00" stroke-width="1.5"/>')

    svg.append(_svg_template_end())
    result = "\n".join(svg)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)

    return result


def render_min_dfa_svg(min_dfa: MinDFA, output_path: str | None = None) -> str:
    """将最小化 DFA 渲染为 SVG"""
    states = min_dfa.states
    positions = _layout_states(len(states))

    id_to_pos: dict[int, tuple[float, float]] = {}
    for st, pos in zip(states, positions):
        id_to_pos[st.id] = pos

    edges: list[tuple[tuple[float, float], tuple[float, float], str, bool]] = []
    for st in states:
        from_pos = id_to_pos[st.id]
        for sym, target in st.transitions.items():
            to_pos = id_to_pos[target.id]
            self_loop = (st.id == target.id)
            edges.append((from_pos, to_pos, sym, self_loop))

    rows = max(1, (len(states) + 4) // 5)
    svg_height = MARGIN_Y + rows * V_SPACING + 80

    svg = _svg_template_begin(svg_height)
    svg.append(_svg_arrow_defs())

    merged_edges: dict[tuple, list[str]] = {}
    self_edges = []
    for from_pos, to_pos, label, self_loop in edges:
        if self_loop:
            self_edges.append((from_pos, to_pos, label))
        else:
            key = (from_pos, to_pos)
            if key not in merged_edges:
                merged_edges[key] = []
            merged_edges[key].append(label)

    for from_pos, to_pos, label in self_edges:
        svg.extend(_svg_arrow(from_pos, to_pos, label, is_epsilon=False, self_loop=True))

    for (from_pos, to_pos), labels in merged_edges.items():
        combined = ",".join(sorted(labels))
        if len(combined) > 8:
            combined = combined[:7] + "…"
        svg.extend(_svg_arrow(from_pos, to_pos, combined, is_epsilon=False, self_loop=False))

    for st, (cx, cy) in zip(states, positions):
        fill = "#F3E5F5" if st.is_final else "#E3F2FD"
        stroke = "#8E24AA" if st.is_final else "#1E88E5"
        svg.append(f'<circle cx="{cx}" cy="{cy}" r="{STATE_RADIUS}" '
                   f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        svg.append(f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" '
                   f'font-size="12" font-family="sans-serif" font-weight="bold">'
                   f'{st.id}</text>')

        # 显示原始状态
        orig_str = ",".join(str(x) for x in st.original_ids)
        svg.append(f'<text x="{cx}" y="{cy + STATE_RADIUS + 14}" '
                   f'text-anchor="middle" font-size="9" fill="#888">'
                   f'[{orig_str}]</text>')

        if st.id == min_dfa.start.id:
            svg.append(
                f'<polygon points="{cx - STATE_RADIUS - 4},{cy} '
                f'{cx - STATE_RADIUS - 16},{cy - 8} '
                f'{cx - STATE_RADIUS - 16},{cy + 8}" '
                f'fill="#333"/>'
            )

        if st.is_final:
            svg.append(f'<circle cx="{cx}" cy="{cy}" r="{STATE_RADIUS + 3}" '
                       f'fill="none" stroke="#8E24AA" stroke-width="1.5"/>')

    svg.append(_svg_template_end())
    result = "\n".join(svg)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)

    return result


# ---- SVG 模板 ----

def _svg_template_begin(height: int) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {SVG_WIDTH} {height}" width="100%">',
        '<rect width="100%" height="100%" fill="#FAFAFA"/>',
    ]


def _svg_arrow_defs() -> str:
    return (
        '<defs>'
        '<marker id="arrowhead" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="6" markerHeight="6" orient="auto">'
        '<path d="M 0 0 L 10 5 L 0 10 Z" fill="#4A90D9"/>'
        '</marker>'
        '</defs>'
    )


def _svg_template_end() -> str:
    return '</svg>'


# ============================================================
# draw.io XML 可视化
# ============================================================

def _drawio_state(cx: float, cy: float, state_id: int, is_final: bool,
                   is_start: bool, nfa_ids: str = '',
                   color: str = "#1E88E5") -> str:
    """生成 draw.io 状态元素"""
    fill = "#E8F5E9" if is_final else "#E3F2FD"
    stroke = "#43A047" if is_final else color
    w, h = 50, 50

    lines = [
        f'<mxCell id="s{state_id}" value="{state_id}{nfa_ids}" '
        f'style="ellipse;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};'
        f'strokeWidth=2;fontSize=11;fontStyle=1" vertex="1" parent="1">',
        f'<mxGeometry x="{cx - w/2:.0f}" y="{cy - h/2:.0f}" width="{w}" height="{h}" as="geometry"/>',
        '</mxCell>',
    ]

    if is_start:
        lines.append(
            f'<mxCell id="start_{state_id}" value="" '
            f'style="endArrow=none;html=1;strokeWidth=2;exitX=0;exitY=0.5;entryX=1;entryY=0.5;" '
            f'edge="1" parent="1">'
            f'<mxGeometry relative="1" as="geometry">'
            f'<mxPoint x="{cx - 70:.0f}" y="{cy:.0f}" as="sourcePoint"/>'
            f'<mxPoint x="{cx - 25:.0f}" y="{cy:.0f}" as="targetPoint"/>'
            f'</mxGeometry>'
            f'</mxCell>'
        )

    if is_final:
        lines.append(
            f'<mxCell id="final_{state_id}" value="" '
            f'style="ellipse;whiteSpace=wrap;html=1;fillColor=none;'
            f'strokeColor={stroke};strokeWidth=1.5;" vertex="1" parent="1">'
            f'<mxGeometry x="{cx - w/2 - 4:.0f}" y="{cy - h/2 - 4:.0f}" '
            f'width="{w + 8}" height="{h + 8}" as="geometry"/>'
            f'</mxCell>'
        )

    return "\n".join(lines)


def _drawio_edge(from_id: int, to_id: int, label: str, is_epsilon: bool = False) -> str:
    """生成 draw.io 转移边"""
    style = 'edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;'
    if is_epsilon:
        style += 'dashed=1;strokeColor=#999999;'
    else:
        style += 'strokeColor=#4A90D9;'
    style += 'exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;'

    display = "ε" if is_epsilon else label
    return (
        f'<mxCell id="e{from_id}_{to_id}" value="{display}" '
        f'style="{style}" edge="1" parent="1" source="s{from_id}" target="s{to_id}">'
        f'<mxGeometry relative="1" as="geometry"/>'
        f'</mxCell>'
    )


def render_drawio_xml(nfa: NFA, dfa: DFA, min_dfa: MinDFA,
                       output_path: str) -> str:
    """生成包含 NFA、DFA、最小化 DFA 三张图的 draw.io XML"""
    doc = ET.Element('mxfile')
    doc.set('host', 'app.diagrams.net')
    doc.set('modified', '2026-06-27T00:00:00.000Z')
    doc.set('agent', 'regex-compiler')
    doc.set('version', '24.0.0')

    # ---- NFA 图 ----
    diag_nfa = ET.SubElement(doc, 'diagram')
    diag_nfa.set('name', 'NFA (Thompson)')
    diag_nfa.set('id', 'nfa-diagram')
    graph_nfa = ET.SubElement(diag_nfa, 'mxGraphModel')
    graph_nfa.set('dx', '1200')
    graph_nfa.set('dy', '800')
    graph_nfa.set('grid', '1')
    graph_nfa.set('gridSize', '10')

    root_nfa = ET.SubElement(graph_nfa, 'root')
    ET.SubElement(root_nfa, 'mxCell', id='0')
    ET.SubElement(root_nfa, 'mxCell', id='1', parent='0')

    _populate_drawio_edges_nfa(nfa, root_nfa)

    # ---- DFA 图 ----
    diag_dfa = ET.SubElement(doc, 'diagram')
    diag_dfa.set('name', 'DFA (Subset)')
    diag_dfa.set('id', 'dfa-diagram')
    graph_dfa = ET.SubElement(diag_dfa, 'mxGraphModel')
    graph_dfa.set('dx', '1200')
    graph_dfa.set('dy', '800')
    graph_dfa.set('grid', '1')
    graph_dfa.set('gridSize', '10')

    root_dfa = ET.SubElement(graph_dfa, 'root')
    ET.SubElement(root_dfa, 'mxCell', id='0')
    ET.SubElement(root_dfa, 'mxCell', id='1', parent='0')

    _populate_drawio_dfa(dfa, root_dfa)

    # ---- 最小化 DFA 图 ----
    diag_min = ET.SubElement(doc, 'diagram')
    diag_min.set('name', 'Minimal DFA (Hopcroft)')
    diag_min.set('id', 'min-dfa-diagram')
    graph_min = ET.SubElement(diag_min, 'mxGraphModel')
    graph_min.set('dx', '1200')
    graph_min.set('dy', '800')
    graph_min.set('grid', '1')
    graph_min.set('gridSize', '10')

    root_min = ET.SubElement(graph_min, 'root')
    ET.SubElement(root_min, 'mxCell', id='0')
    ET.SubElement(root_min, 'mxCell', id='1', parent='0')

    _populate_drawio_min_dfa(min_dfa, root_min)

    # 生成字符串
    rough = ET.tostring(doc, encoding='unicode')
    reparsed = minidom.parseString(rough)
    xml_str = reparsed.toprettyxml(indent="  ")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xml_str)

    return xml_str


def _populate_drawio_edges_nfa(nfa: NFA, root):
    """用 NFA 的状态和转移填充 draw.io 根节点"""
    # 使用 ElementTree 创建元素
    states = nfa.states
    positions = _layout_states(len(states))
    id_to_pos = {st.id: pos for st, pos in zip(states, positions)}

    for st, (cx, cy) in zip(states, positions):
        xml_str = _drawio_state(
            cx, cy, st.id, st.is_final,
            st.id == nfa.start.id, color="#1E88E5"
        )
        _append_xml_to_root(root, xml_str)

    for st in states:
        for sym, targets in st.transitions.items():
            for target in targets:
                xml_str = _drawio_edge(
                    st.id, target.id,
                    '' if sym is EPSILON else sym,
                    is_epsilon=(sym is EPSILON)
                )
                _append_xml_to_root(root, xml_str)


def _populate_drawio_dfa(dfa: DFA, root):
    """用 DFA 的状态和转移填充 draw.io 根节点"""
    states = dfa.states
    positions = _layout_states(len(states))

    for st, (cx, cy) in zip(states, positions):
        nfa_ids = "\n".join(str(s.id) for s in sorted(st.nfa_states, key=lambda x: x.id))
        xml_str = _drawio_state(
            cx, cy, st.id, st.is_final,
            st.id == dfa.start.id, nfa_ids="\n{" + nfa_ids + "}", color="#EF6C00"
        )
        _append_xml_to_root(root, xml_str)

    for st in states:
        # 合并同目标的多转移
        merged: dict[int, list[str]] = {}
        for sym, target in st.transitions.items():
            if target.id not in merged:
                merged[target.id] = []
            merged[target.id].append(sym)

        for target_id, labels in merged.items():
            label = ",".join(sorted(labels))
            xml_str = _drawio_edge(st.id, target_id, label)
            _append_xml_to_root(root, xml_str)


def _populate_drawio_min_dfa(min_dfa: MinDFA, root):
    """用最小化 DFA 的状态和转移填充 draw.io 根节点"""
    states = min_dfa.states
    positions = _layout_states(len(states))

    for st, (cx, cy) in zip(states, positions):
        orig_str = "\n{" + ",".join(str(x) for x in st.original_ids) + "}"
        xml_str = _drawio_state(
            cx, cy, st.id, st.is_final,
            st.id == min_dfa.start.id, nfa_ids=orig_str, color="#8E24AA"
        )
        _append_xml_to_root(root, xml_str)

    for st in states:
        merged: dict[int, list[str]] = {}
        for sym, target in st.transitions.items():
            if target.id not in merged:
                merged[target.id] = []
            merged[target.id].append(sym)

        for target_id, labels in merged.items():
            label = ",".join(sorted(labels))
            xml_str = _drawio_edge(st.id, target_id, label)
            _append_xml_to_root(root, xml_str)


def _append_xml_to_root(root, xml_str: str):
    """将 XML 字符串解析并追加到 ElementTree root 中"""
    try:
        elem = ET.fromstring(xml_str)
        root.append(elem)
    except ET.ParseError:
        pass  # 跳过无法解析的片段
