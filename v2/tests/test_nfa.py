"""NFA 构造测试（Thompson 算法）。"""

from __future__ import annotations

import unittest

from regex_compiler.backend.nfa import (
    EPSILON,
    NFAState,
    ThompsonBuilder,
    epsilon_closure,
)
from regex_compiler.charset import CharClass
from regex_compiler.frontend.parser import parse


def _build(pattern: str):
    """构造指定模式的 NFA。"""
    return ThompsonBuilder().build(parse(pattern))


class TestThompson(unittest.TestCase):
    """各运算符对应的 NFA 子图。"""

    def test_single_char(self) -> None:
        nfa = _build("a")
        self.assertEqual(len(nfa.states), 2)
        charset = next(iter(nfa.start.transitions))
        self.assertEqual(charset.chars, frozenset("a"))
        self.assertIn(nfa.accept, nfa.start.transitions[charset])

    def test_concat(self) -> None:
        nfa = _build("ab")
        self.assertGreaterEqual(len(nfa.states), 3)
        self.assertIn(EPSILON, nfa.states[1].transitions)

    def test_union(self) -> None:
        nfa = _build("a|b")
        self.assertGreaterEqual(len(nfa.states), 4)

    def test_star(self) -> None:
        nfa = _build("a*")
        self.assertGreaterEqual(len(nfa.states), 3)

    def test_plus(self) -> None:
        """正闭包必须至少匹配一次 —— 存在非 ε 的出边。"""
        nfa = _build("a+")
        has_char_edge = any(
            charset is not None
            for state in nfa.states
            for charset in state.transitions
        )
        self.assertTrue(has_char_edge)

    def test_question(self) -> None:
        nfa = _build("a?")
        self.assertGreaterEqual(len(nfa.states), 3)

    def test_single_accept_state(self) -> None:
        """整个 NFA 只有一个终态。"""
        nfa = _build("(a|b)*abb")
        finals = [s for s in nfa.states if s.is_final]
        self.assertEqual(len(finals), 1)

    def test_complex_pattern(self) -> None:
        nfa = _build("(a|b)*abb")
        self.assertGreater(len(nfa.states), 0)
        self.assertGreaterEqual(len(nfa.alphabet), 2)

    def test_char_class_single_edge(self) -> None:
        """字符类在 NFA 中只产生一条边，而不是展开成多个字符。"""
        nfa = _build("[a-z]")
        char_edges = [
            charset
            for state in nfa.states
            for charset in state.transitions
            if charset is not None
        ]
        self.assertEqual(len(char_edges), 1)
        self.assertEqual(char_edges[0].chars, frozenset("abcdefghijklmnopqrstuvwxyz"))


class TestEpsilonClosure(unittest.TestCase):
    """ε-闭包计算。"""

    def test_closure_simple(self) -> None:
        s0 = NFAState(id=0)
        s1 = NFAState(id=1)
        s2 = NFAState(id=2)
        s0.add_transition(EPSILON, s1)
        s1.add_transition(EPSILON, s2)
        s2.add_transition(CharClass(frozenset({"a"})), s0)

        closure = epsilon_closure({s0})
        self.assertIn(s0, closure)
        self.assertIn(s1, closure)
        self.assertIn(s2, closure)

    def test_closure_excludes_char_edges(self) -> None:
        """字符边不能被 ε-闭包穿越。"""
        s0 = NFAState(id=0)
        s1 = NFAState(id=1)
        s0.add_transition(CharClass(frozenset({"a"})), s1)

        closure = epsilon_closure({s0})
        self.assertIn(s0, closure)
        self.assertNotIn(s1, closure)

    def test_closure_of_empty(self) -> None:
        self.assertEqual(epsilon_closure(set()), set())


if __name__ == "__main__":
    unittest.main()
