"""编译器后端 —— NFA 构造、DFA 子集构造与 Hopcroft 最小化。"""

from __future__ import annotations

from .dfa import DFA, DFAState, build_dfa, simulate_dfa
from .minimize import MinDFA, MinDFAState, minimize_dfa, simulate_min_dfa
from .nfa import NFA, NFAState, ThompsonBuilder, epsilon_closure, nfa_move

__all__ = [
    "DFA",
    "DFAState",
    "MinDFA",
    "MinDFAState",
    "NFA",
    "NFAState",
    "ThompsonBuilder",
    "build_dfa",
    "epsilon_closure",
    "minimize_dfa",
    "nfa_move",
    "simulate_dfa",
    "simulate_min_dfa",
]
