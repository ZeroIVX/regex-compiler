"""词法分析器 —— 将正则表达式字符串转换为 Token 流"""

from dataclasses import dataclass
from enum import Enum, auto


# 字符全集：可打印 ASCII 与常见控制字符。
#
# 本版采用「字符集展开」策略实现 `.` 与 `[^...]`：把通配符与取反字符类
# 直接展开成具体字符，因此需要一个有限全集作为展开基准。
# 代价是全集之外的字符（如中文）无法被 `.` 匹配 —— 这是本版本的已知局限。
UNIVERSE: frozenset[str] = frozenset(
    [chr(code) for code in range(0x20, 0x7F)] + ["\t", "\n", "\r"]
)


class TokenType(Enum):
    CHAR = auto()       # 普通字符
    CHARCLASS = auto()  # 字符类 [a-z] / [^a-z]
    LPAREN = auto()     # (
    RPAREN = auto()     # )
    STAR = auto()       # *
    PLUS = auto()       # +
    QUESTION = auto()   # ?
    PIPE = auto()       # |
    DOT = auto()        # .
    EOF = auto()        # 输入结束


@dataclass
class Token:
    type: TokenType
    value: str
    position: int  # 在源字符串中的位置
    charset: frozenset[str] | None = None  # 仅 CHARCLASS 有效：展开后的字符集

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, pos={self.position})"


# 需要转义的元字符
META_CHARS = {'*', '+', '?', '|', '(', ')', '.', '[', ']'}


class LexerError(Exception):
    """词法分析错误"""
    def __init__(self, msg: str, position: int):
        super().__init__(f"Lexer error at position {position}: {msg}")
        self.position = position


def describe_charset(chars) -> str:
    """把字符集压缩成 a-z,0-9 形式的紧凑描述"""
    items = sorted(chars)
    if not items:
        return "(空)"

    parts = []
    start = prev = items[0]
    for ch in items[1:]:
        if ord(ch) == ord(prev) + 1:
            prev = ch
            continue
        parts.append(start if start == prev else f"{start}-{prev}")
        start = prev = ch
    parts.append(start if start == prev else f"{start}-{prev}")
    return ",".join(parts)


class Lexer:
    """正则表达式词法分析器"""

    def __init__(self, pattern: str):
        self.pattern = pattern
        self.pos = 0

    def _current(self) -> str | None:
        """返回当前字符，超出范围返回 None"""
        if self.pos < len(self.pattern):
            return self.pattern[self.pos]
        return None

    def _advance(self) -> None:
        """前进一个字符"""
        self.pos += 1

    def _peek_next(self) -> str | None:
        """查看下一个字符但不移动"""
        if self.pos + 1 < len(self.pattern):
            return self.pattern[self.pos + 1]
        return None

    def tokenize(self) -> list[Token]:
        """将输入字符串转换为 Token 列表"""
        tokens: list[Token] = []
        while self.pos < len(self.pattern):
            ch = self._current()
            pos = self.pos

            if ch == '\\':
                self._advance()
                next_ch = self._current()
                if next_ch is None:
                    raise LexerError("Unexpected end after '\\'", pos)
                tokens.append(Token(TokenType.CHAR, next_ch, pos))
                self._advance()
            elif ch == '(':
                tokens.append(Token(TokenType.LPAREN, '(', pos))
                self._advance()
            elif ch == ')':
                tokens.append(Token(TokenType.RPAREN, ')', pos))
                self._advance()
            elif ch == '*':
                tokens.append(Token(TokenType.STAR, '*', pos))
                self._advance()
            elif ch == '+':
                tokens.append(Token(TokenType.PLUS, '+', pos))
                self._advance()
            elif ch == '?':
                tokens.append(Token(TokenType.QUESTION, '?', pos))
                self._advance()
            elif ch == '|':
                tokens.append(Token(TokenType.PIPE, '|', pos))
                self._advance()
            elif ch == '.':
                tokens.append(Token(TokenType.DOT, '.', pos))
                self._advance()
            elif ch == '[':
                tokens.append(self._lex_char_class())
            elif ch.isspace():
                self._advance()  # 跳过空白
            else:
                tokens.append(Token(TokenType.CHAR, ch, pos))
                self._advance()

        tokens.append(Token(TokenType.EOF, '', self.pos))
        return tokens

    def _lex_char_class(self) -> Token:
        """解析 [...] 字符类，直接展开为具体字符集

        取反形式 `[^...]` 展开为「全集减去被排除字符」，
        因此后续的 NFA 构造无需再关心取反语义。
        """
        start_pos = self.pos
        self._advance()  # 跳过 [

        negated = False
        if self._current() == '^':
            negated = True
            self._advance()

        chars: set[str] = set()
        prev_char: str | None = None

        while self._current() is not None and self._current() != ']':
            ch = self._current()
            pos = self.pos

            if ch == '\\':
                self._advance()
                escaped = self._current()
                if escaped is None:
                    raise LexerError("Unexpected end in char class", pos)
                chars.add(escaped)
                prev_char = escaped
                self._advance()
            elif ch == '-' and prev_char is not None and self._peek_next() not in (None, ']'):
                # 形如 a-z 的字符范围
                self._advance()
                end_ch = self._current()
                if end_ch == '\\':
                    self._advance()
                    end_ch = self._current()
                    if end_ch is None:
                        raise LexerError("Unexpected end in char class range", pos)
                if end_ch is not None and ord(end_ch) >= ord(prev_char):
                    for code in range(ord(prev_char), ord(end_ch) + 1):
                        chars.add(chr(code))
                elif end_ch is not None:
                    # 逆序范围按字面处理
                    chars.add('-')
                    chars.add(end_ch)
                prev_char = end_ch
                if end_ch is not None:
                    self._advance()
            else:
                chars.add(ch)
                prev_char = ch
                self._advance()

        if self._current() != ']':
            raise LexerError("Unclosed character class", start_pos)

        self._advance()  # 跳过 ]

        # 取反：全集减去被排除字符；否则就是字符类本身
        charset = frozenset(UNIVERSE - chars) if negated else frozenset(chars)
        label = ("^" if negated else "") + describe_charset(chars)
        return Token(TokenType.CHARCLASS, label, start_pos, charset)


def lex(pattern: str) -> list[Token]:
    """便捷函数：对正则表达式字符串进行词法分析"""
    return Lexer(pattern).tokenize()
