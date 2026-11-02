"""测试套件 —— NFA Thompson 构造测试"""

from src.parser import parse
from src.nfa import ThompsonBuilder, epsilon_closure, nfa_move, NFAState


class TestThompson:
    def test_single_char(self):
        ast = parse("a")
        builder = ThompsonBuilder()
        nfa = builder.build(ast)
        assert len(nfa.states) == 2
        assert nfa.accept in nfa.start.transitions.get("a", set())

    def test_concat(self):
        ast = parse("ab")
        builder = ThompsonBuilder()
        nfa = builder.build(ast)
        assert len(nfa.states) >= 3

    def test_union(self):
        ast = parse("a|b")
        builder = ThompsonBuilder()
        nfa = builder.build(ast)
        assert len(nfa.states) >= 4

    def test_star(self):
        ast = parse("a*")
        builder = ThompsonBuilder()
        nfa = builder.build(ast)
        assert len(nfa.states) >= 3

    def test_epsilon_closure_simple(self):
        """ε-闭包：从单一状态出发"""
        s0 = NFAState(id=0)
        s1 = NFAState(id=1)
        s2 = NFAState(id=2)
        s0.add_transition(None, s1)
        s1.add_transition(None, s2)
        s2.add_transition("a", s0)

        closure = epsilon_closure({s0})
        assert s0 in closure
        assert s1 in closure
        assert s2 in closure

    def test_nfa_move_basic(self):
        s0 = NFAState(id=0)
        s1 = NFAState(id=1)
        s2 = NFAState(id=2)
        s0.add_transition("a", s1)
        s0.add_transition("a", s2)

        result = nfa_move({s0}, "a")
        assert s1 in result
        assert s2 in result

    def test_nfa_move_no_transition(self):
        s0 = NFAState(id=0)
        target = NFAState(id=1)
        s0.add_transition("a", target)
        result = nfa_move({s0}, "b")
        assert len(result) == 0

    def test_alphabet_collection(self):
        ast = parse("a|b")
        builder = ThompsonBuilder()
        nfa = builder.build(ast)
        assert "a" in nfa.alphabet
        assert "b" in nfa.alphabet

    def test_complex_pattern(self):
        ast = parse("(a|b)*abb")
        builder = ThompsonBuilder()
        nfa = builder.build(ast)
        assert len(nfa.states) > 0
        assert len(nfa.alphabet) >= 2
