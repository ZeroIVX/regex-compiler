"""词法分析器测试。"""

from __future__ import annotations

import unittest

from regex_compiler.errors import LexerError
from regex_compiler.frontend.lexer import Lexer, TokenType, lex


class TestLexer(unittest.TestCase):
    """Token 流的切分正确性。"""

    def test_single_char(self) -> None:
        tokens = lex("a")
        self.assertEqual(len(tokens), 2)  # CHAR + EOF
        self.assertIs(tokens[0].type, TokenType.CHAR)
        self.assertEqual(tokens[0].value, "a")

    def test_simple_concat(self) -> None:
        tokens = lex("ab")
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[0].value, "a")
        self.assertEqual(tokens[1].value, "b")
        self.assertIs(tokens[2].type, TokenType.EOF)

    def test_operators(self) -> None:
        tokens = lex("a|b*c+?")
        types = [t.type for t in tokens[:-1]]
        self.assertEqual(
            types,
            [
                TokenType.CHAR,
                TokenType.PIPE,
                TokenType.CHAR,
                TokenType.STAR,
                TokenType.CHAR,
                TokenType.PLUS,
                TokenType.QUESTION,
            ],
        )

    def test_parentheses(self) -> None:
        types = [t.type for t in lex("(a)")[:-1]]
        self.assertEqual(types, [TokenType.LPAREN, TokenType.CHAR, TokenType.RPAREN])

    def test_dot(self) -> None:
        types = [t.type for t in lex("a.b")[:-1]]
        self.assertEqual(types, [TokenType.CHAR, TokenType.DOT, TokenType.CHAR])

    def test_escaped_chars(self) -> None:
        chars = [t.value for t in lex(r"a\*b") if t.type is TokenType.CHAR]
        self.assertEqual(chars, ["a", "*", "b"])

    def test_ignore_whitespace(self) -> None:
        chars = [t.value for t in lex("a | b") if t.type is TokenType.CHAR]
        self.assertEqual(chars, ["a", "b"])

    def test_position_tracking(self) -> None:
        positions = [t.position for t in lex("abc")]
        self.assertEqual(positions, [0, 1, 2, 3])

    def test_empty_pattern(self) -> None:
        tokens = lex("")
        self.assertEqual(len(tokens), 1)
        self.assertIs(tokens[0].type, TokenType.EOF)

    def test_complex_pattern(self) -> None:
        types = [t.type for t in lex("(a|b)*c+")[:-1]]
        self.assertEqual(
            types,
            [
                TokenType.LPAREN,
                TokenType.CHAR,
                TokenType.PIPE,
                TokenType.CHAR,
                TokenType.RPAREN,
                TokenType.STAR,
                TokenType.CHAR,
                TokenType.PLUS,
            ],
        )


class TestCharClassLexing(unittest.TestCase):
    """字符类的词法分析。"""

    def test_simple_class(self) -> None:
        tokens = lex("[abc]")
        self.assertIs(tokens[0].type, TokenType.CHARCLASS)
        self.assertEqual(tokens[0].charset.chars, frozenset("abc"))
        self.assertFalse(tokens[0].charset.negated)

    def test_range_class(self) -> None:
        tokens = lex("[a-c]")
        self.assertEqual(tokens[0].charset.chars, frozenset("abc"))

    def test_mixed_class(self) -> None:
        tokens = lex("[a-cx]")
        self.assertEqual(tokens[0].charset.chars, frozenset("abcx"))

    def test_negated_class(self) -> None:
        tokens = lex("[^a-z]")
        self.assertTrue(tokens[0].charset.negated)
        self.assertEqual(tokens[0].charset.chars, frozenset("abcdefghijklmnopqrstuvwxyz"))

    def test_escaped_bracket_in_class(self) -> None:
        tokens = lex(r"[\]]")
        self.assertEqual(tokens[0].charset.chars, frozenset("]"))

    def test_class_with_escape(self) -> None:
        tokens = lex(r"[a\-z]")
        self.assertIn("-", tokens[0].charset.chars)
        self.assertIn("a", tokens[0].charset.chars)
        self.assertIn("z", tokens[0].charset.chars)


class TestLexerErrors(unittest.TestCase):
    """词法错误处理。"""

    def test_backslash_at_end(self) -> None:
        with self.assertRaises(LexerError):
            lex("a\\")

    def test_char_class_backslash_end(self) -> None:
        with self.assertRaises(LexerError):
            lex("[\\]")

    def test_unclosed_char_class(self) -> None:
        with self.assertRaises(LexerError):
            lex("[abc")


if __name__ == "__main__":
    unittest.main()
