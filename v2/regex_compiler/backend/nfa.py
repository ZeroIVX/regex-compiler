"""NFA 构造 —— Thompson 算法从 AST 构造 ε-NFA。

NFA 特点：

- 可以有 ε 转移（用 ``None`` 键表示）
- 同一字符可以有多个下一状态
- 一次可以处于多个状态

Thompson 算法为每种运算符定义了固定的 NFA 子图模式，保证整体 O(n) 复杂度。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..charset import CharClass
from ..errors import BuildError
from ..frontend.ast_nodes import (
    ASTNode,
    CharClassNode,
    CharNode,
    ConcatNode,
    DotNode,
    PlusNode,
    QuestionNode,
    StarNode,
    UnionNode,
)

EPSILON: CharClass | None = None  # ε 转移的键值


@dataclass(eq=False)
class NFAState:
    """NFA 状态。

    使用 ``eq=False`` 并显式实现 ``__eq__`` / ``__hash__``（按 id 比较），
    这样状态可以直接放进 ``set``，用于 ε-闭包计算。
    """

    id: int
    is_final: bool = False
    transitions: dict[CharClass | None, set[NFAState]] = field(default_factory=dict)

    def add_transition(self, symbol: CharClass | None, target: NFAState) -> None:
        """添加一条转移边。``symbol`` 为 ``None`` 表示 ε 转移。"""
        self.transitions.setdefault(symbol, set()).add(target)

    def __repr__(self) -> str:
        return f"NFAState(id={self.id}, final={self.is_final})"

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NFAState):
            return NotImplemented
        return self.id == other.id


@dataclass(frozen=True)
class NFAFragment:
    """NFA 构造片段 —— 包含起始状态与接受状态。"""

    start: NFAState
    accept: NFAState


@dataclass
class NFA:
    """完整的 NFA。

    Attributes:
        start: 起始状态。
        accept: 接受状态（终态）。
        states: 全部状态。
        alphabet: 出现过的字符类集合。
    """

    start: NFAState
    accept: NFAState
    states: list[NFAState]
    alphabet: list[CharClass]

    def __repr__(self) -> str:
        return f"NFA(states={len(self.states)}, classes={len(self.alphabet)})"


class ThompsonBuilder:
    """Thompson 算法 NFA 构造器。"""

    def __init__(self) -> None:
        self._next_id = 0

    def _new_state(self, is_final: bool = False) -> NFAState:
        """创建一个新的 NFA 状态。"""
        state = NFAState(id=self._next_id, is_final=is_final)
        self._next_id += 1
        return state

    def build(self, ast: ASTNode) -> NFA:
        """从 AST 构造完整的 NFA。"""
        fragment = self._build_recursive(ast)
        fragment.accept.is_final = True

        all_states = self._collect_states(fragment.start)
        alphabet = self._collect_classes(ast)

        return NFA(
            start=fragment.start,
            accept=fragment.accept,
            states=all_states,
            alphabet=alphabet,
        )

    # ---- 各节点的构造 ----

    def _build_recursive(self, node: ASTNode) -> NFAFragment:
        """递归构造 NFA 片段。"""
        match node:
            case CharNode(char):
                return self._build_char(char)
            case DotNode():
                return self._build_charset(CharClass(frozenset({"\n"}), negated=True))
            case CharClassNode(charset):
                return self._build_charset(charset)
            case ConcatNode(left, right):
                return self._build_concat(
                    self._build_recursive(left),
                    self._build_recursive(right),
                )
            case UnionNode(left, right):
                return self._build_union(
                    self._build_recursive(left),
                    self._build_recursive(right),
                )
            case StarNode(child):
                return self._build_star(self._build_recursive(child))
            case PlusNode(child):
                return self._build_plus(self._build_recursive(child))
            case QuestionNode(child):
                return self._build_question(self._build_recursive(child))
            case _:
                raise BuildError(f"无法处理的 AST 节点类型: {type(node).__name__}")

    def _build_char(self, char: str) -> NFAFragment:
        """单字符：``start --char--> accept``；空字符使用 ε 转移。"""
        start = self._new_state()
        accept = self._new_state()
        if char:
            start.add_transition(CharClass(frozenset({char})), accept)
        else:
            start.add_transition(EPSILON, accept)
        return NFAFragment(start, accept)

    def _build_charset(self, charset: CharClass) -> NFAFragment:
        """字符类：``start --charset--> accept``。

        字符类在 NFA 层面保持为一个整体，语义交由后端的字母表划分处理，
        这样既避免了为 ``[a-z]`` 展开出 26 个状态，也保证了确定性。
        """
        start = self._new_state()
        accept = self._new_state()
        start.add_transition(charset, accept)
        return NFAFragment(start, accept)

    def _build_concat(self, first: NFAFragment, second: NFAFragment) -> NFAFragment:
        """连接：``first.accept --ε--> second.start``。"""
        first.accept.add_transition(EPSILON, second.start)
        first.accept.is_final = False
        return NFAFragment(first.start, second.accept)

    def _build_union(self, left: NFAFragment, right: NFAFragment) -> NFAFragment:
        """选择：新 start 分叉到两侧，两侧汇聚到新 accept。"""
        start = self._new_state()
        accept = self._new_state()
        start.add_transition(EPSILON, left.start)
        start.add_transition(EPSILON, right.start)
        left.accept.add_transition(EPSILON, accept)
        right.accept.add_transition(EPSILON, accept)
        left.accept.is_final = False
        right.accept.is_final = False
        return NFAFragment(start, accept)

    def _build_star(self, inner: NFAFragment) -> NFAFragment:
        """闭包：新 start 可跳过或进入 inner，inner 可自环或退出。"""
        start = self._new_state()
        accept = self._new_state()
        start.add_transition(EPSILON, inner.start)
        start.add_transition(EPSILON, accept)      # 零次匹配
        inner.accept.add_transition(EPSILON, inner.start)  # 循环
        inner.accept.add_transition(EPSILON, accept)      # 退出
        inner.accept.is_final = False
        return NFAFragment(start, accept)

    def _build_plus(self, inner: NFAFragment) -> NFAFragment:
        """正闭包：``inner · inner*``。

        等价于「至少匹配一次」，因此不存在跳过 inner 的 ε 边。
        """
        star = self._build_star(inner)
        return self._build_concat(inner, star)

    def _build_question(self, inner: NFAFragment) -> NFAFragment:
        """可选：新 start 可跳过 inner，也可进入 inner。"""
        start = self._new_state()
        accept = self._new_state()
        start.add_transition(EPSILON, inner.start)
        start.add_transition(EPSILON, accept)  # 零次匹配
        inner.accept.add_transition(EPSILON, accept)
        inner.accept.is_final = False
        return NFAFragment(start, accept)

    # ---- 辅助 ----

    def _collect_states(self, start: NFAState) -> list[NFAState]:
        """从起始状态 BFS 收集所有可达状态。"""
        visited: set[int] = set()
        result: list[NFAState] = []
        queue = [start]

        while queue:
            state = queue.pop(0)
            if state.id in visited:
                continue
            visited.add(state.id)
            result.append(state)
            for targets in state.transitions.values():
                for target in targets:
                    if target.id not in visited:
                        queue.append(target)

        return result

    def _collect_classes(self, node: ASTNode) -> list[CharClass]:
        """收集 AST 中出现的字符类。"""
        from ..frontend.parser import collect_charsets

        return collect_charsets(node)


def epsilon_closure(states: set[NFAState]) -> set[NFAState]:
    """计算一组 NFA 状态的 ε-闭包（通过 ε 转移可达的所有状态）。"""
    closure = set(states)
    stack = list(states)

    while stack:
        state = stack.pop()
        if EPSILON in state.transitions:
            for next_state in state.transitions[EPSILON]:
                if next_state not in closure:
                    closure.add(next_state)
                    stack.append(next_state)

    return closure


def nfa_move(
    states: set[NFAState],
    charset: CharClass,
) -> set[NFAState]:
    """从一组 NFA 状态通过字符类 ``charset`` 转移一步。

    转移边以 :class:`CharClass` 为键；只有当边的字符类 *包含* 目标字符类时
    才可沿该边移动。
    """
    result: set[NFAState] = set()
    for state in states:
        for edge_class, targets in state.transitions.items():
            if edge_class is None:
                continue
            if edge_class.chars == charset.chars and edge_class.negated == charset.negated:
                result.update(targets)
    return result
