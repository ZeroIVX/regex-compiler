"""集成测试 —— 端到端正则匹配测试"""

from src.matcher import RegexMatcher


class TestRegexMatcher:
    def test_match_single_char(self):
        m = RegexMatcher("a")
        assert m.match("a")
        assert not m.match("b")
        assert not m.match("aa")

    def test_match_concat(self):
        m = RegexMatcher("abc")
        assert m.match("abc")
        assert not m.match("ab")
        assert not m.match("abcd")
        assert not m.match("abd")

    def test_match_union(self):
        m = RegexMatcher("a|b")
        assert m.match("a")
        assert m.match("b")
        assert not m.match("c")
        assert not m.match("ab")

    def test_match_star(self):
        m = RegexMatcher("a*")
        assert m.match("")
        assert m.match("a")
        assert m.match("aa")
        assert m.match("aaa")
        assert not m.match("b")
        assert not m.match("aab")

    def test_match_plus(self):
        m = RegexMatcher("a+")
        assert not m.match("")
        assert m.match("a")
        assert m.match("aa")
        assert not m.match("b")

    def test_match_question(self):
        m = RegexMatcher("a?")
        assert m.match("")
        assert m.match("a")
        assert not m.match("aa")
        assert not m.match("b")

    def test_match_complex(self):
        m = RegexMatcher("a(b|c)*d")
        assert m.match("ad")
        assert m.match("abd")
        assert m.match("acd")
        assert m.match("abcd")      # a + (b|c)* [b,c] + d
        assert m.match("abcbcd")    # a + (b|c)* [b,c,b,c] + d
        assert not m.match("a")
        assert not m.match("abc")   # missing trailing d

    def test_match_classic(self):
        m = RegexMatcher("(a|b)*abb")
        assert m.match("abb")
        assert m.match("aabb")
        assert m.match("babb")
        assert m.match("ababb")
        assert not m.match("aba")
        assert not m.match("abba")
        assert not m.match("bbab")

    def test_match_nested(self):
        m = RegexMatcher("((a|b)*c)*")
        assert m.match("")
        assert m.match("c")
        assert m.match("ac")
        assert m.match("bc")
        assert m.match("acbc")
        assert m.match("aabbcc")

    def test_match_with_escape(self):
        m = RegexMatcher(r"a\*b")
        assert m.match("a*b")
        assert not m.match("ab")
        assert not m.match("aaab")

    def test_match_long_string(self):
        m = RegexMatcher("a+b+c+")
        assert m.match("abc")
        assert m.match("aaabbbccc")
        assert not m.match("cba")


class TestSearch:
    def test_search_simple(self):
        m = RegexMatcher("ab")
        result = m.search("xxabxx")
        assert result == (2, 4)

    def test_search_not_found(self):
        m = RegexMatcher("ab")
        assert m.search("aaaa") is None

    def test_search_at_start(self):
        m = RegexMatcher("ab")
        result = m.search("abxx")
        assert result == (0, 2)

    def test_search_at_end(self):
        m = RegexMatcher("ab")
        result = m.search("xxab")
        assert result == (2, 4)


class TestFindAll:
    def test_findall_simple(self):
        m = RegexMatcher("ab")
        results = m.findall("ababab")
        assert len(results) == 3

    def test_findall_aa(self):
        m = RegexMatcher("aa")
        results = m.findall("aaaa")
        assert len(results) == 2

    def test_findall_none(self):
        m = RegexMatcher("ab")
        results = m.findall("cccc")
        assert len(results) == 0


class TestEdgeCases:
    def test_empty_pattern(self):
        m = RegexMatcher("")
        assert m.match("")

    def test_special_chars(self):
        m = RegexMatcher(r"a\|b")
        assert m.match("a|b")

    def test_long_pattern(self):
        m = RegexMatcher("a" * 10)
        assert m.match("a" * 10)
        assert not m.match("a" * 9)


class TestPipelineInfo:
    def test_info_output(self):
        m = RegexMatcher("(a|b)*abb")
        info = m.print_info()
        assert "Pattern:" in info
        assert "NFA States:" in info
        assert "DFA States:" in info
        assert "Min DFA States:" in info
