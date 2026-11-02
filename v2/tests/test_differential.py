"""差分测试 —— 与 Python 标准库 ``re`` 模块逐一对拍。

这是验证编译器正确性最有力的手段：本项目的语义目标就是与 ``re`` 一致，
因此凡是 ``re`` 支持而本项目也支持的语法，其匹配结果必须完全相同。

覆盖的语法子集：
    字面字符、``.``、``[a-z]``、``[^a-z]``、``( )``、``|``、``*``、``+``、``?``、``\\`` 转义
"""

from __future__ import annotations

import itertools
import re
import unittest

from regex_compiler import RegexMatcher

# 本项目支持的模式 —— 全部是 ``re`` 的合法子集
PATTERNS = [
    "a",
    "ab",
    "abc",
    "a|b",
    "a|bc",
    "ab|c",
    "a*",
    "a+",
    "a?",
    "a*b",
    "a+b",
    "a?b",
    "(a|b)*",
    "(a|b)*abb",
    "a(b|c)*d",
    "((a|b)*c)*",
    "a+b+c+",
    "[a-z]",
    "[a-z]+",
    "[abc]",
    "[a-c]+",
    "[a-z0-9]",
    "[^a-z]",
    "[^a-z]+",
    "[^abc]",
    ".",
    ".*",
    ".+",
    "a.b",
    "(ab)+",
    "(a|b)+c",
    "a(bc)*d",
    r"a\*b",
    r"a\|b",
    "[a-z]*[0-9]",
]

# 测试用字符串集合
TEXTS = [
    "",
    "a",
    "b",
    "ab",
    "ba",
    "aa",
    "aaa",
    "abc",
    "abb",
    "ababb",
    "aabb",
    "babb",
    "ababa",
    "abcabc",
    "acbc",
    "acbcbcd",
    "aabbcc",
    "aaabbbccc",
    "xyz",
    "123",
    "a1b2",
    "a*b",
    "a|b",
    "hello world",
    "The quick brown fox",
    "2026-10-28",
    "AbC123",
]


class TestDifferentialAgainstRe(unittest.TestCase):
    """逐对比较本项目与 ``re`` 的完整匹配结果。"""

    def test_full_match_equivalence(self) -> None:
        """``match()`` 必须与 ``re.fullmatch()`` 结果一致。"""
        mismatches: list[str] = []

        for pattern in PATTERNS:
            matcher = RegexMatcher(pattern)
            compiled = re.compile(pattern)
            for text in TEXTS:
                ours = matcher.match(text)
                theirs = compiled.fullmatch(text) is not None
                if ours != theirs:
                    mismatches.append(
                        f"pattern={pattern!r} text={text!r} "
                        f"ours={ours} re={theirs}"
                    )

        self.assertEqual(
            mismatches, [], f"共 {len(mismatches)} 处与 re 不一致:\n" + "\n".join(mismatches[:20])
        )

    def test_search_equivalence(self) -> None:
        """``search()`` 找到的区间必须与 ``re.search()`` 一致。"""
        mismatches: list[str] = []

        for pattern in PATTERNS:
            matcher = RegexMatcher(pattern)
            compiled = re.compile(pattern)
            for text in TEXTS:
                ours = matcher.search(text)
                found = compiled.search(text)
                theirs = (found.start(), found.end()) if found else None

                if ours != theirs:
                    mismatches.append(
                        f"pattern={pattern!r} text={text!r} ours={ours} re={theirs}"
                    )

        self.assertEqual(
            mismatches, [], f"共 {len(mismatches)} 处与 re 不一致:\n" + "\n".join(mismatches[:20])
        )

    def test_findall_equivalence(self) -> None:
        """``findall()`` 的匹配区间序列必须与 ``re.finditer()`` 一致。"""
        mismatches: list[str] = []

        for pattern in PATTERNS:
            matcher = RegexMatcher(pattern)
            compiled = re.compile(pattern)
            for text in TEXTS:
                ours = [(start, end) for start, end, _ in matcher.findall(text)]
                theirs = [(m.start(), m.end()) for m in compiled.finditer(text)]

                if ours != theirs:
                    mismatches.append(
                        f"pattern={pattern!r} text={text!r} ours={ours} re={theirs}"
                    )

        self.assertEqual(
            mismatches, [], f"共 {len(mismatches)} 处与 re 不一致:\n" + "\n".join(mismatches[:20])
        )

    def test_exhaustive_short_strings(self) -> None:
        """在短字符串上做穷举对拍 —— 覆盖所有长度为 0~3 的组合。"""
        alphabet = "ab"
        short_texts = [
            "".join(chars)
            for length in range(4)
            for chars in itertools.product(alphabet, repeat=length)
        ]

        patterns = ["a", "b", "ab", "a|b", "a*", "a+", "a?", "(a|b)*", ".", "[ab]", "[^a]"]
        mismatches: list[str] = []

        for pattern in patterns:
            matcher = RegexMatcher(pattern)
            compiled = re.compile(pattern)
            for text in short_texts:
                ours = matcher.match(text)
                theirs = compiled.fullmatch(text) is not None
                if ours != theirs:
                    mismatches.append(
                        f"pattern={pattern!r} text={text!r} ours={ours} re={theirs}"
                    )

        self.assertEqual(
            mismatches, [], f"共 {len(mismatches)} 处与 re 不一致:\n" + "\n".join(mismatches[:20])
        )


if __name__ == "__main__":
    unittest.main()
