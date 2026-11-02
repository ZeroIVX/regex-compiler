"""draw.io (diagrams.net) XML 导出。

生成的文件可直接用 draw.io 打开编辑，包含 NFA、DFA、最小 DFA 三张图。
输出符合 draw.io 的 ``mxfile`` XML 格式。
"""

from __future__ import annotations

from xml.dom import minidom
from xml.etree import ElementTree as ET

from ..backend.dfa import DFA
from ..backend.minimize import MinDFA
from ..backend.nfa import NFA
from .layout import AutomatonGraph, GraphEdge, GraphNode, graph_height, layout_positions

STATE_WIDTH = 50
STATE_HEIGHT = 50


def render_drawio_xml(
    nfa: NFA,
    dfa: DFA,
    min_dfa: MinDFA,
    output_path: str | None = None,
) -> str:
    """生成包含 NFA、DFA、最小化 DFA 三张图的 draw.io XML。"""
    doc = ET.Element("mxfile")
    doc.set("host", "app.diagrams.net")
    doc.set("agent", "regex-compiler")
    doc.set("version", "24.0.0")

    from .svg import dfa_to_graph, min_dfa_to_graph, nfa_to_graph

    for name, diagram_id, graph, stroke in (
        ("NFA (Thompson)", "nfa-diagram", nfa_to_graph(nfa), "#1E88E5"),
        ("DFA (Subset)", "dfa-diagram", dfa_to_graph(dfa), "#EF6C00"),
        ("Minimal DFA (Hopcroft)", "min-dfa-diagram", min_dfa_to_graph(min_dfa), "#8E24AA"),
    ):
        diagram = ET.SubElement(doc, "diagram")
        diagram.set("name", name)
        diagram.set("id", diagram_id)

        model = ET.SubElement(diagram, "mxGraphModel")
        model.set("dx", "1200")
        model.set("dy", "800")
        model.set("grid", "1")
        model.set("gridSize", "10")
        model.set("page", "1")
        model.set("pageWidth", "1200")
        model.set("pageHeight", str(graph_height(len(graph.nodes))))

        root = ET.SubElement(model, "root")
        ET.SubElement(root, "mxCell", id="0")
        ET.SubElement(root, "mxCell", id="1", parent="0")

        _populate_graph(root, graph, stroke)

    rough = ET.tostring(doc, encoding="unicode")
    xml_str = minidom.parseString(rough).toprettyxml(indent="  ")

    if output_path:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(xml_str)

    return xml_str


def _populate_graph(root, graph: AutomatonGraph, stroke: str) -> None:
    """用节点与边填充 draw.io 的 root 节点。"""
    positions = layout_positions(len(graph.nodes))

    for node in graph.nodes:
        pos = positions.get(node.id)
        if pos is None:
            continue
        _append_state(root, node, pos, stroke)

    for edge in graph.edges:
        _append_edge(root, edge)


def _append_state(root, node: GraphNode, pos: tuple[float, float], stroke: str) -> None:
    """追加一个状态节点（含起始箭头与终态双圈）。"""
    cx, cy = pos
    fill = "#E8F5E9" if node.is_final else "#E3F2FD"
    w = h = STATE_WIDTH

    value = node.label
    if node.sublabel:
        value = f"{node.label}\n{node.sublabel}"

    cell = ET.SubElement(root, "mxCell")
    cell.set("id", f"s{node.id}")
    cell.set("value", value)
    cell.set(
        "style",
        "ellipse;whiteSpace=wrap;html=1;"
        f"fillColor={fill};strokeColor={stroke};strokeWidth=2;"
        "fontSize=11;fontStyle=1",
    )
    cell.set("vertex", "1")
    cell.set("parent", "1")
    geometry = ET.SubElement(cell, "mxGeometry")
    geometry.set("x", f"{cx - w / 2:.0f}")
    geometry.set("y", f"{cy - h / 2:.0f}")
    geometry.set("width", str(w))
    geometry.set("height", str(h))
    geometry.set("as", "geometry")

    if node.is_start:
        arrow = ET.SubElement(root, "mxCell")
        arrow.set("id", f"start_{node.id}")
        arrow.set("value", "")
        arrow.set(
            "style",
            "endArrow=none;html=1;strokeWidth=2;"
            "exitX=0;exitY=0.5;entryX=1;entryY=0.5;",
        )
        arrow.set("edge", "1")
        arrow.set("parent", "1")
        arrow_geom = ET.SubElement(arrow, "mxGeometry")
        arrow_geom.set("relative", "1")
        arrow_geom.set("as", "geometry")
        ET.SubElement(arrow_geom, "mxPoint").set("x", f"{cx - 70:.0f}")
        arrow_geom.find("mxPoint").set("y", f"{cy:.0f}")
        arrow_geom[0].set("as", "sourcePoint")
        target = ET.SubElement(arrow_geom, "mxPoint")
        target.set("x", f"{cx - 25:.0f}")
        target.set("y", f"{cy:.0f}")
        target.set("as", "targetPoint")

    if node.is_final:
        final = ET.SubElement(root, "mxCell")
        final.set("id", f"final_{node.id}")
        final.set("value", "")
        final.set(
            "style",
            "ellipse;whiteSpace=wrap;html=1;fillColor=none;"
            f"strokeColor={stroke};strokeWidth=1.5;",
        )
        final.set("vertex", "1")
        final.set("parent", "1")
        final_geom = ET.SubElement(final, "mxGeometry")
        final_geom.set("x", f"{cx - w / 2 - 4:.0f}")
        final_geom.set("y", f"{cy - h / 2 - 4:.0f}")
        final_geom.set("width", str(w + 8))
        final_geom.set("height", str(h + 8))
        final_geom.set("as", "geometry")


def _append_edge(root, edge: GraphEdge) -> None:
    """追加一条转移边。"""
    style = (
        "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;"
        "jettySize=auto;html=1;"
    )
    if edge.is_epsilon:
        style += "dashed=1;strokeColor=#999999;"
    else:
        style += "strokeColor=#4A90D9;"
    style += "exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;"

    cell = ET.SubElement(root, "mxCell")
    cell.set("id", f"e{edge.source}_{edge.target}_{abs(hash(edge.label)) % 10000}")
    cell.set("value", edge.label)
    cell.set("style", style)
    cell.set("edge", "1")
    cell.set("parent", "1")
    cell.set("source", f"s{edge.source}")
    cell.set("target", f"s{edge.target}")
    geometry = ET.SubElement(cell, "mxGeometry")
    geometry.set("relative", "1")
    geometry.set("as", "geometry")


__all__ = ["render_drawio_xml"]
