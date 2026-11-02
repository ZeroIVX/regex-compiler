"""语法分析器测试。"""

from __future__ import annotations

import unittest

from regex_compiler.errors import ParserError
from regex_compiler.frontend.ast_nodes import (
    CharClassNode,
    CharNode,
    ConcatNode,
    DotNode,
    PlusNode,
    QuestionNode,
    StarNode,
    UnionNode,
)
from regex_compiler.frontend.parser import parse, print_ast


class TestParser(unittest.TestCase):
    """AST 结构正确性。"""

    def test_single_char(self) -> None:
        ast = parse("a")
        self.assertIsInstance(ast, CharNode)
        self.assertEqual(ast.char, "a")

    def test_concat(self) -> None:
        ast = parse("ab")
        self.assertIsInstance(ast, ConcatNode)
        self.assertIsInstance(ast.left, CharNode)
        self.assertEqual(ast.left.char, "a")
        self.assertIsInstance(ast.right, CharNode)
        self.assertEqual(ast.right.char, "b")

    def test_union(self) -> None:
        ast = parse("a|b")
        self.assertIsInstance(ast, UnionNode)
        self.assertIsInstance(ast.left, CharNode)
        self.assertIsInstance(ast.right, CharNode)

    def test_star(self) -> None:
        ast = parse("a*")
        self.assertIsInstance(ast, StarNode)
        self.assertIsInstance(ast.child, CharNode)

    def test_plus(self) -> None:
        ast = parse("a+")
        self.assertIsInstance(ast, PlusNode)
        self.assertIsInstance(ast.child, CharNode)

    def test_question(self) -> None:
        ast = parse("a?")
        self.assertIsInstance(ast, QuestionNode)
        self.assertIsInstance(ast.child, CharNode)

    def test_precedence(self) -> None:
        """``a|b*`` 应解析为 ``a|(b*)``。"""
        ast = parse("a|b*")
        self.assertIsInstance(ast, UnionNode)
        self.assertIsInstance(ast.left, CharNode)
        self.assertIsInstance(ast.right, StarNode)

    def test_parentheses(self) -> None:
        ast = parse("(a|b)*c")
        self.assertIsInstance(ast, ConcatNode)
        self.assertIsInstance(ast.left, StarNode)
        self.assertIsInstance(ast.left.child, UnionNode)
        self.assertIsInstance(ast.right, CharNode)

    def test_nested(self) -> None:
        ast = parse("a(b|c)*")
        self.assertIsInstance(ast, ConcatNode)
        self.assertIsInstance(ast.left, CharNode)
        self.assertIsInstance(ast.right, StarNode)
        self.assertIsInstance(ast.right.child, UnionNode)

    def test_empty(self) -> None:
        ast = parse("")
        self.assertIsInstance(ast, CharNode)
        self.assertEqual(ast.char, "")

    def test_multi_concat(self) -> None:
        """多字符连接为左结合链。"""
        ast = parse("abc")
        self.assertIsInstance(ast, ConcatNode)
        self.assertIsInstance(ast.left, ConcatNode)

    def test_multi_union(self) -> None:
        ast = parse("a|b|c")
        self.assertIsInstance(ast, UnionNode)
        self.assertIsInstance(ast.left, UnionNode)
        self.assertIsInstance(ast.right, CharNode)

    def test_star_plus_combined(self) -> None:
        ast = parse("a*+")
        self.assertIsInstance(ast, PlusNode)
        self.assertIsInstance(ast.child, StarNode)

    def test_question_star(self) -> None:
        ast = parse("a?*")
        self.assertIsInstance(ast, StarNode)
        self.assertIsInstance(ast.child, QuestionNode)

    def test_dot_node(self) -> None:
        ast = parse(".")
        self.assertIsInstance(ast, DotNode)

    def test_char_class_node(self) -> None:
        ast = parse("[a-z]")
        self.assertIsInstance(ast, CharClassNode)
        self.assertFalse(ast.charset.negated)

    def test_negated_char_class_node(self) -> None:
        ast = parse("[^a-z]")
        self.assertIsInstance(ast, CharClassNode)
        self.assertTrue(ast.charset.negated)

    def test_print_ast(self) -> None:
        text = print_ast(parse("(a|b)*c"))
        self.assertIn("Union", text)
        self.assertIn("Star", text)
        self.assertIn("Concat", text)


class TestParserErrors(unittest.TestCase):
    """语法错误处理。"""

    def test_unexpected_operator(self) -> None:
        with self.assertRaises(ParserError):
            parse("*a")

    def test_unmatched_paren(self) -> None:
        with self.assertRaises(ParserError):
            parse("(a")

    def test_extra_close_paren(self) -> None:
        with self.assertRaises(ParserError):
            parse("a)")

    def test_empty_parens(self) -> None:
        with self.assertRaises(ParserError):
            parse("()")

    def test_double_star(self) -> None:
        with self.assertRaises(ParserError):
            parse("**")

    def test_leading_pipe(self) -> None:
        with self.assertRaises(ParserError):
            parse("|a")


if __name__ == "__main__":
    unittest.main()
