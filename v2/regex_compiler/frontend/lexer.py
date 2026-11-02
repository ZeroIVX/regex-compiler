"""词法分析器 —— 把正则表达式字符串切分为 Token 流。

支持的语法元素：

============ ==========================================
记号         说明
============ ==========================================
``CHAR``     字面字符（可由 ``\\`` 转义）
``.``        通配符（除换行外的任意字符）
``[a-z]``    字符类，支持范围、多个字符与 ``^`` 取反
``(`` ``)``  分组
``*`` ``+``  ``?``  后缀运算符
``|``        选择运算符
============ ==========================================
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from ..charset import CharClass
from ..errors import LexerError


class TokenType(Enum):
    """Token 类型枚举。"""

    CHAR = auto()        # 字面字符
    CHARCLASS = auto()   # 字符类 [a-z] / [^a-z]
    LPAREN = auto()      # (
    RPAREN = auto()      # )
    STAR = auto()        # *
    PLUS = auto()        # +
    QUESTION = auto()    # ?
    PIPE = auto()        # |
    DOT = auto()         # .
    EOF = auto()         # 输入结束


@dataclass(frozen=True)
class Token:
    """一个词法单元。

    Attributes:
        type: Token 类型。
        value: 记号文本（``CHARCLASS`` 时为可读描述）。
        position: 在源字符串中的起始下标。
        charset: 仅 ``CHARCLASS`` 有效，承载字符类语义。
    """

    type: TokenType
    value: str
    position: int
    charset: CharClass | None = None

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, pos={self.position})"


# 需要转义的元字符
META_CHARS = frozenset("*+?|()[]")


class Lexer:
    """正则表达式词法分析器。"""

    def __init__(self, pattern: str) -> None:
        self.pattern = pattern
        self.pos = 0

    # ---- 字符游标辅助 ----

    def _current(self) -> str | None:
        """返回当前字符，超出范围返回 ``None``。"""
        if self.pos < len(self.pattern):
            return self.pattern[self.pos]
        return None

    def _advance(self) -> None:
        """前进一个字符。"""
        self.pos += 1

    def _peek(self, offset: int = 1) -> str | None:
        """查看相对当前位置偏移 ``offset`` 的字符，不移动游标。"""
        index = self.pos + offset
        if 0 <= index < len(self.pattern):
            return self.pattern[index]
        return None

    # ---- 主流程 ----

    def tokenize(self) -> list[Token]:
        """把输入字符串转换为 Token 列表（末尾带 ``EOF``）。"""
        tokens: list[Token] = []
        while self.pos < len(self.pattern):
            ch = self.pattern[self.pos]
            pos = self.pos

            if ch == "\\":
                tokens.append(self._lex_escape())
            elif ch == "[":
                tokens.append(self._lex_char_class())
            elif ch == "(":
                self._advance()
                tokens.append(Token(TokenType.LPAREN, "(", pos))
            elif ch == ")":
                self._advance()
                tokens.append(Token(TokenType.RPAREN, ")", pos))
            elif ch == "*":
                self._advance()
                tokens.append(Token(TokenType.STAR, "*", pos))
            elif ch == "+":
                self._advance()
                tokens.append(Token(TokenType.PLUS, "+", pos))
            elif ch == "?":
                self._advance()
                tokens.append(Token(TokenType.QUESTION, "?", pos))
            elif ch == "|":
                self._advance()
                tokens.append(Token(TokenType.PIPE, "|", pos))
            elif ch == ".":
                self._advance()
                tokens.append(Token(TokenType.DOT, ".", pos))
            elif ch.isspace():
                self._advance()  # 跳过空白
            else:
                self._advance()
                tokens.append(Token(TokenType.CHAR, ch, pos))

        tokens.append(Token(TokenType.EOF, "", self.pos))
        return tokens

    def _lex_escape(self) -> Token:
        """处理反斜杠转义，返回一个字面字符 Token。"""
        start = self.pos
        self._advance()
        escaped = self._current()
        if escaped is None:
            raise LexerError("反斜杠后缺少字符", start)
        self._advance()
        return Token(TokenType.CHAR, escaped, start)

    def _lex_char_class(self) -> Token:
        """解析 ``[...]`` 字符类，构造带取反语义的 :class:`CharClass`。"""
        start = self.pos
        self._advance()  # 跳过 '['

        negated = False
        if self._current() == "^":
            negated = True
            self._advance()

        chars: set[str] = set()
        prev_char: str | None = None

        while self._current() is not None and self._current() != "]":
            ch = self._current()
            pos = self.pos

            if ch == "\\":
                self._advance()
                escaped = self._current()
                if escaped is None:
                    raise LexerError("字符类中反斜杠后缺少字符", pos)
                chars.add(escaped)
                prev_char = escaped
                self._advance()
            elif ch == "-" and prev_char is not None and self._peek() not in (None, "]"):
                # 形如 a-z 的范围
                self._advance()
                end_ch = self._current()
                if end_ch == "\\":
                    self._advance()
                    end_ch = self._current()
                    if end_ch is None:
                        raise LexerError("字符类范围中反斜杠后缺少字符", pos)
                if end_ch is not None and ord(end_ch) >= ord(prev_char):
                    chars.update(chr(c) for c in range(ord(prev_char), ord(end_ch) + 1))
                elif end_ch is not None:
                    # 逆序范围按字面处理
                    chars.add(prev_char)
                    chars.add("-")
                    chars.add(end_ch)
                prev_char = end_ch
                self._advance()
            else:
                chars.add(ch)
                prev_char = ch
                self._advance()

        if self._current() != "]":
            raise LexerError("字符类缺少右方括号 ']'", start)

        self._advance()  # 跳过 ']'

        charset = CharClass(frozenset(chars), negated)
        return Token(TokenType.CHARCLASS, charset.label(), start, charset)


def lex(pattern: str) -> list[Token]:
    """便捷函数：对正则表达式字符串进行词法分析。"""
    return Lexer(pattern).tokenize()
