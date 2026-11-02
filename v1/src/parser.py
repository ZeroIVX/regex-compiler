"""语法分析器 —— 递归下降法将 Token 流转换为 AST

语法规则：
    Expr     → Concat ('|' Concat)*
    Concat   → Postfix+
    Postfix  → Atom ('*' | '+' | '?' | ε)
    Atom     → CHAR | '.' | '(' Expr ')' | '[' CharClass ']'
"""

from .lexer import Token, TokenType, LexerError
from .ast_nodes import (
    ASTNode, CharNode, DotNode, ConcatNode,
    UnionNode, StarNode, PlusNode, QuestionNode, CharClassNode,
)


class ParserError(Exception):
    """语法分析错误"""
    def __init__(self, msg: str, token: Token | None = None):
        pos_info = f" at position {token.position}" if token else ""
        super().__init__(f"Parser error{pos_info}: {msg}")
        self.token = token


class Parser:
    """递归下降语法分析器"""

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def _current(self) -> Token:
        """返回当前 Token"""
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        """消费并返回当前 Token，前进到下一个"""
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _check(self, expected: TokenType) -> bool:
        """检查当前 Token 类型是否匹配"""
        return self._current().type == expected

    def _expect(self, expected: TokenType) -> Token:
        """期望当前 Token 为指定类型，否则报错"""
        if self._check(expected):
            return self._advance()
        tok = self._current()
        raise ParserError(
            f"Expected {expected.name}, got {tok.type.name} ({tok.value!r})",
            tok,
        )

    # ---- 语法规则实现 ----

    def parse_expr(self) -> ASTNode:
        """Expr → Concat ('|' Concat)*"""
        left = self.parse_concat()
        while self._check(TokenType.PIPE):
            self._advance()
            right = self.parse_concat()
            left = UnionNode(left, right)
        return left

    def parse_concat(self) -> ASTNode:
        """Concat → Postfix+"""
        nodes: list[ASTNode] = []
        while True:
            tok_type = self._current().type
            # 以下 Token 类型不能开始一个新的 concat 项
            if tok_type in (TokenType.RPAREN, TokenType.PIPE, TokenType.EOF):
                break
            # 后缀运算符不应该出现在这里（它们已经在上层处理了）
            if tok_type in (TokenType.STAR, TokenType.PLUS, TokenType.QUESTION):
                tok = self._current()
                raise ParserError(
                    f"Unexpected postfix operator '{tok.value}' without atom",
                    tok,
                )
            nodes.append(self.parse_postfix())

        if not nodes:
            tok = self._current()
            raise ParserError(
                "Empty expression or unexpected token",
                tok,
            )

        # 左结合构建连接链
        result = nodes[0]
        for node in nodes[1:]:
            result = ConcatNode(result, node)
        return result

    def parse_postfix(self) -> ASTNode:
        """Postfix → Atom ('*' | '+' | '?' | ε)"""
        atom = self.parse_atom()
        while self._current().type in (TokenType.STAR, TokenType.PLUS, TokenType.QUESTION):
            op = self._advance()
            if op.type == TokenType.STAR:
                atom = StarNode(atom)
            elif op.type == TokenType.PLUS:
                atom = PlusNode(atom)
            elif op.type == TokenType.QUESTION:
                atom = QuestionNode(atom)
        return atom

    def parse_atom(self) -> ASTNode:
        """Atom → CHAR | CHARCLASS | '.' | '(' Expr ')'"""
        tok = self._current()

        if tok.type == TokenType.CHARCLASS:
            self._advance()
            return CharClassNode(tok.charset or frozenset())

        elif tok.type == TokenType.CHAR:
            self._advance()
            return CharNode(tok.value)

        elif tok.type == TokenType.DOT:
            self._advance()
            return DotNode()

        elif tok.type == TokenType.LPAREN:
            self._advance()
            expr = self.parse_expr()
            self._expect(TokenType.RPAREN)
            return expr

        else:
            raise ParserError(
                f"Unexpected token: {tok.type.name} ({tok.value!r})",
                tok,
            )


def parse(pattern: str) -> ASTNode:
    """便捷函数：将正则表达式字符串解析为 AST

    先进行词法分析，然后语法分析。
    对于空输入返回一个匹配空串的节点。
    """
    from .lexer import lex

    tokens = lex(pattern)
    # 去除 EOF
    tokens_without_eof = [t for t in tokens if t.type != TokenType.EOF]
    if not tokens_without_eof:
        # 空正则，匹配空字符串
        return CharNode('')

    parser = Parser(tokens)
    ast = parser.parse_expr()

    # 检查是否有未消耗的 Token（非 EOF）
    remaining = parser._current()
    if remaining.type != TokenType.EOF:
        raise ParserError(
            f"Unexpected trailing token: {remaining.type.name} ({remaining.value!r})",
            remaining,
        )
    return ast


def print_ast(node: ASTNode, indent: int = 0) -> str:
    """递归打印 AST 树结构"""
    prefix = "  " * indent
    lines: list[str] = []

    match node:
        case CharNode(char):
            lines.append(f"{prefix}Char({char!r})")
        case DotNode():
            lines.append(f"{prefix}Dot")
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
        case CharClassNode(chars):
            lines.append(f"{prefix}CharClass([{''.join(sorted(chars))}])")
        case _:
            lines.append(f"{prefix}Unknown({node})")

    return "\n".join(lines)
