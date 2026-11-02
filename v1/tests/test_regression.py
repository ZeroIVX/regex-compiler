"""回归测试 —— 针对 v1 修复项的行为验证

这三组用例覆盖了本版修复的语义缺陷：
1. `.` 通配符此前因字母表未收录而完全失效
2. `[^...]` 取反字符类此前语义反转（等价于正向类）
3. `a+` 正闭包构造函数复用了同一片段，状态冗余
"""

from src.matcher import RegexMatcher


class TestWildcard:
    """`.` 通配符语义"""

    def test_match_any_char(self):
        m = RegexMatcher(".")
        assert m.match("x")
        assert m.match("5")
        assert m.match("A")

    def test_requires_exactly_one_char(self):
        m = RegexMatcher(".")
        assert not m.match("")
        assert not m.match("ab")

    def test_excludes_newline(self):
        """与 Python re 一致：`.` 不匹配换行"""
        assert not RegexMatcher(".").match("\n")

    def test_in_sequence(self):
        m = RegexMatcher("a.b")
        assert m.match("axb")
        assert m.match("a b")
        assert not m.match("ab")
        assert not m.match("axxb")


class TestNegatedClass:
    """`[^...]` 取反字符类语义"""

    def test_negated_range(self):
        m = RegexMatcher("[^a-z]")
        assert m.match("5")
        assert m.match("A")
        assert not m.match("a")
        assert not m.match("z")

    def test_positive_range_unaffected(self):
        m = RegexMatcher("[a-z]")
        assert m.match("b")
        assert not m.match("B")
        assert not m.match("5")

    def test_negation_with_literal(self):
        m = RegexMatcher("[^a-z]a")
        assert m.match("5a")
        assert not m.match("aa")

    def test_literal_charset_inside_class(self):
        m = RegexMatcher("[abc]+")
        assert m.match("abc")
        assert m.match("cba")
        assert not m.match("d")


class TestPlusClosure:
    """`+` 正闭包必须至少匹配一次"""

    def test_plus_rejects_empty(self):
        assert not RegexMatcher("a+").match("")

    def test_plus_accepts_one_or_more(self):
        m = RegexMatcher("a+")
        assert m.match("a")
        assert m.match("aaa")

    def test_star_accepts_empty(self):
        assert RegexMatcher("a*").match("")


class TestKnownLimitation:
    """记录本版的已知局限（详见 README「已知局限」）"""

    def test_universe_is_ascii_only(self):
        """字符全集限定为可打印 ASCII 与常见控制字符，
        因此全集之外的字符（如中文）不会被 `.` 匹配。"""
        assert RegexMatcher(".").match("x")
        assert not RegexMatcher(".").match("中")
