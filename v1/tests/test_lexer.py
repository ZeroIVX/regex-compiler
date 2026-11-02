"""测试套件 —— 词法分析器测试"""

from src.lexer import Lexer, TokenType, lex, LexerError


class TestLexer:
    def test_single_char(self):
        tokens = lex("a")
        assert len(tokens) == 2  # CHAR + EOF
        assert tokens[0].type == TokenType.CHAR
        assert tokens[0].value == "a"

    def test_simple_concat(self):
        tokens = lex("ab")
        assert len(tokens) == 3
        assert tokens[0].value == "a"
        assert tokens[1].value == "b"
        assert tokens[2].type == TokenType.EOF

    def test_operators(self):
        tokens = lex("a|b*c+?")
        types = [t.type for t in tokens[:-1]]  # skip EOF
        assert types == [
            TokenType.CHAR, TokenType.PIPE, TokenType.CHAR,
            TokenType.STAR, TokenType.CHAR, TokenType.PLUS,
            TokenType.QUESTION,
        ]

    def test_parentheses(self):
        tokens = lex("(a)")
        types = [t.type for t in tokens[:-1]]
        assert types == [TokenType.LPAREN, TokenType.CHAR, TokenType.RPAREN]

    def test_dot(self):
        tokens = lex("a.b")
        types = [t.type for t in tokens[:-1]]
        assert types == [TokenType.CHAR, TokenType.DOT, TokenType.CHAR]

    def test_escaped_chars(self):
        tokens = lex(r"a\*b")
        chars = [t.value for t in tokens if t.type == TokenType.CHAR]
        assert chars == ["a", "*", "b"]

    def test_ignore_whitespace(self):
        tokens = lex("a | b")
        chars = [t.value for t in tokens if t.type == TokenType.CHAR]
        assert chars == ["a", "b"]

    def test_position_tracking(self):
        tokens = lex("abc")
        positions = [t.position for t in tokens]
        assert positions == [0, 1, 2, 3]

    def test_empty_pattern(self):
        tokens = lex("")
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.EOF

    def test_complex_pattern(self):
        tokens = lex("(a|b)*c+")
        types = [t.type for t in tokens[:-1]]
        expected = [
            TokenType.LPAREN, TokenType.CHAR, TokenType.PIPE,
            TokenType.CHAR, TokenType.RPAREN, TokenType.STAR,
            TokenType.CHAR, TokenType.PLUS,
        ]
        assert types == expected


class TestLexerErrors:
    def test_backslash_at_end(self):
        try:
            lex("a\\")
            assert False, "Expected LexerError"
        except LexerError:
            pass

    def test_char_class_backslash_end(self):
        try:
            lex("[\\]")
            assert False, "Expected LexerError"
        except LexerError:
            pass
