"""匹配器集成测试。"""

from __future__ import annotations

import unittest

from regex_compiler import RegexMatcher
from regex_compiler.errors import LexerError, ParserError


class TestRegexMatcher(unittest.TestCase):
    """完整匹配语义。"""

    def test_match_single_char(self) -> None:
        matcher = RegexMatcher("a")
        self.assertTrue(matcher.match("a"))
        self.assertFalse(matcher.match("b"))
        self.assertFalse(matcher.match("aa"))

    def test_match_concat(self) -> None:
        matcher = RegexMatcher("abc")
        self.assertTrue(matcher.match("abc"))
        self.assertFalse(matcher.match("ab"))
        self.assertFalse(matcher.match("abcd"))
        self.assertFalse(matcher.match("abd"))

    def test_match_union(self) -> None:
        matcher = RegexMatcher("a|b")
        self.assertTrue(matcher.match("a"))
        self.assertTrue(matcher.match("b"))
        self.assertFalse(matcher.match("c"))
        self.assertFalse(matcher.match("ab"))

    def test_match_star(self) -> None:
        matcher = RegexMatcher("a*")
        self.assertTrue(matcher.match(""))
        self.assertTrue(matcher.match("a"))
        self.assertTrue(matcher.match("aaa"))
        self.assertFalse(matcher.match("b"))
        self.assertFalse(matcher.match("aab"))

    def test_match_plus(self) -> None:
        matcher = RegexMatcher("a+")
        self.assertFalse(matcher.match(""))
        self.assertTrue(matcher.match("a"))
        self.assertTrue(matcher.match("aaa"))
        self.assertFalse(matcher.match("b"))

    def test_match_question(self) -> None:
        matcher = RegexMatcher("a?")
        self.assertTrue(matcher.match(""))
        self.assertTrue(matcher.match("a"))
        self.assertFalse(matcher.match("aa"))
        self.assertFalse(matcher.match("b"))

    def test_match_complex(self) -> None:
        matcher = RegexMatcher("a(b|c)*d")
        self.assertTrue(matcher.match("ad"))
        self.assertTrue(matcher.match("abd"))
        self.assertTrue(matcher.match("acd"))
        self.assertTrue(matcher.match("abcd"))
        self.assertTrue(matcher.match("abcbcd"))
        self.assertFalse(matcher.match("a"))
        self.assertFalse(matcher.match("abc"))

    def test_match_classic(self) -> None:
        matcher = RegexMatcher("(a|b)*abb")
        self.assertTrue(matcher.match("abb"))
        self.assertTrue(matcher.match("aabb"))
        self.assertTrue(matcher.match("babb"))
        self.assertTrue(matcher.match("ababb"))
        self.assertFalse(matcher.match("aba"))
        self.assertFalse(matcher.match("abba"))
        self.assertFalse(matcher.match("bbab"))

    def test_match_nested(self) -> None:
        matcher = RegexMatcher("((a|b)*c)*")
        self.assertTrue(matcher.match(""))
        self.assertTrue(matcher.match("c"))
        self.assertTrue(matcher.match("ac"))
        self.assertTrue(matcher.match("bc"))
        self.assertTrue(matcher.match("acbc"))
        self.assertTrue(matcher.match("aabbcc"))

    def test_match_with_escape(self) -> None:
        matcher = RegexMatcher(r"a\*b")
        self.assertTrue(matcher.match("a*b"))
        self.assertFalse(matcher.match("ab"))
        self.assertFalse(matcher.match("aaab"))

    def test_match_long_string(self) -> None:
        matcher = RegexMatcher("a+b+c+")
        self.assertTrue(matcher.match("abc"))
        self.assertTrue(matcher.match("aaabbbccc"))
        self.assertFalse(matcher.match("cba"))


class TestWildcardAndCharClass(unittest.TestCase):
    """通配符与字符类 —— 这两处在旧实现中语义失效，属于重点回归项。"""

    def test_dot_matches_any_char(self) -> None:
        matcher = RegexMatcher(".")
        self.assertTrue(matcher.match("x"))
        self.assertTrue(matcher.match("5"))
        self.assertTrue(matcher.match("A"))

    def test_dot_requires_exactly_one_char(self) -> None:
        matcher = RegexMatcher(".")
        self.assertFalse(matcher.match(""))
        self.assertFalse(matcher.match("ab"))

    def test_dot_excludes_newline(self) -> None:
        """``.`` 不匹配换行符，与 Python ``re`` 语义一致。"""
        self.assertFalse(RegexMatcher(".").match("\n"))

    def test_dot_in_sequence(self) -> None:
        matcher = RegexMatcher("a.b")
        self.assertTrue(matcher.match("axb"))
        self.assertTrue(matcher.match("a b"))
        self.assertFalse(matcher.match("ab"))
        self.assertFalse(matcher.match("axxb"))

    def test_negated_class(self) -> None:
        """``[^a-z]`` 匹配非小写字母，而不是反过来。"""
        matcher = RegexMatcher("[^a-z]")
        self.assertTrue(matcher.match("5"))
        self.assertTrue(matcher.match("A"))
        self.assertFalse(matcher.match("a"))
        self.assertFalse(matcher.match("z"))

    def test_positive_class(self) -> None:
        matcher = RegexMatcher("[a-z]")
        self.assertTrue(matcher.match("b"))
        self.assertTrue(matcher.match("a"))
        self.assertFalse(matcher.match("B"))
        self.assertFalse(matcher.match("5"))

    def test_class_range(self) -> None:
        matcher = RegexMatcher("[a-c]+")
        self.assertTrue(matcher.match("abc"))
        self.assertTrue(matcher.match("cba"))
        self.assertFalse(matcher.match("d"))
        self.assertFalse(matcher.match("abcd"))

    def test_class_with_negation_and_literal(self) -> None:
        matcher = RegexMatcher("[^a-z]a")
        self.assertTrue(matcher.match("5a"))
        self.assertFalse(matcher.match("aa"))

    def test_overlapping_classes_are_deterministic(self) -> None:
        """``a|[a-z]`` 存在重叠，DFA 必须保持确定性。"""
        matcher = RegexMatcher("a|[a-z]")
        self.assertTrue(matcher.match("a"))
        self.assertTrue(matcher.match("b"))
        self.assertFalse(matcher.match("ab"))


class TestSearch(unittest.TestCase):
    """搜索匹配。"""

    def test_search_simple(self) -> None:
        self.assertEqual(RegexMatcher("ab").search("xxabxx"), (2, 4))

    def test_search_not_found(self) -> None:
        self.assertIsNone(RegexMatcher("ab").search("aaaa"))

    def test_search_at_start(self) -> None:
        self.assertEqual(RegexMatcher("ab").search("abxx"), (0, 2))

    def test_search_at_end(self) -> None:
        self.assertEqual(RegexMatcher("ab").search("xxab"), (2, 4))

    def test_search_longest_at_leftmost(self) -> None:
        """最左最长语义：``a|ab`` 在 ``ab`` 上应匹配整个 ``ab``。"""
        self.assertEqual(RegexMatcher("a|ab").search("xab"), (1, 3))


class TestFindAll(unittest.TestCase):
    """查找全部匹配。"""

    def test_findall_simple(self) -> None:
        self.assertEqual(len(RegexMatcher("ab").findall("ababab")), 3)

    def test_findall_aa(self) -> None:
        self.assertEqual(len(RegexMatcher("aa").findall("aaaa")), 2)

    def test_findall_none(self) -> None:
        self.assertEqual(len(RegexMatcher("ab").findall("cccc")), 0)

    def test_findall_returns_substrings(self) -> None:
        """返回的第三个元素应为实际匹配到的子串。"""
        results = RegexMatcher("a+").findall("baaacaaa")
        self.assertEqual([r[2] for r in results], ["aaa", "aaa"])
        self.assertEqual([(r[0], r[1]) for r in results], [(1, 4), (5, 8)])


class TestEdgeCases(unittest.TestCase):
    """边界情况。"""

    def test_empty_pattern(self) -> None:
        self.assertTrue(RegexMatcher("").match(""))

    def test_special_chars(self) -> None:
        self.assertTrue(RegexMatcher(r"a\|b").match("a|b"))

    def test_long_pattern(self) -> None:
        matcher = RegexMatcher("a" * 10)
        self.assertTrue(matcher.match("a" * 10))
        self.assertFalse(matcher.match("a" * 9))

    def test_unicode_input(self) -> None:
        """非 ASCII 字符不应导致崩溃。"""
        matcher = RegexMatcher(".")
        self.assertTrue(matcher.match("中"))


class TestPipelineInfo(unittest.TestCase):
    """流水线信息输出。"""

    def test_info_output(self) -> None:
        info = RegexMatcher("(a|b)*abb").print_info()
        self.assertIn("Pattern:", info)
        self.assertIn("NFA States:", info)
        self.assertIn("DFA States:", info)
        self.assertIn("Min DFA States:", info)

    def test_error_types(self) -> None:
        with self.assertRaises(LexerError):
            RegexMatcher("[abc")
        with self.assertRaises(ParserError):
            RegexMatcher("(a")

    def test_simulate_steps(self) -> None:
        steps = RegexMatcher("ab").simulate("ab")
        self.assertEqual(len(steps), 3)
        self.assertTrue(steps[-1]["accepted"])

    def test_simulate_error_step(self) -> None:
        steps = RegexMatcher("ab").simulate("ax")
        self.assertTrue(steps[-1].get("error"))


if __name__ == "__main__":
    unittest.main()
