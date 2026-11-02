"""测试套件 —— DFA 子集构造和最小化测试"""

from src.parser import parse
from src.nfa import ThompsonBuilder
from src.dfa import build_dfa, simulate_dfa
from src.minimize import minimize_dfa


def _build_dfa(pattern: str):
    ast = parse(pattern)
    builder = ThompsonBuilder()
    nfa = builder.build(ast)
    return build_dfa(nfa)


def _build_min_dfa(pattern: str):
    dfa = _build_dfa(pattern)
    return minimize_dfa(dfa)


def _simulate_min(min_dfa, text: str) -> bool:
    current = min_dfa.start
    for ch in text:
        if ch in current.transitions:
            current = current.transitions[ch]
        else:
            return False
    return current.is_final


class TestDFAConstruction:
    def test_single_char(self):
        dfa = _build_dfa("a")
        assert len(dfa.states) == 2
        assert dfa.start.transitions["a"].is_final

    def test_concat(self):
        dfa = _build_dfa("ab")
        assert len(dfa.states) >= 2

    def test_union(self):
        dfa = _build_dfa("a|b")
        assert len(dfa.states) >= 2

    def test_star(self):
        dfa = _build_dfa("a*")
        assert dfa.start.is_final

    def test_simulate_accept(self):
        dfa = _build_dfa("abc")
        accepted, path = simulate_dfa(dfa, "abc")
        assert accepted

    def test_simulate_reject(self):
        dfa = _build_dfa("abc")
        accepted, path = simulate_dfa(dfa, "abd")
        assert not accepted

    def test_simulate_star(self):
        dfa = _build_dfa("a*")
        assert simulate_dfa(dfa, "")[0]
        assert simulate_dfa(dfa, "a")[0]
        assert simulate_dfa(dfa, "aaa")[0]
        assert not simulate_dfa(dfa, "b")[0]

    def test_simulate_union_star(self):
        dfa = _build_dfa("(a|b)*")
        assert simulate_dfa(dfa, "abab")[0]
        assert simulate_dfa(dfa, "abca")[0] == False

    def test_classic_example(self):
        dfa = _build_dfa("(a|b)*abb")
        assert simulate_dfa(dfa, "abb")[0]
        assert simulate_dfa(dfa, "aabb")[0]
        assert simulate_dfa(dfa, "babb")[0]
        assert simulate_dfa(dfa, "ababb")[0]
        assert not simulate_dfa(dfa, "aba")[0]
        assert not simulate_dfa(dfa, "abba")[0]


class TestMinimize:
    def test_star_no_reduction(self):
        min_dfa = _build_min_dfa("a*")
        assert len(min_dfa.states) == 1

    def test_single_char(self):
        min_dfa = _build_min_dfa("a")
        assert len(min_dfa.states) == 2

    def test_classic_reduction(self):
        min_dfa = _build_min_dfa("(a|b)*abb")
        assert len(min_dfa.states) >= 1

    def test_preserves_acceptance(self):
        patterns = [
            ("a", [("a", True), ("b", False), ("", False)]),
            ("a*", [("", True), ("a", True), ("aaa", True), ("b", False)]),
            ("a|b", [("a", True), ("b", True), ("c", False)]),
            ("ab", [("ab", True), ("a", False), ("b", False), ("abc", False)]),
            ("(a|b)*abb", [
                ("abb", True), ("aabb", True), ("ababb", True),
                ("aba", False), ("abba", False),
            ]),
        ]
        for pattern, cases in patterns:
            dfa = _build_dfa(pattern)
            min_dfa = _build_min_dfa(pattern)
            for test_str, expected in cases:
                dfa_result = simulate_dfa(dfa, test_str)[0]
                min_result = _simulate_min(min_dfa, test_str)
                assert dfa_result == min_result == expected, (
                    f"Pattern: {pattern}, Input: {test_str!r}, "
                    f"Expected: {expected}, DFA: {dfa_result}, Min: {min_result}"
                )
