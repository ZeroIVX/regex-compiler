"""NFA 构造 —— Thompson 算法从 AST 构造 ε-NFA

NFA 特点：
- 可以有 ε 转移（用 None 键表示）
- 同一字符可以有多个下一状态
- 一次可以处于多个状态

数据结构：
- NFAState: 单个状态，包含 id、是否终态、转移表
- NFA: 包含起始状态和接受状态的 NFA 片段
"""

from __future__ import annotations
from dataclasses import dataclass, field

from .ast_nodes import (
    ASTNode, CharNode, DotNode, ConcatNode,
    UnionNode, StarNode, PlusNode, QuestionNode, CharClassNode,
)
from .lexer import UNIVERSE

EPSILON = None  # ε 转移的键值

# 通配符 `.` 展开后的字符集：除换行外的全部字符
DOT_CHARS = frozenset(UNIVERSE - {"\n"})


@dataclass
class NFAState:
    """NFA 状态"""
    id: int
    is_final: bool = False
    transitions: dict[str | None, set[NFAState]] = field(default_factory=dict)

    def add_transition(self, symbol: str | None, target: NFAState) -> None:
        """添加一条转移边"""
        if symbol not in self.transitions:
            self.transitions[symbol] = set()
        self.transitions[symbol].add(target)

    def __repr__(self):
        return f"NFAState(id={self.id}, final={self.is_final})"

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if not isinstance(other, NFAState):
            return False
        return self.id == other.id


@dataclass
class NFAFragment:
    """NFA 构造片段 —— 包含起始状态和接受状态"""
    start: NFAState
    accept: NFAState


class NFA:
    """完整的 NFA"""

    def __init__(self, start: NFAState, accept: NFAState,
                 states: list[NFAState], alphabet: set[str]):
        self.start = start
        self.accept = accept
        self.states = states
        self.alphabet = alphabet  # 不含 ε 的输入符号集

    def __repr__(self):
        return f"NFA(states={len(self.states)}, alphabet={self.alphabet})"


class ThompsonBuilder:
    """Thompson 算法 NFA 构造器"""

    def __init__(self):
        self._next_id = 0

    def _new_state(self, is_final: bool = False) -> NFAState:
        """创建一个新的 NFA 状态"""
        st = NFAState(id=self._next_id, is_final=is_final)
        self._next_id += 1
        return st

    def build(self, ast: ASTNode) -> NFA:
        """从 AST 构造完整的 NFA"""
        fragment = self._build_recursive(ast)
        fragment.accept.is_final = True

        # 收集所有状态
        all_states = self._collect_states(fragment.start)

        # 收集字母表：所有真实字符（不含 ε）
        alphabet: set[str] = set()
        for st in all_states:
            for sym in st.transitions:
                if sym is not EPSILON:
                    alphabet.add(sym)

        return NFA(
            start=fragment.start,
            accept=fragment.accept,
            states=all_states,
            alphabet=alphabet,
        )

    def _build_recursive(self, node: ASTNode) -> NFAFragment:
        """递归构造 NFA 片段"""
        match node:
            case CharNode(char):
                return self._build_char(char)
            case DotNode():
                return self._build_dot()
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
            case CharClassNode(chars):
                return self._build_char_class(chars)
            case _:
                raise ValueError(f"Unknown AST node: {type(node).__name__}")

    def _build_char(self, char: str) -> NFAFragment:
        """构造单字符 NFA: start --char--> accept；空字符使用 ε 转移"""
        start = self._new_state()
        accept = self._new_state()
        if char:
            start.add_transition(char, accept)
        else:
            # 空字符串：使用 ε 转移
            start.add_transition(EPSILON, accept)
        return NFAFragment(start, accept)

    def _build_dot(self) -> NFAFragment:
        """构造通配符 NFA

        `.` 展开为「除换行外的全部字符」构成的字符类选择，
        展开基准是 lexer 中定义的字符全集。
        """
        return self._build_char_class(DOT_CHARS)

    def _build_concat(self, first: NFAFragment, second: NFAFragment) -> NFAFragment:
        """连接: first ---ε---> second"""
        first.accept.add_transition(EPSILON, second.start)
        first.accept.is_final = False
        return NFAFragment(first.start, second.accept)

    def _build_union(self, left: NFAFragment, right: NFAFragment) -> NFAFragment:
        """选择: 新 start --ε--> left.start / right.start
                     left.accept --ε--> 新 accept
                     right.accept --ε--> 新 accept"""
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
        """闭包: 新 start --ε--> inner.start
                    inner.accept --ε--> inner.start (循环)
                    inner.accept --ε--> 新 accept
                    新 start --ε--> 新 accept (跳过)"""
        start = self._new_state()
        accept = self._new_state()
        start.add_transition(EPSILON, inner.start)
        start.add_transition(EPSILON, accept)  # 零次
        inner.accept.add_transition(EPSILON, inner.start)  # 循环
        inner.accept.add_transition(EPSILON, accept)  # 退出
        inner.accept.is_final = False
        return NFAFragment(start, accept)

    def _build_plus(self, inner: NFAFragment) -> NFAFragment:
        """正闭包: 等同于 inner · inner*"""
        star = self._build_star(inner)
        return self._build_concat(inner, star)

    def _build_question(self, inner: NFAFragment) -> NFAFragment:
        """可选: 新 start --ε--> inner.start
                    新 start --ε--> accept (跳过)"""
        start = self._new_state()
        accept = self._new_state()
        start.add_transition(EPSILON, inner.start)
        start.add_transition(EPSILON, accept)  # 零次跳过
        inner.accept.add_transition(EPSILON, accept)
        inner.accept.is_final = False
        return NFAFragment(start, accept)

    def _build_char_class(self, chars) -> NFAFragment:
        """字符类: 用选择连接所有字符

        取反语义已在词法阶段展开为具体字符集，这里只处理普通字符集。
        """
        if not chars:
            return self._build_char('')

        char_list = sorted(chars)
        first = self._build_char(char_list[0])
        for c in char_list[1:]:
            first = self._build_union(first, self._build_char(c))

        return first

    def _collect_states(self, start: NFAState) -> list[NFAState]:
        """从起始状态 BFS 收集所有可达状态"""
        visited: set[int] = set()
        result: list[NFAState] = []
        queue = [start]

        while queue:
            st = queue.pop(0)
            if st.id in visited:
                continue
            visited.add(st.id)
            result.append(st)
            for targets in st.transitions.values():
                for target in targets:
                    if target.id not in visited:
                        queue.append(target)

        return result


def epsilon_closure(states: set[NFAState]) -> set[NFAState]:
    """计算一组 NFA 状态的 ε-闭包（通过 ε 转移可达的所有状态）"""
    closure = set(states)
    stack = list(states)

    while stack:
        st = stack.pop()
        if EPSILON in st.transitions:
            for next_st in st.transitions[EPSILON]:
                if next_st not in closure:
                    closure.add(next_st)
                    stack.append(next_st)

    return closure


def nfa_move(states: set[NFAState], symbol: str) -> set[NFAState]:
    """从一组 NFA 状态通过符号 symbol 转移一步"""
    result: set[NFAState] = set()
    for st in states:
        if symbol in st.transitions:
            result.update(st.transitions[symbol])
    return result
