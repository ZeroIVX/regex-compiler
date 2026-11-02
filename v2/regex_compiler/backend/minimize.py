"""DFA 最小化 —— Hopcroft 算法。

把 DFA 中行为等价的状态合并，得到状态数最少的等价 DFA。

算法流程
--------
1. **补全**：为 DFA 补上一个死状态（sink），使转移函数成为全函数。
   这一步是 Hopcroft 正确性的前提 —— 否则「没有转移」与「转移到非终态」
   会被错误地视为两种不同行为。
2. **初始划分** ``P = {F, Q\\F}``，即终态集合与非终态集合。
3. **反复精炼**：从工作队列 ``W`` 中取出划分块 ``A``，对每个符号 ``a``
   计算其原像 ``X = {q | δ(q, a) ∈ A}``；用 ``X`` 去切分所有划分块。
   切分时按 Hopcroft 的「小半边入队」优化保证 ``O(k·n·log n)`` 复杂度。
4. **重建**：每个划分块映射为最小 DFA 的一个状态，重新建立转移关系。
5. **剪枝**：删除从起始状态不可达的状态（例如上一步引入的死状态）。

实现要点：反向转移表（逆像索引）让 ``X`` 的计算无需扫描全图。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from ..charset import Alphabet
from .dfa import DFA, DFAState

SINK = -1  # 死状态的内部编号


@dataclass(eq=False)
class MinDFAState:
    """最小化 DFA 的状态。

    Attributes:
        id: 状态编号。
        original_ids: 该状态合并的原始 DFA 状态编号。
        is_final: 是否为终态。
        transitions: 转移表，键为字符块 id。
    """

    id: int
    original_ids: tuple[int, ...]
    is_final: bool = False
    transitions: dict[int, MinDFAState] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"MinDFAState(id={self.id}, orig={list(self.original_ids)}, "
            f"final={self.is_final})"
        )

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MinDFAState):
            return NotImplemented
        return self.id == other.id


@dataclass
class MinDFA:
    """最小化 DFA。"""

    start: MinDFAState
    states: list[MinDFAState]
    alphabet: Alphabet

    def __repr__(self) -> str:
        return f"MinDFA(states={len(self.states)})"


def minimize_dfa(dfa: DFA) -> MinDFA:
    """使用 Hopcroft 算法最小化 DFA。

    Args:
        dfa: 待最小化的 DFA。

    Returns:
        与 ``dfa`` 等价的最小 DFA。

    Raises:
        ValueError: 当传入的 DFA 没有状态时。
    """
    if not dfa.states:
        raise ValueError("无法最小化空的 DFA")

    symbols = list(dfa.alphabet.covered_ids)
    n_states = len(dfa.states)

    # ---- 1. 补全：构造全转移表，并加入死状态 ----
    # 补全后的状态编号：0..n_states-1 为原状态，n_states 为死状态
    total = n_states + 1
    sink_id = n_states

    # transitions[state_id][sym_index] -> target_id
    transitions: list[list[int]] = []
    for state in dfa.states:
        row: list[int] = []
        for block_id in symbols:
            target = state.transitions.get(block_id)
            row.append(target.id if target is not None else sink_id)
        transitions.append(row)

    # 死状态：非终态，所有转移指向自身
    transitions.append([sink_id] * len(symbols))

    is_final = [state.is_final for state in dfa.states] + [False]

    # ---- 2. 初始划分 ----
    final_set = frozenset(i for i in range(total) if is_final[i])
    non_final_set = frozenset(i for i in range(total) if not is_final[i])

    blocks: list[frozenset[int]] = []
    block_of: dict[int, int] = {}

    if final_set:
        _add_block(blocks, block_of, final_set)
    if non_final_set:
        _add_block(blocks, block_of, non_final_set)

    if len(blocks) <= 1:
        return _build_min_dfa(dfa, blocks, block_of, transitions, symbols, sink_id)

    # ---- 3. 反向转移表：用于快速计算原像 ----
    # inverse[sym_index][target_id] = {source_id, ...}
    inverse: list[dict[int, set[int]]] = []
    for sym_index in range(len(symbols)):
        table: dict[int, set[int]] = {}
        for source in range(total):
            table.setdefault(transitions[source][sym_index], set()).add(source)
        inverse.append(table)

    # 工作队列存放「划分块编号」，初始放入较小的那个块
    worklist: deque[int] = deque()
    in_worklist: set[int] = set()
    smaller = 0 if len(blocks[0]) <= len(blocks[1]) else 1
    worklist.append(smaller)
    in_worklist.add(smaller)

    while worklist:
        splitter_id = worklist.popleft()
        in_worklist.discard(splitter_id)
        if splitter_id >= len(blocks):
            continue
        splitter = blocks[splitter_id]

        for sym_index in range(len(symbols)):
            # 计算原像 X = {q | δ(q, sym) ∈ splitter}
            preimage: set[int] = set()
            table = inverse[sym_index]
            for target in splitter:
                preimage |= table.get(target, set())
            if not preimage:
                continue

            # 用 preimage 切分所有划分块
            for block_id in range(len(blocks) - 1, -1, -1):
                block = blocks[block_id]
                intersection = block & preimage
                if not intersection or len(intersection) == len(block):
                    continue

                difference = block - intersection
                blocks[block_id] = intersection
                blocks.append(difference)

                for state_id in intersection:
                    block_of[state_id] = block_id
                for state_id in difference:
                    block_of[state_id] = len(blocks) - 1

                if block_id in in_worklist:
                    # 原块已在队列中：两个子块都要入队
                    in_worklist.discard(block_id)
                    worklist.append(block_id)
                    in_worklist.add(block_id)
                    worklist.append(len(blocks) - 1)
                    in_worklist.add(len(blocks) - 1)
                else:
                    # 只把较小的子块入队（Hopcroft 的优化）
                    child = block_id if len(intersection) <= len(difference) else len(blocks) - 1
                    worklist.append(child)
                    in_worklist.add(child)

    # ---- 4 & 5. 重建最小 DFA 并剪除不可达状态 ----
    return _build_min_dfa(dfa, blocks, block_of, transitions, symbols, sink_id)


def _add_block(
    blocks: list[frozenset[int]],
    block_of: dict[int, int],
    members: frozenset[int],
) -> None:
    """把一个集合加入划分列表并更新状态到块编号的映射。"""
    block_id = len(blocks)
    blocks.append(members)
    for state_id in members:
        block_of[state_id] = block_id


def _build_min_dfa(
    dfa: DFA,
    blocks: list[frozenset[int]],
    block_of: dict[int, int],
    transitions: list[list[int]],
    symbols: list[int],
    sink_id: int,
) -> MinDFA:
    """把最终划分映射为最小 DFA 的状态，并剔除不可达状态。"""
    n_states = len(dfa.states)

    # 找出从起始状态可达的块
    start_state = dfa.start
    start_block = block_of[start_state.id]

    reachable: set[int] = set()
    queue = [start_block]
    while queue:
        block_id = queue.pop()
        if block_id in reachable:
            continue
        reachable.add(block_id)
        for member in blocks[block_id]:
            if member == sink_id:
                continue
            for sym_index, target_id in enumerate(transitions[member]):
                target_block = block_of[target_id]
                if target_block not in reachable:
                    queue.append(target_block)

    # 为可达块分配新的状态编号
    block_to_new_id: dict[int, int] = {}
    min_states: list[MinDFAState] = []
    for block_id in sorted(reachable):
        members = blocks[block_id]
        original_ids = tuple(sorted(m for m in members if m != sink_id))
        if not original_ids:
            continue
        new_state = MinDFAState(
            id=len(min_states),
            original_ids=original_ids,
            is_final=any(dfa.states[m].is_final for m in original_ids),
        )
        block_to_new_id[block_id] = new_state.id
        min_states.append(new_state)

    # 重建转移关系
    for block_id, new_id in block_to_new_id.items():
        members = blocks[block_id]
        source = min_states[new_id]
        for sym_index, block_key in enumerate(symbols):
            target_ids = {transitions[m][sym_index] for m in members}
            # 集合内所有成员的转移目标必须落在同一个块，否则划分不合法
            target_block = block_of[next(iter(target_ids))]
            target_new_id = block_to_new_id.get(target_block)
            if target_new_id is None:
                continue
            source.transitions[block_key] = min_states[target_new_id]

    start_new_id = block_to_new_id.get(start_block)
    if start_new_id is None:
        # 起始块里只有死状态，说明 DFA 无任何可接受状态
        start_new_id = 0
        if not min_states:
            min_states.append(MinDFAState(id=0, original_ids=(), is_final=False))

    return MinDFA(
        start=min_states[start_new_id],
        states=min_states,
        alphabet=dfa.alphabet,
    )


def simulate_min_dfa(min_dfa: MinDFA, text: str) -> tuple[bool, list[MinDFAState]]:
    """在最小 DFA 上模拟匹配过程。"""
    current = min_dfa.start
    path = [current]

    for ch in text:
        block_id = min_dfa.alphabet.block_of(ch)
        if block_id is None or block_id not in current.transitions:
            return False, path
        current = current.transitions[block_id]
        path.append(current)

    return current.is_final, path


__all__ = ["MinDFA", "MinDFAState", "minimize_dfa", "simulate_min_dfa"]
