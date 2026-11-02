"""DFA 构造 —— 子集构造法从 NFA 转换为 DFA。

DFA 特点：

- 无 ε 转移
- 每个符号有唯一确定的下一状态
- 状态数是 NFA 状态子集的数量（最坏 O(2^n)）

本实现的关键点：转移标签是 :class:`~regex_compiler.charset.Alphabet` 中的
**互不相交字符块**，而不是单个字符。这保证了 DFA 的确定性 ——
即使模式同时包含 ``a`` 与 ``[a-z]``，同一个输入字符也只会命中一条转移。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..charset import Alphabet
from ..frontend.ast_nodes import ASTNode
from .nfa import NFA, NFAState, epsilon_closure


@dataclass(eq=False)
class DFAState:
    """DFA 状态。

    Attributes:
        id: 状态编号。
        nfa_states: 对应的 NFA 状态子集。
        is_final: 是否为终态。
        transitions: 转移表，键为字符块 id，值为目标状态。
    """

    id: int
    nfa_states: frozenset[NFAState]
    is_final: bool = False
    transitions: dict[int, DFAState] = field(default_factory=dict)

    def __repr__(self) -> str:
        nfa_ids = sorted(st.id for st in self.nfa_states)
        return f"DFAState(id={self.id}, nfa={nfa_ids}, final={self.is_final})"

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DFAState):
            return NotImplemented
        return self.id == other.id


@dataclass
class DFA:
    """完整的 DFA。"""

    start: DFAState
    states: list[DFAState]
    alphabet: Alphabet

    def __repr__(self) -> str:
        return (
            f"DFA(states={len(self.states)}, "
            f"alphabet={len(self.alphabet.covered_ids)})"
        )


def build_dfa(nfa: NFA, alphabet: Alphabet) -> DFA:
    """子集构造法：将 NFA 转换为 DFA。

    算法步骤：

    1. 计算 start 的 ε-闭包作为 DFA 起始状态
    2. 对每个未标记的 DFA 状态和每个字符块：
       a. 计算 move(块) 后取 ε-闭包
       b. 若结果子集对应新的 DFA 状态则创建
       c. 添加转移边
    3. 包含 NFA 终态的 DFA 状态标记为终态
    """
    start_closure = epsilon_closure({nfa.start})

    subset_to_state: dict[frozenset[NFAState], DFAState] = {}
    all_states: list[DFAState] = []
    next_id = 0

    start_dfa = DFAState(
        id=next_id,
        nfa_states=frozenset(start_closure),
        is_final=any(s.is_final for s in start_closure),
    )
    next_id += 1
    subset_to_state[frozenset(start_closure)] = start_dfa
    all_states.append(start_dfa)

    # 只遍历被覆盖的字符块 —— 未覆盖的块没有任何转移边，跳过即可
    covered_blocks = alphabet.covered_blocks

    queue = [start_dfa]
    while queue:
        current = queue.pop(0)
        for block in covered_blocks:
            targets = _move(current.nfa_states, block.sample)
            if not targets:
                continue
            closure = epsilon_closure(targets)
            if not closure:
                continue

            closure_fset = frozenset(closure)
            if closure_fset not in subset_to_state:
                new_state = DFAState(
                    id=next_id,
                    nfa_states=closure_fset,
                    is_final=any(s.is_final for s in closure),
                )
                next_id += 1
                subset_to_state[closure_fset] = new_state
                all_states.append(new_state)
                queue.append(new_state)

            current.transitions[block.id] = subset_to_state[closure_fset]

    return DFA(start=start_dfa, states=all_states, alphabet=alphabet)


def _move(states: frozenset[NFAState], symbol: str) -> set[NFAState]:
    """从一组 NFA 状态通过字符 ``symbol`` 转移一步。

    沿边移动的条件是：边的字符类 *包含* 该字符。
    由于字母表中的字符块是互不相交的完备划分，
    对同一个块而言命中哪些边是确定的。
    """
    result: set[NFAState] = set()
    for state in states:
        for edge_class, targets in state.transitions.items():
            if edge_class is None:
                continue
            if edge_class.contains(symbol):
                result.update(targets)
    return result


def simulate_dfa(dfa: DFA, text: str) -> tuple[bool, list[DFAState]]:
    """在 DFA 上模拟匹配过程，返回是否接受与经过的状态序列。

    输入字符先映射到所属字符块，再沿对应转移边前进；
    若该字符落在未被任何字符类覆盖的块上，则匹配立即失败。
    """
    current = dfa.start
    path = [current]

    for ch in text:
        block_id = dfa.alphabet.block_of(ch)
        if block_id is None or block_id not in current.transitions:
            return False, path
        current = current.transitions[block_id]
        path.append(current)

    return current.is_final, path


def build_dfa_from_ast(ast: ASTNode, alphabet: Alphabet) -> DFA:
    """便捷函数：从 AST 直接构造 DFA。

    等价于「构造 NFA 后再做子集构造」，供只想拿到 DFA 的调用方使用。
    """
    from .nfa import ThompsonBuilder

    nfa = ThompsonBuilder().build(ast)
    return build_dfa(nfa, alphabet)


__all__ = ["DFA", "DFAState", "build_dfa", "build_dfa_from_ast", "simulate_dfa"]
