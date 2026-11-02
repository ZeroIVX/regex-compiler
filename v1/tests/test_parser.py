"""测试套件 —— 语法分析器测试"""

from src.lexer import lex, TokenType
from src.parser import parse, Parser, ParserError
from src.ast_nodes import (
    CharNode, DotNode, ConcatNode, UnionNode,
    StarNode, PlusNode, QuestionNode, CharClassNode,
)


class TestParser:
    def test_single_char(self):
        ast = parse("a")
        assert isinstance(ast, CharNode)
        assert ast.char == "a"

    def test_concat(self):
        ast = parse("ab")
        assert isinstance(ast, ConcatNode)
        assert isinstance(ast.left, CharNode)
        assert ast.left.char == "a"
        assert isinstance(ast.right, CharNode)
        assert ast.right.char == "b"

    def test_union(self):
        ast = parse("a|b")
        assert isinstance(ast, UnionNode)
        assert ast.left.char == "a"
        assert ast.right.char == "b"

    def test_star(self):
        ast = parse("a*")
        assert isinstance(ast, StarNode)
        assert isinstance(ast.child, CharNode)
        assert ast.child.char == "a"

    def test_plus(self):
        ast = parse("a+")
        assert isinstance(ast, PlusNode)
        assert isinstance(ast.child, CharNode)

    def test_question(self):
        ast = parse("a?")
        assert isinstance(ast, QuestionNode)
        assert isinstance(ast.child, CharNode)

    def test_precedence(self):
        # a|b* 应该解析为 a|(b*)
        ast = parse("a|b*")
        assert isinstance(ast, UnionNode)
        assert isinstance(ast.left, CharNode)
        assert isinstance(ast.right, StarNode)

    def test_parentheses(self):
        ast = parse("(a|b)*c")
        assert isinstance(ast, ConcatNode)
        # left should be Star of Union
        assert isinstance(ast.left, StarNode)
        assert isinstance(ast.left.child, UnionNode)
        assert isinstance(ast.right, CharNode)

    def test_nested(self):
        ast = parse("a(b|c)*")
        assert isinstance(ast, ConcatNode)
        assert isinstance(ast.left, CharNode)
        star = ast.right
        assert isinstance(star, StarNode)
        assert isinstance(star.child, UnionNode)

    def test_empty(self):
        ast = parse("")
        assert isinstance(ast, CharNode)
        assert ast.char == ""

    def test_multi_concat(self):
        ast = parse("abc")
        assert isinstance(ast, ConcatNode)
        # 左结合: (a·b)·c
        assert isinstance(ast.left, ConcatNode)

    def test_multi_union(self):
        ast = parse("a|b|c")
        assert isinstance(ast, UnionNode)
        assert isinstance(ast.left, UnionNode)
        assert isinstance(ast.right, CharNode)

    def test_star_plus_combined(self):
        ast = parse("a*+")
        assert isinstance(ast, PlusNode)
        assert isinstance(ast.child, StarNode)

    def test_question_star(self):
        ast = parse("a?*")
        assert isinstance(ast, StarNode)
        assert isinstance(ast.child, QuestionNode)


class TestParserErrors:
    def test_unexpected_operator(self):
        try:
            parse("*a")
            assert False, "Expected ParserError"
        except ParserError:
            pass

    def test_unmatched_paren(self):
        try:
            parse("(a")
            assert False, "Expected ParserError"
        except ParserError:
            pass

    def test_extra_close_paren(self):
        try:
            parse("a)")
            assert False, "Expected ParserError"
        except ParserError:
            pass

    def test_empty_parens(self):
        try:
            parse("()")
            assert False, "Expected ParserError"
        except ParserError:
            pass

    def test_double_star(self):
        try:
            parse("**")
            assert False, "Expected ParserError"
        except ParserError:
            pass
