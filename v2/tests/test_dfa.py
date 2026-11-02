"""DFA 子集构造与 Hopcroft 最小化测试。"""

from __future__ import annotations

import unittest

from regex_compiler.backend.dfa import build_dfa, simulate_dfa
from regex_compiler.backend.minimize import minimize_dfa, simulate_min_dfa
from regex_compiler.backend.nfa import ThompsonBuilder
from regex_compiler.charset import build_alphabet
from regex_compiler.frontend.ast_nodes import collect_charsets
from regex_compiler.frontend.parser import parse


def _build_dfa(pattern: str):
    """构造指定模式的 DFA。"""
    ast = parse(pattern)
    alphabet = build_alphabet(collect_charsets(ast))
    nfa = ThompsonBuilder().build(ast)
    return build_dfa(nfa, alphabet)


def _build_min_dfa(pattern: str):
    """构造指定模式的最小化 DFA。"""
    return minimize_dfa(_build_dfa(pattern))


class TestDFAConstruction(unittest.TestCase):
    """子集构造的正确性。"""

    def test_single_char(self) -> None:
        dfa = _build_dfa("a")
        self.assertEqual(len(dfa.states), 2)
        self.assertTrue(dfa.start.transitions[dfa.alphabet.block_of("a")].is_final)

    def test_concat(self) -> None:
        self.assertGreaterEqual(len(_build_dfa("ab").states), 2)

    def test_union(self) -> None:
        self.assertGreaterEqual(len(_build_dfa("a|b").states), 2)

    def test_star(self) -> None:
        self.assertTrue(_build_dfa("a*").start.is_final)

    def test_simulate_accept(self) -> None:
        self.assertTrue(simulate_dfa(_build_dfa("abc"), "abc")[0])

    def test_simulate_reject(self) -> None:
        self.assertFalse(simulate_dfa(_build_dfa("abc"), "abd")[0])

    def test_simulate_star(self) -> None:
        dfa = _build_dfa("a*")
        self.assertTrue(simulate_dfa(dfa, "")[0])
        self.assertTrue(simulate_dfa(dfa, "a")[0])
        self.assertTrue(simulate_dfa(dfa, "aaa")[0])
        self.assertFalse(simulate_dfa(dfa, "b")[0])

    def test_simulate_union_star(self) -> None:
        dfa = _build_dfa("(a|b)*")
        self.assertTrue(simulate_dfa(dfa, "abab")[0])
        self.assertFalse(simulate_dfa(dfa, "abca")[0])

    def test_classic_example(self) -> None:
        dfa = _build_dfa("(a|b)*abb")
        self.assertTrue(simulate_dfa(dfa, "abb")[0])
        self.assertTrue(simulate_dfa(dfa, "aabb")[0])
        self.assertTrue(simulate_dfa(dfa, "babb")[0])
        self.assertTrue(simulate_dfa(dfa, "ababb")[0])
        self.assertFalse(simulate_dfa(dfa, "aba")[0])
        self.assertFalse(simulate_dfa(dfa, "abba")[0])

    def test_determinism(self) -> None:
        """DFA 中每个状态对每个字符块至多一条出边 —— 这是 DFA 的定义要求。"""
        dfa = _build_dfa("(a|b)*abb")
        for state in dfa.states:
            self.assertLessEqual(
                len(state.transitions),
                len(dfa.alphabet.covered_ids),
                "存在状态拥有超出字母表大小的出边",
            )


class TestMinimize(unittest.TestCase):
    """Hopcroft 最小化的正确性。"""

    def test_star_no_reduction(self) -> None:
        """``a*`` 的最小 DFA 只有一个状态。"""
        self.assertEqual(len(_build_min_dfa("a*").states), 1)

    def test_single_char(self) -> None:
        self.assertEqual(len(_build_min_dfa("a").states), 2)

    def test_classic_reduction(self) -> None:
        min_dfa = _build_min_dfa("(a|b)*abb")
        self.assertLessEqual(len(min_dfa.states), len(_build_dfa("(a|b)*abb").states))

    def test_minimized_is_not_larger(self) -> None:
        """最小化不应增加状态数。"""
        for pattern in ["a", "ab", "a|b", "a*", "(a|b)*abb", "a(b|c)*d", "[a-z]+"]:
            with self.subTest(pattern=pattern):
                dfa = _build_dfa(pattern)
                min_dfa = minimize_dfa(dfa)
                self.assertLessEqual(len(min_dfa.states), len(dfa.states))

    def test_preserves_acceptance(self) -> None:
        """最小化前后接受的语言必须完全一致。"""
        cases = [
            ("a", [("a", True), ("b", False), ("", False)]),
            ("a*", [("", True), ("a", True), ("aaa", True), ("b", False)]),
            ("a|b", [("a", True), ("b", True), ("c", False)]),
            ("ab", [("ab", True), ("a", False), ("b", False), ("abc", False)]),
            (
                "(a|b)*abb",
                [
                    ("abb", True),
                    ("aabb", True),
                    ("ababb", True),
                    ("aba", False),
                    ("abba", False),
                ],
            ),
        ]
        for pattern, expectations in cases:
            dfa = _build_dfa(pattern)
            min_dfa = minimize_dfa(dfa)
            for text, expected in expectations:
                with self.subTest(pattern=pattern, text=text):
                    dfa_result = simulate_dfa(dfa, text)[0]
                    min_result = simulate_min_dfa(min_dfa, text)[0]
                    self.assertEqual(dfa_result, expected)
                    self.assertEqual(min_result, expected)

    def test_distinguishable_states_kept(self) -> None:
        """``a|ab`` 的两个终态可区分（继续读 b 的结果不同），不应被合并。"""
        dfa = _build_dfa("a|ab")
        min_dfa = minimize_dfa(dfa)
        # q1 接受 "a"，q2 接受 "ab"；从 q1 读 b 可达终态，从 q2 读 b 则拒绝
        self.assertEqual(len(min_dfa.states), 3)

    def test_equivalent_states_merged(self) -> None:
        """存在等价状态时最小化必须发生合并。"""
        dfa = _build_dfa("(a|b)*abb")
        min_dfa = minimize_dfa(dfa)
        self.assertLess(len(min_dfa.states), len(dfa.states))


if __name__ == "__main__":
    unittest.main()
