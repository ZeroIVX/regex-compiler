"""DFA 最小化 —— 划分精炼算法（Moore 式）

将 DFA 最小化，合并等价状态。

算法流程：
1. 初始划分 P = {F, Q-F}（终态集合, 非终态集合）
2. 重复精炼：
   - 对每个组 G ∈ P，按"对每个符号 a 转移到哪个组"划分 G
   - 若划分不再变化则停止
3. 每个组映射到最小化 DFA 的一个状态
4. 重建转移关系

实现说明：本版对每一轮精炼都重新扫描全部状态，属于 Moore 式划分精炼，
最坏复杂度约为 O(n²·k)。功能上与 Hopcroft 算法等价，但常数更大。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from .dfa import DFA, DFAState


@dataclass
class MinDFAState:
    """最小化 DFA 状态"""
    id: int
    original_ids: tuple[int, ...]  # 对应的原始 DFA 状态 ID
    is_final: bool = False
    transitions: dict[str, MinDFAState] = field(default_factory=dict)

    def __repr__(self):
        return f"MinDFAState(id={self.id}, orig={list(self.original_ids)}, final={self.is_final})"

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if not isinstance(other, MinDFAState):
            return False
        return self.id == other.id


@dataclass
class MinDFA:
    """最小化 DFA"""
    start: MinDFAState
    states: list[MinDFAState]
    alphabet: set[str]

    def __repr__(self):
        return f"MinDFA(states={len(self.states)})"


def _partition_refine(
    states: list[DFAState],
    alphabet: set[str],
    state_to_part: dict[DFAState, int],
    partitions: list[set[DFAState]],
) -> tuple[bool, dict[DFAState, int], list[set[DFAState]]]:
    """执行一轮划分精炼，返回 (是否有变化, 新映射, 新划分)"""
    changed = False
    new_partitions: list[set[DFAState]] = []
    new_part_map: dict[int, int] = {}

    for part_id, part in enumerate(partitions):
        if len(part) <= 1:
            # 单状态组无法再划分
            new_partitions.append(set(part))
            new_part_map[part_id] = len(new_partitions) - 1
            continue

        # 对组内状态按"转移行为"分组
        subgroups: dict[tuple, set[DFAState]] = {}
        for state in part:
            # 转移特征：对于每个符号，转移到哪个分区
            sig: list[tuple[str, int]] = []
            for sym in sorted(alphabet):
                if sym in state.transitions:
                    target_part = state_to_part[state.transitions[sym]]
                    sig.append((sym, target_part))
                else:
                    sig.append((sym, -1))  # 无转移
            sig_tuple = tuple(sig)

            if sig_tuple not in subgroups:
                subgroups[sig_tuple] = set()
            subgroups[sig_tuple].add(state)

        if len(subgroups) == 1:
            # 没有进一步划分
            new_partitions.append(set(part))
            new_part_map[part_id] = len(new_partitions) - 1
        else:
            changed = True
            for subgroup in subgroups.values():
                new_partitions.append(subgroup)
            new_part_map[part_id] = -1  # 原分区被拆散

    # 重建映射
    new_state_to_part: dict[DFAState, int] = {}
    for part_id, part in enumerate(new_partitions):
        for st in part:
            new_state_to_part[st] = part_id

    return changed, new_state_to_part, new_partitions


def minimize_dfa(dfa: DFA) -> MinDFA:
    """Hopcroft DFA 最小化算法

    简化版：使用基于划分精炼的算法。
    核心思想：不断按"对每个输入符号的转移目标分区"来划分状态组。
    """
    if not dfa.states:
        raise ValueError("Cannot minimize empty DFA")

    alphabet = dfa.alphabet
    states = dfa.states

    # 初始划分：终态 + 非终态
    final_states: set[DFAState] = set()
    non_final_states: set[DFAState] = set()
    for st in states:
        if st.is_final:
            final_states.add(st)
        else:
            non_final_states.add(st)

    partitions: list[set[DFAState]] = []
    if final_states:
        partitions.append(final_states)
    if non_final_states:
        partitions.append(non_final_states)

    # 建立状态到分区的映射
    state_to_part: dict[DFAState, int] = {}
    for part_id, part in enumerate(partitions):
        for st in part:
            state_to_part[st] = part_id

    # 迭代精炼
    while True:
        changed, state_to_part, partitions = _partition_refine(
            states, alphabet, state_to_part, partitions
        )
        if not changed:
            break

    # 将分区映射到最小化 DFA 状态
    partition_states: dict[int, MinDFAState] = {}
    state_to_min: dict[DFAState, MinDFAState] = {}
    min_states: list[MinDFAState] = []

    for part_id, part in enumerate(partitions):
        orig_ids = tuple(sorted(st.id for st in part))
        is_final = any(st.is_final for st in part)
        min_st = MinDFAState(
            id=part_id,
            original_ids=orig_ids,
            is_final=is_final,
        )
        min_states.append(min_st)
        partition_states[part_id] = min_st
        for st in part:
            state_to_min[st] = min_st

    # 重建转移关系
    for orig_st, min_st in state_to_min.items():
        for sym, target in orig_st.transitions.items():
            min_target = state_to_min[target]
            min_st.transitions[sym] = min_target

    # 起始状态
    start_min = state_to_min[dfa.start]

    return MinDFA(
        start=start_min,
        states=min_states,
        alphabet=alphabet,
    )
