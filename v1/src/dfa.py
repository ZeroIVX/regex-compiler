"""DFA 构造 —— 子集构造法从 NFA 转换为 DFA

DFA 特点：
- 无 ε 转移
- 每个符号有唯一确定的下一状态
- 状态数是 NFA 状态子集的数量（最坏 O(2^n)）
"""

from __future__ import annotations
from dataclasses import dataclass, field

from .nfa import NFA, NFAState, epsilon_closure, nfa_move, EPSILON


@dataclass
class DFAState:
    """DFA 状态"""
    id: int
    nfa_states: frozenset[NFAState]  # 对应的 NFA 状态子集
    is_final: bool = False
    transitions: dict[str, DFAState] = field(default_factory=dict)

    def __repr__(self):
        nfa_ids = sorted(st.id for st in self.nfa_states)
        return f"DFAState(id={self.id}, nfa={nfa_ids}, final={self.is_final})"

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if not isinstance(other, DFAState):
            return False
        return self.id == other.id


@dataclass
class DFA:
    """完整的 DFA"""
    start: DFAState
    states: list[DFAState]
    alphabet: set[str]

    def __repr__(self):
        return f"DFA(states={len(self.states)}, alphabet={sorted(self.alphabet)})"


def _frozenset_id(d: dict[frozenset[int], DFAState]) -> dict[int, DFAState]:
    """convenience: 用 NFA id frozenset 查找"""
    return {frozenset(st.id for st in k): v for k, v in d.items()}


def build_dfa(nfa: NFA) -> DFA:
    """子集构造法：将 NFA 转换为 DFA

    算法：
    1. 计算 start 的 ε-闭包作为 DFA 起始状态
    2. 对每个未标记的 DFA 状态和每个输入符号：
       a. 计算 move(symbol) 后取 ε-闭包
       b. 若结果子集对应新的 DFA 状态则创建
       c. 添加转移边
    3. 包含 NFA 终态的 DFA 状态标记为终态
    """
    start_closure = epsilon_closure({nfa.start})

    # frozenset 到 DFAState 的映射
    subset_to_state: dict[frozenset[NFAState], DFAState] = {}
    all_states: list[DFAState] = []
    next_id = 0

    # 起始状态
    start_dfa = DFAState(
        id=next_id,
        nfa_states=frozenset(start_closure),
        is_final=any(s.is_final for s in start_closure),
    )
    next_id += 1
    subset_to_state[frozenset(start_closure)] = start_dfa
    all_states.append(start_dfa)

    # 收集字母表：所有出现过的具体字符
    alphabet = set(nfa.alphabet)

    # 使用列表模拟队列
    queue = [start_dfa]
    while queue:
        current = queue.pop(0)
        for symbol in alphabet:
            # move + ε-闭包
            targets = nfa_move(current.nfa_states, symbol)
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

            current.transitions[symbol] = subset_to_state[closure_fset]

    return DFA(start=start_dfa, states=all_states, alphabet=alphabet)


def simulate_dfa(dfa: DFA, text: str) -> tuple[bool, list[DFAState]]:
    """在 DFA 上模拟匹配过程，返回是否接受和经过的状态序列"""
    current = dfa.start
    path = [current]

    for ch in text:
        if ch in current.transitions:
            current = current.transitions[ch]
            path.append(current)
        else:
            # 无可用转移，提前失败
            return False, path

    return current.is_final, path
