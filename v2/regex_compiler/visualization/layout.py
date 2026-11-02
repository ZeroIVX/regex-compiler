"""自动机图形布局 —— 网格布局与边计算。

把自动机抽象成「节点 + 有向边」的通用结构后，三种自动机
（NFA / DFA / MinDFA）就能复用同一套布局与渲染逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 画布尺寸常量
SVG_WIDTH = 900
STATE_RADIUS = 22
H_SPACING = 150
V_SPACING = 105
MARGIN_X = 80
MARGIN_Y = 60
MAX_COLUMNS = 5


@dataclass(frozen=True)
class GraphNode:
    """自动机图中的一个节点。"""

    id: int
    label: str
    is_final: bool = False
    is_start: bool = False
    sublabel: str = ""


@dataclass(frozen=True)
class GraphEdge:
    """自动机图中的一条有向边。"""

    source: int
    target: int
    label: str
    is_epsilon: bool = False


@dataclass
class AutomatonGraph:
    """自动机的图形表示。"""

    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)

    def node(self, node_id: int) -> GraphNode | None:
        """按 id 取节点。"""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None


def layout_positions(node_count: int) -> dict[int, tuple[float, float]]:
    """网格布局：每行最多 :data:`MAX_COLUMNS` 个节点。

    Returns:
        节点 id 到 ``(x, y)`` 坐标的映射。
    """
    if node_count <= 0:
        return {}

    columns = min(node_count, MAX_COLUMNS)
    positions: dict[int, tuple[float, float]] = {}
    for index in range(node_count):
        row = index // columns
        col = index % columns
        positions[index] = (
            MARGIN_X + col * H_SPACING,
            MARGIN_Y + row * V_SPACING,
        )
    return positions


def graph_height(node_count: int) -> int:
    """根据节点数估算画布高度。"""
    if node_count <= 0:
        return 160
    rows = (node_count + MAX_COLUMNS - 1) // MAX_COLUMNS
    return int(MARGIN_Y + rows * V_SPACING + 90)


def merge_edge_labels(edges: list[GraphEdge]) -> list[GraphEdge]:
    """合并「同起点同终点」的普通边，把标签合并成一个。

    自环单独保留 —— 它的绘制方式与普通边不同。
    """
    merged: dict[tuple[int, int], list[str]] = {}
    self_loops: list[GraphEdge] = []
    order: list[tuple[int, int]] = []

    for edge in edges:
        if edge.is_epsilon:
            continue
        if edge.source == edge.target:
            self_loops.append(edge)
            continue
        key = (edge.source, edge.target)
        if key not in merged:
            merged[key] = []
            order.append(key)
        merged[key].append(edge.label)

    result = [
        GraphEdge(source=s, target=t, label=_combine_labels(merged[(s, t)]))
        for s, t in order
    ]
    result.extend(self_loops)
    return result


def _combine_labels(labels: list[str]) -> str:
    """把多个边标签合并为一个紧凑字符串。"""
    if not labels:
        return ""
    combined = ",".join(sorted(set(labels)))
    if len(combined) > 10:
        combined = combined[:9] + "…"
    return combined
