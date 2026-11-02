"""语法分析器 —— 递归下降法把 Token 流转换为 AST。

文法（上下文无关，采用 LL(1) 递归下降实现）::

    Expr     → Concat ('|' Concat)*
    Concat   → Postfix+
    Postfix  → Atom ('*' | '+' | '?')*
    Atom     → CHAR | CHARCLASS | '.' | '(' Expr ')'
"""

from __future__ import annotations

from ..charset import CharClass
from ..errors import ParserError
from .ast_nodes import (
    ASTNode,
    CharClassNode,
    CharNode,
    ConcatNode,
    DotNode,
    PlusNode,
    QuestionNode,
    StarNode,
    UnionNode,
    collect_charsets,
)
from .lexer import Token, TokenType

__all__ = [
    "Parser",
    "ParserError",
    "collect_charsets",
    "parse",
    "parse_tokens",
    "print_ast",
]


class Parser:
    """递归下降语法分析器。"""

    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    # ---- Token 游标辅助 ----

    @property
    def current(self) -> Token:
        """当前 Token（不消费）。"""
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        """消费并返回当前 Token。"""
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def _check(self, expected: TokenType) -> bool:
        """判断当前 Token 类型是否为 ``expected``。"""
        return self.current.type == expected

    def _expect(self, expected: TokenType) -> Token:
        """断言当前 Token 类型，否则抛出 :class:`ParserError`。"""
        if self._check(expected):
            return self._advance()
        token = self.current
        raise ParserError(
            f"期望 {expected.name}，实际得到 {token.type.name} ({token.value!r})",
            token.position,
        )

    # ---- 文法规则实现 ----

    def parse_expr(self) -> ASTNode:
        """``Expr → Concat ('|' Concat)*`` —— 处理的优先级最低。"""
        left = self.parse_concat()
        while self._check(TokenType.PIPE):
            self._advance()
            right = self.parse_concat()
            left = UnionNode(left, right)
        return left

    def parse_concat(self) -> ASTNode:
        """``Concat → Postfix+`` —— 左结合的连接链。"""
        nodes: list[ASTNode] = []
        while True:
            token_type = self.current.type
            # 以下 Token 不能开始一个新的连接项
            if token_type in (TokenType.RPAREN, TokenType.PIPE, TokenType.EOF):
                break
            # 后缀运算符必须跟在原子之后，这里出现即为语法错误
            if token_type in (TokenType.STAR, TokenType.PLUS, TokenType.QUESTION):
                token = self.current
                raise ParserError(
                    f"后缀运算符 {token.value!r} 前面缺少原子",
                    token.position,
                )
            nodes.append(self.parse_postfix())

        if not nodes:
            token = self.current
            raise ParserError("表达式为空或出现意外的记号", token.position)

        result = nodes[0]
        for node in nodes[1:]:
            result = ConcatNode(result, node)
        return result

    def parse_postfix(self) -> ASTNode:
        """``Postfix → Atom ('*' | '+' | '?')*`` —— 后缀运算符可叠加。"""
        atom = self.parse_atom()
        while self.current.type in (TokenType.STAR, TokenType.PLUS, TokenType.QUESTION):
            op = self._advance()
            match op.type:
                case TokenType.STAR:
                    atom = StarNode(atom)
                case TokenType.PLUS:
                    atom = PlusNode(atom)
                case TokenType.QUESTION:
                    atom = QuestionNode(atom)
        return atom

    def parse_atom(self) -> ASTNode:
        """``Atom → CHAR | CHARCLASS | '.' | '(' Expr ')'``。"""
        token = self.current

        match token.type:
            case TokenType.CHAR:
                self._advance()
                return CharNode(token.value)

            case TokenType.CHARCLASS:
                self._advance()
                charset = token.charset or CharClass(frozenset())
                return CharClassNode(charset)

            case TokenType.DOT:
                self._advance()
                return DotNode()

            case TokenType.LPAREN:
                self._advance()
                expr = self.parse_expr()
                self._expect(TokenType.RPAREN)
                return expr

            case _:
                raise ParserError(
                    f"出现意外的记号 {token.type.name} ({token.value!r})",
                    token.position,
                )


def parse_tokens(tokens: list[Token]) -> ASTNode:
    """把 Token 流解析为 AST。"""
    parser = Parser(tokens)
    ast = parser.parse_expr()

    if not parser._check(TokenType.EOF):
        token = parser.current
        raise ParserError(
            f"存在未消耗的记号 {token.type.name} ({token.value!r})",
            token.position,
        )
    return ast


def parse(pattern: str) -> ASTNode:
    """便捷函数：把正则表达式字符串解析为 AST。

    空输入会得到一个匹配空串的 :class:`CharNode`。
    """
    from .lexer import lex

    tokens = lex(pattern)
    meaningful = [t for t in tokens if t.type is not TokenType.EOF]
    if not meaningful:
        return CharNode("")

    return parse_tokens(tokens)


def print_ast(node: ASTNode, indent: int = 0) -> str:
    """递归打印 AST 树结构。"""
    prefix = "  " * indent
    lines: list[str] = []

    match node:
        case CharNode(char):
            lines.append(f"{prefix}Char({char!r})")
        case DotNode():
            lines.append(f"{prefix}Dot")
        case CharClassNode(charset):
            lines.append(f"{prefix}CharClass({charset.label()})")
        case ConcatNode(left, right):
            lines.append(f"{prefix}Concat")
            lines.append(print_ast(left, indent + 1))
            lines.append(print_ast(right, indent + 1))
        case UnionNode(left, right):
            lines.append(f"{prefix}Union")
            lines.append(print_ast(left, indent + 1))
            lines.append(print_ast(right, indent + 1))
        case StarNode(child):
            lines.append(f"{prefix}Star")
            lines.append(print_ast(child, indent + 1))
        case PlusNode(child):
            lines.append(f"{prefix}Plus")
            lines.append(print_ast(child, indent + 1))
        case QuestionNode(child):
            lines.append(f"{prefix}Question")
            lines.append(print_ast(child, indent + 1))
        case _:
            lines.append(f"{prefix}Unknown({node!r})")

    return "\n".join(lines)
